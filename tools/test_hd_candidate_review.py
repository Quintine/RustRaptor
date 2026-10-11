"""Regression for Cargo dependency directories containing two serde universes."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from hd_candidate_review import freeze_library, select_compatible_serde_json


@unittest.skipUnless(shutil.which("rustc"), "rustc is required for dependency compatibility proof")
class SerdeDependencySelectionTest(unittest.TestCase):
    def test_selects_trait_compatible_dependency_even_when_wrong_build_is_newer(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            deps = project / "target/release/deps"
            deps.mkdir(parents=True)

            def compile_crate(name, tag, source, dependency=None):
                path = project / f"{name}-{tag}.rs"
                path.write_text(source)
                library = deps / f"lib{name}-{tag}.rlib"
                command = ["rustc", "--edition=2021", "--crate-type=rlib",
                           "--crate-name", name, "-C", f"metadata={tag}",
                           str(path), "-o", str(library)]
                if dependency:
                    command.extend(["--extern", f"serde_core={dependency}"])
                subprocess.run(command, check=True, capture_output=True)
                return library

            traits = "pub trait Deserialize {}\npub trait Serialize {}\n"
            first = compile_crate("serde_core", "first", traits)
            second = compile_crate("serde_core", "second", traits)
            game = compile_crate("raptor_replica", "fixture", """pub mod hd {
    pub struct Manifest;
    impl serde_core::Deserialize for Manifest {}
    impl serde_core::Serialize for Manifest {}
}
""", first)
            json_api = """pub fn from_slice<T: serde_core::Deserialize>(_: &[u8]) -> Result<T, ()> {
    unimplemented!()
}
pub fn to_vec<T: serde_core::Serialize>(_: &T) -> Result<Vec<u8>, ()> {
    unimplemented!()
}
"""
            compatible = compile_crate("serde_json", "1-compatible", json_api, first)
            wrong = compile_crate("serde_json", "0-incompatible", json_api, second)
            self.assertGreater(wrong.stat().st_mtime_ns, compatible.stat().st_mtime_ns)
            frozen_game, _, _ = freeze_library(project, game)
            selected, report = select_compatible_serde_json(
                project, frozen_game, deps, project / "review")
            self.assertEqual(selected.read_bytes(), compatible.read_bytes())
            self.assertEqual([attempt["compatible"] for attempt in report["attempts"]], [False, True])
            self.assertIn("Deserialize", report["attempts"][0]["compiler_stderr"])
            self.assertIn("Serialize", report["attempts"][0]["compiler_stderr"])
            self.assertTrue((project / "review/dependency-selection.json").is_file())

            with self.assertRaisesRegex(ValueError, "no compiler-compatible serde_json"):
                select_compatible_serde_json(project, frozen_game, deps,
                                             project / "rejected", [wrong])


if __name__ == "__main__":
    unittest.main()
