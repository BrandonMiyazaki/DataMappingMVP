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

## Changes
- Added package skeleton under src/data_mapping_mvp.
- Added csv_contract.py with contract mapping, validation, and CSV serialization support.
- Added tests/test_csv_contract.py.

## Approved Phase 1 Gate
- CSV contract is defined and accepted.
- Validation rules are in place for required fields and confidence threshold.
- Local test suite passes: 4/4 tests passing.
- Ready to advance to Azure Function and deployment scaffolding work.

## Pending Actions
- Complete the live Azure AI Content Understanding configuration for analyzer registration.
- Verify the analyzer creation endpoint and defaults against the live AI resource, and resolve the current 404 blocker.
- Validate the end-to-end Excel upload path through the Azure Function and Blob workflow.
- Create infrastructure-as-code and deployment workflow files if additional automation is needed.

## Current Azure Status
- Azure Function deployment is running successfully in the live resource group.
- The AI account exists and returns the Content Understanding defaults payload.
- Model deployments for the required embedding and completion models have been added successfully.
- The remaining blocker is that the analyzer creation request keeps returning `404 Resource Not Found` even though the default route is live, indicating the resource needs the Content Understanding capability enabled or the service needs to be created as a Foundry-backed resource instead of only the standard AI Services account.
