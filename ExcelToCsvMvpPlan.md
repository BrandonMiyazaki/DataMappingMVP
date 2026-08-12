# MVP Plan: Excel Batch Upload to Standardized CSV on Azure

> **Review status (2026-08-11): Not deployment-ready**
>
> The architecture is viable, but this repository currently contains only this plan and sample workbooks. Function code, automated tests, analyzer configuration, infrastructure as code, and the Azure deployment workflow still need to be created and validated before deployment.

## Deployment Readiness Review

### Validated design choices

1. Azure AI Content Understanding supports `.xlsx` input in the current `2025-11-01` API documentation.
2. Event Grid can route `Microsoft.Storage.BlobCreated` events to an Azure Function.
3. A system-assigned managed identity with `Storage Blob Data Contributor` can read and write pipeline blobs without storage account keys.
4. Flex Consumption is the recommended hosting plan for a new Azure Functions deployment.
5. Application Insights is appropriate for invocation, dependency, duration, and exception telemetry.

### Blocking items before deployment

1. Confirm the Azure subscription and a region that supports Content Understanding, the required model deployments, and Flex Consumption.
2. Define and approve the exact CSV contract and expected output for each supplied sample workbook.
3. Prove `.xlsx` extraction with the proposed analyzer in Content Understanding before implementing the full event pipeline.
4. Create the Function application, analyzer definition, unit/integration tests, `azure.yaml`, and Bicep infrastructure.
5. Add idempotency because Event Grid can deliver the same event more than once.
6. Choose an orchestration approach that handles Content Understanding polling within the selected Function timeout. Use Durable Functions or a queue-based continuation if representative files cannot complete reliably in one invocation.
7. Create `.azure/deployment-plan.md`, confirm subscription/location and quota, approve it, then run the `azure-prepare` -> `azure-validate` -> `azure-deploy` workflow.

### Scope clarification

The MVP accepts `.xlsx`. Treat `.xlsm` as unsupported until an explicit spike proves that the selected Content Understanding API accepts it and the security review permits macro-enabled uploads. Never execute workbook macros.

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
| Key Vault | Stores secrets only for dependencies that cannot use Microsoft Entra authentication | Optional |

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

state/
  idempotency and terminal processing records keyed by event ID and blob ETag
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

Use Azure Developer CLI (`azd`) with Bicep for repeatable provisioning. The individual Azure CLI commands below are useful for diagnostics and learning, but they must not be the deployment source of truth.

Before generating infrastructure:

1. Create `.azure/deployment-plan.md` using the Azure deployment-plan template.
2. Confirm the target subscription and location with the operator.
3. Verify provider registration, regional Content Understanding/model availability, Flex Consumption availability, and quota.
4. Generate `azure.yaml` and Bicep for the complete resource graph.
5. Keep resource names parameterized and derive globally unique names in Bicep.
6. Run Bicep build/lint and an Azure what-if operation before provisioning.

Do not run `azd up` until the Function code, analyzer definition, automated tests, and Event Grid endpoint are present.

### 3.1 Set local variables

Use PowerShell:

```powershell
$RESOURCE_GROUP = "rg-excel-csv-mvp"
$LOCATION = "<confirmed-content-understanding-region>"
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

Prefer Microsoft Entra authentication for all operator and application data-plane operations. The signed-in deployment identity needs permission to create containers, and the Function managed identity needs `Storage Blob Data Contributor` on the data storage account.

```powershell
az storage container create --name raw --account-name $STORAGE_ACCOUNT --auth-mode login
az storage container create --name processed --account-name $STORAGE_ACCOUNT --auth-mode login
az storage container create --name failed --account-name $STORAGE_ACCOUNT --auth-mode login
az storage container create --name archive --account-name $STORAGE_ACCOUNT --auth-mode login
az storage container create --name state --account-name $STORAGE_ACCOUNT --auth-mode login
az storage container create --name eventgrid-deadletter --account-name $STORAGE_ACCOUNT --auth-mode login
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

Use Python on Flex Consumption unless a representative end-to-end timing spike shows that analysis cannot reliably complete within the configured execution timeout. Generate the Function app and plan from the current Azure Functions Bicep template rather than the legacy Linux Consumption command below.

```powershell
# Run only after the approved deployment plan and generated Bicep pass validation.
azd up
```

