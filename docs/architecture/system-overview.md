# System Overview

`mattermost_archiver.py` owns argparse and offline processing. `export_live.py` registers the export command and isolates subprocess execution.

Export uses argv lists, never a shell. It persists a creating marker before remote mutation; unknown creation outcomes require explicit job adoption. State/output locks prevent concurrent ownership. Polling validates identity/type/status and chooses only JOBID_export.zip. mmctl writes into a unique container temp directory; Compose cp transfers to host staging, then SHA-256 and atomic hard-link publication prevent overwrite. Cleanup never targets server originals.

Offline conversion makes bounded JSONL passes to collect channel metadata before processing nonchronological posts. Explicit selection filters content; selected posts are sorted in memory within a serialized-byte budget. Attachments resolve to data/PATH per v11.7.0 and are streamed without extraction of arbitrary ZIP paths. The renderer escapes all content into one index.html, using details for nested replies and download links for attachments. Categories map team/channel to labels. ZIP stores index, attachments, and a manifest; no source metadata dump is included.

Verification checks exact member set, streaming hashes and sizes, then generated markup counts. It does not trust verification as a signature or source completeness proof.

## Related Documents
- [CLI manuals](../../README.md): extraction and operational procedures.
- [Security decision](../decisions/ADR-002-offline-inert-archive.md): threat and scope choices.

Attachment filename allocation uses a sanitized basename with the last eight path-hash digits before the final extension. A casefold name set detects collisions and extends by four digits up to the full hash, then fails closed. Same ZIP member references reuse their allocated path.
