"""Testes do serviço de impressão sem depender de impressora instalada."""
import io

import pytest

from app.services.printing import (
    PrintingService,
    _code39_runs,
    _render_pdf_first_page,
    _use_gdi,
    extract_ascii_barcode,
    generate_barcode_png,
    ticket_to_pdf,
    ticket_preview_png,
)

BARS_A = "||||  ||||  ||||||  |||   |||  ||||  |"


def test_extract_ascii_barcode_remove_linhas_de_barras():
    texto = "Ticket 123\n" + BARS_A + "\n6508071\n"
    limpo, bars = extract_ascii_barcode(texto)
    assert bars == BARS_A
    assert "6508071" in limpo
    assert "||||" not in limpo


def test_extract_ascii_barcode_sem_barras_mantem_texto():
    texto = "Linha normal\nOutra linha"
    limpo, bars = extract_ascii_barcode(texto)
    assert bars is None and limpo == texto


def test_code39_runs_calcula_larguras():
    assert _code39_runs("|||  |") == [(True, 3), (False, 2), (True, 1)]

TICKET = (
    "=" * 32 + "\n"
    "MasterPark Estacionamento\n"
    "Ticket: 123  Placa: ABC-1D23\n"
    "VALOR FINAL: R$ 12,00\n"
)


def test_ticket_to_pdf_eh_pdf_valido():
    pdf = ticket_to_pdf(TICKET, qr_data="MP:TCK:123", paper_mm=80)
    assert pdf.startswith(b"%PDF-")
    assert b"MasterPark" in pdf


def test_ticket_to_pdf_com_qr_nao_quebra():
    pdf = ticket_to_pdf(TICKET, qr_data="MP:TCK:123", paper_mm=58)
    assert pdf.startswith(b"%PDF-")


def test_ticket_to_pdf_com_barcode_nao_quebra():
    texto = "Ticket 123\n" + BARS_A + "\n6508071\n"
    pdf = ticket_to_pdf(texto, qr_data="MP:TCK:123", paper_mm=58)
    assert pdf.startswith(b"%PDF-")
    img = _render_pdf_first_page(pdf, dpi=150)
    assert img.mode == "RGB"


def test_render_pdf_primeira_pagina_tem_proporcao_do_papel():
    pdf = ticket_to_pdf(TICKET, paper_mm=80, height_mm=200)
    img = _render_pdf_first_page(pdf, dpi=150)
    assert img.mode == "RGB"
    expected = 80 / 200
    actual = img.width / img.height
    assert abs(actual - expected) < 0.02


def test_ticket_preview_png_gera_png_com_qr():
    png = ticket_preview_png(TICKET, qr_data="MP:TCK:123",
                             width_mm=80, height_mm=160, scale=4)
    assert png.startswith(b"\x89PNG")


@pytest.mark.parametrize("name,esperado", [
    ("Microsoft Print to PDF", True),
    ("Adobe PDF", True),
    ("2024 - XPS", True),
    ("HP LaserJet 1000", True),
    ("Generic / Text Only", False),
    ("Bematech MP-4200 TH", False),
])
def test_escolha_do_caminho_de_impressao(name, esperado):
    assert _use_gdi(name) is esperado


@pytest.fixture
def ps():
    return PrintingService("DEMO")


def test_barcode_nao_requer_fonte_ttf(monkeypatch):
    """src: sem write_text=False o EXE frozen quebra com 'cannot open resource'."""
    from PIL import ImageFont

    def boom(*_a, **_k):
        raise OSError("cannot open resource")

    monkeypatch.setattr(ImageFont, "truetype", boom)
    png = generate_barcode_png("T00000042")
    assert png.startswith(b"\x89PNG")


def test_ticket_entrada_mostra_cliente(ps):
    ticket = {"number": "T1", "plate": "ABC-1D23",
              "vehicle_category": "CARRO", "entry_at": "2026-10-11T10:00:00",
              "space_code": "A-01", "customer_name": "Fulano da Silva"}
    texto = ps.render_ticket_entry(
        {"name": "MasterPark"}, {"cnpj": "00"}, ticket)
    assert "Cliente: Fulano da Silva" in texto


def test_ticket_entrada_sem_cliente_usa_fallback(ps):
    ticket = {"number": "T2", "plate": "ABC-1D23",
              "vehicle_category": "MOTO", "entry_at": "2026-10-11T10:00:00",
              "space_code": "B-01"}
    texto = ps.render_ticket_entry(
        {"name": "MasterPark"}, {"cnpj": "00"}, ticket)
    assert "Cliente: Cliente não identificado" in texto


def test_comprovante_saida_mostra_cliente(ps):
    ticket = {"number": "T3", "plate": "ABC-1D23",
              "entry_at": "2026-10-11T10:00:00", "exit_at": "2026-10-11T11:00:00",
              "customer_name": "Maria Souza"}
    preview = {"minutes": 60, "base_value": 1200, "discount_value": 0,
               "final_value": 1200}
    texto = ps.render_receipt({"name": "MasterPark"}, {"cnpj": "00"},
                              ticket, preview)
    assert "Cliente: Maria Souza" in texto
    assert "Cliente não identificado" not in texto