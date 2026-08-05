from __future__ import annotations
from TSRUrl import TSRUrl
from TSRDownload import TSRDownload
from logger import logger
from exceptions import *
from concurrent.futures import ThreadPoolExecutor
from TSRSession import TSRSession
from branding import logStartupBanner
from config import CONFIG, CURRENT_DIR
import clipboard, time, os


def processTarget(url: TSRUrl, tsrdlsession: str, downloadPath: str):
    try:
        downloader = TSRDownload(url, tsrdlsession)
        downloader.init()
        downloader.download(downloadPath)
        logger.info(f"Completed download for: {url.url}")
        return url, True
    except Exception as e:
        logger.error(f"Download failed for {url.url}: {e}")
        return url, False


def callback(future):
    result = future.result()
    if result is None:
        return
    url, success = result
    logger.debug(f"Removing {url.itemId} from queue")
    runningDownloads.remove(url.itemId)
    if success:
        sessionStats["downloaded"] += 1
    else:
        sessionStats["failed"] += 1
    updateUrlFile()
    if len(runningDownloads) == 0:
        logger.info(
            f"All downloads completed. "
            f"Session total: {sessionStats['downloaded']} downloaded, "
            f"{sessionStats['failed']} failed."
        )


def updateUrlFile():
    logger.debug(f"Updating URL file")
    if CONFIG["saveDownloadQueue"]:
        with open(CURRENT_DIR + "/urls.txt", "w") as f:
            f.write(
                "\n".join(
                    [
                        DETAILS_URL + str(item_id)
                        for item_id in [*runningDownloads, *downloadQueue, *vipItemIds]
                    ]
                )
            )


if __name__ == "__main__":
    DETAILS_URL = "https://www.thesimsresource.com/downloads/details/id/"
    lastPastedText = ""
    runningDownloads: list[int] = []
    downloadQueue: list[int] = []
    vipItemIds: list[int] = []
    sessionStats = {"downloaded": 0, "failed": 0}

    logStartupBanner(logger)

    logger.debug(f'downloadDirectory: {CONFIG["downloadDirectory"]}')
    logger.debug(f'maxActiveDownloads: {CONFIG["maxActiveDownloads"]}')
    logger.debug(f'saveDownloadQueue: {CONFIG["saveDownloadQueue"]}')
    logger.debug(f'debug: {CONFIG["debug"]}')

    os.makedirs(CONFIG["downloadDirectory"], exist_ok=True)
    logger.info(f'Download directory: {CONFIG["downloadDirectory"]}')

    session = None
    sessionId = None
    if os.path.exists(CURRENT_DIR + "/session"):
        with open(CURRENT_DIR + "/session", "r") as f:
            sessionId = f.read()

    while session is None:
        session = TSRSession(sessionId)
        if hasattr(session, "tsrdlsession") and session.tsrdlsession != "":
            with open(CURRENT_DIR + "/session", "w") as f:
                f.write(session.tsrdlsession)
            logger.info("Saved TSR download session is valid")

    if os.path.exists(CURRENT_DIR + "/urls.txt") and CONFIG["saveDownloadQueue"]:
        with open(CURRENT_DIR + "/urls.txt", "r") as f:
            urls_content = f.read()
        for url in urls_content.split("\n"):
            if not url.strip():
                continue
            try:
                url = TSRUrl(url)
                if url.isVipExclusive():
                    logger.info(f"Url is still a VIP exclusive: {url.url}")
                    vipItemIds.append(url.itemId)
                    continue

                if url.itemId in downloadQueue:
                    continue
                downloadQueue.append(url.itemId)
            except InvalidURL:
                continue

    logger.info(
        "The tool is now ready to be used. Simply copy links from The Sims Resource and the tool will automatically download them for you."
    )

    executor = ThreadPoolExecutor(max_workers=CONFIG["maxActiveDownloads"])
    while True:
        try:
            pastedText = clipboard.paste()
        except Exception:
            pastedText = lastPastedText

        if lastPastedText == pastedText:
            for item_id in downloadQueue[:]:
                if len(runningDownloads) == CONFIG["maxActiveDownloads"]:
                    break

                url = TSRUrl(DETAILS_URL + str(item_id))
                runningDownloads.append(url.itemId)
                downloadQueue.remove(url.itemId)
                logger.info(f"Moved {url.url} from queue to downloading")
                future = executor.submit(
                    processTarget,
                    url,
                    session.tsrdlsession,
                    CONFIG["downloadDirectory"],
                )
                future.add_done_callback(callback)

                if len(downloadQueue) == 0:
                    logger.info("Queue is now empty")
        else:
            lastPastedText = pastedText
            for line in pastedText.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    url = TSRUrl(line)
                except InvalidURL:
                    continue

                if url.itemId in runningDownloads:
                    logger.info(f"Url is already being downloaded: {url.url}")
                    continue
                if url.itemId in downloadQueue:
                    logger.info(
                        f"Url is already in queue (#{downloadQueue.index(url.itemId)}): {url.url}"
                    )
                    continue

                if url.itemId in vipItemIds:
                    logger.info(f"Url is currently a VIP exclusive: {url.url}")
                    continue
                elif url.isVipExclusive():
                    logger.info(
                        "Url is currently a VIP exclusive, "
                        + (
                            "storing url for later: "
                            if CONFIG["saveDownloadQueue"]
                            else "unable to download: "
                        )
                        + f"{url.url}"
                    )
                    vipItemIds.append(url.itemId)
                    updateUrlFile()
                    continue

                requirements = TSRUrl.getRequiredItems(url)
                logger.info(f"Found valid url in clipboard: {url.url}")
                if len(requirements) != 0:
                    logger.info(f"{url.url} has {len(requirements)} requirements")
                for req_url in [url, *requirements]:
                    if req_url.itemId in runningDownloads:
                        logger.info(f"Url is already being downloaded: {req_url.itemId}")
                        continue
                    if req_url.itemId in downloadQueue:
                        logger.info(
                            f"Url is already in queue (#{downloadQueue.index(req_url.itemId)}): {req_url.url}"
                        )
                        continue
                    if len(runningDownloads) == CONFIG["maxActiveDownloads"]:
                        logger.info(
                            f"Added url to queue (#{len(downloadQueue)}): {req_url.url}"
                        )
                        downloadQueue.append(req_url.itemId)
                    else:
                        runningDownloads.append(req_url.itemId)
                        future = executor.submit(
                            processTarget,
                            req_url,
                            session.tsrdlsession,
                            CONFIG["downloadDirectory"],
                        )
                        future.add_done_callback(callback)
                updateUrlFile()

        time.sleep(0.1)
