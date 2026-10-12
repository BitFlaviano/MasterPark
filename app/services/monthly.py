"""Serviço de mensalistas: cadastro, mensalidades, inadimplência, bloqueio."""
from __future__ import annotations

from datetime import datetime

from app.core.audit import AuditService
from app.domain.models import CurrentUser, format_money, utcnow_iso
from app.repositories import CustomerRepo, SpaceRepo, VehicleRepo
from app.repositories.operation import (MonthlyRepo, NotificationRepo,
                                        PaymentRepo)


class MonthlyError(Exception):
    pass


class MonthlyService:
    def __init__(self, db, lot=None):
        self.db = db
        self.monthly = MonthlyRepo(db)
        self.customers = CustomerRepo(db)
        self.vehicles = VehicleRepo(db)
        self.spaces = SpaceRepo(db)
        self.payments = PaymentRepo(db)
        self.notifications = NotificationRepo(db)
        self.audit = AuditService(db)
        self.lot = lot

    def create(self, *, customer_id: int, placa: str, monthly_value: int,
               billing_day: int = 1, space_code: str = "", user: CurrentUser) -> dict:
        customer = self.customers.get(customer_id)
        if not customer:
            raise MonthlyError("Cliente não encontrado.")
        if monthly_value <= 0:
            raise MonthlyError("Valor mensal inválido.")
        vehicle = self.vehicles.by_plate(placa)
        if not vehicle:
            vid = self.vehicles.create(dict(plate=placa, category="CARRO",
                                            customer_id=customer_id))
            vehicle = self.vehicles.get(vid)
        space_id = None
        if space_code:
            space = self.db.query_one(
                "SELECT * FROM parking_spaces WHERE code=? AND state='LIVRE' AND active=1",
                (space_code.upper(),))
            if not space:
                raise MonthlyError(f"Vaga {space_code} não disponível.")
            space_id = space["id"]

        mid = self.monthly.create(dict(
            customer_id=customer_id, plan_name="Mensalista", status="ATIVO",
            start_at=utcnow_iso(), monthly_value=monthly_value,
            billing_day=max(1, min(28, billing_day))))
        self.monthly.add_contract(mid, vehicle["id"], space_id, monthly_value)
        if space_id:
            self.db.execute(
                "UPDATE parking_spaces SET state='RESERVADA', monthly_contract_id=? WHERE id=?",
                (mid, space_id))

        # gera primeira mensalidade
        today = datetime.now()
        due = today.replace(day=billing_day)
        reference = today.strftime("%Y-%m")
        self.monthly.create_payment(mid, due.strftime("%Y-%m-%d"), reference, monthly_value)
        self.audit.add(user, "MENSALISTA_CRIADO", "monthly_customer", mid,
                       new=f"{customer['name']} · {format_money(monthly_value)}")
        return self.monthly.get(mid)

    def renew(self, monthly_id: int, user: CurrentUser) -> dict:
        row = self.monthly.get(monthly_id)
        if not row:
            raise MonthlyError("Mensalista não encontrado.")
        now = datetime.now()
        due = now.replace(day=max(1, min(28, row.get("billing_day") or 1)))
        ref = now.strftime("%Y-%m")
        existing = self.db.query_one(
            "SELECT id FROM monthly_payments WHERE monthly_customer_id=? AND reference=?",
            (monthly_id, ref))
        if not existing:
            self.monthly.create_payment(monthly_id, due.strftime("%Y-%m-%d"), ref,
                                        int(row["monthly_value"]))
        self.monthly.set_status(monthly_id, "ATIVO")
        self.audit.add(user, "MENSALISTA_RENOVADO", "monthly_customer", monthly_id)
        self._auto_unblock(monthly_id, user)
        return self.monthly.get(monthly_id)

    def pay_pending(self, payment_id: int, value: int, user: CurrentUser,
                    method: str = "DINHEIRO",
                    cash_register_id: int | None = None) -> None:
        pay = self.db.query_one(
            "SELECT * FROM monthly_payments WHERE id=? AND status='PENDENTE'", (payment_id,))
        if not pay:
            raise MonthlyError("Mensalidade não encontrada ou já paga.")
        mid = pay["monthly_customer_id"]
        with self.db.transaction() as cur:
            pid = cur.execute(
                "INSERT INTO payments(monthly_payment_id, payment_method, status, value,"
                " received_at, received_value, operator_id, cash_register_id, created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (payment_id, method, "APROVADO", int(pay["value"]), utcnow_iso(),
                 int(value), user.id, cash_register_id, utcnow_iso())).lastrowid
            cur.execute(
                "UPDATE monthly_payments SET status='PAGO', paid_at=?, paid_value=?, payment_id=?"
                " WHERE id=?", (utcnow_iso(), int(value), pid, payment_id))
            if cash_register_id:
                cur.execute(
                    "INSERT INTO cash_movements(cash_register_id, payment_id, kind, value,"
                    " description, operator_id, created_at) VALUES(?,?,?,?,?,?,?)",
                    (cash_register_id, pid, "PAGAMENTO", int(value),
                     f"Mensalidade {mid} · {method}", user.id, utcnow_iso()))
        self._auto_unblock(mid, user)
        self.audit.add(user, "MENSALIDADE_PAGA", "monthly_payment", payment_id,
                       new=f"{format_money(int(pay['value']))}")

    def _auto_unblock(self, monthly_id: int, user: CurrentUser) -> None:
        overdue = self.db.scalar(
            "SELECT COUNT(*) FROM monthly_payments WHERE monthly_customer_id=? AND status='PENDENTE'",
            (monthly_id,)) or 0
        if overdue == 0:
            self.monthly.set_status(monthly_id, "ATIVO")

    def assess_blocking(self) -> list[dict]:
        """Bloqueia mensalistas inadimplentes por regra de negócio."""
        rows = self.monthly.overdue()
        blocked = []
        for r in rows:
            mid = r["id"]
            if r.get("status") in ("ATIVO", "INADIMPLENTE"):
                self.monthly.set_status(mid, "BLOQUEADO")
                blocked.append(r)
                self.notifications.push("WARNING", "MENSALISTA_BLOQUEADO",
                                        f"{r['customer_name']} bloqueado por inadimplência.")
        return blocked

    def dashboard_alerts(self) -> dict:
        overdue = self.monthly.overdue()
        expiring = self.monthly.expiring(7)
        return {
            "overdue_count": len(overdue),
            "overdue_total": sum(int(r["value"]) for r in overdue),
            "expiring_count": len(expiring),
            "active_count": self.monthly.active_count(),
        }

    def update(self, monthly_id: int, *,
               monthly_value: int | None = None,
               billing_day: int | None = None,
               user: CurrentUser) -> dict:
        """Altera dados do mensalista (valor mensal e/ou dia de cobrança)."""
        row = self.monthly.get(monthly_id)
        if not row:
            raise MonthlyError("Mensalista não encontrado.")
        data: dict = {}
        if monthly_value is not None:
            if monthly_value <= 0:
                raise MonthlyError("Valor mensal inválido.")
            data["monthly_value"] = monthly_value
        if billing_day is not None:
            data["billing_day"] = max(1, min(28, billing_day))
        if not data:
            return row
        self.monthly.update(monthly_id, data)
        self.audit.add(user, "MENSALISTA_ALTERADO", "monthly_customer", monthly_id,
                       new=f"{row['customer_name']} · {format_money(data.get('monthly_value', row['monthly_value']))}"
                       + (f" · dia {data['billing_day']}" if "billing_day" in data else ""))
        return self.monthly.get(monthly_id)

    def delete(self, monthly_id: int, user: CurrentUser) -> None:
        """Exclui o mensalista (exclusão lógica, o histórico fiscal é mantido)."""
        row = self.monthly.get(monthly_id)
        if not row:
            raise MonthlyError("Mensalista não encontrado.")
        if not self.monthly.delete(monthly_id):
            raise MonthlyError("Não foi possível excluir o mensalista.")
        self.audit.add(user, "MENSALISTA_REMOVIDO", "monthly_customer", monthly_id,
                       new=f"{row['customer_name']}")
        self._auto_free_lot()

    def _auto_free_lot(self) -> None:
        """Recalcula totais do painel após exclusão de mensalista."""
        try:
            self.ctx.dashboard_cache_invalidate()
        except Exception:
            pass

    def get(self, monthly_id: int) -> dict | None:
        """Consulta direta usada pela tela antes de alterar/excluir."""
        return self.monthly.get(monthly_id)

    def list(self, status: str = "") -> list[dict]:
        return self.monthly.list(status)