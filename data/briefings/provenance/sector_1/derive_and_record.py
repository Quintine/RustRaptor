"""Preserve untouched imagegen PNG and derive same-composition 16:10 HD/SD."""
from pathlib import Path
import hashlib, json, re, shutil, sys, datetime
from PIL import Image

N = Path(__file__).resolve().parent
wave = int(sys.argv[1])
assert 1 <= wave <= 9
receipt = json.loads((N / f'generation/sector_1_wave_{wave}.safe-provider-and-gate.json').read_bytes())
assert receipt['submitted'] is True and receipt['outcome'] == 'success'
paths = re.findall(r'/home/quintine/\.codex/generated_images/[^\s]+\.png', receipt['output_hint'])
assert len(set(paths)) == 1
source = Path(paths[0])
assert source.is_file() and not source.is_symlink()
assert shutil.disk_usage(N).free - 20_000_000 >= 3_000_000_000
master = N / f'masters/sector_1_wave_{wave}.raw.png'
assert not master.exists()
with master.open('xb') as out:
    out.write(source.read_bytes())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(master) == digest(source)
with Image.open(master) as raw:
    assert raw.format == 'PNG'
    raw.load()
    width, height = raw.size
    # Largest centered integer 16:10 rectangle; no stretch and no pixel painting.
    unit = min(width // 16, height // 10)
    assert unit > 0
    crop_w, crop_h = unit * 16, unit * 10
    left, top = (width - crop_w) // 2, (height - crop_h) // 2
    box = (left, top, left + crop_w, top + crop_h)
    image = raw.convert('RGB').crop(box)
    hd = image.resize((1280, 800), Image.Resampling.LANCZOS)
    sd = hd.resize((320, 200), Image.Resampling.LANCZOS)
    hd_path = N / f'data/briefings/sector_1_wave_{wave}_hd.png'
    sd_path = N / f'data/briefings/sector_1_wave_{wave}_sd.png'
    assert not hd_path.exists() and not sd_path.exists()
    hd.save(hd_path)
    sd.save(sd_path)
    assert Image.open(hd_path).size == (1280, 800)
    assert Image.open(sd_path).size == (320, 200)
    assert Image.open(sd_path).convert('RGB').tobytes() == hd.resize((320, 200), Image.Resampling.LANCZOS).tobytes()
    # Exact crop used by the proposed menu: centered132:70 preview.
    display_h = 1280 * 70 / 132
    menu_box = (0, (800 - display_h) / 2, 1280, (800 + display_h) / 2)
    preview = hd.resize((132, 70), Image.Resampling.LANCZOS, box=menu_box)
    preview_path = N / f'review/sector_1_wave_{wave}_menu132x70.png'
    preview.save(preview_path)
    recipe = dict(format_version=1, mission_id=f'base:sector_1_wave_{wave}',
        asset_type='new_cinematic_mission_briefing_not_original_sprite_HD_credit',
        provider='built_in_imagegen', actual_calls=1,
        actual_provider_primitive_receipt=f'generation/sector_1_wave_{wave}.safe-provider-and-gate.json',
        source_builtin_file=str(source), untouched_master=f'masters/{master.name}',
        untouched_master_sha256=digest(master), master_dimensions=[width, height],
        integer_exact16to10_center_crop=list(box), cropped_dimensions=[crop_w, crop_h],
        HD=dict(path=f'data/briefings/{hd_path.name}', dimensions=[1280, 800], sha256=digest(hd_path), mode='RGB', operation='center_crop_then_LANCZOS_resize_no_painted_changes'),
        SD=dict(path=f'data/briefings/{sd_path.name}', dimensions=[320, 200], sha256=digest(sd_path), mode='RGB', operation='LANCZOS_downsample_of_final_HD_same_composition'),
        menu_preview=dict(path=f'review/{preview_path.name}', dimensions=[132,70], centered_crop_HD_float_box=list(menu_box), runtime_asset=False),
        prompt=f'prompts/sector_1_wave_{wave}.txt', image_edits_or_generated_variants=0,
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    recipe_path = N / f'recipes/sector_1_wave_{wave}.json'
    with recipe_path.open('x') as out:
        json.dump(recipe, out, indent=2)
        out.write('\n')
assert digest(master) == digest(source)
print(json.dumps(dict(wave=wave, raw=[width,height], crop=list(box), hd=str(hd_path), sd=str(sd_path), master_sha256=digest(master)), indent=2))
