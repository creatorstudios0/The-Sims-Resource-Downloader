"""Visual tokens and reusable Qt widgets for the desktop workspace."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSize, QByteArray
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QStyle, QStyledItemDelegate, QStyleOptionProgressBar, QTableView, QVBoxLayout, QWidget,
)

ICONS = {
    "brand": "M12 2 20 11 12 22 4 11Z M12 2 12 22 M4 11h16",
    "home": "m3 10 9-7 9 7v10H3z M9 20v-6h6v6",
    "queue": "M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4",
    "library": "M3 4h4v16H3z M10 4h4v16h-4z M17 5l3-1 4 15-3 1z",
    "history": "M3 12a9 9 0 1 1 3 7 M3 6v6h6M12 7v5l4 2",
    "settings": "M4 6h16M4 12h16M4 18h16M8 4v4m8 2v4m-6 2v4",
    "menu": "M4 6h16M4 12h16M4 18h16",
    "link": "M10 14l4-4m-5 6-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0m0 10a4 4 0 0 0 6 0l5-5a4 4 0 0 0-6-6l-2 2",
    "folder": "M3 5h7l2 3h9v12H3z",
    "refresh": "M20 11a8 8 0 1 0-2 7m2-13v6h-6",
    "check": "m5 12 4 4L19 6",
    "plus": "M12 5v14M5 12h14",
    "search": "M15 15l5 5 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z",
    "console": "M3 5h18v14H3z M6 9l3 3-3 3 M12 15h5",
    "sparkles": "m12 2 2.3 7.7L22 12l-7.7 2.3L12 22l-2.3-7.7L2 12l7.7-2.3L12 2z",
}


def icon(name, color="#A2A8C4"):
    path = ICONS[name]
    data = QByteArray(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="{path}" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>'.encode())
    renderer = QSvgRenderer(data)
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def theme(accent, compact=False):
    density = "5px 9px" if compact else "8px 12px"
    return f"""
    * {{ font-family: 'Segoe UI'; font-size: 10pt; color: #F1F0FF; }}
    QMainWindow, QWidget#workspace, QWidget#scrollViewport {{ background: #0C0D18; }}
    QFrame#sidebar {{ background: #111322; border-right: 1px solid #253244; }}
    QFrame#surface, QFrame#stat {{ background: #191C30; border: 1px solid #30334C; border-radius: 11px; }}
    QFrame#stat {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2A2749, stop:1 #191C30); }}
    QLabel#pageTitle {{ font-size: 27pt; font-weight: 700; color: #F5F2FF; }}
    QLabel#heroTitle {{ font-size: 21pt; font-weight: 750; color: #FFFFFF; }}
    QFrame#hero {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #32244F, stop:0.55 #252547, stop:1 #1B304B); border: 1px solid #67518C; border-radius: 18px; }}
    QFrame#hero QLabel#secondary {{ color: #D3D1E8; }}
    QPushButton#brandButton {{ font-size: 11pt; font-weight: 800; letter-spacing: 1px; color: #E1D6FF; border: none; background: transparent; text-align: left; }}
    QPushButton#brandButton:hover {{ background: #292541; }}
    QLabel#section {{ font-size: 13pt; font-weight: 650; }}
    QLabel#statValue {{ font-size: 23pt; font-weight: 700; color: {accent}; }}
    QLabel#secondary {{ color: #A2A8C4; }}
    QLabel#positive {{ color: #52D6AC; }}
    QLabel#eyebrow {{ color: #A2A8C4; font-size: 8pt; font-weight: 700; }}
    QPushButton, QToolButton, QComboBox, QSpinBox, QDateEdit {{
        background: #23273C; border: 1px solid #30334C; border-radius: 8px; padding: {density};
    }}
    QPushButton:hover, QToolButton:hover {{ background: #303552; border-color: #7B6AB3; }}
    QPushButton:focus, QToolButton:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus,
    QLineEdit:focus, QPlainTextEdit:focus, QTableView:focus, QListView:focus {{ border: 1px solid {accent}; }}
    QPushButton:disabled {{ color: #65778D; background: #191C30; }}
    QPushButton[primary="true"] {{ background: {accent}; color: #0C0D18; font-weight: 700; border-color: {accent}; }}
    QPushButton[primary="true"]:hover {{ background: #CAB9FF; }}
    QPushButton[primary="true"]:disabled {{ color: #65778D; background: #191C30; border-color: #30334C; }}
    QPushButton[nav="true"] {{ text-align: left; background: transparent; border: 1px solid transparent; padding: 10px 12px; }}
    QPushButton[nav="true"]:hover {{ background: #23273C; }}
    QPushButton[nav="true"]:checked {{ background: #292541; color: {accent}; border-color: #30334C; }}
    QPushButton[nav="true"]:focus {{ border-color: {accent}; }}
    QLineEdit, QPlainTextEdit, QTableView, QListView {{
        background: #121526; border: 1px solid #30334C; border-radius: 8px;
        selection-background-color: #514A83; selection-color: #F1F0FF;
    }}
    QLineEdit, QPlainTextEdit {{ padding: {density}; }}
    QPlainTextEdit#activityConsole {{ background: #0A1019; color: #C8D6E5; font-family: 'Cascadia Mono', 'Consolas'; padding: 12px; }}
    QHeaderView::section {{ background: #23273C; color: #C1C2DD; border: none; padding: 8px 6px; font-weight: 600; }}
    QTableView {{ alternate-background-color: #191C30; gridline-color: #30334C; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: #121526; width: 12px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #505576; min-height: 24px; border-radius: 5px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: #121526; height: 12px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: #505576; min-width: 24px; border-radius: 5px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QSplitter::handle {{ background: #30334C; width: 3px; }}
    QProgressBar {{ border: 1px solid #30334C; border-radius: 5px; background: #23273C; text-align: center; }}
    QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
    QToolTip {{ background: #23273C; color: #F1F0FF; border: 1px solid #30334C; padding: 4px; }}
    QMessageBox, QDialog, QMenu, QComboBox QAbstractItemView {{ background: #191C30; }}
    QFrame#toast {{ border-radius: 8px; border: 1px solid #30334C; background: #191C30; }}
    QFrame#toast[level="success"] {{ border-color: #52D6AC; }}
    QFrame#toast[level="warning"] {{ border-color: #F5BC68; }}
    QFrame#toast[level="error"] {{ border-color: #F17878; }}
    """


def label(text, role=None, wrap=False):
    widget = QLabel(text)
    if role:
        widget.setObjectName(role)
    widget.setWordWrap(wrap)
    return widget


def button(text, action, primary=False, glyph=None):
    control = QPushButton(text)
    control.setProperty("primary", primary)
    if glyph:
        control.setIcon(icon(glyph, "#0C0D18" if primary else "#A2A8C4"))
    control.clicked.connect(action)
    return control


def surface(role="surface"):
    frame = QFrame()
    frame.setObjectName(role)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(11)
    return frame, layout


def row(*widgets):
    layout = QHBoxLayout()
    layout.setSpacing(8)
    for widget in widgets:
        if widget is None:
            layout.addStretch(1)
        else:
            layout.addWidget(widget)
    return layout


def scroll_area(widget):
    view = QScrollArea()
    view.setWidgetResizable(True)
    view.viewport().setObjectName("scrollViewport")
    view.setWidget(widget)
    return view


class Rows(QAbstractTableModel):
    """A flat projection of stable IDs and display cells."""
    def __init__(self, headers, parent=None):
        super().__init__(parent)
        self.headers = headers
        self.rows = []
        self.indices = {}
        self.icons = {}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        key, columns = self.rows[index.row()]
        value = columns[index.column()]
        if role == Qt.ItemDataRole.UserRole:
            return key
        if role == Qt.ItemDataRole.DecorationRole and index.column() == 0:
            return self.icons.get(key)
        if role == Qt.ItemDataRole.DisplayRole:
            return value[0] if isinstance(value, tuple) else value
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(value[0] if isinstance(value, tuple) else value)
        if role == Qt.ItemDataRole.ForegroundRole:
            if value in ("Completed", "Enabled", "Downloaded"):
                return QColor("#52D6AC")
            if value in ("Failed", "Missing"):
                return QColor("#F17878")
            if value in ("Requires attention", "Paused", "Disabled", "Partial"):
                return QColor("#F5BC68")

    def replace(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.indices = {key: i for i, (key, _) in enumerate(rows)}
        self.endResetModel()

    def set_icon(self, key, glyph):
        self.icons[key] = glyph
        if key in self.indices:
            index = self.index(self.indices[key], 0)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])

    def patch(self, key, values):
        if key not in self.indices:
            return
        index = self.indices[key]
        self.rows[index] = (key, values)
        self.dataChanged.emit(self.index(index, 0), self.index(index, len(self.headers) - 1))


class ProgressPainter(QStyledItemDelegate):
    def paint(self, painter, option, index):
        entry = index.model().rows[index.row()][1][index.column()]
        if not isinstance(entry, tuple):
            super().paint(painter, option, index)
            return
        title, percentage = entry
        bar = QStyleOptionProgressBar()
        bar.rect = option.rect.adjusted(5, 6, -5, -6)
        bar.minimum = 0
        bar.maximum = 100 if percentage is not None else 0
        bar.progress = percentage if percentage is not None else 0
        bar.text = title
        bar.textVisible = percentage is not None
        option.widget.style().drawControl(QStyle.ControlElement.CE_ProgressBar, bar, painter, option.widget)


def table(headers, widths=None):
    view = QTableView()
    model = Rows(headers, view)
    view.setModel(model)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    view.setAlternatingRowColors(True)
    view.setShowGrid(False)
    view.verticalHeader().hide()
    view.verticalHeader().setDefaultSectionSize(35)
    view.horizontalHeader().setStretchLastSection(True)
    for index, width in enumerate(widths or []):
        view.setColumnWidth(index, width)
    return view, model


def selected(view):
    return [index.data(Qt.ItemDataRole.UserRole) for index in view.selectionModel().selectedRows()]


def update_rows(view, model, rows):
    keys = selected(view)
    if model.rows == rows:
        return
    view.blockSignals(True)
    selection = view.selectionModel()
    selection.blockSignals(True)
    try:
        model.replace(rows)
        flags = selection.SelectionFlag.Select | selection.SelectionFlag.Rows
        for key in keys:
            if key in model.indices:
                selection.select(model.index(model.indices[key], 0), flags)
    finally:
        selection.blockSignals(False)
        view.blockSignals(False)
