# ADR-002: Inert offline archive and explicit privileged extraction

Date: 2026-11-14
Status: Accepted

## Context
The user requested a custom Python archival CLI without external dependencies or server modifications. Mattermost bulk export includes far more sensitive content than a selected channel.

## Decision
Separate full-server acquisition from offline filtering. Require full-export acknowledgment; preserve durable job state and never automatically duplicate ambiguous creation. Default conversion excludes private channels and all DMs. Publish new ZIPs only, with original attachment bytes and escaped HTML rather than executable rich rendering. Explicitly report skipped record counts without excluded names.

## Alternatives considered
Existing mmctl provides acquisition but not this selected offline viewer. API scraping or rich Markdown dependencies increase operational/dependency scope. The user explicitly chose custom implementation.

## Consequences
Safer offline viewing and no pip/server dependency, at the cost of plain text Markdown and unsupported DMs/plugins. Original attachments are not sanitized and must remain untrusted. Hash verification is not authenticity proof.
