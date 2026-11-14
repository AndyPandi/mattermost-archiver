import contextlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import mattermost_archiver as m


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = self.root / 'raw.zip'
        self.out = self.root / 'out.zip'
        self.rows = [
            {'type': 'version', 'version': 1},
            {'type': 'user', 'user': {'username': 'alice', 'email': 'secret@example.invalid', 'roles': 'system_admin'}},
            {'type': 'channel', 'channel': {'team': 'demo', 'name': 'public', 'type': 'O'}},
            {'type': 'channel', 'channel': {'team': 'demo', 'name': 'secret-room', 'type': 'P'}},
            {'type': 'post', 'post': {'team': 'demo', 'channel': 'public', 'user': 'alice', 'create_at': 2000, 'edit_at': 3000, 'is_pinned': True, 'message': '<script>alert(1)</script>\n![x](https://bad.invalid/x)', 'reactions': [{'user': 'bob', 'emoji_name': '+1', 'create_at': 3000}], 'replies': [{'user': 'bob', 'message': 'nested', 'create_at': 2500, 'replies': [{'user': 'alice', 'message': 'deep', 'create_at': 2600}]}]}},
            {'type': 'post', 'post': {'team': 'demo', 'channel': 'public', 'user': 'bob', 'create_at': 1000, 'message': '', 'attachments': [{'path': '20261114/teams/a/channels/b/users/c/file/report.svg'}]}},
            {'type': 'post', 'post': {'team': 'demo', 'channel': 'secret-room', 'user': 'alice', 'create_at': 1000, 'message': 'PRIVATE-MESSAGE'}},
            {'type': 'direct_post', 'direct_post': {'message': 'DM-MESSAGE'}},
            {'type': 'future_extension', 'future_extension': {'private': 'do not copy'}},
        ]
        self.files = {'data/20261114/teams/a/channels/b/users/c/file/report.svg': b'<svg onload="alert(1)"/>'}
        self.make()

    def make(self, extras=None, compression=zipfile.ZIP_STORED):
        with zipfile.ZipFile(self.raw, 'w', compression=compression) as z:
            z.writestr('import.jsonl', '\n'.join(json.dumps(r) for r in self.rows) + '\n')
            for name, data in self.files.items():
                z.writestr(name, data)
            for name, data in extras or []:
                z.writestr(name, data)

    def args(self, cmd='convert', *extra):
        base = [cmd, str(self.out if cmd == 'verify' else self.raw)]
        if cmd == 'convert':
            base += ['--output', str(self.out), '--all-public', '--min-free-bytes', '1']
        return m.build_parser().parse_args(base + list(extra))

    def run_convert(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            m.convert(self.args('convert', *extra))

    def test_short_attachment_name(self):
        used = set()
        member = 'data/path/report.pptx'
        expected = m.hashlib.sha256(member.encode()).hexdigest()[-8:]
        self.assertEqual(m.attachment_target(member, 'report.pptx', used),
                         'attachments/report__' + expected + '.pptx')

    def test_attachment_collision_expands_case_insensitively(self):
        used = set()
        with patch.object(m.hashlib, 'sha256') as fake:
            fake.return_value.hexdigest.return_value = 'a' * 64
            first = m.attachment_target('one', 'Report.pdf', used)
            second = m.attachment_target('two', 'report.pdf', used)
            third = m.attachment_target('three', 'report.pdf', used)
        self.assertEqual(first, 'attachments/Report__aaaaaaaa.pdf')
        self.assertEqual(second, 'attachments/report__aaaaaaaaaaaa.pdf')
        self.assertEqual(third, 'attachments/report__aaaaaaaaaaaaaaaa.pdf')

    def test_full_attachment_collision_refused(self):
        with patch.object(m.hashlib, 'sha256') as fake:
            fake.return_value.hexdigest.return_value = 'a' * 64
            used = {'attachments/report__' + 'a' * n for n in range(8, 65, 4)}
            with self.assertRaises(m.ArchiveError):
                m.attachment_target('one', 'report', used)

    def test_end_to_end_offline_private_filter_and_counts(self):
        self.run_convert()
        with contextlib.redirect_stdout(io.StringIO()):
            m.verify(self.args('verify'))
        with zipfile.ZipFile(self.out) as z:
            page = z.read('index.html').decode()
            manifest = json.loads(z.read('manifest.json'))
            self.assertNotIn('<script>', page)
            self.assertIn('&lt;script&gt;', page)
            self.assertNotIn('<img', page)
            self.assertIn('<details>', page)
            self.assertIn('download rel=', page)
            self.assertIn('+09:00', page)
            self.assertEqual(manifest['counts'], {'posts': 2, 'replies': 2, 'attachments': 1, 'channels': 1})
            for forbidden in ('secret-room', 'PRIVATE-MESSAGE', 'DM-MESSAGE', 'secret@example.invalid', 'system_admin'):
                self.assertNotIn(forbidden, page + json.dumps(manifest))
            self.assertEqual(manifest['skipped']['unsupported_records'], 1)
            self.assertEqual(manifest['skipped']['direct_posts'], 1)
            self.assertLess(page.index('untrusted attachment)</p>'), page.index('&lt;script&gt;'))

    def test_missing_attachment_atomic(self):
        self.files = {}
        self.make()
        with self.assertRaises(m.ArchiveError):
            self.run_convert()
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.root.glob('.mm-archive-*')), [])

    def test_no_overwrite(self):
        self.out.write_bytes(b'original')
        with self.assertRaises(m.ArchiveError):
            self.run_convert()
        self.assertEqual(self.out.read_bytes(), b'original')

    def test_explicit_selection_required(self):
        a = self.args()
        a.all_public = False
        with self.assertRaises(m.ArchiveError):
            m.convert(a)

    def test_private_opt_in(self):
        self.run_convert('--team', 'demo', '--include-private')
        with zipfile.ZipFile(self.out) as z:
            self.assertIn(b'PRIVATE-MESSAGE', z.read('index.html'))

    def test_path_traversal(self):
        for name in ('../escape', '/absolute', 'data/../escape', 'C:/file', 'data\\evil', 'data//evil'):
            with self.subTest(name=name):
                self.make([(name, b'bad')])
                with self.assertRaises(m.ArchiveError):
                    self.run_convert()

    def test_symlink(self):
        i = zipfile.ZipInfo('data/link')
        i.create_system = 3
        i.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.make([(i, b'/etc/passwd')])
        with self.assertRaises(m.ArchiveError):
            self.run_convert()

    def test_duplicate_case(self):
        self.make([('IMPORT.JSONL', b'bad')])
        with self.assertRaises(m.ArchiveError):
            self.run_convert()

    def test_bomb_budget(self):
        self.make([('data/bomb', b'0' * 1000000)], zipfile.ZIP_DEFLATED)
        with self.assertRaises(m.ArchiveError):
            self.run_convert()

    def test_record_line_memory_depth_budgets(self):
        for flags in [('--max-records', '2'), ('--max-line-bytes', '20'), ('--max-post-bytes', '10'), ('--max-depth', '1'), ('--max-bytes', '20'), ('--max-entries', '1')]:
            with self.subTest(flags=flags), self.assertRaises(m.ArchiveError):
                self.run_convert(*flags)

    def test_disk_budget(self):
        with patch.object(m.shutil, 'disk_usage', return_value=type('D', (), {'free': 0})()):
            with self.assertRaises(m.ArchiveError):
                self.run_convert()

    def test_tamper(self):
        self.run_convert()
        with zipfile.ZipFile(self.out) as z:
            entries = {n: z.read(n) for n in z.namelist()}
        entries['index.html'] += b'changed'
        with zipfile.ZipFile(self.out, 'w') as z:
            for name, data in entries.items():
                z.writestr(name, data)
        with self.assertRaises(m.ArchiveError):
            m.verify(self.args('verify'))

    def test_count_tamper(self):
        self.run_convert()
        with zipfile.ZipFile(self.out) as z:
            entries = {n: z.read(n) for n in z.namelist()}
        manifest = json.loads(entries['manifest.json'])
        manifest['counts']['posts'] += 1
        entries['manifest.json'] = json.dumps(manifest).encode()
        with zipfile.ZipFile(self.out, 'w') as z:
            for name, data in entries.items():
                z.writestr(name, data)
        with self.assertRaises(m.ArchiveError):
            m.verify(self.args('verify'))

    def test_cli_subprocess_end_to_end(self):
        cli = str(Path(m.__file__))
        for command in [
            ['list', str(self.raw)],
            ['convert', str(self.raw), '--output', str(self.out), '--all-public', '--min-free-bytes', '1'],
            ['verify', str(self.out)],
        ]:
            result = subprocess.run([sys.executable, cli] + command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, cli, 'export', '--output', str(self.root / 'new.zip')], capture_output=True)
        self.assertEqual(result.returncode, 1)

    def test_list(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            m.list_archive(self.args('list'))
        self.assertEqual(len(json.loads(out.getvalue())['channels']), 2)


if __name__ == '__main__':
    unittest.main()
