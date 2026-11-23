from __future__ import annotations
import os
from config import CONFIG, PROJECT_DIR

APP_NAME = "The Sims Resource Downloader"
ORIGINAL_AUTHOR = "Xientra"
BUILD_CREDIT = "Production build maintained by Infinity"

_VERSION_FILE = os.path.join(PROJECT_DIR, ".version")
_FALLBACK_VERSION = "v1.0.3"


def getAppVersion() -> str:
    """Read the installed version from .version; fall back to the hardcoded string."""
    try:
        with open(_VERSION_FILE, "r") as f:
            v = f.read().strip()
            return v if v else _FALLBACK_VERSION
    except OSError:
        return _FALLBACK_VERSION


def logStartupBanner(logger) -> None:
    watermark = CONFIG.get("watermark", "Infinity Build")
    version = getAppVersion()
    separator = "=" * 62
    for line in [
        separator,
        f"{APP_NAME} - {watermark}",
        f"Version: {version}",
        f"Original build by {ORIGINAL_AUTHOR}",
        BUILD_CREDIT,
        separator,
    ]:
        logger.info(line)
