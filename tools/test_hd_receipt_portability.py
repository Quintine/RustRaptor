"""Canonical bundle copies resolve historical carried-QA receipts without W."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import hashlib, json, os, tempfile, types, unittest
from unittest.mock import patch
import hd_register_reviewed as m

LEGACY=PurePosixPath('/home/quintine/Projects/RaptorReplica/data/hd')
REL=Path('registered-class-review/batch-4742-final-successor-metadata/terrain-203fd-2040c/runtime-qa-current7b-exact-component-alias.json')

class LegacyReceipt(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='receipt-portability-')
        self.work=Path(self.temp.name);self.root=self.work/'Renamed 游戏 bundle/data/hd';self.root.mkdir(parents=True)
        self.payload=b'{"diagnostics":[],"probe":"local-copy"}\n'
        self.digest=hashlib.sha256(self.payload).hexdigest();self.local=self.root/REL
        self.local.parent.mkdir(parents=True);self.local.write_bytes(self.payload)
        self.receipt=dict(path=str(LEGACY/REL.as_posix()),sha256=self.digest)
    def tearDown(self):self.temp.cleanup()
    def deny_legacy_open(self):
        original=os.open;seen=[]
        def guarded(path,*a,**kw):
            seen.append(str(path))
            if Path(path).is_relative_to(LEGACY):raise AssertionError('Must never inspect or open W original')
            return original(path,*a,**kw)
        return patch.object(m.os,'open',new=guarded),seen
    def test_renamed_unicode_bundle_uses_local_when_legacy_unreadable(self):
        guard,seen=self.deny_legacy_open()
        with guard:result=m.receipt_json(self.root,self.receipt)
        self.assertEqual(result,json.loads(self.payload));self.assertEqual(seen,[str(self.local)])
    def test_local_preferred_even_if_legacy_would_be_valid(self):
        original=Path.read_bytes;seen=[]
        def logical_w(self):
            if self==LEGACY/REL:seen.append(str(self));return b'{"probe":"old-W-would-exist"}'
            return original(self)
        with patch.object(Path,'read_bytes',new=logical_w):self.assertEqual(m.receipt_json(self.root,self.receipt),json.loads(self.payload))
        self.assertEqual(seen,[])
    def test_posix_historical_receipt_maps_when_native_windows_absolute_rule_is_false(self):
        self.assertFalse(PureWindowsPath(self.receipt['path']).is_absolute())
        original=Path
        def windows_like_native(*values):
            if len(values)==1 and values[0]==self.receipt['path']:
                return PureWindowsPath(values[0])
            return original(*values)
        with patch.object(m,'Path',new=windows_like_native):
            self.assertEqual(m.receipt_json(self.root,self.receipt),json.loads(self.payload))

    def test_wrong_local_sha_fails_without_external_fallback(self):
        self.local.write_bytes(b'{"probe":"wrong"}')
        guard,seen=self.deny_legacy_open()
        with guard,self.assertRaisesRegex(ValueError,'independent receipt changed'):m.receipt_json(self.root,self.receipt)
        self.assertEqual(seen,[str(self.local)])
    def test_missing_local_fails_without_external_fallback(self):
        self.local.unlink();guard,seen=self.deny_legacy_open()
        with guard,self.assertRaises(FileNotFoundError):m.receipt_json(self.root,self.receipt)
        self.assertEqual(seen,[])
    def test_legacy_parent_traversal_rejects_before_read(self):
        value=dict(self.receipt,path=str(LEGACY/'registered-class-review/../escape.json'))
        with self.assertRaisesRegex(ValueError,'legacy receipt path escapes HD root'):m.receipt_json(self.root,value)
    def test_exact_prefix_without_file_rejects(self):
        with self.assertRaisesRegex(ValueError,'legacy receipt path escapes HD root'):m.receipt_json(self.root,dict(self.receipt,path=str(LEGACY)))
    def test_legacy_leaf_symlink_inside_root_rejects(self):
        target=self.local.with_name('target.json');target.write_bytes(self.payload);self.local.unlink()
        try:self.local.symlink_to(target)
        except OSError as e:self.skipTest(str(e))
        with self.assertRaisesRegex(ValueError,'regular nonsymlink'):m.receipt_json(self.root,self.receipt)
    def test_legacy_parent_symlink_escape_rejects(self):
        out=self.work/'outside';out.mkdir();(out/'qa.json').write_bytes(self.payload)
        link=self.root/'linked'
        try:link.symlink_to(out,target_is_directory=True)
        except OSError as e:self.skipTest(str(e))
        value=dict(self.receipt,path=str(LEGACY/'linked/qa.json'))
        with self.assertRaisesRegex(ValueError,'path escapes HD root'):m.receipt_json(self.root,value)
    def test_legacy_parent_symlink_inside_root_rejects(self):
        actual=self.root/'real';actual.mkdir();(actual/'qa.json').write_bytes(self.payload)
        link=self.root/'linked'
        try:link.symlink_to(actual,target_is_directory=True)
        except OSError as e:self.skipTest(str(e))
        with self.assertRaisesRegex(ValueError,'regular nonsymlink'):m.receipt_json(self.root,dict(self.receipt,path=str(LEGACY/'linked/qa.json')))
    def test_directory_is_not_regular_receipt(self):
        self.local.unlink();self.local.mkdir()
        with self.assertRaisesRegex(ValueError,'regular nonsymlink'):m.receipt_json(self.root,self.receipt)
    def test_metadata_changes_during_fd_read_reject(self):
        original=os.fstat;calls=[]
        def changed(fd):
            s=original(fd);calls.append(fd)
            if len(calls)==2:return types.SimpleNamespace(st_dev=s.st_dev,st_ino=s.st_ino,st_mode=s.st_mode,st_size=s.st_size,st_mtime_ns=s.st_mtime_ns+1)
            return s
        with patch.object(m.os,'fstat',new=changed),self.assertRaisesRegex(ValueError,'changed during read'):m.receipt_json(self.root,self.receipt)
    def test_path_replacement_before_open_rejects_same_bytes(self):
        original=os.open
        def replaced(path,*a,**kw):
            other=self.local.with_suffix('.replacement');other.write_bytes(self.payload);os.replace(other,self.local)
            return original(path,*a,**kw)
        with patch.object(m.os,'open',new=replaced),self.assertRaisesRegex(ValueError,'changed during read'):m.receipt_json(self.root,self.receipt)
    def test_relative_control_and_legacy_errors_unchanged(self):
        good=dict(path=str(REL),sha256=self.digest)
        self.assertEqual(m.receipt_json(self.root,good),json.loads(self.payload))
        for bad in [{},dict(path=str(REL),sha256='BAD'),dict(path=str(REL),sha256='0'*64),dict(path='../escape.json',sha256=self.digest)]:
            with self.subTest(bad=bad):
                expected = ('missing hash-bound independent receipt' if not bad or bad.get('sha256') == 'BAD'
                            else 'independent receipt changed' if bad.get('sha256') == '0'*64
                            else 'path escapes HD root')
                with self.assertRaisesRegex(ValueError,expected):m.receipt_json(self.root,bad)
    def test_unrecognized_absolute_private_proof_is_not_remapped(self):
        original=self.work/'.reference/proof.json';original.parent.mkdir();original.write_bytes(self.payload)
        (self.root/'proof.json').write_bytes(b'{"wrong":"basename-fallback"}')
        ref=dict(path=str(original),sha256=self.digest)
        self.assertEqual(m.receipt_json(self.root,ref),json.loads(self.payload))
    def test_similar_prefix_is_not_remapped(self):
        absolute=Path(str(LEGACY)+'-spoof')/'qa.json';original=Path.read_bytes;seen=[]
        def logical(self):
            if self==absolute:seen.append(str(self));return self_case.payload
            return original(self)
        self_case=self
        with patch.object(Path,'read_bytes',new=logical):
            if absolute.is_absolute():
                self.assertEqual(m.receipt_json(self.root,dict(path=str(absolute),sha256=self.digest)),json.loads(self.payload))
            else:
                # Windows treats this unrecognized POSIX-looking path as rooted,
                # not absolute; preserve the preexisting containment rejection.
                with self.assertRaisesRegex(ValueError,'path escapes HD root'):
                    m.receipt_json(self.root,dict(path=str(absolute),sha256=self.digest))
        self.assertEqual(seen,[str(absolute)] if absolute.is_absolute() else [])

if __name__=='__main__':unittest.main(verbosity=2)
