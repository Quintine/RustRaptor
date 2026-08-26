# Asset pipeline

`data/` is a plain directory tree the engine reads directly. It is derived
from the copyrighted original archives, so it is **gitignored** — restore it
with the extractor, never commit it.

## Layout

```
data/
├── INDEX        # catalog: "<hex asset id> <size> <relative path>", sorted by id
├── music/       # *_MUS            OPL2 register captures
├── sound/       # *_FX, *_SFX      Sound Blaster digital samples
├── sprites/     # *_PIC, *_AGX     pictures and animated sprites
├── tiles/       # *_BLK, *TILES    level tile graphics
├── maps/        # *_MAP            mission maps
├── fonts/       # *_FNT            bitmap fonts
├── text/        # *_TXT, *_DIZ, *_DIX, *_ERR, *_HELP
├── ui/          # *_SWD            menu/window layouts
├── movies/      # *_MDS            cinematic scripts
├── demos/       # *_REC            attract-mode recordings
└── misc/        # palettes, GENMIDI_OP2, DMXGUS_INI, item tables, labels
```

Categories are derived from the GLib item-name suffixes (see `classify()`
in `tools/glbextract.py`).

## INDEX catalog

One line per asset:

```
<hex id> <size in bytes> <category>/<filename>
10005 768 sprites/N0_PIC
```

- `id` is the engine handle: `(archive slot << 16) | item index`, matching
  the constants in `raptor/src/fileids.h`. Example: `10005` = slot 1,
  item 5 = `FILE105_N0_PIC`.
- Lines are sorted by id; the engine binary-searches them
  (`GLB_CatFind` in `raptor/src/glbapi.cpp`).
- `size` is trusted by the engine; the extractor guarantees it matches the
  file on disk.

## Regenerating data/

From a copy of the original game (the seven `FILE000N.GLB` archives):

```sh
tools/glbextract.py extract -o data FILE0000.GLB ... FILE0006.GLB
```

The extractor decrypts everything, classifies by name suffix, resolves name
collisions with numeric suffixes (`unnamed.3` -> `unnamed.3.1` when a second
archive contributes the same name to the same category — suffixes are global
per category so catalog sizes always match the file on disk), and writes the
catalog.

`tools/glbextract.py list FILE0000.GLB` dumps an archive's descriptor table
without writing anything.

## Editing content

Because the engine reads loose files through the catalog:

- **Replace an asset**: overwrite the file, keep the path. If the size
  changes, update the size in `INDEX` (the engine allocates and reads by
  that number).
- **Add a mission pack**: add files under a category, append catalog lines
  with unused ids in the desired slot (slots 2-4 are the packs; slot ids are
  `0x2xxxx`, `0x3xxxx`, `0x4xxxx`). Presence of slots 2/3 flips the engine
  into registered mode.
- **Rename**: never rename an existing catalog file without updating its
  `INDEX` line — the engine looks assets up by id, but item *names* (used by
  `GLB_GetItemID`) come from the path's basename.

## Engine-side contract

`raptor/src/glbapi.cpp` is the only code that touches `data/`:

- `GLB_LoadCatalog()` — parses `INDEX` (working directory first, then the
  directory the binary was launched from).
- `GLB_SlotItems(slot)` — counts a slot's assets (used for pack detection).
- `GLB_CatFind(id)` — binary search.
- `GLB_Load()` — `fopen` + `fread` of the cataloged file.

Payloads are stored pre-decrypted; the runtime never runs the GLB cipher.
