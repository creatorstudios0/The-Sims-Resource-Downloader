from __future__ import annotations
from config import CONFIG

APP_NAME = "The Sims Resource Downloader"
APP_VERSION = "0.5.2-production"  # Must match the GitHub release tag exactly
ORIGINAL_AUTHOR = "Xientra"
BUILD_CREDIT = "Production build maintained by Infinity"


def logStartupBanner(logger) -> None:
    watermark = CONFIG.get("watermark", "Infinity Build")
    separator = "=" * 62
    for line in [
        separator,
        f"{APP_NAME} - {watermark}",
        f"Version: {APP_VERSION}",
        f"Original build by {ORIGINAL_AUTHOR}",
        BUILD_CREDIT,
        separator,
    ]:
        logger.info(line)
