"""Modelos de domínio e utilitários de conversão de valores/data."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def cents(value: float | int | str) -> int:
    """Converte R$ ("12,50" ou 12.5) para centavos inteiros."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value * 100)
    clean = str(value).replace("R$", "").replace(" ", "").strip()
    neg = clean.startswith("-")
    clean = clean.lstrip("-")
    neg = neg or clean.startswith("(")
    clean = clean.replace("(", "").replace(")", "")
    negative = False
    if "-" in clean:
        negative = True
        clean = clean.replace("-", "")
    if "." in clean and "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    try:
        result = round(float(clean) * 100)
    except ValueError:
        return 0
    if negative:
        result = -result
    return result


def format_money(cents_value: int) -> str:
    sign = "-" if cents_value < 0 else ""
    v = abs(int(cents_value))
    return f"{sign}R$ {v // 100},{v % 100:02d}"


def format_minutes(minutes: int | None) -> str:
    if minutes is None:
        return "-"
    minutes = int(minutes)
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h{m:02d}min"
    if h:
        return f"{h}h"
    return f"{m}min"


def format_pt_datetime(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        d = parse_iso(iso).astimezone()
        return d.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso


def format_pt_date(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        d = parse_iso(iso).astimezone()
        return d.strftime("%d/%m/%Y")
    except Exception:
        return iso


def local_to_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_to_local(iso: str) -> datetime:
    return parse_iso(iso).astimezone()


def now_local() -> datetime:
    return datetime.now().astimezone()


PLATE_OLD = re.compile(r"^[A-Z]{3}\d{4}$")
PLATE_MERCOSUL = re.compile(r"^[A-Z]{3}\d[A-Z]\d{2}$")


def validate_plate(plate: str) -> bool:
    p = (plate or "").upper().strip()
    return bool(PLATE_OLD.match(p) or PLATE_MERCOSUL.match(p))


def mask_doc(doc: str) -> str:
    if not doc:
        return ""
    if len(doc) == 11:
        return f"{doc[:3]}.***.***-{doc[-2:]}"
    return f"{doc[:2]}.****.***-**"


@dataclass
class CurrentUser:
    id: int
    username: str
    name: str
    role: str
    terminal: str = ""
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def require(self, permission: str) -> None:
        if not self.can(permission):
            raise PermissionError(f"Acesso negado: permissão '{permission}' requerida.")


@dataclass
class TariffInfo:
    tariff_id: int
    name: str
    base_value: int
    discount_value: int
    final_value: int
    minutes: int
    rule_applied: str = ""


@dataclass
class CashOpenState:
    register_id: int | None = None
    operator: str = ""