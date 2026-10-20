import unittest,struct
import numpy as np
import terrain_component_cleanup as m
class GeometryTests(unittest.TestCase):
 def palette(self):
  p=np.tile(np.arange(256,dtype=np.uint8)[:,None],(1,3));p[:,1]=(p[:,1].astype(int)*3%256).astype(np.uint8);return p
 def sources(self):
  a=np.full((32,32),152,np.uint8);a[:12,:]=197;a[:,13:18]=18;a[:12,18:]=226;a[12:16,18:]=226;a[17:23,18:]=226;a[24:,18:]=226;a[20,1]=242;return [a,a[:,::-1].copy()]
 def fields(self):
  y,x=np.indices((512,1024));return {i:np.stack([(x*19+y*11+i*7)%256,(x*13+y*17)%256,(x*3+y*7)%256],axis=-1).astype(float)for i in range(5)}
 def test_source_decode_includes_honest_protected_indices(self):
  a=self.sources()[0];data=struct.pack('<5i',1,1,0,32,32)+a.tobytes();self.assertTrue(np.array_equal(m.decode_source32(data),a));self.assertEqual(m.decode_source32(data)[20,1],242)
 def test_bad_format_and_truncated_source_rejected(self):
  for b in [b'',struct.pack('<5i',0,1,0,32,32)+bytes(1024),struct.pack('<5i',1,1,0,32,32)+bytes(1023)]:
   with self.assertRaises(ValueError):m.decode_source32(b)
 def test_nonwater_protected_class_not_reclassified_as_ordinary(self):
  a=self.sources()[0];a[2,2]=249
  with self.assertRaises(ValueError):m.material_labels(a,12)
 def test_material_masks_and_approach_are_exact(self):
  a=self.sources()[0];labels=m.material_labels(a,12);self.assertEqual(labels[20,1],0);self.assertEqual(labels[5,13],1);self.assertEqual(labels[5,2],2);self.assertEqual(labels[10,22],4);self.assertEqual(labels[20,22],3);self.assertEqual(labels[16,22],0);self.assertEqual(labels[23,22],0)
 def test_registered_pair_geometry_and_protected_samples(self):
  sources=self.sources();pal=self.palette();out,owners,protected,guide=m.derive_pair(sources,pal,self.fields());expected=m.material_labels(guide,48);self.assertTrue(np.array_equal(owners,np.repeat(np.repeat(expected,4,0),4,1)));self.assertTrue(np.array_equal(out[protected],np.repeat(np.repeat(pal[guide],4,0),4,1)[protected]));self.assertEqual(out.shape,(512,1024,3));self.assertTrue(protected.any());self.assertTrue(np.any(out[~protected]!=np.repeat(np.repeat(pal[guide],4,0),4,1)[~protected]))
 def test_different_genuine_texture_changes_only_its_component(self):
  s=self.sources();p=self.palette();f=self.fields();out,owners,_,_=m.derive_pair(s,p,f);g={k:v.copy()for k,v in f.items()};g[3]=255-g[3];new,_,_,_=m.derive_pair(s,p,g);self.assertTrue(np.array_equal(new[owners!=3],out[owners!=3]));self.assertTrue(np.any(new[owners==3]!=out[owners==3]))
 def test_missing_component_rejected(self):
  f=self.fields();del f[3]
  with self.assertRaises(ValueError):m.derive_pair(self.sources(),self.palette(),f)
 def test_both_frames_required(self):
  with self.assertRaises(ValueError):m.derive_pair(self.sources()[:1],self.palette(),self.fields())
 def test_crop_cannot_escape_genuine_image(self):
  a=np.zeros((8,8,3),np.uint8)
  for box in [(-1,0,3,3),(0,0,9,8),(0,0,0,2)]:
   with self.assertRaises(ValueError):m.donor_field(a,box,(8,8))
 def test_identity_mesh_preserves_every_rgb_pixel(self):
  a=np.arange(16*16*3,dtype=np.uint8).reshape(16,16,3);knots=[0,.5,1];self.assertTrue(np.array_equal(m.warp_landmarks(a,knots,knots,knots,knots),a))
 def test_landmark_rows_are_moved_without_inventing_texture(self):
  a=np.zeros((32,32,3),np.uint8);a[8:10]=[100,150,200];b=m.warp_landmarks(a,[0,1],[0,.5,1],[0,1],[0,.25,1]);self.assertGreater(b[16,:,1].max(),100);self.assertEqual(b.shape,a.shape)
 def test_reversed_missing_nan_mesh_knots_rejected(self):
  a=np.zeros((8,8,3),np.uint8)
  for k in [[0,.7,.6,1],[.1,1],[0,float('nan'),1],[0,0,1]]:
   with self.assertRaises(ValueError):m.warp_landmarks(a,[0,1],k,[0,1],k)
if __name__=='__main__':unittest.main()
