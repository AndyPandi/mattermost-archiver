# Mattermost Archiver

[한국어](README.md) · [English](README.en.md)

**Convert Mattermost conversations and attachments into readable, offline HTML archives.** Browse teams, channels, threads and attachment links without a running server. View the resulting HTML on Windows, macOS or Linux.

Conversion uses Python 3.9+ and its standard library (no pip installation). Commands below target a **Linux server running Mattermost with Docker Compose**. Viewing HTML needs neither Python nor Mattermost. Native Windows CLI execution has not been validated.

> Raw exports may contain private channels, DMs and other sensitive server-wide data. Restrict them to administrators. The conversion example includes public channels only; DM conversion is unsupported. This is not a full backup/restore tool.

First check `python3 --version` (3.9+), `command -v git`, `command -v wget` and `command -v curl`. Fresh VMs may lack some tools; see [prerequisites](docs/manual.en.md). unzip is not required.

## 1. Export conversations and attachments as ZIP

Run in the **Mattermost server SSH terminal**, with full-server export authorization and enough disk space. Freeze message/file changes for a final archive. Examples assume `/opt/mattermost/compose.yaml`, service `mattermost` and enabled local mmctl mode.

```sh
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost /mattermost/bin/mmctl --local export create --include-archived-channels
```

Record the returned **Job ID**. Attachments are included by default and archived channels are requested. This does not preserve every server object or plugin datastore.

## 2. Confirm successful extraction

Replace `JOB_ID` with the actual ID.

```sh
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost /mattermost/bin/mmctl --local export job show JOB_ID
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost /mattermost/bin/mmctl --local export list
```

Continue only when status is **success** and `JOB_ID_export.zip` appears. For pending/in_progress, check the same job again rather than creating duplicates.

Replace `REPLACE_WITH_JOB_ID` below and check each command succeeds before continuing. If `~/archive-work/raw.zip` exists, use a new work directory to avoid overwriting it.

```sh
umask 077
mkdir -p ~/archive-work
chmod 700 ~/archive-work
JOB_ID="REPLACE_WITH_JOB_ID"
REMOTE_DIR="/tmp/mm-archiver-manual-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
SEED_PARENT="$(mktemp -d)"
mkdir -m 700 "$SEED_PARENT/private"
# Pinned deployment Compose user only; NOT a generic Mattermost UID/GID.
sudo chown 2000:2000 "$SEED_PARENT/private"
sudo docker compose -f /opt/mattermost/compose.yaml cp -a \
  "$SEED_PARENT/private" "mattermost:$REMOTE_DIR"
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost /mattermost/bin/mmctl --local export download "${JOB_ID}_export.zip" "$REMOTE_DIR/raw.zip"
LOCAL_DIR="$(mktemp -d ~/archive-work/mm-download-XXXXXXXX)"
sudo docker compose -f /opt/mattermost/compose.yaml cp "mattermost:$REMOTE_DIR/raw.zip" "$LOCAL_DIR/raw.zip"
sudo chown "$(id -u):$(id -g)" "$LOCAL_DIR/raw.zip"
chmod 600 "$LOCAL_DIR/raw.zip"
ln "$LOCAL_DIR/raw.zip" ~/archive-work/raw.zip
python3 -m zipfile -t ~/archive-work/raw.zip
```
No mkdir/sh/id/chmod/rm inside the container is assumed. mkdir/chown above run on the **host**; 2000:2000 applies only to the verified pinned Compose deployment. Have an administrator establish the correct UID:GID for other deployments. Docker cp -a preserves source ownership and permissions. Generate a fresh UUID path every time; never reuse it. Stop immediately if any command fails. ln refuses existing output. The container 0700 directory protects the sensitive ZIP and is retained, not automatically deleted: record its path and handle it under your retention policy without deleting server export originals. Host temporary directories also need retention management. An administrator must check container /tmp capacity separately.


The ZIP test must report no errors. `umask 077` restricts newly created files to their owner by default. The container temporary copy is not automatically removed.

**Already have an export ZIP? Skip steps 1–2** and substitute its path below.

## 3. Download the archiver

**For a public repository, download directly on the server.** Git clone is recommended for easy updates; no login or deploy key is needed.

```sh
cd ~
git clone https://github.com/AndyPandi/mattermost-archiver.git
cd mattermost-archiver
python3 --version
```

Without Git, use either wget or curl to download the ZIP (choose one).

```sh
cd ~
wget -O mattermost-archiver-main.zip https://github.com/AndyPandi/mattermost-archiver/archive/refs/heads/main.zip

# curl alternative (choose ONE download command)
# curl -fL -o mattermost-archiver-main.zip https://github.com/AndyPandi/mattermost-archiver/archive/refs/heads/main.zip

python3 -m zipfile -e mattermost-archiver-main.zip archiver-source
cd ~/archiver-source/mattermost-archiver-main
python3 --version
```

Confirm Python 3.9+. Use a new location if files/directories exist to avoid overwriting. Existing Git clones may use `git pull --ff-only` after inspecting local changes. main is mutable: record or pin a tested commit. Inspect downloaded code before execution; do not pipe downloads into a shell.

**If still private, anonymous downloads fail.** Sign into GitHub, use Code → Download ZIP and transfer the file to the server. Never embed tokens or keys in URLs.

## 4. Convert the archive

Run from the source folder **without sudo**. Inspect the channel list, then convert all public channels.

```sh
python3 mattermost_archiver.py list ~/archive-work/raw.zip
python3 mattermost_archiver.py convert ~/archive-work/raw.zip --all-public --timezone Asia/Seoul --output ~/archive-work/archive.zip
```

To select a channel, replace `--all-public` with `--channel TEAM/CHANNEL`. Success prints the output path and counts. Existing output files are never overwritten.

`metadata_records` means user/role and other metadata records were not copied verbatim into the viewer. Review other omission counts too. See the [detailed manual](docs/manual.en.md) for private channels and categories.

## 5. Verify and view files

Verify on the server:

```sh
python3 mattermost_archiver.py verify ~/archive-work/archive.zip
sha256sum ~/archive-work/archive.zip
```

Run on **your PC**, replacing the key path and server IP (example server user: opc):

```sh
scp -i "<SSH_PRIVATE_KEY>" opc@<SERVER_IP>:/home/opc/archive-work/archive.zip .
```

Compare the server SHA-256 with Linux `sha256sum archive.zip`, macOS `shasum -a 256 archive.zip`, or Windows PowerShell `Get-FileHash archive.zip -Algorithm SHA256`.

Extract into a new folder and open **index.html** in a browser. Check text, chronological order, expandable threads and attachments. Keep the folder structure intact. Internet and SSH tunnels are not needed for viewing.

Attachment names use `sanitized-name__last8hash.ext`, extending the suffix on collision. Integrity verification retains full SHA-256 hashes.

## More information

- [Detailed manual](docs/manual.en.md): automated extraction, resume/recovery, resource limits, categories and private channels
- [Implementation scope](docs/project-state.md)
- ZIPs are unencrypted. Confirm sharing scope and verify an external copy before deleting the server.
- Markdown is plain text; plugin data restoration is not guaranteed. Download is not sanitization: opening HTML/SVG attachments can execute active content. SHA-256 verifies integrity, not authenticity or safety.

## License

Project code and documentation are licensed under the [MIT License](LICENSE). Commercial use, modification and redistribution are permitted subject to retaining the copyright and permission notice. Provided without warranty.

Mattermost and third-party components retain their own licenses. Exported conversations and attachments do not automatically become MIT-licensed.

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
