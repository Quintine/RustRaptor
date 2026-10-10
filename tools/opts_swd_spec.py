"""Spec for the re-authored data/ui/OPTS_SWD (catalog handle 0x1003f).

Same window/dialog as the original, grown from 13 to 23 fields: the original
Music/FX/Detail rows plus FILTER, SCANLINES, RESOLUTION, FULLSCREEN and
ASPECT rows and their selection icons. Window-relative coordinates assume
the window at x=60, y=6, 200x188 (320x200 screen space).

Layout (window-relative):
  y=8     OPTIONS title            (field 8)
  y=20    panel bumpin behind rows (field 2, 5,20 190x100)
  y=24    DETAIL    row + PIC1     (fields 6, 3)
  y=40    FILTER    row + PIC4     (13, 18)
  y=56    SCANLINES row + PIC5     (14, 19)
  y=72    RES       row + PIC6     (15, 20)
  y=88    FULLSCR   row + PIC7     (16, 21)
  y=104   ASPECT    row + PIC8     (17, 22)
  y=122   MUSIC VOLUME label       (9)
  y=131   music slider view/track  (11, 0)
  y=146   SOUND FX VOLUME label    (10)
  y=160   fx slider view/track     (12, 1)
  y=174   EXIT button              (7)

Build: python3 tools/swdbuild.py build tools/opts_swd_spec.py data/ui/OPTS_SWD
(the printed size must be written into data/INDEX's `1003f` line)
"""

from swdbuild import (BUMPIN_TEMPLATE, ICON_TEMPLATE, BUTTON_TEMPLATE,
                      TEXT_TEMPLATE, VIEWAREA_TEMPLATE)

SWIN = {
    "version": 1, "swdsize": 0, "arrowflag": 0, "display": 0,
    "opt3": 0, "opt4": 0, "id": 2, "type": 0,
    "name": "OPTS", "item_name": "TEXTURE_PIC",
    "item": 65559, "picflag": 1, "lock": 1, "fldofs": 120, "txtofs": 0,
    "firstfld": 0, "opt": 1, "color": 1, "numflds": 23,
    "x": 60, "y": 6, "lx": 200, "ly": 188, "shadow": 1,
    # swdsize/txtofs are recomputed by the builder (file size / blob offset).
}

# All rows share the button look; value texts are overwritten at runtime via
# SWD_SetFieldText, so the stored strings are just the initial/label values.
_ROW = {**BUTTON_TEMPLATE, "x": 30, "lx": 140, "maxchars": 22}
_ICON = {**ICON_TEMPLATE, "x": 12, "y": 24}
_LABEL = {**TEXT_TEMPLATE, "x": 30}

FIELDS = [
    # 0-2: bumpins (slider tracks + row panel), repositioned originals
    {**BUMPIN_TEMPLATE, "x": 30, "y": 136, "lx": 127, "ly": 3},
    {**BUMPIN_TEMPLATE, "x": 30, "y": 165, "lx": 127, "ly": 3},
    {**BUMPIN_TEMPLATE, "x": 5, "y": 20, "lx": 190, "ly": 100},

    # 3-5: selection icons for detail / music / fx rows
    {**_ICON, "name": "PIC1", "y": 24},
    {**_ICON, "name": "PIC2", "y": 122},
    {**_ICON, "name": "PIC3", "y": 146},

    # 6-7: buttons
    {**_ROW, "name": "DETAIL", "hotkey": 0x20, "y": 24, "text_index": 2},
    {**_ROW, "name": "EXIT", "id": 4, "hotkey": 0, "x": 118, "y": 174,
     "lx": 57, "maxchars": 5, "text_index": 3},

    # 8-10: texts
    {**TEXT_TEMPLATE, "id": 200, "input_opt": 1, "item_name": "",
     "font_name": "FONT1_FNT", "fontid": 0x10003, "x": 68, "y": 8,
     "lx": 71, "ly": 14, "maxchars": 8, "text_index": 4},
    {**_LABEL, "id": 150, "y": 122, "lx": 104, "maxchars": 13,
     "text_index": 5},
    {**_LABEL, "id": 160, "input_opt": 1, "y": 146, "lx": 112,
     "maxchars": 16, "text_index": 6},

    # 11-12: volume slider view areas
    {**VIEWAREA_TEMPLATE, "name": "VMUSIC", "x": 30, "y": 131},
    {**VIEWAREA_TEMPLATE, "name": "VFX", "x": 30, "y": 160},

    # 13-17: video option rows (hotkeys: F, L, R, -, A)
    {**_ROW, "name": "FILTER", "hotkey": 0x21, "y": 40, "text_index": 7},
    {**_ROW, "name": "SCANLINES", "hotkey": 0x26, "y": 56, "text_index": 8},
    {**_ROW, "name": "RES", "hotkey": 0x13, "y": 72, "text_index": 9},
    {**_ROW, "name": "FULLSCR", "hotkey": 0, "y": 88, "text_index": 10},
    {**_ROW, "name": "ASPECT", "hotkey": 0x1E, "y": 104, "text_index": 11},

    # 18-22: selection icons for the five video rows
    {**_ICON, "name": "PIC4", "y": 40},
    {**_ICON, "name": "PIC5", "y": 56},
    {**_ICON, "name": "PIC6", "y": 72},
    {**_ICON, "name": "PIC7", "y": 88},
    {**_ICON, "name": "PIC8", "y": 104},
]

# 0-1 ("Y","N") are the original bumpin marks; nothing references them at
# runtime but they are kept for parity with the extracted asset.
TEXTS = [
    "Y", "N",
    "DETAIL HIGH ",          # 2: overwritten at open by WIN_Opts
    "EXIT",                  # 3
    "OPTIONS",               # 4
    "MUSIC VOLUME",          # 5
    "SOUND FX VOLUME",       # 6
    "FILTER SCALE 3X",       # 7: overwritten at open
    "SCANLINES OFF",         # 8: overwritten at open
    "RESOLUTION 960X720",    # 9: overwritten at open
    "FULLSCREEN OFF",        # 10: overwritten at open
    "ASPECT 4:3 ON",         # 11: overwritten at open
]
