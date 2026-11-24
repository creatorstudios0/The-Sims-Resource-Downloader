"""Qt workspace for the existing TSR downloader and Sims 4 installer."""
from datetime import datetime, timedelta
from pathlib import Path
import csv
import logging
import os
import sys

from PySide6.QtCore import QBuffer, QIODevice, QByteArray, QPropertyAnimation, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QIcon, QImageReader, QPixmap, QColor, QDesktopServices, QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog,
    QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QInputDialog, QLineEdit, QListWidget,
    QListView, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QSpinBox, QSplitter,
    QStackedWidget, QVBoxLayout, QWidget,
)

import curseforge
from logger import logger
from qt_discover import DiscoverPage
from qt_services import (
    BUSY, DATA_DIR, LABELS, LOOKUP, RELEASES, STATE_PATH, VERSION, WAITING,
    LibraryService, failure_message, release_info, settings_defaults, size_label,
)
from qt_theme import (
    ProgressPainter, ToggleSwitch, button, icon, label, row, scroll_area, selected, surface, table,
    theme, update_rows,
)
from sims_install import installed_path, MOD_EXTENSIONS
from desktop_data import fetch_thumbnail
from library_insights import audit_to_file, format_summary
from palette_search import match_commands
from windows_folders import detect_game
from website_links import WebsiteLinkServer, forward_link, parse_install_link, set_registration

NAV = [
    ("Dashboard", "home", "Track your Sims 4 content and recent activity."),
    ("Download Queue", "queue", "Review TSR links and manage active downloads."),
    ("My Mod Library", "library", "Browse downloaded content and files in your Mods folder."),
    ("Install History", "history", "Review installs, quarantine changes, and uninstall results."),
    ("Discover", "search", "Find Sims 4 content on CurseForge and The Sims Resource."),
    ("Console", "console", "Follow downloads, installs, library scans, and errors."),
    ("Settings", "settings", "Manage folders, downloads, library scanning, and appearance."),
]
LOCAL_FILES = "Sims 4 content (*.zip *.package *.ts4script *.trayitem *.blueprint *.bpi *.hhi *.sgi *.householdbinary *.room *.rmi)"


def local_date(value):
    return value[:16].replace("T", " ") if value else "Unknown"


def open_path(path):
    path = Path(path)
    if path.is_file():
        path = path.parent
    if path.is_dir():
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    return False


def page_layout():
    widget = QWidget()
    widget.setObjectName("workspace")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    return widget, layout


class ConsoleHandler(logging.Handler):
    def __init__(self, display):
        super().__init__(logging.INFO)
        self.display = display
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%H:%M:%S"))

    def emit(self, record):
        self.display(self.format(record))


