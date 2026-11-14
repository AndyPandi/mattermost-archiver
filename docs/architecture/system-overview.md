# System Overview

`mattermost_archiver.py` owns argparse and offline processing. `export_live.py` registers the export command and isolates subprocess execution.

Export uses argv lists, never a shell. It persists a creating marker before remote mutation; unknown creation outcomes require explicit job adoption. State/output locks prevent concurrent ownership. Polling validates identity/type/status and chooses only JOBID_export.zip. Compose resolves a single container ID and a scoped inspect reads only Config.User. An explicit numeric UID:GID is required. Host Python builds a tar containing one UUID-named 0700 directory with that ownership; docker cp -a streams it into /tmp without executing container utilities. mmctl and subsequent copies target that exact container ID. A private 0700 host staging directory protects copied bytes before chmod 0600, SHA-256 and atomic hard-link publication. Remote staging paths are persisted before copy, retained on success/failure and reported for retention management; no remote deletion is attempted. Host space is checked before work and after copy; container capacity is an operator check, not an automated guarantee.

Offline conversion makes bounded JSONL passes to collect channel metadata before processing nonchronological posts. Explicit selection filters content; selected posts are sorted in memory within a serialized-byte budget. Attachments resolve to data/PATH per v11.7.0 and are streamed without extraction of arbitrary ZIP paths. The renderer escapes all content into one index.html, using details for nested replies and download links for attachments. Categories map team/channel to labels. ZIP stores index, attachments, and a manifest; no source metadata dump is included.

Verification checks exact member set, streaming hashes and sizes, then generated markup counts. It does not trust verification as a signature or source completeness proof.

## Related Documents
- [CLI manuals](../../README.md): extraction and operational procedures.
- [Security decision](../decisions/ADR-002-offline-inert-archive.md): threat and scope choices.

Attachment filename allocation uses a sanitized basename with the last eight path-hash digits before the final extension. A casefold name set detects collisions and extends by four digits up to the full hash, then fails closed. Same ZIP member references reuse their allocated path.

Input validation checks consumed channel/post/reply/reaction/attachment shapes before sorting or rendering, without echoing record payloads. Selected reply trees inherit omitted team/channel recursively; any explicit scope (including null) must be a nonempty string matching the parent. Official v11.7.0 ReplyImportData omits scope, so this does not require new fields in normal exports. Optional pointer/slice fields may be omitted/null: user/message use safe defaults, edit_at/is_pinned are absent, and collections are empty; required create_at, attachment paths and reaction fields must have their expected scalar types. Unknown unused metadata is not rendered. See [upstream field definitions](https://github.com/mattermost/mattermost/blob/v11.7.0/server/channels/app/imports/import_types.go). Selection combines team/channel/all-public by union, then applies the private opt-in guard. Manifest object/entry/count types are checked before verification.

The renderer imports independently authored emoji aliases and inline CSS from chat_style.py. Numeric internal channel anchors never use user-controlled IDs. SHA-256 selects avatar color classes. All usernames/initials/aliases/messages are escaped. Native details preserve every reaction record and timestamp, including duplicates/epoch zero, while chips count unique exact usernames grouped by Unicode. Unknown aliases stay literal :name:. Local calendar separators and readable time labels retain precise ISO values in datetime/title. Exact v1 section/post/reply count markers and manifest schema remain unchanged for old/new verifier interoperability.

Palette tokens use lavender #A89BBE and beige #D8C3A8; darker derived text/link colors preserve readable contrast. System fonts and native emoji fonts avoid external assets.
