"""Qt-facing state controller. Workers return results; only the GUI thread saves state."""
from collections import defaultdict
from concurrent.futures import CancelledError, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event
from time import monotonic
from uuid import uuid4
import errno
import os
import shutil
import stat
import sys

import requests
from PySide6.QtCore import QObject, Qt, Signal, Slot

from config import CONFIG, CURRENT_DIR, PROJECT_DIR
import curseforge
from game_recovery import backup_content, read_patch
from desktop_data import fetch_item, inspect_item, parse_url, save_json
from download_organizer import getDownloadCategory, MOD_EXTENSIONS
from exceptions import InvalidURL
from logger import logger
from profile_backups import ProfileBackups, read_state
from sims_install import digest, install, install_all, install_plan, installed_path, verify_record, TRAY_EXTENSIONS
from windows_folders import app_data, default_downloads, detect_game

VERSION = "2.1.1"
RELEASES = "https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases"
FROZEN = getattr(sys, "frozen", False)
DATA_DIR = app_data() if FROZEN else Path(PROJECT_DIR)
SESSION_DIR = DATA_DIR if FROZEN else Path(CURRENT_DIR)
STATE_PATH = DATA_DIR / "desktop-state.json"
WAITING = {"New", "Review", "Queued", "Paused", "Download failed", "Cancelled"}
LOOKUP = {"New", "Lookup failed", "VIP only"}
BUSY = {"Checking", "Downloading"}
LABELS = {
    "New": "Waiting", "Review": "Ready to queue", "Queued": "Waiting",
    "Checking": "Reviewing", "Complete": "Completed", "Download failed": "Failed",
    "Lookup failed": "Requires attention", "VIP only": "Requires attention",
}


def timestamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def size_label(size):
    if size is None:
        return "—"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def settings_defaults():
    return dict(downloads=str(default_downloads(CONFIG["downloadDirectory"])),
                workers=CONFIG["maxActiveDownloads"], organize=CONFIG.get("organizeDownloads", True),
                watch=False, attempts=3, dependencies=True, notifications=True, auto_scan=True,
                duplicates=True, backup_enabled=False, backup=str(DATA_DIR / "Backups"),
                website_links=False, install_location="", mods="", accent="#A996FF", animations=True, density="Comfortable")


def release_info():
    with requests.get(
        "https://api.github.com/repos/creatorstudios0/The-Sims-Resource-Downloader/releases/latest",
        timeout=(5, 10), headers={"Accept": "application/vnd.github+json"},
    ) as response:
        response.raise_for_status()
        return response.json().get("tag_name") or "Unknown version"


