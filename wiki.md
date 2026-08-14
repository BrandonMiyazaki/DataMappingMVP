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
- Confirmed the Content Understanding defaults endpoint returns the configured deployment mapping.

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
- Resolve the remaining Azure AI Content Understanding service configuration issue preventing analyzer creation.
- Validate whether the current resource must be a Foundry-backed or Content Understanding-enabled AI resource for custom analyzer registration.
- Create the custom analyzer once the service capability is confirmed.
- Run the end-to-end Blob upload test through the Azure Function and confirm CSV output or failure handling.
- Revisit infrastructure automation only if the resource path still needs cleanup after the analyzer issue is resolved.

## Current Azure Status
- Resource group: `datamapping-demo-rg`
- Function App: `func-data-mapping-dev-001`
- AI account: `cudatamappingmvp001`
- Region: `eastus2` / configured Azure AI account is live and responding.
- Model deployments created successfully: `gpt-4o`, `gpt-4.1-mini`, and `text-embedding-3-large`.
- Content Understanding defaults endpoint is returning a valid payload: the completion and embedding deployment names are set.
- Current blocker: analyzer creation is still failing with `404 Resource Not Found` from the Content Understanding analyzer endpoint even after the defaults are configured, which indicates the service capability is not yet correctly exposed on the active Azure AI resource. The likely remediation is to use a proper Content Understanding-capable resource or re-create the AI resource in the correct Foundry-backed configuration.
