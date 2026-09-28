#!/usr/bin/env python3
"""
Lloyds Banking Group | UK Retail & SME Banking | Synthetic data generator
==========================================================================
Portfolio project by Joao Paura. HYPOTHETICAL DATA for demonstration only.
Not affiliated with, endorsed by or based on internal data of Lloyds Banking Group.

Simulates the extracts of 8 source systems (CoreBanking, Lending, Payments,
Digital, Network, Conduct, Finance, Reference) as Parquet files, partitioned by
year/month, ready to be landed in Azure Blob Storage and loaded by Azure Data Factory.

Period : Jan 2020 to Aug 2026 (actuals) | Budget to Dec 2026
Scale  : --scale 1.0 = ~500k customers, ~100M rows, ~2 GB of Parquet

Usage
-----
    python generate_lloyds_data.py                 # full run (scale 1.0)
    python generate_lloyds_data.py --scale 0.01    # quick test (~1% of the data)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ----------------------------------------------------------------------------
# 0. Calendar
# ----------------------------------------------------------------------------
N_ACT = 80   # Jan 2020 .. Aug 2026 (actuals)
N_BUD = 84   # Jan 2020 .. Dec 2026 (budget horizon)
PERIODS = pd.period_range("2020-01", periods=240, freq="M")          # extended (deal end dates)
MONTH_START = PERIODS.to_timestamp()
MONTH_END = PERIODS.to_timestamp(how="end").normalize()
LAST_ACTUAL_DATE = MONTH_END[N_ACT - 1]

UK_BANK_HOLIDAYS = [  # England & Wales
    "2020-01-01", "2020-04-10", "2020-04-13", "2020-05-08", "2020-05-25", "2020-08-31", "2020-12-25", "2020-12-28",
    "2021-01-01", "2021-04-02", "2021-04-05", "2021-05-03", "2021-05-31", "2021-08-30", "2021-12-27", "2021-12-28",
    "2022-01-03", "2022-04-15", "2022-04-18", "2022-05-02", "2022-06-02", "2022-06-03", "2022-08-29", "2022-09-19",
    "2022-12-26", "2022-12-27",
    "2023-01-02", "2023-04-07", "2023-04-10", "2023-05-01", "2023-05-08", "2023-05-29", "2023-08-28", "2023-12-25",
    "2023-12-26",
    "2024-01-01", "2024-03-29", "2024-04-01", "2024-05-06", "2024-05-27", "2024-08-26", "2024-12-25", "2024-12-26",
    "2025-01-01", "2025-04-18", "2025-04-21", "2025-05-05", "2025-05-26", "2025-08-25", "2025-12-25", "2025-12-26",
    "2026-01-01", "2026-04-03", "2026-04-06", "2026-05-04", "2026-05-25", "2026-08-31", "2026-12-25", "2026-12-28",
]

# Real Bank of England Bank Rate decisions (effective dates)
BANK_RATE_CHANGES = [
    ("2019-01-01", 0.75), ("2020-03-11", 0.25), ("2020-03-19", 0.10), ("2021-12-16", 0.25),
    ("2022-02-03", 0.50), ("2022-03-17", 0.75), ("2022-05-05", 1.00), ("2022-06-16", 1.25),
    ("2022-08-04", 1.75), ("2022-09-22", 2.25), ("2022-11-03", 3.00), ("2022-12-15", 3.50),
    ("2023-02-02", 4.00), ("2023-03-23", 4.25), ("2023-05-11", 4.50), ("2023-06-22", 5.00),
    ("2023-08-03", 5.25), ("2024-08-01", 5.00), ("2024-11-07", 4.75), ("2025-02-06", 4.50),
    ("2025-05-08", 4.25), ("2025-08-07", 4.00), ("2025-12-18", 3.75),
]

# ----------------------------------------------------------------------------
# 1. Reference data
# ----------------------------------------------------------------------------
# code, name, nation, population weight, unsecured risk multiplier, house price multiplier, HPI growth factor
REGIONS = [
    ("NE", "North East", "England", 0.040, 1.60, 0.70, 1.0),
    ("NW", "North West", "England", 0.110, 1.15, 0.85, 1.1),
    ("YH", "Yorkshire and The Humber", "England", 0.082, 1.10, 0.80, 1.0),
    ("EM", "East Midlands", "England", 0.072, 1.00, 0.90, 1.0),
    ("WM", "West Midlands", "England", 0.089, 1.10, 0.90, 1.0),
    ("EE", "East of England", "England", 0.094, 0.95, 1.20, 0.9),
    ("LDN", "London", "England", 0.134, 0.90, 1.90, 0.5),
    ("SE", "South East", "England", 0.137, 0.85, 1.35, 0.8),
    ("SW", "South West", "England", 0.085, 0.90, 1.10, 1.0),
    ("WAL", "Wales", "Wales", 0.046, 1.10, 0.80, 1.1),
    ("SCO", "Scotland", "Scotland", 0.081, 1.00, 0.80, 0.9),
    ("NI", "Northern Ireland", "Northern Ireland", 0.028, 1.05, 0.70, 1.3),
]
DIRECTORS = ["Sarah Mitchell", "James O'Connor", "Priya Sharma", "David Thompson", "Emma Clarke",
             "Oliver Bennett", "Aisha Rahman", "Thomas Wright", "Charlotte Hughes", "Rhys Evans",
             "Fiona MacLeod", "Ciaran Murphy"]
N_REG = len(REGIONS)
REG_CODE = np.array([r[0] for r in REGIONS])
REG_W = np.array([r[3] for r in REGIONS]); REG_W = REG_W / REG_W.sum()
REG_RISK = np.array([r[4] for r in REGIONS])
REG_HOUSE = np.array([r[5] for r in REGIONS])
REG_HPI_G = np.array([r[6] for r in REGIONS])

# city, postcode area, lat, lon
CITIES = {
    "NE": [("Newcastle upon Tyne", "NE", 54.978, -1.617), ("Sunderland", "SR", 54.906, -1.381),
           ("Middlesbrough", "TS", 54.574, -1.235), ("Durham", "DH", 54.776, -1.575)],
    "NW": [("Manchester", "M", 53.480, -2.242), ("Liverpool", "L", 53.408, -2.991), ("Preston", "PR", 53.763, -2.703),
           ("Bolton", "BL", 53.578, -2.429), ("Chester", "CH", 53.193, -2.893), ("Blackpool", "FY", 53.817, -3.035)],
    "YH": [("Leeds", "LS", 53.800, -1.549), ("Sheffield", "S", 53.381, -1.470), ("Bradford", "BD", 53.796, -1.759),
           ("Hull", "HU", 53.745, -0.336), ("York", "YO", 53.960, -1.087)],
    "EM": [("Nottingham", "NG", 52.954, -1.158), ("Leicester", "LE", 52.637, -1.140), ("Derby", "DE", 52.922, -1.477),
           ("Lincoln", "LN", 53.230, -0.541), ("Northampton", "NN", 52.240, -0.903)],
    "WM": [("Birmingham", "B", 52.486, -1.890), ("Coventry", "CV", 52.407, -1.510),
           ("Wolverhampton", "WV", 52.587, -2.129), ("Stoke-on-Trent", "ST", 53.003, -2.179),
           ("Worcester", "WR", 52.192, -2.220)],
    "EE": [("Norwich", "NR", 52.630, 1.297), ("Cambridge", "CB", 52.205, 0.122), ("Ipswich", "IP", 52.057, 1.148),
           ("Peterborough", "PE", 52.573, -0.249), ("Chelmsford", "CM", 51.736, 0.479), ("Luton", "LU", 51.879, -0.418)],
    "LDN": [("London City", "EC", 51.515, -0.092), ("Croydon", "CR", 51.376, -0.098), ("Stratford", "E", 51.541, -0.003),
            ("Wimbledon", "SW", 51.421, -0.206), ("Ealing", "W", 51.513, -0.305), ("Camden", "NW", 51.539, -0.143)],
    "SE": [("Brighton", "BN", 50.822, -0.137), ("Southampton", "SO", 50.910, -1.404), ("Reading", "RG", 51.454, -0.978),
           ("Oxford", "OX", 51.752, -1.258), ("Portsmouth", "PO", 50.805, -1.087), ("Canterbury", "CT", 51.280, 1.079),
           ("Milton Keynes", "MK", 52.041, -0.759)],
    "SW": [("Bristol", "BS", 51.455, -2.588), ("Plymouth", "PL", 50.376, -4.143), ("Exeter", "EX", 50.718, -3.534),
           ("Bath", "BA", 51.381, -2.359), ("Swindon", "SN", 51.556, -1.780), ("Bournemouth", "BH", 50.720, -1.880)],
    "WAL": [("Cardiff", "CF", 51.482, -3.179), ("Swansea", "SA", 51.621, -3.944), ("Newport", "NP", 51.584, -2.998),
            ("Wrexham", "LL", 53.046, -2.993), ("Bangor", "LL", 53.227, -4.129)],
    "SCO": [("Glasgow", "G", 55.864, -4.252), ("Edinburgh", "EH", 55.953, -3.188), ("Aberdeen", "AB", 57.150, -2.094),
            ("Dundee", "DD", 56.462, -2.971), ("Inverness", "IV", 57.478, -4.225), ("Stirling", "FK", 56.117, -3.937)],
    "NI": [("Belfast", "BT", 54.597, -5.930), ("Derry", "BT", 54.997, -7.309), ("Lisburn", "BT", 54.516, -6.058),
           ("Newry", "BT", 54.176, -6.349)],
}
BRANDS = np.array(["Lloyds Bank", "Halifax", "Bank of Scotland"])
BRAND_W = {"SCO": [0.25, 0.20, 0.55], "NI": [0.45, 0.52, 0.03]}
BRAND_W_DEFAULT = [0.52, 0.43, 0.05]

PRODUCTS = [  # id, name, group, segment, secured, gov guaranteed
    ("P01", "Personal Current Account", "Deposits", "Personal", False, False),
    ("P02", "Easy Access Savings", "Deposits", "Personal", False, False),
    ("P03", "Fixed Term Savings", "Deposits", "Personal", False, False),
    ("P04", "Mortgage", "Lending", "Personal", True, False),
    ("P05", "Personal Loan", "Lending", "Personal", False, False),
    ("P06", "Credit Card", "Lending", "Personal", False, False),
    ("P07", "Business Current Account", "Deposits", "SME", False, False),
    ("P08", "Business Loan", "Lending", "SME", False, False),
    ("P09", "Bounce Back Loan", "Lending", "SME", False, True),
    ("P10", "Business Credit Card", "Lending", "SME", False, False),
]
PROD_ID = np.array([p[0] for p in PRODUCTS])
N_PROD = len(PRODUCTS)
CUR, EAS, FTS, MTG, PLN, CCD, BCA, BLN, BBL, BCC = range(10)

CHANNELS = [("CH01", "Branch"), ("CH02", "Online Banking"), ("CH03", "Mobile App"), ("CH04", "Telephony"),
            ("CH05", "ATM"), ("CH06", "Card Network"), ("CH07", "Automated (BACS/Direct Debit)")]
COMPLAINT_CATS = [
    ("CC01", "Current Accounts", "Banking and credit cards"), ("CC02", "Savings", "Banking and credit cards"),
    ("CC03", "Mortgages", "Home finance"), ("CC04", "Credit Cards", "Banking and credit cards"),
    ("CC05", "Personal Loans", "Banking and credit cards"), ("CC06", "Business Banking", "Banking and credit cards"),
    ("CC07", "Fraud and Scams", "Banking and credit cards"), ("CC08", "Payments and Transfers", "Banking and credit cards"),
    ("CC09", "Digital Banking", "Banking and credit cards"), ("CC10", "Branch Service", "Banking and credit cards"),
]
SUBSEG_P = np.array(["Mass", "Affluent", "Premier"])
SUBSEG_S = np.array(["Micro", "Small", "Medium"])
AGE_BANDS = np.array(["18-24", "25-34", "35-44", "45-54", "55-64", "65+"])
INCOME_BANDS = np.array(["<20k", "20-35k", "35-50k", "50-75k", "75-100k", "100k+"])
SCORE_BANDS = np.array(["Excellent", "Good", "Fair", "Poor", "Very Poor"])
INDUSTRIES = np.array(["Retail", "Hospitality", "Construction", "Professional Services", "Manufacturing",
                       "Health and Care", "Transport and Logistics", "Agriculture", "Technology"])
TURNOVER_BANDS = np.array(["<100k", "100k-500k", "500k-2m", "2m-6.5m", "6.5m-25m"])
ONB_CHANNELS = np.array(["Branch", "Online Banking", "Mobile App", "Telephony"])
BUCKETS = np.array(["Current", "1-29", "30-59", "60-89", "90+"])
RATE_TYPES = np.array(["2y Fixed", "5y Fixed", "Tracker", "SVR", "Fixed", "Variable"])


# ----------------------------------------------------------------------------
# 2. Macro curves (monthly, index 0 = Jan 2020)
# ----------------------------------------------------------------------------
def knots(points, n=N_BUD):
    x, y = zip(*points)
    return np.interp(np.arange(n), x, y)


def build_macro():
    idx = pd.date_range("2020-01-01", "2026-12-31")
    ch = pd.Series({pd.Timestamp(d): r for d, r in BANK_RATE_CHANGES})
    daily = ch.reindex(ch.index.union(idx)).ffill().reindex(idx)
    br = daily.groupby(daily.index.to_period("M")).mean().values                      # 84 values
    lead6 = np.array([br[min(t + 6, N_BUD - 1)] for t in range(N_BUD)])
    swap2 = 0.25 + 0.95 * lead6
    swap5 = 0.45 + 0.80 * lead6
    hist = np.concatenate([np.full(60, 1.30), swap5])
    hedge = np.array([hist[t + 1:t + 61].mean() for t in range(N_BUD)])              # structural hedge yield
    m = dict(
        br=br, swap2=swap2, swap5=swap5, hedge=hedge, daily_rate=daily,
        macro=knots([(0, 1.0), (1, 1.0), (3, 1.45), (8, 1.35), (12, 1.15), (20, 0.95), (27, 1.0), (31, 1.45),
                     (36, 1.55), (44, 1.45), (48, 1.25), (60, 1.05), (72, 0.95), (83, 0.95)]),
        fl=knots([(0, 1.0), (2, 1.0), (3, 1.9), (9, 1.7), (15, 1.25), (23, 1.0), (32, 1.05), (34, 1.3), (47, 1.25),
                  (59, 1.05), (71, 1.0), (83, 1.0)]),                                  # IFRS 9 forward-looking overlay
        hpi=knots([(0, 1.00), (11, 1.08), (23, 1.18), (32, 1.24), (44, 1.19), (59, 1.22), (71, 1.25), (79, 1.27),
                   (83, 1.28)]),
        dep_beta=knots([(0, 0.10), (24, 0.12), (33, 0.25), (42, 0.45), (54, 0.55), (83, 0.55)]),
        mtg_margin=knots([(0, 0.90), (44, 0.90), (50, 0.60), (83, 0.60)]),
        tr_cur=knots([(0, 1.0), (2, 1.0), (14, 1.25), (24, 1.24), (36, 1.12), (48, 1.02), (60, 1.0), (83, 1.02)]),
        tr_eas=knots([(0, 1.0), (14, 1.18), (30, 1.18), (42, 1.02), (54, 0.98), (83, 1.02)]),
        tr_bca=knots([(0, 1.0), (4, 1.0), (7, 1.35), (18, 1.25), (36, 1.08), (83, 1.05)]),
        util=knots([(0, 1.0), (2, 1.0), (4, 0.80), (8, 0.88), (14, 0.90), (20, 0.97), (26, 1.0), (31, 1.05),
                    (40, 1.12), (52, 1.08), (83, 1.05)]),
        w_mtg=knots([(0, 1), (2, 1), (3, 0.35), (5, 0.5), (6, 1.2), (11, 1.3), (14, 1.6), (17, 1.5), (18, 1.1),
                     (23, 1.1), (33, 1.2), (34, 0.9), (40, 0.7), (47, 0.75), (55, 0.95), (62, 1.3), (63, 0.85),
                     (71, 1.05), (79, 1.05)], N_ACT),
        w_pl=knots([(0, 1), (2, 1), (3, 0.35), (8, 0.7), (18, 1.0), (30, 1.2), (42, 1.0), (79, 1.1)], N_ACT),
        w_cust=knots([(0, 1), (3, 0.6), (8, 0.9), (20, 1.0), (79, 1.15)], N_ACT),
        w_fts=knots([(0, 0.3), (24, 0.4), (30, 1.2), (36, 2.0), (48, 1.8), (60, 1.1), (79, 0.9)], N_ACT),
        w_branch_close=knots([(0, 0.2), (12, 0.8), (18, 0.6), (30, 0.5), (36, 1.0), (52, 1.2), (64, 1.0),
                              (79, 0.6)], N_ACT),
    )
    m["support"] = np.where((np.arange(N_BUD) >= 3) & (np.arange(N_BUD) <= 20), 0.6, 1.0)   # furlough / support
    return m


def at(arr, t, pre):
    t = np.asarray(t)
    return np.where(t < 0, pre, arr[np.clip(t, 0, len(arr) - 1)])


def hpi_at(M, t):
    t = np.asarray(t)
    return np.where(t < 0, 1.035 ** (t / 12.0), M["hpi"][np.clip(t, 0, N_BUD - 1)])


def annuity(bal, rate_pct, n_months):
    r = rate_pct / 1200.0
    n = np.maximum(n_months, 1)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        pay = np.where(r > 1e-9, bal * r / (1 - (1 + r) ** (-n)), bal / n)
    return pay


def sample_months(rng, weights, size):
    p = np.asarray(weights, dtype=float)
    return rng.choice(len(p), size=size, p=p / p.sum())


def fmt_ids(prefix, n, width):
    return np.array([f"{prefix}{i:0{width}d}" for i in range(1, n + 1)], dtype=object)


def month_idx_to_date(m, rng=None, day="start"):
    """Month index (can be negative) -> datetime64[D]. day='random' adds a random day 0-27."""
    m = np.asarray(m, dtype=np.int64)
    base = (np.datetime64("2020-01", "M") + m.astype("timedelta64[M]")).astype("datetime64[D]")
    if day == "random":
        base = base + rng.integers(0, 28, size=m.shape).astype("timedelta64[D]")
    return base


# ----------------------------------------------------------------------------
# 3. Writer
# ----------------------------------------------------------------------------
class Writer:
    def __init__(self, root: Path):
        self.root = root
        self.manifest = []

    def write(self, df: pd.DataFrame, source: str, table: str, year: int | None = None, month: int | None = None):
        if year is None:
            path = self.root / source / table / f"{table}.parquet"
        else:
            path = self.root / source / table / f"year={year}" / f"month={month:02d}" / f"{table}_{year}_{month:02d}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        tbl = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(tbl, path, compression="snappy")
        self.manifest.append({"source": source, "table": table, "file": str(path.relative_to(self.root)).replace("\\", "/"),
                              "rows": int(len(df)), "bytes": path.stat().st_size})


def inject_duplicates(df, rng, frac):
    k = int(len(df) * frac)
    if k == 0:
        return df
    return pd.concat([df, df.iloc[rng.choice(len(df), k, replace=False)]], ignore_index=True)


# ----------------------------------------------------------------------------
# 4. Generator
# ----------------------------------------------------------------------------
class Generator:
    def __init__(self, scale: float, out: Path, seed: int = 42, months: int = N_ACT):
        self.scale = scale
        self.rng = np.random.default_rng(seed)
        self.W = Writer(out)
        self.M = build_macro()
        self.n_months = months
        # budget aggregates [metric][month, region, product]
        self.agg = {k: np.zeros((N_ACT, N_REG, N_PROD)) for k in
                    ["balance", "nii", "fees", "ecl", "writeoff", "new_lending"]}
        self.cust_active = np.zeros((N_ACT, N_REG))
        self.branches_open = np.zeros((N_ACT, N_REG))
        self.log = print

    # ---------------- reference -------------------------------------------------
    def gen_reference(self):
        W = self.W
        W.write(pd.DataFrame({
            "region_code": REG_CODE, "region_name": [r[1] for r in REGIONS], "nation": [r[2] for r in REGIONS],
            "regional_director": DIRECTORS,
            "director_email": [f"{c.lower()}.director@example.com" for c in REG_CODE]}), "reference", "regions")
        W.write(pd.DataFrame(PRODUCTS, columns=["product_id", "product_name", "product_group", "segment",
                                                "is_secured", "is_government_guaranteed"]), "reference", "products")
        W.write(pd.DataFrame(CHANNELS, columns=["channel_code", "channel_name"]), "reference", "channels")
        W.write(pd.DataFrame(COMPLAINT_CATS, columns=["category_code", "category_name", "fca_product_group"]),
                "reference", "complaint_categories")
        W.write(pd.DataFrame({"holiday_date": pd.to_datetime(UK_BANK_HOLIDAYS).date}), "reference", "uk_bank_holidays")
        d = self.M["daily_rate"]
        W.write(pd.DataFrame({"rate_date": d.index.date, "bank_rate": d.values}), "external", "bank_rate_fallback")

    # ---------------- branches --------------------------------------------------
    def gen_branches(self):
        rng, M = self.rng, self.M
        rows = []
        for r, code in enumerate(REG_CODE):
            n = max(1, int(round(950 * self.scale * REG_W[r])))
            cities = CITIES[code]
            bw = BRAND_W.get(code, BRAND_W_DEFAULT)
            for k in range(n):
                c = cities[k % len(cities)] if k < len(cities) else cities[rng.integers(len(cities))]
                rows.append((r, rng.choice(3, p=bw), c[0], c[2] + rng.normal(0, 0.03), c[3] + rng.normal(0, 0.03),
                             rng.choice(3, p=[0.7, 0.2, 0.1]), k == 0))
        nb = len(rows)
        b_reg = np.array([x[0] for x in rows]); b_brand = np.array([x[1] for x in rows])
        b_fmt = np.array([x[5] for x in rows]); protected = np.array([x[6] for x in rows])
        close = np.full(nb, 9999)
        closing = (rng.random(nb) < 0.35) & ~protected
        close[closing] = sample_months(rng, M["w_branch_close"], closing.sum())
        open_d = np.datetime64("1950-01-01") + rng.integers(0, 365 * 65, nb).astype("timedelta64[D]")
        self.b_reg, self.b_fmt, self.b_close = b_reg, b_fmt, close
        self.b_ids = fmt_ids("BR", nb, 4)
        self.branches_by_region = [np.where(b_reg == r)[0] for r in range(N_REG)]
        fmt_names = np.array(["Full Service", "Micro", "Shared Hub"])
        df = pd.DataFrame({
            "branch_id": self.b_ids,
            "branch_name": [f"{BRANDS[b]} {x[2]}" + (f" {i % 7 + 1}" if i >= 0 else "") for i, (b, x) in
                            enumerate(zip(b_brand, rows))],
            "brand": BRANDS[b_brand], "region_code": REG_CODE[b_reg], "city": [x[2] for x in rows],
            "latitude": np.round([x[3] for x in rows], 5), "longitude": np.round([x[4] for x in rows], 5),
            "branch_format": fmt_names[b_fmt], "open_date": open_d,
            "closure_date": np.where(close < N_ACT, month_idx_to_date(np.minimum(close, N_ACT - 1), rng, "random"),
                                     np.datetime64("NaT")),
        })
        self.W.write(df, "network", "branches")
        self.log(f"  branches: {nb:,}")

    # ---------------- customers -------------------------------------------------
    def gen_customers(self):
        rng, M = self.rng, self.M
        n = int(500_000 * self.scale)
        self.n_cust = n
        sme = rng.random(n) < 0.08
        region = rng.choice(N_REG, n, p=REG_W)
        brand = np.zeros(n, dtype=int); city = np.empty(n, dtype=object); pc_area = np.empty(n, dtype=object)
        for r, code in enumerate(REG_CODE):
            ix = np.where(region == r)[0]
            brand[ix] = rng.choice(3, len(ix), p=BRAND_W.get(code, BRAND_W_DEFAULT))
            cw = np.array([1.0 / (k + 1) ** 0.6 for k in range(len(CITIES[code]))]); cw /= cw.sum()
            ci = rng.choice(len(CITIES[code]), len(ix), p=cw)
            city[ix] = np.array([c[0] for c in CITIES[code]], dtype=object)[ci]
            pc_area[ix] = np.array([c[1] for c in CITIES[code]], dtype=object)[ci]
        subseg = np.where(sme, rng.choice(3, n, p=[0.75, 0.20, 0.05]), rng.choice(3, n, p=[0.70, 0.22, 0.08]))
        existing = rng.random(n) < 0.82
        onb = np.where(existing, -rng.integers(1, 360, n), sample_months(rng, M["w_cust"], n))
        hz = np.where(sme, 0.0020, 0.0012)
        churn = np.maximum(onb, 0) + rng.geometric(hz)
        churn = np.where(churn >= N_ACT, 9999, churn)
        # age
        age = np.where(existing, rng.choice(6, n, p=[.06, .15, .17, .19, .18, .25]),
                       rng.choice(6, n, p=[.25, .30, .18, .12, .08, .07]))
        inc_p = {0: [.22, .35, .25, .12, .04, .02], 1: [0, .05, .20, .40, .25, .10], 2: [0, 0, .03, .17, .30, .50]}
        income = np.zeros(n, dtype=int)
        score_p = {0: [.18, .33, .28, .14, .07], 1: [.30, .40, .20, .07, .03], 2: [.40, .40, .15, .04, .01]}
        score = np.zeros(n, dtype=int)
        for s in range(3):
            ix = np.where(~sme & (subseg == s))[0]
            income[ix] = rng.choice(6, len(ix), p=inc_p[s])
            score[ix] = rng.choice(5, len(ix), p=score_p[s])
        ixs = np.where(sme)[0]
        score[ixs] = rng.choice(5, len(ixs), p=[.15, .35, .30, .13, .07])
        industry = rng.choice(len(INDUSTRIES), n, p=[.16, .12, .15, .18, .08, .09, .08, .05, .09])
        turnover = np.select([subseg == 0, subseg == 1], [rng.choice([0, 1], n, p=[.6, .4]),
                                                          rng.choice([1, 2], n, p=[.3, .7])],
                             rng.choice([3, 4], n, p=[.6, .4]))
        onb_ch = np.select([onb < -120, onb < 0],
                           [rng.choice(4, n, p=[.85, .10, 0, .05]), rng.choice(4, n, p=[.45, .30, .20, .05])],
                           rng.choice(4, n, p=[.10, .25, .60, .05]))
        # digital registration
        young = np.isin(age, [0, 1, 2])
        pre_reg = existing & (rng.random(n) < np.where(young, 0.85, np.where(age >= 4, 0.40, 0.65)))
        reg = np.where(pre_reg, -1, 9999)
        new_reg = (~existing) & (rng.random(n) < 0.85)
        reg = np.where(new_reg, onb, reg)
        rest = reg == 9999
        g = np.maximum(onb, 0) + rng.geometric(np.where(young, 0.03, 0.012), n)
        reg = np.where(rest & (g < N_ACT), g, reg)
        branch = np.array([rng.choice(self.branches_by_region[r]) for r in region])
        # store
        self.c = dict(sme=sme, region=region, subseg=subseg, onb=onb, churn=churn, age=age, income=income,
                      score=score, reg=reg, brand=brand, branch=branch)
        self.c_ids = fmt_ids("C", n, 7)
        # ---- output (with dirty data) ----
        pc = (pc_area.astype(str) + rng.integers(1, 30, n).astype(str) + " " + rng.integers(1, 10, n).astype(str)
              + np.array(list("ABDEFGHJLNPQRSTUWXYZ"))[rng.integers(0, 20, n)]
              + np.array(list("ABDEFGHJLNPQRSTUWXYZ"))[rng.integers(0, 20, n)]).astype(object)
        messy = rng.random(n) < 0.003
        pc[messy] = np.char.lower(np.char.replace(pc[messy].astype(str), " ", "")).astype(object)
        reg_out = REG_CODE[region].astype(object)
        reg_out[rng.random(n) < 0.001] = None
        onb_date = month_idx_to_date(onb, rng, "random")
        typo = rng.random(n) < 0.0005
        onb_date[typo] = onb_date[typo] + np.timedelta64(3650, "D")
        df = pd.DataFrame({
            "customer_id": self.c_ids,
            "segment": np.where(sme, "SME", "Personal"),
            "sub_segment": np.where(sme, SUBSEG_S[subseg], SUBSEG_P[subseg]),
            "brand": BRANDS[brand], "region_code": reg_out, "city": city, "postcode_sector": pc,
            "age_band": np.where(sme, None, AGE_BANDS[age]),
            "income_band": np.where(sme, None, INCOME_BANDS[income]),
            "industry": np.where(sme, INDUSTRIES[industry], None),
            "turnover_band": np.where(sme, TURNOVER_BANDS[turnover], None),
            "credit_score_band": SCORE_BANDS[score],
            "onboarding_date": onb_date, "onboarding_channel": ONB_CHANNELS[onb_ch],
            "digital_registration_date": np.where(reg < N_ACT, month_idx_to_date(np.minimum(reg, N_ACT), rng, "random"),
                                                  np.datetime64("NaT")),
            "home_branch_id": self.b_ids[branch],
            "churn_date": np.where(churn < N_ACT, month_idx_to_date(np.minimum(churn, N_ACT), rng, "random"),
                                   np.datetime64("NaT")),
            "customer_status": np.where(churn < N_ACT, "Closed", "Active"),
        })
        self.W.write(inject_duplicates(df, rng, 0.002), "corebanking", "customers")
        self.log(f"  customers: {n:,} (active Aug-2026: {(churn >= N_ACT).sum():,})")

    # ---------------- deposit accounts ---------------------------------------------
    def gen_deposit_accounts(self):
        rng, M, c = self.rng, self.M, self.c
        n = self.n_cust
        pers = np.where(~c["sme"])[0]
        smes = np.where(c["sme"])[0]
        parts = []
        # current accounts
        parts.append((np.full(len(pers), CUR), pers, c["onb"][pers], c["churn"][pers]))
        # easy access
        p_eas = np.array([0.45, 0.60, 0.75])[c["subseg"][pers]]
        h = pers[rng.random(len(pers)) < p_eas]
        o = c["onb"][h] + rng.integers(0, 36, len(h))
        ok = o < np.minimum(c["churn"][h], N_ACT)
        h, o = h[ok], o[ok]
        cl = np.where(rng.random(len(h)) < 0.10, o + rng.integers(6, 120, len(h)), 9999)
        parts.append((np.full(len(h), EAS), h, o, np.minimum(cl, c["churn"][h])))
        # fixed term (deposit migration)
        p_fts = np.array([0.18, 0.25, 0.35])[c["subseg"][pers]]
        h = pers[rng.random(len(pers)) < p_fts]
        o = sample_months(rng, M["w_fts"], len(h))
        ok = (o >= c["onb"][h]) & (o < c["churn"][h])
        h, o = h[ok], o[ok]
        term = np.where(rng.random(len(h)) < 0.6, 12, 24)
        cl = np.minimum(o + term, c["churn"][h])
        roll = (rng.random(len(h)) < 0.35) & (cl < N_ACT) & (cl == o + term)
        h2, o2 = h[roll], cl[roll]
        t2 = np.where(rng.random(len(h2)) < 0.6, 12, 24)
        parts.append((np.full(len(h), FTS), h, o, cl))
        parts.append((np.full(len(h2), FTS), h2, o2, np.minimum(o2 + t2, c["churn"][h2])))
        # business current
        parts.append((np.full(len(smes), BCA), smes, c["onb"][smes], c["churn"][smes]))
        prod = np.concatenate([p[0] for p in parts]); cust = np.concatenate([p[1] for p in parts])
        opn = np.concatenate([p[2] for p in parts]); cls = np.concatenate([p[3] for p in parts])
        nd = len(prod)
        ss = c["subseg"][cust]
        med = np.select([prod == CUR, prod == EAS, prod == FTS, prod == BCA],
                        [np.array([1800, 7500, 22000])[ss], np.array([3200, 16000, 52000])[ss],
                         np.array([10000, 30000, 90000])[ss], np.array([18000, 90000, 450000])[ss]])
        base = np.exp(np.log(med) + rng.normal(0, 0.9, nd))
        # fixed term rate at opening
        br_o = at(M["br"], opn, 0.6)
        ft_rate = np.round(np.maximum(0.25, br_o * 0.80 + 0.40), 2)
        ft_ftp = at(M["swap2"], opn, 1.0)
        pack = np.where((prod == CUR) & (ss == 1) & (rng.random(nd) < 0.30), 15.0,
                        np.where((prod == CUR) & (ss == 2) & (rng.random(nd) < 0.50), 20.0, 0.0))
        self.d = dict(prod=prod, cust=cust, open=opn, close=cls, base=base, z=rng.normal(0, 0.25, nd),
                      ft_rate=ft_rate, ft_ftp=ft_ftp, pack=pack, prev=np.zeros(nd),
                      region=c["region"][cust], subseg=ss)
        self.d_ids = fmt_ids("D", nd, 8)
        self.log(f"  deposit accounts: {nd:,}")

    # ---------------- lending accounts ----------------------------------------------
    def gen_loan_accounts(self):
        rng, M, c = self.rng, self.M, self.c
        pers = np.where(~c["sme"])[0]
        smes = np.where(c["sme"])[0]
        L = []  # list of dicts per product

        def add(prod, cust, opn, amount, term, rate, ftp, rtype, deal_end=None, prop=None, ltv=None, limit=None,
                util=None):
            k = len(cust)
            L.append(dict(prod=np.full(k, prod), cust=cust, open=opn, amount=amount, term=term, rate=rate, ftp=ftp,
                          rtype=rtype, deal_end=np.full(k, 9999) if deal_end is None else deal_end,
                          prop=np.zeros(k) if prop is None else prop, ltv=np.zeros(k) if ltv is None else ltv,
                          limit=np.zeros(k) if limit is None else limit, util=np.zeros(k) if util is None else util))

        # ---- mortgages ----
        age = c["age"][pers]; ss = c["subseg"][pers]
        p = np.array([.02, .18, .32, .30, .18, .06])[age] * np.array([1.0, 1.4, 1.6])[ss] * 1.05
        h = pers[rng.random(len(pers)) < p]
        onb, chn = c["onb"][h], c["churn"][h]
        is_new = (onb >= 0) | (rng.random(len(h)) < 0.25)
        o_new = sample_months(rng, M["w_mtg"], len(h))
        o_new = np.where(o_new < onb, np.minimum(onb + rng.integers(0, 4, len(h)), N_ACT - 1), o_new)
        o_old = rng.integers(np.maximum(onb, -228), 0) if False else \
            (np.maximum(onb, -228) + (rng.random(len(h)) * (0 - np.maximum(onb, -228))).astype(int))
        o_old = np.minimum(o_old, -1)
        o = np.where(is_new, o_new, o_old)
        keep = o < np.minimum(chn, N_ACT)
        h, o, is_new = h[keep], o[keep], is_new[keep]
        k = len(h); reg = c["region"][h]; ssk = c["subseg"][h]; agek = c["age"][h]
        amount = np.exp(np.log(175000 * REG_HOUSE[reg] * np.array([1.0, 1.4, 2.0])[ssk]) + rng.normal(0, 0.45, k))
        amount *= np.where(o < 0, hpi_at(M, o), 1.0)
        amount = np.round(np.clip(amount, 40000, 2_500_000), -2)
        ltv = np.clip(rng.beta(7, 3, k) * np.where(agek == 1, 1.12, 0.95), 0.30, 0.95)
        prop = amount / ltv
        term = rng.choice([240, 300, 360, 420], k, p=[.2, .5, .22, .08])
        rt_new = np.where(o >= 30, rng.choice(4, k, p=[.38, .55, .05, .02]), rng.choice(4, k, p=[.47, .43, .07, .03]))
        rt_old = rng.choice(4, k, p=[.40, .38, .10, .12])
        rtype = np.where(is_new, rt_new, rt_old)
        # rate at origination / deal start
        rate = np.zeros(k); ftp = np.zeros(k); deal_end = np.full(k, 9999)
        new_fix = is_new & (rtype <= 1)
        rate[new_fix], ftp[new_fix] = self.mortgage_fix_rate(o[new_fix], rtype[new_fix], ltv[new_fix])
        deal_end[new_fix] = o[new_fix] + np.where(rtype[new_fix] == 0, 24, 60)
        old_fix = ~is_new & (rtype <= 1)
        rate[old_fix] = np.where(rtype[old_fix] == 0, 1.9, 2.2) + rng.normal(0, 0.25, old_fix.sum())
        ftp[old_fix] = np.where(rtype[old_fix] == 0, 0.9, 1.2)
        deal_end[old_fix] = np.where(rtype[old_fix] == 0, rng.integers(0, 24, old_fix.sum()),
                                     rng.integers(0, 60, old_fix.sum()))
        rate = np.round(rate, 2)
        add(MTG, h, o, amount, term, rate, ftp, rtype, deal_end=deal_end, prop=prop, ltv=ltv)

        # ---- personal loans ----
        p = np.array([0.10, 0.08, 0.05])[c["subseg"][pers]] * 2.2
        h = pers[rng.random(len(pers)) < p]
        extra = pers[rng.random(len(pers)) < 0.03]
        h = np.concatenate([h, extra])
        k = len(h)
        is_new = rng.random(k) < 0.65
        o = np.where(is_new, sample_months(rng, M["w_pl"], k), -rng.integers(1, 60, k))
        o = np.where(o < c["onb"][h], c["onb"][h] + rng.integers(0, 12, k), o)
        term = rng.choice([24, 36, 48, 60], k, p=[.15, .35, .25, .25])
        keep = (o < np.minimum(c["churn"][h], N_ACT)) & (o + term > 0)
        h, o, term = h[keep], o[keep], term[keep]; k = len(h)
        amount = np.round(np.clip(np.exp(np.log(10000) + rng.normal(0, 0.55, k)), 1000, 35000), -2)
        br_o = at(M["br"], o, 0.6)
        rate = np.round(6.9 + 0.5 * br_o + np.array([-1.0, -0.4, 0.6, 2.5, 4.5])[c["score"][h]], 2)
        add(PLN, h, o, amount, term, rate, at(M["swap2"], o, 1.0), np.full(k, 4))

        # ---- credit cards ----
        p = np.array([0.25, 0.38, 0.50])[c["subseg"][pers]] * 1.05
        h = pers[rng.random(len(pers)) < p]
        k = len(h); onb = c["onb"][h]
        is_new = (onb >= 0) | (rng.random(k) < 0.20)
        o = np.where(is_new, np.maximum(onb, sample_months(rng, M["w_cust"], k)),
                     np.minimum(-1, np.maximum(onb, -180) + (rng.random(k) * (0 - np.maximum(onb, -180))).astype(int)))
        keep = o < np.minimum(c["churn"][h], N_ACT)
        h, o = h[keep], o[keep]; k = len(h)
        sc = c["score"][h]
        limit = np.exp(np.log(np.array([5500, 12000, 22000])[c["subseg"][h]] * np.array([1.4, 1.1, 0.9, 0.6, 0.4])[sc])
                       + rng.normal(0, 0.4, k))
        limit = np.round(np.clip(limit, 250, 50000), -1)
        util = np.clip(rng.beta(1.2, 2.2, k) * np.array([0.7, 0.9, 1.1, 1.4, 1.6])[sc], 0.0, 0.98)
        add(CCD, h, o, np.zeros(k), np.full(k, 36), np.zeros(k), np.zeros(k), np.full(k, 5), limit=limit, util=util)

        # ---- business loans ----
        h = smes[rng.random(len(smes)) < 0.30]
        k = len(h)
        is_new = rng.random(k) < 0.60
        o = np.where(is_new, sample_months(rng, M["w_pl"], k), -rng.integers(1, 72, k))
        o = np.where(o < c["onb"][h], c["onb"][h] + rng.integers(0, 12, k), o)
        term = rng.choice([36, 60, 84], k, p=[.3, .45, .25])
        keep = (o < np.minimum(c["churn"][h], N_ACT)) & (o + term > 0)
        h, o, term = h[keep], o[keep], term[keep]; k = len(h)
        amount = np.round(np.clip(np.exp(np.log(np.array([30000, 150000, 600000])[c["subseg"][h]])
                                         + rng.normal(0, 0.6, k)), 5000, 5_000_000), -2)
        add(BLN, h, o, amount, term, np.zeros(k), np.zeros(k), np.full(k, 5))

        # ---- bounce back loans (May 2020 - Mar 2021) ----
        elig = smes[(c["onb"][smes] <= 4) & (c["churn"][smes] > 4)]
        p = np.array([0.38, 0.30, 0.08])[c["subseg"][elig]]
        h = elig[rng.random(len(elig)) < p]
        k = len(h)
        mw = np.zeros(N_ACT); mw[4] = 40; mw[5] = 20; mw[6] = 10; mw[7:12] = 4; mw[12:15] = 3.3
        o = np.maximum(sample_months(rng, mw, k), 4)
        cap = np.array([50000, 50000, 50000])
        amount = np.round(np.minimum(np.exp(np.log(np.array([18000, 42000, 50000])[c["subseg"][h]])
                                            + rng.normal(0, 0.5, k)), cap[c["subseg"][h]]), -2)
        amount = np.clip(amount, 2000, 50000)
        keep = o < c["churn"][h]
        h, o, amount = h[keep], o[keep], amount[keep]; k = len(h)
        term = np.where(rng.random(k) < 0.25, 120, 72)       # Pay As You Grow extension for 25%
        add(BBL, h, o, amount, term, np.full(k, 2.5), at(M["swap5"], o, 1.3), np.full(k, 4))

        # ---- business credit cards ----
        h = smes[rng.random(len(smes)) < 0.25]
        k = len(h); onb = c["onb"][h]
        o = np.where(onb >= 0, onb, np.minimum(-1, onb + (rng.random(k) * (-onb)).astype(int)))
        keep = o < np.minimum(c["churn"][h], N_ACT)
        h, o = h[keep], o[keep]; k = len(h)
        limit = np.round(np.exp(np.log(np.array([8000, 20000, 40000])[c["subseg"][h]]) + rng.normal(0, 0.4, k)), -2)
        util = np.clip(rng.beta(1.3, 2.4, k) * np.array([0.8, 0.9, 1.1, 1.4, 1.6])[c["score"][h]], 0, 0.98)
        add(BCC, h, o, np.zeros(k), np.full(k, 36), np.zeros(k), np.zeros(k), np.full(k, 5), limit=limit, util=util)

        # ---- assemble state ----
        S = {key: np.concatenate([x[key] for x in L]) for key in L[0]}
        nl = len(S["prod"])
        S["cust"] = S["cust"].astype(int); S["open"] = S["open"].astype(int); S["term"] = S["term"].astype(int)
        S["deal_end"] = S["deal_end"].astype(int); S["rtype"] = S["rtype"].astype(int)
        S["region"] = c["region"][S["cust"]]; S["score"] = c["score"][S["cust"]]
        S["closed_m"] = np.full(nl, 9999)
        S["bucket"] = np.zeros(nl, dtype=np.int8); S["m90"] = np.zeros(nl, dtype=np.int16)
        S["hol_start"] = np.full(nl, 9999); S["hol_end"] = np.full(nl, 9999); S["sicr_flag"] = np.zeros(nl, bool)
        S["shock"] = np.ones(nl); S["shock_until"] = np.full(nl, -1)
        S["rz"] = rng.normal(0, 0.6, nl)  # behavioural risk drift
        S["status"] = np.zeros(nl, dtype=np.int8)  # 0 open, 1 redeemed/closed, 2 written off
        S["bal"] = np.zeros(nl)
        # balance at Jan 2020 for accounts opened before 2020
        old = S["open"] < 0
        el = -S["open"][old]; n_t = S["term"][old]
        r = np.where(S["prod"][old] == MTG, 2.5, np.maximum(S["rate"][old], 3.0)) / 1200
        with np.errstate(over="ignore", invalid="ignore"):
            frac = ((1 + r) ** n_t - (1 + r) ** el) / ((1 + r) ** n_t - 1)
        frac = np.clip(np.nan_to_num(frac), 0, 1)
        amort = np.isin(S["prod"][old], [MTG, PLN, BLN])
        bal_old = np.where(amort, S["amount"][old] * frac, 0.0)
        S["bal"][old] = bal_old
        # accounts fully amortised before 2020 are dropped
        drop = np.zeros(nl, bool)
        drop[np.where(old)[0][amort & (bal_old < 500)]] = True
        S = {key: v[~drop] for key, v in S.items()}
        nl = len(S["prod"])
        # SME business loan rate and cards
        S["base_p0"] = self.base_p0(S["prod"], S["score"])
        S["pd_orig"] = 1 - (1 - S["base_p0"]) ** 12 * 1.0
        S["pd_orig"] = np.clip((1 - (1 - S["base_p0"]) ** 12) * 0.28, 0.0005, 0.5)
        S["first_pay"] = np.where(S["prod"] == BBL, S["open"] + 12, S["open"] + 1)
        self.L = S
        self.l_ids = fmt_ids("L", nl, 8)
        self.log(f"  lending accounts: {nl:,} " + str({PROD_ID[p]: int((S['prod'] == p).sum())
                                                       for p in [MTG, PLN, CCD, BLN, BBL, BCC]}))

    def mortgage_fix_rate(self, t, rtype, ltv):
        M = self.M
        swap = np.where(rtype == 0, at(M["swap2"], t, 1.0), at(M["swap5"], t, 1.3))
        margin = at(M["mtg_margin"], t, 0.9) - np.where(rtype == 1, 0.1, 0.0)
        load = np.where(ltv > 0.85, 0.45, np.where(ltv > 0.75, 0.20, 0.0))
        rate = np.maximum(np.where(rtype == 0, 1.25, 1.45), swap + margin + load)
        return np.round(rate, 2), swap

    @staticmethod
    def base_p0(prod, score):
        base = np.select([prod == MTG, prod == PLN, prod == CCD, prod == BLN, prod == BBL, prod == BCC],
                         [0.0016, 0.0090, 0.0080, 0.0100, 0.0090, 0.0080], 0.01)
        return base * np.array([0.25, 0.6, 1.4, 3.2, 6.0])[score]

    # ---------------- monthly loop -------------------------------------------------
    def run_months(self):
        for t in range(self.n_months):
            t0 = time.time()
            y, mth = PERIODS[t].year, PERIODS[t].month
            nd = self.month_deposits(t, y, mth)
            nl = self.month_loans(t, y, mth)
            ng = self.month_digital(t, y, mth)
            nb = self.month_branches(t, y, mth)
            nc, nf = self.month_conduct(t, y, mth)
            ntx = self.month_transactions(t, y, mth)
            self.log(f"  {y}-{mth:02d}: deposits {nd:,} | loans {nl:,} | digital {ng:,} | branches {nb:,} | "
                     f"complaints {nc:,} | fraud {nf:,} | txn rows {ntx:,} | {time.time() - t0:.1f}s")

    # ---- deposits
    def month_deposits(self, t, y, mth):
        rng, M, d = self.rng, self.M, self.d
        d["z"] = 0.85 * d["z"] + 0.527 * rng.normal(0, 0.25, len(d["z"]))
        act = (d["open"] <= t) & (d["close"] > t)
        ix = np.where(act)[0]
        prod = d["prod"][ix]
        trend = np.select([prod == CUR, prod == EAS, prod == BCA],
                          [M["tr_cur"][t], M["tr_eas"][t], M["tr_bca"][t]], 1.0)
        eom = d["base"][ix] * np.exp(d["z"][ix]) * trend
        prev = d["prev"][ix]
        prev = np.where(prev <= 0, eom * 0.6, prev)
        avg = (prev + eom) / 2
        d["prev"][ix] = eom
        br = M["br"][t]
        rate = np.select([prod == EAS, prod == FTS],
                         [np.maximum(0.01, M["dep_beta"][t] * br + np.array([0, 0.05, 0.10])[d["subseg"][ix]]),
                          d["ft_rate"][ix]], 0.0)
        rate = np.round(rate, 2)
        ftp = np.select([np.isin(prod, [CUR, BCA]), prod == EAS, prod == FTS],
                        [M["hedge"][t], br, d["ft_ftp"][ix]], 0.0)
        int_exp = avg * rate / 1200
        ftp_credit = avg * ftp / 1200
        od = (prod == CUR) & (d["subseg"][ix] == 0) & (rng.random(len(ix)) < 0.08)
        fees = d["pack"][ix] + np.where(od, rng.uniform(5, 25, len(ix)), 0) + \
            np.select([prod == CUR, prod == BCA], [0.9, 1.8], 0.0) + \
            np.where(prod == BCA, 8.5 + rng.gamma(2.0, 8.0, len(ix)) * np.array([1, 3, 8])[d["subseg"][ix]], 0)
        reg = d["region"][ix]
        np.add.at(self.agg["balance"], (t, reg, prod), eom)
        np.add.at(self.agg["nii"], (t, reg, prod), ftp_credit - int_exp)
        np.add.at(self.agg["fees"], (t, reg, prod), fees)
        avg_out = np.round(avg, 2); eom_out = np.round(eom, 2)
        neg = (prod == EAS) & (rng.random(len(ix)) < 0.0002)          # dirty: sign error
        avg_out[neg] *= -1
        df = pd.DataFrame({
            "account_id": self.d_ids[ix], "month_end": MONTH_END[t].date(), "product_id": PROD_ID[prod],
            "avg_balance": avg_out, "eom_balance": eom_out, "customer_rate": rate, "ftp_rate": np.round(ftp, 4),
            "interest_expense": np.round(int_exp, 2), "ftp_credit": np.round(ftp_credit, 2),
            "fee_income": np.round(fees, 2)})
        df = inject_duplicates(df, rng, 0.0005)
        self.W.write(df, "corebanking", "deposit_balance_monthly", y, mth)
        # counts for transactions
        self.dep_counts = {p: np.bincount(reg[prod == p], minlength=N_REG) for p in [CUR, BCA]}
        return len(df)

    # ---- loans
    def month_loans(self, t, y, mth):
        rng, M, S = self.rng, self.M, self.L
        br = M["br"][t]
        alive = (S["open"] <= t) & (S["closed_m"] >= t) & (S["status"] == 0)
        ix = np.where(alive)[0]
        prod = S["prod"][ix]
        n = len(ix)
        new = S["open"][ix] == t
        is_mtg = prod == MTG
        is_card = np.isin(prod, [CCD, BCC])
        # --- new accounts
        bal = S["bal"][ix].copy()
        bal[new & ~is_card] = S["amount"][ix][new & ~is_card]
        new_lending = np.where(new & ~is_card, S["amount"][ix], 0.0)
        # --- variable rates
        rtype = S["rtype"][ix].copy(); rate = S["rate"][ix].copy(); ftp = S["ftp"][ix].copy()
        deal_end = S["deal_end"][ix].copy()
        rate = np.where(is_mtg & (rtype == 2), br + 0.95, rate)
        rate = np.where(is_mtg & (rtype == 3), br + 3.49, rate)
        ftp = np.where(is_mtg & (rtype >= 2), br, ftp)
        rate = np.where(prod == CCD, 22.9 + 0.35 * br, rate)
        rate = np.where(prod == BCC, 19.9 + 0.35 * br, rate)
        rate = np.where(prod == BLN, br + np.array([4.5, 3.8, 3.0])[self.c["subseg"][S["cust"][ix]]], rate)
        ftp = np.where(np.isin(prod, [CCD, BCC, BLN]), br, ftp)
        # --- mortgage deal maturity (product transfer / refinance away / SVR)
        mat = is_mtg & (rtype <= 1) & (deal_end == t) & ~new
        is_pt = np.zeros(n, bool); refi = np.zeros(n, bool)
        if mat.any():
            u = rng.random(n)
            pt = mat & (u < 0.80); refi = mat & (u >= 0.80) & (u < 0.92); svr = mat & (u >= 0.92)
            is_pt = pt
            old_pay = annuity(bal, rate, S["open"][ix] + S["term"][ix] - t)
            new_rt = np.where(rng.random(n) < 0.5, 0, 1)
            ltv_now = bal / np.maximum(S["prop"][ix] * self.hpi_ratio(ix, t), 1)
            nr, nf = self.mortgage_fix_rate(np.full(n, t), new_rt, ltv_now)
            rtype = np.where(pt, new_rt, np.where(svr, 3, rtype))
            rate = np.where(pt, nr, np.where(svr, br + 3.49, rate))
            ftp = np.where(pt, nf, np.where(svr, br, ftp))
            deal_end = np.where(pt, t + np.where(new_rt == 0, 24, 60), np.where(svr, 9999, deal_end))
            new_pay = annuity(bal, rate, S["open"][ix] + S["term"][ix] - t)
            shock = np.where(pt | svr, new_pay / np.maximum(old_pay, 1), 1.0)
            upd = (pt | svr) & (shock > 1.10)
            S["shock"][ix[upd]] = shock[upd]; S["shock_until"][ix[upd]] = t + 18
        # SVR customers switch back to a fix
        sw = is_mtg & (rtype == 3) & (rng.random(n) < 0.05) & ~new
        if sw.any():
            new_rt = np.where(rng.random(n) < 0.5, 0, 1)
            nr, nf = self.mortgage_fix_rate(np.full(n, t), new_rt, np.full(n, 0.7))
            rtype = np.where(sw, new_rt, rtype); rate = np.where(sw, nr, rate); ftp = np.where(sw, nf, ftp)
            deal_end = np.where(sw, t + np.where(new_rt == 0, 24, 60), deal_end)
            is_pt = is_pt | sw
        # --- COVID payment holidays
        if t in (3, 10):
            share = 0.08 if t == 3 else 0.02
            elig = ~new & (S["bucket"][ix] == 0) & np.isin(prod, [MTG, PLN, CCD])
            p = share * np.array([0.5, 0.8, 1.2, 1.8, 2.2])[S["score"][ix]] * np.where(is_mtg, 1.0, 0.4)
            hol = elig & (rng.random(n) < p)
            S["hol_start"][ix[hol]] = t
            S["hol_end"][ix[hol]] = t + np.where(rng.random(hol.sum()) < 0.5, 3, 6)
            S["sicr_flag"][ix[hol]] = rng.random(hol.sum()) < 0.35
        in_hol = (S["hol_start"][ix] <= t) & (S["hol_end"][ix] > t)
        # --- interest & amortisation
        bucket = S["bucket"][ix].copy()
        util = S["util"][ix]
        if is_card.any():
            season = 1.0 + np.where(mth == 12, 0.06, np.where(mth == 1, 0.04, 0.0))
            u_t = np.clip(util * M["util"][t] * season * np.exp(rng.normal(0, 0.08, n)) + 0.08 * bucket, 0, 1.0)
            bal = np.where(is_card, S["limit"][ix] * u_t, bal)
        bom = bal.copy()
        revolve = np.where(is_card, 0.55, 1.0)
        interest = bom * revolve * rate / 1200
        ftp_charge = bom * ftp / 1200
        amort = np.isin(prod, [MTG, PLN, BLN, BBL])
        rem = S["open"][ix] + S["term"][ix] - t
        pay = np.where(amort, annuity(bom, rate, rem), np.where(is_card, np.maximum(25, bom * 0.01 + interest), 0))
        grace = (prod == BBL) & (t < S["first_pay"][ix])
        pay = np.where(in_hol | grace, 0.0, pay)
        paying = amort & ~in_hol & ~grace & (bucket == 0)
        bal = np.where(paying, np.maximum(bom - (pay - interest), 0), bal)
        bal = np.where(amort & in_hol & ~grace, bom + interest, bal)             # holiday: interest capitalised
        # --- arrears transitions
        region = S["region"][ix]
        mult = M["macro"][t] ** np.where(is_mtg, 1.0, 1.2)
        mult = mult * np.where(is_mtg, 1.0, REG_RISK[region])
        mult = mult * np.where(is_mtg, np.where(M["support"][t] < 1, 0.7, 1.0), M["support"][t])
        shock_on = S["shock_until"][ix] >= t
        mult = mult * np.where(is_mtg & shock_on, 1 + 2.0 * (S["shock"][ix] - 1), 1.0)
        ltv_now = np.where(is_mtg, bal / np.maximum(S["prop"][ix] * self.hpi_ratio(ix, t), 1), 0.0)
        mult = mult * np.where(is_mtg, np.where(ltv_now > 0.9, 1.5, np.where(ltv_now > 0.8, 1.2, 1.0)), 1.0)
        mult = mult * np.where(is_card & (bal / np.maximum(S["limit"][ix], 1) > 0.9), 1.6, 1.0)
        S["rz"][ix] = 0.95 * S["rz"][ix] + 0.312 * rng.normal(0, 0.6, n)
        mult = mult * np.exp(S["rz"][ix] - 0.18)
        p0 = np.clip(S["base_p0"][ix] * mult, 0, 0.5)
        eligible = ~new & ~in_hol & ~grace
        u = rng.random(n)
        nb = bucket.copy()
        bbl_ = prod == BBL
        cure = np.select([bucket == 1, bucket == 2, bucket == 3, bucket == 4],
                         [np.where(bbl_, 0.25, 0.45), np.where(bbl_, 0.15, 0.25), np.where(bbl_, 0.10, 0.15), 0.03], 0)
        roll = np.select([bucket == 1, bucket == 2, bucket == 3],
                         [np.where(bbl_, 0.65, 0.40), 0.55, 0.65], 0)
        nb = np.where(eligible & (bucket == 0) & (u < p0), 1, nb)
        in_arr = eligible & (bucket >= 1)
        nb = np.where(in_arr & (u < cure), 0, nb)
        nb = np.where(in_arr & (bucket <= 3) & (u >= cure) & (u < cure + roll), bucket + 1, nb)
        # write-offs from 90+
        wo_rate = np.select([is_mtg, prod == PLN, prod == CCD, prod == BLN, prod == BBL, prod == BCC],
                            [0.02, 0.12, 0.12, 0.08, 0.09, 0.12], 0.1)
        wo = eligible & (bucket == 4) & (u >= cure) & (u < cure + wo_rate)
        S["m90"][ix] = np.where(nb == 4, S["m90"][ix] + 1, 0)
        bucket = nb.astype(np.int8)
        # --- closures (redemption / attrition / maturity / churn)
        u2 = rng.random(n)
        redeem_p = np.select([is_mtg, prod == PLN, is_card, prod == BLN, bbl_], [0.0035, 0.012, 0.003, 0.008, 0.006], 0)
        redeem = ~new & (bucket == 0) & (u2 < redeem_p)
        redeem |= refi
        matured = amort & ~new & (bal <= 1.0)
        churned = (self.c["churn"][S["cust"][ix]] <= t) & (bucket == 0)
        closing = (redeem | matured | churned) & ~wo
        # --- risk parameters
        pd12 = np.clip((1 - (1 - p0) ** 12) * 0.28 * np.array([1, 8, 20, 35, 1])[bucket], 0.0003, 0.95)
        pd12 = np.where(bucket == 4, 1.0, pd12)
        lgd = np.select([is_mtg, prod == PLN, prod == CCD, prod == BLN, bbl_, prod == BCC],
                        [np.clip(1 - 0.75 / np.maximum(ltv_now, 0.01), 0, 1) + 0.03, 0.80, 0.85, 0.55, 0.05, 0.85], 0.8)
        stage = np.where(bucket == 4, 3, np.where(
            (bucket >= 1) | ((pd12 * M["fl"][t] >= 4.0 * S["pd_orig"][ix]) & (pd12 >= 0.004))
            | ((S["score"][ix] >= 3) & (S["rz"][ix] > 0.4)) | (in_hol & S["sicr_flag"][ix])
, 2, 1))
        undrawn = np.where(is_card, np.maximum(S["limit"][ix] - bal, 0), 0)
        ead = bal + undrawn * np.where(stage == 1, 0.4, 0.6)
        rem_y = np.where(is_card, 3.0, np.clip(rem / 12.0, 0.25, np.where(is_mtg, 8, 10)))
        lpd = 1 - (1 - pd12) ** rem_y
        ecl = np.select([stage == 1, stage == 2, stage == 3], [pd12 * lgd * ead, lpd * lgd * ead, lgd * ead])
        ecl = ecl * M["fl"][t]
        wo_amt = np.where(wo, np.where(is_mtg, bal * lgd, bal), 0.0)
        guar = np.where(wo & bbl_, bal, 0.0)
        # fees
        fees = np.where(is_card & (bucket >= 1), 12.0, 0.0)
        fees += np.where(is_mtg & (new | is_pt) & (rng.random(n) < 0.5), 999.0, 0.0)
        fees += np.where((prod == BLN) & new, S["amount"][ix] * 0.01, 0.0)
        fees += np.where(prod == BCC, 2.67, 0.0)
        fees += np.where(is_card, bal * 0.004 + 1.0, 0.0)          # interchange proxy
        # final balances and closures
        bal_out = np.where(closing | wo, 0.0, bal)
        ecl = np.where(closing | wo, 0.0, ecl)
        status = np.where(wo, "Written Off", np.where(closing, "Closed", "Open"))
        # persist state
        S["bal"][ix] = bal; S["bucket"][ix] = bucket; S["rate"][ix] = rate; S["ftp"][ix] = ftp
        S["rtype"][ix] = rtype; S["deal_end"][ix] = deal_end
        if is_card.any():
            S["util"][ix] = np.where(is_card, np.clip(util + 0.02 * (bucket > 0), 0, 1), util)
        S["closed_m"][ix[closing | wo]] = t
        S["status"][ix[closing]] = 1; S["status"][ix[wo]] = 2
        # aggregates
        np.add.at(self.agg["balance"], (t, region, prod), bal_out)
        np.add.at(self.agg["nii"], (t, region, prod), interest - ftp_charge)
        np.add.at(self.agg["fees"], (t, region, prod), fees)
        np.add.at(self.agg["ecl"], (t, region, prod), ecl)
        np.add.at(self.agg["writeoff"], (t, region, prod), wo_amt - guar)
        np.add.at(self.agg["new_lending"], (t, region, prod), new_lending)
        dpd = np.select([bucket == 1, bucket == 2, bucket == 3, bucket == 4],
                        [rng.integers(1, 30, n), rng.integers(30, 60, n), rng.integers(60, 90, n),
                         np.minimum(90 + 30 * (S["m90"][ix].astype(int) - 1) + rng.integers(0, 30, n), 720)], 0)
        stage_out = stage.astype(float)
        stage_out[rng.random(n) < 0.0002] = np.nan            # dirty: missing stage
        df = pd.DataFrame({
            "account_id": self.l_ids[ix], "month_end": MONTH_END[t].date(), "product_id": PROD_ID[prod],
            "rate_type": RATE_TYPES[rtype], "balance_eom": np.round(bal_out, 2),
            "credit_limit": np.where(is_card, S["limit"][ix], np.nan), "customer_rate": np.round(rate, 2),
            "ftp_rate": np.round(ftp, 4), "interest_income": np.round(interest, 2),
            "ftp_charge": np.round(ftp_charge, 2), "fee_income": np.round(fees, 2),
            "scheduled_payment": np.round(pay, 2), "days_past_due": dpd, "arrears_bucket": BUCKETS[bucket],
            "ifrs9_stage": stage_out, "pd_12m": np.round(pd12, 5), "lgd": np.round(lgd, 4),
            "ead": np.round(np.where(closing | wo, 0, ead), 2), "ecl": np.round(ecl, 2),
            "write_off_amount": np.round(wo_amt, 2), "guarantee_claim_amount": np.round(guar, 2),
            "is_payment_holiday": in_hol,
            "deal_end_date": np.where(is_mtg & (rtype <= 1), MONTH_END.values[np.clip(deal_end, 0, 239)],
                                      np.datetime64("NaT")),
            "is_deal_maturity": mat, "is_product_transfer": is_pt,
            "current_ltv": np.where(is_mtg, np.round(ltv_now, 4), np.nan),
            "new_lending_amount": np.round(new_lending, 2), "account_status": status,
        })
        df["deal_end_date"] = pd.to_datetime(df["deal_end_date"]).dt.date
        df = inject_duplicates(df, rng, 0.0003)
        self.W.write(df, "lending", "loan_performance_monthly", y, mth)
        self.card_counts = {p: np.bincount(region[(prod == p) & (status == "Open")], minlength=N_REG)
                            for p in [CCD, BCC]}
        return len(df)

    def hpi_ratio(self, ix, t):
        S, M = self.L, self.M
        g = REG_HPI_G[S["region"][ix]]
        h_t = 1 + (M["hpi"][t] - 1) * g
        h_o = 1 + (hpi_at(M, S["open"][ix]) - 1) * g
        return h_t / h_o

    # ---- digital
    def month_digital(self, t, y, mth):
        rng, c = self.rng, self.c
        act = (c["onb"] <= t) & (c["churn"] > t)
        self.cust_active[t] = np.bincount(c["region"][act], minlength=N_REG)
        ix = np.where(act & (c["reg"] <= t))[0]
        n = len(ix)
        age = c["age"][ix]; sme = c["sme"][ix]
        ramp = 0.85 + 0.20 * t / (N_ACT - 1)
        p_act = np.clip(np.where(sme, 0.80, np.array([0.92, 0.9, 0.85, 0.78, 0.66, 0.48])[age]) * ramp, 0, 0.97)
        active = rng.random(n) < p_act
        lam_web = np.maximum(3.2 - 1.8 * t / N_ACT, 1.0) * np.where(sme, 2.5, 1.0)
        lam_app = (12 + 10 * t / N_ACT) * np.where(age >= 5, 0.5, 1.0) * np.where(sme, 1.3, 1.0)
        web = np.where(active, rng.poisson(lam_web, n), 0)
        app = np.where(active, rng.poisson(lam_app, n), 0)
        feats = np.where(active, rng.binomial(8, min(0.25 + 0.35 * t / N_ACT, 0.65), n), 0)
        df = pd.DataFrame({"customer_id": self.c_ids[ix], "month_end": MONTH_END[t].date(),
                           "web_logins": web, "app_sessions": app, "is_monthly_active": active,
                           "features_used": feats})
        self.W.write(df, "digital", "digital_activity_monthly", y, mth)
        self.app_share = np.bincount(c["region"][ix][active], minlength=N_REG) / np.maximum(self.cust_active[t], 1)
        return n

    # ---- branches
    def month_branches(self, t, y, mth):
        rng = self.rng
        ix = np.where(self.b_close >= t)[0]
        self.branches_open[t] = np.bincount(self.b_reg[self.b_close > t], minlength=N_REG)
        covid = {3: .35, 4: .40, 5: .60, 6: .70, 7: .75, 8: .80, 10: .60, 12: .55, 13: .55, 14: .65}.get(t, 1.0)
        base = np.array([2600, 1200, 900])[self.b_fmt[ix]] * 0.93 ** (t / 12) * covid
        seas = 1.08 if mth == 12 else (0.92 if mth in (1, 8) else 1.0)
        foot = rng.poisson(base * seas * np.exp(rng.normal(0, 0.1, len(ix))))
        df = pd.DataFrame({"branch_id": self.b_ids[ix], "month_end": MONTH_END[t].date(), "footfall": foot,
                           "counter_txn_count": rng.poisson(foot * 1.3),
                           "staff_fte": np.round(np.array([9.0, 3.0, 2.0])[self.b_fmt[ix]] * 0.98 ** (t / 12)
                                                 + rng.normal(0, 0.3, len(ix)), 1),
                           "is_closure_month": self.b_close[ix] == t})
        self.W.write(df, "network", "branch_activity_monthly", y, mth)
        return len(df)

    # ---- complaints & fraud
    def month_conduct(self, t, y, mth):
        rng, c = self.rng, self.c
        act = np.where((c["onb"] <= t) & (c["churn"] > t))[0]
        m_start = MONTH_START[t].to_datetime64().astype("datetime64[D]")
        days = MONTH_END[t].day
        # complaints
        f = 1.0 + (0.20 if 3 <= t <= 8 else 0) + (0.35 if 42 <= t <= 53 else 0) + (0.10 if t >= 57 else 0)
        n = rng.poisson(len(act) * 2.3 / 1000 * f)
        cust = rng.choice(act, n)
        pw = np.array([.18, .05, .12, .14, .05, .08, .10, .12, .10, .06])
        if t >= 57: pw[6] += 0.04
        if 3 <= t <= 8: pw[2] += 0.05
        cat = rng.choice(10, n, p=pw / pw.sum())
        recv = m_start + rng.integers(0, days, n).astype("timedelta64[D]")
        slow = 0.12 if t < 30 else (0.16 if t < 48 else (0.07 if t < 60 else 0.04))
        dur = np.where(rng.random(n) < slow, rng.integers(57, 120, n), np.exp(rng.normal(np.log(12), 0.8, n))).astype(int)
        resolved = recv + dur.astype("timedelta64[D]")
        resolved = np.where(resolved > np.datetime64(LAST_ACTUAL_DATE.date()), np.datetime64("NaT"), resolved)
        bad = rng.random(n) < 0.001                                    # dirty: resolved before received
        resolved[bad] = recv[bad] - np.timedelta64(3, "D")
        upheld = rng.random(n) < 0.38
        comp = pd.DataFrame({
            "complaint_id": [f"CMP{t:02d}{i:06d}" for i in range(n)], "customer_id": self.c_ids[cust],
            "received_date": recv, "resolved_date": resolved, "category_code": [COMPLAINT_CATS[k][0] for k in cat],
            "root_cause": rng.choice(["Service", "Charges and fees", "Delays", "Advice or sales", "Fraud handling",
                                      "System error"], n, p=[.32, .18, .2, .1, .1, .1]),
            "channel": rng.choice(["Telephone", "Branch", "Online", "Letter", "Social Media"], n,
                                  p=[.45, .15, .28, .07, .05]),
            "upheld": upheld,
            "redress_amount": np.round(np.where(upheld, np.exp(rng.normal(np.log(150), 1.0, n)), 0), 2),
            "referred_to_fos": (~upheld) & (rng.random(n) < 0.04),
        })
        late = rng.random(n) < 0.01
        comp_now = pd.concat([getattr(self, "comp_carry", comp.iloc[0:0]), comp[~late]], ignore_index=True)
        self.comp_carry = comp[late] if t < N_ACT - 1 else comp.iloc[0:0]
        if t == N_ACT - 1:
            comp_now = pd.concat([comp_now, comp[late]], ignore_index=True)
        self.W.write(comp_now, "conduct", "complaints", y, mth)
        # fraud
        app_rate = 0.55 + 0.35 * min(t, 30) / 30
        rates = np.array([app_rate, 1.3 * (1.3 if 3 <= t <= 12 else 1.0), 0.3, 0.2])
        nf = rng.poisson(len(act) * rates.sum() / 1000)
        ftype = rng.choice(4, nf, p=rates / rates.sum())
        cust = rng.choice(act, nf)
        loss = np.select([ftype == 0, ftype == 1, ftype == 2, ftype == 3],
                         [np.exp(rng.normal(np.log(900), 1.4, nf)), np.exp(rng.normal(np.log(110), 0.9, nf)),
                          np.exp(rng.normal(np.log(250), 0.8, nf)), np.exp(rng.normal(np.log(1500), 1.1, nf))])
        loss = np.round(np.minimum(loss, 250000), 2)
        rep = m_start + rng.integers(0, days, nf).astype("timedelta64[D]")
        psr = rep >= np.datetime64("2024-10-07")
        full = np.select([ftype == 0, ftype == 1, ftype == 2, ftype == 3],
                         [np.where(psr, 0.90, 0.55), 0.98, 0.97, 0.95], 0.9)
        reimb = np.where(rng.random(nf) < full, np.where((ftype == 0) & psr, np.minimum(loss, 85000), loss),
                         loss * rng.uniform(0, 0.5, nf))
        rec = np.where(ftype == 0, loss * rng.uniform(0, 0.25, nf), 0)
        fr = pd.DataFrame({
            "case_id": [f"FRD{t:02d}{i:06d}" for i in range(nf)], "customer_id": self.c_ids[cust],
            "reported_date": rep,
            "fraud_type": np.array(["APP Scam", "Card Not Present", "Card Present", "Account Takeover"])[ftype],
            "channel": np.where(ftype == 0, rng.choice(["Mobile App", "Online Banking", "Telephony"], nf, p=[.65, .25, .1]),
                                np.where(ftype == 3, "Online Banking", "Card Network")),
            "loss_amount": loss, "reimbursed_amount": np.round(reimb, 2), "recovered_amount": np.round(rec, 2),
            "case_status": np.where(rep > np.datetime64(LAST_ACTUAL_DATE.date()) - np.timedelta64(20, "D"),
                                    "Under Investigation", "Closed"),
        })
        self.W.write(fr, "conduct", "fraud_cases", y, mth)
        return len(comp_now), nf

    # ---- transactions (daily aggregates)
    TXN = [  # product, type, channel code, per-account monthly rate, avg value, weekday profile
        (CUR, "Card Payment", "CH06", 30.0, 32, "card"), (CUR, "Direct Debit", "CH07", 7.0, 110, "auto"),
        (CUR, "Standing Order", "CH07", 1.5, 250, "auto"), (CUR, "Faster Payment", "*FP", 6.0, 280, "fp"),
        (CUR, "Cash Withdrawal", "*CW", 3.0, 70, "cash"), (CUR, "Cash Deposit", "*CD", 0.4, 300, "branch"),
        (CUR, "Cheque", "*CQ", 0.1, 450, "branch"),
        (CCD, "Card Payment", "CH06", 9.0, 55, "card"), (CCD, "Cash Withdrawal", "CH05", 0.15, 120, "cash"),
        (BCA, "Card Payment", "CH06", 25.0, 85, "card"), (BCA, "Direct Debit", "CH07", 10.0, 600, "auto"),
        (BCA, "Faster Payment", "*FP", 20.0, 2200, "fp"), (BCA, "Bulk Payment", "CH02", 1.2, 12000, "auto"),
        (BCA, "Cash Deposit", "*CD", 2.0, 1500, "branch"), (BCA, "Cheque", "*CQ", 1.0, 2500, "branch"),
        (BCC, "Card Payment", "CH06", 14.0, 140, "card"),
    ]

    def month_transactions(self, t, y, mth):
        rng = self.rng
        days = pd.date_range(MONTH_START[t], MONTH_END[t])
        nd = len(days)
        dow = days.dayofweek.values
        hol = np.isin(days.strftime("%Y-%m-%d"), UK_BANK_HOLIDAYS)
        prof = {"card": np.array([.9, .95, .97, 1.02, 1.15, 1.2, .8]), "auto": np.array([1.3, 1.2, 1.2, 1.2, 1.3, .1, .05]),
                "fp": np.array([1.1, 1.05, 1.05, 1.05, 1.2, .8, .6]), "cash": np.array([.95, .9, .9, 1.0, 1.25, 1.2, .7]),
                "branch": np.array([1.2, 1.1, 1.1, 1.1, 1.2, .5, .0])}
        yrs = t / 12.0
        infl = 1.0 + np.interp(t, [0, 24, 44, 79], [0, 0.03, 0.14, 0.20])
        covid_card = {3: .70, 4: .75, 5: .85, 12: .80, 13: .82, 14: .90}.get(t, 1.0)
        covid_cash = {3: .45, 4: .5, 5: .6, 6: .7, 12: .6, 13: .62, 14: .7}.get(t, 1.0)
        dec = 1.12 if mth == 12 else 1.0
        # channel shares (time-varying)
        s_app = np.interp(t, [0, 79], [0.38, 0.76]); s_web = np.interp(t, [0, 79], [0.42, 0.18])
        s_tel = np.interp(t, [0, 79], [0.07, 0.02]); s_br = max(1 - s_app - s_web - s_tel, 0.02)
        fp_split = [("CH03", s_app), ("CH02", s_web), ("CH04", s_tel), ("CH01", s_br)]
        cw_split = [("CH05", 0.92), ("CH01", 0.08)]
        cd_split = [("CH01", np.interp(t, [0, 79], [0.75, 0.55])), ("CH05", np.interp(t, [0, 79], [0.25, 0.45]))]
        cq_split = [("CH01", np.interp(t, [0, 79], [0.55, 0.25])), ("CH03", np.interp(t, [0, 79], [0.45, 0.75]))]
        splits = {"*FP": fp_split, "*CW": cw_split, "*CD": cd_split, "*CQ": cq_split}
        counts_by_prod = {CUR: self.dep_counts[CUR], BCA: self.dep_counts[BCA], CCD: self.card_counts[CCD],
                          BCC: self.card_counts[BCC]}
        frames = []
        for prod, ttype, ch, rate, val, pk in self.TXN:
            n_acc = counts_by_prod[prod].astype(float)                  # per region
            trend = {"Card Payment": 1.05 ** yrs * covid_card * dec, "Cash Withdrawal": 0.90 ** yrs * covid_cash,
                     "Cash Deposit": 0.93 ** yrs * covid_cash, "Cheque": 0.85 ** yrs,
                     "Faster Payment": 1.08 ** yrs}.get(ttype, 1.0)
            w = prof[pk][dow] * np.where(hol, 0.15 if pk in ("auto", "branch") else 0.9, 1.0)
            w = w / w.mean()
            exp_daily = np.outer(w, n_acc) * rate * trend / nd                   # [day, region]
            for chc, share in (splits[ch] if ch.startswith("*") else [(ch, 1.0)]):
                e = exp_daily * share
                if chc == "CH01":
                    e = e * np.where(dow == 6, 0.0, 1.0)[:, None] * np.where(hol, 0.0, 1.0)[:, None] * \
                        (self.branches_open[t] / np.maximum(self.branches_open[0], 1))[None, :] ** 0.5
                cnt = rng.poisson(e)
                v = cnt * val * infl * np.exp(rng.normal(0, 0.05, cnt.shape))
                keep = cnt > 0
                di, ri = np.where(keep)
                frames.append(pd.DataFrame({"txn_date": days.date[di], "region_code": REG_CODE[ri],
                                            "product_id": PROD_ID[prod], "channel_code": chc, "txn_type": ttype,
                                            "txn_count": cnt[keep], "txn_value": np.round(v[keep], 2)}))
        df = pd.concat(frames, ignore_index=True)
        messy = rng.random(len(df)) < 0.001                                     # dirty: lowercase region code
        df.loc[messy, "region_code"] = df.loc[messy, "region_code"].str.lower()
        self.W.write(df, "payments", "transactions_daily", y, mth)
        return len(df)

    # ---------------- finance: opex & budget --------------------------------------
    def gen_finance(self):
        rng, A = self.rng, self.agg
        T = self.n_months
        income = (A["nii"][:T] + A["fees"][:T]).sum(axis=(1, 2))              # per month, all regions
        cust = self.cust_active[:T]; br = self.branches_open[:T]
        tt = np.arange(T)
        drv = {
            "Staff": 0.6 * br / br[0].sum() + 0.4 * cust / cust[0].sum(),
            "Premises": br / br[0].sum() + 0.1 * cust / cust[0].sum(),
            "Technology": cust / cust[0].sum() * (1.06 ** (tt / 12))[:, None],
            "Marketing": cust / cust[0].sum() * np.array([1.3 if PERIODS[i].month in (1, 9) else 1.0 for i in tt])[:, None],
            "Other": cust / cust[0].sum() * np.array([3.0 if i in (14, 50) else 1.0 for i in tt])[:, None],
        }
        share = {"Staff": .45, "Premises": .12, "Technology": .22, "Marketing": .06, "Other": .15}
        infl = 1 + np.interp(tt, [0, 24, 48, 79], [0, 0.02, 0.14, 0.22])
        for k in ("Staff", "Technology", "Other", "Premises"):
            drv[k] = drv[k] * infl[:, None]
        raw = sum(drv[k] * share[k] for k in drv).sum(axis=1)
        kfac = 0.52 * income.sum() / raw.sum()
        rows = []
        for k in drv:
            actual = drv[k] * share[k] * kfac * np.exp(rng.normal(0, 0.03, drv[k].shape))
            for t in range(N_BUD):
                if t < T:
                    a = actual[t]; b = a * np.exp(rng.normal(0, 0.03, N_REG))
                else:
                    a = np.full(N_REG, np.nan); b = actual[T - 12 + (t - T) % 12] * 1.03   # budget run-rate
                for r in range(N_REG):
                    rows.append((REG_CODE[r], MONTH_END[t].date(), k, a[r], b[r]))
        opex = pd.DataFrame(rows, columns=["region_code", "month_end", "cost_category", "actual_amount", "budget_amount"])
        opex[["actual_amount", "budget_amount"]] = opex[["actual_amount", "budget_amount"]].round(2)
        self.W.write(opex, "finance", "opex_monthly")
        # budget by region x month x product
        imp = np.zeros_like(A["ecl"][:T])
        imp[1:] = A["ecl"][1:T] - A["ecl"][:T - 1]; imp[0] = A["ecl"][0] * 0.02
        imp = imp + A["writeoff"][:T]
        bias = {  # year: (balance, nii, fees, impairment)
            2020: (0.97, 1.08, 1.02, 0.55), 2021: (0.95, 1.00, 1.00, 1.60), 2022: (0.99, 0.92, 1.00, 0.90),
            2023: (1.00, 0.97, 1.01, 0.85), 2024: (1.01, 1.03, 1.00, 1.05), 2025: (1.00, 1.00, 1.00, 1.00),
            2026: (1.00, 0.96, 1.01, 0.90)}
        rows = []
        for t in range(N_BUD):
            yr = PERIODS[t].year
            b = bias[yr]
            src = t if t < T else T - 1
            g = 1.0 if t < T else (1.002 ** (t - T + 1))
            gn = 1.0 if t < T else (0.995 ** (t - T + 1))
            for r in range(N_REG):
                for p in range(N_PROD):
                    noise = np.exp(rng.normal(0, 0.02, 4))
                    ib = b[3] * (0.75 if (yr == 2026 and REG_CODE[r] == "NE") else 1.0)
                    # smooth impairment budget (3m average) to avoid replicating actual volatility
                    imp_s = imp[max(0, src - 2):src + 1, r, p].mean()
                    rows.append((REG_CODE[r], MONTH_END[t].date(), PROD_ID[p],
                                 A["balance"][src, r, p] * b[0] * g * noise[0], A["nii"][src, r, p] * b[1] * gn * noise[1],
                                 A["fees"][src, r, p] * b[2] * noise[2], max(imp_s, 0) * ib * noise[3]))
        bud = pd.DataFrame(rows, columns=["region_code", "month_end", "product_id", "budget_balance", "budget_nii",
                                          "budget_fees", "budget_impairment"])
        bud[bud.columns[3:]] = bud[bud.columns[3:]].round(2)
        self.W.write(bud, "finance", "budget_monthly")
        self.log(f"  opex rows: {len(opex):,} | budget rows: {len(bud):,}")

    # ---------------- accounts dimension ------------------------------------------
    def write_accounts(self):
        rng, d, S = self.rng, self.d, self.L
        dep = pd.DataFrame({
            "account_id": self.d_ids, "customer_id": self.c_ids[d["cust"]], "product_id": PROD_ID[d["prod"]],
            "branch_id": self.b_ids[self.c["branch"][d["cust"]]],
            "open_date": month_idx_to_date(d["open"], rng, "random"),
            "close_date": np.where(d["close"] < N_ACT, month_idx_to_date(np.minimum(d["close"], N_ACT), rng, "random"),
                                   np.datetime64("NaT")),
            "account_status": np.where(d["close"] < N_ACT, "Closed", "Open"),
            "original_amount": np.nan, "term_months": np.where(d["prod"] == FTS, 12, np.nan),
            "origination_rate": np.where(d["prod"] == FTS, d["ft_rate"], np.nan), "origination_ltv": np.nan,
        })
        stat = np.array(["Open", "Closed", "Written Off"])[S["status"]]
        lo = pd.DataFrame({
            "account_id": self.l_ids, "customer_id": self.c_ids[S["cust"]], "product_id": PROD_ID[S["prod"]],
            "branch_id": self.b_ids[self.c["branch"][S["cust"]]],
            "open_date": month_idx_to_date(S["open"], rng, "random"),
            "close_date": np.where(S["closed_m"] < N_ACT, month_idx_to_date(np.minimum(S["closed_m"], N_ACT), rng, "random"),
                                   np.datetime64("NaT")),
            "account_status": stat,
            "original_amount": np.where(np.isin(S["prod"], [CCD, BCC]), S["limit"], S["amount"]),
            "term_months": np.where(np.isin(S["prod"], [CCD, BCC]), np.nan, S["term"]),
            "origination_rate": np.where(np.isin(S["prod"], [CCD, BCC]), np.nan, S["rate"]),
            "origination_ltv": np.where(S["prod"] == MTG, np.round(S["ltv"], 4), np.nan),
        })
        acc = pd.concat([dep, lo], ignore_index=True)
        self.W.write(inject_duplicates(acc, rng, 0.001), "corebanking", "accounts")
        self.log(f"  accounts written: {len(acc):,}")

    # ---------------- run ------------------------------------------------------------
    def run(self):
        t0 = time.time()
        self.log("[1/6] reference data"); self.gen_reference()
        self.log("[2/6] branches"); self.gen_branches()
        self.log("[3/6] customers"); self.gen_customers()
        self.log("[4/6] accounts"); self.gen_deposit_accounts(); self.gen_loan_accounts()
        self.log(f"[5/6] monthly facts ({self.n_months} months)"); self.run_months()
        self.log("[6/6] finance + accounts dimension"); self.gen_finance(); self.write_accounts()
        man = self.W.manifest
        (self.W.root / "manifest.json").write_text(json.dumps({
            "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"), "scale": self.scale,
            "period": "2020-01 to 2026-08", "total_rows": sum(m["rows"] for m in man),
            "total_bytes": sum(m["bytes"] for m in man), "files": man}, indent=1))
        tot = sum(m["rows"] for m in man); size = sum(m["bytes"] for m in man) / 1e6
        self.log(f"\nDONE in {(time.time() - t0) / 60:.1f} min | {len(man):,} files | {tot:,} rows | {size:,.0f} MB")


def main():
    ap = argparse.ArgumentParser(description="Lloyds Banking Group synthetic data generator (hypothetical data)")
    ap.add_argument("--scale", type=float, default=1.0, help="1.0 = ~500k customers (default)")
    ap.add_argument("--out", type=str, default=str(Path(__file__).resolve().parent.parent / "data"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--months", type=int, default=N_ACT, help="for testing: generate only the first N months")
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists() and any(out.iterdir()):
        print(f"WARNING: output folder {out} is not empty. Files will be overwritten.")
    out.mkdir(parents=True, exist_ok=True)
    print(f"Lloyds synthetic data | scale={a.scale} | out={out}")
    Generator(a.scale, out, a.seed, a.months).run()


if __name__ == "__main__":
    main()
