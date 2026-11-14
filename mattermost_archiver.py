#!/usr/bin/env python3
"""Mattermost bulk export to inert, offline HTML. Python 3.9+, stdlib only."""
import argparse
import collections
import contextlib
import datetime
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from zoneinfo import ZoneInfo

VERSION = '0.1.0'
CHUNK = 1024 * 1024


class ArchiveError(Exception):
    pass


def digest(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(CHUNK), b''):
        h.update(block)
    return h.hexdigest()


def attachment_target(member, base, used):
    """Short path hash suffix, expanded on case-insensitive filename collision."""
    suffix = PurePosixPath(base).suffix
    stem = base[:-len(suffix)] if suffix else base
    full_hash = hashlib.sha256(member.encode()).hexdigest()
    for length in range(8, 65, 4):
        target = 'attachments/' + stem + '__' + full_hash[-length:] + suffix
        if target.casefold() not in used:
            used.add(target.casefold())
            return target
    raise ArchiveError('Attachment filename collision even at full SHA-256')


def safe_name(name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ArchiveError('Unsafe ZIP/path name')
    parts = name.rstrip('/').split('/')
    if name.startswith('/') or any(p in ('', '.', '..') or ':' in p for p in parts):
        raise ArchiveError('Unsafe ZIP/path name')
    return name


def inspect_zip(z, args):
    infos = z.infolist()
    if os.fstat(z.fp.fileno()).st_size > args.max_bytes:
        raise ArchiveError('Compressed ZIP byte budget exceeded')
    if len(infos) > args.max_entries:
        raise ArchiveError('ZIP entry budget exceeded')
    seen = set()
    total = 0
    for info in infos:
        safe_name(info.filename)
        key = info.filename.rstrip('/').casefold()
        if key in seen:
            raise ArchiveError('Duplicate/case-colliding ZIP member')
        seen.add(key)
        mode = info.external_attr >> 16
        if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ArchiveError('Symlink/special ZIP member refused')
        if info.flag_bits & 1:
            raise ArchiveError('Encrypted ZIP unsupported')
        total += info.file_size
        if total > args.max_bytes or info.file_size > args.max_bytes:
            raise ArchiveError('Uncompressed ZIP byte budget exceeded')
        if info.file_size > max(1, info.compress_size) * args.max_ratio:
            raise ArchiveError('ZIP compression ratio budget exceeded')
    return total


@contextlib.contextmanager
def open_zip(path, args):
    # zipfile reads the central directory eagerly: bound it before allocation.
    with open(path, 'rb') as stream:
        if os.fstat(stream.fileno()).st_size > args.max_bytes:
            raise ArchiveError('Compressed ZIP byte budget exceeded')
        end = zipfile._EndRecData(stream)
        if end is None:
            raise ArchiveError('Invalid ZIP end record')
        if end[zipfile._ECD_ENTRIES_TOTAL] > args.max_entries or end[zipfile._ECD_SIZE] > 64 * 1024**2:
            raise ArchiveError('ZIP central-directory budget exceeded')
        stream.seek(0)
        with zipfile.ZipFile(stream) as z:
            yield z


def records(z, args):
    if 'import.jsonl' not in z.namelist():
        raise ArchiveError('Expected root import.jsonl')
    with z.open('import.jsonl') as f:
        n = 0
        while True:
            line = f.readline(args.max_line_bytes + 1)
            if not line:
                break
            if len(line) > args.max_line_bytes:
                raise ArchiveError('JSONL line budget exceeded')
            n += 1
            if n > args.max_records:
                raise ArchiveError('JSONL record budget exceeded')
            try:
                item = json.loads(line)
            except (ValueError, UnicodeError):
                raise ArchiveError('Invalid JSONL at line %d' % n)
            if not isinstance(item, dict) or not isinstance(item.get('type'), str):
                raise ArchiveError('Invalid record envelope at line %d' % n)
            yield item


def scan(z, args):
    channels = {}
    version = None
    types = collections.Counter()
    for r in records(z, args):
        t = r['type']
        types[t] += 1
        if t == 'version':
            if version is not None or r.get('version') != 1:
                raise ArchiveError('Expected exactly one supported export version (1)')
            version = r['version']
        if t == 'channel':
            c = r.get('channel', {})
            key = (c.get('team'), c.get('name'))
            if not all(isinstance(x, str) and x for x in key) or c.get('type') not in ('O', 'P'):
                raise ArchiveError('Invalid channel metadata')
            if key in channels:
                raise ArchiveError('Duplicate channel metadata')
            channels[key] = c
    if version is None:
        raise ArchiveError('Missing export version')
    return channels, version, types


def list_archive(args):
    with open_zip(args.input, args) as z:
        inspect_zip(z, args)
        channels, version, types = scan(z, args)
    # Listing is intentionally explicit and local; never included in filtered output.
    print(json.dumps({'version': version, 'channels': [
        {'team': k[0], 'channel': k[1], 'type': c['type']} for k, c in sorted(channels.items())],
        'record_counts': dict(types)}, ensure_ascii=True, indent=2))


def selected_channels(channels, args):
    teams, names = set(args.team or []), set(args.channel or [])
    if not (teams or names or args.all_public):
        raise ArchiveError('Select --team, --channel TEAM/CHANNEL, or --all-public')
    if teams - {k[0] for k in channels} or names - {'/'.join(k) for k in channels}:
        raise ArchiveError('Unknown selected team/channel')
    selected = {k for k, c in channels.items() if
                ((args.all_public and c['type'] == 'O') or k[0] in teams or '/'.join(k) in names)
                and (c['type'] == 'O' or args.include_private)}
    if not selected:
        raise ArchiveError('Selection is empty (private channels require --include-private)')
    return selected


def publish(temp, output):
    # Same-filesystem hard link is atomic and refuses any existing destination.
    os.link(temp, output)


def convert(args):
    output = Path(args.output).absolute()
    if output.exists() or output.is_symlink():
        raise ArchiveError('Output already exists; choose a new path')
    tz = ZoneInfo(args.timezone)
    categories = {}
    if args.categories:
        if Path(args.categories).stat().st_size > 1024 * 1024:
            raise ArchiveError('Categories configuration too large')
        categories = json.loads(Path(args.categories).read_text(encoding='utf-8'))
        if not isinstance(categories, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in categories.items()):
            raise ArchiveError('Categories must map TEAM/CHANNEL to category strings')
    if Path(args.input).stat().st_size > args.max_bytes:
        raise ArchiveError('Compressed ZIP byte budget exceeded')
    with open(args.input, 'rb') as src:
        input_hash = digest(src)
    with open_zip(args.input, args) as z:
        total = inspect_zip(z, args)
        channels, version, types = scan(z, args)
        selected = selected_channels(channels, args)
        # Conservative staging estimate, not a promise about filesystem compression/quota.
        required = total * 3 + args.min_free_bytes
        if shutil.disk_usage(output.parent).free < required:
            raise ArchiveError('Insufficient disk: need uncompressed input * 3 + reserve')
        groups = collections.defaultdict(list)
        skipped = collections.Counter()
        used = 0
        for r in records(z, args):
            t = r['type']
            if t == 'post':
                p = r.get('post')
                if not isinstance(p, dict):
                    raise ArchiveError('Invalid post')
                key = (p.get('team'), p.get('channel'))
                if key not in channels:
                    raise ArchiveError('Post references unknown channel')
                if key in selected:
                    used += len(json.dumps(p, ensure_ascii=False).encode('utf-8'))
                    if used > args.max_post_bytes:
                        raise ArchiveError('Selected post memory budget exceeded')
                    groups[key].append(p)
                else:
                    skipped['excluded_posts'] += 1
            elif t not in ('version', 'team', 'channel', 'user', 'role', 'scheme', 'bot', 'emoji', 'direct_channel'):
                skipped['direct_posts' if t == 'direct_post' else 'unsupported_records'] += 1
            else:
                skipped['metadata_records'] += 1
        with tempfile.TemporaryDirectory(prefix='.mm-archive-', dir=output.parent) as td:
            stage = Path(td)
            (stage / 'attachments').mkdir()
            files = {}
            attachments = {}
            used_attachment_names = set()
            counts = {'posts': 0, 'replies': 0, 'attachments': 0, 'channels': len(selected)}

            def attach(path):
                safe_name(path)
                member = 'data/' + path  # v11.7.0 ExportDataDir = "data"
                if member in attachments:
                    return attachments[member]
                try:
                    info = z.getinfo(member)
                except KeyError:
                    raise ArchiveError('Selected attachment missing from export')
                if info.is_dir():
                    raise ArchiveError('Attachment is a directory')
                base = re.sub(r'[^A-Za-z0-9._-]', '_', PurePosixPath(path).name)[:100] or 'attachment'
                target = attachment_target(member, base, used_attachment_names)
                h = hashlib.sha256()
                size = 0
                with z.open(info) as src, open(stage / target, 'xb') as dst:
                    for block in iter(lambda: src.read(CHUNK), b''):
                        dst.write(block)
                        h.update(block)
                        size += len(block)
                files[target] = {'sha256': h.hexdigest(), 'bytes': size}
                attachments[member] = target
                counts['attachments'] += 1
                return target

            def esc(value):
                return html.escape(str(value), quote=True)

            def timestamp(value):
                if not isinstance(value, (int, float)):
                    raise ArchiveError('Invalid post timestamp')
                return datetime.datetime.fromtimestamp(value / 1000, tz).isoformat()

            def render(p, depth=0):
                if depth > args.max_depth or not isinstance(p, dict):
                    raise ArchiveError('Reply nesting budget exceeded or malformed reply')
                counts['replies' if depth else 'posts'] += 1
                if counts['posts'] + counts['replies'] > args.max_records:
                    raise ArchiveError('Post/reply count budget exceeded')
                header = esc(p.get('user', 'unknown')) + ' · ' + esc(timestamp(p.get('create_at')))
                if p.get('edit_at'):
                    header += ' · edited ' + esc(timestamp(p['edit_at']))
                if p.get('is_pinned'):
                    header += ' · pinned'
                s = '<article class="' + ('reply' if depth else 'post') + '"><header>' + header + '</header>'
                s += '<pre>' + esc(p.get('message', '')) + '</pre>'
                for a in p.get('attachments') or []:
                    target = attach(a['path'])
                    s += '<p><a download rel="noopener noreferrer" href="' + esc(target) + '">' + esc(PurePosixPath(a['path']).name) + '</a> (untrusted attachment)</p>'
                for reaction in p.get('reactions') or []:
                    s += '<span class="reaction">' + esc(reaction.get('emoji_name', '')) + ' — ' + esc(reaction.get('user', ''))
                    if reaction.get('create_at'):
                        s += ' · ' + esc(timestamp(reaction['create_at']))
                    s += '</span> '
                replies = p.get('replies') or []
                if replies:
                    s += '<details><summary>' + str(len(replies)) + ' replies</summary>'
                    for reply in sorted(replies, key=lambda x: x.get('create_at', 0)):
                        s += render(reply, depth + 1)
                    s += '</details>'
                return s + '</article>\n'

            index = stage / 'index.html'
            with open(index, 'w', encoding='utf-8') as f:
                f.write('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;"><title>Mattermost archive</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}article{border:1px solid #999;padding:1rem;margin:1rem 0}.reply{margin-left:1rem}header,.reaction{color:#555}summary{cursor:pointer}</style><h1>Mattermost archive</h1><p>Offline reference, not a backup. Attachments are untrusted; do not open active content without inspection.</p>')
                for key in sorted(selected, key=lambda k: (categories.get('/'.join(k), ''), k)):
                    f.write('<section><h2>' + esc(categories.get('/'.join(key), 'Channels')) + ' / ' + esc(key[0]) + ' / ' + esc(channels[key].get('display_name') or key[1]) + '</h2>')
                    for post in sorted(groups[key], key=lambda p: p.get('create_at', 0)):
                        f.write(render(post))
                    f.write('</section>')
                f.write('</html>')
            with open(index, 'rb') as f:
                files['index.html'] = {'sha256': digest(f), 'bytes': index.stat().st_size}
            manifest = {'format': 'mattermost-offline-archive', 'version': 1, 'generator': VERSION,
                        'input_sha256': input_hash, 'input_version': version, 'timezone': args.timezone,
                        'counts': counts, 'skipped': dict(skipped), 'files': files}
            (stage / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding='utf-8')
            packed = stage / 'result.zip'
            with zipfile.ZipFile(packed, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as out:
                for name in sorted(files):
                    out.write(stage / name, name)
                out.write(stage / 'manifest.json', 'manifest.json')
            os.chmod(packed, 0o600)
            publish(packed, output)
    print(json.dumps({'output': str(output), 'counts': counts, 'skipped': dict(skipped)}))
    if skipped:
        print('Warning: records were omitted; inspect manifest skipped counts. DM and plugin data are not guaranteed.', file=sys.stderr)


def verify(args):
    with open_zip(args.input, args) as z:
        inspect_zip(z, args)
        info = z.getinfo('manifest.json')
        if info.file_size > args.max_line_bytes:
            raise ArchiveError('Manifest budget exceeded')
        m = json.loads(z.read(info))
        if m.get('format') != 'mattermost-offline-archive' or m.get('version') != 1:
            raise ArchiveError('Unsupported manifest')
        files = m['files']
        if set(z.namelist()) != set(files) | {'manifest.json'}:
            raise ArchiveError('Manifest member set mismatch')
        for name, expected in files.items():
            with z.open(name) as f:
                if digest(f) != expected['sha256'] or z.getinfo(name).file_size != expected['bytes']:
                    raise ArchiveError('Archive checksum/size mismatch')
        if 'index.html' not in files or any(n != 'index.html' and not n.startswith('attachments/') for n in files):
            raise ArchiveError('Unexpected viewer member')
        counts = m['counts']
        if counts['attachments'] != sum(n.startswith('attachments/') for n in files):
            raise ArchiveError('Attachment count mismatch')
        # Count generated markup, not user text (user text has escaped angle brackets).
        with z.open('index.html') as f:
            found = collections.Counter()
            tail = b''
            for block in iter(lambda: f.read(CHUNK), b''):
                data = tail + block
                cut = max(0, len(data) - 40)
                for key, needle in [('posts', b'<article class="post">'), ('replies', b'<article class="reply">'), ('channels', b'<section>')]:
                    pos = 0
                    while True:
                        pos = data.find(needle, pos)
                        if pos < 0 or pos >= cut:
                            break
                        found[key] += 1
                        pos += len(needle)
                tail = data[cut:]
            for key, needle in [('posts', b'<article class="post">'), ('replies', b'<article class="reply">'), ('channels', b'<section>')]:
                found[key] += tail.count(needle)
                if found[key] != counts[key]:
                    raise ArchiveError('Viewer count mismatch')
    print(json.dumps({'verified': True, 'counts': counts}))


def budgets(parser):
    parser.add_argument('--max-bytes', type=int, default=20 * 1024**3, help='maximum total uncompressed ZIP bytes')
    parser.add_argument('--max-entries', type=int, default=100000)
    parser.add_argument('--max-ratio', type=int, default=200)
    parser.add_argument('--max-line-bytes', type=int, default=16 * 1024**2)
    parser.add_argument('--max-records', type=int, default=1000000)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', action='version', version=VERSION)
    sub = p.add_subparsers(dest='command', required=True)
    for cmd, fn in [('list', list_archive), ('convert', convert), ('verify', verify)]:
        q = sub.add_parser(cmd)
        q.add_argument('input')
        budgets(q)
        q.set_defaults(func=fn)
        if cmd == 'convert':
            q.add_argument('--output', required=True)
            q.add_argument('--team', action='append')
            q.add_argument('--channel', action='append')
            q.add_argument('--all-public', action='store_true')
            q.add_argument('--include-private', action='store_true')
            q.add_argument('--categories')
            q.add_argument('--timezone', default='Asia/Seoul')
            q.add_argument('--max-post-bytes', type=int, default=256 * 1024**2)
            q.add_argument('--max-depth', type=int, default=50)
            q.add_argument('--min-free-bytes', type=int, default=1024**3)
    from export_live import add_parser
    add_parser(sub)
    return p


def main():
    os.umask(0o077)
    args = build_parser().parse_args()
    try:
        for k, v in vars(args).items():
            if (k.startswith('max_') or k == 'min_free_bytes') and isinstance(v, int) and v <= 0:
                raise ArchiveError('Resource budgets must be positive')
        result = args.func(args)
        return result if isinstance(result, int) else 0
    except (ArchiveError, OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError, zipfile.BadZipFile, RuntimeError) as e:
        # Avoid dumping malformed record contents or subprocess credentials.
        print('Error: ' + (str(e) if isinstance(e, ArchiveError) else type(e).__name__ + ': operation failed; check input, paths, budgets and export state'), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
