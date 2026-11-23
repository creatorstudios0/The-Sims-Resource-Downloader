from pathlib import Path
import json
import zipfile

import pytest

import qt_services
from desktop_qt import MainWindow
from game_recovery import backup_content, game_version


def test_backup_preserves_subfolders_and_quarantined_files(tmp_path):
    game = tmp_path / "game"
    mods = tmp_path / "custom mods"
    folder = mods / "Household Collection"
    tray = game / "Tray"
    folder.mkdir(parents=True)
    tray.mkdir(parents=True)
    (folder / "object.package.disabled").write_bytes(b"object")
    (mods / "Resource.cfg").write_text("Priority 500", encoding="utf-8")
    (tray / "house.trayitem").write_bytes(b"house")
    (game / "GameVersion.txt").write_text("1.114.46.1030", encoding="utf-16")

    output = tmp_path / "content.zip"
    receipt = backup_content(game, mods, output)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert archive.read("Mods/Household Collection/object.package.disabled") == b"object"
        assert archive.read("Mods/Resource.cfg") == b"Priority 500"
        assert archive.read("Tray/house.trayitem") == b"house"
        assert json.loads(archive.read("backup-info.json"))["game_version"] == "1.114.46.1030"
    assert receipt["files"] == 3
    assert (folder / "object.package.disabled").read_bytes() == b"object"

    with pytest.raises(FileExistsError):
        backup_content(game, mods, output)
    with pytest.raises(ValueError, match="outside"):
        backup_content(game, mods, mods / "recursive.zip")


def test_read_game_version_handles_missing_or_unrecognized_metadata(tmp_path):
    assert game_version(tmp_path) is None
    version = tmp_path / "GameVersion.txt"
    version.write_text("still starting", encoding="utf-8")
    assert game_version(tmp_path) is None
    version.write_text("\ufeff1.114.46.1030\n", encoding="utf-8")
    assert game_version(tmp_path) == "1.114.46.1030"


def test_patch_day_keeps_warning_until_player_reviews(tmp_path, qtbot, monkeypatch):
    monkeypatch.setattr(qt_services, "detect_game", lambda: None)
    service = qt_services.LibraryService(tmp_path / "state.json")
    service.settings["auto_scan"] = False
    game = tmp_path / "game"
    game.mkdir()
    service.state["game"] = str(game)
    version = game / "GameVersion.txt"
    version.write_text("1.114.46.1030", encoding="utf-8")

    window = MainWindow(service)
    qtbot.addWidget(window)
    qtbot.waitUntil(lambda: "reviewed baseline" in window.patch_summary.text())
    assert not window.patch_reviewed.isEnabled()

    version.write_text("1.115.200.1030", encoding="utf-8")
    window.patch_check.click()
    qtbot.waitUntil(window.patch_reviewed.isEnabled)
    assert "changed from 1.114.46.1030 to 1.115.200.1030" in window.patch_summary.text()
    assert json.loads(service.path.read_text(encoding="utf-8"))["reviewedGameVersions"][str(game)] == "1.114.46.1030"

    mods = game / "Mods"
    mods.mkdir()
    (mods / "gameplay.ts4script").write_bytes(b"script")
    (mods / "outfit.package").write_bytes(b"package")
    window.review_script_mods()
    assert window.search.text() == ".ts4script"
    qtbot.waitUntil(lambda: window.library_model.rowCount() == 1)
    assert window.library_model.rows[0][1][0] == "gameplay.ts4script"
    window.patch_reviewed.click()
    assert not window.patch_reviewed.isEnabled()
    assert service.patch_versions() == ("1.115.200.1030", "1.115.200.1030")
    service.shutdown()


def test_backup_worker_updates_receipt(tmp_path, qtbot, monkeypatch):
    monkeypatch.setattr(qt_services, "detect_game", lambda: None)
    service = qt_services.LibraryService(tmp_path / "state.json")
    game = tmp_path / "game"
    mods = game / "Mods"
    mods.mkdir(parents=True)
    (mods / "outfit.package").write_bytes(b"test")
    service.state["game"] = str(game)
    output = tmp_path / "one.zip"

    service.create_content_backup(output)
    assert service.mutating_files()
    qtbot.waitUntil(lambda: "lastContentBackup" in service.state)
    assert Path(service.state["lastContentBackup"]["path"]) == output
    assert not service.mutating_files()
    service.shutdown()
