"""Dialog de login do MasterPark."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from app.services.auth import AuthError
from app.ui.theme import PRIMARY


class LoginDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.user = None
        self.setWindowTitle("MasterPark — Login")
        self.setFixedSize(420, 460)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 36, 40, 36)
        outer.setAlignment(Qt.AlignCenter)

        brand = QLabel("MasterPark")
        brand.setObjectName("appName")
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet(
            "font-size:34px; font-weight:900; color:%s; letter-spacing:1px;" % PRIMARY)
        sub = QLabel("Sistema de Gestão de Estacionamentos")
        sub.setObjectName("appSub")
        sub.setAlignment(Qt.AlignCenter)
        outer.addWidget(brand)
        outer.addWidget(sub)
        outer.addSpacing(26)

        self.box_user = QLineEdit()
        self.box_user.setPlaceholderText("Usuário")
        self.box_pass = QLineEdit()
        self.box_pass.setPlaceholderText("Senha")
        self.box_pass.setEchoMode(QLineEdit.Password)
        outer.addWidget(self.box_user)
        outer.addSpacing(8)
        outer.addWidget(self.box_pass)
        outer.addSpacing(18)

        self.btn = QPushButton("Entrar")
        self.btn.setObjectName("primary")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setMinimumHeight(42)
        self.btn.clicked.connect(self.try_login)
        outer.addWidget(self.btn)

        self.err = QLabel("")
        self.err.setStyleSheet("color:%s; font-weight:600;" % "#EF4444")
        self.err.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.err)
        outer.addStretch(1)

        foot = QLabel("v" + self.ctx.version)
        foot.setObjectName("appSub")
        foot.setAlignment(Qt.AlignCenter)
        outer.addWidget(foot)

        self.box_user.returnPressed.connect(self.try_login)
        self.box_pass.returnPressed.connect(self.try_login)
        self.box_user.setFocus()

    def try_login(self):
        self.err.setText("")
        username = self.box_user.text().strip()
        password = self.box_pass.text()
        if not username or not password:
            self.err.setText("Informe usuário e senha.")
            return
        try:
            self.user = self.ctx.auth.login(username, password,
                                            terminal="Terminal II")
            self.accept()
        except AuthError as exc:
            self.err.setText(str(exc))
            self.box_pass.selectAll()
        except PermissionError as exc:
            self.err.setText(str(exc))