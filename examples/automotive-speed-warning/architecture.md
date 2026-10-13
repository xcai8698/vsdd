# Architecture: speed warning

## Context and constraints
This is an illustrative allocation only. Inspect the actual vehicle platform architecture, signal contracts, sound arbitration and telltale ownership before selecting components.

## Candidate flow
Vehicle speed + configured limit → exceedance evaluation → warning request → sound arbitration / telltale presentation

## Open questions
- Authoritative signal names, units, validity and update rates
- Owner of exceedance calculation and calibration
- Sound and telltale arbitration/priority
- Degraded behavior, diagnostics and safety/security constraints
