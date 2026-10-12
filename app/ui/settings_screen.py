"""Configurações da aplicação (dados da empresa, tarifas, usuários, sistema)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout,
                               QLineEdit, QSpinBox, QTabWidget, QVBoxLayout,
                               QWidget)

from app.domain.models import cents
from app.ui.widgets import (Card, error, info, make_label, page_header,
                            primary_button, warn)


class SettingsScreen(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Configurações",
                                  "Empresa, tarifas, usuários e sistema"))

        tabs = QTabWidget()
        tabs.addTab(self._build_company(), "Empresa")
        tabs.addTab(self._build_tariffs(), "Tarifas")
        tabs.addTab(self._build_system(), "Sistema")
        tabs.addTab(self._build_users(), "Usuários")
        tabs.addTab(self._build_license(), "Licença")
        lay.addWidget(tabs, 1)

    def on_show(self):
        self._reload()

    # ------------------------------------------------------------------
    def _build_company(self):
        card = Card("Dados da empresa")
        self.f_name = QLineEdit()
        self.f_legal = QLineEdit()
        self.f_cnpj = QLineEdit()
        self.f_phone = QLineEdit()
        self.f_email = QLineEdit()
        self.f_addr = QLineEdit()
        form = QFormLayout()
        form.addRow("Nome fantasia", self.f_name)
        form.addRow("Razão social", self.f_legal)
        form.addRow("CNPJ", self.f_cnpj)
        form.addRow("Telefone", self.f_phone)
        form.addRow("E-mail", self.f_email)
        form.addRow("Endereço", self.f_addr)
        card.body.addLayout(form)
        btn = primary_button("Salvar empresa", "primary")
        btn.clicked.connect(self.save_company)
        card.body.addWidget(btn)
        return card

    def _build_tariffs(self):
        card = Card("Tarifa padrão")
        self.f_initial = QLineEdit()
        self.f_hour = QLineEdit()
        self.f_daily = QLineEdit()
        self.f_free = QSpinBox(); self.f_free.setSuffix(" min"); self.f_free.setRange(0, 120)
        self.f_fraction = QSpinBox(); self.f_fraction.setSuffix(" min"); self.f_fraction.setRange(10, 120)
        form = QFormLayout()
        form.addRow("Primeiros minutos grátis", self.f_free)
        form.addRow("Primeira hora (R$)", self.f_initial)
        form.addRow("Fração/hora (R$)", self.f_hour)
        form.addRow("Frações de", self.f_fraction)
        form.addRow("Diária (R$)", self.f_daily)
        card.body.addLayout(form)
        btn = primary_button("Aplicar tarifas", "primary")
        btn.clicked.connect(self.save_tariffs)
        card.body.addWidget(btn)
        return card

    def _build_system(self):
        card = Card("Sistema")
        self.chk_print = QCheckBox("Imprimir ticket automaticamente na entrada")
        self.chk_demo = QCheckBox("Modo demonstração (dados fictícios)")
        self.f_printer = QLineEdit()
        self.f_retention = QSpinBox(); self.f_retention.setRange(7, 365); self.f_retention.setSuffix(" dias")
        self.f_attempts = QSpinBox(); self.f_attempts.setRange(3, 10)
        self.f_timeout = QSpinBox(); self.f_timeout.setRange(5, 480); self.f_timeout.setSuffix(" min")
        form = QFormLayout()
        form.addRow("Impressora (térmica)", self.f_printer)
        form.addRow("Reter backups por", self.f_retention)
        form.addRow("Tentativas de login", self.f_attempts)
        form.addRow("Timeout de sessão", self.f_timeout)
        card.body.addLayout(form)
        card.body.addWidget(self.chk_print)
        card.body.addWidget(self.chk_demo)
        btn = primary_button("Salvar sistema", "primary")
        btn.clicked.connect(self.save_system)
        card.body.addWidget(btn)
        return card

    def _build_users(self):
        card = Card("Novo usuário")
        self.u_user = QLineEdit()
        self.u_name = QLineEdit()
        self.u_pass = QLineEdit()
        self.u_pass.setEchoMode(QLineEdit.Password)
        self.u_role = QComboBox()
        from app.domain.permissions import ROLES
        for code in ROLES:
            self.u_role.addItem(ROLES[code][0], code)
        form = QFormLayout()
        form.addRow("Usuário", self.u_user)
        form.addRow("Nome", self.u_name)
        form.addRow("Função", self.u_role)
        form.addRow("Senha", self.u_pass)
        card.body.addLayout(form)
        btn = primary_button("Criar usuário", "primary")
        btn.clicked.connect(self.create_user)
        card.body.addWidget(btn)
        return card

    def _build_license(self):
        card = Card("Licença")
        self.lbl_lic = make_label("-", "statLabel")
        card.body.addWidget(self.lbl_lic)
        btn = primary_button("Ativar / renovar licença", "primary")
        btn.clicked.connect(self.open_activation)
        card.body.addWidget(btn)
        return card

    # ------------------------------------------------------------------
    def _reload(self):
        company = self.ctx.company or {}
        self.f_name.setText(company.get("name", ""))
        self.f_legal.setText(company.get("legal_name", ""))
        self.f_cnpj.setText(company.get("cnpj", ""))
        self.f_phone.setText(company.get("phone", ""))
        self.f_email.setText(company.get("email", ""))
        self.f_addr.setText(company.get("address", ""))
        self.chk_print.setChecked(self.ctx.settings.auto_print_ticket)
        self.f_printer.setText(self.ctx.settings.printer_name)
        self.f_retention.setValue(self.ctx.settings.backup_retention_days)
        self.f_attempts.setValue(self.ctx.settings.failed_login_limit)
        self.f_timeout.setValue(self.ctx.settings.session_timeout_minutes)
        self.chk_demo.setChecked(
            (self.ctx.settings_repo.get("demo_mode") or "") == "1")
        cur = self.ctx.license.current()
        if cur:
            self.lbl_lic.setText(self.ctx.license.describe(cur))
        else:
            self.lbl_lic.setText("Sem licença ativa.")
        # carrega tarifa padrão
        if self.ctx.lot:
            tariffs = self.ctx.tickets.tariffs.list(self.ctx.lot["id"])
            if tariffs:
                rules = self.ctx.tickets.tariffs.rules(tariffs[0]["id"])
                for r in rules:
                    if r["rule_type"] == "FIXED" and r["minutes_from"] == 0:
                        self.f_free.setValue(r["minutes_to"] or 0)
                    elif r["rule_type"] == "PER_FRACTION":
                        self.f_initial.setText(f"{r['value'] / 100:.2f}")
                        self.f_fraction.setValue(r["minutes_to"] or 30)
                    elif r["rule_type"] == "MAX_DAILY":
                        self.f_daily.setText(f"{r['value'] / 100:.2f}")

    # ------------------------------------------------------------------
    def save_company(self):
        self.ctx.auth.require_permission("CONFIG_MANAGE")
        data = dict(name=self.f_name.text().strip(),
                    legal_name=self.f_legal.text().strip(),
                    cnpj=self.f_cnpj.text().strip(),
                    phone=self.f_phone.text().strip(),
                    email=self.f_email.text().strip(),
                    address=self.f_addr.text().strip())
        self.ctx.companies.upsert(data)
        self.ctx.refresh()
        info(self, "OK", "Empresa salva.")

    def save_tariffs(self):
        self.ctx.auth.require_permission("TARIFF_MANAGE")
        if not self.ctx.lot:
            warn(self, "Atenção", "Configure a unidade primeiro.")
            return
        try:
            initial = cents(self.f_initial.text())
            hourly = cents(self.f_hour.text())
            daily = cents(self.f_daily.text())
        except ValueError:
            warn(self, "Valores", "Valores em formato inválido.")
            return
        tariffs = self.ctx.tickets.tariffs
        actives = tariffs.list(self.ctx.lot["id"])
        if not actives:
            warn(self, "Atenção", "Nenhuma tarifa configurada. Use o assistente.")
            return
        tid = actives[0]["id"]
        tariffs.clear_rules(tid)
        from app.services.tariff import build_default_rules
        for r in build_default_rules(initial, hourly, self.f_fraction.value(),
                                     self.f_free.value(), daily):
            tariffs.add_rule(tid, r["minutes_from"], r["minutes_to"],
                             r["rule_type"], r["value"], r["sort"])
        info(self, "OK", "Tarifas aplicadas.")

    def save_system(self):
        self.ctx.auth.require_permission("CONFIG_MANAGE")
        self.ctx.save_settings(
            auto_print_ticket=self.chk_print.isChecked(),
            printer_name=self.f_printer.text().strip(),
            backup_retention_days=self.f_retention.value(),
            failed_login_limit=self.f_attempts.value(),
            session_timeout_minutes=self.f_timeout.value())
        self.ctx.auth.failed_limit = self.ctx.settings.failed_login_limit
        self.ctx.auth.timeout_minutes = self.ctx.settings.session_timeout_minutes
        if self.chk_demo.isChecked() and (self.ctx.settings_repo.get("demo_mode") or "") != "1":
            from app.services.demo import setup_demo
            setup_demo(self.ctx.db)
            self.ctx.refresh()
        elif not self.chk_demo.isChecked():
            self.ctx.settings_repo.set("demo_mode", "0")
        from app.services.printing import PrintingService
        self.ctx.printing = PrintingService(self.ctx.settings.printer_name)
        info(self, "OK", "Configurações salvas.")

    def create_user(self):
        user = self.ctx.auth.require_permission("USER_MANAGE")
        username = self.u_user.text().strip()
        name = self.u_name.text().strip()
        password = self.u_pass.text()
        role = self.u_role.currentData()
        if username and name and len(password) >= 8:
            try:
                from app.services.auth import AuthError
                self.ctx.auth.create_user(username, name, password, role)
                info(self, "OK", f"Usuário '{username}' criado.")
                self.u_user.clear(); self.u_pass.clear(); self.u_name.clear()
            except AuthError as exc:
                warn(self, "Atenção", str(exc))
        else:
            warn(self, "Validação", "Preencha usuário, nome e senha (mín. 8).")

    def open_activation(self):
        from app.ui.activation import ActivationDialog
        dlg = ActivationDialog(self.ctx, self)
        if dlg.exec() and dlg.activated:
            info(self, "Licença", "Licença ativada com sucesso.")
            self._reload()