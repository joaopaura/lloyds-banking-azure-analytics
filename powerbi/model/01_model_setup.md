# Power BI model setup | Lloyds case study

## 1. Connect (Import mode)

- Power BI Desktop > **Get data > Azure SQL database**
- Server: `sql-lloyds-joaopaura.database.windows.net` | Database: `sqldb-lloyds` | Data connectivity mode: **Import**
- Advanced options > Command timeout (minutes): `20` (the serverless database may be resuming)
- Credentials: **Database** | user `pbi_reader` | its password (read-only user, never the admin)

## 2. Select these 23 objects (schema `mart`) and click **Load**

| Group | Objects |
|---|---|
| Dimensions | dim_date, dim_region, dim_product, dim_channel, dim_complaint_category, dim_branch |
| Finance & P&L | fact_product_monthly, fact_budget_monthly, fact_opex_monthly, fact_bank_rate_daily |
| Credit risk | fact_credit_risk_monthly, fact_mortgage_maturity, fact_mortgage_repricing, fact_bbl_vintage |
| Customers & conduct | fact_customer_monthly, fact_transactions_monthly, fact_branch_monthly, fact_complaint, fact_fraud_case |
| Platform | platform_table_stats, pipeline_runs, load_status, data_quality_summary |

## 3. Rename every query to the object name (remove the `mart ` prefix)

Example: `mart dim_date` > `dim_date`. The relationships and measures reference these exact names.

## 4. Apply the TMDL scripts (View > TMDL view > New script > paste > Apply)

1. `02_model.tmdl` | helper tables `dim_segment`, `dim_brand`, `bridge_steps`, 39 relationships, RLS roles
2. `03_measures.tmdl` | table `_Measures` with all measures in display folders 00 to 08

## 5. Model settings

- `dim_date`: **Mark as date table** (column `Date`); sort `MonthName` by `Month`, `MonthShort` by `Month`, `DayName` by `DayOfWeekNum`
- Hide all key columns (`*Key`) and helper columns from report view
- `dim_region[RegionCode]`: Data category **none**; `dim_branch[Latitude]` / `[Longitude]`: data category Latitude / Longitude
- `fact_complaint[ResolvedDateKey]` relationship is inactive by design (use `USERELATIONSHIP` if needed)

## 6. Row-Level Security

- Role **Executive**: no filter (sees all regions)
- Role **Regional Director**: `dim_region[DirectorEmail] = USERPRINCIPALNAME()`
- Test: Modeling > View as > Regional Director + Other user `ne.director@example.com` (should only show North East)

## 7. Refresh strategy

- The marts are rebuilt by the ADF master pipeline (`mart.usp_build_marts`); Power BI imports ~1-2M aggregated rows
- Scheduled refresh in Power BI Service: 1x per month after the ADF incremental run (no gateway needed for Azure SQL)
