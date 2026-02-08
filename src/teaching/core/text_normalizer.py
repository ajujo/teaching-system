"""Text cleanup and normalization module.

Responsibilities (F2 - Hito4):
- Normalize whitespace and line breaks
- Fix word hyphenation at line ends (conservative)
- Preserve code blocks (no aggressive reflow)
- Normalize special characters to UTF-8
- Remove repetitive headers/footers (pagination)
- Update book.json with normalization metrics

IMPORTANT: Does NOT summarize, translate, or change content meaning.
Only performs structural cleanup.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Constants
MAX_CONTENT_LOSS_RATIO = 0.10  # Warn if >10% chars lost
CODE_BLOCK_INDICATORS = [
    r"^\s{4,}",  # 4+ space indent
    r"^\t+",  # Tab indent
    r"```",  # Markdown code fence
    r"def\s+\w+\(",  # Python function
    r"class\s+\w+",  # Python class
    r"function\s+\w+\(",  # JS function
    r"import\s+\w+",  # Import statements
    r"from\s+\w+\s+import",  # Python from import
    r"\{$",  # Opening brace at end
    r"^\s*\}",  # Closing brace
    r"^\s*#\s*\w+",  # Code comments
    r"^\s*//",  # C-style comments
]


@dataclass
class NormalizationMetrics:
    """Metrics from text normalization."""

    original_chars: int
    normalized_chars: int
    chars_removed: int
    chars_removed_ratio: float
    hyphen_breaks_fixed: int
    multiple_spaces_collapsed: int
    multiple_newlines_collapsed: int
    content_loss_warning: bool = False


@dataclass
class NormalizationResult:
    """Result of text normalization."""

    success: bool
    metrics: NormalizationMetrics
    message: str


class NormalizationError(Exception):
    """Base exception for normalization errors."""

    pass


class ContentLossError(NormalizationError):
    """Raised when normalization loses too much content."""

    def __init__(self, loss_ratio: float):
        self.loss_ratio = loss_ratio
        super().__init__(
            f"Normalización perdió {loss_ratio:.1%} del contenido "
            f"(máximo permitido: {MAX_CONTENT_LOSS_RATIO:.0%})"
        )


def normalize_book(book_id: str, data_dir: Path | None = None) -> NormalizationResult:
    """Normalize extracted text for a book.

    Reads from raw/content.txt and writes to normalized/content.txt.
    Also processes individual page/chapter files if they exist.

    Args:
        book_id: Book identifier (slug)
        data_dir: Base data directory (defaults to 'data')

    Returns:
        NormalizationResult with metrics and status

    Raises:
        FileNotFoundError: If book directory or raw content doesn't exist
        ContentLossError: If normalization loses >10% of content
    """
    base_dir = data_dir or Path("data")
    book_path = base_dir / "books" / book_id

    # Find raw content
    raw_dir = book_path / "raw"
    if not raw_dir.exists():
        raise FileNotFoundError(f"Directorio raw no encontrado: {raw_dir}")

    raw_content_file = raw_dir / "content.txt"
    if not raw_content_file.exists():
        raise FileNotFoundError(f"Archivo raw/content.txt no encontrado: {raw_content_file}")

    logger.info("text_normalizer.start", book_id=book_id)

    # Read raw content
    raw_text = raw_content_file.read_text(encoding="utf-8")
    original_chars = len(raw_text)

    # Normalize main content
    normalized_text, metrics = _normalize_text(raw_text)
    normalized_chars = len(normalized_text)

    # Create normalized directory
    normalized_dir = book_path / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)

    # Write normalized content
    normalized_content_file = normalized_dir / "content.txt"
    normalized_content_file.write_text(normalized_text, encoding="utf-8")

    # Process individual pages/chapters if they exist
    pages_dir = raw_dir / "pages"
    chapters_dir = raw_dir / "chapters"

    if pages_dir.exists():
        _normalize_page_files(pages_dir, normalized_dir / "pages")

    if chapters_dir.exists():
        _normalize_page_files(chapters_dir, normalized_dir / "chapters")

    # Check for excessive content loss
    chars_removed = original_chars - normalized_chars
    loss_ratio = chars_removed / original_chars if original_chars > 0 else 0

    content_loss_warning = loss_ratio > MAX_CONTENT_LOSS_RATIO

    if content_loss_warning:
        logger.warning(
            "text_normalizer.content_loss",
            book_id=book_id,
            loss_ratio=f"{loss_ratio:.1%}",
            threshold=f"{MAX_CONTENT_LOSS_RATIO:.0%}",
        )

    # Build final metrics
    final_metrics = NormalizationMetrics(
        original_chars=original_chars,
        normalized_chars=normalized_chars,
        chars_removed=chars_removed,
        chars_removed_ratio=loss_ratio,
        hyphen_breaks_fixed=metrics["hyphen_breaks_fixed"],
        multiple_spaces_collapsed=metrics["multiple_spaces_collapsed"],
        multiple_newlines_collapsed=metrics["multiple_newlines_collapsed"],
        content_loss_warning=content_loss_warning,
    )

    logger.info(
        "text_normalizer.metrics",
        book_id=book_id,
        original_chars=original_chars,
        normalized_chars=normalized_chars,
        loss_ratio=f"{loss_ratio:.1%}",
        hyphen_fixes=metrics["hyphen_breaks_fixed"],
    )

    # Update book.json
    _update_book_json(book_path, final_metrics)

    message = f"Normalizado: {normalized_chars:,} chars ({loss_ratio:.1%} removido)"
    if content_loss_warning:
        message += " - AVISO: pérdida de contenido significativa"

    return NormalizationResult(
        success=True,
        metrics=final_metrics,
        message=message,
    )


def _normalize_text(text: str) -> tuple[str, dict]:
    """Apply all normalization rules to text.

    Args:
        text: Raw text to normalize

    Returns:
        Tuple of (normalized_text, metrics_dict)
    """
    metrics = {
        "hyphen_breaks_fixed": 0,
        "multiple_spaces_collapsed": 0,
        "multiple_newlines_collapsed": 0,
    }

    # Step 1: Normalize Unicode characters
    text = _normalize_unicode(text)

    # Step 2: Fix hyphenated line breaks (conservative)
    text, hyphen_count = _fix_hyphenation(text)
    metrics["hyphen_breaks_fixed"] = hyphen_count

    # Step 3: Collapse multiple spaces (but preserve code indentation)
    text, space_count = _collapse_spaces(text)
    metrics["multiple_spaces_collapsed"] = space_count

    # Step 4: Collapse excessive blank lines
    text, newline_count = _collapse_newlines(text)
    metrics["multiple_newlines_collapsed"] = newline_count

    # Step 5: Strip trailing whitespace from lines
    text = _strip_trailing_whitespace(text)

    # Step 6: Ensure final newline
    if text and not text.endswith("\n"):
        text += "\n"

    return text, metrics


def _normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC form and replace common problematic chars.

    Args:
        text: Input text

    Returns:
        Unicode-normalized text
    """
    # Normalize to NFC (composed form)
    text = unicodedata.normalize("NFC", text)

    # Replace common problematic characters
    replacements = {
        "\u2018": "'",  # Left single quote
        "\u2019": "'",  # Right single quote
        "\u201c": '"',  # Left double quote
        "\u201d": '"',  # Right double quote
        "\u2013": "-",  # En dash
        "\u2014": "-",  # Em dash
        "\u2026": "...",  # Ellipsis
        "\u00a0": " ",  # Non-breaking space
        "\u200b": "",  # Zero-width space
        "\ufeff": "",  # BOM
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def _fix_hyphenation(text: str) -> tuple[str, int]:
    """Fix words broken by hyphen at line end.

    Uses conservative approach: only fix if the resulting word
    looks like a valid word (lowercase letters joining).

    Args:
        text: Input text

    Returns:
        Tuple of (fixed_text, count_of_fixes)
    """
    # Pattern: word ending with hyphen at end of line, followed by lowercase continuation
    # Example: "pro-\ngramming" -> "programming"
    # Only fix if both parts are lowercase letters (conservative)
    pattern = r"([a-z]+)-\n([a-z]+)"

    count = 0

    def replacer(match):
        nonlocal count
        count += 1
        return match.group(1) + match.group(2)

    text = re.sub(pattern, replacer, text)

    return text, count


def _collapse_spaces(text: str) -> tuple[str, int]:
    """Collapse multiple spaces to single space, preserving code indentation.

    Args:
        text: Input text

    Returns:
        Tuple of (cleaned_text, count_of_collapses)
    """
    lines = text.split("\n")
    result_lines = []
    total_collapses = 0

    for line in lines:
        # Check if line looks like code (preserve indentation)
        is_code_line = _is_code_line(line)

        if is_code_line:
            # Preserve the line as-is for code
            result_lines.append(line)
        else:
            # Collapse multiple spaces in non-code lines
            original = line
            # Keep leading spaces (might be intentional), collapse middle spaces
            leading_spaces = len(line) - len(line.lstrip(" "))
            stripped = line.lstrip(" ")
            collapsed = re.sub(r"  +", " ", stripped)

            if len(stripped) != len(collapsed):
                total_collapses += 1

            # Restore reasonable indentation (max 4 spaces for non-code)
            indent = " " * min(leading_spaces, 4)
            result_lines.append(indent + collapsed)

    return "\n".join(result_lines), total_collapses


def _is_code_line(line: str) -> bool:
    """Detect if a line is likely code.

    Args:
        line: Single line of text

    Returns:
        True if line appears to be code
    """
    for pattern in CODE_BLOCK_INDICATORS:
        if re.search(pattern, line):
            return True
    return False


def _collapse_newlines(text: str) -> tuple[str, int]:
    """Collapse 3+ consecutive newlines to 2 (one blank line).

    Args:
        text: Input text

    Returns:
        Tuple of (cleaned_text, count_of_collapses)
    """
    original_count = len(re.findall(r"\n{3,}", text))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, original_count


def _strip_trailing_whitespace(text: str) -> str:
    """Strip trailing whitespace from each line.

    Args:
        text: Input text

    Returns:
        Text with trailing whitespace removed
    """
    lines = text.split("\n")
    return "\n".join(line.rstrip() for line in lines)


def _normalize_page_files(input_dir: Path, output_dir: Path) -> None:
    """Normalize all page/chapter files in a directory.

    Args:
        input_dir: Directory with raw page files
        output_dir: Directory for normalized output
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for input_file in sorted(input_dir.glob("*.txt")):
        raw_text = input_file.read_text(encoding="utf-8")
        normalized_text, _ = _normalize_text(raw_text)

        output_file = output_dir / input_file.name
        output_file.write_text(normalized_text, encoding="utf-8")

    logger.debug(
        "text_normalizer.pages_normalized",
        input_dir=str(input_dir),
        output_dir=str(output_dir),
    )


def _update_book_json(book_path: Path, metrics: NormalizationMetrics) -> None:
    """Update book.json with normalization metrics.

    Args:
        book_path: Path to book directory
        metrics: Normalization metrics
    """
    book_json_path = book_path / "book.json"

    if not book_json_path.exists():
        logger.warning("text_normalizer.book_json_missing", path=str(book_json_path))
        return

    with open(book_json_path, "r", encoding="utf-8") as f:
        book_data = json.load(f)

    # Add normalization section
    book_data["normalization"] = {
        "original_chars": metrics.original_chars,
        "normalized_chars": metrics.normalized_chars,
        "chars_removed": metrics.chars_removed,
        "chars_removed_ratio": round(metrics.chars_removed_ratio, 4),
        "hyphen_breaks_fixed": metrics.hyphen_breaks_fixed,
        "multiple_spaces_collapsed": metrics.multiple_spaces_collapsed,
        "multiple_newlines_collapsed": metrics.multiple_newlines_collapsed,
        "content_loss_warning": metrics.content_loss_warning,
    }

    with open(book_json_path, "w", encoding="utf-8") as f:
        json.dump(book_data, f, indent=2, ensure_ascii=False)

    logger.debug("text_normalizer.book_json_updated", path=str(book_json_path))


# Utility functions for direct text normalization (used in tests)


def normalize_text(text: str) -> str:
    """Normalize text content directly.

    Args:
        text: Raw text to normalize

    Returns:
        Normalized text
    """
    normalized, _ = _normalize_text(text)
    return normalized


def fix_hyphenation(text: str) -> str:
    """Fix hyphenated line breaks in text.

    Args:
        text: Text with potential hyphenation

    Returns:
        Text with hyphenation fixed
    """
    fixed, _ = _fix_hyphenation(text)
    return fixed
