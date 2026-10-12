"""Auditoria: log imutável de operações."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from app.ui.widgets import Card, SearchField, make_label, page_header
from app.domain.models import format_pt_datetime
from app.ui.table_layout import ColumnLayout


class AuditScreen(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Auditoria",
                                  "Trilha imutável de todas as operações"))

        top = QHBoxLayout()
        self.box = SearchField("Filtrar por usuário ou ação...")
        self.box.textChanged.connect(self._refresh)
        top.addWidget(self.box, 1)
        lay.addLayout(top)

        self.card = Card("Registros")
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Data", "Usuário", "Ação", "Entidade",
                                              "Registro", "Detalhe"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.card.body.addWidget(self.table)
        lay.addWidget(self.card, 1)
        self._layout = ColumnLayout(ctx, self.table, "auditoria")

    def on_show(self):
        self._refresh()

    def _refresh(self):
        term = self.box.text().strip()
        rows = self.ctx.audit.list(limit=1000, user=term)
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            detail = r.get("reason") or ""
            if r.get("old_value") or r.get("new_value"):
                detail = f"{r.get('old_value') or ''} → {r.get('new_value') or ''}"
            for c, val in enumerate([format_pt_datetime(r["created_at"]),
                                     r.get("username") or "-", r["action"],
                                     r.get("entity") or "-", r.get("entity_id") or "-",
                                     detail]):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, c, item)
        self._layout.resize_event()