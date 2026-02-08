"""Tests for PDF and EPUB extraction functionality (F2 - Hito3)."""

import json
import tempfile
from pathlib import Path

import pytest

from teaching.core.pdf_extractor import (
    extract_pdf,
    PdfExtractionError,
    ProtectedPdfError,
    _extract_pdf_metadata,
    _detect_language,
)
from teaching.core.epub_extractor import (
    extract_epub,
    EpubExtractionError,
    InvalidEpubError,
    _html_to_text,
)
from teaching.core.book_importer import import_book
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
def test_pdf_multipage(temp_dir):
    """Create a multi-page test PDF file."""
    import fitz

    pdf_path = temp_dir / "multipage_book.pdf"
    doc = fitz.open()

    # Create multiple pages with different content
    pages_content = [
        "Chapter 1: Introduction\n\nThis is the introduction to our test book.",
        "Chapter 2: Main Content\n\nThe main content discusses important topics.",
        "Chapter 3: Advanced Topics\n\nAdvanced concepts are explained here.",
        "Chapter 4: Conclusion\n\nWe conclude with a summary of key points.",
    ]

    for content in pages_content:
        page = doc.new_page()
        page.insert_text((72, 72), content)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def imported_pdf_book(test_pdf_multipage, data_dir, init_test_db):
    """Create an imported PDF book for extraction tests."""
    result = import_book(
        file_path=test_pdf_multipage,
        title="Test Book",
        author="Test Author",
        language="en",
        data_dir=data_dir,
    )
    return result.book_id, data_dir


class TestPdfExtractor:
    """Tests for PDF extraction."""

    def test_extract_creates_page_files(self, imported_pdf_book):
        """Extract creates individual page files."""
        book_id, data_dir = imported_pdf_book

        result = extract_pdf(book_id, data_dir)

        assert result.success
        pages_dir = data_dir / "books" / book_id / "raw" / "pages"
        assert pages_dir.exists()

        # Should have 4 pages
        page_files = sorted(pages_dir.glob("*.txt"))
        assert len(page_files) == 4
        assert page_files[0].name == "0001.txt"
        assert page_files[3].name == "0004.txt"

    def test_extract_creates_content_txt(self, imported_pdf_book):
        """Extract creates consolidated content.txt."""
        book_id, data_dir = imported_pdf_book

        result = extract_pdf(book_id, data_dir)

        content_file = data_dir / "books" / book_id / "raw" / "content.txt"
        assert content_file.exists()

        content = content_file.read_text()
        assert "Chapter 1" in content
        assert "Chapter 4" in content

    def test_extract_returns_metrics(self, imported_pdf_book):
        """Extract returns correct metrics."""
        book_id, data_dir = imported_pdf_book

        result = extract_pdf(book_id, data_dir)

        assert result.metrics.total_pages == 4
        # Note: test PDFs have little text, so pages_with_text may be 0
        # but total_chars should be positive
        assert result.metrics.total_chars > 0
        assert result.metrics.avg_chars_per_page > 0

    def test_extract_updates_book_json(self, imported_pdf_book):
        """Extract updates book.json with metrics."""
        book_id, data_dir = imported_pdf_book

        extract_pdf(book_id, data_dir)

        book_json_path = data_dir / "books" / book_id / "book.json"
        with open(book_json_path) as f:
            book_data = json.load(f)

        assert book_data["total_pages"] == 4
        assert "extraction" in book_data
        assert "pages_with_text" in book_data["extraction"]
        assert "total_chars" in book_data["extraction"]

    def test_extract_nonexistent_book(self, data_dir, init_test_db):
        """Extract raises error for non-existent book."""
        with pytest.raises(FileNotFoundError):
            extract_pdf("nonexistent-book", data_dir)


class TestPdfLanguageDetection:
    """Tests for language detection in PDFs."""

    def test_detect_english(self):
        """Detects English text."""
        text = "This is a sample English text for testing language detection."
        lang = _detect_language(text)
        assert lang == "en"

    def test_detect_spanish(self):
        """Detects Spanish text."""
        text = "Este es un texto de ejemplo en español para probar la detección de idioma."
        lang = _detect_language(text)
        assert lang == "es"


