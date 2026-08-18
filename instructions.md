# DataMappingMVP — Test & Deploy Instructions

This guide walks you from a fresh clone to a working, in-cloud pipeline. It has two parts:

- **Part 1 — Test locally:** run the mapping/enrichment logic offline (no Azure needed).
- **Part 2 — Deploy to Azure:** provision infrastructure, deploy the function, wire the Event Grid trigger, and validate a real upload end-to-end.

> **What this project does (one line):** a raw `.xlsx` uploaded to Blob Storage `raw/` triggers an Azure Function that uses Azure AI Content Understanding to normalize messy test data into a clean 25-column CSV in `processed/` (quarantining bad rows to `failed/`).

---

## Prerequisites

Install these once before you start. Each is used at a specific step below.

| Tool | Why you need it | Install |
| --- | --- | --- |
| **Python 3.12** | Runtime for the function and the local tests. | [python.org](https://www.python.org/downloads/) |
| **Azure CLI (`az`)** | Sign in, configure app settings, create the Event Grid subscription. | `winget install Microsoft.AzureCLI` |
| **Azure Developer CLI (`azd`) ≥ 1.31** | Provisions infrastructure (Bicep) and deploys the function code in one workflow. | `winget install Microsoft.Azd` |
| **An Azure subscription** | Where the resources are created. You need rights to create resource groups, storage, functions, and an AI Services account. | — |

> **Version note:** `azd` older than 1.31 has a token bug (`AADSTS9002313`). If `azd` auth fails, run `winget upgrade Microsoft.Azd`.

---

## Part 1 — Test locally

**Goal:** prove the business logic (schema validation, enrichment, resilient mapping, and end-to-end extraction) works — without any Azure calls. The tests use a **recorded** Content Understanding response in [fixtures/content_understanding_response.json](fixtures/content_understanding_response.json), so they run fully offline.

### Step 1.1 — Create and activate a virtual environment
*Isolates this project's dependencies from the rest of your machine.*

```powershell
# from the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked by execution policy, run this first (current session only):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### Step 1.2 — Install dependencies
*Installs the Azure Functions, identity, and storage SDKs the code imports.*

```powershell
pip install -r requirements.txt
```

### Step 1.3 — Run the test suite
*Exercises the 25-column contract, the enrichment rules, response extraction, and the full mapping pipeline against the recorded fixture. All tests should pass with no network access.*

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Expected result: all tests pass (currently **29 tests**). If they pass, the core logic is healthy and you're ready to deploy.

---

## Part 2 — Deploy to Azure

**Goal:** stand up the cloud resources, deploy the function, connect the blob-upload trigger through Event Grid, and confirm a real file flows `raw/ → processed/`.

### Step 2.1 — Sign in to Azure
*Authenticates both CLIs so they can create and configure resources. Use the same tenant/subscription for both.*

```powershell
az login
az account set --subscription "<your-subscription-id>"

azd auth login
```

### Step 2.2 — Set unique resource names
*Storage account, function app, and App Insights names must be **globally unique**. The defaults in [infra/main.parameters.json](infra/main.parameters.json) are the author's — change them or provisioning will fail with name-conflict errors.*

Edit [infra/main.parameters.json](infra/main.parameters.json) and pick your own values for:

- `storageAccountName` (3–24 chars, lowercase letters/numbers only)
- `functionAppName`
- `appInsightsName`

### Step 2.3 — Provision infrastructure and deploy the code
*`azd up` reads [azure.yaml](azure.yaml), deploys the Bicep in [infra/main.bicep](infra/main.bicep) (Flex Consumption function, storage with `raw`/`processed`/`failed` containers, App Insights, managed identity), then packages and uploads the Python function.*

```powershell
azd up
```

You'll be prompted for an environment name, subscription, and region. When it finishes, note the function app name and storage account name in the output.

> **Why Flex Consumption:** the classic Consumption plan can't integrate with a private VNet. If your storage locks down public access, Flex Consumption + VNet integration is what lets the function host reach it. For a fully public dev setup this isn't required, but the provided Bicep uses Flex so the same code works in a locked-down network.

### Step 2.4 — Grant the function's managed identity access
*The function authenticates to Storage and Content Understanding with its managed identity (no keys). It needs data-plane roles. Replace the placeholders with your values.*

```powershell
# Get the function app's managed identity principal ID
$principalId = az functionapp identity show -g <resource-group> -n <function-app-name> --query principalId -o tsv

# Storage: read/write blobs (input, output, and deployment container)
az role assignment create --assignee $principalId `
  --role "Storage Blob Data Contributor" `
  --scope /subscriptions/<sub-id>/resourceGroups/<resource-group>/providers/Microsoft.Storage/storageAccounts/<storage-account-name>

# Storage: queue access (used by the Functions host)
az role assignment create --assignee $principalId `
  --role "Storage Queue Data Contributor" `
  --scope /subscriptions/<sub-id>/resourceGroups/<resource-group>/providers/Microsoft.Storage/storageAccounts/<storage-account-name>

# AI: call the Content Understanding analyzer
az role assignment create --assignee $principalId `
  --role "Cognitive Services User" `
  --scope /subscriptions/<sub-id>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<ai-account-name>
```

### Step 2.5 — Set the Content Understanding app settings
*Tells the function which AI endpoint, analyzer, and API version to call. Without these the function can't extract data.*

```powershell
az functionapp config appsettings set -g <resource-group> -n <function-app-name> --settings `
  CONTENT_UNDERSTANDING_ENDPOINT="https://<ai-account-name>.cognitiveservices.azure.com" `
  CONTENT_UNDERSTANDING_ANALYZER_ID="assemblyMeasurementAnalyzer3" `
  CONTENT_UNDERSTANDING_API_VERSION="2025-11-01"
```

> The analyzer itself is defined in [excel_csv_mvp_analyzer.json](excel_csv_mvp_analyzer.json). You must create it in your AI Services account once (via the Content Understanding REST API) and reference a strong completion model (e.g. `gpt-5.2`) — a weaker model only extracts the first section of the sample data.

### Step 2.6 — Wire the Event Grid trigger
*The function uses an **Event Grid** blob trigger, so a new upload to `raw/` must be routed to the function. This creates that subscription.*

First, get the blob-extension system key (authenticates Event Grid to the function's webhook):

```powershell
$blobKey = az functionapp keys list -g <resource-group> -n <function-app-name> --query "systemKeys.blobs_extension" -o tsv
```

Then create the subscription on the storage account's system topic:

```powershell
$endpoint = "https://<function-app-name>.azurewebsites.net/runtime/webhooks/blobs?functionName=Host.Functions.excel_to_csv_blob_processor&code=$blobKey"

az eventgrid system-topic event-subscription create `
  --name egs-excel-blob `
  -g <resource-group> `
  --system-topic-name <storage-system-topic-name> `
  --endpoint $endpoint `
  --endpoint-type webhook `
  --included-event-types Microsoft.Storage.BlobCreated `
  --subject-begins-with /blobServices/default/containers/raw/
```

> **Known gotcha (Windows):** `az.cmd` can mangle the `&` characters in the webhook URL and drop `&code=`, causing a **401** validation failure (symptom: warnings that options are "passed to Electron/Chromium"). If that happens, invoke the CLI through Python directly so the URL is preserved:
> ```powershell
> & 'C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\python.exe' -m azure.cli eventgrid system-topic event-subscription create --name egs-excel-blob -g <resource-group> --system-topic-name <topic> --endpoint '<full-url>' --endpoint-type webhook --included-event-types Microsoft.Storage.BlobCreated --subject-begins-with /blobServices/default/containers/raw/
> ```

### Step 2.7 — Run an end-to-end test
*Uploads a fresh raw workbook and confirms the pipeline produces a normalized CSV.*

```powershell
az storage blob upload `
  --account-name <storage-account-name> `
  --container-name raw `
  --name test-run-1.xlsx `
  --file SampleData/synthetic_assembly_line_test_measurements_raw.xlsx `
  --auth-mode login
```

Then verify the outputs:

```powershell
# Should contain test-run-1.csv
az storage blob list --account-name <storage-account-name> --container-name processed --auth-mode login -o table

# Any quarantined rows land here as *.error.json
az storage blob list --account-name <storage-account-name> --container-name failed --auth-mode login -o table
```

> **Important:** always upload a **new** file name. Event Grid does not replay `BlobCreated` events that occurred before the subscription existed, and re-uploading the same name may not re-fire.

Success = a `.csv` appears in `processed/`. You now have a working pipeline.

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `azd` auth fails with `AADSTS9002313` | `azd` older than 1.31 | `winget upgrade Microsoft.Azd`, then `azd auth login` again |
| **0 functions registered** / trigger never fires | Function host can't reach private storage | Ensure the app is Flex Consumption with VNet integration, or that storage public access is enabled for a simple dev setup |
| **403 Ip Forbidden** on deploy | Function app public network access disabled and you're not in the VNet | Temporarily enable public access, or deploy from an in-network host |
| **Key based auth not permitted** | Storage `allowSharedKeyAccess=false` | Confirm managed-identity settings and the role assignments in Step 2.4 |
| Event Grid **401** on subscription create | `az.cmd` dropped `&code=` from the webhook URL | Use the Python-invoked CLI form shown in Step 2.6 |
| CU returns **400 "Expected a JSON content type"** | Wrong request shape | The code already sends `{"inputs":[{"data":"<base64>"}]}` as JSON — make sure you deployed the latest [function_app.py](function_app.py) |
| Only part of the data is extracted | Weak completion model on the analyzer | Point the analyzer's completion alias at a stronger model (e.g. `gpt-5.2`) |

To inspect a live run, check the function's logs in **Application Insights** (works over the public endpoint even when the app itself is private).
