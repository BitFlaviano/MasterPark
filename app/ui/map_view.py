"""Mapa de vagas em tempo real (por setor, colorido por estado)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QGridLayout, QHBoxLayout, QInputDialog,
                               QLabel, QScrollArea, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from app.ui.theme import DARK, LIGHT, SPACE_STATES
from app.ui.widgets import (Card, SearchField, info, make_label, page_header,
                            primary_button, warn, yes_no)

STATE_PT = {"LIVRE": "Livre", "OCUPADA": "Ocupada", "RESERVADA": "Reservada",
            "BLOQUEADA": "Bloqueada", "MANUTENCAO": "Manutenção"}

_STATE_COLORS = SPACE_STATES


def _accent_soft(ctx) -> str:
    try:
        dark = ctx.settings.theme == "dark"
    except AttributeError:
        dark = False
    return (DARK if dark else LIGHT)["ACCENT_SOFT"]


def state_pairs_pt() -> dict:
    return STATE_PT


class SpaceCell(QLabel):
    """Célula colorida representando uma vaga no grid do mapa."""

    def __init__(self, space: dict, parent=None):
        state = space.get("state", "")
        super().__init__(f"{space['code']}\n{STATE_PT.get(state, state)}", parent)
        self.space = space
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(62, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_state(space["state"])
        self.setToolTip(f"Vaga {space['code']} — "
                        f"{STATE_PT.get(space['state'], space['state'])}")

    def set_state(self, state: str):
        color = _STATE_COLORS.get(state, "#64748B")
        self.setStyleSheet(
            f"background:{color}; color:white; font-weight:800; font-size:11px;"
            f"border-radius:8px; padding:2px; line-height:1.1;")


# ----------------------------------------------------------------------
def manage_layout_dialog(parent, ctx) -> None:
    """Diálogo para excluir setores e vagas (cada cliente tem layout próprio).

    A exclusão é feita de forma segura no repositório: vagas ocupadas,
    reservadas, em manutenção, de mensalistas ou com histórico de uso nunca
    são apagadas — o diálogo apenas informa o motivo quando a exclusão é
    bloqueada, preservando a integridade referencial e o registro fiscal.
    """
    lot = ctx.lot
    if not lot:
        warn(parent, "Layout", "Estacionamento ainda não configurado.")
        return

    dlg = QDialog(parent)
    dlg.setWindowTitle("Gerir Layout — Setores e Vagas")
    dlg.resize(820, 560)
    outer = QVBoxLayout(dlg)
    outer.setSpacing(12)

    first = make_label(
        "Crie setores, adicione vagas e exclua os que o seu cliente não utiliza. "
        "Cada estacionamento pode ter um layout próprio.", "subtitle")
    first.setWordWrap(True)
    outer.addWidget(first)

    # ------------------------------------------------- criar setor/vagas
    tools = QHBoxLayout()
    tools.setSpacing(8)
    tools.addWidget(make_label("Setor:", "label"))
    f_name = SearchField("Nome do setor (ex.: Subsolo)")
    tools.addWidget(f_name, 1)
    f_color = SearchField("#4C6FFF")
    f_color.setMaximumWidth(110)
    tools.addWidget(f_color)
    b_new_sector = primary_button("+ Setor")
    tools.addWidget(b_new_sector)
    outer.addLayout(tools)

    tools2 = QHBoxLayout()
    tools2.setSpacing(8)
    tools2.addWidget(make_label("Vagas:", "label"))
    f_from = SearchField("1")
    f_from.setMaximumWidth(70)
    tools2.addWidget(f_from)
    tools2.addWidget(make_label("até", "label"))
    f_to = SearchField("20")
    f_to.setMaximumWidth(70)
    tools2.addWidget(f_to)
    tools2.addWidget(make_label("no setor", "label"))
    f_sector = QComboBox()
    tools2.addWidget(f_sector, 1)
    b_new_spaces = primary_button("+ Vagas")
    tools2.addWidget(b_new_spaces)
    outer.addLayout(tools2)

    sec_tbl = QTableWidget(0, 5)
    sec_tbl.setHorizontalHeaderLabels(["Setor", "Andar", "Vagas", "Ações", ""])
    sec_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    sec_tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    sec_tbl.verticalHeader().setVisible(False)
    sec_tbl.setColumnWidth(0, 300)
    sec_tbl.setColumnWidth(1, 60)
    sec_tbl.setColumnWidth(2, 60)
    sec_tbl.setColumnWidth(3, 150)
    sec_tbl.setColumnWidth(4, 60)
    outer.addWidget(sec_tbl, 1)

    sp_tbl = QTableWidget(0, 4)
    sp_tbl.setHorizontalHeaderLabels(["Código", "Setor", "Estado", "Ações"])
    sp_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    sp_tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    sp_tbl.verticalHeader().setVisible(False)
    sp_tbl.setColumnWidth(0, 130)
    sp_tbl.setColumnWidth(1, 260)
    sp_tbl.setColumnWidth(2, 120)
    sp_tbl.setColumnWidth(3, 130)
    outer.addWidget(sp_tbl, 1)

    def _refresh():
        sec_tbl.setRowCount(0)
        sp_tbl.setRowCount(0)
        lot_id = lot["id"] or 0

        sectors = ctx.sectors.list(lot_id)
        f_sector.blockSignals(True)
        f_sector.clear()
        for sec in sectors:
            f_sector.addItem(f"{sec.get('name', '')} (andar {sec.get('floor', 1)})", sec["id"])
        f_sector.blockSignals(False)
        if f_sector.count() == 0:
            f_sector.addItem("— nenhum setor —", None)

        for sec in sectors:
            r = sec_tbl.rowCount()
            sec_tbl.insertRow(r)
            sec_tbl.setItem(r, 0, QTableWidgetItem(sec.get("name", "—")))
            sec_tbl.setItem(r, 1, QTableWidgetItem(str(sec.get("floor", ""))))
            n = len([sp for sp in ctx.spaces.list(lot_id)
                     if sp.get("sector_id") == sec["id"]])
            sec_tbl.setItem(r, 2, QTableWidgetItem(str(n)))
            box = QWidget()
            bl = QHBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(4)
            b_ren = primary_button("✎ Renomear", "")
            b_ren.setFixedHeight(30)
            b_ren.clicked.connect(
                lambda _=False, sid=sec["id"], nm=sec.get("name", ""): _rename_sector(sid, nm))
            bl.addWidget(b_ren)
            btn = primary_button("✕ Excluir", "danger")
            btn.setFixedHeight(30)
            btn.clicked.connect(
                lambda _=False, sid=sec["id"], nm=sec.get("name", ""):
                _delete_sector(sid, nm))
            bl.addWidget(btn)
            sec_tbl.setCellWidget(r, 3, box)
            sec_tbl.setCellWidget(r, 4, QWidget())

        for sp in ctx.spaces.list(lot_id):
            r = sp_tbl.rowCount()
            sp_tbl.insertRow(r)
            sp_tbl.setItem(r, 0, QTableWidgetItem(sp.get("code", "—")))
            sp_tbl.setItem(r, 1, QTableWidgetItem(
                sp.get("sector_name") or "—"))
            sp_tbl.setItem(r, 2, QTableWidgetItem(
                STATE_PT.get(sp.get("state", ""), sp.get("state", ""))))
            btn = primary_button("✕ Excluir", "danger")
            btn.setFixedHeight(30)
            btn.clicked.connect(
                lambda _=False, sid=sp["id"], cd=sp.get("code", ""):
                _delete_space(sid, cd))
            sp_tbl.setCellWidget(r, 3, btn)

    def _add_sector():
        name = f_name.text().strip()
        if not name:
            warn(dlg, "Novo setor", "Informe o nome do setor.")
            return
        color = (f_color.text().strip() or "#4C6FFF")
        if not (color.startswith("#") and len(color) in (4, 7)):
            warn(dlg, "Novo setor", "A cor deve estar no formato #RRGGBB.")
            return
        existing = {s.get("name", "").lower() for s in ctx.sectors.list(lot["id"] or 0)}
        if name.lower() in existing:
            warn(dlg, "Novo setor", f"Já existe um setor chamado “{name}”.")
            return
        ctx.sectors.create(lot["id"] or 0, name, color)
        f_name.clear()
        _refresh()
        f_sector.setCurrentIndex(f_sector.count() - 1)

    def _add_spaces():
        try:
            first = int(f_from.text().strip())
            last = int(f_to.text().strip())
        except ValueError:
            warn(dlg, "Novas vagas", "Informe início e fim como números (ex.: 1 e 20).")
            return
        if last < first:
            warn(dlg, "Novas vagas", "O fim deve ser maior ou igual ao início.")
            return
        if last - first > 500:
            warn(dlg, "Novas vagas", "Limite de 500 vagas por operação.")
            return
        sector_id = f_sector.currentData()
        if not sector_id:
            warn(dlg, "Novas vagas", "Crie um setor antes de adicionar vagas.")
            return
        prefix = ""
        sectors = {s["id"]: s for s in ctx.sectors.list(lot["id"] or 0)}
        sec = sectors.get(sector_id)
        if sec:
            letters = [c for c in str(sec.get("name", "")) if c.isalpha()]
            prefix = (letters[0].upper() if letters else "V")
        codes = [f"{prefix}-{i:03d}" if prefix else str(i)
                 for i in range(first, last + 1)]
        created = ctx.spaces.create_many(lot["id"] or 0, sector_id, codes)
        _refresh()
        if created:
            f_sector.setCurrentIndex(
                max(0, f_sector.findData(sector_id)))
            info(dlg, "Vagas adicionadas",
                 f"{created} vaga(s) criada(s)."
                 + (" Códigos já existentes foram ignorados."
                    if created < len(codes) else ""))
        else:
            warn(dlg, "Nenhuma vaga criada",
                 "Todos os códigos informados já existem neste "
                 "estacionamento.")

    def _rename_sector(sector_id: int, current: str):
        new, ok = QInputDialog.getText(dlg, "Renomear setor",
                                       "Novo nome do setor:", text=current)
        if not ok or not str(new).strip():
            return
        new = new.strip()
        if not new:
            warn(dlg, "Renomear setor", "O nome não pode ficar vazio.")
            return
        ctx.sectors.rename(sector_id, new)
        _refresh()

    def _delete_space(space_id: int, code: str):
        if not yes_no("Excluir vaga",
                      f"Excluir a vaga “{code}”?\n\n"
                      "A vaga sai do mapa. Tickets antigos continuam "
                      "guardando o histórico."):
            return
        if ctx.spaces.delete(space_id):
            _refresh()
        else:
            reasons = ctx.spaces.delete_blockers(space_id)
            warn(dlg, "Não foi possível excluir a vaga",
                 ("A vaga não pode ser excluída porque "
                  + "; ".join(dict.fromkeys(reasons)) + ".")
                 if reasons else "A vaga não foi encontrada.")

    def _delete_sector(sector_id: int, name: str):
        if not yes_no("Excluir setor",
                      f"Excluir o setor “{name}” e desativar todas as "
                      "suas vagas?\n\n"
                      "A vaga some do mapa, mas os tickets antigos continuam "
                      "guardando o histórico."):
            return
        if ctx.sectors.delete(sector_id):
            _refresh()
        else:
            reasons: list[str] = []
            for sp in ctx.spaces.list(lot["id"] or 0):
                if sp.get("sector_id") == sector_id:
                    reasons.extend(ctx.spaces.delete_blockers(sp["id"]))
            warn(dlg, "Não foi possível excluir o setor",
                 ("O setor tem vagas em uso: "
                  + "; ".join(dict.fromkeys(reasons)) + ".")
                 if reasons else "O setor não foi encontrado.")

    # as conexões vêm depois das definições acima
    b_new_sector.clicked.connect(_add_sector)
    b_new_spaces.clicked.connect(_add_spaces)

    _refresh()
    close_btn = primary_button("Fechar")
    close_btn.clicked.connect(dlg.accept)
    outer.addWidget(close_btn)
    dlg.exec()


class MapViewScreen(QWidget):
    """Grade de vagas agrupadas por setor, colorida pelo estado."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        actions = QHBoxLayout()
        self.btn_refresh = primary_button("🔄  Atualizar", "ghost")
        self.btn_refresh.clicked.connect(self._render)
        actions.addWidget(self.btn_refresh)
        if self.ctx.auth.can("SPACE_MANAGE"):
            for label in ("+ Setor", "+ Vaga", "⚙  Gerir Layout"):
                btn = primary_button(label, "primary" if label == "+ Vaga" else "ghost")
                btn.clicked.connect(self._manage_layout)
                actions.addWidget(btn)
        header = page_header("Mapa de Vagas", "Ocupação em tempo real por setor",
                             actions=actions)
        self.lbl_subtitle = header.findChild(QLabel, "subtitle")
        lay.addWidget(header)

        self.summary_card = Card("Resumo das vagas")
        self.summary = QHBoxLayout()
        self.summary.setSpacing(8)
        self.summary_card.body.addLayout(self.summary)
        lay.addWidget(self.summary_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.grid = QVBoxLayout(self.body)
        self.grid.setSpacing(16)
        scroll.setWidget(self.body)
        lay.addWidget(scroll, 1)

    def _manage_layout(self):
        manage_layout_dialog(self, self.ctx)
        self._render()

    # ------------------------------------------------------------------
    def on_show(self):
        self._render()

    def _render(self):
        # limpa TODOS os ítens (widgets e espaçadores) para não empurrar
        # o conteúdo para baixo a cada atualização
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget_item = item.widget()
            if widget_item:
                widget_item.deleteLater()
        lot = self.ctx.lot
        if not lot:
            self.grid.addWidget(make_label(
                "Estacionamento ainda não configurado. Use o assistente de "
                "primeira execução.", "subtitle"))
            return
        lot_id = lot["id"]
        spaces = self.ctx.spaces.list(lot_id)
        sectors = self.ctx.sectors.list(lot_id)
        spaces_by_sector = {}
        for space in spaces:
            spaces_by_sector.setdefault(space.get("sector_id"), []).append(space)
        sector_total = len(sectors)
        self.lbl_subtitle.setText(
            f"{sector_total} setor(es) • {len(spaces)} vaga(s) — "
            "clique numa vaga para ver detalhes")

        counts = {state: 0 for state in STATE_PT}
        for s in spaces:
            counts[s["state"]] = counts.get(s["state"], 0) + 1

        for i in reversed(range(self.summary.count())):
            item = self.summary.takeAt(i)
            if item.widget():
                item.widget().deleteLater()
        for state, label in STATE_PT.items():
            chip = QLabel(f"● {label}   {counts.get(state, 0)}")
            chip.setContentsMargins(8, 6, 12, 6)
            chip.setStyleSheet(
                f"background:{_accent_soft(self.ctx)}; "
                f"color:{_STATE_COLORS.get(state, '#64748B')};"
                "border-radius:8px; font-weight:700;")
            self.summary.addWidget(chip)
        self.summary.addStretch(1)

        for sector in sectors:
            name = sector.get("name") or "Sem setor"
            items = spaces_by_sector.get(sector.get("id"), [])
            card = Card(f"Setor {name} — {len(items)} vaga(s)")
            grid = QGridLayout()
            grid.setSpacing(8)
            for i, space in enumerate(items):
                cell = SpaceCell(space)
                grid.addWidget(cell, i // 10, i % 10)
            card.body.addLayout(grid)
            self.grid.addWidget(card)
        unassigned = spaces_by_sector.get(None, [])
        if unassigned:
            card = Card(f"Sem setor — {len(unassigned)} vaga(s)")
            grid = QGridLayout()
            grid.setSpacing(8)
            for i, space in enumerate(unassigned):
                grid.addWidget(SpaceCell(space), i // 10, i % 10)
            card.body.addLayout(grid)
            self.grid.addWidget(card)
        if not sectors and not unassigned:
            empty = Card()
            msg = make_label(
                "Nenhum setor cadastrado. Use + Setor para começar.", "subtitle")
            msg.setAlignment(Qt.AlignCenter)
            empty.body.addWidget(msg)
            self.grid.addWidget(empty)
        self.grid.addStretch(1)


def state_pairs_pt() -> dict:
    return STATE_PT
