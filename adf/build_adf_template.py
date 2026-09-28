"""
Builds adf_lloyds_template.json | ARM template for the Lloyds Data Factory
(factory + managed identity access to the lake + linked services + datasets + pipelines + trigger).
Run:  python build_adf_template.py
"""
import json
from pathlib import Path

API = "2018-06-01"
FACTORY = "[parameters('factoryName')]"
FID = "[resourceId('Microsoft.DataFactory/factories', parameters('factoryName'))]"


def child(kind, name):
    return f"[concat(parameters('factoryName'), '/{name}')]"


def dep(kind, name):
    return f"[resourceId('Microsoft.DataFactory/factories/{kind}', parameters('factoryName'), '{name}')]"


def expr(v):
    return {"value": v, "type": "Expression"}


def ls_ref(name):
    return {"referenceName": name, "type": "LinkedServiceReference"}


def ds_ref(name, params=None):
    r = {"referenceName": name, "type": "DatasetReference"}
    if params:
        r["parameters"] = params
    return r


def sp_param(value, typ="String"):
    return {"value": value, "type": typ}


POLICY = {"timeout": "0.12:00:00", "retry": 1, "retryIntervalInSeconds": 120,
          "secureOutput": False, "secureInput": False}
SP_POLICY = {"timeout": "0.12:00:00", "retry": 0, "retryIntervalInSeconds": 30,
             "secureOutput": False, "secureInput": False}

# ------------------------------------------------------------------ linked services
linked_services = {
    "LS_ADLS_Landing": {
        "type": "AzureBlobFS",
        "description": "Data lake (ADLS Gen2). Authenticated with the factory managed identity (no keys stored).",
        "typeProperties": {"url": "[concat('https://', parameters('storageAccountName'), '.dfs.core.windows.net/')]"}},
    "LS_AzureSql_Lloyds": {
        "type": "AzureSqlDatabase",
        "description": "Azure SQL (serverless, free offer). Long connect timeout because the database auto-pauses.",
        "typeProperties": {"connectionString": {"type": "SecureString", "value": (
            "[concat('Integrated Security=False;Encrypt=True;Connection Timeout=180;ConnectRetryCount=3;"
            "ConnectRetryInterval=20;Data Source=tcp:', parameters('sqlServerName'), '.database.windows.net,1433;"
            "Initial Catalog=', parameters('sqlDatabaseName'), ';User ID=', parameters('sqlEtlUser'), "
            "';Password=', parameters('sqlEtlPassword'), ';')]")}}},
    "LS_HTTP_BankOfEngland": {
        "type": "HttpServer",
        "description": "Bank of England Interactive Statistical Database (public, anonymous).",
        "typeProperties": {"url": "https://www.bankofengland.co.uk/", "enableServerCertificateValidation": True,
                           "authenticationType": "Anonymous"}},
}

