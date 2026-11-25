from concurrent.futures import Future
import json
import logging
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
import zipfile

import pytest
from PySide6.QtCore import QAbstractAnimation, QPoint, Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QTableView

import qt_services
import curseforge
from desktop_qt import MainWindow
from desktop_data import parse_url
from qt_services import LibraryService, scan_files
from qt_theme import ToggleSwitch
from desktop_transfer import DesktopTSRDownload as TSRDownload

URL = "https://www.thesimsresource.com/downloads/123"


@pytest.fixture
def app_state(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qt_services, "detect_game", lambda: None)
    service = LibraryService(tmp_path / "desktop-state.json")
    service.settings["auto_scan"] = False
    service.settings["animations"] = False
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.show()
    yield service, window
    service.request_close()
    service.shutdown()


def test_navigation_resize_and_state(app_state, qtbot):
    service, window = app_state
    for index, button in enumerate(window.nav_buttons):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        assert window.pages.currentIndex() == index
    window.resize(800, 650)
    qtbot.waitUntil(lambda: window.collapsed)
    window.resize(1230, 800)
    qtbot.waitUntil(lambda: not window.collapsed)
    window.setting_controls["workers"].setValue(2)
    window.setting_controls["downloads"].setText(str(service.path.parent / "test download"))
    window.confirm = lambda *_: True
    window.save_settings()
    data = json.loads(service.path.read_text(encoding="utf-8"))
    assert data["settings"]["workers"] == 2
    assert Path(data["settings"]["downloads"]).is_dir()


def test_desktop_switches_keep_preferences_in_sync(app_state, qtbot, monkeypatch):
    service, window = app_state
    monkeypatch.delenv("QT_REDUCED_MOTION", raising=False)
    service.settings["animations"] = True
    window.sync_settings()

    window.go(1)
    queue_switch = window.clipboard_toggle
    settings_switch = window.setting_controls["watch"]
    assert isinstance(queue_switch, ToggleSwitch)
    assert isinstance(settings_switch, ToggleSwitch)
    initial = queue_switch.isChecked()

    qtbot.mouseClick(queue_switch, Qt.MouseButton.LeftButton, pos=QPoint(18, 13))
    assert queue_switch.isChecked() != initial
    assert settings_switch.isChecked() == queue_switch.isChecked()
    assert service.settings["watch"] == queue_switch.isChecked()
    assert queue_switch.slide.state() == QAbstractAnimation.State.Running

    monkeypatch.setenv("QT_REDUCED_MOTION", "1")
    window.apply_theme()
    assert queue_switch.slide.state() == QAbstractAnimation.State.Stopped
    window.go(6)
    settings_switch.setFocus()
    qtbot.keyClick(settings_switch, Qt.Key.Key_Space)
    assert settings_switch.isChecked() == initial
    assert settings_switch.slide.state() == QAbstractAnimation.State.Stopped
    assert queue_switch.isChecked() != initial

    window.save_settings()
    assert queue_switch.isChecked() == initial
    assert service.settings["watch"] == initial
    saved = json.loads(service.path.read_text(encoding="utf-8"))
    assert saved["settings"]["watch"] == initial


def test_import_dependencies_progress_retry_and_pause(app_state, qtbot, monkeypatch):
    service, window = app_state
    monkeypatch.setattr(qt_services, "inspect_item", lambda url, dependencies: {
        "name": "Pine Living Room", "creator": "Test creator",
        "status": "Review", "requires": ["124"] if dependencies else [], "detail": "",
    })
    results = service.import_text(f"{URL}\nhttp://invalid.test\n{URL}")
    assert [status.split(" ·")[0] for _, status in results] == ["Added for review", "Invalid link", "Duplicate"]
    qtbot.waitUntil(lambda: service.items["123"]["status"] == "Review")
    assert service.items["123"]["requires"] == ["124"]
    started, continue_work = Event(), Event()
    calls = []

    def transfer(url, session, destination, progress, organize, cancel, attempts):
        calls.append(url)
        started.set()
        progress("file.package", 512, 1024)
        if not continue_work.wait(3):
            raise AssertionError("test transfer was not released")
        if len(calls) == 1:
            raise PermissionError()
        return {"path": str(service.path.parent / "file.package"), "category": "Package Mods",
                "status": "Complete", "detail": ""}

    monkeypatch.setattr(qt_services, "fetch_item", transfer)
    service.queue(["123"])
    qtbot.waitUntil(started.is_set)
    qtbot.waitUntil(lambda: bool(service.progress_data))
    assert window.queue_cells("123")[5] == ("50%", 50)
    assert window.stats[1].text() == "1"
    service.set_paused(True)
    assert service.paused
    continue_work.set()
    qtbot.waitUntil(lambda: service.items["123"]["status"] == "Download failed")
    assert "Permission denied" in service.items["123"]["detail"]
    service.retry(["123"])
    qtbot.waitUntil(lambda: service.items["123"]["status"] == "Complete")
    assert not service.paused



