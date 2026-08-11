# MVP Plan: Excel Batch Upload to Standardized CSV on Azure

## Goal

Build an MVP pipeline that lets users upload complex Excel files into Azure Blob Storage, extracts fields with Azure AI Content Understanding, validates the extracted data, maps it to a standardized CSV format, and writes either a processed CSV output or a failure record.

## MVP Architecture

```text
User uploads Excel file
  -> Azure Blob Storage: raw/
  -> Event Grid blob-created event
  -> Azure Function
      -> calls Azure AI Content Understanding analyzer
      -> validates extracted fields
      -> maps canonical JSON to standardized CSV
  -> Azure Blob Storage: processed/
  -> Azure Blob Storage: failed/ if validation fails
```

## Required Azure Components

| Component | Purpose | Required for MVP |
|---|---|---|
| Azure Storage Account | Stores raw Excel files, processed CSV files, failed records, and optional archived source files | Yes |
| Blob containers | Logical folders for `raw`, `processed`, `failed`, and optionally `archive` | Yes |
| Event Grid | Detects new files uploaded to the `raw` container | Yes |
| Azure Function App | Runs the extraction, validation, and CSV mapping logic | Yes |
| Azure AI Content Understanding | Extracts structured fields from complex Excel files | Yes |
| Content Understanding custom analyzer | Defines the fields and tables to extract from source files | Yes |
| Application Insights | Logs execution details, errors, and processing metrics | Strongly recommended |
| Key Vault | Stores Content Understanding endpoint/key if not using managed identity | Recommended |

## Suggested MVP Folder Layout in Blob Storage

```text
raw/
  incoming Excel files

processed/
  standardized CSV output files

failed/
  validation failures and processing error JSON files

archive/
  optional copy of original files after successful processing
```

Example output names:

```text
raw/customer-report-001.xlsx
processed/customer-report-001.csv
failed/customer-report-001.error.json
archive/customer-report-001.xlsx
```

## Step 1: Define the Standard CSV Contract

Before deploying anything, define the exact CSV output structure.

Create a CSV contract document with:

1. Final column names.
2. Column order.
3. Required fields.
4. Optional fields.
5. Data types.
6. Date and number formatting rules.
7. Default values for missing optional fields.
8. Validation rules.
9. Example valid output.

Example standardized CSV contract:

```csv
SourceFile,CustomerName,ReportingPeriod,LineItemName,Quantity,UnitPrice,TotalAmount,Currency,ConfidenceScore
sample.xlsx,Contoso,2026-07,Product A,10,15.50,155.00,USD,0.91
```

## Step 2: Define the Canonical Extraction Schema

The Content Understanding analyzer should extract a canonical JSON model. This does not need to match the CSV one-to-one. The Azure Function should own the final CSV formatting.

Example canonical model:

```json
{
  "customerName": "Contoso",
  "reportingPeriod": "2026-07",
  "currency": "USD",
  "lineItems": [
    {
      "name": "Product A",
      "quantity": 10,
      "unitPrice": 15.5,
      "totalAmount": 155.0
    }
  ]
}
```

Recommended validation rules:

| Field | Rule |
|---|---|
| `customerName` | Required |
| `reportingPeriod` | Required, valid date or period format |
| `lineItems` | Required, must contain at least one row |
| `lineItems[].name` | Required |
| `lineItems[].quantity` | Required numeric value |
| `lineItems[].totalAmount` | Required numeric value |
| Confidence score | Route to `failed/` if below the MVP threshold |

## Step 3: Create the Azure Resources

### 3.1 Set local variables

Use PowerShell:

```powershell
$RESOURCE_GROUP = "rg-excel-csv-mvp"
$LOCATION = "westus2"
$STORAGE_ACCOUNT = "stexcelcsvmvp001"
$FUNCTION_APP = "func-excel-csv-mvp-001"
$APP_INSIGHTS = "appi-excel-csv-mvp"
$PLAN_NAME = "plan-excel-csv-mvp"
```

Storage account names must be globally unique, lowercase, and 3-24 characters.

### 3.2 Create the resource group

```powershell
az group create `
  --name $RESOURCE_GROUP `
  --location $LOCATION
```

