"""DERIVED gray-cast correction, preserving generated luminance structure.

Bounded to the two reviewed grating compositions. Source supplies only an exact
semantic mask and ONE aggregate gray color per frame, never a painted SourceNx
field. This tool does not approve art, create a runtime policy or modify inputs.
"""
from __future__ import annotations
import argparse, ctypes, errno, hashlib, io, json, os, shutil, stat, struct, sys, tempfile
from pathlib import Path, PurePosixPath
import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION

METHOD = 'generated-grating-semantic-gray-cohort-mean-cast-only-v1'
REGIONS = {'203c6': [21,3,31,31], '203c7': [2,0,31,12]}
MAX_BYTES = 32*1024*1024
MAX_PIXELS = 4_194_304
MAX_SHIFT = 32.0
LUMA = np.asarray([0.2126,0.7152,0.0722], np.float64)


def sha(b): return hashlib.sha256(b).hexdigest()

def read_regular(root, relative, limit=MAX_BYTES):
    """Every component, including the root, is walked with stable no-follow FDs."""
    if type(relative)is not str:raise ValueError('string relative path required')
    p=PurePosixPath(relative)
    if (p.is_absolute() or not p.parts
            or '..'in p.parts or p.as_posix()!=relative):
        raise ValueError('normalized contained relative path required')
    base=Path(root).absolute();fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
    try:
        for name in list(base.parts[1:])+list(p.parts[:-1]):
            newer=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
            os.close(fd);fd=newer
        f=os.open(p.parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        try:
            before=os.fstat(f)
            if not stat.S_ISREG(before.st_mode)or before.st_size>limit:
                raise ValueError('bounded regular input required')
            with os.fdopen(f,'rb',closefd=False)as stream:body=stream.read(limit+1)
            after=os.fstat(f)
            identity=lambda q:(q.st_dev,q.st_ino,q.st_size,q.st_mtime_ns,q.st_ctime_ns)
            if identity(before)!=identity(after)or len(body)!=before.st_size or len(body)>limit:
                raise ValueError('input changed during bounded read')
        finally:os.close(f)
    finally:os.close(fd)
    return body


def read_bound(root,binding,limit=MAX_BYTES):
    if (type(binding)is not dict or set(binding)!={'path','sha256'}
            or type(binding['sha256'])is not str or len(binding['sha256'])!=64
            or any(c not in '0123456789abcdef'for c in binding['sha256'])):
        raise ValueError('exact relative path/sha256 binding required')
    body=read_regular(root,binding['path'],limit)
    if sha(body)!=binding['sha256']:raise ValueError('input SHA mismatch')
    return body


def source_indices(body):
    if len(body)!=1044 or struct.unpack('<5i',body[:20])!=(1,1,0,32,32):
        raise ValueError('exact complete uncompressed 32x32 Source required')
    a=np.frombuffer(body[20:],np.uint8).reshape(32,32).copy()
    if np.any(a>=240):raise ValueError('only opaque ordinary Source supported')
    return a


def palette_rgb(body):
    if len(body)!=768 or max(body)>63:raise ValueError('authentic six-bit palette required')
    a=np.frombuffer(body,np.uint8).astype(np.uint16).reshape(256,3)
    return ((a<<2)|(a>>4)).astype(np.uint8)


def semantic_mask(asset, source):
    if asset not in REGIONS:raise ValueError('unreviewed grating asset')
    x0,y0,x1,y1=REGIONS[asset];m=np.zeros((32,32),bool)
    m[y0:y1,x0:x1]=(source[y0:y1,x0:x1]>=11)&(source[y0:y1,x0:x1]<=30)
    if not m.any():raise ValueError('no authentic gray grating material')
    return m


def selected_digest(mask):
    return sha(json.dumps(sorted([[int(x),int(y)]for y,x in np.argwhere(mask)]),
                          separators=(',',':')).encode())


def validate_recipe(r):
    if (type(r)is not dict or set(r)!={'format_version','method','palette','parent_raw','frames'}
            or type(r['format_version'])is not int or r['format_version']!=1 or r['method']!=METHOD
            or type(r['frames'])is not list or len(r['frames'])!=2):
        raise ValueError('exact reviewed two-frame recipe required')
    if any(type(f)is not dict for f in r['frames']):raise ValueError('frame objects required')
    if [f.get('asset')for f in r['frames']]!=['203c6','203c7']:
        raise ValueError('ordered complete pair required')
    for f in r['frames']:
        if (set(f)!={'asset','Source','selected_cells_sha256'}
                or type(f['selected_cells_sha256'])is not str
                or len(f['selected_cells_sha256'])!=64
                or any(c not in '0123456789abcdef'for c in f['selected_cells_sha256'])):
            raise ValueError('unknown frame field or selector digest')


def prepare_inputs(r, root):
    validate_recipe(r)
    return (palette_rgb(read_bound(root,r['palette'],768)),
            read_bound(root,r['parent_raw']),
            [(f,source_indices(read_bound(root,f['Source'],1044)))for f in r['frames']])


def derive(palette, raw_bytes, frames):
    """Pure verified-bytes operation. Never reopen source or parent filenames."""
    with Image.open(io.BytesIO(raw_bytes)) as opened:
        if (opened.format!='PNG' or opened.mode not in ('RGB','RGBA') or opened.width!=2*opened.height
                or not 128<=opened.height<=2048 or opened.width*opened.height>MAX_PIXELS):
            raise ValueError('bounded exact 2x1 PNG parent required')
        raw=np.asarray(opened.convert('RGBA')).copy()
    if np.any(raw[:,:,3]!=255):raise ValueError('no alpha repair/hidden RGB allowed')
    size=raw.shape[0];output=[]
    for column,(f,src)in enumerate(frames):
        mask=semantic_mask(f['asset'],src)
        if selected_digest(mask)!=f['selected_cells_sha256']:raise ValueError('Source cohort digest mismatch')
        parent=raw[:,column*size:(column+1)*size,:]
        # A raw 3x3 luminance witness must lie wholly in the same gray cohort.
        coordinates=((np.arange(size)*2+1)*32)//(size*2)
        mapped=mask[coordinates[:,None],coordinates[None,:]]
        luma=parent[:,:,:3].astype(np.float64)@LUMA
        eligible=mapped[1:-1,1:-1].copy();low=luma[1:-1,1:-1].copy();high=low.copy()
        for dy,dx in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            yy=slice(1+dy,size-1+dy);xx=slice(1+dx,size-1+dx)
            eligible &= mapped[yy,xx];low=np.minimum(low,luma[yy,xx]);high=np.maximum(high,luma[yy,xx])
        witnesses=int(np.count_nonzero(eligible&(high-low>=2.0)))
        if witnesses==0:raise ValueError('no authentic raw same-material fine luminance witness')
        baseline=np.asarray(Image.fromarray(parent).resize((128,128),Image.Resampling.LANCZOS)).copy()
        area=np.repeat(np.repeat(mask,4,0),4,1);rgb=baseline[:,:,:3].astype(np.float64)
        generated_luma=rgb@LUMA;anchor=palette[src[mask]].astype(np.float64).mean(axis=0)
        if anchor.max()-anchor.min()>8:raise ValueError('Source cohort is not near-neutral gray')
        anchor_luma=float(anchor@LUMA);shift=anchor_luma-float(generated_luma[area].mean())
        if abs(shift)>MAX_SHIFT:raise ValueError('gray mean correction exceeds fixed32 cap')
        proposed=(generated_luma[area]+shift)[:,None]+(anchor-anchor_luma)[None,:]
        if np.any(proposed<0)or np.any(proposed>255):raise ValueError('clipping forbidden')
        result=baseline.copy();result[:,:,:3][area]=np.rint(proposed).astype(np.uint8)
        if not np.array_equal(result[~area],baseline[~area]):raise AssertionError('outside changed')
        transformed_luma=result[:,:,:3].astype(np.float64)@LUMA
        error=float(np.abs(transformed_luma[area]-(generated_luma[area]+shift)).max())
        if error>0.5000001:raise AssertionError('generated luminance structure lost')
        metrics=dict(asset=f['asset'],semantic_Source_cells=int(mask.sum()),corrected_output_pixels=int(area.sum()),
                     unmodified_resized_parent_pixels=int((~area).sum()),Source_aggregate_RGB=anchor.tolist(),
                     generated_luma_mean=float(generated_luma[area].mean()),constant_gray_mean_offset=shift,
                     raw_same_cohort_3x3_luma_witnesses=witnesses,max_luma_structure_rounding_error=error,
                     generated_luma_variance=float(generated_luma[area].var()),
                     output_luma_variance=float(transformed_luma[area].var()),
                     exact_Original_pixel_copies=0,outside_resized_parent_exact=True,
                     selected_cells_sha256=selected_digest(mask),output_scale=4)
        output.append((f['asset'],result,metrics))
    return output


def publish_no_replace(stage,target):
    if os.name=='nt':os.rename(stage,target);return
    if not sys.platform.startswith('linux'):raise OSError(errno.ENOTSUP,'atomic publication unsupported')
    libc=ctypes.CDLL(None,use_errno=True)
    if not hasattr(libc,'renameat2'):raise OSError(errno.ENOTSUP,'renameat2 unavailable')
    fn=libc.renameat2;fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    fn.restype=ctypes.c_int
    if fn(-100,os.fsencode(stage),-100,os.fsencode(target),1)!=0:
        code=ctypes.get_errno();raise OSError(code,os.strerror(code),str(target))


def run(recipe_relative,input_root,output):
    root=Path(input_root).absolute();rel=PurePosixPath(recipe_relative)
    if rel.is_absolute()or '..'in rel.parts or not rel.parts:raise ValueError('relative recipe required')
    # Recipe bytes use the same no-follow reader after a separately bound hash.
    body=read_regular(root,rel.as_posix(),1_000_000)
    r=json.loads(body);prepared=prepare_inputs(r,root);result=derive(*prepared)
    output=Path(output).absolute()
    if output.exists()or output.is_symlink()or not output.parent.is_dir():raise ValueError('fresh output directory required')
    tool_path=Path(__file__).absolute();tool_bytes=read_regular(tool_path.parent,tool_path.name);outputs={};pngs={}
    for asset,rgba,_ in result:
        stream=io.BytesIO();Image.fromarray(rgba).save(stream,format='PNG');pngs[asset]=stream.getvalue();outputs[asset]=sha(pngs[asset])
    execution=dict(status='success',method=METHOD,recipe_sha256=sha(body),tool_sha256=sha(tool_bytes),
                   source_sha256={f['asset']:f['Source']['sha256']for f in r['frames']},
                   parent_raw_sha256=[r['parent_raw']['sha256']],output_sha256=outputs)
    receipt=dict(status='DERIVED_NOT_ART_APPROVAL',execution=execution,frames=[m for _,_,m in result],
                 runtime=dict(python=sys.version,numpy=np.__version__,Pillow=PILLOW_VERSION),
                 limits='Source owns semantic geometry and one aggregate gray anchor only; generated raw owns every luminance difference. No per-cell Source RGB copying, flat fallback, new pixels outside resized-parent selection, or quality approval. Resized-parent baseline uses Pillow Lanczos3; equality to old Rust raw-bank resampling is NOT claimed.')
    stage=Path(tempfile.mkdtemp(prefix='.'+output.name+'.stage-',dir=output.parent))
    try:
        for asset in pngs:(stage/(asset+'-DERIVED-graycast-v1.png')).write_bytes(pngs[asset])
        (stage/'execution-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if read_bound(root,{'path':rel.as_posix(),'sha256':sha(body)},1_000_000)!=body:raise ValueError('recipe changed')
        prepare_inputs(r,root)  # Reauthenticate originals; no second render.
        if read_regular(tool_path.parent,tool_path.name)!=tool_bytes:raise ValueError('tool changed')
        publish_no_replace(stage,output)
    except BaseException:shutil.rmtree(stage,ignore_errors=True);raise
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--recipe',required=True)
    p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    run(a.recipe,a.input_root,a.output)

if __name__=='__main__':main()
