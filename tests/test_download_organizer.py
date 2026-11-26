"""Verify the folders used when organizing downloaded Tray content."""
import zipfile

import pytest

from download_organizer import organizeDownloadedFile


@pytest.mark.parametrize(("name", "members", "folder"), [
    ("Bedroom Retreat.zip", ["lot.bpi", "lot.trayitem"], "Lots"),
    ("Living Room Family.zip", ["family.hhi", "family.trayitem"], "Households"),
    ("Simple.trayitem", [], "Other Tray Files"),
    ("Classic_Room.trayitem", [], "Rooms"),
])
def test_organize_tray_download(tmp_path, name, members, folder):
    source = tmp_path / name
    if members:
        with zipfile.ZipFile(source, "w") as archive:
            for member in members:
                archive.writestr(member, "sample Tray file")
    else:
        source.write_bytes(b"sample Tray file")

    original = source.read_bytes()
    expected = tmp_path / "Tray Files" / folder / name
    assert organizeDownloadedFile(str(source), enabled=True) == str(expected)
    assert expected.read_bytes() == original
    assert not source.exists()