### 3.3 Create the storage account

```powershell
az storage account create `
  --name $STORAGE_ACCOUNT `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku Standard_LRS `
  --kind StorageV2 `
  --allow-blob-public-access false
```

### 3.4 Create the blob containers

```powershell
$STORAGE_KEY = az storage account keys list `
  --resource-group $RESOURCE_GROUP `
  --account-name $STORAGE_ACCOUNT `
  --query "[0].value" `
  --output tsv

az storage container create --name raw --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY
az storage container create --name processed --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY
az storage container create --name failed --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY
az storage container create --name archive --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY
```

### 3.5 Create Application Insights

```powershell
az monitor app-insights component create `
  --app $APP_INSIGHTS `
  --location $LOCATION `
  --resource-group $RESOURCE_GROUP `
  --application-type web
```

### 3.6 Create the Azure Function App

For the MVP, use Python or .NET. Python is a good fit because Excel and CSV processing libraries are mature.

```powershell
az functionapp create `
  --name $FUNCTION_APP `
  --resource-group $RESOURCE_GROUP `
  --storage-account $STORAGE_ACCOUNT `
  --consumption-plan-location $LOCATION `
  --runtime python `
  --runtime-version 3.11 `
  --functions-version 4 `
  --os-type Linux
```

### 3.7 Enable managed identity on the Function App

```powershell
az functionapp identity assign `
  --name $FUNCTION_APP `
  --resource-group $RESOURCE_GROUP
```

### 3.8 Grant the Function App access to Blob Storage

Get the principal ID:

```powershell
$FUNCTION_PRINCIPAL_ID = az functionapp identity show `
  --name $FUNCTION_APP `
  --resource-group $RESOURCE_GROUP `
  --query principalId `
  --output tsv

$STORAGE_SCOPE = az storage account show `
  --name $STORAGE_ACCOUNT `
  --resource-group $RESOURCE_GROUP `
  --query id `
  --output tsv
```

Assign Blob Data Contributor:

```powershell
az role assignment create `
  --assignee $FUNCTION_PRINCIPAL_ID `
  --role "Storage Blob Data Contributor" `
  --scope $STORAGE_SCOPE
```

## Step 4: Create the Content Understanding Resource and Analyzer

### 4.1 Create the Foundry resource

In the Azure portal:

1. Create a Microsoft Foundry resource.
2. Select a region supported by Azure AI Content Understanding.
3. Enable Content Understanding in the Foundry Tools experience.
4. Configure default model deployments for Content Understanding.
5. Record the Content Understanding endpoint.

### 4.2 Create a custom analyzer

Create an analyzer schema that describes the fields and tables you need to extract.

Example analyzer schema:

```json
{
  "description": "Excel to standardized CSV MVP analyzer",
  "baseAnalyzerId": "prebuilt-document",
  "models": {
    "completion": "gpt-5.2",
    "embedding": "text-embedding-3-large"
  },
  "config": {
    "returnDetails": true,
    "enableFormula": false,
    "estimateFieldSourceAndConfidence": true,
    "tableFormat": "html"
  },
  "fieldSchema": {
    "fields": {
      "customerName": {
        "type": "string",
        "method": "extract",
        "description": "Customer or account name associated with the spreadsheet"
      },
      "reportingPeriod": {
        "type": "string",
        "method": "extract",
        "description": "Reporting period represented by the spreadsheet"
      },
      "currency": {
        "type": "string",
        "method": "extract",
        "description": "Currency used for financial values"
      },
      "lineItems": {
        "type": "array",
        "method": "extract",
        "items": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string",
              "method": "extract",
              "description": "Line item name or description"
            },
            "quantity": {
              "type": "number",
              "method": "extract",
              "description": "Quantity for the line item"
            },
            "unitPrice": {
              "type": "number",
              "method": "extract",
              "description": "Unit price for the line item"
            },
            "totalAmount": {
              "type": "number",
              "method": "extract",
              "description": "Total amount for the line item"
            }
          }
        }
      }
    }
  }
}
```

Create the analyzer with the Content Understanding REST API:

```powershell
$CU_ENDPOINT = "https://<your-content-understanding-endpoint>"
$CU_KEY = "<your-content-understanding-key>"
$ANALYZER_ID = "excelCsvMvpAnalyzer"

