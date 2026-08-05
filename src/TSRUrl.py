from __future__ import annotations
from exceptions import InvalidURL
from logger import logger
import re, requests


class TSRUrl:
    def __init__(self, url: str):
        if self.__isValidUrl(url):
            self.url = url
            self.itemId = self.__getItemId(url)
            self.downloadUrl = f"https://www.thesimsresource.com/downloads/download/itemId/{self.itemId}"
        else:
            raise InvalidURL(url)

    def __getItemId(self, url: str) -> int | None:
        itemId = (
            re.search(r"(?<=/id/)[\d]+", url)
            or re.search(r"(?<=/itemId/)[\d]+", url)
            or re.search(r"(?<=.com/downloads/)[\d]+", url)
        )
        logger.debug(
            f"Got ItemId: {itemId[0] if itemId is not None else 'None'} from Url: {url}"
        )
        return None if itemId is None else int(itemId[0])

    def __isValidUrl(self, url: str) -> bool:
        isUrlValid = (
            re.search(r"thesimsresource.com/", url) is not None
            and self.__getItemId(url) is not None
        )
        logger.debug(f"Is url valid: {isUrlValid}")
        return isUrlValid

    def isVipExclusive(self) -> bool:
        try:
            r = requests.get(self.url, timeout=30)
            return "VIP Exclusive" in r.text
        except requests.exceptions.RequestException:
            logger.warning(f"Could not check VIP status for {self.url}, assuming not VIP.")
            return False

    @staticmethod
    def getRequiredItems(url: "TSRUrl") -> list["TSRUrl"]:
        def convertHrefToTSRUrl(href: str) -> TSRUrl:
            logger.debug(f"Converting {href} to TSRUrl")
            return TSRUrl(f"https://www.thesimsresource.com{href}")

        logger.debug(f"Getting required items for {url.url}")
        try:
            r = requests.get(f"https://www.thesimsresource.com/downloads/{url.itemId}", timeout=30)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not fetch required items for {url.url}: {e}")
            return []
        return list(
            map(
                convertHrefToTSRUrl,
                re.findall(
                    r'(?<=<li class="required-download-item"><a href=")/downloads/[\d]+(?=")',
                    r.text,
                ),
            )
        )
