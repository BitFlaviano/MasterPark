"""Tela Sobre: o que é o MasterPark e quem criou."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QScrollArea, QVBoxLayout,
                               QWidget)

from app.ui.theme import (DANGER, INFO, PRIMARY, SUCCESS, WARNING)
from app.ui.widgets import (Card, StatCard, info, make_label, page_header,
                            primary_button)


class AboutScreen(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 12, 0)
        lay.setSpacing(14)
        area.setWidget(body)
        outer.addWidget(area, 1)

        license_btn = primary_button("🔑  Licença", "ghost")
        license_btn.clicked.connect(self.open_activation)
        lay.addWidget(page_header(
            "Sobre o Sistema", "MasterPark — Sistema de Gestão de Estacionamentos",
            actions=license_btn))

        # ---------------------------------------------------------- capa
        cover = Card()
        row = QHBoxLayout()
        logo = QLabel("M")
        logo.setFixedSize(66, 66)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            f"background:{PRIMARY}; color:white; border-radius:16px;"
            "font-size:30px; font-weight:800;")
        row.addWidget(logo)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        name = make_label("M A S T E R P A R K", "statValue")
        name.setStyleSheet(f"color:{PRIMARY}; font-size:22px; font-weight:800;")
        texts.addWidget(name)
        texts.addWidget(make_label("Gestão de Estacionamentos", "statLabel"))

        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(make_label(f"v{ctx.version}", "chip"))
        chips.addWidget(make_label("● Estável", "chipGreen"))
        chips.addWidget(make_label("Desktop · Windows", "chip"))
        chips.addStretch(1)
        texts.addLayout(chips)
        row.addLayout(texts, 1)
        cover.body.addLayout(row)
        lay.addWidget(cover)

        # ---------------------------------------------------- o que é + autor
        two = QHBoxLayout()
        two.setSpacing(12)

        what = Card("O que é o MasterPark")
        about = make_label(
            "O MasterPark é um sistema completo de gestão de estacionamentos, feito para "
            "substituir o controle manual de um pátio por um processo automatizado, "
            "auditável e em tempo real.", "")
        about.setWordWrap(True)
        about.setAlignment(Qt.AlignTop)
        what.body.addWidget(about)

        about2 = make_label(
            "Ele cobre o ciclo completo da operação — da entrada do veículo à saída com "
            "pagamento, incluindo mensalistas, controle de caixa e relatórios gerenciais "
            "— com acesso por nível de permissão e trilha de auditoria de todas as ações.", "")
        about2.setWordWrap(True)
        about2.setAlignment(Qt.AlignTop)
        what.body.addWidget(about2)

        goal = make_label(
            "Objetivo: reduzir erro de digitação, eliminar filas na portaria e dar ao "
            "gestor os números do negócio em um relance.", "")
        goal.setWordWrap(True)
        goal.setStyleSheet(
            f"background:rgba(245,158,11,.12); border:1px solid {WARNING};"
            "border-radius:8px; padding:9px 12px;")
        what.body.addWidget(goal)
        two.addWidget(what, 1)

        author = Card("Autor e créditos")
        arow = QHBoxLayout()
        arow.setSpacing(14)
        av = QLabel("FP")
        av.setFixedSize(58, 58)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(
            f"background:{PRIMARY}; color:white; border-radius:29px;"
            "font-size:22px; font-weight:800;")
        arow.addWidget(av)
        atexts = QVBoxLayout()
        atexts.setSpacing(2)
        aname = make_label("Flaviano Porto", "statValue")
        aname.setStyleSheet("font-size:18px; font-weight:800;")
        atexts.addWidget(aname)
        atexts.addWidget(make_label("Criador e desenvolvedor do MasterPark", "statLabel"))
        atexts.addWidget(make_label("Conceito, arquitetura, banco de dados e interface.", "subtitle"))
        arow.addLayout(atexts, 1)
        author.body.addLayout(arow)

        for label, value in (("Projeto", "MasterPark"),
                             ("Autor", "Flaviano Porto"),
                             ("Categoria", "Gestão de estacionamentos"),
                             ("Versão", ctx.version),
                             ("Plataforma", "Windows (escritório)"),
                             ("Licença", "Proprietária")):
            line = QHBoxLayout()
            line.addWidget(make_label(f"{label}:", "statLabel"))
            val = make_label(value, "statLabel")
            val.setStyleSheet("font-weight:700;")
            line.addWidget(val)
            line.addStretch(1)
            author.body.addLayout(line)
        two.addWidget(author, 1)
        lay.addLayout(two)

        # ------------------------------------------------- recursos + stack
        two2 = QHBoxLayout()
        two2.setSpacing(12)

        feats = Card("Funcionalidades")
        for icon, text in (
                ("🅿", "Operação de entrada e saída de veículos"),
                ("🗺", "Mapa de vagas com estados em tempo real"),
                ("🎫", "Tickets e reimpressão de comprovantes"),
                ("🗓", "Mensalistas, mensalidades e bloqueios"),
                ("👤", "Cadastro de clientes e veículos"),
                ("🧾", "Caixa, sangrias e fechamento de turno"),
                ("📈", "Dashboard, relatórios e exportação"),
                ("🛡", "Perfis de acesso e auditoria completa")):
            r = QHBoxLayout()
            r.setSpacing(10)
            r.addWidget(make_label(icon, "statLabel"))
            r.addWidget(make_label(text, "statLabel"))
            r.addStretch(1)
            feats.body.addLayout(r)
        two2.addWidget(feats, 1)

        tech = Card("Tecnologias utilizadas")
        for label, value in (("Interface", "Python + PySide6 (Qt 6)"),
                             ("Banco de dados", "SQLite (arquivo único, portátil)"),
                             ("Camadas", "UI · Services · Repositories · Domain"),
                             ("Impressão", "Escopos ESC/POS e texto"),
                             ("Segurança", "PBKDF2 + perfis de permissão"),
                             ("Backup", "Automático e manual")):
            r = QHBoxLayout()
            r.addWidget(make_label(f"{label}:", "statLabel"))
            val = make_label(value, "statLabel")
            val.setStyleSheet("font-weight:700;")
            r.addWidget(val)
            r.addStretch(1)
            tech.body.addLayout(r)

        tech.body.addWidget(make_label("Atalhos de teclado", "statLabel"))
        tech.body.addWidget(make_label(
            "F2 Entrada · F3 Saída · F4 Tickets · F5 Caixa · F6 Mensalistas · "
            "F7 Clientes · F9 Relatórios · Ctrl+K Busca", "subtitle"))
        two2.addWidget(tech, 1)
        lay.addLayout(two2)

        # ---------------------------------------------------------- rodapé
        foot = Card()
        fl = QLabel("© 2026 Flaviano Porto — MasterPark. Todos os direitos reservados.")
        fl.setAlignment(Qt.AlignCenter)
        fl.setObjectName("subtitle")
        foot.body.addWidget(fl)
        lay.addWidget(foot)

    # ------------------------------------------------------------------
    def on_show(self):
        return

    def open_activation(self):
        from app.ui.activation import ActivationDialog
        dlg = ActivationDialog(self.ctx, self)
        if dlg.exec() and dlg.activated:
            info(self, "Licença", "Licença ativada com sucesso.")
