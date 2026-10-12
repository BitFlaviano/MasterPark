"""Exclusao de vagas e setores.

Cobre tres bugs encadeados que impediam excluir vagas:
  1. `SpaceRepo.delete()` consultava `monthly_customers.space_id`, coluna que
     nao existe (o vinculo fica em `monthly_contracts`) -> toda exclusao
     estourava OperationalError.
  2. O bloqueio por "qualquer historico" impedia excluir qualquer vaga ja
     usada uma unica vez. Agora so uso ATUAL bloqueia.
  3. `Database.execute()` devolve `lastrowid`, obsoleto em UPDATE/DELETE, entao
     os repos retornavam sucesso mesmo sem alterar nada.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def lot(db):
    cid = db.execute(
        "INSERT INTO companies(name,created_at) VALUES('Empresa','2026-01-01')")
    lot_id = db.execute(
        "INSERT INTO parking_lots(company_id,name,code,created_at)"
        " VALUES(?,'Estacionamento Teste','T1','2026-01-01')", (cid,))
    return db.query_one("SELECT * FROM parking_lots WHERE id=?", (lot_id,))


def _repo(db):
    from app.repositories import SectorRepo, SpaceRepo
    return SpaceRepo(db), SectorRepo(db)


def _space(db, lot_id, code, sector_id=None, state="LIVRE"):
    sid = db.execute(
        "INSERT INTO parking_spaces(lot_id,sector_id,code,state) VALUES(?,?,?,?)",
        (lot_id, sector_id, code, state))
    return db.query_one("SELECT * FROM parking_spaces WHERE id=?", (sid,))


def _sector(db, lot_id, name="A"):
    sid = db.execute(
        "INSERT INTO parking_sectors(lot_id,name,color) VALUES(?,?,'#4C6FFF')",
        (lot_id, name))
    return db.query_one("SELECT * FROM parking_sectors WHERE id=?", (sid,))


def _ticket(db, lot_id, space_id, status="FINALIZADO", number=None):
    return db.execute(
        "INSERT INTO tickets(lot_id,number,status,parking_space_id,plate,entry_at)"
        " VALUES(?,?,?,?,?,?)",
        (lot_id, number or f"T-{abs(hash((status, space_id))) % 10**6}",
         status, space_id, "ABC1D23", "2026-01-01 08:00"))


def _reservation(db, lot_id, space_id, status="CONCLUIDA"):
    return db.execute(
        "INSERT INTO reservations(lot_id,space_id,start_at,end_at,status,"
        "created_at) VALUES(?,?,?,?,?,'2026-01-01 07:00')",
        (lot_id, space_id, "2026-01-01", "2026-01-02", status))


def _monthly_contract(db, space_id, end_at=None):
    cid = db.execute(
        "INSERT INTO customers(name,created_at) VALUES('Cliente Mensalista',"
        "'2026-01-01')")
    mid = db.execute(
        "INSERT INTO monthly_customers(customer_id,plan_name,status,start_at,"
        "monthly_value,billing_day,created_at)"
        " VALUES(?,'Mensalista','ATIVO','2026-01-01',100,1,'2026-01-01')", (cid,))
    return db.execute(
        "INSERT INTO monthly_contracts(monthly_customer_id,space_id,start_at,"
        "value,end_at) VALUES(?,?,'2026-01-01',100,?)", (mid, space_id, end_at))


# ---------------------------------------------------------- db.execute bug
def test_execute_rowcount_distingue_update_sem_match(db):
    """`execute()` devolveria 1 mesmo sem alterar nada."""
    cid = db.execute(
        "INSERT INTO companies(name,created_at) VALUES('C','2026-01-01')")
    lid = db.execute(
        "INSERT INTO parking_lots(company_id,name,code,created_at)"
        " VALUES(?,'L','L1','2026-01-01')", (cid,))
    sp = _space(db, lid, "A-001")
    assert db.execute_rowcount(
        "UPDATE parking_spaces SET notes=? WHERE id=?", ("x", sp["id"])) == 1
    assert db.execute_rowcount(
        "UPDATE parking_spaces SET notes=? WHERE id=?", ("y", 999999)) == 0


# ------------------------------------------------------------ regressao 1
def test_delete_nao_quebra_com_coluna_inexistente(db, lot):
    """A consulta de bloqueio deve rodar sem OperationalError."""
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    assert spaces.delete_blockers(sp["id"]) == []
    assert spaces.delete(sp["id"]) == 1


def test_exclui_vaga_livre(db, lot):
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    assert spaces.delete(sp["id"]) == 1
    assert spaces.get(sp["id"])["active"] == 0


def test_exclusao_logica_some_das_listas(db, lot):
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    assert len(spaces.list(lot["id"])) == 1
    spaces.delete(sp["id"])
    assert spaces.list(lot["id"]) == []
    assert spaces.total(lot["id"]) == 0
    assert spaces.count_by_state(lot["id"])["TOTAL"] == 0
    # get() ainda acha, para os relatorios antigos
    assert spaces.get(sp["id"]) is not None


def test_vaga_inexistente_retorna_zero(db, lot):
    spaces, _ = _repo(db)
    assert spaces.delete(999999) == 0


# ------------------------------------------------------------- bloqueios
@pytest.mark.parametrize("estado", ["OCUPADA", "RESERVADA", "MANUTENCAO"])
def test_bloqueia_vaga_em_uso(db, lot, estado):
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001", state=estado)
    assert spaces.delete(sp["id"]) == 0
    assert spaces.get(sp["id"])["active"] == 1
    assert spaces.delete_blockers(sp["id"])


def test_bloqueia_ticket_aberto(db, lot):
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    _ticket(db, lot["id"], sp["id"], status="ATIVO")
    assert spaces.delete(sp["id"]) == 0
    assert any("ticket aberto" in r for r in spaces.delete_blockers(sp["id"]))


def test_bloqueia_reserva_ativa(db, lot):
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    _reservation(db, lot["id"], sp["id"], status="CONFIRMADA")
    assert spaces.delete(sp["id"]) == 0
    assert any("reserva ativa" in r for r in spaces.delete_blockers(sp["id"]))


def test_bloqueia_contrato_mensal_vigente(db, lot):
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    _monthly_contract(db, sp["id"])
    assert spaces.delete(sp["id"]) == 0
    assert any("contrato mensal" in r
               for r in spaces.delete_blockers(sp["id"]))


# -------------------------------------------------- regressao 2: historico
def test_historico_finalizado_nao_bloqueia(db, lot):
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    _ticket(db, lot["id"], sp["id"], status="FINALIZADO")
    _reservation(db, lot["id"], sp["id"], status="CONCLUIDA")
    assert spaces.delete_blockers(sp["id"]) == []
    assert spaces.delete(sp["id"]) == 1


def test_contrato_mensal_vencido_nao_bloqueia(db, lot):
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    _monthly_contract(db, sp["id"], end_at="2020-01-01")
    assert spaces.delete_blockers(sp["id"]) == []
    assert spaces.delete(sp["id"]) == 1


def test_historico_preserva_codigo_do_ticket(db, lot):
    """A linha permanece, entao o ticket antigo continua com o codigo certo."""
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    _ticket(db, lot["id"], sp["id"], status="FINALIZADO")
    spaces.delete(sp["id"])
    row = db.query_one(
        "SELECT t.number, s.code FROM tickets t"
        " JOIN parking_spaces s ON s.id=t.parking_space_id"
        " WHERE t.parking_space_id=?", (sp["id"],))
    assert row["code"] == "A-001"


# --------------------------------------------------------- recriar codigo
def test_recriar_codigo_excluido_reativa(db, lot):
    spaces, _ = _repo(db)
    sp = _space(db, lot["id"], "A-001")
    spaces.delete(sp["id"])
    assert spaces.create_many(lot["id"], None, ["A-001"]) == 1
    again = spaces.get(sp["id"])
    assert again["active"] == 1
    assert again["state"] == "LIVRE"
    assert len(spaces.list(lot["id"])) == 1


def test_create_many_ignora_codigo_ativo_duplicado(db, lot):
    spaces, _ = _repo(db)
    _space(db, lot["id"], "A-001")
    assert spaces.create_many(lot["id"], None, ["A-001"]) == 0
    assert len(spaces.list(lot["id"])) == 1


def test_create_many_conta_apenas_criados(db, lot):
    spaces, _ = _repo(db)
    _space(db, lot["id"], "A-001")
    assert spaces.create_many(lot["id"], None, ["A-001", "A-002", "A-003"]) == 2


def test_vaga_excluida_nao_e_escolhida_pelo_smart_find(db, lot):
    spaces, _ = _repo(db)
    _space(db, lot["id"], "A-001")
    spaces.delete(spaces.list(lot["id"])[0]["id"])
    assert spaces.smart_find(lot["id"], "CARRO") is None


# ------------------------------------------------------------------ setores
def test_exclui_setor_desativando_vagas(db, lot):
    spaces, sectors = _repo(db)
    sec = _sector(db, lot["id"])
    sp = _space(db, lot["id"], "A-001", sector_id=sec["id"])
    assert sectors.delete(sec["id"]) == 1
    assert spaces.list(lot["id"]) == []
    assert spaces.get(sp["id"])["active"] == 0
    assert spaces.get(sp["id"])["sector_id"] is None
    assert db.query_one(
        "SELECT * FROM parking_sectors WHERE id=?", (sec["id"],)) is None


def test_setor_vazio_exclui(db, lot):
    _, sectors = _repo(db)
    sec = _sector(db, lot["id"])
    assert sectors.delete(sec["id"]) == 1
    assert db.query_one(
        "SELECT * FROM parking_sectors WHERE id=?", (sec["id"],)) is None


def test_setor_com_vaga_ocupada_nao_exclui(db, lot):
    _, sectors = _repo(db)
    sec = _sector(db, lot["id"])
    _space(db, lot["id"], "A-001", sector_id=sec["id"], state="OCUPADA")
    assert sectors.delete(sec["id"]) == 0
    assert db.query_one("SELECT * FROM parking_sectors WHERE id=?", (sec["id"],))


def test_setor_com_historico_exclui_mesmo_assim(db, lot):
    spaces, sectors = _repo(db)
    sec = _sector(db, lot["id"])
    sp = _space(db, lot["id"], "A-001", sector_id=sec["id"])
    _ticket(db, lot["id"], sp["id"], status="FINALIZADO")
    assert sectors.delete(sec["id"]) == 1
    assert spaces.get(sp["id"])["active"] == 0


def test_setor_com_vaga_ja_desativada_nao_quebra_fk(db, lot):
    """Vaga excluida antes continua apontando para o setor."""
    spaces, sectors = _repo(db)
    sec = _sector(db, lot["id"])
    sp = _space(db, lot["id"], "A-001", sector_id=sec["id"])
    spaces.delete(sp["id"])
    assert sectors.delete(sec["id"]) == 1
    assert spaces.get(sp["id"])["sector_id"] is None


# ------------------------------------------------------------- integridade
def test_integridade_do_banco_apos_exclusoes(db, lot):
    spaces, sectors = _repo(db)
    sec = _sector(db, lot["id"])
    for i in range(5):
        _space(db, lot["id"], f"A-{i:03d}", sector_id=sec["id"])
    _ticket(db, lot["id"], 1, status="FINALIZADO")
    for sp in spaces.list(lot["id"])[:3]:
        spaces.delete(sp["id"])
    sectors.delete(sec["id"])
    assert db.integrity_check() == ["ok"]


# --------------------------------------------------------------- migracao
def test_migracao_adiciona_coluna_active_em_banco_antigo(tmp_path):
    """Banco ja criado sem a coluna active deve ser migrado."""
    from app.core.db import Database
    d = Database(tmp_path / "velho.db")
    d.ensure_schema()
    d.execute("ALTER TABLE parking_spaces DROP COLUMN active")
    assert "active" not in {r["name"] for r in
                           d.query("PRAGMA table_info(parking_spaces)")}
    d.ensure_schema()
    assert "active" in {r["name"] for r in
                        d.query("PRAGMA table_info(parking_spaces)")}
    d.close()