Query the current Azure Functions supported-languages documentation when implementation starts and select the latest supported GA Python version; do not freeze the plan to Python 3.11.

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

Also grant the Function identity `Cognitive Services Content Understanding Reader` on the Foundry resource so it can invoke an existing analyzer. Grant `Cognitive Services Content Understanding Contributor` only to the deployment identity that creates or updates analyzers. Do not give the runtime identity analyzer-management permission.

### 3.9 Managed identity and RBAC plan

Use Microsoft Entra authentication and managed identities wherever the target service supports them. Define these identities and assignments in Bicep; the CLI examples are for verification only.

| Caller | Target | Authentication | Least-privilege access |
|---|---|---|---|
| Azure Function system-assigned identity | Pipeline Blob Storage | Managed identity via `DefaultAzureCredential` | `Storage Blob Data Contributor` scoped to the data storage account, or narrower container scopes when practical |
| Azure Function system-assigned identity | Function host/deployment storage | Identity-based Functions storage settings | Assign only the storage data roles required by the generated Flex Consumption template and enabled bindings |
| Azure Function system-assigned identity | Content Understanding | Managed identity via `DefaultAzureCredential` | `Cognitive Services Content Understanding Reader` scoped to the Foundry resource |
| Event Grid subscription delivery identity | Dead-letter Blob container | Managed identity | Blob write access scoped to `eventgrid-deadletter` |
| Deployment operator or CI workload identity | Azure Resource Manager | Entra identity or workload identity federation | Resource deployment access plus only the role-assignment permission required by the Bicep deployment |
| Deployment operator or CI workload identity | Content Understanding analyzer management | Entra identity or workload identity federation | `Cognitive Services Content Understanding Contributor` scoped to the Foundry resource |
| Human or upload application | `raw` Blob container | Entra identity | Blob write access scoped to `raw`; no storage account keys |

Additional rules:

1. Do not enable storage shared-key access unless a proven platform dependency requires it. Record and time-box any exception.
2. Do not place account keys, client secrets, access tokens, or SAS tokens in source control, Bicep parameters, app settings, logs, or pipeline variables.
3. For CI/CD, prefer GitHub Actions or Azure DevOps workload identity federation over a client secret.
4. If an external client cannot authenticate with Entra ID, issue a short-lived, write-only user-delegation SAS from a trusted API; do not distribute account-key SAS tokens.
5. Treat the Application Insights connection string as configuration rather than a credential, and enable Microsoft Entra-authenticated telemetry ingestion when supported by the selected Functions monitoring integration.
6. Validate every role assignment at its narrowest practical scope and document why broader scope is required.

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

The schema below is illustrative. Before infrastructure deployment, submit it against the selected resource and API version, capture a successful analyzer-creation operation, and commit the validated response shape as a test fixture. Confirm model deployment names from the selected region instead of assuming the example model IDs are available.

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
$ANALYZER_ID = "excelCsvMvpAnalyzer"
$CU_TOKEN = az account get-access-token `
  --resource "https://cognitiveservices.azure.com" `
  --query accessToken `
  --output tsv

curl.exe -i -X PUT "$CU_ENDPOINT/contentunderstanding/analyzers/$ANALYZER_ID?api-version=2025-11-01" `
  -H "Authorization: Bearer $CU_TOKEN" `
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

Use `DefaultAzureCredential` and the Function managed identity for Content Understanding and Blob Storage. Do not set `CONTENT_UNDERSTANDING_KEY` or store storage account keys in Function settings. Keep `local.settings.json` out of source control; local development should use the developer's Azure CLI credential.

## Step 6: Build the Azure Function

### 6.1 Function responsibilities

The Function should:

1. Receive an Event Grid blob-created event.
2. Ignore files that are not in the `raw/` container.
3. Ignore unsupported file types.
4. Read the uploaded blob with its managed identity and submit the content directly to Content Understanding; do not generate a SAS URL for the normal processing path.
5. Call the Content Understanding analyzer.
6. Poll for analysis completion.
7. Parse the canonical JSON output.
8. Validate required fields and confidence scores.
9. Map the canonical JSON to the standardized CSV contract.
10. Write the CSV to `processed/`.
11. Write an error JSON document to `failed/` if validation or processing fails.
12. Log processing status to Application Insights.
13. Use the Event Grid event ID plus blob ETag as an idempotency key, persist state in `state/`, and return the existing terminal result for duplicate deliveries.
14. Enforce allowed extension, MIME type, file size, and workbook limits before submitting content.
15. Retry only transient `408`, `429`, and `5xx` dependencies with bounded exponential backoff; record permanent failures without retry loops.
16. Avoid logging extracted customer data, signed URLs, access tokens, or full analyzer responses.

If representative analysis regularly approaches the Function timeout, split submit and poll into Durable Functions activities or queue-backed continuations before deployment. A long synchronous polling loop is not an acceptable production assumption.

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

Pin compatible dependency ranges and generate a lock file for reproducible builds. Prefer the supported Content Understanding SDK when its selected-language release supports the required API; otherwise isolate REST calls behind `content_understanding_client.py`.

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

After the approved `.azure/deployment-plan.md` reaches `Ready for Validation`:

```powershell
azd provision
azd deploy
```

For the governed workflow, run Azure preparation and validation before deployment; do not execute these commands until validation succeeds. Use `func start` for local execution, not as the primary cloud deployment mechanism.

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
  --subject-ends-with ".xlsx" `
  --endpoint-type azurefunction `
  --endpoint "/subscriptions/<subscription-id>/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP/functions/<function-name>"
```

