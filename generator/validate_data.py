#!/usr/bin/env python3
"""
Lloyds synthetic data | validation report
Reads the generated Parquet files month by month (low memory) and prints the
business stories the dashboard must reveal, so you can check them before loading to Azure.

Usage:  python validate_data.py            (default folder ../data)
        python validate_data.py --data C:\\Portfolio\\Lloyds\\data
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


def read_month_files(root: Path, source: str, table: str, cols):
    for f in sorted((root / source / table).rglob("*.parquet")):
        yield pq.read_table(f, columns=cols).to_pandas()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent.parent / "data"))
    root = Path(ap.parse_args().data)
    man = json.loads((root / "manifest.json").read_text())
    pd.set_option("display.width", 200, "display.max_columns", 30, "display.float_format", "{:,.2f}".format)

    print("=" * 90)
    print(f"ROW COUNTS | scale {man['scale']} | {man['total_rows']:,} rows | {man['total_bytes'] / 1e6:,.0f} MB")
    print("=" * 90)
    rc = pd.DataFrame(man["files"]).groupby(["source", "table"]).agg(files=("file", "count"), rows=("rows", "sum"),
                                                                     mb=("bytes", lambda b: b.sum() / 1e6))
    print(rc.to_string())

    # ---------------- deposits ----------------
    dep = []
    for df in read_month_files(root, "corebanking", "deposit_balance_monthly",
                               ["month_end", "product_id", "eom_balance", "interest_expense", "ftp_credit", "fee_income"]):
        dep.append(df.groupby(["month_end", "product_id"]).sum().reset_index())
    dep = pd.concat(dep)
    dep["year"] = pd.to_datetime(dep["month_end"]).dt.year
    # ---------------- loans ----------------
    ln = []
    for df in read_month_files(root, "lending", "loan_performance_monthly",
                               ["month_end", "product_id", "balance_eom", "interest_income", "ftp_charge", "fee_income",
                                "arrears_bucket", "ifrs9_stage", "ecl", "write_off_amount", "guarantee_claim_amount",
                                "new_lending_amount", "is_payment_holiday", "account_status"]):
        df["b90"] = np.where(df["arrears_bucket"] == "90+", df["balance_eom"], 0)
        df["s2"] = np.where(df["ifrs9_stage"] == 2, df["balance_eom"], 0)
        df["s3"] = np.where(df["ifrs9_stage"] == 3, df["balance_eom"], 0)
        df["hol"] = np.where(df["is_payment_holiday"], df["balance_eom"], 0)
        ln.append(df.drop(columns=["arrears_bucket", "ifrs9_stage", "is_payment_holiday", "account_status"])
                  .groupby(["month_end", "product_id"]).sum().reset_index())
    ln = pd.concat(ln)
    ln["year"] = pd.to_datetime(ln["month_end"]).dt.year

    print("\n" + "=" * 90 + "\nSTORY 1 | NII (FTP basis) and NIM vs Bank Rate (annual)\n" + "=" * 90)
    rate = pq.read_table(root / "external" / "bank_rate_fallback" / "bank_rate_fallback.parquet").to_pandas()
    rate["year"] = pd.to_datetime(rate["rate_date"]).dt.year
    nii_d = dep.assign(nii=dep.ftp_credit - dep.interest_expense).groupby("year")["nii"].sum()
    nii_l = ln.assign(nii=ln.interest_income - ln.ftp_charge).groupby("year")["nii"].sum()
    loans_avg = ln.groupby(["year", "month_end"])["balance_eom"].sum().groupby("year").mean()
    months = ln.groupby("year")["month_end"].nunique()
    fees = dep.groupby("year")["fee_income"].sum() + ln.groupby("year")["fee_income"].sum()
    t1 = pd.DataFrame({"bank_rate_avg": rate.groupby("year")["bank_rate"].mean(),
                       "NII_deposits_m": nii_d / 1e6, "NII_lending_m": nii_l / 1e6,
                       "NII_total_m": (nii_d + nii_l) / 1e6, "fees_m": fees / 1e6,
                       "NIM_%": (nii_d + nii_l) / months * 12 / loans_avg * 100}).dropna()
    print(t1.to_string())

    print("\n" + "=" * 90 + "\nSTORY 2 | Deposit migration: EOM balance at December (Aug for 2026), GBP m\n" + "=" * 90)
    last = dep[pd.to_datetime(dep.month_end).dt.month.isin([12]) | (dep.month_end == dep.month_end.max())]
    last = last[last.groupby("year")["month_end"].transform("max") == last["month_end"]]
    print((last.pivot_table(index="year", columns="product_id", values="eom_balance", aggfunc="sum") / 1e6).to_string())

    print("\nLoan book at year-end by product (GBP m):")
    ye0 = ln[ln.groupby("year")["month_end"].transform("max") == ln["month_end"]]
    print((ye0.pivot_table(index="year", columns="product_id", values="balance_eom", aggfunc="sum") / 1e6).round(1).to_string())
    print("\n" + "=" * 90 + "\nSTORY 3-6 | Credit risk by product (year-end): 90+ arrears %, Stage 2 %, Stage 3 %, ECL coverage %\n" + "=" * 90)
    ye = ln[ln.groupby("year")["month_end"].transform("max") == ln["month_end"]]
    g = ye.groupby(["year", "product_id"]).sum(numeric_only=True)
    risk = pd.DataFrame({"balance_m": g.balance_eom / 1e6, "arrears90_%": g.b90 / g.balance_eom * 100,
                         "stage2_%": g.s2 / g.balance_eom * 100, "stage3_%": g.s3 / g.balance_eom * 100,
                         "ecl_cov_%": g.ecl / g.balance_eom * 100})
    print(risk.unstack("product_id")[["arrears90_%", "stage2_%"]].round(2).to_string())
    print("\nECL coverage % by year (all lending):")
    gy = ye.groupby("year").sum(numeric_only=True)
    print((gy.ecl / gy.balance_eom * 100).round(2).to_string())
    print("\nPayment holiday balances (GBP m), 2020:")
    h = ln[ln.year == 2020].groupby("month_end")["hol"].sum() / 1e6
    print(h[h > 0].round(1).to_string())
    print("\nWrite-offs net of BBL guarantee (GBP m) and gross new lending (GBP m):")
    wo = ln.groupby("year").agg(write_off=("write_off_amount", "sum"), guarantee=("guarantee_claim_amount", "sum"),
                                new_lending=("new_lending_amount", "sum")) / 1e6
    print(wo.round(1).to_string())

    # BBL vintage default curve
    print("\n" + "=" * 90 + "\nSTORY 4 | Bounce Back Loans: cumulative default (ever 90+ or written off) by vintage\n" + "=" * 90)
    acc = pq.read_table(root / "corebanking" / "accounts" / "accounts.parquet").to_pandas()
    bbl = acc[acc.product_id == "P09"].drop_duplicates("account_id")
    bbl["vintage"] = pd.to_datetime(bbl.open_date).dt.to_period("Q").astype(str)
    ever = set()
    for df in read_month_files(root, "lending", "loan_performance_monthly", ["account_id", "product_id",
                                                                             "arrears_bucket", "account_status"]):
        d = df[(df.product_id == "P09") & ((df.arrears_bucket == "90+") | (df.account_status == "Written Off"))]
        ever.update(d.account_id.tolist())
    bbl["defaulted"] = bbl.account_id.isin(ever)
    print(bbl.groupby("vintage").agg(loans=("account_id", "count"), default_rate=("defaulted", "mean"))
          .assign(default_rate=lambda x: (x.default_rate * 100).round(1)).to_string())

    # ---------------- network / digital ----------------
    print("\n" + "=" * 90 + "\nSTORY 7 | Branches open vs digital monthly active (December)\n" + "=" * 90)
    br = pq.read_table(root / "network" / "branches" / "branches.parquet").to_pandas()
    rows = []
    for y in range(2020, 2027):
        m = f"{y}-12-31" if y < 2026 else "2026-08-31"
        opn = (br.closure_date.isna() | (pd.to_datetime(br.closure_date) > m)).sum()
        f = root / "digital" / "digital_activity_monthly" / f"year={y}" / f"month={int(m[5:7]):02d}"
        dg = pq.read_table(next(f.glob("*.parquet"))).to_pandas()
        rows.append((y, opn, len(dg), dg.is_monthly_active.sum(), dg.app_sessions.mean()))
    print(pd.DataFrame(rows, columns=["year", "branches_open", "digital_registered", "monthly_active",
                                      "avg_app_sessions"]).to_string(index=False))

    print("\n" + "=" * 90 + "\nSTORY 8-9 | Complaints and fraud\n" + "=" * 90)
    comp = pd.concat(read_month_files(root, "conduct", "complaints", None))
    comp["year"] = pd.to_datetime(comp.received_date).dt.year
    comp["days"] = (pd.to_datetime(comp.resolved_date) - pd.to_datetime(comp.received_date)).dt.days
    print(comp.groupby("year").agg(complaints=("complaint_id", "count"),
                                   within_8_weeks_pct=("days", lambda d: (d <= 56).mean() * 100),
                                   upheld_pct=("upheld", lambda u: u.mean() * 100)).round(1).to_string())
    fr = pd.concat(read_month_files(root, "conduct", "fraud_cases", None))
    fr["period"] = np.where(pd.to_datetime(fr.reported_date) >= "2024-10-07", "after PSR (Oct-24)", "before PSR")
    a = fr[fr.fraud_type == "APP Scam"].groupby("period").agg(cases=("case_id", "count"), loss=("loss_amount", "sum"),
                                                              reimbursed=("reimbursed_amount", "sum"))
    a["reimbursement_%"] = a.reimbursed / a.loss * 100
    print("\nAPP scam reimbursement:\n" + a.round(1).to_string())

    print("\n" + "=" * 90 + "\nSTORY 11 | Budget vs actual NII (GBP m)\n" + "=" * 90)
    bud = pq.read_table(root / "finance" / "budget_monthly" / "budget_monthly.parquet").to_pandas()
    bud["year"] = pd.to_datetime(bud.month_end).dt.year
    act_nii = (nii_d + nii_l) / 1e6
    last_m = pd.to_datetime(dep.month_end.max())
    bud_act = bud[pd.to_datetime(bud.month_end) <= last_m]
    print(pd.DataFrame({"actual_nii": act_nii, "budget_nii": bud_act.groupby("year").budget_nii.sum() / 1e6,
                        "full_year_budget": bud.groupby("year").budget_nii.sum() / 1e6}).round(1).to_string())
    print("(2026 actual = Jan-Aug; full_year_budget includes Sep-Dec forecast)")
    opex = pq.read_table(root / "finance" / "opex_monthly" / "opex_monthly.parquet").to_pandas()
    opex["year"] = pd.to_datetime(opex.month_end).dt.year
    ci = opex.groupby("year").actual_amount.sum() / ((nii_d + nii_l) + fees) * 100
    print("\nCost:income ratio %:\n" + ci.dropna().round(1).to_string())

    print("\n" + "=" * 90 + "\nDATA QUALITY ISSUES INJECTED (for the silver layer)\n" + "=" * 90)
    cust = pq.read_table(root / "corebanking" / "customers" / "customers.parquet").to_pandas()
    print(f"customers: duplicates {cust.duplicated().sum():,} | null region {cust.region_code.isna().sum():,} | "
          f"future onboarding {(pd.to_datetime(cust.onboarding_date) > '2026-08-31').sum():,}")
    print(f"accounts : duplicates {acc.duplicated().sum():,}")
    print(f"complaints: resolved before received {(comp.days < 0).sum():,}")
    print("\nValidation finished.")


if __name__ == "__main__":
    main()
