# Mattermost Archiver

[한국어](../README.md) · [English](../README.en.md)

Export a live Mattermost server, select conversations, and create an offline archive to verify and view in a web browser. Requires **Python 3.9+**, standard library only. No pip installation is required. This is a reading archive, **not a backup or restore tool**.

## Security and scope

- Obtain authorization for a **full-server export**. The raw export can include private channels, direct/group messages, user information, and attachments even if you eventually select one public channel. Selection happens after extraction.
- Direct/group messages are unsupported in the converted archive: they are skipped and reported. Private channels require explicit inclusion. Review the conversion report for omissions.
- Protect the raw ZIP, state file, converted ZIP, extracted folder, and transfer destinations. ZIP files are not encrypted. Use encrypted storage and trusted transfer channels.
- User emails and roles are not copied as viewer metadata. This is not content redaction: messages and attachments may still contain personal information and secrets.
- Source messages are not deleted or modified. Extraction creates a server export artifact; the server’s configured retention lifecycle can expire it. The tool does not disable server cleanup or guarantee indefinite availability.
- Plugin data and polls are not guaranteed to survive conversion. Markdown is displayed as escaped plain text rather than full Mattermost rendering. This is not a complete representation of every server object.
- HTML/SVG and other untrusted attachments are download-only, not inline-rendered. Downloading is not sanitization: opening downloaded files in other applications can still be dangerous.

## 1. Public download and prerequisites

Python 3.9+ and OS timezone data are required. A fresh OCI/Oracle Linux VM may lack Git/wget/unzip. Check first (package installation below is optional and must be run by an authorized operator).

```sh
python3 --version
command -v git; command -v wget; command -v curl
# Optional on Oracle Linux 9 only; use your OS package manager elsewhere:
# sudo dnf install python3 git curl tzdata
```

For a public repository, clone over HTTPS without login. Use a new directory; do not overwrite existing files.

```sh
cd ~
git clone https://github.com/AndyPandi/mattermost-archiver.git
cd mattermost-archiver
python3 mattermost_archiver.py --help
```

Without Git, choose wget or curl. Python’s standard library replaces unzip.

```sh
cd ~
wget -O mattermost-archiver-main.zip https://github.com/AndyPandi/mattermost-archiver/archive/refs/heads/main.zip
# Alternative: choose ONE downloader
# curl -fL -o mattermost-archiver-main.zip https://github.com/AndyPandi/mattermost-archiver/archive/refs/heads/main.zip
python3 -m zipfile -e mattermost-archiver-main.zip archiver-source
cd ~/archiver-source/mattermost-archiver-main
```

**Private fallback:** if anonymous download fails, sign into GitHub, use Code → Download ZIP and transfer it, or clone with an authorized SSH key. Never put tokens/keys in URLs. main is mutable: record/pin a reviewed commit and inspect code before executing it. Never pipe downloads into a shell.

Examples assume Compose service `mattermost`, Compose file `/opt/mattermost/compose.yaml`, and bundled binary `/mattermost/bin/mmctl`. Adapt these to your deployment; use the mmctl shipped with your server and inspect its help for version-specific syntax.

The Python CLI itself does not require root. Export needs Docker daemon/container access. On rootful Docker, membership in the `docker` group is effectively **root-equivalent host access**. Rootless Docker must still have access to the actual deployment. If you lack permission, ask the deployment operator to extract; do not make the Docker socket world-writable.

Local mmctl requires Mattermost `ServiceSettings.EnableLocalMode` and an accessible local Unix socket for the container command’s user. If disabled, an authorized administrator should inspect and merge the existing configuration and apply the deployment’s normal reload/restart procedure as needed. Do not overwrite configuration. Working local mode needs no Mattermost token but is privileged access.

## 2. Prepare protected storage

From the repository directory on the server host:

```sh
umask 077
df -h .
```

The examples write artifacts in the current directory. Keep them out of version control, or use absolute paths to an access-controlled working directory.

Plan for the server-generated export, container download, host raw ZIP, conversion temporary files, converted ZIP, and the local PC ZIP plus extracted contents. Several copies can coexist. Several times the raw ZIP size is only a rough estimate, **not a guarantee**: compressed sizes do not reliably predict expanded sizes. Check server export storage, container storage, temporary storage, host output storage, and local PC storage independently. Attachments often dominate.

## 3. Administrator manual extraction (default for a new OCI VM)

