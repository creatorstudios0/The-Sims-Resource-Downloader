"""Verify startup diagnostics for editable downloader configuration."""
import json
from pathlib import Path
import runpy
import shutil

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "src" / "config.py"
VALID = {"downloadDirectory": "./Downloads", "maxActiveDownloads": 4, "saveDownloadQueue": True}


@pytest.fixture
def config_script(tmp_path):
    script = tmp_path / "src" / "config.py"
    script.parent.mkdir()
    shutil.copyfile(SOURCE, script)
    return script


@pytest.mark.parametrize(("contents", "message"), [
    (None, "config.json"),
    ("{", "Expecting"),
    ("[]", "JSON object"),
    (json.dumps({key: value for key, value in VALID.items() if key != "downloadDirectory"}), "Missing required key"),
    (json.dumps(dict(VALID, downloadDirectory=123)), "'downloadDirectory' expects str"),
    (json.dumps(dict(VALID, maxActiveDownloads=True)), "'maxActiveDownloads' expects int"),
])
def test_invalid_config_has_startup_diagnostic(config_script, capsys, contents, message):
    if contents is not None:
        config_script.with_name("config.json").write_text(contents, encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(config_script))

    assert error.value.code == 1
    output = capsys.readouterr().out
    assert "[CONFIG ERROR]" in output
    assert message in output


def test_valid_config_resolves_project_path_and_keeps_defaults(config_script):
    config_script.with_name("config.json").write_text(json.dumps(VALID), encoding="utf-8")

    config = runpy.run_path(str(config_script))["CONFIG"]

    assert Path(config["downloadDirectory"]) == config_script.parents[1] / "Downloads"
    assert config["maxActiveDownloads"] == 4
    assert config["saveDownloadQueue"] is True
    assert config["organizeDownloads"] is True
