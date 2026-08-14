# Project Wiki

## Overview
This wiki tracks the implementation progress for the Excel-to-CSV MVP solution.

## Completed Steps
- Reviewed the MVP plan in ExcelToCsvMvpPlan.md.
- Established the initial standardized CSV contract and validation expectations.
- Implemented a first-pass mapping module for canonical payloads to CSV rows.
- Added unit tests covering happy path, missing required fields, low-confidence rejection, and CSV serialization.
- Verified the first implementation phase with `python -m unittest discover -s tests -p "test_*.py"`.
- Phase 1 review completed and approved for proceed-after-validation on 2026-08-13.
- Provisioned the Azure resource group and core project resources via `azd`.
- Deployed the Azure Function App successfully.
- Created the Azure AI Services account and confirmed the live endpoint is reachable.
- Added the completion and embedding model deployments required by Content Understanding.
- Created the default Foundry project on the AI Services account.
- Created the Content Understanding custom analyzer `excelCsvMvpAnalyzer` (operation Succeeded).

## Changes
- Added package skeleton under src/data_mapping_mvp.
- Added csv_contract.py with contract mapping, validation, and CSV serialization support.
- Added tests/test_csv_contract.py.
- Added function app deployment and Azure service configuration for the live processing flow.
- Added resource group, App Service, AI account, and deployment configuration steps in the Azure workflow.

## Approved Phase 1 Gate
- CSV contract is defined and accepted.
- Validation rules are in place for required fields and confidence threshold.
- Local test suite passes: 4/4 tests passing.
- Azure Function deployment is live and reachable.
- Azure AI resource exists and model defaults are configured.

## Pending Actions
- Run the end-to-end Blob upload test through the Azure Function and confirm CSV output or failure handling.
- Confirm the Function app settings/API version match the working analyzer configuration.
- Revisit infrastructure automation to capture the analyzer + defaults setup as reproducible steps.

## Current Azure Status
- Resource group: `datamapping-demo-rg`
- Function App: `func-data-mapping-dev-001`
- AI account: `cudatamappingmvp001` (Foundry account, `allowProjectManagement: true`)
- Foundry project: `datamapping-proj` (created, `isDefault: true`)
- Region: `eastus` / Azure AI account is live and responding.
- Model deployments: `gpt-4o`, `gpt-4.1-mini`, `gpt-5-mini`, and `text-embedding-3-large`.
- Content Understanding analyzer `excelCsvMvpAnalyzer` created successfully: operation status `Succeeded`.
- Analyzer endpoint base: `https://cudatamappingmvp001.cognitiveservices.azure.com/contentunderstanding`, API version `2025-11-01`.

## Root Cause of the Earlier Analyzer Blocker (resolved)
- The `PATCH /contentunderstanding/defaults` body must use the `modelDeployments` wrapper AND map the prebuilt model aliases to real deployments. Earlier payloads used unwrapped keys (`{"completion":..}`), which were silently ignored, so defaults were never actually persisted.
- The custom analyzer `models` block must reference the aliases `prebuilt-analyzer-completion` / `prebuilt-analyzer-embedding`, not raw deployment names.
- Working defaults map:
  `{"modelDeployments":{"gpt-4o":"gpt-4o","text-embedding-3-large":"text-embedding-3-large","prebuilt-analyzer-completion":"gpt-4o","prebuilt-analyzer-completion-mini":"gpt-4.1-mini","prebuilt-analyzer-embedding":"text-embedding-3-large"}}`
- A default Foundry project (`datamapping-proj`) was also created on the account during remediation.
