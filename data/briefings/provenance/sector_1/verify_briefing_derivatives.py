"""Read-only check of archived masters and deterministic HD/SD compositions."""
from pathlib import Path
import argparse, hashlib, json
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--private-package', type=Path)
group.add_argument('--game-root', type=Path)
args = parser.parse_args()
game = (args.private_package or args.game_root).resolve()
archive = game if args.private_package else game / 'data/briefings/provenance/sector_1'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
records = []
for wave in range(1, 10):
    recipe = json.loads((archive / f'recipes/sector_1_wave_{wave}.json').read_bytes())
    master = archive / recipe['untouched_master']
    assert sha(master) == recipe['untouched_master_sha256']
    with Image.open(master) as image:
        image.load()
        assert list(image.size) == recipe['master_dimensions']
        hd = image.convert('RGB').crop(recipe['integer_exact16to10_center_crop']).resize((1280, 800), Image.Resampling.LANCZOS)
    sd = hd.resize((320, 200), Image.Resampling.LANCZOS)
    for key, derived in [('HD', hd), ('SD', sd)]:
        path = game / recipe[key]['path']
        assert sha(path) == recipe[key]['sha256']
        with Image.open(path) as actual:
            actual.load()
            assert actual.format == 'PNG' and actual.size == derived.size
            assert actual.convert('RGB').tobytes() == derived.tobytes()
    records.append(dict(mission_id=recipe['mission_id'], HD=True, SD=True, unchanged_master=True))
print(json.dumps(dict(status='PASS', missions=9, unchanged_masters=9, runtime_images=18,
    exact_derivative_RGB=True, mode='private_package' if args.private_package else 'self_contained_game_root',
    Pillow_version=Image.__version__, records=records), indent=2))
