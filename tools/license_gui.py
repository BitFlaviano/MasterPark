"""Gerador de Licenças MasterPark — interface gráfica (PySide6).

Uso:
  python tools/license_gui.py

Funcionalidades:
  - criar arquivos de licença (.lic) assinados com a chave privada
  - gerar códigos de ativação offline (chave + hardware)
  - gerar/embutir o par de chaves RSA
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QPushButton,
                               QSpinBox, QTabWidget, QTextEdit, QVBoxLayout,
                               QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_license import (OUT_DIR, activation_code_str, create_license,
                              embed_public_key, load_or_create_keys)

PLANOS = ["STARTER", "PROFESSIONAL", "BUSINESS", "ENTERPRISE"]
DURACOES = [("1", "1 ano"), ("2", "2 anos"), ("3", "3 anos"),
            ("vida", "Vitalícia"), ("dias", "Personalizada (dias)")]
FEATURES = ["BACKUP_MANAGE", "REPORT_VIEW", "AUDIT_VIEW", "MULTI_CASH",
            "LPR_CAMERA", "MONTHLY_PAYMENTS"]


class LicenseGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Licenças MasterPark")
        self.resize(560, 620)

        tabs = QTabWidget()
        tabs.addTab(self._build_license_tab(), "Licença")
        tabs.addTab(self._build_activation_tab(), "Ativação")
        tabs.addTab(self._build_keys_tab(), "Chaves")
        self.setCentralWidget(tabs)

    # ------------------------------------------------------------------
    def _build_license_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.ed_cliente = QLineEdit()
        self.ed_cliente.setPlaceholderText("Razão social do cliente (obrigatório)")
        form.addRow("Cliente", self.ed_cliente)

        self.ed_cnpj = QLineEdit()
        self.ed_cnpj.setPlaceholderText("00.000.000/0000-00")
        form.addRow("CNPJ", self.ed_cnpj)

        self.cb_plano = QComboBox()
        self.cb_plano.addItems(PLANOS)
        form.addRow("Plano", self.cb_plano)

        self.cb_duracao = QComboBox()
        for value, label in DURACOES:
            self.cb_duracao.addItem(label, value)
        self.cb_duracao.currentIndexChanged.connect(self._toggle_dias)
        form.addRow("Duração", self.cb_duracao)

        self.spin_dias = QSpinBox()
        self.spin_dias.setRange(1, 3650)
        self.spin_dias.setValue(365)
        self.spin_dias.setEnabled(False)
        form.addRow("Dias", self.spin_dias)

        self.spin_term = QSpinBox()
        self.spin_term.setRange(1, 999)
        self.spin_term.setValue(1)
        form.addRow("Terminais", self.spin_term)

        self.spin_vagas = QSpinBox()
        self.spin_vagas.setRange(0, 100000)
        self.spin_vagas.setValue(0)
        form.addRow("Vagas", self.spin_vagas)

        self.ed_versao = QLineEdit("1.0.0")
        form.addRow("Versão", self.ed_versao)

        self.ed_features = QLineEdit()
        self.ed_features.setPlaceholderText("separadas por vírgula (opcional)")
        form.addRow("Recursos", self.ed_features)

        self._feature_checks: list[QCheckBox] = []
        feat_row = QHBoxLayout()
        for f in FEATURES:
            cb = QCheckBox(f)
            feat_row.addWidget(cb)
            self._feature_checks.append(cb)
        form.addRow("", feat_row)

        self.ed_chave = QLineEdit()
        self.ed_chave.setPlaceholderText("em branco gera automaticamente")
        form.addRow("Chave", self.ed_chave)

        bottom = QHBoxLayout()
        btn = QPushButton("Gerar licença")
        btn.setStyleSheet("font-weight:800; padding:8px 14px;")
        btn.clicked.connect(self._do_create)
        bottom.addWidget(btn)
        self.btn_abrir = QPushButton("Abrir pasta de licenças")
        self.btn_abrir.setEnabled(False)
        self.btn_abrir.clicked.connect(self._open_out_dir)
        bottom.addWidget(self.btn_abrir)
        bottom.addStretch(1)

        self.lbl_result = QLabel("")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setTextInteractionFlags(Qt.TextSelectableByMouse)

        outer = QVBoxLayout()
        outer.addWidget(page)
        outer.addLayout(bottom)
        outer.addWidget(self.lbl_result)
        outer.addStretch(1)
        wrap = QWidget()
        wrap.setLayout(outer)
        return wrap

    def _toggle_dias(self):
        self.spin_dias.setEnabled(self.cb_duracao.currentData() == "dias")

    def _collect_features(self) -> list[str]:
        marcados = [c.text() for c in self._feature_checks if c.isChecked()]
        digitados = [f.strip().upper()
                     for f in self.ed_features.text().split(",") if f.strip()]
        vistos, out = set(), []
        for f in marcados + digitados:
            if f and f not in vistos:
                vistos.add(f)
                out.append(f)
        return out

    def _do_create(self):
        cliente = self.ed_cliente.text().strip()
        if not cliente:
            QMessageBox.warning(self, "Atenção", "Informe o nome do cliente.")
            self.ed_cliente.setFocus()
            return
        duracao = self.cb_duracao.currentData()
        args = argparse.Namespace(
            cliente=cliente, cnpj=self.ed_cnpj.text().strip(),
            plano=self.cb_plano.currentText(),
            terminais=str(self.spin_term.value()),
            vagas=str(self.spin_vagas.value()),
            versao=self.ed_versao.text().strip() or "1.0.0",
            feat=self._collect_features(),
            chave=self.ed_chave.text().strip(),
            duracao="" if duracao == "dias" else duracao,
            validade=str(self.spin_dias.value()) if duracao == "dias" else "",
        )
        try:
            out = create_license(args)
        except SystemExit as exc:
            QMessageBox.warning(self, "Atenção", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        try:
            raw = json.loads(out.read_text(encoding="utf-8"))["payload"]
        except Exception:
            raw = {}
        linhas = [
            f"Arquivo: {out.name}",
            f"Chave: {raw.get('license_key', '')}",
            f"Cliente: {raw.get('customer_name', '')}",
            f"Plano: {raw.get('plan', '')} • terminais {raw.get('terminals', '')} • vagas {raw.get('spaces', '')}",
            f"Duração: {raw.get('duracao', '')}"
            + (" (nunca expira)" if raw.get("lifetime") else f" — expira em {raw.get('expires_at', '')[:10]}"),
            f"Recursos: {', '.join(raw.get('features') or []) or '-'}",
        ]
        self.lbl_result.setText("\n".join(linhas))
        self.btn_abrir.setEnabled(True)
        QMessageBox.information(self, "Licença criada",
                                f"Licença salva em:\n{out}")

    def _open_out_dir(self):
        try:
            os_startfile = __import__("os").startfile
        except AttributeError:
            os_startfile = None
        if os_startfile:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            os_startfile(str(OUT_DIR))
        else:
            QMessageBox.information(self, "Pasta", str(OUT_DIR))

    # ------------------------------------------------------------------
    def _build_activation_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.ed_act_chave = QLineEdit()
        self.ed_act_chave.setPlaceholderText("Chave PARK-XXXX-XXXX-XXXX-XXXX")
        form.addRow("Chave", self.ed_act_chave)

        self.ed_act_hw = QLineEdit()
        self.ed_act_hw.setPlaceholderText("Identificador da instalação (hw anchor)")
        form.addRow("Hardware", self.ed_act_hw)

        self.ed_act_code = QTextEdit()
        self.ed_act_code.setReadOnly(True)
        form.addRow("Código", self.ed_act_code)

        bottom = QHBoxLayout()
        btn = QPushButton("Gerar código de ativação")
        btn.setStyleSheet("font-weight:800; padding:8px 14px;")
        btn.clicked.connect(self._do_activation)
        bottom.addWidget(btn)
        copy = QPushButton("Copiar código")
        copy.setStyleSheet("padding:8px 14px;")
        copy.clicked.connect(lambda: self._copy(self.ed_act_code.toPlainText()))
        bottom.addWidget(copy)
        bottom.addStretch(1)

        outer = QVBoxLayout()
        outer.addWidget(page)
        outer.addLayout(bottom)
        outer.addStretch(1)
        wrap = QWidget()
        wrap.setLayout(outer)
        return wrap

    def _do_activation(self):
        chave = self.ed_act_chave.text().strip()
        hw = self.ed_act_hw.text().strip()
        if not chave or not hw:
            QMessageBox.warning(self, "Atenção", "Informe chave e hardware.")
            return
        try:
            code = activation_code_str(chave, hw)
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            return
        self.ed_act_code.setPlainText(code)
        QApplication.clipboard().setText(code)

    # ------------------------------------------------------------------
    def _build_keys_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lbl = QLabel(
            "Gera (se não existirem) as chaves RSA em tools/keys e embute a\n"
            "chave pública em app/core/config.py (DEFAULT_PUBLIC_KEY).\n\n"
            "A chave privada NUNCA deve ir para o cliente.")
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(lbl)
        btn = QPushButton("Gerar par de chaves e embutir pública")
        btn.setStyleSheet("font-weight:800; padding:8px 14px;")
        btn.clicked.connect(self._do_genkeys)
        lay.addWidget(btn)
        lay.addStretch(1)
        return page

    def _do_genkeys(self):
        try:
            private, pub = load_or_create_keys()
            embed_public_key(pub)
            QMessageBox.information(
                self, "Chaves",
                "Par de chaves verificado/criado e chave pública embutida "
                "em app/core/config.py." if pub else "Feito.")
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))

    @staticmethod
    def _copy(text: str):
        QApplication.clipboard().setText(text)


def main() -> int:
    app = QApplication(sys.argv)
    win = LicenseGui()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())