def test_remove_selected_keeps_download_that_starts_during_confirmation(app_state, monkeypatch):
    service, window = app_state
    service.import_text(f"{URL} {URL[:-3]}124 {URL[:-3]}125", lookup=False)
    service.settings["workers"] = 1
    monkeypatch.setattr(service, "submit", Mock())
    service.queue(["123", "124", "125"])
    window.go(1)
    selection = window.queue_view.selectionModel()
    flags = selection.SelectionFlag.Select | selection.SelectionFlag.Rows
    for key in ("124", "125"):
        selection.select(window.queue_model.index(window.queue_model.indices[key], 0), flags)

    failed = Future()
    failed.set_exception(PermissionError())

    def confirm_removal(*_):
        assert service.items["124"]["status"] == "Queued"
        service.finish("download", "123", failed)
        assert service.items["124"]["status"] == "Downloading"
        return True

    with monkeypatch.context() as modal:
        modal.setattr(window, "confirm", confirm_removal)
        try:
            window.remove_selected()
            assert "124" in service.items
            assert "125" not in service.items

            service.finish("download", "124", failed)
            assert service.items["124"]["status"] == "Download failed"
            assert not service.active
        finally:
            service.active.clear()


def test_cancel_and_close(app_state, qtbot, monkeypatch):
    from concurrent.futures import CancelledError
    service, window = app_state
    service.import_text(URL, lookup=False)
    started = Event()
    def transfer(url, session, destination, progress, organize, cancel, attempts):
        started.set()
        assert cancel.wait(3)
        raise CancelledError()
    monkeypatch.setattr(qt_services, "fetch_item", transfer)
    service.queue(["123"])
    qtbot.waitUntil(started.is_set)
    window.confirm = lambda *_: True
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible())
    assert service.items["123"]["status"] == "Cancelled"
    assert service.state["windowGeometry"]


def test_real_disk_scan_install_toggle_and_history(app_state, qtbot, tmp_path, monkeypatch):
    service, window = app_state
    game = tmp_path / "The Sims 4"
    mods = game / "Mods"
    tray = game / "Tray"
    mods.mkdir(parents=True)
    tray.mkdir()
    first = mods / "existing.package"
    duplicate = mods / "copy.package"
    first.write_bytes(b"same")
    duplicate.write_bytes(b"same")
    source = tmp_path / "house.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("../../outside.package", b"safe")
        archive.writestr("house.trayitem", b"cc")
        archive.writestr("existing.package", b"never overwrite")
    service.state["game"] = str(game)
    service.add_local([source])
    key = next(iter(service.items))
    plan = service.install_preview(key)
    assert [entry[3] for entry in plan] == [False, False, True]
    service.install_selected(key, plan)
    qtbot.waitUntil(lambda: bool(service.batches))
    assert first.read_bytes() == b"same"
    assert (tray / "house.trayitem").is_file()
    assert not (tmp_path / "outside.package").exists()
    batch = next(iter(service.batches))
    service.toggle_managed(batch, 0)
    qtbot.waitUntil(lambda: service.batches[batch]["files"][0]["disabled"])
    assert (mods / "outside.package.disabled").is_file()
    service.toggle_managed(batch, 0)
    qtbot.waitUntil(lambda: not service.batches[batch]["files"][0]["disabled"])
    assert (mods / "outside.package").is_file()
    service.scan()
    qtbot.waitUntil(lambda: not service.jobs)
    assert service.health["duplicates"] == 1
    assert window.stats[0].text() == "3"
    service.settings["backup_enabled"] = True
    service.settings["backup"] = str(tmp_path / "backups")
    monkeypatch.setattr(window, "confirm", lambda *_: True)
    window.uninstall(batch)
    qtbot.waitUntil(lambda: batch not in service.batches)
    assert not (mods / "outside.package").exists() and not (tray / "house.trayitem").exists()
    assert list((tmp_path / "backups" / batch).glob("*/house.trayitem"))
    assert any(row["action"] == "Uninstall" for row in service.history_rows())
    assert sum(row["action"] == "Install" for row in service.history_rows()) == 1
    qtbot.waitUntil(lambda: not service.jobs)