Define the subscription in Bicep, including a bounded retry policy and a dead-letter destination in `eventgrid-deadletter`. The Function must still validate the blob path and type because event filters are not a security boundary. Verify that the Event Grid service identity can write to the dead-letter container.

Replace:

| Placeholder | Value |
|---|---|
| `<subscription-id>` | Azure subscription ID |
| `<function-name>` | Event Grid trigger function name |

## Step 9: Test the MVP

Run tests in this order. Do not use an Azure upload as the first test of mapping logic.

### 9.0 Local and pre-deployment gates

1. Unit-test canonical validation, confidence threshold behavior, CSV quoting/encoding, numeric/date formatting, deterministic naming, and duplicate-event handling.
2. Use recorded Content Understanding response fixtures to test mapping without Azure calls.
3. Run the Function locally with a representative Event Grid event and Azurite or a dedicated development storage account.
4. Validate `azure.yaml`, build/lint Bicep, run a resource deployment what-if, and verify RBAC scopes.
5. Run a direct Content Understanding smoke test against `SampleData/synthetic_assembly_line_test_measurements_raw.xlsx` before enabling Event Grid.

### 9.1 Prepare test files

Create a small test set with at least:

1. `SampleData/synthetic_assembly_line_test_measurements_raw.xlsx` as the expected successful input.
2. `SampleData/assembly_line_measurement_mapping_output.xlsx` as the business-provided expected mapping reference; convert its approved expected rows to a checked-in CSV fixture.
3. One file with missing required fields.
4. One file with unusual sheet names.
5. One file with multiple tables.
6. One file with merged cells or non-standard headers.
7. One duplicate event using the same event ID and blob ETag.
8. One oversized or unsupported file, including `.xlsm`, to confirm rejection without macro execution.

### 9.2 Upload a file to the raw container

```powershell
az storage blob upload `
  --account-name $STORAGE_ACCOUNT `
  --auth-mode login `
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
  --auth-mode login `
  --container-name processed `
  --output table
```

Download the generated CSV:

```powershell
az storage blob download `
  --account-name $STORAGE_ACCOUNT `
  --auth-mode login `
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
  --auth-mode login `
  --container-name raw `
  --name "bad-sample.xlsx" `
  --file "C:\path\to\bad-sample.xlsx" `
  --overwrite true
```

List the failed container:

```powershell
az storage blob list `
  --account-name $STORAGE_ACCOUNT `
  --auth-mode login `
  --container-name failed `
  --output table
```

Download the error JSON:

```powershell
az storage blob download `
  --account-name $STORAGE_ACCOUNT `
  --auth-mode login `
  --container-name failed `
  --name "bad-sample.error.json" `
  --file "C:\temp\bad-sample.error.json" `
  --overwrite true
```

Validate:

1. The error file exists in `failed/`.
2. The error file explains the validation or processing failure.
3. No invalid CSV was written to `processed/`.

### 9.5 Confirm reliability and security behavior

