# Mission briefing illustration convention

Reference: `/home/quintine/Projects/RaptorReplica/RustRaptor/mods/iron_coast_mission_4/art/briefing_hd.png` (1280×800). Read and visually inspect this actual reference before generating. Also inspect the relevant actual Original terrain contact sheet below. Artwork must be a cinematic, oblique landscape illustration, not a tile collage or a gameplay screenshot.

Ship each mission separately in a PRIVATE output tree `data/briefings/sector_<sector>_wave_<wave>_hd.png` and matching `_sd.png`. IDs remain `base:sector_<sector>_wave_<wave>`; no IDs, mission names, gameplay or canonical files are edited by artists. Final HD runtime image: **1280×800**, 16:10, RGBA or RGB. Generate genuinely new HD illustration through the built-in imagegen tool, using the Stormwall artwork as style reference and original terrain themes as semantic reference. If the provider returns another aspect/canvas, preserve that untouched original master and derive1280×800 using an explicit crop/resample recipe. SD320×200 is a reproducible downsample of the same complete approved HD composition; no independent generated variation. Maintain SD/HD composition and aspect.

Stormwall style: restrained hand-painted 1990s shooter box-art realism, crisp readable aircraft silhouette and mechanical panels, atmospheric perspective and cinematic light. A compact steel-gray twin-engine Raptor-like strike fighter in the foreground, banking toward the upper right; destination/mission environment in the mid-ground and background. Navy and desaturated teal, steel gray, muted amber industrial lights are shared accents; environment colors must follow actual mission theme, not force oceans or storms into lunar/desert/industrial missions. Broad readable value masses survive small thumbnails; avoid tiny detail as the only mission distinction. Keep the center70–80% of the image's height meaningful for a132×70 aspect-correct centered crop in the menu. Aircraft and signature target must remain legible in that crop. No baked text, labels, HUD, borders, logos, watermarks or new factual mission objectives/enemy designs. Do not put green Earth terrain on airless lunar worlds or oceans in wholly industrial stages.

Each generation is one mission illustration, one tool call, with real PNG preserved, safe provider metadata and text prompt/provenance. No grids/atlases whose cells are counted as separate new mission artwork. Capture actual calls and limitations without embedding provider base64 or complete image URL strings in reports. Inspect final full HD and SD for aircraft geometry, unintended extra aircraft limbs/wings, composition and theme. Reject demonstrably broken art rather than silently smoothing or claiming approval. Existing HD-remaster policy refusals must not be retried or rerouted; these new mission illustrations are separate new authored assets and do not increase original sprite/terrain remaster coverage.

Original terrain contacts, produced from the actual original palette and map catalog, are READ-ONLY references, not runtime/new HD artwork:

- `/home/quintine/Projects/RaptorReplica/RustRaptor/.reference/mission-preview-unification-private-proposal-20261018-v1/original-sector-1-terrain-theme-contact.png`
- `/home/quintine/Projects/RaptorReplica/RustRaptor/.reference/mission-preview-unification-private-proposal-20261018-v1/original-sector-2-terrain-theme-contact.png`
- `/home/quintine/Projects/RaptorReplica/RustRaptor/.reference/mission-preview-unification-private-proposal-20261018-v1/original-sector-3-terrain-theme-contact.png`

Each row is Wave1–9. Left: six most frequent Original tile IDs. Right: genuine map windows at rows10,65,125. These finite samples establish broad scenery; they do not prove complete mission geography. Full Source-derived inventory is `original27-source-inventory.json` in this proposal directory (all layout, tile asset IDs and ordered spawns, no simulation runs).

| Stable mission ID | Actual theme visible in Original terrain samples; illustration direction |
|---|---|
| base:sector_1_wave_1 | Bravo: teal ocean, low reddish-brown rocky islands, sparse coastal installations; open-water approach. |
| base:sector_1_wave_2 | Bravo: teal island channels and reddish-brown headlands, coastal wharf and small industrial platforms. |
| base:sector_1_wave_3 | Bravo: brown rocky coastal landmass with narrow turquoise inlets, sparse scrub and light industrial roofs. |
| base:sector_1_wave_4 | Bravo: rugged brown shore, isolated blue lagoon, scattered coastal depot buildings. |
| base:sector_1_wave_5 | Bravo: brown scrubland and gray industrial compounds/roads, coastline at the edge; landward strike. |
| base:sector_1_wave_6 | Bravo: brown coastal industrial settlement, pale/angular warehouse roofs, narrow turquoise bay. |
| base:sector_1_wave_7 | Bravo: brown headland cut by winding blue channel, paved coastal airfield/apron and installations. |
| base:sector_1_wave_8 | Bravo: dense steel-gray industrial/port works on brown land, roadways and a small shoreline. |
| base:sector_1_wave_9 | Bravo: ocean approach to large gray fortified dock/harbor on brown island, concrete gantries and sea channels. |
| base:sector_2_wave_1 | Tango: gray-brown urban/industrial grid, orange-edged roads, canals/basins and warehouse blocks. |
| base:sector_2_wave_2 | Tango: olive-green agricultural/scrub plains, narrow turquoise river, brown roadways and coastal edge. |
| base:sector_2_wave_3 | Tango: dense deep-green forest/jungle, narrow blue river, gray clearings and concrete installations. |
| base:sector_2_wave_4 | Tango: dark gray city/industrial maze, charcoal roads/roofs and brown courtyards, blocky concrete facilities. |
| base:sector_2_wave_5 | Tango: mixed olive scrubland and gray road/industrial compounds, forest pockets and scattered buildings. |
| base:sector_2_wave_6 | Tango: broad gray paved military/industrial yards on brown earth, rows of installations and road junctions. |
| base:sector_2_wave_7 | Tango: gray-brown dense dockside city blocks, turquoise rectangular canal/basin, industrial roads and warehouses. |
| base:sector_2_wave_8 | Tango: almost-black night city/industrial complex with amber/yellow lighting and bright white circular lamps; use dark fighter. |
| base:sector_2_wave_9 | Tango: deep-green jungle/river complex with conspicuous blue-green gridded industrial/energy installations. |
| base:sector_3_wave_1 | Outer Regions: light-gray airless cratered moon, large white-gray facilities, circular green-lit reactor machinery. |
| base:sector_3_wave_2 | Outer Regions: vivid red/orange rocky or molten terrain, gray industrial facilities; hot volcanic world. |
| base:sector_3_wave_3 | Outer Regions: nearly-black cratered airless moon and dark gray fortified structures, green-lit installation accents; use dark fighter. |
| base:sector_3_wave_4 | Outer Regions: reddish-brown arid rocky plain, large pale/white angular industrial buildings and platforms. |
| base:sector_3_wave_5 | Outer Regions: light-gray cratered moon, large pale complex and circular vivid-green reactor/pod machinery. |
| base:sector_3_wave_6 | Outer Regions: ochre/sandy cratered desert plain with gray-tan industrial machinery and blocky fortified outposts. |
| base:sector_3_wave_7 | Outer Regions: intense red-orange volcanic canyon/flow terrain around massive gray industrial structures and causeways. |
| base:sector_3_wave_8 | Outer Regions: reddish-tan arid rock, orange molten channels, white-gray massive industrial buildings/gantries. |
| base:sector_3_wave_9 | Outer Regions: dense continuous steel-gray fortress/megastructure platforms, geometric industrial roof panels, stark red-lit end-stage machinery. |

No new mission titles or gameplay promises should be inferred from these artwork directions. Original menu names remain Sector#/Wave# until another explicitly authorized naming change.
