"""
Lloyds portfolio | builds the Power BI TMDL scripts
  02_model.tmdl    calculated tables (segment, brand, bridge steps, measures table), relationships, RLS roles
  03_measures.tmdl all DAX measures (display folders 00 to 07)
  measures_catalog.md  documentation of every measure
Paste each .tmdl into Power BI Desktop > TMDL view > Apply.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent
GBP_M = r'£#,0'
GBP_K = r'£#,0'
GBP = r'£#,0'
PCT1 = '0.0%'
PCT2 = '0.00%'
INT = '#,0'
M = []  # (folder, name, format, expression, description)


def m(folder, name, fmt, expr, desc=""):
    M.append((folder, name, fmt, expr.strip("\n"), desc))


PE = """VAR _d = EOMONTH ( [Period End Date], 0 )
VAR _k = YEAR ( _d ) * 10000 + MONTH ( _d ) * 100 + DAY ( _d )"""


def at_end(expr_sum, extra=""):
    """balance-type measure evaluated at the last actual month of the selected period"""
    return f"""{PE}
RETURN
    CALCULATE ( {expr_sum}, REMOVEFILTERS ( dim_date ), dim_date[DateKey] = _k{extra} )"""


def at_end_py(measure):
    return f"""VAR _d = EOMONTH ( EDATE ( [Period End Date], -12 ), 0 )
VAR _k = YEAR ( _d ) * 10000 + MONTH ( _d ) * 100 + DAY ( _d )
RETURN
    CALCULATE ( {measure}, REMOVEFILTERS ( dim_date ), dim_date[DateKey] = _k )"""


def py_flow(measure):
    return f"""VAR _start = EDATE ( MIN ( dim_date[Date] ), -12 )
