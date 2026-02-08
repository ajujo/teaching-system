"""Book import orchestrator.

Responsibilities (F2 - Hito2):
- Detect file format (PDF/EPUB)
- Calculate SHA256 for deduplication
- Generate book.json with metadata
- Copy source file to data/books/{book_id}/source/
- Create folder structure in data/books/{book_id}/
- Register book in SQLite
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import structlog

from teaching.db.database import init_db
from teaching.db.books_repository import (
    get_book_by_id,
    get_book_by_sha256,
    insert_book,
    update_book,
)

logger = structlog.get_logger(__name__)

# Constants
DATA_DIR = Path("data")
BOOKS_DIR = DATA_DIR / "books"
SUPPORTED_FORMATS = ("pdf", "epub")


@dataclass
class BookMetadata:
    """Extracted or provided book metadata."""

    title: str
    authors: list[str]
    language: str
    year: int | None = None
    publisher: str | None = None
    isbn: str | None = None
    edition: str | None = None


@dataclass
class ImportResult:
    """Result of book import operation."""

    success: bool
    book_id: str | None
    book_uuid: str | None
    book_path: Path | None
    message: str
    metadata: BookMetadata | None = None


class BookImportError(Exception):
    """Base exception for book import errors."""

    pass


class DuplicateBookError(BookImportError):
    """Raised when trying to import a book that already exists."""

    def __init__(self, sha256: str, existing_book_id: str):
        self.sha256 = sha256
        self.existing_book_id = existing_book_id
        super().__init__(
            f"Libro ya importado con ID '{existing_book_id}'. "
            f"Usa --force para reimportar."
        )


class Sha256ConflictError(BookImportError):
    """Raised when SHA256 exists with a different book_id (cannot be forced)."""

    def __init__(self, sha256: str, existing_book_id: str, requested_book_id: str):
        self.sha256 = sha256
        self.existing_book_id = existing_book_id
        self.requested_book_id = requested_book_id
        super().__init__(
            f"El archivo ya existe como '{existing_book_id}'. "
            f"No se puede importar como '{requested_book_id}' "
            f"(un archivo solo puede tener un book_id)."
        )


class UnsupportedFormatError(BookImportError):
    """Raised when file format is not supported."""

    def __init__(self, file_path: Path, detected: str | None = None):
        self.file_path = file_path
        self.detected = detected
        msg = f"Formato no soportado: {file_path.suffix}"
        if detected:
            msg += f" (detectado: {detected})"
        super().__init__(msg)


class FileNotFoundError(BookImportError):
    """Raised when source file doesn't exist."""

    pass


