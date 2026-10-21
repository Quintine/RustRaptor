#!/usr/bin/env python3
"""Export an exact frozen release to its existing empty draft; never publish it."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from urllib.parse import quote

REPO = 'Quintine/RustRaptor'
TAG = 'v0.1.0-preview.20261020'
COMMIT = '7ecaa42b29ff0db5d2f7cdfe6da0a3221dfea555'
RELEASE_ID = 418286902
FLOOR = 1_800_000_000


@dataclass(frozen=True)
class ReleaseTarget:
    commit: str = COMMIT
    tag: str = TAG
    release_id: int = RELEASE_ID
    prerelease: bool = True

    def __post_init__(self):
        if not isinstance(self.commit, str) or not re.fullmatch('[0-9a-f]{40}', self.commit):
            raise ValueError('release commit must be an exact lowercase 40-character SHA')
        if not isinstance(self.tag, str) or not re.fullmatch(r'v[0-9A-Za-z._-]+', self.tag):
            raise ValueError('release tag must be a safe exact version tag')
        if type(self.release_id) is not int or self.release_id <= 0:
            raise ValueError('release ID must be a positive integer')
        if type(self.prerelease) is not bool:
            raise ValueError('prerelease expectation must be a boolean')


PREVIEW_TARGET = ReleaseTarget()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def checked_release(release, target=PREVIEW_TARGET):
    if (release.get('id') != target.release_id or release.get('tag_name') != target.tag
            or release.get('target_commitish') != target.commit or release.get('draft') is not True
            or release.get('prerelease') is not target.prerelease):
        raise ValueError('existing release ID/tag/target/draft state differs')
    return release


def checked_tag(reference, annotated=None, target=PREVIEW_TARGET):
    if reference.get('ref') != 'refs/tags/' + target.tag:
        raise ValueError('wrong frozen tag reference')
    obj = reference.get('object', {})
    if obj.get('type') == 'tag':
        if (not isinstance(annotated, dict) or annotated.get('sha') != obj.get('sha')
                or annotated.get('tag') != target.tag):
            raise ValueError('annotated tag identity differs')
        obj = annotated.get('object', {})
    if obj.get('type') != 'commit' or obj.get('sha') != target.commit:
        raise ValueError('frozen tag no longer points to the tested commit')


def checked_remote(remote, name, size, sha256):
    if (remote.get('name') != name or remote.get('size') != size
            or remote.get('state') != 'uploaded' or remote.get('digest') != 'sha256:' + sha256):
        raise ValueError('remote asset name/size/state/SHA-256 differs; retain local export')
    return remote


def checked_receipt(plan, plan_sha, asset, receipt):
    if (receipt.get('status') != 'ZIP_CRC_AND_COMPLETE_PAYLOAD_SHA256_PASS'
            or receipt.get('asset') != asset['name'] or receipt.get('kind') != asset['kind']
            or receipt.get('checkpoint') != plan['snapshot'] or receipt.get('plan_sha256') != plan_sha
            or receipt.get('payload_files') != len(asset['files'])
            or receipt.get('payload_sha256') != {r['name']: r['sha256'] for r in asset['files']}
            or not re.fullmatch('[0-9a-f]{64}', receipt.get('sha256', ''))
            or not 0 < receipt.get('bytes', 0) < 2 * 1024**3):
        raise ValueError('local receipt differs from the one frozen runner plan')


class DraftExporter:
    def __init__(self, package, state, temporary, target=PREVIEW_TARGET):
        self.target = target
        self.package = package.resolve(strict=True)
        self.state = state.absolute()
        self.temporary = temporary.absolute()
        if any(directory.resolve() != directory for directory in (self.state, self.temporary)):
            raise ValueError('state and temporary paths must be literal paths without symlink ancestors')
        for directory in (self.state, self.temporary):
            if directory.is_relative_to(self.package):
                raise ValueError('release outputs must remain outside the frozen source tree')
            directory.mkdir(parents=True, exist_ok=False)
        self.receipts = self.state / 'receipts'
        self.remote = self.state / 'remote-receipts'
        self.receipts.mkdir()
        self.remote.mkdir()
        self.plan_path = self.state / 'release-plan.json'
        self.exporter = self.package / 'tools/export_release.py'
        self.verified = {}

    def log(self, event, **details):
        row = {'time_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'event': event, **details}
        print(json.dumps(row), flush=True)
        with (self.state / 'progress.jsonl').open('a') as stream:
            stream.write(json.dumps(row) + '\n')

    def api(self, endpoint):
        return json.loads(subprocess.check_output(['gh', 'api', endpoint], cwd=self.package))

    def release(self):
        reference = self.api(f'repos/{REPO}/git/ref/tags/{self.target.tag}')
        obj = reference.get('object', {})
        annotated = None
        if obj.get('type') == 'tag':
            sha = obj.get('sha', '')
            if not re.fullmatch('[0-9a-f]{40}', sha):
                raise ValueError('unsafe annotated tag SHA')
            annotated = self.api(f'repos/{REPO}/git/tags/{sha}')
        checked_tag(reference, annotated, self.target)
        return checked_release(self.api(f'repos/{REPO}/releases/{self.target.release_id}'), self.target)

    def snapshot(self):
        actual = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.package, text=True).strip(),
                  'runtime_manifest_sha256': digest(self.package / 'runtime-manifest.json'),
                  'windows_manifest_sha256': digest(self.package / 'runtime-windows-manifest.json')}
        if actual['commit'] != self.target.commit or subprocess.check_output(
                ['git', 'status', '--porcelain', '--untracked-files=all'], cwd=self.package):
            raise ValueError('frozen source commit or cleanliness differs')
        if hasattr(self, 'plan') and actual != self.plan['snapshot']:
            raise ValueError('frozen runtime manifests changed')
        if shutil.disk_usage(self.package).free < FLOOR:
            raise ValueError('runner workspace crossed the 1.8GB free-space floor')

    def remote_members(self, release):
        assets = release.get('assets', [])
        names = [asset.get('name') for asset in assets]
        if len(names) != len(set(names)) or set(names) != set(self.verified):
            raise ValueError('unexpected, missing or duplicate remote assets; no clobber allowed')
        for asset in assets:
            receipt = self.verified[asset['name']]
            checked_remote(asset, asset['name'], receipt['bytes'], receipt['sha256'])
        return assets

    def upload(self, path, name, expected_sha, expected_size):
        self.snapshot()
        self.remote_members(self.release())
        if (path.is_symlink() or not path.is_file() or path.stat().st_size != expected_size
                or digest(path) != expected_sha):
            raise ValueError('local upload no longer matches authenticated receipt')
        self.log('uploading', asset=name, bytes=expected_size, sha256=expected_sha)
        result = subprocess.run(['gh', 'api', '--method', 'POST', f'https://uploads.github.com/repos/{REPO}/releases/{self.target.release_id}/assets?name=' + quote(name, safe=''),
                                 '--input', str(path), '-H', 'Content-Type: application/octet-stream'],
                                cwd=self.package, capture_output=True, text=True)
        (self.state / (name + '.upload.stdout')).write_text(result.stdout)
        (self.state / (name + '.upload.stderr')).write_text(result.stderr)
        if result.returncode:
            raise RuntimeError('upload returned nonzero; retain local file and inspect remote draft before retry')
        uploaded = checked_remote(json.loads(result.stdout), name, expected_size, expected_sha)
        release = self.release()
        matches = [asset for asset in release['assets'] if asset.get('name') == name]
        if len(matches) != 1 or matches[0].get('id') != uploaded.get('id'):
            raise ValueError('uploaded asset is not uniquely attached to the guarded draft')
        checked_remote(matches[0], name, expected_size, expected_sha)
        self.verified[name] = {'bytes': expected_size, 'sha256': expected_sha}
        self.remote_members(release)
        write_json(self.remote / (name + '.json'), matches[0])
        self.log('remote_sha256_verified', asset=name, bytes=expected_size, sha256=expected_sha)

    def run(self):
        self.snapshot()
        initial = self.release()
        if initial.get('assets'):
            raise ValueError('draft must be completely empty before this one-pass export')
        write_json(self.state / 'initial-empty-draft.json', initial)
        subprocess.run([sys.executable, '-B', str(self.exporter), 'plan', '--package', str(self.package),
                        '--expected-commit', self.target.commit, '--output', str(self.plan_path)], check=True, cwd=self.package)
        self.plan = json.loads(self.plan_path.read_text())
        plan_sha = digest(self.plan_path)
        if (len(self.plan['assets']) != 9 or self.plan['snapshot']['commit'] != self.target.commit
                or sorted(asset['kind'] for asset in self.plan['assets']) != ['linux'] + ['shared-data'] * 7 + ['windows']):
            raise ValueError('frozen release no longer has exactly the expected nine ZIPs')
        for asset in self.plan['assets']:
            self.snapshot()
            self.remote_members(self.release())
            name = asset['name']
            path = self.temporary / name
            receipt_path = self.receipts / (name + '.json')
            self.log('building', asset=name, uncompressed_bytes=asset['uncompressed_bytes'])
            subprocess.run([sys.executable, '-B', str(self.exporter), 'archive', '--plan', str(self.plan_path),
                            '--asset', name, '--output', str(path), '--receipt', str(receipt_path)],
                           check=True, cwd=self.package)
            receipt = json.loads(receipt_path.read_text())
            checked_receipt(self.plan, plan_sha, asset, receipt)
            self.upload(path, name, receipt['sha256'], receipt['bytes'])
            path.unlink()  # Only this just-authenticated disposable archive, after remote proof.
            self.log('temporary_export_removed', asset=name)
        sums = self.state / 'SHA256SUMS'
        manifest = self.state / 'release-manifest.json'
        subprocess.run([sys.executable, '-B', str(self.exporter), 'checksums', '--plan', str(self.plan_path),
                        '--receipts', str(self.receipts), '--output', str(sums),
                        '--manifest-output', str(manifest), '--tag', self.target.tag], check=True, cwd=self.package)
        for path in (sums, manifest, self.package / 'release/Install-Linux.sh', self.package / 'release/Install-Windows.ps1'):
            self.upload(path, path.name, digest(path), path.stat().st_size)
        final = self.release()
        self.remote_members(final)
        if len(final['assets']) != 13:
            raise ValueError('complete release must contain nine ZIPs plus four companion assets')
        write_json(self.state / 'final-13-assets-draft-still-unpublished.json', final)
        self.log('COMPLETE_THIRTEEN_REMOTE_ASSETS_VERIFIED_DRAFT_NOT_PUBLISHED', checkpoint=self.target.commit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--temporary', type=Path, required=True)
    parser.add_argument('--commit', default=COMMIT)
    parser.add_argument('--tag', default=TAG)
    parser.add_argument('--release-id', type=int, default=RELEASE_ID)
    parser.add_argument('--prerelease', choices=('true', 'false'), default='true')
    args = parser.parse_args()
    target = ReleaseTarget(args.commit, args.tag, args.release_id, args.prerelease == 'true')
    DraftExporter(args.package, args.state, args.temporary, target).run()


if __name__ == '__main__':
    main()
