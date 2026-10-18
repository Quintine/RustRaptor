"""Narrow DERIVED STAG03 SourceScale4 geometry/full-generated-RGB dispatcher.

Dependency implementations execute from authenticated buffered bytes in fresh
namespaces. Input files are read once through no-follow, contained descriptors.
This tool performs no engine operation or artwork approval.
"""
from __future__ import annotations
import argparse
import builtins
import ctypes
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import types
import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION

METHOD='derived-STAG03-fullcanvas-rational-generated-RGB-SourceScale4-warning66-v1'
FREE_FLOOR=3_000_000_000
OUTPUT_RESERVE=16_000_000
PINS={
    'decoder':'66184a4758027dadbadb5e20fe90b2add2b9fc218b7810304b1a1ea2de74f58e',
    'geometry':'c6123e9591f0a169846677019ddcb944bf9c2b4c9184a7d8ab02a08546de409b',
    'functional':'f8078284e300947aec4d2c9e70cbc7198fa3cb5d34de6b36c07cacc5f3820a84',
}
GROUPS=[sorted([[x,y]for x in range(l,r)for y in range(13,16)])for l,r in ((1,12),(19,30))]
TOOL_BYTES=Path(__file__).read_bytes()

def sha(payload):return hashlib.sha256(payload).hexdigest()

def route(value):
    if (type(value)is not str or not value or '\\'in value or ':'in value
            or Path(value).is_absolute() or Path(value).as_posix()!=value
            or '..'in Path(value).parts):
        raise ValueError('canonical contained relative path required')
    return Path(value)

def safe_read(base, binding, limit):
    if (type(binding)is not dict or set(binding)!={'path','sha256'}
            or type(binding['sha256'])is not str
            or re.fullmatch('[0-9a-f]{64}',binding['sha256'])is None):
        raise ValueError('exact path/SHA256 binding required')
    relative=route(binding['path'])
    flags=os.O_RDONLY|os.O_NOFOLLOW
    directory=os.open(base,flags|os.O_DIRECTORY)
    try:
        for part in relative.parts[:-1]:
            next_fd=os.open(part,flags|os.O_DIRECTORY,dir_fd=directory)
            os.close(directory);directory=next_fd
        fd=os.open(relative.name,flags,dir_fd=directory)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size>limit:
                raise ValueError('bounded regular input required')
            chunks=[];size=0
            while True:
                chunk=os.read(fd,min(65536,limit+1-size))
                if not chunk:break
                chunks.append(chunk);size+=len(chunk)
                if size>limit:raise ValueError('input exceeds byte ceiling')
            payload=b''.join(chunks)
            after=os.fstat(fd)
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
                raise ValueError('input changed during descriptor read')
        finally:os.close(fd)
    finally:os.close(directory)
    if sha(payload)!=binding['sha256']:raise ValueError('input SHA256 mismatch')
    return payload

def verified_modules(payloads):
    """Never use importlib/SourceFileLoader or re-open verified dependency paths."""
    if set(payloads)!=set(PINS) or any(sha(payloads[k])!=v for k,v in PINS.items()):
        raise ValueError('reviewed dependency bytes differ')
    loaded={}
    real_import=builtins.__import__
    proxy_sys=types.SimpleNamespace(path=list(sys.path),version=sys.version)
    def importer(name,globals=None,locals=None,fromlist=(),level=0):
        if name in loaded:return loaded[name]
        if name=='sys':return proxy_sys
        return real_import(name,globals,locals,fromlist,level)
    for key,name in (('decoder','hd_frame_policy'),('geometry','hd_dshp20_cleanup'),('functional','hd_other_functional_cleanup')):
        module=types.ModuleType(name)
        module.__file__=f'/authenticated-buffered-dependency/{name}.py'
        module.__dict__['__builtins__']={**vars(builtins),'__import__':importer}
        exec(compile(payloads[key],module.__file__,'exec'),module.__dict__)
        loaded[name]=module
    return loaded['hd_frame_policy'],loaded['hd_dshp20_cleanup'],loaded['hd_other_functional_cleanup']

def rational(value):
    if type(value)is int and abs(value)<=10**9:return Fraction(value)
    if type(value)is not str or re.fullmatch('-?[0-9]+(?:/[1-9][0-9]*)?',value)is None:
        raise ValueError('finite exact integer/rational string required')
    result=Fraction(value)
    if abs(result.numerator)>10**9 or result.denominator>10**9:
        raise ValueError('rational exceeds bounded arithmetic')
    return result

def rectangle(value,w,h,label):
    if type(value)is not list or len(value)!=4 or any(type(x)is not int for x in value):
        raise ValueError(label+' needs four integers')
    l,t,r,b=value
    if not 0<=l<r<=w or not 0<=t<b<=h:raise ValueError(label+' is out of bounds')
    return value

def alpha_bounds(mask):
    yy,xx=np.nonzero(mask)
    if not len(xx):raise ValueError('empty occupied support')
    return [int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)]