VAR _end = EOMONTH ( EDATE ( [Period End Date], -12 ), 0 )
RETURN
    CALCULATE ( {measure}, REMOVEFILTERS ( dim_date ), DATESBETWEEN ( dim_date[Date], _start, _end ) )"""


# ============================== 00 Helpers ==============================
m("00 Helpers", "Last Actual Date", "dd mmm yyyy",
  "CALCULATE ( MAX ( dim_date[Date] ), REMOVEFILTERS ( dim_date ), dim_date[IsActualPeriod] = TRUE () )",
  "Last month with actual data (31 Aug 2026).")
m("00 Helpers", "Period End Date", "dd mmm yyyy",
  "MIN ( MAX ( dim_date[Date] ), [Last Actual Date] )",
  "End of the selected period, capped at the last actual date. Balance KPIs are read at this date.")
m("00 Helpers", "Months In Period", INT, """VAR _l = [Last Actual Date]
RETURN
    COUNTROWS ( FILTER ( VALUES ( dim_date[MonthEnd] ), dim_date[MonthEnd] <= _l ) )""",
  "Number of actual months in the selection (used to annualise).")
m("00 Helpers", "Data As Of", "", 'FORMAT ( [Last Actual Date], "dd mmm yyyy", "en-GB" )')
m("00 Helpers", "Selected Period Label", "", """VAR _s = MIN ( dim_date[Date] )
VAR _e = [Period End Date]
RETURN
    FORMAT ( _s, "mmm yyyy", "en-GB" ) & " to " & FORMAT ( _e, "mmm yyyy", "en-GB" )""")
m("00 Helpers", "Selected Region Title", "", """IF (
    HASONEVALUE ( dim_region[RegionName] ),
    VALUES ( dim_region[RegionName] ) & " | Regional Director: " & VALUES ( dim_region[RegionalDirector] ),
    "All UK regions"
)""", "Dynamic title for the Region Deep Dive drill-through page.")

# ============================== 01 Income ==============================
FP = "fact_product_monthly"
m("01 Income", "Interest Income", GBP_M, f"SUM ( {FP}[InterestIncome] )")
m("01 Income", "Interest Expense", GBP_M, f"SUM ( {FP}[InterestExpense] )")
m("01 Income", "FTP Credit", GBP_M, f"SUM ( {FP}[FTPCredit] )", "Funds transfer pricing credit earned by deposits.")
m("01 Income", "FTP Charge", GBP_M, f"SUM ( {FP}[FTPCharge] )", "Funds transfer pricing charge paid by loans.")
m("01 Income", "NII", GBP_M, "[Interest Income] - [FTP Charge] + [FTP Credit] - [Interest Expense]",
  "Net Interest Income on a funds transfer pricing basis (product view).")
m("01 Income", "NII PY", GBP_M, py_flow("[NII]"), "Same months of the prior year.")
m("01 Income", "NII YoY %", PCT1, "DIVIDE ( [NII] - [NII PY], [NII PY] )")
m("01 Income", "NII Budget", GBP_M, """VAR _l = [Last Actual Date]
RETURN
    CALCULATE ( SUM ( fact_budget_monthly[BudgetNII] ), KEEPFILTERS ( dim_date[Date] <= _l ) )""",
  "Budget for the actual months of the selection.")
m("01 Income", "NII Budget Full Year", GBP_M, "SUM ( fact_budget_monthly[BudgetNII] )")
m("01 Income", "NII vs Budget", GBP_M, "[NII] - [NII Budget]")
m("01 Income", "NII vs Budget %", PCT1, "DIVIDE ( [NII] - [NII Budget], [NII Budget] )")
m("01 Income", "Fee Income", GBP_M, f"SUM ( {FP}[FeeIncome] )")
m("01 Income", "Fee Income PY", GBP_M, py_flow("[Fee Income]"))
m("01 Income", "Fee Income YoY %", PCT1, "DIVIDE ( [Fee Income] - [Fee Income PY], [Fee Income PY] )")
m("01 Income", "Fee Income Budget", GBP_M, """VAR _l = [Last Actual Date]
RETURN
    CALCULATE ( SUM ( fact_budget_monthly[BudgetFees] ), KEEPFILTERS ( dim_date[Date] <= _l ) )""")
m("01 Income", "Total Income", GBP_M, "[NII] + [Fee Income]")
m("01 Income", "Total Income PY", GBP_M, "[NII PY] + [Fee Income PY]")
m("01 Income", "Operating Costs", GBP_M, "SUM ( fact_opex_monthly[ActualAmount] )",
  "Opex by region and cost category (not allocated to products).")
m("01 Income", "Operating Costs PY", GBP_M, py_flow("[Operating Costs]"))
m("01 Income", "Operating Costs Budget", GBP_M, """VAR _l = [Last Actual Date]
RETURN
    CALCULATE ( SUM ( fact_opex_monthly[BudgetAmount] ), KEEPFILTERS ( dim_date[Date] <= _l ) )""")
m("01 Income", "Cost Income Ratio", PCT1, "DIVIDE ( [Operating Costs], [Total Income] )")
m("01 Income", "Cost Income Ratio PY", PCT1, "DIVIDE ( [Operating Costs PY], [Total Income PY] )")
m("01 Income", "Cost Income Ratio Change pp", "+0.0;-0.0;0.0",
  "( [Cost Income Ratio] - [Cost Income Ratio PY] ) * 100", "Change in percentage points.")

# ============================== 02 Balance sheet ==============================
m("02 Balance Sheet", "Customer Deposits", GBP_M,
  at_end(f"SUM ( {FP}[EOMBalance] )", ', dim_product[ProductGroup] = "Deposits"'), "End of period balance.")
m("02 Balance Sheet", "Customer Deposits PY", GBP_M, at_end_py("[Customer Deposits]"))
m("02 Balance Sheet", "Customer Deposits YoY %", PCT1,
  "DIVIDE ( [Customer Deposits] - [Customer Deposits PY], [Customer Deposits PY] )")
m("02 Balance Sheet", "Current Account Balances", GBP_M,
  at_end(f"SUM ( {FP}[EOMBalance] )", ', dim_product[ProductID] IN { "P01", "P07" }'))
m("02 Balance Sheet", "Savings Balances", GBP_M,
  at_end(f"SUM ( {FP}[EOMBalance] )", ', dim_product[ProductID] IN { "P02", "P03" }'))
m("02 Balance Sheet", "Fixed Term Savings", GBP_M,
  at_end(f"SUM ( {FP}[EOMBalance] )", ', dim_product[ProductID] = "P03"'))
m("02 Balance Sheet", "Fixed Term Share of Deposits", PCT1, "DIVIDE ( [Fixed Term Savings], [Customer Deposits] )",
  "Deposit migration indicator.")
m("02 Balance Sheet", "Loan Book", GBP_M,
  at_end(f"SUM ( {FP}[EOMBalance] )", ', dim_product[ProductGroup] = "Lending"'), "Gross customer loans, end of period.")
m("02 Balance Sheet", "Loan Book PY", GBP_M, at_end_py("[Loan Book]"))
m("02 Balance Sheet", "Loan Book YoY %", PCT1, "DIVIDE ( [Loan Book] - [Loan Book PY], [Loan Book PY] )")
m("02 Balance Sheet", "ECL Stock", GBP_M, at_end(f"SUM ( {FP}[ECL] )"), "Expected credit loss allowance, end of period.")
m("02 Balance Sheet", "Net Loans", GBP_M, "[Loan Book] - [ECL Stock]")
m("02 Balance Sheet", "Net Loans PY", GBP_M, at_end_py("[Net Loans]"))
m("02 Balance Sheet", "Net Loans YoY %", PCT1, "DIVIDE ( [Net Loans] - [Net Loans PY], [Net Loans PY] )")
m("02 Balance Sheet", "Loan to Deposit Ratio", PCT1, "DIVIDE ( [Loan Book], [Customer Deposits] )")
m("02 Balance Sheet", "Avg Loan Balance", GBP_M, """VAR _l = [Last Actual Date]
RETURN
    AVERAGEX (
        FILTER ( VALUES ( dim_date[MonthEnd] ), dim_date[MonthEnd] <= _l ),
        CALCULATE ( SUM ( fact_product_monthly[EOMBalance] ), dim_product[ProductGroup] = "Lending" )
    )""", "Average of month-end loan balances in the period (NIM denominator).")
m("02 Balance Sheet", "NIM", PCT2, "DIVIDE ( [NII] * 12 / [Months In Period], [Avg Loan Balance] )",
  "Net interest margin: annualised NII over average customer loans.")
m("02 Balance Sheet", "NIM PY", PCT2, py_flow("[NIM]"))
m("02 Balance Sheet", "NIM Change bps", "+0;-0;0", "( [NIM] - [NIM PY] ) * 10000", "Change in basis points.")
m("02 Balance Sheet", "Bank Rate", PCT2, "DIVIDE ( AVERAGE ( fact_bank_rate_daily[BankRate] ), 100 )",
  "Average Bank of England Bank Rate in the period (real data).")
m("02 Balance Sheet", "Bank Rate Period End", PCT2, """VAR _d = [Period End Date]
RETURN
    CALCULATE ( DIVIDE ( MAX ( fact_bank_rate_daily[BankRate] ), 100 ), REMOVEFILTERS ( dim_date ), dim_date[Date] = _d )""")
m("02 Balance Sheet", "Customer Rate Deposits", PCT2, f"""CALCULATE (
    DIVIDE ( SUM ( {FP}[RateXBalance] ), SUM ( {FP}[AvgBalance] ) ) / 100,
    dim_product[ProductGroup] = "Deposits"
)""", "Balance-weighted average rate paid on deposits.")
m("02 Balance Sheet", "Customer Rate Loans", PCT2, f"""CALCULATE (
    DIVIDE ( SUM ( {FP}[RateXBalance] ), SUM ( {FP}[EOMBalance] ) ) / 100,
    dim_product[ProductGroup] = "Lending"
)""")
m("02 Balance Sheet", "Deposit Beta", PCT1, """VAR _cur = [Customer Rate Deposits]
VAR _br = [Bank Rate]
RETURN
    DIVIDE ( _cur, _br )""", "Share of Bank Rate passed to depositors.")

# ============================== 02b NII bridge ==============================
m("03 NII Bridge", "Balance Months", GBP_M, f"SUM ( {FP}[AvgBalance] )", "Sum of monthly average balances (volume driver).")
m("03 NII Bridge", "Balance Months PY", GBP_M, py_flow("[Balance Months]"))
m("03 NII Bridge", "Bridge Volume Effect", GBP_M, """SUMX (
    VALUES ( dim_product[ProductID] ),
    VAR _mpy = DIVIDE ( [NII PY], [Balance Months PY] )
    RETURN ( [Balance Months] - [Balance Months PY] ) * _mpy
)""", "NII change explained by balance growth at prior-year margin, per product.")
m("03 NII Bridge", "Bridge Margin Effect", GBP_M, """SUMX (
    VALUES ( dim_product[ProductID] ),
    VAR _mcy = DIVIDE ( [NII], [Balance Months] )
    VAR _mpy = DIVIDE ( [NII PY], [Balance Months PY] )
    RETURN ( _mcy - _mpy ) * [Balance Months]
)""", "NII change explained by margin change (rates, deposit beta, repricing), per product.")
m("03 NII Bridge", "Bridge Other", GBP_M, "[NII] - [NII PY] - [Bridge Volume Effect] - [Bridge Margin Effect]",
  "Residual (new products, rounding).")
m("03 NII Bridge", "NII Bridge Value", GBP_M, """SWITCH (
    SELECTEDVALUE ( bridge_steps[Order] ),
    1, [NII PY],
    2, [Bridge Volume Effect],
    3, [Bridge Margin Effect],
    4, [Bridge Other]
)""", "Waterfall: categories bridge_steps[Step] sorted by Order; total = current period NII.")

# ============================== 04 Credit risk ==============================
m("04 Credit Risk", "Gross New Lending", GBP_M, f"SUM ( {FP}[NewLending] )")
m("04 Credit Risk", "Gross New Lending PY", GBP_M, py_flow("[Gross New Lending]"))
m("04 Credit Risk", "Gross New Lending YoY %", PCT1,
  "DIVIDE ( [Gross New Lending] - [Gross New Lending PY], [Gross New Lending PY] )")
for s in (1, 2, 3):
    m("04 Credit Risk", f"Stage {s} Balance", GBP_M, at_end(f"SUM ( {FP}[Stage{s}Balance] )"))
    m("04 Credit Risk", f"Stage {s} Share", PCT1, f"DIVIDE ( [Stage {s} Balance], [Loan Book] )")
m("04 Credit Risk", "Stage 2 Share PY", PCT1, at_end_py("[Stage 2 Share]"))
m("04 Credit Risk", "Stage 2 Share Change pp", "+0.0;-0.0;0.0", "( [Stage 2 Share] - [Stage 2 Share PY] ) * 100")
m("04 Credit Risk", "Arrears 90+ Balance", GBP_M, at_end(f"SUM ( {FP}[Arrears90Balance] )"))
m("04 Credit Risk", "Arrears 90+ Rate", PCT2, "DIVIDE ( [Arrears 90+ Balance], [Loan Book] )")
m("04 Credit Risk", "Arrears 90+ Rate PY", PCT2, at_end_py("[Arrears 90+ Rate]"))
m("04 Credit Risk", "Arrears 90+ Change bps", "+0;-0;0", "( [Arrears 90+ Rate] - [Arrears 90+ Rate PY] ) * 10000")
m("04 Credit Risk", "Arrears 30+ Balance", GBP_M, at_end(f"SUM ( {FP}[Arrears30Balance] )"))
m("04 Credit Risk", "Arrears 30+ Rate", PCT2, "DIVIDE ( [Arrears 30+ Balance], [Loan Book] )")
m("04 Credit Risk", "ECL Coverage", PCT2, "DIVIDE ( [ECL Stock], [Loan Book] )")
m("04 Credit Risk", "ECL Coverage PY", PCT2, at_end_py("[ECL Coverage]"))
m("04 Credit Risk", "ECL Coverage Change bps", "+0;-0;0", "( [ECL Coverage] - [ECL Coverage PY] ) * 10000")
m("04 Credit Risk", "ECL Opening", GBP_M, f"""VAR _d = EOMONTH ( MIN ( dim_date[Date] ), -1 )
VAR _k = YEAR ( _d ) * 10000 + MONTH ( _d ) * 100 + DAY ( _d )
RETURN
    CALCULATE ( SUM ( {FP}[ECL] ), REMOVEFILTERS ( dim_date ), dim_date[DateKey] = _k )""",
  "ECL at the end of the month before the period starts.")
m("04 Credit Risk", "Net Write-offs", GBP_M, f"SUM ( {FP}[WriteOff] ) - SUM ( {FP}[GuaranteeClaim] )",
  "Write-offs net of the government guarantee (Bounce Back Loans).")
m("04 Credit Risk", "Impairment Charge", GBP_M, "[ECL Stock] - [ECL Opening] + [Net Write-offs]",
  "P&L charge: change in ECL allowance plus net write-offs.")
m("04 Credit Risk", "Impairment Budget", GBP_M, """VAR _l = [Last Actual Date]
RETURN
    CALCULATE ( SUM ( fact_budget_monthly[BudgetImpairment] ), KEEPFILTERS ( dim_date[Date] <= _l ) )""")
m("04 Credit Risk", "Cost of Risk", PCT2, "DIVIDE ( [Impairment Charge] * 12 / [Months In Period], [Avg Loan Balance] )",
  "Annualised impairment charge over average loans.")
m("04 Credit Risk", "Cost of Risk PY", PCT2, py_flow("[Cost of Risk]"))
m("04 Credit Risk", "Cost of Risk Change bps", "+0;-0;0", "( [Cost of Risk] - [Cost of Risk PY] ) * 10000")
m("04 Credit Risk", "Payment Holiday Balance", GBP_M, f"SUM ( {FP}[PaymentHolidayBalance] )",
  "Use by month (COVID payment deferrals, 2020).")
CR = "fact_credit_risk_monthly"
m("04 Credit Risk", "Risk Balance", GBP_M, at_end(f"SUM ( {CR}[Balance] )"),
  "Loan balance from the credit risk mart (heatmap, stage mix by score / LTV).")
m("04 Credit Risk", "Risk 90+ Balance", GBP_M, at_end(f"SUM ( {CR}[Balance] )", f', {CR}[ArrearsBucket] = "90+"'))
m("04 Credit Risk", "Risk 90+ Rate", PCT2, "DIVIDE ( [Risk 90+ Balance], [Risk Balance] )",
  "90+ arrears rate for heatmaps (LTV band x credit score).")
m("04 Credit Risk", "Risk ECL", GBP_M, at_end(f"SUM ( {CR}[ECL] )"))
m("04 Credit Risk", "Risk ECL Coverage", PCT2, "DIVIDE ( [Risk ECL], [Risk Balance] )")
m("04 Credit Risk", "Risk EAD", GBP_M, at_end(f"SUM ( {CR}[EAD] )"))
m("04 Credit Risk", "Risk PD x EAD", GBP_M, at_end(f"SUM ( {CR}[PDxEAD] )"))
m("04 Credit Risk", "Risk Avg PD", PCT2, "DIVIDE ( [Risk PD x EAD], [Risk EAD] )", "EAD-weighted 12-month PD.")
MM = "fact_mortgage_maturity"
m("04 Credit Risk", "Maturing Fixed Balance", GBP_M, f"SUM ( {MM}[Balance] )",
  "Remortgage wall: fixed-rate balances by deal end quarter (snapshot at last actual month).")
m("04 Credit Risk", "Maturing Fixed Accounts", INT, f"SUM ( {MM}[Accounts] )")
m("04 Credit Risk", "Maturing Avg Current Rate", PCT2, f"DIVIDE ( SUM ( {MM}[RateXBalance] ), SUM ( {MM}[Balance] ) ) / 100")
m("04 Credit Risk", "Maturing Next 12M Balance", GBP_M, f"""VAR _l = [Last Actual Date]
VAR _lk = YEAR ( _l ) * 10000 + MONTH ( _l ) * 100 + DAY ( _l )
VAR _e = EOMONTH ( _l, 12 )
VAR _ek = YEAR ( _e ) * 10000 + MONTH ( _e ) * 100 + DAY ( _e )
RETURN
    CALCULATE ( SUM ( {MM}[Balance] ), {MM}[DealEndMonthKey] > _lk, {MM}[DealEndMonthKey] <= _ek )""")
RP = "fact_mortgage_repricing"
m("04 Credit Risk", "Repricings", INT, f"SUM ( {RP}[Repricings] )")
m("04 Credit Risk", "Repricing Old Rate", PCT2, f"DIVIDE ( SUM ( {RP}[OldRateXBalance] ), SUM ( {RP}[Balance] ) ) / 100")
m("04 Credit Risk", "Repricing New Rate", PCT2, f"DIVIDE ( SUM ( {RP}[NewRateXBalance] ), SUM ( {RP}[Balance] ) ) / 100")
m("04 Credit Risk", "Payment Shock %", PCT1, f"DIVIDE ( SUM ( {RP}[NewPayment] ), SUM ( {RP}[OldPayment] ) ) - 1",
  "Average change in the monthly mortgage payment when a fixed deal reprices.")
BV = "fact_bbl_vintage"
m("04 Credit Risk", "BBL Cumulative Default Rate", PCT1, f"DIVIDE ( SUM ( {BV}[DefaultedLoans] ), SUM ( {BV}[Loans] ) )",
  "Bounce Back Loans: share of loans ever 90+ or written off by months on book.")
m("04 Credit Risk", "BBL Loans", INT, f"""CALCULATE ( SUM ( {BV}[Loans] ), {BV}[MonthsOnBook] = 0 )""")

# ============================== 05 Customers & digital ==============================
CU = "fact_customer_monthly"
m("05 Customers", "Active Customers", INT, at_end(f"SUM ( {CU}[ActiveCustomers] )"))
m("05 Customers", "Active Customers PY", INT, at_end_py("[Active Customers]"))
m("05 Customers", "Active Customers YoY %", PCT1, "DIVIDE ( [Active Customers] - [Active Customers PY], [Active Customers PY] )")
m("05 Customers", "New Customers", INT, f"SUM ( {CU}[NewCustomers] )")
m("05 Customers", "Churned Customers", INT, f"SUM ( {CU}[ChurnedCustomers] )")
m("05 Customers", "Annualised Churn Rate", PCT1,
  "DIVIDE ( [Churned Customers] * 12 / [Months In Period], [Active Customers] )")
m("05 Customers", "Digital Registered", INT, at_end(f"SUM ( {CU}[DigitalRegistered] )"))
m("05 Customers", "App Monthly Users", INT, at_end(f"SUM ( {CU}[MonthlyActiveUsers] )"), "Monthly active digital users.")
m("05 Customers", "App Monthly Users PY", INT, at_end_py("[App Monthly Users]"))
m("05 Customers", "App Monthly Users YoY %", PCT1, "DIVIDE ( [App Monthly Users] - [App Monthly Users PY], [App Monthly Users PY] )")
m("05 Customers", "Digital Active Share", PCT1, "DIVIDE ( [App Monthly Users], [Active Customers] )")
m("05 Customers", "Digital Active Share PY", PCT1, at_end_py("[Digital Active Share]"))
m("05 Customers", "Digital Active Share Change pp", "+0.0;-0.0;0.0",
  "( [Digital Active Share] - [Digital Active Share PY] ) * 100")
m("05 Customers", "Digital Active Share UK", PCT1, "CALCULATE ( [Digital Active Share], REMOVEFILTERS ( dim_region ) )",
  "National benchmark for the regional drill-through.")
m("05 Customers", "App Sessions per User", "#,0.0", f"DIVIDE ( SUM ( {CU}[AppSessions] ), SUM ( {CU}[MonthlyActiveUsers] ) )")
BR = "fact_branch_monthly"
m("05 Customers", "Open Branches", INT, at_end(f"COUNTROWS ( {BR} )", f", {BR}[IsClosureMonth] = FALSE ()"))
m("05 Customers", "Open Branches PY", INT, at_end_py("[Open Branches]"))
m("05 Customers", "Branch Closures", INT, f"CALCULATE ( COUNTROWS ( {BR} ), {BR}[IsClosureMonth] = TRUE () )")
m("05 Customers", "Branch Footfall", INT, f"SUM ( {BR}[Footfall] )")
m("05 Customers", "Open Branches Index", "#,0", f"""VAR _base = CALCULATE ( COUNTROWS ( {BR} ), REMOVEFILTERS ( dim_date ), dim_date[DateKey] = 20200131 )
RETURN
    DIVIDE ( [Open Branches], _base ) * 100""", "Index, Jan 2020 = 100 (single-axis comparison with digital users).")
m("05 Customers", "App Monthly Users Index", "#,0", f"""VAR _base = CALCULATE ( SUM ( {CU}[MonthlyActiveUsers] ), REMOVEFILTERS ( dim_date ), dim_date[DateKey] = 20200131 )
RETURN
    DIVIDE ( [App Monthly Users], _base ) * 100""", "Index, Jan 2020 = 100.")
TX = "fact_transactions_monthly"
m("05 Customers", "Transactions", INT, f"SUM ( {TX}[TxnCount] )")
m("05 Customers", "Transaction Value", GBP_M, f"SUM ( {TX}[TxnValue] )")
m("05 Customers", "Digital Transaction Share", PCT1,
  'DIVIDE ( CALCULATE ( [Transactions], dim_channel[ChannelGroup] = "Digital" ), CALCULATE ( [Transactions], dim_channel[ChannelGroup] IN { "Digital", "Branch and Phone" } ) )',
  "Share of assisted + digital transactions done in app or online.")

# ============================== 06 Conduct ==============================
CO, FR = "fact_complaint", "fact_fraud_case"
m("06 Conduct", "Complaints", INT, f"COUNTROWS ( {CO} )")
m("06 Conduct", "Complaints PY", INT, py_flow("[Complaints]"))
m("06 Conduct", "Complaints per 1000 Customers", "#,0.00",
  "DIVIDE ( [Complaints] / [Months In Period], [Active Customers] / 1000 )", "Monthly complaints per 1,000 active customers.")
m("06 Conduct", "Complaints per 1000 PY", "#,0.00", py_flow("[Complaints per 1000 Customers]"))
m("06 Conduct", "Complaints per 1000 Change", "+0.00;-0.00;0.00", "[Complaints per 1000 Customers] - [Complaints per 1000 PY]")
m("06 Conduct", "Resolved Within 8 Weeks %", PCT1, f"""DIVIDE (
    CALCULATE ( COUNTROWS ( {CO} ), {CO}[IsResolvedWithin8Weeks] = TRUE () ),
    CALCULATE ( COUNTROWS ( {CO} ), NOT ISBLANK ( {CO}[IsResolvedWithin8Weeks] ) )
)""", "FCA DISP 8-week rule; open complaints excluded.")
m("06 Conduct", "Upheld %", PCT1, f"DIVIDE ( CALCULATE ( COUNTROWS ( {CO} ), {CO}[IsUpheld] = TRUE () ), [Complaints] )")
m("06 Conduct", "Redress Paid", GBP_K, f"SUM ( {CO}[RedressAmount] )")
m("06 Conduct", "FOS Referral %", PCT1, f"DIVIDE ( CALCULATE ( COUNTROWS ( {CO} ), {CO}[IsReferredToFOS] = TRUE () ), [Complaints] )")
m("06 Conduct", "Open Complaints", INT, f"CALCULATE ( COUNTROWS ( {CO} ), {CO}[IsOpen] = TRUE () )")
m("06 Conduct", "Fraud Cases", INT, f"COUNTROWS ( {FR} )")
m("06 Conduct", "Fraud Losses", GBP_K, f"SUM ( {FR}[LossAmount] )")
m("06 Conduct", "APP Scam Losses", GBP_K, f'CALCULATE ( [Fraud Losses], {FR}[FraudType] = "APP Scam" )')
m("06 Conduct", "APP Scam Reimbursed", GBP_K, f'CALCULATE ( SUM ( {FR}[ReimbursedAmount] ), {FR}[FraudType] = "APP Scam" )')
m("06 Conduct", "APP Reimbursement Rate", PCT1, "DIVIDE ( [APP Scam Reimbursed], [APP Scam Losses] )",
  "Mandatory reimbursement from 7 Oct 2024 (PSR rule).")
m("06 Conduct", "APP Reimbursement Rate PY", PCT1, py_flow("[APP Reimbursement Rate]"))
m("06 Conduct", "APP Reimbursement Change pp", "+0.0;-0.0;0.0",
  "( [APP Reimbursement Rate] - [APP Reimbursement Rate PY] ) * 100")
m("06 Conduct", "Fraud Net Cost", GBP_K, f"SUM ( {FR}[ReimbursedAmount] ) - SUM ( {FR}[RecoveredAmount] )",
  "Cost to the bank: reimbursed minus recovered from receiving banks.")

# ============================== 07 Platform ==============================
m("07 Platform", "Rows in Warehouse", INT, 'CALCULATE ( SUM ( platform_table_stats[row_count] ), platform_table_stats[layer] = "gold" )')
m("07 Platform", "Rows All Layers", INT, "SUM ( platform_table_stats[row_count] )")
m("07 Platform", "Warehouse Size MB", "#,0", "SUM ( platform_table_stats[used_mb] )")
m("07 Platform", "Tables Monitored", INT, "DISTINCTCOUNT ( platform_table_stats[table_name] )")
m("07 Platform", "Pipeline Runs", INT, "COUNTROWS ( pipeline_runs )")
m("07 Platform", "Pipeline Success Rate", PCT1, """DIVIDE (
    CALCULATE ( COUNTROWS ( pipeline_runs ), pipeline_runs[status] = "Succeeded" ),
    CALCULATE ( COUNTROWS ( pipeline_runs ), pipeline_runs[status] IN { "Succeeded", "Failed" } )
)""")
m("07 Platform", "Rows Copied", INT, "SUM ( pipeline_runs[rows_written] )")
m("07 Platform", "Last Load Duration min", "#,0", """VAR _day = CALCULATE ( MAX ( pipeline_runs[run_date] ), REMOVEFILTERS ( pipeline_runs ) )
VAR _s = CALCULATE ( MIN ( pipeline_runs[started_at_utc] ), REMOVEFILTERS ( pipeline_runs ), pipeline_runs[run_date] = _day )
VAR _e = CALCULATE ( MAX ( pipeline_runs[ended_at_utc] ), REMOVEFILTERS ( pipeline_runs ), pipeline_runs[run_date] = _day )
RETURN
    DATEDIFF ( _s, _e, MINUTE )""", "Copy window of the latest load day (staging copies).")
m("07 Platform", "DQ Issues Fixed", INT, "SUM ( data_quality_summary[affected_rows] )")
m("07 Platform", "DQ Checks Triggered", INT, "COUNTROWS ( data_quality_summary )")
m("07 Platform", "Data Freshness", "", """VAR _w = MAX ( load_status[last_loaded_month_end] )
RETURN
    "Loaded to " & FORMAT ( _w, "mmm yyyy", "en-GB" )""")

# ============================== 08 KPI labels & colours ==============================
GOOD, BAD, NEU = "#188038", "#C5221F", "#51625A"


def kpi_label(name, var_expr, unit_fmt, suffix, higher_is_good=True, pp=False):
    fmt = unit_fmt
    m("08 KPI Labels", f"{name} Label", "", f"""VAR _v = {var_expr}
