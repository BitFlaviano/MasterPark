"""Tela de clientes e veículos cadastrados."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from app.domain.models import mask_doc, format_pt_datetime
from app.domain.models import utcnow_iso
from app.ui.table_layout import ColumnLayout
from app.ui.widgets import (Card, SearchField, error, info, make_label,
                            page_header, primary_button, warn, yes_no)


def pick_customer(parent, ctx) -> dict | None:
    """Diálogo reutilizável para escolher um cliente."""
    rows = ctx.customers.list(limit=500)
    if not rows:
        warn(parent, "Sem clientes", "Nenhum cliente cadastrado.")
        return None
    dlg = QDialog(parent)
    dlg.setWindowTitle("Selecionar cliente")
    dlg.resize(560, 420)
    lay = QVBoxLayout(dlg)
    box = SearchField("Buscar por nome, CPF, CNPJ ou telefone...")
    lay.addWidget(box)
    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels(["Nome", "Documento", "Telefone"])
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.verticalHeader().setVisible(False)
    lay.addWidget(table)
    pick_layout = ColumnLayout(ctx, table, "selecao_cliente")
    result = {}

    rows_cache = rows

    def fill(term=""):
        table.setRowCount(0)
        t = term.strip().lower()
        for r in rows_cache:
            if t and t not in (r["name"] or "").lower() and t not in (r["cpf"] or "").lower() \
                    and t not in (r["cnpj"] or "").lower() and t not in (r["phone"] or "").lower():
                continue
            i = table.rowCount()
            table.insertRow(i)
            doc = r["cpf"] or r["cnpj"] or ""
            for c, val in enumerate([r["name"], mask_doc(doc) if doc else "-",
                                     r["phone"] or "-"]):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(i, c, item)
        pick_layout.resize_event()

    fill()
    box.textChanged.connect(fill)

    def ok():
        idx = table.currentRow()
        if idx < 0:
            return
        row = table.selectedItems()
        if not row:
            warn(dlg, "Seleção", "Selecione um cliente.")
            return
        name = row[0].text()
        for r in rows_cache:
            if r["name"] == name:
                result["customer"] = r
                dlg.accept()
                return

    btn = primary_button("Selecionar", "primary")
    btn.clicked.connect(ok)
    lay.addWidget(btn)
    dlg.exec()
    return result.get("customer")


class CustomersScreen(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.rows: list[dict] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Clientes e Veículos",
                                  "Gestão de cadastros de clientes (F7)"))

        top = QHBoxLayout()
        self.box = SearchField("Buscar cliente...")
        self.box.textChanged.connect(self._filter)
        top.addWidget(self.box, 1)
        self.btn_add = primary_button("+ Novo Cliente", "primary")
        self.btn_add.clicked.connect(self.new_customer)
        top.addWidget(self.btn_add)
        self.btn_edit_c = primary_button("Alterar Cliente", "ghost")
        self.btn_edit_c.clicked.connect(self.edit_customer)
        top.addWidget(self.btn_edit_c)
        self.btn_del_c = primary_button("Excluir Cliente", "danger")
        self.btn_del_c.clicked.connect(self.delete_customer)
        top.addWidget(self.btn_del_c)
        self.btn_veh = primary_button("Veículos", "ghost")
        self.btn_veh.clicked.connect(self.manage_vehicles)
        top.addWidget(self.btn_veh)
        lay.addLayout(top)

        self.card = Card("Clientes")
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["#", "Nome", "Documento", "Telefone",
                                              "E-mail", "Veículos", "Status"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.card.body.addWidget(self.table)
        lay.addWidget(self.card, 1)
        self._layout = ColumnLayout(ctx, self.table, "clientes")

    def on_show(self):
        self._refresh()

    def _refresh(self):
        self.rows = self.ctx.customers.list(limit=500)
        self._filter()

    def _filter(self):
        term = self.box.text().strip().lower()
        table = self.table
        table.setRowCount(0)
        for r in self.rows:
            searchable = (r["name"], r["cpf"], r["cnpj"], r["phone"], r["email"])
            if term and not any(term in (value or "").lower() for value in searchable):
                continue
            doc = r["cpf"] or r["cnpj"] or ""
            vid = self.ctx.vehicles.by_customer(r["id"])
            i = table.rowCount()
            table.insertRow(i)
            state = "BLOQUEADO" if r.get("is_blacklisted") else "ATIVO"
            for c, val in enumerate([r["id"], r["name"],
                                     mask_doc(doc) if doc else "-",
                                     r["phone"] or "-", r.get("email") or "-",
                                     str(len(vid)), state]):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(i, c, item)
        self._layout.resize_event()

    def new_customer(self):
        self.ctx.auth.require_permission("CUSTOMER_MANAGE")
        dlg = QDialog(self)
        dlg.setWindowTitle("Novo cliente")
        dlg.setFixedSize(420, 380)
        lay = QVBoxLayout(dlg)
        fields = {}
        for key, label in (("name", "Nome*"), ("person_type", "Tipo (FISICA/JURIDICA)"),
                           ("cpf", "CPF (opcional)"), ("cnpj", "CNPJ (opcional)"),
                           ("phone", "Telefone"), ("whatsapp", "WhatsApp"),
                           ("email", "E-mail"), ("address", "Endereço")):
            box = QLineEdit()
            box.setPlaceholderText(label)
            fields[key] = box
            lay.addWidget(box)
        fields["person_type"].setText("FISICA")

        def save():
            name = fields["name"].text().strip()
            if len(name) < 2:
                warn(dlg, "Validação", "Informe o nome do cliente.")
                return
            data = {"name": name,
                    "person_type": fields["person_type"].text().strip() or "FISICA"}
            for key in ("cpf", "cnpj", "phone", "whatsapp", "email", "address"):
                val = fields[key].text().strip()
                if val:
                    data[key] = val
            data["created_at"] = utcnow_iso()
            try:
                self.ctx.customers.create(data)
                info(dlg, "OK", "Cliente cadastrado.")
                dlg.accept()
                self._refresh()
            except Exception as exc:
                error(dlg, "Erro", str(exc))

        btn = primary_button("Salvar cliente", "success")
        btn.clicked.connect(save)
        lay.addWidget(btn)
        dlg.exec()

    # ------------------------------------------------------------------
    def selected(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            warn(self, "Seleção", "Selecione um cliente na lista.")
            return None
        return self.rows[row]

    def edit_customer(self):
        self.ctx.auth.require_permission("CUSTOMER_MANAGE")
        customer = self.selected()
        if not customer:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Alterar cliente — {customer['name']}")
        dlg.setFixedSize(420, 380)
        lay = QVBoxLayout(dlg)
        fields = {}
        for key, label in (("name", "Nome*"), ("person_type", "Tipo (FISICA/JURIDICA)"),
                           ("cpf", "CPF"), ("cnpj", "CNPJ"), ("phone", "Telefone"),
                           ("whatsapp", "WhatsApp"), ("email", "E-mail"),
                           ("address", "Endereço")):
            box = QLineEdit()
            box.setPlaceholderText(label)
            box.setText(customer.get(key) or "")
            fields[key] = box
            lay.addWidget(box)

        def save():
            name = fields["name"].text().strip()
            if len(name) < 2:
                warn(dlg, "Validação", "Informe o nome do cliente.")
                return
            data = {"name": name,
                    "person_type": fields["person_type"].text().strip() or "FISICA"}
            for key in ("cpf", "cnpj", "phone", "whatsapp", "email", "address"):
                data[key] = fields[key].text().strip()
            try:
                self.ctx.customers.update(customer["id"], data)
                info(dlg, "OK", "Cliente alterado.")
                dlg.accept()
                self._refresh()
            except Exception as exc:
                error(dlg, "Erro", str(exc))

        btn = primary_button("Salvar alterações", "success")
        btn.clicked.connect(save)
        lay.addWidget(btn)
        dlg.exec()

    def delete_customer(self):
        self.ctx.auth.require_permission("CUSTOMER_MANAGE")
        customer = self.selected()
        if not customer:
            return
        if not yes_no("Excluir cliente",
                      f"Excluir <b>{customer['name']}</b>?<br><br>"
                      "A ação fica registrada na auditoria (CLIENTE_REMOVIDO). "
                      "O cliente some da lista, mas o histórico de veículos, "
                      "mensalistas e tickets é preservado."):
            return
        try:
            removed = self.ctx.customers.delete(customer["id"])
        except Exception as exc:
            error(self, "Erro", str(exc))
            return
        if not removed:
            warn(self, "Exclusão bloqueada",
                 "Este cliente possui ticket em aberto, mensalidade em aberto ou "
                 "mensalista ativo. Encerre esses vínculos primeiro.")
            return
        info(self, "OK", "Cliente excluído.")
        self._refresh()

    def manage_vehicles(self):
        self.ctx.auth.require_permission("CUSTOMER_MANAGE")
        customer = self.selected()
        if not customer:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Veículos — {customer['name']}")
        dlg.resize(560, 440)
        lay = QVBoxLayout(dlg)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Placa", "Modelo", "Marca", "Cor", "Categoria"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        lay.addWidget(table)
        v_layout = ColumnLayout(self.ctx, table, f"clientes_veiculos_{customer['id']}")
        vehicles: list[dict] = []

        def fill():
            vehicles[:] = self.ctx.vehicles.by_customer(customer["id"])
            table.setRowCount(0)
            for v in vehicles:
                i = table.rowCount()
                table.insertRow(i)
                for c, val in enumerate([v.get("plate") or "", v.get("model") or "-",
                                         v.get("brand") or "-", v.get("color") or "-",
                                         v.get("category") or "-"]):
                    item = QTableWidgetItem(str(val))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    table.setItem(i, c, item)
            v_layout.resize_event()

        form = QHBoxLayout()
        boxes = {}
        for key, label in (("plate", "Placa*"), ("model", "Modelo"),
                           ("color", "Cor"), ("category", "Categoria")):
            box = QLineEdit()
            box.setPlaceholderText(label)
            if key == "category":
                box.setText("CARRO")
            boxes[key] = box
            form.addWidget(box)
        lay.addLayout(form)

        def add():
            plate = boxes["plate"].text().strip().upper()
            if len(plate) < 6:
                warn(dlg, "Validação", "Informe a placa do veículo.")
                return
            try:
                self.ctx.vehicles.create({
                    "customer_id": customer["id"],
                    "plate": plate,
                    "model": boxes["model"].text().strip(),
                    "brand": "",
                    "color": boxes["color"].text().strip(),
                    "category": boxes["category"].text().strip() or "CARRO",
                })
                boxes["plate"].clear()
                fill()
                self._refresh()
            except Exception as exc:
                error(dlg, "Erro", str(exc))

        def remove():
            row = table.currentRow()
            if row < 0 or row >= len(vehicles):
                warn(dlg, "Seleção", "Selecione um veículo.")
                return
            vehicle = vehicles[row]
            if not yes_no("Remover veículo",
                          f"Remover o veículo <b>{vehicle.get('plate')}</b>?<br><br>"
                          "Veículos com tickets ou mensalidade vinculada não podem "
                          "ser removidos."):
                return
            try:
                if not self.ctx.vehicles.delete(vehicle["id"]):
                    warn(dlg, "Remoção bloqueada",
                         "Este veículo possui histórico de tickets ou mensalidade "
                         "vinculada e não pode ser removido.")
                    return
                fill()
                self._refresh()
            except Exception as exc:
                error(dlg, "Erro", str(exc))

        fill()
        btns = QHBoxLayout()
        b_add = primary_button("Adicionar veículo", "success")
        b_add.clicked.connect(add)
        btns.addWidget(b_add)
        b_del = primary_button("Remover veículo", "danger")
        b_del.clicked.connect(remove)
        btns.addWidget(b_del)
        btns.addStretch(1)
        lay.addLayout(btns)
        dlg.exec()
