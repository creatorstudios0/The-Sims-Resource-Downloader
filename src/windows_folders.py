"""Find Sims 4 user data in Windows Documents and OneDrive."""
from pathlib import Path
import os
import sys
import winreg

GAME_NAME = "The Sims 4"
GAME_FOLDERS = ("Mods", "Tray", "saves")
SHELL_FOLDERS = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"


def known_folder(key, fallback):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SHELL_FOLDERS) as registry:
            value, _ = winreg.QueryValueEx(registry, key)
        return Path(os.path.expandvars(value)) if value else fallback
    except OSError:
        return fallback


def detect_game():
    documents = Path.home() / "Documents"
    locations = [known_folder("Personal", documents), documents, Path.home() / "OneDrive" / "Documents"]
    for variable in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(variable):
            locations.append(Path(os.environ[variable]) / "Documents")

    best = None
    best_score = 0
    for directory in locations:
        for publisher in ("Electronic Arts", "EA Games"):
            candidate = directory / publisher / GAME_NAME
            score = sum((candidate / name).is_dir() for name in GAME_FOLDERS)
            if score > best_score:
                best, best_score = candidate.resolve(), score
    return best


def default_downloads(project_downloads):
    if not getattr(sys, "frozen", False):
        return Path(project_downloads)
    downloads = known_folder("{374DE290-123F-4565-9164-39C4925E467B}", Path.home() / "Downloads")
    return downloads / "Sims 4 Mod Library"


def app_data():
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Sims 4 Mod Library"