def import_book(
    file_path: Path,
    title: str | None = None,
    author: str | None = None,
    language: str = "auto",
    force: bool = False,
    data_dir: Path | None = None,
) -> ImportResult:
    """Import a book and return result with book_id.

    Args:
        file_path: Path to PDF or EPUB file
        title: Book title (extracted from file if not provided)
        author: Author(s), comma-separated (extracted if not provided)
        language: Language code (en, es) or "auto" for detection
        force: If True, reimport even if book exists
        data_dir: Override default data directory

    Returns:
        ImportResult with success status, book_id, and metadata

    Raises:
        FileNotFoundError: If source file doesn't exist
        UnsupportedFormatError: If file format is not PDF or EPUB
        DuplicateBookError: If book already exists and force=False
    """
    base_dir = data_dir or DATA_DIR
    books_dir = base_dir / "books"

    # Initialize database
    init_db(base_dir.parent / "db" / "teaching.db")

    # Validate file exists
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    logger.info("import_book.start", file=str(file_path), force=force)

    # Detect format
    fmt = _detect_format(file_path)
    logger.debug("import_book.format_detected", format=fmt)

    # Calculate SHA256
    sha256 = _calculate_sha256(file_path)
    logger.debug("import_book.sha256", sha256=sha256[:16] + "...")

    # Build metadata (for now, use provided values or placeholders)
    # TODO: Extract from PDF/EPUB in Hito3
    metadata = _build_metadata(
        file_path=file_path,
        title=title,
        author=author,
        language=language,
        fmt=fmt,
    )

    # Generate book_id from metadata
    book_id = _generate_book_id(
        author=metadata.authors[0] if metadata.authors else "unknown",
        year=metadata.year,
        title=metadata.title,
    )

    # Check for existing book by SHA256
    existing_by_sha = get_book_by_sha256(sha256)

    # Determine if this is a reimport scenario
    is_reimport = False

    if existing_by_sha:
        # File already imported - check force flag
        if force:
            # Force reimport: use the EXISTING book_id (overwrite)
            is_reimport = True
            book_id = existing_by_sha.book_id
            logger.info("import_book.reimport", book_id=book_id)
        else:
            # No force: error - file already exists
            raise DuplicateBookError(sha256, existing_by_sha.book_id)
    else:
        # New file (SHA256 not in DB)
        existing_by_id = get_book_by_id(book_id)
        if existing_by_id:
            # book_id collision with different content
            if force:
                # Force with different content: overwrite the book
                is_reimport = True
                logger.info("import_book.reimport_new_content", book_id=book_id)
            else:
                # Collision: append suffix for new book_id
                book_id = _ensure_unique_book_id(book_id, books_dir)
        # else: new book, no collision

    # Generate UUID for internal tracking
    book_uuid = str(uuid.uuid4())

    # Create folder structure
    book_path = _create_book_structure(book_id, books_dir)

    # Copy source file
    source_dir = book_path / "source"
    source_dest = source_dir / file_path.name
    shutil.copy2(file_path, source_dest)
    logger.debug("import_book.source_copied", dest=str(source_dest))

    # Generate book.json
    book_json = _create_book_json(
        book_id=book_id,
        book_uuid=book_uuid,
        metadata=metadata,
        file_path=file_path,
        fmt=fmt,
        sha256=sha256,
    )

    # Write book.json
    book_json_path = book_path / "book.json"
    with open(book_json_path, "w", encoding="utf-8") as f:
        json.dump(book_json, f, indent=2, ensure_ascii=False)

    # Register in database (insert or update)
    if is_reimport:
        update_book(
            book_id=book_id,
            book_uuid=book_uuid,
            title=metadata.title,
            authors=metadata.authors,
            language=metadata.language,
            source_format=fmt,
            source_file=file_path.name,
            source_path=f"source/{file_path.name}",
            sha256=sha256,
            book_json_path="book.json",
            status="imported",
        )
    else:
        insert_book(
            book_id=book_id,
            book_uuid=book_uuid,
            title=metadata.title,
            authors=metadata.authors,
            language=metadata.language,
            source_format=fmt,
            source_file=file_path.name,
            source_path=f"source/{file_path.name}",
            sha256=sha256,
            book_json_path="book.json",
            status="imported",
        )

    logger.info(
        "import_book.success",
        book_id=book_id,
        book_path=str(book_path),
    )

    return ImportResult(
        success=True,
        book_id=book_id,
        book_uuid=book_uuid,
        book_path=book_path,
        message=f"Libro importado: {book_id}",
        metadata=metadata,
    )


def _detect_format(file_path: Path) -> Literal["pdf", "epub"]:
    """Detect format by extension and magic bytes.

    Args:
        file_path: Path to the file

    Returns:
        Format string: "pdf" or "epub"

    Raises:
        UnsupportedFormatError: If format is not supported
    """
    # Check extension first
    ext = file_path.suffix.lower().lstrip(".")

    if ext not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(file_path)

    # Verify with magic bytes
    with open(file_path, "rb") as f:
        header = f.read(8)

    if ext == "pdf":
        if not header.startswith(b"%PDF"):
            raise UnsupportedFormatError(file_path, "not a valid PDF")
    elif ext == "epub":
        # EPUB is a ZIP file starting with PK
        if not header.startswith(b"PK"):
            raise UnsupportedFormatError(file_path, "not a valid EPUB/ZIP")

    return ext  # type: ignore


def _calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of file.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal SHA256 hash string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def _build_metadata(
    file_path: Path,
    title: str | None,
    author: str | None,
    language: str,
    fmt: str,
) -> BookMetadata:
    """Build metadata from provided values or extract from filename.

    Args:
        file_path: Path to source file
        title: Provided title or None
        author: Provided author(s) or None
        language: Language code or "auto"
        fmt: File format

    Returns:
        BookMetadata instance
    """
    # Use filename as fallback title
    if not title:
        title = file_path.stem

    # Parse authors
    authors = []
    if author:
        authors = [a.strip() for a in author.split(",")]

    # Language detection placeholder
    # TODO: Implement actual detection in Hito3
    if language == "auto":
        language = "en"  # Default fallback

    return BookMetadata(
        title=title,
        authors=authors,
        language=language,
    )


