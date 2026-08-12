# DataMappingMVP Deployment Wiki

Last updated: 2026-08-12

## Current Status

Deployment has not started yet.

This repository currently contains the MVP plan, README, license, and sample data. It does not yet contain deployable Azure Function code, automated tests, analyzer definitions, `azure.yaml`, Bicep infrastructure, or `.azure/deployment-plan.md`.

Primary planning reference: `ExcelToCsvMvpPlan.md`.

## Operating Rules

1. Deploy sequentially, one phase at a time.
2. Run appropriate unit, validation, or integration tests between phases when a testable artifact exists.
3. Stop and confirm with the operator before moving to the next phase.
4. Do not run `azd up` until Function code, analyzer configuration, infrastructure, Event Grid endpoint wiring, and automated tests are present and validated.
5. Prefer Azure Developer CLI with Bicep as the deployment source of truth.
6. Use Azure Functions Flex Consumption for the Function App unless a validated constraint requires another plan.
7. Use Linux for Python-based Azure Functions.
8. Enable Application Insights for telemetry before production-like testing.
9. Use managed identity and Microsoft Entra authentication where possible; avoid storage account keys in application code.
10. Clean up partial failed deployments before retrying.

## Approval Checkpoints

Each phase must end with one of these statuses:

| Status | Meaning |
|---|---|
| Not started | Work has not begun. |
| In progress | Work is underway, but not ready for review. |
| Blocked | Work cannot continue without a decision, dependency, or fix. |
| Ready for approval | Required work and tests for the phase are complete. |
| Approved | Operator approved moving to the next phase. |
| Completed | Phase was approved and closed. |

Before advancing, record:

1. What changed.
2. What tests or validations ran.
3. Results or known issues.
4. Operator approval.
5. Next phase.

## Deployment Phases

### Phase 0: Repository Baseline

Status: Ready for approval

Goal: Establish current repo state and deployment tracking.

Completed:

- Reviewed `ExcelToCsvMvpPlan.md`.
- Reviewed `README.md`.
- Confirmed `wiki.md` did not already exist.
- Created this deployment wiki.

Validation:

- Repository inspection only. No executable code exists yet, so no unit tests are available for this phase.

Approval required before next phase: Yes.

Next phase: Phase 1, deployment prerequisites and target Azure environment confirmation.

### Phase 1: Deployment Prerequisites

Status: Not started

Goal: Confirm the target Azure environment and MVP contract before generating deployable artifacts.

Required decisions:

- Azure subscription.
- Azure region that supports Azure AI Content Understanding, the required model/analyzer capabilities, and Azure Functions Flex Consumption.
- Resource naming prefix or naming convention.
- CSV output contract.
- Supported file types for MVP. Current plan supports `.xlsx`; `.xlsm` remains unsupported unless separately approved.
- Confidence threshold and validation failure behavior.

Required validation:

- Confirm provider registration and quota.
- Confirm regional availability for required Azure services.
- Confirm sample workbook expected outputs.

Approval required before next phase: Yes.

### Phase 2: CSV Contract and Canonical Schema

Status: Not started

Goal: Create precise input, extraction, validation, and output contracts.

Expected artifacts:

- CSV contract document.
- Canonical extraction schema.
- Sample valid CSV output.
- Sample validation failure payload.

Required tests:

- Unit tests for schema validation rules once code exists.
- Golden-file tests for sample workbook expected CSV output once parser/mapping code exists.

Approval required before next phase: Yes.

### Phase 3: Analyzer Spike

Status: Not started

Goal: Prove representative `.xlsx` extraction with Azure AI Content Understanding before implementing the full event pipeline.

Expected artifacts:

- Analyzer definition or documented analyzer configuration.
- Sample extraction result for each supplied workbook.
- Decision record for accepted extraction quality and known limitations.

Required validation:

- Run sample workbook extraction against the proposed analyzer.
- Compare extracted JSON against the canonical schema.
- Record confidence scores and missing-field behavior.

Approval required before next phase: Yes.

