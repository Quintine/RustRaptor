Regenerate all nine Outer Regions HD/SD briefing pairs offline from the bundled untouched masters and checked crop recipes. The original `derive_same_composition.py` is historical producer evidence; this script is the portable reproducer.

From the RustRaptor project folder, with Python and Pillow installed:

```sh
python3 data/briefings/provenance/original-sector3-20261018/reproduce_from_bundled_masters.py . regenerated-sector3
```

The destination must be new. All 18 PNG hashes must match before any files are published. The script reads only nine local masters and nine local recipes; it never follows provider output hints or accesses generation services. PNG byte equality was verified with Python 3.14.7, Pillow 12.3.0 and zlib 1.3.2. Other PNG compression versions may require this matching authoring runtime. Playing the game uses the included PNGs and requires none of these authoring tools.
