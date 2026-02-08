"""PDF text extraction module.

Responsibilities (F2 - Hito3):
- Extract text from PDFs with selectable text
- Extract by page for traceability
- Detect content language
- Extract PDF metadata (title, author)
- Handle protected or scanned PDFs (informative error)
- Update book.json with extraction metadata

Dependencies:
- pymupdf (fitz)
- langdetect
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import fitz
import structlog
from langdetect import detect, DetectorFactory

# Make langdetect deterministic
DetectorFactory.seed = 0

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Constants
MIN_CHARS_PER_PAGE = 100  # Below this, consider page as "empty" or scanned
SCANNED_PDF_THRESHOLD = 0.5  # If >50% pages are "empty", likely scanned


@dataclass
class ExtractionMetrics:
    """Metrics from PDF extraction."""

    total_pages: int
    pages_with_text: int
    empty_pages_count: int
    total_chars: int
    avg_chars_per_page: float
    detected_language: str | None = None
    is_likely_scanned: bool = False


@dataclass
class ExtractionResult:
    """Result of PDF extraction."""

    success: bool
    metrics: ExtractionMetrics
    message: str
    pdf_metadata: dict = field(default_factory=dict)


class PdfExtractionError(Exception):
    """Base exception for PDF extraction errors."""

    pass


class ProtectedPdfError(PdfExtractionError):
    """Raised when PDF is password-protected."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        super().__init__(f"PDF protegido con contraseña: {file_path.name}")


class ScannedPdfError(PdfExtractionError):
    """Raised when PDF appears to be scanned (no selectable text)."""

    def __init__(self, file_path: Path, empty_ratio: float):
        self.file_path = file_path
        self.empty_ratio = empty_ratio
        super().__init__(
            f"PDF parece escaneado ({empty_ratio:.0%} páginas sin texto): {file_path.name}. "
            f"Se requiere OCR para extraer texto."
        )


