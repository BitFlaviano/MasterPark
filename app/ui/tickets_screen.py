"""Consulta de tickets: ativos e histórico."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QScrollArea,
                               QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)
from PySide6.QtGui import QPixmap

from PySide6.QtGui import QImage

from app.domain.models import format_minutes, format_money, format_pt_datetime
from app.services.printing import PrintingService
from app.ui.print_dialog import ask_print
from app.ui.table_layout import ColumnLayout
from app.ui.widgets import (Card, SearchField, error, info, make_label,
                            page_header, primary_button, warn)


class _TicketTable(Card):
    def __init__(self, columns):
        super().__init__("")
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.body.addWidget(self.table)


def _image_from_bytes(data: bytes) -> QImage:
    """Converte PNG/bytes de QR ou código de barras num QImage."""
    img = QImage.fromData(data)
    if img.isNull():
        raise ValueError("Não foi possível decodificar a imagem gerada.")
    return img


class TicketsScreen(QWidget):
    def __init__(self, ctx, on_navigate, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.on_navigate = on_navigate
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        actions = QHBoxLayout()
        self.btn_view = primary_button("🎫  Ver ticket", "ghost")
        self.btn_view.clicked.connect(self.view_selected)
        actions.addWidget(self.btn_view)
        self.btn_reprint = primary_button("⟳  Reimprimir ticket", "ghost")
        self.btn_reprint.clicked.connect(self.reprint_selected)
        actions.addWidget(self.btn_reprint)
        actions.addStretch(1)
        lay.addWidget(page_header("Tickets", "Presentes e histórico (F4)", actions))

        top = QHBoxLayout()
        self.box = SearchField("Filtrar por placa, ticket ou status...")
        self.box.textChanged.connect(self._refresh)
        top.addWidget(self.box, 1)
        lay.addLayout(top)

        self.tabs = QTabWidget()
        self.tab_ativos = _TicketTable(["Ticket", "Placa", "Cliente", "Entrada", "Vaga", "Tempo"])
        self.tab_hist = _TicketTable(["Ticket", "Placa", "Cliente", "Entrada", "Saída", "Valor", "Status"])
        self.tabs.addTab(self.tab_ativos, "Presentes")
        self.tabs.addTab(self.tab_hist, "Histórico")

        lay.addWidget(self.tabs, 1)

        self.tab_ativos.table.doubleClicked.connect(self._open_active)

        self._l1 = ColumnLayout(ctx, self.tab_ativos.table, "tickets_ativos")
        self._l2 = ColumnLayout(ctx, self.tab_hist.table, "tickets_historico")

    def on_show(self):
        self._refresh()

    def reprint_selected(self):
        tab = self.tabs.currentWidget()
        table = tab.table
        row = table.currentRow()
        if row < 0:
            warn(self, "Reimprimir", "Selecione um ticket na lista.")
            return
        ticket_number = table.item(row, 0).text()
        active = tab is self.tab_ativos
        try:
            ticket = (self.ctx.tickets.find_single(ticket_number)
                      if active else self.ctx.tickets.history_one(ticket_number))
            if not ticket:
                warn(self, "Reimprimir", "Ticket não encontrado.")
                return
            choice = ask_print(self.ctx, self.ctx.lot, self.ctx.company, ticket, self)
            if not choice:
                return
            printer = PrintingService(choice["printer_name"],
                                      paper_mm=choice.get("paper_mm") or 80)
            sim = choice["simulated"]
            if active:
                ok = printer.print_ticket_entry(self.ctx.lot, self.ctx.company,
                                                ticket, simulated=sim)
            else:
                exit_at = None
                if ticket.get("exit_at"):
                    from datetime import datetime as _dt
                    exit_at = _dt.fromisoformat(ticket["exit_at"].replace("Z", "+00:00"))
                prev = self.ctx.tickets.preview(ticket, exit_at=exit_at)
                ok = printer.print_receipt(self.ctx.lot, self.ctx.company, ticket, prev,
                                           simulated=sim)
            if ok:
                info(self, "Reimprimir", f"Ticket {ticket_number} enviado para impressão.")
            else:
                error(self, "Reimprimir", "Falha ao enviar para a impressora.")
        except Exception as exc:
            error(self, "Reimprimir", str(exc))

    def view_selected(self):
        """Mostra o comprovante do ticket com QR (sem o código de barras, que
        fica apenas na impressão)."""
        tab = self.tabs.currentWidget()
        table = tab.table
        row = table.currentRow()
        if row < 0:
            warn(self, "Ver ticket", "Selecione um ticket na lista.")
            return
        number = table.item(row, 0).text()
        active = tab is self.tab_ativos
        try:
            ticket = (self.ctx.tickets.find_single(number) if active
                      else self.ctx.tickets.history_one(number))
            if not ticket:
                warn(self, "Ver ticket", "Ticket não encontrado.")
                return
            if active:
                receipt = self.ctx.printing.render_ticket_entry(
                    self.ctx.lot, self.ctx.company, ticket)
                qr_data = ticket.get("qr_data") or ""
            else:
                from datetime import datetime
                exit_at = None
                if ticket.get("exit_at"):
                    exit_at = datetime.fromisoformat(
                        ticket["exit_at"].replace("Z", "+00:00"))
                preview = self.ctx.tickets.preview(ticket, exit_at=exit_at)
                receipt = self.ctx.printing.render_receipt(
                    self.ctx.lot, self.ctx.company, ticket, preview)
                qr_data = ticket.get("qr_data") or ""
            # visualização: remove o Code 39 em ASCII (fica só na impressão)
            from app.services.printing import extract_ascii_barcode
            receipt = extract_ascii_barcode(receipt)[0]
            self._show_ticket_dialog(number, receipt, qr_data)
        except Exception as exc:
            error(self, "Ver ticket", str(exc))

    def _show_ticket_dialog(self, number: str, receipt: str, qr_data: str):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Ticket {number}")
        dlg.resize(460, 660)
        outer = QVBoxLayout(dlg)
        area = QScrollArea()
        area.setWidgetResizable(True)
        sheet = QWidget()
        sheet.setStyleSheet("background:#FFFFFF; color:#111827;")
        body = QVBoxLayout(sheet)
        text = QLabel(receipt)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text.setAlignment(Qt.AlignHCenter)
        text.setStyleSheet("font-family:Consolas, monospace; color:#111827;")
        body.addWidget(text)
        body.addSpacing(8)

        try:
            from app.services.printing import generate_qr_png
            if qr_data:
                qr = QLabel()
                qr.setAlignment(Qt.AlignCenter)
                qr.setPixmap(QPixmap.fromImage(_image_from_bytes(generate_qr_png(qr_data))))
                body.addWidget(qr)
            caption = QLabel(number)
            caption.setAlignment(Qt.AlignCenter)
            caption.setStyleSheet("font-family:Consolas, monospace; letter-spacing:2px;")
            body.addWidget(caption)
            if qr_data:
                payload = QLabel(f"QR: {qr_data}")
                payload.setWordWrap(True)
                payload.setAlignment(Qt.AlignCenter)
                body.addWidget(payload)
        except Exception as exc:
            warn(self, "Códigos do ticket", str(exc))
        area.setWidget(sheet)
        outer.addWidget(area, 1)
        close = primary_button("Fechar", "ghost")
        close.clicked.connect(dlg.accept)
        outer.addWidget(close)
        dlg.exec()


    def _refresh(self):
        term = self.box.text().strip()
        t1 = self.tab_ativos.table
        t1.setRowCount(0)
        rows = self.ctx.tickets.find(term)
        for r in rows:
            i = t1.rowCount()
            t1.insertRow(i)
            h, m = divmod(int(r.get("elapsed_minutes") or 0), 60)
            for c, val in enumerate([r["number"], r["plate"] or "-",
                                     r.get("customer_name") or "Cliente não identificado",
                                     format_pt_datetime(r["entry_at"]),
                                     r.get("space_code") or "-",
                                     f"{h}h{m:02d}min" if h or m else "-"]):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                t1.setItem(i, c, item)
        self._l1.resize_event()

        t2 = self.tab_hist.table
        t2.setRowCount(0)
        hrows = self.ctx.db.query(
            "SELECT t.number, t.plate, t.entry_at, t.exit_at, t.final_value, t.status,"
            " c.name customer_name"
            " FROM tickets t LEFT JOIN customers c ON c.id=t.customer_id"
            " WHERE t.status IN ('FINALIZADO','PERDIDO','CANCELADO')"
            " AND (t.plate LIKE ? OR t.number LIKE ?) ORDER BY t.id DESC LIMIT 200",
            (f"%{term.upper()}%", f"%{term.upper()}%"))
        for r in hrows:
            i = t2.rowCount()
            t2.insertRow(i)
            for c, val in enumerate([r["number"], r["plate"] or "-",
                                     r["customer_name"] or "Cliente não identificado",
                                     format_pt_datetime(r["entry_at"]),
                                     format_pt_datetime(r["exit_at"]),
                                     format_money(r["final_value"] or 0), r["status"]]):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                t2.setItem(i, c, item)
        self._l2.resize_event()

    def _open_active(self, _idx):
        table = self.tab_ativos.table
        row = table.currentRow()
        if row < 0:
            return
        ticket_number = table.item(row, 0).text()
        self.on_navigate("exit", ticket_number)
