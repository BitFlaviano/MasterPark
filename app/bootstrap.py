"""Inicialização da aplicação: banco, serviços, contexto da sessão."""
from __future__ import annotations

from pathlib import Path

from app.core.audit import AuditService
from app.core.config import (APP_VERSION, get_backup_dir, get_db_path,
                             load_settings_file, save_settings_file,
                             AppSettings)
from app.core.db import Database
from app.domain.permissions import seed_roles
from app.hardware.devices import DeviceManager
from app.repositories import (CompanyRepo, CustomerRepo, LotRepo, SectorRepo,
                              SettingRepo, SpaceRepo, UserRepo, VehicleRepo)
from app.repositories.operation import NotificationRepo
from app.services.analytics import AnalyticsService
from app.services.auth import AuthService
from app.services.backup import BackupService
from app.services.cash import CashService
from app.services.licensing import LicenseService
from app.services.monthly import MonthlyService
from app.services.printing import PrintingService
from app.services.reports import ReportService
from app.services.tickets import TicketService


class AppContext:
    """Contém todas as dependências compartilhadas pela interface."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or get_db_path()
        self.db = Database(self.db_path)
        self.db.ensure_schema()
        seed_roles(self.db)

        self.settings_repo = SettingRepo(self.db)
        self.settings = self._load_settings()

        self.companies = CompanyRepo(self.db)
        self.lots = LotRepo(self.db)
        self.sectors = SectorRepo(self.db)
        self.spaces = SpaceRepo(self.db)
        self.users = UserRepo(self.db)
        self.customers = CustomerRepo(self.db)
        self.vehicles = VehicleRepo(self.db)
        self.notifications = NotificationRepo(self.db)
        self.company = self.companies.first()
        self.lot = self.lots.first()

        self.audit = AuditService(self.db)
        self.auth = AuthService(self.db, failed_limit=self.settings.failed_login_limit,
                                timeout_minutes=self.settings.session_timeout_minutes)
        self.license = LicenseService(self.db)
        self.tickets = TicketService(self.db, self.lot)
        self.cash = CashService(self.db)
        self.monthly = MonthlyService(self.db, self.lot)
        self.backup = BackupService(self.db, self.audit)
        self.analytics = AnalyticsService(self.db)
        self.reports = ReportService(self.db, self.lot)
        self.printing = PrintingService(self.settings.printer_name)
        self.devices = DeviceManager(self.db)
        try:
            self.devices.build_demo_set()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _load_settings(self) -> AppSettings:
        merged = dict(AppSettings().as_dict())
        for key, value in self.settings_repo.all().items():
            if key in merged:
                try:
                    if isinstance(merged[key], bool):
                        merged[key] = value.lower() in ("1", "true", "sim", "yes")
                    elif isinstance(merged[key], int):
                        merged[key] = int(value)
                    else:
                        merged[key] = value
                except (TypeError, ValueError):
                    pass
        file_cfg = load_settings_file()
        merged.update({k: v for k, v in file_cfg.items() if k in merged})
        return AppSettings.from_dict(merged)

    def save_settings(self, **kwargs) -> None:
        for key, value in kwargs.items():
            self.settings_repo.set(key, str(value).lower() if isinstance(value, bool) else str(value))
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        save_settings_file(self.settings.as_dict())

    def refresh(self):
        self.company = self.companies.first()
        self.lot = self.lots.first()
        self.tickets.lot = self.lot
        self.monthly.lot = self.lot
        self.reports.lot = self.lot
        self.settings = self._load_settings()

    # ------------------------------------------------------------------
    def is_first_run(self) -> bool:
        return not (self.company and self.lot and self.users.list())

    def is_license_ok(self) -> bool:
        cur = self.license.current()
        return bool(cur and cur.get("status") == "ATIVA" and not cur.get("expired"))

    @property
    def version(self) -> str:
        return APP_VERSION

    def notify(self, level: str, code: str, title: str, message: str = ""):
        self.notifications.push(level, code, title, message,
                                lot_id=self.lot["id"] if self.lot else None)