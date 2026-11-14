"""Resumable full-server export; Python 3.9+, POSIX, no external Python dependencies.

Verified against mattermost/mattermost tag v11.7.0:
server/cmd/mmctl/{commands/export.go,commands/job.go,printer/printer.go},
server/public/model/job.go, server/channels/jobs/export_process/worker.go.
JSON printer normally emits arrays (single-object mode is also accepted).
Job fields are lowercase; export artifact is <job.id>_export.zip.
"""
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tarfile
import io
import time
import uuid


class ExportError(Exception):
    """Sanitized operator-facing error; never contains mmctl output."""


def add_parser(subparsers):
    p = subparsers.add_parser('export', help='Create/resume a full-server export')
    p.add_argument('--compose-file', default='/opt/mattermost/compose.yaml')
    p.add_argument('--output', required=True, help='New host ZIP path; never overwritten')
    p.add_argument('--state', help='State path (default: OUTPUT.state.json); retain for retries')
    p.add_argument('--job-id', help='Explicitly recover/adopt an existing export job')
    p.add_argument('--acknowledge-full-server-export', action='store_true',
                   help='Consent to export ALL server data, including private channels and DMs')
    p.add_argument('--dry-run', action='store_true', help='Local checks/plan only; no Docker or writes')
    p.add_argument('--preflight', action='store_true', help='Read-only Docker checks only; no job or state')
    p.add_argument('--min-free-bytes', type=int, default=1073741824,
                   help='Minimum free host bytes; check container space separately')
    p.add_argument('--poll-interval', type=float, default=5.0)
    p.add_argument('--poll-timeout', type=float, default=3600.0)
    p.add_argument('--command-timeout', type=float, default=600.0)
    p.set_defaults(func=execute)
    return p


def _run(command, timeout, input_data=None):
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, check=False, input=input_data)
    except subprocess.TimeoutExpired:
        raise ExportError('Docker command timed out; state retained. Resume with the same state.') from None
    except OSError:
        raise ExportError('Cannot execute Docker command; check Docker installation and permissions.') from None
    if result.returncode:
        raise ExportError('Docker command failed; inspect server locally. Command output withheld.')
    return result.stdout.decode('utf-8', errors='strict')