curl.exe -i -X PUT "$CU_ENDPOINT/contentunderstanding/analyzers/$ANALYZER_ID?api-version=2025-11-01" `
  -H "Ocp-Apim-Subscription-Key: $CU_KEY" `
  -H "Content-Type: application/json" `
  --data-binary "@analyzer.json"
```

Poll the operation URL returned in the `Operation-Location` response header until the analyzer creation status is `succeeded`.

## Step 5: Configure Function App Settings

Set the settings needed by the Azure Function:

```powershell
az functionapp config appsettings set `
  --name $FUNCTION_APP `
  --resource-group $RESOURCE_GROUP `
  --settings `
    "DATA_STORAGE_ACCOUNT=$STORAGE_ACCOUNT" `
    "RAW_CONTAINER=raw" `
    "PROCESSED_CONTAINER=processed" `
    "FAILED_CONTAINER=failed" `
    "ARCHIVE_CONTAINER=archive" `
    "CONTENT_UNDERSTANDING_ENDPOINT=$CU_ENDPOINT" `
    "CONTENT_UNDERSTANDING_ANALYZER_ID=$ANALYZER_ID" `
    "CONTENT_UNDERSTANDING_API_VERSION=2025-11-01" `
    "MIN_CONFIDENCE_SCORE=0.80"
```

For production, store the Content Understanding key in Key Vault instead of directly in Function App settings.

For the MVP, if using a key:

```powershell
az functionapp config appsettings set `
  --name $FUNCTION_APP `
  --resource-group $RESOURCE_GROUP `
  --settings "CONTENT_UNDERSTANDING_KEY=$CU_KEY"
```

## Step 6: Build the Azure Function

### 6.1 Function responsibilities

The Function should:

1. Receive an Event Grid blob-created event.
2. Ignore files that are not in the `raw/` container.
3. Ignore unsupported file types.
4. Generate a secure read URL for the uploaded file or download the file and submit it to Content Understanding.
5. Call the Content Understanding analyzer.
6. Poll for analysis completion.
7. Parse the canonical JSON output.
8. Validate required fields and confidence scores.
9. Map the canonical JSON to the standardized CSV contract.
10. Write the CSV to `processed/`.
11. Write an error JSON document to `failed/` if validation or processing fails.
12. Log processing status to Application Insights.

### 6.2 Suggested local project structure

```text
excel-csv-function/
  function_app.py
  requirements.txt
  host.json
  local.settings.json
  shared/
    content_understanding_client.py
    csv_mapper.py
    validation.py
    storage.py
```

### 6.3 Suggested Python dependencies

```text
azure-functions
azure-identity
azure-storage-blob
requests
```

If pre-processing Excel locally before Content Understanding is needed, add:

```text
openpyxl
pandas
```

### 6.4 Validation failure format

Write failed records as JSON so users and operators can understand why the file failed.

Example:

```json
{
  "sourceFile": "customer-report-001.xlsx",
  "status": "failed",
  "reason": "Validation failed",
  "errors": [
    "customerName is required",
    "lineItems must contain at least one row"
  ],
  "contentUnderstandingOperationId": "operation-id",
  "timestampUtc": "2026-08-11T22:00:00Z"
}
```

## Step 7: Deploy the Function Code

From the Function project folder:

```powershell
func azure functionapp publish $FUNCTION_APP
```

If the Azure Functions Core Tools are not available, deploy from VS Code or a CI/CD pipeline instead.

## Step 8: Create the Event Grid Subscription

Create an Event Grid subscription that triggers the Function when a blob is created in the `raw` container.

Get the storage account ID:

```powershell
$STORAGE_ID = az storage account show `
  --name $STORAGE_ACCOUNT `
  --resource-group $RESOURCE_GROUP `
  --query id `
  --output tsv
