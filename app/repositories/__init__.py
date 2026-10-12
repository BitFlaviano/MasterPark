"""Repositórios (acesso a dados). SQL parametrizado, banco agnóstico."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.core.db import Database
from app.domain.models import CurrentUser, parse_iso, utcnow_iso


def _dt() -> str:
    return utcnow_iso()


class Repo:
    def __init__(self, db: Database):
        self.db = db


# ----------------------------------------------------------------------
# Configurações
# ----------------------------------------------------------------------
class SettingRepo(Repo):
    def get(self, key: str, default: str = "") -> str:
        row = self.db.query_one("SELECT value FROM system_settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        self.db.execute("INSERT INTO system_settings(key,value) VALUES(?,?)"
                       " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, value))

    def all(self) -> dict:
        return {r["key"]: r["value"] for r in self.db.query("SELECT * FROM system_settings")}


class CompanyRepo(Repo):
    def list(self) -> list[dict]:
        return self.db.query("SELECT * FROM companies ORDER BY id")

    def first(self) -> dict | None:
        return self.db.query_one("SELECT * FROM companies ORDER BY id LIMIT 1")

    def upsert(self, data: dict) -> int:
        existing = self.first()
        if existing:
            sets = ", ".join(f"{k}=?" for k in data)
            self.db.execute(f"UPDATE companies SET {sets}, updated_at=? WHERE id=?",
                            (*data.values(), _dt(), existing["id"]))
            return existing["id"]
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        return self.db.execute(
            f"INSERT INTO companies({cols}, created_at) VALUES({placeholders}, ?)",
            (*data.values(), _dt()))


class LotRepo(Repo):
    def first(self) -> dict | None:
        return self.db.query_one("SELECT * FROM parking_lots ORDER BY id LIMIT 1")

    def upsert(self, data: dict) -> int:
        existing = self.first()
        if existing:
            sets = ", ".join(f"{k}=?" for k in data)
            self.db.execute(f"UPDATE parking_lots SET {sets} WHERE id=?", (*data.values(), existing["id"]))
            return existing["id"]
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        return self.db.execute(
            f"INSERT INTO parking_lots({cols}, created_at) VALUES({placeholders}, ?)",
            (*data.values(), _dt()))


class SectorRepo(Repo):
    def list(self, lot_id: int | None = None) -> list[dict]:
        if lot_id is None:
            return self.db.query("SELECT * FROM parking_sectors ORDER BY sort, id")
        return self.db.query("SELECT * FROM parking_sectors WHERE lot_id=? ORDER BY sort, id",
                             (lot_id,))

    def create(self, lot_id: int, name: str, color: str = "#4C6FFF",
               floor: int = 1) -> int:
        maxsort = self.db.scalar(
            "SELECT COALESCE(MAX(sort),0) FROM parking_sectors WHERE lot_id=?", (lot_id,)) or 0
        return self.db.execute(
            "INSERT INTO parking_sectors(lot_id,name,color,floor,sort) VALUES(?,?,?,?,?)",
            (lot_id, name, color, floor, maxsort + 1))

    def count_spaces_by_state(self, sector_id: int) -> dict:
        res = {"LIVRE": 0, "OCUPADA": 0, "RESERVADA": 0, "BLOQUEADA": 0,
               "MANUTENCAO": 0}
        for r in self.db.query(
                "SELECT state, COUNT(*) c FROM parking_spaces"
                " WHERE sector_id=? AND active=1 GROUP BY state",
                (sector_id,)):
            if r["state"] in res:
                res[r["state"]] = r["c"]
        return res

    def rename(self, sector_id: int, name: str) -> int:
        """Renomeia o setor preservando o resto dos dados."""
        name = (name or "").strip()
        if not name:
            return 0
        return self.db.execute_rowcount(
            "UPDATE parking_sectors SET name=? WHERE id=?", (name, sector_id))

    def update(self, sector_id: int, data: dict) -> int:
        """Atualização genérica de atributos do setor (cor, andar, nome)."""
        allowed = {"name", "color", "floor", "sort"}
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return 0
        sets = ", ".join(f"{k}=?" for k in fields)
        return self.db.execute_rowcount(
            f"UPDATE parking_sectors SET {sets} WHERE id=?",
            (*fields.values(), sector_id))

    def delete(self, sector_id: int) -> int:
        """Exclui o setor e desativa as vagas dele.

        Bloqueia apenas se houver uso ATUAL (vaga ocupada/reservada/manutencao,
        ticket aberto, reserva ativa, contrato mensal vigente). Historico nao
        bloqueia: as vagas ficam com active=0 e sector_id=NULL, preservando o
        codigo nos tickets antigos sem impedir a exclusao do setor.
        Retorna 0 e deixa tudo intacto se for necessario bloquear.
        """
        spaces = self.db.query(
            "SELECT * FROM parking_spaces WHERE sector_id=? AND active=1",
            (sector_id,))
        reasons: list[str] = []
        for sp in spaces:
            reasons.extend(SpaceRepo(self.db).delete_blockers(sp["id"]))
        if reasons:
            return 0
        with self.db.transaction() as cur:
            cur.execute(
                "UPDATE parking_spaces SET active=0, state='LIVRE',"
                " monthly_contract_id=NULL WHERE sector_id=? AND active=1",
                (sector_id,))
            # vagas ja desativadas continuam apontando para o setor e
            # quebrariam a FK; solta o vinculo de todas.
            cur.execute(
                "UPDATE parking_spaces SET sector_id=NULL WHERE sector_id=?",
                (sector_id,))
            cur.execute("DELETE FROM parking_sectors WHERE id=?", (sector_id,))
        return 1


class SpaceRepo(Repo):
    """Vagas do estacionamento.

    Exclusao e logica: `delete()` marca a vaga como active=0 em vez de apagar a
    linha, porque o PRAGMA foreign_keys=ON impede apagar linhas referenciadas
    por tickets e o historico precisa preservar o codigo da vaga. Vagas com
    active=0 somem do mapa e das listas, mas `get()` ainda as encontra.
    """

    def count_by_state(self, lot_id: int | None = None) -> dict:
        sql = "SELECT state, COUNT(*) c FROM parking_spaces WHERE active=1"
        params: tuple = ()
        if lot_id is not None:
            sql += " AND lot_id=?"
            params = (lot_id,)
        sql += " GROUP BY state"
        result = {"LIVRE": 0, "OCUPADA": 0, "RESERVADA": 0, "BLOQUEADA": 0, "MANUTENCAO": 0}
        for r in self.db.query(sql, params):
            if r["state"] in result:
                result[r["state"]] = r["c"]
        result["TOTAL"] = sum(result.values())
        return result

    def total(self, lot_id: int | None = None) -> int:
        if lot_id is None:
            return int(self.db.scalar("SELECT COUNT(*) FROM parking_spaces WHERE active=1") or 0)
        return int(self.db.scalar("SELECT COUNT(*) FROM parking_spaces WHERE lot_id=? AND active=1", (lot_id,)) or 0)

    def list(self, lot_id: int | None = None) -> list[dict]:
        if lot_id is None:
            return self.db.query(
                "SELECT s.*, sec.name sector_name FROM parking_spaces s"
                " LEFT JOIN parking_sectors sec ON sec.id=s.sector_id"
                " WHERE s.active=1 ORDER BY s.sector_id, s.code")
        return self.db.query(
            "SELECT s.*, sec.name sector_name FROM parking_spaces s"
            " LEFT JOIN parking_sectors sec ON sec.id=s.sector_id"
            " WHERE s.lot_id=? AND s.active=1 ORDER BY s.sector_id, s.code", (lot_id,))

    def get(self, space_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM parking_spaces WHERE id=?", (space_id,))

    def create_many(self, lot_id: int, sector_id: int | None, codes: list[str],
                    space_type: str = "CARRO") -> int:
        """Cria varias vagas. Codigo existente e inativo volta a ativa.

        O UNIQUE(lot_id, code) impede reinserir um codigo que foi excluido
        logicamente, entao esses casos sao reativados em vez de ignorados.
        """
        created = 0
        with self.db.transaction() as cur:
            for code in codes:
                code = (code or "").strip()
                if not code:
                    continue
                existing = cur.execute(
                    "SELECT id, active FROM parking_spaces WHERE lot_id=? AND code=?",
                    (lot_id, code)).fetchone()
                if existing is None:
                    cur.execute(
                        "INSERT INTO parking_spaces"
                        "(lot_id,sector_id,code,space_type,state,notes,active)"
                        " VALUES(?,?,?,?,'LIVRE','',1)",
                        (lot_id, sector_id, code, space_type))
                    created += 1
                elif not existing["active"]:
                    cur.execute(
                        "UPDATE parking_spaces SET active=1, sector_id=?,"
                        " state='LIVRE', monthly_contract_id=NULL WHERE id=?",
                        (sector_id, existing["id"]))
                    created += 1
        return created

    def set_state(self, space_id: int, state: str, monthly_contract_id: int | None = None) -> None:
        self.db.execute(
            "UPDATE parking_spaces SET state=?,"
            " monthly_contract_id=COALESCE(?, monthly_contract_id) WHERE id=?",
            (state, monthly_contract_id, space_id))

    def set_bulk_state(self, space_id: int, state: str) -> None:
        self.db.execute("UPDATE parking_spaces SET state=? WHERE id=?", (state, space_id))

    def update(self, space_id: int, data: dict) -> int:
        """Atualização genérica de atributos da vaga (código, tipo, estado)."""
        allowed = {"code", "space_type", "state", "notes", "sector_id"}
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return 0
        sets = ", ".join(f"{k}=?" for k in fields)
        return self.db.execute_rowcount(
            f"UPDATE parking_spaces SET {sets} WHERE id=?",
            (*fields.values(), space_id))

    def delete_blockers(self, space_id: int) -> list[str]:
        """Motivos que impedem excluir a vaga (lista vazia = pode excluir).

        Considera apenas uso ATUAL. Historico (ticket finalizado, reserva
        encerrada, contrato mensal vencido) nao bloqueia: a linha e preservada
        com active=0, o que mantem o codigo correto nos relatorios antigos.
        """
        reasons: list[str] = []
        space = self.get(space_id)
        if not space:
            return reasons
        if space["state"] in ("OCUPADA", "RESERVADA", "MANUTENCAO"):
            reasons.append("a vaga esta em uso ou em manutencao")
        if self.db.scalar(
                "SELECT COUNT(*) FROM tickets t WHERE t.parking_space_id=?"
                " AND t.status='ATIVO'", (space_id,)) or 0:
            reasons.append("existe um ticket aberto nesta vaga")
        if self.db.scalar(
                "SELECT COUNT(*) FROM reservations r WHERE r.space_id=?"
                " AND r.status IN ('PENDENTE','CONFIRMADA','ATIVA')", (space_id,)) or 0:
            reasons.append("existe uma reserva ativa nesta vaga")
        if self.db.scalar(
                "SELECT COUNT(*) FROM monthly_contracts m WHERE m.space_id=?"
                " AND (m.end_at IS NULL OR m.end_at >= date('now'))", (space_id,)) or 0:
            reasons.append("a vaga esta vinculada a um contrato mensal vigente")
        return reasons

    def delete(self, space_id: int) -> int:
        """Exclui a vaga logicamente (active=0).

        Retorna 0 e nao altera nada quando `delete_blockers()` encontra uso
        atual. Caso contrario a linha permanece no banco para os tickets e
        reservas antigos continuarem referenciando o codigo da vaga.
        """
        if not self.get(space_id):
            return 0
        if self.delete_blockers(space_id):
            return 0
        return self.db.execute_rowcount(
            "UPDATE parking_spaces SET active=0, state='LIVRE',"
            " monthly_contract_id=NULL WHERE id=?", (space_id,))

    def find_free(self, lot_id: int, space_type: str | None = None) -> dict | None:
        sql = "SELECT * FROM parking_spaces WHERE lot_id=? AND state='LIVRE' AND active=1"
        params: list = [lot_id]
        if space_type:
            sql += " AND space_type=?"
            params.append(space_type)
        sql += " ORDER BY sector_id, code LIMIT 1"
        return self.db.query_one(sql, tuple(params))

    def smart_find(self, lot_id: int, vehicle_category: str) -> dict | None:
        """Escolhe vaga compatível com a categoria do veículo."""
        mapping = {
            "MOTO": "MOTO",
            "ELETRICO": "ELETRICO",
            "UTILITARIO": "CARRO",
            "PICKUP": "CARRO",
        }
        stype = mapping.get(vehicle_category)
        candidates = [stype, None]
        for t in candidates:
            space = self.find_free(lot_id, t)
            if space:
                return space
        # qualquer livre
        for r in self.db.query(
                "SELECT * FROM parking_spaces WHERE lot_id=? AND state='LIVRE' AND active=1"
                " ORDER BY sector_id, code LIMIT 5", (lot_id,)):
            return r
        return None


# ----------------------------------------------------------------------
# Usuários e permissões
# ----------------------------------------------------------------------
class UserRepo(Repo):
    def create(self, username: str, name: str, password_hash: str, salt: str,
               role_code: str, terminal: str = "") -> int:
        return self.db.execute(
            "INSERT INTO users(username,name,password_hash,salt,role_code,terminal,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (username, name, password_hash, salt, role_code, terminal, _dt()))

    def get_by_username(self, username: str) -> dict | None:
        return self.db.query_one("SELECT * FROM users WHERE username=?",
                                 (username.strip().lower(),))

    def get(self, user_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM users WHERE id=?", (user_id,))

    def list(self) -> list[dict]:
        return self.db.query("SELECT u.*, r.name role_name FROM users u"
                             " LEFT JOIN roles r ON r.code=u.role_code ORDER BY u.id")

    def update_profile(self, user_id: int, name: str | None = None,
                       role_code: str | None = None, is_active: int | None = None,
                       must_change: int | None = None) -> None:
        sets, params = [], []
        if name is not None:
            sets.append("name=?"); params.append(name)
        if role_code is not None:
            sets.append("role_code=?"); params.append(role_code)
        if is_active is not None:
            sets.append("is_active=?"); params.append(is_active)
        if must_change is not None:
            sets.append("must_change_password=?"); params.append(must_change)
        if not sets:
            return
        params.append(user_id)
        self.db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", tuple(params))

    def set_password(self, user_id: int, password_hash: str, salt: str) -> None:
        self.db.execute(
            "UPDATE users SET password_hash=?, salt=?, must_change_password=0,"
            " failed_attempts=0, locked_until=NULL WHERE id=?",
            (password_hash, salt, user_id))

    def register_failure(self, user_id: int, max_failures: int,
                         lock_minutes: int = 15) -> bool:
        self.db.execute("UPDATE users SET failed_attempts=failed_attempts+1 WHERE id=?",
                        (user_id,))
        row = self.db.query_one("SELECT failed_attempts FROM users WHERE id=?", (user_id,))
        if row and row["failed_attempts"] >= max_failures:
            until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
            self.db.execute("UPDATE users SET locked_until=? WHERE id=?",
                            (until.strftime("%Y-%m-%dT%H:%M:%SZ"), user_id))
            return True
        return False

    def lock_expired(self, row: dict) -> bool:
        """True quando há registro de bloqueio, mas o prazo já passou."""
        locked = row.get("locked_until")
        if not locked:
            return False
        try:
            return parse_iso(locked) <= datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return True

    def clear_lock(self, user_id: int) -> None:
        self.db.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?",
                        (user_id,))

    def reset_failures(self, user_id: int) -> None:
        self.db.execute("UPDATE users SET failed_attempts=0, locked_until=NULL, last_login_at=?"
                        " WHERE id=?", (_dt(), user_id))

    def permissions(self, user_id: int) -> set[str]:
        row = self.db.query_one("SELECT role_code FROM users WHERE id=?", (user_id,))
        perms: set[str] = set()
        if row:
            perms = set(p["permission_code"] for p in self.db.query(
                "SELECT permission_code FROM role_permissions WHERE role_code=?", (row["role_code"],)))
        overrides = self.db.query(
            "SELECT permission_code, allowed FROM user_permissions WHERE user_id=?",
            (user_id,))
        for o in overrides:
            if o["allowed"]:
                perms.add(o["permission_code"])
            else:
                perms.discard(o["permission_code"])
        return perms

    def set_override(self, user_id: int, permission: str, allowed: bool) -> None:
        if allowed:
            self.db.execute("INSERT INTO user_permissions(user_id,permission_code,allowed)"
                           " VALUES(?,?,1) ON CONFLICT(user_id,permission_code)"
                           " DO UPDATE SET allowed=1",
                           (user_id, permission))
        else:
            self.db.execute("INSERT INTO user_permissions(user_id,permission_code,allowed)"
                           " VALUES(?,?,0) ON CONFLICT(user_id,permission_code)"
                           " DO UPDATE SET allowed=0",
                           (user_id, permission))

    def to_current(self, row: dict) -> CurrentUser:
        row = dict(row)
        perms = self.permissions(row["id"])
        return CurrentUser(id=row["id"], username=row["username"], name=row["name"],
                           role=row["role_code"] or "", terminal=row.get("terminal") or "",
                           permissions=perms)


# ----------------------------------------------------------------------
# Clientes e veículos
# ----------------------------------------------------------------------
class CustomerRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO customers({cols}, created_at) VALUES({ph}, ?)",
                               (*data.values(), _dt()))

    def update(self, customer_id: int, data: dict) -> None:
        sets = ", ".join(f"{k}=?" for k in data)
        self.db.execute(f"UPDATE customers SET {sets}, updated_at=? WHERE id=?",
                        (*data.values(), _dt(), customer_id))

    def get(self, customer_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM customers WHERE id=?", (customer_id,))

    def delete(self, customer_id: int) -> int:
        """Exclui o cliente (exclusão lógica, preserva o histórico).

        O cliente some das telas (active=0) mas a linha permanece para
        os veículos, mensalistas e tickets antigos continuarem apontando
        para o cadastro original — preserve a integridade referencial e o
        registro fiscal.

        Bloqueia (retorna 0, nada é alterado) apenas em uso ATUAL:
        ticket em aberto, mensalidade em aberto ou mensalista ativo.
        """
        used = self.db.scalar(
            "SELECT COUNT(*) FROM customers c WHERE c.id=? AND"
            " (EXISTS(SELECT 1 FROM tickets t WHERE t.customer_id=c.id"
            "   AND t.status='ATIVO')"
            " OR EXISTS(SELECT 1 FROM monthly_customers m WHERE m.customer_id=c.id"
            "   AND m.active=1)"
            " OR EXISTS(SELECT 1 FROM monthly_payments mp"
            "   JOIN monthly_customers m2 ON m2.id=mp.monthly_customer_id"
            "   WHERE m2.customer_id=c.id AND mp.status='PENDENTE'))",
            (customer_id,)) or 0
        if used:
            return 0
        return self.db.execute_rowcount(
            "UPDATE customers SET active=0, updated_at=? WHERE id=?",
            (_dt(), customer_id))

    def search(self, term: str, limit: int = 50) -> list[dict]:
        like = f"%{term}%"
        return self.db.query(
            "SELECT * FROM customers WHERE active=1 AND (name LIKE ? OR cpf LIKE ?"
            " OR cnpj LIKE ? OR phone LIKE ? OR email LIKE ?)"
            " ORDER BY name LIMIT ?",
            (like, like, like, like, like, limit))

    def list(self, limit: int = 200, offset: int = 0) -> list[dict]:
        return self.db.query(
            "SELECT * FROM customers WHERE active=1 ORDER BY name LIMIT ? OFFSET ?",
            (limit, offset))

    def count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM customers WHERE active=1") or 0)


class VehicleRepo(Repo):
    def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        ph = ", ".join("?" for _ in data)
        return self.db.execute(f"INSERT INTO vehicles({cols}) VALUES({ph})",
                               (*data.values(),))

    def update(self, vehicle_id: int, data: dict) -> None:
        sets = ", ".join(f"{k}=?" for k in data)
        self.db.execute(f"UPDATE vehicles SET {sets} WHERE id=?", (*data.values(), vehicle_id))

    def delete(self, vehicle_id: int) -> int:
        """Exclui o veículo, desde que não possua vínculos ativos.

        Bloqueia (retorna 0, nada é alterado) quando o veículo possui
        histórico de tickets, contratos mensais ou vínculo com mensalista
        — preserva a integridade referencial e o registro fiscal.
        """
        used = self.db.scalar(
            "SELECT COUNT(*) FROM vehicles v WHERE v.id=? AND"
            " (EXISTS(SELECT 1 FROM tickets t WHERE t.vehicle_id=v.id)"
            " OR EXISTS(SELECT 1 FROM monthly_customers m WHERE m.vehicle_id=v.id)"
            " OR EXISTS(SELECT 1 FROM monthly_contracts mc WHERE mc.vehicle_id=v.id))",
            (vehicle_id,)) or 0
        if used:
            return 0
        return self.db.execute_rowcount("DELETE FROM vehicles WHERE id=?", (vehicle_id,))

    def get(self, vehicle_id: int) -> dict | None:
        return self.db.query_one("SELECT * FROM vehicles WHERE id=?", (vehicle_id,))

    def by_plate(self, plate: str) -> dict | None:
        return self.db.query_one("SELECT * FROM vehicles WHERE plate=?", (plate,))

    def by_customer(self, customer_id: int) -> list[dict]:
        return self.db.query("SELECT * FROM vehicles WHERE customer_id=? ORDER BY plate",
                             (customer_id,))

    def list(self, plate: str = "", limit: int = 100) -> list[dict]:
        if plate:
            return self.db.query(
                "SELECT v.*, c.name customer_name FROM vehicles v"
                " LEFT JOIN customers c ON c.id=v.customer_id"
                " WHERE v.plate LIKE ? ORDER BY v.plate LIMIT ?", (f"%{plate}%", limit))
        return self.db.query(
            "SELECT v.*, c.name customer_name FROM vehicles v"
            " LEFT JOIN customers c ON c.id=v.customer_id ORDER BY v.plate LIMIT ?",
            (limit,))

    def history(self, plate: str, limit: int = 30) -> list[dict]:
        return self.db.query(
            "SELECT t.number, t.entry_at, t.exit_at, t.base_value, t.discount_value,"
            " t.final_value, t.status FROM tickets t WHERE t.plate=? ORDER BY t.id DESC LIMIT ?",
            (plate.upper(), limit))