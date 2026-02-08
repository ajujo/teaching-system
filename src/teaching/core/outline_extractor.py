"""Book structure detection module.

Responsibilities (F2 - Hito5):
- Detect chapters and sections from book text
- Use multiple detection methods with confidence scoring
- Generate outline.json per contracts schema
- Support manual review via YAML export

Detection methods:
1. toc: Detect table of contents in text -> confidence: 0.8-0.95
2. headings: Pattern detection ("Chapter X", "1.", "1.1") -> confidence: 0.6-0.9
3. auto: Try toc -> headings, pick best by confidence
4. llm: Use LLM for structure identification (fallback) -> confidence: 0.5-0.8
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import structlog
import yaml

logger = structlog.get_logger(__name__)

# Detection method types
DetectionMethod = Literal["auto", "toc", "headings", "llm"]

# Confidence thresholds
MIN_CONFIDENCE_AUTO = 0.6  # Below this, suggest --review
MIN_CHAPTERS_EXPECTED = 2  # At least 2 chapters expected

# Heading patterns (ordered by specificity)
# STRICT: Only explicit "Chapter N" patterns create chapters
CHAPTER_PATTERNS = [
    # "Chapter 1: Title" or "Chapter 1. Title" or "capítulo 1. Título" - PRIMARY pattern
    # Note: Using (?i) for case-insensitive matching
    (r"(?i)^(?:Chapter|Capítulo)\s+(\d+)[:\.\s]+(.+)$", "chapter_word"),
    # "Part I: Title" or "Part 1: Title"
    (r"(?i)^(?:Part|Parte)\s+([IVXLC]+|\d+)[:\.\s]+(.+)$", "part_word"),
]

# These patterns are DEMOTED - they might match too aggressively
CHAPTER_PATTERNS_SECONDARY = [
    # "I. Title" (Roman numerals) - can be section in some books
    (r"^([IVXLC]+)\.\s+([A-Z][^.]{10,})$", "roman_dot"),
]

SECTION_PATTERNS = [
    # "1.1 Title" or "1.1. Title"
    (r"^(\d+\.\d+)\.?\s+(.+)$", "decimal"),
    # "Section 1.1: Title"
    (r"^(?:Section|SECTION|Sección)\s+(\d+\.\d+)[:\.\s]+(.+)$", "section_word"),
    # "1. Title" - demoted from chapter to section
    (r"^(\d+)\.\s+([A-Z][^.]+)$", "number_dot"),
]

SUBSECTION_PATTERNS = [
    # "1.1.1 Title"
    (r"^(\d+\.\d+\.\d+)\.?\s+(.+)$", "triple_decimal"),
]

# TOC detection patterns
TOC_MARKERS = [
    r"(?i)^(?:table\s+of\s+)?contents?\s*$",
    r"(?i)^índice\s*$",
    r"(?i)^contenido\s*$",
    r"(?i)^sumario\s*$",
]

# =============================================================================
# TOC FORMAT: Packt style - "Chapter N: Title ... page"
# =============================================================================
# Standard format with page on same line
CHAPTER_LINE_PATTERN_PACKT = re.compile(
    r"^(?:Chapter|CHAPTER|Capítulo|CAPÍTULO)\s+(\d+)[:\.\s]+(.+?)(?:\s+(\d+))?\s*$",
    re.IGNORECASE
)
# Packt format where title may end with control char, page on next line
CHAPTER_LINE_PATTERN_PACKT_MULTILINE = re.compile(
    r"^(?:Chapter|CHAPTER|Capítulo|CAPÍTULO)\s+(\d+)[:\.\s]+(.+?)\s*[\x00-\x1f]?\s*$",
    re.IGNORECASE
)

# =============================================================================
# TOC FORMAT: O'Reilly/Manning style - "N. Title ... page"
# =============================================================================
# Pattern: "1. Introduction to Agents. . . . . . . . 1"
CHAPTER_LINE_PATTERN_NUMERIC = re.compile(
    r"^(\d{1,2})\.\s+(.+?)\s*[\.·\s]{2,}\s*(\d+)\s*$"
)

# Pattern: "1. Introduction to Agents" (without page, but with number prefix)
CHAPTER_LINE_PATTERN_NUMERIC_NO_PAGE = re.compile(
    r"^(\d{1,2})\.\s+([A-Z].{5,})$"
)

# =============================================================================
# TOC FORMAT: O'Reilly Spanish - "capítulo N. Título" (lowercase)
# =============================================================================
# Pattern: "capítulo 1. Introducción a la creación de..."
CHAPTER_LINE_PATTERN_CAPITULO = re.compile(
    r"^capítulo\s+(\d+)\.\s+(.+)$",
    re.IGNORECASE
)

# =============================================================================
# TOC FORMAT: Cookbook style - chapter number alone on one line
# Format:
#   1
#   Imputing Missing Data
#   1
# =============================================================================
# Matches standalone chapter number at start of chapter entry
COOKBOOK_CHAPTER_NUMBER = re.compile(r"^(\d{1,2})$")

# =============================================================================
# TOC entry patterns - for sections and general entries
# =============================================================================
TOC_ENTRY_PATTERNS = [
    # "Title ........... 123" or "Title ... 123" (with leader dots)
    re.compile(r"^(.+?)\s*[\.·]{3,}\s*(\d+)\s*$"),
    # "Title   123" (spaces + page at end, min 2 spaces)
    re.compile(r"^([A-Z].+?)\s{2,}(\d+)\s*$"),
    # "Title 123" (single space + page at end, for O'Reilly sections)
    # Must start with capital letter and have at least 2 words
    re.compile(r"^([A-Z][a-z]+(?:\s+[A-Za-z]+)+)\s+(\d+)\s*$"),
]

# Pattern for frontmatter with roman numerals: "Preface ... xiii"
FRONTMATTER_PATTERN = re.compile(
    r"^(.+?)\s*[\.·\s]{2,}\s*([xivlc]+)\s*$",
    re.IGNORECASE
)

# Maximum chapters from headings method (guardrail)
MAX_CHAPTERS_HEADINGS = 50

# =============================================================================
# INDEX-ONLY DETECTION PATTERNS
# =============================================================================
# Alphabetical index patterns (A, B, C sections with subentries)
INDEX_ALPHABETICAL_PATTERN = re.compile(r"^[A-Z]\s*$")
INDEX_ENTRY_PATTERN = re.compile(r"^[a-z].+,\s*\d+", re.IGNORECASE)

# Index header patterns (to find index section in last pages)
INDEX_HEADER_PATTERNS = [
    re.compile(r"(?i)^índice\s*$"),
    re.compile(r"(?i)^index\s*$"),
]

# How many lines to search for index in the last part of the book
INDEX_SEARCH_LAST_LINES = 3000  # ~30-50 pages worth of lines

# =============================================================================
# TOC LOCATOR CONSTANTS
# =============================================================================
TOC_SEARCH_FIRST_LINES = 1500  # Check first N lines for TOC
TOC_SEARCH_LAST_LINES = 500    # Check last N lines for TOC (rare but possible)
TOC_MIN_CHAPTER_ENTRIES = 3    # Minimum chapters to consider valid TOC

# Leader dots pattern for TOC entries
LEADER_DOTS_PATTERN = re.compile(r"^(.+?)\s*[\.·]{3,}\s*(\d+|[xivlc]+)\s*$", re.IGNORECASE)

# Non-chapter entries that should be sections, not chapters
NON_CHAPTER_TITLES = {
    "summary", "references", "bibliography", "index", "glossary",
    "appendix", "acknowledgments", "about the author", "preface",
    "foreword", "introduction", "conclusion", "resumen", "referencias",
    "bibliografía", "índice", "glosario", "apéndice", "agradecimientos",
}


@dataclass
class Section:
    """A section within a chapter."""

    section_id: str
    number: str
    title: str
    start_page: int | None = None
    end_page: int | None = None
    subsections: list[dict] = field(default_factory=list)


@dataclass
class Chapter:
    """A chapter in the outline."""

    chapter_id: str
    number: int
    title: str
    start_page: int | None = None
    end_page: int | None = None
    sections: list[Section] = field(default_factory=list)


@dataclass
class Outline:
    """Complete book outline."""

    book_id: str
    chapters: list[Chapter]
    generated_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": "outline_v1",
            "book_id": self.book_id,
            "generated_date": self.generated_date,
            "chapters": [
                {
                    "chapter_id": ch.chapter_id,
                    "number": ch.number,
                    "title": ch.title,
                    "start_page": ch.start_page,
                    "end_page": ch.end_page,
                    "sections": [
                        {
                            "section_id": sec.section_id,
                            "number": sec.number,
                            "title": sec.title,
                            "start_page": sec.start_page,
                            "end_page": sec.end_page,
                            "subsections": sec.subsections,
                        }
                        for sec in ch.sections
                    ],
                }
                for ch in self.chapters
            ],
        }


@dataclass
class TocLocation:
    """Location information for detected TOC."""

    start_line: int
    end_line: int
    confidence_locator: float
    method: str  # "marker", "pattern", "heuristic"

    def to_dict(self) -> dict:
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "confidence_locator": round(self.confidence_locator, 2),
            "method": self.method,
        }


@dataclass
class OutlineReport:
    """Report with extraction metadata."""

    method_used: str
    confidence: float
    chapters_found: int
    sections_found: int
    warnings: list[str] = field(default_factory=list)
    method_scores: dict = field(default_factory=dict)
    # New fields for robustness
    index_only_detected: bool = False
    toc_location: TocLocation | None = None

    def to_dict(self) -> dict:
        result = {
            "method_used": self.method_used,
            "confidence": round(self.confidence, 2),
            "chapters_found": self.chapters_found,
            "sections_found": self.sections_found,
            "warnings": self.warnings,
            "method_scores": self.method_scores,
            "index_only_detected": self.index_only_detected,
        }
        if self.toc_location:
            result["toc_location"] = self.toc_location.to_dict()
        return result


@dataclass
class ExtractionResult:
    """Result of outline extraction."""

    success: bool
    outline: Outline | None
    report: OutlineReport
    message: str
    needs_review: bool = False


class OutlineExtractionError(Exception):
    """Base exception for outline extraction errors."""

    pass


def extract_outline(
    book_id: str,
    method: DetectionMethod = "auto",
    data_dir: Path | None = None,
) -> ExtractionResult:
    """Extract book structure and generate outline.json.

    Args:
        book_id: Book identifier (slug)
        method: Detection method (auto, toc, headings, llm)
        data_dir: Base data directory (defaults to 'data')

    Returns:
        ExtractionResult with outline and report

    Raises:
        FileNotFoundError: If book directory or content doesn't exist
        OutlineExtractionError: If extraction fails completely
    """
    base_dir = data_dir or Path("data")
    book_path = base_dir / "books" / book_id

    # Find content file (prefer normalized, fallback to raw)
    normalized_content = book_path / "normalized" / "content.txt"
    raw_content = book_path / "raw" / "content.txt"

    if normalized_content.exists():
        content_file = normalized_content
    elif raw_content.exists():
        content_file = raw_content
    else:
        raise FileNotFoundError(
            f"No se encontró content.txt en normalized/ ni raw/ para {book_id}"
        )

    logger.info(
        "outline_extractor.start",
        book_id=book_id,
        method=method,
        content_file=str(content_file),
    )

    # Read content
    content = content_file.read_text(encoding="utf-8")

    # Extract based on method
    if method == "auto":
        result = _extract_auto(book_id, content)
    elif method == "toc":
        result = _extract_from_toc(book_id, content)
    elif method == "headings":
        result = _extract_from_headings(book_id, content)
    elif method == "llm":
        result = _extract_with_llm(book_id, content)
    else:
        raise OutlineExtractionError(f"Método no soportado: {method}")

    if not result.success or result.outline is None:
        return result

    # Create outline directory
    outline_dir = book_path / "outline"
    outline_dir.mkdir(parents=True, exist_ok=True)

    # Write outline.json
    outline_json_path = outline_dir / "outline.json"
    with open(outline_json_path, "w", encoding="utf-8") as f:
        json.dump(result.outline.to_dict(), f, indent=2, ensure_ascii=False)

    # Write report
    report_path = outline_dir / "outline_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result.report.to_dict(), f, indent=2, ensure_ascii=False)

    # Update book.json
    _update_book_json(book_path, result)

    logger.info(
        "outline_extractor.success",
        book_id=book_id,
        method=result.report.method_used,
        chapters=result.report.chapters_found,
        confidence=result.report.confidence,
    )

    return result


def generate_review_yaml(book_id: str, data_dir: Path | None = None) -> Path:
    """Generate YAML file for manual review/editing.

    Args:
        book_id: Book identifier
        data_dir: Base data directory

    Returns:
        Path to generated YAML file
    """
    base_dir = data_dir or Path("data")
    book_path = base_dir / "books" / book_id
    outline_dir = book_path / "outline"

    outline_json_path = outline_dir / "outline.json"
    if not outline_json_path.exists():
        raise FileNotFoundError(f"outline.json no encontrado: {outline_json_path}")

    with open(outline_json_path, "r", encoding="utf-8") as f:
        outline_data = json.load(f)

    # Convert to YAML-friendly format
    yaml_path = outline_dir / "outline_draft.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("# Outline Draft - Edit and save\n")
        f.write("# Delete chapters/sections as needed\n")
        f.write("# Run 'teach outline <book_id> --validate' to apply changes\n\n")
        yaml.dump(outline_data, f, default_flow_style=False, allow_unicode=True)

    logger.info("outline_extractor.yaml_generated", path=str(yaml_path))
    return yaml_path


def validate_and_apply_yaml(book_id: str, data_dir: Path | None = None) -> ExtractionResult:
    """Validate edited YAML and convert back to outline.json.

    Args:
        book_id: Book identifier
        data_dir: Base data directory

    Returns:
        ExtractionResult with validated outline
    """
    base_dir = data_dir or Path("data")
    book_path = base_dir / "books" / book_id
    outline_dir = book_path / "outline"

    yaml_path = outline_dir / "outline_draft.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"outline_draft.yaml no encontrado: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        outline_data = yaml.safe_load(f)

    # Validate structure
    errors = _validate_outline_structure(outline_data, book_id)
    if errors:
        return ExtractionResult(
            success=False,
            outline=None,
            report=OutlineReport(
                method_used="manual",
                confidence=0.0,
                chapters_found=0,
                sections_found=0,
                warnings=errors,
            ),
            message=f"Errores de validación: {len(errors)}",
            needs_review=True,
        )

    # Convert to Outline object
    outline = _dict_to_outline(outline_data)

    # Write validated outline.json
    outline_json_path = outline_dir / "outline.json"
    with open(outline_json_path, "w", encoding="utf-8") as f:
        json.dump(outline.to_dict(), f, indent=2, ensure_ascii=False)

    chapters_count = len(outline.chapters)
    sections_count = sum(len(ch.sections) for ch in outline.chapters)

    report = OutlineReport(
        method_used="manual",
        confidence=1.0,  # Manual = trusted
        chapters_found=chapters_count,
        sections_found=sections_count,
    )

    # Update book.json
    result = ExtractionResult(
        success=True,
        outline=outline,
        report=report,
        message=f"Outline validado: {chapters_count} capítulos, {sections_count} secciones",
    )
    _update_book_json(book_path, result)

    return result


# =============================================================================
# Detection Methods
# =============================================================================


def _detect_index_only(lines: list[str], start: int, end: int) -> bool:
    """Detect if a block is an alphabetical index, not a TOC.

    Index-only blocks have:
    - Single letter headers (A, B, C...)
    - Entries with lowercase text + page numbers
    - No chapter/section structure
    """
    if end - start < 10:
        return False

    alpha_headers = 0
    index_entries = 0
    total_lines = 0

    for i in range(start, min(end, len(lines))):
        line = lines[i].strip()
        if not line:
            continue

        total_lines += 1

        # Check for alphabetical headers (A, B, C...)
        if INDEX_ALPHABETICAL_PATTERN.match(line):
            alpha_headers += 1
            continue

        # Check for index entries (lowercase text, page number)
        if INDEX_ENTRY_PATTERN.match(line):
            index_entries += 1

    if total_lines < 10:
        return False

    # Index if: many alpha headers AND entries have index pattern
    alpha_ratio = alpha_headers / total_lines if total_lines > 0 else 0
    entry_ratio = index_entries / total_lines if total_lines > 0 else 0

    # Consider index-only if we see alphabetical section structure
    return alpha_headers >= 5 and alpha_ratio > 0.02


def _detect_index_in_last_pages(lines: list[str]) -> bool:
    """Detect alphabetical index in the last pages of the book.

    For books without a traditional TOC (like Chip's AI Engineering),
    we check if the last 30-50 pages contain an alphabetical index.
    This helps explain why method=toc fails - the book has no TOC,
    only an index at the end.

    Returns True if an alphabetical index is found in the last pages.
    """
    if len(lines) < 100:
        return False

    # Search in the last N lines
    search_start = max(0, len(lines) - INDEX_SEARCH_LAST_LINES)

    # Look for "Index" or "Índice" header
    index_section_start = None
    for i in range(search_start, len(lines)):
        line = lines[i].strip()
        for pattern in INDEX_HEADER_PATTERNS:
            if pattern.match(line):
                index_section_start = i
                break
        if index_section_start:
            break

    if index_section_start is None:
        return False

    # Found an "Index" header, now check if it's an alphabetical index
    # Check the next ~500 lines for alphabetical structure
    check_end = min(index_section_start + 500, len(lines))
    return _detect_index_only(lines, index_section_start, check_end)


def _locate_toc(lines: list[str]) -> TocLocation | None:
    """Locate TOC section in the document.

    Searches in:
    1. First N lines (most common location)
    2. Last N lines (rare, but some books have TOC at end)

    Returns TocLocation with start/end lines and confidence.
    """
    # Search first part of document
    first_result = _search_toc_region(lines, 0, min(TOC_SEARCH_FIRST_LINES, len(lines)))
    if first_result and first_result.confidence_locator >= 0.7:
        return first_result

    # If not found with high confidence, check end of document
    if len(lines) > TOC_SEARCH_LAST_LINES:
        last_start = len(lines) - TOC_SEARCH_LAST_LINES
        last_result = _search_toc_region(lines, last_start, len(lines))
        if last_result:
            # Prefer first location if both found
            if first_result:
                if last_result.confidence_locator > first_result.confidence_locator:
                    return last_result
                return first_result
            return last_result

    return first_result


def _search_toc_region(lines: list[str], start: int, end: int) -> TocLocation | None:
    """Search for TOC within a region of lines."""
    best_location = None
    best_score = 0.0

    for i in range(start, end):
        line = lines[i].strip()

        # Method 1: Explicit marker
        if any(re.match(pattern, line) for pattern in TOC_MARKERS):
            # Found marker, estimate TOC extent
            toc_end = _estimate_toc_end(lines, i + 1)
            score = 0.9  # High confidence for explicit marker
            if toc_end - i > 20:  # Reasonable size
                score = 0.95
            if score > best_score:
                best_score = score
                best_location = TocLocation(
                    start_line=i + 1,
                    end_line=toc_end,
                    confidence_locator=score,
                    method="marker",
                )

        # Method 2: Pattern detection (leader dots with page numbers)
        elif LEADER_DOTS_PATTERN.match(line):
            # Check if we're in a TOC-like region
            toc_start, toc_end, score = _detect_toc_by_pattern(lines, i)
            if score > best_score and toc_end - toc_start >= 10:
                best_score = score
                best_location = TocLocation(
                    start_line=toc_start,
                    end_line=toc_end,
                    confidence_locator=score,
                    method="pattern",
                )

    return best_location


def _estimate_toc_end(lines: list[str], start: int) -> int:
    """Estimate where TOC ends based on content patterns."""
    consecutive_empty = 0
    last_content_line = start

    for i in range(start, min(start + 800, len(lines))):
        line = lines[i].strip()

        if not line:
            consecutive_empty += 1
            if consecutive_empty >= 4 and i - start > 20:
                break
            continue

        consecutive_empty = 0
        last_content_line = i

        # Stop at Index/Glossary markers (end of TOC)
        if re.match(r"^(Index|Glossary|Índice)\s*[\.·\s]*\d*\s*$", line, re.IGNORECASE):
            return i + 1

        # Stop if we see long paragraphs (actual content)
        if len(line) > 120 and "." not in line[-50:]:
            break

    return last_content_line + 1


def _detect_toc_by_pattern(lines: list[str], hint_line: int) -> tuple[int, int, float]:
    """Detect TOC boundaries by pattern matching (leader dots, chapter patterns)."""
    # Look backward for start
    start = hint_line
    for i in range(hint_line - 1, max(0, hint_line - 50), -1):
        line = lines[i].strip()
        if not line:
            continue
        if LEADER_DOTS_PATTERN.match(line) or re.match(r"^(Chapter|Capítulo)\s+\d+", line, re.IGNORECASE):
            start = i
        else:
            # If we hit non-TOC content, stop
            if len(line) > 100:
                break

    # Look forward for end
    end = _estimate_toc_end(lines, hint_line)

    # Calculate confidence based on TOC characteristics
    chapter_count = 0
    entry_count = 0
    for i in range(start, end):
        line = lines[i].strip()
        if re.match(r"^(Chapter|Capítulo)\s+\d+", line, re.IGNORECASE):
            chapter_count += 1
        if LEADER_DOTS_PATTERN.match(line):
            entry_count += 1

    # Score based on found patterns
    score = 0.5
    if chapter_count >= 3:
        score += 0.2
    if entry_count >= 10:
        score += 0.2
    if end - start >= 30:
        score += 0.1

    return start, end, min(score, 0.9)


def _extract_auto(book_id: str, content: str) -> ExtractionResult:
    """Auto-detect best method based on content analysis.

    Always tries both TOC and headings methods, reporting scores for each.
    Handles index-only detection to prefer headings when TOC is actually an index.
    """
    lines = content.split("\n")
    method_scores = {}
    warnings = []

    # First, locate potential TOC
    toc_location = _locate_toc(lines)

    # Check if "TOC" is actually an index-only block
    index_only = False
    if toc_location:
        index_only = _detect_index_only(
            lines, toc_location.start_line, toc_location.end_line
        )
        if index_only:
            warnings.append("Detectado índice alfabético en lugar de TOC")

    # Try TOC method (unless index-only)
    toc_result = None
    if not index_only:
        toc_result = _extract_from_toc(book_id, content, toc_location)
        if toc_result.success and toc_result.outline:
            method_scores["toc"] = toc_result.report.confidence
        else:
            method_scores["toc"] = 0.0
            # TOC failed - check if book has index-only in last pages
            # This explains WHY toc method doesn't work for books like Chip's
            if _detect_index_in_last_pages(lines):
                index_only = True
                warnings.append("index_only")
            else:
                warnings.append("toc_unusable")

    # Always try headings
    headings_result = _extract_from_headings(book_id, content)
    if headings_result.success and headings_result.outline:
        method_scores["headings"] = headings_result.report.confidence
    else:
        method_scores["headings"] = 0.0

    # Determine best method
    best_result = None
    best_method = None

    # If index-only, prefer headings
    if index_only and headings_result.success:
        best_result = headings_result
        best_method = "headings"
    elif toc_result and toc_result.success and toc_result.report.confidence >= 0.6:
        # Prefer TOC if confidence is good
        if not headings_result.success:
            best_result = toc_result
            best_method = "toc"
        elif toc_result.report.confidence >= headings_result.report.confidence:
            best_result = toc_result
            best_method = "toc"
        else:
            best_result = headings_result
            best_method = "headings"
    elif headings_result.success:
        best_result = headings_result
        best_method = "headings"
    elif toc_result and toc_result.success:
        best_result = toc_result
        best_method = "toc"

    if not best_result:
        # Nothing worked
        return ExtractionResult(
            success=False,
            outline=None,
            report=OutlineReport(
                method_used="auto",
                confidence=0.0,
                chapters_found=0,
                sections_found=0,
                warnings=warnings + ["No se detectó estructura. Use --method llm o --review"],
                method_scores=method_scores,
                index_only_detected=index_only,
                toc_location=toc_location,
            ),
            message="No se pudo detectar estructura automáticamente",
            needs_review=True,
        )

    # Update report with all method scores and metadata
    best_result.report.method_scores = method_scores
    best_result.report.method_used = f"auto:{best_method}"
    best_result.report.index_only_detected = index_only
    best_result.report.toc_location = toc_location
    best_result.report.warnings.extend(warnings)

    # Check if confidence is low
    if best_result.report.confidence < MIN_CONFIDENCE_AUTO:
        best_result.needs_review = True
        best_result.report.warnings.append(
            f"Confianza baja ({best_result.report.confidence:.0%}). Considere --review"
        )

    return best_result


def _extract_from_toc(
    book_id: str, content: str, toc_location: TocLocation | None = None
) -> ExtractionResult:
    """Extract outline from table of contents in text.

    Supports multiple TOC formats (by pattern, not editorial):
    - leaderdots: "Title .... 123" (leader dots with page number)
    - chapterline: "Chapter N: Title [page]" / "Capítulo N: Título"
    - numeric: "N. Title [page]" (numeric prefix)
    - multiline: chapter number, title, page on separate lines

    Args:
        book_id: Book identifier
        content: Full text content
        toc_location: Pre-computed TOC location (optional, for optimization)
    """
    lines = content.split("\n")

    # Use provided location or find TOC
    toc_start = None
    toc_end = None

    if toc_location:
        toc_start = toc_location.start_line
        toc_end = toc_location.end_line
    else:
        # Find TOC section - look for "Table of Contents" marker
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if any(re.match(pattern, line_stripped) for pattern in TOC_MARKERS):
                toc_start = i + 1
                break

        # Also try to find cookbook-style TOC without explicit marker
        cookbook_toc_start = _find_cookbook_toc_start(lines)

        # Use the earlier of the two start positions, preferring cookbook if found
        if cookbook_toc_start is not None:
            if toc_start is None or cookbook_toc_start < toc_start:
                toc_start = cookbook_toc_start

    if toc_start is None:
        return ExtractionResult(
            success=False,
            outline=None,
            report=OutlineReport(
                method_used="toc",
                confidence=0.0,
                chapters_found=0,
                sections_found=0,
                warnings=["No se encontró tabla de contenidos"],
            ),
            message="No se encontró TOC en el texto",
        )

    # Collect TOC lines - stop when we hit actual content
    # For cookbook format, we need to keep standalone numbers
    toc_lines = _collect_toc_lines(lines, toc_start, keep_numbers=True)

    if not toc_lines:
        return ExtractionResult(
            success=False,
            outline=None,
            report=OutlineReport(
                method_used="toc",
                confidence=0.0,
                chapters_found=0,
                sections_found=0,
                warnings=["TOC vacío o no parseable"],
            ),
            message="No se encontraron líneas de TOC",
        )

    # Try different TOC formats (by PATTERN, not editorial) and pick the best
    results = []

    # Pattern: "Chapter N: Title" / "Capítulo N: Título" (chapterline format)
    chapterline_result = _parse_toc_chapterline(book_id, toc_lines)
    if chapterline_result and chapterline_result[0]:
        results.append(("toc:chapterline", chapterline_result))

    # Pattern: "N. Title ... page" (numeric prefix with leader dots)
    numeric_result = _parse_toc_numeric(book_id, toc_lines)
    if numeric_result and numeric_result[0]:
        results.append(("toc:numeric", numeric_result))

    # Pattern: chapter number, title, page on separate lines (multiline format)
    multiline_result = _parse_toc_multiline(book_id, toc_lines)
    if multiline_result and multiline_result[0]:
        results.append(("toc:multiline", multiline_result))

    # Pattern: "Title .... page" (leaderdots format, generic)
    leaderdots_result = _parse_toc_leaderdots(book_id, toc_lines)
    if leaderdots_result and leaderdots_result[0]:
        results.append(("toc:leaderdots", leaderdots_result))

    if not results:
        return ExtractionResult(
            success=False,
            outline=None,
            report=OutlineReport(
                method_used="toc",
                confidence=0.0,
                chapters_found=0,
                sections_found=0,
                warnings=["TOC encontrado pero no se pudieron extraer capítulos"],
            ),
            message="No se pudieron extraer capítulos del TOC",
        )

    # Pick the best result by confidence
    best_format, (chapters, confidence, sections_count) = max(
        results, key=lambda x: x[1][1]
    )

    outline = Outline(book_id=book_id, chapters=chapters)

    return ExtractionResult(
        success=True,
        outline=outline,
        report=OutlineReport(
            method_used=best_format,
            confidence=confidence,
            chapters_found=len(chapters),
            sections_found=sections_count,
        ),
        message=f"TOC: {len(chapters)} capítulos, {sections_count} secciones",
    )


def _find_cookbook_toc_start(lines: list[str]) -> int | None:
    """Find start of cookbook-style TOC without explicit marker.

    Looks for pattern: "Preface" + roman numeral page, then "1" + title + page.
    Common in Packt Cookbook format from 2-column PDF extraction.
    """
    def clean(s: str) -> str:
        """Remove control characters and strip."""
        return re.sub(r"[\x00-\x1f\x7f]", "", s).strip()

    for i in range(min(300, len(lines))):  # Check first 300 lines
        line = clean(lines[i])

        # Look for "Preface" or "Foreword" alone on a line (case insensitive)
        if line.lower() in ("preface", "foreword"):
            # Check if next lines follow cookbook pattern
            # Preface, xv (roman page), 1 (chapter), Title, page
            if i + 5 >= len(lines):
                continue

            # Get next few non-empty lines
            next_lines = []
            for j in range(i + 1, min(i + 10, len(lines))):
                cleaned = clean(lines[j])
                if cleaned:
                    next_lines.append(cleaned)
                if len(next_lines) >= 5:
                    break

            if len(next_lines) < 4:
                continue

            # Pattern: roman_page, chapter_num, title, page
            # next_lines[0] should be roman numeral (page of Preface)
            if not re.match(r"^[xivlc]+$", next_lines[0].lower()):
                continue

            # next_lines[1] should be chapter number "1"
            if next_lines[1] != "1":
                continue

            # next_lines[2] should be a title (text, not just a number)
            if next_lines[2].isdigit():
                continue

            # next_lines[3] should be a page number (digit)
            if not next_lines[3].isdigit():
                continue

            # Found cookbook TOC start
            return i

    return None


def _collect_toc_lines(lines: list[str], toc_start: int, keep_numbers: bool = False) -> list[str]:
    """Collect TOC lines, stopping when we hit actual content.

    Args:
        lines: All lines from the content
        toc_start: Line number where TOC starts
        keep_numbers: If True, keep standalone numbers (needed for cookbook format)
    """
    toc_lines = []
    consecutive_empty = 0
    seen_chapter_numbers = set()
    passed_index_or_glossary = False  # Persistent flag once we pass Index

    for i in range(toc_start, min(toc_start + 800, len(lines))):
        line = lines[i].strip()

        # Track consecutive empty lines
        if not line:
            consecutive_empty += 1
            # End TOC after empty lines following Index/Glossary
            if consecutive_empty >= 2 and passed_index_or_glossary:
                break
            # End TOC after many empty lines (but only if we have content)
            if consecutive_empty >= 4 and len(toc_lines) > 15:
                break
            continue
        else:
            consecutive_empty = 0

        # Skip repeated TOC page headers (common in multi-page TOCs)
        if any(re.match(pattern, line) for pattern in TOC_MARKERS):
            continue

        # Skip roman numeral page numbers (like "xv", "viii")
        if re.match(r"^[xivlc]+$", line.lower()):
            if not keep_numbers:
                continue
            # For cookbook, keep roman numerals as they might be page numbers
            toc_lines.append(line)
            continue

        # Handle arabic page numbers
        if re.match(r"^\d{1,3}$", line):
            if keep_numbers:
                # For cookbook format, keep numbers as they're chapter nums or pages
                toc_lines.append(line)
            continue

        # Check for Index/Glossary which marks end of TOC
        if re.match(r"^(Index|Glossary|Índice|Other Books)\s*[\.·\s]*\d*\s*$", line, re.IGNORECASE):
            toc_lines.append(line)
            passed_index_or_glossary = True
            continue

        # After Index/Glossary, Chapter without page number = content (not TOC)
        if passed_index_or_glossary:
            if re.match(r"^Chapter\s+\d+", line, re.IGNORECASE):
                has_page = bool(re.search(r"\d+\s*$", line))
                if not has_page:
                    break

        # Detect if we've left the TOC and entered content
        if len(toc_lines) > 15:
            # Long paragraph without TOC markers = content
            if len(line) > 100 and not any(c in line for c in [".", "·"]):
                break

            # Check for chapter pattern
            chapter_match = re.match(
                r"^(?:Chapter\s+)?(\d+)[\.:]\s", line, re.IGNORECASE
            )
            if chapter_match:
                chapter_num = int(chapter_match.group(1))

                # If we've already seen this chapter number, we're in content
                if chapter_num in seen_chapter_numbers:
                    break

                seen_chapter_numbers.add(chapter_num)

        toc_lines.append(line)

    return toc_lines


def _parse_toc_chapterline(
    book_id: str, toc_lines: list[str]
) -> tuple[list[Chapter], float, int] | None:
    """Parse TOC with explicit chapter word: 'Chapter N: Title' / 'Capítulo N: Título'.

    Pattern: chapterline
    - Lines starting with "Chapter" or "Capítulo" followed by number
    - Title follows the number, optionally with page at end
    - Page may be on next line for some PDF extractions
    """
    chapters = []
    current_chapter = None
    pending_chapter_page = False  # Track if we need page from next line

    for i, line in enumerate(toc_lines):
        if not line:
            continue

        # Check if this is a page number for pending chapter
        if pending_chapter_page and current_chapter:
            page_match = re.match(r"^\s*(\d+)\s*$", line)
            if page_match:
                current_chapter.start_page = int(page_match.group(1))
                pending_chapter_page = False
                continue
            pending_chapter_page = False  # Not a page, move on

        # Skip standalone page numbers (not part of chapter)
        if re.match(r"^[xivlc]+$", line.lower()):
            continue

        # Skip frontmatter entries
        if _is_skip_entry(line):
            continue

        # Try "Chapter N: Title" pattern (with optional page on same line)
        match = CHAPTER_LINE_PATTERN_PACKT.match(line)
        if match:
            chapter_num = int(match.group(1))
            title = match.group(2).strip()
            page = int(match.group(3)) if match.group(3) else None

            current_chapter = Chapter(
                chapter_id=f"{book_id}:ch:{chapter_num}",
                number=chapter_num,
                title=_clean_title(title),
                start_page=page,
            )
            chapters.append(current_chapter)

            # If no page, look for it on next line
            if page is None:
                pending_chapter_page = True
            continue

        # Also try multiline pattern (title ends with control char)
        match = CHAPTER_LINE_PATTERN_PACKT_MULTILINE.match(line)
        if match and not CHAPTER_LINE_PATTERN_PACKT.match(line):
            chapter_num = int(match.group(1))
            title = match.group(2).strip()

            current_chapter = Chapter(
                chapter_id=f"{book_id}:ch:{chapter_num}",
                number=chapter_num,
                title=_clean_title(title),
                start_page=None,
            )
            chapters.append(current_chapter)
            pending_chapter_page = True  # Page on next line
            continue

        # Try section entries (Title ... page) under current chapter
        if current_chapter:
            for pattern in TOC_ENTRY_PATTERNS:
                entry_match = pattern.match(line)
                if entry_match:
                    entry_title = entry_match.group(1).strip()
                    entry_page = (
                        int(entry_match.group(2))
                        if entry_match.lastindex >= 2
                        else None
                    )

                    # Skip if looks like a chapter
                    if _looks_like_chapter_title(entry_title):
                        continue

                    sec_num = len(current_chapter.sections) + 1
                    section = Section(
                        section_id=f"{current_chapter.chapter_id}:sec:{sec_num}",
                        number=f"{current_chapter.number}.{sec_num}",
                        title=_clean_title(entry_title),
                        start_page=entry_page,
                    )
                    current_chapter.sections.append(section)
                    break

    if not chapters:
        return None

    sections_count = sum(len(ch.sections) for ch in chapters)
    confidence = _calculate_toc_confidence(chapters, len(toc_lines))

    return (chapters, confidence, sections_count)


def _parse_toc_numeric(
    book_id: str, toc_lines: list[str]
) -> tuple[list[Chapter], float, int] | None:
    """Parse O'Reilly/Manning-style TOC: 'N. Title ... page'."""
    chapters = []
    current_chapter = None

    for line in toc_lines:
        if not line:
            continue

        # Skip standalone page numbers
        if re.match(r"^[xivlc]+$", line.lower()) or re.match(r"^\d+$", line):
            continue

        # Skip frontmatter entries (Preface, Index, etc)
        if _is_skip_entry(line):
            continue

        # Skip frontmatter with roman numerals (Preface ... xiii)
        if FRONTMATTER_PATTERN.match(line):
            continue

        # Try "N. Title ... page" pattern (O'Reilly format)
        match = CHAPTER_LINE_PATTERN_NUMERIC.match(line)
        if match:
            chapter_num = int(match.group(1))
            title = match.group(2).strip()
            page = int(match.group(3))

            current_chapter = Chapter(
                chapter_id=f"{book_id}:ch:{chapter_num}",
                number=chapter_num,
                title=_clean_title(title),
                start_page=page,
            )
            chapters.append(current_chapter)
            continue

        # Try section entries under current chapter
        # O'Reilly sections don't have number prefix, just "Title page"
        if current_chapter:
            for pattern in TOC_ENTRY_PATTERNS:
                entry_match = pattern.match(line)
                if entry_match:
                    entry_title = entry_match.group(1).strip()
                    entry_page = (
                        int(entry_match.group(2))
                        if entry_match.lastindex >= 2
                        else None
                    )

                    # Skip if starts with number (likely a chapter we missed)
                    if re.match(r"^\d+\.", entry_title):
                        continue

                    # Skip frontmatter-like entries
                    if _is_skip_entry(entry_title):
                        continue

                    sec_num = len(current_chapter.sections) + 1
                    section = Section(
                        section_id=f"{current_chapter.chapter_id}:sec:{sec_num}",
                        number=f"{current_chapter.number}.{sec_num}",
                        title=_clean_title(entry_title),
                        start_page=entry_page,
                    )
                    current_chapter.sections.append(section)
                    break

    if not chapters:
        return None

    # Validate sequential numbering for O'Reilly format
    numbers = [ch.number for ch in chapters]
    is_sequential = numbers == list(range(1, len(numbers) + 1))

    sections_count = sum(len(ch.sections) for ch in chapters)
    confidence = _calculate_toc_confidence(chapters, len(toc_lines))

    # Bonus confidence for O'Reilly if sequential and enough chapters
    if is_sequential and len(chapters) >= 8:
        confidence = min(1.0, confidence + 0.1)

    return (chapters, confidence, sections_count)


def _parse_toc_multiline(
    book_id: str, toc_lines: list[str]
) -> tuple[list[Chapter], float, int] | None:
    """Parse TOC where chapter number, title, and page are on separate lines.

    Pattern: multiline
    - Chapter number alone on one line
    - Title on next line(s)
    - Page number on following line
    - Common in 2-column PDF extractions

    Example:
        1
        Imputing Missing Data
        1
        Technical requirements
        2
    """
    chapters = []
    current_chapter = None

    # State machine for parsing cookbook TOC
    # States: LOOKING_FOR_CHAPTER, EXPECTING_TITLE, EXPECTING_PAGE
    state = "LOOKING_FOR_CHAPTER"
    pending_chapter_num = None
    pending_title_lines = []

    i = 0
    while i < len(toc_lines):
        line = toc_lines[i].strip()
        i += 1

        if not line:
            continue

        # Skip roman numerals (page numbers like xv, viii)
        if re.match(r"^[xivlc]+$", line.lower()):
            continue

        # Skip frontmatter entries
        if _is_skip_entry(line):
            continue

        if state == "LOOKING_FOR_CHAPTER":
            # Look for standalone chapter number (1, 2, 3, ...)
            chapter_num_match = COOKBOOK_CHAPTER_NUMBER.match(line)
            if chapter_num_match:
                candidate_num = int(chapter_num_match.group(1))
                # Valid chapter number: sequential or first chapter
                expected_num = len(chapters) + 1
                if candidate_num == expected_num or (candidate_num == 1 and not chapters):
                    pending_chapter_num = candidate_num
                    pending_title_lines = []
                    state = "EXPECTING_TITLE"
                    continue

            # If we have a current chapter, treat non-number lines as sections
            if current_chapter and not line.isdigit():
                # Section entry: "Technical requirements" followed by page "2"
                # Check if next line is a page number
                next_line = toc_lines[i].strip() if i < len(toc_lines) else ""
                if next_line.isdigit():
                    page_num = int(next_line)
                    i += 1  # Consume page line

                    sec_num = len(current_chapter.sections) + 1
                    section = Section(
                        section_id=f"{current_chapter.chapter_id}:sec:{sec_num}",
                        number=f"{current_chapter.number}.{sec_num}",
                        title=_clean_title(line),
                        start_page=page_num,
                    )
                    current_chapter.sections.append(section)

        elif state == "EXPECTING_TITLE":
            # Title can span multiple lines until we hit a page number
            if line.isdigit():
                # This is the page number - finalize chapter
                page_num = int(line)
                title = " ".join(pending_title_lines)

                current_chapter = Chapter(
                    chapter_id=f"{book_id}:ch:{pending_chapter_num}",
                    number=pending_chapter_num,
                    title=_clean_title(title),
                    start_page=page_num,
                )
                chapters.append(current_chapter)
                state = "LOOKING_FOR_CHAPTER"
            else:
                # Accumulate title lines
                pending_title_lines.append(line)

    if not chapters:
        return None

    # Validate sequential numbering
    numbers = [ch.number for ch in chapters]
    is_sequential = numbers == list(range(1, len(numbers) + 1))

    if not is_sequential:
        # Not a valid cookbook format
        return None

    sections_count = sum(len(ch.sections) for ch in chapters)
    confidence = _calculate_toc_confidence(chapters, len(toc_lines))

    # Bonus for cookbook format with good structure
    if len(chapters) >= 8 and is_sequential:
        confidence = min(1.0, confidence + 0.1)

    return (chapters, confidence, sections_count)


def _parse_toc_leaderdots(
    book_id: str, toc_lines: list[str]
) -> tuple[list[Chapter], float, int] | None:
    """Parse TOC with leader dots: 'Title .... page'.

    Pattern: leaderdots
    - Entries with title followed by dots/spaces and page number
    - Chapters detected by capitalization or explicit markers
    - Common in many book formats

    Example:
        Introduction .................. 1
        Getting Started ............... 15
        Advanced Topics ............... 45
    """
    chapters = []
    current_chapter = None
    chapter_num = 0

    for line in toc_lines:
        if not line:
            continue

        # Skip frontmatter
        if _is_skip_entry(line):
            continue

        # Try leader dots pattern
        match = LEADER_DOTS_PATTERN.match(line)
        if not match:
            continue

        title = match.group(1).strip()
        page_str = match.group(2)

        # Skip if page is roman numeral (frontmatter)
        if re.match(r"^[xivlc]+$", page_str.lower()):
            continue

        page = int(page_str) if page_str.isdigit() else None

        # Determine if this is a chapter or section
        is_chapter = _looks_like_chapter_title(title)

        # Also check if title starts with number (like "1. Introduction")
        num_match = re.match(r"^(\d+)\.\s*(.+)$", title)
        if num_match:
            is_chapter = True
            title = num_match.group(2)

        if is_chapter:
            chapter_num += 1
            current_chapter = Chapter(
                chapter_id=f"{book_id}:ch:{chapter_num}",
                number=chapter_num,
                title=_clean_title(title),
                start_page=page,
            )
            chapters.append(current_chapter)
        elif current_chapter:
            # Add as section to current chapter
            sec_num = len(current_chapter.sections) + 1
            section = Section(
                section_id=f"{current_chapter.chapter_id}:sec:{sec_num}",
                number=f"{current_chapter.number}.{sec_num}",
                title=_clean_title(title),
                start_page=page,
            )
            current_chapter.sections.append(section)

    if not chapters or len(chapters) < TOC_MIN_CHAPTER_ENTRIES:
        return None

    sections_count = sum(len(ch.sections) for ch in chapters)
    confidence = _calculate_toc_confidence(chapters, len(toc_lines))

    return (chapters, confidence, sections_count)


def _extract_from_headings(book_id: str, content: str) -> ExtractionResult:
    """Extract outline by detecting heading patterns."""
    lines = content.split("\n")
    chapters = []
    current_chapter = None
    current_section = None
    prev_line_empty = True  # Track if previous line was empty

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            prev_line_empty = True
            continue

        # Try chapter patterns
        chapter_match = None
        for pattern, pattern_type in CHAPTER_PATTERNS:
            match = re.match(pattern, line_stripped)
            if match:
                chapter_match = (match, pattern_type)
                break

        if chapter_match:
            match, pattern_type = chapter_match
            number_str = match.group(1)
            title = match.group(2).strip()

            # IMPORTANT: Only treat as chapter heading if previous line was empty
            # This prevents capturing references like "Capítulo 3" in middle of text
            if not prev_line_empty:
                prev_line_empty = False
                continue

            # Skip if title looks like a sentence (not a heading)
            # Headings typically: start with capital letter, are short, don't start with articles
            title_lower = title.lower()
            sentence_starters = (
                "en ", "el ", "la ", "los ", "las ", "un ", "una ",
                "si ", "por ", "para ", "que ", "como ", "cuando ",
                "the ", "a ", "an ", "in ", "on ", "for ", "with ", "if ",
            )
            if any(title_lower.startswith(s) for s in sentence_starters):
                prev_line_empty = False
                continue

            # Also skip if title is too long (likely a sentence)
            if len(title) > 60:
                prev_line_empty = False
                continue

            # Skip non-chapter entries (should be sections, not chapters)
            # BUT only for weak patterns - explicit "Chapter N:" markers are always chapters
            # even if title is "Introduction" or "Summary"
            if pattern_type not in ("chapter_word", "part_word"):
                title_lower_clean = title.lower().strip()
                if title_lower_clean in NON_CHAPTER_TITLES:
                    prev_line_empty = False
                    continue

            # Convert roman numerals if needed
            if pattern_type in ("roman_dot", "part_word") and not number_str.isdigit():
                chapter_num = _roman_to_int(number_str)
            else:
                chapter_num = int(number_str) if number_str.isdigit() else len(chapters) + 1

            current_chapter = Chapter(
                chapter_id=f"{book_id}:ch:{chapter_num}",
                number=chapter_num,
                title=_clean_title(title),
            )
            chapters.append(current_chapter)
            current_section = None
            prev_line_empty = False
            continue

        prev_line_empty = False

        # Try section patterns (only if we have a chapter)
        if current_chapter:
            for pattern, pattern_type in SECTION_PATTERNS:
                match = re.match(pattern, line_stripped)
                if match:
                    number = match.group(1)
                    title = match.group(2).strip()

                    sec_num = len(current_chapter.sections) + 1
                    current_section = Section(
                        section_id=f"{current_chapter.chapter_id}:sec:{sec_num}",
                        number=number,
                        title=_clean_title(title),
                    )
                    current_chapter.sections.append(current_section)
                    break

            # Try subsection patterns
            if current_section:
                for pattern, pattern_type in SUBSECTION_PATTERNS:
                    match = re.match(pattern, line_stripped)
                    if match:
                        number = match.group(1)
                        title = match.group(2).strip()

                        current_section.subsections.append({
                            "subsection_id": f"{current_section.section_id}:sub:{len(current_section.subsections) + 1}",
                            "number": number,
                            "title": _clean_title(title),
                        })
                        break

    if not chapters:
        return ExtractionResult(
            success=False,
            outline=None,
            report=OutlineReport(
                method_used="headings",
                confidence=0.0,
                chapters_found=0,
                sections_found=0,
                warnings=["No se detectaron patrones de capítulos"],
            ),
            message="No se encontraron encabezados de capítulos",
        )

    # Guardrail: too many chapters indicates bad detection
    warnings = []
    if len(chapters) > MAX_CHAPTERS_HEADINGS:
        warnings.append(
            f"Demasiados capítulos detectados ({len(chapters)}), "
            f"probablemente falsos positivos. Máximo recomendado: {MAX_CHAPTERS_HEADINGS}"
        )
        # Drastically reduce confidence
        confidence = 0.3
    else:
        confidence = _calculate_headings_confidence(chapters)

    sections_count = sum(len(ch.sections) for ch in chapters)

    outline = Outline(book_id=book_id, chapters=chapters)

    return ExtractionResult(
        success=True,
        outline=outline,
        report=OutlineReport(
            method_used="headings",
            confidence=confidence,
            chapters_found=len(chapters),
            sections_found=sections_count,
            warnings=warnings,
        ),
        message=f"Headings: {len(chapters)} capítulos, {sections_count} secciones",
    )


def _extract_with_llm(book_id: str, content: str) -> ExtractionResult:
    """Extract outline using LLM (placeholder for now)."""
    # TODO: Implement LLM extraction in future iteration
    # For now, return a result indicating LLM is not available

    return ExtractionResult(
        success=False,
        outline=None,
        report=OutlineReport(
            method_used="llm",
            confidence=0.0,
            chapters_found=0,
            sections_found=0,
            warnings=["LLM extraction not yet implemented. Use --review for manual editing."],
        ),
        message="Extracción LLM no implementada. Use --review",
        needs_review=True,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _is_skip_entry(line: str) -> bool:
    """Check if this TOC line should be skipped (front/back matter, etc)."""
    line_lower = line.lower().strip()

    # Skip these specific entries that are not chapters
    skip_patterns = [
        r"^preface\b",
        r"^foreword\b",
        r"^acknowledgment",
        r"^about\s+the\s+author",
        r"^contributor",
        r"^table\s+of\s+contents",
        r"^contents?\s*$",
        r"^index\s*$",
        r"^bibliography\b",
        r"^appendix\b",  # Could be chapter, but usually not numbered
        r"^glossary\b",
        r"^references?\s*$",
        r"^summary\s*$",  # When alone, not a chapter
        r"^making\s+the\s+most",  # Common Packt intro
        r"^join\s+our",  # Community links
        r"^other\s+books",
    ]

    for pattern in skip_patterns:
        if re.match(pattern, line_lower):
            return True

    return False


def _looks_like_chapter_title(title: str) -> bool:
    """Determine if a title looks like a chapter (vs section).

    STRICT: Only return True for strong chapter indicators.
    """
    title_lower = title.lower().strip()

    # Skip front/back matter and non-chapter entries
    if _is_skip_entry(title):
        return False

    # Non-chapter titles (Summary, References, etc.) should be sections
    if title_lower in NON_CHAPTER_TITLES:
        return False

    # Explicit chapter markers (strongest signal)
    if re.match(r"^(?:chapter|capítulo)\s+\d+", title_lower):
        return True

    # Part markers
    if re.match(r"^(?:part|parte)\s+[ivxlc\d]+", title_lower):
        return True

    # Roman numeral at start (like "I. Introduction") - only if title is substantial
    if re.match(r"^[IVXLC]+[\.\s]", title) and len(title) > 5:
        return True

    # DO NOT treat single digit + dot as chapter (like "1. Title")
    # These are often sections within chapters

    # All caps title (often chapters) - but not if too short or common words
    if title.isupper() and len(title) > 15:
        return True

    return False


def _clean_title(title: str) -> str:
    """Clean up a title string."""
    # Remove leading numbers and dots
    title = re.sub(r"^[\d\.]+\s*", "", title)
    # Remove trailing dots
    title = title.rstrip(".")
    # Remove control characters (backspace, etc)
    title = re.sub(r"[\x00-\x1f\x7f]", "", title)
    # Normalize whitespace
    title = " ".join(title.split())
    return title


def _roman_to_int(roman: str) -> int:
    """Convert Roman numeral to integer."""
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    result = 0
    prev = 0
    for char in reversed(roman.upper()):
        curr = values.get(char, 0)
        if curr < prev:
            result -= curr
        else:
            result += curr
        prev = curr
    return result if result > 0 else 1


def _calculate_toc_confidence(chapters: list[Chapter], toc_lines: int) -> float:
    """Calculate confidence score for TOC extraction."""
    if not chapters:
        return 0.0

    # Base confidence for finding TOC
    confidence = 0.7

    # Strong bonus for having multiple chapters (8+ is typical for a book)
    if len(chapters) >= 8:
        confidence += 0.15
    elif len(chapters) >= 5:
        confidence += 0.1

    # Bonus for having sections
    sections_count = sum(len(ch.sections) for ch in chapters)
    if sections_count > 0:
        confidence += 0.05
    if sections_count >= len(chapters) * 2:  # Average 2+ sections per chapter
        confidence += 0.05

    # Bonus for having page numbers
    pages_found = sum(1 for ch in chapters if ch.start_page)
    if pages_found == len(chapters):
        confidence += 0.1
    elif pages_found > len(chapters) * 0.5:
        confidence += 0.05

    # Bonus for sequential chapter numbers (1, 2, 3, ...)
    numbers = [ch.number for ch in chapters]
    if numbers == list(range(1, len(numbers) + 1)):
        confidence += 0.1

    # Penalty for too few chapters
    if len(chapters) < MIN_CHAPTERS_EXPECTED:
        confidence -= 0.3

    # Penalty for suspicious ratio (too many chapters for TOC size)
    if toc_lines > 0 and len(chapters) > toc_lines * 0.5:
        confidence -= 0.2

    return max(0.0, min(1.0, confidence))


def _calculate_headings_confidence(chapters: list[Chapter]) -> float:
    """Calculate confidence score for headings extraction."""
    if not chapters:
        return 0.0

    # Base confidence
    confidence = 0.6

    # Bonus for consistent numbering
    numbers = [ch.number for ch in chapters]
    if numbers == list(range(1, len(numbers) + 1)):
        confidence += 0.15

    # Bonus for having sections
    chapters_with_sections = sum(1 for ch in chapters if ch.sections)
    if chapters_with_sections > len(chapters) * 0.5:
        confidence += 0.1

    # Penalty for too few chapters
    if len(chapters) < MIN_CHAPTERS_EXPECTED:
        confidence -= 0.2

    # Penalty for inconsistent structure
    section_counts = [len(ch.sections) for ch in chapters]
    if section_counts and max(section_counts) > 20:
        confidence -= 0.1  # Suspiciously many sections

    return max(0.0, min(1.0, confidence))


def _validate_outline_structure(data: dict, book_id: str) -> list[str]:
    """Validate outline structure from YAML."""
    errors = []

    if "$schema" not in data:
        errors.append("Missing $schema field")

    if data.get("book_id") != book_id:
        errors.append(f"book_id mismatch: expected {book_id}")

    chapters = data.get("chapters", [])
    if not isinstance(chapters, list):
        errors.append("chapters must be a list")
        return errors

    if len(chapters) < 1:
        errors.append("At least one chapter required")

    for i, ch in enumerate(chapters):
        if not ch.get("title"):
            errors.append(f"Chapter {i + 1}: missing title")
        if not ch.get("chapter_id"):
            errors.append(f"Chapter {i + 1}: missing chapter_id")

    return errors


def _dict_to_outline(data: dict) -> Outline:
    """Convert dictionary to Outline object."""
    chapters = []
    for ch_data in data.get("chapters", []):
        sections = []
        for sec_data in ch_data.get("sections", []):
            section = Section(
                section_id=sec_data.get("section_id", ""),
                number=sec_data.get("number", ""),
                title=sec_data.get("title", ""),
                start_page=sec_data.get("start_page"),
                end_page=sec_data.get("end_page"),
                subsections=sec_data.get("subsections", []),
            )
            sections.append(section)

        chapter = Chapter(
            chapter_id=ch_data.get("chapter_id", ""),
            number=ch_data.get("number", 0),
            title=ch_data.get("title", ""),
            start_page=ch_data.get("start_page"),
            end_page=ch_data.get("end_page"),
            sections=sections,
        )
        chapters.append(chapter)

    return Outline(
        book_id=data.get("book_id", ""),
        chapters=chapters,
        generated_date=data.get("generated_date", datetime.now(timezone.utc).isoformat()),
    )


def _update_book_json(book_path: Path, result: ExtractionResult) -> None:
    """Update book.json with outline metadata."""
    book_json_path = book_path / "book.json"

    if not book_json_path.exists():
        logger.warning("outline_extractor.book_json_missing", path=str(book_json_path))
        return

    with open(book_json_path, "r", encoding="utf-8") as f:
        book_data = json.load(f)

    # Update outline fields
    if result.outline:
        book_data["total_chapters"] = len(result.outline.chapters)

    book_data["outline"] = {
        "method_used": result.report.method_used,
        "confidence": round(result.report.confidence, 2),
        "chapters_found": result.report.chapters_found,
        "sections_found": result.report.sections_found,
        "needs_review": result.needs_review,
    }

    with open(book_json_path, "w", encoding="utf-8") as f:
        json.dump(book_data, f, indent=2, ensure_ascii=False)

    logger.debug("outline_extractor.book_json_updated", path=str(book_json_path))
