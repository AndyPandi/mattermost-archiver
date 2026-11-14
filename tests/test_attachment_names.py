import contextlib
import html
import io
import json
import unittest
import unicodedata as u
import zipfile
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urlsplit
from unittest.mock import patch
import mattermost_archiver as m
import test_archive


class FilenameTests(unittest.TestCase):
    def test_unicode_nfc_and_original_hash(self):
        for name in ('가상 문서.pptx', 'café 中文 😀.pdf', '보고서.확장자'):
            for original in (name, u.normalize('NFD', name)):
                member = 'data/demo/' + original
                h = m.hashlib.sha256(member.encode()).hexdigest()[-8:]
                stem, ext = name.rsplit('.', 1)
                self.assertEqual(m.attachment_target(member, original, set()),
                                 'attachments/' + stem + '_' + h + '.' + ext)

    def test_canonical_casefold_collision(self):
        used = set()
        with patch.object(m.hashlib, 'sha256') as fake:
            fake.return_value.hexdigest.return_value = 'b' * 64
            for i, name in enumerate(('가상 Straße.pdf', u.normalize('NFD', '가상 STRASSE.pdf'), '가상 strasse.pdf')):
                target = m.attachment_target(str(i), name, used)
                self.assertTrue(target.endswith('_' + 'b' * (8 + i * 4) + '.pdf'))
                self.assertEqual(target, u.normalize('NFC', target))

    def test_reserved_characters_controls_and_names(self):
        name = '가상<>:"/\\|?*' + ''.join(map(chr, (0, 31, 127, 0x202e, 0x2066, 0x200b, 0x2028, 0xd800))) + '.txt'
        target = m.attachment_target('data/synthetic', name, set()).split('/', 1)[1]
        self.assertTrue(target.startswith('가상'))
        self.assertTrue(target.endswith('.txt'))
        self.assertFalse(any(c in '<>:"/\\|?*' or u.category(c).startswith('C') for c in target))
        for name in ('CON.txt', 'aux.more.txt', 'COM1', 'LPT².txt', 'NUL .pdf'):
            self.assertTrue(m.attachment_target('member', name, set()).startswith('attachments/_'))
        for name in ('report.  ', ' . ', '', '...'):
            target = m.attachment_target('member', name, set()).split('/', 1)[1]
            self.assertFalse(target.endswith((' ', '.')))

    def test_byte_unit_extension_bounds_and_full_collision(self):
        for stem in ('가' * 400, '😀' * 400, 'a' * 400):
            for ext in ('.pptx', '.' + '가' * 10, '.' + 'a' * 31, '.' + 'a' * 32, '.' + '가' * 11):
                used = set()
                with patch.object(m.hashlib, 'sha256') as fake:
                    fake.return_value.hexdigest.return_value = 'c' * 64
                    for length in range(8, 65, 4):
                        target = m.attachment_target('member', stem + ext, used).split('/', 1)[1]
                        self.assertLessEqual(len(target.encode()), 240)
                        self.assertLessEqual(len(target.encode('utf-16-le')) // 2, 240)
                        ending = ext if len(ext.encode()) <= 32 else ''
                        self.assertTrue(target.endswith('_' + 'c' * length + ending))
                    with self.assertRaises(m.ArchiveError):
                        m.attachment_target('member', stem + ext, used)
        self.assertEqual(m.filename_prefix('😀😀', 99, 3), '😀')
        self.assertEqual(m.filename_prefix('가가', 5, 99), '가')

    def test_href_bytes_hash_and_exact_nfd_lookup(self):
        fixture = test_archive.ArchiveTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        names = [u.normalize('NFD', '가상 문서 #100% & "견본".pdf'),
                 '가상 문서 #100% & "견본".pdf', '😀' * 100 + '.pptx']
        paths = ['demo/' + name for name in names]
        payloads = [bytes(range(256)) + str(i).encode() for i in range(len(paths))]
        fixture.rows[5]['post']['attachments'] = [{'path': p} for p in paths + paths[:1]]
        fixture.files = {'data/' + p: data for p, data in zip(paths, payloads)}
        fixture.make()
        fixture.run_convert()
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'a' and 'download' in attrs:
                    self.links.append(attrs['href'])
        with zipfile.ZipFile(fixture.out) as z:
            page = z.read('index.html').decode()
            manifest = json.loads(z.read('manifest.json'))
            parser = Links()
            parser.feed(page)
            self.assertEqual(parser.links[0], parser.links[-1])
            self.assertEqual(manifest['counts']['attachments'], 3)
            for href, name, payload in zip(parser.links, names, payloads):
                target = unquote(href)
                self.assertEqual(href, quote(target, safe='/'))
                self.assertEqual(urlsplit(href).fragment, '')
                self.assertNotIn(' ', href)
                self.assertIn(html.escape(name, quote=True), page)
                self.assertEqual(z.read(target), payload)
                self.assertEqual(manifest['files'][target],
                                 {'sha256': m.hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)})
            self.assertIn('%23', parser.links[0])
            self.assertIn('%25', parser.links[0])
        with contextlib.redirect_stdout(io.StringIO()):
            m.verify(fixture.args('verify'))
