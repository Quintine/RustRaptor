#!/usr/bin/env bash
set -euo pipefail
task_mod_root=$(cd "$(dirname "$0")" && pwd)
task_engine_root=$(cd "$task_mod_root/../.." && pwd)
task_repo_root=$(cd "$task_engine_root/.." && pwd)
task_output_root="$task_repo_root/.reference"
mkdir -p "$task_output_root"
cargo build --locked --manifest-path "$task_engine_root/Cargo.toml" --no-default-features --lib
task_library=$(python3 - "$task_engine_root/target/debug/deps" <<'PY'
import sys
from pathlib import Path
print(max(Path(sys.argv[1]).glob('libraptor_replica-*.rlib'), key=lambda p: p.stat().st_mtime))
PY
)
rustc --edition=2024 "$task_mod_root/validate.rs" \
  --extern "raptor_replica=$task_library" \
  -L "dependency=$task_engine_root/target/debug/deps" \
  -L "native=$HOME/.local/lib" \
  -o "$task_output_root/iron-coast-mission-3-validate"
LD_LIBRARY_PATH="$HOME/.local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  "$task_output_root/iron-coast-mission-3-validate" "$task_repo_root"