@pytest.mark.parametrize("legacy_batch", [False, True])
def test_install_history_keeps_selected_batch_when_new_activity_arrives(app_state, monkeypatch, legacy_batch):
    service, window = app_state
    service.batches["older-batch"] = dict(item="Older mod", files=[], date="2025-01-01")
    if not legacy_batch:
        service.history_event("Older mod", "Install", "Completed", [], when="2025-01-01")
        service.history[-1]["batch"] = "older-batch"
    service.publish()
    window.go(3)
    window.history_view.selectRow(0)
    assert window.current_history()["batch"] == "older-batch"

    service.batches["newer-batch"] = dict(item="Newer mod", files=[], date="2025-01-02")
    service.history_event("Newer mod", "Install", "Completed", [], when="2025-01-02")
    service.history[-1]["batch"] = "newer-batch"
    service.publish()

    assert window.current_history()["batch"] == "older-batch"
    uninstall = Mock()
    monkeypatch.setattr(window, "uninstall", uninstall)
    window.history_undo.click()
    uninstall.assert_called_once_with("older-batch")


@pytest.mark.parametrize("change", ["removed", "quarantined", "busy"])
def test_uninstall_rechecks_the_batch_after_confirmation(app_state, monkeypatch, change):
    service, window = app_state
    record = dict(path=str(service.path.parent / "dress.package"), disabled=False, hash="recorded")
    service.batches["batch"] = dict(item="Dress", files=[record])
    undo = Mock()
    monkeypatch.setattr(service, "undo", undo)

    def confirm(*_):
        if change == "removed":
            del service.batches["batch"]
        elif change == "quarantined":
            record["disabled"] = True
        else:
            service.jobs.add("content-backup")
        return True

    monkeypatch.setattr(window, "confirm", confirm)
    window.uninstall("batch")
    undo.assert_not_called()
    assert window.notifications.entries[0][1] == "WARNING"


def test_import_and_refresh_hides_deleted_files(app_state, qtbot, tmp_path, monkeypatch):
    service, window = app_state
    service.state["game"] = str(tmp_path)
    source = tmp_path / "mixed.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("nested/dress.package", b"package")
        archive.writestr("nested/house.trayitem", b"tray")
    monkeypatch.setattr("desktop_qt.QFileDialog.getOpenFileNames", lambda *_: ([str(source)], ""))
    window.add_files()
    qtbot.waitUntil(lambda: not service.jobs)
    assert (tmp_path / "Mods" / "dress.package").read_bytes() == b"package"
    assert (tmp_path / "Tray" / "house.trayitem").read_bytes() == b"tray"
    assert window.library_model.rowCount() == 3
    source.unlink()
    (tmp_path / "Mods" / "dress.package").unlink()
    refresh = next(button for button in window.pages.widget(2).findChildren(type(window.install_button))
                   if button.text() == "Refresh Library")
    refresh.click()
    qtbot.waitUntil(lambda: not service.jobs)
    assert [cells[0] for _, cells in window.library_model.rows] == ["house.trayitem"]
    assert service.history_rows()[0]["result"] == "Completed"


