"""Serviço de caixa: abertura, fechamento, sangria, suprimento, lançamentos."""
from __future__ import annotations

from app.core.audit import AuditService
from app.domain.models import CurrentUser, utcnow_iso
from app.repositories.operation import CashRepo


class CashError(Exception):
    pass


class CashService:
    def __init__(self, db):
        self.db = db
        self.cash = CashRepo(db)
        self.audit = AuditService(db)

    def active_for(self, user_id: int) -> dict | None:
        return self.cash.active(user_id)

    def require_open(self, user: CurrentUser) -> dict:
        reg = self.cash.active(user.id)
        if not reg:
            raise CashError("Nenhum caixa aberto para este operador. Abra o caixa primeiro.")
        return reg

    def open(self, *, user: CurrentUser, opening_value: int = 0,
             lot_id: int | None = None) -> dict:
        existing = self.cash.active(user.id)
        if existing:
            raise CashError(f"Caixa {existing['id']} já está aberto.")
        reg_id = self.cash.open_register(lot_id, user.id, opening_value)
        self.cash.add_movement(reg_id, "ABERTURA", opening_value,
                               "Abertura de caixa", user.id)
        self.audit.add(user, "CAIXA_ABERTO", "cash_register", reg_id,
                       new=f"abertura={opening_value}")
        return self.cash.get(reg_id)

    def close(self, *, user: CurrentUser, informed: int,
              justification: str = "") -> dict:
        reg = self.cash.active(user.id)
        if not reg:
            raise CashError("Nenhum caixa aberto.")
        # pré-valida diferença antes de fechar
        expected = self.cash.current_balance(reg["id"])
        diff = expected - informed
        if diff != 0 and not justification.strip():
            raise CashError("Diferença de caixa exige justificativa.")
        result = self.cash.close(reg["id"], informed, justification)
        self.audit.add(user, "CAIXA_FECHADO", "cash_register", reg["id"],
                       new=f"diferença={result['difference']}",
                       reason=justification)
        return result

    def sangria(self, *, user: CurrentUser, value: int, reason: str) -> dict:
        reg = self.require_open(user)
        if value <= 0:
            raise CashError("Valor de sangria inválido.")
        if not reason.strip():
            raise CashError("Informe o motivo da sangria.")
        self.cash.add_movement(reg["id"], "SANGRIA", -value, reason, user.id)
        self.audit.add(user, "CAIXA_SANGRIA", "cash_register", reg["id"],
                       new=f"-{value}", reason=reason)
        return self.cash.get(reg["id"])

    def suprimento(self, *, user: CurrentUser, value: int, reason: str) -> dict:
        reg = self.require_open(user)
        if value <= 0:
            raise CashError("Valor de suprimento inválido.")
        self.cash.add_movement(reg["id"], "SUPRIMENTO", value, reason, user.id)
        self.audit.add(user, "CAIXA_SUPRIMENTO", "cash_register", reg["id"],
                       new=f"+{value}", reason=reason)
        return self.cash.get(reg["id"])

    def manual_entry(self, *, user: CurrentUser, value: int, description: str) -> dict:
        reg = self.require_open(user)
        self.cash.add_movement(reg["id"], "ENTRADA_MANUAL", value, description, user.id)
        self.audit.add(user, "CAIXA_ENTRADA_MANUAL", "cash_register", reg["id"],
                       new=f"+{value}", reason=description)
        return self.cash.get(reg["id"])

    def manual_exit(self, *, user: CurrentUser, value: int, description: str) -> dict:
        reg = self.require_open(user)
        self.cash.add_movement(reg["id"], "SAIDA_MANUAL", -value, description, user.id)
        self.audit.add(user, "CAIXA_SAIDA_MANUAL", "cash_register", reg["id"],
                       new=f"-{value}", reason=description)
        return self.cash.get(reg["id"])

    def current_balance(self, user: CurrentUser) -> int:
        reg = self.cash.active(user.id)
        if not reg:
            return 0
        return int(self.db.scalar(
            "SELECT COALESCE(SUM(value),0) FROM cash_movements WHERE cash_register_id=?",
            (reg["id"],)) or 0) + int(reg["opening_value"] or 0)

    def status(self, user: CurrentUser) -> dict:
        reg = self.cash.active(user.id)
        if not reg:
            return {"open": False}
        return {"open": True, "register_id": reg["id"], "opened_at": reg["opened_at"],
                "opening_value": reg["opening_value"],
                "balance": self.current_balance(user),
                "movements": self.cash.movements(reg["id"])}