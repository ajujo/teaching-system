"""Repository functions for books table.

Provides CRUD operations for the books table.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import structlog

from teaching.db.database import get_db

logger = structlog.get_logger(__name__)


@dataclass
class BookRecord:
    """Book record from database."""

    book_id: str
    book_uuid: str | None
    title: str
    authors: list[str]
    language: str
    source_format: str
    source_file: str
    source_path: str
    sha256: str
    imported_at: str
    book_json_path: str
    status: str


def insert_book(
    book_id: str,
    book_uuid: str,
    title: str,
    authors: list[str],
    language: str,
    source_format: str,
    source_file: str,
    source_path: str,
    sha256: str,
    book_json_path: str,
    status: str = "imported",
) -> None:
    """Insert a new book record.

    Args:
        book_id: Book slug identifier
        book_uuid: UUID v4 for internal tracking
        title: Book title
        authors: List of author names
        language: ISO 639-1 language code
        source_format: 'pdf' or 'epub'
        source_file: Original filename
        source_path: Relative path to source file
        sha256: File hash
        book_json_path: Relative path to book.json
        status: Initial status (default: 'imported')

    Raises:
        sqlite3.IntegrityError: If book_id or sha256 already exists
    """
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO books (
                book_id, book_uuid, title, authors, language,
                source_format, source_file, source_path,
                sha256, book_json_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_id,
                book_uuid,
                title,
                json.dumps(authors),
                language,
                source_format,
                source_file,
                source_path,
                sha256,
                book_json_path,
                status,
            ),
        )

    logger.debug("books.inserted", book_id=book_id)


def get_book_by_id(book_id: str) -> BookRecord | None:
    """Get book by ID.

    Args:
        book_id: Book slug identifier

    Returns:
        BookRecord if found, None otherwise
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM books WHERE book_id = ?", (book_id,)
        ).fetchone()

    if row is None:
        return None

    return _row_to_record(row)


def get_book_by_sha256(sha256: str) -> BookRecord | None:
    """Get book by SHA256 hash.

    Args:
        sha256: File hash

    Returns:
        BookRecord if found, None otherwise
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM books WHERE sha256 = ?", (sha256,)
        ).fetchone()

    if row is None:
        return None

    return _row_to_record(row)


def get_all_books() -> list[BookRecord]:
    """Get all books.

    Returns:
        List of all BookRecord instances
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM books ORDER BY imported_at DESC"
        ).fetchall()

    return [_row_to_record(row) for row in rows]


def update_book_status(book_id: str, status: str) -> None:
    """Update book status.

    Args:
        book_id: Book slug identifier
        status: New status value
    """
    with get_db() as conn:
        conn.execute(
            "UPDATE books SET status = ? WHERE book_id = ?",
            (status, book_id),
        )

    logger.debug("books.status_updated", book_id=book_id, status=status)


def delete_book(book_id: str) -> bool:
    """Delete book by ID.

    Args:
        book_id: Book slug identifier

    Returns:
        True if deleted, False if not found
    """
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM books WHERE book_id = ?", (book_id,)
        )

    deleted = cursor.rowcount > 0
    if deleted:
        logger.debug("books.deleted", book_id=book_id)

    return deleted


def update_book(
    book_id: str,
    book_uuid: str,
    title: str,
    authors: list[str],
    language: str,
    source_format: str,
    source_file: str,
    source_path: str,
    sha256: str,
    book_json_path: str,
    status: str = "imported",
) -> None:
    """Update an existing book record (for --force reimport).

    Args:
        book_id: Book slug identifier (must exist)
        book_uuid: New UUID v4
        title: Book title
        authors: List of author names
        language: ISO 639-1 language code
        source_format: 'pdf' or 'epub'
        source_file: Original filename
        source_path: Relative path to source file
        sha256: File hash
        book_json_path: Relative path to book.json
        status: Status (default: 'imported')

    Raises:
        ValueError: If book_id doesn't exist
    """
    with get_db() as conn:
        cursor = conn.execute(
            """
            UPDATE books SET
                book_uuid = ?,
                title = ?,
                authors = ?,
                language = ?,
                source_format = ?,
                source_file = ?,
                source_path = ?,
                sha256 = ?,
                book_json_path = ?,
                status = ?,
                imported_at = datetime('now')
            WHERE book_id = ?
            """,
            (
                book_uuid,
                title,
                json.dumps(authors),
                language,
                source_format,
                source_file,
                source_path,
                sha256,
                book_json_path,
                status,
                book_id,
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError(f"Book not found: {book_id}")

    logger.debug("books.updated", book_id=book_id)


def _row_to_record(row) -> BookRecord:
    """Convert database row to BookRecord."""
    return BookRecord(
        book_id=row["book_id"],
        book_uuid=row["book_uuid"],
        title=row["title"],
        authors=json.loads(row["authors"]) if row["authors"] else [],
        language=row["language"],
        source_format=row["source_format"],
        source_file=row["source_file"],
        source_path=row["source_path"],
        sha256=row["sha256"],
        imported_at=row["imported_at"],
        book_json_path=row["book_json_path"],
        status=row["status"],
    )
