# Adoption guide

1. Clone this repository and review `.vsdd/constitution.md`.
2. Copy `.agents/skills/` and `scripts/vsdd.py` into the product repository, or run the CLI from this repository with `--root /path/to/product`.
3. Run `python scripts/vsdd.py init --root /path/to/product`.
4. Create a change with `python scripts/vsdd.py new <kebab-case-feature> --root /path/to/product`.
5. Ask your coding agent to follow `.agents/skills/vsdd-orchestrate/SKILL.md`.
6. Review each artifact at its semantic gate. Never pass a made-up approval reference to move the workflow forward.
7. Run `status`, `validate`, and `trace` as the artifacts evolve.
8. After convergence, sync only approved artifacts and archive the change record.

Start with one pilot feature and tune templates/gates to your real engineering process before broad adoption. For automotive work, link project-owned requirements, interface definitions, safety/security analyses, coding rules, test policies, and configuration-management records. VSDD itself does not establish compliance with any standard.
