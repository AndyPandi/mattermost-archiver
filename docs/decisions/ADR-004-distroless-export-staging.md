# ADR-004: Distroless export staging through Docker archive copy

Date: 2026-11-14
Status: Accepted

## Context
Pinned Mattermost images may contain mmctl but no mkdir, df, stat, rm, shell or other utilities. Sensitive export files cannot safely be downloaded directly into shared /tmp.

## Decision
Create a private 0700 UUID directory through Docker archive copy. Manuals prepare a host directory owned by the verified deployment UID:GID and copy with -a. Automation requires explicit numeric Config.User UID:GID from a single-field inspection and constructs the directory tar in host Python, avoiding host chown privileges. Pin subsequent calls to that inspected container ID. Retain container staging and record paths rather than rely on unavailable deletion utilities. Only host space is probed.

## Alternatives Considered
Shared /tmp files expose sensitive export data; shell/coreutils installation changes production images; a helper container or bind-mount reconfiguration adds operational scope. Guessing UID 2000 for arbitrary images is unsafe. UID-only or named identities require administrator manual handling rather than guessing a group.

## Consequences
No container utility dependencies or remote deletion. Private remote copies consume space until approved retention maintenance; users must check container capacity. UUID collision avoidance is probabilistic, not an atomic Docker no-clobber guarantee; never reuse staging paths. Docker cp -a ownership and directory semantics follow https://docs.docker.com/reference/cli/docker/container/cp/ . Actual Docker execution remains unverified locally.
