"""Serviço de impressão térmica (ESC/POS) e geração de QR/código de barras.

- Impressora ESC/POS direta (drivers genéricos/térmicas): envia bytes via RAW.
- Impressoras comuns (PDF, laser, jato): o recibo é convertido em PDF pelo
  Python (reportlab) e enviado via GDI — impressoras que salvam arquivo
  (ex.: Microsoft Print to PDF) abrem o diálogo "salvar como", como qualquer
  aplicativo, sem depender do driver Adobe.
- Caso contrário usa um adaptador DEMO que salva o ticket em .txt/.png
  (claramente identificado), garantindo que a operação não quebre offline.
"""
from __future__ import annotations

import io
import os
from datetime import datetime

from app.core.config import get_data_dir
from app.domain.models import format_money

PRINT_DIR = get_data_dir() / "printed" / "demo"

# ----------------------------------------------------------------------
# Code 39 — codigo de barras padrao de estacionamento.
# 9 elementos por caractere (5 barras + 4 espacos), com 'w' = largo.
# ----------------------------------------------------------------------
CODE39 = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn",
    "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw",
    "8": "wnnwnnwnn", "9": "nnwwnnwnn", "A": "wnnnnwnnw", "B": "nnwnnwnnw",
    "C": "wnwnnwnnn", "D": "nnnnwwnnw", "E": "wnnnwwnnn", "F": "nnwnwwnnn",
    "G": "nnnnnwwnw", "H": "wnnnnwwnn", "I": "nnwnnwwnn", "J": "nnnnwwwnn",
    "K": "wnnnnnnww", "L": "nnwnnnnww", "M": "wnwnnnnwn", "N": "nnnnwnnww",
    "O": "wnnnwnnwn", "P": "nnwnwnnwn", "Q": "nnnnnnwww", "R": "wnnnnnwwn",
    "S": "nnwnnnwwn", "T": "nnnnwnwwn", "U": "wwnnnnnnw", "V": "nwwnnnnnw",
    "W": "wwwnnnnnn", "X": "nwnnwnnnw", "Y": "wwnnwnnnn", "Z": "nwwnwnnnn",
    "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "$": "nwnwnwnnn",
    "/": "nwnwnnnwn", "+": "nwnnnwnwn", "%": "nnnwnwnwn", "*": "nwnnwnwnn",
}


def code39_bars(data: str, narrow: int = 1, wide: int = 3) -> str:
    """Codifica `data` em Code 39 usando caracteres de texto.

    Barras em '|' e espacos em ' ', o que permite imprimir o codigo em
    qualquer impressora (inclusive as que nao aceitam grafico) e ainda
    assim ser lido por qualquer leitor de codigo de barras.
    """
    text = "".join(c for c in str(data).upper() if c in CODE39)
    if not text:
        return ""
    out: list[str] = []
    for char in f"*{text}*":
        pattern = CODE39[char]
        for i, elem in enumerate(pattern):
            width = wide if elem == "w" else narrow
            out.append("|" * width if i % 2 == 0 else " " * width)
        out.append(" " * narrow)  # separacao entre caracteres
    return "".join(out).rstrip()


def qr_matrix(data: str, border: int = 2) -> list[list[bool]]:
    """Matriz booleana do QR Code (True = modulo escuro)."""
    import qrcode

    qr = qrcode.QRCode(border=border, box_size=1)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()


