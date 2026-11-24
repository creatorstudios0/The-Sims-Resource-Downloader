"""Preview and install supported Sims 4 files without overwriting game files."""
from contextlib import ExitStack
from hashlib import file_digest
from pathlib import Path, PureWindowsPath
from tempfile import NamedTemporaryFile
import os
import re
import shutil
import zipfile

from download_organizer import MOD_EXTENSIONS, TRAY_EXTENSIONS

SUPPORTED = MOD_EXTENSIONS | TRAY_EXTENSIONS
MAX_ARCHIVE_FILES = 10_000
MAX_ARCHIVE_FILE_BYTES = 1_000_000_000
MAX_ARCHIVE_TOTAL_BYTES = 2_000_000_000


def digest(path):
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def validate_filename(name):
    if (not name or name in {".", ".."} or name.rstrip(" .") != name
            or any(ord(char) < 32 or char in '<>"|?*:\\/' for char in name)
            or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])", name.split(".")[0].rstrip().upper())):
        raise ValueError(f"Invalid Windows filename: {name}")


def install_plan(source, game, mods=None):
    source, game = Path(source), Path(game)
    if not game.is_dir():
        raise ValueError("Select your existing The Sims 4 user data folder first.")
    if source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            members = [
                (entry, entry.file_size)
                for entry in archive.infolist()
                if not entry.is_dir() and Path(entry.filename).suffix.lower() in SUPPORTED
            ]
        if len(members) > MAX_ARCHIVE_FILES:
            raise ValueError("Archive contains too many supported Sims 4 files.")
        if any(size > MAX_ARCHIVE_FILE_BYTES for _, size in members):
            raise ValueError("Archive contains a supported file that is too large to install.")
        if sum(size for _, size in members) > MAX_ARCHIVE_TOTAL_BYTES:
            raise ValueError("Archive contains too much supported content to install safely.")
    elif source.suffix.lower() in SUPPORTED:
        members = [(None, source.stat().st_size)]
    else:
        raise ValueError("Install supports ZIP, package, script and Tray files.")
    if not members:
        raise ValueError("No supported Sims 4 files were found.")
    plan = []
    seen = set()
    for member, size in members:
        name = PureWindowsPath(member.filename).name if member else source.name
        validate_filename(name)
        folder = "Tray" if Path(name).suffix.lower() in TRAY_EXTENSIONS else "Mods"
        root = Path(mods).resolve() if mods and folder == "Mods" else game.resolve() / folder
        target = root / name
        if target.parent.resolve() != root:
            raise ValueError(f"Game subfolder points outside the selected folder: {folder}")
        key = str(target).casefold()
        conflict = key in seen or os.path.lexists(target) or os.path.lexists(target.with_name(name + ".disabled"))
        seen.add(key)
        plan.append((member, target, size, conflict))
    return plan


def install(source, plan):
    installed = []
    try:
        with ExitStack() as stack:
            archive = stack.enter_context(zipfile.ZipFile(source)) if Path(source).suffix.lower() == ".zip" else None
            for member, target, size, conflict in plan:
                if conflict:
                    continue
                if target.parent.resolve() != target.parent.absolute():
                    raise ValueError(f"Game subfolder changed: {target.parent}")
                target.parent.mkdir(exist_ok=True)
                temporary = None
                try:
                    with (archive.open(member) if archive else Path(source).open("rb")) as stream:
                        with NamedTemporaryFile(dir=target.parent, suffix=".tmp", delete=False) as output:
                            temporary = Path(output.name)
                            shutil.copyfileobj(stream, output)
                            if output.tell() != size:
                                raise OSError(f"Incomplete copy: {target.name}")
                    signature = digest(temporary)
                    if os.name == "nt":
                        temporary.rename(target)
                    else:
                        os.link(temporary, target)
                    installed.append({"path": str(target), "hash": signature, "disabled": False})
                finally:
                    if temporary:
                        temporary.unlink(missing_ok=True)
    except BaseException:
        for record in installed:
            target = Path(record["path"])
            if target.is_file() and digest(target) == record["hash"]:
                target.unlink()
        raise
    return installed


def install_all(source, game, mods):
    return install(source, install_plan(source, game, mods))


def installed_path(record):
    path = Path(record["path"])
    return path.with_name(path.name + ".disabled") if record["disabled"] else path


def verify_record(record):
    path = installed_path(record)
    if (path.parent.resolve() != path.parent.absolute() or path.is_symlink()
            or not path.is_file() or digest(path) != record["hash"]):
        raise ValueError(f"Installed file is missing or changed: {path.name}")
    return path
