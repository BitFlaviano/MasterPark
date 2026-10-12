"""Segurança: hash de senha, validação, bloqueio de conta e utilitários."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid

PBKDF2_ITERATIONS = 210_000


class PasswordService:
    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        salt = salt or secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt), PBKDF2_ITERATIONS)
        return dk.hex(), salt

    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        dk, _ = PasswordService.hash_password(password, salt)
        return hmac.compare_digest(dk, password_hash)


def generate_token() -> str:
    return uuid.uuid4().hex


def new_ticket_number() -> str:
    return f"{secrets.randbelow(10)}{secrets.randbelow(10)}" + uuid.uuid4().hex[:6].upper()


def hash_fingerprint(parts: str) -> str:
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:32]


def secure_rand(n: int = 6) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(n))


def sanitize_plate(plate: str) -> str:
    return "".join(ch for ch in (plate or "").upper() if ch.isalnum())[:7]