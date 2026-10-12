"""Serviço de licenciamento MasterPark.

Mecânica: o fabricante gera a licença (payload JSON + assinatura RSA-SHA256).
A aplicação valida a assinatura com a chave pública embutida. A ativação
associa a licença à instalação (machine id). Ativação offline acontece por
código de ativação assinado fornecido pelo fabricante.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.audit import AuditService
from app.core.config import DEFAULT_PUBLIC_KEY
from app.repositories.operation import Repo

PUBLIC_KEY = DEFAULT_PUBLIC_KEY  # definido pelo gerador de licenças


class LicenseError(Exception):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LicenseService:
    def __init__(self, db):
        self._db = db
        self._audit = AuditService(db)

    # ------------------------------------------------------------------
    # Criptografia
    # ------------------------------------------------------------------
    def _rsa_verify(self, payload: bytes, signature_b64: str) -> bool:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        import cryptography.exceptions
        try:
            pub = serialization.load_pem_public_key(PUBLIC_KEY.strip().encode("utf-8"))
            sig = base64.b64decode(signature_b64)
            pub.verify(sig, payload,
                       padding.PKCS1v15(),
                       hashes.SHA256())
            return True
        except (cryptography.exceptions.InvalidSignature, Exception):
            return False

    @staticmethod
    def _canonical_json(obj: dict) -> bytes:
        return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8")

    def _normalize_key(self, key: str) -> str:
        return "".join(ch for ch in (key or "").upper() if ch.isalnum() or ch == "-")

    # ------------------------------------------------------------------
    # Validação de licença assinada
    # ------------------------------------------------------------------
    def validate_license_file(self, raw: str) -> dict:
        """Valida um arquivo de licença texto (payload JSON + assinatura)."""
        try:
            data = json.loads(raw)
            payload = data.get("payload", {})
            signature = data.get("signature", "")
        except Exception as exc:
            raise LicenseError("Arquivo de licença inválido.") from exc
        if not signature or not payload:
            raise LicenseError("Licença incompleta (sem assinatura ou payload).")
        payload_bytes = self._canonical_json(payload)
        if not self._rsa_verify(payload_bytes, signature):
            raise LicenseError("Assinatura da licença inválida. Licença adulterada.")
        if payload.get("product", "").upper() != "MASTERPARK":
            raise LicenseError("Produto da licença não confere.")
        self._check_dates(payload)
        return payload

    @staticmethod
    def _check_dates(payload: dict) -> None:
        if payload.get("lifetime"):
            return  # licença vitalícia não expira
        try:
            exp = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                raise LicenseError("Licença expirada.")
        except KeyError:
            raise LicenseError("Licença sem data de expiração (e não é vitalícia).")
        except ValueError:
            raise LicenseError("Data de expiração inválida.")

    # ------------------------------------------------------------------
    # Ativação
    # ------------------------------------------------------------------
    def activate(self, raw_license: str, hw_anchor: str | None = None,
                 mode: str = "ONLINE") -> dict:
        """Persiste e ativa uma licença válida nesta instalação."""
        payload = self.validate_license_file(raw_license)
        key = self._normalize_key(payload.get("license_key", ""))
        anchor = (hw_anchor or hashlib.sha256(
            (key + "|masterpark").encode()).hexdigest()[:16])

        existing = self._db.query_one(
            "SELECT * FROM licenses WHERE license_key=?", (key,))
        if existing:
            if existing["status"] == "ATIVA":
                return dict(existing, already_active=True)
            license_id = existing["id"]
            self._db.execute(
                "UPDATE licenses SET customer_name=?, cnpj=?, product=?, version=?,"
                " plan=?, activated_at=?, expires_at=?, lifetime=?, duracao=?,"
                " terminals=?, spaces=?, features=?, installation_id=?, hw_anchor=?,"
                " signature=?, status='ATIVA' WHERE id=?",
                _lic_cols(payload, anchor, raw_license, license_id))
        else:
            license_id = self._db.execute(
                "INSERT INTO licenses(license_key, customer_name, cnpj, product,"
                " version, plan, activated_at, expires_at, lifetime, duracao,"
                " terminals, spaces, features, installation_id, hw_anchor,"
                " signature, status, created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'ATIVA',?)",
                _lic_vals(payload, anchor, raw_license))
        self._db.execute(
            "INSERT INTO license_activations(license_id,installation_id,activated_at,"
            " machine_name,mode) VALUES(?,?,?,?,?)",
            (license_id, anchor, utcnow(), "terminal", mode))
        return self.current()

    def activate_offline(self, license_key: str, activation_code: str,
                         hw_anchor: str | None = None) -> dict:
        """Ativa uma licença offline: o fabricante assina o código de ativação
        correspondente a chave+instalação."""
        key = self._normalize_key(license_key)
        anchor = hw_anchor or hash_anchor(key)
        canonical = json.dumps({"activation": key, "hw": anchor},
                               sort_keys=True).encode()
        if not self._rsa_verify(canonical, activation_code):
            raise LicenseError("Código de ativação inválido para esta instalação.")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS licenses_files(license_key TEXT PRIMARY KEY, raw TEXT)")
        raw_license = self._db.scalar(
            "SELECT raw FROM licenses_files WHERE license_key=?", (key,))
        if not raw_license:
            raise LicenseError("Licença não encontrada localmente."
                               " Obtenha o arquivo de licença do fabricante.")
        return self.activate(raw_license, hw_anchor=anchor, mode="OFFLINE")

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------
    def current(self) -> dict | None:
        row = self._db.query_one(
            "SELECT * FROM licenses ORDER BY id DESC LIMIT 1")
        if not row:
            return None
        row["lifetime"] = bool(row.get("lifetime"))
        row["days_left"] = None if row["lifetime"] else (
            self.days_left(row["expires_at"]) if row["expires_at"] else None)
        row["expired"] = False if row["lifetime"] else (
            bool(row["expires_at"]) and self.days_left(row["expires_at"]) <= 0)
        return row

    @staticmethod
    def describe(cur: dict | None) -> str:
        """Descrição amigável da licença (para telas)."""
        if not cur:
            return "Sem licença ativa."
        plan = cur.get("plan") or "-"
        key = cur.get("license_key") or "-"
        if cur.get("lifetime"):
            duracao = cur.get("duracao") or "VITALICIA"
            return f"{plan} • {key} • {duracao} — nunca expira"
        exp = (cur.get("expires_at") or "")[:10]
        days = cur.get("days_left")
        tail = f"vence em {exp}" if exp else ""
        if days is not None:
            tail += f" • {days} dia(s) restante(s)"
        return f"{plan} • {key} • {tail}".strip(" •")

    @staticmethod
    def days_left(expires_at: str | None) -> int | None:
        if not expires_at:
            return None
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return (exp - datetime.now(timezone.utc)).days
        except Exception:
            return None

    @staticmethod
    def is_lifetime(payload_or_row: dict) -> bool:
        return bool(payload_or_row.get("lifetime"))

    def features(self) -> list[str]:
        cur = self.current()
        if not cur:
            return []
        try:
            return json.loads(cur.get("features") or "[]")
        except Exception:
            return []

    def plan(self) -> str:
        cur = self.current()
        return (cur or {}).get("plan", "")

    def has_feature(self, feature: str) -> bool:
        return feature in self.features()

    def verify_expiry_notifications(self) -> list[str]:
        msgs = []
        cur = self.current()
        if not cur or not cur.get("expires_at"):
            return msgs
        days = cur["days_left"]
        for threshold in (30, 15, 7, 3, 1):
            if days == threshold:
                msgs.append(f"Sua licença expirará em {days} dia(s).")
        if cur.get("expired"):
            msgs.append("Licença expirada. Os dados locais estão preservados e a"
                        " operação de consulta continua disponível. Renove sua licença.")
        return msgs

    def save_license_file(self, raw: str) -> None:
        payload = self.validate_license_file(raw)
        key = self._normalize_key(payload.get("license_key", ""))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS licenses_files(license_key TEXT PRIMARY KEY, raw TEXT)")
        self._db.execute(
            "INSERT OR REPLACE INTO licenses_files(license_key, raw) VALUES(?,?)",
            (key, raw))


def _lic_cols(payload, anchor, raw, license_id):
    return (payload.get("customer_name", ""), payload.get("cnpj", ""),
            payload.get("product", "MASTERPARK"), payload.get("version", ""),
            payload.get("plan", ""), payload.get("activated_at", ""),
            payload.get("expires_at", ""),
            int(payload.get("lifetime") in (True, 1, "1", "true")),
            payload.get("duracao", ""),
            int(payload.get("terminals", 1)),
            int(payload.get("spaces", 0)), json.dumps(payload.get("features", [])),
            anchor, anchor, raw, license_id)


def _lic_vals(payload, anchor, raw):
    return (payload.get("license_key", ""), payload.get("customer_name", ""),
            payload.get("cnpj", ""), payload.get("product", "MASTERPARK"),
            payload.get("version", ""), payload.get("plan", ""),
            payload.get("activated_at", ""), payload.get("expires_at", ""),
            int(payload.get("lifetime") in (True, 1, "1", "true")),
            payload.get("duracao", ""),
            int(payload.get("terminals", 1)), int(payload.get("spaces", 0)),
            json.dumps(payload.get("features", [])), anchor, anchor, raw, utcnow())


def hash_anchor(key: str) -> str:
    return hashlib.sha256((key + "|masterpark").encode()).hexdigest()[:16]


class LicenseRepo(Repo):
    pass