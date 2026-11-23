"""Accept browser handoffs for the Windows desktop installer."""
import hashlib
from pathlib import Path
import re
import sys
from time import monotonic
import winreg

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


SCHEME = "sims4modlibrary"
REGISTRY_KEY = rf"Software\Classes\{SCHEME}"
OWNER = "Sims 4 Mod Library"
MAX_LINK_BYTES = 160
LINK = re.compile(r"sims4modlibrary://curseforge/install\?project=([1-9][0-9]{0,9})&file=([1-9][0-9]{0,9})")


def parse_install_link(url):
    match = LINK.fullmatch(url)
    if not match:
        raise ValueError("This website link is not a supported Sims 4 Mod Library install request.")
    project, file = map(int, match.groups())
    if max(project, file) > 2**32 - 1:
        raise ValueError("The website link contains an invalid CurseForge ID.")
    return project, file


def set_registration(enabled):
    if not getattr(sys, "frozen", False):
        raise ValueError("Website links are available in the packaged Windows app.")
    executable = str(Path(sys.executable).resolve())
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
            try:
                owner = winreg.QueryValueEx(key, "SimsModLibraryOwner")[0]
            except FileNotFoundError:
                owner = None
            if owner != OWNER:
                raise ValueError("Another program has registered the Sims 4 Mod Library website link.")
    except FileNotFoundError:
        if not enabled:
            return
    if enabled:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
            winreg.SetValueEx(key, "SimsModLibraryOwner", 0, winreg.REG_SZ, OWNER)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Sims 4 Mod Library")
            with winreg.CreateKey(key, r"shell\open\command") as command:
                value = f'"{executable}" "%1"'
                winreg.SetValueEx(command, "", 0, winreg.REG_SZ, value)
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    else:
        for suffix in (r"\shell\open\command", r"\shell\open", r"\shell", ""):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY + suffix)
            except FileNotFoundError:
                continue


def socket_name(state_path):
    path = str(Path(state_path).resolve()).casefold().encode("utf-8")
    return "sims4modlibrary-" + hashlib.sha256(path).hexdigest()[:24]


class WebsiteLinkServer(QObject):
    received = Signal(str)

    def __init__(self, state_path, parent):
        super().__init__(parent)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.accept_connection)
        if not self.server.listen(socket_name(state_path)):
            raise OSError("The website link listener could not start.")

    def accept_connection(self):
        while self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            connection.setReadBufferSize(MAX_LINK_BYTES + 1)
            connection.disconnected.connect(connection.deleteLater)
            connection.readyRead.connect(lambda client=connection: self.read_request(client))
            QTimer.singleShot(2000, connection, connection.abort)
            self.read_request(connection)

    def read_request(self, connection):
        if connection.bytesAvailable() > MAX_LINK_BYTES:
            connection.abort()
        elif connection.canReadLine():
            value = bytes(connection.readLine()).rstrip(b"\n")
            try:
                url = value.decode("ascii")
                parse_install_link(url)
            except (UnicodeError, ValueError):
                connection.abort()
                return
            connection.write(b"OK")
            connection.disconnectFromServer()
            QTimer.singleShot(0, self, lambda: self.received.emit(url))


def forward_link(state_path, value):
    parse_install_link(value)
    deadline = monotonic() + 2
    while monotonic() < deadline:
        connection = QLocalSocket()
        connection.connectToServer(socket_name(state_path))
        if not connection.waitForConnected(250):
            continue
        connection.write(value.encode("ascii") + b"\n")
        if connection.bytesToWrite() and not connection.waitForBytesWritten(500):
            return False
        if not connection.bytesAvailable() and not connection.waitForReadyRead(800):
            return False
        return bytes(connection.read(2)) == b"OK"
    return False