# ------------------------------------------------------------------ datasets
BOE_URL = ("boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2020&Dateto=now"
           "&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
datasets = {
    "DS_Landing_Parquet": {
        "linkedServiceName": ls_ref("LS_ADLS_Landing"), "type": "Parquet",
        "typeProperties": {"location": {"type": "AzureBlobFSLocation", "fileSystem": "landing"},
                           "compressionCodec": "snappy"}, "schema": []},
    "DS_Landing_Folder": {
        "linkedServiceName": ls_ref("LS_ADLS_Landing"), "type": "Binary",
        "parameters": {"folder_path": {"type": "string"}},
        "typeProperties": {"location": {"type": "AzureBlobFSLocation", "fileSystem": "landing",
                                        "folderPath": expr("@dataset().folder_path")}}},
    "DS_SQL_Table": {
        "linkedServiceName": ls_ref("LS_AzureSql_Lloyds"), "type": "AzureSqlTable",
        "parameters": {"schema_name": {"type": "string", "defaultValue": "ops"},
                       "table_name": {"type": "string", "defaultValue": "load_config"}},
        "typeProperties": {"schema": expr("@dataset().schema_name"), "table": expr("@dataset().table_name")},
        "schema": []},
    "DS_BoE_BankRate_CSV": {
        "linkedServiceName": ls_ref("LS_HTTP_BankOfEngland"), "type": "DelimitedText",
        "typeProperties": {"location": {"type": "HttpServerLocation", "relativeUrl": BOE_URL},
                           "columnDelimiter": ",", "escapeChar": "\\", "firstRowAsHeader": True, "quoteChar": "\""},
        "schema": []},
}

# ------------------------------------------------------------------ pipeline: copy one table to staging
def log_sp(name, depends, status, rows=True, message=None):
    params = {
        "pipeline_run_id": sp_param(expr("@pipeline().RunId")),
        "pipeline_name": sp_param(expr("@pipeline().Pipeline")),
        "source_table": sp_param(expr("@pipeline().parameters.table_name")),
        "source_folder": sp_param(expr("@pipeline().parameters.copy_folder")),
        "status": sp_param(status),
    }
    if rows:
        params["rows_read"] = sp_param(expr("@activity('Copy_To_Staging').output.rowsRead"), "Int64")
        params["rows_written"] = sp_param(expr("@activity('Copy_To_Staging').output.rowsCopied"), "Int64")
    if message:
        params["message"] = sp_param(message)
    return {"name": name, "type": "SqlServerStoredProcedure", "dependsOn": depends, "policy": SP_POLICY,
            "linkedServiceName": ls_ref("LS_AzureSql_Lloyds"),
            "typeProperties": {"storedProcedureName": "[[ops].[usp_log_copy]", "storedProcedureParameters": params}}


copy_activity = {
    "name": "Copy_To_Staging", "type": "Copy", "dependsOn": [], "policy": POLICY,
    "inputs": [ds_ref("DS_Landing_Parquet")],
    "outputs": [ds_ref("DS_SQL_Table", {
        "schema_name": expr("@split(pipeline().parameters.stg_table, '.')[0]"),
        "table_name": expr("@split(pipeline().parameters.stg_table, '.')[1]")})],
    "typeProperties": {
        "source": {"type": "ParquetSource",
                   "storeSettings": {"type": "AzureBlobFSReadSettings", "recursive": True,
                                     "wildcardFolderPath": expr("@pipeline().parameters.copy_folder"),
                                     "wildcardFileName": "*.parquet", "enablePartitionDiscovery": False},
                   "additionalColumns": [{"name": "_source_file", "value": "$$FILEPATH"}]},
        "sink": {"type": "AzureSqlSink", "writeBehavior": "insert", "sqlWriterUseTableLock": True,
                 "writeBatchSize": 100000,
                 "preCopyScript": expr("@concat('TRUNCATE TABLE ', pipeline().parameters.stg_table)"),
                 "disableMetricsCollection": False},
        "enableStaging": False}}

pl_copy = {
    "description": "Copies every Parquet file under copy_folder (recursive) into a truncated staging table. "
                   "Skips gracefully when the folder does not exist (incremental run with no new month).",
    "parameters": {"table_name": {"type": "string"}, "copy_folder": {"type": "string"},
                   "stg_table": {"type": "string"}},
    "activities": [
        {"name": "Check_Source_Exists", "type": "GetMetadata", "dependsOn": [], "policy": POLICY,
         "typeProperties": {"dataset": ds_ref("DS_Landing_Folder", {"folder_path": expr("@pipeline().parameters.copy_folder")}),
                            "fieldList": ["exists"],
                            "storeSettings": {"type": "AzureBlobFSReadSettings", "recursive": True},
                            "formatSettings": {"type": "BinaryReadSettings"}}},
        {"name": "If_Source_Exists", "type": "IfCondition",
         "dependsOn": [{"activity": "Check_Source_Exists", "dependencyConditions": ["Succeeded"]}],
         "typeProperties": {
             "expression": expr("@activity('Check_Source_Exists').output.exists"),
             "ifTrueActivities": [
                 copy_activity,
                 log_sp("Log_Copy_Succeeded", [{"activity": "Copy_To_Staging", "dependencyConditions": ["Succeeded"]}],
                        "Succeeded"),
                 log_sp("Log_Copy_Failed", [{"activity": "Copy_To_Staging", "dependencyConditions": ["Failed"]}],
                        "Failed", rows=False, message=expr("@activity('Copy_To_Staging').error.message")),
                 {"name": "Fail_Copy", "type": "Fail",
                  "dependsOn": [{"activity": "Log_Copy_Failed", "dependencyConditions": ["Succeeded"]}],
                  "typeProperties": {"message": expr("@concat('Copy failed for ', pipeline().parameters.table_name)"),
                                     "errorCode": "COPY_FAILED"}}],
             "ifFalseActivities": [
                 log_sp("Log_No_Source_Data", [], "Skipped", rows=False,
                        message="Folder not found in the lake (no new data for this period)")]}}],
    "folder": {"name": "Lloyds"}, "annotations": ["lloyds-portfolio"]}

# ------------------------------------------------------------------ pipeline: Bank of England Bank Rate
bank_rate_mapping = {"type": "TabularTranslator", "typeConversion": True, "mappings": [
    {"source": {"name": "DATE"}, "sink": {"name": "rate_date"}},
    {"source": {"name": "IUDBEDR"}, "sink": {"name": "bank_rate"}},
    {"source": {"name": "source_system"}, "sink": {"name": "source_system"}}]}
fallback_mapping = {"type": "TabularTranslator", "typeConversion": True, "mappings": [
    {"source": {"name": "rate_date"}, "sink": {"name": "rate_date"}},
    {"source": {"name": "bank_rate"}, "sink": {"name": "bank_rate"}},
    {"source": {"name": "source_system"}, "sink": {"name": "source_system"}}]}
stg_bank_rate = ds_ref("DS_SQL_Table", {"schema_name": "stg", "table_name": "bank_rate"})
pl_boe = {
    "description": "Real Bank of England Bank Rate (series IUDBEDR) from the public IADB API. "
                   "Try/catch: if the API fails, the fallback file in the lake is used.",
    "activities": [
        {"name": "Copy_BoE_API", "type": "Copy", "dependsOn": [],
         "policy": {**POLICY, "retry": 2, "timeout": "0.00:10:00"},
         "inputs": [ds_ref("DS_BoE_BankRate_CSV")], "outputs": [stg_bank_rate],
         "typeProperties": {
             "source": {"type": "DelimitedTextSource",
                        "storeSettings": {"type": "HttpReadSettings", "requestMethod": "GET",
                                          "additionalHeaders": "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) portfolio-adf\nAccept: text/csv,*/*"},
                        "formatSettings": {"type": "DelimitedTextReadSettings"},
                        "additionalColumns": [{"name": "source_system", "value": "BoE API"}]},
             "sink": {"type": "AzureSqlSink", "writeBehavior": "insert",
                      "preCopyScript": "TRUNCATE TABLE stg.bank_rate"},
             "enableStaging": False, "translator": bank_rate_mapping}},
        {"name": "Copy_Fallback_File", "type": "Copy",
         "dependsOn": [{"activity": "Copy_BoE_API", "dependencyConditions": ["Failed"]}], "policy": POLICY,
         "inputs": [ds_ref("DS_Landing_Parquet")], "outputs": [stg_bank_rate],
         "typeProperties": {
             "source": {"type": "ParquetSource",
                        "storeSettings": {"type": "AzureBlobFSReadSettings", "recursive": True,
                                          "wildcardFolderPath": "external/bank_rate_fallback",
                                          "wildcardFileName": "*.parquet"},
                        "additionalColumns": [{"name": "source_system", "value": "Fallback"}]},
             "sink": {"type": "AzureSqlSink", "writeBehavior": "insert",
                      "preCopyScript": "TRUNCATE TABLE stg.bank_rate"},
             "enableStaging": False, "translator": fallback_mapping}},
        {"name": "Load_Bank_Rate_Gold", "type": "SqlServerStoredProcedure",
         "dependsOn": [{"activity": "Copy_Fallback_File", "dependencyConditions": ["Succeeded", "Skipped"]}],
         "policy": SP_POLICY, "linkedServiceName": ls_ref("LS_AzureSql_Lloyds"),
         "typeProperties": {"storedProcedureName": "[[gold].[usp_load_bank_rate]"}}],
    "folder": {"name": "Lloyds"}, "annotations": ["lloyds-portfolio"]}

# ------------------------------------------------------------------ master pipeline
def lookup(name, group, depends):
    return {"name": name, "type": "Lookup", "dependsOn": depends, "policy": POLICY,
            "typeProperties": {
                "source": {"type": "AzureSqlSource", "sqlReaderStoredProcedureName": "[[ops].[usp_get_load_plan]",
                           "storedProcedureParameters": {
                               "load_group": {"type": "Int16", "value": group},
                               "load_mode": {"type": "String", "value": expr("@pipeline().parameters.p_load_mode")}},
                           "queryTimeout": "02:00:00", "partitionOption": "None"},
                "dataset": ds_ref("DS_SQL_Table"), "firstRowOnly": False}}


def exec_copy(depends=None):
    return {"name": "Copy_Table_To_Staging", "type": "ExecutePipeline", "dependsOn": depends or [],
            "typeProperties": {"pipeline": {"referenceName": "PL_Copy_To_Staging", "type": "PipelineReference"},
                               "waitOnCompletion": True,
                               "parameters": {"table_name": expr("@item().table_name"),
                                              "copy_folder": expr("@item().copy_folder"),
                                              "stg_table": expr("@item().stg_table")}}}


def foreach(name, lookup_name, sequential, batch, inner):
    fe = {"name": name, "type": "ForEach",
          "dependsOn": [{"activity": lookup_name, "dependencyConditions": ["Succeeded"]}],
          "typeProperties": {"items": expr(f"@activity('{lookup_name}').output.value"),
                             "isSequential": sequential, "activities": inner}}
    if not sequential:
        fe["typeProperties"]["batchCount"] = batch
    return fe


def sp(name, proc, depends):
    return {"name": name, "type": "SqlServerStoredProcedure", "dependsOn": depends, "policy": SP_POLICY,
            "linkedServiceName": ls_ref("LS_AzureSql_Lloyds"), "typeProperties": {"storedProcedureName": proc}}


ok = lambda a: {"activity": a, "dependencyConditions": ["Succeeded"]}
fact_inner = [
    exec_copy(),
    {"name": "Load_Fact_To_Gold", "type": "SqlServerStoredProcedure",
     "dependsOn": [ok("Copy_Table_To_Staging")], "policy": SP_POLICY,
     "linkedServiceName": ls_ref("LS_AzureSql_Lloyds"),
     "typeProperties": {"storedProcedureName": expr("@item().target_proc")}}]

pl_master = {
    "description": "Lloyds end-to-end load | metadata-driven (ops.load_config). "
                   "p_load_mode = FULL (backfill all history) or INCREMENTAL (next month after the watermark).",
    "parameters": {"p_load_mode": {"type": "string", "defaultValue": "FULL"}},
    "activities": [
        lookup("Get_Reference_Tables", 1, []),
        foreach("Copy_Reference_Tables", "Get_Reference_Tables", False, 5, [exec_copy()]),
        lookup("Get_Master_Data_Tables", 2, []),
        foreach("Copy_Master_Data_Tables", "Get_Master_Data_Tables", False, 3, [exec_copy()]),
        sp("Load_Dimensions", "[[gold].[usp_load_dimensions]",
           [ok("Copy_Reference_Tables"), ok("Copy_Master_Data_Tables")]),
        {"name": "Load_Bank_Rate", "type": "ExecutePipeline", "dependsOn": [ok("Load_Dimensions")],
         "typeProperties": {"pipeline": {"referenceName": "PL_BankRate_BoE", "type": "PipelineReference"},
                            "waitOnCompletion": True}},
        lookup("Get_Fact_Tables", 3, [ok("Load_Dimensions")]),
        foreach("Load_Fact_Tables", "Get_Fact_Tables", True, 1, fact_inner),
        lookup("Get_Finance_Tables", 4, [ok("Load_Dimensions")]),
        foreach("Copy_Finance_Tables", "Get_Finance_Tables", False, 2, [exec_copy()]),
        sp("Load_Finance", "[[gold].[usp_load_finance]", [ok("Copy_Finance_Tables")]),
        sp("Refresh_Marts", "[[mart].[usp_refresh_marts]",
           [ok("Load_Fact_Tables"), ok("Load_Finance"), ok("Load_Bank_Rate")]),
    ],
    "folder": {"name": "Lloyds"}, "annotations": ["lloyds-portfolio"]}

# ------------------------------------------------------------------ template
resources = [{
    "type": "Microsoft.DataFactory/factories", "apiVersion": API, "name": FACTORY,
    "location": "[parameters('location')]", "identity": {"type": "SystemAssigned"},
    "tags": {"project": "lloyds-portfolio"}, "properties": {}}]

resources.append({
    "type": "Microsoft.Authorization/roleAssignments", "apiVersion": "2022-04-01",
    "name": "[guid(resourceId('Microsoft.Storage/storageAccounts', parameters('storageAccountName')), parameters('factoryName'), 'blob-data-reader')]",
    "scope": "[concat('Microsoft.Storage/storageAccounts/', parameters('storageAccountName'))]",
    "dependsOn": [FID],
    "properties": {
        "roleDefinitionId": "[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')]",
        "principalId": "[reference(resourceId('Microsoft.DataFactory/factories', parameters('factoryName')), '2018-06-01', 'Full').identity.principalId]",
        "principalType": "ServicePrincipal"}})

for n, p in linked_services.items():
    resources.append({"type": "Microsoft.DataFactory/factories/linkedServices", "apiVersion": API,
                      "name": child("linkedServices", n), "dependsOn": [FID], "properties": p})
for n, p in datasets.items():
    resources.append({"type": "Microsoft.DataFactory/factories/datasets", "apiVersion": API,
                      "name": child("datasets", n),
                      "dependsOn": [FID, dep("linkedServices", p["linkedServiceName"]["referenceName"])],
                      "properties": p})
ds_deps = [dep("datasets", n) for n in datasets] + [dep("linkedServices", n) for n in linked_services]
resources.append({"type": "Microsoft.DataFactory/factories/pipelines", "apiVersion": API,
                  "name": child("pipelines", "PL_Copy_To_Staging"), "dependsOn": [FID] + ds_deps, "properties": pl_copy})
resources.append({"type": "Microsoft.DataFactory/factories/pipelines", "apiVersion": API,
                  "name": child("pipelines", "PL_BankRate_BoE"), "dependsOn": [FID] + ds_deps, "properties": pl_boe})
resources.append({"type": "Microsoft.DataFactory/factories/pipelines", "apiVersion": API,
                  "name": child("pipelines", "PL_00_Master_Load"),
                  "dependsOn": [FID] + ds_deps + [dep("pipelines", "PL_Copy_To_Staging"), dep("pipelines", "PL_BankRate_BoE")],
                  "properties": pl_master})
resources.append({"type": "Microsoft.DataFactory/factories/triggers", "apiVersion": API,
                  "name": child("triggers", "TR_Monthly_Incremental"),
                  "dependsOn": [FID, dep("pipelines", "PL_00_Master_Load")],
                  "properties": {
                      "description": "Monthly incremental load (2nd of each month, 06:00 UK). Deployed STOPPED to avoid costs.",
                      "annotations": ["lloyds-portfolio"],
                      "pipelines": [{"pipelineReference": {"referenceName": "PL_00_Master_Load", "type": "PipelineReference"},
                                     "parameters": {"p_load_mode": "INCREMENTAL"}}],
                      "type": "ScheduleTrigger",
                      "typeProperties": {"recurrence": {
                          "frequency": "Month", "interval": 1, "startTime": "2026-10-02T06:00:00",
                          "timeZone": "GMT Standard Time", "schedule": {"monthDays": [2], "hours": [6], "minutes": [0]}}}}})

template = {
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "contentVersion": "1.0.0.0",
    "metadata": {"description": "Lloyds Banking Group portfolio (hypothetical data) | Azure Data Factory"},
    "parameters": {
        "factoryName": {"type": "string", "defaultValue": "adf-lloyds-joaopaura"},
        "location": {"type": "string", "defaultValue": "swedencentral"},
        "storageAccountName": {"type": "string", "defaultValue": "stlloydsjp01"},
        "sqlServerName": {"type": "string", "defaultValue": "sql-lloyds-joaopaura"},
        "sqlDatabaseName": {"type": "string", "defaultValue": "sqldb-lloyds"},
        "sqlEtlUser": {"type": "string", "defaultValue": "etl_loader"},
        "sqlEtlPassword": {"type": "securestring", "metadata": {"description": "Password of the etl_loader SQL user"}}},
    "resources": resources,
    "outputs": {"factoryPrincipalId": {"type": "string",
                "value": "[reference(resourceId('Microsoft.DataFactory/factories', parameters('factoryName')), '2018-06-01', 'Full').identity.principalId]"}}}

out = Path(__file__).with_name("adf_lloyds_template.json")
out.write_text(json.dumps(template, indent=2))
print(f"written {out} | {len(resources)} resources")
