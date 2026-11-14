<!-- project-ssot:agents-contract begin version=3 -->
# Agent Instructions

## Project SSOT Documentation Rules

This repository uses a docs-based Single Source of Truth system.
Before project changes, read `docs/README.md` and `docs/project-state.md`; judge current state only by `docs/project-state.md`.

## Document Read Routing

Read only the documents needed for the question or task.

| Question or task | Primary reference |
| --- | --- |
| Current state, features, priorities, constraints, or technical debt | `docs/project-state.md` |
| Overall architecture and system behavior | `docs/architecture/system-overview.md` |
| Important decisions and reasons | The relevant ADR in `docs/decisions/` |
| Completed work and history | The relevant monthly file in `docs/journal/` |
| Unadopted ideas | The relevant file in `docs/ideas/` |
| Document roles and maintenance rules | `docs/README.md` |

Read detailed architecture documents only when they are linked from `system-overview.md` and relevant; do not guess filenames.
Do not duplicate detailed project knowledge in `AGENTS.md`.

## Document Write Routing

- When current state, features, priorities, constraints, technical debt, or roadmap changes, update `docs/project-state.md`.
- When system structure or behavior changes, update the relevant `docs/architecture/*`.
- Record an important decision in a new `docs/decisions/ADR-XXX-*.md`.
- Record completed work in `docs/journal/YYYY-MM.md`.
- Record unadopted ideas in `docs/ideas/YYYY-MM-*.md`, and promote them to official documents when adopted.

Do not document project facts that are not established by the request or verified implementation. If the change scope is materially ambiguous, report the ambiguity instead of broadening SSOT changes by inference.
When one change spans multiple roles, update every related SSOT document. Follow `docs/README.md` for detailed rules.
<!-- project-ssot:agents-contract end -->
