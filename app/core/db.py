"""Camada de acesso ao banco de dados.

Abstrai o dialeto (hoje SQLite) e o ciclo de schema para que a troca para
PostgreSQL/SQL Server exija apenas nova implementação desta classe e das
migrações, sem tocar em regras de negócio (Services/Repositories usam SQL
parametrizado com marcadores `?`).
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def _find_schema_sql() -> Path:
    """Localiza schema.sql no código-fonte ou nas três disposições do PyInstaller.

    O PyInstaller coleta o .sql com datas/--add-data em destinos diferentes
    conforme o modo de build:
      onefile : sys._MEIPASS\app\core\schema.sql
      onedir  : _internal app core schema.sql (via __file__)
      fonte   : app core schema.sql
    """
    import sys as _sys
    meipass = getattr(_sys, "_MEIPASS", None)  # só existe em builds congelados

    candidates = []
    if meipass:
        candidates.append(Path(meipass) / "app" / "core" / "schema.sql")
    candidates.append(Path(__file__).resolve().parent / "schema.sql")
    candidates.append(Path(__file__).resolve().parent / ".." / ".." / ".."
                      / ".." / "app" / "core" / "schema.sql")
    for cand in candidates:
        if cand.is_file():
            return cand
    # último recurso: embedding direto de schema para não depender de arquivo
    return Path(__file__).resolve().parent / "schema.sql"


_SCHEMA = _find_schema_sql()


class DatabaseError(Exception):
    pass


class Database:
    def __init__(self, path: Path | str):
        self._path = str(path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Conexão
    # ------------------------------------------------------------------
    def connect(self) -> "Database":
        with self._lock:
            if self._conn is not None:
                return self
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            self._conn.execute("PRAGMA busy_timeout = 5000")
        return self

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        if self._conn is None:
            self.connect()
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        """Transação única: commit no final, rollback em erro."""
        if self._conn is None:
            self.connect()
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def execute(self, sql: str, params: tuple = ()) -> int:
        with self.transaction() as cur:
            cur.execute(sql, params)
            return cur.lastrowid or 0

    def execute_rowcount(self, sql: str, params: tuple = ()) -> int:
        """Executa UPDATE/DELETE e devolve quantas linhas foram afetadas.

        `execute()` devolve `lastrowid`, que em UPDATE/DELETE e o id obsoleto do
        ultimo INSERT: um UPDATE que nao casa nada devolveria 1. Use este metodo
        sempre que o retorno indicar sucesso/fracasso.
        """
        with self.transaction() as cur:
            cur.execute(sql, params)
            return cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0

    def execute_many(self, sql: str, seq: list[tuple]) -> None:
        with self.transaction() as cur:
            cur.executemany(sql, seq)

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def query_one(self, sql: str, params: tuple = ()) -> dict | None:
        with self.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def scalar(self, sql: str, params: tuple = ()) -> Any:
        with self.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row and len(row) else None

    # ------------------------------------------------------------------
    # Migração
    # ------------------------------------------------------------------
    def ensure_schema(self, version: int = 1) -> None:
        if self._conn is None:
            self.connect()
        with self._lock:
            try:
                self._conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
                self._conn.commit()
                self._conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, applied_at)"
                    " VALUES (?, datetime('now'))", (version,))
                self._conn.commit()
                self._migrate_columns()
            except Exception as exc:
                self._conn.rollback()
                raise DatabaseError(f"Falha ao aplicar schema: {exc}")

    def _migrate_columns(self) -> None:
        """Adiciona colunas novas em bancos já criados (migrações idempotentes)."""
        existing = {r["name"] for r in self.query("PRAGMA table_info(licenses)")}
        adds = [("lifetime", "INTEGER DEFAULT 0"),
                ("duracao", "TEXT DEFAULT ''")]
        for name, definition in adds:
            if name not in existing:
                self._conn.execute(
                    f"ALTER TABLE licenses ADD COLUMN {name} {definition}")
        # exclusao logica: a linha sai das telas mas permanece no banco para
        # tickets/reservas/pagamentos antigos continuarem apontando para o
        # registro certo (PRAGMA foreign_keys=ON impede apagar a referencia).
        for tabela, coluna in (("parking_spaces", "active"),
                               ("customers", "active"),
                               ("monthly_customers", "active")):
            atual = {r["name"] for r in
                     self.query(f"PRAGMA table_info({tabela})")}
            if coluna not in atual:
                self._conn.execute(
                    f"ALTER TABLE {tabela} ADD COLUMN {coluna}"
                    " INTEGER NOT NULL DEFAULT 1")
        self._conn.commit()

    def integrity_check(self) -> list[str]:
        rows = self.query("PRAGMA integrity_check")
        return [r["integrity_check"] for r in rows]

    def db_file(self) -> str:
        return self._path