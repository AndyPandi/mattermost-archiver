# Mattermost Archiver

[English](README.md) · [한국어](README.ko.md)

Export a live Mattermost server, select conversations, and create an offline archive to verify and view on a Mac. Requires **Python 3.9+**, standard library only. No pip installation is required. This is a reading archive, **not a backup or restore tool**.

## Security and scope

- Obtain authorization for a **full-server export**. The raw export can include private channels, direct/group messages, user information, and attachments even if you eventually select one public channel. Selection happens after extraction.
- Direct/group messages are unsupported in the converted archive: they are skipped and reported. Private channels require explicit inclusion. Review the conversion report for omissions.
- Protect the raw ZIP, state file, converted ZIP, extracted folder, and transfer destinations. ZIP files are not encrypted. Use encrypted storage and trusted transfer channels.
- User emails and roles are not copied as viewer metadata. This is not content redaction: messages and attachments may still contain personal information and secrets.
- Source messages are not deleted or modified. Extraction creates a server export artifact; the server’s configured retention lifecycle can expire it. The tool does not disable server cleanup or guarantee indefinite availability.
- Plugin data and polls are not guaranteed to survive conversion. Markdown is displayed as escaped plain text rather than full Mattermost rendering. This is not a complete representation of every server object.
- HTML/SVG and other untrusted attachments are download-only, not inline-rendered. Downloading is not sanitization: opening downloaded files in other applications can still be dangerous.

## 1. Get the private repository and prerequisites

Use Python 3.9+, Git, enough free disk space, and authorized access to the Docker deployment. Clone the private repository with your authorized SSH key:

```sh
git clone git@github.com:AndyPandi/mattermost-archiver.git
cd mattermost-archiver
python3 --version
python3 mattermost_archiver.py --help
```

Alternatively, use an installed GitHub CLI and interactive authentication:

```sh
gh auth login
gh repo clone AndyPandi/mattermost-archiver
cd mattermost-archiver
```

Never embed tokens, passwords, or private keys in clone URLs, scripts, archives, or committed files. Use the same repository revision on the extraction host and Mac.

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

Plan for the server-generated export, container download, host raw ZIP, conversion temporary files, converted ZIP, and the Mac ZIP plus extracted contents. Several copies can coexist. Several times the raw ZIP size is only a rough estimate, **not a guarantee**: compressed sizes do not reliably predict expanded sizes. Check server export storage, container storage, temporary storage, host output storage, and Mac storage independently. Attachments often dominate.

## 3. Extract from the live server

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

### Manual extraction fallback

Run on the Docker host. Confirm syntax with the installed `mmctl --local export --help`. Replace `JOB_ID` and `ID_export.zip` with actual returned values.

```sh
docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local --json export create --include-archived-channels

# Record the returned job ID; check until successful.
docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local --json export job show JOB_ID

docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local --json export list

# Use the exact export filename from the list.
REMOTE_DIR="/tmp/mm-archiver-manual-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  mkdir -m 700 "$REMOTE_DIR"
docker compose -f /opt/mattermost/compose.yaml exec -T mattermost \
  /mattermost/bin/mmctl --local export download ID_export.zip "$REMOTE_DIR/export.zip"

LOCAL_DIR="$(mktemp -d ./mm-manual-XXXXXXXX)"
docker compose -f /opt/mattermost/compose.yaml cp \
  "mattermost:$REMOTE_DIR/export.zip" "$LOCAL_DIR/raw.zip"
chmod 600 "$LOCAL_DIR/raw.zip"
# ln refuses an existing raw.zip; retain temporary files if any command fails.
ln "$LOCAL_DIR/raw.zip" ./raw.zip
sha256sum raw.zip
```

Wait for job success before downloading. On failure, inspect job errors and server logs. Container temporary downloads may disappear after recreation. Manage temporary copies through your retention process; these instructions do not delete source messages or export artifacts.

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

Optional `--categories mapping.json` supplies category grouping. The JSON schema is a flat object, for example: `{"engineering/town-square":"Company", "operations/incidents":"Operations"}`. Categories are a viewing aid, not a reconstruction of Mattermost’s per-user sidebar. They are not required for export or selection.

