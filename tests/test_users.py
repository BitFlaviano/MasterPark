"""Gestão de usuários: CRUD, senha, permissões e proteções."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import PasswordService
from app.repositories import UserRepo
from app.services.auth import AuthError, AuthService


def _create(repo: UserRepo, username: str, role: str, pwd: str = "senha123"):
    h, s = PasswordService.hash_password(pwd)
    return repo.create(username, username.upper(), h, s, role)


def test_cria_usuario_com_senha_valida(db):
    repo = UserRepo(db)
    uid = _create(repo, "recepcao", "CAIXA")
    row = repo.get(uid)
    assert row["username"] == "recepcao"
    assert PasswordService.verify_password("senha123", row["password_hash"], row["salt"])


def test_login_ignora_caixa_e_espaco(db):
    repo = UserRepo(db)
    _create(repo, "recepcao", "CAIXA", pwd="Senha#123")
    assert repo.get_by_username("  RECEPCAO  ") is not None


def test_altera_nome_e_perfil(db):
    repo = UserRepo(db)
    uid = _create(repo, "recepcao", "CAIXA")
    repo.update_profile(uid, name="Recepcao Sul", role_code="GERENTE")
    row = repo.get(uid)
    assert row["name"] == "Recepcao Sul"
    assert row["role_code"] == "GERENTE"
    assert "USER_MANAGE" not in repo.permissions(uid)
    assert "CUSTOMER_MANAGE" in repo.permissions(uid)


def test_alterar_perfil_troca_permissoes(db):
    repo = UserRepo(db)
    uid = _create(repo, "recepcao", "OPERADOR")
    assert repo.permissions(uid) == {"DASH_VIEW", "ENTRY_CREATE", "EXIT_CREATE",
                                     "TICKET_LOST", "INCIDENT_MANAGE"}
    repo.update_profile(uid, role_code="AUDITOR")
    assert "AUDIT_VIEW" in repo.permissions(uid)
    assert "ENTRY_CREATE" not in repo.permissions(uid)


def test_reativar_usuario_nao_acrescenta_permissao(db):
    repo = UserRepo(db)
    uid = _create(repo, "recepcao", "CAIXA")
    repo.update_profile(uid, is_active=0)
    assert repo.get(uid)["is_active"] == 0
    repo.update_profile(uid, is_active=1)
    assert repo.get(uid)["is_active"] == 1
    assert "USER_MANAGE" not in repo.permissions(uid)


def test_redefinir_senha_limpa_bloqueio(db):
    repo = UserRepo(db)
    uid = _create(repo, "operador", "OPERADOR")
    for _ in range(AuthService(db).failed_limit):
        repo.register_failure(uid, AuthService(db).failed_limit)
    assert repo.get(uid)["locked_until"] is not None
    h, s = PasswordService.hash_password("novasenha9")
    repo.set_password(uid, h, s)
    row = repo.get(uid)
    assert PasswordService.verify_password("novasenha9", row["password_hash"], row["salt"])
    assert row["failed_attempts"] == 0
    assert row["locked_until"] is None
    assert row["must_change_password"] == 0


def test_excluir_remove_permissoes_especificas(db):
    repo = UserRepo(db)
    uid = _create(repo, "recepcao", "CAIXA")
    repo.set_override(uid, "USER_MANAGE", True)
    assert "USER_MANAGE" in repo.permissions(uid)
    db.execute("DELETE FROM user_permissions WHERE user_id=?", (uid,))
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    assert repo.get(uid) is None
    assert repo.permissions(uid) == set()


def test_permissao_customizada_concede_e_revoga(db):
    repo = UserRepo(db)
    uid = _create(repo, "recepcao", "OPERADOR")
    repo.set_override(uid, "REPORT_VIEW", True)
    assert "REPORT_VIEW" in repo.permissions(uid)
    repo.set_override(uid, "REPORT_VIEW", False)
    assert "REPORT_VIEW" not in repo.permissions(uid)


def test_operador_nao_pode_gerenciar_usuarios(db, admin_user):
    repo = UserRepo(db)
    _create(repo, "operador", "OPERADOR")
    auth = AuthService(db)
    auth._session = type("S", (), {"user": repo.to_current(repo.get_by_username("operador"))})()
    with pytest.raises(PermissionError):
        auth.require_permission("USER_MANAGE")
    auth._session = type("S", (), {"user": admin_user})()
    assert auth.require_permission("USER_MANAGE").username == "admin"


def test_bloqueio_expira_e_login_normaliza(db, admin_user):
    repo = UserRepo(db)
    uid = _create(repo, "alvo", "OPERADOR", pwd="certa123")
    auth = AuthService(db, lock_minutes=15)
    auth._session = type("S", (), {"user": admin_user})()
    for _ in range(auth.failed_limit):
        with pytest.raises(AuthError):
            auth.login("alvo", "errada")
    assert repo.get(uid)["locked_until"] is not None
    with pytest.raises(AuthError):
        auth.login("alvo", "certa123")
    passado = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    db.execute("UPDATE users SET locked_until=? WHERE id=?", (passado, uid))
    assert auth.login("alvo", "certa123").username == "alvo"
    row = repo.get(uid)
    assert row["locked_until"] is None
    assert row["failed_attempts"] == 0


def test_bloqueio_ativo_bloqueia_senha_correta(db, admin_user):
    repo = UserRepo(db)
    uid = _create(repo, "alvo", "OPERADOR", pwd="certa123")
    auth = AuthService(db)
    for _ in range(auth.failed_limit):
        with pytest.raises(AuthError):
            auth.login("alvo", "errada")
    with pytest.raises(AuthError, match="bloqueada"):
        auth.login("alvo", "certa123")
    h, s = PasswordService.hash_password("nova1234")
    repo.set_password(uid, h, s)
    assert auth.login("alvo", "nova1234").username == "alvo"


def test_update_profile_sem_campos_nao_altera_nada(db):
    repo = UserRepo(db)
    uid = _create(repo, "alvo", "CAIXA")
    antes = dict(repo.get(uid))
    repo.update_profile(uid)
    assert dict(repo.get(uid)) == antes