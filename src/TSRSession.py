from __future__ import annotations
import requests
from typing import Optional
from logger import logger


class TSRSession:
    def __init__(self, sessionId: Optional[str] = None) -> None:
        logger.debug("Creating new TSRSession")
        self.session = requests.Session()
        self.tsrdlsession = ""

        if not sessionId:
            logger.info(
                "No saved TSR download session found; downloads will use fresh tickets."
            )
            return

        logger.debug("SessionId is not none")
        if self.__isValidSessionId(sessionId):
            logger.debug("SessionId is valid")
            self.tsrdlsession = sessionId
            return

        logger.info(
            "Saved TSR download session is invalid; downloads will use fresh tickets."
        )

    def __isValidSessionId(self, sessionId: str) -> bool:
        logger.debug(f"Checking if SessionId: {sessionId} is valid")
        try:
            self.__getTSRDLTicketCookie()
            r = self.session.get(
                "https://www.thesimsresource.com/downloads/download/itemId/1646133",
                cookies={"tsrdlsession": sessionId},
                timeout=30,
            )
            return (
                r.url == "https://www.thesimsresource.com/downloads/download/itemId/1646133"
            )
        except requests.exceptions.RequestException as e:
            logger.warning(f"Session validation failed due to network error: {e}")
            return False

    def __getTSRDLTicketCookie(self) -> str:
        logger.debug("Getting TSRDLTicket cookie")
        response = self.session.get(
            "https://www.thesimsresource.com/ajax.php?c=downloads&a=initDownload&itemid=1646133&setItems=&format=zip",
            timeout=30,
        )
        return response.cookies.get("tsrdlticket")
