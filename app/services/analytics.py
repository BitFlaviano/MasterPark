"""Analytics: KPIs do dashboard e relatórios gerenciais."""
from __future__ import annotations

import datetime

from app.domain.models import parse_iso, utcnow_iso
from app.repositories import SpaceRepo
from app.repositories.operation import MonthlyRepo

WEEKDAYS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


class AnalyticsService:
    def __init__(self, db):
        self.db = db
        self.spaces = SpaceRepo(db)
        self.monthly = MonthlyRepo(db)

    # ------------------------------------------------------------------
    def _bracket(self, start: datetime.datetime, end: datetime.datetime) -> tuple[str, str]:
        return (start.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ"),
                end.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ"))

    def day_session(self, days: int = 1) -> tuple[str, str]:
        now = datetime.datetime.now()
        start = now - datetime.timedelta(days=days - 1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._bracket(start, now + datetime.timedelta(seconds=1))

    def month_session(self) -> tuple[str, str]:
        now = datetime.datetime.now()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self._bracket(start, now + datetime.timedelta(seconds=1))

    # ------------------------------------------------------------------
    def dashboard(self) -> dict:
        spaces = self.spaces.count_by_state()
        total = int(spaces["TOTAL"] or 0)
        occupied = int(spaces["OCUPADA"] or 0) + int(spaces.get("RESERVADA") or 0)
        pct = round((occupied / total) * 100, 1) if total else 0.0

        today_start, today_end = self.day_session()
        month_start, month_end = self.month_session()
        revenue_today = self._revenue(today_start, today_end)
        revenue_month = self._revenue(month_start, month_end)

        entries = self.db.scalar(
            "SELECT COUNT(*) FROM tickets WHERE entry_at>=? AND entry_at<=?", (today_start, today_end)) or 0
        exits = self.db.scalar(
            "SELECT COUNT(*) FROM tickets WHERE exit_at>=? AND exit_at<=? AND status!='ATIVO'",
            (today_start, today_end)) or 0
        open_tickets = self.db.scalar("SELECT COUNT(*) FROM tickets WHERE status='ATIVO'") or 0
        overdue = self.monthly.overdue()
        expiring = self.monthly.expiring(7)
        monthly_alerts = {
            "overdue_count": len(overdue),
            "overdue_total": sum(int(r["value"]) for r in overdue),
            "expiring_count": len(expiring),
            "active_count": self.monthly.active_count(),
        }

        payments = self._payments_by_method(today_start, today_end)
        ticket_medio = int(revenue_today) // entries if entries else 0

        return {
            "total": total, "occupied": occupied, "free": int(spaces["LIVRE"] or 0),
            "reserved": int(spaces["RESERVADA"] or 0),
            "pct_occupied": pct,
            "vehicles_now": open_tickets,
            "entries_today": int(entries), "exits_today": int(exits),
            "revenue_today": revenue_today, "revenue_month": revenue_month,
            "revenue_month_prev": self._revenue_prev_month(month_start, month_end),
            "ticket_medio": ticket_medio,
            "monthly_active": monthly_alerts["active_count"],
            "monthly_overdue": monthly_alerts["overdue_count"],
            "monthly_overdue_total": monthly_alerts["overdue_total"],
            "monthly_expiring": monthly_alerts["expiring_count"],
            "open_tickets": open_tickets,
            "payments": payments,
            "blocks": self._occupancy_blocks(),
            "avg_time": self._avg_time(today_start, today_end),
        }

    def _revenue(self, start: str, end: str) -> int:
        return int(self.db.scalar(
            "SELECT COALESCE(SUM(final_value),0) FROM tickets"
            " WHERE exit_at>=? AND exit_at<=? AND status IN ('FINALIZADO','PERDIDO')",
            (start, end)) or 0)

    def _revenue_prev_month(self, month_start: str, month_end: str) -> int:
        try:
            s = parse_iso(month_start); e = parse_iso(month_end)
            prev = s - __import__("datetime").timedelta(days=1)
            prev_start = prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return self._revenue(
                prev_start.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ"),
                s.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ"))
        except Exception:
            return 0

    def _payments_by_method(self, start: str, end: str) -> list[dict]:
        return self.db.query(
            "SELECT pm.name method_name, COALESCE(SUM(p.value),0) total, COUNT(*) qty"
            " FROM payments p JOIN payment_methods pm ON pm.code=p.payment_method"
            " WHERE p.received_at>=? AND p.received_at<=? AND p.status='APROVADO'"
            " GROUP BY pm.name ORDER BY total DESC", (start, end))

    def _occupancy_blocks(self) -> list[dict]:
        """Horários de maior movimento (entradas por hora do dia de hoje)."""
        start, end = self.day_session()
        rows = self.db.query(
            "SELECT strftime('%H', entry_at, 'localtime') hour, COUNT(*) c"
            " FROM tickets WHERE entry_at>=? AND entry_at<=? GROUP BY hour ORDER BY hour",
            (start, end))
        return [{"hour": int(r["hour"]), "count": r["c"]} for r in rows]

    def _avg_time(self, start: str, end: str) -> int:
        return int(self.db.scalar(
            "SELECT CAST(COALESCE(AVG(total_minutes),0) AS INTEGER) FROM tickets"
            " WHERE exit_at>=? AND exit_at<=? AND total_minutes IS NOT NULL",
            (start, end)) or 0)

    # ------------------------------------------------------------------
    def revenue_series(self, start: str, end: str, granularity: str = "day") -> list[dict]:
        fmt = "%d/%m" if granularity == "day" else "%m/%Y"
        rows = self.db.query(
            "SELECT entry_at AS e, exit_at AS x, final_value v FROM tickets"
            " WHERE exit_at>=? AND exit_at<=? AND status IN ('FINALIZADO','PERDIDO')",
            (start, end))
        import collections
        acc = collections.defaultdict(int)
        for r in rows:
            if not r["x"]:
                continue
            try:
                d = parse_iso(r["x"]).astimezone()
                acc[d.strftime(fmt)] += int(r["v"])
            except Exception:
                continue
        result = [{"label": k, "value": v} for k, v in sorted(acc.items())]
        return result

    def top_spaces(self, limit: int = 10) -> list[dict]:
        return self.db.query(
            "SELECT s.code, COUNT(*) used, SUM(t.final_value) revenue"
            " FROM tickets t LEFT JOIN parking_spaces s ON s.id=t.parking_space_id"
            " WHERE t.status IN ('FINALIZADO','PERDIDO') AND s.code IS NOT NULL"
            " GROUP BY s.code ORDER BY revenue DESC LIMIT ?", (limit,))

    def revenue_by_operator(self, start: str, end: str) -> list[dict]:
        return self.db.query(
            "SELECT u.name operator, COUNT(*) tickets, COALESCE(SUM(t.final_value),0) revenue"
            " FROM tickets t JOIN users u ON u.id=t.exit_user_id"
            " WHERE t.exit_at>=? AND t.exit_at<=? AND t.status IN ('FINALIZADO','PERDIDO')"
            " GROUP BY u.name ORDER BY revenue DESC", (start, end))

    def revenue_by_hour(self, start: str, end: str) -> list[dict]:
        rows = self.db.query(
            "SELECT strftime('%H', exit_at, 'localtime') hour, COALESCE(SUM(final_value),0) v"
            " FROM tickets WHERE exit_at>=? AND exit_at<=? AND status IN ('FINALIZADO','PERDIDO')"
            " GROUP BY hour ORDER BY hour", (start, end))
        return [{"hour": int(r["hour"]), "value": int(r["v"])} for r in rows]

    def comparative_months(self, months: int = 6) -> list[dict]:
        rows = self.db.query(
            "SELECT strftime('%Y-%m', exit_at) ym, COALESCE(SUM(final_value),0) v, COUNT(*) n"
            " FROM tickets WHERE status IN ('FINALIZADO','PERDIDO')"
            " GROUP BY ym ORDER BY ym DESC LIMIT ?", (months,))
        return [{"period": r["ym"], "value": int(r["v"]), "count": r["n"]} for r in reversed(rows)]

    def discount_summary(self, start: str, end: str) -> list[dict]:
        return self.db.query(
            "SELECT kind, COUNT(*) qty, COALESCE(SUM(value),0) total"
            " FROM discounts WHERE created_at>=? AND created_at<=? GROUP BY kind",
            (start, end))