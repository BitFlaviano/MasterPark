"""Janela principal do MasterPark (sidebar + navegação)."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from app.boot_ui import build_screens
from app.domain.permissions import (ADMIN_ONLY_SCREENS, first_screen_for,
                                    hidden_menu_keys, is_admin_role, role_label)
from app.ui.icons import make_icon
from app.ui.search import GlobalSearchDialog
from app.ui.widgets import make_label

# (seção, [(texto, chave, ícone, atalho)])
MENU = [
    ("OPERAÇÃO", [
        ("Nova Entrada", "entry", "log-in", "F2"),
        ("Nova Saída", "exit", "log-out", "F3"),
        ("Mapa de Vagas", "map", "map", ""),
        ("Tickets", "tickets", "tag", "F4"),
    ]),
    ("GESTÃO", [
        ("Dashboard", "dashboard", "grid", ""),
        ("Mensalistas", "monthly", "calendar", "F6"),
        ("Clientes", "customers", "user", "F7"),
    ]),
    ("FINANCEIRO", [
        ("Caixa", "cash", "dollar", "F5"),
        ("Relatórios", "reports", "trending", "F9"),
    ]),
    ("SISTEMA", [
        ("Configurações", "settings", "sliders", ""),
        ("Saúde do Sistema", "health", "activity", ""),
        ("Usuários", "users", "users", ""),
        ("Auditoria", "audit", "shield", ""),
        ("Sobre o Sistema", "about", "info", ""),
    ]),
]

# cores dos ícones: (claro, escuro)
ICON_NAV = ("#475569", "#94A3B8")
ICON_NAV_ACTIVE = ("#1D4ED8", "#FFFFFF")
ICON_TOOL = ("#475569", "#CBD5E1")
ICON_DANGER = ("#B91C1C", "#F87171")


def _sections_to_hide(hidden_keys) -> tuple[str, ...]:
    """Títulos de seção sem nenhum item visível dado o conjunto oculto."""
    hidden = set(hidden_keys)
    return tuple(
        title for title, entries in MENU
        if entries and all(key in hidden for _text, key, _icon, _shot in entries))


def _is_dark(ctx) -> bool:
    try:
        return ctx.settings.theme == "dark"
    except AttributeError:
        return False


def _pick(pair: tuple[str, str], dark: bool) -> str:
    return pair[1] if dark else pair[0]


def _repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


class NavItem(QPushButton):
    """Item do menu lateral: ícone de linha + texto."""

    def __init__(self, text: str, key: str, icon_name: str, parent=None):
        super().__init__(f"  {text}", parent)
        self.key = key
        self.icon_name = icon_name
        self.setObjectName("navItem")
        self.setFixedHeight(36)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)   # não rouba foco ao clicar

    def refresh(self, dark: bool, active: bool) -> None:
        color = _pick(ICON_NAV_ACTIVE if active else ICON_NAV, dark)
        self.setIcon(make_icon(self.icon_name, color))


class Sidebar(QWidget):
    def __init__(self, ctx, on_navigate, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        # sem isto o Qt NÃO pinta background/border do stylesheet em QWidget customizado
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(248)
        self.ctx = ctx
        self.on_navigate = on_navigate
        self._items: dict[str, NavItem] = {}
        self._section_labels: dict[str, QWidget] = {}
        self._active = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 18, 12, 14)
        lay.setSpacing(1)

        # marca
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(6, 0, 0, 0)
        brand_row.setSpacing(10)
        logo = make_label("P", "logo")
        logo.setFixedSize(38, 38)
        logo.setAlignment(Qt.AlignCenter)
        brand_row.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(make_label("MasterPark", "brand"))
        names.addWidget(make_label("Gestão de Estacionamentos", "brandSub"))
        brand_row.addLayout(names, 1)
        lay.addLayout(brand_row)
        lay.addSpacing(14)

        dark = _is_dark(ctx)
        for title, entries in MENU:
            lay.addSpacing(8)
            section_label = make_label(title, "navSection")
            lay.addWidget(section_label)
            self._section_labels[title] = section_label
            for text, key, icon_name, shortcut in entries:
                item = NavItem(text, key, icon_name)
                if shortcut:
                    item.setToolTip(f"Atalho: {shortcut}")
                item.clicked.connect(lambda _checked=False, k=key: self.on_navigate(k))
                item.refresh(dark, False)
                lay.addWidget(item)
                self._items[key] = item

        lay.addStretch(1)
        ver = make_label(f"v{ctx.version}", "subtitle")
        ver.setAlignment(Qt.AlignCenter)
        lay.addWidget(ver)

    def set_active(self, key: str):
        self._active = key
        dark = _is_dark(self.ctx)
        for k, item in self._items.items():
            active = k == key
            item.setObjectName("navItemActive" if active else "navItem")
            _repolish(item)
            item.refresh(dark, active)

    def refresh_theme(self):
        """Recolore os ícones depois de alternar claro/escuro."""
        dark = _is_dark(self.ctx)
        for k, item in self._items.items():
            item.refresh(dark, k == self._active)

    def apply_permissions(self, user):
        hidden = hidden_menu_keys(user.role, user.permissions)
        for key in hidden:
            if key in self._items:
                self._items[key].hide()
        # esconde o título da seção quando não sobra nenhum item nela
        for title in _sections_to_hide(hidden):
            label = self._section_labels.get(title)
            if label is not None:
                label.hide()


class TopBar(QWidget):
    def __init__(self, ctx, on_navigate, on_theme_changed=None, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setAttribute(Qt.WA_StyledBackground, True)   # ver comentário em Sidebar
        self.setFixedHeight(60)
        self.ctx = ctx
        self.on_navigate = on_navigate
        self.on_theme_changed = on_theme_changed
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(10)

        user = ctx.auth.current()
        if user:
            lay.addWidget(make_label(f"Olá, {user.name}", "greeting"))
            try:
                role = role_label(user.role)
            except Exception:
                role = user.role
            lay.addWidget(make_label(str(role), "chip"))
        lay.addStretch(1)

        self.btn_cash = QPushButton("Caixa: —")
        self.btn_cash.setObjectName("outline")
        self.btn_cash.setCursor(Qt.PointingHandCursor)
        self.btn_cash.clicked.connect(lambda: self.on_navigate("cash"))
        lay.addWidget(self.btn_cash)

        self.btn_search = QPushButton("Buscar  ·  Ctrl+K")
        self.btn_search.setObjectName("outline")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.setIconSize(QSize(16, 16))
        self.btn_search.clicked.connect(self.open_search)
        lay.addWidget(self.btn_search)

        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("iconBtn")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setIconSize(QSize(18, 18))
        self.btn_theme.setToolTip("Alternar tema claro/escuro")
        self.btn_theme.clicked.connect(self.toggle_theme)
        lay.addWidget(self.btn_theme)

        divider = QFrame()
        divider.setObjectName("vline")
        divider.setFixedSize(1, 24)
        lay.addWidget(divider)

        self.btn_logout = QPushButton("Sair")
        self.btn_logout.setObjectName("ghostDanger")
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.setIconSize(QSize(16, 16))
        self.btn_logout.clicked.connect(self.logout)
        lay.addWidget(self.btn_logout)

        self.refresh_theme()

    def refresh_theme(self):
        dark = _is_dark(self.ctx)
        tool = _pick(ICON_TOOL, dark)
        self.btn_search.setIcon(make_icon("search", tool, 16))
        self.btn_theme.setIcon(make_icon("sun" if dark else "moon", tool))
        self.btn_logout.setIcon(make_icon("log-out", _pick(ICON_DANGER, dark), 16))

    def open_search(self):
        dlg = GlobalSearchDialog(self.ctx, self)
        if dlg.exec() and dlg.result_data:
            key, value = dlg.result_data
            self.on_navigate(key, value)

    def toggle_theme(self):
        self.ctx.save_settings(theme="light" if self.ctx.settings.theme == "dark" else "dark")
        app = QApplication.instance()
        if app:
            from app.ui.theme import build_stylesheet
            app.setStyleSheet(build_stylesheet(self.ctx.settings.theme == "dark"))
        self.refresh_theme()
        if self.on_theme_changed:
            self.on_theme_changed()

    def logout(self):
        self.ctx.auth.logout()
        app = QApplication.instance()
        if app:
            app.exit(0)

    def _set_cash(self, text: str, name: str) -> None:
        self.btn_cash.setText(text)
        if self.btn_cash.objectName() != name:
            self.btn_cash.setObjectName(name)
            _repolish(self.btn_cash)

    def refresh_cash(self):
        user = self.ctx.auth.current()
        if not user:
            return
        try:
            status = self.ctx.cash.status(user)
            if status.get("open"):
                self._set_cash(f"●  Caixa #{status['register_id']} aberto", "cashOpen")
            else:
                self._set_cash("●  Caixa fechado — Abrir", "cashClosed")
        except Exception:
            self._set_cash("Caixa: —", "outline")


class MainWindow(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("MasterPark — Sistema de Gestão de Estacionamentos")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 700)
        self.setObjectName("root")

        self.root = QHBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)

        self.sidebar = Sidebar(ctx, self.navigate)
        self.root.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.topbar = TopBar(ctx, self.navigate, self._on_theme_changed)
        right.addWidget(self.topbar)

        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        self.root.addLayout(right)

        self.screens = build_screens(ctx, self)
        for page in self.screens.values():
            self.stack.addWidget(page)

        self.KEYBOARD = {
            "F2": "entry", "F3": "exit", "F4": "tickets", "F5": "cash",
            "F6": "monthly", "F7": "customers", "F9": "reports",
        }
        self.navigate(self.require_first_screen())

    def require_first_screen(self):
        user = self.ctx.auth.current()
        return first_screen_for(user.role if user else "")

    def _on_theme_changed(self):
        self.sidebar.refresh_theme()
        self.topbar.refresh_theme()

    # ------------------------------------------------------------------
    def navigate(self, key: str, payload=None):
        if isinstance(payload, tuple) and len(payload) == 2:
            key, payload = payload
        page = self.screens.get(key)
        if not page:
            return
        user = self.ctx.auth.current()
        if key in ADMIN_ONLY_SCREENS and not (user and is_admin_role(user.role)):
            return  # tentativa de abrir recurso de administrador
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        if payload and hasattr(page, "load_payload"):
            page.load_payload(payload)
        if hasattr(page, "on_show"):
            page.on_show()
        self.topbar.refresh_cash()

    def keyPressEvent(self, event):
        from PySide6.QtGui import QKeySequence
        shot = QKeySequence(event)
        up = shot.toString().upper()
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_K:
            self.topbar.open_search()
            return
        if up in self.KEYBOARD:
            self.navigate(self.KEYBOARD[up])
            return
        super().keyPressEvent(event)


def nav_button(text: str, kind: str = "primary") -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(kind)
    btn.setCursor(Qt.PointingHandCursor)
    return btn