def test_discover_search_and_install(app_state, qtbot, tmp_path, monkeypatch):
    service, window = app_state
    service.state["game"] = str(tmp_path)
    service.settings["downloads"] = str(tmp_path / "downloads")
    asset = "https://mediafilez.forgecdn.net/files/test/dress.package"
    project = dict(id=42, name="Summer Dress", authors=[{"name": "Creator"}],
                   links={"websiteUrl": "https://www.curseforge.com/sims4/create-a-sim/summer-dress"},
                   latestFiles=[dict(id=27, isAvailable=True, fileName="dress.package", fileLength=4, downloadUrl=asset)])

    def get(url, **kwargs):
        response = Mock(status_code=200)
        response.__enter__ = lambda _: response
        response.__exit__ = lambda *_: None
        if url == asset:
            assert "headers" not in kwargs
            response.iter_content.return_value = [b"test"]
        else:
            assert url == curseforge.API + "/mods/search"
            assert kwargs["headers"]["x-api-key"] == "test-key"
            assert kwargs["params"]["gameId"] == 781
            assert kwargs["params"]["searchFilter"] == "dress"
            response.json.return_value = {"data": [project], "pagination": {"totalCount": 1}}
        return response

    monkeypatch.setattr(curseforge.requests, "get", get)
    window.go(4)
    window.discover.api_key.setText("test-key")
    window.discover.search_box.setText("dress")
    window.discover.search()
    qtbot.waitUntil(lambda: window.discover.model.rowCount() == 1)
    window.discover.results.selectRow(0)
    assert window.discover.install_button.isEnabled()
    window.discover.install_button.click()
    qtbot.waitUntil(lambda: bool(service.batches) and not service.jobs)
    assert (tmp_path / "Mods" / "dress.package").read_bytes() == b"test"
    assert window.queue_cells("cf-42-27")[2] == "CurseForge"
    assert "test-key" not in service.path.read_text(encoding="utf-8")
    assert curseforge.latest_file(dict(project, allowModDistribution=False)) is None


def test_console_shows_background_activity(app_state, qtbot, caplog):
    service, window = app_state
    with caplog.at_level(logging.INFO, logger="logger"):
        service.scan()
        qtbot.waitUntil(lambda: "Library refreshed" in window.console.toPlainText())



def test_discover_can_retry_failed_page_without_losing_results(app_state, qtbot, monkeypatch):
    _, window = app_state
    page = window.discover
    failed_next = False

    def search(key, query, index):
        nonlocal failed_next
        assert (key, query) == ("test-key", "dress")
        if index == curseforge.PAGE_SIZE and not failed_next:
            failed_next = True
            raise ValueError("Temporary catalog error")
        return [{"id": index + 1, "name": f"Dress {index + 1}"}], curseforge.PAGE_SIZE + 1

    monkeypatch.setattr(curseforge, "search", search)
    page.api_key.setText("test-key")
    page.search_box.setText("dress")
    page.search()
    qtbot.waitUntil(page.next.isEnabled)
    page.next.click()
    qtbot.waitUntil(lambda: "Temporary catalog error" in page.status.text())
    assert page.model.rows[0][1][0] == "Dress 1"
    assert page.next.isEnabled()
    page.next.click()
    qtbot.waitUntil(page.previous.isEnabled)
    assert page.model.rows[0][1][0] == f"Dress {curseforge.PAGE_SIZE + 1}"


def test_tsr_discover_downloads_and_installs(app_state, qtbot, tmp_path, monkeypatch):
    service, window = app_state
    service.state["game"] = str(tmp_path)
    source = tmp_path / "room.trayitem"
    source.write_bytes(b"room")
    monkeypatch.setattr(qt_services, "fetch_item", lambda *_: {
        "path": str(source), "status": "Complete", "category": "Tray Files", "detail": "",
    })
    window.discover.tsr_link.setText(URL)
    window.discover.install_tsr()
    qtbot.waitUntil(lambda: bool(service.batches) and not service.jobs)
    assert (tmp_path / "Tray" / "room.trayitem").read_bytes() == b"room"
    assert window.pages.currentIndex() == 1


def test_profile_backup_recovers_corrupt_state(tmp_path, qtbot, monkeypatch):
    monkeypatch.setattr(qt_services, "detect_game", lambda: None)
    state_path = tmp_path / "desktop-state.json"
    service = LibraryService(state_path)
    service.profiles["Favorites"] = ["123"]
    service.save()
    snapshot = service.backups.snapshots()[0]
    service.shutdown()
    state_path.write_text("{truncated", encoding="utf-8")
    recovered = LibraryService(state_path)
    assert recovered.recovered == snapshot
    assert recovered.profiles == {"Favorites": ["123"]}
    recovered.profiles["Recent"] = ["456"]
    recovered.save()
    preserved = recovered.backups.snapshots()[0]
    recovered.restore_backup(snapshot)
    qtbot.waitUntil(lambda: not recovered.jobs)
    assert recovered.profiles == {"Favorites": ["123"]}
    assert "Recent" in json.loads(preserved.read_text(encoding="utf-8"))["profiles"]
    recovered.shutdown()


