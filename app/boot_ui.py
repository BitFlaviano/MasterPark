"""Constrói todas as telas do sistema e as liga à janela principal."""
from __future__ import annotations

from app.ui.about_screen import AboutScreen
from app.ui.audit_screen import AuditScreen
from app.ui.users_screen import UsersScreen
from app.ui.cash_screen import CashScreen
from app.ui.customers_screen import CustomersScreen
from app.ui.dashboard import DashboardScreen
from app.ui.entry import EntryScreen
from app.ui.exit_screen import ExitScreen
from app.ui.health_screen import HealthScreen
from app.ui.map_view import MapViewScreen
from app.ui.monthly_screen import MonthlyScreen
from app.ui.reports_screen import ReportsScreen
from app.ui.settings_screen import SettingsScreen
from app.ui.tickets_screen import TicketsScreen


def build_screens(ctx, win) -> dict:
    screens = {
        "entry": EntryScreen(ctx, parent=win),
        "exit": ExitScreen(ctx, parent=win),
        "map": MapViewScreen(ctx, parent=win),
        "tickets": TicketsScreen(ctx, ctx and win.navigate, parent=win),
        "dashboard": DashboardScreen(ctx, ctx and win.navigate, parent=win),
        "monthly": MonthlyScreen(ctx, parent=win),
        "customers": CustomersScreen(ctx, parent=win),
        "cash": CashScreen(ctx, parent=win),
        "reports": ReportsScreen(ctx, parent=win),
        "settings": SettingsScreen(ctx, parent=win),
        "health": HealthScreen(ctx, parent=win),
        "audit": AuditScreen(ctx, parent=win),
        "users": UsersScreen(ctx, parent=win),
        "about": AboutScreen(ctx, parent=win),
    }
    return screens