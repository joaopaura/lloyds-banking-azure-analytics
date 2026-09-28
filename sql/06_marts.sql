/* =====================================================================================
   Lloyds Banking Group | Portfolio project (HYPOTHETICAL DATA)
   06 | Mart layer for Power BI
   - Aggregated tables (built by mart.usp_build_marts, called at the end of the ADF master pipeline)
   - Thin views over gold for small dimensions/facts
   - Power BI imports ONLY the mart schema (user pbi_reader): ~1-2M rows instead of ~96M
   Grain notes: monthly facts use the month-end DateKey (yyyymmdd) and relate to mart.dim_date
   ===================================================================================== */
SET NOCOUNT ON;
GO
IF DB_NAME() <> 'sqldb-lloyds'
BEGIN
    RAISERROR('WRONG DATABASE: select sqldb-lloyds in the database drop-down and run again.', 16, 1);
    SET NOEXEC ON;
END
GO
/* =============================== VIEWS (dimensions) =============================== */
CREATE OR ALTER VIEW mart.dim_date AS
SELECT DateKey, [Date], [Year], [Quarter], QuarterLabel, [Month], MonthName, MonthShort, YearMonth, MonthStart,
       MonthEnd, gold.fn_date_key(MonthEnd) AS MonthEndKey, IsMonthEnd, DayOfWeekNum, DayName, IsWeekend,
       IsUKBankHoliday, IsWorkingDay, IsActualPeriod
FROM gold.DimDate
WHERE [Date] BETWEEN '2020-01-01' AND '2026-12-31';
GO
CREATE OR ALTER VIEW mart.dim_region AS
SELECT RegionKey, RegionCode, RegionName, Nation, RegionalDirector, DirectorEmail FROM gold.DimRegion;
GO
CREATE OR ALTER VIEW mart.dim_product AS
SELECT ProductKey, ProductID, ProductName, ProductGroup, Segment, IsSecured, IsGovernmentGuaranteed, SortOrder
FROM gold.DimProduct;
GO
CREATE OR ALTER VIEW mart.dim_channel AS
SELECT ChannelKey, ChannelCode, ChannelName, ChannelGroup FROM gold.DimChannel;
GO
CREATE OR ALTER VIEW mart.dim_complaint_category AS
SELECT CategoryKey, CategoryCode, CategoryName, FCAProductGroup FROM gold.DimComplaintCategory;
GO
CREATE OR ALTER VIEW mart.dim_branch AS
SELECT BranchKey, BranchID, BranchName, Brand, RegionKey, City, Latitude, Longitude, BranchFormat, OpenDate,
       ClosureDate, BranchStatus
FROM gold.DimBranch;
GO
/* =============================== VIEWS (small facts) ============================== */
CREATE OR ALTER VIEW mart.fact_branch_monthly AS
SELECT DateKey, BranchKey, RegionKey, Footfall, CounterTxnCount, StaffFTE, IsClosureMonth FROM gold.FactBranchMonthly;
GO
CREATE OR ALTER VIEW mart.fact_complaint AS
SELECT f.ComplaintID, f.RegionKey, f.CategoryKey, f.ReceivedDateKey, f.ResolvedDateKey, f.RootCause, f.Channel,
       f.IsUpheld, f.RedressAmount, f.IsReferredToFOS, f.DaysToResolve, f.IsResolvedWithin8Weeks, f.IsOpen,
       c.Segment, c.Brand
FROM gold.FactComplaint f JOIN gold.DimCustomer c ON c.CustomerKey = f.CustomerKey;
GO
CREATE OR ALTER VIEW mart.fact_fraud_case AS
SELECT f.CaseID, f.RegionKey, f.ReportedDateKey, f.FraudType, f.Channel, f.LossAmount, f.ReimbursedAmount,
       f.RecoveredAmount, f.CaseStatus, f.IsPostPSRRule, c.Segment, c.Brand, c.AgeBand
