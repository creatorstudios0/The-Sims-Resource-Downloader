"""Guard release launcher structure against accidental batch label corruption."""
from pathlib import Path
import re
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

    def test_separate_console_requirements_and_launcher(self):
        source = (PROJECT / "start.bat").read_text(encoding="utf-8")
        self.assertIn('set "REQUIREMENTS_FILE=requirements-console.txt"', source)
        self.assertIn('goto :ConsoleTools', source)
        console = (PROJECT / "Run Console.bat").read_text(encoding="utf-8")
        self.assertIn("--console", console)
        self.assertIn("start.bat", console)


if __name__ == "__main__":
    unittest.main()
