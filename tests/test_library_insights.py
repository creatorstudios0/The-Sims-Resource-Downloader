"""Read-only inventory regression tests with fake temporary game folders."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tempfile import TemporaryDirectory
import errno
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

    def test_inaccessible_subfolder_reports_warning_and_keeps_readable_files(self):
        blocked = self.mods / "blocked"
        blocked.mkdir()
        (self.mods / "one.package").write_bytes(b"test")
        scandir = os.scandir

        def selectively_scan(path):
            if Path(path) == blocked:
                raise PermissionError(errno.EACCES, "Permission denied", str(path))
            return scandir(path)

        with patch("library_insights.os.scandir", side_effect=selectively_scan):
            report = scan_inventory(self.mods)

        self.assertEqual(report["total_files"], 1)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("blocked", report["warnings"][0])

    @unittest.skipUnless(os.name == "nt", "Windows junctions unavailable")
    def test_excludes_junction_roots_and_subfolders(self):
        from _winapi import CreateJunction

        relocated = self.root / "relocated"
        relocated.mkdir()
        (relocated / "external.package").write_bytes(b"external")
        (self.mods / "local.package").write_bytes(b"local")
        linked_root = self.root / "linked-mods"
        CreateJunction(str(relocated), str(linked_root))
        CreateJunction(str(relocated), str(self.mods / "linked-subfolder"))

        root_report = scan_inventory(linked_root)
        self.assertEqual(root_report["total_files"], 0)
        self.assertEqual(len(root_report["warnings"]), 1)
        self.assertEqual([entry["relative_path"] for entry in scan_inventory(self.mods)["files"]],
                         ["local.package"])

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
