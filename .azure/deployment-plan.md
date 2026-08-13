# Azure Deployment Plan

## Project
DataMappingMVP

## Goal
Deploy the Excel-to-CSV MVP pipeline to Azure using Blob Storage, Event Grid, Azure Functions, and Azure AI Content Understanding.

## Approved scope
- Use Python Azure Functions for the processing host.
- Use a lifecycle starting from raw/.xlsx blob upload.
- Use Azure AI Content Understanding for structured extraction.
- Convert analyzer output to the standardized CSV contract.
- Write successful output to processed/ and failures to failed/.

## Target environment
- Subscription: confirm before deployment
- Region: confirm before deployment; must support Azure AI Content Understanding and Flex Consumption/Functions requirements
- Resource group: rg-data-mapping-mvp-dev

## Required resources
- Storage account with raw, processed, failed, archive, state, and eventgrid-deadletter containers
- Application Insights
- Azure Function App (Flex Consumption target)
- Event Grid system topic or custom topic for blob-created events
- Azure AI Content Understanding resource and custom analyzer

## Prerequisites
- Azure subscription access with permission to create resource groups and resources
- Region validated for Content Understanding and Functions support
- Azure CLI and Azure Developer CLI installed
- Local Python virtual environment for function development
- Managed identity enabled on the Function App

## Workstream checklist
- [x] Define and validate the CSV contract locally
- [x] Implement local CSV mapping and validation logic
- [x] Add function app scaffold and parser fixture tests
- [ ] Confirm target Azure subscription and region
- [ ] Validate Content Understanding analyzer behavior against the sample workbook
- [ ] Provision storage and observability resources
- [ ] Provisions Function App, Event Grid wiring, and managed identities
- [ ] Add analyzer resource and deployment configuration
- [ ] Run deployment validation and smoke tests

## Deployment sequence
1. Confirm subscription and region.
2. Run azd provision.
3. Validate created resources and RBAC.
4. Run funcional smoke tests against a sample file.
5. Enable Event Grid event flow and verify idempotency behavior.

## Operational guardrails
- Use managed identity, not storage account keys.
- Keep local.settings.json out of source control.
- Treat .xlsm as unsupported until an explicit analyzer validation proves it.
- Do not run workbook macros.
- Keep a state record for idempotency and duplicate Event Grid delivery handling.
