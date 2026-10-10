#!/bin/sh
# RustRaptor is the default; the original engine is an optional reference.
set -eu
cd "$(dirname "$0")"
ROOT="$PWD"
ENGINE=rust
if [ "${1:-}" = --engine ]; then
    [ "$#" -ge 2 ] || { echo 'Usage: ./play.sh --engine legacy|rust [arguments]' >&2; exit 2; }
    ENGINE="$2"
    shift 2
fi
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$HOME/.local/lib"
case "$ENGINE" in
    rust)
        exec cargo run --locked --release --manifest-path "$ROOT/RustRaptor/Cargo.toml" --bin raptor-rust -- "$@"
        ;;
    legacy)
        if [ ! -f data/INDEX ]; then
            echo 'Missing data/INDEX; see docs/asset-pipeline.md' >&2
            exit 1
        fi
        CMAKE=cmake
        if ! command -v cmake >/dev/null 2>&1; then
            CMAKE="$HOME/.local/opt/cmake/bin/cmake"
        fi
        if [ ! -x raptor/build/bin/raptor ]; then
            "$CMAKE" -S raptor -B raptor/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$HOME/.local${CMAKE_PREFIX_PATH:+;$CMAKE_PREFIX_PATH}"
        fi
        "$CMAKE" --build raptor/build --target raptor --parallel "$(nproc)"
        cd data
        exec "$ROOT/raptor/build/bin/raptor" "$@"
        ;;
    *) echo "Unknown engine: $ENGINE (choose legacy or rust)" >&2; exit 2 ;;
esac