class TestHtmlToText:
    """Tests for HTML to text conversion."""

    def test_removes_html_tags(self):
        """Removes HTML tags correctly."""
        html = "<p>Hello <strong>world</strong>!</p>"
        text = _html_to_text(html)
        assert "Hello" in text
        assert "world" in text
        assert "<" not in text

    def test_removes_script_tags(self):
        """Removes script and style tags."""
        html = "<p>Content</p><script>alert('hi');</script><style>.cls{}</style>"
        text = _html_to_text(html)
        assert "Content" in text
        assert "alert" not in text
        assert ".cls" not in text

    def test_preserves_text_structure(self):
        """Preserves paragraph structure."""
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        text = _html_to_text(html)
        assert "First paragraph" in text
        assert "Second paragraph" in text


class TestEpubExtractor:
    """Tests for EPUB extraction."""

    @pytest.fixture
    def test_epub(self, temp_dir):
        """Create a minimal test EPUB file."""
        from ebooklib import epub

        book = epub.EpubBook()
        book.set_identifier("test-book-123")
        book.set_title("Test EPUB Book")
        book.set_language("en")
        book.add_author("Test Author")

        # Create chapters
        c1 = epub.EpubHtml(title="Introduction", file_name="intro.xhtml", lang="en")
        c1.content = "<html><body><h1>Introduction</h1><p>This is the introduction.</p></body></html>"

        c2 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
        c2.content = "<html><body><h1>Chapter 1</h1><p>Chapter one content here.</p></body></html>"

        c3 = epub.EpubHtml(title="Conclusion", file_name="conclusion.xhtml", lang="en")
        c3.content = "<html><body><h1>Conclusion</h1><p>Final thoughts and summary.</p></body></html>"

        book.add_item(c1)
        book.add_item(c2)
        book.add_item(c3)

        # Add navigation
        book.toc = [
            epub.Link("intro.xhtml", "Introduction", "intro"),
            epub.Link("ch1.xhtml", "Chapter 1", "ch1"),
            epub.Link("conclusion.xhtml", "Conclusion", "conclusion"),
        ]

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", c1, c2, c3]

        epub_path = temp_dir / "test_book.epub"
        epub.write_epub(str(epub_path), book)
        return epub_path

    @pytest.fixture
    def imported_epub_book(self, test_epub, data_dir, init_test_db):
        """Create an imported EPUB book for extraction tests."""
        result = import_book(
            file_path=test_epub,
            title="Test EPUB",
            author="Test Author",
            language="en",
            data_dir=data_dir,
        )
        return result.book_id, data_dir

    def test_extract_creates_chapter_files(self, imported_epub_book):
        """Extract creates individual chapter files."""
        book_id, data_dir = imported_epub_book

        result = extract_epub(book_id, data_dir)

        assert result.success
        chapters_dir = data_dir / "books" / book_id / "raw" / "chapters"
        assert chapters_dir.exists()

        chapter_files = sorted(chapters_dir.glob("*.txt"))
        assert len(chapter_files) > 0

    def test_extract_creates_content_txt(self, imported_epub_book):
        """Extract creates consolidated content.txt."""
        book_id, data_dir = imported_epub_book

        result = extract_epub(book_id, data_dir)

        content_file = data_dir / "books" / book_id / "raw" / "content.txt"
        assert content_file.exists()

        content = content_file.read_text()
        assert len(content) > 0

    def test_extract_returns_metrics(self, imported_epub_book):
        """Extract returns correct metrics."""
        book_id, data_dir = imported_epub_book

        result = extract_epub(book_id, data_dir)

        assert result.metrics.total_chapters > 0
        assert result.metrics.total_chars > 0

    def test_extract_updates_book_json(self, imported_epub_book):
        """Extract updates book.json with metrics."""
        book_id, data_dir = imported_epub_book

        extract_epub(book_id, data_dir)

        book_json_path = data_dir / "books" / book_id / "book.json"
        with open(book_json_path) as f:
            book_data = json.load(f)

        assert "total_chapters" in book_data
        assert "extraction" in book_data

    def test_extract_creates_toc_json(self, imported_epub_book):
        """Extract creates toc.json when TOC is present."""
        book_id, data_dir = imported_epub_book

        result = extract_epub(book_id, data_dir)

        # TOC should be extracted
        if result.toc:
            toc_file = data_dir / "books" / book_id / "raw" / "toc.json"
            assert toc_file.exists()

    def test_extract_nonexistent_book(self, data_dir, init_test_db):
        """Extract raises error for non-existent book."""
        with pytest.raises(FileNotFoundError):
            extract_epub("nonexistent-book", data_dir)
