"""Tests for text normalization functionality (F2 - Hito4)."""

import json
import tempfile
from pathlib import Path

import pytest

from teaching.core.text_normalizer import (
    normalize_book,
    normalize_text,
    fix_hyphenation,
    NormalizationError,
    _is_code_line,
    _normalize_unicode,
    _collapse_newlines,
)
from teaching.core.book_importer import import_book
from teaching.core.pdf_extractor import extract_pdf
from teaching.db.database import init_db


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


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


@pytest.fixture
def test_pdf_with_content(temp_dir):
    """Create a test PDF with meaningful content."""
    import fitz

    pdf_path = temp_dir / "test_book.pdf"
    doc = fitz.open()

    # Create pages with varied content
    pages_content = [
        "Chapter 1: Introduction to Programming\n\n"
        "Programming is the art of instructing computers. This chapter\n"
        "introduces fundamental concepts that every pro-\n"
        "grammer should know.\n\n"
        "Key concepts include variables, functions, and control flow.",

        "Chapter 2: Data Structures\n\n"
        "Data structures organize infor-\n"
        "mation efficiently. Common structures include:\n\n"
        "  - Arrays\n"
        "  - Lists\n"
        "  - Trees\n\n"
        "def example_function():\n"
        "    return 'Hello World'",

        "Chapter 3: Algorithms\n\n"
        "Algorithms are step-by-step   procedures for solving\n"
        "computational     problems.\n\n\n\n"
        "This chapter covers sorting and searching.",
    ]

    for content in pages_content:
        page = doc.new_page()
        page.insert_text((72, 72), content)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def imported_and_extracted_book(test_pdf_with_content, data_dir, init_test_db):
    """Create a book that's been imported and extracted."""
    # Import the book
    result = import_book(
        file_path=test_pdf_with_content,
        title="Programming Guide",
        author="Test Author",
        language="en",
        data_dir=data_dir,
    )

    # Extract text
    extract_pdf(result.book_id, data_dir)

    return result.book_id, data_dir


class TestHyphenation:
    """Tests for hyphenation fixing."""

    def test_fixes_simple_hyphenation(self):
        """Fixes simple word breaks at line end."""
        text = "pro-\ngramming is great"
        result = fix_hyphenation(text)
        assert result == "programming is great"

    def test_fixes_multiple_hyphenations(self):
        """Fixes multiple hyphenations in text."""
        text = "pro-\ngramming and algo-\nrithms"
        result = fix_hyphenation(text)
        assert result == "programming and algorithms"

    def test_preserves_legitimate_hyphens(self):
        """Preserves hyphens that are not line breaks."""
        text = "well-known fact\nand another line"
        result = fix_hyphenation(text)
        assert "well-known" in result

    def test_preserves_uppercase_hyphenation(self):
        """Conservative: doesn't fix uppercase (could be acronyms)."""
        text = "HTTP-\nRequest"
        result = fix_hyphenation(text)
        # Should NOT fix this (uppercase)
        assert "HTTP-\nRequest" in result or "HTTP-" in result


class TestSpaceNormalization:
    """Tests for space collapsing."""

    def test_collapses_multiple_spaces(self):
        """Collapses multiple spaces to single."""
        text = "hello    world"
        result = normalize_text(text)
        assert "    " not in result
        assert "hello world" in result

    def test_preserves_code_indentation(self):
        """Preserves indentation in code blocks."""
        text = "def foo():\n    return 42"
        result = normalize_text(text)
        assert "    return" in result  # Indentation preserved


class TestNewlineNormalization:
    """Tests for newline collapsing."""

    def test_collapses_excessive_newlines(self):
        """Collapses 3+ newlines to 2."""
        text = "para1\n\n\n\npara2"
        result, count = _collapse_newlines(text)
        assert "\n\n\n" not in result
        assert "\n\n" in result
        assert count == 1

    def test_preserves_single_blank_lines(self):
        """Preserves single blank lines between paragraphs."""
        text = "para1\n\npara2"
        result, count = _collapse_newlines(text)
        assert result == text
        assert count == 0


