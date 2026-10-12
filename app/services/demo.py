"""Modo demonstração: gera dados fictícios realistas para o sistema."""
from __future__ import annotations

import datetime
import random

from app.core.security import PasswordService
from app.domain.models import utcnow_iso
from app.repositories import (CompanyRepo, CustomerRepo, LotRepo, SectorRepo,
                              SpaceRepo, UserRepo, VehicleRepo)
from app.repositories.operation import MonthlyRepo, TariffRepo
from app.services.monthly import MonthlyService
from app.services.tariff import build_default_rules

NAMES = ["Maria Silva", "João Pereira", "Ana Souza", "Carlos Lima", "Fernanda Costa",
         "Ricardo Alves", "Juliana Rocha", "Paulo Mendes", "Beatriz Santos",
         "Rodrigo Nunes", "Camila Ferreira", "Eduardo Barbosa", "Patrícia Gomes",
         "Rafael Moreira", "Larissa Cardoso"]
PLATES = ["ABC1D23", "XYZ9E87", "BRA2F42", "MPK7G11", "QWE3H56", "RTY6J78",
          "UIO2K90", "PAS4L21", "DFG8M33", "HJK5N44", "ZXC1P65", "VBN3Q77",
          "LMN6R88", "POI2S99", "AOE7T10", "JKL4U22", "FGH9V33", "ERT3W44"]
BRANDS = ["Fiat", "VW", "Chevrolet", "Hyundai", "Toyota", "Ford", "Honda", "Renault"]
MODELS = ["Argo", "Gol", "Onix", "HB20", "Corolla", "Ka", "Civic", "Kwid"]
COLORS = ["Branco", "Preto", "Prata", "Vermelho", "Azul", "Cinza"]


