import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import export_live as live

JOB = 'a' * 26
PAYLOAD = b'fake archive bytes'


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.compose = self.root / 'compose.yaml'
        self.compose.write_text('services: {}')
        self.output = self.root / 'out.zip'
        self.state = Path(str(self.output) + '.state.json')
        self.calls = []
        self.status = 'success'
        self.create_error = None
        self.copy_error = False
        self.download_error = False
        self.host_copy_error = False
        self.listed = True
        self.container_user = '2345:3456'
        self.container_id = 'b' * 64
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        self.addCleanup(patch.stopall)
        patch('export_live.subprocess.run', side_effect=self.fake).start()
        self.parser = argparse.ArgumentParser()
        live.add_parser(self.parser.add_subparsers())

    def args(self, *extra):
        return self.parser.parse_args(['export', '--compose-file', str(self.compose),
            '--output', str(self.output), '--min-free-bytes', '0',
            '--acknowledge-full-server-export'] + list(extra))

    def execute(self, args=None):
        with contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            return live.execute(args or self.args())

    def fake(self, cmd, **kwargs):
        self.calls.append(cmd)
        self.assertNotIn('shell', kwargs)
        data = b''
        if 'create' in cmd:
            self.assertEqual(json.loads(self.state.read_text())['phase'], 'creating')
            self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
            if self.create_error:
                if isinstance(self.create_error, Exception):
                    raise self.create_error
                return subprocess.CompletedProcess(cmd, 0, self.create_error, b'')
            data = json.dumps([{'id': JOB, 'type': 'export_process', 'status': 'pending'}]).encode()
        elif 'show' in cmd:
            data = json.dumps([{'id': JOB, 'type': 'export_process', 'status': self.status,
                                'data': {'error': 'DO NOT PRINT SECRET'}}]).encode()
        elif cmd[-2:] == ['export', 'list']:
            data = json.dumps([JOB + '_export.zip'] if self.listed else ['other_export.zip']).encode()
        elif 'ps' in cmd:
            data = self.container_id.encode()
        elif 'inspect' in cmd:
            self.assertEqual(cmd, ['docker', 'inspect', '--format', '{{.Config.User}}', self.container_id])
            data = self.container_user.encode()
        elif 'download' in cmd and self.download_error:
            return subprocess.CompletedProcess(cmd, 1, b'SECRET', b'SECRET')
        elif 'cp' in cmd:
            if self.copy_error:
                return subprocess.CompletedProcess(cmd, 1, b'SECRET', b'SECRET')
            if '-a' in cmd:
                with tarfile.open(fileobj=io.BytesIO(kwargs['input'])) as tar:
                    entries = tar.getmembers()
                    self.assertEqual(len(entries), 1)
                    entry = entries[0]
                    self.assertTrue(entry.isdir())
                    self.assertEqual((entry.mode, entry.uid, entry.gid), (0o700, 2345, 3456))
                    self.assertRegex(entry.name, r'^mm-archiver-[0-9a-f]{32}$')
                self.assertEqual(cmd[-1], self.container_id + ':/tmp')
            else:
                if self.host_copy_error:
                    Path(cmd[-1]).write_bytes(b'partial SECRET')
                    return subprocess.CompletedProcess(cmd, 1, b'SECRET', b'SECRET')
                self.assertEqual(Path(cmd[-1]).parent.stat().st_mode & 0o777, 0o700)
                Path(cmd[-1]).write_bytes(PAYLOAD)
                Path(cmd[-1]).chmod(0o644)
        if 'exec' in cmd:
            self.assertIn('/mattermost/bin/mmctl', cmd)
        return subprocess.CompletedProcess(cmd, 0, data, b'')

    def test_complete_hash_permissions_cleanup_and_command(self):
        self.assertEqual(self.execute(), 0)
        self.assertEqual(self.output.read_bytes(), PAYLOAD)
        state = json.loads(self.state.read_text())
        self.assertEqual(state['phase'], 'complete')
        self.assertEqual(state['sha256'], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        create = next(c for c in self.calls if 'create' in c)
        self.assertEqual(create, ['docker', 'exec', self.container_id, '/mattermost/bin/mmctl', '--local', '--json', 'export', 'create',
            '--include-archived-channels'])
        self.assertFalse(any('delete' in c for c in self.calls))
        self.assertFalse(any('rm' in c or 'rmdir' in c for c in self.calls))
        self.assertEqual(len(state['temporary_directories']), 1)
        self.assertIn(state['temporary_directories'][0], self.stderr.getvalue())
        self.assertEqual(list(self.root.glob('.mm-export-*')), [])

    def test_ambiguous_container_user_refused_before_create(self):
        for user in ('', '2000', 'mattermost', '2000:group', '1:2;SECRET', '99999999999:0'):
            self.container_user = user
            self.calls.clear()
            self.assertEqual(self.execute(), 1)
            self.assertFalse(any('create' in c or 'cp' in c for c in self.calls))
        self.assertNotIn('SECRET', self.stderr.getvalue())

    def test_multiple_containers_refused(self):
        self.container_id = 'b' * 64 + '\n' + 'c' * 64
        self.assertEqual(self.execute(), 1)
        self.assertFalse(any('inspect' in c or 'create' in c for c in self.calls))

    def test_resume_keeps_all_private_staging_paths(self):
        self.copy_error = True
        self.assertEqual(self.execute(), 1)
        self.copy_error = False
        self.assertEqual(self.execute(), 0)
        paths = json.loads(self.state.read_text())['temporary_directories']
        self.assertEqual(len(set(paths)), 2)

    def test_download_and_host_copy_failure_private_cleanup(self):
        for attr in ('download_error', 'host_copy_error'):
            setattr(self, attr, True)
            self.assertEqual(self.execute(), 1)
            self.assertFalse(self.output.exists())
            self.assertEqual(list(self.root.glob('.mm-export-*')), [])
            self.assertNotIn('SECRET', self.stderr.getvalue())
            setattr(self, attr, False)
        self.assertEqual(self.execute(), 0)
        self.assertEqual(sum('create' in c for c in self.calls), 1)

    def test_invalid_staging_history_fails_without_docker(self):
        self.copy_error = True
        self.assertEqual(self.execute(), 1)
        state = json.loads(self.state.read_text())
        state['temporary_directories'] = 'SECRET'
        self.state.write_text(json.dumps(state))
        self.calls.clear()
        self.assertEqual(self.execute(), 1)
        self.assertFalse(self.calls)
        self.assertNotIn('SECRET', self.stderr.getvalue())

    def test_acknowledgment_required(self):
        args = self.args()
        args.acknowledge_full_server_export = False
        self.assertEqual(self.execute(args), 1)
        self.assertFalse(self.calls)

    def test_dry_run_no_calls_or_state(self):
        self.assertEqual(self.execute(self.args('--dry-run')), 0)
        self.assertFalse(self.calls)
        self.assertFalse(self.state.exists())
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_read_only_preflight(self):
        self.assertEqual(self.execute(self.args('--preflight')), 0)
        self.assertEqual(len(self.calls), 3)
        self.assertFalse(self.state.exists())

    def test_ambiguous_create_does_not_repeat_and_can_recover(self):
        self.create_error = subprocess.TimeoutExpired('docker', 1, output=b'SECRET')
        self.assertEqual(self.execute(), 1)
        self.assertEqual(json.loads(self.state.read_text())['phase'], 'creating')
        self.calls.clear()
        self.assertEqual(self.execute(), 1)
        self.assertFalse(self.calls)
        self.create_error = None
        self.assertEqual(self.execute(self.args('--job-id', JOB)), 0)
        self.assertFalse(any('create' in c for c in self.calls))
        self.assertNotIn('SECRET', self.stderr.getvalue())

    def test_invalid_create_json_is_ambiguous(self):
        self.create_error = b'not JSON SECRET'
        self.assertEqual(self.execute(), 1)
        self.calls.clear()
        self.assertEqual(self.execute(), 1)
        self.assertFalse(self.calls)
        self.assertNotIn('SECRET', self.stderr.getvalue())

    def test_resume_after_copy_failure_never_creates_again(self):
        self.copy_error = True
        self.assertEqual(self.execute(), 1)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.mm-export-*')), [])
        self.calls.clear()
        self.copy_error = False
        self.assertEqual(self.execute(), 0)
        self.assertFalse(any('create' in c for c in self.calls))
        self.assertNotIn('SECRET', self.stderr.getvalue())

    def test_existing_output_refused_even_after_success(self):
        self.assertEqual(self.execute(), 0)
        self.calls.clear()
        self.assertEqual(self.execute(), 1)
        self.assertFalse(self.calls)
        self.assertEqual(self.output.read_bytes(), PAYLOAD)

    def test_dangling_output_symlink_refused(self):
        self.output.symlink_to(self.root / 'missing')
        self.assertEqual(self.execute(), 1)
        self.assertFalse(self.calls)

    def test_job_terminal_failure_no_sensitive_error(self):
        self.status = 'error'
        self.assertEqual(self.execute(), 1)
        self.assertFalse(any('download' in c for c in self.calls))
        self.assertNotIn('SECRET', self.stderr.getvalue())

    def test_job_poll_timeout_retains_id(self):
        self.status = 'pending'
        with patch('export_live.time.monotonic', side_effect=[0, 0, 2, 2]), patch('export_live.time.sleep'):
            self.assertEqual(self.execute(self.args('--poll-timeout', '1')), 1)
        self.assertEqual(json.loads(self.state.read_text())['job_id'], JOB)

    def test_select_exact_job_artifact_only(self):
        self.listed = False
        self.assertEqual(self.execute(), 1)
        self.assertFalse(any('download' in c for c in self.calls))

    def test_disk_budget_failure_before_docker(self):
        with patch('export_live.shutil.disk_usage') as disk:
            disk.return_value.free = 0
            self.assertEqual(self.execute(self.args('--min-free-bytes', '1')), 1)
        self.assertFalse(self.calls)

    def test_atomic_publish_race_no_overwrite(self):
        def race(source, dest):
            Path(dest).write_bytes(b'competitor')
            raise FileExistsError()
        with patch('export_live.os.link', side_effect=race):
            self.assertEqual(self.execute(), 1)
        self.assertEqual(self.output.read_bytes(), b'competitor')

    def test_lock_excludes_second_owner(self):
        with live._lock(Path(str(self.output) + '.lock')):
            self.assertEqual(self.execute(), 1)
        self.assertFalse(self.calls)

    def test_wrong_job_type_and_id_rejected(self):
        for job in ({'id': JOB, 'type': 'import_process'},
                    {'id': 'bad', 'type': 'export_process'}):
            with self.assertRaises(live.ExportError):
                live._job(json.dumps([job]))

    def test_single_object_json_supported(self):
        job = {'id': JOB, 'type': 'export_process', 'status': 'success'}
        self.assertEqual(live._job(json.dumps(job)), job)

    def test_nonfinite_timeout_rejected(self):
        self.assertEqual(self.execute(self.args('--poll-timeout', 'nan')), 1)
        self.assertFalse(self.calls)


if __name__ == '__main__':
    unittest.main()
