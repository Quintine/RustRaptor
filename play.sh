#!/bin/sh
# Launch Raptor: Call of the Shadows (original engine + extracted data).
#
# Layout:
#   data/                asset tree the engine loads: INDEX catalog plus
#                        music/, sprites/, ... (see docs/asset-pipeline.md)
#   raptor/build/bin/    built engine
#
# The engine resolves the catalog and assets relative to its working
# directory, so we run it from data/. Saves and SETUP.INI go to
# ~/.local/share/Raptor (SDL pref path) — nothing is written into the repo.
set -e
cd "$(dirname "$0")"
ROOT="$PWD"

if [ ! -f data/INDEX ]; then
    echo "Missing data/INDEX — restore the data/ asset tree" >&2
    echo "  (see docs/asset-pipeline.md and tools/glbextract.py)" >&2
    exit 1
fi

BIN=raptor/build/bin/raptor
if [ ! -x "$BIN" ]; then
    echo "Building raptor (first run)..." >&2
    cmake -E make_directory raptor/build
    ( cd raptor/build && cmake .. -DCMAKE_BUILD_TYPE=Release ${CMAKE_PREFIX_PATH:+-DCMAKE_PREFIX_PATH=$CMAKE_PREFIX_PATH} && make -j"$(nproc)" )
fi

export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$HOME/.local/lib"
cd data
exec "$ROOT/$BIN"
