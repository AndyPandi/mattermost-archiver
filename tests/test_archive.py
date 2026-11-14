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
                         'attachments/report_' + expected + '.pptx')

    def test_attachment_collision_expands_case_insensitively(self):
        used = set()
        with patch.object(m.hashlib, 'sha256') as fake:
            fake.return_value.hexdigest.return_value = 'a' * 64
            first = m.attachment_target('one', 'Report.pdf', used)
            second = m.attachment_target('two', 'report.pdf', used)
            third = m.attachment_target('three', 'report.pdf', used)
        self.assertEqual(first, 'attachments/Report_aaaaaaaa.pdf')
        self.assertEqual(second, 'attachments/report_aaaaaaaaaaaa.pdf')
        self.assertEqual(third, 'attachments/report_aaaaaaaaaaaaaaaa.pdf')

    def test_full_attachment_collision_refused(self):
        with patch.object(m.hashlib, 'sha256') as fake:
            fake.return_value.hexdigest.return_value = 'a' * 64
            used = {'attachments/report_' + 'a' * n for n in range(8, 65, 4)}
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

    def viewer(self):
        with zipfile.ZipFile(self.out) as z:
            return z.read('index.html').decode()

    def test_emoji_group_unique_users_preserve_records(self):
        self.rows[4]['post']['reactions'] = [
            {'user': user, 'emoji_name': name, 'create_at': at}
            for user, name, at in [('a', '+1', 0), ('a', 'thumbs_up', 1),
                                   ('b', 'thumbsup', 2), ('c', 'grinning', 3),
                                   ('d', 'white_check_mark', 4)]]
        self.make()
        self.run_convert()
        page = self.viewer()
        self.assertEqual(page.count('<details class="reaction">'), 3)
        self.assertIn('👍</span> <b>2</b>', page)
        self.assertIn('😀</span> <b>1</b>', page)
        self.assertNotIn('😃', page)
        self.assertIn('✅</span> <b>1</b>', page)
        for iso in ('1970-01-01T09:00:00+09:00', '1970-01-01T09:00:00.001000+09:00',
                    '1970-01-01T09:00:00.002000+09:00'):
            self.assertIn('datetime="' + iso + '" title="' + iso + '"', page)
        self.assertIn('고유 사용자 수', page)

    def test_unknown_reactions_and_metadata_escaped(self):
        evil = '"><img src=x onerror=alert(1)><section><article class="post">'
        self.rows[2]['channel']['display_name'] = evil
        self.rows[4]['post']['user'] = evil
        self.rows[4]['post']['reactions'] = [
            {'user': evil, 'emoji_name': evil, 'create_at': 0},
            {'user': 'synthetic', 'emoji_name': 'custom_demo', 'create_at': 1}]
        self.make()
        self.run_convert()
        page = self.viewer()
        self.assertIn(':custom_demo:', page)
        self.assertIn(':&quot;&gt;&lt;img', page)
        for tag in ('<img', '<script', '<iframe', '<svg', '<object'):
            self.assertNotIn(tag, page)
        with contextlib.redirect_stdout(io.StringIO()):
            m.verify(self.args('verify'))

    def test_chat_navigation_empty_channels_and_day_boundaries(self):
        from html.parser import HTMLParser
        self.rows.append({'type': 'channel', 'channel': {'team': 'other', 'name': 'empty', 'type': 'O', 'display_name': None}})
        self.rows[4]['post']['create_at'] = 86400000
        self.rows[4]['post']['message'] = '긴 메시지 English ' + 'long' * 1000
        self.make()
        self.run_convert()
        page = self.viewer()
        class Markup(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.links, self.tags = [], [], []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                self.tags.append((tag, attrs))
                if 'id' in attrs:
                    self.ids.append(attrs['id'])
                if tag == 'a':
                    self.links.append(attrs.get('href', ''))
        parser = Markup()
        parser.feed(page)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for link in parser.links:
            if link.startswith('#'):
                self.assertIn(link[1:], parser.ids)
            else:
                self.assertTrue(link.startswith('attachments/'))
        self.assertEqual(page.count('class="day-separator"'), 2)
        self.assertIn('1970-01-02 09:00', page)
        self.assertIn('아직 보관된 메시지가 없습니다.', page)
        self.assertIn('@media(max-width:640px)', page)
        self.assertIn('overflow-wrap:anywhere', page)
        self.assertIn('default-src &#39;none&#39;', page)
        self.assertNotIn('url(', page)
        self.assertEqual(page.count('답글 1개'), 2)
        with contextlib.redirect_stdout(io.StringIO()):
            m.verify(self.args('verify'))

    def test_avatars_deterministic_and_null_metadata(self):
        import re
        self.rows[4]['post']['user'] = 'Synthetic User'
        self.rows[4]['post']['replies'][0]['user'] = 'Synthetic User'
        self.rows[4]['post']['edit_at'] = 0
        self.make()
        self.run_convert()
        page = self.viewer()
        avatars = re.findall(r'class="avatar (color-[0-5])">SU</span>', page)
        self.assertEqual(len(avatars), 2)
        self.assertEqual(avatars[0], avatars[1])
        self.assertIn('수정 <time datetime="1970-01-01T09:00:00+09:00"', page)

    def test_verify_count_markers_across_small_chunks(self):
        self.run_convert()
        with patch.object(m, 'CHUNK', 43), contextlib.redirect_stdout(io.StringIO()):
            m.verify(self.args('verify'))

    def test_legacy_v1_viewer_verification(self):
        self.run_convert()
        with zipfile.ZipFile(self.out) as z:
            entries = {n: z.read(n) for n in z.namelist()}
        # Synthetic legacy markup, same exact markers used by d9a7bbd.
        page = b'<html><section><article class="post"></article><article class="post"><details><article class="reply"><article class="reply"></article></article></details></article></section></html>'
        manifest = json.loads(entries['manifest.json'])
        manifest['files']['index.html'] = {'sha256': m.hashlib.sha256(page).hexdigest(), 'bytes': len(page)}
        entries['index.html'] = page
        entries['manifest.json'] = json.dumps(manifest).encode()
        with zipfile.ZipFile(self.out, 'w') as z:
            for name, data in entries.items():
                z.writestr(name, data)
        with contextlib.redirect_stdout(io.StringIO()):
            m.verify(self.args('verify'))

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

    def assert_invalid_input(self):
        self.make()
        with self.assertRaises(m.ArchiveError) as error:
            self.run_convert()
        self.assertNotIn('SENSITIVE', str(error.exception))
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.root.glob('.mm-archive-*')), [])
        result = subprocess.run([sys.executable, m.__file__, 'convert', str(self.raw),
                                 '--output', str(self.out), '--all-public',
                                 '--min-free-bytes', '1'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn('SENSITIVE', result.stderr + result.stdout)
        self.assertFalse(self.out.exists())

    def test_malformed_channel_metadata(self):
        for value in ([], ['SENSITIVE'], None, 'SENSITIVE',
                      {'team': [], 'name': 'x', 'type': 'O'},
                      {'team': 'demo', 'name': {}, 'type': 'O'},
                      {'team': 'demo', 'name': 'x', 'type': []},
                      {'team': 'demo', 'name': 'x', 'type': 'O', 'display_name': {}}):
            with self.subTest(value=value):
                self.rows[2]['channel'] = value
                self.assert_invalid_input()
                with self.assertRaises(m.ArchiveError):
                    m.list_archive(self.args('list'))

    def test_malformed_post_scalars(self):
        import copy
        original = copy.deepcopy(self.rows[4]['post'])
        for field, value in [('team', []), ('channel', {}), ('user', {}),
                             ('message', ['SENSITIVE']), ('create_at', True),
                             ('create_at', 'SENSITIVE'), ('create_at', None),
                             ('create_at', 1.5), ('create_at', 10**100),
                             ('edit_at', []), ('is_pinned', 'SENSITIVE')]:
            with self.subTest(field=field, value=value):
                self.rows[4]['post'] = copy.deepcopy(original)
                self.rows[4]['post'][field] = value
                self.assert_invalid_input()

    def test_malformed_nested_collections(self):
        import copy
        original = copy.deepcopy(self.rows[4]['post'])
        cases = [(field, value) for field in ('replies', 'reactions', 'attachments')
                 for value in ({}, 'SENSITIVE', 1, [None], ['SENSITIVE'], [[]])]
        cases += [('attachments', [{}]), ('attachments', [{'path': []}]),
                  ('reactions', [{}]), ('reactions', [{'user': {}, 'emoji_name': 'x', 'create_at': 1}]),
                  ('reactions', [{'user': 'x', 'emoji_name': [], 'create_at': 1}]),
                  ('reactions', [{'user': 'x', 'emoji_name': 'x', 'create_at': False}]),
                  ('replies', [{'create_at': 'SENSITIVE'}])]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.rows[4]['post'] = copy.deepcopy(original)
                self.rows[4]['post'][field] = value
                self.assert_invalid_input()

    def test_reply_scope_rejection_recursive(self):
        import copy
        original = copy.deepcopy(self.rows[4]['post'])
        for depth in (0, 1):
            for field, value in [('team', 'SENSITIVE'), ('channel', 'secret-room'),
                                 ('team', None), ('channel', None), ('channel', [])]:
                with self.subTest(depth=depth, field=field, value=value):
                    self.rows[4]['post'] = copy.deepcopy(original)
                    reply = self.rows[4]['post']['replies'][0]
                    if depth:
                        reply = reply['replies'][0]
                    reply[field] = value
                    self.assert_invalid_input()

    def test_reply_inherited_and_explicit_scope(self):
        reply = self.rows[4]['post']['replies'][0]
        reply.update(team='demo', channel='public')
        reply['replies'][0]['channel'] = 'public'
        self.make()
        self.run_convert()
        with contextlib.redirect_stdout(io.StringIO()):
            m.verify(self.args('verify'))

    def test_nullable_optional_export_fields(self):
        post = self.rows[4]['post']
        for field in ('message', 'user', 'edit_at', 'is_pinned', 'attachments', 'reactions', 'replies'):
            post[field] = None
        self.make()
        self.run_convert()
        with contextlib.redirect_stdout(io.StringIO()):
            m.verify(self.args('verify'))

    def test_selection_union_and_privacy_guards(self):
        channels = {('a', 'one'): {'type': 'O'}, ('a', 'two'): {'type': 'O'},
                    ('a', 'private'): {'type': 'P'}, ('b', 'one'): {'type': 'O'}}
        a = self.args()
        a.all_public = False
        a.channel = ['a/one']
        self.assertEqual(m.selected_channels(channels, a), {('a', 'one')})
        a.team = ['a']
        a.channel = ['b/one']
        self.assertEqual(m.selected_channels(channels, a), set(channels) - {('a', 'private')})
        a.include_private = True
        self.assertEqual(m.selected_channels(channels, a), set(channels))
        a.team = a.channel = None
        a.all_public = True
        self.assertNotIn(('a', 'private'), m.selected_channels(channels, a))
        a.all_public = False
        a.channel = ['a/private']
        a.include_private = False
        with self.assertRaises(m.ArchiveError):
            m.selected_channels(channels, a)
        a.include_private = True
        self.assertEqual(m.selected_channels(channels, a), {('a', 'private')})
        a.all_public = True
        self.assertEqual(m.selected_channels(channels, a), set(channels))

    def test_malformed_manifest_shapes(self):
        for manifest in ([], None, {'format': 'mattermost-offline-archive', 'version': 1, 'files': []},
                         {'format': 'mattermost-offline-archive', 'version': 1,
                          'files': {'index.html': ['SENSITIVE']}}):
            with self.subTest(manifest=manifest):
                with zipfile.ZipFile(self.out, 'w') as z:
                    z.writestr('manifest.json', json.dumps(manifest))
                with self.assertRaises(m.ArchiveError):
                    m.verify(self.args('verify'))

    def test_list(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            m.list_archive(self.args('list'))
        self.assertEqual(len(json.loads(out.getvalue())['channels']), 2)


if __name__ == '__main__':
    unittest.main()