def timerange_days(days: int) -> str:
    return (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")


def seed_company(db) -> dict:
    repo = CompanyRepo(db)
    existing = repo.first()
    if existing:
        return existing
    repo.upsert(dict(name="Estacionamento Centro Demo",
                     legal_name="MasterPark Demo Ltda",
                     cnpj="12.345.678/0001-99",
                     address="Av. Central, 1000 - Centro",
                     phone="(11) 4002-8922", whatsapp="(11) 99999-0000",
                     email="contato@masterpark.com.br"))
    return repo.first()


def seed_lot(db, company) -> dict:
    repo = LotRepo(db)
    existing = repo.first()
    if existing:
        return existing
    repo.upsert(dict(company_id=company["id"], name="Estacionamento Centro",
                     code="UNID-01", address="Av. Central, 1000 - Centro",
                     phone="(11) 4002-8922", opening_time="07:00",
                     closing_time="22:00", tolerance_minutes=10))
    return repo.first()


def seed_tariffs(db, lot) -> None:
    t = TariffRepo(db)
    existing = t.list(lot["id"])
    if existing:
        return
    for name, vertex, free, hourly in (("Padrão", 1200, 15, 1000),
                                       ("Moto", 800, 15, 600)):
        tid = t.create(dict(lot_id=lot["id"], name=name,
                            vehicle_category="*" if name == "Padrão" else "MOTO",
                            period_type="NORMAL", is_default=1 if name == "Padrão" else 0,
                            days_mask="1111111"))
        rules = build_default_rules(vertex, hourly, fraction_minutes=30,
                                    free_minutes=free, max_daily_cents=vertex * 12)
        for r in rules:
            t.add_rule(tid, r["minutes_from"], r["minutes_to"],
                       r["rule_type"], r["value"], r["sort"])


def seed_spaces(db, lot) -> None:
    spaces = SpaceRepo(db)
    if spaces.total(lot["id"]) > 0:
        return
    sectors = SectorRepo(db)
    A = sectors.create(lot["id"], "Setor A", "#4C6FFF", 1)
    B = sectors.create(lot["id"], "Setor B", "#22C55E", 1)
    for sector_id, prefix in ((A, "A"), (B, "B")):
        codes = [f"{prefix}{str(i).zfill(2)}" for i in range(1, 51)]
        spaces.create_many(lot["id"], sector_id, codes, "CARRO")
    # vagas especiais
    spaces.create_many(lot["id"], A, ["PD1", "PD2"], "DEFICIENTE")
    spaces.create_many(lot["id"], B, ["ID1", "ID2"], "IDOSO")
    spaces.create_many(lot["id"], A, ["M1", "M2", "M3", "M4"], "MOTO")


def seed_users(db) -> dict:
    users = UserRepo(db)
    existing = users.get_by_username("admin")
    if existing:
        return users.get(existing["id"])
    h, s = PasswordService.hash_password("admin123")
    uid = users.create("admin", "Administrador", h, s, "ADMINISTRADOR")
    h2, s2 = PasswordService.hash_password("operador123")
    users.create("operador", "Operador Demo", h2, s2, "OPERADOR")
    return users.get(uid)


def seed_customers_vehicles(db, count: int = 20) -> list[int]:
    cust = CustomerRepo(db)
    veh = VehicleRepo(db)
    ids = []
    for i in range(min(count, 30)):
        c = cust.create(dict(name=random.choice(NAMES), person_type="FISICA",
                             cpf=_random_cpf(), phone=f"(11) 9{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
                             whatsapp="", email=""))
        veh.create(dict(customer_id=c, plate=PLATES[i % len(PLATES)],
                        model=random.choice(MODELS), brand=random.choice(BRANDS),
                        color=random.choice(COLORS), category=random.choice(["CARRO", "CARRO", "CARRO", "MOTO"])))
        ids.append(c)
    return ids


def seed_monthly(db, lot, customer_ids: list[int]) -> None:
    monthly = MonthlyRepo(db)
    if monthly.active_count() > 0:
        return
    svc = MonthlyService(db, lot)
    customers = CustomerRepo(db)
    admin_u = UserRepo(db).get_by_username("admin")
    user = UserRepo(db).to_current(admin_u)
    for i in range(5):
        cid = customer_ids[i % len(customer_ids)]
        plate = PLATES[i * 2 % len(PLATES)]
        svc.create(customer_id=cid, placa=plate, monthly_value=25000,
                   billing_day=1 + i, space_code="", user=user)
    # paga os 3 primeiros, deixa 2 pendentes (inadimplentes/vencendo)
    pays = monthly.list()
    for idx, m in enumerate(pays):
        if idx >= 3:
            continue
        pay = monthly.payments(m["id"])[0]
        try:
            svc.pay_pending(pay["id"], int(m["monthly_value"]), "PIX", user)
        except Exception:
            pass
    # paga os 3 primeiros, deixa 2 pendentes (inadimplentes/vencendo)
    pays = monthly.list()
    from app.domain.models import CurrentUser
    admin_u = UserRepo(db).get_by_username("admin")
    user = UserRepo(db).to_current(admin_u)
    for idx, m in enumerate(pays):
        if idx >= 3:
            continue
        pay = monthly.payments(m["id"])[0]
        try:
            svc.pay_pending(pay["id"], int(m["monthly_value"]), "PIX", user)
        except Exception:
            pass
    # atrasa as duas pendentes
    db.execute(
        "UPDATE monthly_payments SET due_date=date('now','-5 day')"
        " WHERE status='PENDENTE'")


def seed_tickets(db, lot, days: int = 60) -> None:
    from app.services.tickets import TicketService
    from app.repositories.operation import TariffRepo, TicketRepo
    from app.domain.models import CurrentUser
    users = UserRepo(db)
    admin = users.to_current(users.get_by_username("admin"))
    svc = TicketService(db, lot)
    tickets = TicketRepo(db)
    existing = tickets.count()
    if existing > 0:
        # alguns tickets ativos já existem? garantir algum aberto
        open_count = db.scalar("SELECT COUNT(*) FROM tickets WHERE status='ATIVO'") or 0
        if open_count < 5:
            for i in range(5):
                svc.register_entry(plate=PLATES[(i + 10) % len(PLATES)],
                                   category="CARRO", user=admin, terminal="GUARITA",
                                   model=random.choice(MODELS), color=random.choice(COLORS))
        return
    tariffs = TariffRepo(db)
    default = tariffs.list(lot["id"])[0]
    engine = None
    hourly = [("07:00", "09:30"), ("10:00", "12:00"), ("12:30", "13:30"),
              ("14:00", "16:00"), ("17:00", "19:30"), ("20:00", "21:00")]
    for day_offset in range(days, 0, -1):
        day = datetime.datetime.now() - datetime.timedelta(days=day_offset)
        for h_in, h_out in hourly[:random.randint(2, len(hourly))]:
            if random.random() < 0.15:
                continue
            entry = day.replace(hour=int(h_in[:2]), minute=int(h_in[3:]), second=0)
            exit_dt = day.replace(hour=int(h_out[:2]), minute=int(h_out[3:]), second=0)
            if exit_dt <= entry:
                continue
            plate = random.choice(PLATES)
            plate = plate if random.random() < 0.8 else "AVU" + str(random.randint(10, 99))
            cat = "CARRO" if "M" not in plate[0] else "CARRO"
            try:
                t = svc.register_entry(plate=plate, category=cat, user=admin,
                                       terminal="GUARITA")
            except Exception:
                continue
            # processa saída diretamente no banco (consistente)
            mins = int((exit_dt - entry).total_seconds() // 60)
            method = random.choice(["DINHEIRO", "PIX", "CREDITO", "DEBITO", "PIX"])
            base = monto_por_minuto(mins)
            final = base - int(base * random.uniform(0, 0.05)) if random.random() < 0.1 else base
            with db.transaction() as cur:
                cur.execute(
                    "UPDATE tickets SET status='FINALIZADO', exit_at=?, exit_user_id=?,"
                    " total_minutes=?, tariff_id=?, base_value=?, final_value=?,"
                    " terminal_exit='GUARITA' WHERE id=?",
                    (exit_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                     admin.id if users.get_by_username("operador") else admin.id,
                     mins, default["id"], base, final, t["id"]))
                cur.execute(
                    "INSERT INTO payments(ticket_id, payment_method, status, value,"
                    " received_at, received_value, operator_id, created_at)"
                    " VALUES(?,?,?,?,?,?,?,?)",
                    (t["id"], method, "APROVADO", final,
                     exit_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), final, admin.id,
                     exit_dt.strftime("%Y-%m-%dT%H:%M:%SZ")))
                cur.execute(
                    "UPDATE parking_spaces SET state='LIVRE' WHERE id=?",
                    (t["parking_space_id"],))
                cur.execute(
                    "UPDATE parking_sessions SET exit_at=?, status='ENCERRADA'"
                    " WHERE ticket_id=? AND status='ATIVA'",
                    (exit_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), t["id"]))
    # alguns ativos agora
    for i in range(8):
        try:
            svc.register_entry(plate=PLATES[(i + 20) % len(PLATES)], category="CARRO",
                               user=admin, terminal="GUARITA")
        except Exception:
            pass


