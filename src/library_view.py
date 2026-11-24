"""Search and sort the existing library projection without mutating its records."""
from pathlib import Path

from sims_install import MOD_EXTENSIONS, TRAY_EXTENSIONS

FILE_TYPES = ("All types", "Package mods", "Script mods", "Tray files", "Archives")
FILE_STATES = ("All states", "Installed", "Enabled", "Quarantined", "Downloaded")


def extension(record):
    path = Path(record["path"])
    if record.get("disabled") and path.suffix.lower() == ".disabled":
        path = path.with_suffix("")
    return path.suffix.lower()


def member_key(key, record):
    return record.get("item") or key


def library_rows(records, *, query, category, file_type, state, sort, groups, managed):
    query = query.strip().casefold()
    rows = []
    for key, record in records.items():
        if any(group is not None and key not in group and member_key(key, record) not in group for group in groups):
            continue
        if category not in ("All categories", record.get("category", "Other")):
            continue
        suffix = extension(record)
        kind = ("Package mods" if suffix in MOD_EXTENSIONS and suffix != ".ts4script" else
                "Script mods" if suffix == ".ts4script" else "Tray files" if suffix in TRAY_EXTENSIONS else
                "Archives" if suffix == ".zip" else "Other")
        if file_type not in ("All types", kind):
            continue
        if record["origin"] == "library":
            status = "Installed copy exists" if key in managed else "Downloaded"
            status_filter = "Downloaded"
        else:
            status = "Disabled" if record.get("disabled") else "Enabled"
            status_filter = "Quarantined" if record.get("disabled") else "Enabled"
        if state not in ("All states", status_filter) and not (state == "Installed" and record["origin"] != "library"):
            continue
        if query.startswith(".") and query[1:].isalnum():
            if suffix != query:
                continue
        elif query:
            haystack = " ".join(str(record.get(field, "")) for field in
                                ("name", "creator", "category", "path", "url")).casefold()
            if not all(part in haystack for part in query.split()):
                continue
        rows.append((key, record, suffix.lstrip("."), status))

    rows.sort(key=lambda entry: entry[1]["name"].casefold())
    if sort == "Newest first":
        rows.sort(key=lambda entry: entry[1].get("added") or entry[1].get("date", ""), reverse=True)
    elif sort == "Largest first":
        rows.sort(key=lambda entry: entry[1].get("size") or 0, reverse=True)
    elif sort == "Creator A–Z":
        rows.sort(key=lambda entry: (not entry[1].get("creator"), entry[1].get("creator", "").casefold()))
    return rows
