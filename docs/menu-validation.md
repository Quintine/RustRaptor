# Menu and classic-intro screenshot review

The full local-original-data audit captures 31 menu states and 11 frames of the original logos/intro. All 42 captures were inspected, including main menu, hangar, registration, shop purchase/sale details, equipment, missions, options, pilot slots, empty legacy archive, mod dependencies and disable confirmation, mismatched-save loading, pause and results.

The authored coastal-hangar background is packaged at `art/menu-background-v1.png`. Menus use a 400×225 logical canvas at 16:9. Main-menu navigation occupies the open right side, with a compact pilot card above the visible ship; off-white labels and amber focus match the hangar lighting. Secondary screens retain their detailed classic layout centered within the wider background. Bitmap labels remain sharp and long text stays within panels. The mission preview is outside the actionable list hitboxes. Shop cards display artwork, prices, resale value, quantity and automatic/selectable/passive behavior.

Gameplay uses the original 320×200 simulation canvas, presented at 4:3 with aspect correction enabled. At 1080p its viewport is 1440×1080, centered between subdued hangar sidebars. Original cinematics always use 4:3 with black borders, including when gameplay aspect correction is disabled. New profiles default to 1280×720; existing saved window sizes remain respected.

The widescreen mouse check covers all eight main actions at 1280×720, 1280×800 and 1920×1080, secondary-screen offsets and clicks outside the viewport. The full 42-frame menu/intro audit was rerun after the layout change. A relocated packaged SDL executable also rendered menu and gameplay captures at 1280×800 and 1920×1080, with nonzero stereo audio captures. Those screenshots are under ignored `.reference/standalone-package/`.

Installed mod rows stay in stable ID order through activation, dependency
selection, disabling and priority changes. Requested load priority remains
separate and is visible in diagnostics; arrow-key changes report the new
priority without moving the cursor. Returning from details or a disable
confirmation restores the selected mod and its list position. Opening details
again while already in diagnostics preserves its parent, so Escape always
returns one level. Portable regressions exercise these navigation sequences.
The 42-capture audit was rerun after the navigation fixes on 11 October and
all four current contact sheets were visually reviewed; panels, focus,
confirmation text and shop information remain readable and correctly placed.

The audit also verifies the complete startup reaches its return screen at exactly 1,891 70 Hz service ticks and restores menu music. Cancelling a mod-mismatch prompt preserves the original save; accepting it displays unavailable equipment without silently discarding it.

Run the local audit from `RustRaptor/`:

```sh
RAPTOR_TEST_DATA="$PWD/../data" LD_LIBRARY_PATH="$HOME/.local/lib" \
  cargo test --locked --lib every_menu_screen_and_original_intro_visual_audit -- --ignored
```

Captures and the action-row manifest remain local in `../.reference/ui-all/`,
outside the current Git root. The background was generated with the imagegen
skill's built-in image generation tool; its prompt and provenance are tracked
in `art/menu-background-v1.prompt.txt` and `art/provenance.json`. The packaged
original cinematics are now included in tracked `data/`.
