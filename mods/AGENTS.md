# Instructions for AI agents authoring mods

Read [the mod authoring checklist](../docs/mod-authoring-checklist.md) and
[the version 1 API](../docs/modding-api.md) before creating or changing a mod.
Follow the user's requested behavior and controls, and preserve other agents'
work in the shared checkout.

- Implement gameplay through content definitions, Rhai callbacks and documented
  commands. Keep a standalone mod independent unless its content needs a real
  dependency. Do not select legacy engine behavior for new content.
- If the API lacks a required capability, define the smallest general addition
  and coordinate engine work with the responsible agent when authorized. Keep
  content-specific targeting, damage and tuning in the mod.
- Ship actual SD and HD PNG assets for every artwork reference, plus required
  sounds/music. Keep dimensions, frame alignment and transparency consistent.
  Store generation prompts, provenance and reproduction recipes with the mod.
- Price equipment against original and shipped equipment, using controlled
  simulation observations as well as targeting, range, cooldown and loadout
  utility. Do not copy cheap placeholder prices from an example.
- Finish independent activation, gameplay and coexistence tests, real package
  validation where the original catalog is available, and a visual check of
  both SD and HD. Document any checks that cannot run.
- Document enabling, controls, prices and behavior limits. Deliver complete
  local packages without changing the user's pilot, selected mods or unrelated
  content unless requested.
