#!/usr/bin/env python3
"""Read-only exact generated-cell and Source check; references are HD-root relative."""
from pathlib import Path
import hashlib,json,io,sys
from PIL import Image
J=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve();H=J.parent.parent;d=json.loads((J/'direct-atlas-extraction-recipe.json').read_text());assert d['path_base']=='hd_root';sha=lambda b:hashlib.sha256(b).hexdigest()
def checked(r):
 p=H/r['path'];assert p.resolve().is_relative_to(H);b=p.read_bytes();assert sha(b)==r['sha256'];return b
m=Image.open(io.BytesIO(checked(d['untouched_master'])));assert m.mode=='RGB'and m.size==(1254,1254);l,t,w,h=d['crop'];c=m.crop((l,t,l+w,t+h));a=checked(d['accepted_artwork']);assert Image.open(io.BytesIO(a)).tobytes()==c.tobytes();buf=io.BytesIO();c.save(buf,format='PNG');assert sha(buf.getvalue())==sha(a)
for r in d['Original_sources']:checked(r)
checked(d['palette']);checked(d['shared_lineage']);print(json.dumps(dict(status='PASS_EXACT_DIRECT_CELL_AND_CROSS_NEW_JOB_HD_REFERENCES',asset=d['asset'],new_QA_or_pixel_operations=0)))
