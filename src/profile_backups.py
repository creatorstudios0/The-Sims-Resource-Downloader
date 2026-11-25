"""Rolling snapshots of the library database and its saved profiles."""
from datetime import datetime
import json

from desktop_data import save_json


def read_state(path):
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or any(
        key in value and not isinstance(value[key], kind)
        for key, kind in (
            ("settings", dict), ("items", dict), ("installs", dict), ("profiles", dict), ("history", list),
            ("queueHidden", list), ("categoryOverrides", dict), ("game", str),
        )
    ):
        raise ValueError("The library state file has an invalid structure.")

    for key, item in value.get("items", {}).items():
        if (not isinstance(item, dict) or not isinstance(item.get("status"), str)
                or not isinstance(item.get("name"), str)):
            raise ValueError(f"The library state file has an invalid queue item ({key}).")

    # Recovery metadata can be rebuilt without rolling back library records.
    if not isinstance(value.get("reviewedGameVersions"), dict):
        value.pop("reviewedGameVersions", None)
    receipt = value.get("lastContentBackup")
    if not (
        isinstance(receipt, dict)
        and isinstance(receipt.get("path"), str)
        and receipt["path"]
        and type(receipt.get("files")) is int
        and receipt["files"] >= 0
    ):
        value.pop("lastContentBackup", None)
    return value


class ProfileBackups:
    def __init__(self, path):
        self.directory = path.with_name(path.stem + "-backups")
        self.last_snapshot = None

    def snapshots(self):
        return sorted(self.directory.glob("profile-*.json"), reverse=True)

    def save(self, state):
        # Window position alone does not warrant a new recovery point.
        content = json.dumps({key: value for key, value in state.items() if key != "windowGeometry"}, sort_keys=True)
        if content == self.last_snapshot:
            return
        newest = next(iter(self.snapshots()), None)
        if self.last_snapshot is None and newest:
            try:
                previous = read_state(newest)
                previous.pop("windowGeometry", None)
                if json.dumps(previous, sort_keys=True) == content:
                    self.last_snapshot = content
                    return
            except (OSError, ValueError):
                pass
        self.directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        save_json(self.directory / f"profile-{timestamp}.json", state)
        self.last_snapshot = content
        for obsolete in self.snapshots()[10:]:
            obsolete.unlink(missing_ok=True)

    def load(self, path):
        try:
            if path.exists():
                return read_state(path), None
        except (OSError, ValueError):
            for snapshot in self.snapshots():
                try:
                    return read_state(snapshot), snapshot
                except (OSError, ValueError):
                    continue
            raise
        for snapshot in self.snapshots():
            try:
                return read_state(snapshot), snapshot
            except (OSError, ValueError):
                continue
        return {}, None