### Phase 4: Function Implementation

Status: Not started

Goal: Build the Azure Function that handles blob events, calls Content Understanding, validates data, maps to CSV, and writes processed or failed outputs.

Expected artifacts:

- Azure Functions project.
- Event Grid-triggered Function or equivalent event handler.
- Content Understanding client wrapper.
- Validation module.
- CSV mapper module.
- Blob storage read/write module.
- Idempotency/state handling.

Required tests:

- Unit tests for validation.
- Unit tests for CSV mapping.
- Unit tests for idempotency behavior.
- Unit tests for error routing to `failed/`.
- Local Function test where feasible.

Approval required before next phase: Yes.

### Phase 5: Infrastructure as Code

Status: Not started

Goal: Generate repeatable Azure deployment configuration.

Expected artifacts:

- `azure.yaml`.
- `.azure/deployment-plan.md`.
- Bicep files for storage, containers, Function App, Flex Consumption plan, managed identity, role assignments, Event Grid, Application Insights, and any required AI resources.
- Parameter files or environment configuration.

Required validation:

- Bicep build/lint.
- Azure what-if.
- Secret/configuration review.
- Policy check if a subscription is selected and policy assignments are available.

Approval required before next phase: Yes.

### Phase 6: Pre-Deployment Validation

Status: Not started

Goal: Confirm code and infrastructure are ready before provisioning.

Required validation:

- Full unit test suite.
- Static analysis or linting where configured.
- Bicep build/lint.
- Azure what-if.
- Deployment plan review.
- Operator approval of target subscription, location, resource group, and expected cost profile.

Approval required before next phase: Yes.

### Phase 7: Provision Azure Resources

Status: Not started

Goal: Provision resources only after code, analyzer, tests, and infrastructure validation are complete.

Expected action:

- Run approved provisioning workflow, likely `azd up`, only after prior approvals.

Required validation:

- Confirm resources were created successfully.
- Confirm managed identity exists.
- Confirm role assignments are present.
- Confirm Application Insights is connected.
- Confirm Event Grid subscription endpoint is configured.

Approval required before next phase: Yes.

### Phase 8: Deployment Smoke Test

Status: Not started

Goal: Prove the deployed MVP can process representative files end to end.

Required validation:

- Upload representative `.xlsx` file to `raw/`.
- Confirm Function invocation.
- Confirm Content Understanding call succeeds.
- Confirm CSV appears in `processed/` for valid input.
- Confirm error JSON appears in `failed/` for invalid input.
- Confirm duplicate event or duplicate upload handling is idempotent.
- Review Application Insights logs and exceptions.

Approval required before next phase: Yes.

### Phase 9: Operational Handoff

Status: Not started

Goal: Document how to operate, monitor, troubleshoot, and resume deployment work.

Expected artifacts:

- Deployment runbook.
- Troubleshooting notes.
- Known limitations.
- Cost and cleanup notes.
- Rollback or teardown instructions.

Required validation:

- Confirm wiki and README reflect the deployed state.
- Confirm no unresolved deployment blockers remain.

Approval required before next phase: Final operator signoff.

## Activity Log

| Date | Phase | Activity | Validation | Approval |
|---|---|---|---|---|
| 2026-08-12 | 0 | Created deployment wiki and recorded current repo baseline. | Repo inspection only; no executable tests exist yet. | Pending operator approval. |

## Open Questions

1. Which Azure subscription should be used?
2. Which Azure region should be targeted?
3. What is the final standardized CSV contract?
4. Which sample workbook should be the first golden test case?
5. Should the MVP archive successfully processed source files?
6. What confidence threshold should route extraction results to `failed/`?
7. Should orchestration use a single Function invocation, Durable Functions, or queue-based continuation after the analyzer spike?

## Next Operator Decision

Approve Phase 0 completion and authorize Phase 1 discovery.

Phase 1 should not create or deploy Azure resources. It should only confirm prerequisites, target environment, contracts, and availability before any deployment artifacts are generated.
