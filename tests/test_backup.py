"""Testes do serviço de backup e restauração."""
from __future__ import annotations

import pytest

from app.services.backup import BackupError, BackupService


def test_backup_cria_arquivo_validado(db):
    svc = BackupService(db)
    result = svc.create(kind="MANUAL", note="teste")
    assert result["path"].endswith(".db")
    import os
    assert os.path.exists(result["path"])
    assert svc.validate(result["path"])["valid"]


def test_restore_dry_run_rejeita_arquivo_inexistente(db):
    svc = BackupService(db)
    with pytest.raises(BackupError):
        svc.validate("C:\\nao_existe\\x.db")


def test_backup_nao_sobrescreve_anterior(db):
    svc = BackupService(db)
    a = svc.create(kind="MANUAL")
    b = svc.create(kind="MANUAL")
    assert a["path"] != b["path"]
    # último backup válido preservado
    assert svc.validate(a["path"])["valid"]
    assert svc.validate(b["path"])["valid"]