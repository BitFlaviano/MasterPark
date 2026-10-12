"""Relatórios: seleção, pré-visualização e exportação CSV/Excel/PDF."""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDateEdit, QFileDialog, QHBoxLayout,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from app.ui.table_layout import ColumnLayout
from app.ui.widgets import (Card, error, info, make_label, page_header,
                            primary_button, warn)


class ReportsScreen(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Relatórios", "Gere relatórios gerenciais (F9)"))

        top = QHBoxLayout()
        self.box_report = QComboBox()
        from app.services.reports import REPORTS
        for key, meta in REPORTS.items():
            self.box_report.addItem(meta["title"], key)
        self.dt_start = QDateEdit()
        self.dt_start.setCalendarPopup(True)
        self.dt_start.setDate(self.dt_start.date().addMonths(0))
        self.dt_end = QDateEdit()
        self.dt_end.setCalendarPopup(True)
        self.dt_end.setDate(self.dt_end.date())
        self.btn_run = primary_button("Gerar", "primary")
        self.btn_run.clicked.connect(self.run)
        self.btn_csv = primary_button("Exportar CSV", "")
        self.btn_csv.clicked.connect(lambda: self.export("csv"))
        self.btn_xlsx = primary_button("Excel", "")
        self.btn_xlsx.clicked.connect(lambda: self.export("xlsx"))
        self.btn_pdf = primary_button("PDF", "")
        self.btn_pdf.clicked.connect(lambda: self.export("pdf"))
        top.addWidget(make_label("Relatório", "statLabel"))
        top.addWidget(self.box_report, 1)
        top.addWidget(make_label("De", "statLabel"))
        top.addWidget(self.dt_start)
        top.addWidget(make_label("Até", "statLabel"))
        top.addWidget(self.dt_end)
        for b in (self.btn_run, self.btn_csv, self.btn_xlsx, self.btn_pdf):
            top.addWidget(b)
        lay.addLayout(top)

        self.card = Card("Resultado")
        self.table = QTableWidget(0, 1)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.card.body.addWidget(self.table)
        lay.addWidget(self.card, 1)

        self._layout = ColumnLayout(ctx, self.table, "relatorios")

        self._title, self._cols, self._rows = "", [], []

    # ------------------------------------------------------------------
    def on_show(self):
        self.run()

    def _period(self) -> tuple[str, str]:
        start = self.dt_start.date().toPython()
        end = self.dt_end.date().toPython()
        s = datetime(start.year, start.month, start.day).strftime("%Y-%m-%dT00:00:00Z")
        e = datetime(end.year, end.month, end.day, 23, 59, 59).strftime("%Y-%m-%dT00:00:00Z")
        return s, e

    def run(self):
        report = self.box_report.currentData()
        s, e = self._period()
        try:
            self._title, self._cols, self._rows = self.ctx.reports.build(
                report, start=s, end=e)
        except Exception as exc:
            error(self, "Erro", str(exc))
            return
        self.table.setColumnCount(len(self._cols))
        self.table.setHorizontalHeaderLabels(self._cols)
        self.table.setRowCount(0)
        for i, row in enumerate(self._rows):
            self.table.insertRow(i)
            for c, val in enumerate(row):
                item = QTableWidgetItem("" if val is None else str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, c, item)
        if len(self._cols) != self._layout.table.columnCount():
            self._layout = ColumnLayout(self.ctx, self.table, "relatorios")
        self._layout.resize_event()

    def export(self, kind: str):
        self.ctx.auth.require_permission("REPORT_EXPORT")
        if not self._rows:
            self.run()
        report = self.box_report.currentData()
        s, e = self._period()
        default = os.path.join(os.path.expanduser("~"), "Desktop") if os.path.exists(
            os.path.join(os.path.expanduser("~"), "Desktop")) else os.getcwd()
        if kind == "csv":
            path, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", default, "CSV (*.csv)")
            if not path:
                return
            try:
                self.ctx.reports.save_csv(report, start=s, end=e)
                info(self, "OK", "CSV gerado na pasta 'relatorios'.")
            except Exception as exc:
                error(self, "Erro", str(exc))
            return
        if kind == "xlsx":
            path, _ = QFileDialog.getSaveFileName(self, "Salvar Excel", default, "Excel (*.xlsx)")
            if not path:
                return
            data = self.ctx.reports.to_excel(self._title, self._cols, self._rows)
            with open(path, "wb") as f:
                f.write(data)
            info(self, "OK", f"Excel salvo em {path}")
            return
        if kind == "pdf":
            path, _ = QFileDialog.getSaveFileName(self, "Salvar PDF", default, "PDF (*.pdf)")
            if not path:
                return
            data = self.ctx.reports.to_pdf(self._title, self._cols, self._rows)
            with open(path, "wb") as f:
                f.write(data)
            info(self, "OK", f"PDF salvo em {path}")