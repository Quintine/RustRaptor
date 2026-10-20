"""Private proposal: exact generated-RGB transfer for an unsupported gray island.

The authentic Source selects one complete green semantic component. No Source
RGB, synthesized color, luminance conversion, random texture or rescaling is used.
Only a bounded generated island inside that component can change. Other atlas
cells and all pixels outside the measured target remain byte-identical as RGB.
"""
from __future__ import annotations
import argparse,collections,hashlib,io,json,os,stat,struct
from pathlib import Path
import numpy as np
from PIL import Image

METHOD='direct-own-generated-green-contiguous-patch-transfer-v2'

def read_regular(path,limit):
 p=Path(path).absolute()
 if p.resolve(strict=True)!=p:raise ValueError('input symlinks are unsupported')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  a=os.fstat(fd)
  if not stat.S_ISREG(a.st_mode) or a.st_size>limit:raise ValueError('input type or size')
  with os.fdopen(fd,'rb',closefd=False)as f:data=f.read(limit+1)
  b=os.fstat(fd)
  if len(data)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns)or len(data)!=a.st_size:raise ValueError('input changed')
 finally:os.close(fd)
 return data

def checked(binding,base,limit):
 p=Path(binding['path']);p=p if p.is_absolute()else base/p
 data=read_regular(p,limit)
 if hashlib.sha256(data).hexdigest()!=binding['sha256']:raise ValueError('input checksum')
 return data

def components(mask):
 h,w=mask.shape;seen=np.zeros(mask.shape,bool);out=[]
 for y,x in np.argwhere(mask):
  if seen[y,x]:continue
  todo=[(int(x),int(y))];seen[y,x]=True;cells=[]
  while todo:
   xx,yy=todo.pop();cells.append((xx,yy))
   for nx,ny in [(xx-1,yy),(xx+1,yy),(xx,yy-1),(xx,yy+1)]:
    if 0<=nx<w and 0<=ny<h and mask[ny,nx]and not seen[ny,nx]:seen[ny,nx]=True;todo.append((nx,ny))
  out.append(cells)
 return out

def source_component(source,palette):
 if len(source)!=1044 or struct.unpack_from('<5i',source)!=(1,1,0,32,32):raise ValueError('Original must be32x32 uncompressed')
 if len(palette)!=768:raise ValueError('palette size')
 idx=np.frombuffer(source[20:],np.uint8).reshape(32,32)
 if np.any(idx>=240):raise ValueError('ordinary Original required')
 pal=np.minimum(np.frombuffer(palette,np.uint8).reshape(256,3).astype(np.uint16),63);rgb=((pal<<2)|(pal>>4))[idx];green=(rgb[:,:,1]>rgb[:,:,0])&(rgb[:,:,1]>rgb[:,:,2]);hits=[]
 for cells in components(green):
  if any(12<=x<19 and 8<=y<12 for x,y in cells):hits.append(cells)
 if len(hits)!=1:raise ValueError('ROI must identify one complete green component')
 mask=np.zeros((32,32),bool)
 for x,y in hits[0]:mask[y,x]=True
 return mask,hits[0]

def plan(image,source,palette,expected_cells):
 if image.mode!='RGB' or image.width!=image.height or image.width%2 or not 128<=image.width<=2048:raise ValueError('exact opaque RGB square2x2 atlas required')
 sem,cells=source_component(source,palette)
 if len(cells)!=expected_cells:raise ValueError('Source component count differs')
 raw=np.asarray(image);side=image.width//2;tile=raw[:side,side:].astype(np.int16);coord=((np.arange(side)*2+1)*32//(2*side)).clip(0,31);allowed=sem[coord[:,None],coord[None,:]]
 neutral=(tile.max(2)-tile.min(2)<=6)&(tile[:,:,0]>65)&allowed;rawroi=(coord[:,None]>=8)&(coord[:,None]<12)&(coord[None,:]>=12)&(coord[None,:]<19);islands=[c for c in components(neutral)if any(rawroi[y,x]for x,y in c)]
 if not islands:raise ValueError('no unsupported gray island')
 islands.sort(key=lambda c:(-len(c),min(c)));island=islands[0];x0=min(x for x,y in island);x1=max(x for x,y in island)+1;y0=min(y for x,y in island);y1=max(y for x,y in island)+1
 if len(island)<4 or (x1-x0)*32>side*5.5 or (y1-y0)*32>side*5.5:raise ValueError('island is not bounded')
 # Eight raw pixels at this pinned master are less than one logical Source cell.
 pad=8;x0=max(0,x0-pad);x1=min(side,x1+pad);y0=max(0,y0-pad);y1=min(side,y1+pad);target=np.zeros((side,side),bool);target[y0:y1,x0:x1]=allowed[y0:y1,x0:x1]
 if int(target.sum())*1024>side*side*36:raise ValueError('target exceeds36logical-cell area')
 donors=allowed&(tile[:,:,1]>tile[:,:,0]+8)&(tile[:,:,1]>tile[:,:,2]+8)&(tile[:,:,1]>=24)&~target
 if not np.any(donors):raise ValueError('no genuine own-green material')
 report=dict(method=METHOD,Source_component_cells=len(cells),Source_component_sorted=[list(p)for p in sorted(cells)],Source_roi=[12,8,19,12],atlas_cell=[1,0],tile_side=side,neutral_island_pixels=len(island),island_bbox_before_pad=[x0+pad,y0+pad,x1-pad,y1-pad],target_bbox=[x0,y0,x1,y1],target_pixels=int(target.sum()),donor_pixels=int(donors.sum()),target_logical_area=float(target.sum()*1024/(side*side)),pad_raw_pixels=pad,new_RGB_colors_synthesized=0)
 return raw.copy(),tile.astype(np.uint8),allowed,target,donors,report

