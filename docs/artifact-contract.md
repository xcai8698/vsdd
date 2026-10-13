# Artifact contract

## Stable identifiers

Use stable IDs for material engineering entities, for example: `FB-001` feature brief, `CAP-001` capability, `FR-001` feature requirement/scenario, `AC-001` acceptance criterion, `SYS-001` system requirement, `ADR-001` architecture decision, `SWE-001` software requirement, `T-001` task, `TC-001` test case, and `VE-001` verification evidence.

Never recycle an ID for a different meaning. Mark replaced items as superseded and link to the replacement.

## Traceability CSV

The canonical edge list uses columns:

`source_id,target_id,relationship,status,evidence`

Suggested relationships: derives, allocates, implemented-by, verified-by, constrains, supersedes, impacts. Suggested statuses: proposed, approved, verified, invalidated, not-applicable.

Example chain:

`FR-001 → SYS-001 → SWE-001 → T-001 → TC-001 → VE-001`

This chain should be navigable in both directions. A relationship is not proven merely because an ID is mentioned in prose: the edge should exist and point to evidence where appropriate.

## Source and confidence

For every material requirement or decision, preserve its source. Distinguish confirmed source statements, derived proposals, assumptions, and unresolved questions. Do not infer product thresholds, timing, priorities, interfaces or safety behavior without authoritative inputs.