def render(recipe,inputs,modules):
    decoder,geometry,functional=modules
    if (type(recipe)is not dict or set(recipe)!={'format_version','method','asset','source','palette','parent_raw',
            'logical_canvas','origin','output_scale','alignment','max_fill_distance_pixels','functional_groups',
            'dependencies','expected_tool_sha256'} or type(recipe['format_version'])is not int
            or recipe['format_version']!=1 or recipe['method']!=METHOD or recipe['asset']!='300ae'):
        raise ValueError('exact STAG03 recipe fields/version/asset required')
    if recipe['logical_canvas']!=[32,32] or recipe['origin']!=[0,0] or type(recipe['output_scale'])is not int or recipe['output_scale']!=4:
        raise ValueError('native32 canvas/origin0/scale4 required')
    if any(type(x)is not int for x in recipe['logical_canvas']+recipe['origin']):
        raise ValueError('literal integer canvas/origin required')
    if type(recipe['max_fill_distance_pixels'])is not int or recipe['max_fill_distance_pixels']!=12:
        raise ValueError('exact twelve-output-pixel noncascading donor bound required')
    if recipe['functional_groups']!=GROUPS or any(type(x)is not int for g in recipe['functional_groups']for xy in g for x in xy):
        raise ValueError('exact two disjoint sorted33-cell functional groups required')
    w,h,cells=decoder._indices(inputs['source'])
    if (w,h)!=(32,32):raise ValueError('authentic Source canvas differs')
    source=np.asarray(cells,np.uint16).reshape(h,w)
    if (source<256).sum()<264 or any(source[y,x]>=256 for g in GROUPS for x,y in g):
        raise ValueError('all66 cells must be painted Source and within quarter bound')
    pb=inputs['palette']
    if len(pb)!=768 or max(pb)>63:raise ValueError('exact six-bit Original palette required')
    p6=np.frombuffer(pb,np.uint8).reshape(256,3).astype(np.uint16)
    palette=((p6<<2)|(p6>>4)).astype(np.uint8)
    with Image.open(io.BytesIO(inputs['parent_raw']))as image:
        if image.format!='PNG' or image.width*image.height>4_194_304:
            raise ValueError('bounded PNG parent required')
        parent=image.convert('RGBA')
    alignment=recipe['alignment']
    if type(alignment)is not dict or set(alignment)!={'raw_painted_bounds','source_painted_bounds','inverse_affine'}:
        raise ValueError('exact alignment declarations required')
    rl,rt,rr,rb=rectangle(alignment['raw_painted_bounds'],*parent.size,'raw bounds')
    sl,st,sr,sb=rectangle(alignment['source_painted_bounds'],w,h,'Source bounds')
    if alpha_bounds(np.asarray(parent)[:,:,3]>=128)!=[rl,rt,rr,rb] or alpha_bounds(source<256)!=[sl,st,sr,sb]:
        raise ValueError('declared bounds differ from actual complete Source/raw support')
    values=alignment['inverse_affine']
    if type(values)is not list or len(values)!=6:raise ValueError('six inverse affine rationals required')
    affine=list(map(rational,values))
    ax,ay=Fraction(rr-rl,(sr-sl)*4),Fraction(rb-rt,(sb-st)*4)
    expected=[ax,Fraction(0),rl-ax*sl*4,Fraction(0),ay,rt-ay*st*4]
    if affine!=expected:raise ValueError('affine differs from complete Source/raw support alignment')
    sampled=np.asarray(parent.transform((128,128),Image.Transform.AFFINE,
        tuple(map(float,affine)),Image.Resampling.BICUBIC)).copy()
    s4=geometry.scale2(geometry.scale2(source));mask=s4<256
    trusted=sampled[:,:,3]>=128
    rgb,fill=geometry.fill_generated_rgb(sampled[:,:,:3],trusted,mask,s4,12)
    body=np.zeros((128,128,4),np.uint8)
    body[:,:,:3][mask]=rgb[mask];body[:,:,3][mask]=255
    out=body;retentions=[];selected=np.zeros(mask.shape,bool)
    for group in GROUPS:
        out,receipt=functional.retain_functional_original(out,source,palette,group)
        retentions.append(receipt)
        for x,y in group:selected[y*4:(y+1)*4,x*4:(x+1)*4]=True
    if not np.array_equal(out[:,:,3],body[:,:,3]) or not np.array_equal(out[~selected],body[~selected]):
        raise ValueError('functional retention changed alpha or undeclared body samples')
    outside=mask&~selected
    direct=outside&trusted
    if int(direct.sum())*2<int(mask.sum()):raise ValueError('less than half complete body retains direct generated RGB')
    if not np.array_equal(out[:,:,:3][direct],sampled[:,:,:3][direct]):
        raise ValueError('direct generated RGB was changed')
    # Boundary interpolation is not evidence of preserved generated detail.
    # Check fully direct, unpatched interior cells, excluding a one-cell rim.
    interior=np.zeros((32,32),bool)
    for y in range(1,31):
        for x in range(1,31):interior[y,x]=bool(np.all(source[y-1:y+2,x-1:x+2]<256))
    for group in GROUPS:
        for x,y in group:interior[y,x]=False
    detail_cells=0
    for y,x in np.argwhere(interior):
        ys,xs=slice(y*4,(y+1)*4),slice(x*4,(x+1)*4)
        if np.all(direct[ys,xs]) and np.any(out[ys,xs,:3]!=out[y*4,x*4,:3]):detail_cells+=1
    if not detail_cells:
        raise ValueError('no generated interior detail remains')
    return out,dict(output_class='DERIVED_NOT_UNTOUCHED_GENERATION',
        native=[32,32],origin=[0,0],output_scale=4,fullcanvas_inverse_affine=[str(x)for x in affine],
        alpha_exact_SourceScale4=True,inputs_not_written_by_dispatcher=True,
        Source_painted_cells=int((source<256).sum()),functional_Original_cells=66,
        actual_Original_Scale4_RGBA_samples=int(selected.sum()),functional_Original_not_HD_credit=True,
        functional_groups=retentions,outside_functional_RGBA_exact=True,
        direct_generated_RGB_samples=int(direct.sum()),total_painted_samples=int(mask.sum()),
        direct_generated_nonconstant_interior_cells=detail_cells,
        noncascading_generated_RGB_fill=fill,actual_functional_calls=2,
        runtime_versions=dict(python=sys.version,numpy=np.__version__,Pillow=PILLOW_VERSION))

