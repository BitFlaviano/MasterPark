"""Busca global: placa, ticket, cliente, CPF/CNPJ, telefone, mensalista."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QLabel, QLineEdit, QVBoxLayout,
                               QTableWidget, QTableWidgetItem)

from app.domain.models import format_pt_datetime
from app.ui.table_layout import ColumnLayout


class GlobalSearchDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.result_data = None
        self.setWindowTitle("Busca Global (Ctrl+K)")
        self.resize(720, 480)
        lay = QVBoxLayout(self)
        self.box = QLineEdit()
        self.box.setPlaceholderText("Placa, ticket, cliente, CPF/CNPJ, telefone...")
        self.box.textChanged.connect(self.do_search)
        lay.addWidget(self.box)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Tipo", "Resultado", "Detalhe"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.pick)
        lay.addWidget(self.table)
        self._layout = ColumnLayout(ctx, self.table, "busca_global")
        self.box.setFocus()

    def do_search(self, text: str):
        term = text.strip()
        self.table.setRowCount(0)
        if len(term) < 2:
            return
        rows = []
        db = self.ctx.db
        like = f"%{term.upper()}%"
        # tickets ativos
        for t in db.query(
                "SELECT number, plate, entry_at, status FROM tickets"
                " WHERE (number LIKE ? OR plate LIKE ?) ORDER BY id DESC LIMIT 8",
                (like, like)):
            rows.append(("Ticket", f"{t['number']} • {t['plate']}",
                         f"{t['status']} {format_pt_datetime(t['entry_at'])}",
                         ("exit", t["id"])))
        # clientes
        for c in db.query(
                "SELECT id, name, cpf, cnpj, phone FROM customers"
                " WHERE name LIKE ? OR cpf LIKE ? OR cnpj LIKE ? OR phone LIKE ? LIMIT 8",
                (like, like, like, like)):
            doc = c["cpf"] or c["cnpj"] or ""
            rows.append(("Cliente", c["name"], f"{doc} • {c['phone'] or ''}",
                         ("customers", c["id"])))
        for r, (typ, title, detail, payload) in enumerate(rows):
            self.table.insertRow(r)
            for c, value in enumerate((typ, title, detail)):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, item)
        self._layout.resize_event()
        self._rows = rows

    def pick(self, index):
        if hasattr(self, "_rows") and 0 <= index.row() < len(self._rows):
            _, _, payload = self._rows[index.row()]
            self.result_data = payload
            self.accept()