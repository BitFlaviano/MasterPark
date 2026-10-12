"""Tela de ENTRADA DE VEÍCULOS (alta velocidade operacional)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFormLayout, QFrame, QLabel,
                               QLineEdit, QVBoxLayout, QWidget, QHBoxLayout)

from app.domain.models import format_pt_datetime, validate_plate
from app.services.printing import PrintingService
from app.services.tickets import TicketError
from app.ui.print_dialog import ask_print
from app.ui.theme import SUCCESS
from app.ui.widgets import (Card, make_label, page_header, primary_button,
                            warn)
from PySide6.QtWidgets import QMessageBox


class EntryScreen(QWidget):
    def __init__(self, ctx, button_callback=None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.on_printed = button_callback
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        lay.addWidget(page_header(
            "Nova Entrada", "Registre a entrada do veículo rapidamente (F2)",
            None))

        row = QHBoxLayout()
        row.setSpacing(14)

        # --- formulário
        form = QWidget()
        form.setMaximumWidth(520)
        f_lay = QVBoxLayout(form)
        f_lay.setContentsMargins(0, 0, 0, 0)
        card = Card("Dados do veículo")
        card.add_row(make_label("Placa (Mercosul: AAA1A11)", "statLabel"))
        self.box_plate = QLineEdit()
        self.box_plate.setPlaceholderText("Ex.: ABC1D23")
        self.box_plate.setMaxLength(7)
        self.box_plate.setAlignment(Qt.AlignCenter)
        self.box_plate.setStyleSheet("font-size:26px; font-weight:900; "
                                     "text-transform:uppercase;")
        card.add_row(self.box_plate)
        self.box_plate.setFocus()

        card.add_row(make_label("Categoria do veículo", "statLabel"))
        self.box_cat = QComboBox()
        self.box_cat.addItems(["CARRO", "MOTO", "ELETRICO", "UTILITARIO", "PICKUP", "OUTRO"])
        card.add_row(self.box_cat)

        card.add_row(make_label("Vaga (deixe automática para escolher a melhor)", "statLabel"))
        self.box_space = QComboBox()
        card.add_row(self.box_space)

        form_grid = QFormLayout()
        self.box_model = QLineEdit(); self.box_model.setPlaceholderText("Modelo (opcional)")
        self.box_color = QLineEdit(); self.box_color.setPlaceholderText("Cor (opcional)")
        self.box_customer = QLineEdit(); self.box_customer.setPlaceholderText("Nome do cliente (opcional)")
        form_grid.addRow("Modelo", self.box_model)
        form_grid.addRow("Cor", self.box_color)
        form_grid.addRow("Cliente", self.box_customer)
        card.add_row(form_grid)

        f_lay.addWidget(card)
        f_lay.addStretch(1)

        # --- status / última entrada
        self.result_card = Card("Última entrada")
        self.result_card.body.setSpacing(6)
        self.result_card.hide()
        f_lay.addWidget(self.result_card)
        f_lay.addStretch(1)

        row.addWidget(form)
        row.addStretch(1)

        # --- painel direito: botões rápidos + QR
        right = QWidget()
        r_lay = QVBoxLayout(right)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(12)
        self.btn_enter = primary_button("🅿  Registrar Entrada", "success", "F2")
        self.btn_enter.setMinimumHeight(54)
        self.btn_enter.setStyleSheet("font-size:15px; font-weight:800;"
                                     f"background:{SUCCESS}; color:white; border-radius:10px;")
        self.btn_enter.clicked.connect(self.register)
        r_lay.addWidget(self.btn_enter)
        r_lay.addWidget(make_label("Dica: você pode digitar só a placa e pressionar "
                                   "Enter ou F2.", "subtitle"))
        r_lay.addWidget(make_label(
            "Se houver câmera LPR configurada (veja Hardware), a placa aparece "
            "automaticamente.", "subtitle"))

        r_lay.addStretch(1)
        qr_box = QFrame()
        qr_box.setObjectName("card")
        qr_lay = QVBoxLayout(qr_box)
        self.lbl_qr = QLabel("O QR Code e o código de barras do ticket serão "
                             "gerados na impressão.")
        self.lbl_qr.setObjectName("subtitle")
        self.lbl_qr.setWordWrap(True)
        qr_lay.addWidget(self.lbl_qr)
        r_lay.addWidget(qr_box)

        row.addWidget(right)
        lay.addLayout(row, 1)

        # atalhos
        self.box_plate.returnPressed.connect(self.register)

    def on_show(self):
        self._reload_spaces()
        self.box_plate.setFocus()

    def _reload_spaces(self):
        """Vagas livres para o operador escolher (Automática fica em primeiro)."""
        self.box_space.blockSignals(True)
        self.box_space.clear()
        self.box_space.addItem("Automática (melhor vaga livre)", None)
        spaces = self.ctx.spaces.list(self.ctx.lot["id"]) if self.ctx.lot else []
        for sp in spaces:
            if sp.get("state") != "LIVRE":
                continue
            code = sp.get("code") or f"vaga {sp.get('id')}"
            sector = sp.get("sector_name") or "Sem setor"
            self.box_space.addItem(f"{code} — {sector}", sp.get("id"))
        self.box_space.blockSignals(False)

    def _use_lpr(self):
        cam = self.ctx.devices.get("camera_entrada")
        if cam and cam.status == "CONECTADO":
            result = cam.read_plate()
            if result:
                self.box_plate.setText(result["plate"])
                return result
        return None

    def register(self):
        user = self.ctx.auth.require_permission("ENTRY_CREATE")
        plate = self.box_plate.text().strip()
        if plate and not validate_plate(plate):
            warn(self, "Placa inválida",
                 "A placa deve estar no formato AAA1A11 (Mercosul) ou AAA-1111.")
            return
        category = self.box_cat.currentText()
        space_id = self.box_space.currentData()
        try:
            ticket = self.ctx.tickets.register_entry(
                plate=plate, category=category,
                model=self.box_model.text().strip(),
                color=self.box_color.text().strip(),
                customer_name=self.box_customer.text().strip(),
                space_id=space_id,
                user=user, terminal="GUI1")
        except TicketError as exc:
            warn(self, "Não foi possível registrar", str(exc))
            self._reload_spaces()
            return

        self._from_ticket(ticket)
        self._reload_spaces()
        self._print(ticket)

    def _from_ticket(self, ticket: dict):
        for i in reversed(range(self.result_card.body.count())):
            item = self.result_card.body.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        safe = [
            f"Ticket: {ticket['number']}",
            f"Placa: {ticket['plate'] or '—'}",
            f"Entrada: {format_pt_datetime(ticket['entry_at'])}",
            f"Categoria: {ticket['vehicle_category']}",
            f"Cliente: {ticket.get('customer_name') or 'Cliente não identificado'}",
            f"Vaga: {ticket.get('space_code') or ticket['vehicle_category']} "
            f"({self._space_code(ticket)})",
        ]
        for line in safe:
            lbl = make_label(line, "statLabel")
            self.result_card.body.addWidget(lbl)
        self.result_card.show()

    def _space_code(self, ticket):
        if ticket.get("space_code"):
            return ticket["space_code"]
        sp = self.ctx.spaces.get(ticket.get("parking_space_id")) if ticket.get("parking_space_id") else None
        return sp["code"] if sp else "—"

    def _print(self, ticket):
        if not self.ctx.settings.auto_print_ticket:
            self.lbl_qr.setText(
                f"Ticket {ticket.get('number', '')} gerado. A impressão automática "
                "está desativada em Configurações — use Imprimir para emitir.")
            return
        choice = ask_print(self.ctx, self.ctx.lot, self.ctx.company, ticket, self)
        if not choice:
            self.lbl_qr.setText(
                f"Ticket {ticket.get('number', '')} gerado, mas a impressão foi "
                "cancelada. O veículo já está registrado no pátio.")
            return
        printer = PrintingService(choice["printer_name"],
                                  paper_mm=choice.get("paper_mm") or 80)
        ok = printer.print_ticket_entry(self.ctx.lot, self.ctx.company, ticket,
                                        simulated=choice["simulated"])
        if ok and choice["simulated"]:
            self.lbl_qr.setText(
                f"Ticket {ticket.get('number', '')} gerado no SIMULADOR: "
                "comprovante e QR Code gravados em arquivo.")
        elif not ok:
            self.lbl_qr.setText("Ticket gerado, mas houve falha na impressão.")

    def clear(self):
        self.box_plate.clear()
        self.box_model.clear()
        self.box_color.clear()
        self.box_customer.clear()
        self.result_card.hide()
        self.box_plate.setFocus()