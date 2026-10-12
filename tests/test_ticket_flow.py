"""Testes do fluxo operacional: entrada, saída, ticket, caixa, mensalistas."""
from __future__ import annotations

import pytest

from app.services.auth import AuthService
from app.services.cash import CashService, CashError
from app.services.demo import setup_demo
from app.services.tickets import TicketError, TicketService
from app.domain.models import CurrentUser
from app.repositories import SpaceRepo


def login_admin(db) -> CurrentUser:
    return AuthService(db).login("admin", "admin123")


def test_entrada_vincula_cliente_digitado(demo_db):
    svc = TicketService(demo_db)
    user = login_admin(demo_db)
    t = svc.register_entry(plate="ABC1D23", category="CARRO",
                           customer_name="Fulano da Silva", user=user)
    assert t["customer_name"] == "Fulano da Silva"
    # segunda visita da MESMA placa também aproveita o nome digitado
    t2 = svc.register_entry(plate="ABC1D23", category="CARRO",
                            customer_name="Fulano da Silva", user=user)
    assert t2["customer_name"] == "Fulano da Silva"
    assert t2["status"] == "ATIVO"


def test_entrada_sem_cliente_nao_cria_customer(demo_db):
    svc = TicketService(demo_db)
    user = login_admin(demo_db)
    t = svc.register_entry(plate="KLM7B99", category="MOTO", user=user)
    assert not t.get("customer_name")
    assert t["status"] == "ATIVO"


def test_registro_de_saida_retorna_cliente(demo_db):
    svc = TicketService(demo_db)
    user = login_admin(demo_db)
    t = svc.register_entry(plate="PQR3C12", category="CARRO",
                           customer_name="Maria Souza", user=user)
    out = svc.register_exit(ticket_id=t["id"], payment_method="DINHEIRO",
                            user=user)
    assert out["customer_name"] == "Maria Souza"


def test_ciclo_completo_entrada_saida(demo_db):
    svc = TicketService(demo_db)
    user = login_admin(demo_db)
    t = svc.register_entry(plate="ABC1D23", category="CARRO", user=user,
                           terminal="GUARITA")
    assert t["status"] == "ATIVO"
    assert t["plate"] == "ABC1D23"
    assert t["number"].startswith("T")
    space = SpaceRepo(demo_db).get(t["parking_space_id"])
    assert space["state"] == "OCUPADA"

    found = svc.find_single(t["number"])
    assert found["id"] == t["id"]

    preview = svc.preview(found)
    assert preview["minutes"] >= 0

    out = svc.register_exit(ticket_id=t["id"], payment_method="PIX",
                            user=user, terminal="GUARITA")
    assert out["status"] == "FINALIZADO"
    assert out["final_value"] >= 0

    space2 = SpaceRepo(demo_db).get(t["parking_space_id"])
    assert space2["state"] == "LIVRE"


def test_saida_dupla_impedida(demo_db):
    svc = TicketService(demo_db)
    user = login_admin(demo_db)
    t = svc.register_entry(plate="XYZ9E87", category="CARRO", user=user,
                           terminal="GUARITA")
    svc.register_exit(ticket_id=t["id"], payment_method="DINHEIRO", user=user)
    with pytest.raises(TicketError):
        svc.register_exit(ticket_id=t["id"], payment_method="DINHEIRO", user=user)


def test_cancelamento_libera_vaga(demo_db):
    svc = TicketService(demo_db)
    user = login_admin(demo_db)
    t = svc.register_entry(plate="BRA2F42", category="CARRO", user=user)
    assert SpaceRepo(demo_db).get(t["parking_space_id"])["state"] == "OCUPADA"
    svc.cancel(ticket_id=t["id"], reason="Cliente desistiu", user=user)
    assert SpaceRepo(demo_db).get(t["parking_space_id"])["state"] == "LIVRE"


def test_cancelamento_exige_motivo(demo_db):
    svc = TicketService(demo_db)
    user = login_admin(demo_db)
    t = svc.register_entry(plate="QWE3H56", category="CARRO", user=user)
    with pytest.raises(TicketError):
        svc.cancel(ticket_id=t["id"], reason="  ", user=user)


def test_veiculo_bloqueado_nao_entra(demo_db):
    svc = TicketService(demo_db)
    user = login_admin(demo_db)
    demo_db.execute("UPDATE vehicles SET is_blocked=1 WHERE plate='DFG8M33'")
    with pytest.raises(TicketError) as e:
        svc.register_entry(plate="DFG8M33", category="CARRO", user=user)
    assert "bloqueado" in str(e.value)


def test_caixa_abre_fecha_com_diferenca_exigindo_justificativa(demo_db):
    cash = CashService(demo_db)
    user = login_admin(demo_db)
    # se já existe caixa aberto da demo, fecha antes
    existing = cash.active_for(user.id)
    if existing:
        cash.close(user=user, informed=0, justification="demo")
    reg = cash.open(user=user, opening_value=0)
    assert reg["status"] == "ABERTO"
    with pytest.raises(CashError):
        cash.close(user=user, informed=100)  # diferença sem justificativa
    result = cash.close(user=user, informed=100, justification="troco")
    assert result["difference"] != 0


def test_sangria_deve_ter_motivo(demo_db):
    cash = CashService(demo_db)
    user = login_admin(demo_db)
    existing = cash.active_for(user.id)
    if existing:
        cash.close(user=user, informed=0, justification="demo")
    cash.open(user=user, opening_value=0)
    with pytest.raises(CashError):
        cash.sangria(user=user, value=1000, reason="   ")


def test_mensalista_inadimplente_bloqueado(demo_db):
    from app.services.monthly import MonthlyService
    user = login_admin(demo_db)
    blocked = MonthlyService(demo_db).assess_blocking()
    # pelo menos os mensalistas pendentes são bloqueados
    assert len(blocked) >= 1