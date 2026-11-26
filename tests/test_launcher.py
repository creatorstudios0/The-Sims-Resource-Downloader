"""Guard release launcher structure against accidental batch label corruption."""
import json
import os
from pathlib import Path
import re
from shutil import copyfile
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_launcher_has_single_entry_points(self):
        source = (PROJECT / "start.bat").read_text(encoding="utf-8")
        labels = re.findall(r"(?m)^:([A-Za-z][A-Za-z0-9]*)\s*$", source)
        self.assertEqual(len(labels), len(set(labels)))
        for required in ("ConsoleTools", "Usage", "LaunchApp", "LaunchClassic", "CheckConsoleUpdates"):
            self.assertIn(required, labels)
        self.assertNotIn("xcopy", source.lower())
        self.assertNotIn("tsr_update.zip", source.lower())

    def test_console_option_forwarding_does_not_shift(self):
        source = (PROJECT / "start.bat").read_text(encoding="utf-8")
        body = source.split("\n:ConsoleTools\n", 1)[1].split("\n:Usage\n", 1)[0]
        self.assertNotIn("\nshift\n", body.lower())
        self.assertIn(r"src\console_tools.py %TOOL% %2 %3", body)

    @unittest.skipUnless(os.name == "nt", "Requires the Windows batch launcher")
    def test_audit_preserves_exclamation_marks_in_paths(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            for name in ("start.bat", "src/config.json", "src/console_tools.py", "src/library_insights.py"):
                copyfile(PROJECT / name, root / name)
            subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root / "venv")],
                           check=True, capture_output=True, timeout=30)
            game = root / "My Sims 4!"
            mods = game / "Mods"
            mods.mkdir(parents=True)
            (mods / "dress.package").write_bytes(b"sample mod")
            report = root / "Mod audit!.json"
            result = subprocess.run(
                ["cmd.exe", "/d", "/v:off", "/c", "start.bat", "--audit",
                 "--game", str(game), "--output", str(report)],
                cwd=root,
                env={**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(report.is_file(), result.stdout)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["total_files"], 1)

    def test_separate_console_requirements_and_launcher(self):
        source = (PROJECT / "start.bat").read_text(encoding="utf-8")
        self.assertIn('set "REQUIREMENTS_FILE=requirements-console.txt"', source)
        self.assertIn('goto :ConsoleTools', source)
        console = (PROJECT / "Run Console.bat").read_text(encoding="utf-8")
        self.assertIn("--console", console)
        self.assertIn("start.bat", console)


if __name__ == "__main__":
    unittest.main()