def test_profile_backup_restore_resets_library_group_filters(app_state, qtbot, tmp_path, monkeypatch):
    service, window = app_state
    files = [tmp_path / name for name in ("first.package", "second.package")]
    for path in files:
        path.write_bytes(b"package")
    service.add_local(files)
    first = next(iter(service.items))
    service.profiles["Favorites"] = [first]
    service.collections["Family"] = [first]
    service.publish()
    snapshot = service.backups.snapshots()[0]
    window.profile_control.setCurrentText("Favorites")
    window.collection_control.setCurrentText("Family")
    assert window.library_model.rowCount() == 1

    def choose_snapshot(dialog):
        dialog.findChild(QTableView).selectRow(0)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(service.backups, "snapshots", lambda: [snapshot])
    monkeypatch.setattr(QDialog, "exec", choose_snapshot)
    monkeypatch.setattr(window, "confirm", lambda *_: True)
    window.profile_backups()
    qtbot.waitUntil(lambda: not service.jobs)

    assert window.profile_control.currentText() == "All profiles"
    assert window.collection_control.currentText() == "All collections"
    assert window.library_model.rowCount() == 2


def test_migration_preserves_classic_data(tmp_path, qapp, monkeypatch):
    monkeypatch.setattr(qt_services, "detect_game", lambda: None)
    location = tmp_path / "desktop-state.json"
    original = dict(game=str(tmp_path / "Existing game"), legacyImported=True,
                    settings={"workers": 2, "watch": True, "downloads": str(tmp_path / "old downloads")},
                    items={"123": {"status": "Downloading", "name": "Existing download", "url": URL}},
                    installs={"old": {"item": "123", "files": [{"path": str(tmp_path / "example.package"),
                                                               "hash": "123", "disabled": False}]}},
                    profiles={"Original": ["123"]})
    location.write_text(json.dumps(original), encoding="utf-8")
    service = LibraryService(location)
    assert service.items["123"]["status"] == "Paused"
    assert service.settings["downloads"] == original["settings"]["downloads"]
    assert service.settings["watch"] and service.settings["workers"] == 2
    assert service.state["game"] == original["game"]
    assert service.profiles == original["profiles"]
    assert service.batches == original["installs"]
    assert service.history_rows()[0]["date"] == ""
    service.shutdown()


def test_engine_file_request_and_validated_resume(tmp_path, monkeypatch):
    downloader = TSRDownload(parse_url(URL), "")
    monkeypatch.setattr(downloader, "_getDownloadUrl", lambda: "https://files.example.com/item")
    data = []
    def got_response(status, chunks, headers):
        response = requests_response(status, chunks, headers)
        monkeypatch.setattr(downloader.session, "get", Mock(return_value=response))
    got_response(200, [b"fresh"], {"Content-Length": "5"})
    test = downloader._attemptDownload(str(tmp_path), lambda *args: data.append(args), False)
    assert Path(test).read_bytes() == b"fresh" and data[-1][-2:] == (5, 5)
    assert downloader.session.get.call_count == 1
    partial = tmp_path / ".partial/123.part"
    partial.write_bytes(b"old")
    partial.with_suffix(".etag").write_text('"E1"')
    got_response(200, [b"fresh"], {"Content-Length": "5"})
    test = downloader._attemptDownload(str(tmp_path), lambda *args: None, False)
    assert Path(test).read_bytes() == b"fresh"
    partial.write_bytes(b"old")
    partial.with_suffix(".etag").write_text('"E1"')
    got_response(206, [b"+new"], {"Content-Range": "bytes 3-6/7", "Content-Length": "4", "ETag": '"E1"'})
    test = downloader._attemptDownload(str(tmp_path), lambda *args: None, False)
    assert Path(test).read_bytes() == b"old+new"
    assert downloader.session.get.call_args.kwargs["headers"]["Range"] == "bytes=3-"


def requests_response(status, chunks, headers):
    response = Mock()
    response.status_code = status
    response.headers = {"Content-Disposition": 'attachment; filename="test.package"', **headers}
    response.iter_content.return_value = iter(chunks)
    response.__enter__ = lambda _: response
    response.__exit__ = lambda *_: None
    return response


