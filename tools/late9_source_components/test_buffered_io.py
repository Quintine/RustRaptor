import unittest,tempfile,os,hashlib,io,struct,zlib
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import numpy as np
import terrain_component_cleanup as m
class BufferedIOTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'inputs').mkdir();self.file=self.root/'inputs/a';self.file.write_bytes(b'bounded');self.binding={'path':'inputs/a','sha256':hashlib.sha256(b'bounded').hexdigest()}
 def tearDown(self):self.temp.cleanup()
 def test_absolute_and_dotdot_escape_rejected(self):
  for rel in [str(self.file),'../outside','inputs/../inputs/a','./inputs/a','inputs//a','/etc/passwd']:
   with self.assertRaises(ValueError):m.read_contained(self.root,rel)
 def test_intermediate_and_final_symlink_rejected(self):
  (self.root/'alias').symlink_to(self.root/'inputs',target_is_directory=True);(self.root/'inputs/link').symlink_to(self.file)
  for rel in ['alias/a','inputs/link']:
   with self.assertRaises((OSError,ValueError)):m.read_contained(self.root,rel)
 def test_fifo_is_rejected_without_waiting_for_writer(self):
  os.mkfifo(self.root/'inputs/fifo')
  with self.assertRaises(ValueError):m.read_contained(self.root,'inputs/fifo')
 def test_directory_is_not_regular_source(self):
  with self.assertRaises(ValueError):m.read_contained(self.root,'inputs')
 def test_stat_oversize_rejected_before_read(self):
  with patch.object(m.os,'read',side_effect=AssertionError('must not read oversized source')):
   with self.assertRaises(ValueError):m.read_contained(self.root,'inputs/a',3)
 def test_bounded_eof_cannot_accept_extra_bytes(self):
  with patch.object(m.os,'read',side_effect=[b'too-long',b'']):
   with self.assertRaises(ValueError):m.read_contained(self.root,'inputs/a',7)
 def test_cached_authenticated_source_never_reopens_path(self):
  c=m.BufferedInputs(self.root);first,pin=c.read(self.binding);self.file.unlink()
  with patch.object(m.os,'open',side_effect=AssertionError('cached path reopened')):
   second,same=c.read(self.binding)
  self.assertEqual(first,second);self.assertEqual(pin,same);self.assertEqual(c.physical_reads,1)
 def test_bad_hash_and_changed_cached_expected_hash_rejected(self):
  c=m.BufferedInputs(self.root)
  with self.assertRaises(ValueError):c.read(dict(self.binding,sha256='0'*64))
  c.read(self.binding)
  with self.assertRaises(ValueError):c.read(dict(self.binding,sha256='1'*64))
 def png(self):
  f=io.BytesIO();Image.new('RGB',(8,8),(20,30,40)).save(f,format='PNG');return f.getvalue()
 def test_png_decoded_from_bytesio_never_input_path(self):
  raw=self.png();original=m.Image.open;seen=[]
  def check(fp,*args,**kwargs):
   self.assertIsInstance(fp,io.BytesIO);seen.append(True);return original(fp,*args,**kwargs)
  with patch.object(m.Image,'open',side_effect=check),patch.object(Path,'read_bytes',side_effect=AssertionError('path reopen')):
   result=m.decode_png(raw)
  self.assertEqual(result.shape,(8,8,3));self.assertTrue(seen)
 def test_png_declared_dimensions_bounded_before_convert(self):
  raw=bytearray(self.png());raw[16:24]=struct.pack('>II',4097,1024);raw[29:33]=struct.pack('>I',zlib.crc32(raw[12:29]))
  with patch.object(m.Image.Image,'convert',side_effect=AssertionError('oversized decode converted')):
   with self.assertRaises(ValueError):m.decode_png(bytes(raw))
 def test_non_png_encoded_oversize_and_nonopaque_rejected(self):
  f=io.BytesIO();Image.new('RGBA',(2,2),(0,0,0,0)).save(f,format='PNG')
  for raw in [f.getvalue(),b'x'*(m.MAX_INPUT_BYTES+1)]:
   with self.assertRaises(ValueError):m.decode_png(raw)
  f=io.BytesIO();Image.new('RGB',(2,2)).save(f,format='JPEG')
  with self.assertRaises(ValueError):m.decode_png(f.getvalue())
 def test_regular_bounded_payload_sha_and_size_truthful(self):
  payload,pin=m.read_contained(self.root,'inputs/a');self.assertEqual(payload,b'bounded');self.assertEqual(pin['sha256'],self.binding['sha256']);self.assertEqual(pin['size'],7)
if __name__=='__main__':unittest.main()
