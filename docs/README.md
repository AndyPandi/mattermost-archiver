<!-- project-ssot:docs-constitution version=3 -->
# Documentation Constitution

This document defines the documentation system for `mattermost-archiver`.
People and AI agents use this as the shared documentation standard.

## Core Principle

### Single Source of Truth

The current project state must be recorded only in `docs/project-state.md`.

Do not duplicate current phase, current features, current priorities, current constraints, technical debt, or roadmap in other documents.

### Document Role Separation

Each document has one role.

- `docs/project-state.md`: what is true now
- `docs/architecture/*`: how the system works now
- `docs/decisions/*`: why important decisions were made
- `docs/journal/*`: when completed work happened
- `docs/ideas/YYYY-MM-brainstorming.md`: brainstorming and candidate ideas that are not official current state

## Document Priority

When documents conflict, use this order:

1. `docs/project-state.md`
2. `docs/architecture/*`
3. `docs/decisions/*`
4. `docs/journal/*`
5. `docs/ideas/*`

Higher-priority documents win. If documentation and implementation disagree, treat the documentation as a candidate for correction unless the implementation is clearly wrong.

## Document Structure

```text
docs/
├── README.md
├── project-state.md
├── ideas/
│   ├── YYYY-MM-brainstorming.md
│   ├── YYYY-MM-storyboard.md
│   ├── YYYY-MM-user-flows.md
│   └── YYYY-MM-notes.md
├── architecture/
│   └── system-overview.md
├── decisions/
│   └── ADR-XXX-*.md
└── journal/
    └── YYYY-MM.md
```

## `docs/project-state.md`

`docs/project-state.md` is the Single Source of Truth for current state.

Include:

- Project purpose
- Current architecture summary
- Current features
- Current priorities
- Known constraints
- Technical debt
- Roadmap

Do not include:

- Work history
- Meeting notes
- Temporary notes
- Past decision details
- Detailed component documentation

### Optional Current-State Evidence

An important current feature, constraint, or technical-debt list item may be followed immediately by an optional evidence marker.

```md
- The payment API is available in production.
  <!-- project-ssot:evidence {"claim_id":"payment-api","verified_on":"2026-07-20","sources":[{"kind":"repository","path":"src/payments/api.py"},{"kind":"repository","path":"tests/test_payments.py"},{"kind":"external","reference":"deploy-2026-07-20"}]} -->
```

- Keep each `claim_id` unique in the project.
- A `repository` source names an existing regular file inside the project.
- An `external` source records a human-traceable value such as a deployment or operations check identifier.
- `verified_on` records the last date on which the evidence was checked.
- Evidence supports review but does not automatically prove the meaning of the claim.
- Keep the current fact itself only in this document; do not duplicate current state in the marker.

The following checker does not execute documentation content or commands. It validates marker shape, duplicate JSON keys and sources, dates, repository-path existence and safety, and common secret shapes.

```bash
python3 <project-ssot-skill-dir>/scripts/check_ssot_evidence.py <target-project-root>
```

Evidence remains optional for existing Contract v3 projects. Use `--require` only after the project explicitly adopts strict coverage for actual list claims under Current Features, Known Constraints, and Technical Debt.

## `docs/architecture/`

Architecture documents describe how the system currently works.

Fixed file:

- `system-overview.md`: overall structure and main flows

Create project-specific detailed architecture documents by responsibility when needed. Every detail document must be linked from the Related Documents section of `system-overview.md` together with its role. Do not guess unlinked filenames.

Architecture documents explain current structure, not work phases or priorities.

## `docs/decisions/`

Store Architecture Decision Records here.

Purpose:

- Record important decisions and their reasons.
- When a decision changes, create a new ADR instead of rewriting the old one.

Filename format:

```text
docs/decisions/ADR-001-documentation-single-source-of-truth.md
docs/decisions/ADR-002-example-decision.md
docs/decisions/ADR-XXX-*.md
```

Rules:

- Do not reuse ADR numbers.
- Do not delete ADRs.
- Do not edit historical ADRs except for typos or broken links.
- Use one of these statuses: `Proposed`, `Accepted`, `Superseded`, `Rejected`.

ADR structure:

```text
Title
Date
Status
Context
Decision
Alternatives Considered
Consequences
```

