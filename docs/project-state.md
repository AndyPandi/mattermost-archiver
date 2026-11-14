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

- Consumed input shapes/scalars and selected recursive reply scope are validated with payload-free ArchiveError failures before publication; nullable optional Go export fields remain accepted. Selection UNION/private opt-in behavior is explicit in help/manuals and regression-tested.
- Detailed bilingual manuals default to administrator manual extraction and unprivileged conversion for restricted OCI permissions; public downloads, prerequisites, cross-platform viewing and active attachment/integrity limitations are documented. Local synthetic suite: 60 tests; actual VM/live export remains unvalidated.

- Automated staging uses a numeric UID:GID from only the scoped container Config.User field, never a generic 2000 default. Missing/named/UID-only identities fail before creation. Docker cp -a receives a host-generated 0700 directory tar; subsequent operations pin the inspected container ID.
- Container staging is retained and recorded in state (including retries); no remote delete is attempted. Host staging is private and publication remains no-overwrite. Container capacity must be verified separately; the free-space option covers host only. Docker is unavailable in the development environment, so archive-copy behavior is documentation-backed and mocked, not live-validated.

## Current priorities
Independent review and authorized representative deployment validation before production use.

## Known constraints
- DM/group-DM records omitted and counted; full raw export still includes sensitive private data.
- Plain text Markdown; plugins/polls, custom emoji images, user profile metadata, roles and sidebar categories not reconstructed. Not a complete backup.
- Default 256 MiB selected-post serialized budget is not an RSS cap; ZIP central directory has a preallocation 64 MiB cap; the guard uses Python zipfile internal EOCD helpers. Filesystem checks are estimates, not quota reservations.
- Tested locally under Python 3.12 with Python 3.9 syntax validation, not live Mattermost, OL9/macOS or browser integration.
- Requires OS timezone database, POSIX locking/hardlinks and Docker archive-copy support and mmctl for live extraction; no container shell/coreutils required.
- Manifest is integrity evidence, not a digital signature. User content/attachments can contain secrets and active content remains dangerous if opened separately.

## Technical debt and roadmap
Potential future work needs separate scope: streaming disk-backed post indexing, richer safe Markdown, representative server-version compatibility matrix. No scheduled rollout or production operation is authorized.

- Attachment filenames preserve Unicode/Korean and ordinary spaces in NFC as `stem_last8hash.ext` (one underscore), using the original unnormalized ZIP member path hash. NFC+casefold collision detection expands 8/12/16…64 then refuses; bytes and full integrity SHA-256 are unchanged. Portable sanitization and 240 UTF-8-byte/UTF-16-unit component limits include hash/extension; final extensions up to 32 bytes/units are preserved. URL-encoded HTML hrefs retain escaped original labels. Existing raw exports need only reconversion to a new output ZIP, not server re-export.

- Public download quick starts support HTTPS clone, wget and curl, with private fallback. Project code and documentation use the MIT License (LICENSE); archived user data and third-party software retain their own rights.

- Responsive offline chat layout includes team/channel anchors, deterministic initials/color avatars, day separators, exact ISO time metadata, native nested replies and attachment download cards. Unicode reaction chips count unique exact users across synonymous aliases; all original reaction records remain in accessible details.
- v1 manifest/count markers remain unchanged; synthetic old d9a7bbd archives verify with the new code and new archives verify with d9a7bbd. Browser visual review was attempted but blocked by no supported installed browser; no screenshot available.

- Presentation palette: lavender #A89BBE and beige #D8C3A8, pale surfaces with dark text, 16px body and 1.65 line height. Synthetic downloadable HTML preview prepared; browser rendering remains unverified.
