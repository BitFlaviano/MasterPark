"""Exclusão lógica de clientes e mensalistas (mesma estratégia das vagas).

O registro some das telas (active=0) mas permanece no banco para o
histórico fiscal continuar íntegro — nunca levantando FK/OperationalError.
"""
import pytest

from app.repositories import CustomerRepo
from app.repositories.operation import MonthlyRepo
from app.services.monthly import MonthlyService


def test_mensalista_pode_editar_valor_e_dia(demo_db, admin_user):
    """Antes: MonthlyService.get não existia e a tela abria erro genérico."""
    svc = MonthlyService(demo_db, None)
    lista = svc.list()
    assert {m["customer_name"] for m in lista}  # tem mensalistas
    mid = lista[0]["id"]
    row = svc.get(mid)
    assert row is not None and row["id"] == mid
    novo = row["monthly_value"] + 100
    svc.update(mid, monthly_value=novo, billing_day=10, user=admin_user)
    assert svc.get(mid)["monthly_value"] == novo


def test_mensalista_com_pagamento_pago_pode_ser_excluido(demo_db, admin_user):
    """Antes: bloqueava para sempre com histórico de pagamento."""
    repo = MonthlyRepo(demo_db)
    mensalistas = repo.list()
    com_pagamento = None
    for m in mensalistas:
        total = demo_db.scalar(
            "SELECT COUNT(*) FROM monthly_payments WHERE monthly_customer_id=?",
            (m["id"],))
        if total:
            com_pagamento = m
            break
    assert com_pagamento is not None, "demo deveria ter mensalista com pagamento"
    mid = com_pagamento["id"]
    n_payments = demo_db.scalar(
        "SELECT COUNT(*) FROM monthly_payments WHERE monthly_customer_id=?", (mid,))

    MonthlyService(demo_db, None).delete(mid, admin_user)

    assert all(m["id"] != mid for m in repo.list()), "sumiu da lista ativa"
    restante = demo_db.query_one(
        "SELECT active, status FROM monthly_customers WHERE id=?", (mid,))
    assert restante["active"] == 0, "exclusão lógica (linha preservada)"
    assert restante["status"] == "INATIVO"
    assert demo_db.scalar(
        "SELECT COUNT(*) FROM monthly_payments WHERE monthly_customer_id=?",
        (mid,)) == n_payments, "lançamentos fiscais preservados"


def test_cliente_com_historico_passa_do_passado_e_pode_ser_excluido(demo_db):
    """Antes: quebrava com 'no such column: mco.customer_id'."""
    repo = CustomerRepo(demo_db)
    candidatos = demo_db.query(
        "SELECT c.id FROM customers c"
        " WHERE NOT EXISTS (SELECT 1 FROM tickets t"
        "   WHERE t.customer_id=c.id AND t.status='ATIVO')"
        " AND NOT EXISTS (SELECT 1 FROM monthly_customers m"
        "   WHERE m.customer_id=c.id AND m.active=1)"
        " AND NOT EXISTS (SELECT 1 FROM monthly_payments mp"
        "   JOIN monthly_customers m2 ON m2.id=mp.monthly_customer_id"
        "   WHERE m2.customer_id=c.id AND mp.status='PENDENTE')"
        " LIMIT 5")
    assert candidatos, "demo deveria ter cliente sem vínculo atual"
    cid = candidatos[0]["id"]
    tem_veiculo = demo_db.scalar(
        "SELECT COUNT(*) FROM vehicles WHERE customer_id=?", (cid,)) > 0

    resultado = repo.delete(cid)

    assert resultado == 1
    linha = demo_db.query_one("SELECT active FROM customers WHERE id=?", (cid,))
    assert linha["active"] == 0, "soft delete"
    assert all(c["id"] != cid for c in repo.list(limit=1000)), "some da lista"
    if tem_veiculo:
        assert demo_db.scalar(
            "SELECT COUNT(*) FROM vehicles WHERE customer_id=?", (cid,)) > 0


def test_cliente_com_mensalista_ativo_bloqueado(demo_db):
    """Vínculo atual (mensalista ativo) trava a exclusão, como deve."""
    repo = CustomerRepo(demo_db)
    cid = demo_db.scalar(
        "SELECT customer_id FROM monthly_customers WHERE active=1 LIMIT 1")
    assert cid is not None, "demo deveria ter mensalista ativo"

    assert repo.delete(cid) == 0
    linha = demo_db.query_one("SELECT active FROM customers WHERE id=?", (cid,))
    assert linha["active"] == 1, "nada muda com o bloqueio"


def test_excluir_varios_clientes_nunca_levanta_sql_error(demo_db):
    """A causa raiz (mco.customer_id inexistente) não pode voltar."""
    repo = CustomerRepo(demo_db)
    for c in demo_db.query("SELECT id FROM customers LIMIT 8"):
        try:
            repo.delete(c["id"])
        except Exception as exc:  # pragma: no cover
            pytest.fail(f"cliente {c['id']} elevou erro: {exc}")