FROM gold.FactFraudCase f JOIN gold.DimCustomer c ON c.CustomerKey = f.CustomerKey;
GO
CREATE OR ALTER VIEW mart.fact_budget_monthly AS
SELECT DateKey, RegionKey, ProductKey, BudgetBalance, BudgetNII, BudgetFees, BudgetImpairment FROM gold.FactBudgetMonthly;
GO
CREATE OR ALTER VIEW mart.fact_opex_monthly AS
SELECT DateKey, RegionKey, CostCategory, ActualAmount, BudgetAmount FROM gold.FactOpexMonthly;
GO
CREATE OR ALTER VIEW mart.fact_bank_rate_daily AS
SELECT DateKey, BankRate, SourceSystem FROM gold.FactBankRateDaily;
GO
CREATE OR ALTER VIEW mart.data_quality_summary AS
SELECT layer, table_name, check_name, severity, action_taken,
       SUM(affected_rows) AS affected_rows, MAX(checked_at_utc) AS last_checked_utc
FROM ops.dq_results
GROUP BY layer, table_name, check_name, severity, action_taken;
GO
/* =============================== BUILD PROCEDURE ================================== */
CREATE OR ALTER PROCEDURE mart.usp_build_marts
    @last_actual DATE = '2026-08-31'
WITH EXECUTE AS OWNER
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    DECLARE @last_key INT = gold.fn_date_key(@last_actual);

    /* ---------------------------------------------------------------------------------
       1. Product P&L and balance sheet | month x region x product x brand x sub-segment
       NII (FTP basis) = InterestIncome - FTPCharge + FTPCredit - InterestExpense
       --------------------------------------------------------------------------------- */
    DROP TABLE IF EXISTS mart.fact_product_monthly;
    SELECT DateKey, RegionKey, ProductKey, Brand, SubSegment,
           CAST(SUM(Accounts) AS INT)                 AS Accounts,
           CAST(SUM(AvgBalance) AS DECIMAL(18,2))     AS AvgBalance,
           CAST(SUM(EOMBalance) AS DECIMAL(18,2))     AS EOMBalance,
           CAST(SUM(InterestIncome) AS DECIMAL(18,2)) AS InterestIncome,
           CAST(SUM(InterestExpense) AS DECIMAL(18,2)) AS InterestExpense,
           CAST(SUM(FTPCredit) AS DECIMAL(18,2))      AS FTPCredit,
           CAST(SUM(FTPCharge) AS DECIMAL(18,2))      AS FTPCharge,
           CAST(SUM(FeeIncome) AS DECIMAL(18,2))      AS FeeIncome,
           CAST(SUM(NewLending) AS DECIMAL(18,2))     AS NewLending,
           CAST(SUM(WriteOff) AS DECIMAL(18,2))       AS WriteOff,
           CAST(SUM(GuaranteeClaim) AS DECIMAL(18,2)) AS GuaranteeClaim,
           CAST(SUM(ECL) AS DECIMAL(18,2))            AS ECL,
           CAST(SUM(Stage1Balance) AS DECIMAL(18,2))  AS Stage1Balance,
           CAST(SUM(Stage2Balance) AS DECIMAL(18,2))  AS Stage2Balance,
           CAST(SUM(Stage3Balance) AS DECIMAL(18,2))  AS Stage3Balance,
           CAST(SUM(Arrears30Balance) AS DECIMAL(18,2)) AS Arrears30Balance,
           CAST(SUM(Arrears90Balance) AS DECIMAL(18,2)) AS Arrears90Balance,
           CAST(SUM(PaymentHolidayBalance) AS DECIMAL(18,2)) AS PaymentHolidayBalance,
           CAST(SUM(CreditLimit) AS DECIMAL(18,2))    AS CreditLimit,
           CAST(SUM(RateXBalance) AS DECIMAL(22,4))   AS RateXBalance      -- for balance-weighted customer rate
    INTO mart.fact_product_monthly
    FROM (
        SELECT f.DateKey, f.RegionKey, f.ProductKey, c.Brand, c.SubSegment,
               COUNT_BIG(*) AS Accounts, SUM(f.AvgBalance) AS AvgBalance, SUM(f.EOMBalance) AS EOMBalance,
               0 AS InterestIncome, SUM(f.InterestExpense) AS InterestExpense, SUM(f.FTPCredit) AS FTPCredit,
               0 AS FTPCharge, SUM(f.FeeIncome) AS FeeIncome, 0 AS NewLending, 0 AS WriteOff, 0 AS GuaranteeClaim,
               0 AS ECL, 0 AS Stage1Balance, 0 AS Stage2Balance, 0 AS Stage3Balance, 0 AS Arrears30Balance,
               0 AS Arrears90Balance, 0 AS PaymentHolidayBalance, 0 AS CreditLimit,
               SUM(f.CustomerRate * f.AvgBalance) AS RateXBalance
        FROM gold.FactDepositBalanceMonthly f
        JOIN gold.DimCustomer c ON c.CustomerKey = f.CustomerKey
        GROUP BY f.DateKey, f.RegionKey, f.ProductKey, c.Brand, c.SubSegment
        UNION ALL
        SELECT f.DateKey, f.RegionKey, f.ProductKey, c.Brand, c.SubSegment,
               SUM(CASE WHEN f.AccountStatus = 'Open' THEN 1 ELSE 0 END), SUM(f.BalanceEOM), SUM(f.BalanceEOM),
               SUM(f.InterestIncome), 0, 0, SUM(f.FTPCharge), SUM(f.FeeIncome), SUM(f.NewLendingAmount),
               SUM(f.WriteOffAmount), SUM(f.GuaranteeClaimAmount), SUM(f.ECL),
               SUM(CASE WHEN f.IFRS9Stage = 1 THEN f.BalanceEOM ELSE 0 END),
               SUM(CASE WHEN f.IFRS9Stage = 2 THEN f.BalanceEOM ELSE 0 END),
               SUM(CASE WHEN f.IFRS9Stage = 3 THEN f.BalanceEOM ELSE 0 END),
               SUM(CASE WHEN f.DaysPastDue >= 30 THEN f.BalanceEOM ELSE 0 END),
               SUM(CASE WHEN f.ArrearsBucket = '90+' THEN f.BalanceEOM ELSE 0 END),
               SUM(CASE WHEN f.IsPaymentHoliday = 1 THEN f.BalanceEOM ELSE 0 END),
               SUM(COALESCE(f.CreditLimit, 0)),
               SUM(f.CustomerRate * f.BalanceEOM)
        FROM gold.FactLoanPerformanceMonthly f
        JOIN gold.DimCustomer c ON c.CustomerKey = f.CustomerKey
        GROUP BY f.DateKey, f.RegionKey, f.ProductKey, c.Brand, c.SubSegment
    ) x
    GROUP BY DateKey, RegionKey, ProductKey, Brand, SubSegment;

    /* ---------------------------------------------------------------------------------
       2. Credit risk | month x region x product x score band x LTV band x stage x arrears
       --------------------------------------------------------------------------------- */
    DROP TABLE IF EXISTS mart.fact_credit_risk_monthly;
    SELECT f.DateKey, f.RegionKey, f.ProductKey, c.CreditScoreBand,
           CASE WHEN f.CurrentLTV IS NULL THEN 'n/a'
                WHEN f.CurrentLTV <= 0.50 THEN '1. <= 50%'
                WHEN f.CurrentLTV <= 0.60 THEN '2. 50-60%'
                WHEN f.CurrentLTV <= 0.75 THEN '3. 60-75%'
                WHEN f.CurrentLTV <= 0.85 THEN '4. 75-85%'
                WHEN f.CurrentLTV <= 0.90 THEN '5. 85-90%'
                ELSE '6. > 90%' END AS LTVBand,
           f.IFRS9Stage, f.ArrearsBucket,
           CAST(COUNT_BIG(*) AS INT)                                   AS Accounts,
           CAST(SUM(f.BalanceEOM) AS DECIMAL(18,2))                    AS Balance,
           CAST(SUM(f.EAD) AS DECIMAL(18,2))                           AS EAD,
           CAST(SUM(f.ECL) AS DECIMAL(18,2))                           AS ECL,
           CAST(SUM(f.WriteOffAmount - f.GuaranteeClaimAmount) AS DECIMAL(18,2)) AS NetWriteOff,
           CAST(SUM(f.PD12m * f.EAD) AS DECIMAL(22,4))                 AS PDxEAD
    INTO mart.fact_credit_risk_monthly
    FROM gold.FactLoanPerformanceMonthly f
    JOIN gold.DimCustomer c ON c.CustomerKey = f.CustomerKey
    WHERE f.AccountStatus = 'Open' OR f.WriteOffAmount > 0
    GROUP BY f.DateKey, f.RegionKey, f.ProductKey, c.CreditScoreBand,
             CASE WHEN f.CurrentLTV IS NULL THEN 'n/a'
                  WHEN f.CurrentLTV <= 0.50 THEN '1. <= 50%'
                  WHEN f.CurrentLTV <= 0.60 THEN '2. 50-60%'
                  WHEN f.CurrentLTV <= 0.75 THEN '3. 60-75%'
                  WHEN f.CurrentLTV <= 0.85 THEN '4. 75-85%'
                  WHEN f.CurrentLTV <= 0.90 THEN '5. 85-90%'
                  ELSE '6. > 90%' END,
             f.IFRS9Stage, f.ArrearsBucket;

    /* ---------------------------------------------------------------------------------
       3. Remortgage wall | fixed-rate mortgages open at the last actual month, by deal end quarter
       --------------------------------------------------------------------------------- */
    DROP TABLE IF EXISTS mart.fact_mortgage_maturity;
    SELECT CONCAT(f.DealEndDateKey / 10000, ' Q', ((f.DealEndDateKey / 100) % 100 + 2) / 3) AS DealEndQuarter,
           f.DealEndDateKey AS DealEndMonthKey, f.RegionKey, f.RateType,
           CASE WHEN f.CustomerRate < 2 THEN '1. < 2%' WHEN f.CustomerRate < 3 THEN '2. 2-3%'
                WHEN f.CustomerRate < 4 THEN '3. 3-4%' WHEN f.CustomerRate < 5 THEN '4. 4-5%'
                ELSE '5. >= 5%' END AS CurrentRateBand,
           CAST(COUNT_BIG(*) AS INT)                          AS Accounts,
           CAST(SUM(f.BalanceEOM) AS DECIMAL(18,2))           AS Balance,
           CAST(SUM(f.CustomerRate * f.BalanceEOM) AS DECIMAL(22,4)) AS RateXBalance,
           CAST(SUM(f.ScheduledPayment) AS DECIMAL(18,2))     AS MonthlyPayment
    INTO mart.fact_mortgage_maturity
    FROM gold.FactLoanPerformanceMonthly f
    JOIN gold.DimProduct p ON p.ProductKey = f.ProductKey AND p.ProductID = 'P04'
    WHERE f.DateKey = @last_key AND f.AccountStatus = 'Open' AND f.DealEndDateKey IS NOT NULL
    GROUP BY CONCAT(f.DealEndDateKey / 10000, ' Q', ((f.DealEndDateKey / 100) % 100 + 2) / 3), f.DealEndDateKey,
             f.RegionKey, f.RateType,
             CASE WHEN f.CustomerRate < 2 THEN '1. < 2%' WHEN f.CustomerRate < 3 THEN '2. 2-3%'
                  WHEN f.CustomerRate < 4 THEN '3. 3-4%' WHEN f.CustomerRate < 5 THEN '4. 4-5%'
                  ELSE '5. >= 5%' END;

    /* ---------------------------------------------------------------------------------
       4. Mortgage repricing events (payment shock) | old vs new rate and payment
       --------------------------------------------------------------------------------- */
    DROP TABLE IF EXISTS mart.fact_mortgage_repricing;
    WITH e AS (
        SELECT f.DateKey, f.AccountKey, f.RegionKey, f.RateType, f.CustomerRate, f.ScheduledPayment, f.BalanceEOM,
               gold.fn_date_key(EOMONTH(d.[Date], -1)) AS PrevKey
        FROM gold.FactLoanPerformanceMonthly f
        JOIN gold.DimProduct p ON p.ProductKey = f.ProductKey AND p.ProductID = 'P04'
        JOIN gold.DimDate d ON d.DateKey = f.DateKey
        WHERE (f.IsProductTransfer = 1 OR f.IsDealMaturity = 1) AND f.AccountStatus = 'Open')
    SELECT e.DateKey, e.RegionKey, e.RateType AS NewRateType,
           CAST(COUNT_BIG(*) AS INT)                                AS Repricings,
           CAST(SUM(e.BalanceEOM) AS DECIMAL(18,2))                 AS Balance,
           CAST(SUM(p.CustomerRate * e.BalanceEOM) AS DECIMAL(22,4)) AS OldRateXBalance,
           CAST(SUM(e.CustomerRate * e.BalanceEOM) AS DECIMAL(22,4)) AS NewRateXBalance,
           CAST(SUM(p.ScheduledPayment) AS DECIMAL(18,2))           AS OldPayment,
           CAST(SUM(e.ScheduledPayment) AS DECIMAL(18,2))           AS NewPayment
    INTO mart.fact_mortgage_repricing
    FROM e
    JOIN gold.FactLoanPerformanceMonthly p ON p.AccountKey = e.AccountKey AND p.DateKey = e.PrevKey
    WHERE p.ScheduledPayment > 0
    GROUP BY e.DateKey, e.RegionKey, e.RateType;

    /* ---------------------------------------------------------------------------------
       5. Bounce Back Loans | cumulative default curve by vintage quarter and months on book
       --------------------------------------------------------------------------------- */
    DROP TABLE IF EXISTS mart.fact_bbl_vintage;
    WITH acc AS (
        SELECT a.AccountKey, a.VintageQuarter, EOMONTH(a.OpenDate) AS OpenMonth, a.OriginalAmount
        FROM gold.DimAccount a JOIN gold.DimProduct p ON p.ProductKey = a.ProductKey AND p.ProductID = 'P09'),
    def AS (
        SELECT f.AccountKey, MIN(d.[Date]) AS DefaultMonth
        FROM gold.FactLoanPerformanceMonthly f
        JOIN gold.DimProduct p ON p.ProductKey = f.ProductKey AND p.ProductID = 'P09'
        JOIN gold.DimDate d ON d.DateKey = f.DateKey
        WHERE f.ArrearsBucket = '90+' OR f.AccountStatus = 'Written Off'
        GROUP BY f.AccountKey),
    n AS (SELECT TOP (80) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS MonthsOnBook FROM sys.all_objects)
    SELECT acc.VintageQuarter, n.MonthsOnBook,
           CAST(COUNT_BIG(*) AS INT) AS Loans,
           CAST(SUM(acc.OriginalAmount) AS DECIMAL(18,2)) AS OriginalAmount,
           CAST(SUM(CASE WHEN def.DefaultMonth <= EOMONTH(acc.OpenMonth, n.MonthsOnBook) THEN 1 ELSE 0 END) AS INT) AS DefaultedLoans,
           CAST(SUM(CASE WHEN def.DefaultMonth <= EOMONTH(acc.OpenMonth, n.MonthsOnBook) THEN acc.OriginalAmount ELSE 0 END) AS DECIMAL(18,2)) AS DefaultedAmount
    INTO mart.fact_bbl_vintage
    FROM acc
    CROSS JOIN n
    LEFT JOIN def ON def.AccountKey = acc.AccountKey
    WHERE EOMONTH(acc.OpenMonth, n.MonthsOnBook) <= @last_actual
    GROUP BY acc.VintageQuarter, n.MonthsOnBook;

    /* ---------------------------------------------------------------------------------
       6. Customers and digital | month x region x segment x sub-segment x brand x age band
       --------------------------------------------------------------------------------- */
    DROP TABLE IF EXISTS mart.fact_customer_monthly;
    WITH m AS (
        SELECT DateKey, [Date], MonthStart FROM gold.DimDate
        WHERE IsMonthEnd = 1 AND [Date] BETWEEN '2020-01-31' AND @last_actual),
    base AS (
        SELECT m.DateKey, c.RegionKey, c.Segment, c.SubSegment, c.Brand, COALESCE(c.AgeBand, 'SME') AS AgeBand,
               SUM(CASE WHEN (c.OnboardingDate IS NULL OR c.OnboardingDate <= m.[Date])
                         AND (c.ChurnDate IS NULL OR c.ChurnDate > m.[Date]) THEN 1 ELSE 0 END) AS ActiveCustomers,
               SUM(CASE WHEN c.OnboardingDate BETWEEN m.MonthStart AND m.[Date] THEN 1 ELSE 0 END) AS NewCustomers,
               SUM(CASE WHEN c.ChurnDate BETWEEN m.MonthStart AND m.[Date] THEN 1 ELSE 0 END) AS ChurnedCustomers
        FROM gold.DimCustomer c CROSS JOIN m
        GROUP BY m.DateKey, c.RegionKey, c.Segment, c.SubSegment, c.Brand, COALESCE(c.AgeBand, 'SME')),
    dig AS (
        SELECT f.DateKey, f.RegionKey, c.Segment, c.SubSegment, c.Brand, COALESCE(c.AgeBand, 'SME') AS AgeBand,
               COUNT_BIG(*) AS DigitalRegistered,
               SUM(CAST(f.IsMonthlyActive AS INT)) AS MonthlyActiveUsers,
               SUM(CAST(f.AppSessions AS BIGINT)) AS AppSessions,
               SUM(CAST(f.WebLogins AS BIGINT)) AS WebLogins,
               SUM(CAST(f.FeaturesUsed AS BIGINT)) AS FeaturesUsed
        FROM gold.FactDigitalMonthly f
        JOIN gold.DimCustomer c ON c.CustomerKey = f.CustomerKey
        GROUP BY f.DateKey, f.RegionKey, c.Segment, c.SubSegment, c.Brand, COALESCE(c.AgeBand, 'SME'))
    SELECT b.DateKey, b.RegionKey, b.Segment, b.SubSegment, b.Brand, b.AgeBand,
           CAST(b.ActiveCustomers AS INT)  AS ActiveCustomers,
           CAST(b.NewCustomers AS INT)     AS NewCustomers,
           CAST(b.ChurnedCustomers AS INT) AS ChurnedCustomers,
           CAST(COALESCE(d.DigitalRegistered, 0) AS INT)  AS DigitalRegistered,
           CAST(COALESCE(d.MonthlyActiveUsers, 0) AS INT) AS MonthlyActiveUsers,
           COALESCE(d.AppSessions, 0)  AS AppSessions,
           COALESCE(d.WebLogins, 0)    AS WebLogins,
           COALESCE(d.FeaturesUsed, 0) AS FeaturesUsed
    INTO mart.fact_customer_monthly
    FROM base b
    LEFT JOIN dig d ON d.DateKey = b.DateKey AND d.RegionKey = b.RegionKey AND d.Segment = b.Segment
                   AND d.SubSegment = b.SubSegment AND d.Brand = b.Brand AND d.AgeBand = b.AgeBand;

    /* ---------------------------------------------------------------------------------
       7. Transactions by channel | month x region x product x channel x type
       --------------------------------------------------------------------------------- */
    DROP TABLE IF EXISTS mart.fact_transactions_monthly;
    SELECT gold.fn_date_key(d.MonthEnd) AS DateKey, f.RegionKey, f.ProductKey, f.ChannelKey, f.TxnType,
           CAST(SUM(CAST(f.TxnCount AS BIGINT)) AS BIGINT) AS TxnCount,
           CAST(SUM(f.TxnValue) AS DECIMAL(18,2))           AS TxnValue
    INTO mart.fact_transactions_monthly
    FROM gold.FactTransactionDaily f
    JOIN gold.DimDate d ON d.DateKey = f.DateKey
    GROUP BY gold.fn_date_key(d.MonthEnd), f.RegionKey, f.ProductKey, f.ChannelKey, f.TxnType;

    /* summary of what was built */
    SELECT 'fact_product_monthly' AS mart_table, COUNT_BIG(*) AS row_count FROM mart.fact_product_monthly
    UNION ALL SELECT 'fact_credit_risk_monthly', COUNT_BIG(*) FROM mart.fact_credit_risk_monthly
    UNION ALL SELECT 'fact_mortgage_maturity', COUNT_BIG(*) FROM mart.fact_mortgage_maturity
    UNION ALL SELECT 'fact_mortgage_repricing', COUNT_BIG(*) FROM mart.fact_mortgage_repricing
    UNION ALL SELECT 'fact_bbl_vintage', COUNT_BIG(*) FROM mart.fact_bbl_vintage
    UNION ALL SELECT 'fact_customer_monthly', COUNT_BIG(*) FROM mart.fact_customer_monthly
    UNION ALL SELECT 'fact_transactions_monthly', COUNT_BIG(*) FROM mart.fact_transactions_monthly;
END;
GO
SELECT SCHEMA_NAME(schema_id) + '.' + name AS mart_object, type_desc
FROM sys.objects WHERE SCHEMA_NAME(schema_id) = 'mart' AND type IN ('V', 'P') ORDER BY type_desc, name;
GO
SET NOEXEC OFF;