1. Redeliver the same Event Grid event and verify that no duplicate Content Understanding job or output is created.
2. Force a transient dependency failure and verify bounded retries followed by a useful terminal error.
3. Verify Event Grid dead-lettering with a deliberately unavailable endpoint in a non-production environment.
4. Verify the Function can process blobs and invoke Content Understanding using managed identity after local credentials and account keys are removed.
5. Verify a caller without data-plane RBAC cannot read `raw`, `processed`, or `failed` blobs.
6. Verify logs contain correlation IDs, event IDs, blob names, durations, and status but no extracted sensitive values or credentials.
7. Verify storage shared-key access is disabled, or document the exact platform blocker and approved exception.
8. Verify the deployment pipeline authenticates with workload identity federation and contains no client secret.
9. Enumerate effective RBAC assignments and confirm the Function identity has no Owner, Contributor, analyzer-management, or unrelated data-plane roles.

### 9.6 Check Function logs

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

1. A user can upload an `.xlsx` file to `raw/`.
2. Event Grid triggers the Azure Function automatically.
3. The Function calls the Content Understanding analyzer.
4. Valid extracted data is mapped to the exact standard CSV headers.
5. The generated CSV is written to `processed/`.
6. Invalid files write a useful error JSON file to `failed/`.
7. Function logs show processing status and errors.
8. At least 3-5 representative sample files have been tested.
9. Replaying the same event is idempotent.
10. All deployed resources come from `azure.yaml` and Bicep, and a clean environment can be recreated with the same artifacts.
11. Managed identity is used for runtime access; no storage or Content Understanding keys are present in Function settings.
12. Unit, fixture-based integration, infrastructure validation, and Azure end-to-end tests all pass.

## Recommended MVP Enhancements After Initial Success

After the MVP works, consider adding:

1. Durable Functions for long-running analysis, retries, and state tracking.
2. Data Factory for scheduled batch orchestration and operational visibility.
3. Service Bus Queue between Event Grid and Function for better retry control.
4. Human review workflow for low-confidence extractions.
5. A metadata database, such as Azure SQL or Cosmos DB, to track file status.
6. Key Vault for any future dependency that cannot use Microsoft Entra authentication.
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
| Secrets | Use managed identity; use Key Vault only for a dependency that cannot use Microsoft Entra authentication |
| Deployment | Use `azd` with Bicep; treat portal/CLI changes as diagnostics, not source of truth |
| Hosting | Use Flex Consumption after confirming representative execution time |
| Authentication | Use managed identity for Blob Storage and Content Understanding |
| CI/CD authentication | Use workload identity federation; do not create a client secret |
| User upload authentication | Use Entra ID; permit only short-lived user-delegation SAS as an approved external-client exception |
| Delivery semantics | Assume Event Grid at-least-once delivery and implement idempotency |

## Deployment Go/No-Go Gate

Proceed to Azure deployment only when every item is `Yes`:

| Gate | Current state |
|---|---|
| CSV contract and expected sample output approved | No |
| Direct `.xlsx` Content Understanding spike passed in target region | No |
| Function code and analyzer definition committed | No |
| Unit and fixture-based integration tests passed | No |
| `.azure/deployment-plan.md` approved with subscription, region, cost classification, and quota evidence | No |
| `azure.yaml` and Bicep generated and validated | No |
| Managed identity and least-privilege RBAC validated | No |
| Shared-key access disabled or an approved exception documented | No |
| CI/CD workload identity federation validated with no client secret | No |
| Event Grid retry, dead-letter, and idempotency behavior validated | No |
| Azure what-if completed without unexpected destructive changes | No |
| `azure-validate` workflow completed with recorded proof | No |

**Current decision: No-Go.** The next action is to approve the CSV contract and run the direct Content Understanding spike against the raw sample workbook. After those pass, scaffold the Function and deployment artifacts; then perform subscription-specific validation and deployment.

## Official References Used for This Review

1. [Azure Content Understanding supported file formats and limits](https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits)
2. [Content Understanding security and managed identities](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/secure-communications)
3. [Azure Functions Flex Consumption](https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan)
4. [Azure Functions idempotent design](https://learn.microsoft.com/azure/azure-functions/functions-idempotent)
5. [Event Grid delivery and retry](https://learn.microsoft.com/azure/event-grid/delivery-and-retry)
6. [Azure Developer CLI documentation](https://learn.microsoft.com/azure/developer/azure-developer-cli/)

