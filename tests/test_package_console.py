"""Verify both editions are packaged from source without private user data."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from package_console import build, CONSOLE_VERSION


class PackageTests(unittest.TestCase):
    def test_console_zip_contains_entry_point_and_no_runtime_data(self):
        with TemporaryDirectory() as temp:
            archive, checksum = build(Path(temp) / "console.zip")
            self.assertEqual(len(checksum), 64)
            with ZipFile(archive) as package:
                paths = package.namelist()
                prefix = f"CreatorStudios-Sims4-Console-{CONSOLE_VERSION}/"
                self.assertIn(prefix + "start.bat", paths)
                self.assertIn(prefix + "Run Console.bat", paths)
                self.assertIn(prefix + "requirements-console.txt", paths)
                self.assertIn(prefix + "src/main.py", paths)
                self.assertIn(prefix + "src/console_tools.py", paths)
                self.assertIn(prefix + "src/library_insights.py", paths)
                self.assertIn(prefix + ".version", paths)
                self.assertTrue(all("session" not in name.lower() or name.endswith("TSRSession.py")
                                    for name in paths))
                self.assertFalse(any("Downloads/" in name or "desktop-state.json" in name for name in paths))


if __name__ == "__main__":
    unittest.main()