def _json(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        raise ExportError('Unexpected mmctl JSON; state retained, no automatic new job.') from None


def _job(text, expected=None):
    value = _json(text)
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if not isinstance(value, dict) or value.get('type') != 'export_process':
        raise ExportError('Expected exactly one export_process job.')
    ident = value.get('id', '')
    if not isinstance(ident, str) or not re.fullmatch('[a-z0-9]{26}', ident):
        raise ExportError('Invalid export job ID in response.')
    if expected and ident != expected:
        raise ExportError('Export job identity mismatch.')
    return value


def _sync_dir(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _save(path, data):
    fd, tmp = tempfile.mkstemp(prefix='.export-state-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        _sync_dir(path.parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextlib.contextmanager
def _lock(path):
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ExportError('Lock must be a regular file.')
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ExportError('Another export owns this state/output lock.') from None
        yield
    finally:
        os.close(fd)  # Keep lock inode: unlinking would allow concurrent lock owners.


def _hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _disk(path, required):
    if shutil.disk_usage(path).free < required:
        raise ExportError('Insufficient host disk space for configured budget.')


def _execute(args):
    if not args.acknowledge_full_server_export:
        raise ExportError('Required: --acknowledge-full-server-export (ALL server data, not channel scoped).')
    for value in (args.poll_interval, args.poll_timeout, args.command_timeout):
        if not math.isfinite(value) or value <= 0:
            raise ExportError('Timeouts and poll interval must be finite positive numbers.')
    if args.min_free_bytes < 0:
        raise ExportError('--min-free-bytes must be nonnegative.')
    if args.job_id and not re.fullmatch('[a-z0-9]{26}', args.job_id):
        raise ExportError('--job-id must be a 26-character lowercase alphanumeric ID.')
    # Resolve parents, not leaf symlinks: pre-existing output symlinks must be refused.
    raw = Path(args.output).absolute()
    output = raw.parent.resolve() / raw.name
    raw_state = Path(args.state or str(output) + '.state.json').absolute()
    state_path = raw_state.parent.resolve() / raw_state.name
    compose = str(Path(args.compose_file).resolve())
    if not Path(compose).is_file() or not output.parent.is_dir() or not state_path.parent.is_dir():
        raise ExportError('Compose file and existing output/state parent directories are required.')
    protected = {str(output), str(state_path), str(state_path) + '.lock', str(output) + '.lock', compose}
    if len(protected) != 5:
        raise ExportError('Compose, output, state and lock paths must be distinct.')
    if os.path.lexists(output):
        raise ExportError('Output already exists; refusing overwrite (even for a completed state).')
    _disk(output.parent, args.min_free_bytes)
    base = ['docker', 'compose', '-f', compose]
    container = base + ['exec', '-T', 'mattermost']
    mmctl = container + ['/mattermost/bin/mmctl', '--local', '--json']
    def run(command, timeout=None, input_data=None):
        return _run(command, args.command_timeout if timeout is None else timeout, input_data)
    print('Full-server export includes private data and attachments; original server export is retained.')
    print('Disk budget is only a floor, not an export-size estimate. Allow server storage plus container /tmp plus host ZIP; these may share a disk.')
    if args.dry_run:
        print('Dry run: preflight, create/adopt, poll, list, private retained download, Docker cp, SHA-256, no-overwrite publish. No Docker calls or writes.')
        return 0
    def preflight():
        _json(run(mmctl + ['export', 'list']))  # Verify local access and JSON compatibility.
        # Allowlist one field; never inspect environment or other secrets.
        cid = run(base + ['ps', '-q', 'mattermost']).strip()
        if not re.fullmatch('[a-f0-9]{12,64}', cid):
            raise ExportError('Expected exactly one running Mattermost container.')
        user = run(['docker', 'inspect', '--format', '{{.Config.User}}', cid]).strip()
        if not re.fullmatch('[0-9]{1,10}:[0-9]{1,10}', user):
            raise ExportError('Container Config.User must specify numeric UID:GID; use the manual workflow for other images.')
        uid, gid = map(int, user.split(':'))
        if max(uid, gid) > 2147483647:
            raise ExportError('Container UID:GID is outside supported range.')
        print('Container free space is not probed: verify /tmp capacity separately before extraction.')
        return cid, uid, gid
    if args.preflight:
        preflight()
        print('Read-only preflight passed; no job created.')
        return 0
    with _lock(Path(str(output) + '.lock')), _lock(Path(str(state_path) + '.lock')):
        if os.path.lexists(output):
            raise ExportError('Output already exists; refusing overwrite.')
        identity = {'version': 1, 'output': str(output), 'compose_file': compose}
        state = dict(identity)
        if os.path.lexists(state_path):
            info = state_path.lstat()
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                raise ExportError('Existing state must be a regular file with mode 0600.')
            state = _json(state_path.read_text(encoding='utf-8'))
            if not isinstance(state, dict) or any(state.get(k) != v for k, v in identity.items()):
                raise ExportError('State does not match output/compose configuration.')
            if state.get('phase') not in ('creating', 'polling', 'download', 'publishing', 'complete'):
                raise ExportError('Unknown state phase; refusing job creation.')
        paths = state.get('temporary_directories', [])
        if not isinstance(paths, list) or any(
                not isinstance(path, str) or not re.fullmatch('/tmp/mm-archiver-[0-9a-f]{32}', path)
                for path in paths):
            raise ExportError('Invalid staging history in state; inspect locally.')
        ident = state.get('job_id')
        if ident and (not isinstance(ident, str) or not re.fullmatch('[a-z0-9]{26}', ident)):
            raise ExportError('Invalid stored job identity; refusing job creation.')
        if args.job_id:
            if ident and ident != args.job_id:
                raise ExportError('--job-id conflicts with stored job identity.')
            ident = args.job_id
        if state.get('phase') and not ident:
            raise ExportError('Creation outcome unknown. Inspect export job list and recover with --job-id; never auto-retrying create.')
        cid, uid, gid = preflight()
        mmctl = ['docker', 'exec', cid, '/mattermost/bin/mmctl', '--local', '--json']
        if not ident:
            state['phase'] = 'creating'
            _save(state_path, state)  # Durable BEFORE any possibly successful remote mutation.
            job = _job(run(mmctl + ['export', 'create', '--include-archived-channels']))
            ident = job['id']
        state.update(job_id=ident, phase='polling')
        _save(state_path, state)
        deadline = time.monotonic() + args.poll_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ExportError('Export polling timed out; resume same state. Job was not canceled.')
            job = _job(run(mmctl + ['export', 'job', 'show', ident],
                           min(args.command_timeout, remaining)), ident)
            status = job.get('status')
            if status == 'success':
                break
            if status in ('error', 'canceled', 'warning', 'cancel_requested'):
                raise ExportError('Export job failed, warned or was canceled; no new job created. Inspect locally.')
            if status not in ('pending', 'in_progress'):
                raise ExportError('Unknown export job status; refusing download.')
            time.sleep(min(args.poll_interval, max(0, deadline - time.monotonic())))
        name = ident + '_export.zip'
        exports = _json(run(mmctl + ['export', 'list']))
        if isinstance(exports, str):
            exports = [exports]
        if not isinstance(exports, list) or name not in exports:
            raise ExportError('Expected job-specific export is not listed; resume later, never select newest.')
        state.update(phase='download', export_name=name)
        _save(state_path, state)
        temporary = '/tmp/mm-archiver-' + uuid.uuid4().hex
        remote_file = temporary + '/export.zip'
        local_tmp = None
        made_remote = False
        try:
            # Archive API carries numeric ownership without host chown/root Python.
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode='w') as tar:
                entry = tarfile.TarInfo(temporary[len('/tmp/'):])
                entry.type = tarfile.DIRTYPE
                entry.mode, entry.uid, entry.gid = 0o700, uid, gid
                tar.addfile(entry)
            state.setdefault('temporary_directories', []).append(temporary)
            _save(state_path, state)
            made_remote = True
            run(['docker', 'cp', '-a', '-', cid + ':/tmp'], input_data=archive.getvalue())
            run(mmctl + ['export', 'download', name, remote_file])
            # Protect bytes even if cp preserves a world-readable file mode.
            with tempfile.TemporaryDirectory(prefix='.mm-export-', dir=str(output.parent)) as staging:
                local_tmp = str(Path(staging) / 'export.zip')
                run(['docker', 'cp', cid + ':' + remote_file, local_tmp])
                info = os.lstat(local_tmp)
                if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
                    raise ExportError('Refusing non-regular or empty copied export.')
                os.chmod(local_tmp, 0o600)
                size = info.st_size
                _disk(output.parent, args.min_free_bytes)
                fd, saved = tempfile.mkstemp(prefix='.mm-export-', dir=str(output.parent))
                os.close(fd)
                os.replace(local_tmp, saved)
                local_tmp = saved
            checksum = _hash(local_tmp)
            with open(local_tmp, 'rb') as stream:
                os.fsync(stream.fileno())
            state.update(phase='publishing', sha256=checksum, bytes=size)
            _save(state_path, state)
            try:
                os.link(local_tmp, output)  # Atomic, same filesystem, NEVER overwrites.
            except FileExistsError:
                raise ExportError('Output appeared during export; refusing overwrite.') from None
            _sync_dir(output.parent)
            state['phase'] = 'complete'
            _save(state_path, state)
            print(json.dumps({'output': str(output), 'job_id': ident, 'bytes': size, 'sha256': checksum}))
        finally:
            if local_tmp and os.path.exists(local_tmp):
                os.unlink(local_tmp)
            if made_remote:
                print('Retention notice: private container staging may remain (no container utilities used): '
                      + temporary + '; recorded in state. Do not delete server export originals.', file=sys.stderr)
        return 0


def execute(args):
    """CLI handler: returns 0 on success, 1 on sanitized operational failure."""
    try:
        return _execute(args)
    except ExportError as error:
        print('Export error: ' + str(error), file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        print('Export error: local I/O or decoding failure; state retained. Inspect locally.', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Export interrupted; retain state and resume. Remote job was not canceled.', file=sys.stderr)
        return 130
