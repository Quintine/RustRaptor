# GLB archive format

The original game ships its data as `FILE0000.GLB` ... `FILE0006.GLB`,
produced by the "GLib" library bundled with the commercial source. The
format below was reverse-engineered from `raptor/src/glbapi.cpp` (upstream
loader) and verified against all seven shipped archives (6449 items total).

## Container

A GLB file is a flat sequence of 28-byte records:

```c
typedef struct {
    uint32_t opt;        // 0 = plain payload, 1 = encrypted payload
    uint32_t offset;     // payload offset in the file
    uint32_t filesize;   // payload size in bytes
    char     name[16];   // NUL-padded item name, e.g. "GENMIDI_OP2"
} KEYFILE;               // little-endian fields
```

- **Record 0 is the header.** Its `offset` field holds the *item count*;
  its other fields are unused.
- Records `1 .. count` are the item descriptor table, starting at byte 28.
- Item payloads live at each descriptor's `offset`, `filesize` bytes long.
- Names are unique per archive only in practice; duplicates (e.g. dozens of
  `CHASE_AGX`, thousands of empty `unnamed` labels) are common.
- Descriptor entries with `filesize == 0` are labels/placeholders.

## Cipher

Every record *and* every payload flagged `opt == 1` is scrambled with a
rolling additive cipher keyed on the ASCII string `32768GLB`, seeded at 25
(`SEED` in `glbapi.h`):

```
kidx = 25 % len(key)          # 25 % 8 = 1
prev = key[kidx]

# decrypt (GLB_DeCrypt):
for each byte b:
    out   = (b - key[kidx] - prev) mod 256
    prev  = b                  # chain uses the CIPHERTEXT byte
    kidx  = (kidx + 1) mod len(key)

# encrypt (GLB_EnCrypt) is the inverse:
    out   = (b + key[kidx] + prev) mod 256
    prev  = out                # chain uses the PLAINTEXT byte
```

Notes:

- The cipher state resets **per record** and **per payload**.
- The original C uses signed `char`; the stored byte equals the
  mathematical result mod 256 either way, so unsigned arithmetic is
  byte-exact.
- Payload encryption is independent of descriptor encryption: an archive
  typically mixes plain and encrypted items.

## Verification

`tools/glbextract.py` implements this format. Correctness was checked
against known payloads:

- `GENMIDI_OP2` starts with the DMX magic `#OPL_II#` (11908 bytes)
- `PALETTE_DAT` is exactly 768 bytes (256 x RGB)
- `DMXGUS_INI` decodes to readable INI text
- item counts per archive match the id ranges in `raptor/src/fileids.h`
  (e.g. slot 0: 230 items, last id `0x0e5`)
- every payload lies within its archive's bounds (extractor warns otherwise)

## See also

- [asset-pipeline.md](asset-pipeline.md) — how archives become `data/`
- `tools/glbextract.py` — reference implementation (Python, stdlib only)
