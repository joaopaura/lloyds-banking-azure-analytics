/* =====================================================================================
   Lloyds Banking Group | Portfolio project (HYPOTHETICAL DATA)
   05 | Load procedures  stg -> silver -> gold   (called by Azure Data Factory)
   Design notes
   - Procedures run WITH EXECUTE AS OWNER, so the ETL user needs no DDL rights
   - Dimensions: MERGE (SCD type 1) to keep surrogate keys stable across reloads
   - Facts: processed month by month (idempotent: delete period + insert), one transaction
     per month to keep the log small on the serverless tier
   - Silver rules for the large facts are applied in-flight (dedupe, sign fixes, imputation)
     instead of persisting a second 90M-row copy: a deliberate trade-off for the free tier
   - Every data quality rule writes to ops.dq_results
   ===================================================================================== */
SET NOCOUNT ON;
GO
IF DB_NAME() <> 'sqldb-lloyds'
BEGIN
    RAISERROR('WRONG DATABASE: select sqldb-lloyds in the database drop-down and run again.', 16, 1);
    SET NOEXEC ON;
END
GO
/* =====================================================================================
   Helpers
   ===================================================================================== */
CREATE OR ALTER FUNCTION gold.fn_date_key (@d DATE)
RETURNS INT WITH SCHEMABINDING
AS
BEGIN
    RETURN CASE WHEN @d IS NULL THEN NULL ELSE YEAR(@d) * 10000 + MONTH(@d) * 100 + DAY(@d) END;
END;
GO
CREATE OR ALTER PROCEDURE ops.usp_set_watermark @table_name VARCHAR(128), @month_end DATE
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE ops.watermark
       SET last_loaded_month_end = CASE WHEN last_loaded_month_end IS NULL OR @month_end > last_loaded_month_end
                                        THEN @month_end ELSE last_loaded_month_end END,
           updated_at_utc = SYSUTCDATETIME()
     WHERE table_name = @table_name;
