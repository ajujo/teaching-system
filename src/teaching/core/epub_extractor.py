"""EPUB text extraction module.

Responsibilities (F2 - Hito3):
- Extract text from EPUB preserving structure
- Map EPUB chapters to separate files
- Extract OPF metadata (title, author, etc.)
- Clean HTML to plain text
- Extract TOC (table of contents) if present
- Update book.json with extraction metadata

Dependencies:
- ebooklib
- beautifulsoup4
- lxml
- langdetect
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ebooklib import epub
from langdetect import detect, DetectorFactory

import structlog

# Suppress XML parser warning for EPUB content
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Make langdetect deterministic
DetectorFactory.seed = 0

logger = structlog.get_logger(__name__)


@dataclass
class ExtractionMetrics:
    """Metrics from EPUB extraction."""

    total_chapters: int
    chapters_with_text: int
    empty_chapters_count: int
    total_chars: int
    avg_chars_per_chapter: float
    detected_language: str | None = None


@dataclass
class TocEntry:
    """Table of contents entry."""

    title: str
    href: str
    level: int = 0


@dataclass
class ExtractionResult:
    """Result of EPUB extraction."""

    success: bool
    metrics: ExtractionMetrics
    message: str
    epub_metadata: dict = field(default_factory=dict)
    toc: list[TocEntry] = field(default_factory=list)


class EpubExtractionError(Exception):
    """Base exception for EPUB extraction errors."""

    pass


class InvalidEpubError(EpubExtractionError):
    """Raised when EPUB file is invalid or corrupted."""

    def __init__(self, file_path: Path, detail: str = ""):
        self.file_path = file_path
        msg = f"EPUB inválido o corrupto: {file_path.name}"
        if detail:
            msg += f" ({detail})"
        super().__init__(msg)


def extract_epub(book_id: str, data_dir: Path | None = None) -> ExtractionResult:
    """Extract text from EPUB and generate raw/chapters files.

    Args:
        book_id: Book identifier (slug)
        data_dir: Base data directory (defaults to 'data')

    Returns:
        ExtractionResult with metrics and status

    Raises:
        FileNotFoundError: If book directory or source EPUB doesn't exist
        InvalidEpubError: If EPUB is invalid or corrupted
    """
    base_dir = data_dir or Path("data")
    book_path = base_dir / "books" / book_id

    # Find source EPUB
    source_dir = book_path / "source"
    if not source_dir.exists():
        raise FileNotFoundError(f"Directorio source no encontrado: {source_dir}")

    epub_files = list(source_dir.glob("*.epub"))
    if not epub_files:
        raise FileNotFoundError(f"No se encontró EPUB en: {source_dir}")

    epub_path = epub_files[0]
    logger.info("epub_extractor.start", book_id=book_id, epub=epub_path.name)

    # Open EPUB
    try:
        book = epub.read_epub(str(epub_path))
    except Exception as e:
        raise InvalidEpubError(epub_path, str(e))

    # Extract metadata
    epub_metadata = _extract_epub_metadata(book)

    # Extract TOC
    toc = _extract_toc(book)

    # Create output directories
    raw_dir = book_path / "raw"
    chapters_dir = raw_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    # Get document items in reading order (spine)
    spine_items = _get_spine_items(book)

    # Extract text chapter by chapter
    all_text_parts = []
    chapters_with_text = 0
    empty_chapters = 0
    total_chars = 0

    for idx, item in enumerate(spine_items):
        chapter_text = _extract_item_text(item)
        char_count = len(chapter_text.strip())

        # Write chapter file (1-indexed)
        chapter_file = chapters_dir / f"{idx + 1:04d}.txt"
        chapter_file.write_text(chapter_text, encoding="utf-8")

        if char_count > 0:
            chapters_with_text += 1
            all_text_parts.append(chapter_text)
        else:
            empty_chapters += 1

        total_chars += char_count

    # Write full content
    full_content = "\n\n".join(all_text_parts)
    content_file = raw_dir / "content.txt"
    content_file.write_text(full_content, encoding="utf-8")

    # Write TOC if available
    if toc:
        toc_file = raw_dir / "toc.json"
        toc_data = [{"title": t.title, "href": t.href, "level": t.level} for t in toc]
        with open(toc_file, "w", encoding="utf-8") as f:
            json.dump(toc_data, f, indent=2, ensure_ascii=False)

    # Calculate metrics
    total_chapters = len(spine_items)
    avg_chars = total_chars / total_chapters if total_chapters > 0 else 0

    # Detect language from extracted text
    detected_lang = None
    if full_content.strip():
        detected_lang = _detect_language(full_content)

    metrics = ExtractionMetrics(
        total_chapters=total_chapters,
        chapters_with_text=chapters_with_text,
        empty_chapters_count=empty_chapters,
        total_chars=total_chars,
        avg_chars_per_chapter=avg_chars,
        detected_language=detected_lang,
    )

    logger.info(
        "epub_extractor.metrics",
        book_id=book_id,
        total_chapters=total_chapters,
        chapters_with_text=chapters_with_text,
        empty_chapters=empty_chapters,
        avg_chars_per_chapter=round(avg_chars, 1),
        detected_language=detected_lang,
        toc_entries=len(toc),
    )

    # Update book.json with extraction metadata
    _update_book_json(book_path, metrics, epub_metadata, toc)

    message = f"Extraídos {total_chapters} capítulos ({chapters_with_text} con texto)"
    if toc:
        message += f", TOC con {len(toc)} entradas"

    return ExtractionResult(
        success=True,
        metrics=metrics,
        message=message,
        epub_metadata=epub_metadata,
        toc=toc,
    )


def _get_spine_items(book: epub.EpubBook) -> list[epub.EpubItem]:
    """Get document items in reading order from spine.

    Args:
        book: EpubBook instance

    Returns:
        List of EpubItem in reading order
    """
    items = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        items.append(item)
    return items


def _extract_item_text(item: epub.EpubItem) -> str:
    """Extract clean text from an EPUB item (chapter).

    Args:
        item: EpubItem (HTML document)

    Returns:
        Clean text without HTML tags
    """
    content = item.get_content()
    return _html_to_text(content)


def _html_to_text(html_content: bytes | str) -> str:
    """Convert HTML to plain text.

    Args:
        html_content: HTML content as bytes or string

    Returns:
        Clean plain text
    """
    if isinstance(html_content, bytes):
        html_content = html_content.decode("utf-8", errors="ignore")

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html_content, "lxml")

    # Remove script and style elements
    for element in soup(["script", "style", "head", "meta", "link"]):
        element.decompose()

    # Get text with proper spacing
    text = soup.get_text(separator="\n")

    # Clean up whitespace
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


def _extract_toc(book: epub.EpubBook) -> list[TocEntry]:
    """Extract table of contents from EPUB.

    Args:
        book: EpubBook instance

    Returns:
        List of TocEntry with title, href, and level
    """
    toc_entries = []

    def process_toc_item(item, level=0):
        if isinstance(item, epub.Link):
            toc_entries.append(
                TocEntry(title=item.title or "", href=item.href or "", level=level)
            )
        elif isinstance(item, tuple):
            # Section with sub-items: (Section, [items])
            section, sub_items = item
            if hasattr(section, "title"):
                toc_entries.append(
                    TocEntry(
                        title=section.title or "",
                        href=getattr(section, "href", "") or "",
                        level=level,
                    )
                )
            for sub_item in sub_items:
                process_toc_item(sub_item, level + 1)

    toc = book.toc
    if toc:
        for item in toc:
            process_toc_item(item)

    return toc_entries


def _extract_epub_metadata(book: epub.EpubBook) -> dict:
    """Extract metadata from EPUB.

    Args:
        book: EpubBook instance

    Returns:
        Dictionary with available metadata
    """

    def get_metadata(namespace, name):
        items = book.get_metadata(namespace, name)
        if items:
            return items[0][0] if isinstance(items[0], tuple) else items[0]
        return None

    return {
        "title": get_metadata("DC", "title"),
        "creator": get_metadata("DC", "creator"),
        "language": get_metadata("DC", "language"),
        "publisher": get_metadata("DC", "publisher"),
        "date": get_metadata("DC", "date"),
        "identifier": get_metadata("DC", "identifier"),
        "description": get_metadata("DC", "description"),
        "subject": get_metadata("DC", "subject"),
    }


def _detect_language(text: str) -> str | None:
    """Detect language of text using langdetect.

    Args:
        text: Text to analyze

    Returns:
        ISO 639-1 language code or None if detection fails
    """
    try:
        # Use a sample of the text for detection
        sample = text[:10000] if len(text) > 10000 else text
        return detect(sample)
    except Exception as e:
        logger.debug("epub_extractor.language_detection_failed", error=str(e))
        return None


def _update_book_json(
    book_path: Path,
    metrics: ExtractionMetrics,
    epub_metadata: dict,
    toc: list[TocEntry],
) -> None:
    """Update book.json with extraction metadata.

    Args:
        book_path: Path to book directory
        metrics: Extraction metrics
        epub_metadata: EPUB embedded metadata
        toc: Table of contents
    """
    book_json_path = book_path / "book.json"

    if not book_json_path.exists():
        logger.warning("epub_extractor.book_json_missing", path=str(book_json_path))
        return

    with open(book_json_path, "r", encoding="utf-8") as f:
        book_data = json.load(f)

    # Update fields
    book_data["total_chapters"] = metrics.total_chapters
    book_data["extraction"] = {
        "chapters_with_text": metrics.chapters_with_text,
        "empty_chapters_count": metrics.empty_chapters_count,
        "total_chars": metrics.total_chars,
        "avg_chars_per_chapter": round(metrics.avg_chars_per_chapter, 1),
        "detected_language": metrics.detected_language,
        "toc_entries": len(toc),
    }

    # Add EPUB metadata if available
    if any(v for v in epub_metadata.values()):
        book_data["epub_metadata"] = {k: v for k, v in epub_metadata.items() if v}

    with open(book_json_path, "w", encoding="utf-8") as f:
        json.dump(book_data, f, indent=2, ensure_ascii=False)

    logger.debug("epub_extractor.book_json_updated", path=str(book_json_path))
