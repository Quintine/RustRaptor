"""Finite DERIVED terrain; Source broad colour + genuine parent fine/mid luminance.
No generator, registry, World or original-data writes. Source-only regions and
retained pale-tip/lavender cells receive zero HD detail credit. Independent ART required.
"""
from pathlib import Path
import argparse, hashlib, io, json, os, re, shutil, stat, types
import numpy as np
from PIL import Image
METHOD='six-dark-Source-gray-lavender-generated-fine-mid-buffered-v1'
DEPENDENCIES={'hd_terrain_retexture':'0e4d7d5a4f7a7ddf6e396e757691156dfc74d231d9925744c342078532b89a98','hd_terrain_group_retexture':'24e3751d26090699f2d8d317ed98f73e05f51f3caa6dc2bf21fc40a109068a27'}
PARAMETERS={'output_side':512,'source_sigma':3.0,'residual_sigma_fine':0.65,'residual_sigma_coarse':10.0,'residual_percentile':80.0}
GROUPS=[{'name': 'pale', 'indices': [1], 'texture_log_gain': 0.06, 'quiet_from_source_variance': True}, {'name': 'gray', 'indices': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27], 'texture_log_gain': 0.38, 'quiet_from_source_variance': True}, {'name': 'floor', 'indices': [28, 29, 30, 31], 'texture_log_gain': 0.38, 'quiet_from_source_variance': True}, {'name': 'lavender', 'indices': [113], 'texture_log_gain': 0.06, 'quiet_from_source_variance': True}]
COHORTS=[['301c3','301c8','301cc'],['301d1','301d4','301d7']]
PALETTE='1cf6adb926d1dee1888b3e3d33b51a7049b3e5eb5f90a3067ef71c8970547204'
PINS={'301c3': ['9c370900214a601e40200cb67e959f042323d001f7a2e6de3627e5044a2078b5', 'dc4244108b9e760f324f4279e530ef2e02a799b087fe21570668c345fbe37b43'], '301c8': ['4d87a0251b8b064c6ab5835ae31f5eaabfec405f56b0408980f93484b70470d1', '8b6d719ecd4762156a81e9f0173ccea0dcfd9d1967b3fae6f04f82d6aba9297d'], '301cc': ['be151484d73ebe4461115391c3fcea20f109a14b0f2eee1ce13f1cbb34014355', 'e2cf0453dfc61b5729ef9c968bf48dc6dc3deb42e1fa6e1e520904ebf4f6e502'], '301d1': ['c9acde36a4eba021ede70d02f13a63be869b8403636d0d8e61b2647484b26aa7', 'b35415096e86ef4e3e7b73994f1f2ab7e7ef44109b7a339bf8325e3189aa69cc'], '301d4': ['ca09a82a3379d6bdf15360a3469e7d7f0a278c1edfaab835c4b7d3e80ebff239', 'b4cf5cfde22ea1ab889cea70a905d3320ec7395a20e8657f69716251c4a9f166'], '301d7': ['4d39e7d667501dca5941243b5f371e4e783663faaf5f69c64385a98c41e015af', '569ecfbae3dc723f1bc2c2dca2f0aa3d452f94e3c68d11bb21ca48b02537d4e7']}
def sha(payload):return hashlib.sha256(payload).hexdigest()

def binding(value):
    if type(value)is not dict or set(value)!={'path','sha256'} or type(value['path'])is not str or type(value['sha256'])is not str or re.fullmatch('[0-9a-f]{64}',value['sha256'])is None:raise ValueError('exact path/hash binding required')
    return value

