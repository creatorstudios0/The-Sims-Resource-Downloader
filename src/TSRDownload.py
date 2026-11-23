from __future__ import annotations
import requests, time, re
from concurrent.futures import CancelledError
from urllib.parse import urljoin, urlsplit
from ipaddress import ip_address
from pathlib import Path
from email.message import Message
from TSRUrl import TSRUrl
from logger import logger
from exceptions import *
from download_organizer import organizeDownloadedFile, move_with_unique_name
from config import CONFIG

REQUEST_TIMEOUT = 30            # seconds for all network calls
MAX_RETRIES = 3                 # number of retry attempts on failure
RETRY_BACKOFF = 5               # base seconds to wait between retries
TICKET_WAIT_MS = 15_000

_CYAN = "\033[36m"
_RESET = "\033[0m"


def stripForbiddenCharacters(string: str) -> str:
    return "".join(char for char in string if ord(char) >= 32 and char not in '\\<>/:"|?*')


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

    def init(self):
        logger.info(f"Initializing TSRDownload for: {self.url.url}")
        self.TSRDLTicket = self.__getTSRDLTicket()
        self.session.cookies.set(
            "tsrdlsession",
            self.sessionId or self.__getTSRDLTicketCookie(),
            domain=".thesimsresource.com",
        )
        self.ticketInitializedTime = time.monotonic() * 1000

    def download(self, downloadPath: str, progress=None, organize=None, cancel=None, attempts=MAX_RETRIES) -> str:
        report = progress or _print_progress
        for attempt in range(1, attempts + 1):
            self._check_cancel(cancel)
            try:
                if attempt > 1 or self.ticketInitializedTime < 0:
                    self.init()
                remaining = TICKET_WAIT_MS / 1000 - (
                    time.monotonic() - self.ticketInitializedTime / 1000
                )
                if remaining > 0:
                    if progress:
                        progress("Waiting for TSR", 0, 0)
                    self._wait(remaining, cancel)
                return self._attemptDownload(downloadPath, report, organize, cancel)
            except requests.HTTPError as error:
                if error.response.status_code == 429:
                    raise
                if error.response.status_code < 500 or attempt == attempts:
                    raise
            except (requests.RequestException, InvalidDownloadTicket):
                if attempt == attempts:
                    raise
            if progress:
                progress("Retrying transfer", 0, 0)
            self._wait(RETRY_BACKOFF * attempt, cancel)

    def _attemptDownload(self, downloadPath: str, report, organize=None, cancel=None) -> str:
        root = Path(downloadPath)
        staging = root / ".partial"
        staging.mkdir(parents=True, exist_ok=True)
        if staging.is_symlink() or getattr(staging, "is_junction", lambda: False)():
            raise ValueError("Download staging folder is a filesystem link")
        partial = staging / f"{self.url.itemId}.part"
        validator = partial.with_suffix(".etag")
        if partial.is_symlink() or validator.is_symlink():
            raise ValueError("Download staging file is a filesystem link")
        offset = partial.stat().st_size if partial.exists() else 0
        etag = validator.read_text(encoding="utf-8") if offset and validator.exists() else ""
        headers = {"Accept-Encoding": "identity"}
        if etag:
            headers.update({"Range": f"bytes={offset}-", "If-Range": etag})
        url = self.__getDownloadUrl()
        with self._delivery_response(url, headers, cancel) as response:
            if response.status_code == 416 and etag:
                partial.unlink(missing_ok=True)
                validator.unlink(missing_ok=True)
                raise requests.ConnectionError("Server rejected the saved byte range")
            response.raise_for_status()
            disposition = Message()
            disposition["Content-Disposition"] = response.headers.get("Content-Disposition", "")
            raw_name = disposition.get_filename()
            if not raw_name:
                raise ValueError("TSR did not return a download filename")
            name = stripForbiddenCharacters(raw_name).strip(" .")
            if not name:
                raise ValueError("TSR returned an empty filename")
            received_etag = response.headers.get("ETag", "")
            expected = int(response.headers.get("Content-Length") or 0)
            if response.status_code == 206:
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
                if (not etag or received_etag != etag or not match
                        or int(match[1]) != offset or int(match[2]) + 1 != int(match[3])):
                    partial.unlink(missing_ok=True)
                    validator.unlink(missing_ok=True)
                    raise requests.ConnectionError("Invalid resume response")
                total = int(match[3])
            elif response.status_code == 200:
                offset = 0
                total = expected if response.headers.get("Content-Encoding", "identity") == "identity" else 0
            else:
                raise ValueError(f"Unexpected download status {response.status_code}")
            downloaded = offset
            last_update = 0.0
            with partial.open("ab" if offset else "wb") as out:
                if received_etag and not received_etag.startswith("W/") and response.headers.get("Content-Encoding", "identity") == "identity":
                    validator.write_text(received_etag, encoding="utf-8")
                else:
                    validator.unlink(missing_ok=True)
                for chunk in response.iter_content(128 * 1024):
                    self._check_cancel(cancel)
                    out.write(chunk)
                    downloaded += len(chunk)
                    now = time.monotonic()
                    if now - last_update >= 0.25:
                        report(name, downloaded, total)
                        last_update = now
            if not downloaded or (total and downloaded != total):
                if total and downloaded > total:
                    partial.unlink(missing_ok=True)
                    validator.unlink(missing_ok=True)
                raise requests.ConnectionError("Incomplete download")
        self._check_cancel(cancel)
        target = move_with_unique_name(partial, root / f"{self.url.itemId}-{name}")
        validator.unlink(missing_ok=True)
        report(name, downloaded, total or downloaded)
        if report is _print_progress:
            print()
        return organizeDownloadedFile(str(target), enabled=organize)

    @staticmethod
    def _check_cancel(cancel):
        if cancel is not None and cancel.is_set():
            raise CancelledError()

    @staticmethod
    def _wait(seconds, cancel):
        if cancel is None:
            time.sleep(seconds)
        elif cancel.wait(seconds):
            raise CancelledError()

    def _delivery_response(self, url, headers, cancel):
        initial_host = urlsplit(url).hostname
        for _ in range(6):
            self._check_cancel(cancel)
            target = urlsplit(url)
            host = target.hostname or ""
            if (target.scheme != "https" or target.username or target.password
                    or "." not in host or host.endswith((".localhost", ".local", ".internal"))
                    or target.port not in (None, 443)
                    or (host != initial_host and not host.endswith(".thesimsresource.com")
                        and host != "thesimsresource.com")):
                raise ValueError("Unexpected TSR download destination")
            try:
                address = ip_address(host)
            except ValueError:
                pass
            else:
                if not address.is_global:
                    raise ValueError("Unexpected TSR download destination")
            response = self.session.get(url, stream=True, timeout=REQUEST_TIMEOUT,
                                        headers=headers, allow_redirects=False)
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            with response:
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("TSR download redirect had no destination")
                url = urljoin(url, location)
        raise ValueError("TSR download redirected too many times")

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
