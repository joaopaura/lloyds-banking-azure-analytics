# Measure catalogue

197 measures in table `_Measures`, grouped by display folder.

| Folder | Measure | Format | Description |
|---|---|---|---|
| 00 Helpers | Last Actual Date | `dd mmm yyyy` | Last month with actual data (31 Aug 2026). |
| 00 Helpers | Period End Date | `dd mmm yyyy` | End of the selected period, capped at the last actual date. Balance KPIs are read at this date. |
| 00 Helpers | Months In Period | `#,0` | Number of actual months in the selection (used to annualise). |
| 00 Helpers | Data As Of | `` |  |
| 00 Helpers | Selected Period Label | `` |  |
| 00 Helpers | Selected Region Title | `` | Dynamic title for the Region Deep Dive drill-through page. |
| 01 Income | Interest Income | `£#,0.0,,\m` |  |
| 01 Income | Interest Expense | `£#,0.0,,\m` |  |
| 01 Income | FTP Credit | `£#,0.0,,\m` | Funds transfer pricing credit earned by deposits. |
| 01 Income | FTP Charge | `£#,0.0,,\m` | Funds transfer pricing charge paid by loans. |
| 01 Income | NII | `£#,0.0,,\m` | Net Interest Income on a funds transfer pricing basis (product view). |
| 01 Income | NII PY | `£#,0.0,,\m` | Same months of the prior year. |
| 01 Income | NII YoY % | `0.0%` |  |
| 01 Income | NII Budget | `£#,0.0,,\m` | Budget for the actual months of the selection. |
| 01 Income | NII Budget Full Year | `£#,0.0,,\m` |  |
| 01 Income | NII vs Budget | `£#,0.0,,\m` |  |
| 01 Income | NII vs Budget % | `0.0%` |  |
| 01 Income | Fee Income | `£#,0.0,,\m` |  |
| 01 Income | Fee Income PY | `£#,0.0,,\m` |  |
| 01 Income | Fee Income YoY % | `0.0%` |  |
| 01 Income | Fee Income Budget | `£#,0.0,,\m` |  |
| 01 Income | Total Income | `£#,0.0,,\m` |  |
| 01 Income | Total Income PY | `£#,0.0,,\m` |  |
| 01 Income | Operating Costs | `£#,0.0,,\m` | Opex by region and cost category (not allocated to products). |
| 01 Income | Operating Costs PY | `£#,0.0,,\m` |  |
| 01 Income | Operating Costs Budget | `£#,0.0,,\m` |  |
| 01 Income | Cost Income Ratio | `0.0%` |  |
| 01 Income | Cost Income Ratio PY | `0.0%` |  |
| 01 Income | Cost Income Ratio Change pp | `+0.0;-0.0;0.0` | Change in percentage points. |
| 02 Balance Sheet | Customer Deposits | `£#,0.0,,\m` | End of period balance. |
| 02 Balance Sheet | Customer Deposits PY | `£#,0.0,,\m` |  |
| 02 Balance Sheet | Customer Deposits YoY % | `0.0%` |  |
| 02 Balance Sheet | Current Account Balances | `£#,0.0,,\m` |  |
| 02 Balance Sheet | Savings Balances | `£#,0.0,,\m` |  |
| 02 Balance Sheet | Fixed Term Savings | `£#,0.0,,\m` |  |
| 02 Balance Sheet | Fixed Term Share of Deposits | `0.0%` | Deposit migration indicator. |
| 02 Balance Sheet | Loan Book | `£#,0.0,,\m` | Gross customer loans, end of period. |
| 02 Balance Sheet | Loan Book PY | `£#,0.0,,\m` |  |
| 02 Balance Sheet | Loan Book YoY % | `0.0%` |  |
| 02 Balance Sheet | ECL Stock | `£#,0.0,,\m` | Expected credit loss allowance, end of period. |
| 02 Balance Sheet | Net Loans | `£#,0.0,,\m` |  |
| 02 Balance Sheet | Net Loans PY | `£#,0.0,,\m` |  |
| 02 Balance Sheet | Net Loans YoY % | `0.0%` |  |
| 02 Balance Sheet | Loan to Deposit Ratio | `0.0%` |  |
| 02 Balance Sheet | Avg Loan Balance | `£#,0.0,,\m` | Average of month-end loan balances in the period (NIM denominator). |
| 02 Balance Sheet | NIM | `0.00%` | Net interest margin: annualised NII over average customer loans. |
| 02 Balance Sheet | NIM PY | `0.00%` |  |
| 02 Balance Sheet | NIM Change bps | `+0;-0;0` | Change in basis points. |
| 02 Balance Sheet | Bank Rate | `0.00%` | Average Bank of England Bank Rate in the period (real data). |
| 02 Balance Sheet | Bank Rate Period End | `0.00%` |  |
| 02 Balance Sheet | Customer Rate Deposits | `0.00%` | Balance-weighted average rate paid on deposits. |
| 02 Balance Sheet | Customer Rate Loans | `0.00%` |  |
| 02 Balance Sheet | Deposit Beta | `0.0%` | Share of Bank Rate passed to depositors. |
| 03 NII Bridge | Balance Months | `£#,0.0,,\m` | Sum of monthly average balances (volume driver). |
| 03 NII Bridge | Balance Months PY | `£#,0.0,,\m` |  |
| 03 NII Bridge | Bridge Volume Effect | `£#,0.0,,\m` | NII change explained by balance growth at prior-year margin, per product. |
| 03 NII Bridge | Bridge Margin Effect | `£#,0.0,,\m` | NII change explained by margin change (rates, deposit beta, repricing), per product. |
| 03 NII Bridge | Bridge Other | `£#,0.0,,\m` | Residual (new products, rounding). |
| 03 NII Bridge | NII Bridge Value | `£#,0.0,,\m` | Waterfall: categories bridge_steps[Step] sorted by Order; total = current period NII. |
| 04 Credit Risk | Gross New Lending | `£#,0.0,,\m` |  |
| 04 Credit Risk | Gross New Lending PY | `£#,0.0,,\m` |  |
| 04 Credit Risk | Gross New Lending YoY % | `0.0%` |  |
| 04 Credit Risk | Stage 1 Balance | `£#,0.0,,\m` |  |
| 04 Credit Risk | Stage 1 Share | `0.0%` |  |
| 04 Credit Risk | Stage 2 Balance | `£#,0.0,,\m` |  |
| 04 Credit Risk | Stage 2 Share | `0.0%` |  |
| 04 Credit Risk | Stage 3 Balance | `£#,0.0,,\m` |  |
| 04 Credit Risk | Stage 3 Share | `0.0%` |  |
| 04 Credit Risk | Stage 2 Share PY | `0.0%` |  |
| 04 Credit Risk | Stage 2 Share Change pp | `+0.0;-0.0;0.0` |  |
| 04 Credit Risk | Arrears 90+ Balance | `£#,0.0,,\m` |  |
| 04 Credit Risk | Arrears 90+ Rate | `0.00%` |  |
| 04 Credit Risk | Arrears 90+ Rate PY | `0.00%` |  |
| 04 Credit Risk | Arrears 90+ Change bps | `+0;-0;0` |  |
| 04 Credit Risk | Arrears 30+ Balance | `£#,0.0,,\m` |  |
| 04 Credit Risk | Arrears 30+ Rate | `0.00%` |  |
| 04 Credit Risk | ECL Coverage | `0.00%` |  |
| 04 Credit Risk | ECL Coverage PY | `0.00%` |  |
| 04 Credit Risk | ECL Coverage Change bps | `+0;-0;0` |  |
| 04 Credit Risk | ECL Opening | `£#,0.0,,\m` | ECL at the end of the month before the period starts. |
| 04 Credit Risk | Net Write-offs | `£#,0.0,,\m` | Write-offs net of the government guarantee (Bounce Back Loans). |
| 04 Credit Risk | Impairment Charge | `£#,0.0,,\m` | P&L charge: change in ECL allowance plus net write-offs. |
| 04 Credit Risk | Impairment Budget | `£#,0.0,,\m` |  |
| 04 Credit Risk | Cost of Risk | `0.00%` | Annualised impairment charge over average loans. |
| 04 Credit Risk | Cost of Risk PY | `0.00%` |  |
| 04 Credit Risk | Cost of Risk Change bps | `+0;-0;0` |  |
| 04 Credit Risk | Payment Holiday Balance | `£#,0.0,,\m` | Use by month (COVID payment deferrals, 2020). |
| 04 Credit Risk | Risk Balance | `£#,0.0,,\m` | Loan balance from the credit risk mart (heatmap, stage mix by score / LTV). |
| 04 Credit Risk | Risk 90+ Balance | `£#,0.0,,\m` |  |
| 04 Credit Risk | Risk 90+ Rate | `0.00%` | 90+ arrears rate for heatmaps (LTV band x credit score). |
| 04 Credit Risk | Risk ECL | `£#,0.0,,\m` |  |
| 04 Credit Risk | Risk ECL Coverage | `0.00%` |  |
| 04 Credit Risk | Risk EAD | `£#,0.0,,\m` |  |
| 04 Credit Risk | Risk PD x EAD | `£#,0.0,,\m` |  |
| 04 Credit Risk | Risk Avg PD | `0.00%` | EAD-weighted 12-month PD. |
| 04 Credit Risk | Maturing Fixed Balance | `£#,0.0,,\m` | Remortgage wall: fixed-rate balances by deal end quarter (snapshot at last actual month). |
| 04 Credit Risk | Maturing Fixed Accounts | `#,0` |  |
| 04 Credit Risk | Maturing Avg Current Rate | `0.00%` |  |
| 04 Credit Risk | Maturing Next 12M Balance | `£#,0.0,,\m` |  |
| 04 Credit Risk | Repricings | `#,0` |  |
| 04 Credit Risk | Repricing Old Rate | `0.00%` |  |
| 04 Credit Risk | Repricing New Rate | `0.00%` |  |
| 04 Credit Risk | Payment Shock % | `0.0%` | Average change in the monthly mortgage payment when a fixed deal reprices. |
| 04 Credit Risk | BBL Cumulative Default Rate | `0.0%` | Bounce Back Loans: share of loans ever 90+ or written off by months on book. |
| 04 Credit Risk | BBL Loans | `#,0` |  |
| 05 Customers | Active Customers | `#,0` |  |
| 05 Customers | Active Customers PY | `#,0` |  |
| 05 Customers | Active Customers YoY % | `0.0%` |  |
| 05 Customers | New Customers | `#,0` |  |
| 05 Customers | Churned Customers | `#,0` |  |
| 05 Customers | Annualised Churn Rate | `0.0%` |  |
| 05 Customers | Digital Registered | `#,0` |  |
| 05 Customers | App Monthly Users | `#,0` | Monthly active digital users. |
| 05 Customers | App Monthly Users PY | `#,0` |  |
| 05 Customers | App Monthly Users YoY % | `0.0%` |  |
| 05 Customers | Digital Active Share | `0.0%` |  |
| 05 Customers | Digital Active Share PY | `0.0%` |  |
| 05 Customers | Digital Active Share Change pp | `+0.0;-0.0;0.0` |  |
| 05 Customers | Digital Active Share UK | `0.0%` | National benchmark for the regional drill-through. |
| 05 Customers | App Sessions per User | `#,0.0` |  |
| 05 Customers | Open Branches | `#,0` |  |
| 05 Customers | Open Branches PY | `#,0` |  |
| 05 Customers | Branch Closures | `#,0` |  |
| 05 Customers | Branch Footfall | `#,0` |  |
| 05 Customers | Open Branches Index | `#,0` | Index, Jan 2020 = 100 (single-axis comparison with digital users). |
| 05 Customers | App Monthly Users Index | `#,0` | Index, Jan 2020 = 100. |
| 05 Customers | Transactions | `#,0` |  |
| 05 Customers | Transaction Value | `£#,0.0,,\m` |  |
| 05 Customers | Digital Transaction Share | `0.0%` | Share of assisted + digital transactions done in app or online. |
| 06 Conduct | Complaints | `#,0` |  |
| 06 Conduct | Complaints PY | `#,0` |  |
| 06 Conduct | Complaints per 1000 Customers | `#,0.00` | Monthly complaints per 1,000 active customers. |
| 06 Conduct | Complaints per 1000 PY | `#,0.00` |  |
| 06 Conduct | Complaints per 1000 Change | `+0.00;-0.00;0.00` |  |
| 06 Conduct | Resolved Within 8 Weeks % | `0.0%` | FCA DISP 8-week rule; open complaints excluded. |
| 06 Conduct | Upheld % | `0.0%` |  |
| 06 Conduct | Redress Paid | `£#,0,\k` |  |
| 06 Conduct | FOS Referral % | `0.0%` |  |
| 06 Conduct | Open Complaints | `#,0` |  |
| 06 Conduct | Fraud Cases | `#,0` |  |
| 06 Conduct | Fraud Losses | `£#,0,\k` |  |
| 06 Conduct | APP Scam Losses | `£#,0,\k` |  |
| 06 Conduct | APP Scam Reimbursed | `£#,0,\k` |  |
| 06 Conduct | APP Reimbursement Rate | `0.0%` | Mandatory reimbursement from 7 Oct 2024 (PSR rule). |
| 06 Conduct | APP Reimbursement Rate PY | `0.0%` |  |
| 06 Conduct | APP Reimbursement Change pp | `+0.0;-0.0;0.0` |  |
| 06 Conduct | Fraud Net Cost | `£#,0,\k` | Cost to the bank: reimbursed minus recovered from receiving banks. |
| 07 Platform | Rows in Warehouse | `#,0` |  |
| 07 Platform | Rows All Layers | `#,0` |  |
| 07 Platform | Warehouse Size MB | `#,0` |  |
| 07 Platform | Tables Monitored | `#,0` |  |
| 07 Platform | Pipeline Runs | `#,0` |  |
| 07 Platform | Pipeline Success Rate | `0.0%` |  |
| 07 Platform | Rows Copied | `#,0` |  |
| 07 Platform | Last Load Duration min | `#,0` | Copy window of the latest load day (staging copies). |
| 07 Platform | DQ Issues Fixed | `#,0` |  |
| 07 Platform | DQ Checks Triggered | `#,0` |  |
| 07 Platform | Data Freshness | `` |  |
| 08 KPI Labels | NII YoY Label | `` |  |
| 08 KPI Labels | NII YoY Colour | `` |  |
| 08 KPI Labels | NII vs Budget Label | `` |  |
| 08 KPI Labels | NII vs Budget Colour | `` |  |
| 08 KPI Labels | NIM Label | `` |  |
| 08 KPI Labels | NIM Colour | `` |  |
| 08 KPI Labels | Fee Income YoY Label | `` |  |
| 08 KPI Labels | Fee Income YoY Colour | `` |  |
| 08 KPI Labels | Cost Income Label | `` |  |
| 08 KPI Labels | Cost Income Colour | `` |  |
| 08 KPI Labels | Deposits YoY Label | `` |  |
| 08 KPI Labels | Deposits YoY Colour | `` |  |
| 08 KPI Labels | Net Loans YoY Label | `` |  |
| 08 KPI Labels | Net Loans YoY Colour | `` |  |
| 08 KPI Labels | New Lending YoY Label | `` |  |
| 08 KPI Labels | New Lending YoY Colour | `` |  |
| 08 KPI Labels | Loan Book YoY Label | `` |  |
| 08 KPI Labels | Loan Book YoY Colour | `` |  |
| 08 KPI Labels | Arrears 90 Label | `` |  |
| 08 KPI Labels | Arrears 90 Colour | `` |  |
| 08 KPI Labels | Stage 2 Label | `` |  |
| 08 KPI Labels | Stage 2 Colour | `` |  |
| 08 KPI Labels | ECL Coverage Label | `` |  |
| 08 KPI Labels | ECL Coverage Colour | `` |  |
| 08 KPI Labels | Cost of Risk Label | `` |  |
| 08 KPI Labels | Cost of Risk Colour | `` |  |
| 08 KPI Labels | Active Customers YoY Label | `` |  |
| 08 KPI Labels | Active Customers YoY Colour | `` |  |
| 08 KPI Labels | Digital Share Label | `` |  |
| 08 KPI Labels | Digital Share Colour | `` |  |
| 08 KPI Labels | App Users YoY Label | `` |  |
| 08 KPI Labels | App Users YoY Colour | `` |  |
| 08 KPI Labels | Branches Label | `` |  |
| 08 KPI Labels | Branches Colour | `` |  |
| 08 KPI Labels | Complaints Label | `` |  |
| 08 KPI Labels | Complaints Colour | `` |  |
| 08 KPI Labels | APP Reimbursement Label | `` |  |
| 08 KPI Labels | APP Reimbursement Colour | `` |  |
| 08 KPI Labels | Budget Variance Colour | `` | Conditional colour for 'Budget delivery by region' bars. |