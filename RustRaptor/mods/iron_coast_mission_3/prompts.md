# Saltworks Convoy artwork provenance

All three masters were generated with the built-in imagegen tool. Reference
images served only as style references; they were not edit targets. Generated
masters are retained beside their deterministically packaged footprints.
The packaging builder crops alpha bounds, resamples complete canvases, applies
the original palette for SD, splits terrain and synthesizes new sounds. It
does not generate artwork or paint over the imagegen sources.

## Terrain master

Reference: `iron_coast_mission_1/art/terrain-source-hd.png`.
Output: `art/terrain-source-hd.png`.

> Use case: stylized-concept. Asset type: opaque scrolling terrain master for RustRaptor Iron Coast Mission 3, Saltworks Convoy. Image 1 is a style reference only, not an edit target. Create a NEW tall terrain image, 3:4 aspect, strictly orthographic top-down, a classic 1990s Raptor military shoot-em-up terrain remastered in restrained HD. Salt-processing industrial coastal flats: pale gray mineral evaporation pools in rectangular grids, corroded steel salt conveyor bridges, gray industrial service roads, dark navy brine channels along the left edge, rusted machinery huts, pipelines, olive supply crates and tiny caution-yellow markings at the sides. Keep a wide readable vertical gray roadway through the center for aircraft combat; no aircraft, enemies, people, text, logos, UI, perspective or cast-long shadows. Match the reference's military navy/gray/rust/olive palette, fine hand-rendered metallic textures, strong simple forms and subtle top-left light. Full bleed, continuous terrain, no borders. New image must be visually distinct from reference harbor docks while fitting same game art direction.

## Briefing master

Reference: `iron_coast_mission_1/art/briefing-source-hd.png`.
Output: `art/briefing-source-hd.png`.

> Use case: stylized-concept. Asset type: opaque mission briefing illustration for the classic military vertical shooter RustRaptor, Iron Coast Mission 3: Saltworks Convoy. Image 1 is style reference only, not an edit target. Create a NEW landscape 16:10 image, strict orthographic top-down aerial reconnaissance view of an industrial saltworks convoy route. Wide gray vertical industrial roadway cuts through center, small armored olive cargo transport convoy heading upward along it, pale gray rectangular salt evaporation basins, rusted salt conveyors over narrow dark navy brine channels, compact pipes and cylindrical tanks at road margins. Two or three tiny olive defensive military emplacements can mark convoy escort. Strong clean simple silhouettes and a restrained navy/gray/rust/olive palette, caution-yellow road strips, detailed hand-rendered metal textures matching the Raptor HD military pixel-art reference. Full bleed single finished scene. No aircraft or huge battle effects, no lettering/text/numbers, no logos/watermarks, no framing/UI, no oblique perspective or horizon. Show the Saltworks setting clearly different from reference harbor docks; this must reduce to a readable 320x200 briefing image.

## Cargo sprite master

Reference: `iron_coast_turret/art/unit-hd.png`.
Output: `art/convoy-source-hd.png`.

> Use case: stylized-concept. Asset type: transparent sprite master for RustRaptor Iron Coast Mission 3 Saltworks Convoy. Reference image for matching olive/gray military game art only. NEW single armored supply truck, orthographic top-down, front UP. Compact olive-drab cab, rectangular weathered gray cargo container, six narrow dark tires. Unarmed industrial military convoy transport. Strong readable 24x40 logical sprite silhouette, symmetry, upper-left lighting, subtle caution-yellow metal details. Complete centered outline with small transparent margin. Actual transparent background. No shadow, terrain, text, logos, people, turret, perspective or sprite sheet. One isolated vehicle in restrained 1990s military pixel-art HD-remaster style.

The first cargo generation attempt failed with a connection error and produced
no usable output. The prompt above is the successful retry. Sources are
AI-generated game artwork; shared mod artwork and the classic original catalog
retain their own provenance. Sound cues are fresh deterministic PCM16 mono WAVs
at 22,050 Hz made with sine harmonics, seeded noise and short envelopes.
