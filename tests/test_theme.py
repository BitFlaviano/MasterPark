"""Folhas de estilo do Design System — regras que não podem regredir."""
from __future__ import annotations

import re

import pytest

from app.ui import theme

REGRAS_COMBO = [
    "QComboBox::drop-down",
    "QComboBox::drop-down:hover",
    "QComboBox::down-arrow",
    "QComboBox::down-arrow:hover",
    "QComboBox::down-arrow:disabled",
    "QComboBox QAbstractItemView",
    "QComboBox QAbstractItemView::item",
]

# todo estado de selecao/indicador precisa manter o raio, senao o item
# selecionado sai com canto quadrado por cima do raio do item base
REGRAS_ARREDONDADAS = [
    "QListWidget::item",
    "QListWidget::item:hover",
    "QListWidget::item:selected",
    "QTabBar::tab",
    "QTabBar::tab:hover",
    "QTabBar::tab:selected",
    "QComboBox QAbstractItemView::item:hover",
    "QComboBox QAbstractItemView::item:selected",
    "QCheckBox::indicator",
    "QCheckBox::indicator:hover",
    "QCheckBox::indicator:checked",
    "QCheckBox::indicator:disabled",
    "QRadioButton::indicator",
    "QRadioButton::indicator:hover",
    "QRadioButton::indicator:checked",
    "QRadioButton::indicator:disabled",
]


def _corpo(css: str, seletor: str) -> str:
    """Corpo da declaracao de um seletor, ou '' se nao existir.

    Tolera listas separadas por virgula, como
    `QCheckBox::indicator, QCheckBox::indicator:unchecked { ... }`.
    Comentarios CSS antes do seletor nao fazem parte do seletor.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for regra in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sels = [s.strip() for s in regra.group(1).split(",")]
        if seletor in sels:
            return regra.group(2)
    return ""


@pytest.fixture(params=[False, True], ids=["light", "dark"])
def css(request):
    return theme.build_stylesheet(request.param)


def test_build_stylesheet_escolhe_tema():
    assert theme.build_stylesheet(False) != theme.build_stylesheet(True)
    assert "#F1F5F9" in theme.build_stylesheet(False)
    assert theme.BG_DARK in theme.build_stylesheet(True)


def test_combo_tem_drop_down_e_seta(css):
    for regra in REGRAS_COMBO:
        assert regra in css, f"falta {regra}"


def test_drop_down_do_combo_arredondado(css):
    """O botão nativo do Qt desenhava por cima do border-radius do combo."""
    bloco = css.split("QComboBox::drop-down {")[1].split("}")[0]
    assert "border-top-right-radius" in bloco
    assert "border-bottom-right-radius" in bloco
    assert "border: none" in bloco


def test_seta_do_combo_e_css_nao_nativa(css):
    bloco = css.split("QComboBox::down-arrow {")[1].split("}")[0]
    assert "image: none" in bloco
    assert "border-top:" in bloco


def test_popup_do_combo_arredondado_e_com_padding(css):
    bloco = css.split("QComboBox QAbstractItemView {")[1].split("}")[0]
    assert "border-radius" in bloco
    assert "padding" in bloco


def test_combo_tem_espaco_para_a_seta(css):
    linha = [l for l in css.splitlines() if l.strip().startswith("QComboBox {")][0]
    assert "padding-right" in linha


def _padding_left(css: str, seletor: str) -> int:
    """Extrai o padding esquerdo efetivo de um seletor (tolera 1, 2 ou 4 valores)."""
    corpo = _corpo(css, seletor)
    m = re.search(r"padding:\s*([^;]+);", corpo)
    assert m, f"seletor {seletor} sem padding em {corpo!r}"
    v = [t for t in re.split(r"\s+", m.group(1).strip()) if t]
    v = [int(t.rstrip("px")) for t in v if t.rstrip("px").isdigit()]
    if len(v) == 1:
        return v[0]
    if len(v) in (2, 3):
        return v[1]
    return v[3]


def test_texto_do_popup_alinhado_ao_texto_do_campo(css):
    """O texto do primeiro item do popup deve começar exatamente onde o texto
    do campo começa — o desalinhamento horizontal visível ao abrir a lista."""
    campo_esq = _padding_left(css, "QLineEdit")
    popup_esq = _padding_left(css, "QComboBox QAbstractItemView")
    item_esq = _padding_left(css, "QComboBox QAbstractItemView::item")
    assert popup_esq + item_esq == campo_esq, (
        f"popup_texto={popup_esq + item_esq}px != campo_texto={campo_esq}px")


def test_todos_os_campos_de_formulario_compartilham_o_estilo(css):
    assert "QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit" in css
    assert "QComboBox:focus" in css


def test_spinbox_tem_setas_customizadas(css):
    assert "QSpinBox::up-arrow" in css
    assert "QSpinBox::down-arrow" in css
    assert "QDoubleSpinBox::up-arrow" in css


def test_date_edit_tem_drop_down_redondo(css):
    assert "QDateEdit::drop-down" in css
    assert "QDateEdit::down-arrow" in css


def test_botoes_mantem_cantos_redondados(css):
    assert "QPushButton { background" in css
    assert "border-radius: 8px" in css


def test_css_nao_tem_placeholder_não_resolvido(css):
    assert "{PRIMARY}" not in css
    assert "{SURFACE}" not in css
    assert "{TEXT_DARK}" not in css
    assert "{RAISED_DARK}" not in css

@pytest.mark.parametrize("seletor", REGRAS_ARREDONDADAS)
def test_estado_de_selecao_mantem_canto_redondo(css, seletor):
    """Hover/selected/indicator nao podem perder o raio do item base."""
    corpo = _corpo(css, seletor)
    assert corpo, f"regra ausente: {seletor}"
    assert "border-radius" in corpo, f"{seletor} sem border-radius"


def test_radio_e_circular(css):
    """O indicador de radio precisa de raio >= metade da largura."""
    for sel in ("QRadioButton::indicator",
                "QRadioButton::indicator:hover",
                "QRadioButton::indicator:checked",
                "QRadioButton::indicator:disabled"):
        corpo = _corpo(css, sel)
        raio = float(corpo.split("border-radius:")[1].split("px")[0])
        assert raio >= 8.5, f"{sel} com raio {raio}px"


def test_checkbox_mais_redondo_que_quadrado(css):
    corpo = _corpo(css, "QCheckBox::indicator:checked")
    raio = float(corpo.split("border-radius:")[1].split("px")[0])
    assert 3 <= raio <= 8, f"checkbox com raio {raio}px"


def test_item_selecionado_tem_fundo(css):
    """Sem fundo, o arredondamento nao aparece."""
    for sel in ("QListWidget::item:selected",
                "QComboBox QAbstractItemView::item:selected",
                "QTabBar::tab:selected"):
        corpo = _corpo(css, sel)
        assert "background:" in corpo and "background: transparent" not in corpo