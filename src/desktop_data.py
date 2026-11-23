"""Desktop queue metadata and background TSR work."""
from pathlib import Path
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse
import json
import os
import re
import requests

from exceptions import InvalidURL
from TSRUrl import TSRUrl
from desktop_transfer import DesktopTSRDownload
from download_organizer import getDownloadCategory

DETAILS = "https://www.thesimsresource.com/downloads/"
HOSTS = {"www.thesimsresource.com", "thesimsresource.com"}


class ItemMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            values = dict(attrs)
            name = values.get("property") or values.get("name")
            if name and values.get("content"):
                self.values[name.lower()] = values["content"]


def parse_url(value):
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() not in HOSTS:
        raise InvalidURL(value)
    path = parsed.path
    valid_path = path.startswith("/downloads/") and re.search(
        r"(?:^/downloads/|/id/|/itemId/)[0-9]+(?:/|$)", path
    )
    if not valid_path:
        raise InvalidURL(value)
    return TSRUrl(f"https://{parsed.netloc}{parsed.path}")


def save_json(path, value):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def inspect_item(url, dependencies=True):
    item = parse_url(url)
    response = requests.get(DETAILS + str(item.itemId), timeout=(8, 20))
    response.raise_for_status()
    if urlparse(response.url).hostname not in HOSTS:
        raise ValueError("TSR item review redirected outside the supported website.")
    page = response.text
    metadata = ItemMetadata()
    metadata.feed(page)
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    name = unescape(title[1]).strip() if title else f"TSR item {item.itemId}"
    name = re.sub(r"^The Sims Resource\s*[-–]\s*", "", name, flags=re.I)
    creator = metadata.values.get("author", "")
    thumbnail = metadata.values.get("og:image", "")
    if not thumbnail_allowed(thumbnail):
        thumbnail = ""
    children = list(dict.fromkeys(re.findall(
        r'<li[^>]+class=["\']required-download-item["\'][^>]*>\s*<a[^>]+href=["\']/downloads/(\d+)',
        page, re.I,
    ))) if dependencies else []
    return {"name": name, "creator": creator, "thumbnail": thumbnail,
            "requires": [value for value in children if value != str(item.itemId)],
            "status": "VIP only" if "VIP Exclusive" in page else "Review",
            "detail": ""}



def thumbnail_allowed(url):
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.netloc.lower() == host and (host in HOSTS or host.endswith(".thesimsresource.com")))


def fetch_thumbnail(url):
    if not thumbnail_allowed(url):
        return b""
    with requests.get(url, timeout=(4, 7), stream=True, allow_redirects=False) as response:
        if response.status_code != 200 or response.headers.get("Content-Type", "").split(";", 1)[0] not in {
                "image/png", "image/jpeg", "image/webp"}:
            return b""
        result = bytearray()
        for chunk in response.iter_content(32768):
            result.extend(chunk)
            if len(result) > 2_000_000:
                return b""
        return bytes(result)


def fetch_item(url, session_id, destination, progress, organize=None, cancel=None, attempts=3):
    downloader = DesktopTSRDownload(parse_url(url), session_id)
    with downloader.session:
        path = downloader.download(destination, progress, organize, cancel, attempts)
    try:
        category = " / ".join(getDownloadCategory(path))
    except (OSError, ValueError):
        category = "Uncategorized"
    return {"path": path, "category": category, "status": "Complete", "detail": ""}
