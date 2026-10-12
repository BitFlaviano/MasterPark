"""Testes de autenticação, senha e RBAC."""
from __future__ import annotations

import pytest

from app.core.security import PasswordService
from app.services.auth import AuthError, AuthService


def test_hash_senha_verifica():
    h, s = PasswordService.hash_password("secret123")
    assert PasswordService.verify_password("secret123", h, s)
    assert not PasswordService.verify_password("wrong", h, s)


def test_hash_unico_por_salt():
    h1, s1 = PasswordService.hash_password("same")
    h2, s2 = PasswordService.hash_password("same")
    assert h1 != h2


def test_login_ok(db, admin_user):
    svc = AuthService(db)
    user = svc.login("admin", "admin123")
    assert user.can("CONFIG_MANAGE")
    assert user.role == "ADMINISTRADOR"


def test_login_senha_errada(db, admin_user):
    svc = AuthService(db)
    with pytest.raises(AuthError):
        svc.login("admin", "errada")


def test_conta_bloqueada_apos_tentativas(db, admin_user):
    svc = AuthService(db, failed_limit=3)
    for _ in range(3):
        with pytest.raises(AuthError):
            svc.login("admin", "senha_incorreta")
    with pytest.raises(AuthError):
        svc.login("admin", "admin123")


def test_operador_nao_gera_config(db, admin_user):
    from app.core.security import PasswordService
    from app.repositories import UserRepo
    h, s = PasswordService.hash_password("operador123")
    UserRepo(db).create("op", "Operador", h, s, "OPERADOR")
    svc = AuthService(db)
    user = svc.login("op", "operador123")
    assert not user.can("CONFIG_MANAGE")


def test_permissao_customizada(db, admin_user):
    from app.repositories import UserRepo
    svc = AuthService(db)
    from app.core.security import PasswordService
    h, s = PasswordService.hash_password("ger123")
    UserRepo(db).create("ger", "Gerente", h, s, "GERENTE")
    user = svc.login("ger", "ger123")
    assert user.can("DISCOUNT_APPLY")
    assert not user.can("USER_MANAGE")