"""Saúde do sistema: banco, backup, dispositivos e integridade."""
from __future__ import annotations

from PySide6.QtWidgets import (QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from app.core.config import get_db_path
from app.services.backup import BackupError
from app.ui.widgets import Card, info, make_label, page_header, primary_button


class HealthScreen(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Saúde do Sistema",
                                  "Diagnóstico de banco, backup e hardware"))

        self.db_card = Card("Banco de Dados")
        lay.addWidget(self.db_card)
        self.bk_card = Card("Backups")
        lay.addWidget(self.bk_card)
        self.hw_card = Card("Dispositivos / Hardware")
        lay.addWidget(self.hw_card)
        self.diag_card = Card("Diagnóstico")
        lay.addWidget(self.diag_card)

        row = QHBoxLayout()
        self.btn_backup = primary_button("Fazer backup agora", "primary")
        self.btn_backup.clicked.connect(self.do_backup)
        self.btn_restore = primary_button("Restaurar (validar)", "")
        self.btn_restore.clicked.connect(self.validate_backup)
        self.btn_integrity = primary_button("Verificar integridade", "")
        self.btn_integrity.clicked.connect(self.integrity)
        for b in (self.btn_backup, self.btn_restore, self.btn_integrity):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)

    def on_show(self):
        self._render()

    def _render(self):
        db = self.ctx.db
        for name, body in ((self.db_card, []), (self.bk_card, []), (self.hw_card, []),
                           (self.diag_card, [])):
            self._reset(name)
        # banco
        path = get_db_path()
        size = path.stat().st_size if path.exists() else 0
        self._add(self.db_card, f"Arquivo: {path}")
        self._add(self.db_card, f"Tamanho: {size / 1024:.0f} KB")
        self._add(self.db_card, f"Integridade: {self.ctx.db.integrity_check()}")
        # backups
        backups = self.ctx.backup.list()
        if backups:
            b = backups[0]
            self._add(self.bk_card, f"Último backup: {b['created_at']} ({b['size']} bytes)")
            self._add(self.bk_card, f"Total registrado: {len(backups)}")
        else:
            self._add(self.bk_card, "Nenhum backup registrado ainda.")
        # hardware
        for dev in self.ctx.devices.all():
            h = dev.health()
            tag = " (DEMO)" if h.get("simulated") else ""
            self._add(self.hw_card, f"{h['name']} {tag} — {h['status']}")
        # diagnóstico
        self._add(self.diag_card, f"Usuários: {len(self.ctx.users.list())}")
        if self.ctx.lot:
            self._add(self.diag_card, f"Vagas: {self.ctx.spaces.total(self.ctx.lot['id'])}")
        cur = self.ctx.license.current()
        if cur:
            self._add(self.diag_card, f"Licença: {self.ctx.license.describe(cur)}")

    @staticmethod
    def _reset(card):
        for i in reversed(range(card.body.count())):
            item = card.body.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

    @staticmethod
    def _add(card, text):
        card.body.addWidget(QLabel(text))

    def do_backup(self):
        self.ctx.auth.require_permission("BACKUP_MANAGE")
        try:
            result = self.ctx.backup.create(kind="MANUAL", note="backup manual")
            info(self, "OK", f"Backup criado: {result['path']}")
            self._render()
        except BackupError as exc:
            info(self, "Backup", f"Falha: {exc}")

    def validate_backup(self):
        backups = self.ctx.backup.list()
        if not backups:
            info(self, "Backup", "Nenhum backup para validar.")
            return
        from app.core.config import get_backup_dir
        path = backups[0]["path"]
        try:
            result = self.ctx.backup.validate(path)
            info(self, "Backup", f"Válido: {result['path']}")
        except BackupError as exc:
            info(self, "Backup", f"Inválido: {exc}")

    def integrity(self):
        rows = self.ctx.db.integrity_check()
        info(self, "Integridade", "Banco íntegro." if rows == ["ok"] else str(rows))