#!/usr/bin/env bash
set -euo pipefail
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'This package requires Linux x86_64.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Install Python 3 to use this download helper. The game itself does not require Python.' >&2; exit 1; }
python3 - "${1:-$PWD}" <<'PYTHON'
# BEGIN INSTALLER PYTHON
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile

TAG = 'v1.0.0'
BASE = 'https://github.com/Quintine/RustRaptor/releases/download/' + TAG


def safe_name(name):
    if not isinstance(name, str) or not name.startswith('RustRaptor/') or '\\' in name:
        raise ValueError('Unsafe ZIP member path')
    parts = name.split('/')
    if any(not p or p in ('.', '..') or ':' in p or any(ord(c) < 32 for c in p) for p in parts):
        raise ValueError('Unsafe ZIP member path')
    return name


def extract(archive_path, destination, files):
    expected = {safe_name('RustRaptor/' + row['name']): row for row in files}
    if len(expected) != len(files):
        raise ValueError('Duplicate planned ZIP members')
    with zipfile.ZipFile(archive_path) as archive:
        if len(archive.infolist()) != len(expected) or set(archive.namelist()) != set(expected):
            raise ValueError('ZIP membership differs from frozen release manifest')
        for member in archive.infolist():
            safe_name(member.filename)
            mode = member.external_attr >> 16
            if member.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise ValueError('ZIP member is not an ordinary file')
            row = expected[member.filename]
            if member.file_size != row['bytes'] or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
                raise ValueError('Invalid member size or SHA-256')
            target = destination / member.filename
            # The installation root must be fresh; refuse links and collisions.
            parent = destination
            for part in Path(member.filename).parts[:-1]:
                parent /= part
                if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                    raise ValueError('Unsafe installation parent')
                parent.mkdir(exist_ok=True)
            digest = hashlib.sha256()
            with target.open('xb') as output, archive.open(member) as source:
                while block := source.read(128 * 1024):
                    digest.update(block)
                    output.write(block)
            if digest.hexdigest() != row['sha256']:
                raise ValueError('Installed payload SHA-256 differs from frozen manifest')
            target.chmod(0o755 if mode & 0o111 else 0o644)


def install(destination):
    destination.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve(strict=True)
    if (destination / 'RustRaptor').exists() or (destination / 'RustRaptor').is_symlink():
        raise ValueError('Use a directory without an existing RustRaptor folder')
    with tempfile.TemporaryDirectory(prefix='RustRaptor-download-') as temp:
        cache = Path(temp)
        urllib.request.urlretrieve(BASE + '/release-manifest.json', cache / 'manifest.json')
        manifest = json.loads((cache / 'manifest.json').read_bytes())
        if manifest['format_version'] != 1 or manifest['tag'] != TAG:
            raise ValueError('Wrong release manifest version or tag')
        assets = [a for a in manifest['assets'] if a['kind'] in ('shared-data', 'linux')]
        names = [a['name'] for a in assets]
        data = [a for a in assets if a['kind'] == 'shared-data']
        if names.count('RustRaptor-linux-x86_64.zip') != 1 or not data or len(set(names)) != len(names):
            raise ValueError('Incomplete release asset manifest')
        required = {f'RustRaptor-data-{i:02d}-of-{len(data):02d}.zip' for i in range(1, len(data) + 1)}
        if {a['name'] for a in data} != required:
            raise ValueError('Incomplete data-volume sequence')
        all_files = [row['name'].casefold() for a in assets for row in a['files']]
        if len(set(all_files)) != len(all_files):
            raise ValueError('Duplicate installation paths across archives')
        needed = sum(row['bytes'] for a in assets for row in a['files'])
        if shutil.disk_usage(destination).free < needed + 128 * 1024**2:
            raise ValueError('Insufficient space for the complete installation')
        for asset in assets:
            name = asset['name']
            if name != 'RustRaptor-linux-x86_64.zip' and name not in required:
                raise ValueError('Unsafe release asset name')
            if not re.fullmatch('[0-9a-f]{64}', asset['sha256']) or not 0 < asset['bytes'] < 2 * 1024**3:
                raise ValueError('Invalid release asset SHA-256 or size')
            if shutil.disk_usage(cache).free < asset['bytes'] + 128 * 1024**2:
                raise ValueError('Insufficient temporary space for one download')
            print('Downloading ' + name, flush=True)
            archive_path = cache / name
            urllib.request.urlretrieve(BASE + '/' + name, archive_path)
            with archive_path.open('rb') as source:
                digest = hashlib.sha256()
                while block := source.read(128 * 1024):
                    digest.update(block)
            if archive_path.stat().st_size != asset['bytes'] or digest.hexdigest() != asset['sha256']:
                raise ValueError('Downloaded archive size or SHA-256 mismatch: ' + name)
            extract(archive_path, destination, asset['files'])
            archive_path.unlink()
    print('Installed. Start: ' + str(destination / 'RustRaptor/run.sh'))


if __name__ == '__main__':
    install(Path(sys.argv[1]))
# END INSTALLER PYTHON
PYTHON
