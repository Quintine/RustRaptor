"""Synthetic guards for this one fixed preview upload; no GitHub mutations."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import upload_draft_release as upload


class FrozenDraftUploadTests(unittest.TestCase):
    def test_release_guard_rejects_any_changed_identity_or_published_state(self):
        good = {'id': upload.RELEASE_ID, 'tag_name': upload.TAG,
                'target_commitish': upload.COMMIT, 'draft': True, 'prerelease': True}
        self.assertEqual(upload.checked_release(good), good)
        for field, value in (('id', 1), ('tag_name', 'wrong'), ('target_commitish', 'main'), ('draft', False), ('prerelease', False)):
            bad = dict(good)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                upload.checked_release(bad)

    def test_direct_and_annotated_tag_must_peel_to_exact_commit(self):
        direct = {'ref': 'refs/tags/' + upload.TAG, 'object': {'type': 'commit', 'sha': upload.COMMIT}}
        upload.checked_tag(direct)
        reference = {'ref': direct['ref'], 'object': {'type': 'tag', 'sha': 'a' * 40}}
        annotation = {'sha': 'a' * 40, 'tag': upload.TAG, 'object': direct['object']}
        upload.checked_tag(reference, annotation)
        for bad in (None, dict(annotation, sha='b' * 40), dict(annotation, object={'type': 'commit', 'sha': 'b' * 40})):
            with self.assertRaises(ValueError):
                upload.checked_tag(reference, bad)

    def test_remote_asset_requires_exact_hash_size_name_and_uploaded_state(self):
        good = {'name': 'one.zip', 'size': 42, 'state': 'uploaded', 'digest': 'sha256:' + 'a' * 64}
        upload.checked_remote(good, 'one.zip', 42, 'a' * 64)
        for field, value in (('name', 'two.zip'), ('size', 41), ('state', 'starter'), ('digest', None)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                upload.checked_remote(dict(good, **{field: value}), 'one.zip', 42, 'a' * 64)

    def test_receipt_must_bind_same_plan_checkpoint_kind_and_every_payload(self):
        plan = {'snapshot': {'commit': upload.COMMIT}}
        asset = {'name': 'one.zip', 'kind': 'shared-data', 'files': [{'name': 'data/pic', 'sha256': 'b' * 64}]}
        good = {'status': 'ZIP_CRC_AND_COMPLETE_PAYLOAD_SHA256_PASS', 'asset': 'one.zip', 'kind': 'shared-data',
                'checkpoint': plan['snapshot'], 'plan_sha256': 'c' * 64, 'payload_files': 1,
                'payload_sha256': {'data/pic': 'b' * 64}, 'bytes': 42, 'sha256': 'd' * 64}
        upload.checked_receipt(plan, 'c' * 64, asset, good)
        for field, value in (('checkpoint', {}), ('plan_sha256', 'a' * 64), ('kind', 'linux'),
                             ('payload_files', 0), ('payload_sha256', {}), ('bytes', 2 * 1024**3), ('sha256', 'x')):
            with self.subTest(field=field), self.assertRaises(ValueError):
                upload.checked_receipt(plan, 'c' * 64, asset, dict(good, **{field: value}))

    def test_remote_members_rejects_unplanned_missing_or_duplicate_assets(self):
        controller = object.__new__(upload.DraftExporter)
        controller.verified = {'one.zip': {'bytes': 42, 'sha256': 'a' * 64}}
        asset = {'name': 'one.zip', 'size': 42, 'state': 'uploaded', 'digest': 'sha256:' + 'a' * 64}
        controller.remote_members({'assets': [asset]})
        for assets in ([], [asset, asset], [dict(asset, name='extra.zip')]):
            with self.assertRaises(ValueError):
                controller.remote_members({'assets': assets})

    def test_upload_failure_or_remote_digest_mismatch_never_deletes_local_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / 'frozen'
            package.mkdir()
            controller = upload.DraftExporter(package, root / 'state', root / 'single')
            archive = root / 'single/one.zip'
            archive.write_bytes(b'complete ZIP fixture')
            expected = upload.digest(archive)
            before = {'assets': []}
            wrong = {'id': 123, 'name': 'one.zip', 'size': archive.stat().st_size,
                     'state': 'uploaded', 'digest': 'sha256:' + '0' * 64}
            with patch.object(controller, 'snapshot'), patch.object(controller, 'release', return_value=before), \
                 patch.object(controller, 'log'), patch.object(upload.subprocess, 'run') as run:
                run.return_value.returncode = 0
                run.return_value.stdout = json.dumps(wrong)
                run.return_value.stderr = ''
                with self.assertRaises(ValueError):
                    controller.upload(archive, 'one.zip', expected, archive.stat().st_size)
                self.assertTrue(archive.exists())
                self.assertEqual(controller.verified, {})
                run.return_value.returncode = 1
                with self.assertRaises(RuntimeError):
                    controller.upload(archive, 'one.zip', expected, archive.stat().st_size)
                self.assertTrue(archive.exists())

    def test_output_directories_must_be_new_and_outside_frozen_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / 'frozen'
            package.mkdir()
            with self.assertRaises(ValueError):
                upload.DraftExporter(package, package / 'state', root / 'single')
            state = root / 'already-existing-state'
            state.mkdir()
            with self.assertRaises(FileExistsError):
                upload.DraftExporter(package, state, root / 'single')


if __name__ == '__main__':
    unittest.main()
