"""Layout de colunas: ajuste do usuário sobrevive a refresh e reinício."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from app.core.config import AppSettings, load_settings_file, save_settings_file
from app.ui.table_layout import ColumnLayout


@pytest.fixture(scope="module")
def qtapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    from app.bootstrap import AppContext
    from app.core.db import Database
    from app.domain.permissions import seed_roles

    db = Database(tmp_path / "layout.db")
    db.ensure_schema()
    seed_roles(db)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from app.core import config as cfg
    monkeypatch.setattr(cfg, "get_config_dir", lambda: tmp_path)
    monkeypatch.setattr(cfg, "settings_file", lambda: tmp_path / "settings.json")
    c = AppContext()
    yield c
    db.close()


def _table(qtapp, headers):
    t = QTableWidget(3, len(headers))
    t.setHorizontalHeaderLabels(headers)
    for r in range(3):
        for c in range(len(headers)):
            t.setItem(r, c, QTableWidgetItem(f"{r}-{c}"))
    return t


def _names(table):
    h = table.horizontalHeader()
    return [table.horizontalHeaderItem(h.visualIndex(v)).text()
            for v in range(table.columnCount())]


def test_ajuste_manual_marca_como_personalizado(ctx, qtapp):
    t = _table(qtapp, list("abc"))
    lay = ColumnLayout(ctx, t, "t")
    assert lay.custom is False
    t.setColumnWidth(0, 300)
    lay._on_changed()
    assert lay.custom is True


def test_refresh_nao_destroi_ajuste(ctx, qtapp):
    t = _table(qtapp, list("abc"))
    lay = ColumnLayout(ctx, t, "t")
    t.setColumnWidth(0, 300)
    lay._on_changed()
    lay.resize_event()
    assert t.columnWidth(0) == 300


def test_persiste_entre_sessoes(ctx, qtapp, tmp_path):
    t = _table(qtapp, list("abcd"))
    lay = ColumnLayout(ctx, t, "tickets_ativos")
    for c, w in enumerate([300, 90, 140, 70]):
        t.setColumnWidth(c, w)
    lay._on_changed()
    lay.save()

    saved = load_settings_file()["table_columns"]["tickets_ativos"]
    assert saved["widths"] == [300, 90, 140, 70]

    ctx2 = type(ctx)()
    t2 = _table(qtapp, list("abcd"))
    lay2 = ColumnLayout(ctx2, t2, "tickets_ativos")
    assert lay2.custom is True
    # a última coluna absorve a sobra de largura, então nunca fica menor que a salva
    assert [t2.columnWidth(c) for c in range(3)] == [300, 90, 140]
    assert t2.columnWidth(3) >= 70


def test_ordem_das_colunas_persiste(ctx, qtapp):
    t = _table(qtapp, list("abcd"))
    lay = ColumnLayout(ctx, t, "t")
    t.horizontalHeader().moveSection(0, 2)
    lay._on_changed()
    lay.save()
    assert _names(t) == ["c", "a", "b", "d"]

    ctx2 = type(ctx)()
    t2 = _table(qtapp, list("abcd"))
    ColumnLayout(ctx2, t2, "t")
    assert _names(t2) == ["c", "a", "b", "d"]


def test_reset_volta_ao_automatico_e_apaga_do_arquivo(ctx, qtapp):
    t = _table(qtapp, list("abcd"))
    lay = ColumnLayout(ctx, t, "t")
    t.setColumnWidth(0, 400)
    t.horizontalHeader().moveSection(0, 3)
    lay._on_changed()
    lay.save()
    assert "t" in load_settings_file()["table_columns"]

    lay.reset()
    assert lay.custom is False
    assert _names(t) == list("abcd")
    assert "t" not in load_settings_file().get("table_columns", {})


def test_largura_limitada_entre_min_e_max(ctx, qtapp):
    t = _table(qtapp, list("abcd"))
    lay = ColumnLayout(ctx, t, "t")
    t.setColumnWidth(0, 5)
    t.setColumnWidth(1, 9999)
    lay._on_changed()
    assert t.columnWidth(0) == 60
    assert t.columnWidth(1) == 520


def test_schema_diferente_cai_no_automatico(ctx, qtapp):
    t = _table(qtapp, list("abcdef"))
    lay = ColumnLayout(ctx, t, "t")
    t.setColumnWidth(0, 400)
    lay._on_changed()
    lay.save()

    ctx2 = type(ctx)()
    t2 = _table(qtapp, list("abc"))
    lay2 = ColumnLayout(ctx2, t2, "t")
    assert lay2.custom is False


def test_settings_tem_campo_table_columns():
    assert "table_columns" in AppSettings().as_dict()
    assert AppSettings().table_columns == {}


def test_ultima_coluna_usa_espaco_restante(ctx, qtapp):
    t = _table(qtapp, list("abc"))
    t.resize(600, 200)
    lay = ColumnLayout(ctx, t, "t")
    t.setColumnWidth(0, 300)
    lay._on_changed()
    lay.resize_event()
    total = sum(t.columnWidth(c) for c in range(t.columnCount()))
    assert total >= t.viewport().width() - 4