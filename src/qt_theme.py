"""Visual tokens and reusable Qt widgets for the desktop workspace."""
from PySide6.QtCore import (
    QByteArray, QAbstractAnimation, QAbstractTableModel, QEasingCurve, QModelIndex, QRect, QRectF,
    QSize, Qt, QVariantAnimation,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QStyle, QStyledItemDelegate, QStyleOptionProgressBar, QTableView, QVBoxLayout, QWidget,
)

from functools import lru_cache
import json

from qt_tokens import ACCENT, ASSETS, DENSITIES, ERROR, INK, SUCCESS, WARNING, load_typeface, palette

BRAND = '<path d="M19 5H8l-5 7 5 7h11M9 12h7l3 4M19 8l-3 4"/>'
ICONS = json.loads((ASSETS / "lucide.json").read_text(encoding="utf-8"))
ICONS["brand"] = BRAND


@lru_cache(maxsize=128)
def icon(name, color="#A8A5B2"):
    drawing = ICONS[name]
    data = QByteArray((
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
        f'{drawing}</g></svg>'
    ).encode())
    renderer = QSvgRenderer(data)
    result = QIcon()
    for scale in (1, 2, 3):
        pixmap = QPixmap(24 * scale, 24 * scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        result.addPixmap(pixmap)
    return result


def theme(accent=ACCENT, compact=False, name="Midnight"):
    p = palette(name)
    density = DENSITIES["Compact" if compact else "Comfortable"][1]
    family = load_typeface()
    return f"""
    * {{ font-family: '{family}'; font-size: 10pt; color: {p.text}; }}
    QMainWindow, QWidget#workspace, QWidget#scrollViewport {{ background: {p.background}; }}
    QFrame#sidebar {{ background: {p.sidebar}; border-right: 1px solid {p.border}; }}
    QFrame#surface {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 8px; }}
    QFrame#dashboardPanel {{ background: {p.surface}; border-top: 1px solid {p.border}; }}
    QFrame#metricStrip {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 7px; }}
    QLabel#pageTitle {{ font-size: 23pt; font-weight: 700; }}
    QLabel#gameTitle {{ font-size: 32pt; font-weight: 750; color: #F7F4FF; }}
    QLabel#heroCopy {{ color: #D4D0DE; }}
    QLabel#section {{ font-size: 12pt; font-weight: 650; }}
    QLabel#statValue {{ font-size: 19pt; font-weight: 700; }}
    QLabel#secondary {{ color: {p.muted}; }}
    QLabel#positive {{ color: {SUCCESS}; }}
    QLabel#eyebrow {{ color: {p.muted}; font-size: 8pt; font-weight: 650; }}
    QPushButton#brandButton {{ font-size: 10pt; font-weight: 750; color: {p.text}; border: 1px solid transparent; background: transparent; text-align: left; }}
    QPushButton#brandButton:hover {{ background: {p.hover}; }}
    QPushButton, QToolButton, QComboBox, QSpinBox, QDateEdit {{
        background: {p.control}; border: 1px solid {p.border}; border-radius: 6px; padding: {density};
    }}
    QPushButton:hover, QToolButton:hover, QComboBox:hover {{ background: {p.hover}; }}
    QPushButton:focus, QToolButton:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus,
    QLineEdit:focus, QPlainTextEdit:focus, QTableView:focus, QListView:focus {{ border: 1px solid {accent}; }}
    QPushButton:disabled {{ color: {p.subdued}; background: {p.surface}; }}
    QPushButton[primary="true"] {{ background: {accent}; color: {INK}; font-weight: 650; border-color: {accent}; }}
    QPushButton[primary="true"]:hover {{ background: #D1C5FC; }}
    QPushButton[primary="true"]:disabled {{ color: {p.subdued}; background: {p.surface}; border-color: {p.border}; }}
    QPushButton[nav="true"] {{ text-align: left; background: transparent; border: 1px solid transparent; padding: 8px 9px; }}
    QPushButton[nav="true"]:hover {{ background: {p.control}; }}
    QPushButton[nav="true"]:checked {{ background: {p.selection}; color: {accent}; border-color: {p.border}; }}
    QPushButton[nav="true"]:focus {{ border-color: {accent}; }}
    QLineEdit, QPlainTextEdit, QTableView, QListView {{
        background: {p.input}; border: 1px solid {p.border}; border-radius: 6px;
        selection-background-color: {p.selection}; selection-color: {p.text};
    }}
    QLineEdit, QPlainTextEdit {{ padding: {density}; }}
    QListWidget::item {{ padding: 7px; }}
    QListView::item:selected, QTableView::item:selected {{ background: {p.selection}; color: {p.text}; }}
    QPlainTextEdit#activityConsole {{ background: {p.input}; color: {p.text}; font-family: 'Cascadia Mono', 'Consolas'; padding: 12px; }}
    QHeaderView::section {{ background: {p.control}; color: {p.muted}; border: none; padding: 7px 6px; font-weight: 650; }}
    QTableView {{ alternate-background-color: {p.surface}; gridline-color: {p.border}; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: {p.input}; width: 11px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {p.subdued}; min-height: 24px; border-radius: 5px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: {p.input}; height: 11px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: {p.subdued}; min-width: 24px; border-radius: 5px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QSplitter::handle {{ background: {p.border}; width: 3px; }}
    QProgressBar {{ border: 1px solid {p.border}; border-radius: 4px; background: {p.control}; text-align: center; }}
    QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
    QToolTip {{ background: {p.control}; color: {p.text}; border: 1px solid {p.border}; padding: 4px; }}
    QMessageBox, QDialog, QMenu, QComboBox QAbstractItemView {{ background: {p.surface}; }}
    QMenu::item {{ padding: 6px 20px; }}
    QMenu::item:selected {{ background: {p.selection}; }}
    QMenu::item:disabled {{ color: {p.subdued}; }}
    QFrame#toast {{ border-radius: 6px; border: 1px solid {p.border}; background: {p.surface}; }}
    QFrame#toast[level="success"] {{ border-color: {SUCCESS}; }}
    QFrame#toast[level="warning"] {{ border-color: {WARNING}; }}
    QFrame#toast[level="error"] {{ border-color: {ERROR}; }}
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
        control.setIcon(icon(glyph, INK if primary else "#A8A5B2"))
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


class ToggleSwitch(QCheckBox):
    """A binary checkbox with a sliding thumb and native checkable behavior."""

    track_width = 38
    track_height = 22
    label_gap = 10
    margin = 3

    def __init__(self, text):
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.accent = QColor(ACCENT)
        self.colors = palette("Midnight")
        self.animate_changes = True
        self.slide = QVariantAnimation(self)
        self.slide.setDuration(150)
        self.slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.slide.valueChanged.connect(self.update)
        self.clicked.connect(self.animate_toggle)

    def set_appearance(self, accent, animate, colors):
        self.accent = QColor(accent)
        self.colors = colors
        self.animate_changes = animate
        if not animate:
            self.slide.stop()
        self.update()

    def animate_toggle(self, checked):
        if not self.animate_changes:
            return
        start = float(not checked)
        if self.slide.state() == QAbstractAnimation.State.Running:
            start = self.slide.currentValue()
        self.slide.stop()
        self.slide.setStartValue(start)
        self.slide.setEndValue(float(checked))
        self.slide.start()

    def sizeHint(self):
        font = self.fontMetrics()
        return QSize(self.track_width + self.label_gap + font.horizontalAdvance(self.text()) + 2 * self.margin,
                     max(self.track_height, font.height()) + 2 * self.margin)

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, position):
        bounds = QRect(0, 0, min(self.width(), self.sizeHint().width()), self.height())
        return QStyle.visualRect(self.layoutDirection(), self.rect(), bounds).contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left_to_right = self.layoutDirection() == Qt.LayoutDirection.LeftToRight
        track = QRect(self.margin, (self.height() - self.track_height) // 2, self.track_width, self.track_height)
        track = QRectF(QStyle.visualRect(self.layoutDirection(), self.rect(), track))
        checked = self.isChecked()
        position = float(checked)
        if self.slide.state() == QAbstractAnimation.State.Running and self.slide.endValue() == position:
            position = self.slide.currentValue()
        if not left_to_right:
            position = 1.0 - position

        track_color = self.accent if checked else QColor(self.colors.hover)
        outline = self.accent if checked or self.underMouse() else QColor(self.colors.subdued)
        thumb = QColor(INK if checked else self.colors.text)
        if not self.isEnabled():
            track_color = QColor(self.colors.control)
            outline = QColor(self.colors.border)
            thumb = QColor(self.colors.subdued)

        if self.hasFocus():
            painter.setPen(QPen(self.accent, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(track.adjusted(-2, -2, 2, 2), 13, 13)
        painter.setPen(QPen(outline, 1))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 11, 11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(thumb)
        painter.drawEllipse(QRectF(track.x() + 4 + 16 * position, track.y() + 4, 14, 14))

        label_offset = self.margin + self.track_width + self.label_gap
        text_bounds = QRect(label_offset, 0, max(0, self.width() - label_offset), self.height())
        text_bounds = QStyle.visualRect(self.layoutDirection(), self.rect(), text_bounds)
        alignment = Qt.AlignmentFlag.AlignLeft if left_to_right else Qt.AlignmentFlag.AlignRight
        painter.setPen(QColor(self.colors.text if self.isEnabled() else self.colors.subdued))
        painter.drawText(text_bounds, alignment | Qt.AlignmentFlag.AlignVCenter, self.text())


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
                return QColor(SUCCESS)
            if value in ("Failed", "Missing"):
                return QColor(ERROR)
            if value in ("Requires attention", "Paused", "Disabled", "Partial"):
                return QColor(WARNING)

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
