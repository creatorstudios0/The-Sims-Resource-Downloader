"""Cancelable TSR transfers for the desktop queue."""
from concurrent.futures import CancelledError
from email.message import Message
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import re
import time

import requests

from TSRDownload import TSRDownload, MAX_RETRIES, REQUEST_TIMEOUT, RETRY_BACKOFF, _print_progress
from download_organizer import move_with_unique_name, organizeDownloadedFile
from exceptions import InvalidDownloadTicket
from logger import logger

TICKET_WAIT_MS = 15_000


class DesktopTSRDownload(TSRDownload):
    """Share ticket handling with the original console downloader."""

    @staticmethod
    def display_name(value):
        return "".join(char for char in value if ord(char) >= 32 and char not in r'\<>/:"|?*')

    def init(self):
        logger.info(f"Initializing TSRDownload for: {self.url.url}")
        self.TSRDLTicket = self._getTSRDLTicket()
        self.session.cookies.set(
            "tsrdlsession",
            self.sessionId or self._getTSRDLTicketCookie(),
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
        url = self._getDownloadUrl()
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
            name = self.display_name(raw_name).strip(" .")
            if not name:
                raise ValueError("TSR returned an empty filename")
            received_etag = response.headers.get("ETag", "")
            encoding = response.headers.get("Content-Encoding", "identity")
            range_end = None
            if response.status_code == 206:
                match = re.fullmatch(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)",
                                     response.headers.get("Content-Range", ""), re.IGNORECASE)
                if (not etag or received_etag != etag or encoding != "identity" or not match
                        or int(match[1]) != offset or not offset <= int(match[2]) < int(match[3])):
                    partial.unlink(missing_ok=True)
                    validator.unlink(missing_ok=True)
                    raise requests.ConnectionError("Invalid resume response")
                range_end = int(match[2]) + 1
                total = int(match[3])
            elif response.status_code == 200:
                offset = 0
                total = int(response.headers.get("Content-Length") or 0) if encoding == "identity" else 0
            else:
                raise ValueError(f"Unexpected download status {response.status_code}")
            downloaded = offset
            last_update = 0.0
            with partial.open("ab" if offset else "wb") as out:
                if received_etag and not received_etag.startswith("W/") and encoding == "identity":
                    validator.write_text(received_etag, encoding="utf-8")
                else:
                    validator.unlink(missing_ok=True)
                for chunk in response.iter_content(128 * 1024):
                    self._check_cancel(cancel)
                    if range_end is not None and downloaded + len(chunk) > range_end:
                        out.truncate(offset)
                        raise requests.ConnectionError("Download body exceeds Content-Range")
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