`--timezone Asia/Seoul` controls displayed timestamps, not source timestamps. The host must have the requested IANA timezone in its system timezone database; resolve a missing database rather than silently using a different zone.

Review the conversion summary/report for selection, skipped direct/group messages, unsupported records, missing attachments, and limits reached. Processing uses bounded resource budgets; consult `convert --help` for available configuration and defaults. Raise limits only for trusted input after checking resources. Limits are safeguards, not guarantees against every malformed ZIP. Do not interpret an incomplete conversion as a complete backup.

## 5. Verify and transfer to Mac

On the server:

```sh
python3 mattermost_archiver.py verify archive.zip
sha256sum archive.zip
```

Record the digest through a trusted channel. On the Mac, replace the SSH host/path:

```sh
mkdir -p ~/MattermostArchives
chmod 700 ~/MattermostArchives
cd ~/MattermostArchives
scp user@server:/absolute/path/archive.zip ./archive.zip
shasum -a 256 archive.zip
```

The digests must match exactly. This checks transfer consistency, not authenticity if an attacker can replace both ZIP and digest. Internal archive verification checks integrity/structure according to its manifest; it does not prove that the source export captured everything.

Clone the same repository revision on the Mac as described above. With Python 3.9+:

```sh
python3 /absolute/path/mattermost-archiver/mattermost_archiver.py verify \
  ~/MattermostArchives/archive.zip
```

If verification fails, inspect the error and compare digests; re-copy if necessary. Never hand-edit hashes to make corrupted content pass.

## 6. Extract and view locally on Mac

Extract the **converted archive**, not the sensitive raw export, into a new folder:

```sh
cd ~/MattermostArchives
mkdir archive-view
unzip archive.zip -d archive-view
open archive-view/index.html
```

Open the extracted top-level `index.html` in your browser. Keep the folder structure intact for conversation pages and attachments. No upload or public server is needed. This is an offline view, not a live Mattermost client. Treat attachment links as untrusted downloads. If links fail, check extraction completed and you opened the extracted index, not a preview inside the ZIP.

Apply your organization’s access/retention policy to both ZIP and extracted folder. Sharing either shares the included conversations and attachments. Deleting the raw export is a separate retention decision: first verify the final archive and understand its omissions.

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
- Export: `--poll-interval` 5 seconds, `--poll-timeout` 3600, `--command-timeout` 600, `--min-free-bytes` 1073741824 is a host/container free-space floor, not export size prediction.
- Preserve state and lock files for retries. Never delete an ambiguous state just to retry. A completed output is never overwritten; after a crash during publication, compare its hash to the persisted state. SIGKILL may leave generated temporary copies; inspect them manually, never sweep server export originals. POSIX flock, same-filesystem hard links, and container df/mkdir/stat/rm/rmdir are required.
- `verify` checks hashes, byte sizes, member set, and rendered post/reply/channel/attachment counts. It is not a signature or completeness proof. The manifest does not authenticate itself.
- Native Python 3.9 runtime, OL9, macOS, live server, and browser integration are not certified by synthetic tests alone. Python timezone data must be installed by the OS.

Pinned source evidence (v11.7.0): [export commands](https://github.com/mattermost/mattermost/blob/v11.7.0/server/cmd/mmctl/commands/export.go), [JSON printer](https://github.com/mattermost/mattermost/blob/v11.7.0/server/cmd/mmctl/printer/printer.go), [worker](https://github.com/mattermost/mattermost/blob/v11.7.0/server/channels/jobs/export_process/worker.go), [attachment writer](https://github.com/mattermost/mattermost/blob/v11.7.0/server/channels/app/export.go), [data directory constant](https://github.com/mattermost/mattermost/blob/v11.7.0/server/public/model/bulk_export.go). The root is `import.jsonl`; an attachment path `PATH` resolves strictly to `data/PATH`. JSON job fields are lowercase, normally inside a single-element array; type `export_process`, status `success`, artifact `JOBID_export.zip`. Unknown layouts fail rather than guessing.
