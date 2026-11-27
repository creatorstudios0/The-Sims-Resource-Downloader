import json, os, sys, typing

CONFIG_DICT = typing.TypedDict(
    "Config Dict",
    {
        "downloadDirectory": str,
        "maxActiveDownloads": int,
        "saveDownloadQueue": bool,
        "organizeDownloads": bool,
        "colorConsole": bool,
        "watermark": str,
        "debug": bool,
    },
)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(CURRENT_DIR)


def resolvePath(path: str) -> str:
    expandedPath = os.path.expandvars(os.path.expanduser(path))
    if not os.path.isabs(expandedPath):
        expandedPath = os.path.join(PROJECT_DIR, expandedPath)
    return os.path.abspath(expandedPath)


def validateConfig(config: dict) -> None:
    """Validate required settings before the application uses them."""
    if not isinstance(config, dict):
        raise ValueError("The settings must be a JSON object.")

    errors = []

    required_keys = {
        "downloadDirectory": str,
        "maxActiveDownloads": int,
        "saveDownloadQueue": bool,
    }

    for key, expected_type in required_keys.items():
        if key not in config:
            errors.append(f"  - Missing required key: '{key}'")
        elif type(config[key]) is not expected_type:
            actual = type(config[key]).__name__
            errors.append(
                f"  - '{key}' expects {expected_type.__name__}, but got {actual} ({config[key]!r})"
            )

    workers = config.get("maxActiveDownloads")
    if type(workers) is int:
        if workers < 1:
            errors.append("  - 'maxActiveDownloads' must be at least 1")
        elif workers > 10:
            errors.append("  - 'maxActiveDownloads' should not exceed 10 (to avoid rate-limiting by TSR)")

    if errors:
        raise ValueError("\n".join(errors))


try:
    with open(os.path.join(CURRENT_DIR, "config.json"), "r") as f:
        CONFIG: CONFIG_DICT = json.load(f)
    validateConfig(CONFIG)
except (OSError, ValueError) as error:
    print(f"\n[CONFIG ERROR] Could not load src/config.json:\n{error}")
    print("\nPlease fix the issues above and restart the tool.")
    sys.exit(1)


CONFIG["downloadDirectory"] = resolvePath(CONFIG["downloadDirectory"])
CONFIG.setdefault("organizeDownloads", True)
CONFIG.setdefault("colorConsole", True)
CONFIG.setdefault("watermark", "Infinity Build")
CONFIG.setdefault("debug", False)
