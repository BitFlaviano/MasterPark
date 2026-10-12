"""Separação de recursos de administrador (menus/telas/primeira tela)."""
from app.domain.permissions import (ADMIN_ONLY_SCREENS, ADMIN_ROLE, ROLES,
                                    first_screen_for, hidden_menu_keys,
                                    is_admin_role, role_permissions)
from app.ui.main_window import _sections_to_hide


def test_admin_role_e_reconhecido():
    assert is_admin_role(ADMIN_ROLE)
    assert not is_admin_role("GERENTE")
    assert not is_admin_role("")


def test_recursos_admin_definidos():
    assert ADMIN_ONLY_SCREENS == {
        "dashboard", "reports", "settings", "health", "audit", "users",
    }


def test_mapa_visivel_para_todos_mas_gerenciamento_admin():
    # o mapa é de TODOS (visualização) — não entra nas telas exclusivas
    assert "map" not in ADMIN_ONLY_SCREENS
    for role in ("GERENTE", "SUPERVISOR", "CAIXA", "OPERADOR", "AUDITOR"):
        keys = hidden_menu_keys(role, role_permissions(role))
        assert "map" not in keys, role


def test_nao_admin_esconde_todas_as_telas_de_admin():
    for role in ("GERENTE", "SUPERVISOR", "CAIXA", "OPERADOR", "AUDITOR"):
        keys = hidden_menu_keys(role, role_permissions(role))
        assert ADMIN_ONLY_SCREENS <= keys, role
        assert not {"entry", "exit", "tickets", "map", "about"} & keys, role


def test_gerente_mantem_recursos_operacionais_por_permissao():
    keys = hidden_menu_keys("GERENTE", role_permissions("GERENTE"))
    # gerente tem MONTHLY_MANAGE/CUSTOMER_MANAGE/CASH_OPEN
    assert not {"monthly", "customers", "cash"} & keys
    assert "tickets" not in keys


def test_admin_so_perde_por_permissao_individual():
    keys = hidden_menu_keys("ADMINISTRADOR", role_permissions("ADMINISTRADOR"))
    assert keys == set()
    # admin sem permissões pontuais ainda não perde as telas de admin
    assert "dashboard" not in hidden_menu_keys(ADMIN_ROLE, set())
    # mas perde mensalistas/clientes/caixa
    assert {"monthly", "customers", "cash"} <= hidden_menu_keys(ADMIN_ROLE, set())


def test_primeira_tela_segundo_o_perfil():
    assert first_screen_for("ADMINISTRADOR") == "dashboard"
    assert first_screen_for("OPERADOR") == "entry"
    assert first_screen_for("CAIXA") == "entry"
    assert first_screen_for("AUDITOR") == "entry"
    assert first_screen_for("") == "entry"


def test_operador_sem_gestao_e_financeiro_ocultam_titulos():
    hid = hidden_menu_keys("OPERADOR", role_permissions("OPERADOR"))
    assert _sections_to_hide(hid) == ("GESTÃO", "FINANCEIRO")
    # sistema continua (tem "Sobre") e operação (tem entrada/saída/mapa/tickets)
    assert "SISTEMA" not in _sections_to_hide(hid)
    assert "OPERAÇÃO" not in _sections_to_hide(hid)


def test_titulo_visivel_quando_sobra_item_disponivel():
    # CAIXA tem permissão de caixa -> FINANCEIRO continua visível
    hid = hidden_menu_keys("CAIXA", role_permissions("CAIXA"))
    assert _sections_to_hide(hid) == ("GESTÃO",)
    # GERENTE tem mensalistas/clientes/caixa -> gestão e financeiro ficam
    hid2 = hidden_menu_keys("GERENTE", role_permissions("GERENTE"))
    assert _sections_to_hide(hid2) == ()


def test_admin_nao_oculta_nenhum_titulo():
    hid = hidden_menu_keys("ADMINISTRADOR", role_permissions("ADMINISTRADOR"))
    assert _sections_to_hide(hid) == ()