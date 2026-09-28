import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@unittest.skipUnless((ROOT / "plugins/research-dojo").is_dir(), "Run installation tests from a built distribution")
class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_install_upgrade_remove_preserves_unrelated_entries(self):
        path = self.project / ".agents/plugins/marketplace.json"
        path.parent.mkdir(parents=True)
        existing = {"name": "my-team", "plugins": [{"name": "other", "source": "./other"}]}
        path.write_text(json.dumps(existing))
        result = installer.install(self.project, "both")
        self.assertEqual(result["marketplaces"]["codex"], "my-team")
        self.assertEqual(len(json.loads(path.read_text())["plugins"]), 2)
        installer.install(self.project, "both")
        self.assertEqual(len(json.loads(path.read_text())["plugins"]), 2)
        (self.project / "my-experiment.txt").write_text("keep")
        installer.install(self.project, "both", uninstall=True)
        self.assertEqual(json.loads(path.read_text()), existing)
        self.assertEqual((self.project / "my-experiment.txt").read_text(), "keep")
        self.assertFalse((self.project / "plugins/research-dojo").exists())

    def test_modified_plugin_is_preserved(self):
        installer.install(self.project, "codex")
        path = self.project / "plugins/research-dojo/plugin.json"
        path.write_text("user edits")
        for removing in (True, False):
            with self.assertRaises(ValueError):
                installer.install(self.project, "codex", uninstall=removing)
        self.assertEqual(path.read_text(), "user edits")

    def test_unmanaged_destination_is_preserved(self):
        path = self.project / "plugins/research-dojo"
        path.mkdir(parents=True)
        with self.assertRaises(ValueError):
            installer.install(self.project, "both")

    def test_marketplace_entry_collision_is_preserved(self):
        path = self.project / ".claude-plugin/marketplace.json"
        path.parent.mkdir(parents=True)
        original = {"name": "team", "plugins": [{"name": "research-dojo", "source": "./different"}]}
        path.write_text(json.dumps(original))
        with self.assertRaises(ValueError):
            installer.install(self.project, "both")
        self.assertEqual(json.loads(path.read_text()), original)
        self.assertFalse((self.project / "plugins/research-dojo").exists())

    def test_symlinked_destination_is_rejected(self):
        outside = self.project / "elsewhere"
        outside.mkdir()
        (self.project / "plugins").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            installer.install(self.project, "both")


if __name__ == "__main__":
    unittest.main()