def scan_files(mods, items, batches, find_duplicates, tray=None):
    """Observe the disk without mutating user data or following directory links."""
    paths = {}
    def by_path(path):
        return os.path.normcase(str(path))

    for folder, extensions in ((mods, MOD_EXTENSIONS), (tray, TRAY_EXTENSIONS)):
        if not folder or not Path(folder).is_dir():
            continue
        for directory, children, files in os.walk(folder):
            children[:] = [name for name in children if not (
                (Path(directory) / name).is_symlink() or
                getattr(Path(directory) / name, "is_junction", lambda: False)()
            )]
            for filename in files:
                file = Path(directory) / filename
                original = file.with_suffix("") if file.suffix.lower() == ".disabled" else file
                if original.suffix.lower() in extensions:
                    paths[by_path(file)] = (file, original, None)
    for batch in batches.values():
        for record in batch["files"]:
            file = installed_path(record)
            paths[by_path(file)] = (file, Path(record["path"]), batch["item"])
    disk = {}
    candidates = defaultdict(list)
    missing = storage = mods_count = 0
    for key, (file, original, item_key) in paths.items():
        try:
            if file.is_symlink():
                raise OSError("File is a link")
            info = file.stat()
            if not stat.S_ISREG(info.st_mode):
                raise OSError("Not a regular file")
            size = info.st_size
        except OSError:
            size = None
            missing += 1
        is_mod = original.suffix.lower() in MOD_EXTENSIONS
        if size is not None:
            storage += size
            mods_count += is_mod
            if is_mod:
                candidates[size].append((key, file))
        extension = original.suffix.lower()
        category = "Script Mods" if extension == ".ts4script" else "Package Mods" if is_mod else "Tray Files"
        disk[key] = dict(path=str(file), name=original.name, size=size, disabled=file != original,
                         item=item_key, category=category, inferred=True,
                         date=datetime.fromtimestamp(info.st_mtime).date().isoformat() if size is not None else "")
    files_present = {}
    for key, item in items.items():
        if item.get("path") and item.get("status") == "Complete":
            try:
                path = Path(item["path"])
                if path.is_file():
                    files_present[key] = path.stat().st_size
            except OSError:
                continue
    absent = {dep for item in items.values() for dep in item.get("requires", []) if dep not in files_present}
    missing += sum(bool(item.get("path")) and key not in files_present for key, item in items.items()
                   if item.get("status") == "Complete")
    duplicates = collisions = 0
    names = defaultdict(int)
    for record in disk.values():
        if record["size"] is not None:
            names[record["name"].casefold()] += 1
    collisions = sum(count > 1 for count in names.values())
    if find_duplicates:
        for group in candidates.values():
            if len(group) < 2:
                continue
            hashes = defaultdict(int)
            for _, path in group:
                try:
                    hashes[digest(path)] += 1
                except OSError:
                    continue
            duplicates += sum(count - 1 for count in hashes.values() if count > 1)
    return disk, files_present, dict(mods=mods_count, storage=storage, missing=missing, dependencies=len(absent),
                      duplicates=duplicates if find_duplicates else None, collisions=collisions)


def remove_partials(downloads):
    folder = Path(downloads) / ".partial"
    if folder.is_symlink() or getattr(folder, "is_junction", lambda: False)():
        raise ValueError("The staging folder points outside the download directory.")
    if not folder.is_dir():
        return 0
    count = 0
    for path in folder.iterdir():
        if path.stem.isdecimal() and path.suffix in {".part", ".etag"} and path.is_file() and not path.is_symlink():
            path.unlink()
            count += 1
    return count


def failure_message(error):
    if isinstance(error, requests.Timeout):
        return "Network timeout. Retry when the connection is available."
    response = getattr(error, "response", None)
    if response is not None:
        status = response.status_code
        return {401: "Authentication required.", 403: "TSR denied access.",
                404: "The file is unavailable.", 429: "TSR rate limit. Wait before retrying."}.get(status, f"TSR returned HTTP {status}.")
    if isinstance(error, requests.RequestException):
        return "Network transfer failed. Check your connection and retry."
    if isinstance(error, PermissionError):
        return "Permission denied. Check access to the selected folders."
    if getattr(error, "errno", None) == errno.ENOSPC:
        return "There is insufficient disk space."
    return str(error)[:400] if str(error) and "https://" not in str(error) else type(error).__name__


def rename_managed(record):
    """Quarantine a managed file safely, retrying transient Windows sharing locks.

    An in-flight read-only inventory scan may have a temporary read handle open.
    Do not replace a destination that appeared while waiting for that handle.
    """
    from time import sleep

    original = Path(record["path"])
    target = original if record["disabled"] else original.with_name(original.name + ".disabled")
    for attempt in range(10):
        try:
            current = verify_record(record)
            if os.path.lexists(target):
                raise FileExistsError(f"Target already exists: {target}")
            current.rename(target)
            return str(target)
        except PermissionError:
            if attempt == 9:
                raise
            sleep(0.12)


def remove_managed(records, backup=None):
    removed, indices, errors = [], [], []
    for index, record in enumerate(records):
        try:
            path = verify_record(record)
            if backup:
                backup.mkdir(parents=True, exist_ok=True)
                backup_file = backup / path.name
                temporary = backup / (uuid4().hex + ".tmp")
                try:
                    with path.open("rb") as source, temporary.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    temporary.rename(backup_file)
                finally:
                    temporary.unlink(missing_ok=True)
            path.unlink()
            removed.append(str(path))
            indices.append(index)
        except (OSError, ValueError) as error:
            errors.append(f"{Path(record['path']).name}: {failure_message(error)}")
    return removed, indices, errors