**Proceed only with explicit full-server export consent.** Selecting one public channel later does not narrow extraction. Check every command succeeds; stop on failure. Run from the ordinary user's SSH shell, applying sudo only to the Docker and scoped chown commands below. New OCI VMs have root-owned /opt/mattermost mode 0700, compose mode 0600, and opc outside the docker group. Never weaken directory/env/compose permissions or Docker socket/group access to bypass this boundary. The chown below transfers only the newly downloaded file in a fresh private temporary directory to the ordinary user. Subsequent list/convert/verify run without sudo.

Run on the Docker host. Confirm syntax with the installed `mmctl --local export --help`. Replace `JOB_ID` and `ID_export.zip` with actual returned values.

```sh
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local --json export create --include-archived-channels

# Record the returned job ID; check until successful.
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local --json export job show JOB_ID

sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local --json export list

# Use the exact export filename from the list.
REMOTE_DIR="/tmp/mm-archiver-manual-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
SEED_PARENT="$(mktemp -d)"
mkdir -m 700 "$SEED_PARENT/private"
# Pinned deployment Compose user only; NOT a generic Mattermost UID/GID.
sudo chown 2000:2000 "$SEED_PARENT/private"
sudo docker compose -f /opt/mattermost/compose.yaml cp -a \
  "$SEED_PARENT/private" "mattermost:$REMOTE_DIR"
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local export download ID_export.zip "$REMOTE_DIR/export.zip"

umask 077
LOCAL_DIR="$(mktemp -d ./mm-manual-XXXXXXXX)"
sudo docker compose -f /opt/mattermost/compose.yaml cp \
  "mattermost:$REMOTE_DIR/export.zip" "$LOCAL_DIR/raw.zip"
sudo chown "$(id -u):$(id -g)" "$LOCAL_DIR/raw.zip"
chmod 600 "$LOCAL_DIR/raw.zip"
# ln refuses an existing raw.zip; retain temporary files if any command fails.
ln "$LOCAL_DIR/raw.zip" ./raw.zip
python3 -m zipfile -t raw.zip
sha256sum raw.zip
```
No mkdir/sh/id/chmod/rm inside the container is assumed. mkdir/chown above run on the **host**; 2000:2000 applies only to the verified pinned Compose deployment. Have an administrator establish the correct UID:GID for other deployments. Docker cp -a preserves source ownership and permissions. Generate a fresh UUID path every time; never reuse it. Stop immediately if any command fails. ln refuses existing output. The container 0700 directory protects the sensitive ZIP and is retained, not automatically deleted: record its path and handle it under your retention policy without deleting server export originals. Host temporary directories also need retention management. An administrator must check container /tmp capacity separately.


Wait for job success before downloading. On failure, inspect job errors and server logs. Container temporary downloads may disappear after recreation. Manage temporary copies through your retention process; these instructions do not delete source messages or export artifacts.

### Optional advanced workflow: automated extraction and resume

The following Python export flow is only for a user **already authorized to access the actual Docker daemon and protected compose/env files**. Do not assume an ordinary opc user on a new OCI VM has that access. Prefer the administrator manual flow above. Sudo Python is not the default: root would execute both downloaded mattermost_archiver.py and imported export_live.py. If an administrator deliberately chooses root execution, review and pin the entire revision and import paths, place code in root-owned locations not writable by ordinary users, and protect working directories, state and output files. Do not run root Python from a user-writable checkout.

Inspect options and preview the operation:

```sh
python3 mattermost_archiver.py export --help
python3 mattermost_archiver.py export \
  --state export-state.json --output raw.zip \
  --acknowledge-full-server-export \
  --compose-file /opt/mattermost/compose.yaml --dry-run
```

Execute by removing `--dry-run`:

```sh
python3 mattermost_archiver.py export \
  --state export-state.json --output raw.zip \
  --acknowledge-full-server-export \
  --compose-file /opt/mattermost/compose.yaml
```

`--compose-file` defaults to `/opt/mattermost/compose.yaml`. `--preflight` performs read-only local-mode and container disk checks; `--dry-run` does not call Docker. The acknowledgment is deliberate: this is a full-server export, not a selected-channel download. Keep `export-state.json` for resumable progress. After interruption, reuse the same state/output instead of immediately creating another export.

If creation succeeded but its response/state write was lost, creation is ambiguous. Inspect existing jobs/exports and recover the actual job ID before retrying, otherwise you may create duplicate large exports. Resume explicitly:

```sh
python3 mattermost_archiver.py export \
  --state export-state.json --output raw.zip \
  --acknowledge-full-server-export \
  --compose-file /opt/mattermost/compose.yaml --job-id JOB_ID
```

A job ID is not an export filename. Match the completed job to the artifact listed by mmctl. If retention has expired that artifact, resume cannot restore it; an authorized new export is needed.

## 4. Inspect and select conversations