```

Create the subscription:

```powershell
az eventgrid event-subscription create `
  --name "evg-raw-excel-upload-to-function" `
  --source-resource-id $STORAGE_ID `
  --included-event-types Microsoft.Storage.BlobCreated `
  --subject-begins-with "/blobServices/default/containers/raw/blobs/" `
  --endpoint-type azurefunction `
  --endpoint "/subscriptions/<subscription-id>/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP/functions/<function-name>"
```

Replace:

| Placeholder | Value |
|---|---|
| `<subscription-id>` | Azure subscription ID |
| `<function-name>` | Event Grid trigger function name |

## Step 9: Test the MVP

### 9.1 Prepare test files

Create a small test set with at least:

1. One expected successful Excel file.
2. One file with missing required fields.
3. One file with unusual sheet names.
4. One file with multiple tables.
5. One file with merged cells or non-standard headers.

### 9.2 Upload a file to the raw container

```powershell
az storage blob upload `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name raw `
  --name "customer-report-001.xlsx" `
  --file "C:\path\to\customer-report-001.xlsx" `
  --overwrite true
```

### 9.3 Confirm processing succeeded

List the processed container:

```powershell
az storage blob list `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name processed `
  --output table
```

Download the generated CSV:

```powershell
az storage blob download `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name processed `
  --name "customer-report-001.csv" `
  --file "C:\temp\customer-report-001.csv" `
  --overwrite true
```

Validate:

1. The file exists in `processed/`.
2. The CSV headers exactly match the standard contract.
3. The column order is correct.
4. Required fields are populated.
5. Numeric/date fields are formatted correctly.
6. Row count matches expected extracted line items.

### 9.4 Confirm failed-file behavior

Upload a bad file:

```powershell
az storage blob upload `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name raw `
  --name "bad-sample.xlsx" `
  --file "C:\path\to\bad-sample.xlsx" `
  --overwrite true
```

List the failed container:

```powershell
az storage blob list `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name failed `
  --output table
```

Download the error JSON:

```powershell
az storage blob download `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --container-name failed `
  --name "bad-sample.error.json" `
  --file "C:\temp\bad-sample.error.json" `
  --overwrite true
```

Validate:

1. The error file exists in `failed/`.
2. The error file explains the validation or processing failure.
3. No invalid CSV was written to `processed/`.

### 9.5 Check Function logs

Stream Function logs:

```powershell
az webapp log tail `
  --name $FUNCTION_APP `
  --resource-group $RESOURCE_GROUP
```

In Application Insights, check:

1. Function invocation count.
2. Processing duration.
3. Exceptions.
4. Failed validation count.
5. Content Understanding API call failures.

## Step 10: MVP Acceptance Criteria

The MVP is complete when:

1. A user can upload an `.xlsx` or `.xlsm` file to `raw/`.
2. Event Grid triggers the Azure Function automatically.
3. The Function calls the Content Understanding analyzer.
4. Valid extracted data is mapped to the exact standard CSV headers.
5. The generated CSV is written to `processed/`.
6. Invalid files write a useful error JSON file to `failed/`.
7. Function logs show processing status and errors.
8. At least 3-5 representative sample files have been tested.

## Recommended MVP Enhancements After Initial Success

After the MVP works, consider adding:

1. Durable Functions for long-running analysis, retries, and state tracking.
2. Data Factory for scheduled batch orchestration and operational visibility.
3. Service Bus Queue between Event Grid and Function for better retry control.
4. Human review workflow for low-confidence extractions.
5. A metadata database, such as Azure SQL or Cosmos DB, to track file status.
6. Key Vault for all secrets.
7. Private endpoints and managed identity for production security.
8. A web upload portal for business users.
9. Automated CSV contract tests.
10. Alerting for high failure rates or processing delays.

## Key Design Decisions for the MVP

| Decision | Recommendation |
|---|---|
| Orchestration | Use Event Grid directly to Azure Function for the MVP |
| Extraction | Use Content Understanding custom analyzer |
| Final CSV generation | Keep deterministic in Azure Function code |
| Validation | Fail closed if required fields are missing |
| Low confidence | Route to `failed/` or manual review |
| File storage | Use Blob Storage containers for each pipeline stage |
| Monitoring | Use Application Insights |
| Secrets | Use Key Vault for production; app settings are acceptable only for a short-lived MVP |

