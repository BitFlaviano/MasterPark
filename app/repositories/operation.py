"""Repositórios da operação: tickets, caixa, mensalistas, tarifas, etc."""
from __future__ import annotations

from app.core.db import Database
from app.domain.models import utcnow_iso


def _dt() -> str:
    return utcnow_iso()


class Repo:
    def __init__(self, db: Database):
        self.db = db


# ----------------------------------------------------------------------
# Tickets
# ----------------------------------------------------------------------
class TicketRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO tickets({cols}) VALUES({ph})",
                               (*data.values(),))

    def get(self, ticket_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM tickets WHERE id=?", (ticket_id,))

    def by_number(self, number: str) -> dict | None:
        return self.db.query_one("SELECT * FROM tickets WHERE number=?", (number.strip().upper(),))

    def by_plate_open(self, plate: str) -> dict | None:
        return self.db.query_one(
            "SELECT * FROM tickets WHERE plate=? AND status='ATIVO' ORDER BY id DESC LIMIT 1",
            (plate.upper(),))

    def active(self, limit: int = 100, term: str = "") -> list[dict]:
        sql = ("SELECT t.*, s.code space_code FROM tickets t"
               " LEFT JOIN parking_spaces s ON s.id=t.parking_space_id"
               " WHERE t.status='ATIVO'")
        params: list = []
        if term:
            sql += " AND (t.plate LIKE ? OR t.number LIKE ?)"
            params += [f"%{term.upper()}%", f"%{term.upper()}%"]
        sql += " ORDER BY t.entry_at DESC LIMIT ?"
        params.append(limit)
        return self.db.query(sql, tuple(params))

    def full_details(self, ticket_id: int) -> dict | None:
        return self.db.query_one(
            "SELECT t.*, s.code space_code, sec.name sector_name,"
            " ue.name entry_user_name, ux.name exit_user_name,"
            " c.name customer_name"
            " FROM tickets t"
            " LEFT JOIN parking_spaces s ON s.id=t.parking_space_id"
            " LEFT JOIN parking_sectors sec ON sec.id=s.sector_id"
            " LEFT JOIN users ue ON ue.id=t.entry_user_id"
            " LEFT JOIN users ux ON ux.id=t.exit_user_id"
            " LEFT JOIN customers c ON c.id=t.customer_id"
            " WHERE t.id=?",
            (ticket_id,))

    def finish(self, ticket_id: int, *, exit_at: str, exit_user_id: int,
               terminal: str, total_minutes: int, tariff_id: int | None,
               base_value: int, discount_value: int, final_value: int) -> None:
        self.db.execute(
            "UPDATE tickets SET status='FINALIZADO', exit_at=?, exit_user_id=?,"
            " terminal_exit=?, total_minutes=?, tariff_id=?, base_value=?,"
            " discount_value=?, final_value=? WHERE id=?",
            (exit_at, exit_user_id, terminal, total_minutes, tariff_id,
             base_value, discount_value, final_value, ticket_id))

    def cancel(self, ticket_id: int, reason: str, user_id: int) -> None:
        self.db.execute(
            "UPDATE tickets SET status='CANCELADO', exit_user_id=?, cancel_reason=?,"
            " exit_at=? WHERE id=?", (user_id, reason, _dt(), ticket_id))

    def lost(self, ticket_id: int, user_id: int, terminal: str,
             total_minutes: int, tariff_id: int | None, base_value: int,
             discount_value: int, final_value: int) -> None:
        self.db.execute(
            "UPDATE tickets SET status='PERDIDO', exit_user_id=?, terminal_exit=?,"
            " exit_at=?, total_minutes=?, tariff_id=?, base_value=?, discount_value=?,"
            " final_value=? WHERE id=?", (user_id, terminal, _dt(), total_minutes,
                                          tariff_id, base_value, discount_value, final_value))

    def stats_today(self) -> dict:
        today = _dt()
        return {
            "entradas": self._count(f"entry_at >= date('now','localtime')"),
            "saidas": self._count("status='FINALIZADO'"),
            "abertos": self._count("status='ATIVO'"),
            "cancelados": self._count("status='CANCELADO'"),
        }

    def _count(self, where: str) -> int:
        return int(self.db.scalar(f"SELECT COUNT(*) FROM tickets WHERE {where}") or 0)

    def revenue_by_period(self, start_utc: str, end_utc: str) -> int:
        row = self.db.query_one(
            "SELECT COALESCE(SUM(final_value),0) v FROM tickets"
            " WHERE exit_at>=? AND exit_at<=? AND status IN ('FINALIZADO','PERDIDO')",
            (start_utc, end_utc))
        return int(row["v"]) if row else 0

    def payments_by_method(self, start_utc: str, end_utc: str) -> list[dict]:
        return self.db.query(
            "SELECT pm.code, pm.name method_name, COALESCE(SUM(m.value),0) total, COUNT(*) qty"
            " FROM payments m JOIN payment_methods pm ON pm.code=m.payment_method"
            " WHERE m.received_at>=? AND m.received_at<=? AND m.status='APROVADO'"
            " GROUP BY pm.code, pm.name ORDER BY total DESC",
            (start_utc, end_utc))

    def list_paged(self, term: str = "", status: str = "", limit: int = 50,
                   offset: int = 0) -> list[dict]:
        sql = "SELECT t.* FROM tickets t WHERE 1=1"
        params: list = []
        if term:
            sql += " AND (t.plate LIKE ? OR t.number LIKE ?)"
            params += [f"%{term}%", f"%{term}%"]
        if status:
            sql += " AND t.status=?"
            params.append(status)
        sql += " ORDER BY t.id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        return self.db.query(sql, tuple(params))

    def count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM tickets") or 0)

    def next_number(self) -> str:
        last = int(self.db.scalar("SELECT COALESCE(MAX(id),0) FROM tickets") or 0)
        return f"T{last + 1:08d}"


# ----------------------------------------------------------------------
# Tarifas
# ----------------------------------------------------------------------
class TariffRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO tariffs({cols}, created_at) VALUES({ph}, ?)",
                               (*data.values(), _dt()))

    def list(self, lot_id: int | None = None, active_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM tariffs"
        where, params = [], []
        if lot_id is not None:
            where.append("lot_id=?"); params.append(lot_id)
        if active_only:
            where.append("active=1")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY is_default DESC, id"
        return self.db.query(sql, tuple(params))

    def get(self, tariff_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM tariffs WHERE id=?", (tariff_id,))

    def active_for(self, lot_id: int, vehicle_category: str,
                   weekday: int, minutes_of_day: int) -> list[dict]:
        """Tarifas ativas aplicáveis à categoria e período. Ordenadas por
        prioridade: período específico > normal; categoria específica > genérica."""
        masks = ("430000", )  # placeholder; ignored
        rows = self.db.query(
            "SELECT * FROM tariffs WHERE lot_id=? AND active=1", (lot_id,))
        out = []
        for t in rows:
            cat_ok = t["vehicle_category"] in ("*", "", vehicle_category)
            wk = str(weekday)  # 0=segunda
            if t["days_mask"]:
                mask = f"{t['days_mask']}"
                if len(mask) >= 7 and mask[weekday] == "0":
                    continue
            start = self._hm(t["starts_at_str"])
            end = self._hm(t["ends_at_str"])
            if start <= minutes_of_day <= end:
                out.append(t)
        return out

    @staticmethod
    def _hm(value: str) -> int:
        try:
            h, m = (value or "00:00").split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return 0

    def rules(self, tariff_id: int) -> list[dict]:
        return self.db.query(
            "SELECT * FROM tariff_rules WHERE tariff_id=? ORDER BY minutes_from, sort",
            (tariff_id,))

    def add_rule(self, tariff_id: int, minutes_from: int, minutes_to: int | None,
                 rule_type: str, value: int, sort: int = 0) -> int:
        return self.db.execute(
            "INSERT INTO tariff_rules(tariff_id,minutes_from,minutes_to,rule_type,value,sort)"
            " VALUES(?,?,?,?,?,?)",
            (tariff_id, minutes_from, minutes_to, rule_type, value, sort))

    def clear_rules(self, tariff_id: int) -> None:
        self.db.execute("DELETE FROM tariff_rules WHERE tariff_id=?", (tariff_id,))

    def set_active(self, tariff_id: int, active: bool) -> None:
        self.db.execute("UPDATE tariffs SET active=? WHERE id=?", (1 if active else 0, tariff_id))

    def set_default(self, tariff_id: int, lot_id: int) -> None:
        self.db.execute("UPDATE tariffs SET is_default=0 WHERE lot_id=?", (lot_id,))
        self.db.execute("UPDATE tariffs SET is_default=1 WHERE id=?", (tariff_id,))


# ----------------------------------------------------------------------
# Caixa
# ----------------------------------------------------------------------
class CashRepo(Repo):
    def open_register(self, lot_id: int, operator_id: int, opening_value: int) -> int:
        return self.db.execute(
            "INSERT INTO cash_registers(lot_id,operator_id,opened_at,opening_value,status)"
            " VALUES(?,?,?,?,'ABERTO')",
            (lot_id, operator_id, _dt(), opening_value))

    def active(self, operator_id: int | None = None) -> dict | None:
        if operator_id is None:
            return self.db.query_one("SELECT * FROM cash_registers WHERE status='ABERTO'"
                                     " ORDER BY id DESC LIMIT 1")
        return self.db.query_one(
            "SELECT * FROM cash_registers WHERE status='ABERTO' AND operator_id=?"
            " ORDER BY id DESC LIMIT 1", (operator_id,))

    def get(self, register_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM cash_registers WHERE id=?", (register_id,))

    def current_balance(self, register_id: int) -> int:
        row = self.db.query_one(
            "SELECT opening_value + COALESCE((SELECT SUM(value) FROM cash_movements"
            " WHERE cash_register_id=?),0) balance FROM cash_registers WHERE id=?",
            (register_id, register_id))
        return int(row["balance"]) if row else 0

    def close(self, register_id: int, informed: int, justification: str = "") -> dict:
        expected = int(self.db.scalar(
            "SELECT COALESCE(SUM(value),0) FROM cash_movements WHERE cash_register_id=?", (register_id,)) or 0) \
            + int(self.db.scalar(
            "SELECT opening_value FROM cash_registers WHERE id=?", (register_id,)) or 0)
        diff = expected - informed
        self.db.execute(
            "UPDATE cash_registers SET closed_at=?, closing_expected=?,"
            " closing_informed=?, closing_difference=?, difference_justification=?,"
            " status='FECHADO' WHERE id=?",
            (_dt(), expected, informed, diff, justification, register_id))
        return {"expected": expected, "informed": informed, "difference": diff}

    def movements(self, register_id: int) -> list[dict]:
        return self.db.query(
            "SELECT cm.*, u.name operator_name FROM cash_movements cm"
            " LEFT JOIN users u ON u.id=cm.operator_id"
            " WHERE cm.cash_register_id=? ORDER BY cm.id", (register_id,))

    def add_movement(self, register_id: int, kind: str, value: int,
                     description: str, operator_id: int,
                     payment_id: int | None = None) -> int:
        return self.db.execute(
            "INSERT INTO cash_movements(cash_register_id,payment_id,kind,value,"
            " description,operator_id,created_at) VALUES(?,?,?,?,?,?,?)",
            (register_id, payment_id, kind, value, description, operator_id, _dt()))


# ----------------------------------------------------------------------
# Pagamentos
# ----------------------------------------------------------------------
class PaymentRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO payments({cols}, created_at) VALUES({ph}, ?)",
                               (*data.values(), _dt()))

    def get(self, payment_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM payments WHERE id=?", (payment_id,))

    def set_status(self, payment_id: int, status: str, received_value: int = 0,
                   received_at: str | None = None) -> None:
        received_at = received_at or _dt()
        self.db.execute(
            "UPDATE payments SET status=?, received_value=?, received_at=? WHERE id=?",
            (status, received_value, received_at, payment_id))


# ----------------------------------------------------------------------
# Mensalistas
# ----------------------------------------------------------------------
class MonthlyRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO monthly_customers({cols}, created_at)"
                               f" VALUES({ph}, ?)", (*data.values(), _dt()))

    def add_contract(self, monthly_customer_id: int, vehicle_id: int | None,
                     space_id: int | None, value: int = 0) -> int:
        return self.db.execute(
            "INSERT INTO monthly_contracts(monthly_customer_id,vehicle_id,space_id,start_at,value)"
            " VALUES(?,?,?,?,?)",
            (monthly_customer_id, vehicle_id, space_id, _dt(), value))

    def list(self, status: str = "") -> list[dict]:
        where = ["m.active=1"]
        params: list = []
        if status:
            where.append("m.status=?")
            params.append(status)
        sql = ("SELECT m.*, c.name customer_name, c.cpf, c.cnpj, c.phone,"
               " (SELECT COUNT(*) FROM monthly_payments mp WHERE"
               " mp.monthly_customer_id=m.id AND mp.status='PENDENTE'"
               " AND mp.due_date < date('now') ) overdue_count"
               " FROM monthly_customers m LEFT JOIN customers c ON c.id=m.customer_id"
               " WHERE " + " AND ".join(where))
        if status:
            return self.db.query(sql, tuple(params))
        sql += " ORDER BY m.id DESC"
        return self.db.query(sql)

    def get(self, monthly_id: int) -> dict | None:
        return self.db.query_one(
            "SELECT m.*, c.name customer_name, c.cpf, c.cnpj, c.phone, c.whatsapp, c.email"
            " FROM monthly_customers m LEFT JOIN customers c ON c.id=m.customer_id"
            " WHERE m.id=?", (monthly_id,))

    def set_status(self, monthly_id: int, status: str) -> None:
        self.db.execute("UPDATE monthly_customers SET status=? WHERE id=?", (status, monthly_id))

    def update(self, monthly_id: int, data: dict) -> None:
        """Atualiza dados do contrato mensal (valor, dia de cobrança, etc.)."""
        sets = ", ".join(f"{k}=?" for k in data)
        self.db.execute(f"UPDATE monthly_customers SET {sets} WHERE id=?",
                        (*data.values(), monthly_id))

    def delete(self, monthly_id: int) -> int:
        """Exclui o mensalista (exclusão lógica, mantém histórico fiscal).

        O mensalista some das telas (active=0), mas a linha permanece para
        os lançamentos de pagamento antigos continuarem apontando para o
        cadastro original — preserve a integridade fiscal e os relatórios.
        Encerra contratos vigentes e libera a vaga contratada.
        Retorna 1 em sucesso, 0 se o id não existir.
        """
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE parking_spaces SET state='LIVRE', monthly_contract_id=NULL"
                " WHERE monthly_contract_id IN (SELECT id FROM monthly_contracts"
                " WHERE monthly_customer_id=?)", (monthly_id,))
            cur.execute(
                "UPDATE monthly_contracts SET end_at=date('now','localtime')"
                " WHERE monthly_customer_id=? AND end_at IS NULL", (monthly_id,))
            cur.execute(
                "UPDATE monthly_customers SET status='INATIVO', active=0"
                " WHERE id=?", (monthly_id,))
        return cur.rowcount

    def payments(self, monthly_id: int, limit: int = 100) -> list[dict]:
        return self.db.query(
            "SELECT * FROM monthly_payments WHERE monthly_customer_id=?"
            " ORDER BY due_date DESC LIMIT ?", (monthly_id, limit))

    def create_payment(self, monthly_customer_id: int, due_date: str, reference: str,
                       value: int) -> int:
        return self.db.execute(
            "INSERT INTO monthly_payments(monthly_customer_id,due_date,reference,value,"
            " status,created_at) VALUES(?,?,?,?,'PENDENTE',?)",
            (monthly_customer_id, due_date, reference, value, _dt()))

    def mark_paid(self, monthly_payment_id: int, paid_value: int, payment_id: int | None) -> None:
        self.db.execute(
            "UPDATE monthly_payments SET status='PAGO', paid_at=?, paid_value=?, payment_id=?"
            " WHERE id=?", (_dt(), paid_value, payment_id, monthly_payment_id))

    def overdue(self) -> list[dict]:
        return self.db.query(
            "SELECT m.*, c.name customer_name, mp.id payment_id, mp.due_date, mp.reference,"
            " mp.value FROM monthly_payments mp"
            " JOIN monthly_customers m ON m.id=mp.monthly_customer_id"
            " JOIN customers c ON c.id=m.customer_id"
            " WHERE mp.status='PENDENTE' AND mp.due_date < date('now')"
            " ORDER BY mp.due_date")

    def expiring(self, days: int = 7) -> list[dict]:
        return self.db.query(
            "SELECT m.*, c.name customer_name, mp.due_date, mp.reference, mp.value"
            " FROM monthly_payments mp"
            " JOIN monthly_customers m ON m.id=mp.monthly_customer_id"
            " JOIN customers c ON c.id=m.customer_id"
            " WHERE mp.status='PENDENTE' AND mp.due_date >= date('now')"
            " AND mp.due_date <= date('now', ? ) ORDER BY mp.due_date",
            (f"+{days} day",))

    def active_count(self) -> int:
        return int(self.db.scalar(
            "SELECT COUNT(*) FROM monthly_customers WHERE status='ATIVO'") or 0)


# ----------------------------------------------------------------------
# Convênios, reservas, ocorrências
# ----------------------------------------------------------------------
class AgreementRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO agreements({cols}) VALUES({ph})",
                               (*data.values(),))

    def list(self, active_only: bool = False) -> list[dict]:
        if active_only:
            return self.db.query("SELECT * FROM agreements WHERE active=1 ORDER BY name")
        return self.db.query("SELECT * FROM agreements ORDER BY name")

    def get(self, agreement_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM agreements WHERE id=?", (agreement_id,))


class ReservationRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO reservations({cols}, created_at) VALUES({ph}, ?)",
                               (*data.values(), _dt()))

    def list(self, status: str = "") -> list[dict]:
        sql = ("SELECT r.*, c.name customer_name, v.plate, s.code space_code"
               " FROM reservations r"
               " LEFT JOIN customers c ON c.id=r.customer_id"
               " LEFT JOIN vehicles v ON v.id=r.vehicle_id"
               " LEFT JOIN parking_spaces s ON s.id=r.space_id")
        if status:
            sql += " WHERE r.status=?"
            return self.db.query(sql, (status,))
        sql += " ORDER BY r.start_at DESC"
        return self.db.query(sql)


class IncidentRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO incidents({cols}, created_at) VALUES({ph}, ?)",
                               (*data.values(), _dt()))

    def attach(self, incident_id: int, file_path: str, kind: str = "IMAGEM") -> int:
        return self.db.execute(
            "INSERT INTO incident_attachments(incident_id,file_path,kind) VALUES(?,?,?)",
            (incident_id, file_path, kind))

    def list(self, limit: int = 100) -> list[dict]:
        return self.db.query(
            "SELECT i.*, u.name operator_name FROM incidents i"
            " LEFT JOIN users u ON u.id=i.operator_id ORDER BY i.id DESC LIMIT ?",
            (limit,))


# ----------------------------------------------------------------------
# Notificações, backups, dispositivos
# ----------------------------------------------------------------------
class NotificationRepo(Repo):
    def push(self, level: str, code: str, title: str, message: str = "",
             lot_id: int | None = None) -> int:
        return self.db.execute(
            "INSERT INTO notifications(lot_id,level,code,title,message,created_at)"
            " VALUES(?,?,?,?,?,?)", (lot_id, level, code, title, message, _dt()))

    def list(self, limit: int = 50, unread_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM notifications"
        if unread_only:
            sql += " WHERE read_at IS NULL"
        sql += " ORDER BY id DESC LIMIT ?"
        return self.db.query(sql, (limit,))

    def mark_all_read(self) -> None:
        self.db.execute("UPDATE notifications SET read_at=? WHERE read_at IS NULL", (_dt(),))

    def unread_count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM notifications WHERE read_at IS NULL") or 0)


class BackupRepo(Repo):
    def record(self, path: str, size: int, kind: str, status: str = "OK",
               note: str = "") -> int:
        return self.db.execute(
            "INSERT INTO backups(path,size,kind,status,note,created_at) VALUES(?,?,?,?,?,?)",
            (path, size, kind, status, note, _dt()))

    def list(self, limit: int = 30) -> list[dict]:
        return self.db.query("SELECT * FROM backups ORDER BY id DESC LIMIT ?", (limit,))


class DeviceRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO devices({cols}) VALUES({ph})", (*data.values(),))

    def list(self, kind: str = "") -> list[dict]:
        if kind:
            return self.db.query("SELECT * FROM devices WHERE kind=? ORDER BY name", (kind,))
        return self.db.query("SELECT * FROM devices ORDER BY kind, name")

    def set_status(self, device_id: int, status: str) -> None:
        self.db.execute("UPDATE devices SET status=?, last_seen=? WHERE id=?",
                        (status, _dt(), device_id))


class CameraRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO cameras({cols}) VALUES({ph})", (*data.values(),))

    def list(self) -> list[dict]:
        return self.db.query("SELECT * FROM cameras ORDER BY name")

    def set_status(self, camera_id: int, status: str) -> None:
        self.db.execute("UPDATE cameras SET status=?, last_event=? WHERE id=?",
                        (status, _dt(), camera_id))

    def add_event(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO access_events({cols}, event_at)"
                               f" VALUES({ph}, ?)", (*data.values(), _dt()))

    def events(self, limit: int = 50) -> list[dict]:
        return self.db.query(
            "SELECT ae.*, c.name camera_name FROM access_events ae"
            " LEFT JOIN cameras c ON c.id=ae.camera_id"
            " ORDER BY ae.id DESC LIMIT ?", (limit,))

    def latest_event(self, camera_id: int) -> dict | None:
        return self.db.query_one(
            "SELECT * FROM access_events WHERE camera_id=? ORDER BY id DESC LIMIT 1",
            (camera_id,))