"""Componentes reutilizáveis do Design System."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget, QLayout)

from app.ui import theme
from app.ui.table_layout import ColumnLayout


def make_label(text: str, obj: str = "", size: int = 0, bold: bool = False) -> QLabel:
    label = QLabel(text)
    if obj:
        label.setObjectName(obj)
    if size:
        label.setStyleSheet(f"font-size:{size}px;")
    if bold:
        label.setStyleSheet("font-weight:700;" + (label.styleSheet() or ""))
    return label


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class Card(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumWidth(200)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)
        head = None
        if title:
            head = make_label(title, "cardTitle")
            lay.addWidget(head)
        self.body = lay
        self._title = head

    def add_row(self, row: QWidget | QLayout):
        if isinstance(row, QLayout):
            self.body.addLayout(row)
        else:
            self.body.addWidget(row)


# cores semânticas -> "tone" (o tema define a cor certa para claro/escuro)
_TONES = {theme.SUCCESS: "success", theme.DANGER: "danger", theme.WARNING: "warning",
          theme.INFO: "info", theme.PRIMARY: "primary"}
_TONE_NAMES = {"neutral", "primary", "success", "warning", "danger", "info"}


class StatCard(QFrame):
    """Indicador: rótulo no topo, valor grande e subtítulo opcional."""

    def __init__(self, label: str, value: str = "-", accent: str | None = theme.PRIMARY,
                 sub: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setMinimumHeight(96)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(2)
        lay.addWidget(make_label(label, "statLabel"))
        self.value_label = make_label(value, "statValue")
        lay.addWidget(self.value_label)
        if sub:
            lay.addWidget(make_label(sub, "subtitle"))
        lay.addStretch(1)
        self.set_tone(accent)

    def set_tone(self, tone: str | None) -> None:
        """tone: neutral | primary | success | warning | danger | info, ou uma cor #RRGGBB."""
        tone = "neutral" if tone is None else _TONES.get(tone, tone)
        if tone in _TONE_NAMES:
            self.value_label.setStyleSheet("")
            self.value_label.setProperty("tone", tone)
        else:  # cor customizada
            self.value_label.setProperty("tone", "")
            self.value_label.setStyleSheet(f"color:{tone};")
        style = self.value_label.style()
        style.unpolish(self.value_label)
        style.polish(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(str(value))


class PrimaryButton(QPushButton):
    def __init__(self, text: str = "", kind: str = "primary", parent=None,
                 shortcut: str | None = None):
        super().__init__(text, parent)
        self.setObjectName(kind)
        self.setCursor(Qt.PointingHandCursor)
        if shortcut:
            self.setShortcut(shortcut)


class GhostButton(PrimaryButton):
    def __init__(self, text: str = "", parent=None, shortcut: str | None = None):
        super().__init__(text, "ghost", parent, shortcut)


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Pesquisar...", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setMinimumWidth(220)


class DataTable(QTableWidget):
    """Tabela com cabeçalho simples, autotamanho e seleção por linha."""

    def __init__(self, columns: list[str], rows: list[list] | None = None,
                 parent=None, ctx=None, layout_key: str = ""):
        super().__init__(parent)
        self._rows = rows or []
        self._columns = columns
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(38)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setHighlightSections(False)
        self.layout = (ColumnLayout(ctx, self, layout_key)
                       if ctx is not None and layout_key else None)
        self.set_data(self._rows)

    def set_data(self, rows: list[list]):
        self.setRowCount(0)
        self._rows = rows
        for r, row in enumerate(rows):
            self.insertRow(r)
            for c, value in enumerate(row):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.setItem(r, c, item)
        if self.layout is not None:
            self.layout.resize_event()
        else:
            self.resizeColumnsToContents()
            for c in range(self.columnCount()):
                width = self.columnWidth(c)
                self.setColumnWidth(c, min(max(width, 80), 260))
            if self.columnCount():
                self.setColumnWidth(self.columnCount() - 1, max(
                    self.columnWidth(self.columnCount() - 1), 160))

    def selected_row(self, row: int) -> list:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return []

    def selected_row_data(self, id_col: int = 0) -> object:
        idx = self.currentRow()
        if idx < 0 or not self._rows:
            return None
        row = self._rows[idx]
        return row[id_col] if id_col < len(row) else None


def page_header(title: str, subtitle: str = "",
                actions: QWidget | None = None) -> QWidget:
    wrap = QWidget()
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(0, 0, 0, 8)
    texts = QVBoxLayout()
    texts.setSpacing(0)
    texts.addWidget(make_label(title, "title"))
    if subtitle:
        texts.addWidget(make_label(subtitle, "subtitle"))
    lay.addLayout(texts)
    lay.addStretch(1)
    if actions is not None:
        if isinstance(actions, QHBoxLayout):
            lay.addLayout(actions)
        else:
            lay.addWidget(actions)
    return wrap


def primary_button(text: str, kind: str = "primary", shortcut: str | None = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(kind)
    btn.setCursor(Qt.PointingHandCursor)
    if shortcut:
        btn.setShortcut(shortcut)
    return btn


def icon_button(text: str) -> QPushButton:
    return primary_button(text, "ghost")


def search_field(placeholder: str = "Pesquisar...") -> QLineEdit:
    return SearchField(placeholder)


def yes_no(title: str, message: str) -> bool:
    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox()
    box.setWindowTitle(title)
    box.setText(message)
    yes = box.addButton("Sim", QMessageBox.YesRole)
    box.addButton("Não", QMessageBox.NoRole)
    box.setIcon(QMessageBox.Warning)
    box.exec()
    return box.clickedButton() is yes


def info(parent, title: str, message: str):
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.information(parent, title, message)


def warn(parent, title: str, message: str):
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.warning(parent, title, message)


def error(parent, title: str, message: str):
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.critical(parent, title, message)