def _generate_book_id(author: str, year: int | None, title: str) -> str:
    """Generate slug: author-year-title.

    Normalized: lowercase, no accents, only alphanumeric and hyphens.

    Args:
        author: Author name (uses last name / first word)
        year: Publication year or None
        title: Book title

    Returns:
        Normalized slug like "martin-2008-clean-code"
    """

    def normalize(text: str) -> str:
        """Normalize text to slug-friendly format."""
        # Remove accents
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        # Lowercase
        text = text.lower()
        # Replace spaces and special chars with hyphens
        text = re.sub(r"[^a-z0-9]+", "-", text)
        # Remove leading/trailing hyphens
        text = text.strip("-")
        # Collapse multiple hyphens
        text = re.sub(r"-+", "-", text)
        return text

    # Extract author last name (first word)
    author_slug = normalize(author.split()[0]) if author else "unknown"

    # Normalize title (limit to ~50 chars for readability)
    title_slug = normalize(title)[:50].rstrip("-")

    # Build slug
    if year:
        return f"{author_slug}-{year}-{title_slug}"
    else:
        return f"{author_slug}-{title_slug}"


def _ensure_unique_book_id(book_id: str, books_dir: Path) -> str:
    """Ensure book_id is unique, appending suffix if needed.

    Args:
        book_id: Proposed book_id
        books_dir: Directory containing book folders

    Returns:
        Unique book_id (original or with -2, -3, etc. suffix)
    """
    if not books_dir.exists():
        return book_id

    if not (books_dir / book_id).exists():
        return book_id

    # Find unique suffix
    counter = 2
    while (books_dir / f"{book_id}-{counter}").exists():
        counter += 1

    return f"{book_id}-{counter}"


def _create_book_structure(book_id: str, books_dir: Path) -> Path:
    """Create folder structure for a book.

    Creates:
        data/books/{book_id}/
        data/books/{book_id}/source/
        data/books/{book_id}/raw/pages/
        data/books/{book_id}/normalized/
        data/books/{book_id}/outline/
        data/books/{book_id}/artifacts/notes/
        data/books/{book_id}/artifacts/exercises/
        data/books/{book_id}/artifacts/exams/

    Args:
        book_id: Book identifier (slug)
        books_dir: Base directory for books

    Returns:
        Path to the created book directory
    """
    book_path = books_dir / book_id

    # Create directory structure per f2_spec.md
    (book_path / "source").mkdir(parents=True, exist_ok=True)
    (book_path / "raw" / "pages").mkdir(parents=True, exist_ok=True)
    (book_path / "normalized").mkdir(parents=True, exist_ok=True)
    (book_path / "outline").mkdir(parents=True, exist_ok=True)
    (book_path / "artifacts" / "notes").mkdir(parents=True, exist_ok=True)
    (book_path / "artifacts" / "exercises").mkdir(parents=True, exist_ok=True)
    (book_path / "artifacts" / "exams").mkdir(parents=True, exist_ok=True)

    logger.debug("import_book.structure_created", book_path=str(book_path))

    return book_path


def _create_book_json(
    book_id: str,
    book_uuid: str,
    metadata: BookMetadata,
    file_path: Path,
    fmt: str,
    sha256: str,
) -> dict:
    """Create book.json content according to contracts_v1.md schema.

    Args:
        book_id: Book identifier (slug)
        book_uuid: UUID v4 for internal tracking
        metadata: Book metadata
        file_path: Path to source file
        fmt: File format (pdf/epub)
        sha256: File hash

    Returns:
        Dictionary ready to be serialized as JSON
    """
    return {
        "$schema": "book_v1",
        "book_id": book_id,
        "book_uuid": book_uuid,
        "title": metadata.title,
        "authors": metadata.authors,
        "language": metadata.language,
        "source_file": file_path.name,
        "source_format": fmt,
        "import_date": datetime.now(timezone.utc).isoformat(),
        "total_pages": None,  # TODO: Fill in Hito3 after extraction
        "total_chapters": None,  # TODO: Fill after outline extraction
        "sha256": sha256,
        "metadata": {
            "publisher": metadata.publisher,
            "year": metadata.year,
            "isbn": metadata.isbn,
            "edition": metadata.edition,
        },
    }
