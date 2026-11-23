"""Create the Windows icon from the original Qt workspace SVG glyph."""
from pathlib import Path
import struct
import sys

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from qt_theme import ICONS


def main(destination):
    app = QGuiApplication([])
    path = ICONS["brand"]
    svg = QByteArray(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#101722"/><path d="{path}" transform="translate(4 4)" fill="none" stroke="#46DFAE" stroke-width="1.6" stroke-linejoin="round"/></svg>'.encode())
    renderer = QSvgRenderer(svg)
    directory, images = [], []
    sizes = (16, 24, 32, 48, 64, 128, 256)
    offset = 6 + 16 * len(sizes)
    for size in sizes:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        target = QBuffer()
        target.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(target, "PNG")
        data = bytes(target.data())
        dimension = size % 256
        directory.append(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset))
        images.append(data)
        offset += len(data)
    Path(destination).write_bytes(struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(directory + images))


if __name__ == "__main__":
    main(sys.argv[1])
