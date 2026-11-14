# Project State

The single current-state source of truth for mattermost-archiver.

## Purpose and architecture
Python 3.9+ standard-library CLI separates privileged full-server extraction from local selection, inert HTML conversion, and manifest verification. No server installation, database, network viewer, or OCI integration.

## Current features
- Export create/poll/list/download through Compose with explicit full-server acknowledgment, preflight/dry-run, durable resume and ambiguity refusal, exact job artifact matching, and no-overwrite publish.
- Offline list/convert/verify with public default, explicit private opt-in and team/channel selection, categories, Seoul/default configurable timezone, sorted nested threads and attachment-only posts, reactions, edits and pin metadata.
- Original attachment bytes, shallow hashed names, escaped HTML, no script/CDN/remote images, streaming hashes/copies, manifest input provenance and skipped/count verification.
- Traversal/symlink/duplicate/compression-budget rejection, missing selected attachment refusal and temporary staging.
- Korean-default README.md and English README.en.md five-step extraction-to-browser quick starts and separate detailed manuals; synthetic adversarial and mocked export tests.

## Current priorities
Independent review and authorized representative deployment validation before production use.

## Known constraints
- DM/group-DM records omitted and counted; full raw export still includes sensitive private data.
- Plain text Markdown; plugins/polls, custom emoji images, user profile metadata, roles and sidebar categories not reconstructed. Not a complete backup.
- Default 256 MiB selected-post serialized budget is not an RSS cap; ZIP central directory has a preallocation 64 MiB cap; the guard uses Python zipfile internal EOCD helpers. Filesystem checks are estimates, not quota reservations.
- Tested locally under Python 3.12 with Python 3.9 syntax validation, not live Mattermost, OL9/macOS or browser integration.
- Requires OS timezone database, POSIX locking/hardlinks and Docker/container utilities for live extraction.
- Manifest is integrity evidence, not a digital signature. User content/attachments can contain secrets and active content remains dangerous if opened separately.

## Technical debt and roadmap
Potential future work needs separate scope: streaming disk-backed post indexing, richer safe Markdown, representative server-version compatibility matrix. No scheduled rollout or production operation is authorized.

- Attachment filenames use a last-8 path-hash suffix before the extension, with casefold collision detection and 4-character expansion up to 64; integrity SHA-256 unchanged.

- Public download quick starts support HTTPS clone, wget and curl, with private fallback. No project LICENSE has been selected.
