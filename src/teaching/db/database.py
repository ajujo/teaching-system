"""SQLite database connection and schema management.

Provides connection management and schema initialization for the teaching system.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import structlog

logger = structlog.get_logger(__name__)

# Default database location
DEFAULT_DB_PATH = Path("db/teaching.db")

# Current connection (module-level for simplicity in CLI context)
_db_path: Path | None = None


def init_db(db_path: Path | None = None) -> None:
    """Initialize database with schema.

    Creates the database file and all required tables if they don't exist.

    Args:
        db_path: Path to database file. Defaults to db/teaching.db
    """
    global _db_path
    _db_path = db_path or DEFAULT_DB_PATH

    # Ensure directory exists
    _db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_db() as conn:
        _create_schema(conn)

    logger.info("database.initialized", path=str(_db_path))


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Get database connection as context manager.

    Yields:
        SQLite connection with row factory set to sqlite3.Row

    Example:
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM books")
            rows = cursor.fetchall()
    """
    db_path = _db_path or DEFAULT_DB_PATH

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create database schema.

    Creates all tables defined in contracts_v1.md.
    Uses IF NOT EXISTS for idempotency.
    """
    conn.executescript(
        """
        -- Tabla: books (registro local de libros importados)
        -- sha256 es UNIQUE: un archivo solo puede estar en un book_id
        CREATE TABLE IF NOT EXISTS books (
            book_id TEXT PRIMARY KEY,
            book_uuid TEXT UNIQUE,
            title TEXT NOT NULL,
            authors TEXT,
            language TEXT NOT NULL DEFAULT 'en',
            source_format TEXT NOT NULL CHECK(source_format IN ('pdf', 'epub')),
            source_file TEXT NOT NULL,
            source_path TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            imported_at TEXT NOT NULL DEFAULT (datetime('now')),
            book_json_path TEXT NOT NULL,
            status TEXT DEFAULT 'imported' CHECK(status IN ('imported', 'extracted', 'outlined', 'planned', 'active', 'completed'))
        );

        -- Tabla: student_profile (para fases futuras)
        CREATE TABLE IF NOT EXISTS student_profile (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            preferences TEXT DEFAULT '{}',
            notes TEXT
        );

        -- Índices
        CREATE INDEX IF NOT EXISTS idx_books_sha256 ON books(sha256);
        CREATE INDEX IF NOT EXISTS idx_books_status ON books(status);
        """
    )
