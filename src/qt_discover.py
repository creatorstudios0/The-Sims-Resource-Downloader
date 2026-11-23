"""Search CurseForge and install content from either download source."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

import curseforge
from exceptions import InvalidURL
from qt_services import failure_message
from qt_theme import button, label, row, selected, surface, table, update_rows


class DiscoverPage(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.service = window.s
        self.projects = {}
        self.index = self.total = 0
        self.query = ""
        self.setObjectName("workspace")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tsr, controls = surface()
        controls.addLayout(row(label("The Sims Resource", "section"), None,
                               button("Browse website", self.open_tsr, glyph="link")))
        self.tsr_link = QLineEdit()
        self.tsr_link.setPlaceholderText("Paste a Sims 4 item URL from The Sims Resource")
        self.tsr_link.setAccessibleName("The Sims Resource item URL")
        self.tsr_link.returnPressed.connect(self.install_tsr)
        controls.addLayout(row(self.tsr_link, button("Download and install", self.install_tsr, True, "queue")))
        layout.addWidget(tsr)

        catalog, controls = surface()
        controls.addLayout(row(label("CurseForge", "section"), None,
                               button("Browse website", lambda: self.open_url(curseforge.CATALOG), glyph="link")))
        self.api_key = QLineEdit(self.service.curseforge_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("CurseForge API key")
        self.api_key.setAccessibleName("CurseForge API key")
        self.api_key.setToolTip("Used for this session. Set CURSEFORGE_API_KEY to use it on future launches.")
        self.api_key.returnPressed.connect(self.search)
        controls.addLayout(row(self.api_key, button("Get API access", lambda: self.open_url("https://docs.curseforge.com/rest-api/"))))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search Sims 4 projects or leave blank to browse")
        self.search_box.setAccessibleName("Search CurseForge")
        self.search_box.returnPressed.connect(self.search)
        self.search_button = button("Search", self.search, True, "search")
        controls.addLayout(row(self.search_box, self.search_button))
        self.status = label("Enter an API key and search for Sims 4 resources.", "secondary", True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        controls.addWidget(self.status)
        self.results, self.model = table(["Project", "Creator", "Install source"], [250, 170])
        self.results.selectionModel().selectionChanged.connect(self.selection_changed)
        controls.addWidget(self.results, 1)
        self.summary = label("", "secondary", True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setMaximumHeight(56)
        controls.addWidget(self.summary)
        self.previous = button("Previous", lambda: self.load(self.index - curseforge.PAGE_SIZE))
        self.next = button("Next", lambda: self.load(self.index + curseforge.PAGE_SIZE))
        self.view_project = button("Open project", self.open_project, glyph="link")
        self.install_button = button("Install", self.install_curseforge, True, "queue")
        controls.addLayout(row(self.previous, self.next, None, self.view_project, self.install_button))
        layout.addWidget(catalog, 1)
        self.set_busy(False)

    @staticmethod
    def open_url(url):
        QDesktopServices.openUrl(QUrl(url))

    def open_tsr(self):
        self.open_url("https://www.thesimsresource.com/")

    def install_tsr(self):
        try:
            self.service.request_tsr_install(self.tsr_link.text().strip())
        except InvalidURL:
            self.window.inform("Paste an HTTPS item link from The Sims Resource.", "warning")
            return
        except (OSError, ValueError) as error:
            self.window.inform(failure_message(error), "error")
            return
        self.tsr_link.clear()
        self.window.go(1)

    def search(self):
        if "curseforge-search" in self.service.jobs:
            return
        self.service.curseforge_key = self.api_key.text().strip()
        if not self.service.curseforge_key:
            self.status.setText("Enter a CurseForge API key first.")
            self.api_key.setFocus()
            return
        self.query = self.search_box.text().strip()
        self.load(0)

    def load(self, index):
        self.requested_index = index
        self.status.setText("Searching CurseForge…")
        self.service.job("curseforge-search", curseforge.search, self.service.curseforge_key, self.query, index)
        self.set_busy(True)

    def result(self, value, error):
        if error:
            self.projects.clear()
            self.index = self.total = 0
            update_rows(self.results, self.model, [])
            self.status.setText(error)
        else:
            projects, self.total = value
            self.index = self.requested_index
            self.projects = {str(project["id"]): project for project in projects}
            update_rows(self.results, self.model, [
                (key, (project["name"], ", ".join(author["name"] for author in project.get("authors", [])),
                       "In-app" if curseforge.latest_file(project) else "Project website"))
                for key, project in self.projects.items()
            ])
            self.status.setText(f"{self.index + 1}–{self.index + len(projects)} of {self.total:,} projects"
                                if projects else "No matching projects found.")
        self.set_busy(False)

    def set_busy(self, busy):
        self.search_button.setEnabled(not busy)
        self.results.setEnabled(not busy)
        self.previous.setEnabled(not busy and self.index > 0)
        self.next.setEnabled(not busy and self.index + curseforge.PAGE_SIZE < self.total)
        self.selection_changed()

    def current_project(self):
        keys = selected(self.results)
        return self.projects.get(keys[0]) if self.results.isEnabled() and len(keys) == 1 else None

    def selection_changed(self, *_):
        project = self.current_project()
        self.summary.setText(project.get("summary", "") if project else "")
        self.summary.setVisible(bool(self.summary.text()))
        self.view_project.setEnabled(bool(project))
        self.install_button.setEnabled(bool(project and curseforge.latest_file(project)))

    def open_project(self):
        project = self.current_project()
        if project:
            self.open_url(curseforge.web_url(project.get("links", {}).get("websiteUrl")))

    def install_curseforge(self):
        project = self.current_project()
        if not project:
            return
        try:
            self.service.request_curseforge_install(project)
        except (OSError, ValueError) as error:
            self.window.inform(failure_message(error), "error")
        else:
            self.window.go(1)
