"""Sims 4 discovery and distribution through the public CurseForge API."""
from concurrent.futures import CancelledError
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from time import monotonic
from urllib.parse import urlsplit

import requests

from download_organizer import getDownloadCategory, move_with_unique_name
from sims_install import SUPPORTED, validate_filename


API = "https://api.curseforge.com/v1"
CATALOG = "https://www.curseforge.com/sims4"
GAME_ID = 781
PAGE_SIZE = 25


def search(key, query, index):
    response = api_get("/mods/search", key, gameId=GAME_ID, searchFilter=query,
                       index=index, pageSize=PAGE_SIZE, sortField=2, sortOrder="desc")
    pagination = response["pagination"]
    return response["data"], min(10_000, pagination["totalCount"])


def api_get(path, key, **params):
    with requests.get(API + path, params=params, allow_redirects=False,
                      timeout=(8, 20), headers={"Accept": "application/json", "x-api-key": key}) as response:
        if response.status_code in (401, 403):
            raise ValueError("CurseForge rejected the API key. Check the key or request API access.")
        if response.status_code != 200:
            raise ValueError(f"CurseForge API returned HTTP {response.status_code}.")
        return response.json()


def web_url(url):
    parsed = urlsplit(url or "")
    return url if parsed.scheme == "https" and parsed.netloc in {"www.curseforge.com", "curseforge.com"} else CATALOG


def asset_url(url):
    parsed = urlsplit(url or "")
    host = parsed.netloc.lower()
    if parsed.scheme != "https" or not (host.endswith(".forgecdn.net") or host == "forgecdn.net"):
        raise ValueError("CurseForge did not supply a supported CDN download. Open the project to download it.")
    return url


def installable(file):
    return (file.get("isAvailable") and file.get("downloadUrl") and
            PureWindowsPath(file.get("fileName", "")).suffix.lower() in SUPPORTED | {".zip"})


def linked_file(key, project_id, file_id):
    project = api_get(f"/mods/{project_id}", key)["data"]
    if project.get("id") != project_id or project.get("gameId") != GAME_ID:
        raise ValueError("The linked project is not a Sims 4 resource.")
    if project.get("allowModDistribution") is False:
        return project, None
    file = api_get(f"/mods/{project_id}/files/{file_id}", key)["data"]
    if file.get("id") != file_id or file.get("modId") != project_id or file.get("gameId") != GAME_ID:
        raise ValueError("CurseForge returned a file that does not match the website link.")
    if not installable(file):
        return project, None
    validate_filename(file["fileName"])
    asset_url(file["downloadUrl"])
    return project, file


def latest_file(project):
    if project.get("allowModDistribution") is False:
        return None
    main = project.get("mainFileId")
    files = sorted(project.get("latestFiles", []), key=lambda file: (
        file["id"] != main, file.get("releaseType", 1) != 1, -file["id"]))
    return next((file for file in files if installable(file)), None)


def download(file, folder, progress, organize, cancel):
    name = file["fileName"]
    validate_filename(name)
    if PureWindowsPath(name).suffix.lower() not in SUPPORTED | {".zip"}:
        raise ValueError("CurseForge file format is unsupported. Import an extracted Sims 4 file instead.")
    if cancel.is_set():
        raise CancelledError()
    root = Path(folder).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="curseforge-", dir=root) as temporary:
        staged = Path(temporary) / name
        with requests.get(asset_url(file["downloadUrl"]), stream=True, allow_redirects=False,
                          timeout=(8, 30)) as response:
            if response.status_code != 200:
                raise ValueError(f"CurseForge download returned HTTP {response.status_code}.")
            total = file.get("fileLength") or 0
            received = 0
            last_update = 0
            with staged.open("xb") as output:
                for chunk in response.iter_content(256 * 1024):
                    if cancel.is_set():
                        raise CancelledError()
                    output.write(chunk)
                    received += len(chunk)
                    now = monotonic()
                    if now - last_update >= 0.25:
                        progress(name, received, total)
                        last_update = now
            if not received or (total and received != total):
                raise ValueError("CurseForge download was incomplete.")
        if cancel.is_set():
            raise CancelledError()
        category = getDownloadCategory(str(staged))
        destination = root.joinpath(*category) if organize else root
        if destination.resolve() != destination:
            raise ValueError("The download destination is a filesystem link.")
        destination.mkdir(parents=True, exist_ok=True)
        path = move_with_unique_name(staged, destination / name)
    return dict(path=str(path), status="Complete", detail="Downloaded", size=received, category=" / ".join(category))