```sh
python3 mattermost_archiver.py list raw.zip
python3 mattermost_archiver.py convert --help
```

Use exact team/channel identifiers from `list`, not guessed display names. Choose a selection mode:

```sh
# Selected teams; repeat --team.
python3 mattermost_archiver.py convert raw.zip --output archive.zip \
  --team engineering --team operations --timezone Asia/Seoul

# Selected channels; repeat --channel.
python3 mattermost_archiver.py convert raw.zip --output archive.zip \
  --channel engineering/town-square --channel operations/incidents \
  --timezone Asia/Seoul

# All supported public channels.
python3 mattermost_archiver.py convert raw.zip --output archive.zip \
  --all-public --timezone Asia/Seoul
```

Private channels are excluded by default. Add `--include-private` to an explicit team/channel selection only when authorized and intended. Naming a private channel does not bypass the opt-in requirement. Do not assume `--all-public` includes private channels. Direct/group messages remain unsupported regardless of this flag.

**Selectors form a UNION, not an intersection.** Combining --team, --channel and --all-public adds their scopes. --team engineering --channel engineering/town-square does not narrow to one channel. --include-private can include every private channel in an explicitly selected team. --all-public with only --include-private adds no private channels.

For exactly one public channel, use no other selection flags:

```sh
python3 mattermost_archiver.py convert raw.zip --output one-channel.zip --channel engineering/town-square
```

Optional `--categories mapping.json` supplies category grouping. The JSON schema is a flat object, for example: `{"engineering/town-square":"Company", "operations/incidents":"Operations"}`. Categories are a viewing aid, not a reconstruction of Mattermost’s per-user sidebar. They are not required for export or selection.

`--timezone Asia/Seoul` controls displayed timestamps, not source timestamps. The host must have the requested IANA timezone in its system timezone database; resolve a missing database rather than silently using a different zone.

Review the conversion summary/report for selection, skipped direct/group messages, unsupported records, missing attachments, and limits reached. Processing uses bounded resource budgets; consult `convert --help` for available configuration and defaults. Raise limits only for trusted input after checking resources. Limits are safeguards, not guarantees against every malformed ZIP. Do not interpret an incomplete conversion as a complete backup.

## 5. Verify and transfer to a PC (Windows/macOS/Linux)

Verify as the ordinary server user. SHA-256 checks integrity, not authenticity, safety or completeness. An attacker replacing both ZIP and digest defeats comparison; record the digest through a trusted channel.

```sh
python3 mattermost_archiver.py verify archive.zip
sha256sum archive.zip
```

In your PC terminal, replace the SSH host/path. Use a new local folder with no existing destination file.

```sh
scp user@server:/absolute/path/archive.zip ./archive.zip
```

Compare hashes using Linux `sha256sum archive.zip`, macOS `shasum -a 256 archive.zip`, or Windows PowerShell `Get-FileHash archive.zip -Algorithm SHA256`. On Linux/macOS with Python 3.9+ and the same source revision, you can also run verify locally. Native Windows CLI execution is not validated. On failure, re-copy; never edit hashes to force a pass.

## 6. Extract and view locally

Extract the **converted archive.zip**, not sensitive raw.zip, into a new folder using your OS archive utility. Alternatively, with Python use `python3 -m zipfile -e archive.zip archive-view` without unzip. Open the extracted index.html in a browser on Windows, macOS or Linux. Viewing needs neither Python nor Mattermost. Keep the folder structure intact; do not use the ZIP preview. No Internet, public server or SSH tunnel is needed.

HTML/SVG attachments are download links only, but **download is not sanitization**: opening them separately may execute active content. Passing integrity verification does not prove file safety. Protect ZIP and extracted folder under your access/retention policy, review sharing scope and omissions, and verify an external copy. Deleting the raw export is a separate retention decision.

## Synthetic tests

Run local synthetic tests without production access:

```sh
python3 -m unittest discover -s tests -v
```

Passing tests does not certify every Mattermost version/plugin. Validate a representative authorized export when changing server versions.

## Official references

