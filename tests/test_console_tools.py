"""Console tools run without a TSR account or network."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tempfile import TemporaryDirectory
import unittest

import pytest

from console_tools import diagnostics, queue_info, resolved_download_folder, build_parser, main


def test_audit_finds_game_in_redirected_windows_documents(tmp_path, monkeypatch):
    if sys.platform != "win32":
        pytest.skip("Windows Documents redirection")
    import windows_folders

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    documents = tmp_path / "redirected" / "Documents"
    monkeypatch.setattr(windows_folders, "known_folder", lambda key, fallback: documents)
    mods = documents / "Electronic Arts" / "The Sims 4" / "Mods"
    mods.mkdir(parents=True)
    (mods / "test.package").write_bytes(b"test mod")
    output = tmp_path / "audit.json"

    assert main(["audit", "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["roots"]["Mods"] == str(mods)
    assert report["total_files"] == 1


class ConsoleToolsTests(unittest.TestCase):
    def test_queue_ignores_invalid_and_duplicate_hosts(self):
        with TemporaryDirectory() as temp:
            saved = Path(temp) / "urls.txt"
            saved.write_text("https://www.thesimsresource.com/downloads/details/id/42\n"
                             "https://www.thesimsresource.com/downloads/details/id/42\n"
                             "https://evil.example/downloads/id/43\n")
            info = queue_info(saved)
            self.assertEqual(info["count"], 1)

    def test_missing_queue_is_empty(self):
        with TemporaryDirectory() as temp:
            self.assertEqual(queue_info(Path(temp) / "missing.txt")["count"], 0)

    def test_doctor_validates_worker_range(self):
        with TemporaryDirectory() as temp:
            rows = diagnostics({"maxActiveDownloads": 0}, Path(temp))
            self.assertFalse(rows[-1][-1])

    def test_parser_has_all_tools(self):
        for command in ("doctor", "audit", "queue", "settings"):
            self.assertEqual(build_parser().parse_args([command]).command, command)

    def test_relative_download_path_uses_project(self):
        self.assertTrue(resolved_download_folder({"downloadDirectory": "./Downloads"}).is_absolute())


if __name__ == "__main__":
    unittest.main()
