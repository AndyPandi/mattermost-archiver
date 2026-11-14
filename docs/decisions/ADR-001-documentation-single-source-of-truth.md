# ADR-001: Documentation Single Source of Truth

Date: 2026-11-14

Status: Accepted

## Context

The project needs a repeatable documentation structure that humans and AI agents can both follow.
Without clear document roles, current state, architecture notes, decisions, and history can drift or duplicate each other.

## Decision

Use a docs-based Single Source of Truth system:

- `docs/project-state.md` is the only current-state source of truth.
- `docs/README.md` defines the documentation constitution.
- `docs/architecture/*` describes current system behavior and structure.
- `docs/decisions/ADR-XXX-*.md` records important decisions.
- `docs/journal/YYYY-MM.md` records completed work history.
- `AGENTS.md` instructs AI agents to read and maintain this structure.

## Alternatives Considered

1. Keep all notes in `README.md`.
2. Keep ad hoc documents without fixed roles.
3. Use issue tracker history as the primary project memory.

## Consequences

### Positive

- Current project truth has one clear location.
- Architecture, decisions, and history are separated.
- AI agents have stable instructions for reading and updating docs.

### Negative

- Work that changes project state requires documentation updates.
- Existing projects may need one-time document cleanup.
