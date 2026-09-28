/* =====================================================================================
   Lloyds Banking Group | Portfolio project (HYPOTHETICAL DATA)
   03 | Gold layer | Kimball star schema
   - Integer surrogate keys (smaller facts, faster joins, Power BI friendly)
   - Clustered COLUMNSTORE on the large facts (~10x compression, fast aggregation)
   - DateKey = yyyymmdd integer
   ===================================================================================== */
SET NOCOUNT ON;
GO
IF DB_NAME() <> 'sqldb-lloyds'
BEGIN
    RAISERROR('WRONG DATABASE: select sqldb-lloyds in the database drop-down and run again.', 16, 1);
    SET NOEXEC ON;
END
GO
DROP TABLE IF EXISTS gold.FactDepositBalanceMonthly, gold.FactLoanPerformanceMonthly, gold.FactDigitalMonthly,
    gold.FactTransactionDaily, gold.FactBranchMonthly, gold.FactComplaint, gold.FactFraudCase,
    gold.FactBudgetMonthly, gold.FactOpexMonthly, gold.FactBankRateDaily;
DROP TABLE IF EXISTS gold.DimAccount, gold.DimCustomer, gold.DimBranch, gold.DimComplaintCategory,
    gold.DimChannel, gold.DimProduct, gold.DimRegion, gold.DimDate;