def read_contained(root,relative,limit=32*1024*1024):
    if type(relative)is not str or relative.startswith('/') or '\\'in relative or any(x in ('','.','..')for x in relative.split('/')):raise ValueError('strict contained relative path required')
    root=Path(root).absolute()
    if '..'in root.parts:raise ValueError('noncanonical root path')
    flags=os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK
    fd=os.open('/',flags|os.O_DIRECTORY)
    try:
        for part in root.parts[1:]+tuple(relative.split('/')[:-1]):
            following=os.open(part,flags|os.O_DIRECTORY,dir_fd=fd);os.close(fd);fd=following
        source=os.open(relative.split('/')[-1],flags,dir_fd=fd)
        try:
            before=os.fstat(source)
            if not stat.S_ISREG(before.st_mode)or not 0<=before.st_size<=limit:raise ValueError('bounded regular input required')
            chunks=[];size=0
            while True:
                chunk=os.read(source,min(65536,limit+1-size))
                if not chunk:break
                chunks.append(chunk);size+=len(chunk)
                if size>limit:raise ValueError('EOF limit exceeded')
            after=os.fstat(source)
            identity=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_mode)
            if identity(before)!=identity(after)or size!=before.st_size:raise ValueError('input changed/non-EOF read')
            return b''.join(chunks)
        finally:os.close(source)
    finally:os.close(fd)

class BufferedInputs:
    def __init__(self,root):self.root=root;self.cache={};self.physical_reads=0
    def read(self,value,limit=32*1024*1024):
        binding(value);relative=value['path']
        if relative not in self.cache:self.cache[relative]=read_contained(self.root,relative,limit);self.physical_reads+=1
        payload=self.cache[relative]
        if len(payload)>limit or sha(payload)!=value['sha256']:raise ValueError('input hash/limit mismatch')
        return payload

def modules(payloads):
    if set(payloads)!=set(DEPENDENCIES)or any(sha(payloads[k])!=v for k,v in DEPENDENCIES.items()):raise ValueError('dependency buffer pins differ')
    loaded={}
    for name,payload in payloads.items():
        m=types.ModuleType('verified_'+name);m.__file__='/authenticated-buffered/'+name+'.py';exec(compile(payload,m.__file__,'exec'),m.__dict__);loaded[name]=m
    return loaded

def decode_png(payload):
    with Image.open(io.BytesIO(payload))as im:
        if im.format!='PNG'or im.size!=(1254,1254)or getattr(im,'n_frames',1)!=1 or im.mode not in('RGB','RGBA'):raise ValueError('exact bounded single full provider PNG required')
        if im.mode=='RGBA'and im.getchannel('A').getextrema()!=(255,255):raise ValueError('opaque parent required; never fill holes')
        return np.array(im.convert('RGB'))

def validate_recipe(recipe):
    if type(recipe)is not dict or set(recipe)!={'format_version','method','dependencies','palette','frames','parameters','material_groups'}or type(recipe['format_version'])is not int or recipe['format_version']!=1 or recipe['method']!=METHOD:raise ValueError('exact versioned recipe required')
    if recipe['parameters']!=PARAMETERS or recipe['material_groups']!=GROUPS:raise ValueError('fixed math only')
    if type(recipe['frames'])is not list or any(type(f)is not dict for f in recipe['frames'])or [f.get('asset')for f in recipe['frames']]not in COHORTS:raise ValueError('exact complete3 distinct-tile cohort required')
    if type(recipe['dependencies'])is not dict or set(recipe['dependencies'])!=set(DEPENDENCIES):raise ValueError('exact dependencies required')
    for k,pin in DEPENDENCIES.items():
        if binding(recipe['dependencies'][k])['sha256']!=pin:raise ValueError('dependency pin differs')
    if binding(recipe['palette'])['sha256']!=PALETTE:raise ValueError('palette pin differs')
    for f in recipe['frames']:
        if type(f)is not dict or set(f)!={'asset','Source','parent_raw','origin','crop'}or f['asset']not in PINS:raise ValueError('exact frame fields required')
        if f['origin']!=[0,0]or f['crop']!=[0,0,1254,1254]or any(type(v)is not int for v in f['origin']+f['crop']):raise ValueError('exact whole canvas required')
        for key,pin in zip(('Source','parent_raw'),PINS[f['asset']]):
            if binding(f[key])['sha256']!=pin:raise ValueError('Source/provider binding differs')

