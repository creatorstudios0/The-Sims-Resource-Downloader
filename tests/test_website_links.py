from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

import curseforge
import qt_services
from desktop_qt import MainWindow
from website_links import WebsiteLinkServer, parse_install_link


LINK = "sims4modlibrary://curseforge/install?project=42&file=27"


@pytest.mark.parametrize("link", [
    LINK + "&url=https://invalid.test", LINK + "#x", LINK.replace("file=27", "file=%32%37"),
    LINK.replace("project=42", "project=0"), LINK.replace("project=42", "project=4294967296"),
    LINK.replace("curseforge", "evil.example"), "file:///C:/example.zip",
])
def test_protocol_rejects_unexpected_input(link):
    with pytest.raises(ValueError):
        parse_install_link(link)


def test_forwards_to_an_existing_desktop_instance(qtbot, tmp_path):
    from PySide6.QtCore import QObject

    host = QObject()
    state = tmp_path / "state.json"
    server = WebsiteLinkServer(state, host)
    script = ('import sys; from PySide6.QtCore import QCoreApplication; '
              'from website_links import forward_link; app = QCoreApplication([]); '
              'sys.exit(0 if forward_link(sys.argv[1], sys.argv[2]) else 1)')
    source = Path(__file__).resolve().parents[1] / 'src'
    with subprocess.Popen([sys.executable, '-c', script, str(state), LINK], cwd=source) as caller:
        with qtbot.waitSignal(server.received, timeout=5000) as message:
            pass
        assert caller.wait(5) == 0
    assert message.args == [LINK]


@pytest.fixture
def library(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(qt_services, "detect_game", lambda: None)
    service = qt_services.LibraryService(tmp_path / "state.json")
    service.settings.update(auto_scan=False, animations=False, website_links=True)
    window = MainWindow(service)
    qtbot.addWidget(window)
    window.discover.api_key.setText("test-key")
    yield service, window
    service.request_close()
    service.shutdown()


def test_website_cannot_install_before_confirmation(library, tmp_path, qtbot, monkeypatch):
    service, window = library
    game = tmp_path / "game"
    mods = game / "Mods"
    mods.mkdir(parents=True)
    existing = mods / "existing.package"
    existing.write_bytes(b"original")
    service.state["game"] = str(game)
    project = dict(id=42, name="Test House", gameId=781, authors=[])
    file = dict(id=27, modId=42, gameId=781, fileName="house.zip", fileLength=100,
                isAvailable=True, downloadUrl="https://mediafilez.forgecdn.net/file")
    calls = []

    def fake_api(endpoint, key):
        calls.append(endpoint)
        assert key == "test-key"
        return {"data": file if endpoint.endswith("/27") else project}

    monkeypatch.setattr(curseforge, "api_get", fake_api)
    downloads = []
    archive = tmp_path / "house.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("existing.package", b"replacement")
        output.writestr("new.package", b"package")
        output.writestr("lot.trayitem", b"tray")

    def download(*_args):
        downloads.append(True)
        return dict(path=str(archive), status="Complete", category="Tray Files")

    monkeypatch.setattr(curseforge, "download", download)
    monkeypatch.setattr(window, "confirm", lambda *_: False)
    window.receive_website_link(LINK)
    qtbot.waitUntil(lambda: not service.jobs)
    assert calls == ["/mods/42", "/mods/42/files/27"]
    assert not downloads and not service.items and not (game / "Tray").exists()

    monkeypatch.setattr(window, "confirm", lambda *_: True)
    previews = []
    monkeypatch.setattr(window, "show_preview", lambda key, _inputs, plan: previews.append((key, plan)))
    window.receive_website_link(LINK)
    qtbot.waitUntil(lambda: bool(previews))
    assert downloads == [True]
    assert not service.batches and not (game / "Tray").exists()
    key, plan = previews[0]
    assert any(target == existing and conflict for _, target, _, conflict in plan)
    service.install_selected(key, plan)
    qtbot.waitUntil(lambda: bool(service.batches) and not service.jobs)
    assert existing.read_bytes() == b"original"
    assert (mods / "new.package").read_bytes() == b"package"
    assert (game / "Tray" / "lot.trayitem").read_bytes() == b"tray"
    assert service.history_rows()[0]["result"] == "Completed"


def test_website_link_requires_game_folder(library, monkeypatch):
    service, window = library
    monkeypatch.setattr(curseforge, "linked_file", lambda *_: pytest.fail("lookup was started"))
    window.receive_website_link(LINK)
    assert window.pages.currentIndex() == window.pages.count() - 1
    assert "Sims 4 user data folder" in window.toast_content.text()
    assert not service.jobs


def test_curseforge_restricted_file_hands_off_to_website(monkeypatch):
    def project_only(path, _):
        assert path == "/mods/42"
        return {"data": dict(id=42, gameId=781, allowModDistribution=False)}

    monkeypatch.setattr(curseforge, "api_get", project_only)
    _, file = curseforge.linked_file("test-key", 42, 27)
    assert file is None
