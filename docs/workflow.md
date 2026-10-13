# VSDD workflow

## State sequence

`intake → capability-mapped → specified → architecture-ready → planned → implementing → verifying → converged → archived`

Each state describes the maturity of a change, not a promise that a particular command or document exists. Advance one state at a time. If upstream intent changes, identify impacted downstream artifacts and rerun affected checks.

## Stage outcomes

| Stage | Required outcome |
|---|---|
| intake | Source-grounded feature brief, scope and unknowns |
| capability-mapped | Evidence-backed reuse/extend/create decision |
| specified | Observable scenarios and approved acceptance criteria |
| architecture-ready | System requirements, component allocation, interfaces and decisions |
| planned | Software requirements, vertical-slice tasks and traceability |
| implementing | Code and tests developed in small slices |
| verifying | Actual verification procedures/results and limitations recorded |
| converged | No unaccepted gaps; traceability and evidence reviewed |
| archived | Approved change snapshot retained for audit |

## Iteration rule

A failed check returns the change to the artifact that owns the issue. Do not repair symptoms downstream while leaving the source requirement or architecture inconsistent. If a requirement changes, mark dependent evidence stale and plan re-verification.

## Human approvals

Approval references must point to real review/decision records. A CLI argument merely records a reference supplied by the operator; it does not authenticate the person, prove the review happened, or replace a safety/process approval.
