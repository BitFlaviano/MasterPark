"""Design System MasterPark — cores, tipografia e folhas de estilo (Qt).

Um único template renderizado com tokens (claro/escuro), para que os dois
temas tenham exatamente a mesma estrutura visual. As cores de marca são
literais; as cores de superfície/hover/borda vêm dos dicionários LIGHT/DARK.
"""
from __future__ import annotations

import re

PRIMARY = "#4C6FFF"
PRIMARY_DARK = "#3B5BEA"
SUCCESS = "#22C55E"
DANGER = "#EF4444"
WARNING = "#F59E0B"
INFO = "#06B6D4"
TEXT = "#0F172A"
TEXT_DARK = "#EEF2FB"
SIDEBAR = "#101728"
SURFACE = "#FFFFFF"
SURFACE_DARK_TEXT = "#E2E8F0"
BG_DARK = "#0B1220"
PAGE_DARK = "#0F172A"
CARD_DARK = "#131C31"
RAISED_DARK = "#1E2A45"

SPACE_STATES = {
    "LIVRE": SUCCESS,
    "OCUPADA": DANGER,
    "RESERVADA": WARNING,
    "BLOQUEADA": "#64748B",
    "MANUTENCAO": "#A855F7",
}

# Tokens do tema claro
LIGHT = {
    "BG": "#F4F7FB",            # fundo da página
    "SIDEBAR": "#FFFFFF",       # menu lateral
    "SURFACE": "#FFFFFF",       # cartões, barra superior
    "SUBTLE": "#F8FAFC",        # cabeçalho de tabela, linhas alternadas
    "RAISED": "#F1F5F9",        # áreas elevadas / chips
    "HOVER": "#F1F5F9",         # hover de itens
    "FIELD": "#FFFFFF",         # fundo de campos
    "BORDER": "#E4EAF2",        # bordas de cartões e divisórias
    "BORDER2": "#D6E0EC",       # bordas de campos e botões
    "TEXT": "#0F172A",          # texto principal
    "TEXT2": "#334155",         # texto secundário (menu, rótulos)
    "MUTED": "#64748B",         # texto de apoio
    "FAINT": "#9AA8C0",         # desabilitado
    "TRACK": "#E7EDF5",         # fundo de progresso / trilho de rolagem
    "THUMB": "#C7D2E0",         # alça de rolagem
    "ACCENT": "#4C6FFF",        # cor de destaque
    "ACCENT_HOVER": "#3B5BEA",
    "ACCENT_SOFT": "#EEF3FF",   # fundo suave do item ativo / hover
    "ACCENT_SOFT2": "#DCE8FF",  # seleção em tabelas e listas
    "DANGER_SOFT": "#FEE2E2",
    "SUCCESS_SOFT": "#DCFCE7",
    "WARNING_SOFT": "#FEF3C7",
}

# Tokens do tema escuro (mesma estrutura do claro)
DARK = {
    "BG": "#0B1220",
    "SIDEBAR": "#101728",
    "SURFACE": "#131C31",
    "SUBTLE": "#1B2740",
    "RAISED": "#1E2A45",
    "HOVER": "#23304F",
    "FIELD": "#0E172A",
    "BORDER": "#26324D",
    "BORDER2": "#31405F",
    "TEXT": "#EEF2FB",
    "TEXT2": "#C6D2E4",
    "MUTED": "#8CA0C0",
    "FAINT": "#5E6F90",
    "TRACK": "#1E2A45",
    "THUMB": "#33415F",
    "ACCENT": "#4C6FFF",
    "ACCENT_HOVER": "#6480FF",
    "ACCENT_SOFT": "#1B2A52",
    "ACCENT_SOFT2": "#23345F",
    "DANGER_SOFT": "#3B1219",
    "SUCCESS_SOFT": "#0F3D28",
    "WARNING_SOFT": "#3B2A0A",
}

