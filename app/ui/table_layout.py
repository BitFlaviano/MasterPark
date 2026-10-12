"""Layout de colunas ajustável e persistente nas tabelas do sistema.

Enquanto o usuário não mexe nas colunas, elas continuam se ajustando ao
conteúdo (comportamento atual). Na primeira alteração manual — largura ou
posição — o auto-ajuste para e a escolha passa a valer, inclusive ao
reiniciar o programa. Botão direito no cabeçalho volta ao automático.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHeaderView, QMenu

from app.core.config import save_settings_file

MIN_WIDTH = 60
MAX_WIDTH = 520


class ColumnLayout:
    """Larguras e ordem das colunas ajustáveis pelo usuário e persistidas."""

    def __init__(self, ctx, table, key: str, min_width: int = MIN_WIDTH,
                 max_width: int = MAX_WIDTH):
        self.ctx = ctx
        self.table = table
        self.key = key
        self.min_width = min_width
        self.max_width = max_width
        self.custom = False
        self._loading = False

        self._timer = QTimer(table)
        self._timer.setSingleShot(True)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self.save)

        header = table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(min_width)
        header.setStretchLastSection(True)
        header.sectionResized.connect(self._on_changed)
        header.sectionMoved.connect(self._on_changed)

        self._menu = QMenu(table)
        self._menu.addAction("Restaurar layout das colunas").triggered.connect(self.reset)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_menu)

        self.restore()

    # ------------------------------------------------------------------
    def restore(self) -> None:
        saved = (getattr(self.ctx.settings, "table_columns", None) or {}).get(self.key)
        if not saved:
            self.auto()
            return
        self.custom = True
        self._apply(saved)

    def _apply(self, saved: dict) -> None:
        n = self.table.columnCount()
        widths = saved.get("widths") or []
        if len(widths) != n or not all(isinstance(w, int) and w > 0 for w in widths):
            self.auto()
            return
        self._loading = True
        try:
            header = self.table.horizontalHeader()
            header.setStretchLastSection(False)
            order = saved.get("order") or list(range(n))
            if len(order) == n:
                for target_visual, logical in enumerate(order):
                    current_visual = header.visualIndex(logical)
                    if 0 <= current_visual != target_visual:
                        header.moveSection(current_visual, target_visual)
            for c, w in enumerate(widths):
                self.table.setColumnWidth(c, max(self.min_width, min(int(w), self.max_width)))
        finally:
            self._loading = False
        self._fill_extra()

    def auto(self) -> None:
        self.custom = False
        self._loading = True
        try:
            header = self.table.horizontalHeader()
            n = self.table.columnCount()
            for target_visual in range(n):
                if header.visualIndex(target_visual) != target_visual:
                    header.moveSection(header.visualIndex(target_visual), target_visual)
            header.setStretchLastSection(True)
            self.table.resizeColumnsToContents()
            for c in range(n):
                w = self.table.columnWidth(c)
                self.table.setColumnWidth(c, max(self.min_width, min(w, self.max_width)))
        finally:
            self._loading = False
        self._forget()

    def reset(self) -> None:
        self.auto()

    # ------------------------------------------------------------------
    def _fill_extra(self) -> None:
        """Usa a largura restante na última coluna para não sobrar espaço vazio."""
        n = self.table.columnCount()
        if n < 2:
            return
        used = sum(self.table.columnWidth(c) for c in range(n))
        available = self.table.viewport().width()
        extra = available - used
        if extra > 0:
            last = n - 1
            self.table.setColumnWidth(
                last, min(self.table.columnWidth(last) + extra, self.max_width))

    def resize_event(self) -> None:
        if self.custom:
            self._fill_extra()

    def _on_changed(self, section: int = 0, old: int = 0, new: int = 0) -> None:
        if self._loading:
            return
        header = self.table.horizontalHeader()
        if header.minimumSectionSize() < self.min_width:
            header.setMinimumSectionSize(self.min_width)
        width = header.sectionSize(section)
        if width > self.max_width:
            self._loading = True
            try:
                header.resizeSection(section, self.max_width)
            finally:
                self._loading = False
        self.custom = True
        header.setStretchLastSection(False)
        self._timer.start()

    def _show_menu(self, pos) -> None:
        self._menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    # ------------------------------------------------------------------
    def save(self) -> None:
        self._timer.stop()
        n = self.table.columnCount()
        header = self.table.horizontalHeader()
        store = dict(getattr(self.ctx.settings, "table_columns", None) or {})
        store[self.key] = {
            "widths": [self.table.columnWidth(c) for c in range(n)],
            "order": [header.logicalIndex(v) for v in range(n)],
        }
        self.ctx.settings.table_columns = store
        save_settings_file(self.ctx.settings.as_dict())

    def _forget(self) -> None:
        store = dict(getattr(self.ctx.settings, "table_columns", None) or {})
        if store.pop(self.key, None) is not None:
            self.ctx.settings.table_columns = store
            save_settings_file(self.ctx.settings.as_dict())

    def flush(self) -> None:
        if self.custom:
            self.save()