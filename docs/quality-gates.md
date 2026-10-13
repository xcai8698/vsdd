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
