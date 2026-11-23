from __future__ import annotations
import os, zipfile
from pathlib import Path
from config import CONFIG
from logger import logger

TRAY_EXTENSIONS = {
    ".blueprint",
    ".bpi",
    ".hhi",
    ".householdbinary",
    ".rmi",
    ".room",
    ".sgi",
    ".trayitem",
}
MOD_EXTENSIONS = {".package", ".ts4script"}

MOD_KEYWORDS = {
    "Default Replacements": ["default", "replacement", "override"],
    "Poses and Animations": ["pose", "poses", "animation", "animations"],
    "CAS": [
        "accessory",
        "accessories",
        "beard",
        "cas",
        "clothes",
        "clothing",
        "dress",
        "eye",
        "eyebrow",
        "eyelash",
        "face",
        "hair",
        "lip",
        "makeup",
        "nail",
        "pants",
        "preset",
        "shirt",
        "shoe",
        "skin",
        "slider",
        "tattoo",
        "top",
    ],
    "Build Buy": [
        "bathroom",
        "bed",
        "bedroom",
        "build",
        "buy",
        "chair",
        "clutter",
        "decor",
        "door",
        "floor",
        "furniture",
        "kitchen",
        "lamp",
        "painting",
        "plant",
        "rug",
        "sofa",
        "table",
        "wall",
        "window",
    ],
    "Gameplay Mods": ["aspiration", "career", "gameplay", "interaction", "trait"],
}


def organizeDownloadedFile(filePath: str, enabled: bool | None = None) -> str:
    if enabled is None:
        enabled = CONFIG.get("organizeDownloads", True)
    if not enabled:
        return filePath

    category, subcategory = getDownloadCategory(filePath)
    targetDirectory = os.path.join(os.path.dirname(filePath), category, subcategory)
    targetPath = os.path.join(targetDirectory, os.path.basename(filePath))

    if os.path.normcase(os.path.abspath(filePath)) == os.path.normcase(
        os.path.abspath(targetPath)
    ):
        return filePath

    directory = Path(targetDirectory)
    root = Path(filePath).parent.resolve()
    if directory.resolve() != root / category / subcategory:
        logger.warning("Skipped organization because the destination was redirected: %s", directory)
        return filePath

    directory.mkdir(parents=True, exist_ok=True)
    published = move_with_unique_name(Path(filePath), Path(targetPath))
    logger.info(f"Organized download into: {category}/{subcategory}")
    return str(published)


def move_with_unique_name(source: Path, destination: Path) -> Path:
    """Publish on the same volume using Windows rename without replacing an existing file."""
    candidate = destination
    number = 2
    while True:
        try:
            source.rename(candidate)
            return candidate
        except FileExistsError:
            candidate = destination.with_stem(f"{destination.stem} ({number})")
            number += 1

def getDownloadCategory(filePath: str) -> tuple[str, str]:
    fileNames = [os.path.basename(filePath), *_getArchiveFileNames(filePath)]
    extensions = {os.path.splitext(name)[1].lower() for name in fileNames}
    searchableText = " ".join(fileNames).lower()

    if extensions & TRAY_EXTENSIONS:
        return "Tray Files", _getTraySubcategory(extensions, searchableText)

    if extensions & MOD_EXTENSIONS:
        return "Mod Files", _getModSubcategory(extensions, searchableText)

    if os.path.splitext(filePath)[1].lower() in {".7z", ".rar", ".zip"}:
        return "Other Files", "Archives"

    return "Other Files", "Misc"


def _getArchiveFileNames(filePath: str) -> list[str]:
    if not zipfile.is_zipfile(filePath):
        return []

    try:
        with zipfile.ZipFile(filePath) as archive:
            return [
                os.path.basename(name)
                for name in archive.namelist()
                if not name.endswith("/")
            ]
    except zipfile.BadZipFile:
        return []


def _getTraySubcategory(extensions: set[str], searchableText: str) -> str:
    if ".room" in extensions or _hasKeyword(searchableText, ["room"]):
        return "Rooms"
    if extensions & {".householdbinary", ".hhi", ".sgi"} or _hasKeyword(
        searchableText, ["household", "sim", "sims"]
    ):
        return "Households"
    if extensions & {".blueprint", ".bpi"} or _hasKeyword(
        searchableText, ["build", "house", "lot"]
    ):
        return "Lots"
    return "Other Tray Files"


def _getModSubcategory(extensions: set[str], searchableText: str) -> str:
    if ".ts4script" in extensions:
        return "Script Mods"

    for category, keywords in MOD_KEYWORDS.items():
        if _hasKeyword(searchableText, keywords):
            return category

    return "Package Mods"


def _hasKeyword(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
