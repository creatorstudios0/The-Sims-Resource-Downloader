"""Searchable session activity and notification views."""
from collections import deque
from datetime import datetime
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QVBoxLayout, QWidget

from qt_theme import button, label, row
from qt_tokens import ERROR, SUCCESS, WARNING, palette

LEVELS = {"DEBUG": "#A8A5B2", "INFO": "#D4D6E4", "SUCCESS": SUCCESS,
          "WARNING": WARNING, "ERROR": ERROR, "CRITICAL": ERROR}


class ConsoleHandler(logging.Handler):
    def __init__(self, display):
        super().__init__()
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", "%H:%M:%S"))
        self.display = display

    def emit(self, record):
        self.display(record.levelname, self.format(record))


class ActivityConsole(QWidget):
    def __init__(self, open_logs):
        super().__init__()
        self.entries = deque(maxlen=3000)
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search logs…")
        self.search.setAccessibleName("Search activity log")
        self.level = QComboBox()
        self.level.setAccessibleName("Filter log level")
        self.level.addItems(["All levels", "Debug", "Info", "Warning", "Error", "Critical"])
        self.output = QPlainTextEdit()
        self.output.setObjectName("activityConsole")
        self.output.setAccessibleName("Activity log")
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(self.entries.maxlen)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        toolbar = row(self.search, self.level, button("Open log folder", open_logs, glyph="folder"),
                      button("Copy visible", self.copy), button("Clear session", self.clear))
        toolbar.setStretch(0, 1)
        shell.addLayout(toolbar)
        self.summary = label("", "secondary")
        shell.addWidget(self.summary)
        shell.addWidget(self.output, 1)
        self.search.textChanged.connect(self.rebuild)
        self.level.currentTextChanged.connect(self.rebuild)
        self.rebuild()

    def matches(self, level, text):
        selected = self.level.currentText()
        return (selected == "All levels" or selected.upper() == level) and self.search.text().casefold() in text.casefold()

    def insert(self, cursor, level, text):
        if cursor.position():
            cursor.insertBlock()
        style = QTextCharFormat()
        style.setForeground(QColor(LEVELS.get(level, palette("Midnight").text)))
        # Keep each event in one QTextBlock so eviction preserves multiline messages.
        display_text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u2029", "\n")
        cursor.insertText(display_text.replace("\n", "\u2028"), style)

    def append(self, level, text):
        at_capacity = len(self.entries) == self.entries.maxlen
        self.entries.append((level, text))
        if at_capacity and (self.search.text() or self.level.currentIndex()):
            self.rebuild()
        elif self.matches(level, text):
            bar = self.output.verticalScrollBar()
            follow = bar.value() == bar.maximum()
            cursor = QTextCursor(self.output.document())
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.insert(cursor, level, text)
            if follow:
                bar.setValue(bar.maximum())
        self.update_summary()

    def rebuild(self):
        self.output.clear()
        cursor = QTextCursor(self.output.document())
        cursor.beginEditBlock()
        for level, text in self.entries:
            if self.matches(level, text):
                self.insert(cursor, level, text)
        cursor.endEditBlock()
        self.update_summary()

    def update_summary(self):
        self.summary.setText("Showing filtered session events" if self.search.text() or self.level.currentIndex()
                             else f"{len(self.entries):,} session " + ("event" if len(self.entries) == 1 else "events"))

    def copy(self):
        QApplication.clipboard().setText(self.output.toPlainText())

    def clear(self):
        self.entries.clear()
        self.rebuild()


class Notifications:
    def __init__(self, control):
        self.control = control
        self.entries = deque(maxlen=100)
        self.unread = 0
        self.refresh_dialog = None
        self.update_label()

    def update_label(self):
        name = "Notifications" + (f" ({self.unread})" if self.unread else "")
        self.control.setText(name)
        self.control.setAccessibleName(name)
        self.control.setToolTip("Open session notifications (Ctrl+Shift+N)")

    def add(self, level, message):
        self.entries.appendleft((datetime.now().strftime("%H:%M"), level.upper(), message))
        if self.refresh_dialog:
            self.refresh_dialog()
        else:
            self.unread = min(100, self.unread + 1)
            self.update_label()

    def open(self, parent):
        self.unread = 0
        self.update_label()
        dialog = QDialog(parent)
        dialog.setWindowTitle("Notifications")
        dialog.resize(550, 375)
        layout = QVBoxLayout(dialog)
        entries = QListWidget()
        entries.setAccessibleName("Session notification history")
        entries.setWordWrap(True)
        empty = label("You’re caught up. Download, install, and scan messages appear here during this session.",
                      "secondary", True)
        layout.addWidget(empty)
        layout.addWidget(entries, 1)

        def render():
            entries.clear()
            empty.setVisible(not self.entries)
            entries.setVisible(bool(self.entries))
            for stamp, level, message in self.entries:
                item = QListWidgetItem(f"{stamp}  ·  {level.title()}\n{message}")
                item.setForeground(QColor(LEVELS.get(level, LEVELS["INFO"])))
                entries.addItem(item)
            clear.setEnabled(bool(self.entries))

        def clear_all():
            self.entries.clear()
            self.unread = 0
            self.update_label()
            render()

        clear = button("Clear notifications", clear_all)
        layout.addLayout(row(clear, None, button("Close", dialog.accept)))
        render()
        self.refresh_dialog = render
        try:
            dialog.exec()
        finally:
            self.refresh_dialog = None
