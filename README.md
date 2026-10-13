# VSDD — Verifiable Spec-Driven Development

**A change-driven, evidence-backed workflow from product intent to verified software.**

VSDD combines reusable Agent Skills, versioned engineering artifacts, explicit human approval gates, traceability contracts, and a dependency-free validation CLI. It is designed for mixed AI coding environments and includes an automotive-software profile without requiring every project to use an automotive process model.

> Core rule: no AI-generated assumption silently becomes a requirement, design decision, implementation, or pass result.

## What it is

- **A workflow contract**: one feature/change advances through explicit states, and each transition has evidence-based preconditions.
- **An artifact graph**: IDs link product intent, capabilities, feature/system/software requirements, architecture decisions, tasks, code locations, tests, and verification evidence.
- **A set of skills**: cross-tool `SKILL.md` files under `.agents/skills/` direct an AI agent through each step.
- **A lightweight local CLI**: `scripts/vsdd.py` scaffolds changes, reports state, checks required artifacts and traceability, advances gates, and archives converged changes.
- **A change history**: each iteration remains visible; accepted baseline specifications are separated from proposed deltas.

## Quick start

Requirements: Python 3.10+; no third-party Python packages.

```bash
# 1. Clone/download this repository, or copy .agents/skills and scripts into your project.
python scripts/vsdd.py init --root /path/to/your-project

# 2. Create a change in your project. Use kebab-case names.
python scripts/vsdd.py new add-speed-warning --root /path/to/your-project

# 3. Open the project in an AI coding agent that supports Agent Skills.
# Ask it to follow .agents/skills/vsdd-orchestrate/SKILL.md, then review the artifacts.

# 4. After editing artifacts, inspect and validate.
python scripts/vsdd.py status --root /path/to/your-project
python scripts/vsdd.py validate add-speed-warning --root /path/to/your-project
python scripts/vsdd.py trace add-speed-warning --root /path/to/your-project --id FR-001
# After the converged state and approvals have genuinely been recorded:
python scripts/vsdd.py sync add-speed-warning --root /path/to/your-project --approval REVIEW-123
python scripts/vsdd.py archive add-speed-warning --root /path/to/your-project
```

The initial scaffold is intentionally incomplete: the CLI should report blockers until humans and agents replace placeholders with project-grounded content. It must not manufacture approval or test evidence.

## Recommended operating loop

```text
Explore / clarify intent
    ↓
Feature brief + capability/reuse map
    ↓ human gate: capability boundaries and unresolved questions are explicit
Feature specification + acceptance scenarios
    ↓ human gate: testable, approved intent
System requirements + architecture / ADRs
    ↓ human gate: allocation and interfaces approved
Software requirements + tasks + bidirectional traceability
    ↓ static gate: no broken links, missing task paths, or unresolved blockers
Implement one vertical slice at a time
    ↓ automated checks + review of actual diff
Verify requirements against code with test results and evidence
    ↓
Converge: compare intended behavior with actual repository state
    ├── gap → return to owning artifact, update downstream impacts, repeat
    └── no gap + required evidence → sync approved baseline and archive change
```

A feature is not complete just because code compiles, tasks are checked, or a test was authored. Completion requires the approved acceptance criteria to be mapped to verification evidence and remaining gaps to be dispositioned.

## Project layout after `init`

```text
project/
├── .agents/skills/                 # AI workflow skills (copy if not auto-installed)
├── .vsdd/
│   ├── config.json                 # lightweight project configuration
│   ├── constitution.md             # non-negotiable engineering principles
│   ├── specs/                      # accepted capability/product/system/software baseline
│   ├── changes/<change-id>/        # active proposals, delta artifacts, tasks, evidence
│   └── changes/archive/            # completed change snapshots
└── scripts/vsdd.py                 # local workflow/validation CLI
```

## Skills

| Skill | Responsibility |
|---|---|
| `vsdd-orchestrate` | Select the next valid action, enforce gates, route feedback to the owning artifact |
| `vsdd-explore` | Clarify outcome, actors, boundaries, existing behavior, unknowns and capability candidates |
| `vsdd-capabilities` | Discover, compare, reuse, extend or propose capabilities with evidence |
| `vsdd-specify` | Author feature behavior and acceptance scenarios without prematurely choosing implementation |
| `vsdd-architecture` | Derive system requirements, architecture options, interfaces, constraints and allocation |
| `vsdd-plan` | Derive software requirements, ordered tasks, code ownership/path hypotheses and test mapping |
| `vsdd-implement` | Execute small traceable slices; inspect repository conventions; keep task/code/test links current |
| `vsdd-verify` | Execute checks and collect requirement-level verification evidence |
| `vsdd-converge` | Compare required behavior with actual code and evidence, append gaps and loop |
| `vsdd-change` | Assess change impact, revise deltas and invalidate/re-run affected downstream artifacts |

## CLI reference

Run `python scripts/vsdd.py --help` for current syntax.

- `init`: create VSDD folders and a project constitution/config if missing.
- `new <slug>`: scaffold a feature/change from templates.
- `status`: show active changes and stage.
- `validate [slug]`: validate artifact structure, unresolved markers, IDs and traceability links; return non-zero on blockers.
- `advance <slug> --to <stage>`: attempt the next state transition only when its gate passes.
- `trace <slug> --id <ID>`: print one-hop incoming/outgoing traceability relations.
- `sync <slug> --approval <ref> [--artifact ...]`: promote selected approved artifacts after convergence; existing baseline files require explicit `--overwrite` and are backed up under `.vsdd/specs/history/`.
- `archive <slug>`: archive only a converged change; preserves the audit snapshot.

## Design principles

1. **Source-grounded, not guess-driven.** Record source and status for each material requirement or decision. Unknowns are explicit.
2. **One approved baseline, many proposed changes.** Do not silently rewrite accepted requirements when a new feature arrives.
3. **The smallest useful vertical slice.** Each slice traverses requirement → task → code → test/evidence rather than completing all documentation in a big-bang sequence.
4. **Bidirectional traceability.** Every in-scope requirement has a planned verification path; every material code change has a reason and acceptance target.
5. **Human authority at semantic gates.** AI may draft and analyze; it cannot approve its own safety/sign-off decisions.
6. **Evidence beats status.** A checkbox is workflow state, not proof. The actual command output, test report, review decision, or measured result is evidence.
7. **Change-aware iteration.** When an upstream node changes, identify downstream artifacts and verification results that may be invalidated.
8. **Tool-neutral core.** Skills are plain Markdown; CLI uses Python standard library; tool-specific wrappers can be added later.

## Inspiration and differentiation

VSDD borrows spec clarification, planning, task sequencing, analysis and convergence habits from [GitHub Spec Kit](https://github.com/github/spec-kit), plus the change-focused artifacts, reversible iteration, formal-spec synchronization and archival model from [OpenSpec](https://github.com/Fission-AI/OpenSpec). VSDD adds explicit capability reuse, code allocation, source/status metadata, evidence-linked verification and a machine-checkable traceability contract.

## Safety boundary for automotive use

This kit is a workflow aid, not a functional-safety certification tool and not a substitute for required engineering processes, safety analyses, reviews, configuration management or qualified approval. A project must load its applicable standards, hazard analyses, platform contracts, coding standards and test policies as sources of truth. The example deliberately leaves unspecified thresholds, timing, priorities, interfaces and failure behavior unresolved rather than inventing them.

## License

MIT. See `LICENSE`.