RETURN
    IF ( ISBLANK ( _v ), "no comparison",
        IF ( _v >= 0, "▲ ", "▼ " ) & FORMAT ( ABS ( _v ), "{fmt}", "en-GB" ) & " {suffix}" )""")
    good_cond = "_v >= 0" if higher_is_good else "_v <= 0"
    m("08 KPI Labels", f"{name} Colour", "", f"""VAR _v = {var_expr}
RETURN
    IF ( ISBLANK ( _v ), "{NEU}", IF ( {good_cond}, "{GOOD}", "{BAD}" ) )""")


kpi_label("NII YoY", "[NII YoY %]", "0.0%", "vs PY")
kpi_label("NII vs Budget", "[NII vs Budget %]", "0.0%", "vs budget")
kpi_label("NIM", "[NIM Change bps]", "0", "bps vs PY")
kpi_label("Fee Income YoY", "[Fee Income YoY %]", "0.0%", "vs PY")
kpi_label("Cost Income", "[Cost Income Ratio Change pp]", "0.0", "pp vs PY", higher_is_good=False)
kpi_label("Deposits YoY", "[Customer Deposits YoY %]", "0.0%", "vs PY")
kpi_label("Net Loans YoY", "[Net Loans YoY %]", "0.0%", "vs PY")
kpi_label("New Lending YoY", "[Gross New Lending YoY %]", "0.0%", "vs PY")
kpi_label("Loan Book YoY", "[Loan Book YoY %]", "0.0%", "vs PY")
kpi_label("Arrears 90", "[Arrears 90+ Change bps]", "0", "bps vs PY", higher_is_good=False)
kpi_label("Stage 2", "[Stage 2 Share Change pp]", "0.0", "pp vs PY", higher_is_good=False)
kpi_label("ECL Coverage", "[ECL Coverage Change bps]", "0", "bps vs PY", higher_is_good=True)
kpi_label("Cost of Risk", "[Cost of Risk Change bps]", "0", "bps vs PY", higher_is_good=False)
kpi_label("Active Customers YoY", "[Active Customers YoY %]", "0.0%", "vs PY")
kpi_label("Digital Share", "[Digital Active Share Change pp]", "0.0", "pp vs PY")
kpi_label("App Users YoY", "[App Monthly Users YoY %]", "0.0%", "vs PY")
kpi_label("Branches", "[Open Branches] - [Open Branches PY]", "#,0", "branches vs PY")
kpi_label("Complaints", "[Complaints per 1000 Change]", "0.00", "vs PY", higher_is_good=False)
kpi_label("APP Reimbursement", "[APP Reimbursement Change pp]", "0.0", "pp vs PY")
m("08 KPI Labels", "Budget Variance Colour", "", f"""VAR _v = [NII vs Budget %]
RETURN
    IF ( ISBLANK ( _v ), "{NEU}", IF ( _v >= 0, "{GOOD}", "{BAD}" ) )""", "Conditional colour for 'Budget delivery by region' bars.")


# ============================== write measures TMDL ==============================
def tmdl_measure(folder, name, fmt, expr, desc):
    lines = [f"\t\tmeasure '{name}' = ```"]
    lines += [f"\t\t\t\t{l}" for l in expr.split("\n")]
    lines += ["\t\t\t\t```"]
    if fmt:
        lines.append(f"\t\t\tformatString: {fmt}")
    lines.append(f"\t\t\tdisplayFolder: {folder}")
    if desc:
        lines.insert(0, f"\t\t/// {desc}")
    return "\n".join(lines)


measures_tmdl = ["createOrReplace", "", "\ttable _Measures", ""]
measures_tmdl += [tmdl_measure(*x) + "\n" for x in M]
measures_tmdl += ["\t\tcolumn Value",
                  "\t\t\tdataType: string", "\t\t\tisHidden", "\t\t\tisNameInferred", "\t\t\tsummarizeBy: none",
                  "\t\t\tsourceColumn: [Value]", "",
                  "\t\tpartition _Measures = calculated", "\t\t\tmode: import",
                  '\t\t\tsource = ROW ( "Value", "measures" )', ""]
(OUT / "03_measures.tmdl").write_text("\n".join(measures_tmdl), encoding="utf-8")

# ============================== model TMDL (calc tables, relationships, roles) ==============================
rels = [  # (from table, from column, to table, to column, active)
    ("fact_product_monthly", "DateKey", "dim_date", "DateKey", True),
    ("fact_product_monthly", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_product_monthly", "ProductKey", "dim_product", "ProductKey", True),
    ("fact_product_monthly", "Brand", "dim_brand", "Brand", True),
    ("fact_credit_risk_monthly", "DateKey", "dim_date", "DateKey", True),
    ("fact_credit_risk_monthly", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_credit_risk_monthly", "ProductKey", "dim_product", "ProductKey", True),
    ("fact_mortgage_maturity", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_mortgage_repricing", "DateKey", "dim_date", "DateKey", True),
    ("fact_mortgage_repricing", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_customer_monthly", "DateKey", "dim_date", "DateKey", True),
    ("fact_customer_monthly", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_customer_monthly", "Segment", "dim_segment", "Segment", True),
    ("fact_customer_monthly", "Brand", "dim_brand", "Brand", True),
    ("fact_transactions_monthly", "DateKey", "dim_date", "DateKey", True),
    ("fact_transactions_monthly", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_transactions_monthly", "ProductKey", "dim_product", "ProductKey", True),
    ("fact_transactions_monthly", "ChannelKey", "dim_channel", "ChannelKey", True),
    ("fact_branch_monthly", "DateKey", "dim_date", "DateKey", True),
    ("fact_branch_monthly", "BranchKey", "dim_branch", "BranchKey", True),
    ("dim_branch", "RegionKey", "dim_region", "RegionKey", True),
    ("dim_branch", "Brand", "dim_brand", "Brand", True),
    ("fact_complaint", "ReceivedDateKey", "dim_date", "DateKey", True),
    ("fact_complaint", "ResolvedDateKey", "dim_date", "DateKey", False),
    ("fact_complaint", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_complaint", "CategoryKey", "dim_complaint_category", "CategoryKey", True),
    ("fact_complaint", "Segment", "dim_segment", "Segment", True),
    ("fact_complaint", "Brand", "dim_brand", "Brand", True),
    ("fact_fraud_case", "ReportedDateKey", "dim_date", "DateKey", True),
    ("fact_fraud_case", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_fraud_case", "Segment", "dim_segment", "Segment", True),
    ("fact_fraud_case", "Brand", "dim_brand", "Brand", True),
    ("fact_budget_monthly", "DateKey", "dim_date", "DateKey", True),
    ("fact_budget_monthly", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_budget_monthly", "ProductKey", "dim_product", "ProductKey", True),
    ("fact_opex_monthly", "DateKey", "dim_date", "DateKey", True),
    ("fact_opex_monthly", "RegionKey", "dim_region", "RegionKey", True),
    ("fact_bank_rate_daily", "DateKey", "dim_date", "DateKey", True),
    ("dim_product", "Segment", "dim_segment", "Segment", True),
]
model = ["createOrReplace", ""]
model += ["\ttable dim_segment", "",
          "\t\tcolumn Segment", "\t\t\tdataType: string", "\t\t\tisNameInferred", "\t\t\tsummarizeBy: none",
          "\t\t\tsourceColumn: [Segment]", "",
          "\t\tpartition dim_segment = calculated", "\t\t\tmode: import",
          '\t\t\tsource = DATATABLE ( "Segment", STRING, { { "Personal" }, { "SME" } } )', ""]
model += ["\ttable dim_brand", "",
          "\t\tcolumn Brand", "\t\t\tdataType: string", "\t\t\tisNameInferred", "\t\t\tsummarizeBy: none",
          "\t\t\tsourceColumn: [Brand]", "",
          "\t\tpartition dim_brand = calculated", "\t\t\tmode: import",
          '\t\t\tsource = DATATABLE ( "Brand", STRING, { { "Lloyds Bank" }, { "Halifax" }, { "Bank of Scotland" } } )', ""]
model += ["\ttable bridge_steps", "",
          "\t\tcolumn Step", "\t\t\tdataType: string", "\t\t\tisNameInferred", "\t\t\tsummarizeBy: none",
          "\t\t\tsourceColumn: [Step]", "\t\t\tsortByColumn: Order", "",
          "\t\tcolumn Order", "\t\t\tdataType: int64", "\t\t\tisNameInferred", "\t\t\tsummarizeBy: none",
          "\t\t\tsourceColumn: [Order]", "",
          "\t\tpartition bridge_steps = calculated", "\t\t\tmode: import",
          '\t\t\tsource = DATATABLE ( "Step", STRING, "Order", INTEGER, { { "Prior year NII", 1 }, { "Volume", 2 }, { "Margin", 3 }, { "Other", 4 } } )', ""]
for i, (ft, fc, tt, tc, act) in enumerate(rels, 1):
    model.append(f"\trelationship rel_{i:02d}_{ft}_{fc}")
    if not act:
        model.append("\t\tisActive: false")
    model += [f"\t\tfromColumn: {ft}.{fc}", f"\t\ttoColumn: {tt}.{tc}", ""]
model += ["\trole 'Executive'", "\t\tmodelPermission: read", "",
          "\trole 'Regional Director'", "\t\tmodelPermission: read", "",
          "\t\ttablePermission dim_region = [DirectorEmail] = USERPRINCIPALNAME ()", ""]
(OUT / "02_model.tmdl").write_text("\n".join(model), encoding="utf-8")

# ============================== catalog ==============================
cat = ["# Measure catalogue", "", f"{len(M)} measures in table `_Measures`, grouped by display folder.", "",
       "| Folder | Measure | Format | Description |", "|---|---|---|---|"]
for f, n, fmt, e, d in M:
    cat.append(f"| {f} | {n} | `{fmt}` | {d} |")
(OUT / "measures_catalog.md").write_text("\n".join(cat), encoding="utf-8")
print(f"{len(M)} measures | {len(rels)} relationships | files written to {OUT}")
