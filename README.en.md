# Mattermost Archiver

[한국어](README.md) · [English](README.en.md)

**Convert Mattermost conversations and attachments into readable, offline HTML archives.** Browse teams, channels, threads and attachment links without a running server. View the resulting HTML on Windows, macOS or Linux.

Conversion uses Python 3.9+ and its standard library (no pip installation). Commands below target a **Linux server running Mattermost with Docker Compose**. Viewing HTML needs neither Python nor Mattermost. Native Windows CLI execution has not been validated.

> Raw exports may contain private channels, DMs and other sensitive server-wide data. Restrict them to administrators. The conversion example includes public channels only; DM conversion is unsupported. This is not a full backup/restore tool.

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
REMOTE_DIR="/tmp/archive-$JOB_ID"
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost mkdir -m 700 "$REMOTE_DIR"
sudo docker compose -f /opt/mattermost/compose.yaml exec -T mattermost /mattermost/bin/mmctl --local export download "${JOB_ID}_export.zip" "$REMOTE_DIR/raw.zip"
sudo docker compose -f /opt/mattermost/compose.yaml cp "mattermost:$REMOTE_DIR/raw.zip" ~/archive-work/raw.zip
sudo chown "$(id -u):$(id -g)" ~/archive-work/raw.zip
chmod 600 ~/archive-work/raw.zip
unzip -t ~/archive-work/raw.zip
```

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
- Markdown is plain text; plugin data restoration is not guaranteed. Open only trusted attachments.
