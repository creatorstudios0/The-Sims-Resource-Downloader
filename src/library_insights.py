"""Read-only Sims 4 library audit shared by CreatorStudios desktop and console.

Never mutates, removes, or follows symlinks in game folders. Only candidate files
with identical byte sizes are hashed to detect byte-for-byte duplicates.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import csv
import json
import os

from game_recovery import folder_link

MOD_TYPES = {".package", ".ts4script"}
TRAY_TYPES = {".trayitem", ".blueprint", ".bpi", ".hhi", ".sgi",
              ".householdbinary", ".room", ".rmi"}
SUPPORTED = MOD_TYPES | TRAY_TYPES
MAX_FILES = 100_000


def _digest(path):
    checksum = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def _is_junction(path):
    try:
        return folder_link(path.lstat())
    except OSError:
        # Let the directory walk report unreadable paths.
        return False


def _kind(name):
    suffix = Path(name).suffix.lower()
    disabled = suffix == ".disabled"
    if disabled:
        suffix = Path(name[:-len(".disabled")]).suffix.lower()
    return suffix, disabled


def scan_inventory(mods, tray=None, max_files=MAX_FILES):
    """Return JSON-serializable inventory with exact hashes for equal-size candidates."""
    if not 1 <= max_files <= MAX_FILES:
        raise ValueError("max_files must be between 1 and 100000")
    roots = [("Mods", Path(mods))] if mods else []
    if tray:
        roots.append(("Tray", Path(tray)))
    records, warnings = [], []
    sizes = defaultdict(list)
    types = Counter()
    bytes_total = 0
    disabled_count = 0
    truncated = False

    def report_walk_error(error):
        warnings.append(f"Cannot scan folder: {error}")

    for label, root in roots:
        if not root.is_dir() or root.is_symlink() or _is_junction(root):
            warnings.append(f"{label} folder is unavailable or unsafe: {root}")
            continue
        for directory, children, files in os.walk(root, followlinks=False, onerror=report_walk_error):
            children[:] = [child for child in children if not (
                (Path(directory) / child).is_symlink() or
                _is_junction(Path(directory) / child))]
            for name in files:
                path = Path(directory) / name
                ext, disabled = _kind(name)
                if ext not in SUPPORTED or path.is_symlink():
                    continue
                if len(records) >= max_files:
                    truncated = True
                    break
                try:
                    stat = path.stat()
                    if not path.is_file():
                        continue
                except OSError as error:
                    warnings.append(f"Cannot inspect {path.name}: {error}")
                    continue
                record = {
                    "section": label, "relative_path": str(path.relative_to(root)),
                    "path": str(path), "bytes": stat.st_size,
                    "extension": ext, "disabled": disabled,
                }
                sizes[stat.st_size].append(record)
                records.append(record)
                types[ext] += 1
                bytes_total += stat.st_size
                disabled_count += int(disabled)
            if truncated:
                break
        if truncated:
            warnings.append(f"Audit stopped at the {max_files:,}-file safety limit")
            break

    duplicates = []
    for same_size in sizes.values():
        if len(same_size) < 2:
            continue
        hashes = defaultdict(list)
        for record in same_size:
            try:
                hashes[_digest(Path(record["path"]))].append(record["path"])
            except OSError as error:
                warnings.append(f"Cannot hash {Path(record['path']).name}: {error}")
        for signature, paths in hashes.items():
            if len(paths) > 1:
                duplicates.append({"sha256": signature, "bytes_per_file": same_size[0]["bytes"],
                                   "paths": sorted(paths)})
    duplicates.sort(key=lambda group: (-len(group["paths"]), group["paths"][0]))
    names = defaultdict(list)
    for record in records:
        names[Path(record["relative_path"]).name.casefold()].append(record["path"])
    collisions = {name: paths for name, paths in names.items() if len(paths) > 1}
    return {
        "format": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": {label: str(path) for label, path in roots},
        "total_files": len(records), "total_bytes": bytes_total,
        "disabled_files": disabled_count, "types": dict(sorted(types.items())),
        "duplicate_groups": duplicates, "shared_filenames": collisions,
        "warnings": warnings, "truncated": truncated,
        "files": records,
    }


def write_report(report, destination):
    """Export JSON or CSV; the caller chooses the output file explicitly."""
    destination = Path(destination)
    if destination.suffix.lower() not in {".json", ".csv"}:
        raise ValueError("Choose a .json or .csv report filename")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        if destination.suffix.lower() == ".json":
            with temporary.open("w", encoding="utf-8") as output:
                json.dump(report, output, indent=2, ensure_ascii=False)
                output.write("\n")
        else:
            with temporary.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=[
                    "section", "relative_path", "path", "bytes", "extension", "disabled"])
                writer.writeheader()
                writer.writerows(report["files"])
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return str(destination)


def audit_to_file(mods, tray, destination):
    """Run in a worker thread to keep the desktop interface responsive."""
    report = scan_inventory(mods, tray)
    return report, write_report(report, destination)


def format_summary(report):
    groups = report["duplicate_groups"]
    recoverable = sum((len(group["paths"]) - 1) * group["bytes_per_file"] for group in groups)
    return (f"{report['total_files']:,} files | "
            f"{report['disabled_files']:,} disabled | "
            f"{len(groups):,} exact duplicate groups | "
            f"{recoverable / (1024 * 1024):.1f} MiB in additional copies | "
            f"{len(report['warnings'])} warnings")