END;
GO
/* =====================================================================================
   DimDate (generated in SQL, UK bank holidays from reference data)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_build_dim_date
    @start DATE = '2019-01-01', @end DATE = '2027-12-31', @last_actual DATE = '2026-08-31'
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;
    SET LANGUAGE us_english;
    TRUNCATE TABLE gold.DimDate;
    WITH n AS (
        SELECT TOP (DATEDIFF(DAY, @start, @end) + 1) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS i
        FROM sys.all_objects a CROSS JOIN sys.all_objects b),
    d AS (SELECT DATEADD(DAY, i, @start) AS dt FROM n)
    INSERT gold.DimDate (DateKey, [Date], [Year], [Quarter], QuarterLabel, [Month], MonthName, MonthShort, YearMonth,
                         MonthStart, MonthEnd, IsMonthEnd, DayOfMonth, DayOfWeekNum, DayName, IsWeekend,
                         IsUKBankHoliday, IsWorkingDay, IsActualPeriod)
    SELECT gold.fn_date_key(d.dt), d.dt, YEAR(d.dt), DATEPART(QUARTER, d.dt),
           CONCAT(YEAR(d.dt), ' Q', DATEPART(QUARTER, d.dt)), MONTH(d.dt), DATENAME(MONTH, d.dt),
           LEFT(DATENAME(MONTH, d.dt), 3), CONVERT(CHAR(7), d.dt, 126), DATEFROMPARTS(YEAR(d.dt), MONTH(d.dt), 1),
           EOMONTH(d.dt), IIF(d.dt = EOMONTH(d.dt), 1, 0), DAY(d.dt), w.dow, DATENAME(WEEKDAY, d.dt),
           IIF(w.dow >= 6, 1, 0), IIF(h.holiday_date IS NULL, 0, 1), IIF(w.dow < 6 AND h.holiday_date IS NULL, 1, 0),
           IIF(d.dt <= @last_actual, 1, 0)
    FROM d
    CROSS APPLY (SELECT ((DATEPART(WEEKDAY, d.dt) + @@DATEFIRST - 2) % 7) + 1 AS dow) w
    LEFT JOIN (SELECT DISTINCT holiday_date FROM stg.uk_bank_holidays) h ON h.holiday_date = d.dt;
END;
GO
/* =====================================================================================
   Dimensions: reference + master data (silver cleansing + gold MERGE)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_dimensions
    @last_actual DATE = '2026-08-31'
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @stg BIGINT, @slv BIGINT, @n BIGINT;

    EXEC gold.usp_build_dim_date @last_actual = @last_actual;

    /* ---------- reference dimensions ---------- */
    MERGE gold.DimRegion AS t
    USING (SELECT DISTINCT region_code, region_name, nation, regional_director, director_email FROM stg.regions) AS s
       ON t.RegionCode = s.region_code
    WHEN MATCHED THEN UPDATE SET RegionName = s.region_name, Nation = s.nation,
                                 RegionalDirector = s.regional_director, DirectorEmail = s.director_email
    WHEN NOT MATCHED THEN INSERT (RegionCode, RegionName, Nation, RegionalDirector, DirectorEmail)
                          VALUES (s.region_code, s.region_name, s.nation, s.regional_director, s.director_email);

    MERGE gold.DimProduct AS t
    USING (SELECT DISTINCT product_id, product_name, product_group, segment, is_secured, is_government_guaranteed,
                  TRY_CAST(RIGHT(product_id, 2) AS TINYINT) AS sort_order FROM stg.products) AS s
       ON t.ProductID = s.product_id
    WHEN MATCHED THEN UPDATE SET ProductName = s.product_name, ProductGroup = s.product_group, Segment = s.segment,
                                 IsSecured = s.is_secured, IsGovernmentGuaranteed = s.is_government_guaranteed,
                                 SortOrder = s.sort_order
    WHEN NOT MATCHED THEN INSERT (ProductID, ProductName, ProductGroup, Segment, IsSecured, IsGovernmentGuaranteed, SortOrder)
                          VALUES (s.product_id, s.product_name, s.product_group, s.segment, s.is_secured,
                                  s.is_government_guaranteed, s.sort_order);

    MERGE gold.DimChannel AS t
    USING (SELECT DISTINCT channel_code, channel_name,
                  CASE WHEN channel_code IN ('CH02', 'CH03') THEN 'Digital'
                       WHEN channel_code IN ('CH01', 'CH04') THEN 'Branch and Phone'
                       WHEN channel_code = 'CH05' THEN 'ATM'
                       ELSE 'Automated' END AS channel_group FROM stg.channels) AS s
       ON t.ChannelCode = s.channel_code
    WHEN MATCHED THEN UPDATE SET ChannelName = s.channel_name, ChannelGroup = s.channel_group
    WHEN NOT MATCHED THEN INSERT (ChannelCode, ChannelName, ChannelGroup) VALUES (s.channel_code, s.channel_name, s.channel_group);

    MERGE gold.DimComplaintCategory AS t
    USING (SELECT DISTINCT category_code, category_name, fca_product_group FROM stg.complaint_categories) AS s
       ON t.CategoryCode = s.category_code
    WHEN MATCHED THEN UPDATE SET CategoryName = s.category_name, FCAProductGroup = s.fca_product_group
    WHEN NOT MATCHED THEN INSERT (CategoryCode, CategoryName, FCAProductGroup)
                          VALUES (s.category_code, s.category_name, s.fca_product_group);

    /* ---------- branches ---------- */
    MERGE gold.DimBranch AS t
    USING (SELECT b.branch_id, b.branch_name, b.brand, r.RegionKey, b.city,
                  CAST(b.latitude AS DECIMAL(9,5)) AS lat, CAST(b.longitude AS DECIMAL(9,5)) AS lon, b.branch_format,
                  CAST(b.open_date AS DATE) AS open_date, CAST(b.closure_date AS DATE) AS closure_date,
                  IIF(b.closure_date IS NULL OR CAST(b.closure_date AS DATE) > @last_actual, 'Open', 'Closed') AS status
           FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY branch_id ORDER BY (SELECT NULL)) rn FROM stg.branches) b
           JOIN gold.DimRegion r ON r.RegionCode = UPPER(b.region_code)
           WHERE b.rn = 1) AS s
       ON t.BranchID = s.branch_id
    WHEN MATCHED THEN UPDATE SET BranchName = s.branch_name, Brand = s.brand, RegionKey = s.RegionKey, City = s.city,
                                 Latitude = s.lat, Longitude = s.lon, BranchFormat = s.branch_format,
                                 OpenDate = s.open_date, ClosureDate = s.closure_date, BranchStatus = s.status
    WHEN NOT MATCHED THEN INSERT (BranchID, BranchName, Brand, RegionKey, City, Latitude, Longitude, BranchFormat,
                                  OpenDate, ClosureDate, BranchStatus)
                          VALUES (s.branch_id, s.branch_name, s.brand, s.RegionKey, s.city, s.lat, s.lon,
                                  s.branch_format, s.open_date, s.closure_date, s.status);

    /* ---------- silver.customers (dedupe, postcode standardisation, region repair, date checks) ---------- */
    DROP TABLE IF EXISTS silver.customers;
    WITH d AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY _load_ts DESC) AS rn,
               UPPER(REPLACE(LTRIM(RTRIM(postcode_sector)), ' ', '')) AS pc
        FROM stg.customers)
    SELECT customer_id, segment, sub_segment, brand,
           NULLIF(UPPER(LTRIM(RTRIM(region_code))), '') AS region_code_src, city,
           CASE WHEN LEN(pc) >= 5 THEN LEFT(pc, LEN(pc) - 3) + ' ' + RIGHT(pc, 3) ELSE pc END AS postcode,
           LEFT(pc, PATINDEX('%[0-9]%', pc + '0') - 1) AS postcode_area,
           IIF(postcode_sector COLLATE Latin1_General_CS_AS <> UPPER(postcode_sector) OR CHARINDEX(' ', postcode_sector) = 0, 1, 0) AS pc_fixed,
           age_band, income_band, industry, turnover_band, credit_score_band,
           CAST(onboarding_date AS DATE) AS onboarding_date_src, onboarding_channel,
           CAST(digital_registration_date AS DATE) AS digital_registration_date, home_branch_id,
           CAST(churn_date AS DATE) AS churn_date, customer_status
    INTO silver.customers
    FROM d WHERE rn = 1;

    DROP TABLE IF EXISTS silver.postcode_area_region;
    SELECT postcode_area, region_code
    INTO silver.postcode_area_region
    FROM (SELECT postcode_area, region_code_src AS region_code,
                 ROW_NUMBER() OVER (PARTITION BY postcode_area ORDER BY COUNT(*) DESC) AS rn
          FROM silver.customers WHERE region_code_src IS NOT NULL
          GROUP BY postcode_area, region_code_src) x
    WHERE rn = 1;

    SELECT @stg = COUNT(*) FROM stg.customers;
    SELECT @slv = COUNT(*) FROM silver.customers;
    SET @n = @stg - @slv;
    EXEC ops.usp_log_dq 'silver', 'customers', NULL, 'Duplicate customer rows removed', 'Warning', @n, @stg, N'Kept latest row per customer_id';
    SELECT @n = COUNT(*) FROM silver.customers WHERE region_code_src IS NULL;
    EXEC ops.usp_log_dq 'silver', 'customers', NULL, 'Missing region code', 'Warning', @n, @slv, N'Region derived from postcode area mapping';
    SELECT @n = COUNT(*) FROM silver.customers WHERE pc_fixed = 1;
    EXEC ops.usp_log_dq 'silver', 'customers', NULL, 'Non-standard postcode format', 'Info', @n, @slv, N'Upper-cased and re-spaced (outward + inward code)';
    SELECT @n = COUNT(*) FROM silver.customers WHERE onboarding_date_src > @last_actual;
    EXEC ops.usp_log_dq 'silver', 'customers', NULL, 'Onboarding date in the future', 'Error', @n, @slv, N'Date set to NULL and flagged';

    MERGE gold.DimCustomer AS t
    USING (
        SELECT c.customer_id, c.segment, c.sub_segment, c.brand, r.RegionKey, c.city,
               CASE WHEN LEN(c.postcode) >= 5 THEN LEFT(c.postcode, LEN(c.postcode) - 2) ELSE c.postcode END AS postcode_sector, c.postcode_area,
               c.age_band, c.income_band, c.industry, c.turnover_band, c.credit_score_band,
               IIF(c.onboarding_date_src > @last_actual, NULL, c.onboarding_date_src) AS onboarding_date,
               c.onboarding_channel, c.digital_registration_date, b.BranchKey, c.churn_date, c.customer_status,
               NULLIF(CONCAT_WS('; ',
                   IIF(c.region_code_src IS NULL, 'Region derived from postcode', NULL),
                   IIF(c.onboarding_date_src > @last_actual, 'Future onboarding date removed', NULL)), '') AS dq_flag
        FROM silver.customers c
        LEFT JOIN silver.postcode_area_region m ON m.postcode_area = c.postcode_area
        JOIN gold.DimRegion r ON r.RegionCode = COALESCE(c.region_code_src, m.region_code)
        LEFT JOIN gold.DimBranch b ON b.BranchID = c.home_branch_id) AS s
       ON t.CustomerID = s.customer_id
    WHEN MATCHED THEN UPDATE SET
        Segment = s.segment, SubSegment = s.sub_segment, Brand = s.brand, RegionKey = s.RegionKey, City = s.city,
        PostcodeSector = s.postcode_sector, PostcodeArea = s.postcode_area, AgeBand = s.age_band,
        IncomeBand = s.income_band, Industry = s.industry, TurnoverBand = s.turnover_band,
        CreditScoreBand = s.credit_score_band, OnboardingDate = s.onboarding_date, OnboardingYear = YEAR(s.onboarding_date),
        OnboardingChannel = s.onboarding_channel, DigitalRegistrationDate = s.digital_registration_date,
        IsDigitallyRegistered = IIF(s.digital_registration_date IS NULL, 0, 1), HomeBranchKey = s.BranchKey,
        ChurnDate = s.churn_date, CustomerStatus = s.customer_status,
        TenureBand = CASE WHEN s.onboarding_date IS NULL THEN 'Unknown'
                          WHEN DATEDIFF(MONTH, s.onboarding_date, @last_actual) < 12 THEN '< 1 year'
                          WHEN DATEDIFF(MONTH, s.onboarding_date, @last_actual) < 36 THEN '1-3 years'
                          WHEN DATEDIFF(MONTH, s.onboarding_date, @last_actual) < 60 THEN '3-5 years'
                          WHEN DATEDIFF(MONTH, s.onboarding_date, @last_actual) < 120 THEN '5-10 years'
                          ELSE '10+ years' END,
        DQFlag = s.dq_flag
    WHEN NOT MATCHED THEN INSERT (CustomerID, Segment, SubSegment, Brand, RegionKey, City, PostcodeSector, PostcodeArea,
        AgeBand, IncomeBand, Industry, TurnoverBand, CreditScoreBand, OnboardingDate, OnboardingYear, OnboardingChannel,
        DigitalRegistrationDate, IsDigitallyRegistered, HomeBranchKey, ChurnDate, CustomerStatus, TenureBand, DQFlag)
    VALUES (s.customer_id, s.segment, s.sub_segment, s.brand, s.RegionKey, s.city, s.postcode_sector, s.postcode_area,
        s.age_band, s.income_band, s.industry, s.turnover_band, s.credit_score_band, s.onboarding_date,
        YEAR(s.onboarding_date), s.onboarding_channel, s.digital_registration_date,
        IIF(s.digital_registration_date IS NULL, 0, 1), s.BranchKey, s.churn_date, s.customer_status,
        CASE WHEN s.onboarding_date IS NULL THEN 'Unknown'
             WHEN DATEDIFF(MONTH, s.onboarding_date, @last_actual) < 12 THEN '< 1 year'
             WHEN DATEDIFF(MONTH, s.onboarding_date, @last_actual) < 36 THEN '1-3 years'
             WHEN DATEDIFF(MONTH, s.onboarding_date, @last_actual) < 60 THEN '3-5 years'
             WHEN DATEDIFF(MONTH, s.onboarding_date, @last_actual) < 120 THEN '5-10 years'
             ELSE '10+ years' END, s.dq_flag);

    /* ---------- accounts ---------- */
    DROP TABLE IF EXISTS silver.accounts;
    SELECT account_id, customer_id, product_id, branch_id, CAST(open_date AS DATE) AS open_date,
           CAST(close_date AS DATE) AS close_date, account_status, original_amount, term_months,
           origination_rate, origination_ltv
    INTO silver.accounts
    FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY _load_ts DESC) AS rn FROM stg.accounts) x
    WHERE rn = 1;
    SELECT @stg = COUNT(*) FROM stg.accounts;
    SELECT @slv = COUNT(*) FROM silver.accounts;
    SET @n = @stg - @slv;
    EXEC ops.usp_log_dq 'silver', 'accounts', NULL, 'Duplicate account rows removed', 'Warning', @n, @stg, N'Kept one row per account_id';

    MERGE gold.DimAccount AS t
    USING (
        SELECT a.account_id, c.CustomerKey, p.ProductKey, b.BranchKey, a.open_date, a.close_date, a.account_status,
               CAST(a.original_amount AS DECIMAL(18,2)) AS original_amount, CAST(a.term_months AS SMALLINT) AS term_months,
               CAST(a.origination_rate AS DECIMAL(7,4)) AS origination_rate, CAST(a.origination_ltv AS DECIMAL(7,4)) AS ltv,
               CASE WHEN a.origination_ltv IS NULL THEN NULL
                    WHEN a.origination_ltv <= 0.60 THEN '<= 60%'
                    WHEN a.origination_ltv <= 0.75 THEN '60-75%'
                    WHEN a.origination_ltv <= 0.85 THEN '75-85%'
                    WHEN a.origination_ltv <= 0.90 THEN '85-90%'
                    ELSE '> 90%' END AS ltv_band,
               YEAR(a.open_date) AS vintage_year, CONCAT(YEAR(a.open_date), ' Q', DATEPART(QUARTER, a.open_date)) AS vintage_q
        FROM silver.accounts a
        JOIN gold.DimCustomer c ON c.CustomerID = a.customer_id
        JOIN gold.DimProduct p ON p.ProductID = a.product_id
        LEFT JOIN gold.DimBranch b ON b.BranchID = a.branch_id) AS s
       ON t.AccountID = s.account_id
    WHEN MATCHED THEN UPDATE SET CustomerKey = s.CustomerKey, ProductKey = s.ProductKey, BranchKey = s.BranchKey,
        OpenDate = s.open_date, CloseDate = s.close_date, AccountStatus = s.account_status,
        OriginalAmount = s.original_amount, TermMonths = s.term_months, OriginationRate = s.origination_rate,
        OriginationLTV = s.ltv, OriginationLTVBand = s.ltv_band, VintageYear = s.vintage_year, VintageQuarter = s.vintage_q
    WHEN NOT MATCHED THEN INSERT (AccountID, CustomerKey, ProductKey, BranchKey, OpenDate, CloseDate, AccountStatus,
        OriginalAmount, TermMonths, OriginationRate, OriginationLTV, OriginationLTVBand, VintageYear, VintageQuarter)
    VALUES (s.account_id, s.CustomerKey, s.ProductKey, s.BranchKey, s.open_date, s.close_date, s.account_status,
        s.original_amount, s.term_months, s.origination_rate, s.ltv, s.ltv_band, s.vintage_year, s.vintage_q);
