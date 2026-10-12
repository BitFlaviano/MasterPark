"""Configurações e caminhos do MasterPark."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "MasterPark"
APP_VERSION = "1.0.0"
PRODUCT_NAME = "MasterPark"
COMPANY_NAME = "MasterPark Software"
DEFAULT_PUBLIC_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAscJkSjpPDE1JakEVEqVb
P2O2NgGBIvtz4Sy2EwwEbk10IVoUQBZb0yoX4YGHVBPvjJJ1sh3pv4vBVzxpgJVz
KJ4E2XYC//day0xncBNWDLm65UiJnIEincsVGicbNf6PTjLzB3XggTdF+90PR6Ie
mUb9FvAKfCdQUUzwg/+0fv94EYCix1RzLXtGsd4Z3BD238EraTAXpBN02/enFxXw
90NJA99H4QQ9qg9TRtKZByi9p8XN8Jx2xpmMtfr01qKtIsiNe0MyqZy5gx5S1Ynh
zg34EWuQm7bJ7mh9d2s9XGBPS6OBpL3oNNfwjNMMkC3rbkS0hkH9bmiNkm1fgEDS
qQIDAQAB
-----END PUBLIC KEY-----
"""


# ----------------------------------------------------------------------
# Caminhos de dados (runtime) — fora da pasta de instalação
# ----------------------------------------------------------------------
def _app_data_dir() -> Path:
    if os.environ.get("MASTERPARK_PORTABLE"):
        return Path(os.environ["MASTERPARK_PORTABLE"])
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / APP_NAME


def get_config_dir() -> Path:
    path = _app_data_dir() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    path = _app_data_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    return get_data_dir() / "masterpark.db"


def get_backup_dir() -> Path:
    path = _app_data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_dir() -> Path:
    path = _app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return get_config_dir() / "settings.json"


def load_settings_file() -> dict:
    path = settings_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings_file(data: dict) -> None:
    try:
        settings_file().write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ----------------------------------------------------------------------
# Identificação da máquina (âncora de licenciamento)
# ----------------------------------------------------------------------
def detect_machine_id() -> str:
    """Identificador estável da instalação para licenciamento."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            if value:
                return str(value).upper()
    except Exception:
        pass
    try:
        node = uuid.getnode()
        return hashlib.sha256(f"masterpark|{node}".encode()).hexdigest()[:16].upper()
    except Exception:
        return "ID-" + platform.node().upper().replace(" ", "")


# ----------------------------------------------------------------------
# Configurações do aplicativo (persistidas em settings.json + banco)
# ----------------------------------------------------------------------
@dataclass
class AppSettings:
    theme: str = "light"                       # light | dark
    language: str = "pt-BR"
    currency: str = "BRL"
    timezone: str = "America/Sao_Paulo"

    failed_login_limit: int = 5                # bloqueio após N tentativas
    session_timeout_minutes: int = 30          # ociosidade => logout

    printer_name: str = ""                     # vazio = impressora simulada/demo
    printer_width_mm: int = 58
    auto_print_ticket: bool = True
    print_receipt: bool = True

    backup_retention_days: int = 30
    auto_backup_days: int = 1

    total_spaces: int = 0
    demo_mode: bool = False

    # layout de colunas por tela, ex.: {"tickets_ativos": {"widths": [], "order": []}}
    table_columns: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        known = set(cls.__dataclass_fields__.keys())
        values = {k: v for k, v in data.items() if k in known}
        return cls(**values)