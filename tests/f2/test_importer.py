"""Tests for book import functionality (F2 - Hito2)."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from teaching.core.book_importer import (
    BookImportError,
    DuplicateBookError,
    FileNotFoundError,
    UnsupportedFormatError,
    import_book,
    _detect_format,
    _generate_book_id,
    _calculate_sha256,
)
from teaching.db.database import init_db, get_db
from teaching.db.books_repository import get_book_by_id, get_book_by_sha256


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_pdf(temp_dir):
    """Create a minimal test PDF file."""
    import fitz

    pdf_path = temp_dir / "test_book.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test PDF content for Teaching System")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def data_dir(temp_dir):
    """Create data directory structure."""
    data = temp_dir / "data"
    data.mkdir()
    return data


@pytest.fixture
def init_test_db(temp_dir):
    """Initialize test database."""
    db_path = temp_dir / "db" / "teaching.db"
    init_db(db_path)
    return db_path


class TestDetectFormat:
    """Tests for format detection."""

    def test_detect_pdf(self, test_pdf):
        """Detects PDF format correctly."""
        assert _detect_format(test_pdf) == "pdf"

    def test_reject_unsupported_extension(self, temp_dir):
        """Rejects unsupported file extensions."""
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("not a book")

        with pytest.raises(UnsupportedFormatError):
            _detect_format(txt_file)

    def test_reject_invalid_pdf_magic(self, temp_dir):
        """Rejects files with wrong magic bytes."""
        fake_pdf = temp_dir / "fake.pdf"
        fake_pdf.write_bytes(b"NOT A PDF FILE")

        with pytest.raises(UnsupportedFormatError) as exc:
            _detect_format(fake_pdf)
        assert "not a valid PDF" in str(exc.value)


class TestGenerateBookId:
    """Tests for book_id slug generation."""

    def test_basic_slug(self):
        """Generates basic slug from author and title."""
        book_id = _generate_book_id("Robert Martin", 2008, "Clean Code")
        assert book_id == "robert-2008-clean-code"

    def test_slug_without_year(self):
        """Generates slug without year if not provided."""
        book_id = _generate_book_id("Martin Fowler", None, "Refactoring")
        assert book_id == "martin-refactoring"

    def test_slug_removes_accents(self):
        """Removes accents from slug."""
        book_id = _generate_book_id("José García", 2020, "Programación")
        assert book_id == "jose-2020-programacion"

    def test_slug_normalizes_special_chars(self):
        """Normalizes special characters to hyphens."""
        book_id = _generate_book_id("Author", 2020, "Title: A Book (2nd Ed.)")
        assert book_id == "author-2020-title-a-book-2nd-ed"

    def test_slug_truncates_long_titles(self):
        """Truncates very long titles."""
        long_title = "A" * 100
        book_id = _generate_book_id("Author", 2020, long_title)
        # Title part should be max ~50 chars
        assert len(book_id) <= 70


class TestCalculateSha256:
    """Tests for SHA256 calculation."""

    def test_calculates_hash(self, test_pdf):
        """Calculates SHA256 hash of file."""
        sha = _calculate_sha256(test_pdf)
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)

    def test_same_content_same_hash(self, temp_dir):
        """Same content produces same hash."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        content = b"identical content"
        file1.write_bytes(content)
        file2.write_bytes(content)

        assert _calculate_sha256(file1) == _calculate_sha256(file2)


