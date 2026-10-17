# Iron Coast Turret

API 1 package, version 1.0.1. Enable it in Mods at the main menu and apply the selection. This package has no mod dependencies.

Ground-fixed at the terrain scroll rate of 1 pixel/tick; no sideways drift or lifetime despawn. Missions can hold it with ordinary move/velocity commands.

The body remains 32×32, health 30, reward 120. SD and HD use the existing aligned PNGs. All PNG/WAV/master/prompt/provenance bytes are unchanged. Nonlegacy hostile projectile collision remains the engine's fixed `abs(dx)<10 && abs(dy)<10` point-to-player-center test, independent of artwork size. The following canvas change only changes visible sampling; it does not shrink that threshold. Projectile logical canvas is 6×6 in both modes; the complete existing square PNG canvas is sampled by the normal renderer, without crop or asset repaint. Its narrow visible core is checked in both modes.

All four difficulty profiles are authored in Rhai. Training/Rookie/Veteran/Elite (difficulty0/1/2/3) repeat periods are [112, 96, 82, 72] ticks, short-salvo counts [1, 1, 1, 2], windups [14, 13, 12, 11], projectile maximum-axis speeds [3, 3, 4, 4]; successive salvo shots are 7 ticks apart. These periods are script clocks, not the unused engine auto-fire cooldown. The enemy has no automatic weapon so it cannot fire a second implicit volley. Existing `:gun` definitions in Stage 2 remain compatibility content and do not drive this AI.

Aim is frozen at the start of a short salvo. Units only fire when their complete body is visible and still safely above the player. Salvos cancel as soon as that condition fails. Shot audio plays once per actual projectile; siege/skimmer warning audio plays once per salvo. Existing large explosion/flare effects are not used as muzzle blooms. Native death feedback remains engine-owned.

`event.difficulty` must be integer 0–3; absent or invalid data uses difficulty1 (Rookie). Optional `event.actor` uses the current central-dispatch enemy snapshot, or null for a retired actor. Older engines lacking both new fields use a compatibility lookup through `event.entities`. Current null actors have the integer difficulty field and skip immediately. No full-event native map methods or helper arguments are used in the current path. The dense-wave operation-budget acceptance requires the current actor API; a fallback trace does not prove that new API is installed.

Per-entity script state is bounded to 64 entries. Birth/death update the bounded lifecycle index; normal ticks never prune or scan the world when actor metadata is present. State, RNG and salvo timing are deterministic and save-continuable. Only actual engine death callbacks increment `iron_coast_turret:defeated` once. Air exits never award kill credit; required ground units never self-clear. The script never deals direct damage, grants equipment, spawns enemy reinforcements or completes a mission.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.
