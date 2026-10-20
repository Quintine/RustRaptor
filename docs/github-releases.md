# Downloadable releases

Current release: [0.1.0 Preview — Linux and Windows](https://github.com/Quintine/RustRaptor/releases/tag/v0.1.0-preview.20261020).

The GitHub release provides playable Linux x86_64 and Windows x86_64 packages.
Cargo, Python, the old engine and a Git checkout are unnecessary for play.

The approved HD artwork makes the shared data larger than GitHub's
[2 GiB limit per release asset](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
Each platform ZIP therefore contains the executable, platform libraries, all
45 mods with SD/HD artwork and audio, and the source/docs. Shared data ZIPs
contain the complete unchanged original catalog, approved HD pack, briefings
and the runtime manifest's other data files. Extracting them together produces
one self-contained `RustRaptor` folder. A single ZIP is only part of the download.

## Install

Download `Install-Windows.ps1` or `Install-Linux.sh` from the release. Review it,
then run it in a directory without an existing `RustRaptor` folder. It downloads
your platform ZIP and every shared data ZIP, checks each archive and every extracted payload against the versioned
`release-manifest.json` (and publishes `SHA256SUMS` for manual verification),
and extracts them into the same destination. Downloads are processed one at a
time. Linux needs Bash and Python 3.8 or later for this optional installer; Windows uses
built-in Windows PowerShell 5.1 and .NET. The Windows helper uses explicit extended
paths to retain long accepted proof filenames without an admin policy change.
A failed install preserves its partial folder for inspection; move or remove that
folder before retrying. All archives reject unexpected paths, links and file collisions.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Windows.ps1
```

```sh
bash ./Install-Linux.sh
```

For manual installation:

1. Download **one** platform ZIP: `RustRaptor-windows-x86_64.zip` or
   `RustRaptor-linux-x86_64.zip`.
2. Download **every** `RustRaptor-data-NN-of-TT.zip` and `SHA256SUMS` from
   the **same release**. Do not mix snapshots.
3. Verify the downloaded hashes. On Windows use `Get-FileHash -Algorithm SHA256`;
   on Linux use `sha256sum`. Compare them with `SHA256SUMS`.
4. Extract every downloaded ZIP into the **same parent directory**. Every ZIP
   starts with `RustRaptor/`; do not make a different subfolder for each ZIP.
5. Start `RustRaptor/run.cmd` on Windows or `RustRaptor/run.sh` on Linux.

Keep enough storage for the installed folder plus one data ZIP during install.
The release notes state the exact installed/download sizes. Your pilots and
settings stay in the separate `RaptorReplica` user profile directories.

## Maintainer export

Export only a clean, fully committed final tested commit with current Linux and Windows manifests.
The exporter does not build, refresh the runtime, change manifests or upload.

```sh
python3 tools/export_release.py plan --package . \
  --expected-commit FULL_TESTED_COMMIT --output /tmp/release-plan.json
python3 tools/export_release.py archive --plan /tmp/release-plan.json \
  --asset RustRaptor-data-01-of-07.zip \
  --output /tmp/RustRaptor-data-01-of-07.zip \
  --receipt /path/to/receipts/RustRaptor-data-01-of-07.zip.json
```

Use the actual volume count in the plan. Each asset is under 1.5 GB before ZIP
overhead, is checked against every planned source SHA-256 while writing, and
passes whole-archive CRC validation before a receipt is produced. The exporter
retains Linux execute permissions. The exporter inventories selected source files without following symlinks and
rejects non-regular members. It preserves every physical runtime-data file,
including directories named `derived`; proof/lineage files already present in
the runtime manifest remain included.

Create a draft release at the exact tested tag. Write, verify and upload one
archive at a time, record its remote size/digest, then remove only that disposable
export copy before producing the next. Keep receipts. After all assets exist:

```sh
python3 tools/export_release.py checksums --plan /tmp/release-plan.json \
  --receipts /path/to/receipts --output /tmp/SHA256SUMS \
  --manifest-output /tmp/release-manifest.json --tag v0.1.0-preview.20261020
```

Upload the versioned release manifest, checksum list and installers, check complete remote membership, and
publish the draft only after all checks pass. Native Windows CI and local
representative rendering/audio evidence retain their actual commit and scope;
archive integrity checks do not imply a fresh full playthrough.

## Hosted export for this preview

The manually dispatched **Upload frozen preview to existing draft** workflow
packages the immutable `7ecaa42b29ff0db5d2f7cdfe6da0a3221dfea555` game
checkpoint on a GitHub runner. Its publishing controller is checked out
separately from the later maintenance commit; the release tag stays fixed.
The controller requires the existing empty preview draft, verifies every local
and remote asset, and retains the frozen plan and receipts as an Actions
artifact. It leaves the draft unpublished for final review. It cannot be reused
for a different release without explicitly updating its fixed identity guards.
