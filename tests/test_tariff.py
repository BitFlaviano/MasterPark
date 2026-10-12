"""Testes do motor de tarifação (regra de negócio crítica)."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.services.tariff import (TariffEngine, apply_discount,
                                 build_default_rules)


def dt(minutes: int) -> datetime:
    """Entrada fixa; saída = entrada + minutes."""
    entry = datetime(2026, 9, 20, 8, 0, 0)
    return entry, entry + timedelta(minutes=minutes)


def test_tolerancia_gratuita():
    engine = TariffEngine(tolerance_minutes=10)
    rules = build_default_rules(1200, 1000, free_minutes=15)
    _, exit_dt = dt(8)
    r = engine.calculate(datetime(2026, 9, 20, 8), exit_dt, rules, "Padrão")
    assert r.final_value == 0


def test_primeiros_15_min_gratis():
    engine = TariffEngine(tolerance_minutes=0)
    rules = build_default_rules(1200, 1000, free_minutes=15)
    entry, exit_dt = dt(10)
    r = engine.calculate(entry, exit_dt, rules)
    assert r.final_value == 0


def test_primeira_hora_valor_fixo():
    engine = TariffEngine()
    rules = build_default_rules(1200, 1000, free_minutes=15)
    entry, exit_dt = dt(45)
    r = engine.calculate(entry, exit_dt, rules, "Padrão")
    # 15 grátis + 30 min da fixa => R$ 12,00
    assert r.final_value == 1200
    assert r.minutes == 45


def test_1h30_uma_hora_mais_fracao():
    engine = TariffEngine()
    rules = build_default_rules(1200, 1000, free_minutes=15)
    entry, exit_dt = dt(90)
    r = engine.calculate(entry, exit_dt, rules, "Padrão")
    # 15 grátis + até 60 min fixa (1200) + 30 min fração (frações de 30min = 500) => 1700
    assert r.final_value == 1700


def test_maximo_diario():
    engine = TariffEngine()
    rules = build_default_rules(1200, 1000, free_minutes=0, max_daily_cents=12000)
    entry, exit_dt = dt(14 * 60)  # 14h
    r = engine.calculate(entry, exit_dt, rules, "Padrão")
    assert r.final_value == 12000


def test_diaria_menor_que_soma():
    engine = TariffEngine()
    rules = [
        {"rule_type": "FREE", "minutes_from": 0, "minutes_to": 15, "value": 0},
        {"rule_type": "FIXED", "minutes_from": 15, "minutes_to": 60, "value": 1200},
        {"rule_type": "PER_FRACTION", "minutes_from": 60, "minutes_to": None, "value": 500},
        {"rule_type": "DIARIA", "minutes_from": 0, "minutes_to": None, "value": 9000},
    ]
    entry, exit_dt = dt(10 * 60)
    r = engine.calculate(entry, exit_dt, rules)
    # soma > diária => diária
    assert r.final_value == 9000


def test_desconto_percentual():
    assert apply_discount(10000, percent=0.10) == 1000
    assert apply_discount(10000, percent=0.25) == 2500


def test_desconto_gratuidade():
    assert apply_discount(10000, gratuity=True) == 10000


def test_arredondamento_minutos_para_cima():
    engine = TariffEngine()
    rules = build_default_rules(1200, 1000)
    entry = datetime(2026, 9, 20, 8, 0, 1)
    out = datetime(2026, 9, 20, 8, 5, 0)
    r = engine.calculate(entry, out, rules)
    assert r.minutes == 5