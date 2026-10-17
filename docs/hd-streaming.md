# Full-catalog HD loading and caches

The runtime can register the complete original picture catalog without retaining every decoded replacement in RAM. Registration accepts up to 8 MiB of JSON metadata, 8,192 sequences and 16,384 distinct asset IDs. Each sequence still has at most 512 declared frames. These are validation ceilings, not coverage claims.

`HdAssets::load_lazy(root, catalog, cache_dir)` checks all sequence IDs before committing the manifest. Duplicate IDs, arithmetic overflow, unsupported formats and invalid sequence lengths reject the pack atomically. Each supplied frame must match the checked original payload SHA-256, logical canvas and `[0,0]` anchor. Its PNG path must resolve inside the pack, including symlinks. Missing files and individual source mismatches produce diagnostics and native-art fallback.

Registration does not imply a PNG has been decoded. `registered_count()` reports source-checked candidates that have not been rejected; `validated_count()` and the compatibility alias `coverage()` report frames whose artwork has passed validation. First use checks PNG format, crop bounds, matching aspect ratio, at least 2× logical resolution, visible pixels and source-aware transparency. Transparent originals require transparent negative space; opaque originals accept opaque art. A failed frame returns `Ok(None)` from `sprite`, records one diagnostic and keeps native fallback until the pack is reloaded.

A complete PNG for either an opaque or transparent original may use dimensions produced by rounding one common scale by less than half a pixel on each axis. The strict rule is `2 * abs(width * logical_height - height * logical_width) < logical_width + logical_height`; logical dimensions still equal the original, and both axes must supply at least 2× resolution. For example, 1,586×992 fits a 320×200 background, and 1,402×1,122 fits a transparent 40×32 sprite. Selection must cover the whole PNG, with no crop or an explicit full-canvas crop; inexact partial crops, conflicting half-way ties and arbitrary aspect changes remain rejected. Rounded opaque originals still require every raw PNG alpha value to be 255 before downsampling. Transparent originals retain zero-alpha negative space and at least one visible pixel with alpha ≥128, checked on both raw and resident RGBA and again on disk-cache reads. Exact-frame and rounded-opaque cache keys stay unchanged; newly eligible transparent rounded frames use a separate namespace. This dimension rule adds no per-asset policy and does not approve source contours or reconstruct missing artwork.

## Optional frame presentation policies

All policies below default to disabled. They require explicit frame metadata and source/art review; loader validation alone does not approve a remaster.

- `atlas_grid: {"columns": 4, "rows": 2, "column": 0, "row": 0}` selects one equal cell of an unchanged atlas. It is mutually exclusive with `crop`. The complete atlas must have the exact aspect ratio implied by the grid and original logical canvas, with at least 2× detail per cell. Fractional boundaries use an isolated Lanczos3 filter without truncating edge strips. Pixels wholly outside the selected cell are excluded; boundary-straddling pixels contribute only their overlapping area. Grid selections have separate cache identities; frames without this option retain their existing sampling and cache keys.
- `preserve_reserved_coverage: true` retains an original gameplay palette label 250–255 at a feathered edge only when its resident logical cell has mean alpha of at least 128 and at least half its area has alpha of 128 or greater. Missing or sparse artwork stays transparent. Ordinary colors, water/fire classes and static-card rendering keep their existing behavior.
- `native_nearest_cues: [[x, y], ...]` samples the unchanged resident RGBA at the nearest pixel for up to 64 explicitly listed original cells, only at gameplay scale 1. Coordinates must be sorted lexicographically, unique, within an opaque original canvas, and refer to ordinary source indices below 240. This can preserve a small raw-supported warning color that averaging dulls. It does not recolor artwork or reconstruct absent details; other cells, higher scales and static-card rendering keep their existing sampler.

