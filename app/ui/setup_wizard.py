"""Assistente de configuração inicial (primeira execução)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QSpinBox, QVBoxLayout, QWizard, QWizardPage)

from app.core.security import PasswordService
from app.domain.models import cents
from app.repositories import LotRepo, SectorRepo, SpaceRepo
from app.repositories.operation import TariffRepo
from app.services.tariff import build_default_rules


def _wire_complete(page, *widgets):
    """Reavalia isComplete quando qualquer campo muda (habilita Avançar/Voltar)."""
    for w in widgets:
        if isinstance(w, QLineEdit):
            w.textChanged.connect(page.completeChanged)
        elif isinstance(w, QSpinBox):
            w.valueChanged.connect(page.completeChanged)
        elif isinstance(w, QCheckBox):
            w.stateChanged.connect(page.completeChanged)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(page.completeChanged)


def ask_setup_mode() -> str:
    """Pergunta como iniciar o sistema (demo ou assistente completo)."""
    box = QDialog()
    box.setWindowTitle("MasterPark — Bem-vindo")
    box.setFixedSize(520, 240)
    lay = QVBoxLayout(box)
    lay.addWidget(QLabel("Bem-vindo ao MasterPark!"))
    lay.addWidget(QLabel(
        "Este é o assistente de configuração inicial. Você pode configurar "
        "manualmente (empresa, vagas, tarifas, caixa, usuário) ou carregar "
        "dados de demonstração para conhecer o sistema imediatamente.",
        objectName="appSub") if False else QLabel(
        "Você pode configurar o estacionamento manualmente ou carregar dados "
        "de demonstração para conhecer o sistema imediatamente."))
    btn_wizard = QPushButton("Configurar agora (assistente)")
    btn_wizard.setObjectName("primary")
    btn_wizard.clicked.connect(lambda: (setattr(box, "_mode", "wizard"), box.accept()))
    btn_demo = QPushButton("Carregar dados de demonstração")
    btn_demo.clicked.connect(lambda: (setattr(box, "_mode", "demo"), box.accept()))
    lay.addWidget(btn_wizard)
    lay.addWidget(btn_demo)
    box.exec()
    mode = getattr(box, "_mode", None)
    box.deleteLater()
    return mode


class CompanyPage(QWizardPage):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setTitle("Dados da empresa")
        self.setSubTitle("Estas informações aparecem nos tickets.")
        self.ctx = ctx
        form = QFormLayout(self)
        self.f_name = QLineEdit()
        self.f_legal_name = QLineEdit()
        self.f_cnpj = QLineEdit()
        self.f_address = QLineEdit()
        self.f_phone = QLineEdit()
        self.f_email = QLineEdit()
        form.addRow("Nome fantasia", self.f_name)
        form.addRow("Razão social", self.f_legal_name)
        form.addRow("CNPJ", self.f_cnpj)
        form.addRow("Endereço", self.f_address)
        form.addRow("Telefone", self.f_phone)
        form.addRow("E-mail", self.f_email)

    def isComplete(self):
        return len(self.f_name.text().strip()) >= 2

    def save(self):
        self.ctx.companies.upsert(dict(
            name=self.f_name.text().strip(), legal_name=self.f_legal_name.text().strip(),
            cnpj=self.f_cnpj.text().strip(), address=self.f_address.text().strip(),
            phone=self.f_phone.text().strip(), email=self.f_email.text().strip()))
        self.ctx.refresh()


class UnitPage(QWizardPage):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setTitle("Cadastro da unidade")
        self.setSubTitle("A unidade é o estacionamento físico.")
        self.ctx = ctx
        form = QFormLayout(self)
        self.f_name = QLineEdit("Estacionamento Centro")
        self.f_addr = QLineEdit()
        self.f_open = QLineEdit("07:00")
        self.f_close = QLineEdit("22:00")
        self.f_tol = QSpinBox(); self.f_tol.setRange(0, 120); self.f_tol.setValue(10)
        self.f_tol.setSuffix(" min")
        form.addRow("Nome da unidade", self.f_name)
        form.addRow("Endereço", self.f_addr)
        form.addRow("Abertura", self.f_open)
        form.addRow("Fechamento", self.f_close)
        form.addRow("Tolerância (grátis)", self.f_tol)

    def isComplete(self):
        return len(self.f_name.text().strip()) >= 3

    def save(self):
        company = self.ctx.companies.first()
        self.ctx.lots.upsert(dict(
            company_id=company["id"] if company else None,
            name=self.f_name.text().strip(), code="UNID-01",
            address=self.f_addr.text().strip(), opening_time=self.f_open.text(),
            closing_time=self.f_close.text(), tolerance_minutes=self.f_tol.value()))
        self.ctx.refresh()


class SpacesPage(QWizardPage):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setTitle("Configuração das vagas")
        self.setSubTitle("Configure o setor e a quantidade de vagas.")
        self.ctx = ctx
        form = QFormLayout(self)
        self.f_sector = QLineEdit("Setor A")
        self.f_cars = QSpinBox(); self.f_cars.setRange(1, 5000); self.f_cars.setValue(100)
        self.f_moto = QSpinBox(); self.f_moto.setRange(0, 500); self.f_moto.setValue(4)
        self.f_pcd = QSpinBox(); self.f_pcd.setRange(0, 100); self.f_pcd.setValue(2)
        self.f_idoso = QSpinBox(); self.f_idoso.setRange(0, 100); self.f_idoso.setValue(2)
        form.addRow("Setor", self.f_sector)
        form.addRow("Vagas de carro", self.f_cars)
        form.addRow("Vagas de moto", self.f_moto)
        form.addRow("Vagas PCD", self.f_pcd)
        form.addRow("Vagas idosos", self.f_idoso)

    def save(self):
        lot = self.ctx.lots.first()
        spaces = SpaceRepo(self.ctx.db)
        if spaces.total(lot["id"]):
            return
        sectors = SectorRepo(self.ctx.db)
        sid = sectors.create(lot["id"], self.f_sector.text().strip(), "#4C6FFF", 1)
        n = self.f_cars.value()
        spaces.create_many(lot["id"], sid,
                           [f"V{str(i).zfill(3)}" for i in range(1, n + 1)], "CARRO")
        spaces.create_many(lot["id"], sid,
                           [f"M{str(i).zfill(2)}" for i in range(1, self.f_moto.value() + 1)],
                           "MOTO")
        spaces.create_many(lot["id"], sid,
                           [f"PD{str(i).zfill(2)}" for i in range(1, self.f_pcd.value() + 1)],
                           "DEFICIENTE")
        spaces.create_many(lot["id"], sid,
                           [f"ID{str(i).zfill(2)}" for i in range(1, self.f_idoso.value() + 1)],
                           "IDOSO")
        self.ctx.save_settings(total_spaces=spaces.total(lot["id"]))


class TariffsPage(QWizardPage):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setTitle("Configuração de tarifas")
        self.setSubTitle("Valores em reais. Tudo é configurável depois.")
        self.ctx = ctx
        form = QFormLayout(self)
        self.f_free = QSpinBox(); self.f_free.setRange(0, 60); self.f_free.setValue(15)
        self.f_free.setSuffix(" min")
        self.f_initial = QLineEdit("12,00")
        self.f_hour = QLineEdit("10,00")
        self.f_daily = QLineEdit("144,00")
        self.f_fraction = QSpinBox(); self.f_fraction.setRange(15, 120)
        self.f_fraction.setValue(30); self.f_fraction.setSuffix(" min")
        for w, label in ((self.f_free, "Primeiros minutos grátis"),
                         (self.f_initial, "Primeira hora (R$)"),
                         (self.f_hour, "Fração/hora (R$)"),
                         (self.f_fraction, "Frações de"),
                         (self.f_daily, "Diária máxima (R$)")):
            form.addRow(label, w)

    def save(self):
        lot = self.ctx.lots.first()
        tariffs = TariffRepo(self.ctx.db)
        if tariffs.list(lot["id"]):
            return
        fid = tariffs.create(dict(lot_id=lot["id"], name="Padrão",
                                  vehicle_category="*", period_type="NORMAL",
                                  is_default=1, days_mask="1111111",
                                  starts_at_str="00:00", ends_at_str="23:59"))
        for idx, r in enumerate(build_default_rules(
                cents(self.f_initial.text()), cents(self.f_hour.text()),
                self.f_fraction.value(), self.f_free.value(),
                cents(self.f_daily.text()))):
            tariffs.add_rule(fid, r["minutes_from"], r["minutes_to"],
                             r["rule_type"], r["value"], r["sort"] or idx)


class PrinterPage(QWizardPage):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setTitle("Impressora")
        self.setSubTitle("Impressora térmica para tickets (opcional).")
        self.ctx = ctx
        form = QFormLayout(self)
        self.f_name = QLineEdit()
        self.f_name.setPlaceholderText("Ex.: TICKET 58 (vazio = simulação DEMO)")
        self.f_width = QComboBox(); self.f_width.addItems(["58 mm", "80 mm"])
        self.f_auto = QCheckBox("Imprimir ticket automaticamente na entrada")
        self.f_auto.setChecked(True)
        form.addRow("Impressora", self.f_name)
        form.addRow("Largura", self.f_width)
        form.addRow("", self.f_auto)
        self.setLayout(form)

    def save(self):
        self.ctx.save_settings(
            printer_name=self.f_name.text().strip(),
            printer_width_mm=58 if "58" in self.f_width.currentText() else 80,
            auto_print_ticket=self.f_auto.isChecked())


class AdminPage(QWizardPage):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setTitle("Usuário administrador")
        self.setSubTitle("Crie o usuário com acesso total.")
        self.ctx = ctx
        form = QFormLayout(self)
        self.f_user = QLineEdit("admin")
        self.f_name = QLineEdit("Administrador")
        self.f_pass = QLineEdit()
        self.f_pass.setEchoMode(QLineEdit.Password)
        form.addRow("Usuário", self.f_user)
        form.addRow("Nome", self.f_name)
        form.addRow("Senha (mín. 8)", self.f_pass)
        self.setLayout(form)

    def isComplete(self):
        return len(self.f_pass.text()) >= 8

    def save(self):
        username = self.f_user.text().strip()
        if self.ctx.users.get_by_username(username):
            return
        h, s = PasswordService.hash_password(self.f_pass.text())
        self.ctx.users.create(username.lower(), self.f_name.text().strip(), h, s,
                              "ADMINISTRADOR")


class BackupPage(QWizardPage):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setTitle("Backup automático")
        self.setSubTitle("Retenção dos backups.")
        self.ctx = ctx
        form = QFormLayout(self)
        self.f_days = QSpinBox(); self.f_days.setRange(7, 365); self.f_days.setValue(30)
        self.f_days.setSuffix(" dias")
        form.addRow("Reter backups por", self.f_days)
        self.setLayout(form)

    def save(self):
        self.ctx.save_settings(backup_retention_days=self.f_days.value())


class FinalPage(QWizardPage):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setTitle("Concluído")
        self.setSubTitle("Pronto para ativar a licença e operar.")
        self.ctx = ctx


class SetupWizard(QWizard):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("MasterPark — Configuração Inicial")
        self.setFixedSize(720, 520)
        self.setWizardStyle(QWizard.ModernStyle)
        self.setButtonText(QWizard.FinishButton, "Concluir")
        self.setButtonText(QWizard.NextButton, "Avançar")
        self.pages = [CompanyPage(ctx), UnitPage(ctx), SpacesPage(ctx),
                      TariffsPage(ctx), PrinterPage(ctx), AdminPage(ctx),
                      BackupPage(ctx), FinalPage(ctx)]
        for page in self.pages:
            self.addPage(page)
        self._wire_complete()

    def _wire_complete(self):
        """Reavalia isComplete() a cada mudança, habilitando Avançar/Voltar."""
        from PySide6.QtWidgets import QWidget
        for page in self.pages:
            for w in page.findChildren(QWidget):
                if isinstance(w, QLineEdit):
                    w.textChanged.connect(page.completeChanged)
                elif isinstance(w, QSpinBox):
                    w.valueChanged.connect(page.completeChanged)
                elif isinstance(w, QComboBox):
                    w.currentIndexChanged.connect(page.completeChanged)
                elif isinstance(w, QCheckBox):
                    w.stateChanged.connect(page.completeChanged)

    def accept(self):
        try:
            for page in self.pages:
                if hasattr(page, "save"):
                    page.save()
            self.ctx.refresh()
            self.ctx.backup.create(kind="MANUAL", note="backup após configuração inicial")
        except Exception as exc:
            QMessageBox.warning(self, "Atenção", f"Não foi possível salvar: {exc}")
            return
        super().accept()