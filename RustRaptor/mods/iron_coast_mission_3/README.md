# Iron Coast — Mission 3: Saltworks Convoy

Intercept three armored cargo transports, disable two escort turrets and destroy
the **Saltbreaker** command cruiser. Cargo wrecks recover maintenance supplies
that restore 15 shield each. The completion bonus is 7,500 credits, in addition
to enemy destruction rewards. Waiting out the duration cannot complete it.

Enable this individual mod to select its installed dependencies automatically:
`iron_coast_scout`, `iron_coast_turret`, `iron_coast_boss_3`, `pulse_cannon`,
`seeker_swarm`, `ion_lance`, and `iron_coast_music`, all compatible with `^1.0`.
Then choose **Iron Coast 3 — Saltworks Convoy** in the mission list. The optional
Iron Coast campaign assembly places this mission after Mission 2; the individual
mod works independently and does not override any other mission.

The saltworks include rectangular evaporation basins, steel conveyors, brine
channels and a central cargo route. Eighteen fighter arrivals mix fourteen
scripted Iron Coast scouts with four original Raptor enemy definitions:
`base:enemy_0_20` uses a weaving descent; `base:enemy_0_21` and
`base:enemy_0_22` make opposing lateral sweeps; `base:enemy_0_73` makes a
curved approach. Their original sprite IDs, animation, weapons, movement paths,
health and rewards are retained. They spawn before the command cruiser.

Cargo transports and required turrets stop at their interdiction lines instead
of scrolling out of reach. The Saltbreaker remains in its patrol corridor until
destroyed. A full 20-slot inventory can start and complete this mission: it
does not grant loans or additional equipment, and cargo recovery restores
shield directly. Mission start resets the objective and phase state on retries.

All new artwork and sound are included in Git: three built-in imagegen master
images, their packaged SD and HD variants, five synthesized WAV cues, the
deterministic asset builder and provenance. SD uses the original game palette;
HD keeps the same logical canvases. Terrain is quantized as one complete image
before tile extraction. A forward/reflected repeat makes both scroll boundaries
match exactly. `asset-report.json` records dimensions, transparency, palette
checks, seam checks, source hashes and audio hashes.

Regenerate the packaged images and cues from the checked-in masters:

```sh
python3 RustRaptor/mods/iron_coast_mission_3/build_assets.py
```

The default builder palette comes from the separately installed original catalog
at `data/misc/PALETTE_DAT`; use `--palette PATH` to select another copy. Original
game assets are not copied into the mod. `prompts.md` and `prompts.json` document
generation, including the style-reference roles.

Run the local acceptance probe from the repository root:

```sh
RustRaptor/mods/iron_coast_mission_3/validate.sh
```

The probe uses the actual original catalog and scripts, tests registered pilots
(75 shield and 10,000 credits) on difficulties 1–3, tests a default deterministic
fixture, checks that essential targets remain available, and checks restart,
full-inventory and single-reward behavior. Ordinary playthroughs use starter
forward guns with held fire at logical position `(144, 160)` and inject no
damage, credits, shield or inventory commands into the playthrough. The separate retention
test restores test shield only to observe waiting behavior; it is not used as
a successful gameplay proof. `validation-report.txt` records final results.

Final registered-pilot starter results: difficulty 1 completed at tick **1184**
with **88** shield; difficulties 2 and 3 completed at tick **1264** with
**83** shield. All three ended with **21,515** credits. The full 20-slot flight
completed at tick **1178** with 82 shield and retained every non-energy item
and count. No paid refills or premium weapon purchases are required.
