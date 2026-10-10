# Menu and classic-intro screenshot review

The full local-original-data audit captures 31 menu states and 11 frames of the original logos/intro. All 42 captures were inspected, including main menu, hangar, registration, shop purchase/sale details, equipment, missions, options, pilot slots, empty legacy archive, mod dependencies and disable confirmation, mismatched-save loading, pause and results.

The authored coastal-hangar background is packaged at `art/menu-background-v1.png`. Original bitmap labels remain sharp, panels preserve readable contrast, focus and feedback colors are consistent, and long text stays within panels. Main-menu and hangar actions stay visible together. The mission preview is outside the actionable list hitboxes. Shop cards display artwork, prices, resale value, quantity and automatic/selectable/passive behavior.

The audit also verifies the complete startup reaches its return screen at exactly 1,891 70 Hz service ticks and restores menu music. Cancelling a mod-mismatch prompt preserves the original save; accepting it displays unavailable equipment without silently discarding it.

Run the local audit from `RustRaptor/`:

```sh
RAPTOR_TEST_DATA="$PWD/../data" LD_LIBRARY_PATH="$HOME/.local/lib" \
  cargo test --locked --lib every_menu_screen_and_original_intro_visual_audit -- --ignored
```

Captures and the action-row manifest stay ignored in `../.reference/ui-all/`. The background was generated with the imagegen skill's built-in image generation tool; the exact prompt and provenance are tracked in `art/menu-background-v1.prompt.txt` and `art/provenance.json`. Original cinematic pixels remain outside Git.
