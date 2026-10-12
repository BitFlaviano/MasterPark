"""Ícones de linha monocromáticos (estilo Feather) desenhados via SVG.

Uso:  button.setIcon(make_icon("log-in", "#FFFFFF"))

Se o módulo QtSvg não estiver disponível, retorna QIcon vazio (a interface
continua funcionando, só sem ícones).
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap

try:  # QtSvg faz parte do PySide6, mas é um módulo separado
    from PySide6.QtSvg import QSvgRenderer
except ImportError:  # pragma: no cover
    QSvgRenderer = None

_PATHS = {
    "log-in": '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>'
              '<polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/>',
    "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
               '<polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    "map": '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/>'
           '<line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>',
    "tag": '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>'
           '<line x1="7" y1="7" x2="7.01" y2="7"/>',
    "grid": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>'
            '<rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>'
                '<line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>'
                '<line x1="3" y1="10" x2="21" y2="10"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
             '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "dollar": '<line x1="12" y1="1" x2="12" y2="23"/>'
              '<path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "trending": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>'
                '<polyline points="17 6 23 6 23 12"/>',
    "sliders": '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>'
               '<line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>'
               '<line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>'
               '<line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>'
               '<line x1="17" y1="16" x2="23" y2="16"/>',
    "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "info": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/>'
            '<line x1="12" y1="8" x2="12.01" y2="8"/>',
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "moon": '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
    "sun": '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/>'
           '<line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>'
           '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/>'
           '<line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>'
           '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
}

_cache: dict[tuple, QIcon] = {}


def make_icon(name: str, color: str = "#475569", size: int = 18) -> QIcon:
    key = (name, color, size)
    if key in _cache:
        return _cache[key]
    icon = QIcon()
    body = _PATHS.get(name)
    if QSvgRenderer is not None and body:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
               f'stroke="{color}" stroke-width="2" stroke-linecap="round" '
               f'stroke-linejoin="round">{body}</svg>')
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        ratio = 2.0  # renderiza em 2x para ficar nítido em telas HiDPI
        pm = QPixmap(int(size * ratio), int(size * ratio))
        pm.fill(Qt.GlobalColor.transparent)
        pm.setDevicePixelRatio(ratio)
        painter = QPainter(pm)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        icon = QIcon(pm)
    _cache[key] = icon
    return icon
