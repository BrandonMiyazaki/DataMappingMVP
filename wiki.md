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

Status: Completed

Goal: Establish current repo state and deployment tracking.

Completed:

- Reviewed `ExcelToCsvMvpPlan.md`.
- Reviewed `README.md`.
- Confirmed `wiki.md` did not already exist.
- Created this deployment wiki.

Validation:

- Repository inspection only. No executable code exists yet, so no unit tests are available for this phase.

Approval: Approved by operator on 2026-08-12.

Next phase: Phase 1, deployment prerequisites and target Azure environment confirmation.

### Phase 1: Deployment Prerequisites

Status: Completed

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

Findings recorded on 2026-08-12:

- Azure extension auth is signed in as `brandon_admin@miyazaki.dev` in tenant `Miyazaki.Dev`.
- Target subscription discovered: `ME-MngEnvMCAP973733-bmiyazaki-1` / `4fe102d0-58c1-40b4-aa01-9542624b1711`.
- Azure CLI context matches the Azure extension subscription and tenant.
- Azure CLI is installed: `azure-cli 2.86.0`.
- Azure Developer CLI is installed but outdated: `azd 1.11.1`; latest reported by the tool is `1.30.0`.
- Azure Functions Core Tools is not installed or not on PATH: `func` was not found.
- Sample data files found:
	- `SampleData/synthetic_assembly_line_test_measurements_raw.xlsx`
	- `SampleData/assembly_line_measurement_mapping_output.xlsx`
- Planned resource types are regionally available in multiple regions, including `eastus`, `eastus2`, `centralus`, `westus2`, and `westus3`.
- Candidate region checked: `eastus`.
- `eastus` quota check did not show an obvious storage quota blocker: storage accounts limit `250`, used `0`.
- `eastus` quota check returned `No Limit` style responses for `Microsoft.Web/sites`, `Microsoft.EventGrid/systemTopics`, and `Microsoft.Insights/components`.
- `eastus` Cognitive Services quota entries show unused quota for relevant account/model capacity categories, but the exact Content Understanding and Foundry model deployment choices still need confirmation.
- Operator-selected target region: `westus2`.
- `westus2` quota check did not show an obvious storage quota blocker: storage accounts limit `250`, used `9`.
- `westus2` quota check returned `No Limit` style responses for `Microsoft.Web/sites`, `Microsoft.EventGrid/systemTopics`, and `Microsoft.Insights/components`.
- `westus2` Cognitive Services quota entries show available AIServices S0 regional resource capacity and unused capacity for relevant document/model categories; exact Content Understanding and model deployment choices still need confirmation during analyzer setup.
- Azure Policy assignments are present at subscription and management-group scopes, including Defender/compliance initiatives, MCAPSGov deny/audit/deploy policies, MFA enforcement for write/delete actions, and a policy named `Block Azure RM Resource Creation`.
- Current Microsoft documentation confirms Azure Content Understanding is a Foundry resource and supports `.xlsx`; `.xlsm` is also listed as technically supported by service limits, but it remains out of MVP scope unless the operator separately approves macro-enabled uploads.

Phase 1 operator decisions recorded on 2026-08-12:

- Approved target subscription: `ME-MngEnvMCAP973733-bmiyazaki-1` / `4fe102d0-58c1-40b4-aa01-9542624b1711`.
- Approved target region: `westus2`.
- Approved first golden input workbook: `SampleData/synthetic_assembly_line_test_measurements_raw.xlsx`.
- Approved first expected output/contract workbook: `SampleData/assembly_line_measurement_mapping_output.xlsx`.
- Approved default processing behavior: archive successful source files.
- Approved initial confidence threshold: `0.80`.
- Approved tooling setup before Function implementation: upgrade `azd` and install Azure Functions Core Tools.
- Governance risk accepted for now: discovered policy assignments may block resource creation until tested by what-if/provisioning in a later approved phase.

Approval: Approved by operator on 2026-08-12.

### Phase 2: CSV Contract and Canonical Schema

Status: In progress

Goal: Create precise input, extraction, validation, and output contracts.

Expected artifacts:

- CSV contract document.
- Canonical extraction schema.
- Sample valid CSV output.
- Sample validation failure payload.

Findings recorded on 2026-08-12:

- The approved sample files have `.xlsx` extensions but are not ZIP-based `.xlsx` files.
- File signatures show OLE compound binary format: `D0 CF 11 E0 A1 B1 1A E1`.
- `openpyxl` cannot read the files because they are not ZIP-based workbooks.
- `xlrd` cannot find a workbook stream inside the OLE containers.
- OLE stream inspection shows both files contain `EncryptedPackage` plus DRM-related `DataSpaces` streams.
- Current conclusion: the sample files are encrypted/protected Office packages and cannot be used to infer the CSV contract or canonical schema in this environment.

Phase 2 recovery action started on 2026-08-12:

- Operator clarified that `SampleData/synthetic_assembly_line_test_measurements_raw.xlsx` is the raw input workbook.
- Operator clarified that `SampleData/assembly_line_measurement_mapping_output.xlsx` is the desired output workbook.
- Retrying workbook inspection using the raw/output roles rather than treating the filenames as ambiguous.

Current blocker remains:

- Provide unencrypted sample workbooks, or
- Provide an explicit CSV contract manually, or
- Open/export the protected expected-output workbook to CSV/XLSX outside this environment and commit the unprotected export.

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
| 2026-08-12 | 0 | Created deployment wiki and recorded current repo baseline. | Repo inspection only; no executable tests exist yet. | Approved by operator. |
| 2026-08-12 | 1 | Completed deployment prerequisite discovery. | Azure auth, subscription, local tooling, policy, region availability, `eastus` and `westus2` quota, docs, and sample data checks completed. | Approved by operator. |
| 2026-08-12 | 2 | Retried CSV contract and canonical schema work using the clarified raw/output file roles. | In progress; workbook contents still need to be read before drafting the contract. | Pending. |

## Open Questions

1. What resource naming prefix should be used for generated Azure resources?
2. Should orchestration use a single Function invocation, Durable Functions, or queue-based continuation after the analyzer spike?
3. Are there additional expected output examples beyond the approved first workbook pair?
4. Can you provide unencrypted versions of the approved sample workbooks, or an explicit CSV contract to use instead?

## Next Operator Decision

Review the Phase 2 contract/schema draft if workbook contents can be read; otherwise provide unencrypted workbook exports or an explicit CSV contract.

Phase 2 should create the CSV contract and canonical schema from the approved sample workbook pair. It should not create or deploy Azure resources.
