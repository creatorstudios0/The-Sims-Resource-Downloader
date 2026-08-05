from __future__ import annotations
import requests, time, os, re
from TSRUrl import TSRUrl
from logger import logger
from exceptions import *
from download_organizer import organizeDownloadedFile

REQUEST_TIMEOUT = 30    # seconds for all network calls
MAX_RETRIES = 3         # number of retry attempts on failure
RETRY_BACKOFF = 5       # base seconds to wait between retries


def stripForbiddenCharacters(string: str) -> str:
    return re.sub('[\\<>/:"\\|?*]', "", string)


def _findExistingFile(fileName: str, searchRoot: str) -> str | None:
    """Walk the download directory tree to find an already-downloaded file."""
    for dirpath, _, filenames in os.walk(searchRoot):
        if fileName in filenames:
            return os.path.join(dirpath, fileName)
    return None


class TSRDownload:
    def __init__(self, url: TSRUrl, sessionId: str):
        self.TSRDLTicket = ""
        self.url: TSRUrl = url
        self.sessionId = sessionId
        self.ticketInitializedTime = -1.0
        self.session: requests.Session = requests.Session()

    def init(self):
        logger.info(f"Initializing TSRDownload for: {self.url.url}")
        self.TSRDLTicket = self.__getTSRDLTicket()
        self.session.cookies.set(
            "tsrdlsession",
            self.sessionId or self.__getTSRDLTicketCookie()
        )
        self.ticketInitializedTime = time.time() * 1000

    def download(self, downloadPath: str) -> str:
        logger.info(f"Starting download for: {self.url.url}")
        os.makedirs(downloadPath, exist_ok=True)
        timeToSleep = 15000 - (time.time() * 1000 - self.ticketInitializedTime)
        if timeToSleep > 0:
            time.sleep(timeToSleep / 1000)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._attemptDownload(downloadPath)
            except Exception as e:
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF * attempt
                    logger.warning(
                        f"Download attempt {attempt}/{MAX_RETRIES} failed for "
                        f"{self.url.url}: {e}. Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        f"All {MAX_RETRIES} download attempts failed for {self.url.url}: {e}"
                    )
                    raise

    def _attemptDownload(self, downloadPath: str) -> str:
        downloadUrl = self.__getDownloadUrl()
        logger.debug(f"Got downloadUrl: {downloadUrl}")
        fileName = stripForbiddenCharacters(self.__getFileName(downloadUrl))
        logger.debug(f"Got fileName: {fileName}")

        # Duplicate detection — scan all organized subfolders
        existing = _findExistingFile(fileName, downloadPath)
        if existing:
            logger.info(f"Skipping download, file already exists: {existing}")
            return existing

        partPath = os.path.join(downloadPath, f"{fileName}.part")
        finalPath = os.path.join(downloadPath, fileName)

        startingBytes = os.path.getsize(partPath) if os.path.exists(partPath) else 0
        logger.debug(f"Got startingBytes: {startingBytes}")
        request = self.session.get(
            downloadUrl,
            stream=True,
            timeout=REQUEST_TIMEOUT,
            headers={"Range": f"bytes={startingBytes}-"},
        )
        logger.debug(f"Request status is: {request.status_code}")
        request.raise_for_status()

        with open(partPath, "ab" if startingBytes > 0 else "wb") as file:
            for index, chunk in enumerate(request.iter_content(1024 * 128)):
                logger.debug(f"Downloading chunk #{index} of {downloadUrl}")
                file.write(chunk)

        logger.debug(f"Removing .part from file name: {fileName}")
        if os.path.exists(finalPath):
            logger.debug(f"{finalPath} Already exists! Replacing file")
            os.replace(partPath, finalPath)
        else:
            logger.debug(f"{finalPath} doesn't exist! Renaming file")
            os.rename(partPath, finalPath)
        return organizeDownloadedFile(finalPath)

    def __getFileName(self, downloadUrl: str) -> str:
        response = requests.get(downloadUrl, stream=True, timeout=REQUEST_TIMEOUT)
        match = re.search(
            r'(?<=filename=").+(?=")',
            response.headers.get("Content-Disposition", ""),
        )
        if not match:
            raise ValueError(f"Could not determine filename from download URL: {downloadUrl}")
        return match[0]

    def __getDownloadUrl(self) -> str:
        response = self.session.get(
            f"https://www.thesimsresource.com/ajax.php?c=downloads&a=getdownloadurl&ajax=1&itemid={self.url.itemId}&mid=0&lk=0&ticket={self.TSRDLTicket}",
            cookies=self.session.cookies,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        responseJSON = response.json()

        if responseJSON["error"] == "":
            return responseJSON["url"]
        elif responseJSON["error"] == "Invalid download ticket":
            raise InvalidDownloadTicket(response.url, self.session.cookies)
        else:
            raise ValueError(f"Unexpected TSR error: {responseJSON['error']}")

    def __getTSRDLTicketCookie(self) -> str:
        logger.info(f"Getting 'tsrdlticket' cookie for: {self.url.url}")
        url = f"{self.url.downloadUrl}/ticket/{self.TSRDLTicket}"
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        set_cookie = response.headers.get("Set-Cookie")
        return set_cookie.split(";")[0].split("=")[1] if set_cookie else ""

    def __getTSRDLTicket(self) -> str:
        logger.info(f"Getting 'tsrdlticket' for: {self.url.url}")
        response = self.session.get(
            f"https://www.thesimsresource.com/ajax.php?c=downloads&a=initDownload&itemid={self.url.itemId}&format=zip",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["ticket"]
