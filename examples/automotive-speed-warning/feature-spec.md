# Feature specification: speed warning

## Source and status
- Source: illustrative feature brief in this folder
- Status: proposed; not customer-approved

## Scenario
### FR-001: Configured speed limit warning
**Given** a valid configured speed limit and an available vehicle-speed input
**When** the approved exceedance condition is met
**Then** the system requests the approved visual and audible warning behavior

## Acceptance criteria
- AC-001: Verify the approved exceedance condition and warning output against the product-owned requirement. The condition, timing, priority and output semantics remain open in this example.

## Open decisions
Exceedance equality/hysteresis, debounce/filtering, onset/clear timing, warning priority, HMI signal names, failure handling, and safety classification.


## Completeness review
| dimension | applicability | FR / AC IDs | rationale / evidence | review record |
|---|---|---|---|---|
| normal | applicable | FR-001 / AC-001 | Illustrative happy path only | EXAMPLE-ONLY |
| boundary | unresolved |  | Equality and hysteresis not defined |  |
| invalid-input | unresolved |  | Signal validity not defined |  |
| state-transition | unresolved |  |  |  |
| failure | unresolved |  | Failure behavior is not supplied |  |
| recovery | unresolved |  |  |  |
| timing-performance | unresolved |  | Timing not supplied |  |
| interface-semantics | unresolved |  | Signal/interface names not supplied |  |
| safety-security-diagnostics | unresolved |  | Classification and diagnostics not supplied |  |
