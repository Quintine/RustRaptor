# Iron Coast 2 — Tidal Relay

Disrupt the tidal communications network after the Breakwater raid. Destroy
all three armored navigation relays, then defeat the **Relay Warden** radar
carrier. Relays anchor in the firing corridor until destroyed; neither an
escaped optional enemy nor an early boss kill can lock the objectives.
Each relay yields 140 credits and recovers 12 ordinary energy. Victory pays
7,500 credits in addition to normal destruction and salvage rewards.

Enable this package in **Mods** to select its eight-package standalone set:
this mission, `iron_coast_scout`, `iron_coast_turret`, `pulse_cannon`,
`seeker_swarm`, `ion_lance`, `iron_coast_boss_2`, and `iron_coast_music`.
Choose **Iron Coast 2 — Tidal Relay** in the mission menu. The optional
`iron_coast_campaign` assembly package connects it to the full six-level
route. This individual package has no next-mission override and can be played
without the other five mission packages.

The flight grants a mission-only Pulse Cannon when a free inventory slot
exists. The cannon is returned on success or failure; a cannon already owned
by the pilot is retained. A full 20-slot inventory skips the loan. No kits,
ammunition, or premium weapon purchases are required for the acceptance route.
The duration of 2,300 ticks is a catalog hint; timer expiry does not win.
The Relay Warden arrives at tick 860 and remains available until destroyed.

The waves mix Iron Coast scouts and turrets with untouched original enemy
registry definitions and their native animation, guns, and movement:

| Spawn | Original definition | Native movement |
| --- | --- | --- |
| Tick 75, x216 | `base:enemy_0_20` / SHIP05G1_PIC | Six-leg zigzag entry, speed 3 |
| Tick 330, x168 | `base:enemy_0_23` / SHIP06G1_PIC | Wide crossing sweep, speed 3 |
| Tick 620, x176 | `base:enemy_0_56` / SHIP25G1_PIC | Authored entry then player chase, speed 5 |

All three appear on every difficulty. Their original assets remain in the
separately installed game catalog; this package neither duplicates nor
redefines original enemy data. New package-local art supplies the relay
station, briefing and scrolling tidal causeway in SD and HD. The shared
**Coastal Steel** soundtrack is a 96-second generated MUS loop played by
the Rust FM synthesizer. Six local WAV cues cover approach, network alert,
relay destruction, network shutdown, boss arrival and victory.

All three generated art masters, 216 pairs of terrain crops, SD/HD briefing
and relay sprites, WAVs, scripts and provenance are included in Git.
`prompts.json` and `prompts.md` record the exact built-in imagegen prompts.
The original VGA palette remains outside Git. The builder converts the full
SD terrain canvas before splitting tiles, uses a reflected scroll period with
identical repeat boundaries, and normalizes excessive transparent padding
around the relay silhouette without changing its logical 32×32 canvas.

```sh
python3 RustRaptor/mods/iron_coast_mission_2/build_assets.py
cargo run --locked --manifest-path RustRaptor/Cargo.toml --no-default-features \
  -- --data data --mods RustRaptor/mods \
  --validate-mods iron_coast_scout,iron_coast_turret,pulse_cannon,seeker_swarm,ion_lance,iron_coast_boss_2,iron_coast_music,iron_coast_mission_2
cargo run --locked \
  --manifest-path RustRaptor/mods/iron_coast_mission_2/validation/Cargo.toml \
  --target-dir RustRaptor/target --bin validate-mission
```

The standalone validator uses the actual engine and locally installed original
catalog. It preserves script state between four mission restarts, exercises a
registered 75-energy/10,000-credit pilot, a 100-energy fixture, an owned cannon
and a full inventory, and checks exact completion gating and one-time reward.
It fires continuously at y160, moving at most four pixels per tick toward the
first live relay, or x144 when no relay is alive. It injects no damage, shield,
credit or purchased-weapon commands during its playable routes.

The normal registration run wins at **tick 926**, with **86 energy** and
**21,365 total credits** (11,365 earned). All three native enemies are observed
moving. The full-inventory run wins at tick 930 with 82 energy, no loaned cannon
and ordinary equipment preserved. Combat shield charge may naturally change.
The owned-cannon run retains the pilot's cannon. All six local cues dispatch.
See `acceptance-report.json` for exact independent/restarted-run results and
`asset-report.json` for palette, seam, transparency and waveform checks.
Human play difficulty and audiovisual preference still require normal play
review; these controlled simulations establish a viable path.
