/* =====================================================================================
   Lloyds Banking Group | Portfolio project (HYPOTHETICAL DATA)
   04 | Metadata-driven load configuration + logging procedures (used by Azure Data Factory)
   ===================================================================================== */
SET NOCOUNT ON;
GO
IF DB_NAME() <> 'sqldb-lloyds'
BEGIN
    RAISERROR('WRONG DATABASE: select sqldb-lloyds in the database drop-down and run again.', 16, 1);
    SET NOEXEC ON;
END
GO
/* -------------------------------------------------------------------------------------
   ops.load_config | one row per source table. ADF reads this table (Lookup activity)
   and loops over it (ForEach), so adding a new source = inserting one row, no pipeline change.
   load_group: 1 reference | 2 master data | 3 monthly facts | 4 finance
   ------------------------------------------------------------------------------------- */
DROP TABLE IF EXISTS ops.load_config;
CREATE TABLE ops.load_config (
    config_id      INT IDENTITY(1,1) CONSTRAINT PK_load_config PRIMARY KEY,
    table_name     VARCHAR(128)  NOT NULL CONSTRAINT UQ_load_config UNIQUE,
    source_folder  VARCHAR(256)  NOT NULL,     -- folder inside container 'landing'
    stg_table      VARCHAR(128)  NOT NULL,     -- target staging table (schema.table)
    target_proc    VARCHAR(128)  NULL,         -- proc that moves stg -> gold (facts)
    load_type      VARCHAR(12)   NOT NULL,     -- FULL / INCREMENTAL
    load_group     TINYINT       NOT NULL,
    load_order     TINYINT       NOT NULL,
    is_active      BIT           NOT NULL CONSTRAINT DF_lc_active DEFAULT 1
);
INSERT ops.load_config (table_name, source_folder, stg_table, target_proc, load_type, load_group, load_order) VALUES
 ('regions',                  'reference/regions',                    'stg.regions',                  NULL, 'FULL', 1, 1),
 ('products',                 'reference/products',                   'stg.products',                 NULL, 'FULL', 1, 2),
 ('channels',                 'reference/channels',                   'stg.channels',                 NULL, 'FULL', 1, 3),
 ('complaint_categories',     'reference/complaint_categories',       'stg.complaint_categories',     NULL, 'FULL', 1, 4),
 ('uk_bank_holidays',         'reference/uk_bank_holidays',           'stg.uk_bank_holidays',         NULL, 'FULL', 1, 5),
 ('branches',                 'network/branches',                     'stg.branches',                 NULL, 'FULL', 2, 1),
 ('customers',                'corebanking/customers',                'stg.customers',                NULL, 'FULL', 2, 2),
 ('accounts',                 'corebanking/accounts',                 'stg.accounts',                 NULL, 'FULL', 2, 3),
 ('deposit_balance_monthly',  'corebanking/deposit_balance_monthly',  'stg.deposit_balance_monthly',  'gold.usp_load_fact_deposit_balance',  'INCREMENTAL', 3, 1),
 ('loan_performance_monthly', 'lending/loan_performance_monthly',     'stg.loan_performance_monthly', 'gold.usp_load_fact_loan_performance', 'INCREMENTAL', 3, 2),
 ('digital_activity_monthly', 'digital/digital_activity_monthly',     'stg.digital_activity_monthly', 'gold.usp_load_fact_digital',          'INCREMENTAL', 3, 3),
 ('transactions_daily',       'payments/transactions_daily',          'stg.transactions_daily',       'gold.usp_load_fact_transactions',     'INCREMENTAL', 3, 4),
 ('branch_activity_monthly',  'network/branch_activity_monthly',      'stg.branch_activity_monthly',  'gold.usp_load_fact_branch_activity',  'INCREMENTAL', 3, 5),
 ('complaints',               'conduct/complaints',                   'stg.complaints',               'gold.usp_load_fact_complaints',       'INCREMENTAL', 3, 6),
 ('fraud_cases',              'conduct/fraud_cases',                  'stg.fraud_cases',              'gold.usp_load_fact_fraud',            'INCREMENTAL', 3, 7),
 ('budget_monthly',           'finance/budget_monthly',               'stg.budget_monthly',           NULL, 'FULL', 4, 1),
 ('opex_monthly',             'finance/opex_monthly',                 'stg.opex_monthly',             NULL, 'FULL', 4, 2);
GO
/* -------------------------------------------------------------------------------------
   ops.usp_get_load_plan | returns what ADF must copy for a load group
   @load_mode = FULL        -> whole table folder (backfill, all months)
   @load_mode = INCREMENTAL -> only the month after the watermark (year=YYYY/month=MM)
   ------------------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE ops.usp_get_load_plan
    @load_group TINYINT,
    @load_mode  VARCHAR(12) = 'FULL'
AS
BEGIN
    SET NOCOUNT ON;
    SELECT c.table_name, c.stg_table, c.target_proc, c.load_type,
           CASE WHEN @load_mode = 'INCREMENTAL' AND c.load_type = 'INCREMENTAL'
                THEN CONCAT(c.source_folder, '/year=', YEAR(n.next_month_end),
                            '/month=', RIGHT(CONCAT('0', MONTH(n.next_month_end)), 2))
                ELSE c.source_folder END                  AS copy_folder,
           CONVERT(VARCHAR(10), n.next_month_end, 23)     AS next_month_end
    FROM ops.load_config c
    LEFT JOIN ops.watermark w ON w.table_name = c.table_name
    OUTER APPLY (SELECT EOMONTH(DATEADD(MONTH, 1, COALESCE(w.last_loaded_month_end, '2019-12-31'))) AS next_month_end) n
    WHERE c.load_group = @load_group AND c.is_active = 1
    ORDER BY c.load_order;
END;
GO
/* -------------------------------------------------------------------------------------
   ops.usp_log_copy | called by ADF after each Copy activity (success or failure)
   ------------------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE ops.usp_log_copy
    @pipeline_run_id VARCHAR(64),
    @pipeline_name   VARCHAR(128),
    @source_table    VARCHAR(128),
    @source_folder   NVARCHAR(400),
    @rows_read       BIGINT = NULL,
    @rows_written    BIGINT = NULL,
    @status          VARCHAR(20),
    @message         NVARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT ops.pipeline_run_log (pipeline_run_id, pipeline_name, activity_name, source_table, source_file,
                                 rows_read, rows_written, status, message, ended_at_utc)
    VALUES (@pipeline_run_id, @pipeline_name, 'Copy to staging', @source_table, @source_folder,
            @rows_read, @rows_written, @status, LEFT(@message, 4000), SYSUTCDATETIME());
END;
GO
/* helper used by the load procedures */
CREATE OR ALTER PROCEDURE ops.usp_log_dq
    @layer VARCHAR(10), @table_name VARCHAR(128), @period DATE, @check_name VARCHAR(128),
    @severity VARCHAR(10), @affected BIGINT, @total BIGINT, @action NVARCHAR(400)
AS
BEGIN
    SET NOCOUNT ON;
    IF @affected > 0
        INSERT ops.dq_results (layer, table_name, period_month_end, check_name, severity, affected_rows, total_rows, action_taken)
        VALUES (@layer, @table_name, @period, @check_name, @severity, @affected, @total, @action);
END;
GO
GRANT EXECUTE ON SCHEMA::ops TO etl_loader;
GO
EXEC ops.usp_get_load_plan @load_group = 3, @load_mode = 'FULL';
EXEC ops.usp_get_load_plan @load_group = 3, @load_mode = 'INCREMENTAL';
GO
SET NOEXEC OFF;
