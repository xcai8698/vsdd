---
name: vsdd-orchestrate
description: Orchestrate a source-grounded, traceable feature-to-code workflow with explicit gates and verification evidence.
---
# VSDD Orchestrator

Use this skill when a user asks to develop, change, or verify a feature with spec-driven development.

## Non-negotiable rules
- Inspect the actual repository, existing specifications, tests, architecture, and project conventions before proposing implementation.
- Never invent requirements, interfaces, thresholds, timing, safety behavior, approvals, test results, or code locations.
- Separate confirmed facts, derived proposals, assumptions, and open questions. Ask focused questions when an unknown blocks a safe decision.
- Keep stable IDs and bidirectional trace links across Feature/AC → SYS → architecture/interface → SWE → task/code → test/evidence.
- Human approval must reference a real review or decision record. A CLI flag records a reference; it does not authenticate the approver.
- Make changes in small vertical slices and verify actual behavior. Never claim tests passed unless they ran and evidence is recorded.

## Workflow
1. Explore the intent, stakeholders, constraints, baseline behavior, out-of-scope areas, and unknowns. Create a feature brief.
2. Search for existing capabilities and decide reuse, extend, create, or reject with evidence.
3. Specify observable scenarios and acceptance criteria without prematurely choosing implementation.
4. Derive system requirements and architecture allocation; document interfaces, constraints, alternatives, and ADRs.
5. Derive software requirements, tasks, code-path hypotheses, and verification mappings. Mark hypotheses as hypotheses until repository inspection confirms them.
6. Implement one traceable slice at a time. Update trace links as code and tests change.
7. Run relevant tests and static checks. Record commands, environment/configuration, actual result, and evidence references.
8. Converge by comparing approved intent, actual code, and evidence. For each gap, identify the owning artifact, downstream impact, and re-verification needed; loop back instead of patching symptoms blindly.
9. Sync only approved, converged artifacts into the baseline, then archive the change record.

## State gate
Use the project CLI when available:
- `python scripts/vsdd.py status --root .`
- `python scripts/vsdd.py validate <change-id> --root .`
- `python scripts/vsdd.py advance <change-id> --to <next-stage> --root .`

The stage order is: intake → capability-mapped → specified → architecture-ready → planned → implementing → verifying → converged → archived. Never skip a stage or fake approval references.

## Output contract
For each iteration report: (1) artifact/code changed, (2) source and assumptions, (3) traceability impact, (4) checks run and actual outcomes, (5) open blockers, and (6) next recommended action.