class MainWindow(QMainWindow):
    console_line = Signal(str)

    def __init__(self, service):
        super().__init__()
        self.s = service
        self.setWindowTitle("CreatorStudios • Sims 4 Mod Library")
        self.setWindowIcon(icon("brand", "#A996FF"))
        self.resize(1320, 850)
        self.setMinimumSize(785, 605)
        self.collapsed = self.manual_collapse = self.closing = False
        self.profile = None
        self.library_entries = {}
        self.thumbnails = {}
        self.thumbnail_requested = set()
        self.recent_items = {}
        self.website_previews = set()
        self.website_review = False
        self.setup()
        self.apply_theme()
        geometry = self.s.state.get("windowGeometry")
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
        self.s.changed.connect(self.refresh)
        self.s.transfer_changed.connect(self.refresh_transfer)
        self.s.notice.connect(self.toast)
        self.s.job_done.connect(self.job_done)
        self.s.download_ready.connect(self.website_download_ready)
        QApplication.clipboard().dataChanged.connect(self.clipboard_changed)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.focus_import)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.command_palette)
        self.go(0)
        self.refresh()
        self.s.auto_scan()
        self.s.check_patch()
        self.s.pump_installs()
        if self.s.recovered:
            self.inform(f"Recovered the library from {self.s.recovered.name}.", "success")
            logger.info("Recovered library from %s", self.s.recovered.name)
        if self.s.backup_error:
            self.inform(self.s.backup_error, "warning")

    def setup(self):
        root = QWidget()
        root.setObjectName("workspace")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.setCentralWidget(root)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(224)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14, 16, 14, 16)
        side.setSpacing(8)
        self.brand = button("CREATORSTUDIOS", self.toggle_sidebar, glyph="brand")
        self.brand.setObjectName("brandButton")
        self.brand.setToolTip("Collapse or expand navigation")
        self.brand.setAccessibleName("Toggle sidebar")
        self.brand.setProperty("nav", True)
        side.addWidget(self.brand)
        side.addSpacing(12)
        self.workspace_label = label("SIMS 4 WORKSPACE", "eyebrow")
        self.preferences_label = label("PREFERENCES", "eyebrow")
        side.addWidget(self.workspace_label)
        self.nav = QButtonGroup(self)
        self.nav_buttons = []
        for index, (name, glyph, _) in enumerate(NAV):
            if name == "Settings":
                side.addSpacing(16)
                side.addWidget(self.preferences_label)
            control = button(name, lambda checked=False, page=index: self.go(page), glyph=glyph)
            control.setCheckable(True)
            control.setProperty("nav", True)
            control.setToolTip(name)
            control.setAccessibleName(name)
            self.nav.addButton(control, index)
            self.nav_buttons.append(control)
            side.addWidget(control)
        side.addStretch()
        self.health_label = label("Library health · awaiting scan", "secondary", True)
        self.release_status = label("", "secondary", True)
        self.version_label = label(f"CREATORSTUDIOS  ·  v{VERSION}", "eyebrow")
        for widget in (self.health_label, self.release_status, self.version_label):
            side.addWidget(widget)
        shell.addWidget(self.sidebar)
        main = QWidget()
        main.setObjectName("workspace")
        content = QVBoxLayout(main)
        content.setContentsMargins(24, 20, 24, 16)
        content.setSpacing(14)
        header = QVBoxLayout()
        header.setSpacing(3)
        self.title = label("", "pageTitle")
        self.description = label("", "secondary", True)
        header.addWidget(self.title)
        header.addWidget(self.description)
        self.releases = button("Check releases", self.check_releases, glyph="refresh")
        self.quick_switch = button("Quick switch  Ctrl+K", self.command_palette, glyph="search")
        self.quick_switch.setAccessibleName("Open quick switch command palette")
        line = QHBoxLayout()
        line.addLayout(header, 1)
        line.addWidget(self.quick_switch, alignment=Qt.AlignmentFlag.AlignTop)
        line.addWidget(self.releases, alignment=Qt.AlignmentFlag.AlignTop)
        content.addLayout(line)
        self.pages = QStackedWidget()
        for builder in (self.dashboard_page, self.queue_page, self.library_page, self.history_page,
                        self.discover_page, self.console_page, self.settings_page):
            self.pages.addWidget(builder())
        content.addWidget(self.pages, 1)

        self.toast_frame = QFrame()
        self.toast_frame.setObjectName("toast")
        bar = QHBoxLayout(self.toast_frame)
        bar.setContentsMargins(12, 5, 6, 5)
        self.toast_content = label("", wrap=True)
        self.toast_content.setTextFormat(Qt.TextFormat.PlainText)
        bar.addWidget(self.toast_content, 1)
        close = button("×", self.toast_frame.hide)
        close.setToolTip("Dismiss notification")
        close.setAccessibleName("Dismiss notification")
        bar.addWidget(close)
        content.addWidget(self.toast_frame)
        self.toast_frame.hide()
        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.timeout.connect(self.toast_frame.hide)
        shell.addWidget(main, 1)

    def go(self, index):
        self.pages.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
        self.title.setText(NAV[index][0])
        self.description.setText(NAV[index][2])

    def command_palette(self):
        """Keyboard-first navigation without changing the existing workflows."""
        actions = [
            {"title": name, "description": description, "keywords": glyph,
             "run": lambda index=index: self.go(index)}
            for index, (name, glyph, description) in enumerate(NAV)
        ]
        actions.extend([
            {"title": "Import local content", "description": "Choose Sims 4 files to install",
             "keywords": "mods package zip", "run": self.add_files},
            {"title": "Scan library", "description": "Inspect folders and refresh library health",
             "keywords": "health duplicates", "run": self.s.scan},
            {"title": "Open Mods folder", "description": "View installed Sims 4 mods",
             "keywords": "files explorer", "run": lambda: self.open_setting_folder("Mods")},
            {"title": "Check for releases", "description": "Check for application updates",
             "keywords": "update version", "run": self.check_releases},
            {"title": "Search my mods", "description": "Filter installed content",
             "keywords": "library find", "run": self.focus_search},
        ])
        dialog = QDialog(self)
        dialog.setWindowTitle("CreatorStudios · Quick switch")
        dialog.setMinimumWidth(500)
        panel = QVBoxLayout(dialog)
        panel.setContentsMargins(16, 16, 16, 16)
        panel.addWidget(label("QUICK SWITCH", "eyebrow"))
        search = QLineEdit()
        search.setPlaceholderText("Find a page or action…")
        search.setAccessibleName("Search commands")
        panel.addWidget(search)
        results = QListWidget()
        results.setAccessibleName("Matching commands")
        panel.addWidget(results)
        hint = label("Enter to select  ·  Escape to close  ·  Ctrl+K to open", "secondary")
        panel.addWidget(hint)
        visible = []

        def update(text):
            visible[:] = match_commands(actions, text)
            results.clear()
            for action in visible:
                results.addItem(f"{action['title']}   ·   {action['description']}")
            if visible:
                results.setCurrentRow(0)
            hint.setText(f"{len(visible)} actions found  ·  Enter to open" if visible else "No matching actions")

        def execute():
            index = results.currentRow()
            if 0 <= index < len(visible):
                callback = visible[index]["run"]
                dialog.accept()
                callback()

        search.textChanged.connect(update)
        search.returnPressed.connect(execute)
        results.itemActivated.connect(lambda _: execute())
        update("")
        search.setFocus()
        dialog.exec()

    def focus_import(self):
        self.go(1)
        self.links.setFocus()

    def focus_search(self):
        self.go(2)
        self.search.setFocus()

    def toggle_sidebar(self):
        self.manual_collapse = not self.manual_collapse
        self.adapt_sidebar()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "sidebar"):
            self.adapt_sidebar()

    def adapt_sidebar(self):
        collapsed = self.width() < 1020 or self.manual_collapse
        if collapsed == self.collapsed:
            return
        self.collapsed = collapsed
        self.sidebar.setFixedWidth(76 if collapsed else 224)
        self.brand.setText("" if collapsed else "CREATORSTUDIOS")
        for index, control in enumerate(self.nav_buttons):
            control.setText("" if collapsed else NAV[index][0])
        for control in (self.workspace_label, self.preferences_label, self.health_label, self.release_status, self.version_label):
            control.setVisible(not collapsed)

    def apply_theme(self):
        compact = self.s.settings["density"] == "Compact"
        accent = self.s.settings["accent"]
        QApplication.instance().setStyleSheet(theme(accent, compact))
        animate = self.s.settings["animations"] and not os.environ.get("QT_REDUCED_MOTION")
        for control in self.findChildren(ToggleSwitch):
            control.set_appearance(accent, animate)
        for view in (self.queue_view, self.library_list, self.history_view, self.recent, self.discover.results):
            view.verticalHeader().setDefaultSectionSize(29 if compact else 36)

    def toast(self, level, text, force=False):
        if not force and not self.s.settings["notifications"]:
            return
        self.toast_content.setText(text)
        self.toast_frame.setProperty("level", level)
        self.toast_frame.style().unpolish(self.toast_frame)
        self.toast_frame.style().polish(self.toast_frame)
        self.toast_frame.show()
        if self.s.settings["animations"] and not os.environ.get("QT_REDUCED_MOTION"):
            if hasattr(self, "fade"):
                self.fade.stop()
                self.fade.deleteLater()
            effect = QGraphicsOpacityEffect(self.toast_frame)
            self.toast_frame.setGraphicsEffect(effect)
            self.fade = QPropertyAnimation(effect, b"opacity", self.toast_frame)
            self.fade.setDuration(140)
            self.fade.setStartValue(0.4)
            self.fade.setEndValue(1.0)
            self.fade.start()
        else:
            self.toast_frame.setGraphicsEffect(None)
        self.toast_timer.start(6500)

    def inform(self, text, level="info"):
        self.toast(level, text, True)

    def confirm(self, title, text, detail=""):
        dialog = QMessageBox(QMessageBox.Icon.Question, title, text,
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        dialog.setDetailedText(detail)
        return dialog.exec() == QMessageBox.StandardButton.Yes

    def dashboard_page(self):
        page, layout = page_layout()
        layout.setContentsMargins(0, 0, 4, 4)
        layout.setSpacing(14)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        self.stats = []
        for column, (name, detail, glyph) in enumerate((
            ("Installed mods", "Package and script files", "library"),
            ("Download queue", "Waiting and active items", "queue"),
            ("Completed installs", "Successful install batches", "history"),
            ("Library storage", "Installed content on disk", "folder"),
        )):
            card, contents = surface("stat")
            contents.setSpacing(5)
            badge = label("", "metricIcon")
            badge.setFixedSize(30, 30)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setPixmap(icon(glyph, "#D5C8FF").pixmap(QSize(17, 17)))
            contents.addLayout(row(badge, None))
            contents.addWidget(label(name, "metricLabel", True))
            value = label("—", "statValue")
            contents.addWidget(value)
            contents.addWidget(label(detail, "secondary", True))
            contents.addStretch()
            metrics.addWidget(card, 0, column)
            metrics.setColumnStretch(column, 1)
            self.stats.append(value)
        layout.addLayout(metrics)

        quick, controls = surface("dashboardActions")
        controls.addLayout(row(
            label("Quick actions", "section"), None,
            button("Discover content", lambda: self.go(4), True, "search"),
            button("Import files", self.add_files, glyph="plus"),
            button("View library", lambda: self.go(2), glyph="library"),
        ))
        layout.addWidget(quick)

        health, contents = surface()
        contents.addLayout(row(
            label("Library health", "section"), None,
            button("Scan library", self.s.scan, glyph="refresh"),
            button("Export mod audit", self.export_audit, glyph="folder"),
        ))
        self.diagnostics = label("", "secondary", True)
        contents.addWidget(self.diagnostics)
        layout.addWidget(health)

        maintenance = QGridLayout()
        maintenance.setHorizontalSpacing(12)
        maintenance.setColumnStretch(0, 1)
        maintenance.setColumnStretch(1, 1)

        patch, controls = surface()
        controls.addWidget(label("Patch Day Checkup", "section"))
        self.patch_summary = label("", "secondary", True)
        controls.addWidget(self.patch_summary)
        controls.addStretch()
        self.patch_check = button("Check game version", self.s.check_patch, glyph="refresh")
        self.patch_reviewed = button("Mark reviewed", self.s.mark_patch_reviewed, glyph="check")
        advice = "https://help.ea.com/en/articles/the-sims/the-sims-4/mods-and-the-sims-4-game-updates/"
        patch_actions = QGridLayout()
        patch_actions.addWidget(self.patch_check, 0, 0)
        patch_actions.addWidget(button("Review script mods", self.review_script_mods), 0, 1)
        patch_actions.addWidget(self.patch_reviewed, 1, 0)
        patch_actions.addWidget(button("EA patch guide", lambda: QDesktopServices.openUrl(QUrl(advice))), 1, 1)
        controls.addLayout(patch_actions)
        maintenance.addWidget(patch, 0, 0)

        backup, controls = surface()
        controls.addWidget(label("Mods and Tray backups", "section"))
        self.backup_summary = label("", "secondary", True)
        self.backup_summary.setTextFormat(Qt.TextFormat.PlainText)
        controls.addWidget(self.backup_summary)
        controls.addStretch()
        self.backup_create = button("Create backup ZIP", self.create_content_backup, True, "plus")
        self.backup_open = button("Open last backup", self.open_content_backup, glyph="folder")
        controls.addWidget(self.backup_create, alignment=Qt.AlignmentFlag.AlignLeft)
        controls.addWidget(self.backup_open, alignment=Qt.AlignmentFlag.AlignLeft)
        maintenance.addWidget(backup, 0, 1)
        layout.addLayout(maintenance)

        recent, contents = surface()
        contents.addLayout(row(
            label("Recently installed", "section"), None,
            button("View install history", lambda: self.go(3), glyph="history"),
        ))
        self.recent_empty = label("No installations have been recorded yet.", "secondary", True)
        contents.addWidget(self.recent_empty)
        self.recent, self.recent_model = table(["Mod", "Creator", "Category", "Status", "Installed"], [165, 117, 110, 90])
        self.recent.setMinimumHeight(155)
        contents.addWidget(self.recent)
        layout.addWidget(recent)
        layout.addStretch()
        return scroll_area(page)

    def review_script_mods(self):
        self.go(2)
        self.category_filter.setCurrentText("All categories")
        self.profile_control.setCurrentIndex(0)
        self.search.setText(".ts4script")
        self.search.setFocus()
        self.s.scan()

    def create_content_backup(self):
        folder = Path(self.s.settings["backup"])
        if not folder.is_dir():
            folder = Path.home() / "Documents"
        name = datetime.now().strftime("Sims 4 Content Backup %Y-%m-%d %H%M%S.zip")
        target, _ = QFileDialog.getSaveFileName(
            self, "Back up Mods and Tray", str(folder / name), "ZIP archives (*.zip)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if target:
            try:
                self.s.create_content_backup(target)
            except (OSError, ValueError) as error:
                self.inform(failure_message(error), "error")

    def open_content_backup(self):
        path = self.s.state.get("lastContentBackup", {}).get("path")
        if path and Path(path).is_file():
            if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                return
        self.inform("The last backup ZIP could not be opened.", "warning")

    def refresh_recovery(self):
        current, reviewed = self.s.patch_versions()
        checking = "patch-check" in self.s.jobs
        if checking:
            self.patch_summary.setText("Checking the installed game version…")
        elif not self.s.game():
            self.patch_summary.setText("Choose your Sims 4 user data folder in Settings.")
        elif not current:
            self.patch_summary.setText("Game version unavailable. Launch The Sims 4 once, then check again.")
        elif current != reviewed:
            self.patch_summary.setText(
                f"Game version changed from {reviewed or 'unknown'} to {current}. Review script mods before re-enabling them."
            )
        else:
            self.patch_summary.setText(f"Game version {current} · reviewed baseline")
        self.patch_check.setEnabled(bool(self.s.game()) and not checking)
        self.patch_reviewed.setEnabled(bool(current and current != reviewed and not checking))
        backing_up = "content-backup" in self.s.jobs
        last = self.s.state.get("lastContentBackup", {})
        if backing_up:
            self.backup_summary.setText("Creating a ZIP of Mods and Tray…")
        elif last:
            self.backup_summary.setText(f"Last backup · {Path(last['path']).name} · {last['files']} files")
        else:
            self.backup_summary.setText("Save a ZIP with your Mods and Tray folder structure.")
        self.backup_create.setEnabled(bool(self.s.game()) and not self.s.mutating_files())
        self.backup_open.setEnabled(bool(last) and not backing_up)

    def discover_page(self):
        self.discover = DiscoverPage(self)
        return self.discover

    def console_page(self):
        page, layout = page_layout()
        self.console = QPlainTextEdit()
        self.console.setObjectName("activityConsole")
        self.console.setAccessibleName("Activity console")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(3000)
        self.console.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addLayout(row(label("Activity log", "section"), None,
                             button("Open log folder", self.open_logs, glyph="folder"),
                             button("Copy log", lambda: QApplication.clipboard().setText(self.console.toPlainText())),
                             button("Clear", self.console.clear)))
        layout.addWidget(self.console, 1)
        self.console_line.connect(self.console.appendPlainText, Qt.ConnectionType.QueuedConnection)
        handler = ConsoleHandler(self.console_line.emit)
        self.console_handler = handler
        logger.addHandler(handler)
        self.destroyed.connect(lambda: logger.removeHandler(handler))
        self.console.appendPlainText(f"Sims 4 Mod Library {VERSION} started.")
        return page

    def queue_page(self):
        page, layout = page_layout()
        panel, form = surface()
        form.addLayout(row(label("Import TSR links", "section"), None, button("Import link list", self.import_links, glyph="folder")))
        self.links = QPlainTextEdit()
        self.links.setPlaceholderText("Paste one or more The Sims Resource item links")
        self.links.setAccessibleName("The Sims Resource links")
        self.links.setFixedHeight(63)
        form.addWidget(self.links)
        self.clipboard_toggle = ToggleSwitch("Watch clipboard")
        self.clipboard_toggle.setChecked(self.s.settings["watch"])
        self.clipboard_toggle.toggled.connect(self.toggle_clipboard)
        form.addLayout(row(button("Review links", self.review_links, True, "link"), self.clipboard_toggle, None))
        self.validation = QPlainTextEdit()
        self.validation.setReadOnly(True)
        self.validation.setAccessibleName("Link validation results")
        self.validation.setMaximumHeight(75)
        self.validation.hide()
        form.addWidget(self.validation)
        layout.addWidget(panel)
        self.download_button = button("Download selected", lambda: self.s.queue(self.queue_keys()), True)
        self.pause_button = button("Resume queue", lambda: self.s.set_paused(not self.s.paused))
        self.retry_button = button("Retry / recheck", lambda: self.s.retry(self.queue_keys()))
        self.dependency_button = button("Dependencies", lambda: self.dependencies(self.queue_keys()))
        layout.addLayout(row(self.download_button, self.pause_button, self.retry_button, self.dependency_button, None))
        self.cancel_button = button("Cancel selected", self.cancel_selected)
        self.remove_button = button("Remove selected", self.remove_selected)
        self.clear_button = button("Clear completed", self.clear_completed)
        self.queue_status = label("", "secondary")
        layout.addLayout(row(self.cancel_button, self.remove_button, self.clear_button, None, self.queue_status))
        self.queue_busy = QProgressBar()
        self.queue_busy.setRange(0, 0)
        self.queue_busy.setFixedHeight(5)
        self.queue_busy.setTextVisible(False)
        self.queue_busy.setAccessibleName("Waiting for download or metadata")
        self.queue_busy.hide()
        layout.addWidget(self.queue_busy)
        self.queue_empty = label("Your download queue is empty. Add a mod link to get started.", "secondary", True)
        layout.addWidget(self.queue_empty)
        self.queue_view, self.queue_model = table(
            ["Mod", "Creator", "Source", "Size", "Status", "Progress", "Speed", "ETA", "Detail"],
            [153, 91, 67, 73, 111, 91, 80, 64])
        self.queue_view.setItemDelegateForColumn(5, ProgressPainter(self.queue_view))
        self.queue_view.setAccessibleName("Download queue")
        self.queue_view.selectionModel().selectionChanged.connect(self.queue_actions)
        self.queue_view.doubleClicked.connect(lambda _: self.dependencies(self.queue_keys()))
        layout.addWidget(self.queue_view, 1)
        return page

    def queue_keys(self):
        return [key for key in selected(self.queue_view) if key in self.s.items]

    def import_links(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import TSR link list", "", "Text files (*.txt)")
        if path:
            try:
                self.show_validation(self.s.import_text(Path(path).read_text(encoding="utf-8-sig")))
                self.go(1)
            except (OSError, ValueError) as error:
                self.inform(failure_message(error), "error")

    def review_links(self):
        text = self.links.toPlainText().strip()
        if not text:
            self.inform("Paste a TSR item link to review.", "warning")
            return
        result = self.s.import_text(text)
        self.show_validation(result)
        if any(status == "Added for review" for _, status in result):
            self.links.clear()

    def show_validation(self, result):
        self.validation.setPlainText("\n".join(f"{status}  |  {value}" for value, status in result))
        self.validation.setVisible(bool(result))

    def clipboard_changed(self):
        if self.s.settings["watch"] and not self.s.closing:
            entries = [entry for entry in QApplication.clipboard().text().split()
                       if "thesimsresource.com/" in entry.casefold()]
            if entries:
                result = self.s.import_text(" ".join(entries))
                self.show_validation(result)
                if any(status == "Added for review" for _, status in result):
                    self.inform("Clipboard links added for review.")

    def toggle_clipboard(self, checked):
        self.s.settings["watch"] = checked
        self.s.save()
        self.setting_controls["watch"].setChecked(checked)

    def cancel_selected(self):
        keys = [key for key in self.queue_keys() if self.s.items[key]["status"] in WAITING | {"Downloading"}]
        if keys and self.confirm("Cancel downloads", f"Cancel {len(keys)} item(s)? Partial files will be kept."):
            self.s.cancel(keys)

    def remove_selected(self):
        keys = [key for key in self.queue_keys() if self.s.items[key]["status"] not in BUSY and key not in self.s.lookups]
        if keys and self.confirm("Remove downloads", f"Remove {len(keys)} item(s) from the queue?"):
            for key in keys:
                if self.s.items[key]["status"] == "Complete":
                    if key not in self.s.state["queueHidden"]:
                        self.s.state["queueHidden"].append(key)
                else:
                    self.website_previews.discard(key)
                    del self.s.items[key]
            self.s.publish()

    def clear_completed(self):
        hidden = set(self.s.state["queueHidden"])
        hidden.update(key for key, item in self.s.items.items() if item["status"] == "Complete" and item.get("url"))
        self.s.state["queueHidden"] = sorted(hidden)
        self.s.publish()

    def dependencies(self, keys):
        if not keys:
            return
        key = keys[0]
        item = self.s.items[key]
        lines, missing = [], []
        for dep in item.get("requires", []):
            child = self.s.items.get(dep, {})
            available = child.get("status") == "Complete" and Path(child.get("path", "")).is_file()
            lines.append(f"{child.get('name', 'TSR item ' + dep)} · {'Downloaded' if available else 'Missing'}")
            if not available:
                missing.append(dep)
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Required content")
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(item["name"])
        dialog.setInformativeText("\n".join(lines) or "No required files have been detected.")
        dialog.addButton(QMessageBox.StandardButton.Close)
        recheck = None if (key in self.s.lookups or key in self.s.active or item.get("source") == "CurseForge") else dialog.addButton("Check TSR", QMessageBox.ButtonRole.ActionRole)
        add = dialog.addButton("Review missing links", QMessageBox.ButtonRole.ActionRole) if missing else None
        dialog.exec()
        if recheck and dialog.clickedButton() == recheck:
            self.s.lookup(key, force_dependencies=True)
            self.s.publish()
            self.inform("Checking TSR for required content…")
        if add and dialog.clickedButton() == add:
            self.show_validation(self.s.import_text("\n".join("https://www.thesimsresource.com/downloads/" + dep for dep in missing)))
            self.go(1)

    def queue_cells(self, key):
        item = self.s.items[key]
        state = item["status"]
        progress = self.s.progress_data.get(key)
        bar = ("100%", 100) if state == "Complete" else "—"
        speed = eta = "—"
        if state == "Downloading":
            bar = ("Working", None)
            if progress:
                total, received, rate = progress["total"], progress["received"], progress["speed"]
                if total:
                    percentage = min(100, int(received / total * 100))
                    bar = (f"{percentage}%", percentage)
                if rate:
                    speed = size_label(rate) + "/s"
                    if total > received:
                        seconds = int((total - received) / rate)
                        eta = f"{seconds // 60}m {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"
        return (item["name"], item.get("creator") or "—", item.get("source", "TSR"), size_label(item.get("size")),
                "Paused" if state == "Queued" and self.s.paused else LABELS.get(state, state),
                bar, speed, eta, item.get("detail", ""))

    def refresh_transfer(self, key):
        self.queue_model.patch(key, self.queue_cells(key))
        self.refresh_queue_busy()

    def queue_actions(self):
        keys = self.queue_keys()
        states = {self.s.items[key]["status"] for key in keys}
        self.download_button.setEnabled(bool(states & WAITING))
        self.retry_button.setEnabled(bool(states & (LOOKUP | {"Paused", "Cancelled", "Download failed"})))
        self.cancel_button.setEnabled(bool(states & (WAITING | {"Downloading"})))
        self.remove_button.setEnabled(any(self.s.items[key]["status"] not in BUSY and key not in self.s.lookups for key in keys))
        self.dependency_button.setEnabled(len(keys) == 1 and self.s.items[keys[0]].get("source") != "CurseForge")
        self.clear_button.setEnabled(any(self.s.items[key]["status"] == "Complete" for key in self.queue_model.indices))
        self.pause_button.setText("Resume queue" if self.s.paused else "Pause queue")
        self.pause_button.setEnabled(not self.s.paused or any(item["status"] in {"Queued", "Paused"} for item in self.s.items.values()))
        if len(keys) == 1:
            self.request_thumbnail(keys[0])
        count = len(self.s.lookups)
        self.queue_status.setText(f"{len(self.s.active)} active" + (f" · Reviewing {count}" if count else ""))
        self.refresh_queue_busy()

    def refresh_queue_busy(self):
        unknown = any(not self.s.progress_data.get(key, {}).get("total") for key in self.s.active)
        self.queue_busy.setVisible(unknown or bool(self.s.lookups))

    def library_page(self):
        page, layout = page_layout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search mods, creators, and filenames")
        self.search.setAccessibleName("Search library")
        self.search.setMinimumWidth(120)
        self.search.textChanged.connect(self.refresh_library)
        self.category_filter = QComboBox()
        self.category_filter.setAccessibleName("Filter library category")
        self.category_filter.addItem("All categories")
        self.category_filter.currentTextChanged.connect(self.refresh_library)
        self.sort_order = QComboBox()
        self.sort_order.setAccessibleName("Sort library")
        self.sort_order.addItems(["Name A–Z", "Newest first", "Largest first"])
        self.sort_order.currentTextChanged.connect(self.refresh_library)
        controls = row(button("Import files", self.add_files, True, "plus"),
                       button("Refresh Library", self.s.scan, glyph="refresh"), self.category_filter, self.sort_order)
        controls.insertWidget(0, self.search, 1)
        layout.addLayout(controls)
        self.view_switch = QComboBox()
        self.view_switch.setAccessibleName("Grid or list view")
        self.view_switch.addItems(["List", "Grid"])
        self.view_switch.setCurrentText(self.s.state.get("libraryView", "List"))
        self.view_switch.currentIndexChanged.connect(self.switch_library)
        self.profile_control = QComboBox()
        self.profile_control.setAccessibleName("Library profile")
        self.profile_control.currentTextChanged.connect(self.profile_changed)
        layout.addLayout(row(self.view_switch, self.profile_control, button("Save profile", self.save_profile),
                             button("Profile backups", self.profile_backups), button("Export TSR links", self.export_links), None))
        self.library_empty = label("No mods found. Add local files or scan your Mods folder.", "secondary", True)
        layout.addWidget(self.library_empty)
        split = QSplitter()
        self.library_views = QStackedWidget()
        self.library_list, self.library_model = table(["Mod", "Category", "Type", "Size", "Status"], [154, 142, 68, 74])
        self.library_list.selectionModel().selectionChanged.connect(self.library_actions)
        self.library_views.addWidget(self.library_list)
        self.library_grid = QListView()
        self.library_grid.setViewMode(QListView.ViewMode.IconMode)
        self.library_grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.library_grid.setMovement(QListView.Movement.Static)
        self.library_grid.setWrapping(True)
        self.library_grid.setWordWrap(True)
        self.library_grid.setGridSize(QSize(136, 85))
        self.library_grid.setIconSize(QSize(25, 25))
        self.library_grid.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.grid_model = QStandardItemModel(self.library_grid)
        self.library_grid.setModel(self.grid_model)
        self.library_grid.selectionModel().selectionChanged.connect(self.library_actions)
        self.library_views.addWidget(self.library_grid)
        self.library_views.setCurrentIndex(self.view_switch.currentIndex())
        split.addWidget(self.library_views)
        details, info = surface()
        self.detail_title = label("Mod details", "section", True)
        self.detail_title.setTextFormat(Qt.TextFormat.PlainText)
        self.detail = label("Select a mod to see its details.", "secondary", True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.install_button = button("Install preview", self.preview_install, True)
        self.enable_button = button("Enable / disable", self.toggle_library)
        self.open_button = button("Open file location", self.open_library, glyph="folder")
        self.category_button = button("Edit category", self.edit_category)
        self.lib_deps = button("Check dependencies", self.library_dependencies)
        self.uninstall_button = button("Uninstall managed batch", self.uninstall_library)
        info.addWidget(self.detail_title)
        self.detail_image = label("")
        self.detail_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_image.hide()
        info.addWidget(self.detail_image)
        info.addWidget(self.detail)
        info.addStretch()
        for widget in (self.install_button, self.enable_button, self.open_button, self.category_button, self.lib_deps, self.uninstall_button):
            info.addWidget(widget)
        scroller = scroll_area(details)
        scroller.setMinimumWidth(214)
        scroller.setMaximumWidth(328)
        split.addWidget(scroller)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([670, 275])
        layout.addWidget(split, 1)
        return page

    def library_keys(self):
        if self.library_views.currentIndex() == 1:
            return [index.data(Qt.ItemDataRole.UserRole) for index in self.library_grid.selectedIndexes()]
        return selected(self.library_list)

    def select_grid(self, rows, keys):
        selection = self.library_grid.selectionModel()
        selection.blockSignals(True)
        try:
            if getattr(self, "grid_rows", None) != rows:
                self.grid_model.clear()
                glyph = icon("library", "#46DFAE")
                for key, cells in rows:
                    image = self.thumbnails.get(self.library_entries[key].get("item"))
                    item = QStandardItem(QIcon(image) if image else glyph, str(cells[0]))
                    item.setData(key, Qt.ItemDataRole.UserRole)
                    item.setEditable(False)
                    item.setToolTip(" · ".join(str(cell) for cell in cells))
                    self.grid_model.appendRow(item)
                self.grid_rows = rows
            selection.clearSelection()
            keys = set(keys)
            for index, (key, _) in enumerate(rows):
                if key in keys:
                    selection.select(self.grid_model.index(index, 0), selection.SelectionFlag.Select)
        finally:
            selection.blockSignals(False)

    def switch_library(self, index):
        previous = self.library_keys()
        self.library_views.setCurrentIndex(index)
        if index == 1:
            self.select_grid(self.library_model.rows, previous)
        else:
            selection = self.library_list.selectionModel()
            selection.clearSelection()
            for key in previous:
                if key in self.library_model.indices:
                    selection.select(self.library_model.index(self.library_model.indices[key], 0),
                                     selection.SelectionFlag.Select | selection.SelectionFlag.Rows)
        self.s.state["libraryView"] = self.view_switch.currentText()
        self.s.save()
        self.library_actions()

    def refresh_library(self, *_):
        if not hasattr(self, "library_model"):
            return
        keys = self.library_keys()
        records = {key: dict(item, item=key, origin="library", size=self.s.library_present.get(key, item.get("size"))) for key, item in self.s.items.items()
                   if item["status"] == "Complete" and item.get("path")
                   and (self.s.scanned_sources.get(key) != item["path"] or key in self.s.library_present)}
        managed_items = set()
        for batch_key, batch in self.s.batches.items():
            for index, file in enumerate(batch["files"]):
                location = installed_path(file)
                disk = self.s.disk.get(os.path.normcase(str(location)), {})
                if disk and disk["size"] is None:
                    continue
                managed_items.add(batch["item"])
                item = self.s.items.get(batch["item"], {})
                records[f"managed:{batch_key}:{index}"] = dict(
                    disk, name=Path(file["path"]).name, path=str(location), item=batch["item"],
                    creator=item.get("creator", ""), category=item.get("category") or disk.get("category", "Other"),
                    inferred=item.get("inferred", True), disabled=file["disabled"], origin="managed",
                    batch=batch_key, index=index, date=batch.get("date") or disk.get("date", ""))
        managed_paths = {os.path.normcase(record["path"]) for record in records.values() if record["origin"] == "managed"}
        current = self.s.state.get("categoryOverrides", {})
        for key, file in self.s.disk.items():
            if key not in managed_paths and not file["item"] and file["size"] is not None:
                category = current.get(self.category_key(file))
                records[key] = dict(file, origin="scan", category=category or file["category"], inferred=not category)
        self.library_entries = records
        query = self.search.text().strip().casefold()
        category = self.category_filter.currentText()
        categories = ["All categories", *sorted({record.get("category", "Other") for record in records.values()})]
        if [self.category_filter.itemText(i) for i in range(self.category_filter.count())] != categories:
            self.category_filter.blockSignals(True)
            self.category_filter.clear()
            self.category_filter.addItems(categories)
            self.category_filter.setCurrentText(category if category in categories else "All categories")
            self.category_filter.blockSignals(False)
            category = self.category_filter.currentText()
        result = []
        profile = self.s.profiles.get(self.profile, []) if self.profile else None
        for key, record in records.items():
            if profile is not None and (record.get("item") or key) not in profile and key not in profile:
                continue
            if category not in ("All categories", record.get("category", "Other")):
                continue
            path = Path(record["path"])
            filetype = (path.with_suffix("") if record.get("disabled") else path).suffix.lower()
            if query == ".ts4script":
                if filetype != query:
                    continue
            elif query and query not in " ".join(str(record.get(field, "")) for field in ("name", "creator", "category", "path", "url")).casefold():
                continue
            result.append((key, record, filetype.lstrip(".")))
        sort_index = self.sort_order.currentIndex()
        if sort_index == 1:
            result.sort(key=lambda pair: pair[1].get("added") or pair[1].get("date", ""), reverse=True)
        elif sort_index == 2:
            result.sort(key=lambda pair: pair[1].get("size") or 0, reverse=True)
        else:
            result.sort(key=lambda pair: pair[1]["name"].casefold())
        rows = []
        for key, record, filetype in result:
            if record["origin"] == "library":
                status = "Installed copy exists" if key in managed_items else "Downloaded"
            else:
                status = "Disabled" if record.get("disabled") else "Enabled"
            tag = record.get("category", "Other") + (" (inferred)" if record.get("inferred") else "")
            rows.append((key, (record["name"], tag, filetype or "—", size_label(record.get("size")), status)))
        update_rows(self.library_list, self.library_model, rows)
        if self.library_views.currentIndex() == 1:
            self.select_grid(rows, keys)
        scanning = "scan" in self.s.jobs
        self.library_empty.setVisible(not rows or scanning)
        self.library_empty.setText("Scanning the library…" if scanning else
                                   "No mods match the current filters." if query or self.profile or category != "All categories"
                                   else "No mods found. Add local files or scan your Mods folder.")
        self.profile_control.blockSignals(True)
        self.profile_control.clear()
        self.profile_control.addItems(["All profiles", *sorted(self.s.profiles)])
        self.profile_control.setCurrentText(self.profile or "All profiles")
        self.profile_control.blockSignals(False)
        self.library_actions()

    @staticmethod
    def category_key(record):
        path = Path(record["path"])
        return os.path.normcase(str(path.with_suffix("") if record.get("disabled") else path))

    def current_mod(self):
        keys = self.library_keys()
        return self.library_entries.get(keys[0]) if len(keys) == 1 else None

    def library_actions(self):
        if not hasattr(self, "install_button"):
            return
        record = self.current_mod()
        origin = record["origin"] if record else ""
        item = self.s.items.get(record.get("item"), {}) if record else {}
        fs_busy = self.s.mutating_files() or any(job.startswith("preview:") for job in self.s.jobs)
        self.install_button.setEnabled(origin == "library" and not fs_busy)
        is_mod = record and (Path(record["path"]).with_suffix("") if record.get("disabled") else Path(record["path"])).suffix.lower() in MOD_EXTENSIONS
        self.enable_button.setEnabled((origin == "managed" or (origin == "scan" and is_mod)) and not fs_busy)
        self.open_button.setEnabled(bool(record))
        self.category_button.setEnabled(bool(record))
        self.lib_deps.setEnabled(bool(item.get("url")) and item.get("source") != "CurseForge")
        self.uninstall_button.setEnabled(origin == "managed" and not fs_busy)
        self.detail_image.hide()
        if not record:
            self.detail_title.setText("Mod details")
            self.detail.setText("Select one mod to see its file and installation details.")
            return
        self.detail_title.setText(record["name"])
        item_key = record.get("item")
        image = self.thumbnails.get(item_key)
        if image:
            self.detail_image.setPixmap(image.scaled(208, 126, Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
            self.detail_image.show()
        elif item_key:
            self.request_thumbnail(item_key)
        self.enable_button.setText("Restore file" if record.get("disabled") else "Quarantine file")
        self.detail.setText("\n\n".join([
            f"Creator  {record.get('creator') or 'Unknown'}",
            f"Category  {record.get('category', 'Other')}" + (" (inferred)" if record.get("inferred") else ""),
            f"Type  {Path(record['path']).suffix}", f"Size  {size_label(record.get('size'))}",
            f"Date  {local_date(record.get('added') or record.get('date', ''))}",
            f"Status  {'Disabled' if record.get('disabled') else 'Enabled' if origin != 'library' else 'Download or local source'}",
            f"Path\n{record['path']}", f"Source\n{item.get('url') or 'Local file'}",
        ]))

    def add_files(self):
        try:
            self.s.install_destination()
        except ValueError as error:
            self.inform(str(error), "warning")
            self.go(len(NAV) - 1)
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Sims 4 files", self.s.settings["downloads"], LOCAL_FILES)
        if paths:
            try:
                self.s.add_local(paths, install_now=True)
                self.go(2)
            except (OSError, ValueError) as error:
                self.inform(failure_message(error), "error")

    def profile_changed(self, name):
        self.profile = None if name == "All profiles" else name
        self.refresh_library()

    def save_profile(self):
        keys = self.library_keys()
        if not keys:
            self.inform("Select mods to save as a profile.", "warning")
            return
        name, accepted = QInputDialog.getText(self, "Save library profile", "Profile name")
        name = name.strip()
        if accepted and name and name != "All profiles":
            if name in self.s.profiles and not self.confirm("Replace profile", f"Replace the saved selections in {name}?"):
                return
            self.s.profiles[name] = sorted({self.library_entries[key].get("item") or key for key in keys})
            self.s.publish()
            self.inform(f"Saved {name}.", "success")

    def export_audit(self):
        """Run a read-only Sims 4 inventory audit outside the UI thread."""
        if "creatorstudios-audit" in self.s.jobs:
            self.inform("An inventory audit is already running.", "warning")
            return
        game = self.s.game()
        if not game:
            self.inform("Choose your Sims 4 user data folder in Settings first.", "warning")
            self.go(6)
            return
        name = str(Path(self.s.settings["downloads"]) / "CreatorStudios-Mod-Audit.json")
        destination, _ = QFileDialog.getSaveFileName(
            self, "Export CreatorStudios mod audit", name,
            "JSON report (*.json);;CSV report (*.csv)")
        if destination:
            self.s.job("creatorstudios-audit", audit_to_file,
                       self.s.mods(), str(game / "Tray"), destination)
            self.inform("Scanning your library without modifying any game files.", "info")

    def profile_backups(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Profile backups")
        dialog.resize(580, 390)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Autosaved profiles", "section"))
        layout.addWidget(label("The last 10 autosaves include profiles, settings, queue, and library records. "
                               "Game files stay on disk when a snapshot is restored.", "secondary", True))
        snapshots = {path.name: path for path in self.s.backups.snapshots()}
        view, model = table(["Recovery point"], [])
        model.replace([(name, (name.removeprefix("profile-").removesuffix(".json").replace("_", " "),)) for name in snapshots])
        layout.addWidget(view, 1)
        restore = button("Restore selected", dialog.accept, True)
        restore.setEnabled(False)
        view.selectionModel().selectionChanged.connect(lambda *_: restore.setEnabled(len(selected(view)) == 1))
        layout.addLayout(row(button("Open backup folder", lambda: open_path(self.s.backups.directory), glyph="folder"),
                             None, button("Close", dialog.reject), restore))
        if dialog.exec() == QDialog.DialogCode.Accepted and self.confirm(
            "Restore profile backup", "Restore the selected library records and settings? A snapshot of your current state is kept."
        ):
            try:
                self.s.restore_backup(snapshots[selected(view)[0]])
                self.profile = None
                self.view_switch.setCurrentText(self.s.state.get("libraryView", "List"))
                self.refresh_library()
                self.sync_settings()
                self.inform("Restored the profile backup.", "success")
            except (OSError, ValueError) as error:
                self.inform(failure_message(error), "error")

    def export_links(self):
        items = (self.s.items.get(self.library_entries[key].get("item"), {}) for key in self.library_keys())
        links = list(dict.fromkeys(item["url"] for item in items if item.get("url") and item.get("source") != "CurseForge"))
        if not links:
            self.inform("Select downloaded TSR items to export their links.", "warning")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export TSR links", "TSR links.txt", "Text files (*.txt)")
        if path:
            try:
                Path(path).write_text("\n".join(links) + "\n", encoding="utf-8")
                self.inform("Exported selected TSR links.", "success")
            except OSError as error:
                self.inform(failure_message(error), "error")

    def edit_category(self):
        record = self.current_mod()
        if not record:
            return
        value, accepted = QInputDialog.getItem(self, "Mod category", "Choose or enter a category",
                                               ["Gameplay", "Create-a-Sim", "Clothing", "Hair", "Furniture", "Build & Buy",
                                                "Utilities", "Script Mods", "Other"], 8, True)
        if accepted and value.strip():
            if record.get("item") in self.s.items:
                self.s.items[record["item"]].update(category=value.strip(), inferred=False)
            else:
                self.s.state.setdefault("categoryOverrides", {})[self.category_key(record)] = value.strip()
            self.s.publish()

    def library_dependencies(self):
        record = self.current_mod()
        if record and record.get("item") in self.s.items:
            self.dependencies([record["item"]])

    def open_library(self):
        record = self.current_mod()
        if record:
            path = Path(record["path"])
            if not open_path(path.parent):
                self.inform("This file's folder could not be opened.", "warning")

    def preview_install(self):
        record = self.current_mod()
        if record and record["origin"] == "library":
            key = record["item"]
            self.s.job("preview:" + key, self.s.install_preview, key)
            self.inform("Preparing installation preview…")

    def show_preview(self, key, plan):
        dialog = QDialog(self)
        dialog.setWindowTitle("Install preview")
        dialog.resize(680, 410)
        layout = QVBoxLayout(dialog)
        title = label(self.s.items[key]["name"], "section", True)
        title.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(title)
        layout.addWidget(label("Existing filenames will be skipped. Close The Sims 4 before installing.", "secondary", True))
        preview, model = table(["File", "Destination", "Action"], [190, 245])
        model.replace([(str(i), (target.name, str(target.parent), "Skip · conflict" if conflict else "Copy"))
                       for i, (_, target, _, conflict) in enumerate(plan)])
        layout.addWidget(preview)
        count = sum(not entry[3] for entry in plan)
        confirm = button(f"Install {count} file(s)", dialog.accept, True)
        confirm.setEnabled(bool(count))
        layout.addLayout(row(None, button("Close", dialog.reject), confirm))
        if dialog.exec() == QDialog.DialogCode.Accepted and not self.closing and not self.s.mutating_files():
            self.s.install_selected(key, plan)

    def toggle_library(self):
        record = self.current_mod()
        if not record:
            return
        verb = "Restore" if record.get("disabled") else "Quarantine"
        if not self.confirm(f"{verb} mod", f"{verb} {Path(record['path']).name}? Close the game before changing its files."):
            return
        try:
            if record["origin"] == "managed":
                self.s.toggle_managed(record["batch"], record["index"])
                return
            elif record["origin"] == "scan":
                self.s.toggle_scanned(self.library_keys()[0])
            self.inform(f"{verb} completed.", "success")
        except (OSError, ValueError) as error:
            self.inform(failure_message(error), "error")

    def uninstall_library(self):
        record = self.current_mod()
        if record and record.get("batch"):
            self.uninstall(record["batch"])

    def uninstall(self, batch_key):
        batch = self.s.batches.get(batch_key)
        if not batch or self.s.mutating_files():
            return
        paths = [record["path"] for record in batch["files"]]
        if not self.confirm("Uninstall managed files", f"Remove {len(paths)} file(s) from this install batch?",
                            "\n".join(paths)):
            return
        self.s.undo(batch_key)
        self.inform("Verifying and uninstalling managed files…")

    def history_page(self):
        page, layout = page_layout()
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Search mod, creator, path, or error")
        self.history_search.setAccessibleName("Search install history")
        self.history_search.textChanged.connect(self.refresh_history)
        self.history_date = QComboBox()
        self.history_date.addItems(["Any date", "Last 7 days", "Last 30 days", "Unknown date"])
        self.history_date.setAccessibleName("Filter history by date")
        self.history_date.currentTextChanged.connect(self.refresh_history)
        self.history_result = QComboBox()
        self.history_result.addItems(["All results", "Completed", "Failed", "Partial", "Skipped"])
        self.history_result.setAccessibleName("Filter history by result")
        self.history_result.currentTextChanged.connect(self.refresh_history)
        filters = row(self.history_date, self.history_result, button("Export CSV", self.export_history))
        filters.insertWidget(0, self.history_search, 1)
        layout.addLayout(filters)
        self.history_empty = label("No installation activity has been recorded yet.", "secondary", True)
        layout.addWidget(self.history_empty)
        self.history_view, self.history_model = table(
            ["Date and time", "Mod", "Creator", "Action", "Result", "Path", "Error"], [125, 152, 105, 92, 88, 187])
        self.history_view.setAccessibleName("Install history")
        self.history_view.selectionModel().selectionChanged.connect(self.history_actions)
        self.history_view.doubleClicked.connect(lambda _: self.inspect_history())
        layout.addWidget(self.history_view, 1)
        self.history_detail_button = button("View details", self.inspect_history)
        self.history_open = button("Open location", self.history_folder, glyph="folder")
        self.history_undo = button("Uninstall batch", self.history_uninstall)
        layout.addLayout(row(self.history_detail_button, self.history_open, self.history_undo, None))
        return page

    def refresh_history(self, *_):
        if not hasattr(self, "history_model"):
            return
        search = self.history_search.text().strip().casefold()
        date_filter = self.history_date.currentIndex()
        status_filter = self.history_result.currentText()
        self.filtered_history = {}
        for index, record in enumerate(self.s.history_rows()):
            if status_filter != "All results" and record["result"] != status_filter:
                continue
            date = record.get("date", "")
            if date_filter in (1, 2):
                cutoff = (datetime.now() - timedelta(days=7 if date_filter == 1 else 30)).date().isoformat()
                if date[:10] < cutoff:
                    continue
            elif date_filter == 3 and date:
                continue
            if search and search not in " ".join([record["name"], record["creator"], record["action"],
                                                    record.get("error", ""), *record["paths"]]).casefold():
                continue
            self.filtered_history[str(index)] = record
        rows = [(key, (local_date(record["date"]), record["name"], record["creator"] or "—", record["action"],
                       record["result"], record["paths"][0] if record["paths"] else "—", record.get("error", "")))
                for key, record in self.filtered_history.items()]
        update_rows(self.history_view, self.history_model, rows)
        self.history_empty.setVisible(not rows)
        self.history_empty.setText("No activity matches these filters." if self.s.history_rows()
                                   else "No installation activity has been recorded yet.")
        self.history_actions()

    def current_history(self):
        keys = selected(self.history_view)
        return self.filtered_history.get(keys[0]) if len(keys) == 1 else None

    def history_actions(self):
        if not hasattr(self, "history_open"):
            return
        record = self.current_history()
        self.history_detail_button.setEnabled(bool(record))
        self.history_open.setEnabled(bool(record and record["paths"]))
        self.history_undo.setEnabled(bool(record and record.get("batch") in self.s.batches and not self.s.mutating_files()))

    def inspect_history(self):
        record = self.current_history()
        if not record:
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Installation details")
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.setText(record["name"])
        dialog.setInformativeText(f"{record['action']} · {record['result']}\n{local_date(record['date'])}")
        dialog.setDetailedText("\n".join([*record["paths"], record.get("error", "")]).strip())
        dialog.exec()

    def history_folder(self):
        record = self.current_history()
        if record and record["paths"] and not open_path(Path(record["paths"][0]).parent):
            self.inform("The recorded folder is unavailable.", "warning")

    def history_uninstall(self):
        record = self.current_history()
        if record and record.get("batch"):
            self.uninstall(record["batch"])

    def export_history(self):
        if not self.filtered_history:
            self.inform("There are no install records to export.", "warning")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export install history", "Install history.csv", "CSV files (*.csv)")
        if not path:
            return
        def csv_cell(value):
            return "'" + value if value[:1] in {"=", "+", "-", "@", "\t", "\r"} else value
        try:
            with Path(path).open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output)
                writer.writerow(["Date", "Mod", "Creator", "Action", "Result", "Paths", "Error"])
                for record in self.filtered_history.values():
                    writer.writerow([csv_cell(value) for value in (record["date"], record["name"], record["creator"],
                                     record["action"], record["result"], "\n".join(record["paths"]), record.get("error", ""))])
            self.inform("Install history exported.", "success")
        except OSError as error:
            self.inform(failure_message(error), "error")

    def settings_page(self):
        page, layout = page_layout()
        self.setting_controls = {}
        folders, form = surface()
        form.addWidget(label("Game directories", "section"))
        for key, name in (("game", "Sims 4 user data"), ("install_location", "Game installation"),
                          ("mods", "Mods folder override"), ("downloads", "Download folder"), ("backup", "Backup folder")):
            field = QLineEdit(self.s.state.get("game", "") if key == "game" else self.s.settings[key])
            field.setAccessibleName(name)
            if key == "mods":
                field.setPlaceholderText("Use the Mods folder under Sims 4 user data")
            self.setting_controls[key] = field
            name_label = label(name)
            name_label.setFixedWidth(152)
            entry = row(name_label, button("Browse", lambda checked=False, item=key: self.browse_setting(item)))
            entry.insertWidget(1, field, 1)
            form.addLayout(entry)
        self.game_path_hint = label("", "secondary", True)
        form.addWidget(self.game_path_hint)
        for key in ("game", "mods"):
            self.setting_controls[key].textChanged.connect(self.show_paths)
        form.addLayout(row(button("Detect folders", lambda: self.s.job("detect", detect_game), glyph="refresh"),
                           button("Open Mods", lambda: self.open_setting_folder("Mods")),
                           button("Open Tray", lambda: self.open_setting_folder("Tray")),
                           button("Open Saves", lambda: self.open_setting_folder("saves")), None))
        layout.addWidget(folders)
        self.show_paths()

        preferences, controls = surface()
        controls.addWidget(label("Download preferences", "section"))
        for key, title, low, high in (("workers", "Concurrent downloads", 1, 10), ("attempts", "Attempts per download", 1, 5)):
            picker = QSpinBox()
            picker.setRange(low, high)
            picker.setValue(self.s.settings[key])
            picker.setAccessibleName(title)
            self.setting_controls[key] = picker
            controls.addLayout(row(label(title), picker, None))
        for key, name in (("watch", "Watch clipboard for TSR links"), ("dependencies", "Check dependencies during link review"),
                          ("organize", "Sort new downloads into category folders"), ("notifications", "Show background notifications")):
            controls.addWidget(self.setting_toggle(key, name))
        layout.addWidget(preferences)

        browser, controls = surface()
        controls.addWidget(label("Browser integration", "section"))
        controls.addWidget(label("Allow the Sims 4 Mod Library website to open an install review in this app.", "secondary", True))
        self.website_link_button = button("", self.toggle_website_links, glyph="link")
        self.update_website_link_button()
        controls.addLayout(row(self.website_link_button, None))
        layout.addWidget(browser)

        library, controls = surface()
        controls.addWidget(label("Library management", "section"))
        for key, name in (("auto_scan", "Scan on startup and after changes"), ("duplicates", "Find byte-identical copies during scans"),
                          ("backup_enabled", "Back up managed files before uninstalling")):
            controls.addWidget(self.setting_toggle(key, name))
        controls.addLayout(row(button("Refresh library", self.s.scan, glyph="refresh"),
                               button("Export audit report", self.export_audit),
                               button("Clean partial downloads", self.clean_cache), None))
        layout.addWidget(library)

        appearance, controls = surface()
        controls.addWidget(label("Appearance", "section"))
        density = QComboBox()
        density.addItems(["Comfortable", "Compact"])
        density.setCurrentText(self.s.settings["density"])
        density.setAccessibleName("Layout density")
        self.setting_controls["density"] = density
        self.accent = self.s.settings["accent"]
        self.accent_button = button("Accent " + self.accent.upper(), self.pick_accent)
        controls.addLayout(row(label("Dark theme"), density, self.accent_button, None))
        controls.addWidget(self.setting_toggle("animations", "Animate switches and notifications"))
        layout.addWidget(appearance)

        app, controls = surface()
        controls.addWidget(label(f"Application · version {VERSION}", "section"))
        controls.addLayout(row(button("Check releases", self.check_releases),
                               button("Open logs folder", self.open_logs, glyph="folder"),
                               button("About", self.about), button("Reset preferences", self.reset_settings), None))
        layout.addWidget(app)
        layout.addLayout(row(button("Save settings", self.save_settings, True, "check"), None))
        return scroll_area(page)


    def toggle_website_links(self):
        enable = not self.s.settings["website_links"]
        try:
            set_registration(enable)
            self.s.settings["website_links"] = enable
            self.s.save()
        except (OSError, ValueError) as error:
            self.inform(failure_message(error), "error")
        self.update_website_link_button()

    def update_website_link_button(self):
        enabled = self.s.settings["website_links"]
        self.website_link_button.setText("Disable website links" if enabled else "Enable website links")

    def receive_website_link(self, value):
        if self.closing:
            return
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        if not self.s.settings["website_links"]:
            self.go(len(NAV) - 1)
            self.inform("Choose Enable website links in Settings to accept links from your browser.", "warning")
            return
        try:
            project, file = parse_install_link(value)
            self.s.install_destination()
        except ValueError as error:
            self.go(len(NAV) - 1)
            self.inform(str(error), "warning")
            return
        key = self.discover.api_key.text().strip()
        self.go(4)
        if not key:
            self.inform("Enter your CurseForge API key in Discover, then open the website link again.", "warning")
            self.discover.api_key.setFocus()
            return
        if self.website_review or "website-link" in self.s.jobs:
            self.inform("Finish reviewing the current website download first.", "warning")
            return
        self.s.job("website-link", curseforge.linked_file, key, project, file)
        self.inform("Checking the linked CurseForge file…")

    def review_website_file(self, project, file):
        self.website_review = True
        try:
            if not file:
                if self.confirm("Download on CurseForge", "This file cannot be downloaded in the app. Open its CurseForge project?"):
                    self.discover.open_url(curseforge.web_url(project.get("links", {}).get("websiteUrl")))
                return
            if not self.confirm("Review website download", "Download this file for an install preview?",
                                f"{project['name']}\n{file['fileName']}\n{size_label(file.get('fileLength'))}"):
                return
            key = self.s.queue_curseforge_file(project, file)
            self.website_previews.add(key)
            self.go(1)
            if self.s.items[key]["status"] == "Complete":
                self.website_download_ready(key)
        except (OSError, ValueError) as error:
            self.inform(failure_message(error), "error")
        finally:
            self.website_review = False

    def website_download_ready(self, key):
        if key in self.website_previews and not self.closing:
            self.website_previews.remove(key)
            self.s.job("preview:" + key, self.s.install_preview, key)

    def setting_toggle(self, key, name):
        control = ToggleSwitch(name)
        control.setChecked(self.s.settings[key])
        self.setting_controls[key] = control
        return control

    def browse_setting(self, key):
        field = self.setting_controls[key]
        path = QFileDialog.getExistingDirectory(self, "Choose folder", field.text() or str(Path.home()))
        if path:
            field.setText(str(Path(path)))

    def chosen_path(self, key):
        return self.setting_controls[key].text().strip()

    def show_paths(self, *_):
        game = self.chosen_path("game")
        mods = self.chosen_path("mods") or (str(Path(game) / "Mods") if game else "")
        if game:
            self.game_path_hint.setText(f"Mods: {mods}\nTray: {Path(game) / 'Tray'}\nGame saves: {Path(game) / 'saves'}")
        else:
            self.game_path_hint.setText("Choose or detect the Sims 4 user data folder to locate Mods, Tray, and saves.")

    def open_setting_folder(self, name):
        game = self.chosen_path("game")
        path = self.chosen_path("mods") if name == "Mods" else ""
        folder = Path(path) if path else Path(game) / name if game else None
        if not folder or not open_path(folder):
            self.inform(f"The {name} folder could not be found.", "warning")

    def pick_accent(self):
        choice = QColorDialog.getColor(QColor(self.accent), self, "Choose an accent color")
        if choice.isValid():
            if choice.lightness() < 115:
                self.inform("Choose a lighter accent for readable text in the dark theme.", "warning")
                return
            self.accent = choice.name()
            self.accent_button.setText("Accent " + self.accent.upper())

    def sync_settings(self):
        for key, field in self.setting_controls.items():
            value = self.s.state.get("game", "") if key == "game" else self.s.settings[key]
            if isinstance(field, QLineEdit):
                field.setText(value)
            elif isinstance(field, QCheckBox):
                field.setChecked(value)
            elif isinstance(field, QSpinBox):
                field.setValue(value)
            else:
                field.setCurrentText(value)
        self.clipboard_toggle.blockSignals(True)
        self.clipboard_toggle.setChecked(self.s.settings["watch"])
        self.clipboard_toggle.blockSignals(False)
        self.accent = self.s.settings["accent"]
        self.accent_button.setText("Accent " + self.accent.upper())
        self.apply_theme()
        self.update_website_link_button()

    def save_settings(self):
        settings = {}
        game = ""
        try:
            for key, control in self.setting_controls.items():
                if isinstance(control, QLineEdit):
                    raw = control.text().strip()
                    path = Path(raw).expanduser() if raw else None
                    if path and not path.is_absolute():
                        raise ValueError(f"Choose a full path for {control.accessibleName()}.")
                    value = str(path.resolve()) if path else ""
                    if key == "game":
                        if path and not any((path / part).is_dir() for part in ("Mods", "Tray", "saves")):
                            raise ValueError("Choose a Sims 4 user data folder containing Mods, Tray, or saves.")
                        game = value
                        continue
                    if key in {"install_location", "mods"} and path and not path.is_dir():
                        raise ValueError(f"{control.accessibleName()} must be an existing folder.")
                    if key in {"downloads", "backup"} and not path:
                        raise ValueError(f"Choose {control.accessibleName().lower()}.")
                elif isinstance(control, QCheckBox):
                    value = control.isChecked()
                elif isinstance(control, QSpinBox):
                    value = control.value()
                else:
                    value = control.currentText()
                settings[key] = value
            old_paths = {"game": self.s.state.get("game", ""),
                         **{key: self.s.settings[key] for key in ("mods", "downloads", "backup", "install_location")}}
            changes = [f"{key}: {old or 'unset'} → {(game if key == 'game' else settings[key]) or 'unset'}"
                       for key, old in old_paths.items() if old != (game if key == "game" else settings[key])]
            if changes and not self.confirm("Change directories", "Use these new directories for future operations?", "\n".join(changes)):
                return
            Path(settings["downloads"]).mkdir(parents=True, exist_ok=True)
            if settings["backup_enabled"]:
                backup = Path(settings["backup"])
                mods = Path(settings["mods"]) if settings["mods"] else Path(game) / "Mods" if game else None
                if mods and backup.is_relative_to(mods):
                    raise ValueError("Choose a backup folder outside of the Mods folder.")
                backup.mkdir(parents=True, exist_ok=True)
            settings["accent"] = self.accent
            self.s.update_settings(game, settings)
            self.sync_settings()
            self.inform("Settings saved.", "success")
        except (OSError, ValueError) as error:
            self.inform(failure_message(error), "error")

    def reset_settings(self):
        if self.confirm("Reset preferences", "Restore download, library, and appearance defaults? Your folders and library records will be kept."):
            keep = {"downloads", "backup", "install_location", "mods", "website_links"}
            self.s.update_settings(self.s.state.get("game", ""), {key: value for key, value in settings_defaults().items() if key not in keep})
            self.sync_settings()
            self.inform("Preferences reset.", "success")

    def clean_cache(self):
        if self.s.active:
            self.inform("Finish or cancel active downloads before cleaning partial files.", "warning")
            return
        if self.confirm("Clean partial downloads", "Delete unfinished partial download files from the configured download folder?"):
            self.s.clear_partials()

    def open_logs(self):
        if not open_path(DATA_DIR):
            self.inform("The log folder could not be opened.", "warning")

    def about(self):
        QMessageBox.about(self, "About CreatorStudios Sims 4 Mod Library",
                          f"CreatorStudios Sims 4 Mod Library {VERSION}\nPySide6 desktop workspace for The Sims Resource and local Sims 4 content.\nOriginal downloader attribution is retained in NOTICE.md.")

    def check_releases(self):
        self.release_status.setText("Checking releases…")
        self.s.job("release", release_info)

    def request_thumbnail(self, key):
        url = self.s.items.get(key, {}).get("thumbnail")
        if url and key not in self.thumbnail_requested and len(self.thumbnail_requested) < 128 and not self.closing:
            self.thumbnail_requested.add(key)
            QTimer.singleShot(0, lambda: self.s.job("thumbnail:" + key, fetch_thumbnail, url))

    def thumbnail_ready(self, key, data):
        if not data:
            return
        buffer = QBuffer()
        buffer.setData(data)
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
        size = reader.size()
        if not size.isValid() or size.width() > 4096 or size.height() > 4096:
            return
        reader.setScaledSize(size.scaled(280, 168, Qt.AspectRatioMode.KeepAspectRatio))
        image = QPixmap.fromImage(reader.read())
        if image.isNull():
            return
        self.thumbnails[key] = image
        glyph = QIcon(image)
        self.queue_model.set_icon(key, glyph)
        for library_key, record in self.library_entries.items():
            if record.get("item") == key:
                self.library_model.set_icon(library_key, glyph)
        for recent_key, item_key in self.recent_items.items():
            if item_key == key:
                self.recent_model.set_icon(recent_key, glyph)
        self.grid_rows = None
        if self.library_views.currentIndex() == 1:
            self.select_grid(self.library_model.rows, self.library_keys())
        self.library_actions()

    def job_done(self, job, result):
        value, error = result
        if job.startswith("thumbnail:"):
            self.thumbnail_ready(job.split(":", 1)[1], value)
            return
        if job == "website-link" and not error and not self.closing:
            if self.s.settings["website_links"]:
                self.review_website_file(*value)
        elif job == "curseforge-search":
            self.discover.result(value, error)
        elif job.startswith("install:"):
            if not error:
                if value:
                    self.inform(f"Installed {len(value)} file(s) into Mods or Tray.", "success")
                else:
                    self.inform("Install skipped. The destination files already exist.", "warning")
        elif job.startswith("rename:") and not error:
            self.inform("File quarantine state updated.", "success")
        elif job.startswith("uninstall:") and not error:
            removed, _, errors = value
            self.inform(f"Removed {len(removed)} file(s)." + (f" {len(errors)} issue(s) recorded in history." if errors else ""),
                        "warning" if errors else "success")
        elif job.startswith("preview:") and not error and not self.closing:
            self.show_preview(job.split(":", 1)[1], value)
        elif job == "detect" and not error:
            if value:
                self.setting_controls["game"].setText(str(value))
                self.inform("Sims 4 folders detected. Save settings to use this location.", "success")
            else:
                self.inform("No Sims 4 user data folder was found in Documents or OneDrive.", "warning")
        elif job == "release":
            self.release_status.setText(f"Upstream release · {value}" if not error else "Release check unavailable")
            if not self.closing and not error:
                if self.confirm("Upstream release", f"The latest upstream release is {value}. Open the release page?"):
                    QDesktopServices.openUrl(QUrl(RELEASES))
            elif not self.closing and error:
                if self.confirm("Release check unavailable", "Open the upstream release page in your browser?"):
                    QDesktopServices.openUrl(QUrl(RELEASES))
        elif job == "creatorstudios-audit" and not error:
            report, destination = value
            self.inform("Audit exported: " + format_summary(report), "success")
            self.diagnostics.setToolTip(f"Last audit report: {destination}")
        elif job == "content-backup" and not error:
            count = value["files"]
            skipped = value["skipped"]
            extra = f" Skipped {skipped} linked or special entries." if skipped else ""
            self.inform(f"Saved a content backup with {count} files." + extra, "warning" if skipped else "success")
        elif job == "cleanup" and not error:
            self.inform(f"Removed {value} partial download file(s).", "success")
        if error and job != "release" and not self.closing:
            self.inform(error, "error")

    def refresh(self):
        self.refresh_recovery()
        hidden = set(self.s.state["queueHidden"])
        rows = [(key, self.queue_cells(key)) for key, item in self.s.items.items()
                if item.get("url") and (key not in hidden or item["status"] != "Complete")]
        update_rows(self.queue_view, self.queue_model, rows)
        self.queue_empty.setVisible(not rows)
        self.queue_actions()
        self.refresh_library()
        self.refresh_history()
        history = [record for record in self.s.history_rows() if record["action"] == "Install" and record["result"] == "Completed"]
        health = self.s.health
        queue = sum(item["status"] in {"Queued", "Downloading", "Paused"} for item in self.s.items.values())
        for control, text in zip(self.stats, [str(health["mods"]) if health else "—", str(queue), str(len(history)),
                                              size_label(health.get("storage"))]):
            control.setText(text)
        recent = []
        self.recent_items = {}
        self.recent_model.icons.clear()
        for index, record in enumerate(history[:5]):
            item_key = record["item"]
            self.recent_items[str(index)] = item_key
            if item_key in self.thumbnails:
                self.recent_model.icons[str(index)] = QIcon(self.thumbnails[item_key])
            item = self.s.items.get(record["item"], {})
            recent.append((str(index), (record["name"], record["creator"] or "—",
                                        item.get("category", "—"), record["result"], local_date(record["date"]))))
        update_rows(self.recent, self.recent_model, recent)
        self.recent_empty.setVisible(not recent)
        self.recent.setVisible(bool(recent))
        if "scan" in self.s.jobs:
            self.diagnostics.setText("Scanning folders and inspecting files…")
            self.health_label.setText("Library health · scanning")
        elif health:
            duplicates = health["duplicates"]
            self.diagnostics.setText(
                f"Missing required downloads: {health['dependencies']}  ·  Missing or unreadable files: {health['missing']}\n"
                f"Identical copies: {duplicates if duplicates is not None else 'scan disabled'}  ·  Shared filenames: {health['collisions']}"
            )
            issues = health["dependencies"] + health["missing"] + (duplicates or 0) + health["collisions"]
            self.health_label.setText(f"Library health · {issues} findings" if issues else "Library health · no scan findings")
        else:
            self.diagnostics.setText("Run a library scan to check for missing files, required downloads, and duplicate content.")
        self.releases.setEnabled("release" not in self.s.jobs)
        if self.closing and not self.s.jobs and not self.s.active and not self.s.lookups:
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event):
        busy = self.s.jobs or self.s.lookups or self.s.active
        if busy:
            event.ignore()
            if not self.closing and self.confirm(
                "Close during active work", "Cancel active transfers and close after file operations finish?"
            ):
                self.closing = True
                self.s.request_close()
                self.centralWidget().setEnabled(False)
                self.inform("Closing after background operations finish…")
            return
        self.s.state["windowGeometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.s.save()
        self.s.shutdown()
        logger.removeHandler(self.console_handler)
        event.accept()


def main():
    # Only the Windows entry point needs the native file lock; Linux CI imports
    # the UI for offscreen regression tests without the msvcrt module.
    import msvcrt
    arguments = sys.argv[1:]
    link = arguments[0] if len(arguments) == 1 else None
    app = QApplication([sys.argv[0]])
    if arguments:
        try:
            parse_install_link(link or "")
        except ValueError as error:
            QMessageBox.warning(None, "Sims 4 Mod Library", str(error))
            return 1
    app.setApplicationName("Sims 4 Mod Library")
    app.setApplicationVersion(VERSION)
    app.setStyle("Fusion")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.with_suffix(".lock").open("a+b") as lock:
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            if link and forward_link(STATE_PATH, link):
                return 0
            QMessageBox.information(None, "Sims 4 Mod Library",
                                    "The library is already open. Paste the link into the browser again after it starts.")
            return 1
        try:
            service = LibraryService()
            window = MainWindow(service)
        except (OSError, ValueError) as error:
            QMessageBox.critical(None, "Sims 4 Mod Library", failure_message(error))
            return 1
        try:
            listener = WebsiteLinkServer(STATE_PATH, window)
            listener.received.connect(window.receive_website_link)
        except OSError as error:
            window.inform(str(error), "warning")
        window.show()
        if link:
            QTimer.singleShot(0, window, lambda: window.receive_website_link(link))
        return app.exec()


if __name__ == "__main__":
    sys.exit(main())
