"""Diálogo de seleção de impressora, com preview do ticket."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout,
                               QLabel, QScrollArea, QVBoxLayout, QWidget)

from app.services.printing import (available_printers, ticket_preview_png)
from app.ui.theme import DANGER
from app.ui.widgets import Card, make_label, primary_button

PAPER = [("58 mm", 58, 160), ("80 mm", 80, 200)]


class PrintDialog(QDialog):
    """Escolha de impressora/largura antes de emitir o ticket.

    Retorna `dict(printer_name=str, paper_mm=int, simulated=bool)` em
    `accepted`, ou `None` se o usuário cancelar.
    """

    def __init__(self, ctx, lot, company, ticket, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.lot = lot
        self.company = company
        self.ticket = ticket
        self.setWindowTitle("Imprimir ticket")
        self.setModal(True)
        self.resize(660, 720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        head = make_label("Imprimir ticket", "h2")
        outer.addWidget(head)
        sub = make_label(
            f"Ticket {ticket.get('number', '—')} · {ticket.get('plate', '—')}", "subtitle")
        outer.addWidget(sub)

        # ------------------------------------------------- impressora
        card = Card("Impressora")
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(make_label("Impressora:", "label"))
        self.cmb = QComboBox()
        self.printers = available_printers()
        self.cmb.addItem("Padrão do Windows (automática)")
        for p in self.printers:
            self.cmb.addItem(p)
        current_name = getattr(getattr(ctx, "settings", None), "printer_name", "") or ""
        if current_name:
            idx = self.cmb.findText(current_name)
            if idx >= 0:
                self.cmb.setCurrentIndex(idx)
        self.cmb.currentIndexChanged.connect(self._update_preview)
        row.addWidget(self.cmb, 1)
        card.body.addLayout(row)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(make_label("Largura:", "label"))
        self.cmb_paper = QComboBox()
        for name, mm, _h in PAPER:
            self.cmb_paper.addItem(name, mm)
        if not self.printers:
            self.cmb_paper.setCurrentIndex(0)
        self.cmb_paper.currentIndexChanged.connect(self._update_preview)
        row2.addWidget(self.cmb_paper)

        self.chk_sim = QCheckBox("Simular (não enviar para a impressora)")
        self.chk_sim.setChecked(not self.printers)
        self.chk_sim.toggled.connect(self._update_preview)
        row2.addWidget(self.chk_sim, 1)
        card.body.addLayout(row2)

        if not self.printers:
            notice = make_label(
                "Nenhuma impressora encontrada — o modo simular grava o ticket "
                "e o QR Code em arquivo.", "subtitle")
            notice.setStyleSheet(f"color:{DANGER};")
            notice.setWordWrap(True)
            card.body.addWidget(notice)
        outer.addWidget(card)

        # ---------------------------------------------------- preview
        prev = Card("Pré-visualização")
        self.lbl_info = make_label("", "subtitle")
        self.lbl_info.setWordWrap(True)
        prev.body.addWidget(self.lbl_info)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.holder = QWidget()
        self.holder.setStyleSheet("background:#FFFFFF;")
        hlay = QVBoxLayout(self.holder)
        hlay.setContentsMargins(10, 10, 10, 10)
        self.lbl_img = QLabel()
        self.lbl_img.setAlignment(Qt.AlignCenter)
        hlay.addWidget(self.lbl_img)
        area.setWidget(self.holder)
        prev.body.addWidget(area, 1)
        outer.addWidget(prev, 1)

        # ------------------------------------------------------ acoes
        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = primary_button("Cancelar")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        self.btn_ok = primary_button("🖨  Imprimir")
        self.btn_ok.clicked.connect(self.accept)
        actions.addWidget(self.btn_ok)
        outer.addLayout(actions)

        self._update_preview()

    # ------------------------------------------------------------------
    def _paper_mm(self) -> int:
        return int(self.cmb_paper.currentData() or 80)

    def _printer_name(self) -> str:
        text = self.cmb.currentText()
        return "" if text.startswith("Padrão do Windows") else text

    def _update_preview(self):
        mm = self._paper_mm()
        sim = self.chk_sim.isChecked()
        name = self._printer_name()
        kind = "Simulação (arquivo)" if sim else (name or "Padrão do Windows")
        self.lbl_info.setText(
            f"Destino: <b>{kind}</b> · Papel <b>{mm} mm</b> · "
            f"QR Code e código de barras incluídos.")
        try:
            text = self.ctx.printing.render_ticket_entry(self.lot, self.company, self.ticket)
        except Exception as exc:
            self.lbl_img.setText(f"Erro ao gerar o ticket: {exc}")
            return
        qr_data = self.ticket.get("qr_data") or ""
        try:
            data = ticket_preview_png(text, qr_data, width_mm=mm)
            self.lbl_img.setPixmap(QPixmap.fromImage(_pil_to_qimage(data)))
        except Exception as exc:
            self.lbl_img.setText(f"Erro no preview: {exc}")

    def result(self) -> dict:
        return {"printer_name": self._printer_name(),
                "paper_mm": self._paper_mm(),
                "simulated": self.chk_sim.isChecked()}


def _pil_to_qimage(data: bytes):
    """Converte PNG (bytes) em QImage sem depender de arquivos temporários."""
    from PySide6.QtGui import QImage
    return QImage.fromData(data)


def ask_print(ctx, lot, company, ticket, parent=None) -> dict | None:
    """Abre o diálogo e devolve a escolha, ou None se cancelado."""
    dlg = PrintDialog(ctx, lot, company, ticket, parent)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.result()
