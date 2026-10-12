"""Tela de ativação de licença (primeira execução e renovações)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFileDialog, QLabel, QLineEdit,
                               QPushButton, QTextEdit, QVBoxLayout)

from app.services.licensing import LicenseError
from app.core.config import detect_machine_id


class ActivationDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.activated = False
        self.setWindowTitle("MasterPark — Ativação")
        self.setFixedSize(520, 560)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(12)

        brand = QLabel("Ativação de Licença")
        brand.setStyleSheet("font-size:24px; font-weight:900;")
        lay.addWidget(brand)
        note = QLabel("Informe o arquivo de licença (.lic) fornecido pelo fabricante. "
                      "Funciona também sem internet (ativação offline).")
        note.setObjectName("appSub")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addSpacing(6)

        lay.addWidget(QLabel("Instalação (máquina):"))
        self.lbl_hw = QLabel(detect_machine_id())
        self.lbl_hw.setObjectName("chip")
        self.lbl_hw.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.lbl_hw)
        lay.addSpacing(6)

        lay.addWidget(QLabel("Chave de licença (PARK-XXXX-XXXX-XXXX-XXXX):"))
        self.box_key = QLineEdit()
        self.box_key.setPlaceholderText("PARK-XXXX-XXXX-XXXX-XXXX")
        lay.addWidget(self.box_key)
        lay.addSpacing(4)

        btn_file = QPushButton("Carregar arquivo .lic")
        btn_file.clicked.connect(self.load_file)
        lay.addWidget(btn_file)

        lay.addWidget(QLabel("— ou ativação offline —"))
        lay.addWidget(QLabel("Código de ativação (gerado pelo fabricante):"))
        self.box_code = QLineEdit()
        self.box_code.setPlaceholderText("Cole aqui o código de ativação")
        lay.addWidget(self.box_code)
        lay.addSpacing(4)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        lay.addWidget(self.log)

        self.btn_activate = QPushButton("Ativar")
        self.btn_activate.setObjectName("primary")
        self.btn_activate.setMinimumHeight(42)
        self.btn_activate.clicked.connect(self.try_activate)
        lay.addWidget(self.btn_activate)

        self.err = QLabel("")
        self.err.setStyleSheet("color:#EF4444; font-weight:600;")
        self.err.setWordWrap(True)
        lay.addWidget(self.err)

        # se houver licença ativa, oferece renovar o arquivo
        cur = ctx.license.current()
        if cur and cur.get("status") == "ATIVA":
            self.log.append("Licença atualmente ATIVA. Use esta tela para renovar.")

    # ------------------------------------------------------------------
    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar licença",
                                              "", "Licença (*.lic *.txt);;Todos (*)")
        if not path:
            return
        try:
            raw = Path(path).read_text(encoding="utf-8")
            payload = self.ctx.license.validate_license_file(raw)
            if payload.get("lifetime"):
                validade = "validade VITALÍCIA (nunca expira)"
            else:
                validade = f"até {payload.get('expires_at')}"
            self.log.append(f"Licença válida: {payload.get('customer_name')} "
                            f"({payload.get('license_key')}) {validade}")
            self.box_key.setText(payload.get("license_key", ""))
            self._pending_raw = raw
        except LicenseError as exc:
            self.err.setText(str(exc))

    def try_activate(self):
        self.err.setText("")
        key = self.box_key.text().strip()
        code = self.box_code.text().strip()
        try:
            if code:
                self.ctx.license.activate_offline(key, code)
                self.activated = True
                self.log.append("Ativada via código offline com sucesso.")
            else:
                raw = getattr(self, "_pending_raw", "")
                if not raw:
                    raise LicenseError("Carregue o arquivo .lic ou cole o código offline.")
                self.ctx.license.activate(raw)
                self.activated = True
                self.log.append("Licença ativada com sucesso.")
            cur = self.ctx.license.current()
            if cur:
                self.log.append(self.ctx.license.describe(cur))
            self.accept()
        except LicenseError as exc:
            self.err.setText(str(exc))