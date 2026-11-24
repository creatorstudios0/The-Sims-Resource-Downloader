"""The library overview, backed by the same scan, transfer, and history records as the workspace."""
from PySide6.QtCore import QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QBoxLayout, QComboBox, QFrame, QGridLayout, QListWidget, QListWidgetItem, QProgressBar, QScrollArea, QVBoxLayout, QWidget

from qt_services import size_label
from qt_theme import button, icon, label, row, surface
from qt_tokens import ACCENT, ASSETS, ERROR, SUCCESS, WARNING

STORAGE_TYPES = ("Package mods", "Script mods", "Tray files")
PATCH_GUIDE = "https://help.ea.com/en/articles/the-sims/the-sims-4/mods-and-the-sims-4-game-updates/"


class GameBanner(QFrame):
    def __init__(self, window):
        super().__init__()
        self.artwork = QPixmap(str(ASSETS / "sims-home.png"))
        self.setMinimumHeight(182)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(3)
        layout.addStretch()
        layout.addWidget(label("The Sims 4", "gameTitle"))
        self.status = label("", "heroCopy", True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        layout.addSpacing(10)
        layout.addLayout(row(button("Open library", lambda: window.go(2), True, "library"),
                             button("Import files", window.add_files, glyph="plus"),
                             button("Discover", lambda: window.go(4), glyph="sparkles"), None))
        layout.addStretch()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor("#191822"))
        if not self.artwork.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            art_rect = rect.adjusted(rect.width() // 3, 0, 0, 0)
            aspect = art_rect.width() / max(1, art_rect.height())
            source_height = min(self.artwork.height(), self.artwork.width() / aspect)
            source_width = min(self.artwork.width(), source_height * aspect)
            source = QRectF(self.artwork.width() - source_width,
                            (self.artwork.height() - source_height) * 0.48, source_width, source_height)
            painter.drawPixmap(QRectF(art_rect), self.artwork, source)
        wash = QLinearGradient(0, 0, max(1, rect.width()), 0)
        wash.setColorAt(0, QColor("#191822"))
        wash.setColorAt(0.36, QColor("#191822"))
        wash.setColorAt(0.68, QColor(25, 24, 34, 105))
        wash.setColorAt(1, QColor(25, 24, 34, 0))
        painter.fillRect(rect, wash)


class Dashboard(QScrollArea):
    def __init__(self, window):
        super().__init__()
        self.service = window.s
        self.setWidgetResizable(True)
        self.viewport().setObjectName("scrollViewport")
        page = QWidget()
        page.setObjectName("workspace")
        self.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 3, 3)
        layout.setSpacing(12)
        self.banner = GameBanner(window)
        layout.addWidget(self.banner)

        strip = QFrame()
        strip.setObjectName("metricStrip")
        strip_layout = QGridLayout(strip)
        strip_layout.setContentsMargins(14, 8, 14, 10)
        strip_layout.setHorizontalSpacing(14)
        self.stats = []
        for index, name in enumerate(("Installed mods", "Download queue", "Completed installs", "Installed storage")):
            strip_layout.addWidget(label(name, "secondary", True), 0, index)
            value = label("—", "statValue")
            value.setAccessibleName(name)
            strip_layout.addWidget(value, 1, index)
            strip_layout.setColumnStretch(index, 1)
            self.stats.append(value)
        layout.addWidget(strip)

        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(12)
        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(12)
        self.columns.addWidget(main, 5)
        self.columns.addWidget(side, 4)
        layout.addLayout(self.columns)

        health, controls = surface("dashboardPanel")
        controls.addLayout(row(label("Library health", "section"), None,
                               button("Scan", self.service.scan, glyph="refresh")))
        self.diagnostics = label("", "secondary", True)
        controls.addWidget(self.diagnostics)
        controls.addWidget(button("Export mod audit", window.export_audit, glyph="folder"),
                           alignment=Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(health)

        monitor, controls = surface("dashboardPanel")
        controls.addLayout(row(label("Transfers", "section"), None,
                               button("Open queue", lambda: window.go(1), glyph="queue")))
        self.transfer_status = label("", "secondary", True)
        self.transfer_status.setTextFormat(Qt.TextFormat.PlainText)
        self.download_bar = QProgressBar()
        self.download_bar.setAccessibleName("Current download progress")
        self.install_bar = QProgressBar()
        self.install_bar.setRange(0, 0)
        self.install_bar.setAccessibleName("Installation in progress")
        controls.addWidget(self.transfer_status)
        controls.addWidget(self.download_bar)
        controls.addWidget(self.install_bar)
        main_layout.addWidget(monitor)

        activity, controls = surface("dashboardPanel")
        controls.addLayout(row(label("Recent activity", "section"), None,
                               button("History", lambda: window.go(3), glyph="history")))
        self.timeline = QListWidget()
        self.timeline.setAccessibleName("Recent installation and library actions")
        self.timeline.setWordWrap(True)
        self.timeline.setMaximumHeight(204)
        self.timeline.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.timeline_empty = label("Installs, removals, and file changes will appear here.", "secondary", True)
        self.timeline_entries = None
        controls.addWidget(self.timeline)
        controls.addWidget(self.timeline_empty)
        main_layout.addWidget(activity)
        main_layout.addStretch()

        storage, controls = surface("dashboardPanel")
        controls.addWidget(label("Storage breakdown", "section"))
        self.disk = None
        self.storage_totals = {}
        self.storage_type = QComboBox()
        self.storage_type.setAccessibleName("Storage file type")
        self.storage_type.addItems(STORAGE_TYPES)
        self.storage_type.currentTextChanged.connect(self.refresh_storage)
        self.storage_status = label("", "secondary", True)
        self.storage_bar = QProgressBar()
        self.storage_bar.setAccessibleName("Share of installed storage")
        controls.addWidget(self.storage_type)
        controls.addWidget(self.storage_status)
        controls.addWidget(self.storage_bar)
        self.storage_open = button("Show files", lambda: window.show_storage_files(self.storage_type.currentIndex()),
                                   glyph="drive")
        controls.addWidget(self.storage_open, alignment=Qt.AlignmentFlag.AlignLeft)
        side_layout.addWidget(storage)

        patch, controls = surface("dashboardPanel")
        controls.addWidget(label("Patch readiness", "section"))
        self.patch_summary = label("", "secondary", True)
        controls.addWidget(self.patch_summary)
        self.patch_check = button("Check version", self.service.check_patch, glyph="refresh")
        self.patch_reviewed = button("Mark reviewed", self.service.mark_patch_reviewed, glyph="check")
        actions = QGridLayout()
        actions.addWidget(self.patch_check, 0, 0)
        actions.addWidget(button("Review scripts", window.review_script_mods), 0, 1)
        actions.addWidget(self.patch_reviewed, 1, 0)
        actions.addWidget(button("EA patch guide", lambda: QDesktopServices.openUrl(QUrl(PATCH_GUIDE))), 1, 1)
        controls.addLayout(actions)
        side_layout.addWidget(patch)

        backup, controls = surface("dashboardPanel")
        controls.addWidget(label("Mods and Tray backups", "section"))
        self.backup_summary = label("", "secondary", True)
        self.backup_summary.setTextFormat(Qt.TextFormat.PlainText)
        controls.addWidget(self.backup_summary)
        self.backup_create = button("Create backup ZIP", window.create_content_backup, glyph="archive")
        self.backup_open = button("Open last backup", window.open_content_backup, glyph="folder")
        controls.addLayout(row(self.backup_create, self.backup_open, None))
        controls.addWidget(button("Profile backups", window.profile_backups), alignment=Qt.AlignmentFlag.AlignLeft)
        side_layout.addWidget(backup)
        side_layout.addStretch()
        layout.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "columns"):
            self.columns.setDirection(QBoxLayout.Direction.LeftToRight if self.viewport().width() >= 780
                                      else QBoxLayout.Direction.TopToBottom)

    def refresh(self, history):
        service = self.service
        health = service.health
        queue = sum(item["status"] in {"Queued", "Downloading", "Paused"} for item in service.items.values())
        completed = sum(record["action"] == "Install" and record["result"] == "Completed" for record in history)
        values = (str(health["mods"]) if health else "—", str(queue), str(completed), size_label(health.get("storage")))
        for control, value in zip(self.stats, values):
            control.setText(value)
        current, _ = service.patch_versions()
        self.banner.status.setText(f"Game version {current}" if current else
                                   "Game folder connected" if service.game() else "Set your game folder in Settings")
        if "scan" in service.jobs:
            self.diagnostics.setText("Scanning installed files and required downloads…")
        elif health:
            duplicates = health["duplicates"] if health["duplicates"] is not None else "scan disabled"
            self.diagnostics.setText(f"Missing dependencies   {health['dependencies']}\n"
                                     f"Missing or unreadable files   {health['missing']}\n"
                                     f"Identical copies   {duplicates}\nShared filenames   {health['collisions']}")
        else:
            self.diagnostics.setText("Scan your library to look for missing files, dependencies, and duplicates.")
        if service.disk is not self.disk:
            self.disk = service.disk
            self.storage_totals = dict.fromkeys(STORAGE_TYPES, 0)
            for record in self.disk.values():
                kind = record["category"]
                category = "Script mods" if kind == "Script Mods" else "Package mods" if kind == "Package Mods" else "Tray files"
                self.storage_totals[category] += record.get("size") or 0
        self.refresh_storage()
        self.refresh_transfers()
        self.refresh_timeline(history)

    def refresh_storage(self, *_):
        scanned = bool(self.service.health)
        capacity = sum(self.storage_totals.values())
        used = self.storage_totals.get(self.storage_type.currentText(), 0)
        self.storage_type.setEnabled(scanned)
        self.storage_open.setEnabled(scanned)
        self.storage_open.setToolTip("Filter the library to this installed file type" if scanned else
                                     "Run a library scan before opening the storage breakdown")
        self.storage_bar.setVisible(scanned)
        self.storage_bar.setValue(round(used / capacity * 100) if capacity else 0)
        self.storage_status.setText(f"{size_label(used)} of {size_label(capacity)} installed" if scanned
                                    else "Run a library scan to measure installed space.")

    def refresh_transfers(self):
        service = self.service
        downloads = sorted(service.active)
        installs = sorted(job[8:] for job in service.jobs if job.startswith("install:"))
        lines = []
        if downloads:
            key = downloads[0]
            name = service.items.get(key, {}).get("name", key)
            progress = service.progress_data.get(key, {})
            total = progress.get("total")
            self.download_bar.setRange(0, 100 if total else 0)
            if total:
                self.download_bar.setValue(min(100, int(progress.get("received", 0) / total * 100)))
            extra = f" and {len(downloads) - 1} more" if len(downloads) > 1 else ""
            lines.append(f"Downloading {name}{extra}")
        if installs:
            name = service.items.get(installs[0], {}).get("name", installs[0])
            lines.append(f"Installing {name}")
        if not lines:
            waiting = sum(item["status"] in {"Queued", "Paused"} for item in service.items.values())
            lines.append(f"{waiting} waiting in the download queue" if waiting else "No active transfers or installs.")
        self.transfer_status.setText("\n".join(lines))
        self.download_bar.setVisible(bool(downloads))
        self.install_bar.setVisible(bool(installs))

    def refresh_timeline(self, history):
        events = history[:6]
        if events == self.timeline_entries:
            return
        self.timeline_entries = events
        self.timeline.clear()
        for event in events:
            stamp = event["date"][:16].replace("T", " ") or "Unknown date"
            result = event["result"]
            color = SUCCESS if result == "Completed" else ERROR if result == "Failed" else WARNING
            item = QListWidgetItem(icon("check" if result == "Completed" else "activity", color),
                                   f"{event['action']} · {event['name']}\n{stamp}  ·  {result}")
            item.setToolTip(event.get("error") or event["name"])
            self.timeline.addItem(item)
        self.timeline.setVisible(bool(events))
        self.timeline_empty.setVisible(not events)