def monto_por_minuto(minutes: int) -> int:
    if minutes <= 15:
        return 0
    if minutes <= 60:
        return 1200
    total = 1200
    minutes -= 60
    while minutes > 0:
        total += 500
        minutes -= 30
    return min(total, 12000)


def setup_demo(db, password_admin: str = "admin123", password_op: str = "operador123") -> None:
    company = seed_company(db)
    lot = seed_lot(db, company)
    seed_tariffs(db, lot)
    seed_spaces(db, lot)
    admin = seed_users(db)
    cids = seed_customers_vehicles(db, 20)
    seed_monthly(db, lot, cids)
    seed_tickets(db, lot)
    db.execute("INSERT OR REPLACE INTO system_settings(key,value)"
               " VALUES('demo_seeded','1')")
    db.execute("INSERT OR REPLACE INTO system_settings(key,value)"
               " VALUES('demo_mode','1')")


from random import randint


def _random_cpf() -> str:
    nums = [randint(0, 9) for _ in range(9)]
    d1 = sum((i + 1) * v for i, v in enumerate(nums)) % 11
    d1 = 0 if d1 < 2 else 11 - d1
    nums.append(d1)
    d2 = sum((i + 1) * v for i, v in enumerate(nums)) % 11
    d2 = 0 if d2 < 2 else 11 - d2
    nums.append(d2)
    return "".join(map(str, nums))