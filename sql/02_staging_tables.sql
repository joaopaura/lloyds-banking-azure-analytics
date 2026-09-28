/* =====================================================================================
   Lloyds Banking Group | Portfolio project (HYPOTHETICAL DATA)
   02 | Staging layer (stg) | one table per source Parquet table
   - Column names = source column names (snake_case), so ADF maps them automatically
   - Heaps, all columns nullable: staging accepts dirty data, cleansing happens downstream
   - _source_file is filled by ADF ("Additional columns" = $$FILEPATH) for lineage
   - Tables are truncated by ADF before each file load (pre-copy script)
   ===================================================================================== */
SET NOCOUNT ON;
GO
IF DB_NAME() <> 'sqldb-lloyds'
BEGIN
    RAISERROR('WRONG DATABASE: select sqldb-lloyds in the database drop-down and run again.', 16, 1);
    SET NOEXEC ON;
END
GO
DROP TABLE IF EXISTS stg.regions, stg.products, stg.channels, stg.complaint_categories, stg.uk_bank_holidays,
    stg.bank_rate, stg.branches, stg.customers, stg.accounts, stg.deposit_balance_monthly,
    stg.loan_performance_monthly, stg.digital_activity_monthly, stg.transactions_daily,
    stg.branch_activity_monthly, stg.complaints, stg.fraud_cases, stg.budget_monthly, stg.opex_monthly;
GO
/* ---------- reference ---------- */
CREATE TABLE stg.regions (
    region_code VARCHAR(10), region_name VARCHAR(60), nation VARCHAR(30), regional_director VARCHAR(80),
    director_email VARCHAR(120), _source_file NVARCHAR(400), _load_ts DATETIME2(0) DEFAULT SYSUTCDATETIME());
CREATE TABLE stg.products (
    product_id VARCHAR(10), product_name VARCHAR(60), product_group VARCHAR(20), segment VARCHAR(20),
    is_secured BIT, is_government_guaranteed BIT, _source_file NVARCHAR(400), _load_ts DATETIME2(0) DEFAULT SYSUTCDATETIME());
CREATE TABLE stg.channels (
    channel_code VARCHAR(10), channel_name VARCHAR(60), _source_file NVARCHAR(400), _load_ts DATETIME2(0) DEFAULT SYSUTCDATETIME());
CREATE TABLE stg.complaint_categories (
    category_code VARCHAR(10), category_name VARCHAR(60), fca_product_group VARCHAR(60),
    _source_file NVARCHAR(400), _load_ts DATETIME2(0) DEFAULT SYSUTCDATETIME());
CREATE TABLE stg.uk_bank_holidays (
    holiday_date DATE, _source_file NVARCHAR(400), _load_ts DATETIME2(0) DEFAULT SYSUTCDATETIME());
/* Bank of England Bank Rate: loaded from the BoE API (CSV) or from the fallback Parquet */
CREATE TABLE stg.bank_rate (
    rate_date NVARCHAR(30), bank_rate NVARCHAR(20), source_system VARCHAR(20),
    _source_file NVARCHAR(400), _load_ts DATETIME2(0) DEFAULT SYSUTCDATETIME());

/* ---------- master data ---------- */
CREATE TABLE stg.branches (
    branch_id VARCHAR(10), branch_name NVARCHAR(100), brand VARCHAR(30), region_code VARCHAR(10), city NVARCHAR(60),
    latitude FLOAT, longitude FLOAT, branch_format VARCHAR(20), open_date DATETIME2(3), closure_date DATETIME2(3),
    _source_file NVARCHAR(400), _load_ts DATETIME2(0) DEFAULT SYSUTCDATETIME());
CREATE TABLE stg.customers (
    customer_id VARCHAR(12), segment VARCHAR(10), sub_segment VARCHAR(12), brand VARCHAR(30), region_code VARCHAR(10),
    city NVARCHAR(60), postcode_sector VARCHAR(12), age_band VARCHAR(10), income_band VARCHAR(10),
    industry VARCHAR(40), turnover_band VARCHAR(15), credit_score_band VARCHAR(12), onboarding_date DATETIME2(3),
    onboarding_channel VARCHAR(20), digital_registration_date DATETIME2(3), home_branch_id VARCHAR(10),
    churn_date DATETIME2(3), customer_status VARCHAR(10),
    _source_file NVARCHAR(400), _load_ts DATETIME2(0) DEFAULT SYSUTCDATETIME());
