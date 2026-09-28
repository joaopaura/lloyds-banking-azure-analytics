/* =====================================================================================
   Lloyds Banking Group | Portfolio project (HYPOTHETICAL DATA)
   01 | Schemas, security (least privilege) and operational tables
   Target: Azure SQL Database  sqldb-lloyds  (server sql-lloyds-joaopaura, Sweden Central)
   Run as: lloydsadmin, connected to database sqldb-lloyds
   -------------------------------------------------------------------------------------
   Layers
     stg    raw copy of each Parquet file (transient, truncated before every load)
     silver cleansed / conformed reference data and dimensions (DQ rules applied)
     gold   Kimball star schema (dimensions + facts, columnstore on large facts)
     mart   aggregated tables/views consumed by Power BI
     ops    pipeline log, watermarks, data quality results
   ===================================================================================== */
SET NOCOUNT ON;
GO
/* Safety check: stop if the query window is connected to master instead of sqldb-lloyds */
IF DB_NAME() <> 'sqldb-lloyds'
BEGIN
    RAISERROR('WRONG DATABASE: select sqldb-lloyds in the database drop-down and run again.', 16, 1);
    SET NOEXEC ON;
END
GO
IF SCHEMA_ID('stg')    IS NULL EXEC('CREATE SCHEMA stg');
IF SCHEMA_ID('silver') IS NULL EXEC('CREATE SCHEMA silver');
IF SCHEMA_ID('gold')   IS NULL EXEC('CREATE SCHEMA gold');
IF SCHEMA_ID('mart')   IS NULL EXEC('CREATE SCHEMA mart');
IF SCHEMA_ID('ops')    IS NULL EXEC('CREATE SCHEMA ops');
GO

/* -------------------------------------------------------------------------------------
   Operational tables
   ------------------------------------------------------------------------------------- */
IF OBJECT_ID('ops.pipeline_run_log') IS NULL
CREATE TABLE ops.pipeline_run_log (
    log_id            BIGINT IDENTITY(1,1) CONSTRAINT PK_pipeline_run_log PRIMARY KEY,
    pipeline_run_id   VARCHAR(64)    NULL,      -- ADF @pipeline().RunId
    pipeline_name     VARCHAR(128)   NOT NULL,
    activity_name     VARCHAR(128)   NULL,
    source_table      VARCHAR(128)   NULL,
    source_file       NVARCHAR(400)  NULL,
    period_month_end  DATE           NULL,
    rows_read         BIGINT         NULL,
    rows_written      BIGINT         NULL,
    status            VARCHAR(20)    NOT NULL,  -- Started / Succeeded / Failed
    message           NVARCHAR(4000) NULL,
    started_at_utc    DATETIME2(0)   NOT NULL CONSTRAINT DF_prl_start DEFAULT SYSUTCDATETIME(),
    ended_at_utc      DATETIME2(0)   NULL
);
GO
IF OBJECT_ID('ops.watermark') IS NULL
CREATE TABLE ops.watermark (
    table_name            VARCHAR(128) NOT NULL CONSTRAINT PK_watermark PRIMARY KEY,
    last_loaded_month_end DATE         NULL,     -- last period successfully loaded into gold
    last_source_file      NVARCHAR(400) NULL,
    updated_at_utc        DATETIME2(0) NOT NULL CONSTRAINT DF_wm_upd DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID('ops.dq_results') IS NULL
CREATE TABLE ops.dq_results (
    dq_id           BIGINT IDENTITY(1,1) CONSTRAINT PK_dq_results PRIMARY KEY,
    checked_at_utc  DATETIME2(0)  NOT NULL CONSTRAINT DF_dq_ts DEFAULT SYSUTCDATETIME(),
    layer           VARCHAR(10)   NOT NULL,     -- silver / gold
    table_name      VARCHAR(128)  NOT NULL,
    period_month_end DATE         NULL,
    check_name      VARCHAR(128)  NOT NULL,
    severity        VARCHAR(10)   NOT NULL,     -- Info / Warning / Error
    affected_rows   BIGINT        NOT NULL,
    total_rows      BIGINT        NULL,
    action_taken    NVARCHAR(400) NULL
);
GO

/* Watermarks for the monthly (incremental) tables */
MERGE ops.watermark AS t
USING (VALUES ('deposit_balance_monthly'), ('loan_performance_monthly'), ('digital_activity_monthly'),
              ('transactions_daily'), ('branch_activity_monthly'), ('complaints'), ('fraud_cases')) AS s(table_name)
ON t.table_name = s.table_name
WHEN NOT MATCHED THEN INSERT (table_name) VALUES (s.table_name);
GO

/* -------------------------------------------------------------------------------------
   Security | contained database users (least privilege)
   etl_loader : used by Azure Data Factory (write stg/silver/gold/mart/ops, run procs)
   pbi_reader : used by Power BI (read-only on mart + gold dimensions)
   >>> Replace the two passwords before running (min 8 chars, upper, lower, digit, symbol) <<<
   ------------------------------------------------------------------------------------- */
IF DATABASE_PRINCIPAL_ID('etl_loader') IS NULL
    CREATE USER etl_loader WITH PASSWORD = 'CHANGE_ME_Etl#2026';
IF DATABASE_PRINCIPAL_ID('pbi_reader') IS NULL
    CREATE USER pbi_reader WITH PASSWORD = 'CHANGE_ME_Pbi#2026';
GO
GRANT SELECT, INSERT, UPDATE, DELETE, ALTER, EXECUTE ON SCHEMA::stg    TO etl_loader;
GRANT SELECT, INSERT, UPDATE, DELETE, ALTER, EXECUTE ON SCHEMA::silver TO etl_loader;
GRANT SELECT, INSERT, UPDATE, DELETE, ALTER, EXECUTE ON SCHEMA::gold   TO etl_loader;
GRANT SELECT, INSERT, UPDATE, DELETE, ALTER, EXECUTE ON SCHEMA::mart   TO etl_loader;
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE        ON SCHEMA::ops    TO etl_loader;
GRANT SELECT ON SCHEMA::mart TO pbi_reader;
GRANT SELECT ON SCHEMA::gold TO pbi_reader;
GO

SELECT s.name AS schema_name FROM sys.schemas s WHERE s.name IN ('stg','silver','gold','mart','ops') ORDER BY 1;
SELECT name AS user_name, type_desc, authentication_type_desc FROM sys.database_principals
WHERE name IN ('etl_loader','pbi_reader');
GO
SET NOEXEC OFF;
