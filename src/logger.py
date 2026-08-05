import ctypes, logging, os, sys, traceback
from typing import Type
from types import TracebackType
from config import CONFIG


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[90m",
        logging.INFO: "\033[36m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        if not CONFIG.get("colorConsole", True):
            return message
        return f"{self.COLORS.get(record.levelno, '')}{message}{self.RESET}"


def enableWindowsColors() -> None:
    if os.name != "nt":
        return

    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


enableWindowsColors()
streamHandler = logging.StreamHandler(sys.stdout)
streamHandler.setFormatter(ColorFormatter("[%(levelname)s] %(message)s"))
logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    filename="logs.log",
    level=logging.DEBUG if CONFIG.get("debug") == True else logging.INFO,
)
logger = logging.getLogger(__name__)
logger.addHandler(streamHandler)


def exceptionHandler(
    type: Type[BaseException], value: BaseException, tb: TracebackType
):
    for line in traceback.TracebackException(type, value, tb).format(chain=True):
        logging.exception(line)
    logging.exception(type, value, tb)
    sys.__excepthook__(type, value, tb)


sys.excepthook = exceptionHandler