def publish_no_replace(staging,output):
    """Atomic directory install, never replace even an empty existing directory."""
    libc=ctypes.CDLL(None,use_errno=True)
    rename=getattr(libc,'renameat2',None)
    if rename is None:raise RuntimeError('Linux renameat2 required for no-replace publication')
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    fd=os.open(output.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        if rename(fd,os.fsencode(staging.name),fd,os.fsencode(output.name),1)!=0:
            number=ctypes.get_errno();raise OSError(number,os.strerror(number),str(output))
    finally:os.close(fd)

def run_recipe(recipe_path,output):
    recipe_path=Path(recipe_path)
    if recipe_path.is_symlink():raise ValueError('recipe must not be a symlink')
    base=recipe_path.parent.resolve(strict=True)
    output=Path(output)
    output=output if output.is_absolute()else base/output
    if output.parent.resolve(strict=True)!=base or output.name in ('','.','..'):
        raise ValueError('fresh output must be a direct child of recipe root')
    if output.exists() or output.is_symlink():raise ValueError('fresh absent output directory required')
    if shutil.disk_usage(base).free-OUTPUT_RESERVE<FREE_FLOOR:
        raise ValueError('three-gigabyte free floor plus bounded output reserve required')
    rb=recipe_path.read_bytes()
    if len(rb)>128*1024:raise ValueError('recipe exceeds metadata ceiling')
    recipe=json.loads(rb)
    if type(recipe)is not dict or recipe.get('expected_tool_sha256')!=sha(TOOL_BYTES):
        raise ValueError('actual tool bytes differ from declared reviewed dispatcher')
    deps=recipe.get('dependencies')
    if type(deps)is not dict or set(deps)!=set(PINS):raise ValueError('exact three dependencies required')
    payloads={k:safe_read(base,v,128*1024)for k,v in deps.items()}
    modules=verified_modules(payloads)
    inputs={k:safe_read(base,recipe[k],32*1024*1024 if k=='parent_raw' else 4*1024*1024)
            for k in ('source','palette','parent_raw')}
    rgba,report=render(recipe,inputs,modules)
    buffer=io.BytesIO();Image.fromarray(rgba).save(buffer,format='PNG',compress_level=9)
    png=buffer.getvalue()
    execution=dict(status='success',method=METHOD,recipe_sha256=sha(rb),tool_sha256=sha(TOOL_BYTES),
        source_sha256={'300ae':sha(inputs['source'])},parent_raw_sha256=[sha(inputs['parent_raw'])],
        output_sha256={'300ae':sha(png)})
    report.update(execution=execution,authenticated_dependency_bytes=PINS,
        dependency_execution='Fresh isolated namespaces executed from verified buffered bytes; no dependency/input path reopening for processing.',
        Source_decoder_sha256=PINS['decoder'],RGBA_sha256=sha(rgba.tobytes()))
    staging=Path(tempfile.mkdtemp(prefix='.stag03-derived-',dir=base))
    try:
        for name,payload in [('300ae-derived.png',png),('derived-provenance.json',(json.dumps(report,indent=2,sort_keys=True)+'\n').encode())]:
            with(staging/name).open('xb')as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
        publish_no_replace(staging,output)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe',type=Path);parser.add_argument('fresh_output',type=Path)
    args=parser.parse_args()
    print(json.dumps(run_recipe(args.recipe,args.fresh_output)['execution'],sort_keys=True))
