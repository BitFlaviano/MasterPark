"""Serviço de backup e restauração (SQLite online backup + retenção)."""
from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from app.core.audit import AuditService
from app.core.config import get_backup_dir, get_db_path
from app.repositories.operation import BackupRepo


class BackupError(Exception):
    pass


class BackupService:
    def __init__(self, db, audit: AuditService | None = None):
        self.db = db
        self.repo = BackupRepo(db)
        self.audit = audit or AuditService(db)
        self.backup_dir = get_backup_dir()

    def create(self, kind: str = "MANUAL", note: str = "") -> dict:
        """Cria backup usando o mecanismo de online backup do SQLite para
        garantir consistência mesmo durante operação. Nunca sobrescreve o
        último backup válido: todo backup gera arquivo novo."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self.backup_dir / f"masterpark_backup_{stamp}.db"
        n = 1
        while dest.exists():
            dest = self.backup_dir / f"masterpark_backup_{stamp}_{n}.db"
            n += 1
        src = self.db.db_file()
        integrity = self.db.integrity_check()
        if integrity != ["ok"]:
            raise BackupError("Banco de dados com inconsistência. Execute o verificador.")
        try:
            import sqlite3
            con = sqlite3.connect(str(dest))
            try:
                with con:
                    self.db._conn.backup(con)
            finally:
                con.close()
        except Exception as exc:
            raise BackupError(f"Falha ao gerar backup: {exc}") from exc

        size = dest.stat().st_size if dest.exists() else 0
        self.repo.record(str(dest), size, kind, "OK", note)
        self._apply_retention()
        return {"path": str(dest), "size": size, "created_at": stamp}

    def _apply_retention(self) -> None:
        try:
            days = int(self.db.scalar(
                "SELECT value FROM system_settings WHERE key='backup_retention_days'") or 30)
        except Exception:
            days = 30
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        for item in self.backup_dir.glob("masterpark_backup_*.db"):
            try:
                mtime = datetime.datetime.fromtimestamp(item.stat().st_mtime)
                if mtime < cutoff:
                    try:
                        item.unlink()
                    except PermissionError:
                        pass
            except Exception:
                pass

    def list(self, limit: int = 30) -> list[dict]:
        return self.repo.list(limit)

    def restore(self, backup_path: str, dry_run: bool = True) -> dict:
        """Restaura um backup (por padrão valida a integridade antes)."""
        path = Path(backup_path)
        if not path.exists():
            raise BackupError("Arquivo de backup não encontrado.")
        import sqlite3
        con = sqlite3.connect(str(path))
        try:
            rows = con.execute("PRAGMA integrity_check").fetchall()
            if rows != [("ok",)]:
                raise BackupError("Backup corrompido ou incompleto.")
        finally:
            con.close()
        if dry_run:
            return {"valid": True, "path": str(path), "size": path.stat().st_size}
        # restauração real: para a conexão aberta e copia o arquivo
        self.db.close()
        try:
            src = get_db_path()
            src.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                # preserva o banco atual como cópia de segurança antes de sobrescrever
                shutil.copy2(src, str(src) + ".pre_restore")
            shutil.copy2(str(path), str(src))
        finally:
            self.db.connect()
        integrity = self.db.integrity_check()
        if integrity != ["ok"]:
            raise BackupError("Banco restaurado com inconsistência.")
        return {"valid": True, "restored": True, "path": str(path)}

    def validate(self, backup_path: str) -> dict:
        return self.restore(backup_path, dry_run=True)