def test_redirect_and_cancel_guards(tmp_path, monkeypatch):
    from concurrent.futures import CancelledError
    downloader = TSRDownload(parse_url(URL), "")
    redirect = requests_response(302, [], {"Location": "https://other.example.org/file"})
    send = Mock(return_value=redirect)
    monkeypatch.setattr(downloader.session, "get", send)
    with pytest.raises(ValueError, match="Unexpected"):
        downloader._delivery_response("https://files.example.com/file", {}, None)
    assert send.call_count == 1
    cancel = Event()
    cancel.set()
    with pytest.raises(CancelledError):
        downloader.download(str(tmp_path), cancel=cancel)


def test_large_library_model(app_state, tmp_path):
    service, window = app_state
    service.items.update({str(index): dict(name=f"Mod {index:04d}", status="Complete", path=str(tmp_path / f"{index}.package"),
                                           category="Gameplay", size=index) for index in range(5000)})
    service.publish(False)
    assert window.library_model.rowCount() == 5000
    window.search.setText("Mod 0042")
    assert window.library_model.rowCount() == 1
    window.view_switch.setCurrentText("Grid")
    assert window.grid_model.rowCount() == 1

def test_standard_tsr_paths_and_query_validation():
    from exceptions import InvalidURL
    assert parse_url("https://www.thesimsresource.com/downloads/details/category/sims4-sets/id/123/item/").itemId == 123
    assert parse_url(f"{URL}?utm_source=test").url == URL
    for value in ("https://example.com/downloads/123", "https://www.thesimsresource.com/downloads/search/?x=/id/123",
                  "https://www.thesimsresource.com/downloads/123broken"):
        with pytest.raises(InvalidURL):
            parse_url(value)


def test_scans_unmanaged_tray_without_counting_it_as_mod(tmp_path):
    mods = tmp_path / "Mods"
    tray = tmp_path / "Tray"
    mods.mkdir()
    tray.mkdir()
    (mods / "enabled.package").write_bytes(b"abc")
    (mods / "disabled.ts4script.disabled").write_bytes(b"def")
    (tray / "room.trayitem").write_bytes(b"12345")
    files, local, health = scan_files(mods, {}, {}, True, tray)
    assert len(files) == 3 and not local
    assert health["mods"] == 2 and health["storage"] == 11
    assert any(record["disabled"] for record in files.values())


def test_safe_transfer_does_not_replace_existing_file(tmp_path, monkeypatch):
    downloader = TSRDownload(parse_url(URL), "")
    existing = tmp_path / "123-test.package"
    existing.write_bytes(b"preserve")
    monkeypatch.setattr(downloader, "_getDownloadUrl", lambda: "https://files.example.com/item")
    response = requests_response(200, [b"data"], {"Content-Length": "4"})
    monkeypatch.setattr(downloader.session, "get", Mock(return_value=response))
    published = Path(downloader._attemptDownload(str(tmp_path), lambda *args: None, False))
    assert published != existing and published.read_bytes() == b"data"
    assert existing.read_bytes() == b"preserve"



def test_dashboard_storage_filters_real_scan_results(app_state, qtbot, tmp_path):
    service, window = app_state
    service.state["game"] = str(tmp_path)
    mods = tmp_path / "Mods"
    mods.mkdir()
    (mods / "outfit.package").write_bytes(b"x" * 60)
    (mods / "controller.ts4script").write_bytes(b"x" * 40)

    service.scan()
    qtbot.waitUntil(lambda: not service.jobs)
    dashboard = window.dashboard
    assert window.stats[0].text() == "2"
    assert dashboard.storage_bar.value() == 60
    dashboard.storage_type.setCurrentText("Script mods")
    assert dashboard.storage_bar.value() == 40
    qtbot.mouseClick(dashboard.storage_open, Qt.MouseButton.LeftButton)
    assert window.pages.currentIndex() == 2
    assert [record[1][0] for record in window.library_model.rows] == ["controller.ts4script"]
    window.view_switch.setCurrentText("Compact")
    assert window.library_list.isColumnHidden(1)
    window.view_switch.setCurrentText("Grid")
    assert window.grid_model.rowCount() == 1
    window.view_switch.setCurrentText("List")
    assert not window.library_list.isColumnHidden(1)


