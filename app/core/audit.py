"""Serviço de auditoria: registra operações relevantes de forma imutável."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AuditService:
    def __init__(self, db):
        self._db = db

    def log(self, *, action: str, user_id: int | None = None, username: str = "",
            terminal: str = "", ip: str = "", entity: str = "",
            entity_id: Any = None, old_value: Any = None, new_value: Any = None,
            reason: str = "") -> None:
        try:
            self._db.execute(
                "INSERT INTO audit_logs(user_id, username, terminal, ip, action,"
                " entity, entity_id, old_value, new_value, reason, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (user_id, username, terminal, ip, action, entity,
                 str(entity_id) if entity_id is not None else "",
                 str(old_value) if old_value is not None else "",
                 str(new_value) if new_value is not None else "",
                 reason, _utcnow()))
        except Exception:
            # Auditoria nunca pode derrubar a operação principal.
            pass

    def add(self, user, action, entity="", entity_id=None,
            old=None, new=None, reason=""):
        return self.log(action=action, user_id=user.id if user else None,
                        username=user.username if user else "",
                        terminal=user.terminal if user else "",
                        entity=entity, entity_id=entity_id,
                        old_value=old, new_value=new, reason=reason)

    def list(self, limit: int = 500, action: str = "", user: str = "",
             created_from: str = "", created_to: str = "") -> list[dict]:
        sql = ("SELECT * FROM audit_logs WHERE 1=1")
        params: list[Any] = []
        if action:
            sql += " AND action = ?"
            params.append(action)
        if user:
            sql += " AND username LIKE ?"
            params.append(f"%{user}%")
        if created_from:
            sql += " AND created_at >= ?"
            params.append(created_from)
        if created_to:
            sql += " AND created_at <= ?"
            params.append(created_to)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self._db.query(sql, tuple(params))