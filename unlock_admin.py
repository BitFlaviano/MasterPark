"""Desbloqueia a conta admin apos excesso de tentativas.

Reutiliza PasswordService do proprio app (PBKDF2-SHA256, 210k iter.)
para NUNCA divergir do formato real: mesmo salt hex e mesmo iterador.
"""
from __future__ import annotations

import os
import sqlite3

from app.core.config import get_db_path
from app.core.security import PasswordService


def main() -> int:
    conn = sqlite3.connect(get_db_path())
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, salt, failed_attempts, locked_until, is_active"
            " FROM users WHERE username='admin'").fetchone()
        if not row:
            print("ERRO: nao existe usuario admin.")
            return 1
        uid, username, _, _, fa, locked, active = row

        hash_hex, salt = PasswordService.hash_password("admin123")
        assert PasswordService.verify_password("admin123", hash_hex, salt)

        conn.execute(
            "UPDATE users SET password_hash=?, salt=?, failed_attempts=0,"
            " locked_until=NULL, is_active=1, must_change_password=0 WHERE id=?",
            (hash_hex, salt, uid))
        conn.commit()

        print("OK: conta admin desbloqueada.")
        print(f"    username: {username} (id={uid})")
        print(f"    senha:    admin123")
        print(f"    attempts: {fa} -> 0 | locked_until: {locked} -> NULL")
        print(f"    hash novo: {hash_hex[:10]}... (validado com verify_password)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
