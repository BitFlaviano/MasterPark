"""Dashboard com KPIs reais, ocupação e faturamento."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QProgressBar,
                               QVBoxLayout, QWidget)

from app.domain.models import format_money
from app.ui.icons import make_icon
from app.ui.theme import DANGER, SUCCESS, WARNING
from app.ui.widgets import Card, StatCard, make_label, page_header, primary_button

# Mantido por compatibilidade (o dashboard não usa mais emojis).
PL = {"DINHEIRO": "💵",
      "PIX": "⚡",
      "CREDITO": "💳",
      "DEBITO": "💳",
      "TRANSFERENCIA": "🏦",
      "CONVENIO": "🤝"}


def _text(value) -> str:
    return "-" if value is None else str(value)


class DashboardScreen(QWidget):
    def __init__(self, ctx, on_navigate, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.on_navigate = on_navigate
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(16)
        lay.addWidget(page_header(
            "Dashboard", f"Visão geral em {datetime.now().strftime('%d/%m/%Y %H:%M')}"))

        # Cor só quando tem significado: verde = receita, vermelho/âmbar = atenção.
        # (label, tom, subtítulo)
        spec = [
            ("Veículos agora", None, "tickets ativos"),
            ("Entradas hoje", None, ""),
            ("Saídas hoje", None, ""),
            ("Faturamento hoje", SUCCESS, ""),
            ("Receita do mês", None, ""),
            ("Ticket médio", None, ""),
            ("Mensalistas ativos", None, "planos"),
            ("Inadimplentes", DANGER, "bloqueiam na entrada"),
            ("Vencendo em 7 dias", WARNING, ""),
        ]
        grid = QGridLayout()
        grid.setSpacing(14)
        self.cards = [StatCard(label, "-", tone, sub) for label, tone, sub in spec]
        for i, card in enumerate(self.cards):
            grid.addWidget(card, i // 3, i % 3)
        for col in range(3):
            grid.setColumnStretch(col, 1)
        lay.addLayout(grid)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)

        # ocupação
        occ = Card("Ocupação das vagas")
        self.lbl_occ = make_label("-", "statValue")
        self.lbl_occ.setStyleSheet("font-size:34px;")
        self.lbl_occ.setProperty("tone", "primary")
        occ.body.addWidget(self.lbl_occ)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        occ.body.addWidget(self.progress)
        self.lbl_occ_detail = make_label("", "subtitle")
        self.lbl_occ_detail.setWordWrap(True)
        occ.body.addWidget(self.lbl_occ_detail)
        occ.body.addStretch(1)
        bottom.addWidget(occ, 2)

        # métodos de pagamento hoje
        pay = Card("Pagamentos de hoje")
        self.pay_box = QVBoxLayout()
        self.pay_box.setSpacing(10)
        pay.body.addLayout(self.pay_box)
        pay.body.addStretch(1)
        bottom.addWidget(pay, 2)

        # horários de pico
        peak = Card("Horários de pico (entradas)")
        self.peak_box = QVBoxLayout()
        self.peak_box.setSpacing(10)
        peak.body.addLayout(self.peak_box)
        peak.body.addStretch(1)
        bottom.addWidget(peak, 2)

        lay.addLayout(bottom, 1)

        # atalhos rápidos
        quick = QHBoxLayout()
        quick.setSpacing(10)
        for text, key, icon_name, tip in (("Nova Entrada", "entry", "log-in", "Atalho: F2"),
                                          ("Nova Saída", "exit", "log-out", "Atalho: F3")):
            btn = primary_button(text, "primary")
            btn.setIcon(make_icon(icon_name, "#FFFFFF"))
            btn.setIconSize(QSize(16, 16))
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _checked=False, k=key: self.on_navigate(k))
            quick.addWidget(btn)
        quick.addStretch(1)
        lay.addLayout(quick)

    # ------------------------------------------------------------------
    def on_show(self):
        data = self.ctx.analytics.dashboard()
        values = [
            data.get("vehicles_now"), data.get("entries_today"),
            data.get("exits_today"), format_money(data.get("revenue_today")),
            format_money(data.get("revenue_month")),
            format_money(data.get("ticket_medio")),
            data.get("monthly_active"), data.get("monthly_overdue"),
            data.get("monthly_expiring"),
        ]
        for card, value in zip(self.cards, values):
            card.set_value(_text(value))

        # alerta só quando há algo a tratar
        self.cards[7].set_tone(DANGER if (data.get("monthly_overdue") or 0) > 0 else None)
        self.cards[8].set_tone(WARNING if (data.get("monthly_expiring") or 0) > 0 else None)

        total = data.get("total") or 0
        occupied = data.get("occupied") or 0
        pct = data.get("pct_occupied") or 0
        self.lbl_occ.setText(f"{pct:.0f}%")
        self.progress.setValue(int(pct))
        self.lbl_occ_detail.setText(
            f"{occupied} ocupada(s) • {data.get('free') or 0} livre(s) • "
            f"{data.get('reserved') or 0} reservada(s) • {total} no total")

        self._fill_payments(data.get("payments") or [])
        self._fill_peak(data.get("blocks") or [])

    def _fill_payments(self, payments):
        self._clear(self.pay_box)
        if not payments:
            self.pay_box.addWidget(make_label("Nenhum pagamento hoje.", "subtitle"))
            return
        for p in payments:
            row = QHBoxLayout()
            row.addWidget(make_label(str(p["method_name"]), "statLabel"))
            row.addStretch(1)
            row.addWidget(make_label(format_money(p["total"]), "statValue", 15))
            qty = make_label(f"{p['qty']}x", "subtitle")
            qty.setMinimumWidth(30)
            row.addWidget(qty)
            self.pay_box.addLayout(row)

    def _fill_peak(self, blocks):
        self._clear(self.peak_box)
        if not blocks:
            self.peak_box.addWidget(make_label("Sem dados de hoje.", "subtitle"))
            return
        biggest = max((x["count"] for x in blocks), default=1) or 1
        for b in sorted(blocks, key=lambda x: -x["count"])[:6]:
            row = QHBoxLayout()
            row.setSpacing(10)
            hour = make_label(f"{b['hour']:02d}h", "statLabel")
            hour.setMinimumWidth(34)
            row.addWidget(hour)
            bar = QProgressBar()
            bar.setRange(0, biggest)
            bar.setValue(b["count"])
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            row.addWidget(bar, 1)
            count = make_label(f"{b['count']}", "statLabel")
            count.setMinimumWidth(24)
            row.addWidget(count)
            self.peak_box.addLayout(row)

    @staticmethod
    def _clear(layout):
        """Remove widgets E sub-layouts (senão as linhas vazias acumulam espaçamento)."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                DashboardScreen._clear(item.layout())
                item.layout().deleteLater()
