#!/usr/bin/env bash
set -euo pipefail
mission_root="$(cd "$(dirname "$0")" && pwd)"
engine_root="$(cd "$mission_root/../.." && pwd)"
export LD_LIBRARY_PATH="$HOME/.local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
cargo build --locked --no-default-features --lib --manifest-path "$engine_root/Cargo.toml"
rustc --edition=2024 "$mission_root/validate.rs" \
  --extern "raptor_replica=$engine_root/target/debug/libraptor_replica.rlib" \
  -L "dependency=$engine_root/target/debug/deps" \
  -o "$engine_root/target/cinder-docks-validation"
"$engine_root/target/cinder-docks-validation" "${1:-$engine_root/../data}" "$engine_root/mods"