def test_collections_persist_and_filter_independently(app_state, qtbot, tmp_path, monkeypatch):
    service, window = app_state
    service.state["game"] = str(tmp_path)
    mods = tmp_path / "Mods"
    mods.mkdir()
    (mods / "A.package").write_bytes(b"family")
    (mods / "B.package").write_bytes(b"build")
    service.scan()
    qtbot.waitUntil(lambda: not service.jobs)

    window.go(2)
    window.library_list.selectRow(0)
    monkeypatch.setattr("desktop_qt.QInputDialog.getText", lambda *args, **kwargs: ("Family", True))
    window.save_group("collection")
    assert "Family" in json.loads(service.path.read_text(encoding="utf-8"))["collections"]
    assert not service.profiles
    window.collection_control.setCurrentText("Family")
    assert [record[1][0] for record in window.library_model.rows] == ["A.package"]
    window.library_list.selectRow(0)
    window.edit_group("collection", "remove")
    assert window.library_model.rowCount() == 0
    window.clear_library_filters()
    assert window.library_model.rowCount() == 2


def test_activity_filters_and_popup_preference(app_state):
    service, window = app_state
    console = window.activity_console
    console.append("INFO", "Completed library scan")
    console.append("ERROR", "Library path could not be read")
    console.level.setCurrentText("Error")
    assert console.output.toPlainText() == "Library path could not be read"
    console.search.setText("download")
    assert not console.output.toPlainText()
    console.search.clear()
    console.level.setCurrentText("All levels")
    assert "Completed library scan" in console.output.toPlainText()

    service.settings["notifications"] = False
    window.toast("warning", "A dependency needs attention")
    assert window.notifications.entries[0][2] == "A dependency needs attention"
    assert not window.toast_frame.isVisible()



def test_activity_retains_complete_multiline_events(app_state):
    _, window = app_state
    console = window.activity_console
    console.clear()
    console.append("INFO", "Oldest event")
    console.append("ERROR", "Error heading\r\nError detail")
    for index in range(console.entries.maxlen - 2):
        console.append("INFO", f"Event {index}")

    assert console.output.toPlainText().startswith("Oldest event\nError heading\nError detail\n")
    console.append("INFO", "Newest event")
    assert console.output.toPlainText().startswith("Error heading\nError detail\n")
    console.level.setCurrentText("Error")
    assert console.output.toPlainText() == "Error heading\nError detail"
    console.level.setCurrentText("All levels")
    console.append("INFO", "Another event")
    assert "Error detail" not in console.output.toPlainText()


def test_scanned_mod_keeps_saved_memberships_when_toggled(app_state, qtbot, tmp_path):
    service, window = app_state
    service.state["game"] = str(tmp_path)
    mods = tmp_path / "Mods"
    mods.mkdir()
    mod = mods / "A.package"
    mod.write_bytes(b"family")
    disabled = mod.with_suffix(".package.disabled")

    service.scan()
    qtbot.waitUntil(lambda: not service.jobs)
    original_key = next(iter(service.disk))
    service.profiles["Gameplay"] = [original_key]
    service.collections["Family"] = [original_key]
    service.publish()
    window.profile_control.setCurrentText("Gameplay")
    window.collection_control.setCurrentText("Family")

    for expected_path in (disabled, mod):
        service.toggle_scanned(next(iter(service.disk)))
        qtbot.waitUntil(lambda: not service.jobs)
        assert expected_path.is_file()
        assert window.library_model.rowCount() == 1
        key = next(iter(service.disk))
        saved = json.loads(service.path.read_text(encoding="utf-8"))
        assert saved["profiles"]["Gameplay"] == [key]
        assert saved["collections"]["Family"] == [key]


@pytest.mark.parametrize("kind", ["profile", "collection"])
def test_can_add_selection_to_another_group_while_filtering(app_state, qtbot, tmp_path, monkeypatch, kind):
    service, window = app_state
    service.state["game"] = str(tmp_path)
    mods = tmp_path / "Mods"
    mods.mkdir()
    (mods / "A.package").write_bytes(b"family")
    service.scan()
    qtbot.waitUntil(lambda: not service.jobs)
    key = next(iter(service.disk))
    groups = window.group_records(kind)
    groups.update({"Source": [key], "Destination": []})
    service.publish()
    window.go(2)
    getattr(window, f"{kind}_control").setCurrentText("Source")
    window.library_list.selectRow(0)
    monkeypatch.setattr("desktop_qt.QInputDialog.getItem", lambda *args, **kwargs: ("Destination", True))

    window.edit_group(kind, "add")

    assert groups["Destination"] == [key]
    assert getattr(window, kind) == "Source"