def repair(image,source,palette,expected_cells):
 atlas,tile,allowed,target,donors,report=plan(image,source,palette,expected_cells);h,w=allowed.shape;x0,y0,x1,y1=report['target_bbox'];hh=y1-y0;ww=x1-x0;rgb=tile.astype(np.int16)
 green=(rgb[:,:,1]>rgb[:,:,0]+8)&(rgb[:,:,1]>rgb[:,:,2]+8)&(rgb[:,:,1]>=24)
 material=allowed&~target&(green|(rgb.max(2)<=65))
 def windows(mask):
  integral=np.pad(mask.astype(np.int32),((1,0),(1,0))).cumsum(0).cumsum(1)
  return integral[hh:,ww:]-integral[:-hh,ww:]-integral[hh:,:-ww]+integral[:-hh,:-ww]
 counts=windows(material);gcounts=windows(green);ys,xs=np.where((counts==hh*ww)&(gcounts*100>=85*hh*ww))
 if len(ys)==0:raise ValueError('no contiguous coherent own-green material patch')
 order=np.lexsort((xs,ys,(xs.astype(np.int64)-x0)**2+(ys.astype(np.int64)-y0)**2));j=order[0];px=int(xs[j]);py=int(ys[j]);dx=px-x0;dy=py-y0
 out=atlas.copy();view=out[:h,w:];ty,tx=np.where(target);view[ty,tx]=tile[ty+dy,tx+dx];support=np.zeros(atlas.shape[:2],bool);support[:h,w:]=target
 if not np.array_equal(out[~support],atlas[~support]):raise AssertionError('outside support changed')
 copied=view[target].astype(np.int16);valid=((copied[:,1]>copied[:,0]+8)&(copied[:,1]>copied[:,2]+8)&(copied[:,1]>=24))|(copied.max(1)<=65)
 if not np.all(valid):raise AssertionError('copied material is not own green/dark shade')
 report.update(changed_pixels=int(np.any(out!=atlas,axis=2).sum()),outside_support_exact=True,fa_fc_and_unused_exact=True,donor_patch_bbox=[px,py,px+ww,py+hh],translation=[dx,dy],full_patch_green_pixels=int(gcounts[py,px]),full_patch_area=hh*ww,candidate_patch_count=len(ys),coherent_unscaled_translation=True)
 return Image.fromarray(out),report

def main():
 p=argparse.ArgumentParser();p.add_argument('--recipe',type=Path,required=True);p.add_argument('--output',type=Path);p.add_argument('--analyze',action='store_true');a=p.parse_args();recipe=json.loads(read_regular(a.recipe,262144));base=a.recipe.absolute().parent
 if recipe.get('method')!=METHOD:raise ValueError('method mismatch')
 source=checked(recipe['Source'],base,1044);palette=checked(recipe['palette'],base,768);raw=checked(recipe['master'],base,16777216)
 with Image.open(io.BytesIO(raw))as im:
  if im.mode!='RGB' or im.size!=tuple(recipe['master_dimensions']):raise ValueError('master dimensions/mode')
  im.load();image=im.copy()
 if a.analyze:
  *_,report=plan(image,source,palette,recipe['expected_Source_component_cells'])
 else:
  if a.output is None:raise ValueError('output required')
  out,report=repair(image,source,palette,recipe['expected_Source_component_cells']);dest=a.output.absolute()
  if dest.parent.resolve(strict=True)!=dest.parent:raise ValueError('output parent symlink')
  fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
  with os.fdopen(fd,'wb')as f:out.save(f,format='PNG')
  report['output_sha256']=hashlib.sha256(read_regular(dest,16777216)).hexdigest()
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