def escpos_image(matrix: list[list[bool]], scale: int = 4) -> bytes:
    """Converte uma matriz de pontos em bytes ESC/POS (GS v 0).

    Cada modulo vira `scale` x `scale` pixels; a largura e arredondada
    para multiplos de 8, conforme exige o comando de raster.
    """
    height = len(matrix) * scale
    width = len(matrix[0]) * scale
    row_bytes = (width + 7) // 8
    data = bytearray()
    for y in range(height):
        row = matrix[y // scale]
        line = bytearray(row_bytes)
        for x in range(width):
            if row[x // scale]:
                line[x // 8] |= 0x80 >> (x % 8)
        data += line
    m = 0  # 8 pontos, densidade simples
    return (b"\x1d\x76\x30" + bytes([m])
            + bytes([row_bytes & 0xFF, row_bytes >> 8, height & 0xFF, height >> 8])
            + bytes(data) + b"\n")


def qr_escpos(data: str, target_dots: int = 256) -> bytes:
    """QR Code pronto para a impressora termica (raster ESC/POS)."""
    matrix = qr_matrix(data)
    size = len(matrix)
    scale = max(1, target_dots // size)
    # centraliza horizontalmente numa impressora de 32 colunas (256 dots)
    pad_left = ((32 - ((size * scale) // 8)) // 2) * 8
    out = b""
    if pad_left > 0:
        out += b" " * (pad_left // 8)
    out += escpos_image(matrix, scale)
    return out


def text_block(text: str, center: bool = False) -> bytes:
    """Converte texto em bytes cp1252, opcionalmente centralizado."""
    raw = text.encode("cp1252", errors="replace")
    if not center:
        return raw
    lines = raw.split(b"\n")
    out = bytearray()
    for line in lines:
        pad = max(0, (32 - len(line)) // 2)
        out += b" " * pad + line + b"\n"
    return bytes(out)


class PrinterAdapter:
    name = "DEMO"

    def print_raw(self, bytes_data: bytes) -> bool:
        raise NotImplementedError

    def print_text(self, text: str) -> bool:
        raise NotImplementedError

    def print_ticket(self, text_bytes: bytes, codes_bytes: bytes = b"",
                     meta: dict | None = None) -> bool:
        """Imprime o ticket: texto monoespacado + raster do QR Code."""
        return self.print_raw(text_bytes + codes_bytes + b"\n\x1d\x56\x41\x00")

    def is_available(self) -> bool:
        return False


class WindowsThermalPrinter(PrinterAdapter):
    """Impressora térmica Windows via win32print (RAW ESC/POS)."""

    def __init__(self, printer_name: str):
        self.printer_name = printer_name
        self.name = printer_name or "PRINTER"

    def is_available(self) -> bool:
        try:
            import win32print
            printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
            return self.printer_name in printers or not self.printer_name
        except Exception:
            return False

    def print_raw(self, bytes_data: bytes) -> bool:
        try:
            import win32print
            printer_name = self.printer_name
            if not printer_name:
                printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
                if not printers:
                    raise RuntimeError("Nenhuma impressora instalada.")
                printer_name = printers[0]
            handle = win32print.OpenPrinter(printer_name)
            try:
                win32print.StartDocPrinter(handle, 1, ("MasterPark", None, "RAW"))
                win32print.StartPagePrinter(handle)
                win32print.WritePrinter(handle, bytes_data)
                win32print.EndPagePrinter(handle)
                win32print.EndDocPrinter(handle)
            finally:
                win32print.ClosePrinter(handle)
            return True
        except Exception as exc:
            print(f"[impressão] falha: {exc}")
            return False

    def print_text(self, text: str) -> bool:
        width_cmds = (b"\x1b\x40"  # init
                      b"\x1b\x61\x01")  # center
        return self.print_raw(width_cmds + text.encode("cp1252", errors="replace") + b"\n\x1d\x56\x41\x00")


def _default_printer_name() -> str:
    try:
        import win32print
        return win32print.GetDefaultPrinter()
    except Exception:
        return ""


def _print_driver(printer_name: str) -> str:
    """Nome do driver da impressora ("" se nao for possivel descobrir)."""
    try:
        import win32print
        handle = win32print.OpenPrinter(printer_name)
        try:
            info = win32print.GetPrinter(handle, 2) or {}
            return str(info.get("pDriverName") or "")
        finally:
            win32print.ClosePrinter(handle)
    except Exception:
        return ""


def _use_gdi(printer_name: str) -> bool:
    """Escolhe o caminho de impressão correto.

    - Impressoras PDF/de arquivo ou comuns → GDI (renderiza imagem e o driver
      cuida da saída, abrindo o diálogo "salvar" quando for de arquivo).
    - Térmicas ESC/POS instalam drives de texto genérico (ou marcas/ESC/POS)
      → RAW, para manter o corte e o QR nativos da impressora.
    """
    low = printer_name.lower()
    pdf_hints = ("adobe", "pdf", "xps", "factura", "cute", "bullzip",
                 "novapdf", "dopdf", "print to", "onenote", "win2pdf")
    if any(k in low for k in pdf_hints):
        return True
    driver = _print_driver(printer_name).lower()
    thermal_hints = ("generic / text", "esc/pos", "tm-", "bematech", "elgin",
                     "daruma", "sweda", "gertec", "tanca", "xp-58", "p-58",
                     "bechtech", "pos-58", "pos58", "v58", "thermal")
    for hint in thermal_hints:
        if hint in low or hint in driver:
            return False
    return True


def _gdi_print_receipt(printer_name: str, text_bytes: bytes, paper_mm: int,
                       meta: dict) -> bool:
    """Envia o recibo (texto + QR Code) renderizado via GDI (GDI/WINSPOOL).

    O recibo é convertido em PDF real pelo Python (reportlab) e rasterizado
    pelo PyMuPDF; a página virada em imagem vai via StartDoc/StartPage/EndPage.
    É esse fluxo que faz impressoras PDF (ex.: Microsoft Print to PDF) exibir
    a janela "salvar como" — sem depender do driver Adobe.
    """
    import win32con
    import win32ui
    from PIL import Image, ImageWin

    text = text_bytes.decode("cp1252", errors="replace")
    qr_data = str(meta.get("qr_data") or "").strip()

    img = None
    try:
        pdf = ticket_to_pdf(text, qr_data, paper_mm)
        img = _render_pdf_first_page(pdf)
    except Exception as exc:
        print(f"[impressão GDI] PDF indisponível, usando preview: {exc}")
        img = None
    if img is None:
        png = ticket_preview_png(text, qr_data, width_mm=paper_mm,
                                 height_mm=200, scale=8)
        img = Image.open(io.BytesIO(png)).convert("RGB")

    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(printer_name)
    try:
        dpi_x = dc.GetDeviceCaps(win32con.LOGPIXELSX) or 600
        dpi_y = dc.GetDeviceCaps(win32con.LOGPIXELSY) or dpi_x
        off_x = dc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
        off_y = dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)
        page_w = dc.GetDeviceCaps(win32con.PHYSICALWIDTH) or int(210 / 25.4 * dpi_x)
        width_px = int(paper_mm / 25.4 * dpi_x)
        width_px = min(width_px, max(page_w - 2 * off_x, 100))
        height_px = int(img.height * width_px / img.width)
        dc.StartDoc("MasterPark — Recibo")
        dc.StartPage()
        dib = ImageWin.Dib(img)
        dib.draw(dc.GetSafeHdc(), (off_x, off_y, off_x + width_px,
                                   off_y + height_px))
        dc.EndPage()
        dc.EndDoc()
        return True
    except Exception:
        try:
            dc.AbortDoc()
        except Exception:
            pass
        raise
    finally:
        dc.DeleteDC()


def extract_ascii_barcode(text: str) -> tuple[str, str | None]:
    """Remove a(s) linha(s) do Code 39 em ASCII ('|' e espaços) do texto.

    Retorna (texto_sem_barras, barras). O barcode é redesenhado como barras
    proporcionais na imagem/PDF — em texto monoespaçado ele estoura a largura
    da folha e quebra, saindo "desconfigurado".
    """
    lines = text.split("\n")
    cleaned: list[str] = []
    bars: str | None = None
    for line in lines:
        s = line.strip()
        if len(s) >= 8 and set(s) <= {"|", " "}:
            if bars is None:
                bars = s
            continue
        cleaned.append(line)
    if not bars or len(bars) < 8:
        bars = None
    return "\n".join(cleaned), bars


def _code39_runs(bars: str) -> list[tuple[bool, int]]:
    """Converte o barcode ASCII em sequências (barra real vs espaço).

    Cada caractere '|' conta 1 unidade estreita e 3 unidades quando largo —
    os comprimentos das sequências já são as larguras em unidades.
    """
    if not bars:
        return []
    runs: list[tuple[bool, int]] = []
    prev, count = bars[0], 0
    for ch in bars:
        if ch == prev:
            count += 1
        else:
            runs.append((prev == "|", count))
            prev, count = ch, 1
    runs.append((prev == "|", count))
    return runs


def ticket_to_pdf(text: str, qr_data: str = "", paper_mm: int = 80,
                  height_mm: int = 200) -> bytes:
    """Gera o recibo como PDF real usando reportlab (conversão em Python).

    O Code 39 (em ASCII no texto do ticket) é extraído e desenhado como
    barras proporcionais abaixo do QR Code — em texto puro ele quebra e sai
    desconfigurado. Usado para imprimir em impressoras PDF com o Windows puro,
    sem depender do driver Adobe.
    """
    import io as _io
    import re
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import qr as rl_qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.pagesizes import mm
    from reportlab.pdfgen import canvas

    text, bars_ascii = extract_ascii_barcode(text)
    page_w = paper_mm * mm
    page_h = height_mm * mm
    reserve = 210.0 if bars_ascii else 0.0
    buf = _io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setTitle("MasterPark - Recibo")
    c.setFont("Courier", 8)
    char_w = 4.8  # Courier: ~0.6x o tamanho da fonte
    max_chars = max(8, int((page_w - 12) / char_w))
    x = 6
    y = page_h - 10
    line_h = 9
    for raw in (text.split("\n") or [""]):
        line = raw
        while len(line) > max_chars:
            c.drawString(x, y, line[:max_chars])
            line = line[max_chars:]
            y -= line_h
        c.drawString(x, y, line)
        y -= line_h
        if y < 40 + reserve:
            break
    if bars_ascii:
        _draw_code39_pdf(c, bars_ascii, page_w, 16)
        qr_y = 70
    else:
        qr_y = 8
    if qr_data:
        try:
            qr = rl_qr.QrCodeWidget(qr_data)
            box = 110 if bars_ascii else 120
            d = Drawing(box, box)
            d.add(qr)
            renderPDF.draw(d, c, (page_w - box) / 2, qr_y)
        except Exception as exc:
            c.setFont("Courier", 7)
            safe = re.sub(r"[^\x20-\x7e]", "?", str(exc))
            c.drawString(x, 20, f"[QR indisponivel: {safe}]")
    c.showPage()
    c.save()
    return buf.getvalue()


def _draw_code39_pdf(c, bars_ascii: str, page_w: float, y: float,
                     bar_h: float = 34.0, edge: float = 24.0) -> None:
    """Desenha o Code 39 como barras proporcionais (legível e sem quebra)."""
    runs = _code39_runs(bars_ascii)
    if not runs:
        return
    total = sum(n for _, n in runs)
    usable = max(page_w - 2 * edge, 1.0)
    module = min(0.6, usable / max(total, 1))
    if module <= 0:
        return
    x = (page_w - total * module) / 2
    for ink, n in runs:
        if ink:
            c.rect(x, y, n * module, bar_h, stroke=0, fill=1)
        x += n * module


def _render_pdf_first_page(pdf_bytes: bytes, dpi: int = 300):
    """Rasteriza a primeira página do PDF para imagem PIL RGB (PyMuPDF)."""
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    from PIL import Image

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[0]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


class WindowsGdiPrinter(PrinterAdapter):
    """Impressora comum do Windows (PDF, laser, jato de tinta...).

    Em vez de RAW ESC/POS, renderiza o recibo como imagem de ~58/80 mm de
    largura e manda via GDI; o driver/porta decide a saída (e impressoras de
    arquivo abrem o diálogo "salvar como").
    """

    def __init__(self, printer_name: str = "", paper_mm: int = 80):
        self.printer_name = printer_name or _default_printer_name()
        self.paper_mm = paper_mm or 80
        self.name = self.printer_name or "PRINTER (GDI)"

    def is_available(self) -> bool:
        try:
            import win32print
            names = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
            return self.printer_name in names or not self.printer_name
        except Exception:
            return False

    def print_ticket(self, text_bytes: bytes, codes_bytes: bytes = b"",
                     meta: dict | None = None) -> bool:
        try:
            return _gdi_print_receipt(self.printer_name, text_bytes,
                                      self.paper_mm, meta or {})
        except Exception as exc:
            print(f"[impressão GDI] falha: {exc}")
            return False

    def print_text(self, text: str) -> bool:
        try:
            return _gdi_print_receipt(self.printer_name,
                                      text.encode("cp1252", errors="replace"),
                                      self.paper_mm, {})
        except Exception as exc:
            print(f"[impressão GDI] falha: {exc}")
            return False

    def print_raw(self, bytes_data: bytes) -> bool:
        return self.print_text(bytes_data.decode("cp1252", errors="replace"))


class SimulatedPrinter(PrinterAdapter):
    """Salva a impressão como arquivo para fins de demonstração."""

    def __init__(self, printer_name: str = "DEMO"):
        self.printer_name = printer_name
        self.name = "SIMULADOR DEMO"

    def is_available(self) -> bool:
        return True

    def print_raw(self, bytes_data: bytes) -> bool:
        return self.print_text("(conteúdo gráfico)")

    def print_text(self, text: str) -> bool:
        PRINT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = PRINT_DIR / f"impressao_{stamp}.txt"
        path.write_text(text, encoding="utf-8")
        print(f"[IMPRESSÃO DEMO] arquivo salvo em: {path}")
        return True

    def print_ticket(self, text_bytes: bytes, codes_bytes: bytes = b"",
                     meta: dict | None = None) -> bool:
        """Salva o ticket simulado como .txt e o QR Code como .png."""
        PRINT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        meta = meta or {}
        number = meta.get("number") or "ticket"
        txt = PRINT_DIR / f"ticket_{number}_{stamp}.txt"
        txt.write_bytes(text_bytes)
        saved = str(txt)
        if meta.get("qr_data"):
            try:
                png = PRINT_DIR / f"ticket_{number}_{stamp}_qr.png"
                png.write_bytes(generate_qr_png(meta["qr_data"], box_size=6))
                saved += f"\n[IMPRESSÃO DEMO] QR Code: {png}"
            except Exception as exc:
                saved += f"\n[IMPRESSÃO DEMO] QR indisponível: {exc}"
        print(f"[IMPRESSÃO DEMO] {saved}")
        return True


class PrintingService:
    def __init__(self, printer_name: str = "", simulated: bool = False,
                 paper_mm: int = 80):
        self.printer_name = printer_name
        self.simulated = simulated
        self.paper_mm = paper_mm
        self._demo = SimulatedPrinter(printer_name or "DEMO")
        self._real = None

    def _resolve_name(self) -> str:
        """Nome real da impressora: o configurado, ou a padrão do Windows."""
        if self.printer_name:
            return self.printer_name
        try:
            import win32print
            return win32print.GetDefaultPrinter()
        except Exception:
            return ""

    def adapter(self) -> PrinterAdapter:
        """Impressora real configurada (ou a padrão do Windows).

        PDF/laser/jato → GDI (abre diálogo de salvar em impressoras de
        arquivo); térmicas ESC/POS → RAW, para preservar o fluxo nativo.
        """
        if self._real is None:
            name = self._resolve_name()
            if _use_gdi(name):
                self._real = WindowsGdiPrinter(name, self.paper_mm)
            else:
                self._real = WindowsThermalPrinter(name)
        return self._real

    def _pick(self, simulated: bool | None) -> PrinterAdapter:
        if simulated is None:
            simulated = self.simulated
        return self._demo if simulated else self.adapter()

    def get_active_kind(self) -> str:
        a = self.adapter()
        if isinstance(a, SimulatedPrinter):
            return "DEMO"
        return "REAL"

    # ------------------------------------------------------------------
    def render_ticket_entry(self, lot: dict, company: dict | None, ticket: dict,
                            show_prices: bool = False) -> str:
        c = company or {}
        lines = [
            "=" * 32,
            (lot.get("name") or "").center(32),
            (lot.get("address") or "").center(32),
            f"CNPJ: {c.get('cnpj') or '-'}",
            f"Telefone: {lot.get('phone') or '-'}",
            "=" * 32,
            "TICKET DE ESTACIONAMENTO",
            f"Ticket: {ticket.get('number')}",
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            f"Entrada: {ticket.get('entry_at', '')[:16]}",
            f"Placa: {ticket.get('plate') or '-'}",
            ticket.get("vehicle_category") and f"Categoria: {ticket.get('vehicle_category')}" or "",
            f"Cliente: {(ticket.get('customer_name') or 'Cliente não identificado')[:24]}",
            f"Vaga: {ticket.get('space_code') or '-'}",
        ]
        lines += ["", "Importante:  ", "Perdeu o ticket? Procure a administração.",
                  "Não nos responsabilizamos por objetos deixados no veículo.",
                  "Ao estacionar, você concorda com as regras abaixo:"]
        lines += [f"  1. Efêto somente com pagamento.",
                  "  2. Saídas bloqueadas em caso de não pagamento.",
                  "  3. Veículos sujeitos a verificação."]
        lines += ["=" * 32, "Apresente o QR Code ou o código de barras", ""]
        bars = code39_bars(ticket.get("barcode_data") or ticket.get("number") or "")
        code = str(ticket.get("barcode_data") or ticket.get("number") or "")
        if bars:
            lines += [bars, code.center(32)]
        lines += ["=" * 32, "", ""]
        return "\n".join([l for l in lines if l is not None])

    def ticket_codes(self, ticket: dict) -> bytes:
        """Bytes ESC/POS do QR Code gravado no ticket.

        O codigo de barras ja sai como texto (Code 39) em
        `render_ticket_entry`; aqui vao apenas os comandos de raster do QR.
        """
        payload = ticket.get("qr_data") or f"MP:TCK:{ticket.get('number') or ''}"
        if not payload.strip():
            return b""
        try:
            return qr_escpos(payload.strip())
        except Exception as exc:  # nunca impede a emissao do ticket
            print(f"[impressão] QR não gerado: {exc}")
            return b""

    def render_receipt(self, lot: dict, company: dict | None, ticket: dict,
                       preview: dict, paid: bool = True) -> str:
        c = company or {}
        total_min = preview.get("minutes", 0)
        h, m = divmod(total_min, 60)
        lines = [
            "=" * 32,
            (lot.get("name") or "").center(32),
            f"CNPJ: {c.get('cnpj') or '-'}",
            "----- COMPROVANTE DE SAÍDA -----",
            f"Ticket: {ticket.get('number')}",
            f"Placa: {ticket.get('plate') or '-'}",
            f"Cliente: {(ticket.get('customer_name') or 'Cliente não identificado')[:24]}",
            f"Entrada: {(ticket.get('entry_at') or '')[:16]}",
            f"Saída:   {(ticket.get('exit_at') or '')[:16]}",
            f"Permanência: {h}h{m:02d}",
            "-" * 32,
        ]
        if preview.get("discount_value"):
            lines.append(f"Valor original: {format_money(preview.get('base_value', 0))}")
            lines.append(f"Desconto:       {format_money(preview.get('discount_value', 0))}")
        lines.append(f"VALOR FINAL:    {format_money(preview.get('final_value', 0))}")
        if paid:
            lines += ["PAGO ✓", "=" * 32, "Muito obrigado pela preferência!", "", ""]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def print_ticket_entry(self, lot, company, ticket, simulated: bool | None = None) -> bool:
        text = self.render_ticket_entry(lot, company, ticket)
        codes = self.ticket_codes(ticket)
        printer = self._pick(simulated)
        return printer.print_ticket(
            text_block(text), codes,
            {"number": ticket.get("number"), "qr_data": ticket.get("qr_data")})

    def print_receipt(self, lot, company, ticket, preview, simulated: bool | None = None) -> bool:
        text = self.render_receipt(lot, company, ticket, preview)
        codes = self.ticket_codes(ticket)
        return self._pick(simulated).print_ticket(
            text_block(text), codes,
            {"number": ticket.get("number"), "qr_data": ticket.get("qr_data")})

    def preview_text(self, text: str) -> str:
        return text


def generate_qr_png(data: str, box_size: int = 8) -> bytes:
    import qrcode
    qr = qrcode.QRCode(box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_barcode_png(data: str) -> bytes:
    import barcode
    from barcode.writer import ImageWriter
    code = barcode.get("code128", data, writer=ImageWriter())
    buf = io.BytesIO()
    # write_text=False evita carregar a fonte TTF do pacote (que não é
    # embarcada no executável do PyInstaller e gera "cannot open resource")
    code.write(buf, options={"module_width": 0.25, "module_height": 10,
                             "write_text": False})
    return buf.getvalue()


def available_printers() -> list[str]:
    """Lista as impressoras instaladas no Windows (vazio se pywin32 falhar)."""
    try:
        import win32print
        names = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
        names += [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_CONNECTIONS)]
    except Exception:
        return []
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return sorted(out)


def ticket_preview_png(text: str, qr_data: str, width_mm: int = 80,
                       height_mm: int = 160, scale: int = 4) -> bytes:
    """Renderiza o ticket (texto + QR) em PNG para o preview do diálogo.

    Usa uma fonte monoespaçada do sistema para manter o alinhamento
    das colunas, que é o que torna o ticket legível.
    """
    from PIL import Image, ImageDraw, ImageFont

    px_w = int(width_mm * scale)
    px_h = int(height_mm * scale)
    img = Image.new("RGB", (px_w, px_h), "white")
    draw = ImageDraw.Draw(img)

    font = None
    for name in ("consola.ttf", "cour.ttf", "lucon.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(name, 11 * scale // 3)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    y = 4 * scale
    line_h = 13 * scale // 3
    text, bars_ascii = extract_ascii_barcode(text)
    reserve = (96 if bars_ascii else 70) * scale
    for line in text.split("\n"):
        draw.text((4 * scale, y), line, fill="black", font=font)
        y += line_h
        if y > px_h - reserve:
            break

    if qr_data:
        by = y + line_h
        try:
            import qrcode
            qr = qrcode.QRCode(border=2, box_size=1)
            qr.add_data(qr_data)
            qr.make(fit=True)
            m = qr.get_matrix()
            size = len(m)
            target = min(px_w - 16 * scale, (46 if bars_ascii else 60) * scale)
            s = max(1, target // size)
            off_x = (px_w - size * s) // 2
            for yy in range(size):
                for xx in range(size):
                    if m[yy][xx]:
                        draw.rectangle(
                            [off_x + xx * s, y + yy * s,
                             off_x + (xx + 1) * s - 1, y + (yy + 1) * s - 1],
                            fill="black")
            by = y + size * s + 6 * scale
        except Exception as exc:
            draw.text((4 * scale, y), f"[QR: {exc}]", fill="red", font=font)
    else:
        by = y + line_h

    if bars_ascii and by + 22 * scale <= px_h:
        _draw_code39_pil(draw, bars_ascii, px_w, by, scale)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _draw_code39_pil(draw, bars_ascii: str, px_w: int, y: int,
                     scale: int, bar_h: int | None = None) -> None:
    """Desenha o Code 39 como barras proporcionais centralizadas."""
    runs = _code39_runs(bars_ascii)
    if not runs:
        return
    total = sum(n for _, n in runs)
    edge = 8 * scale
    usable = max(px_w - 2 * edge, 1)
    unit = max(1, min(scale // 2, usable // max(total, 1)))
    width = total * unit
    x = (px_w - width) // 2
    bar_height = bar_h or 20 * scale
    for ink, n in runs:
        if ink:
            w = n * unit
            draw.rectangle([x, y, x + w - 1, y + bar_height - 1], fill="black")
        x += n * unit