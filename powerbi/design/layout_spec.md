# Lloyds dashboard | layout spec (canvas 1920 x 1080)

Power BI: View > Page view > Actual size; Page format > Canvas settings > Custom 1920 x 1080;
Canvas background > Image > Fit, transparency 0%. For each visual: Format > General > Properties.

## Cover

| Visual | X | Y | W | H |
|---|---|---|---|---|
| Hero KPI 1 (card) | 840 | 160 | 320 | 170 |
| Hero KPI 2 (card) | 1180 | 160 | 320 | 170 |
| Hero KPI 3 (card) | 1520 | 160 | 320 | 170 |
| Nav button 1 (blank button, transparent) | 840 | 440 | 1000 | 124 |
| Nav button 2 (blank button, transparent) | 840 | 580 | 1000 | 124 |
| Nav button 3 (blank button, transparent) | 840 | 720 | 1000 | 124 |
| Nav button 4 (blank button, transparent) | 840 | 860 | 1000 | 124 |

## Profitability & Balance Sheet

| Visual | X | Y | W | H |
|---|---|---|---|---|
| Slicer strip (4-5 slicers inside) | 40 | 104 | 1840 | 56 |
| KPI Net Interest Income | 40 | 176 | 293 | 128 |
| KPI Net Interest Margin | 349 | 176 | 293 | 128 |
| KPI Fee Income | 659 | 176 | 293 | 128 |
| KPI Cost:Income Ratio | 968 | 176 | 293 | 128 |
| KPI Customer Deposits | 1277 | 176 | 293 | 128 |
| KPI Net Loans | 1587 | 176 | 293 | 128 |
| NII by month vs budget | 40 | 320 | 1112 | 356 |
| NIM vs Bank Rate (%) | 1168 | 320 | 712 | 356 |
| NII bridge vs prior year | 40 | 692 | 600 | 348 |
| Deposit mix | 656 | 692 | 600 | 348 |
| Budget delivery by region | 1272 | 692 | 608 | 348 |

## Lending & Credit Risk

| Visual | X | Y | W | H |
|---|---|---|---|---|
| Slicer strip (4-5 slicers inside) | 40 | 104 | 1840 | 56 |
| KPI Gross New Lending | 40 | 176 | 293 | 128 |
| KPI Loan Book | 349 | 176 | 293 | 128 |
| KPI 90+ Arrears Rate | 659 | 176 | 293 | 128 |
| KPI Stage 2 Share | 968 | 176 | 293 | 128 |
| KPI ECL Coverage | 1277 | 176 | 293 | 128 |
| KPI Cost of Risk | 1587 | 176 | 293 | 128 |
| IFRS 9 stage mix | 40 | 320 | 912 | 356 |
| Remortgage wall | 968 | 320 | 912 | 356 |
| 90+ arrears by product | 40 | 692 | 600 | 348 |
| LTV x credit score heatmap | 656 | 692 | 600 | 348 |
| Bounce Back Loans default curve | 1272 | 692 | 608 | 348 |

## Customers, Digital & Conduct

| Visual | X | Y | W | H |
|---|---|---|---|---|
| Slicer strip (4-5 slicers inside) | 40 | 104 | 1840 | 56 |
| KPI Active Customers | 40 | 176 | 293 | 128 |
| KPI Digital Active Share | 349 | 176 | 293 | 128 |
| KPI App Monthly Users | 659 | 176 | 293 | 128 |
| KPI Open Branches | 968 | 176 | 293 | 128 |
| KPI Complaints per 1,000 | 1277 | 176 | 293 | 128 |
| KPI APP Scam Reimbursement | 1587 | 176 | 293 | 128 |
| Branches vs digital users (index) | 40 | 320 | 912 | 356 |
| Transaction channel mix | 968 | 320 | 912 | 356 |
| Complaints by category | 40 | 692 | 600 | 348 |
| APP scam losses vs reimbursed | 656 | 692 | 600 | 348 |
| Branch network | 1272 | 692 | 608 | 348 |

## Data Platform & Quality

| Visual | X | Y | W | H |
|---|---|---|---|---|
| Slicer strip (4-5 slicers inside) | 40 | 104 | 1840 | 56 |
| KPI Rows in Warehouse | 40 | 176 | 293 | 128 |
| KPI Data As Of | 349 | 176 | 293 | 128 |
| KPI Pipeline Success Rate | 659 | 176 | 293 | 128 |
| KPI Last Load Duration | 968 | 176 | 293 | 128 |
| KPI Data Quality Issues Fixed | 1277 | 176 | 293 | 128 |
| KPI Tables Monitored | 1587 | 176 | 293 | 128 |
| Architecture (image: docs/architecture.png) | 40 | 320 | 1112 | 356 |
| Rows by layer and table | 1168 | 320 | 712 | 356 |
| Pipeline runs (rows written, duration, status) | 40 | 692 | 912 | 348 |
| Data quality checks and actions | 968 | 692 | 912 | 348 |

## Region Deep Dive

| Visual | X | Y | W | H |
|---|---|---|---|---|
| Slicer strip (4-5 slicers inside) | 40 | 104 | 1840 | 56 |
| KPI Net Interest Income | 40 | 176 | 293 | 128 |
| KPI Net Interest Margin | 349 | 176 | 293 | 128 |
| KPI Customer Deposits | 659 | 176 | 293 | 128 |
| KPI Loan Book | 968 | 176 | 293 | 128 |
| KPI 90+ Arrears Rate | 1277 | 176 | 293 | 128 |
| KPI Active Customers | 1587 | 176 | 293 | 128 |
| NII vs budget | selected region | 40 | 320 | 912 | 356 |
| Product scorecard (matrix) | 968 | 320 | 912 | 356 |
| IFRS 9 stage mix | 40 | 692 | 600 | 348 |
| Digital active share vs UK | 656 | 692 | 600 | 348 |
| Branches in region (map) | 1272 | 692 | 608 | 348 |

## Header navigation (pages 1-4)

| Button | X | Y | W | H |
|---|---|---|---|---|
| Home | 1080 | 22 | 152 | 44 |
| Profitability | 1242 | 22 | 152 | 44 |
| Credit Risk | 1404 | 22 | 152 | 44 |
| Customers | 1566 | 22 | 152 | 44 |
| Data Platform | 1728 | 22 | 152 | 44 |

Button style: fill #FFFFFF, border 1px #DDE6E1, radius 8, text Segoe UI 12 #51625A; current page: fill #006A4D, text #FFFFFF.
Action: Page navigation.

## Region Deep Dive (drill-through, hidden page)

- Page type: Drill through | Drill-through field: dim_region[RegionName] | "Keep all filters" on | hide the page.
- Back button: X 1728, Y 22, W 152, H 44 (Power BI Back button, same style).
- Dynamic title: card or text box at X 440, Y 26 with measure `Selected Region Title` (e.g. "North East | Regional Director: ...").
- Users right-click a region in any visual (e.g. Budget delivery by region) > Drill through > Region Deep Dive.

## Colour rules

- Single-series absolute values: #0B8157 (brand green). Comparisons (PY, budget): grey #B8C4BE
- Variance / status only: good #188038, warning #E8A317, bad #C5221F, always with an arrow or text label
- Categorical order (never cycled): #0B8157, #2E6FD8, #C97A00, #8C5BB5, #D1495B (validated for colour blindness)
- Heatmaps: single green ramp #EAF4EF > #6FB597 > #00402E
- No dual-axis charts: NIM and Bank Rate share one % axis; branches vs digital users indexed (2020 = 100)
