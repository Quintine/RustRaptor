#!/bin/sh
set -eu
cd "$(dirname "$0")"
export LD_LIBRARY_PATH="$PWD/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if [ -x "$PWD/bin/raptor-rust" ]; then
    exec "$PWD/bin/raptor-rust" "$@"
fi
export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$HOME/.local/lib"
exec cargo run --locked --release --manifest-path "$PWD/Cargo.toml" --bin raptor-rust -- "$@"
