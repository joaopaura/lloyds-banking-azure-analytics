# Lloyds dashboard | visual build guide

Positions: see `layout_spec.md`. Measures: table `_Measures` (folders 00 to 08). Theme already sets fonts, colours and transparent backgrounds.

## Conventions

- **KPI card = 2 visuals** stacked in the KPI slot (same as Żabka):
  - *Card (new)* with the value measure, callout 28 pt, title = KPI name (12 pt, #51625A). X/W = slot, Y = slot Y + 8, H = 84
  - *Card* or text box with the `... Label` measure, 11 pt, font colour = conditional (Format > Callout value > Color > fx > Field value > `... Colour`). Y = slot Y + 88, H = 32
- Chart titles: sentence case, what the chart shows, e.g. "NII by month vs budget".
- Absolute values in brand green #0B8157; prior year / budget in grey #B8C4BE; variances coloured good/bad only.
- Every chart gets a tooltip with the exact value; no data labels on every point (only last point or totals).

## Slicer strip (pages 1, 2, 3; Y 104, H 56)

Horizontal row of 5 dropdown slicers, each ~340 x 48, starting X 56, gap 16:
`dim_date[Year]` (single select, default 2026) | `dim_date[MonthShort]` | `dim_region[RegionName]` | `dim_segment[Segment]` | `dim_brand[Brand]`.
Sync slicers across pages 1 to 3 (View > Sync slicers).

Add a text box at the right end of the strip with measure `Data As Of` (card, 10 pt, #8A9A92).

## Cover

| Slot | Visual | Fields |
|---|---|---|
| Hero KPI 1 | Card | `NII` + label `NII YoY Label` (title "Net interest income YTD") |
| Hero KPI 2 | Card | `NIM` + label `NIM Label` |
| Hero KPI 3 | Card | `Active Customers` + label `Active Customers YoY Label` |
| Nav buttons 1-4 | Blank buttons | transparent, page navigation |

Cover filter: page-level filter `dim_date[Year] = 2026`.

## Page 1 | Profitability & Balance Sheet

| Slot | Visual | Fields / measures | Notes |
|---|---|---|---|
| KPI 1 | Card pair | `NII` / `NII vs Budget Label` + colour | |
| KPI 2 | Card pair | `NIM` / `NIM Label` + `NIM Colour` | |
| KPI 3 | Card pair | `Fee Income` / `Fee Income YoY Label` | |
| KPI 4 | Card pair | `Cost Income Ratio` / `Cost Income Label` | lower is better |
| KPI 5 | Card pair | `Customer Deposits` / `Deposits YoY Label` | |
| KPI 6 | Card pair | `Net Loans` / `Net Loans YoY Label` | |
| NII by month vs budget | Line and clustered column | X `dim_date[YearMonth]`; columns `NII`; line `NII Budget` | ONE axis (same unit). Column #0B8157, line grey dashed |
| NIM vs Bank Rate (%) | Line chart | X `dim_date[YearMonth]`; Y `NIM`, `Bank Rate` | both % on one axis; the story: margin follows the rate cycle with a lag |
| NII bridge vs prior year | Waterfall | Category `bridge_steps[Step]` (sorted by Order); Y `NII Bridge Value` | Total label "Current period NII"; increase #188038, decrease #C5221F, total #0B8157 |
| Deposit mix | 100% stacked area | X `dim_date[YearMonth]`; Y `EOMBalance` via measures `Current Account Balances`, `Savings Balances` | or stacked column by `dim_product[ProductName]` (deposits only) |
| Budget delivery by region | Clustered bar | Y `dim_region[RegionName]`; X `NII vs Budget %` | bar colour fx `Budget Variance Colour`; sort ascending; right-click > Drill through > Region Deep Dive |

## Page 2 | Lending & Credit Risk

| Slot | Visual | Fields / measures | Notes |
|---|---|---|---|
| KPI 1 | Card pair | `Gross New Lending` / `New Lending YoY Label` | |
| KPI 2 | Card pair | `Loan Book` / `Loan Book YoY Label` | |
| KPI 3 | Card pair | `Arrears 90+ Rate` / `Arrears 90 Label` | lower is better |
| KPI 4 | Card pair | `Stage 2 Share` / `Stage 2 Label` | lower is better |
| KPI 5 | Card pair | `ECL Coverage` / `ECL Coverage Label` | |
| KPI 6 | Card pair | `Cost of Risk` / `Cost of Risk Label` | lower is better |
| IFRS 9 stage mix | 100% stacked column | X `dim_date[YearMonth]`; Y `Stage 1 Balance`, `Stage 2 Balance`, `Stage 3 Balance` | colours: Stage 1 #0B8157, Stage 2 #C97A00, Stage 3 #D1495B |
| Remortgage wall | Stacked column | X `fact_mortgage_maturity[DealEndQuarter]`; Y `Maturing Fixed Balance`; legend `fact_mortgage_maturity[CurrentRateBand]` | subtitle: measure `Maturing Next 12M Balance`; tooltip `Maturing Avg Current Rate`, `Payment Shock %` |
| 90+ arrears by product | Line chart | X `dim_date[YearMonth]`; Y `Arrears 90+ Rate`; legend `dim_product[ProductName]` filtered to Mortgage, Personal Loan, Credit Card, Business Loan, Bounce Back Loan | 5 series max (categorical order) |
| LTV x credit score heatmap | Matrix | Rows `fact_credit_risk_monthly[LTVBand]` (filter <> "n/a"); Columns `fact_credit_risk_monthly[CreditScoreBand]`; Values `Risk 90+ Rate` | Cell background: gradient #EAF4EF > #00402E; values 0.00% |
| Bounce Back Loans default curve | Line chart | X `fact_bbl_vintage[MonthsOnBook]`; Y `BBL Cumulative Default Rate`; legend `fact_bbl_vintage[VintageQuarter]` | 4 vintages; no date slicer interaction (Edit interactions > none) |

## Page 3 | Customers, Digital & Conduct

| Slot | Visual | Fields / measures | Notes |
|---|---|---|---|
| KPI 1 | Card pair | `Active Customers` / `Active Customers YoY Label` | |
| KPI 2 | Card pair | `Digital Active Share` / `Digital Share Label` | |
| KPI 3 | Card pair | `App Monthly Users` / `App Users YoY Label` | |
| KPI 4 | Card pair | `Open Branches` / `Branches Label` | |
| KPI 5 | Card pair | `Complaints per 1000 Customers` / `Complaints Label` | lower is better |
| KPI 6 | Card pair | `APP Reimbursement Rate` / `APP Reimbursement Label` | |
| Branches vs digital users (index) | Line chart | X `dim_date[YearMonth]`; Y `Open Branches Index`, `App Monthly Users Index` | index Jan 2020 = 100, one axis |
| Transaction channel mix | 100% stacked column | X `dim_date[Year]`; Y `Transactions`; legend `dim_channel[ChannelGroup]` | |
| Complaints by category | Clustered bar | Y `dim_complaint_category[CategoryName]`; X `Complaints` | tooltip `Resolved Within 8 Weeks %`, `Upheld %` |
| APP scam losses vs reimbursed | Clustered column | X `dim_date[YearMonth]` or `[Year]`; Y `APP Scam Losses`, `APP Scam Reimbursed` | add constant line / annotation at Oct 2024 "PSR mandatory reimbursement" |
| Branch network | Azure Maps | Lat `dim_branch[Latitude]`; Long `dim_branch[Longitude]`; legend `dim_branch[BranchStatus]` | Open #0B8157, Closed #B8C4BE |

## Page 4 | Data Platform & Quality (no slicer strip needed: use the strip for a text box "Pipeline: PL_00_Master_Load | Azure SQL serverless | Sweden Central")

| Slot | Visual | Fields / measures |
|---|---|---|
| KPI 1 | Card | `Rows in Warehouse` |
| KPI 2 | Card | `Data Freshness` |
| KPI 3 | Card | `Pipeline Success Rate` |
| KPI 4 | Card | `Last Load Duration min` |
| KPI 5 | Card | `DQ Issues Fixed` |
| KPI 6 | Card | `Tables Monitored` |
| Architecture | Image | `docs/architecture.png`, scaling Fit |
| Rows by layer and table | Clustered bar | Y `platform_table_stats[table_name]`; X `row_count`; legend `layer`; top 12 |
| Pipeline runs | Table | `pipeline_runs`: source_table, rows_written, status, started_at_utc, ended_at_utc; status icon via conditional formatting |
| Data quality checks | Table | `data_quality_summary`: layer, table_name, check_name, severity, affected_rows, action_taken |

## Region Deep Dive (drill-through)

Format page > Page information > Page type **Drill through**; drill-through field `dim_region[RegionName]`; Keep all filters **On**; then hide the page.

| Slot | Visual | Fields / measures |
|---|---|---|
| Title | Card at X 440, Y 26 | `Selected Region Title` |
| KPIs | Card pairs | `NII`, `NIM`, `Customer Deposits`, `Loan Book`, `Arrears 90+ Rate`, `Active Customers` |
| NII vs budget | Line and clustered column | as page 1 |
| Product scorecard | Matrix | Rows `dim_product[ProductName]`; values `Loan Book`, `Customer Deposits`, `NII`, `Arrears 90+ Rate` |
| IFRS 9 stage mix | 100% stacked column | as page 2 |
| Digital active share vs UK | Line chart | `Digital Active Share`, `Digital Active Share UK` |
| Branches in region | Azure Maps | as page 3 |
