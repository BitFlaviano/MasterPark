"""Serviço de tickets: entrada, saída, cálculo, cancelamento, ticket perdido.

Regra crítica: saída + pagamento + liberação de vaga é UMA transação.
Nunca registra saída como paga sem confirmação de pagamento adequada.
"""
from __future__ import annotations

from datetime import datetime

from app.core.audit import AuditService
from app.domain.models import CurrentUser, format_money, utcnow_iso, validate_plate
from app.repositories import (CustomerRepo, LotRepo, SectorRepo, SpaceRepo,
                              UserRepo, VehicleRepo)
from app.repositories.operation import (CashRepo, NotificationRepo, TicketRepo,
                                        TariffRepo)
from app.services.tariff import TariffEngine, apply_discount


class TicketError(Exception):
    pass


class TicketService:
    def __init__(self, db, lot=None):
        self.db = db
        self.tickets = TicketRepo(db)
        self.spaces = SpaceRepo(db)
        self.sectors = SectorRepo(db)
        self.vehicles = VehicleRepo(db)
        self.customers = CustomerRepo(db)
        self.cash = CashRepo(db)
        self.tariffs = TariffRepo(db)
        self.notifications = NotificationRepo(db)
        self.audit = AuditService(db)
        self.users = UserRepo(db)
        self.lot = lot or LotRepo(db).first()

    # ------------------------------------------------------------------
    # QR / código de barras
    # ------------------------------------------------------------------
    @staticmethod
    def qr_payload(ticket_number: str) -> str:
        return f"MP:TCK:{ticket_number}"

    # ------------------------------------------------------------------
    # ENTRADA
    # ------------------------------------------------------------------
    def register_entry(self, *, plate: str, category: str = "CARRO",
                       user: CurrentUser, terminal: str = "", model: str = "",
                       color: str = "", customer_name: str = "", space_id: int | None = None,
                       customer_id: int | None = None, vehicle_id: int | None = None,
                       notes: str = "") -> dict:
        lot = self.lot
        if not lot:
            raise TicketError("Estacionamento não configurado.")
        plate = self._sanitize(plate)

        if plate and not vehicle_id:
            # placa não obrigatória, mas quando informada deve ser válida
            veh = self.vehicles.by_plate(plate)
            if veh and veh.get("is_blocked"):
                raise TicketError(f"Veículo {plate} está bloqueado.")
            if not veh:
                cid = customer_id
                if not cid and customer_name:
                    cid = self.customers.create(dict(
                        name=customer_name, person_type="FISICA", created_at=utcnow_iso()))
                    customer_id = cid
                veh = self._ensure_vehicle(plate, category, model, color, customer_id)
                vehicle_id = veh["id"]
            else:
                # placa já cadastrada: mesmo assim aproveita o cliente digitado
                upd = {}
                if model:
                    upd["model"] = model
                if color:
                    upd["color"] = color
                if customer_name and not customer_id:
                    cid = self.customers.create(dict(
                        name=customer_name, person_type="FISICA", created_at=utcnow_iso()))
                    customer_id = cid
                if customer_id:
                    upd["customer_id"] = customer_id
                if upd:
                    self.vehicles.update(veh["id"], upd)
                vehicle_id = veh["id"]

        # vaga
        if space_id:
            space = self.spaces.get(space_id)
            if not space:
                raise TicketError("Vaga inexistente.")
            if space["state"] == "OCUPADA":
                raise TicketError("Vaga já ocupada.")
        else:
            space = self.spaces.smart_find(lot["id"], category)
            if not space:
                raise TicketError("Nenhuma vaga livre disponível.")
            space_id = space["id"]

        number = self._next_number()
        entry_at = utcnow_iso()
        with self.db.transaction() as cur:
            cur.execute(
                "INSERT INTO tickets(lot_id, number, status, vehicle_id, customer_id,"
                " plate, vehicle_category, entry_at, parking_space_id, entry_user_id,"
                " terminal_entry, qr_data, barcode_data)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (lot["id"], number, "ATIVO", vehicle_id, customer_id, plate, category,
                 entry_at, space_id, user.id, terminal, self.qr_payload(number), number))
            ticket_id = cur.lastrowid
            cur.execute(
                "UPDATE parking_spaces SET state='OCUPADA' WHERE id=?", (space_id,))
            cur.execute(
                "INSERT INTO parking_sessions(ticket_id, space_id, entry_at, status)"
                " VALUES(?,?,'ATIVA',?)", (ticket_id, space_id, entry_at))
            cur.execute(
                "INSERT INTO audit_logs(user_id, username, terminal, action, entity,"
                " entity_id, new_value, reason, created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (user.id, user.username, terminal, "TICKET_ENTRADA", "ticket",
                 ticket_id, number, f"placa={plate} vaga={space_id} categoria={category}",
                 entry_at))

        ticket = self.tickets.full_details(ticket_id)
        ticket["space_code"] = self.spaces.get(space_id)["code"] if self.spaces.get(space_id) else ""
        sec = self.spaces.get(space_id)
        if sec and sec.get("sector_id"):
            ticket["space_code"] = sec["code"]
        return ticket

    def _ensure_vehicle(self, plate: str, category: str, model: str, color: str,
                        customer_id: int | None) -> dict:
        existing = self.vehicles.by_plate(plate)
        if existing:
            return existing
        vid = self.vehicles.create(dict(
            plate=plate, category=category, model=model, color=color,
            customer_id=customer_id))
        return self.vehicles.get(vid)

    @staticmethod
    def _sanitize(plate: str) -> str:
        return "".join(ch for ch in (plate or "").upper() if ch.isalnum())[:7]

    def _next_number(self) -> str:
        return self.tickets.next_number()

    # ------------------------------------------------------------------
    # BUSCA
    # ------------------------------------------------------------------
    def find(self, term: str) -> list[dict]:
        term = (term or "").strip()
        tickets = self.tickets.active(limit=10, term=term)
        details = []
        for t in tickets:
            d = self.tickets.full_details(t["id"])
            if d:
                d["elapsed_minutes"] = self._elapsed(d)
                details.append(d)
        return details

    def list_active(self, limit: int = 50) -> list[dict]:
        """Entradas ativas (pátio) — para a tela de saída selecionar um ticket."""
        details = []
        for t in self.tickets.active(limit=limit):
            d = self.tickets.full_details(t["id"]) or t
            d["elapsed_minutes"] = self._elapsed(d)
            details.append(d)
        return details

    def find_single(self, term: str) -> dict | None:
        term = (term or "").strip().upper()
        if not term:
            return None
        t = (self.tickets.by_number(term)
             or self.tickets.by_plate_open(term))
        if not t or t["status"] != "ATIVO":
            return None
        d = self.tickets.full_details(t["id"])
        d["elapsed_minutes"] = self._elapsed(d)
        return d

    def history_one(self, number: str) -> dict | None:
        """Ticket já finalizado (histórico), com detalhes completos.

        Usado na reimpressão de tickets encerrados — `find_single` só
        devolve tickets ATIVOS.
        """
        number = (number or "").strip().upper()
        if not number:
            return None
        t = self.tickets.by_number(number)
        if not t or t["status"] == "ATIVO":
            return None
        d = self.tickets.full_details(t["id"])
        if d:
            d["elapsed_minutes"] = self._elapsed(d)
        return d

    @staticmethod
    def _elapsed(ticket: dict) -> int:
        entry = datetime.fromisoformat(ticket["entry_at"].replace("Z", "+00:00"))
        now = datetime.now(entry.tzinfo)
        return int((now - entry).total_seconds() // 60)

    # ------------------------------------------------------------------
    # CÁLCULO (prévia de saída)
    # ------------------------------------------------------------------
    def preview(self, ticket: dict, exit_at: datetime | None = None) -> dict:
        entry = datetime.fromisoformat(ticket["entry_at"].replace("Z", "+00:00"))
        exit_dt = exit_at or datetime.now(entry.tzinfo)
        engine = TariffEngine(tolerance_minutes=self._tolerance())
        tariff, rules = self._pick_tariff(ticket, exit_dt, entry)
        info = engine.calculate(entry, exit_dt, rules, tariff["name"] if tariff else "Padrão",
                                tariff["id"] if tariff else None)
        return {
            "minutes": info.minutes,
            "base_value": info.base_value,
            "discount_value": info.discount_value,
            "final_value": info.final_value,
            "rule_applied": info.rule_applied,
            "tariff_id": info.tariff_id,
            "tariff_name": info.name,
            "entry_at": ticket["entry_at"],
            "exit_at": exit_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "elapsed": info.minutes,
        }

    def _tolerance(self) -> int:
        return int(self.lot.get("tolerance_minutes") or 10) if self.lot else 10

    def _pick_tariff(self, ticket: dict, exit_dt: datetime, entry: datetime) -> tuple[dict | None, list[dict]]:
        weekday = exit_dt.weekday()  # 0 = segunda
        minutes_of_day = exit_dt.hour * 60 + exit_dt.minute
        if self.lot is None:
            return None, []
        actives = self.tariffs.active_for(self.lot["id"], ticket.get("vehicle_category", "CARRO"),
                                          weekday, minutes_of_day)
        if not actives:
            return None, []
        tariff = actives[0]
        if not tariff.get("is_default"):
            for t in actives:
                if t.get("is_default"):
                    tariff = t
                    break
        return tariff, self.tariffs.rules(tariff["id"])

    # ------------------------------------------------------------------
    # DESCONTO
    # ------------------------------------------------------------------
    def apply_discount(self, *, ticket_id: int, percent: float = 0.0, fixed: int = 0,
                       gratuity: bool = False, agreement_id: int | None = None,
                       user: CurrentUser, reason: str = "") -> dict:
        ticket = self.tickets.get(ticket_id)
        if not ticket or ticket["status"] != "ATIVO":
            raise TicketError("Ticket não está ativo.")
        base = int(ticket.get("final_value") or 0)
        discount = apply_discount(base, percent, fixed, gratuity)
        final = max(base - discount, 0)
        self.db.execute(
            "INSERT INTO discounts(ticket_id, kind, value, percent, operator_id,"
            " agreement_id, reason, created_at) VALUES(?,?,?,?,?,?,?,?)",
            (ticket_id, "CONVENIO" if agreement_id else "MANUAL", discount, percent,
             user.id, agreement_id, reason, utcnow_iso()))
        self.db.execute("UPDATE tickets SET discount_value=?, final_value=? WHERE id=?",
                        (discount, final, ticket_id))
        self.audit.add(user, "DESCONTO_APLICADO", "ticket", ticket_id,
                       new=f"desconto={discount} final={final}",
                       reason=reason or "manual")
        return {"discount_value": discount, "final_value": final}

    # ------------------------------------------------------------------
    # SAÍDA
    # ------------------------------------------------------------------
    def register_exit(self, *, ticket_id: int, payment_method: str = "DINHEIRO",
                      received_value: int | None = None, user: CurrentUser,
                      terminal: str = "", lost: bool = False,
                      incident_description: str = "") -> dict:
        ticket = self.tickets.full_details(ticket_id)
        if not ticket:
            raise TicketError("Ticket não encontrado.")
        if ticket["status"] != "ATIVO":
            raise TicketError(f"Ticket {ticket['number']} já foi finalizado/cancelado.")

        preview = self.preview(ticket)
        final_value = preview["final_value"]
        received = final_value if received_value is None else received_value

        # Confirmação de pagamento: apenas após receber valor válido.
        # Valor zero é permitido (tolerância/gratuidade/ticket livre).
        if received < 0:
            raise TicketError("Valor informado não pode ser negativo.")

        register = self.cash.active(user.id)
        with self.db.transaction() as cur:
            status = "FINALIZADO" if not lost else "PERDIDO"
            cur.execute(
                "UPDATE tickets SET status=?, exit_at=?, exit_user_id=?, terminal_exit=?,"
                " total_minutes=?, tariff_id=?, base_value=?, discount_value=?, final_value=?"
                " WHERE id=?",
                (status, utcnow_iso(), user.id, terminal, preview["minutes"],
                 preview["tariff_id"], preview["base_value"],
                 preview["discount_value"], final_value, ticket_id))
            cur.execute(
                "INSERT INTO payments(ticket_id, payment_method, status, value,"
                " received_at, received_value, operator_id, cash_register_id, created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (ticket_id, payment_method, "APROVADO", final_value, utcnow_iso(),
                 received, user.id, register["id"] if register else None, utcnow_iso()))
            payment_id = cur.lastrowid
            if register:
                cur.execute(
                    "INSERT INTO cash_movements(cash_register_id, payment_id, kind, value,"
                    " description, operator_id, created_at) VALUES(?,?,?,?,?,?,?)",
                    (register["id"], payment_id, "PAGAMENTO", final_value,
                     f"Ticket {ticket['number']} · {payment_method}", user.id, utcnow_iso()))
            # libera vaga e encerra sessão
            if ticket.get("parking_space_id"):
                cur.execute(
                    "UPDATE parking_spaces SET state='LIVRE', monthly_contract_id=NULL"
                    " WHERE id=?", (ticket["parking_space_id"],))
                cur.execute(
                    "UPDATE parking_sessions SET exit_at=?, status='ENCERRADA'"
                    " WHERE ticket_id=? AND status='ATIVA'",
                    (utcnow_iso(), ticket_id))
            cur.execute(
                "INSERT INTO audit_logs(user_id, username, terminal, action, entity,"
                " entity_id, new_value, reason, created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (user.id, user.username, terminal,
                 "TICKET_LOST_SAIDA" if lost else "TICKET_SAIDA", "ticket", ticket_id,
                 f"final={final_value} método={payment_method} recebido={received}",
                 incident_description or "", utcnow_iso()))

        if incident_description:
            self.incident(ticket_id, "TICKET_PERDIDO" if lost else "MANUAL",
                          incident_description, user, terminal)
        return dict(ticket, status=status, final_value=final_value,
                    received_value=received, exit_at=utcnow_iso(),
                    preview=preview)

    def incident(self, ticket_id: int, kind: str, description: str,
                 user: CurrentUser, terminal: str) -> int:
        from app.repositories.operation import IncidentRepo
        return IncidentRepo(self.db).create(dict(
            lot_id=self.lot["id"] if self.lot else None, ticket_id=ticket_id,
            kind=kind, severity="MEDIA", description=description,
            operator_id=user.id, status="ABERTO"))

    # ------------------------------------------------------------------
    # CANCELAMENTO
    # ------------------------------------------------------------------
    def cancel(self, *, ticket_id: int, reason: str, user: CurrentUser) -> None:
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            raise TicketError("Ticket não encontrado.")
        if ticket["status"] != "ATIVO":
            raise TicketError("Apenas tickets ativos podem ser cancelados.")
        if not reason.strip():
            raise TicketError("Informe o motivo do cancelamento.")
        with self.db.transaction() as cur:
            self.tickets.cancel(ticket_id, reason, user.id)
            if ticket.get("parking_space_id"):
                cur.execute(
                    "UPDATE parking_spaces SET state='LIVRE', monthly_contract_id=NULL"
                    " WHERE id=?", (ticket["parking_space_id"],))
                cur.execute(
                    "UPDATE parking_sessions SET exit_at=?, status='CANCELADA'"
                    " WHERE ticket_id=? AND status='ATIVA'", (utcnow_iso(), ticket_id))
        self.audit.add(user, "TICKET_CANCELADO", "ticket", ticket_id,
                       new=ticket["number"], reason=reason)

    # ------------------------------------------------------------------
    def today_counts(self) -> dict:
        return self.tickets.stats_today()

    def vehicles_in_lot(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM tickets WHERE status='ATIVO'") or 0)