def derive(recipe,root):
    validate_recipe(recipe);inputs=BufferedInputs(root);deps=modules({k:inputs.read(v,1024*1024)for k,v in recipe['dependencies'].items()});kernel=deps['hd_terrain_retexture'];group=deps['hd_terrain_group_retexture']
    palette=kernel.palette_rgb(inputs.read(recipe['palette'],768));outputs=[];reports=[]
    for f in recipe['frames']:
        source=kernel.decode_source(inputs.read(f['Source'],1044))
        if source.shape!=(32,32)or not set(map(int,np.unique(source)))<={i for group in GROUPS for i in group['indices']}:raise ValueError('exact supported Source shape/indices required')
        raw=decode_png(inputs.read(f['parent_raw']))
        result,base,labels,metrics=group.reconstruct(source,palette,raw,PARAMETERS,GROUPS,kernel)
        marker_owners=set()
        for factor in range(1,5):
            ys,xs=np.where(np.isin(kernel.scale_nx(source,factor),[1,113]))
            marker_owners.update((int(x)//factor,int(y)//factor)for x,y in zip(xs,ys))
        marker_cells=[list(xy)for xy in sorted(marker_owners)]
        # Runtime retains these literal logical cells using its own exact SourceNx.
        # The derived physical PNG remains honestly as returned by reconstruct().
        outputs.append((f['asset'],result));reports.append(dict(asset=f['asset'],Source_sha256=f['Source']['sha256'],parent_raw_sha256=f['parent_raw']['sha256'],original_detail_cells=marker_cells,retained_Source_cells_HD_credit=0,metrics=metrics))
    return outputs,dict(method=METHOD,assets=reports,physical_authenticated_input_reads=inputs.physical_reads,dependencies=DEPENDENCIES,scope='DERIVED Source broad RGB/Scale4x material geometry plus genuine generated monochrome fine/mid log-luminance; not untouched provider RGB. Source-backed structure and runtime pale-tip/lavender retentions receive zero new HD detail credit. Separate intrinsic/context ART approval required.')

def main(recipe_relative,recipe_sha,project_root,output):
    root=Path(project_root).absolute();payload=read_contained(root,recipe_relative,1024*1024)
    if sha(payload)!=recipe_sha:raise ValueError('recipe hash mismatch')
    recipe=json.loads(payload);validate_recipe(recipe);out=Path(output).absolute()
    if '..'in out.parts or not out.parent.is_dir()or any(p.is_symlink()for p in(out.parent,*out.parent.parents))or os.path.lexists(out):raise ValueError('fresh nonsymlink output required')
    if shutil.disk_usage(out.parent).free<1_932_735_284+32*1024*1024:raise ValueError('disk floor/reserve required')
    results,report=derive(recipe,root);prepared=[]
    for asset,result in results:
        buf=io.BytesIO();Image.fromarray(result).save(buf,format='PNG',compress_level=9);prepared.append((asset,buf.getvalue()))
    report['execution']=dict(status='success',tool_sha256=sha(read_contained(Path(__file__).parent,Path(__file__).name,1024*1024)),recipe_sha256=sha(payload),source_sha256={f['asset']:f['Source']['sha256']for f in recipe['frames']},parent_raw_sha256={f['asset']:f['parent_raw']['sha256']for f in recipe['frames']},outputs=[dict(asset=a,file=a+'-derived.png',sha256=sha(b))for a,b in prepared])
    out.mkdir()
    for asset,b in prepared:(out/(asset+'-derived.png')).write_bytes(b)
    (out/'ACTUAL-DERIVATION-RECEIPT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['execution']))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('recipe_relative');ap.add_argument('recipe_sha');ap.add_argument('project_root');ap.add_argument('output');a=ap.parse_args();main(a.recipe_relative,a.recipe_sha,a.project_root,a.output)
