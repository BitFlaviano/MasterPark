"""Fixtures de teste: banco em memória (perpétuo) com schema e roles."""
from __future__ import annotations

import pytest

from app.core.db import Database
from app.domain.permissions import seed_roles


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    d.ensure_schema()
    seed_roles(d)
    yield d
    d.close()


@pytest.fixture
def demo_db(tmp_path):
    """Banco populado com dados de demonstração."""
    from app.services.demo import setup_demo
    d = Database(tmp_path / "demo.db")
    d.ensure_schema()
    seed_roles(d)
    setup_demo(d)
    yield d
    d.close()


@pytest.fixture
def admin_user(db):
    from app.core.security import PasswordService
    from app.repositories import UserRepo
    h, s = PasswordService.hash_password("admin123")
    uid = UserRepo(db).create("admin", "Administrador", h, s, "ADMINISTRADOR")
    return UserRepo(db).to_current(UserRepo(db).get(uid))