GO
/* =============================== DIMENSIONS ======================================= */
CREATE TABLE gold.DimDate (
    DateKey          INT          NOT NULL CONSTRAINT PK_DimDate PRIMARY KEY,
    [Date]           DATE         NOT NULL,
    [Year]           SMALLINT     NOT NULL,
    [Quarter]        TINYINT      NOT NULL,
    QuarterLabel     CHAR(7)      NOT NULL,   -- 2024 Q1
    [Month]          TINYINT      NOT NULL,
    MonthName        VARCHAR(10)  NOT NULL,
    MonthShort       CHAR(3)      NOT NULL,
    YearMonth        CHAR(7)      NOT NULL,   -- 2024-01
    MonthStart       DATE         NOT NULL,
    MonthEnd         DATE         NOT NULL,
    IsMonthEnd       BIT          NOT NULL,
    DayOfMonth       TINYINT      NOT NULL,
    DayOfWeekNum     TINYINT      NOT NULL,   -- 1 = Monday
    DayName          VARCHAR(10)  NOT NULL,
    IsWeekend        BIT          NOT NULL,
    IsUKBankHoliday  BIT          NOT NULL,
    IsWorkingDay     BIT          NOT NULL,
    IsActualPeriod   BIT          NOT NULL    -- <= last actual month end (31 Aug 2026)
);
CREATE TABLE gold.DimRegion (
    RegionKey        SMALLINT IDENTITY(1,1) CONSTRAINT PK_DimRegion PRIMARY KEY,
    RegionCode       VARCHAR(10)  NOT NULL CONSTRAINT UQ_DimRegion UNIQUE,
    RegionName       VARCHAR(60)  NOT NULL,
    Nation           VARCHAR(30)  NOT NULL,
    RegionalDirector VARCHAR(80)  NULL,
    DirectorEmail    VARCHAR(120) NULL      -- used by Power BI Row-Level Security
);
CREATE TABLE gold.DimProduct (
    ProductKey       SMALLINT IDENTITY(1,1) CONSTRAINT PK_DimProduct PRIMARY KEY,
    ProductID        VARCHAR(10)  NOT NULL CONSTRAINT UQ_DimProduct UNIQUE,
    ProductName      VARCHAR(60)  NOT NULL,
    ProductGroup     VARCHAR(20)  NOT NULL,  -- Deposits / Lending
    Segment          VARCHAR(20)  NOT NULL,  -- Personal / SME
    IsSecured        BIT          NOT NULL,
    IsGovernmentGuaranteed BIT    NOT NULL,
    SortOrder        TINYINT      NOT NULL
);
CREATE TABLE gold.DimChannel (
    ChannelKey       SMALLINT IDENTITY(1,1) CONSTRAINT PK_DimChannel PRIMARY KEY,
    ChannelCode      VARCHAR(10)  NOT NULL CONSTRAINT UQ_DimChannel UNIQUE,
    ChannelName      VARCHAR(60)  NOT NULL,
    ChannelGroup     VARCHAR(20)  NOT NULL   -- Digital / Physical / Automated
);
CREATE TABLE gold.DimComplaintCategory (
    CategoryKey      SMALLINT IDENTITY(1,1) CONSTRAINT PK_DimComplaintCategory PRIMARY KEY,
    CategoryCode     VARCHAR(10)  NOT NULL CONSTRAINT UQ_DimComplaintCategory UNIQUE,
    CategoryName     VARCHAR(60)  NOT NULL,
    FCAProductGroup  VARCHAR(60)  NOT NULL
);
CREATE TABLE gold.DimBranch (
    BranchKey        INT IDENTITY(1,1) CONSTRAINT PK_DimBranch PRIMARY KEY,
    BranchID         VARCHAR(10)  NOT NULL CONSTRAINT UQ_DimBranch UNIQUE,
    BranchName       NVARCHAR(100) NOT NULL,
    Brand            VARCHAR(30)  NOT NULL,
    RegionKey        SMALLINT     NOT NULL,
    City             NVARCHAR(60) NOT NULL,
    Latitude         DECIMAL(9,5) NULL,
    Longitude        DECIMAL(9,5) NULL,
    BranchFormat     VARCHAR(20)  NOT NULL,
    OpenDate         DATE         NULL,
    ClosureDate      DATE         NULL,
    BranchStatus     VARCHAR(10)  NOT NULL   -- Open / Closed (as of last actual date)
);
CREATE TABLE gold.DimCustomer (
    CustomerKey      INT IDENTITY(1,1) CONSTRAINT PK_DimCustomer PRIMARY KEY,
    CustomerID       VARCHAR(12)  NOT NULL CONSTRAINT UQ_DimCustomer UNIQUE,
    Segment          VARCHAR(10)  NOT NULL,
    SubSegment       VARCHAR(12)  NOT NULL,
    Brand            VARCHAR(30)  NOT NULL,
    RegionKey        SMALLINT     NOT NULL,
    City             NVARCHAR(60) NULL,
    PostcodeSector   VARCHAR(10)  NULL,
    PostcodeArea     VARCHAR(4)   NULL,
    AgeBand          VARCHAR(10)  NULL,
    IncomeBand       VARCHAR(10)  NULL,
    Industry         VARCHAR(40)  NULL,
    TurnoverBand     VARCHAR(15)  NULL,
    CreditScoreBand  VARCHAR(12)  NOT NULL,
    OnboardingDate   DATE         NULL,
    OnboardingYear   SMALLINT     NULL,
    OnboardingChannel VARCHAR(20) NULL,
    DigitalRegistrationDate DATE  NULL,
    IsDigitallyRegistered BIT     NOT NULL,
    HomeBranchKey    INT          NULL,
    ChurnDate        DATE         NULL,
    CustomerStatus   VARCHAR(10)  NOT NULL,
    TenureBand       VARCHAR(12)  NULL,
    DQFlag           VARCHAR(100) NULL       -- data quality fixes applied in silver
);
CREATE TABLE gold.DimAccount (
    AccountKey       INT IDENTITY(1,1) CONSTRAINT PK_DimAccount PRIMARY KEY,
    AccountID        VARCHAR(12)  NOT NULL CONSTRAINT UQ_DimAccount UNIQUE,
    CustomerKey      INT          NOT NULL,
    ProductKey       SMALLINT     NOT NULL,
    BranchKey        INT          NULL,
    OpenDate         DATE         NULL,
    CloseDate        DATE         NULL,
    AccountStatus    VARCHAR(15)  NOT NULL,
    OriginalAmount   DECIMAL(18,2) NULL,
    TermMonths       SMALLINT     NULL,
    OriginationRate  DECIMAL(7,4) NULL,
    OriginationLTV   DECIMAL(7,4) NULL,
    OriginationLTVBand VARCHAR(10) NULL,
    VintageYear      SMALLINT     NULL,
    VintageQuarter   CHAR(7)      NULL
);
GO
/* ================================== FACTS ========================================= */
CREATE TABLE gold.FactDepositBalanceMonthly (
    DateKey          INT           NOT NULL,
    AccountKey       INT           NOT NULL,
    CustomerKey      INT           NOT NULL,
    ProductKey       SMALLINT      NOT NULL,
    RegionKey        SMALLINT      NOT NULL,
    AvgBalance       DECIMAL(18,2) NOT NULL,
    EOMBalance       DECIMAL(18,2) NOT NULL,
    CustomerRate     DECIMAL(7,4)  NOT NULL,
    FTPRate          DECIMAL(9,4)  NOT NULL,
    InterestExpense  DECIMAL(18,2) NOT NULL,
    FTPCredit        DECIMAL(18,2) NOT NULL,
    FeeIncome        DECIMAL(18,2) NOT NULL,
    INDEX CCI_FactDepositBalanceMonthly CLUSTERED COLUMNSTORE
);
CREATE TABLE gold.FactLoanPerformanceMonthly (
    DateKey          INT           NOT NULL,
    AccountKey       INT           NOT NULL,
    CustomerKey      INT           NOT NULL,
    ProductKey       SMALLINT      NOT NULL,
    RegionKey        SMALLINT      NOT NULL,
    RateType         VARCHAR(10)   NOT NULL,
    BalanceEOM       DECIMAL(18,2) NOT NULL,
    CreditLimit      DECIMAL(18,2) NULL,
    CustomerRate     DECIMAL(7,4)  NOT NULL,
    FTPRate          DECIMAL(9,4)  NOT NULL,
    InterestIncome   DECIMAL(18,2) NOT NULL,
    FTPCharge        DECIMAL(18,2) NOT NULL,
    FeeIncome        DECIMAL(18,2) NOT NULL,
    ScheduledPayment DECIMAL(18,2) NOT NULL,
    DaysPastDue      SMALLINT      NOT NULL,
    ArrearsBucket    VARCHAR(8)    NOT NULL,
    IFRS9Stage       TINYINT       NOT NULL,
    PD12m            DECIMAL(9,6)  NOT NULL,
    LGD              DECIMAL(9,6)  NOT NULL,
    EAD              DECIMAL(18,2) NOT NULL,
    ECL              DECIMAL(18,2) NOT NULL,
    WriteOffAmount   DECIMAL(18,2) NOT NULL,
    GuaranteeClaimAmount DECIMAL(18,2) NOT NULL,
    IsPaymentHoliday BIT           NOT NULL,
    DealEndDateKey   INT           NULL,
    IsDealMaturity   BIT           NOT NULL,
    IsProductTransfer BIT          NOT NULL,
    CurrentLTV       DECIMAL(9,4)  NULL,
    NewLendingAmount DECIMAL(18,2) NOT NULL,
    AccountStatus    VARCHAR(12)   NOT NULL,
    INDEX CCI_FactLoanPerformanceMonthly CLUSTERED COLUMNSTORE
);
CREATE TABLE gold.FactDigitalMonthly (
    DateKey          INT       NOT NULL,
    CustomerKey      INT       NOT NULL,
    RegionKey        SMALLINT  NOT NULL,
    WebLogins        SMALLINT  NOT NULL,
    AppSessions      SMALLINT  NOT NULL,
    IsMonthlyActive  BIT       NOT NULL,
    FeaturesUsed     TINYINT   NOT NULL,
    INDEX CCI_FactDigitalMonthly CLUSTERED COLUMNSTORE
);
CREATE TABLE gold.FactTransactionDaily (
    DateKey          INT           NOT NULL,
    RegionKey        SMALLINT      NOT NULL,
    ProductKey       SMALLINT      NOT NULL,
    ChannelKey       SMALLINT      NOT NULL,
    TxnType          VARCHAR(30)   NOT NULL,
    TxnCount         INT           NOT NULL,
    TxnValue         DECIMAL(18,2) NOT NULL,
    INDEX CCI_FactTransactionDaily CLUSTERED COLUMNSTORE
);
CREATE TABLE gold.FactBranchMonthly (
    DateKey          INT          NOT NULL,
    BranchKey        INT          NOT NULL,
    RegionKey        SMALLINT     NOT NULL,
    Footfall         INT          NOT NULL,
    CounterTxnCount  INT          NOT NULL,
    StaffFTE         DECIMAL(5,1) NOT NULL,
    IsClosureMonth   BIT          NOT NULL,
    CONSTRAINT PK_FactBranchMonthly PRIMARY KEY (DateKey, BranchKey)
);
CREATE TABLE gold.FactComplaint (
    ComplaintID      VARCHAR(20)   NOT NULL CONSTRAINT PK_FactComplaint PRIMARY KEY,
    CustomerKey      INT           NOT NULL,
    RegionKey        SMALLINT      NOT NULL,
    CategoryKey      SMALLINT      NOT NULL,
    ReceivedDateKey  INT           NOT NULL,
    ResolvedDateKey  INT           NULL,
    RootCause        VARCHAR(40)   NOT NULL,
    Channel          VARCHAR(20)   NOT NULL,
    IsUpheld         BIT           NOT NULL,
    RedressAmount    DECIMAL(18,2) NOT NULL,
    IsReferredToFOS  BIT           NOT NULL,
    DaysToResolve    INT           NULL,
    IsResolvedWithin8Weeks BIT     NULL,     -- NULL while the complaint is still open
    IsOpen           BIT           NOT NULL,
    DQFlag           VARCHAR(60)   NULL
);
CREATE TABLE gold.FactFraudCase (
    CaseID           VARCHAR(20)   NOT NULL CONSTRAINT PK_FactFraudCase PRIMARY KEY,
    CustomerKey      INT           NOT NULL,
    RegionKey        SMALLINT      NOT NULL,
    ReportedDateKey  INT           NOT NULL,
    FraudType        VARCHAR(30)   NOT NULL,
    Channel          VARCHAR(20)   NOT NULL,
    LossAmount       DECIMAL(18,2) NOT NULL,
    ReimbursedAmount DECIMAL(18,2) NOT NULL,
    RecoveredAmount  DECIMAL(18,2) NOT NULL,
    CaseStatus       VARCHAR(25)   NOT NULL,
    IsPostPSRRule    BIT           NOT NULL  -- reported on/after 7 Oct 2024 (mandatory APP reimbursement)
);
CREATE TABLE gold.FactBudgetMonthly (
    DateKey          INT           NOT NULL,
    RegionKey        SMALLINT      NOT NULL,
    ProductKey       SMALLINT      NOT NULL,
    BudgetBalance    DECIMAL(18,2) NOT NULL,
    BudgetNII        DECIMAL(18,2) NOT NULL,
    BudgetFees       DECIMAL(18,2) NOT NULL,
    BudgetImpairment DECIMAL(18,2) NOT NULL,
    CONSTRAINT PK_FactBudgetMonthly PRIMARY KEY (DateKey, RegionKey, ProductKey)
);
CREATE TABLE gold.FactOpexMonthly (
    DateKey          INT           NOT NULL,
    RegionKey        SMALLINT      NOT NULL,
    CostCategory     VARCHAR(20)   NOT NULL,
    ActualAmount     DECIMAL(18,2) NULL,     -- NULL for forecast months (Sep-Dec 2026)
    BudgetAmount     DECIMAL(18,2) NOT NULL,
    CONSTRAINT PK_FactOpexMonthly PRIMARY KEY (DateKey, RegionKey, CostCategory)
);
CREATE TABLE gold.FactBankRateDaily (
    DateKey          INT          NOT NULL CONSTRAINT PK_FactBankRateDaily PRIMARY KEY,
    BankRate         DECIMAL(5,2) NOT NULL,
    SourceSystem     VARCHAR(20)  NOT NULL   -- BoE API / Fallback
);
GO
SELECT SCHEMA_NAME(t.schema_id) + '.' + t.name AS gold_table,
       CASE WHEN EXISTS (SELECT 1 FROM sys.indexes i WHERE i.object_id = t.object_id AND i.type = 5)
            THEN 'Clustered Columnstore' ELSE 'Rowstore' END AS storage
FROM sys.tables t WHERE SCHEMA_NAME(t.schema_id) = 'gold' ORDER BY t.name;
GO
SET NOEXEC OFF;
