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

configPath = os.path.join(CURRENT_DIR, "config.json")
if not os.path.exists(configPath):
    configPath = os.path.join(CURRENT_DIR, "config.defaults.json")

with open(configPath, "r") as f:
    CONFIG: CONFIG_DICT = json.load(f)


def resolvePath(path: str) -> str:
    expandedPath = os.path.expandvars(os.path.expanduser(path))
    if not os.path.isabs(expandedPath):
        expandedPath = os.path.join(PROJECT_DIR, expandedPath)
    return os.path.abspath(expandedPath)


def validateConfig(config: dict) -> None:
    """Validate config.json values at startup and exit with a clear message if invalid."""
    errors = []

    required_keys = {
        "downloadDirectory": str,
        "maxActiveDownloads": int,
        "saveDownloadQueue": bool,
    }

    for key, expected_type in required_keys.items():
        if key not in config:
            errors.append(f"  - Missing required key: '{key}'")
        elif not isinstance(config[key], expected_type):
            actual = type(config[key]).__name__
            errors.append(
                f"  - '{key}' must be a {expected_type.__name__}, but got {actual} ({config[key]!r})"
            )

    if "maxActiveDownloads" in config and isinstance(config["maxActiveDownloads"], int):
        if config["maxActiveDownloads"] < 1:
            errors.append("  - 'maxActiveDownloads' must be at least 1")
        elif config["maxActiveDownloads"] > 10:
            errors.append("  - 'maxActiveDownloads' should not exceed 10 (to avoid rate-limiting by TSR)")

    if errors:
        print("\n[CONFIG ERROR] src/config.json has invalid settings:")
        for err in errors:
            print(err)
        print("\nPlease fix the issues above and restart the tool.")
        sys.exit(1)


CONFIG["downloadDirectory"] = resolvePath(CONFIG["downloadDirectory"])
CONFIG.setdefault("organizeDownloads", True)
CONFIG.setdefault("colorConsole", True)
CONFIG.setdefault("watermark", "Infinity Build")
CONFIG.setdefault("debug", False)

validateConfig(CONFIG)
