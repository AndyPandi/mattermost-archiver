import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
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
        self.listed = True
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
        elif 'df' in cmd:
            data = b'Filesystem 1024-blocks Used Available Capacity Mounted on\nx 100000 0 100000 0% /tmp\n'
        elif 'stat' in cmd:
            data = str(len(PAYLOAD)).encode()
        elif 'cp' in cmd:
            if self.copy_error:
                return subprocess.CompletedProcess(cmd, 1, b'SECRET', b'SECRET')
            Path(cmd[-1]).write_bytes(PAYLOAD)
        return subprocess.CompletedProcess(cmd, 0, data, b'')

    def test_complete_hash_permissions_cleanup_and_command(self):
        self.assertEqual(self.execute(), 0)
        self.assertEqual(self.output.read_bytes(), PAYLOAD)
        state = json.loads(self.state.read_text())
        self.assertEqual(state['phase'], 'complete')
        self.assertEqual(state['sha256'], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        create = next(c for c in self.calls if 'create' in c)
        self.assertEqual(create, ['docker', 'compose', '-f', str(self.compose), 'exec', '-T',
            'mattermost', '/mattermost/bin/mmctl', '--local', '--json', 'export', 'create',
            '--include-archived-channels'])
        self.assertFalse(any('delete' in c for c in self.calls))
        remove = next(c for c in self.calls if 'rm' in c)
        self.assertTrue(remove[-1].startswith('/tmp/mm-archiver-'))
        self.assertEqual(list(self.root.glob('.mm-export-*')), [])

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
        self.assertEqual(len(self.calls), 2)
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