END;
GO
/* =====================================================================================
   Bank of England Bank Rate (API or fallback) -> daily series with forward fill
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_bank_rate
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @src VARCHAR(20), @min DATE, @max DATE, @first DECIMAL(5,2);
    DROP TABLE IF EXISTS #r;
    SELECT d, MAX(r) AS r, MAX(source_system) AS source_system
    INTO #r
    FROM (SELECT COALESCE(TRY_CONVERT(DATE, rate_date, 106), TRY_CONVERT(DATE, rate_date, 23),
                          TRY_CONVERT(DATE, LEFT(rate_date, 10), 23), TRY_CONVERT(DATE, rate_date)) AS d,
                 TRY_CONVERT(DECIMAL(5,2), bank_rate) AS r, source_system
          FROM stg.bank_rate
          WHERE source_system = (SELECT TOP 1 source_system FROM stg.bank_rate
                                 ORDER BY IIF(source_system = 'BoE API', 0, 1))) x
    WHERE d IS NOT NULL AND r IS NOT NULL
    GROUP BY d;
    IF NOT EXISTS (SELECT 1 FROM #r) BEGIN RAISERROR('No valid Bank Rate rows in stg.bank_rate', 16, 1); RETURN; END;
    SELECT @src = MAX(source_system), @min = '2020-01-01', @max = MAX(d) FROM #r;
    SELECT TOP 1 @first = r FROM #r ORDER BY d;
    BEGIN TRAN;
    TRUNCATE TABLE gold.FactBankRateDaily;
    WITH cal AS (SELECT DateKey, [Date] FROM gold.DimDate WHERE [Date] BETWEEN @min AND @max),
         j AS (SELECT cal.DateKey, cal.[Date], r.r FROM cal LEFT JOIN #r r ON r.d = cal.[Date]),
         g AS (SELECT *, COUNT(r) OVER (ORDER BY [Date] ROWS UNBOUNDED PRECEDING) AS grp FROM j)
    INSERT gold.FactBankRateDaily (DateKey, BankRate, SourceSystem)
    SELECT DateKey, COALESCE(MAX(r) OVER (PARTITION BY grp), @first), @src FROM g;
    COMMIT;
END;
GO
/* =====================================================================================
   FACT | deposit balances (monthly, ~50M rows)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_fact_deposit_balance
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @m DATE, @dk INT, @total BIGINT, @distinct BIGINT, @ins BIGINT, @neg BIGINT, @max DATE, @n BIGINT;
    IF NOT EXISTS (SELECT 1 FROM stg.deposit_balance_monthly) RETURN;
    IF INDEXPROPERTY(OBJECT_ID('stg.deposit_balance_monthly'), 'IX_stg_dep_month', 'IndexID') IS NULL
        CREATE CLUSTERED INDEX IX_stg_dep_month ON stg.deposit_balance_monthly (month_end);
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT DISTINCT month_end FROM stg.deposit_balance_monthly ORDER BY month_end;
    OPEN c; FETCH NEXT FROM c INTO @m;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @dk = gold.fn_date_key(@m);
        SELECT @total = COUNT(*), @distinct = COUNT(DISTINCT account_id),
               @neg = SUM(CASE WHEN avg_balance < 0 AND product_id IN ('P02', 'P03') THEN 1 ELSE 0 END)
        FROM stg.deposit_balance_monthly WHERE month_end = @m;
        BEGIN TRAN;
        DELETE gold.FactDepositBalanceMonthly WHERE DateKey = @dk;
        WITH s AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY (SELECT NULL)) AS rn
                   FROM stg.deposit_balance_monthly WHERE month_end = @m)
        INSERT gold.FactDepositBalanceMonthly WITH (TABLOCK)
            (DateKey, AccountKey, CustomerKey, ProductKey, RegionKey, AvgBalance, EOMBalance, CustomerRate, FTPRate,
             InterestExpense, FTPCredit, FeeIncome)
        SELECT @dk, a.AccountKey, a.CustomerKey, a.ProductKey, cu.RegionKey,
               CASE WHEN s.avg_balance < 0 AND s.product_id IN ('P02', 'P03') THEN -s.avg_balance ELSE s.avg_balance END,
               s.eom_balance, s.customer_rate, s.ftp_rate, s.interest_expense, s.ftp_credit, s.fee_income
        FROM s
        JOIN gold.DimAccount a ON a.AccountID = s.account_id
        JOIN gold.DimCustomer cu ON cu.CustomerKey = a.CustomerKey
        WHERE s.rn = 1;
        SET @ins = @@ROWCOUNT;
        COMMIT;
        SET @n = @total - @distinct;
        EXEC ops.usp_log_dq 'gold', 'FactDepositBalanceMonthly', @m, 'Duplicate rows removed', 'Warning', @n, @total, N'Kept one row per account and month';
        EXEC ops.usp_log_dq 'gold', 'FactDepositBalanceMonthly', @m, 'Negative savings balance (sign error)', 'Warning', @neg, @total, N'Converted to absolute value';
        SET @n = @distinct - @ins;
        EXEC ops.usp_log_dq 'gold', 'FactDepositBalanceMonthly', @m, 'Orphan rows (account not in DimAccount)', 'Error', @n, @total, N'Rejected';
        SET @max = @m;
        FETCH NEXT FROM c INTO @m;
    END
    CLOSE c; DEALLOCATE c;
    EXEC ops.usp_set_watermark 'deposit_balance_monthly', @max;
    DROP INDEX IX_stg_dep_month ON stg.deposit_balance_monthly;
    TRUNCATE TABLE stg.deposit_balance_monthly;
END;
GO
/* =====================================================================================
   FACT | loan performance (monthly, ~16M rows)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_fact_loan_performance
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @m DATE, @dk INT, @total BIGINT, @distinct BIGINT, @ins BIGINT, @nostage BIGINT, @max DATE, @n BIGINT;
    IF NOT EXISTS (SELECT 1 FROM stg.loan_performance_monthly) RETURN;
    IF INDEXPROPERTY(OBJECT_ID('stg.loan_performance_monthly'), 'IX_stg_loan_month', 'IndexID') IS NULL
        CREATE CLUSTERED INDEX IX_stg_loan_month ON stg.loan_performance_monthly (month_end);
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT DISTINCT month_end FROM stg.loan_performance_monthly ORDER BY month_end;
    OPEN c; FETCH NEXT FROM c INTO @m;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @dk = gold.fn_date_key(@m);
        SELECT @total = COUNT(*), @distinct = COUNT(DISTINCT account_id),
               @nostage = SUM(CASE WHEN ifrs9_stage IS NULL THEN 1 ELSE 0 END)
        FROM stg.loan_performance_monthly WHERE month_end = @m;
        BEGIN TRAN;
        DELETE gold.FactLoanPerformanceMonthly WHERE DateKey = @dk;
        WITH s AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY (SELECT NULL)) AS rn
                   FROM stg.loan_performance_monthly WHERE month_end = @m)
        INSERT gold.FactLoanPerformanceMonthly WITH (TABLOCK)
            (DateKey, AccountKey, CustomerKey, ProductKey, RegionKey, RateType, BalanceEOM, CreditLimit, CustomerRate,
             FTPRate, InterestIncome, FTPCharge, FeeIncome, ScheduledPayment, DaysPastDue, ArrearsBucket, IFRS9Stage,
             PD12m, LGD, EAD, ECL, WriteOffAmount, GuaranteeClaimAmount, IsPaymentHoliday, DealEndDateKey,
             IsDealMaturity, IsProductTransfer, CurrentLTV, NewLendingAmount, AccountStatus)
        SELECT @dk, a.AccountKey, a.CustomerKey, a.ProductKey, cu.RegionKey, s.rate_type, s.balance_eom, s.credit_limit,
               s.customer_rate, s.ftp_rate, s.interest_income, s.ftp_charge, s.fee_income, s.scheduled_payment,
               s.days_past_due, s.arrears_bucket,
               COALESCE(CAST(s.ifrs9_stage AS TINYINT),                       -- imputation rule for missing stage
                        CASE WHEN s.arrears_bucket = '90+' THEN 3 WHEN s.days_past_due >= 30 THEN 2 ELSE 1 END),
               s.pd_12m, s.lgd, s.ead, s.ecl, s.write_off_amount, s.guarantee_claim_amount, s.is_payment_holiday,
               gold.fn_date_key(s.deal_end_date), s.is_deal_maturity, s.is_product_transfer, s.current_ltv,
               s.new_lending_amount, s.account_status
        FROM s
        JOIN gold.DimAccount a ON a.AccountID = s.account_id
        JOIN gold.DimCustomer cu ON cu.CustomerKey = a.CustomerKey
        WHERE s.rn = 1;
        SET @ins = @@ROWCOUNT;
        COMMIT;
        SET @n = @total - @distinct;
        EXEC ops.usp_log_dq 'gold', 'FactLoanPerformanceMonthly', @m, 'Duplicate rows removed', 'Warning', @n, @total, N'Kept one row per account and month';
        EXEC ops.usp_log_dq 'gold', 'FactLoanPerformanceMonthly', @m, 'Missing IFRS 9 stage', 'Warning', @nostage, @total, N'Imputed from arrears (90+ = Stage 3, 30+ DPD = Stage 2, else Stage 1)';
        SET @n = @distinct - @ins;
        EXEC ops.usp_log_dq 'gold', 'FactLoanPerformanceMonthly', @m, 'Orphan rows (account not in DimAccount)', 'Error', @n, @total, N'Rejected';
        SET @max = @m;
        FETCH NEXT FROM c INTO @m;
    END
    CLOSE c; DEALLOCATE c;
    EXEC ops.usp_set_watermark 'loan_performance_monthly', @max;
    DROP INDEX IX_stg_loan_month ON stg.loan_performance_monthly;
    TRUNCATE TABLE stg.loan_performance_monthly;
END;
GO
/* =====================================================================================
   FACT | digital activity (monthly, ~27M rows)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_fact_digital
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @m DATE, @dk INT, @total BIGINT, @ins BIGINT, @max DATE, @n BIGINT;
    IF NOT EXISTS (SELECT 1 FROM stg.digital_activity_monthly) RETURN;
    IF INDEXPROPERTY(OBJECT_ID('stg.digital_activity_monthly'), 'IX_stg_dig_month', 'IndexID') IS NULL
        CREATE CLUSTERED INDEX IX_stg_dig_month ON stg.digital_activity_monthly (month_end);
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT DISTINCT month_end FROM stg.digital_activity_monthly ORDER BY month_end;
    OPEN c; FETCH NEXT FROM c INTO @m;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @dk = gold.fn_date_key(@m);
        SELECT @total = COUNT(*) FROM stg.digital_activity_monthly WHERE month_end = @m;
        BEGIN TRAN;
        DELETE gold.FactDigitalMonthly WHERE DateKey = @dk;
        INSERT gold.FactDigitalMonthly WITH (TABLOCK)
            (DateKey, CustomerKey, RegionKey, WebLogins, AppSessions, IsMonthlyActive, FeaturesUsed)
        SELECT @dk, cu.CustomerKey, cu.RegionKey, s.web_logins, s.app_sessions, s.is_monthly_active, s.features_used
        FROM stg.digital_activity_monthly s
        JOIN gold.DimCustomer cu ON cu.CustomerID = s.customer_id
        WHERE s.month_end = @m;
        SET @ins = @@ROWCOUNT;
        COMMIT;
        SET @n = @total - @ins;
        EXEC ops.usp_log_dq 'gold', 'FactDigitalMonthly', @m, 'Orphan rows (customer not in DimCustomer)', 'Error', @n, @total, N'Rejected';
        SET @max = @m;
        FETCH NEXT FROM c INTO @m;
    END
    CLOSE c; DEALLOCATE c;
    EXEC ops.usp_set_watermark 'digital_activity_monthly', @max;
    DROP INDEX IX_stg_dig_month ON stg.digital_activity_monthly;
    TRUNCATE TABLE stg.digital_activity_monthly;
END;
GO
/* =====================================================================================
   FACT | daily transactions (aggregated, ~0.7M rows) - set based
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_fact_transactions
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @total BIGINT, @lower BIGINT, @min DATE, @max DATE;
    IF NOT EXISTS (SELECT 1 FROM stg.transactions_daily) RETURN;
    SELECT @total = COUNT(*), @min = MIN(txn_date), @max = MAX(txn_date),
           @lower = SUM(CASE WHEN region_code COLLATE Latin1_General_CS_AS <> UPPER(region_code) THEN 1 ELSE 0 END)
    FROM stg.transactions_daily;
    BEGIN TRAN;
    DELETE gold.FactTransactionDaily WHERE DateKey BETWEEN gold.fn_date_key(@min) AND gold.fn_date_key(@max);
    INSERT gold.FactTransactionDaily WITH (TABLOCK) (DateKey, RegionKey, ProductKey, ChannelKey, TxnType, TxnCount, TxnValue)
    SELECT gold.fn_date_key(s.txn_date), r.RegionKey, p.ProductKey, ch.ChannelKey, s.txn_type,
           SUM(s.txn_count), SUM(s.txn_value)
    FROM stg.transactions_daily s
    JOIN gold.DimRegion r ON r.RegionCode = UPPER(LTRIM(RTRIM(s.region_code)))
    JOIN gold.DimProduct p ON p.ProductID = s.product_id
    JOIN gold.DimChannel ch ON ch.ChannelCode = s.channel_code
    GROUP BY s.txn_date, r.RegionKey, p.ProductKey, ch.ChannelKey, s.txn_type;
    COMMIT;
    EXEC ops.usp_log_dq 'gold', 'FactTransactionDaily', NULL, 'Lower-case region code', 'Info', @lower, @total, N'Upper-cased and re-aggregated';
    EXEC ops.usp_set_watermark 'transactions_daily', @max;
    TRUNCATE TABLE stg.transactions_daily;
END;
GO
/* =====================================================================================
   FACT | branch activity (monthly)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_fact_branch_activity
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @min DATE, @max DATE;
    IF NOT EXISTS (SELECT 1 FROM stg.branch_activity_monthly) RETURN;
    SELECT @min = MIN(month_end), @max = MAX(month_end) FROM stg.branch_activity_monthly;
    BEGIN TRAN;
    DELETE gold.FactBranchMonthly WHERE DateKey BETWEEN gold.fn_date_key(@min) AND gold.fn_date_key(@max);
    INSERT gold.FactBranchMonthly (DateKey, BranchKey, RegionKey, Footfall, CounterTxnCount, StaffFTE, IsClosureMonth)
    SELECT gold.fn_date_key(s.month_end), b.BranchKey, b.RegionKey, MAX(s.footfall), MAX(s.counter_txn_count),
           MAX(s.staff_fte), MAX(CAST(s.is_closure_month AS TINYINT))
    FROM stg.branch_activity_monthly s
    JOIN gold.DimBranch b ON b.BranchID = s.branch_id
    GROUP BY s.month_end, b.BranchKey, b.RegionKey;
    COMMIT;
    EXEC ops.usp_set_watermark 'branch_activity_monthly', @max;
    TRUNCATE TABLE stg.branch_activity_monthly;
END;
GO
/* =====================================================================================
   FACT | complaints (MERGE handles late-arriving records)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_fact_complaints
    @last_actual DATE = '2026-08-31'
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @total BIGINT, @late BIGINT, @bad BIGINT, @max DATE;
    IF NOT EXISTS (SELECT 1 FROM stg.complaints) RETURN;
    SELECT @total = COUNT(*),
           @bad = SUM(CASE WHEN resolved_date < received_date THEN 1 ELSE 0 END),
           @late = SUM(CASE WHEN EOMONTH(received_date) < TRY_CONVERT(DATE, SUBSTRING(_source_file,
                         CHARINDEX('year=', _source_file) + 5, 4) + '-' +
                         SUBSTRING(_source_file, CHARINDEX('month=', _source_file) + 6, 2) + '-01') THEN 1 ELSE 0 END),
           @max = EOMONTH(MAX(received_date))
    FROM stg.complaints;
    MERGE gold.FactComplaint AS t
    USING (
        SELECT s.complaint_id, cu.CustomerKey, cu.RegionKey, cc.CategoryKey,
               gold.fn_date_key(CAST(s.received_date AS DATE)) AS rec_key,
               CASE WHEN s.resolved_date >= s.received_date THEN gold.fn_date_key(CAST(s.resolved_date AS DATE)) END AS res_key,
               s.root_cause, s.channel, s.upheld, CAST(s.redress_amount AS DECIMAL(18,2)) AS redress, s.referred_to_fos,
               CASE WHEN s.resolved_date >= s.received_date THEN DATEDIFF(DAY, s.received_date, s.resolved_date) END AS days,
               CASE WHEN s.resolved_date IS NULL THEN 1 ELSE 0 END AS is_open,
               CASE WHEN s.resolved_date < s.received_date THEN 'Resolved before received: date removed' END AS dq
        FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY complaint_id ORDER BY (SELECT NULL)) rn FROM stg.complaints) s
        JOIN gold.DimCustomer cu ON cu.CustomerID = s.customer_id
        JOIN gold.DimComplaintCategory cc ON cc.CategoryCode = s.category_code
        WHERE s.rn = 1) AS s
       ON t.ComplaintID = s.complaint_id
    WHEN MATCHED THEN UPDATE SET CustomerKey = s.CustomerKey, RegionKey = s.RegionKey, CategoryKey = s.CategoryKey,
        ReceivedDateKey = s.rec_key, ResolvedDateKey = s.res_key, RootCause = s.root_cause, Channel = s.channel,
        IsUpheld = s.upheld, RedressAmount = s.redress, IsReferredToFOS = s.referred_to_fos, DaysToResolve = s.days,
        IsResolvedWithin8Weeks = CASE WHEN s.days IS NULL THEN NULL WHEN s.days <= 56 THEN 1 ELSE 0 END,
        IsOpen = s.is_open, DQFlag = s.dq
    WHEN NOT MATCHED THEN INSERT (ComplaintID, CustomerKey, RegionKey, CategoryKey, ReceivedDateKey, ResolvedDateKey,
        RootCause, Channel, IsUpheld, RedressAmount, IsReferredToFOS, DaysToResolve, IsResolvedWithin8Weeks, IsOpen, DQFlag)
    VALUES (s.complaint_id, s.CustomerKey, s.RegionKey, s.CategoryKey, s.rec_key, s.res_key, s.root_cause, s.channel,
        s.upheld, s.redress, s.referred_to_fos, s.days,
        CASE WHEN s.days IS NULL THEN NULL WHEN s.days <= 56 THEN 1 ELSE 0 END, s.is_open, s.dq);
    EXEC ops.usp_log_dq 'gold', 'FactComplaint', NULL, 'Resolved date before received date', 'Error', @bad, @total, N'Resolved date removed, complaint kept';
    EXEC ops.usp_log_dq 'gold', 'FactComplaint', NULL, 'Late-arriving records', 'Info', @late, @total, N'Upserted by ComplaintID into the correct received month';
    EXEC ops.usp_set_watermark 'complaints', @max;
    TRUNCATE TABLE stg.complaints;
END;
GO
/* =====================================================================================
   FACT | fraud cases
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_fact_fraud
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @max DATE;
    IF NOT EXISTS (SELECT 1 FROM stg.fraud_cases) RETURN;
    SELECT @max = EOMONTH(MAX(reported_date)) FROM stg.fraud_cases;
    MERGE gold.FactFraudCase AS t
    USING (
        SELECT s.case_id, cu.CustomerKey, cu.RegionKey, gold.fn_date_key(CAST(s.reported_date AS DATE)) AS rep_key,
               s.fraud_type, s.channel, CAST(s.loss_amount AS DECIMAL(18,2)) AS loss,
               CAST(s.reimbursed_amount AS DECIMAL(18,2)) AS reimb, CAST(s.recovered_amount AS DECIMAL(18,2)) AS rec,
               s.case_status, IIF(CAST(s.reported_date AS DATE) >= '2024-10-07', 1, 0) AS post_psr
        FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY case_id ORDER BY (SELECT NULL)) rn FROM stg.fraud_cases) s
        JOIN gold.DimCustomer cu ON cu.CustomerID = s.customer_id
        WHERE s.rn = 1) AS s
       ON t.CaseID = s.case_id
    WHEN MATCHED THEN UPDATE SET CustomerKey = s.CustomerKey, RegionKey = s.RegionKey, ReportedDateKey = s.rep_key,
        FraudType = s.fraud_type, Channel = s.channel, LossAmount = s.loss, ReimbursedAmount = s.reimb,
        RecoveredAmount = s.rec, CaseStatus = s.case_status, IsPostPSRRule = s.post_psr
    WHEN NOT MATCHED THEN INSERT (CaseID, CustomerKey, RegionKey, ReportedDateKey, FraudType, Channel, LossAmount,
        ReimbursedAmount, RecoveredAmount, CaseStatus, IsPostPSRRule)
    VALUES (s.case_id, s.CustomerKey, s.RegionKey, s.rep_key, s.fraud_type, s.channel, s.loss, s.reimb, s.rec,
        s.case_status, s.post_psr);
    EXEC ops.usp_set_watermark 'fraud_cases', @max;
    TRUNCATE TABLE stg.fraud_cases;
END;
GO
/* =====================================================================================
   FINANCE | budget + opex (full reload)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE gold.usp_load_finance
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    BEGIN TRAN;
    TRUNCATE TABLE gold.FactBudgetMonthly;
    INSERT gold.FactBudgetMonthly (DateKey, RegionKey, ProductKey, BudgetBalance, BudgetNII, BudgetFees, BudgetImpairment)
    SELECT gold.fn_date_key(s.month_end), r.RegionKey, p.ProductKey, SUM(s.budget_balance), SUM(s.budget_nii),
           SUM(s.budget_fees), SUM(s.budget_impairment)
    FROM stg.budget_monthly s
    JOIN gold.DimRegion r ON r.RegionCode = s.region_code
    JOIN gold.DimProduct p ON p.ProductID = s.product_id
    GROUP BY s.month_end, r.RegionKey, p.ProductKey;
    TRUNCATE TABLE gold.FactOpexMonthly;
    INSERT gold.FactOpexMonthly (DateKey, RegionKey, CostCategory, ActualAmount, BudgetAmount)
    SELECT gold.fn_date_key(s.month_end), r.RegionKey, s.cost_category, SUM(s.actual_amount), SUM(s.budget_amount)
    FROM stg.opex_monthly s
    JOIN gold.DimRegion r ON r.RegionCode = s.region_code
    GROUP BY s.month_end, r.RegionKey, s.cost_category;
    COMMIT;
END;
GO
/* =====================================================================================
   MART refresh (placeholder - the Power BI marts are built in script 06)
   ===================================================================================== */
CREATE OR ALTER PROCEDURE mart.usp_refresh_marts
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON;
    IF OBJECT_ID('mart.usp_build_marts') IS NOT NULL EXEC ('EXEC mart.usp_build_marts');
END;
GO
SELECT SCHEMA_NAME(schema_id) + '.' + name AS procedure_name, create_date
FROM sys.procedures WHERE SCHEMA_NAME(schema_id) IN ('gold', 'ops', 'mart') ORDER BY 1;
GO
SET NOEXEC OFF;
