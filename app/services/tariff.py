"""Motor de tarifação MasterPark — regras de negócio puras (testáveis).

Regras (tariff_rules.rule_type):
  FREE          minutos gratuitos
  FIXED         valor fixo para o intervalo
  PER_HOUR      valor por hora (inteiro: centavos/hora)
  PER_FRACTION  valor por fração (ex.: R$ 2,00 / 30 min)
  MAX_DAILY     teto diário (valor único, aplicado no fim)
  DIARIA        valor de diária (fixo)
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from app.domain.models import TariffInfo

CENTAVOS = int


def total_minutes(entry: datetime, exit_dt: datetime) -> int:
    delta = exit_dt - entry
    minutes = int(math.ceil(delta.total_seconds() / 60))
    return max(minutes, 0)


def _ceil_hours(minutes: int) -> int:
    return int(math.ceil(minutes / 60))


class TariffEngine:
    """Calcula o valor de permanência com base em regras ordenadas."""

    FREE = "FREE"
    FIXED = "FIXED"
    PER_HOUR = "PER_HOUR"
    PER_FRACTION = "PER_FRACTION"
    MAX_DAILY = "MAX_DAILY"
    DIARIA = "DIARIA"

    FRACTION_DEFAULT_MINUTES = 30

    def __init__(self, tolerance_minutes: int = 0):
        self.tolerance = int(tolerance_minutes)

    # ------------------------------------------------------------------
    def calculate(self, entry: datetime, exit_dt: datetime, rules: list[dict],
                  tariff_name: str = "", tariff_id: int | None = None) -> TariffInfo:
        minutes = total_minutes(entry, exit_dt)
        return self.calculate_minutes(minutes, rules, tariff_name, tariff_id)

    def calculate_minutes(self, minutes: int, rules: list[dict], tariff_name: str = "",
                          tariff_id: int | None = None) -> TariffInfo:
        if minutes <= self.tolerance:
            return TariffInfo(tariff_id=tariff_id or 0, name=tariff_name,
                              base_value=0, discount_value=0, final_value=0,
                              minutes=minutes, rule_applied=f"Tolerância ({self.tolerance} min)")

        ordered = sorted(rules, key=lambda r: (r.get("minutes_from", 0), r.get("sort", 0)))
        used_rules: list[str] = []
        covered = 0
        total_value = 0
        max_daily = 0
        diaria_value = 0

        # teto diário e diária são pré-extraídos (não participam da segmentação)
        for r0 in ordered:
            if r0.get("rule_type") == self.MAX_DAILY:
                max_daily = max(max_daily, int(r0.get("value", 0) or 0))
            elif r0.get("rule_type") == self.DIARIA:
                diaria_value = max(diaria_value, int(r0.get("value", 0) or 0))

        while covered < minutes:
            rule = self._rule_for(ordered, covered)
            if rule is None:
                # sem mais regras aplicáveis: permanência sem tarifa definida
                break
            rtype = rule.get("rule_type")
            value = int(rule.get("value", 0) or 0)
            r_from = int(rule.get("minutes_from", 0))
            r_to = rule.get("minutes_to")
            prev = covered

            if rtype == self.FREE:
                seg = self._segment(covered, r_from, r_to, minutes)
                covered += max(seg, 0)
                used_rules.append(f"Grátis {seg}min")
            else:
                seg = self._segment(covered, r_from, r_to, minutes)
                if seg <= 0:
                    covered = minutes
                    continue
                seg = min(seg, minutes - covered)
                if rtype == self.FIXED:
                    total_value += value
                    used_rules.append(f"Fixo {value}c até {covered + seg}min")
                elif rtype == self.PER_HOUR:
                    total_value += _ceil_hours(seg) * value
                    used_rules.append(f"Hora {value}c por {seg}min")
                elif rtype == self.PER_FRACTION:
                    fraction_len = (max(int(r_to) - r_from, 1)
                                    if r_to is not None
                                    else self.FRACTION_DEFAULT_MINUTES)
                    total_value += math.ceil(seg / fraction_len) * value
                    used_rules.append(f"Fração {value}c a cada {fraction_len}min")
                covered += seg

            if covered <= prev:  # salvaguarda anti loop infinito
                break

        base = max(total_value, 0)
        if diaria_value and diaria_value > base:
            base = diaria_value
        if max_daily > 0:
            base = min(base, max_daily)

        rule_summary = ", ".join(used_rules[:5]) if used_rules else "Sem regra aplicada"
        return TariffInfo(tariff_id=tariff_id or 0, name=tariff_name,
                          base_value=base, discount_value=0, final_value=base,
                          minutes=minutes, rule_applied=rule_summary)

    # ------------------------------------------------------------------
    @staticmethod
    def _segment(current: int, r_from: int, r_to: int | None, total: int) -> int:
        if r_to is None:
            return total - current
        if current < r_from:
            return (r_from - current)  # avança até o início da regra (grátis)
        return min(r_to - current, total - current)

    @staticmethod
    def _rule_for(ordered: list[dict], current: int) -> Optional[dict]:
        for rule in ordered:
            if rule.get("rule_type") in ("MAX_DAILY",):
                continue
            r_from = int(rule.get("minutes_from", 0))
            r_to = rule.get("minutes_to")
            if current >= r_from and (r_to is None or current < r_to):
                return rule
        # extensão além das regras: reutiliza a última regra de cobrança
        for rule in reversed(ordered):
            if rule.get("rule_type") not in ("FREE", "MAX_DAILY", "DIARIA"):
                return rule
        return None


def apply_discount(base_value: int, percent: float = 0.0, fixed: int = 0,
                   gratuity: bool = False) -> int:
    if gratuity:
        return base_value
    discount = int(round(base_value * percent)) if percent else 0
    if fixed and fixed < (base_value - discount):
        discount = max(discount, fixed)
    return discount


def build_default_rules(initial_value_cents: int, per_hour_cents: int,
                        fraction_minutes: int = 30, free_minutes: int = 0,
                        max_daily_cents: int = 0) -> list[dict]:
    rules = []
    if free_minutes > 0:
        rules.append(dict(rule_type="FREE", minutes_from=0, minutes_to=free_minutes,
                          value=0, sort=0))
    rules.append(dict(rule_type="FIXED", minutes_from=free_minutes,
                      minutes_to=60, value=initial_value_cents, sort=10))
    rules.append(dict(rule_type="PER_FRACTION", minutes_from=60, minutes_to=None,
                      value=per_hour_cents * fraction_minutes // 60
                      if per_hour_cents * fraction_minutes % 60 == 0 else 0,
                      sort=20))
    last = rules[-1]
    if last["value"] == 0:
        rules[-1] = dict(rule_type="PER_HOUR", minutes_from=60, minutes_to=None,
                         value=per_hour_cents, sort=20)
    if max_daily_cents > 0:
        rules.append(dict(rule_type="MAX_DAILY", minutes_from=0, minutes_to=None,
                          value=max_daily_cents, sort=99))
    return rules