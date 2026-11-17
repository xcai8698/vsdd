# Quality gates

A change should not progress when its required artifacts are missing, empty, contain unresolved placeholders, or have broken traceability.

## Gate checklist

- **Intent:** source, scope, constraints, assumptions, and open questions are explicit.
- **Reuse:** existing capabilities were searched and a decision is justified with repository evidence.
- **Specification:** acceptance criteria are observable and testable; unknown product decisions remain open.
- **Architecture:** system requirements are allocated to components/interfaces; material decisions and alternatives are recorded.
- **Plan:** software requirements, tasks, code changes and tests have trace links.
- **Implementation:** actual repository conventions and interfaces were inspected; diff is scoped and reviewed.
- **Verification:** commands/procedures, environment, actual outcomes and evidence references are recorded.
- **Convergence:** each acceptance criterion is covered; gaps are accepted with rationale or resolved; stale evidence is rerun.
- **Baseline:** only approved converged artifacts are synchronized; existing baselines are reviewed and backed up before overwrite.

## Evidence record

For every verification, capture at least: ID, linked requirement/acceptance criterion, environment/configuration, command or procedure, actual result, pass/fail/blocked status, and evidence location. “Test added” is not the same as “test passed.”

## Actionable traceability audit

Use `vsdd audit <change-id>` for a finding-oriented report. Markdown output is intended for engineering review; JSON output is a versioned report bundle for CI and the standalone graph viewer:

```bash
vsdd audit add-speed-warning --format markdown
vsdd audit add-speed-warning --format json --output .vsdd/reports/audit.json
```

Each finding identifies the affected node/edge, missing relation classes, known reachable descendants, responsible artifact, and recommended repair stage. A BLOCKED audit returns a non-zero exit code while preserving the report file. Suggestions guide engineers to the owning artifact; the command never edits a requirement or trace edge automatically.