- `original_detail_cells: [[x, y], ...]` retains explicitly listed **Original** logical details at gameplay scales 1–4. Legacy lists of up to 64 cells keep their existing behavior. Lists of 65–128 cells additionally require `4 * retained_cell_count <= painted_Source_cell_count`, counted from the decoded authentic Original payload (indices 0–255, excluding transparency), never canvas area or generated PNG alpha. All cells must remain sorted, unique, in bounds, painted and disjoint from `native_nearest_cues`; transparent Source cells are rejected. The runtime copies the exact Original ScaleNx footprint into the generated replacement only in SourceClasses/gameplay mode. Terrain conditions retained samples with the authentic joined Original control before blending neighbors, then restores their exact footprints after all joins. This can also change neighboring pixels within the existing join bands; unrelated pixels and fallback behavior remain unchanged. Static cards continue to sample the PNG. Raw PNG bytes, alpha, framing and loader eligibility do not change.

Retained pixels are Original details, not generated HD. Original palette cycling, water/fire and blinking labels remain live Source indices; ScaleNx may also contain transparent subpixels shaped by Original neighbors. Coarse detail or palette effects can form visible seams and require explicit independent all-scale and genuine-context hybrid review. The ordinary-only predecessor is not a current hybrid approval. Registration accepts the existing `retained-original-details-v2-painted0255` declaration only for legacy lists of up to 64, or `retained-original-details-v3-max128-quarter-painted0255` with exact selected cells. Longer lists always require v3 and actual catalog Source validation by the registrar. Metadata-only candidate preparation cannot prove the density bound. Lists up to 64 preserve existing per-frame, indexed and rejected-fallback cache identities; longer lists use new indexed and rejected-fallback namespaces. Protected terrain joins follow the conditioning rule above for either list size. The combined 32 MiB Source-reference budget is unchanged. Retained cells never count as generated detail, and the area rule does not prove novelty in the unretained cells. A whole-Source fallback cannot gain artistic HD approval through this option; legacy acceptance is preserved without relabeling its pixels. Material, all-scale and genuine-context gates stay in force (the separately bounded unused-catalog scope still explicitly declares no genuine runtime context). Existing default artwork holds are preserved; this option does not rescue invalid framing, provider refusals or broad geometry/material failures.

Opt-in metadata participates in both derived and indexed cache identities. Frames without these policies retain their previous cache keys and pixels. Retained-detail opt-ins have a distinct versioned frame, rejected-fallback and prepared-terrain key; absent/empty selections keep the previous identities. The candidate and original-art audit tools validate the same metadata restrictions as the Rust loader.

`HdAssets::load` performs full eager validation using the same bounded caches. `validate_all()` can also validate a lazily registered pack; its report distinguishes registered, validated and rejected frames. Full validation can therefore be used in a CLI or audit without raising runtime memory limits. It validates supplied artwork and does not infer coverage for absent originals.

## Memory bounds

Each PNG is limited to 32 MiB on disk, 4,096 pixels per dimension, 4,194,304 total pixels and a 64 MiB decoder allocation limit. Reads are bounded even if a file grows after metadata inspection. A loaded frame retains at most its logical canvas at 4× resolution. Larger generated originals remain unchanged on disk.

Three least-recently-used caches each have a 32 MiB ceiling:

- Decoded atlas images, keyed by the exact source PNG SHA-256.
- Cropped, resampled RGBA frames, keyed by PNG identity, original payload SHA-256, crop, canvas, anchor, alpha requirement and kernel version.
- Indexed sprites, keyed by the derived frame identity, presentation scale, complete palette identity and palette policy.

Resident cached pixels total at most 96 MiB, irrespective of catalog coverage. Decoder input, resampling work buffers and returned owned sprites are additional bounded working allocations; callers should retain only currently needed sprites. Eviction removes cached pixels, not frame registrations or validated coverage. Adjacent crops reuse the decoded atlas; an atlas is not cloned in full merely to extract a small crop. Repeated draws copy only the final indexed canvas. Palette changes cannot reuse stale indexed colors.

