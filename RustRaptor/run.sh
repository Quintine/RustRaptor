#!/bin/sh
set -eu
cd "$(dirname "$0")"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$HOME/.local/lib"
exec cargo run --locked --release --manifest-path "$PWD/Cargo.toml" --bin raptor-rust -- "$@"