class LibraryService(QObject):
    changed = Signal()
    transfer_changed = Signal(str)
    download_ready = Signal(str)
    notice = Signal(str, str)
    job_done = Signal(str, object)
    completed = Signal(str, str, object)
    progress = Signal(str, str, object, object)

    def __init__(self, state_path=STATE_PATH):
        super().__init__()
        self.path = Path(state_path)
        self.backups = ProfileBackups(self.path)
        state, self.recovered = self.backups.load(self.path)
        self.load_state(state)
        self.backup_error = None
        self.curseforge_key = os.environ.get("CURSEFORGE_API_KEY", "").strip()
        self.active = {}
        self.lookups = set()
        self.lookup_previous = {}
        self.jobs = set()
        self.progress_data = {}
        self.disk = {}
        self.library_present = {}
        self.scanned_sources = {}
        self.patch_version = None
        self.health = {}
        self.paused = True
        self.closing = False
        self.scan_again = False
        self.transfer_pool = ThreadPoolExecutor(max_workers=10)
        self.workers = ThreadPoolExecutor(max_workers=4)
        self.completed.connect(self.finish, Qt.ConnectionType.QueuedConnection)
        self.progress.connect(self.record_progress, Qt.ConnectionType.QueuedConnection)
        if "game" not in self.state:
            detected = detect_game()
            if detected:
                self.state["game"] = str(detected)
        if not self.state.get("legacyImported"):
            legacy = SESSION_DIR / "urls.txt"
            if legacy.is_file():
                self.import_text(legacy.read_text(encoding="utf-8-sig"), lookup=False)
            self.state["legacyImported"] = True
        self.save()

    def load_state(self, state):
        self.state = state
        self.settings = self.state.setdefault("settings", {})
        for key, value in settings_defaults().items():
            self.settings.setdefault(key, value)
        self.items = self.state.setdefault("items", {})
        self.batches = self.state.setdefault("installs", {})
        self.history = self.state.setdefault("history", [])
        self.profiles = self.state.setdefault("profiles", {})
        self.state.setdefault("queueHidden", [])
        for item in self.items.values():
            if item["status"] == "Downloading":
                item["status"] = "Paused"
            elif item["status"] == "Checking":
                item["status"] = "New"

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        save_json(self.path, self.state)
        try:
            self.backups.save(self.state)
            self.backup_error = None
        except OSError as error:
            message = f"Profile autosave failed. {failure_message(error)}"
            if message != self.backup_error:
                self.backup_error = message
                logger.warning(message)
                self.notice.emit("warning", message)

    def restore_backup(self, snapshot):
        if self.jobs or self.active or self.lookups or self.closing:
            raise ValueError("Wait for downloads and file operations to finish before restoring a profile.")
        state = read_state(snapshot)
        state.setdefault("settings", {})["website_links"] = self.settings["website_links"]
        self.backups.save(self.state)
        save_json(self.path, state)
        self.load_state(state)
        for item in self.items.values():
            item.pop("install_requested", None)
        self.paused = True
        self.disk, self.library_present, self.health = {}, {}, {}
        self.scanned_sources.clear()
        self.publish()
        self.scan()
        self.check_patch()
        logger.info("Restored profile backup %s", snapshot.name)

    def publish(self, persist=True):
        if persist:
            self.save()
        self.changed.emit()

    def submit(self, pool, action, key, fn, *args):
        future = pool.submit(fn, *args)
        future.add_done_callback(lambda done: self.completed.emit(action, key, done))

    def job(self, name, fn, *args):
        if name in self.jobs or self.closing:
            return
        self.jobs.add(name)
        if not name.startswith("thumbnail:"):
            logger.info("Started %s", name)
        self.submit(self.workers, "job", name, fn, *args)
        self.changed.emit()

    def import_text(self, text, lookup=True):
        result = []
        for raw in text.split():
            try:
                url = parse_url(raw)
            except (InvalidURL, ValueError):
                result.append((raw, "Invalid link · use an HTTPS TSR item URL"))
                continue
            key = str(url.itemId)
            existing = self.items.get(key)
            if existing and existing["status"] == "Complete" and not Path(existing.get("path", "")).is_file():
                existing.update(status="New", detail="The previous file is missing")
            elif existing:
                result.append((raw, "Duplicate · " + existing["name"]))
                continue
            self.items.setdefault(key, dict(url=url.url, name=f"TSR item {key}", creator="",
                                            requires=[], status="New", detail="", added=timestamp()))
            if lookup:
                self.lookup(key)
            result.append((raw, "Added for review"))
        self.publish()
        return result

    def lookup(self, key, force_dependencies=False):
        if key in self.lookups or key in self.active or self.closing or self.items[key].get("source") == "CurseForge":
            return
        self.lookups.add(key)
        previous = self.items[key]["status"]
        self.lookup_previous[key] = previous
        if not force_dependencies or previous in LOOKUP | {"Review"}:
            self.items[key]["status"] = "Checking"
        self.submit(self.workers, "lookup", key, inspect_item, self.items[key]["url"],
                    force_dependencies or self.settings["dependencies"])

    def queue(self, keys):
        for key in keys:
            if self.items[key]["status"] in WAITING:
                self.items[key].update(status="Queued", detail="")
                self.progress_data.pop(key, None)
        self.paused = False
        self.pump()
        self.publish()

    def retry(self, keys):
        transfer = []
        for key in keys:
            status = self.items[key]["status"]
            if status in LOOKUP:
                self.lookup(key)
            elif status in {"Download failed", "Cancelled", "Paused"}:
                transfer.append(key)
        if transfer:
            self.queue(transfer)
        else:
            self.publish()

    def pump(self):
        if self.paused or self.closing or "cleanup" in self.jobs:
            return
        for key, item in self.items.items():
            if len(self.active) >= self.settings["workers"]:
                break
            if item["status"] != "Queued" or key in self.lookups:
                continue
            token = Event()
            self.active[key] = token
            logger.info("Downloading %s", item["name"])
            progress = lambda *args, item_key=key: self.progress.emit(item_key, *args)
            if item.get("source") == "CurseForge":
                item.update(status="Downloading", detail="Connecting to CurseForge")
                self.submit(self.transfer_pool, "download", key, curseforge.download, item["curseforge_file"],
                            self.settings["downloads"], progress, self.settings["organize"], token)
            else:
                session_file = SESSION_DIR / "session"
                try:
                    session = session_file.read_text(encoding="utf-8-sig").strip() if session_file.is_file() else ""
                except OSError:
                    session = ""
                item.update(status="Downloading", detail="Requesting TSR ticket")
                self.submit(self.transfer_pool, "download", key, fetch_item, item["url"], session,
                            self.settings["downloads"], progress, self.settings["organize"], token, self.settings["attempts"])

    def set_paused(self, value):
        self.paused = value
        if not value:
            for item in self.items.values():
                if item["status"] == "Paused":
                    item["status"] = "Queued"
            self.pump()
        self.publish()

    def cancel(self, keys):
        for key in keys:
            if key in self.active:
                self.active[key].set()
                self.items[key]["detail"] = "Cancelling…"
            elif self.items[key]["status"] in WAITING:
                self.items[key].update(status="Cancelled", detail="Cancelled")
        self.publish()

    @Slot(str, str, object, object)
    def record_progress(self, key, label, received, total):
        if key not in self.active or self.active[key].is_set():
            return
        prior = self.progress_data.get(key, {})
        now = monotonic()
        speed = None
        if received and prior.get("received", 0) and now > prior["time"]:
            rate = (received - prior["received"]) / (now - prior["time"])
            if rate > 0:
                speed = rate if not prior.get("speed") else 0.25 * rate + 0.75 * prior["speed"]
        self.progress_data[key] = dict(received=received, total=total, time=now, speed=speed)
        self.items[key]["detail"] = label
        if total:
            self.items[key]["size"] = total
        self.transfer_changed.emit(key)

    @Slot(str, str, object)
    def finish(self, action, key, future):
        value = None
        error = None
        try:
            value = future.result()
        except CancelledError:
            error = "Cancelled"
        except Exception as exc:
            error = failure_message(exc)
            if getattr(getattr(exc, "response", None), "status_code", None) == 429:
                self.paused = True
            logger.warning("%s failed: %s", action, error)
        if action == "job":
            self.jobs.discard(key)
            if key == "scan" and value is not None:
                self.disk, self.library_present, self.health = value
                self.scanned_sources = self.scan_sources
                logger.info("Library refreshed: %d mods, %d missing or unreadable files", self.health["mods"], self.health["missing"])
            elif error is None and not key.startswith("thumbnail:"):
                logger.info("Finished %s", key)
            if key == "cleanup":
                self.pump()
                self.save()
            if key == "patch-check" and value is not None:
                self.commit_patch(*value)
            elif key == "content-backup" and value is not None:
                self.state["lastContentBackup"] = value
                self.save()
            if key.startswith("install:"):
                self.commit_install(key.split(":", 1)[1], value, error)
            elif key.startswith("rename:") and value is not None:
                _, batch_key, index = key.split(":")
                self.commit_rename(batch_key, int(index), value)
            elif key.startswith("uninstall:") and value is not None:
                self.commit_undo(key.split(":", 1)[1], value)
            self.job_done.emit(key, (value, error))
            self.pump_installs()
            self.changed.emit()
            if key == "scan" and self.scan_again:
                self.scan_again = False
                self.scan()
            return
        item = self.items[key]
        if action == "lookup":
            self.lookups.discard(key)
            previous = self.lookup_previous.pop(key)
            if item["status"] != "Checking":
                if value:
                    item["requires"] = value["requires"]
                    if value.get("thumbnail"):
                        item["thumbnail"] = value["thumbnail"]
                elif error != "Cancelled":
                    self.notice.emit("warning", error)
            elif error == "Cancelled":
                item["status"] = previous
            elif value:
                item.update(value)
            else:
                item.update(status="Lookup failed", detail=error)
            if item.get("install_requested") and item["status"] == "Review":
                item.update(status="Queued", detail="")
        else:
            self.active.pop(key, None)
            self.progress_data.pop(key, None)
            if value:
                item.update(value)
                if item["name"] == f"TSR item {key}":
                    item["name"] = Path(item["path"]).stem
                item.update(added=item.get("added") or timestamp(), inferred=True)
                logger.info("Downloaded %s", item["name"])
                self.notice.emit("success", f"Downloaded {item['name']}")
            else:
                item.update(status="Cancelled" if error == "Cancelled" else "Download failed", detail=error)
                if error != "Cancelled":
                    self.notice.emit("error", f"{item['name']} · {error}")
        self.pump()
        self.publish()
        self.pump_installs()
        if action == "download" and value:
            self.download_ready.emit(key)
        if action == "download" or action == "lookup":
            self.auto_scan()

    def game(self):
        value = self.state.get("game")
        return Path(value) if value else None

    def mods(self):
        return self.settings["mods"] or str(self.game() / "Mods" if self.game() else "")

    def patch_versions(self):
        game = self.game()
        current = self.patch_version[1] if self.patch_version and self.patch_version[0] == str(game) else None
        reviewed = self.state.get("reviewedGameVersions", {}).get(str(game))
        return current, reviewed

    def check_patch(self):
        if self.game():
            self.job("patch-check", read_patch, self.game())

    def commit_patch(self, folder, version):
        if folder != str(self.game()):
            self.check_patch()
            return
        self.patch_version = folder, version
        reviewed = self.state.setdefault("reviewedGameVersions", {})
        if version and folder not in reviewed:
            reviewed[folder] = version
            self.save()

    def mark_patch_reviewed(self):
        version, previous = self.patch_versions()
        if version and version != previous:
            self.state.setdefault("reviewedGameVersions", {})[str(self.game())] = version
            self.publish()

    def create_content_backup(self, target):
        if self.mutating_files():
            raise ValueError("Wait for active file operations to finish before creating a backup.")
        game, _ = self.install_destination()
        self.job("content-backup", backup_content, game, self.mods(), target)

    def auto_scan(self):
        if self.settings["auto_scan"]:
            self.scan()

    def scan(self):
        if self.closing:
            return
        if "scan" in self.jobs:
            self.scan_again = True
            return
        items = {key: dict(item) for key, item in self.items.items()}
        self.scan_sources = {key: item["path"] for key, item in items.items()
                             if item["status"] == "Complete" and item.get("path")}
        batches = {key: dict(item=batch["item"], files=[dict(record) for record in batch["files"]])
                   for key, batch in self.batches.items()}
        tray = str(self.game() / "Tray") if self.game() else None
        self.job("scan", scan_files, self.mods(), items, batches, self.settings["duplicates"], tray)

    def add_local(self, paths, install_now=False):
        if install_now:
            self.install_destination()
        known = {os.path.normcase(item["path"]): key for key, item in self.items.items() if item.get("path")}
        sources = [(Path(path).resolve(), Path(path).stat().st_size) for path in paths]
        for path, size in sources:
            key = known.get(os.path.normcase(str(path)))
            if key is None:
                key = uuid4().hex
                self.items[key] = dict(name=path.name, creator="", status="Complete", path=str(path),
                                       category=" / ".join(getDownloadCategory(str(path))), inferred=True,
                                       size=size, added=timestamp())
                known[os.path.normcase(str(path))] = key
            if install_now:
                self.items[key]["install_requested"] = True
        self.publish()
        self.pump_installs()
        self.auto_scan()

    def install_destination(self):
        game = self.game()
        if not game or not game.is_dir():
            raise ValueError("Choose your Sims 4 user data folder in Settings before installing.")
        return game, self.settings["mods"] or None

    def request_tsr_install(self, link):
        self.install_destination()
        url = parse_url(link)
        key = str(url.itemId)
        self.import_text(url.url, lookup=False)
        item = self.items[key]
        if item["status"] == "VIP only":
            raise ValueError("This resource requires access through The Sims Resource website.")
        if item["status"] == "Lookup failed":
            item["status"] = "New"
        item["install_requested"] = True
        if item["status"] != "Complete":
            self.queue([key])
        else:
            self.publish()
            self.pump_installs()

    def request_curseforge_install(self, project):
        self.install_destination()
        file = curseforge.latest_file(project)
        if not file:
            raise ValueError("Open the CurseForge project to download this resource.")
        self.queue_curseforge_file(project, file, install_now=True)

    def queue_curseforge_file(self, project, file, install_now=False):
        self.install_destination()
        key = f"cf-{project['id']}-{file['id']}"
        item = self.items.setdefault(key, dict(name=project["name"], source="CurseForge",
                                              url=curseforge.web_url(project.get("links", {}).get("websiteUrl")),
                                              creator=", ".join(author["name"] for author in project.get("authors", [])),
                                              requires=[], status="New", added=timestamp()))
        item.update(curseforge_file={field: file[field] for field in ("fileName", "downloadUrl", "fileLength") if field in file},
                    install_requested=install_now)
        if item["status"] == "Complete" and not Path(item.get("path", "")).is_file():
            item["status"] = "New"
        if item["status"] != "Complete":
            self.queue([key])
        else:
            self.publish()
            self.pump_installs()

        return key

    def pump_installs(self):
        if self.closing or self.mutating_files():
            return
        for key, item in self.items.items():
            if item["status"] == "Complete" and item.get("install_requested"):
                game = self.game()
                if not game:
                    return
                self.job("install:" + key, install_all, item["path"], game, self.settings["mods"] or None)
                return

    def history_event(self, key, action, result, paths, error="", when=None):
        item = self.items.get(key, {})
        self.history.append(dict(item=key, name=item.get("name") or (Path(paths[0]).name if paths else key),
                                 creator=item.get("creator", ""), action=action, result=result,
                                 paths=list(paths), error=error, date=when or timestamp()))

    def history_rows(self):
        rows = list(self.history)
        recorded = {event.get("batch") for event in rows if event["action"] == "Install"}
        for batch_id, batch in self.batches.items():
            if batch_id not in recorded:
                item = self.items.get(batch["item"], {})
                rows.append(dict(item=batch["item"], name=item.get("name", batch["item"]),
                                 creator=item.get("creator", ""), action="Install", result="Completed",
                                 paths=[rec["path"] for rec in batch["files"]], error="",
                                 date=batch.get("date", ""), batch=batch_id))
        return sorted(rows, key=lambda row: row["date"], reverse=True)

    def install_preview(self, key):
        game = self.game()
        if not game:
            raise ValueError("Choose your Sims 4 user data folder in Settings.")
        return install_plan(self.items[key]["path"], game, self.settings["mods"] or None)

    def install_selected(self, key, plan):
        if self.mutating_files():
            return
        self.job("install:" + key, install, self.items[key]["path"], plan)

    def commit_install(self, key, records, error):
        self.items[key].pop("install_requested", None)
        if records:
            batch_id = uuid4().hex
            self.batches[batch_id] = dict(item=key, files=records, date=timestamp())
            self.history_event(key, "Install", "Completed", [record["path"] for record in records])
            self.history[-1]["batch"] = batch_id
        elif error:
            self.history_event(key, "Install", "Failed", [], error)
        else:
            self.history_event(key, "Install", "Skipped", [], "The destination files already exist.")
        self.publish()
        self.scan()

    def toggle_managed(self, batch, index):
        if self.mutating_files():
            return
        record = self.batches[batch]["files"][index]
        self.job(f"rename:{batch}:{index}", rename_managed, dict(record))

    def commit_rename(self, batch, index, target):
        entry = self.batches[batch]
        record = entry["files"][index]
        record["disabled"] = not record["disabled"]
        self.history_event(entry["item"], "Quarantine" if record["disabled"] else "Restore", "Completed", [target])
        self.publish()
        self.scan()

    def toggle_scanned(self, key):
        record = self.disk[key]
        original = Path(record["path"])
        mods = Path(self.mods()).resolve()
        if (not original.is_file() or original.is_symlink()
                or not original.resolve().is_relative_to(mods) or not original.parent.resolve().is_relative_to(mods)):
            raise ValueError("File is missing or is outside the configured Mods folder.")
        target = original.with_suffix("") if record["disabled"] else original.with_name(original.name + ".disabled")
        if target.exists() or target.is_symlink():
            raise FileExistsError(target)
        original.rename(target)
        self.history_event("", "Restore" if record["disabled"] else "Quarantine", "Completed", [str(target)])
        self.publish()
        self.scan()

    def undo(self, batch_key):
        if self.mutating_files():
            return
        batch = self.batches[batch_key]
        backup = None
        if self.settings["backup_enabled"]:
            backup = Path(self.settings["backup"]) / batch_key / uuid4().hex
        self.job("uninstall:" + batch_key, remove_managed, [dict(record) for record in batch["files"]], backup)

    def commit_undo(self, batch_key, value):
        removed, indices, errors = value
        batch = self.batches[batch_key]
        if not any(row.get("batch") == batch_key for row in self.history):
            self.history_event(batch["item"], "Install", "Completed", [record["path"] for record in batch["files"]])
            self.history[-1]["date"] = batch.get("date", "")
            self.history[-1]["batch"] = batch_key
        for index in reversed(indices):
            del batch["files"][index]
        if not batch["files"]:
            del self.batches[batch_key]
        result = "Partial" if errors and removed else "Failed" if errors else "Completed"
        self.history_event(batch["item"], "Uninstall", result, removed, "\n".join(errors))
        self.publish()
        self.scan()

    def mutating_files(self):
        return "content-backup" in self.jobs or any(name.startswith(("install:", "rename:", "uninstall:"))
                                                    for name in self.jobs)

    def update_settings(self, game, settings):
        if game:
            self.state["game"] = game
        else:
            self.state.pop("game", None)
        self.settings.update(settings)
        self.pump()
        self.publish()
        self.pump_installs()
        self.auto_scan()
        self.check_patch()

    def clear_partials(self):
        if not self.active:
            self.job("cleanup", remove_partials, self.settings["downloads"])

    def request_close(self):
        self.closing = True
        self.paused = True
        for token in self.active.values():
            token.set()
        self.workers.shutdown(wait=False, cancel_futures=True)

    def shutdown(self):
        self.workers.shutdown(wait=True, cancel_futures=True)
        self.transfer_pool.shutdown(wait=True, cancel_futures=True)
