"""Tela do caixa: abertura, fechamento, sangria, suprimento, movimentos."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout,
                               QWidget)

from app.domain.models import cents, format_money, format_pt_datetime
from app.services.cash import CashError
from app.ui.theme import DANGER, PRIMARY, SUCCESS, WARNING
from app.ui.widgets import (Card, StatCard, error, info, make_label,
                            page_header, primary_button, warn, yes_no)


class CashScreen(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Caixa", "Abertura, fechamento e movimentações (F5)"))

        self.cards = [
            StatCard("Estado", "-", PRIMARY),
            StatCard("Caixa nº", "-", PRIMARY),
            StatCard("Saldo atual", "-", SUCCESS),
            StatCard("Abertura", "-", WARNING),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, c in enumerate(self.cards):
            grid.addWidget(c, 0, i)
        lay.addLayout(grid)

        # ações
        action_row = QHBoxLayout()
        self.btn_open = primary_button("Abrir Caixa", "success")
        self.btn_open.clicked.connect(self.ask_open)
        self.btn_close = primary_button("Fechar Caixa", "danger")
        self.btn_close.clicked.connect(self.ask_close)
        self.btn_sangria = primary_button("Sangria", "")
        self.btn_sangria.clicked.connect(lambda: self.ask_move("sangria"))
        self.btn_sup = primary_button("Suprimento", "")
        self.btn_sup.clicked.connect(lambda: self.ask_move("suprimento"))
        self.btn_manual = primary_button("Lançamento manual", "")
        self.btn_manual.clicked.connect(self.ask_manual)
        for b in (self.btn_open, self.btn_close, self.btn_sangria, self.btn_sup,
                  self.btn_manual):
            action_row.addWidget(b)
        action_row.addStretch(1)
        lay.addLayout(action_row)

        self.mov = Card("Movimentações")
        self.mov_list = QVBoxLayout()
        self.mov.body.addLayout(self.mov_list)
        lay.addWidget(self.mov, 1)

    # ------------------------------------------------------------------
    def on_show(self):
        self._refresh()

    def _refresh(self):
        try:
            user = self.ctx.auth.current()
            status = self.ctx.cash.status(user)
        except Exception:
            status = {"open": False}
        opened = status.get("open", False)
        if opened:
            self.cards[0].set_value("● Aberto")
            self.cards[0].set_tone(SUCCESS)
        else:
            self.cards[0].set_value("● Fechado")
            self.cards[0].set_tone("#94A3B8")
        self.cards[1].set_value(str(status.get("register_id", "-")))
        self.cards[2].set_value(format_money(status.get("balance", 0)))
        self.cards[3].set_value(format_pt_datetime(status.get("opened_at", "-")))
        self.btn_open.setEnabled(not opened)
        for b in (self.btn_close, self.btn_sangria, self.btn_sup, self.btn_manual):
            b.setEnabled(opened)
        self._fill_movements(status.get("movements") or [])

    def _fill_movements(self, rows):
        # remove itens antigos do layout (layouts e widgets) para não repetir
        while self.mov_list.count():
            item = self.mov_list.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        if not rows:
            self.mov_list.addWidget(make_label(
                "Nenhuma movimentação neste turno de caixa.", "subtitle"))
            return
        for m in rows:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.addWidget(make_label(format_pt_datetime(m["created_at"]), "statLabel"))
            rl.addWidget(make_label(self._kind_pt(m["kind"]), "statLabel"))
            rl.addWidget(make_label(m["description"] or "", "subtitle"), 1)
            val = m["value"]
            color = SUCCESS if val >= 0 else DANGER
            lbl = make_label(format_money(val), "statValue", 13)
            lbl.setStyleSheet(f"color:{color}; font-weight:800;")
            rl.addWidget(lbl)
            self.mov_list.addWidget(row)

    @staticmethod
    def _kind_pt(kind):
        return {"ABERTURA": "Abertura", "FECHAMENTO": "Fechamento",
                "SANGRIA": "Sangria", "SUPRIMENTO": "Suprimento",
                "PAGAMENTO": "Pagamento", "ENTRADA_MANUAL": "Entrada manual",
                "SAIDA_MANUAL": "Saída manual"}.get(kind, kind)

    # ------------------------------------------------------------------
    def ask_open(self):
        user = self.ctx.auth.require_permission("CASH_OPEN")
        from PySide6.QtWidgets import QInputDialog
        value, ok = QInputDialog.getDouble(
            self, "Abrir caixa", "Valor inicial (R$):", 0.0, 0.0, 100000.0, 2)
        if not ok:
            return
        try:
            self.ctx.cash.open(user=user, opening_value=cents(str(value).replace(".", ",")))
            info(self, "Caixa aberto", "Caixa aberto com sucesso.")
            self._refresh()
        except CashError as exc:
            warn(self, "Atenção", str(exc))

    def ask_close(self):
        user = self.ctx.auth.require_permission("CASH_CLOSE")
        status = self.ctx.cash.status(user)
        expected = status.get("balance", 0)
        from PySide6.QtWidgets import QInputDialog
        value, ok = QInputDialog.getDouble(
            self, "Fechar caixa",
            f"Valor conferido (saldo esperado: {format_money(expected)}):",
            expected / 100, 0.0, 10**12, 2)
        if not ok:
            return
        informed = cents(str(value).replace(".", ","))
        justification = ""
        if informed != expected:
            justification, okj = QInputDialog.getText(
                self, "Diferença", "Justificativa da diferença de caixa:")
            if not okj or not justification.strip():
                warn(self, "Atenção", "A diferença de caixa exige justificativa.")
                return
        if not yes_no("Confirmar fechamento",
                      f"Saldo esperado: {format_money(expected)}\n"
                      f"Conferido: {format_money(informed)}\n"
                      f"Diferença: {format_money(expected - informed)}"):
            return
        try:
            result = self.ctx.cash.close(user=user, informed=informed,
                                         justification=justification)
            msg = (f"Caixa fechado.\nEsperado: {format_money(result['expected'])}\n"
                   f"Conferido: {format_money(result['informed'])}\n"
                   f"Diferença: {format_money(result['difference'])}")
            (info if result["difference"] == 0 else warn)(self, "Caixa fechado", msg)
            self._refresh()
        except CashError as exc:
            warn(self, "Atenção", str(exc))

    def ask_move(self, kind: str):
        user = self.ctx.auth.require_permission("CASH_SANGRIA")
        from PySide6.QtWidgets import QInputDialog
        value, ok = QInputDialog.getDouble(self, "Sangria" if kind == "sangria"
                                           else "Suprimento",
                                           "Valor (R$):", 0.0, 0.01, 10**10, 2)
        if not ok:
            return
        reason, okr = QInputDialog.getText(self, "Motivo", "Motivo:")
        if not okr or not reason.strip():
            warn(self, "Atenção", "Informe o motivo.")
            return
        value_c = cents(str(value).replace(".", ","))
        if value_c <= 0:
            warn(self, "Atenção", "Valor inválido.")
            return
        try:
            if kind == "sangria":
                self.ctx.cash.sangria(user=user, value=value_c, reason=reason)
            else:
                self.ctx.cash.suprimento(user=user, value=value_c, reason=reason)
            info(self, "OK", "Lançamento realizado.")
            self._refresh()
        except CashError as exc:
            warn(self, "Atenção", str(exc))

    def ask_manual(self):
        user = self.ctx.auth.require_permission("CASH_MANUAL")
        from PySide6.QtWidgets import QInputDialog
        value, ok = QInputDialog.getDouble(self, "Lançamento manual",
                                           "Valor positivo (+) ou negativo (-) em R$:", 0.0)
        if not ok:
            return
        desc, okd = QInputDialog.getText(self, "Descrição", "Descrição do lançamento:")
        if not okd or not desc.strip():
            warn(self, "Atenção", "Informe a descrição.")
            return
        value_c = cents(str(value).replace(".", ","))
        try:
            if value_c >= 0:
                self.ctx.cash.manual_entry(user=user, value=value_c, description=desc)
            else:
                self.ctx.cash.manual_exit(user=user, value=-value_c, description=desc)
            info(self, "OK", "Lançamento registrado.")
            self._refresh()
        except CashError as exc:
            warn(self, "Atenção", str(exc))