- [Mattermost mmctl documentation](https://docs.mattermost.com/manage/mmctl-command-line-tool.html)
- [Mattermost documentation](https://docs.mattermost.com/) — consult bulk export and local-mode configuration for your installed release.

Installed mmctl help and deployment configuration govern version-specific behavior.

## Budgets, evidence, and recovery details

- `list`, `convert`, `verify`: `--max-bytes` 21474836480 (compressed input and total expanded bytes), `--max-entries` 100000, `--max-ratio` 200, `--max-line-bytes` 16777216, `--max-records` 1000000.
- Conversion: `--max-post-bytes` 268435456 (serialized selected posts, not exact RSS), `--max-depth` 50, `--min-free-bytes` 1073741824. Free output disk must exceed 3 × total expanded input + reserve. Python object overhead and generated HTML expansion mean memory/disk estimates are not hard process limits. ZIP central-directory size is capped at 64 MiB before allocation; entry count is also prechecked. Use only authorized exports, not arbitrary hostile uploads.
- Export: `--poll-interval` 5 seconds, `--poll-timeout` 3600, `--command-timeout` 600, `--min-free-bytes` 1073741824 is a host-only free-space floor (check container capacity separately), not export size prediction.
- Preserve state and lock files for retries. Never delete an ambiguous state just to retry. A completed output is never overwritten; after a crash during publication, compare its hash to the persisted state. SIGKILL may leave generated temporary copies; inspect them manually, never sweep server export originals. POSIX flock, same-filesystem hard links and Docker archive-copy support are required; only mmctl is executed inside the container. Automated export requires an explicit numeric Config.User UID:GID (no default 2000 assumption). Staging is retained and all generated paths are recorded in state; no remote cleanup commands are run.
- `verify` checks hashes, byte sizes, member set, and rendered post/reply/channel/attachment counts. It is not a signature or completeness proof. The manifest does not authenticate itself.
- Native Python 3.9 runtime, OL9, macOS, live server, and browser integration are not certified by synthetic tests alone. Python timezone data must be installed by the OS.

Pinned source evidence (v11.7.0): [export commands](https://github.com/mattermost/mattermost/blob/v11.7.0/server/cmd/mmctl/commands/export.go), [JSON printer](https://github.com/mattermost/mattermost/blob/v11.7.0/server/cmd/mmctl/printer/printer.go), [worker](https://github.com/mattermost/mattermost/blob/v11.7.0/server/channels/jobs/export_process/worker.go), [attachment writer](https://github.com/mattermost/mattermost/blob/v11.7.0/server/channels/app/export.go), [data directory constant](https://github.com/mattermost/mattermost/blob/v11.7.0/server/public/model/bulk_export.go). The root is `import.jsonl`; an attachment path `PATH` resolves strictly to `data/PATH`. JSON job fields are lowercase, normally inside a single-element array; type `export_process`, status `success`, artifact `JOBID_export.zip`. Unknown layouts fail rather than guessing.

### Attachment filenames
Stored filenames use `sanitized-name__last8hash.ext`. The suffix is the last 8 hex characters of the original ZIP member path SHA-256, not a content hash. Case-insensitive collisions extend the suffix to 12, 16, and further characters up to 64; unresolved collisions fail without overwriting. HTML keeps the original display name. Manifest integrity hashes remain full SHA-256. Reconvert the original export to a new output ZIP to apply this policy; existing archives are not modified.

Docker copy reference: https://docs.docker.com/reference/cli/docker/container/cp/ — -a preserves source UID/GID; copying a directory to a nonexistent destination creates that destination. UUID paths must not be reused. No real Docker validation was performed for this revision.

## Rebuild the chat viewer from an existing raw.zip

No new server export is needed. Download the **whole source ZIP** into a fresh directory or update your clone; do not replace only one Python file (matching chat_style.py and export_live.py are required). Repeat conversion, verification, copying and opening in the five-step flow, using a new output name. This example selects public channels; retain previous team/channel/private opt-in/categories/timezone options if different.

```bash
RAW="$HOME/archive-work/raw.zip"
OUT="$HOME/archive-work/archive-chat.zip"
python3 mattermost_archiver.py convert "$RAW" --all-public --timezone Asia/Seoul --output "$OUT"
python3 mattermost_archiver.py verify "$OUT"
```

Team/channel anchors and native reply/reaction details work without JavaScript. “답글 N개” counts **direct replies**; deeper replies expand separately. Reaction chips count **unique exact usernames per Unicode emoji**, merging synonymous aliases (+1/thumbsup/thumbs_up). Every original record, including duplicates, retains user, timestamp and alias in details. Visible times use YYYY-MM-DD HH:mm in the chosen timezone; exact ISO seconds/fractions/UTC offset remain in time datetime/title.

Common reactions render as Unicode (grinning=😀, smiley=😃, white_check_mark=✅). The complete independently authored small subset is EMOJI_ALIASES in chat_style.py. Unknown/custom aliases stay escaped :name: text without custom image/API calls. Emoji appearance depends on the OS. Avatars use deterministic username initials/colors, not fetched profile images. All attachments including HTML/SVG remain download cards, not sanitized files. No scripts, external fonts/CDNs or network viewer dependencies are introduced.
