"""Tela de mensalistas: cadastro, mensalidades, inadimplência."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QInputDialog, QTabWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from app.domain.models import cents, format_money, format_pt_date
from app.services.monthly import MonthlyError
from app.ui.table_layout import ColumnLayout
from app.ui.widgets import (Card, error, info, make_label, page_header,
                            primary_button, warn, yes_no)


class _MonthlyTable(Card):
    def __init__(self, columns):
        super().__init__("")
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.body.addWidget(self.table)


class MonthlyScreen(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Mensalistas",
                                  "Planos mensais, cobranças e bloqueios (F6)"))

        actions = QHBoxLayout()
        self.btn_new = primary_button("+ Novo Mensalista", "primary")
        self.btn_new.clicked.connect(self.new_monthly)
        self.btn_pay = primary_button("Receber mensalidade", "success")
        self.btn_pay.clicked.connect(self.receive)
        self.btn_renew = primary_button("Renovar", "")
        self.btn_renew.clicked.connect(self.renew)
        self.btn_block = primary_button("Reavaliar bloqueios", "")
        self.btn_block.clicked.connect(self.assess)
        self.btn_edit = primary_button("Alterar", "")
        self.btn_edit.clicked.connect(self.edit_monthly)
        self.btn_del = primary_button("Excluir", "danger")
        self.btn_del.clicked.connect(self.remove_monthly)
        for b in (self.btn_new, self.btn_pay, self.btn_renew, self.btn_block,
                  self.btn_edit, self.btn_del):
            actions.addWidget(b)
        actions.addStretch(1)
        lay.addLayout(actions)

        self.tabs = QTabWidget()
        self.tab_ativo = _MonthlyTable(["Cliente", "Telefone", "Plano", "Valor",
                                        "Status", "Atrasadas"])
        self.tab_inad = _MonthlyTable(["Cliente", "Referência", "Vencimento", "Valor"])
        self.tab_pending = _MonthlyTable(["Cliente", "Placa", "Referência",
                                          "Vencimento", "Valor", "Ação"])
        self.tabs.addTab(self.tab_ativo, "Cadastrados")
        self.tabs.addTab(self.tab_inad, "Inadimplentes")
        self.tabs.addTab(self.tab_pending, "Mensalidades pendentes")
        lay.addWidget(self.tabs, 1)

        self._l1 = ColumnLayout(ctx, self.tab_ativo.table, "mensalistas_ativos")
        self._l2 = ColumnLayout(ctx, self.tab_inad.table, "mensalistas_inadimplentes")
        self._l3 = ColumnLayout(ctx, self.tab_pending.table, "mensalistas_pendentes")

    # ------------------------------------------------------------------
    def on_show(self):
        self._refresh()

    def _refresh(self):
        rows = self.ctx.monthly.list()
        t1 = self.tab_ativo.table
        t1.setRowCount(0)
        for r in rows:
            i = t1.rowCount()
            t1.insertRow(i)
            for c, val in enumerate([r["customer_name"], r["phone"] or "-",
                                     r["plan_name"],
                                     format_money(r["monthly_value"]),
                                     r["status"], r.get("overdue_count", 0)]):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                t1.setItem(i, c, item)
        self._l1.resize_event()

        overdue = self.ctx.db.query(
            "SELECT c.name customer_name, mp.reference, mp.due_date, mp.value"
            " FROM monthly_payments mp"
            " JOIN monthly_customers m ON m.id=mp.monthly_customer_id"
            " JOIN customers c ON c.id=m.customer_id"
            " WHERE mp.status='PENDENTE' AND mp.due_date < date('now')"
            " ORDER BY mp.due_date")
        t2 = self.tab_inad.table
        t2.setRowCount(0)
        for r in overdue:
            i = t2.rowCount()
            t2.insertRow(i)
            for c, val in enumerate([r["customer_name"], r["reference"],
                                     format_pt_date(r["due_date"]),
                                     format_money(r["value"])]):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                t2.setItem(i, c, item)
        self._l2.resize_event()

        pending = self.ctx.db.query(
            "SELECT mp.id payment_id, c.name customer_name, mp.reference, "
            "mp.due_date, mp.value, COALESCE((SELECT group_concat(v.plate, ', ') "
            "FROM monthly_contracts mc JOIN vehicles v ON v.id=mc.vehicle_id "
            "WHERE mc.monthly_customer_id=m.id), '—') plate "
            "FROM monthly_payments mp "
            "JOIN monthly_customers m ON m.id=mp.monthly_customer_id "
            "JOIN customers c ON c.id=m.customer_id "
            "WHERE mp.status='PENDENTE' ORDER BY mp.due_date")
        pt = self.tab_pending.table
        pt.setRowCount(0)
        for payment in pending:
            i = pt.rowCount()
            pt.insertRow(i)
            values = [payment["customer_name"], payment["plate"],
                      payment["reference"], format_pt_date(payment["due_date"]),
                      format_money(payment["value"])]
            for c, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                pt.setItem(i, c, item)
            pt.item(i, 0).setData(Qt.UserRole, payment["payment_id"])
            btn = primary_button("Receber", "success")
            btn.clicked.connect(
                lambda _=False, pid=payment["payment_id"]: self.receive_payment(pid))
            pt.setCellWidget(i, 5, btn)
        self._l3.resize_event()

    def _selected_monthly(self):
        table = self.tab_ativo.table
        idx = table.currentRow()
        rows = self.ctx.monthly.list()
        if idx < 0 or idx >= len(rows):
            warn(self, "Seleção", "Selecione um mensalista na lista.")
            return None
        return rows[idx]["id"]

    # ------------------------------------------------------------------
    def new_monthly(self):
        user = self.ctx.auth.require_permission("MONTHLY_MANAGE")
        customers = self.ctx.customers.list(limit=1000)
        if not customers:
            warn(self, "Sem clientes",
                 "Cadastre clientes primeiro (tela Clientes).")
            return
        name, okn = QInputDialog.getItem(self, "Cliente", "Selecione o cliente:",
                                         [f"{c['id']} — {c['name']}" for c in customers], 0, False)
        if not okn:
            return
        cid = int(name.split(" — ")[0])
        plate, okp = QInputDialog.getText(self, "Placa do veículo",
                                          "Placa (ex.: ABC1D23):")
        if not okp or not plate.strip():
            return
        value, okv = QInputDialog.getDouble(self, "Valor mensal",
                                            "Valor mensal (R$):", 250.0, 0.0, 10**8, 2)
        if not okv:
            return
        day, okd = QInputDialog.getInt(self, "Dia de vencimento",
                                       "Dia do mês (1-28):", 1, 1, 28)
        if not okd:
            return
        try:
            self.ctx.monthly.create(customer_id=cid, placa=plate.upper(),
                                    monthly_value=cents(str(value).replace(".", ",")),
                                    billing_day=day, user=user)
            info(self, "OK", "Mensalista cadastrado.")
            self._refresh()
        except MonthlyError as exc:
            warn(self, "Atenção", str(exc))
        except Exception as exc:
            error(self, "Erro", str(exc))

    def edit_monthly(self):
        user = self.ctx.auth.require_permission("MONTHLY_MANAGE")
        mid = self._selected_monthly()
        if not mid:
            return
        row = self.ctx.monthly.get(mid)
        if not row:
            warn(self, "Atenção", "Mensalista não encontrado.")
            return
        value, okv = QInputDialog.getDouble(
            self, "Alterar mensalista", "Valor mensal (R$):",
            row["monthly_value"] / 100.0, 0.0, 10**8, 2)
        if not okv:
            return
        day, okd = QInputDialog.getInt(
            self, "Alterar mensalista", "Dia de vencimento (1-28):",
            int(row.get("billing_day") or 1), 1, 28)
        if not okd:
            return
        try:
            self.ctx.monthly.update(mid,
                                    monthly_value=cents(str(value).replace(".", ",")),
                                    billing_day=day, user=user)
            info(self, "OK", "Mensalista alterado.")
            self._refresh()
        except MonthlyError as exc:
            warn(self, "Atenção", str(exc))
        except Exception as exc:
            error(self, "Erro", str(exc))

    def remove_monthly(self):
        user = self.ctx.auth.require_permission("MONTHLY_MANAGE")
        mid = self._selected_monthly()
        if not mid:
            return
        row = self.ctx.monthly.get(mid)
        if not row:
            warn(self, "Atenção", "Mensalista não encontrado.")
            return
        if not yes_no("Excluir mensalista",
                      f"Excluir o mensalista de <b>{row['customer_name']}</b>?<br><br>"
                      "A ação fica registrada na auditoria (MENSALISTA_REMOVIDO). "
                      "O mensalista some da lista, mas o histórico de pagamentos "
                      "e o cadastro original são preservados."):
            return
        try:
            self.ctx.monthly.delete(mid, user)
            info(self, "OK", "Mensalista excluído.")
            self._refresh()
        except MonthlyError as exc:
            warn(self, "Exclusão bloqueada", str(exc))
        except Exception as exc:
            error(self, "Erro", str(exc))

    def receive(self):
        if self.tabs.currentWidget() is self.tab_pending:
            row = self.tab_pending.table.currentRow()
            if row < 0:
                warn(self, "Seleção", "Use Receber na linha da mensalidade desejada.")
                return
            payment_id = self.tab_pending.table.item(row, 0).data(Qt.UserRole)
            if payment_id:
                self.receive_payment(payment_id)
            return
        mid = self._selected_monthly()
        if not mid:
            return
        pend = self.ctx.db.query(
            "SELECT * FROM monthly_payments WHERE monthly_customer_id=?"
            " AND status='PENDENTE' ORDER BY due_date LIMIT 1", (mid,))
        if not pend:
            info(self, "Em dia", "Este mensalista não possui mensalidades pendentes.")
            return
        pay = pend[0]
        self.receive_payment(pay["id"])

    def receive_payment(self, payment_id: int):
        user = self.ctx.auth.require_permission("MONTHLY_MANAGE")
        pay = self.ctx.db.query_one(
            "SELECT * FROM monthly_payments WHERE id=? AND status='PENDENTE'",
            (payment_id,))
        if not pay:
            warn(self, "Mensalidade", "Esta mensalidade já foi recebida ou não existe.")
            self._refresh()
            return
        method, okm = QInputDialog.getItem(
            self, "Pagamento", "Forma de pagamento:",
            ["DINHEIRO", "PIX", "CREDITO", "DEBITO", "TRANSFERENCIA"], 0, False)
        if not okm:
            return
        register = None
        try:
            reg = self.ctx.cash.require_open(user)
            register = reg["id"]
        except Exception:
            register = None
        try:
            self.ctx.monthly.pay_pending(pay["id"], int(pay["value"]), user=user,
                                         method=method, cash_register_id=register)
            info(self, "OK", f"Mensalidade de {format_money(pay['value'])} recebida.")
            self._refresh()
        except MonthlyError as exc:
            warn(self, "Atenção", str(exc))
        except Exception as exc:
            error(self, "Erro", str(exc))

    def renew(self):
        user = self.ctx.auth.require_permission("MONTHLY_MANAGE")
        mid = self._selected_monthly()
        if not mid:
            return
        try:
            self.ctx.monthly.renew(mid, user)
            info(self, "OK", "Mensalista renovado.")
            self._refresh()
        except MonthlyError as exc:
            warn(self, "Atenção", str(exc))

    def assess(self):
        self.ctx.auth.require_permission("MONTHLY_MANAGE")
        blocked = self.ctx.monthly.assess_blocking()
        if blocked:
            info(self, "Bloqueios",
                 f"{len(blocked)} mensalista(s) bloqueado(s) por inadimplência.")
        else:
            info(self, "Bloqueios", "Nenhum bloqueio aplicado.")
        self._refresh()
