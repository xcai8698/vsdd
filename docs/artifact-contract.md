# Artifact contract

## Stable identifiers

Use stable IDs for engineering entities: `FB-001` Feature, `SRC-001` source obligation, `FR-001` Feature requirement, `AC-001` acceptance criterion, `SYS-001` system requirement, `ARCH-001` architecture element, `SWE-001` software requirement, `T-001` implementation task and `TC-001` test case. Code files use `FILE:<repository-relative-path>`.

Never recycle an ID for a different meaning. Mark replaced items as superseded and link to the replacement.

## Canonical traceability graph

The single canonical relationship store for each change is:

`.vsdd/changes/<change-id>/traceability.json`

It contains two top-level collections:

- `nodes[]`: one record per source, Feature, requirement, architecture element, task, code file or test case. Each node has a stable `id`, `type`, human-readable `title`, and an `artifact` / `anchor` pointing back to the authoritative artifact.
- `edges[]`: one directed record per relationship, with `id`, `source`, `target`, `type`, lifecycle `status` and `evidence[]`.

Do not store reverse copies of edges. An edge `SRC-001 → FR-001` is traversed upstream and downstream by the CLI / viewer. This prevents duplicated directions from drifting out of sync.

Validate the JSON structure against `.vsdd/schemas/traceability.schema.json`. The Markdown artifacts remain the authoritative text; JSON is the graph index, not a second copy of requirement prose.

## Node audit states and colors

Node health is derived from the graph and the selected workflow stage; it is not manually written into the graph JSON.

| State | Color | Meaning |
|---|---|---|
| `complete` | green | Every link type required at the current stage is present and endpoints are valid |
| `incomplete` | amber | The node has some valid links, but one or more required upstream/downstream link types or evidence are missing |
| `broken` | red | A relation has a dangling endpoint, invalid endpoint/type pairing, duplicate or malformed relation |
| `orphan` | red with dashed outline | The node has no valid incoming or outgoing edge |
| `excluded` | gray | A source obligation is explicitly out-of-scope or deferred with rationale |

Edges use green for structurally valid relationships, amber for blocked/invalidated or not yet accepted at convergence, and red for broken endpoints or invalid relationship types.

The current stage determines which links are expected. For example, a Feature Requirement must link to its Feature, at least one in-scope source, and an Acceptance Criterion from `specified` onward. A SWE must link to a SYS, an implementation task and a test case from `planned` onward. A task must link to a real `FILE:` node from `verifying` onward.

## Review and quality gates

Run:

```bash
vsdd trace-check <change-id>
vsdd trace-check <change-id> --stage planned
vsdd trace <change-id> --id FR-001 --direction both
```

The audit detects:
- IDs declared in Markdown but missing from graph nodes, and graph nodes absent from their authoritative Markdown artifact;
- duplicate IDs, duplicate edges, unknown/dangling endpoints and invalid relationship types;
- orphan nodes and nodes missing required upstream/downstream relationship classes;
- graph source scope that disagrees with the source register;
- missing edge rationale/evidence, missing implementation file links and absent verification records.

The standalone `tools/traceability-viewer.html` loads `traceability.json` in a browser, draws the graph, colors each node/edge using the audit state, and lists review issues. The viewer is a visual graph review tool; `vsdd trace-check` remains the authoritative repository-aware check because it also reads the Markdown source inventory and requirement artifacts.

## Semantic completeness is a reviewed obligation

No graph checker can infer that the source inventory itself captured every sentence or intent in a natural-language PRD. Before the `specified` gate, a responsible reviewer must confirm that `source-register.md` is exhaustive and record the reviewer and real review reference. Each Feature Spec completeness dimension must be marked applicable with FR/AC links, or not applicable with rationale and a review record.

A relationship is not proven merely because an ID is mentioned in prose: the edge should exist and point to evidence where appropriate. Do not invent product thresholds, timing, priorities, interfaces or safety behavior.