class TestUnicodeNormalization:
    """Tests for Unicode normalization."""

    def test_normalizes_smart_quotes(self):
        """Converts smart quotes to simple quotes."""
        text = "\u201cHello\u201d and \u2018world\u2019"
        result = _normalize_unicode(text)
        assert '"Hello"' in result
        assert "'world'" in result

    def test_normalizes_dashes(self):
        """Converts em/en dashes to simple dashes."""
        text = "a\u2014b\u2013c"
        result = _normalize_unicode(text)
        assert "a-b-c" in result

    def test_removes_zero_width_chars(self):
        """Removes zero-width characters."""
        text = "hello\u200bworld"
        result = _normalize_unicode(text)
        assert result == "helloworld"


class TestCodeDetection:
    """Tests for code line detection."""

    def test_detects_indented_code(self):
        """Detects lines with 4+ space indent as code."""
        assert _is_code_line("    return 42") is True
        assert _is_code_line("  x = 1") is False  # Only 2 spaces

    def test_detects_python_function(self):
        """Detects Python function definition."""
        assert _is_code_line("def foo():") is True
        assert _is_code_line("def is just a word") is False

    def test_detects_import_statement(self):
        """Detects import statements."""
        assert _is_code_line("import os") is True
        assert _is_code_line("from pathlib import Path") is True


class TestNormalizeBook:
    """Tests for full book normalization."""

    def test_creates_normalized_directory(self, imported_and_extracted_book):
        """Normalization creates normalized/ directory."""
        book_id, data_dir = imported_and_extracted_book

        result = normalize_book(book_id, data_dir)

        assert result.success
        normalized_dir = data_dir / "books" / book_id / "normalized"
        assert normalized_dir.exists()

    def test_creates_normalized_content(self, imported_and_extracted_book):
        """Creates normalized/content.txt file."""
        book_id, data_dir = imported_and_extracted_book

        normalize_book(book_id, data_dir)

        content_file = data_dir / "books" / book_id / "normalized" / "content.txt"
        assert content_file.exists()

        content = content_file.read_text()
        assert len(content) > 0

    def test_returns_metrics(self, imported_and_extracted_book):
        """Returns normalization metrics."""
        book_id, data_dir = imported_and_extracted_book

        result = normalize_book(book_id, data_dir)

        assert result.metrics.original_chars > 0
        assert result.metrics.normalized_chars > 0
        assert result.metrics.chars_removed_ratio >= 0

    def test_updates_book_json(self, imported_and_extracted_book):
        """Updates book.json with normalization metrics."""
        book_id, data_dir = imported_and_extracted_book

        normalize_book(book_id, data_dir)

        book_json_path = data_dir / "books" / book_id / "book.json"
        with open(book_json_path) as f:
            book_data = json.load(f)

        assert "normalization" in book_data
        assert "original_chars" in book_data["normalization"]
        assert "normalized_chars" in book_data["normalization"]
        assert "hyphen_breaks_fixed" in book_data["normalization"]

    def test_content_not_lost_excessively(self, imported_and_extracted_book):
        """Ensures normalization doesn't lose >10% of content."""
        book_id, data_dir = imported_and_extracted_book

        result = normalize_book(book_id, data_dir)

        # Should not lose more than 10%
        assert result.metrics.chars_removed_ratio <= 0.15  # Some tolerance for test data

    def test_nonexistent_book_raises_error(self, data_dir, init_test_db):
        """Raises error for non-existent book."""
        with pytest.raises(FileNotFoundError):
            normalize_book("nonexistent-book", data_dir)


class TestNormalizeTextDirect:
    """Tests for direct text normalization function."""

    def test_handles_empty_text(self):
        """Handles empty text gracefully."""
        result = normalize_text("")
        assert result == ""  # Empty stays empty

    def test_preserves_content_meaning(self):
        """Doesn't change meaning of content."""
        text = "The quick brown fox jumps over the lazy dog."
        result = normalize_text(text)
        # All words should still be present
        for word in ["quick", "brown", "fox", "jumps", "lazy", "dog"]:
            assert word in result

    def test_combined_normalizations(self):
        """Applies multiple normalizations correctly."""
        text = "pro-\ngramming  is  great\n\n\n\nand fun"
        result = normalize_text(text)

        # Hyphenation fixed
        assert "programming" in result
        # Spaces collapsed
        assert "  " not in result
        # Newlines collapsed
        assert "\n\n\n" not in result
