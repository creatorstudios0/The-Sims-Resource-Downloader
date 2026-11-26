from __future__ import annotations
import requests, time, os, re
from TSRUrl import TSRUrl
from logger import logger
from exceptions import *
from download_organizer import organizeDownloadedFile
from config import CONFIG

REQUEST_TIMEOUT = 30            # seconds for all network calls
MAX_RETRIES = 3                 # number of retry attempts on failure
RETRY_BACKOFF = 5               # base seconds to wait between retries
TICKET_VALIDITY_MS = 15_000    # TSR download tickets expire after 15 seconds

_CYAN = "\033[36m"
_RESET = "\033[0m"


def stripForbiddenCharacters(string: str) -> str:
    return re.sub('[\\<>/:"|?*]', "", string)


def _findExistingFile(fileName: str, searchRoot: str) -> str | None:
    """Walk the download directory tree to find an already-downloaded file."""
    for dirpath, _, filenames in os.walk(searchRoot):
        if fileName in filenames:
            return os.path.join(dirpath, fileName)
    return None


def _fmt_bytes(n: float) -> str:
    """Format a byte count as a human-readable string (B / KB / MB / GB)."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _print_progress(fileName: str, downloaded: int, total: int) -> None:
    """Overwrite the current console line with a live download progress bar."""
    use_color = CONFIG.get("colorConsole", True)
    prefix = f"{_CYAN}[DOWNLOAD]{_RESET}" if use_color else "[DOWNLOAD]"

    if total > 0:
        pct = min(downloaded / total * 100, 100.0)
        bar_width = 25
        filled = int(bar_width * downloaded / total)
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
        line = (
            f"\r{prefix} {fileName}  "
            f"[{bar}] {pct:.1f}%  "
            f"({_fmt_bytes(downloaded)} / {_fmt_bytes(total)})"
        )
    else:
        # Content-Length unknown — just show bytes so far
        line = f"\r{prefix} {fileName}  {_fmt_bytes(downloaded)} downloaded"

    print(line, end="", flush=True)


class TSRDownload:
    def __init__(self, url: TSRUrl, sessionId: str):
        self.TSRDLTicket = ""
        self.url: TSRUrl = url
        self.sessionId = sessionId
        self.ticketInitializedTime = -1.0
        self.session: requests.Session = requests.Session()

    # Public-to-subclass hooks keep the desktop downloader compatible while the
    # console retains its original private ticket methods and resume safeguards.
    def _getDownloadUrl(self):
        return self.__getDownloadUrl()

    def _getTSRDLTicketCookie(self):
        return self.__getTSRDLTicketCookie()

    def _getTSRDLTicket(self):
        return self.__getTSRDLTicket()

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
        timeToSleep = TICKET_VALIDITY_MS - (time.time() * 1000 - self.ticketInitializedTime)
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

        # Probe request: read Content-Disposition for filename without consuming the body.
        # Uses self.session so auth cookies are sent (fixes the previous unauthenticated call).
        probe = self.session.get(downloadUrl, stream=True, timeout=REQUEST_TIMEOUT)
        probe.raise_for_status()
        match = re.search(
            r'(?<=filename=").+(?=")',
            probe.headers.get("Content-Disposition", ""),
        )
        probe.close()
        if not match:
            raise ValueError(
                f"Could not determine filename from download URL: {downloadUrl}"
            )
        fileName = stripForbiddenCharacters(match[0])
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

        headers = {"Accept-Encoding": "identity"}
        if startingBytes:
            headers["Range"] = f"bytes={startingBytes}-"
        with self.session.get(
            downloadUrl,
            stream=True,
            timeout=REQUEST_TIMEOUT,
            headers=headers,
        ) as response:
            logger.debug(f"Request status is: {response.status_code}")
            if response.status_code == 416 and startingBytes:
                # The next attempt must start fresh instead of repeating the rejected range.
                os.remove(partPath)
            response.raise_for_status()

            rangeEnd = None
            contentEncoding = response.headers.get("Content-Encoding", "identity")
            if response.status_code == 200:
                # The server returned the entire file, so discard the stale prefix.
                startingBytes = 0
                total = int(response.headers.get("content-length", 0)) if contentEncoding == "identity" else 0
            elif response.status_code == 206:
                contentRange = response.headers.get("Content-Range", "")
                rangeMatch = re.fullmatch(
                    r"bytes ([0-9]+)-([0-9]+)/([0-9]+)", contentRange, re.IGNORECASE
                )
                if (
                    rangeMatch is None
                    or int(rangeMatch[1]) != startingBytes
                    or not startingBytes <= int(rangeMatch[2]) < int(rangeMatch[3])
                    or contentEncoding != "identity"
                ):
                    raise ValueError(
                        f"Download returned unexpected Content-Range {contentRange!r} "
                        f"for requested offset {startingBytes}"
                    )
                rangeEnd = int(rangeMatch[2]) + 1
                total = int(rangeMatch[3])
            else:
                raise ValueError(f"Unexpected download response status: {response.status_code}")

            downloaded = startingBytes

            with open(partPath, "ab" if startingBytes > 0 else "wb") as file:
                for chunk in response.iter_content(1024 * 128):
                    if rangeEnd is not None and downloaded + len(chunk) > rangeEnd:
                        file.truncate(startingBytes)
                        raise ValueError("Download body exceeds Content-Range")
                    file.write(chunk)
                    downloaded += len(chunk)
                    _print_progress(fileName, downloaded, total)

            if rangeEnd is not None and downloaded != total:
                raise ValueError(f"Download is incomplete ({downloaded} of {total} bytes)")

        # Final progress line — ensure 100% is shown, then move to a new line
        _print_progress(fileName, total if total > 0 else downloaded, total if total > 0 else downloaded)
        print()

        logger.debug(f"Removing .part from file name: {fileName}")
        if os.path.exists(finalPath):
            logger.debug(f"{finalPath} Already exists! Replacing file")
            os.replace(partPath, finalPath)
        else:
            logger.debug(f"{finalPath} doesn't exist! Renaming file")
            os.rename(partPath, finalPath)
        return organizeDownloadedFile(finalPath)

    def __getDownloadUrl(self) -> str:
        response = self.session.get(
            f"https://www.thesimsresource.com/ajax.php?c=downloads&a=getdownloadurl&ajax=1"
            f"&itemid={self.url.itemId}&mid=0&lk=0&ticket={self.TSRDLTicket}",
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
            f"https://www.thesimsresource.com/ajax.php?c=downloads&a=initDownload"
            f"&itemid={self.url.itemId}&format=zip",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        try:
            data = response.json()
        except Exception:
            raise ValueError(
                f"TSR initDownload returned non-JSON response (status {response.status_code}): "
                f"{response.text[:200]!r}"
            )
        if "ticket" not in data:
            logger.debug(f"TSR initDownload response: {data}")
            error_msg = data.get("error") or data.get("message") or str(data)
            raise ValueError(
                f"TSR initDownload did not return a ticket for item {self.url.itemId}. "
                f"Server said: {error_msg!r}"
            )
        return data["ticket"]