## `docs/journal/`

Record completed work history here.

Filename format:

```text
docs/journal/YYYY-MM.md
```

Record:

- Completed work
- Problems encountered
- Decisions made during the work
- Next steps identified at that time
- Manual operational work

The journal is historical. Use `docs/project-state.md` to judge current state.

## `docs/ideas/`

Record unadopted ideas, candidate features, brainstorming notes, and items to revisit later here.

Filename format:

```text
docs/ideas/YYYY-MM-brainstorming.md
docs/ideas/YYYY-MM-storyboard.md
docs/ideas/YYYY-MM-user-flows.md
docs/ideas/YYYY-MM-notes.md
```

The installer creates only `docs/ideas/YYYY-MM-brainstorming.md` by default.
Add the storyboard, user-flows, and notes files only when needed.
Every ideas document must begin by stating that it is not official current state.

Record:

- Unadopted ideas
- Candidate features
- Brainstorming notes
- Storyboards and candidate user flows
- Items to revisit later

Do not record:

- Current priorities
- Accepted roadmap
- Current system behavior
- Completed work history

When an idea is adopted, promote it to the right place in `docs/project-state.md`, `docs/architecture/*`, or `docs/decisions/*`.
`docs/ideas/*` is not official current state and always has lower authority when documents conflict.

## Inference and Ambiguity

An accepted decision alone does not establish implementation, current architecture, or completed work.
A current-state fact does not authorize inventing architecture details absent from the documentation.
Without completion evidence, do not add a completed-history entry.
When verified facts span multiple roles, update every related SSOT document.
If the change scope is materially ambiguous, preserve existing content and report the ambiguity.

## Change Rules

Feature added:

- `docs/project-state.md`
- Relevant `docs/architecture/*` if needed
- `docs/journal/YYYY-MM.md` after completion

Feature removed:

- `docs/project-state.md`
- Relevant `docs/architecture/*`
- `docs/journal/YYYY-MM.md` after completion

Architecture changed:

- New ADR
- Relevant `docs/architecture/*`
- `docs/project-state.md`
- `docs/journal/YYYY-MM.md` after completion

Database/storage changed:

- `docs/architecture/system-overview.md` or an existing detail document linked from it
- If a new detail document is created, add its link and role to Related Documents in `docs/architecture/system-overview.md`
- `docs/project-state.md`
- ADR if needed
- `docs/journal/YYYY-MM.md` after completion

External integration changed:

- `docs/architecture/system-overview.md` or an existing detail document linked from it
- If a new detail document is created, add its link and role to Related Documents in `docs/architecture/system-overview.md`
- `docs/project-state.md`
- ADR if needed
- `docs/journal/YYYY-MM.md` after completion

Technical debt added or resolved:

- `docs/project-state.md`
- `docs/journal/YYYY-MM.md` after completion

## Document Routing

`AGENTS.md` is the lightweight entry point and document router for AI agents. It does not duplicate detailed project knowledge.

- Read `docs/project-state.md` for current state, features, priorities, constraints, and technical debt.
- Read `docs/architecture/system-overview.md` for overall architecture and system behavior.
- Read the relevant ADR in `docs/decisions/` for important decisions and reasons.
- Read the relevant monthly file in `docs/journal/` for completed work and history.
- Read the relevant file in `docs/ideas/` for unadopted ideas.
- Document roles and maintenance rules are defined in `docs/README.md`.

`docs/architecture/system-overview.md` is the fixed architecture entry point. It links project-specific detailed architecture documents together with their roles; read only documents that are linked there and relevant to the current question or task. Do not guess unlinked filenames.

## AI Work Rules

All AI agents must read these before project-changing work:

1. `docs/README.md`
2. `docs/project-state.md`

If the current question or task concerns architecture or system behavior, start at `docs/architecture/system-overview.md` and read only the linked detailed architecture documents relevant to the current task. Do not guess unlinked filenames.

After work:

- Confirm whether `docs/project-state.md` still matches current state.
- Update `docs/architecture/*` if structure or behavior changed.
- Add an ADR for important decisions.
- Record completed work in `docs/journal/YYYY-MM.md`.

## Final Principle

`docs/README.md` is the documentation constitution.

`docs/project-state.md` is the current truth.