def extract_pdf(book_id: str, data_dir: Path | None = None) -> ExtractionResult:
    """Extract text from PDF and generate raw/pages files.

    Args:
        book_id: Book identifier (slug)
        data_dir: Base data directory (defaults to 'data')

    Returns:
        ExtractionResult with metrics and status

    Raises:
        FileNotFoundError: If book directory or source PDF doesn't exist
        ProtectedPdfError: If PDF is password-protected
        ScannedPdfError: If PDF appears to be scanned (no text)
    """
    base_dir = data_dir or Path("data")
    book_path = base_dir / "books" / book_id

    # Find source PDF
    source_dir = book_path / "source"
    if not source_dir.exists():
        raise FileNotFoundError(f"Directorio source no encontrado: {source_dir}")

    pdf_files = list(source_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No se encontró PDF en: {source_dir}")

    pdf_path = pdf_files[0]
    logger.info("pdf_extractor.start", book_id=book_id, pdf=pdf_path.name)

    # Open PDF
    doc = fitz.open(pdf_path)

    # Check if protected
    if doc.is_encrypted:
        doc.close()
        raise ProtectedPdfError(pdf_path)

    # Extract metadata
    pdf_metadata = _extract_pdf_metadata(doc)

    # Create output directories
    raw_dir = book_path / "raw"
    pages_dir = raw_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # Extract text page by page
    all_text_parts = []
    pages_with_text = 0
    empty_pages = 0
    total_chars = 0

    for page_num in range(len(doc)):
        page_text = _extract_page_text(doc, page_num)
        char_count = len(page_text.strip())

        # Write page file (0-indexed internally, 1-indexed for files)
        page_file = pages_dir / f"{page_num + 1:04d}.txt"
        page_file.write_text(page_text, encoding="utf-8")

        if char_count >= MIN_CHARS_PER_PAGE:
            pages_with_text += 1
            all_text_parts.append(page_text)
        else:
            empty_pages += 1
            if page_text.strip():  # Some text but very little
                all_text_parts.append(page_text)

        total_chars += char_count

    # Get total pages before closing
    total_pages = len(doc)
    doc.close()

    # Write full content
    full_content = "\n\n".join(all_text_parts)
    content_file = raw_dir / "content.txt"
    content_file.write_text(full_content, encoding="utf-8")
    avg_chars = total_chars / total_pages if total_pages > 0 else 0
    empty_ratio = empty_pages / total_pages if total_pages > 0 else 0
    is_scanned = empty_ratio > SCANNED_PDF_THRESHOLD

    # Detect language from extracted text
    detected_lang = None
    if full_content.strip():
        detected_lang = _detect_language(full_content)

    metrics = ExtractionMetrics(
        total_pages=total_pages,
        pages_with_text=pages_with_text,
        empty_pages_count=empty_pages,
        total_chars=total_chars,
        avg_chars_per_page=avg_chars,
        detected_language=detected_lang,
        is_likely_scanned=is_scanned,
    )

    logger.info(
        "pdf_extractor.metrics",
        book_id=book_id,
        total_pages=total_pages,
        pages_with_text=pages_with_text,
        empty_pages=empty_pages,
        avg_chars_per_page=round(avg_chars, 1),
        detected_language=detected_lang,
        is_scanned=is_scanned,
    )

    # Warn if likely scanned
    if is_scanned:
        logger.warning(
            "pdf_extractor.likely_scanned",
            book_id=book_id,
            empty_ratio=f"{empty_ratio:.0%}",
            hint="Consider OCR for better text extraction",
        )

    # Update book.json with extraction metadata
    _update_book_json(book_path, metrics, pdf_metadata)

    message = f"Extraídas {total_pages} páginas ({pages_with_text} con texto)"
    if is_scanned:
        message += " - AVISO: PDF parece escaneado, considere OCR"

    return ExtractionResult(
        success=True,
        metrics=metrics,
        message=message,
        pdf_metadata=pdf_metadata,
    )


def _extract_page_text(doc: fitz.Document, page_num: int) -> str:
    """Extract text from a specific page.

    Args:
        doc: PyMuPDF document
        page_num: Page number (0-indexed)

    Returns:
        Extracted text from the page
    """
    page = doc[page_num]
    return page.get_text()


def _detect_language(text: str) -> str | None:
    """Detect language of text using langdetect.

    Args:
        text: Text to analyze

    Returns:
        ISO 639-1 language code or None if detection fails
    """
    try:
        # Use a sample of the text for detection (faster and more reliable)
        sample = text[:10000] if len(text) > 10000 else text
        return detect(sample)
    except Exception as e:
        logger.debug("pdf_extractor.language_detection_failed", error=str(e))
        return None


def _extract_pdf_metadata(doc: fitz.Document) -> dict:
    """Extract embedded metadata from PDF.

    Args:
        doc: PyMuPDF document

    Returns:
        Dictionary with available metadata
    """
    metadata = doc.metadata or {}
    return {
        "title": metadata.get("title") or None,
        "author": metadata.get("author") or None,
        "subject": metadata.get("subject") or None,
        "keywords": metadata.get("keywords") or None,
        "creator": metadata.get("creator") or None,
        "producer": metadata.get("producer") or None,
        "creation_date": metadata.get("creationDate") or None,
        "mod_date": metadata.get("modDate") or None,
    }


def _update_book_json(
    book_path: Path, metrics: ExtractionMetrics, pdf_metadata: dict
) -> None:
    """Update book.json with extraction metadata.

    Args:
        book_path: Path to book directory
        metrics: Extraction metrics
        pdf_metadata: PDF embedded metadata
    """
    book_json_path = book_path / "book.json"

    if not book_json_path.exists():
        logger.warning("pdf_extractor.book_json_missing", path=str(book_json_path))
        return

    with open(book_json_path, "r", encoding="utf-8") as f:
        book_data = json.load(f)

    # Update fields
    book_data["total_pages"] = metrics.total_pages
    book_data["extraction"] = {
        "pages_with_text": metrics.pages_with_text,
        "empty_pages_count": metrics.empty_pages_count,
        "total_chars": metrics.total_chars,
        "avg_chars_per_page": round(metrics.avg_chars_per_page, 1),
        "detected_language": metrics.detected_language,
        "is_likely_scanned": metrics.is_likely_scanned,
    }

    # Add PDF metadata if available
    if any(v for v in pdf_metadata.values()):
        book_data["pdf_metadata"] = {k: v for k, v in pdf_metadata.items() if v}

    with open(book_json_path, "w", encoding="utf-8") as f:
        json.dump(book_data, f, indent=2, ensure_ascii=False)

    logger.debug("pdf_extractor.book_json_updated", path=str(book_json_path))