_TEMPLATE = r"""
* { font-family: 'Segoe UI', 'Arial'; font-size: 13px; }
QMainWindow, QWidget#root { background: @BG@; color: @TEXT@; }
QWidget { color: @TEXT@; }
QDialog, QMessageBox { background: @SURFACE@; }
QMessageBox QPushButton { min-width: 84px; }
QLabel { background: transparent; }
QLabel:disabled { color: @FAINT@; }
QToolTip { background: @TEXT2@; color: #FFFFFF; border: none; padding: 6px 9px; border-radius: 6px; }

/* ---------- Tipografia ---------- */
QLabel#title { font-size: 23px; font-weight: 800; color: @TEXT@; }
QLabel#subtitle { color: @MUTED@; }
QLabel#h3 { font-size: 15px; font-weight: 700; color: @TEXT@; }
QLabel#cardTitle { font-size: 13px; font-weight: 700; color: @TEXT@; letter-spacing: .3px; }
QLabel#greeting { font-size: 14px; font-weight: 700; color: @TEXT@; }
QLabel#statLabel { color: @MUTED@; font-weight: 600; }
QLabel#statValue { font-size: 26px; font-weight: 800; color: @TEXT@; }
QLabel#statValue[tone="primary"] { color: @ACCENT@; }
QLabel#statValue[tone="success"] { color: #16A34A; }
QLabel#statValue[tone="warning"] { color: #B45309; }
QLabel#statValue[tone="danger"] { color: #DC2626; }
QLabel#statValue[tone="info"] { color: #0E7490; }
QLabel#chip { background: @ACCENT_SOFT@; color: @ACCENT_HOVER@; border-radius: 10px; padding: 3px 10px; font-weight: 700; }
QLabel#chipGreen { background: @SUCCESS_SOFT@; color: #15803D; }

/* ---------- Menu lateral ---------- */
QWidget#sidebar { background: @SIDEBAR@; border-right: 1px solid @BORDER@; }
QLabel#logo { background: @ACCENT@; color: #FFFFFF; border-radius: 10px; font-size: 18px; font-weight: 800; }
QLabel#brand { font-size: 18px; font-weight: 800; color: @TEXT@; }
QLabel#brandSub { font-size: 12px; color: @MUTED@; }
QLabel#navSection { color: @MUTED@; font-size: 11px; font-weight: 700; padding: 4px 12px 2px 12px; letter-spacing: .6px; }
QPushButton#navItem { background: transparent; color: @TEXT2@; border: none; border-radius: 8px;
  padding: 0 12px; text-align: left; font-weight: 600; }
QPushButton#navItem:hover { background: @HOVER@; color: @TEXT@; }
QPushButton#navItemActive { background: @ACCENT_SOFT@; color: @ACCENT_HOVER@; border: none; border-radius: 8px;
  padding: 0 12px; text-align: left; font-weight: 700; }

/* ---------- Barra superior ---------- */
QWidget#topbar { background: @SURFACE@; border-bottom: 1px solid @BORDER@; }
QFrame#vline { background: @BORDER@; border: none; }

/* ---------- Cartões ---------- */
QFrame#card, QFrame#statCard { background: @SURFACE@; border: 1px solid @BORDER@; border-radius: 12px; }
QFrame#card QFrame#card { border-radius: 10px; }

/* ---------- Campos ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {
  background: @FIELD@; color: @TEXT@; border: 1px solid @BORDER2@; border-radius: 8px; padding: 7px 10px;
  selection-background-color: @ACCENT_SOFT2@; selection-color: @TEXT@;
  placeholder-text-color: @FAINT@; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover { border-color: @FAINT@; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid @ACCENT@; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled,
QTextEdit:disabled, QPlainTextEdit:disabled { background: @SUBTLE@; color: @FAINT@; border-color: @BORDER@; }
QLineEdit:read-only { background: @RAISED@; }
QComboBox { padding-right: 30px; }
QComboBox::drop-down {
  subcontrol-origin: padding; subcontrol-position: top right;
  width: 26px; border: none; border-top-right-radius: 7px;
  border-bottom-right-radius: 7px; background: transparent; }
QComboBox::drop-down:hover { background: @ACCENT_SOFT@;
  border-top-right-radius: 7px; border-bottom-right-radius: 7px; }
QComboBox::down-arrow { image: none; width: 0; height: 0;
  border-left: 4px solid transparent; border-right: 4px solid transparent;
  border-top: 5px solid @MUTED@; margin-right: 8px; }
QComboBox::down-arrow:hover { border-top-color: @ACCENT@; }
QComboBox::down-arrow:disabled { border-top-color: @FAINT@; }
QComboBox QAbstractItemView {
  background: @SURFACE@; border: 1px solid @BORDER@; border-radius: 8px;
  padding: 4px; outline: none; selection-background-color: @ACCENT_SOFT@;
  selection-color: @ACCENT_HOVER@; }
QComboBox QAbstractItemView::item { padding: 7px 9px 7px 6px; border-radius: 6px; min-height: 22px; }
QComboBox QAbstractItemView::item:hover { background: @HOVER@; border-radius: 6px; }
QComboBox QAbstractItemView::item:selected { background: @ACCENT_SOFT@; color: @ACCENT_HOVER@; border-radius: 6px; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
  background: transparent; border: none; width: 18px; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
  image: none; width: 0; height: 0; border-left: 3px solid transparent;
  border-right: 3px solid transparent; border-bottom: 4px solid @MUTED@; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
  image: none; width: 0; height: 0; border-left: 3px solid transparent;
  border-right: 3px solid transparent; border-top: 4px solid @MUTED@; }
QDateEdit::drop-down { subcontrol-origin: padding; subcontrol-position: top right;
  width: 24px; border: none; background: transparent; }
QDateEdit::drop-down:hover { background: @ACCENT_SOFT@; }
QDateEdit::down-arrow { image: none; width: 0; height: 0;
  border-left: 4px solid transparent; border-right: 4px solid transparent;
  border-top: 5px solid @MUTED@; margin-right: 6px; }

/* ---------- Botões ---------- */
QPushButton { background: @SURFACE@; color: @TEXT@; border: 1px solid @BORDER2@; border-radius: 8px;
  padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: @HOVER@; border-color: @FAINT@; }
QPushButton:pressed { background: @ACCENT_SOFT@; }
QPushButton:focus { border-color: @ACCENT@; }
QPushButton:disabled { background: @SUBTLE@; color: @FAINT@; border-color: @BORDER@; }
QPushButton#primary { background: @ACCENT@; color: #FFFFFF; border: 1px solid @ACCENT@; font-weight: 700; }
QPushButton#primary:hover { background: @ACCENT_HOVER@; border-color: @ACCENT_HOVER@; }
QPushButton#primary:pressed { background: @ACCENT@; }
QPushButton#primary:disabled { background: @ACCENT_SOFT2@; border-color: @ACCENT_SOFT2@; color: @FAINT@; }
QPushButton#success { background: #16A34A; color: #FFFFFF; border: 1px solid #16A34A; font-weight: 700; }
QPushButton#success:hover { background: #15803D; border-color: #15803D; }
QPushButton#success:disabled { background: @SUCCESS_SOFT@; border-color: @SUCCESS_SOFT@; color: @FAINT@; }
QPushButton#danger { background: #DC2626; color: #FFFFFF; border: 1px solid #DC2626; font-weight: 700; }
QPushButton#danger:hover { background: #B91C1C; border-color: #B91C1C; }
QPushButton#danger:disabled { background: @DANGER_SOFT@; border-color: @DANGER_SOFT@; color: @FAINT@; }
QPushButton#ghost { background: transparent; color: @ACCENT@; border: 1px solid transparent; }
QPushButton#ghost:hover { background: @ACCENT_SOFT@; border-color: transparent; }
QPushButton#ghost:disabled { background: transparent; color: @FAINT@; border-color: transparent; }
QPushButton#outline { background: @SURFACE@; color: @TEXT2@; border: 1px solid @BORDER2@; font-weight: 600; }
QPushButton#outline:hover { background: @HOVER@; }
QPushButton#iconBtn { background: @SURFACE@; border: 1px solid @BORDER2@; padding: 0; min-width: 36px; max-width: 36px;
  min-height: 34px; max-height: 34px; }
QPushButton#iconBtn:hover { background: @HOVER@; }
QPushButton#ghostDanger { background: transparent; color: #B91C1C; border: 1px solid transparent; font-weight: 700; }
QPushButton#ghostDanger:hover { background: @DANGER_SOFT@; }
QPushButton#cashOpen { background: @SUCCESS_SOFT@; color: #15803D; border: 1px solid #BBF7D0; font-weight: 700; }
QPushButton#cashOpen:hover { background: #BBF7D0; }
QPushButton#cashClosed { background: @WARNING_SOFT@; color: #B45309; border: 1px solid #FDE68A; font-weight: 700; }
QPushButton#cashClosed:hover { background: #FDE68A; }

/* ---------- Tabelas ---------- */
QTableWidget { background: @SURFACE@; border: 1px solid @BORDER@; border-radius: 10px;
  gridline-color: @BORDER@; alternate-background-color: @SUBTLE@;
  selection-background-color: @ACCENT_SOFT2@; selection-color: @TEXT@; outline: none; }
QTableWidget::item { padding: 6px 8px; border: none; }
QTableWidget::item:hover { background: @HOVER@; }
QTableWidget::item:selected { background: @ACCENT_SOFT2@; color: @TEXT@; }
QHeaderView { background: @SUBTLE@; border: none; }
QHeaderView::section { background: @SUBTLE@; color: @MUTED@; font-weight: 700; font-size: 12px;
  border: none; border-bottom: 1px solid @BORDER@; padding: 10px 8px; text-align: left; }
QTableCornerButton::section { background: @SUBTLE@; border: none; }

/* ---------- Abas ---------- */
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: transparent; color: @MUTED@; padding: 8px 16px; border-radius: 8px; font-weight: 700; }
QTabBar::tab:hover { background: @HOVER@; color: @TEXT@; border-radius: 8px; }
QTabBar::tab:selected { background: @ACCENT_SOFT@; color: @ACCENT_HOVER@; border-radius: 8px; }

/* ---------- Listas ---------- */
QListWidget { background: @SURFACE@; border: 1px solid @BORDER@; border-radius: 8px; outline: none; }
QListWidget::item { padding: 8px 10px; border-radius: 6px; }
QListWidget::item:hover { background: @HOVER@; border-radius: 6px; }
QListWidget::item:selected { background: @ACCENT_SOFT2@; color: @TEXT@; border-radius: 6px; }

/* ---------- Menus ---------- */
QMenu { background: @SURFACE@; border: 1px solid @BORDER@; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 7px 24px 7px 12px; border-radius: 6px; }
QMenu::item:selected { background: @ACCENT_SOFT@; color: @TEXT@; }
QMenu::item:disabled { color: @FAINT@; }
QMenu::separator { height: 1px; background: @BORDER@; margin: 4px 8px; }

/* ---------- Progresso ---------- */
QProgressBar { border: none; background: @TRACK@; border-radius: 4px; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { background: @ACCENT@; border-radius: 4px; }

/* ---------- Barras de rolagem ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @THUMB@; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @FAINT@; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @THUMB@; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: @FAINT@; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; background: none; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QScrollArea { border: none; background: transparent; }

/* ---------- Seleção ---------- */
QCheckBox { spacing: 8px; }
QCheckBox::indicator, QCheckBox::indicator:unchecked {
  width: 17px; height: 17px; border-radius: 5px;
  border: 1px solid @THUMB@; background: @FIELD@; }
QCheckBox::indicator:hover { border-radius: 5px; border: 1px solid @ACCENT@; }
QCheckBox::indicator:checked {
  border-radius: 5px; border: 1px solid @ACCENT@; background: @ACCENT@;
  image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png); }
QCheckBox::indicator:disabled { border-radius: 5px; background: @RAISED@; border: 1px solid @BORDER@; }
QRadioButton { spacing: 8px; }
QRadioButton::indicator, QRadioButton::indicator:unchecked {
  width: 17px; height: 17px; border-radius: 9px;
  border: 1px solid @THUMB@; background: @FIELD@; }
QRadioButton::indicator:hover { border-radius: 9px; border: 1px solid @ACCENT@; }
QRadioButton::indicator:checked {
  border-radius: 9px; border: 5px solid @ACCENT@; background: @FIELD@; }
QRadioButton::indicator:disabled { border-radius: 9px; background: @RAISED@; border: 1px solid @BORDER@; }

/* ---------- Calendário ---------- */
QCalendarWidget { background: @SURFACE@; color: @TEXT@; }
QCalendarWidget QWidget { alternate-background-color: @SURFACE@; color: @TEXT@; }
QCalendarWidget QAbstractItemView { background: @SURFACE@;
  selection-background-color: @ACCENT@; selection-color: #FFFFFF;
  color: @TEXT@; outline: 0; border: 1px solid @BORDER@; border-radius: 8px; padding: 4px; }
QCalendarWidget QAbstractItemView:disabled { color: @FAINT@; }
QCalendarWidget QToolButton { background: @RAISED@; color: @TEXT@;
  icon-size: 32px, 32px; border-radius: 6px; padding: 4px; }
QCalendarWidget QToolButton:hover { background: @ACCENT_SOFT@; }
QCalendarWidget QToolButton::menu-indicator { image: none; }
QCalendarWidget QSpinBox { background: @FIELD@; color: @TEXT@;
  border: 1px solid @BORDER2@; border-radius: 6px; }
QCalendarWidget QSpinBox::up-button, QCalendarWidget QSpinBox::down-button
  { background: transparent; border: none; }
QCalendarWidget QWidget#qt_calendar_navigationbar
  { background: @RAISED@; border-bottom: 1px solid @BORDER@; }

/* ---------- Divisores ---------- */
QSplitter::handle { background: @BORDER@; }
QSplitter::handle:hover { background: @ACCENT@; }
"""


def _render(tokens: dict) -> str:
    """Substitui @TOKENS@ do template pelos valores do dicionário."""
    return re.sub(r"@(\w+)@", lambda m: tokens[m.group(1)], _TEMPLATE)


def _light_css() -> str:
    return _render(LIGHT)


def _dark_css() -> str:
    return _render(DARK)


def build_stylesheet(dark: bool = False) -> str:
    if not dark:
        return _light_css()
    return _dark_css()