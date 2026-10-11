#!/usr/bin/env python3
"""Run Stormwall acceptance against the project's latest compiled Rust library.

Build RustRaptor first. This small rustc harness reuses its dependencies and
keeps generated binaries in the ignored root .reference directory.
"""
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
project = root.parents[2]
deps = project / "RustRaptor/target/release/deps"
libraries = sorted(deps.glob("libraptor_replica-*.rlib"),key=lambda p:p.stat().st_mtime,reverse=True)
if not libraries:
    raise SystemExit("Build RustRaptor in release mode before running this harness")
output = project / ".reference/iron-coast-stormwall-validation"
output.parent.mkdir(exist_ok=True)
env = os.environ.copy()
env["RAPTOR_PROJECT"] = str(project)
local_lib = Path.home()/".local/lib"
env["LD_LIBRARY_PATH"] = f"{local_lib}:{env.get('LD_LIBRARY_PATH','')}"
env["LIBRARY_PATH"] = f"{local_lib}:{env.get('LIBRARY_PATH','')}"
subprocess.run(["rustc","--edition=2024","--test",str(root/"validate.rs"),
                "--extern",f"raptor_replica={libraries[0]}","-L",f"dependency={deps}",
                "-L",str(local_lib),"-o",str(output)],check=True,env=env)
subprocess.run([str(output),"--nocapture","--test-threads=1"],check=True,env=env)
