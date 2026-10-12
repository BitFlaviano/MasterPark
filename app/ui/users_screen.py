"""Gestão de usuários: listar, criar, alterar senha/perfil e excluir."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLineEdit,
                               QMenu, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from app.core.security import PasswordService
from app.domain.permissions import PERMISSIONS, ROLES, role_label
from app.domain.models import parse_iso
from app.ui.theme import DANGER, SUCCESS
from app.ui.widgets import (Card, SearchField, error, make_label, page_header,
                            primary_button, warn, yes_no)

STATUS = {1: "Ativo", 0: "Inativo"}

# Mesma regra do AuthService (create_user / change_password).
MIN_PASSWORD = 8

WARNING = "#B45309"   # âmbar: atenção (falhas de login, bloqueio vencido)
MUTED = "#64748B"     # cinza: usuário inativo / textos de apoio

COLUMNS = ["ID", "Usuário", "Nome", "Perfil", "Status", "Último acesso", "Criado em"]
COL_ID, COL_USER, COL_NAME, COL_ROLE, COL_STATUS, COL_LOGIN, COL_CREATED = range(7)

STATUS_FILTERS = [("Todos os status", "all"), ("Ativos", "active"),
                  ("Inativos", "inactive"), ("Bloqueados", "locked")]

NO_PERMISSION = "Você não tem permissão para gerenciar usuários."


# ----------------------------------------------------------------------
# Utilitários
# ----------------------------------------------------------------------
def _fmt_dt(value, fmt: str) -> tuple[str, str]:
    """(texto para exibir no horário local, chave de ordenação)."""
    if not value:
        return "—", ""
    try:
        return parse_iso(value).astimezone().strftime(fmt), str(value)
    except (ValueError, TypeError, AttributeError):
        return str(value)[:16].replace("T", " "), str(value)


def _perm_label(code: str) -> str:
    value = PERMISSIONS.get(code)
    if isinstance(value, (tuple, list)) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return code


class _Item(QTableWidgetItem):
    """Item que ordena pela chave em UserRole (datas e números corretos)."""

    def __lt__(self, other):
        a = self.data(Qt.ItemDataRole.UserRole)
        b = other.data(Qt.ItemDataRole.UserRole)
        if a is not None and b is not None:
            try:
                return a < b
            except TypeError:
                pass
        return super().__lt__(other)


# ----------------------------------------------------------------------
# Tela
# ----------------------------------------------------------------------
class UsersScreen(QWidget):
    """Lista os usuários do sistema e permite criar, alterar e excluir."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.rows: list[dict] = []
        self.filter = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Usuários",
                                  "Contas de acesso, perfis e permissões"))

        # --- Linha 1: busca, filtro e criação --------------------------
        top = QHBoxLayout()
        top.setSpacing(8)
        self.box = SearchField("Buscar por nome, usuário ou perfil...")
        self.box.textChanged.connect(self._filter)
        top.addWidget(self.box, 1)

        self.f_status = QComboBox()
        for label, code in STATUS_FILTERS:
            self.f_status.addItem(label, code)
        self.f_status.setMinimumWidth(150)
        self.f_status.currentIndexChanged.connect(lambda _i: self._refresh())
        top.addWidget(self.f_status)

        self.btn_new = primary_button("+ Novo Usuário", "primary")
        self.btn_new.clicked.connect(self.new_user)
        top.addWidget(self.btn_new)
        lay.addLayout(top)

        # --- Linha 2: ações do usuário selecionado ---------------------
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.sel_label = make_label("", "subtitle")
        bar.addWidget(self.sel_label, 1)

        self.btn_edit = primary_button("Alterar", "")
        self.btn_edit.clicked.connect(self.edit_user)
        self.btn_pass = primary_button("Redefinir senha", "ghost")
        self.btn_pass.clicked.connect(self.reset_password)
        self.btn_unlock = primary_button("Desbloquear", "ghost")
        self.btn_unlock.clicked.connect(self.unlock_user)
        self.btn_toggle = primary_button("Desativar", "ghost")
        self.btn_toggle.clicked.connect(self.toggle_active)
        self.btn_del = primary_button("Excluir", "danger")
        self.btn_del.clicked.connect(self.delete_user)
        for btn in (self.btn_edit, self.btn_pass, self.btn_unlock,
                    self.btn_toggle, self.btn_del):
            bar.addWidget(btn)
        lay.addLayout(bar)

        # --- Tabela ----------------------------------------------------
        card = Card()
        t = self.table = QTableWidget(0, len(COLUMNS))
        t.setHorizontalHeaderLabels(COLUMNS)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        t.setAlternatingRowColors(True)
        t.setShowGrid(False)
        t.setWordWrap(False)
        t.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(38)

        head = t.horizontalHeader()
        head.setStretchLastSection(False)
        head.setMinimumSectionSize(60)
        for col in range(len(COLUMNS)):
            head.setSectionResizeMode(
                col, QHeaderView.ResizeMode.Stretch if col == COL_NAME
                else QHeaderView.ResizeMode.ResizeToContents)
        t.setSortingEnabled(True)
        t.sortByColumn(COL_ID, Qt.SortOrder.AscendingOrder)

        t.doubleClicked.connect(lambda _i: self.edit_user())
        t.itemSelectionChanged.connect(self._update_actions)
        t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        t.customContextMenuRequested.connect(self._context_menu)
        card.body.addWidget(t)

        self.empty = make_label("", "subtitle")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setMinimumHeight(140)
        self.empty.hide()
        card.body.addWidget(self.empty)
        lay.addWidget(card, 1)

        # --- Rodapé: contagem + feedback das ações ---------------------
        foot = QHBoxLayout()
        self.count = make_label("", "subtitle")
        foot.addWidget(self.count, 1)
        self.status = make_label("", "subtitle")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        foot.addWidget(self.status)
        lay.addLayout(foot)

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self.status.setText(""))

        self._update_actions()

    # ------------------------------------------------------------------
    def on_show(self):
        self._refresh()

    def _flash(self, text: str, kind: str = "ok") -> None:
        """Mensagem rápida no rodapé (substitui pop-ups de 'OK')."""
        color = {"ok": SUCCESS, "warn": WARNING}.get(kind, MUTED)
        self.status.setStyleSheet(f"color:{color}; font-weight:600;")
        self.status.setText(text)
        self._flash_timer.start(6000)

    # ------------------------------------------------------------------
    # Dados
    # ------------------------------------------------------------------
    def _is_locked(self, r: dict) -> bool:
        return bool(r.get("locked_until")) and not self.ctx.users.lock_expired(r)

    def _lock_left(self, row: dict) -> int:
        try:
            delta = parse_iso(row["locked_until"]) - datetime.now(timezone.utc)
            return max(0, int(delta.total_seconds() // 60) + 1)
        except (ValueError, TypeError, KeyError):
            return 0

    def _status_info(self, r: dict) -> tuple[str, str, str]:
        """(texto, cor, dica) do status do usuário."""
        fails = r.get("failed_attempts") or 0
        if not r.get("is_active", 1):
            return STATUS[0], MUTED, "Acesso desativado."
        if r.get("locked_until"):
            if self.ctx.users.lock_expired(r):
                return ("Bloqueio expirado", WARNING,
                        "O prazo do bloqueio já passou; o próximo login libera a conta.")
            return (f"Bloqueado · {self._lock_left(r)} min", DANGER,
                    "Conta bloqueada por excesso de tentativas de login.")
        if fails:
            return (f"{STATUS[1]} · {fails} falha(s)", WARNING,
                    f"{fails} tentativa(s) de login com senha incorreta.")
        return STATUS[1], SUCCESS, ""

    def _matches(self, r: dict, term: str, mode: str) -> bool:
        if term:
            hay = f"{r.get('username', '')} {r.get('name', '')} {r.get('role_name') or ''}".lower()
            if term not in hay:
                return False
        active = bool(r.get("is_active", 1))
        if mode == "active":
            return active
        if mode == "inactive":
            return not active
        if mode == "locked":
            return self._is_locked(r)
        return True

    def _refresh(self, keep_id: int | None = None):
        keep = keep_id if keep_id is not None else self._current_id()
        self.rows = self.ctx.users.list()
        term = self.filter.strip().lower()
        mode = self.f_status.currentData()
        visible = [r for r in self.rows if self._matches(r, term, mode)]

        t = self.table
        t.setSortingEnabled(False)   # evita reordenar linha a linha durante o preenchimento
        t.setRowCount(0)
        t.setRowCount(len(visible))
        left_center = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        for i, r in enumerate(visible):
            status, color, tip = self._status_info(r)
            login_txt, login_key = _fmt_dt(r.get("last_login_at"), "%d/%m/%Y %H:%M")
            created_txt, created_key = _fmt_dt(r.get("created_at"), "%d/%m/%Y")
            cells = [
                (r.get("id"), r.get("id")),
                (r.get("username", ""), (r.get("username") or "").lower()),
                (r.get("name", ""), (r.get("name") or "").lower()),
                (r.get("role_name") or role_label(r.get("role_code", "")), None),
                (status, status),
                (login_txt, login_key),
                (created_txt, created_key),
            ]
            for c, (text, key) in enumerate(cells):
                item = _Item(str(text))
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if c == COL_ID
                                      else left_center)
                if not r.get("is_active", 1):
                    item.setForeground(QBrush(QColor(MUTED)))
                if c == COL_STATUS:
                    item.setForeground(QBrush(QColor(color)))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    if tip:
                        item.setToolTip(tip)
                t.setItem(i, c, item)
        t.setSortingEnabled(True)

        # restaura a seleção anterior, se o usuário ainda estiver visível
        t.clearSelection()
        if keep is not None:
            for i in range(t.rowCount()):
                it = t.item(i, COL_ID)
                if it and it.data(Qt.ItemDataRole.UserRole) == keep:
                    t.selectRow(i)
                    break

        # estado vazio
        has_rows = bool(visible)
        t.setVisible(has_rows)
        self.empty.setVisible(not has_rows)
        if not has_rows:
            self.empty.setText(
                "Nenhum usuário cadastrado." if not self.rows
                else "Nenhum usuário encontrado com os filtros atuais.")
        self.count.setText(f"{len(visible)} de {len(self.rows)} usuário(s)")
        self._update_actions()

    def _filter(self):
        self.filter = self.box.text()
        self._refresh()

    # ------------------------------------------------------------------
    # Seleção e estado dos botões
    # ------------------------------------------------------------------
    def _current_id(self) -> int | None:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return None
        item = self.table.item(sel[0].row(), COL_ID)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected(self, silent: bool = False) -> dict | None:
        uid = self._current_id()
        if uid is None:
            if not silent:
                warn(self, "Seleção", "Selecione um usuário na lista.")
            return None
        for r in self.rows:
            if r["id"] == uid:
                return r
        return None

    def _update_actions(self):
        can_manage = self.ctx.auth.can("USER_MANAGE")
        row = self._selected(silent=True)
        me = self.ctx.auth.current()
        is_me = bool(row and me and me.id == row["id"])
        has = bool(row) and can_manage
        locked = bool(row and (row.get("locked_until") or row.get("failed_attempts")))
        active = bool(row.get("is_active", 1)) if row else True

        self.btn_new.setEnabled(can_manage)
        self.btn_new.setToolTip("" if can_manage else NO_PERMISSION)
        self.btn_toggle.setText("Desativar" if active else "Ativar")

        self.btn_edit.setEnabled(has)
        self.btn_pass.setEnabled(has)
        self.btn_unlock.setEnabled(has and locked)
        self.btn_toggle.setEnabled(has and not is_me)
        self.btn_del.setEnabled(has and not is_me)

        self.btn_unlock.setToolTip(
            "Este usuário não está bloqueado." if has and not locked else "")
        own = "Você não pode fazer isso com o próprio usuário." if has and is_me else ""
        self.btn_toggle.setToolTip(own)
        self.btn_del.setToolTip(own)

        if not can_manage:
            self.sel_label.setText(NO_PERMISSION)
        elif row:
            self.sel_label.setText(
                f"Selecionado: <b>{escape(str(row.get('name', '')))}</b> "
                f"({escape(str(row.get('username', '')))})")
        else:
            self.sel_label.setText("Selecione um usuário para ver as ações.")

    def _context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid():
            return
        self.table.selectRow(idx.row())
        menu = QMenu(self)
        entries = [(self.btn_edit, self.edit_user), (self.btn_pass, self.reset_password),
                   (self.btn_unlock, self.unlock_user), (self.btn_toggle, self.toggle_active),
                   None, (self.btn_del, self.delete_user)]
        for entry in entries:
            if entry is None:
                menu.addSeparator()
                continue
            btn, handler = entry
            act = menu.addAction(btn.text())
            act.setEnabled(btn.isEnabled())
            act.triggered.connect(handler)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _guard(self):
        try:
            return self.ctx.auth.require_permission("USER_MANAGE")
        except Exception as exc:
            warn(self, "Sem permissão", str(exc))
            return None

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
    def new_user(self):
        if self._guard() is None:
            return
        dlg = _UserDialog(self.ctx, None, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        user = self.ctx.auth.current()
        try:
            h, s = PasswordService.hash_password(v["password"])
            uid = self.ctx.users.create(v["username"], v["name"], h, s,
                                        v["role_code"], v["terminal"])
            self.ctx.audit.add(user, "USUARIO_CRIADO", "user", uid,
                               new=f"{v['username']} · {v['name']} · {v['role_code']}")
        except Exception as exc:
            error(self, "Erro", str(exc))
            return
        self._refresh(keep_id=uid)
        self._flash(f"Usuário “{v['username']}” criado.")

    def edit_user(self):
        if self._guard() is None:
            return
        row = self._selected()
        if not row:
            return
        dlg = _UserDialog(self.ctx, row, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if (v["name"] == row["name"] and v["role_code"] == row["role_code"]
                and v["terminal"] == (row.get("terminal") or "")):
            self._flash("Nenhuma alteração feita.", "muted")
            return
        user = self.ctx.auth.current()
        try:
            self.ctx.users.update_profile(row["id"], name=v["name"],
                                          role_code=v["role_code"])
            self.ctx.db.execute("UPDATE users SET terminal=? WHERE id=?",
                                (v["terminal"], row["id"]))
            self.ctx.audit.add(user, "USUARIO_ALTERADO", "user", row["id"],
                               old=f"{row['name']} · {row['role_code']}",
                               new=f"{v['name']} · {v['role_code']}")
        except Exception as exc:
            error(self, "Erro", str(exc))
            return
        self._refresh(keep_id=row["id"])
        self._flash("Usuário alterado.")

    def unlock_user(self):
        if self._guard() is None:
            return
        row = self._selected()
        if not row:
            return
        if not (row.get("locked_until") or row.get("failed_attempts")):
            self._flash("Este usuário não está bloqueado.", "muted")
            return
        if not yes_no("Desbloquear usuário",
                      f"Limpar o bloqueio e as tentativas falhas de "
                      f"<b>{escape(row['name'])}</b> ({escape(row['username'])})?"):
            return
        try:
            self.ctx.users.clear_lock(row["id"])
            self.ctx.audit.add(self.ctx.auth.current(), "USUARIO_DESBLOQUEADO",
                               "user", row["id"], new=row["username"])
        except Exception as exc:
            error(self, "Erro", str(exc))
            return
        self._refresh(keep_id=row["id"])
        self._flash("Usuário desbloqueado.")

    def toggle_active(self):
        if self._guard() is None:
            return
        row = self._selected()
        if not row:
            return
        current = self.ctx.auth.current()
        if current and current.id == row["id"]:
            warn(self, "Usuário", "Você não pode desativar o próprio usuário.")
            return
        novo = 0 if row.get("is_active", 1) else 1
        acao, feito = ("ativar", "ativado") if novo else ("desativar", "desativado")
        if not yes_no(f"{acao.capitalize()} usuário",
                      f"{acao.capitalize()} o acesso de "
                      f"<b>{escape(row['name'])}</b> ({escape(row['username'])})?"):
            return
        try:
            self.ctx.users.update_profile(row["id"], is_active=novo)
            self.ctx.audit.add(current, "USUARIO_ALTERADO", "user", row["id"],
                               old="ativo" if not novo else "inativo",
                               new="ativo" if novo else "inativo")
        except Exception as exc:
            error(self, "Erro", str(exc))
            return
        self._refresh(keep_id=row["id"])
        self._flash(f"Usuário {feito}.")

    def reset_password(self):
        if self._guard() is None:
            return
        row = self._selected()
        if not row:
            return
        dlg = _PasswordDialog(row, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        current = self.ctx.auth.current()
        try:
            h, s = PasswordService.hash_password(dlg.password())
            self.ctx.users.set_password(row["id"], h, s)
            self.ctx.audit.add(current, "SENHA_ALTERADA", "user", row["id"],
                               new=f"{row['username']}")
        except Exception as exc:
            error(self, "Erro", str(exc))
            return
        self._refresh(keep_id=row["id"])
        self._flash("Senha redefinida.")

    def delete_user(self):
        if self._guard() is None:
            return
        row = self._selected()
        if not row:
            return
        current = self.ctx.auth.current()
        if current and current.id == row["id"]:
            warn(self, "Excluir usuário",
                 "Você não pode excluir o próprio usuário.")
            return
        admins = [u for u in self.ctx.users.list()
                  if u.get("role_code") == "ADMINISTRADOR" and u.get("is_active", 1)]
        if row.get("role_code") == "ADMINISTRADOR" and len(admins) <= 1:
            warn(self, "Excluir usuário",
                 "Este é o último administrador ativo — o sistema ficaria "
                 "sem ninguém capaz de gerenciar usuários.")
            return
        if not yes_no("Excluir usuário",
                      f"Excluir <b>{escape(row['name'])}</b> ({escape(row['username'])})?<br><br>"
                      "Os registros criados por este usuário (tickets, caixa, "
                      "auditoria) são preservados, mas o acesso será removido."):
            return
        try:
            self.ctx.db.execute("DELETE FROM user_permissions WHERE user_id=?",
                                (row["id"],))
            self.ctx.db.execute("DELETE FROM users WHERE id=?", (row["id"],))
            self.ctx.audit.add(current, "USUARIO_REMOVIDO", "user", row["id"],
                               new=f"{row['name']} ({row['username']})")
        except Exception as exc:
            error(self, "Erro", str(exc))
            return
        self._refresh(keep_id=-1)   # nada selecionado após excluir
        self._flash("Usuário excluído.")


# ----------------------------------------------------------------------
# Diálogos
# ----------------------------------------------------------------------
class _DialogBase(QDialog):
    """Estrutura comum: formulário, mensagem de erro inline e botões."""

    def __init__(self, title: str, subtitle: str, min_width: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)

        self.out = QVBoxLayout(self)
        self.out.setContentsMargins(20, 18, 20, 16)
        self.out.setSpacing(12)
        self.out.addWidget(make_label(title, "h3"))
        sub = make_label(subtitle, "subtitle")
        sub.setWordWrap(True)
        self.out.addWidget(sub)

        self.form = QFormLayout()
        self.form.setSpacing(10)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.out.addLayout(self.form)

    def finish(self, ok_text: str, ok_variant: str, on_ok):
        """Adiciona a mensagem de erro e a linha de botões (chamar por último)."""
        self.err = make_label("", "subtitle")
        self.err.setStyleSheet(f"color:{DANGER}; font-weight:600;")
        self.err.setWordWrap(True)
        self.err.hide()
        self.out.addWidget(self.err)

        box = QHBoxLayout()
        box.addStretch(1)
        b_cancel = primary_button("Cancelar", "ghost")
        b_cancel.clicked.connect(self.reject)
        box.addWidget(b_cancel)
        b_ok = primary_button(ok_text, ok_variant)
        b_ok.setDefault(True)          # Enter confirma
        b_ok.clicked.connect(on_ok)
        box.addWidget(b_ok)
        self.out.addLayout(box)

    def fail(self, message: str, field: QLineEdit | None = None) -> None:
        self.err.setText(message)
        self.err.show()
        if field is not None:
            field.setFocus()
            field.selectAll()


class _UserDialog(_DialogBase):
    """Formulário de criação/edição de usuário."""

    def __init__(self, ctx, row, parent=None):
        editing = bool(row)
        super().__init__(
            "Alterar usuário" if editing else "Novo usuário",
            "O login não pode ser alterado; edite nome, perfil e terminal." if editing
            else "Preencha os dados de acesso. A senha pode ser trocada depois "
                 "em “Redefinir senha”.",
            480, parent)
        self.ctx = ctx
        self.row = row

        self.f_user = QLineEdit(row["username"] if editing else "")
        self.f_user.setPlaceholderText("ex.: maria.silva")
        if editing:
            self.f_user.setReadOnly(True)
        self.form.addRow("Login:", self.f_user)

        self.f_name = QLineEdit(row["name"] if editing else "")
        self.f_name.setPlaceholderText("Nome completo")
        self.form.addRow("Nome:", self.f_name)

        self.f_role = QComboBox()
        current_role = row.get("role_code") if editing else "OPERADOR"
        for code, (label, _perms) in sorted(ROLES.items()):
            self.f_role.addItem(label, code)
            if code == current_role:
                self.f_role.setCurrentIndex(self.f_role.count() - 1)
        self.form.addRow("Perfil:", self.f_role)

        self.f_term = QLineEdit(row.get("terminal", "") or "" if editing else "")
        self.f_term.setPlaceholderText("ex.: PDV-01 (opcional)")
        self.form.addRow("Terminal:", self.f_term)

        self.f_pass = QLineEdit()
        self.f_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.f_pass.setPlaceholderText(f"mínimo {MIN_PASSWORD} caracteres")
        if not editing:
            self.form.addRow("Senha:", self.f_pass)
            show = QCheckBox("Mostrar senha")
            show.toggled.connect(lambda on: self.f_pass.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
            self.form.addRow("", show)

        if editing:
            perms = sorted(_perm_label(c) for c in self.ctx.users.permissions(row["id"]))
            box = Card("Permissões atuais")
            lbl = make_label(", ".join(perms) or "nenhuma", "subtitle")
            lbl.setWordWrap(True)
            box.body.addWidget(lbl)
            self.out.addWidget(box)
        else:
            lbl = make_label(
                f"“{_perm_label('USER_MANAGE')}” é exclusiva do perfil Administrador.",
                "subtitle")
            lbl.setWordWrap(True)
            self.out.addWidget(lbl)

        self.finish("Salvar" if editing else "Criar usuário", "success", self._validate)
        (self.f_name if editing else self.f_user).setFocus()

    def _validate(self):
        user = (self.f_user.text() or "").strip().lower()
        name = (self.f_name.text() or "").strip()
        if not user:
            return self.fail("Informe o login.", self.f_user)
        if not name:
            return self.fail("Informe o nome completo.", self.f_name)
        if not self.row:
            if self.ctx.users.get_by_username(user):
                return self.fail("Já existe um usuário com esse login.", self.f_user)
            if len(self.f_pass.text()) < MIN_PASSWORD:
                return self.fail(
                    f"A senha deve ter pelo menos {MIN_PASSWORD} caracteres.", self.f_pass)
        self.accept()

    def values(self) -> dict:
        return {
            "username": (self.f_user.text() or "").strip().lower(),
            "name": (self.f_name.text() or "").strip(),
            "role_code": self.f_role.currentData(),
            "terminal": (self.f_term.text() or "").strip(),
            "password": self.f_pass.text() if not self.row else "",
        }


class _PasswordDialog(_DialogBase):
    """Redefinição de senha de um usuário."""

    def __init__(self, row, parent=None):
        super().__init__(
            "Redefinir senha",
            f"Nova senha para <b>{escape(row['name'])}</b> ({escape(row['username'])}). "
            "Se a conta estiver bloqueada, o bloqueio também é removido.",
            440, parent)
        self.f1 = QLineEdit()
        self.f2 = QLineEdit()
        for f, ph in ((self.f1, f"Nova senha (mínimo {MIN_PASSWORD} caracteres)"),
                      (self.f2, "Repita a nova senha")):
            f.setEchoMode(QLineEdit.EchoMode.Password)
            f.setPlaceholderText(ph)
        self.form.addRow("Nova senha:", self.f1)
        self.form.addRow("Confirmação:", self.f2)

        show = QCheckBox("Mostrar senha")
        show.toggled.connect(self._toggle_echo)
        self.form.addRow("", show)

        self.finish("Redefinir", "primary", self._validate)
        self.f1.setFocus()

    def _toggle_echo(self, on: bool):
        mode = QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
        self.f1.setEchoMode(mode)
        self.f2.setEchoMode(mode)

    def _validate(self):
        p1, p2 = self.f1.text(), self.f2.text()
        if len(p1) < MIN_PASSWORD:
            return self.fail(
                f"A senha deve ter pelo menos {MIN_PASSWORD} caracteres.", self.f1)
        if p1 != p2:
            return self.fail("As senhas não conferem.", self.f2)
        self.accept()

    def password(self) -> str:
        return self.f1.text()
