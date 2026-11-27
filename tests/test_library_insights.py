"""Read-only inventory regression tests with fake temporary game folders."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tempfile import TemporaryDirectory
from threading import Barrier, Lock
import json
import os
import unittest
from unittest.mock import patch

from library_insights import scan_inventory, write_report, format_summary


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mods = self.root / "Mods"
        self.tray = self.root / "Tray"
        self.mods.mkdir()
        self.tray.mkdir()

    def test_identical_bytes_only_and_disabled_mods(self):
        (self.mods / "one.package").write_bytes(b"same")
        (self.mods / "two.package").write_bytes(b"same")
        (self.mods / "other.package").write_bytes(b"diff")
        (self.mods / "script.ts4script.disabled").write_bytes(b"script")
        (self.tray / "room.room").write_bytes(b"room")
        (self.mods / "not-a-mod.txt").write_text("ignored")
        report = scan_inventory(self.mods, self.tray)
        self.assertEqual(report["total_files"], 5)
        self.assertEqual(report["disabled_files"], 1)
        self.assertEqual(len(report["duplicate_groups"]), 1)
        self.assertEqual(len(report["duplicate_groups"][0]["paths"]), 2)
        self.assertIn("exact duplicate groups", format_summary(report))

    def test_no_directory_mutations_and_csv_json_export(self):
        (self.mods / "one.package").write_bytes(b"test")
        report = scan_inventory(self.mods)
        json_file = self.root / "inventory.json"
        csv_file = self.root / "inventory.csv"
        write_report(report, json_file)
        write_report(report, csv_file)
        self.assertEqual(json.loads(json_file.read_text())["total_files"], 1)
        self.assertIn("one.package", csv_file.read_text())
        self.assertEqual((self.mods / "one.package").read_bytes(), b"test")

    def test_missing_folders_report_warning(self):
        report = scan_inventory(self.mods / "missing")
        self.assertEqual(report["total_files"], 0)
        self.assertEqual(len(report["warnings"]), 1)

    def test_export_preserves_existing_temporary_namesake(self):
        destination = self.root / "inventory.json"
        unrelated = destination.with_name(destination.name + ".tmp")
        unrelated.write_text("keep this", encoding="utf-8")

        write_report({"files": []}, destination)

        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep this")
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), {"files": []})

    def test_overlapping_exports_publish_complete_reports(self):
        destination = self.root / "inventory.json"
        reports = [{"files": [], "run": run} for run in (1, 2)]
        ready = Barrier(2)
        publishing = Lock()
        replace = os.replace

        def replace_together(source, target):
            ready.wait(timeout=5)
            with publishing:
                replace(source, target)

        with patch("library_insights.os.replace", side_effect=replace_together):
            with ThreadPoolExecutor(max_workers=2) as workers:
                futures = [workers.submit(write_report, report, destination) for report in reports]
                for future in futures:
                    self.assertEqual(future.result(), str(destination))

        self.assertIn(json.loads(destination.read_text(encoding="utf-8")), reports)
        self.assertEqual(set(self.root.iterdir()), {self.mods, self.tray, destination})

    def test_max_files_limit(self):
        for name in ("one.package", "two.package"):
            (self.mods / name).write_bytes(b"same")
        report = scan_inventory(self.mods, max_files=1)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["total_files"], 1)

    def test_symlink_skipped(self):
        (self.mods / "real.package").write_bytes(b"test")
        try:
            (self.mods / "linked.package").symlink_to(self.mods / "real.package")
        except (OSError, NotImplementedError):
            self.skipTest("Symlink unavailable")
        self.assertEqual(scan_inventory(self.mods)["total_files"], 1)

    def test_unsupported_export_format_rejected(self):
        with self.assertRaises(ValueError):
            write_report({"files": []}, self.root / "report.exe")


if __name__ == "__main__":
    unittest.main()
