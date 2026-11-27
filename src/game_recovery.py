"""Read the installed game version and export local content recovery ZIPs."""
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
import json
import os
import re
import shutil
import stat
import zipfile


VERSION_PATTERN = re.compile(r"[0-9]{1,6}(?:\.[0-9]{1,6}){2,3}")


def game_version(game):
    path = Path(game) / "GameVersion.txt"
    try:
        with path.open("rb") as source:
            raw = source.read(256)
    except FileNotFoundError:
        return None
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8-sig", errors="replace").replace("\x00", "")
    version = text.strip()
    return version if VERSION_PATTERN.fullmatch(version) else None


def read_patch(game):
    return str(game), game_version(game)


def folder_link(info):
    return getattr(info, "st_reparse_tag", 0) in (0xA0000003, 0xA000000C)


def throw_walk_error(error):
    raise error


def backup_content(game, mods_folder, target):
    target = Path(target)
    target = target.parent.resolve() / target.name
    if target.suffix.lower() != ".zip":
        raise ValueError("Choose a .zip file for the content backup.")
    if os.path.lexists(target):
        raise FileExistsError("A backup already exists at that path. Choose a new filename.")
    configured = {"Mods": Path(mods_folder), "Tray": Path(game).resolve() / "Tray"}
    roots = {}
    for label, folder in configured.items():
        try:
            info = folder.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or folder_link(info):
            raise ValueError(f"The {folder.name} folder is a filesystem link. Select the real folder before backing up.")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"The {label} path is not a folder: {folder}")
        roots[label] = folder.resolve()
    if any(target.is_relative_to(root) for root in roots.values()):
        raise ValueError("Save the backup outside your Mods and Tray folders.")
    if not roots:
        raise ValueError("The selected game folder has no Mods or Tray folder to back up.")

    try:
        version = game_version(game)
    except OSError:
        version = None
    created = datetime.now().astimezone().isoformat(timespec="seconds")
    copied = skipped = 0
    temporary = None
    try:
        with NamedTemporaryFile(dir=target.parent, prefix=".sims-backup-", suffix=".tmp", delete=False) as staging:
            temporary = Path(staging.name)
            with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
                for label, root in roots.items():
                    for current, directories, filenames in os.walk(root, onerror=throw_walk_error):
                        current = Path(current)
                        if current.resolve() != current:
                            raise OSError("A content folder moved while the backup was running.")
                        relative = (Path(label) / current.relative_to(root)).as_posix()
                        archive.mkdir(relative)
                        allowed = []
                        for name in directories:
                            info = (current / name).lstat()
                            if stat.S_ISDIR(info.st_mode) and not folder_link(info):
                                allowed.append(name)
                            else:
                                skipped += 1
                        directories[:] = allowed
                        for name in filenames:
                            source = current / name
                            before = source.lstat()
                            if not stat.S_ISREG(before.st_mode) or folder_link(before):
                                skipped += 1
                                continue
                            with source.open("rb") as handle:
                                if not os.path.samestat(before, os.fstat(handle.fileno())):
                                    raise OSError(f"File moved while backing up {name}. Retry after closing the game.")
                                with archive.open(f"{relative}/{name}", "w", force_zip64=True) as output:
                                    shutil.copyfileobj(handle, output, 1024 * 1024)
                                after = os.fstat(handle.fileno())
                                if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
                                    raise OSError(f"File changed while backing up {name}. Retry after closing the game.")
                            if not os.path.samestat(before, source.lstat()):
                                raise OSError(f"File moved while backing up {name}. Retry after closing the game.")
                            copied += 1
                archive.writestr("backup-info.json", json.dumps({
                    "format": 1, "created": created, "game_version": version, "files": copied, "skipped_links": skipped,
                }, indent=2))
            staging.flush()
            os.fsync(staging.fileno())
        if os.name == "nt":
            temporary.rename(target)
        else:
            os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return dict(path=str(target), date=created, files=copied, skipped=skipped, version=version)
