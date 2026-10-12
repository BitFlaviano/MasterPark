"""Tela de SAÍDA DE VEÍCULOS (busca + tarifação + pagamento)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit,
                               QScrollArea, QVBoxLayout, QWidget, QHBoxLayout)

from app.domain.models import (cents, format_money, format_minutes,
                               format_pt_datetime)
from app.services.tickets import TicketError
from app.ui.theme import PRIMARY, WARNING
from app.ui.widgets import (Card, SearchField, error, make_label, page_header,
                            primary_button, warn, yes_no)


class ExitScreen(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.current_ticket = None
        self.current_preview = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(page_header("Nova Saída",
                                  "Selecione uma entrada ativa ou busque por ticket, QR, código ou placa (F3)"))

        active_card = Card("Entradas ativas — clique para selecionar")
        active_row = QHBoxLayout()
        self.box_active = QComboBox()
        self.box_active.currentIndexChanged.connect(self._on_active_selected)
        active_row.addWidget(self.box_active, 1)
        btn_refresh = primary_button("⟳  Atualizar", "ghost")
        btn_refresh.clicked.connect(self._reload_active)
        active_row.addWidget(btn_refresh)
        active_card.body.addLayout(active_row)
        lay.addWidget(active_card)

        search_row = QHBoxLayout()
        self.box_search = SearchField(
            "Digite o número do ticket, código de barras ou placa...")
        self.box_search.returnPressed.connect(self.search)
        search_row.addWidget(self.box_search, 1)
        btn = primary_button("Buscar", "primary")
        btn.clicked.connect(self.search)
        search_row.addWidget(btn)
        lay.addLayout(search_row)

        self.result = QWidget()
        self.r_lay = QVBoxLayout(self.result)
        self.r_lay.setContentsMargins(0, 0, 0, 0)
        self.r_lay.setSpacing(12)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setWidget(self.result)
        lay.addWidget(self.scroll, 1)

        self._build_result_card()
        self.scroll.hide()

    # ------------------------------------------------------------------
    def _build_result_card(self):
        self.info = Card("Ticket encontrado")
        self.r_lay.addWidget(self.info)

        self.preview = Card("Cálculo da permanência")
        self.preview.setMinimumHeight(150)
        grid = QHBoxLayout()
        grid.setSpacing(30)
        self.lbl_time = make_label("-", "statValue")
        self.lbl_base = make_label("-", "statValue")
        self.lbl_discount = make_label("-", "statValue")
        self.lbl_final = make_label("-", "statValue", 26)
        for lbl, name, color in ((self.lbl_time, "Permanência", ""),
                                  (self.lbl_base, "Valor original", ""),
                                  (self.lbl_discount, "Desconto", WARNING),
                                  (self.lbl_final, "Valor final", PRIMARY)):
            col = QVBoxLayout()
            col.setSpacing(10)
            col.addWidget(make_label(name, "statLabel"))
            lbl.setStyleSheet(f"color:{color}; font-size:24px; font-weight:900;"
                              if color else "font-size:24px; font-weight:900;")
            col.addWidget(lbl)
            grid.addLayout(col, 1)
        grid.addStretch(2)
        self.preview.body.addLayout(grid)
        self.rule_line = make_label("", "subtitle")
        self.rule_line.setWordWrap(True)
        self.preview.body.addWidget(self.rule_line)
        self.r_lay.addWidget(self.preview)

        self.pay = Card("Pagamento")
        pay_row = QHBoxLayout()
        self.box_method = QComboBox()
        self.box_method.addItems(["DINHEIRO", "PIX", "CREDITO", "DEBITO",
                                  "TRANSFERENCIA", "CONVENIO"])
        self.box_discount = QDoubleSpinBox()
        self.box_discount.setRange(0, 100)
        self.box_discount.setSuffix(" %")
        self.box_discount.setDecimals(0)
        self.box_received = QLineEdit()
        self.box_received.setPlaceholderText("Valor recebido")
        self.box_gratis = QCheckBox("Gratuidade")
        pay_row.addWidget(make_label("Forma", "statLabel"))
        pay_row.addWidget(self.box_method, 3)
        pay_row.addWidget(make_label("Desconto", "statLabel"))
        pay_row.addWidget(self.box_discount, 2)
        pay_row.addWidget(make_label("Recebido", "statLabel"))
        pay_row.addWidget(self.box_received, 2)
        pay_row.addWidget(self.box_gratis)
        self.pay.body.addLayout(pay_row)
        self.box_received.textChanged.connect(lambda _: self._sync_received())
        self.box_method.currentTextChanged.connect(lambda _: self._sync_received())
        self.box_discount.valueChanged.connect(lambda _: self._sync_received())
        self.box_gratis.toggled.connect(lambda _: self._sync_received())
        self.r_lay.addWidget(self.pay)

        actions = QHBoxLayout()
        self.btn_confirm = primary_button("✓  Confirmar Saída e Pagamento", "success")
        self.btn_confirm.setMinimumHeight(50)
        self.btn_confirm.clicked.connect(self.confirm_exit)
        self.btn_lost = primary_button("Ticket Perdido", "ghost")
        self.btn_lost.clicked.connect(self.lost_ticket)
        self.btn_cancel = primary_button("Cancelar Ticket", "ghost")
        self.btn_cancel.clicked.connect(self.cancel_ticket)
        actions.addWidget(self.btn_confirm)
        actions.addWidget(self.btn_lost)
        actions.addWidget(self.btn_cancel)
        actions.addStretch(1)
        self.r_lay.addLayout(actions)

    # ------------------------------------------------------------------
    def on_show(self):
        self._reload_active()
        self.box_search.setFocus()

    def _reload_active(self):
        current = self.box_active.currentData()
        self.box_active.blockSignals(True)
        self.box_active.clear()
        self.box_active.addItem("— Selecione uma entrada ativa —", None)
        for t in self.ctx.tickets.list_active(limit=50):
            self.box_active.addItem(
                f"#{t['number']}   {t.get('plate') or '—'}   "
                f"desde {format_pt_datetime(t['entry_at'])[:16]}   "
                f"vaga {t.get('space_code') or 'livre'}", t["number"])
        if current is not None:
            idx = self.box_active.findData(current)
            self.box_active.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.box_active.setCurrentIndex(0)
        self.box_active.blockSignals(False)

    def _on_active_selected(self, index):
        number = self.box_active.itemData(index)
        if number:
            self.load_payload(str(number))

    def load_payload(self, ticket_id_or_number):
        self.box_search.setText(str(ticket_id_or_number))
        self.search()

    def search(self):
        term = self.box_search.text().strip()
        if not term:
            return
        try:
            ticket = self.ctx.tickets.find_single(term)
        except Exception as exc:
            error(self, "Erro", str(exc))
            return
        if not ticket:
            warn(self, "Não encontrado", "Nenhum ticket ativo para este termo.")
            return
        self.current_ticket = ticket
        self.current_preview = self.ctx.tickets.preview(ticket)
        self._render()

    def _render(self):
        t = self.current_ticket
        p = self.current_preview
        self._clear_info()
        lines = [
            f"Ticket: {t['number']}     Placa: {t.get('plate') or '—'}     "
            f"Categoria: {t.get('vehicle_category')}",
            f"Entrada: {format_pt_datetime(t['entry_at'])}     "
            f"Vaga: {t.get('space_code') or 'livre'}",
            f"Operador de entrada: {t.get('entry_user_name') or '-'}",
        ]
        for line in lines:
            self.info.body.addWidget(make_label(line, "statLabel"))

        self.lbl_time.setText(format_minutes(p["minutes"]))
        self.lbl_base.setText(format_money(p["base_value"]))
        self.lbl_discount.setText(format_money(p["discount_value"]))
        self.lbl_final.setText(format_money(p["final_value"]))
        self.rule_line.setText(f"Regra aplicada: {p.get('rule_applied') or '-'}")
        self.box_received.setText(
            f"{p['final_value'] / 100:.2f}".replace(".", ","))
        self.box_discount.setValue(0)
        self.box_gratis.setChecked(False)
        self.scroll.show()
        self.result.show()

    def _clear_info(self):
        for i in reversed(range(self.info.body.count())):
            item = self.info.body.itemAt(i)
            if item.widget() and item.widget() is not self.info._title:
                item.widget().deleteLater()

    def _sync_received(self):
        p = self.current_preview
        if not p:
            return
        method = self.box_method.currentText()
        base = p["base_value"]
        percent = self.box_discount.value()
        gratuity = self.box_gratis.isChecked()
        discount = base if gratuity else int(base * percent / 100)
        final = max(base - discount, 0)
        self.lbl_discount.setText(format_money(discount))
        if method == "CONVENIO":
            self.lbl_final.setText(format_money(base))
            return
        self.lbl_final.setText(format_money(final))
        raw = self.box_received.text().strip()
        if raw:
            received = cents(raw)
            if received and not gratuity:
                self.lbl_final.setText(format_money(max(received, 0)))

    def _received_value(self) -> int:
        p = self.current_preview
        raw = self.box_received.text().strip()
        if not raw:
            return p["final_value"] if p else 0
        return cents(raw)

    # ------------------------------------------------------------------
    def confirm_exit(self):
        if not self.current_ticket:
            return
        user = self.ctx.auth.require_permission("EXIT_CREATE")
        p = self.current_preview
        base = p["base_value"]
        percent = self.box_discount.value()
        gratuity = self.box_gratis.isChecked()
        method = self.box_method.currentText()
        discount = base if gratuity else int(base * percent / 100)
        final_value = max(base - discount, 0)
        received = self._received_value()
        if method != "CONVENIO" and received < final_value:
            warn(self, "Pagamento incompleto",
                 f"Valor final: {format_money(final_value)}. Valor recebido menor.")
            return
        if not yes_no("Confirmar saída",
                      f"Liberar o veículo {self.current_ticket.get('plate') or '-'}?\n\n"
                      f"Permanência: {format_minutes(p['minutes'])}\n"
                      f"Valor final: {format_money(final_value)}\n"
                      f"Forma: {method}"):
            return
        try:
            if discount:
                self.ctx.tickets.apply_discount(
                    ticket_id=self.current_ticket["id"],
                    percent=0.0 if gratuity else percent / 100,
                    gratuity=gratuity, user=user, reason="desconto na saída")
            result = self.ctx.tickets.register_exit(
                ticket_id=self.current_ticket["id"], payment_method=method,
                received_value=received, user=user, terminal="GUI1")
            self.ctx.printing.print_receipt(self.ctx.lot, self.ctx.company,
                                            result, result["preview"])
            self._reset()
        except (TicketError, PermissionError) as exc:
            error(self, "Erro na saída", str(exc))

    def lost_ticket(self):
        if not self.current_ticket:
            return
        user = self.ctx.auth.require_permission("TICKET_LOST")
        if not yes_no("Ticket perdido",
                      "Confirma tratar como TICKET PERDIDO? Será registrada "
                      "ocorrência e aplicada a tarifa."):
            return
        try:
            result = self.ctx.tickets.register_exit(
                ticket_id=self.current_ticket["id"], payment_method="DINHEIRO",
                user=user, terminal="GUI1", lost=True,
                incident_description="Cliente perdeu o ticket")
            self.ctx.printing.print_receipt(self.ctx.lot, self.ctx.company,
                                            result, result["preview"])
            self._reset()
        except (TicketError, PermissionError) as exc:
            error(self, "Erro", str(exc))

    def cancel_ticket(self):
        if not self.current_ticket:
            return
        user = self.ctx.auth.require_permission("TICKET_CANCEL")
        from PySide6.QtWidgets import QInputDialog
        reason, ok = QInputDialog.getText(
            self, "Cancelar ticket (exige autorização e motivo)",
            "Motivo do cancelamento:")
        if not ok or not reason.strip():
            return
        if not yes_no("Confirmar cancelamento",
                      f"Cancelar o ticket {self.current_ticket['number']}?\n"
                      f"Motivo: {reason}"):
            return
        try:
            self.ctx.tickets.cancel(ticket_id=self.current_ticket["id"],
                                    reason=reason, user=user)
            self._reset()
        except (TicketError, PermissionError) as exc:
            error(self, "Erro", str(exc))

    def _reset(self):
        self.current_ticket = None
        self.current_preview = None
        self.box_search.clear()
        self.scroll.hide()
        self.result.hide()
        self.box_received.clear()
        self.box_discount.setValue(0)
        self.box_gratis.setChecked(False)
        self._reload_active()
        self.box_search.setFocus()