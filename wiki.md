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
- Realigned the solution to the real sample domain (assembly-line test-measurement normalization) using SampleData raw + desired-output workbooks.
- Rebuilt the CSV contract to the 25-column desired output with per-record validation and multi-row serialization.
- Added an enrichment layer (constants, work-order propagation, station-ID normalization, spec-limit reference table, result synonyms).
- Added per-record resilience: valid rows are mapped to CSV and invalid records are quarantined instead of failing the whole file.
- Validated `.xlsx` end-to-end against the live analyzer; upgraded the completion model to `gpt-5.2` and tightened the analyzer prompt (multi-measurement splitting + anti-fragmentation).

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
- Run a true Blob-triggered end-to-end test (storage `publicNetworkAccess` is policy-forced to Disabled, blocking direct test uploads from a workstation); the extraction + mapping path is already validated against the live analyzer using the raw sample workbook.
- Decide whether to consolidate analyzer versions (v1 invoice + v2 + v3) once the schema is final; delete requires elevated permission (data-plane DELETE returns 401 for the current identity).
- Revisit infrastructure automation to capture the analyzer + defaults + gpt-5.2 setup as reproducible steps.

## Current Azure Status
- Resource group: `datamapping-demo-rg`
- Function App: `func-data-mapping-dev-001` (setting `CONTENT_UNDERSTANDING_ANALYZER_ID=assemblyMeasurementAnalyzer3`)
- AI account: `cudatamappingmvp001` (Foundry account, `allowProjectManagement: true`)
- Foundry project: `datamapping-proj` (created, `isDefault: true`)
- Region: `eastus` / Azure AI account is live and responding.
- Model deployments: `gpt-4o`, `gpt-4.1-mini`, `gpt-5-mini`, `gpt-5.2` (GlobalStandard, 50K TPM), and `text-embedding-3-large`.
- CU default `prebuilt-analyzer-completion` is mapped to `gpt-5.2` (the doc-recommended analyzer model).
- Active analyzer `assemblyMeasurementAnalyzer3` (measurement-normalization schema with anti-fragmentation prompt).
- Analyzer endpoint base: `https://cudatamappingmvp001.cognitiveservices.azure.com/contentunderstanding`, API version `2025-11-01`.

## Latest End-to-End Result (raw sample workbook)
- gpt-4o extracted only the Torque section (13 records). gpt-5.2 extracts all 7 test categories and all 4 serials.
- With gpt-5.2 + anti-fragmentation prompt + resilient mapping: 59 valid rows, 16 quarantined value-fragments (down from 52 with the fragmentation-prone prompt).
- Core columns (Record_ID, Work_Order, Serial_Number, Line, Shift, Station_ID, Test_Category, Measurement_Name, Result, Attempt_Number, Source_Record_Text) are 100% filled; spec limits fill where the reference table matches.

## Root Cause of the Earlier Analyzer Blocker (resolved)
- The `PATCH /contentunderstanding/defaults` body must use the `modelDeployments` wrapper AND map the prebuilt model aliases to real deployments. Earlier payloads used unwrapped keys (`{"completion":..}`), which were silently ignored, so defaults were never actually persisted.
- The custom analyzer `models` block must reference the aliases `prebuilt-analyzer-completion` / `prebuilt-analyzer-embedding`, not raw deployment names.
- Working defaults map:
  `{"modelDeployments":{"gpt-4o":"gpt-4o","gpt-5.2":"gpt-5.2","text-embedding-3-large":"text-embedding-3-large","prebuilt-analyzer-completion":"gpt-5.2","prebuilt-analyzer-completion-mini":"gpt-4.1-mini","prebuilt-analyzer-embedding":"text-embedding-3-large"}}`
- A default Foundry project (`datamapping-proj`) was also created on the account during remediation.