CREATE TABLE stg.accounts (
    account_id VARCHAR(12), customer_id VARCHAR(12), product_id VARCHAR(10), branch_id VARCHAR(10),
    open_date DATETIME2(3), close_date DATETIME2(3), account_status VARCHAR(15), original_amount FLOAT,
    term_months FLOAT, origination_rate FLOAT, origination_ltv FLOAT,
    _source_file NVARCHAR(400), _load_ts DATETIME2(0) DEFAULT SYSUTCDATETIME());

/* ---------- monthly / daily facts (incremental) ---------- */
CREATE TABLE stg.deposit_balance_monthly (
    account_id VARCHAR(12), month_end DATE, product_id VARCHAR(10), avg_balance FLOAT, eom_balance FLOAT,
    customer_rate FLOAT, ftp_rate FLOAT, interest_expense FLOAT, ftp_credit FLOAT, fee_income FLOAT,
    _source_file NVARCHAR(400));
CREATE TABLE stg.loan_performance_monthly (
    account_id VARCHAR(12), month_end DATE, product_id VARCHAR(10), rate_type VARCHAR(10), balance_eom FLOAT,
    credit_limit FLOAT, customer_rate FLOAT, ftp_rate FLOAT, interest_income FLOAT, ftp_charge FLOAT,
    fee_income FLOAT, scheduled_payment FLOAT, days_past_due BIGINT, arrears_bucket VARCHAR(10),
    ifrs9_stage FLOAT, pd_12m FLOAT, lgd FLOAT, ead FLOAT, ecl FLOAT, write_off_amount FLOAT,
    guarantee_claim_amount FLOAT, is_payment_holiday BIT, deal_end_date DATE, is_deal_maturity BIT,
    is_product_transfer BIT, current_ltv FLOAT, new_lending_amount FLOAT, account_status VARCHAR(15),
    _source_file NVARCHAR(400));
CREATE TABLE stg.digital_activity_monthly (
    customer_id VARCHAR(12), month_end DATE, web_logins BIGINT, app_sessions BIGINT, is_monthly_active BIT,
    features_used BIGINT, _source_file NVARCHAR(400));
CREATE TABLE stg.transactions_daily (
    txn_date DATE, region_code VARCHAR(10), product_id VARCHAR(10), channel_code VARCHAR(10), txn_type VARCHAR(30),
    txn_count BIGINT, txn_value FLOAT, _source_file NVARCHAR(400));
CREATE TABLE stg.branch_activity_monthly (
    branch_id VARCHAR(10), month_end DATE, footfall BIGINT, counter_txn_count BIGINT, staff_fte FLOAT,
    is_closure_month BIT, _source_file NVARCHAR(400));
CREATE TABLE stg.complaints (
    complaint_id VARCHAR(20), customer_id VARCHAR(12), received_date DATETIME2(3), resolved_date DATETIME2(3),
    category_code VARCHAR(10), root_cause VARCHAR(40), channel VARCHAR(20), upheld BIT, redress_amount FLOAT,
    referred_to_fos BIT, _source_file NVARCHAR(400));
CREATE TABLE stg.fraud_cases (
    case_id VARCHAR(20), customer_id VARCHAR(12), reported_date DATETIME2(3), fraud_type VARCHAR(30),
    channel VARCHAR(20), loss_amount FLOAT, reimbursed_amount FLOAT, recovered_amount FLOAT, case_status VARCHAR(25),
    _source_file NVARCHAR(400));

/* ---------- finance (full reload) ---------- */
CREATE TABLE stg.budget_monthly (
    region_code VARCHAR(10), month_end DATE, product_id VARCHAR(10), budget_balance FLOAT, budget_nii FLOAT,
    budget_fees FLOAT, budget_impairment FLOAT, _source_file NVARCHAR(400));
CREATE TABLE stg.opex_monthly (
    region_code VARCHAR(10), month_end DATE, cost_category VARCHAR(20), actual_amount FLOAT, budget_amount FLOAT,
    _source_file NVARCHAR(400));
GO
SELECT t.name AS staging_table, COUNT(c.column_id) AS columns
FROM sys.tables t JOIN sys.columns c ON c.object_id = t.object_id
WHERE SCHEMA_NAME(t.schema_id) = 'stg' GROUP BY t.name ORDER BY t.name;
GO
SET NOEXEC OFF;