class TestImportBook:
    """Tests for full import flow."""

    def test_import_creates_structure(self, test_pdf, data_dir, init_test_db):
        """Import creates correct folder structure."""
        result = import_book(
            file_path=test_pdf,
            title="Clean Code",
            author="Robert Martin",
            data_dir=data_dir,
        )

        assert result.success
        assert result.book_id == "robert-clean-code"

        book_path = result.book_path
        assert book_path.exists()
        assert (book_path / "source").is_dir()
        assert (book_path / "raw" / "pages").is_dir()
        assert (book_path / "normalized").is_dir()
        assert (book_path / "outline").is_dir()
        assert (book_path / "artifacts" / "notes").is_dir()

    def test_import_copies_source(self, test_pdf, data_dir, init_test_db):
        """Import copies source file."""
        result = import_book(
            file_path=test_pdf,
            title="Test Book",
            author="Test Author",
            data_dir=data_dir,
        )

        source_copy = result.book_path / "source" / test_pdf.name
        assert source_copy.exists()
        assert source_copy.stat().st_size == test_pdf.stat().st_size

    def test_import_creates_book_json(self, test_pdf, data_dir, init_test_db):
        """Import creates valid book.json."""
        result = import_book(
            file_path=test_pdf,
            title="Clean Code",
            author="Robert Martin",
            language="en",
            data_dir=data_dir,
        )

        book_json_path = result.book_path / "book.json"
        assert book_json_path.exists()

        with open(book_json_path) as f:
            book_data = json.load(f)

        assert book_data["$schema"] == "book_v1"
        assert book_data["book_id"] == "robert-clean-code"
        assert book_data["book_uuid"]  # Should have a UUID
        assert book_data["title"] == "Clean Code"
        assert book_data["authors"] == ["Robert Martin"]
        assert book_data["language"] == "en"
        assert book_data["source_format"] == "pdf"
        assert book_data["sha256"]

    def test_import_registers_in_db(self, test_pdf, data_dir, init_test_db):
        """Import creates database record."""
        result = import_book(
            file_path=test_pdf,
            title="Clean Code",
            author="Robert Martin",
            data_dir=data_dir,
        )

        db_record = get_book_by_id(result.book_id)
        assert db_record is not None
        assert db_record.title == "Clean Code"
        assert db_record.authors == ["Robert Martin"]
        assert db_record.source_format == "pdf"
        assert db_record.status == "imported"
        assert db_record.sha256

    def test_duplicate_detection(self, test_pdf, data_dir, init_test_db):
        """Detects duplicate imports by SHA256."""
        # First import
        import_book(
            file_path=test_pdf,
            title="Clean Code",
            author="Robert Martin",
            data_dir=data_dir,
        )

        # Second import should fail
        with pytest.raises(DuplicateBookError) as exc:
            import_book(
                file_path=test_pdf,
                title="Different Title",
                author="Different Author",
                data_dir=data_dir,
            )

        assert exc.value.existing_book_id == "robert-clean-code"

    def test_force_reimport_same_book_id(self, test_pdf, data_dir, init_test_db):
        """Force flag allows reimport of same book_id."""
        # First import
        result1 = import_book(
            file_path=test_pdf,
            title="Clean Code",
            author="Robert Martin",
            data_dir=data_dir,
        )
        original_uuid = result1.book_uuid

        # Force reimport same file (same sha256 → same book_id)
        result2 = import_book(
            file_path=test_pdf,
            title="Clean Code Updated",
            author="Robert Martin",
            data_dir=data_dir,
            force=True,
        )

        assert result2.success
        # Should keep same book_id (overwrite)
        assert result2.book_id == result1.book_id
        # But new UUID
        assert result2.book_uuid != original_uuid

        # Check DB was updated
        db_record = get_book_by_id(result2.book_id)
        assert db_record.title == "Clean Code Updated"

    def test_force_uses_existing_book_id_for_same_sha256(
        self, test_pdf, data_dir, init_test_db
    ):
        """Force uses existing book_id when SHA256 matches (ignores new metadata for ID)."""
        # First import
        result1 = import_book(
            file_path=test_pdf,
            title="Clean Code",
            author="Robert Martin",
            data_dir=data_dir,
        )

        # Reimport with different metadata - should use existing book_id
        result2 = import_book(
            file_path=test_pdf,
            title="Different Title",
            author="Different Author",  # Would generate different book_id if new
            data_dir=data_dir,
            force=True,
        )

        # Should reuse existing book_id (not generate new one)
        assert result2.book_id == result1.book_id
        # But metadata should be updated
        db_record = get_book_by_id(result2.book_id)
        assert db_record.title == "Different Title"

    def test_file_not_found(self, data_dir, init_test_db):
        """Raises error for non-existent file."""
        with pytest.raises(FileNotFoundError):
            import_book(
                file_path=Path("/nonexistent/file.pdf"),
                data_dir=data_dir,
            )

    def test_auto_title_from_filename(self, test_pdf, data_dir, init_test_db):
        """Uses filename as title if not provided."""
        result = import_book(
            file_path=test_pdf,
            author="Author",
            data_dir=data_dir,
        )

        assert result.metadata.title == "test_book"