Source palette labels and full Original references for opted-in retained details share one checked 32 MiB ceiling. Frames using only ordinary colors need no label map. A nonempty retained-detail selection keeps one bounded full Original indexed reference; absent/empty selections keep none. Frames containing animated labels retain one byte per original logical pixel; transparent and ordinary source locations use the ordinary class. Quantization restricts ordinary HD pixels to indices 0–239, water to 240–244 and fire to 245–249. Original glow/flash labels 250–255 remain exact. Newly visible HD pixels outside the original silhouette use ordinary colors. This prevents a bright static highlight from acquiring fire, water or blinking behavior. Cache color keys include the source class; equal RGB values in different classes cannot share an incorrect palette result.

Standalone opening cards use `sprite_static_palette` with all 256 entries of their own unfaded palette. Its indexed cache policy is distinct from gameplay source classes; both share the same checked PNG and RGBA caches. Cinematic fades apply during presentation. See [hd-opening-cards.md](hd-opening-cards.md) for the route and fallback checks.

## Derived disk cache

The optional cache belongs under the separate Rust profile cache, for example `RaptorReplica/cache/hd-art-v1`. It stores original-independent derived RGBA files; originals and raw generations are never overwritten. Each filename binds the source PNG hash, exact original payload hash, crop, logical dimensions, anchor, alpha policy and resampling kernel. Palette-dependent indexed sprites remain in memory only.

A derived file has a versioned header, exact frame identity, dimensions and payload SHA-256. Reads recheck dimensions, byte count, alpha policy and checksum. A corrupted or escaping symlink cache entry is discarded and rebuilt from the checked PNG. Artwork continues to work if the cache is unwritable. Files are written to a new temporary file and atomically renamed; interruption may lose a cache entry, which is safe to regenerate.

The disk cache is capped at 512 MiB. Older generated `.rgba` files are evicted when space is needed; unrelated files and original art are untouched. Delete this cache to reclaim space at any time. A changed PNG, original source payload, crop or kernel produces a different cache identity.

## Validation

`raptor-rust --data /absolute/path/to/data --validate-hd` fully validates the supplied pack and exits unsuccessfully if any supplied artwork fails. Its totals describe supplied frames; the full-catalog completion ledger separately records originals that are still missing replacements.

Portable synthetic tests exercise a 5,753-frame manifest, full validation, adjacent atlas crops, memory eviction, palette changes and source animation classes at every scale, 4× residency, malformed PNGs, original hash mismatches, corrupted caches, disk eviction and escaping artwork/cache symlinks.

Run the local original-data integration check with:

```sh
RAPTOR_TEST_DATA=/absolute/path/to/data \
  cargo test --locked --lib hd::tests::original_hd_pack_validates_with_bounded_residency \
  -- --ignored --nocapture
```

That check validates every supplied frame and renders it through `HdAssets::sprite` at scales 1–4 with the original palette. It checks dimensions, visible output and each cache ceiling. Visual review, animation alignment and terrain seams remain separate acceptance checks.

## Earlier retained detail validation — 17 October 2026

The optional detail policy passed 70 unique Rust regressions in the private source
validation and 31 Python checks against the applied shared files. Both included
Linux and Windows executables were rebuilt. All 5,339 HD frames supplied at that checkpoint load with
zero rejects. Actual 1080p software-SDL menu, Sector 1 Wave 7 and Sector 3 Wave 9
captures match their pre-change images byte for byte (6,220,800 pixels compared).
These default-mode checks do not approve a new hybrid asset. Explicit retained
Original selectors still require their own whole-frame and scene review.

## Atlas and terrain-join update — 17 October 2026

The rational atlas sampler, protected join inputs and bounded 65–128-cell
retention policy pass 90 Rust tests and 78 Python tests; five existing Rust
integration checks remain ignored. Both bundled executables were rebuilt.
The installed Linux build validates all 5,384 supplied frames with zero rejects,
all 45 mods with one explicit override, and the 6,449-entry original catalog.
Fresh 1080p menu, Sector 1 Wave 7 and Sector 3 Wave 9 software-SDL captures
match the previous build exactly across 6,220,800 presented pixels. These are
bounded regression controls, not evidence for unreviewed artwork or every
possible terrain placement.
