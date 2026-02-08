"""Notes generation module.

Responsibilities (F4):
- Generate study notes in Spanish from book content using LLM
- Track source pages for traceability
- Two-phase LLM pipeline: chunk summaries → final notes

Output structure (Markdown):
- Resumen (5-8 viñetas)
- Conceptos clave (tabla)
- Explicación paso a paso
- Mini-ejemplo (if applicable)
- Preguntas de repaso (5 questions)
- Fuentes (pages used)
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from teaching.llm.client import LLMClient, LLMConfig, Message, LLMError

logger = structlog.get_logger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Text selection targets
TARGET_CHARS_MIN = 12000
TARGET_CHARS_MAX = 18000
TARGET_CHARS_DEFAULT = 15000

# Chunk sizes
CHUNK_SIZE_MIN = 6000
CHUNK_SIZE_MAX = 10000
CHUNK_SIZE_TARGET = 8000

# Patterns to sanitize from LLM output (thinking tags, etc.)
SANITIZE_PATTERNS = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<analysis>.*?</analysis>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE),
]


def sanitize_output(text: str) -> str:
    """Remove thinking/reasoning tags from LLM output.

    Removes <think>, <analysis>, <reasoning> blocks that some models emit.
    These internal reasoning blocks should never appear in final output.

    Args:
        text: Raw LLM output text

    Returns:
        Sanitized text with thinking tags removed
    """
    result = text
    for pattern in SANITIZE_PATTERNS:
        result = pattern.sub("", result)
    return result.strip()

# Prompts
SYSTEM_PROMPT_SUMMARY = """Eres un asistente académico especializado en resumir contenido técnico.

REGLAS ESTRICTAS:
1. SIEMPRE responde en español, aunque el texto esté en inglés
2. NO inventes información que no esté en el texto
3. Responde ÚNICAMENTE en formato JSON válido
4. Extrae conceptos con sus definiciones textuales

El JSON debe tener esta estructura exacta:
{
  "resumen": "Resumen de 2-3 oraciones del fragmento",
  "puntos_clave": ["punto 1", "punto 2", ...],
  "conceptos_definidos": [
    {"concepto": "nombre", "definicion": "definición del texto"}
  ]
}"""

USER_PROMPT_SUMMARY = """Analiza el siguiente fragmento del libro (páginas {pages}):

---
{chunk}
---

Extrae un resumen estructurado en JSON."""

SYSTEM_PROMPT_NOTES = """Eres un profesor universitario experto en crear apuntes de estudio claros y concisos.

REGLAS ESTRICTAS:
1. SIEMPRE escribe en español, aunque los resúmenes mencionen términos en inglés
2. USA SOLO la información de los resúmenes proporcionados - NO inventes nada
3. Genera Markdown bien formateado
4. Sé conciso pero completo
5. Los términos técnicos pueden mantenerse en inglés si es lo estándar (ej: "fine-tuning", "API")

ESTRUCTURA OBLIGATORIA del Markdown:
# Apuntes — {libro} — {unidad}

## Resumen
- (5-8 viñetas principales)

## Conceptos clave
| Concepto | Definición |
|----------|------------|
| ... | ... |

## Explicación paso a paso
(Organiza el contenido en subsecciones lógicas)

## Mini-ejemplo
(Solo si hay ejemplos en los resúmenes, si no omite esta sección)

## Preguntas de repaso
1. (5 preguntas de comprensión)

## Fuentes
Páginas utilizadas: X-Y"""

USER_PROMPT_NOTES = """Genera apuntes de estudio para:
- Libro: {book_title}
- Unidad: {unit_title}

Resúmenes de los fragmentos analizados:

{summaries}

Genera los apuntes completos en Markdown siguiendo la estructura indicada."""

# Fallback prompt for text-only summary (when JSON fails)
SYSTEM_PROMPT_SUMMARY_TEXT = """Eres un asistente académico especializado en resumir contenido técnico.

REGLAS:
1. SIEMPRE responde en español, aunque el texto esté en inglés
2. NO inventes información que no esté en el texto
3. Proporciona un resumen de 3-5 oraciones sobre el contenido principal
4. Menciona los conceptos más importantes definidos en el texto"""


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class TextSelection:
    """Selected text from book for a unit."""

    text: str
    pages: list[int]
    start_page: int
    end_page: int
    total_chars: int
    source: str  # "pages" or "content"


@dataclass
class ChunkSummary:
    """Summary of a text chunk."""

    resumen: str
    puntos_clave: list[str]
    conceptos_definidos: list[dict[str, str]]
    pages: list[int]
    mode: str = "json"  # "json" | "text_fallback" | "error"


@dataclass
class NotesMetadata:
    """Metadata for generated notes."""

    unit_id: str
    book_id: str
    provider: str
    model: str
    pages_used: list[int]
    start_page: int
    end_page: int
    chunks_processed: int
    total_tokens: int | None  # None if usage not available from provider
    generation_time_ms: int
    created_at: str
    chunk_modes: dict[str, int] = field(default_factory=dict)  # {"json": N, "text_fallback": M}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "unit_id": self.unit_id,
            "book_id": self.book_id,
            "provider": self.provider,
            "model": self.model,
            "pages_used": self.pages_used,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "chunks_processed": self.chunks_processed,
            "total_tokens": self.total_tokens,
            "generation_time_ms": self.generation_time_ms,
            "created_at": self.created_at,
            "chunk_modes": self.chunk_modes,
        }


@dataclass
class NotesResult:
    """Result of notes generation."""

    success: bool
    notes_path: Path | None
    metadata_path: Path | None
    metadata: NotesMetadata | None
    message: str
    warnings: list[str] = field(default_factory=list)


class NotesGenerationError(Exception):
    """Error during notes generation."""

    pass


# =============================================================================
# TEXT SELECTION
# =============================================================================


def _find_section_page(
    section_title: str,
    pages_dir: Path,
    start_search: int = 1,
) -> int | None:
    """Find page number containing section title.

    Searches pages starting from start_search for case-insensitive match.

    Returns page number or None if not found.
    """
    # Normalize search title
    search_title = section_title.lower().strip()

    # Also try without leading numbers (e.g., "1.1 Title" -> "Title")
    search_variants = [search_title]
    # Remove leading section numbers like "1.1", "1.2.3", etc.
    no_number = re.sub(r"^\d+(\.\d+)*\s*", "", search_title).strip()
    if no_number and no_number != search_title:
        search_variants.append(no_number)

    # Get sorted page files
    page_files = sorted(pages_dir.glob("*.txt"))

    for page_file in page_files:
        page_num = int(page_file.stem)
        if page_num < start_search:
            continue

        try:
            content = page_file.read_text(encoding="utf-8").lower()
            for variant in search_variants:
                if variant in content:
                    return page_num
        except (OSError, UnicodeDecodeError):
            continue

    return None


def _load_pages_range(
    pages_dir: Path,
    start_page: int,
    end_page: int,
) -> tuple[str, list[int]]:
    """Load text from a range of pages.

    Returns (combined_text, list_of_page_numbers).
    """
    texts = []
    pages = []

    for page_num in range(start_page, end_page + 1):
        page_file = pages_dir / f"{page_num:04d}.txt"
        if page_file.exists():
            try:
                content = page_file.read_text(encoding="utf-8")
                texts.append(content)
                pages.append(page_num)
            except (OSError, UnicodeDecodeError):
                continue

    return "\n\n".join(texts), pages


def _load_content_window(
    content_path: Path,
    target_chars: int = TARGET_CHARS_DEFAULT,
) -> tuple[str, int]:
    """Load text from content.txt with target character count.

    Returns (text, estimated_page_count).
    """
    content = content_path.read_text(encoding="utf-8")

    # Take first target_chars characters
    if len(content) > target_chars:
        # Try to break at paragraph boundary
        text = content[:target_chars]
        last_para = text.rfind("\n\n")
        if last_para > target_chars * 0.7:
            text = text[:last_para]
    else:
        text = content

    # Estimate pages (rough: ~2000 chars per page)
    estimated_pages = max(1, len(text) // 2000)

    return text, estimated_pages


def select_unit_text(
    book_id: str,
    unit: dict[str, Any],
    outline: dict[str, Any],
    data_dir: Path,
    target_chars: tuple[int, int] = (TARGET_CHARS_MIN, TARGET_CHARS_MAX),
) -> TextSelection:
    """Select text from book for a unit.

    Strategy:
    1. Get section titles from outline using section_ids
    2. Search for titles in pages/*.txt to find page range
    3. Load pages within range up to target chars
    4. Fallback to content.txt if no pages/

    Args:
        book_id: Book identifier
        unit: Unit data from units.json
        outline: Outline data from outline.json
        data_dir: Base data directory
        target_chars: (min, max) character targets

    Returns:
        TextSelection with text and page info
    """
    book_path = data_dir / "books" / book_id
    pages_dir = book_path / "normalized" / "pages"
    content_path = book_path / "normalized" / "content.txt"

    section_ids = unit.get("section_ids", [])

    # Build section title lookup from outline
    section_titles: dict[str, dict[str, Any]] = {}
    for chapter in outline.get("chapters", []):
        for section in chapter.get("sections", []):
            sid = section.get("section_id", "")
            if sid:
                section_titles[sid] = section

    # Get titles for this unit's sections
    unit_sections = [section_titles.get(sid, {}) for sid in section_ids if sid in section_titles]

    # Try pages-based selection first
    if pages_dir.exists() and list(pages_dir.glob("*.txt")):
        return _select_from_pages(
            pages_dir=pages_dir,
            unit_sections=unit_sections,
            target_chars=target_chars,
        )

    # Fallback to content.txt
    if content_path.exists():
        return _select_from_content(
            content_path=content_path,
            target_chars=target_chars,
        )

    raise NotesGenerationError(
        f"No se encontró contenido normalizado para {book_id}"
    )


def _select_from_pages(
    pages_dir: Path,
    unit_sections: list[dict[str, Any]],
    target_chars: tuple[int, int],
) -> TextSelection:
    """Select text using page files."""
    # Find start and end pages from section titles
    start_page = None
    end_page = None
    last_search_start = 1

    for section in unit_sections:
        title = section.get("title", "")
        hint_page = section.get("start_page", last_search_start)

        if title:
            found_page = _find_section_page(
                section_title=title,
                pages_dir=pages_dir,
                start_search=max(1, hint_page - 5) if hint_page else last_search_start,
            )

            if found_page:
                if start_page is None:
                    start_page = found_page
                end_page = found_page
                last_search_start = found_page

    # If we couldn't find sections, use hint pages from outline
    if start_page is None and unit_sections:
        hint_pages = [s.get("start_page") for s in unit_sections if s.get("start_page")]
        if hint_pages:
            start_page = min(hint_pages)
            end_page = max(hint_pages) + 10  # Estimate section length

    # Default fallback
    if start_page is None:
        start_page = 1
        end_page = 15

    # Expand end_page to reach target chars
    text, pages = _load_pages_range(pages_dir, start_page, end_page)

    # If not enough text, keep loading pages
    max_page = max(int(f.stem) for f in pages_dir.glob("*.txt"))
    while len(text) < target_chars[0] and end_page < max_page:
        end_page = min(end_page + 5, max_page)
        text, pages = _load_pages_range(pages_dir, start_page, end_page)

    # Trim if too much text
    if len(text) > target_chars[1]:
        text = text[: target_chars[1]]
        # Find last complete paragraph
        last_para = text.rfind("\n\n")
        if last_para > target_chars[0]:
            text = text[:last_para]

    return TextSelection(
        text=text,
        pages=pages,
        start_page=pages[0] if pages else start_page,
        end_page=pages[-1] if pages else end_page,
        total_chars=len(text),
        source="pages",
    )


def _select_from_content(
    content_path: Path,
    target_chars: tuple[int, int],
) -> TextSelection:
    """Select text from content.txt (fallback)."""
    text, estimated_pages = _load_content_window(
        content_path=content_path,
        target_chars=target_chars[1],
    )

    return TextSelection(
        text=text,
        pages=list(range(1, estimated_pages + 1)),
        start_page=1,
        end_page=estimated_pages,
        total_chars=len(text),
        source="content",
    )


# =============================================================================
# CHUNKING
# =============================================================================


def chunk_text(
    text: str,
    pages: list[int],
    chunk_size: tuple[int, int] = (CHUNK_SIZE_MIN, CHUNK_SIZE_MAX),
) -> list[tuple[str, list[int]]]:
    """Split text into chunks with page tracking.

    Chunks are split at paragraph boundaries when possible.

    Args:
        text: Full text to chunk
        pages: List of page numbers corresponding to text
        chunk_size: (min, max) characters per chunk

    Returns:
        List of (chunk_text, chunk_pages) tuples
    """
    if not text:
        return []

    # Split into paragraphs
    paragraphs = text.split("\n\n")

    chunks: list[tuple[str, list[int]]] = []
    current_chunk = []
    current_chars = 0

    # Estimate chars per page for page tracking
    chars_per_page = len(text) / max(len(pages), 1) if pages else 2000

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_len = len(para)

        # Would this paragraph exceed max?
        if current_chars + para_len > chunk_size[1] and current_chunk:
            # Save current chunk
            chunk_text = "\n\n".join(current_chunk)
            chunk_pages = _estimate_chunk_pages(
                len(chunks), chunk_text, pages, chars_per_page
            )
            chunks.append((chunk_text, chunk_pages))
            current_chunk = []
            current_chars = 0

        current_chunk.append(para)
        current_chars += para_len

        # Is this chunk big enough?
        if current_chars >= chunk_size[0]:
            chunk_text = "\n\n".join(current_chunk)
            chunk_pages = _estimate_chunk_pages(
                len(chunks), chunk_text, pages, chars_per_page
            )
            chunks.append((chunk_text, chunk_pages))
            current_chunk = []
            current_chars = 0

    # Don't forget remaining text
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunk_pages = _estimate_chunk_pages(
            len(chunks), chunk_text, pages, chars_per_page
        )
        chunks.append((chunk_text, chunk_pages))

    return chunks


def _estimate_chunk_pages(
    chunk_idx: int,
    chunk_text: str,
    all_pages: list[int],
    chars_per_page: float,
) -> list[int]:
    """Estimate which pages a chunk covers.

    Simple heuristic based on character position.
    """
    if not all_pages:
        return [1]

    # Estimate start position in chars
    # This is approximate since we don't track exact positions
    chunk_len = len(chunk_text)
    estimated_page_span = max(1, int(chunk_len / chars_per_page))

    # Calculate offset based on chunk index
    pages_before = chunk_idx * estimated_page_span

    start_idx = min(pages_before, len(all_pages) - 1)
    end_idx = min(start_idx + estimated_page_span, len(all_pages))

    return all_pages[start_idx:end_idx] or [all_pages[-1]]


# =============================================================================
# LLM PIPELINE
# =============================================================================


def _summarize_chunk(
    client: LLMClient,
    chunk_text: str,
    chunk_pages: list[int],
) -> ChunkSummary:
    """Generate summary for a text chunk using LLM.

    Phase 1 of the pipeline. Falls back to text-only if JSON fails.
    """
    pages_str = f"{min(chunk_pages)}-{max(chunk_pages)}" if chunk_pages else "?"

    user_prompt = USER_PROMPT_SUMMARY.format(
        pages=pages_str,
        chunk=chunk_text,
    )

    # Intento 1: JSON estructurado
    try:
        result = client.simple_json(
            system_prompt=SYSTEM_PROMPT_SUMMARY,
            user_message=user_prompt,
            temperature=0.3,  # Lower temperature for factual extraction
        )
        return ChunkSummary(
            resumen=result.get("resumen", ""),
            puntos_clave=result.get("puntos_clave", []),
            conceptos_definidos=result.get("conceptos_definidos", []),
            pages=chunk_pages,
            mode="json",
        )
    except LLMError as e:
        logger.warning("chunk_json_failed_trying_text", pages=pages_str, error=str(e))

    # Intento 2: Fallback a texto plano
    try:
        text_response = client.simple_chat(
            system_prompt=SYSTEM_PROMPT_SUMMARY_TEXT,
            user_message=user_prompt,
            temperature=0.3,
        )
        return ChunkSummary(
            resumen=text_response,
            puntos_clave=[],
            conceptos_definidos=[],
            pages=chunk_pages,
            mode="text_fallback",
        )
    except LLMError as e:
        logger.error("chunk_summary_failed", pages=pages_str, error=str(e))
        return ChunkSummary(
            resumen="Error al procesar este fragmento.",
            puntos_clave=[],
            conceptos_definidos=[],
            pages=chunk_pages,
            mode="error",
        )


def _generate_final_notes(
    client: LLMClient,
    book_title: str,
    unit_title: str,
    summaries: list[ChunkSummary],
    pages_range: tuple[int, int],
) -> str:
    """Generate final notes from chunk summaries.

    Phase 2 of the pipeline.
    """
    # Format summaries for prompt
    summaries_text = ""
    for i, summary in enumerate(summaries, 1):
        pages_str = f"{min(summary.pages)}-{max(summary.pages)}" if summary.pages else "?"
        summaries_text += f"\n### Fragmento {i} (páginas {pages_str})\n"
        summaries_text += f"**Resumen:** {summary.resumen}\n"

        if summary.puntos_clave:
            summaries_text += "**Puntos clave:**\n"
            for punto in summary.puntos_clave:
                summaries_text += f"- {punto}\n"

        if summary.conceptos_definidos:
            summaries_text += "**Conceptos:**\n"
            for concepto in summary.conceptos_definidos:
                nombre = concepto.get("concepto", "")
                definicion = concepto.get("definicion", "")
                summaries_text += f"- {nombre}: {definicion}\n"

    user_prompt = USER_PROMPT_NOTES.format(
        book_title=book_title,
        unit_title=unit_title,
        summaries=summaries_text,
    )

    # Add pages range to system prompt
    system_prompt = SYSTEM_PROMPT_NOTES.replace(
        "Páginas utilizadas: X-Y",
        f"Páginas utilizadas: {pages_range[0]}-{pages_range[1]}",
    )

    response = client.simple_chat(
        system_prompt=system_prompt,
        user_message=user_prompt,
        temperature=0.5,  # Slightly higher for more natural writing
        max_tokens=4096,
    )

    return response


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def generate_notes(
    unit_id: str,
    data_dir: Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    force: bool = False,
    client: LLMClient | None = None,
) -> NotesResult:
    """Generate study notes for a unit.

    Args:
        unit_id: Unit identifier (e.g., "book-id-ch01-u01")
        data_dir: Base data directory (default: ./data)
        provider: Override LLM provider
        model: Override LLM model
        force: Overwrite existing notes
        client: Optional pre-configured LLM client (for testing)

    Returns:
        NotesResult with paths and metadata
    """
    if data_dir is None:
        data_dir = Path("data")

    start_time = time.time()
    warnings: list[str] = []
    total_tokens: int | None = None  # None if provider doesn't return usage

    # Extract book_id from unit_id
    # Format: {book_id}-ch{XX}-u{YY}
    match = re.match(r"(.+)-ch\d{2}-u\d{2}$", unit_id)
    if not match:
        return NotesResult(
            success=False,
            notes_path=None,
            metadata_path=None,
            metadata=None,
            message=f"Formato de unit_id inválido: {unit_id}",
        )

    book_id = match.group(1)
    book_path = data_dir / "books" / book_id

    # Load required files
    units_path = book_path / "artifacts" / "units" / "units.json"
    outline_path = book_path / "outline" / "outline.json"
    book_json_path = book_path / "book.json"

    if not units_path.exists():
        return NotesResult(
            success=False,
            notes_path=None,
            metadata_path=None,
            metadata=None,
            message=f"No se encontró units.json para {book_id}",
        )

    if not outline_path.exists():
        return NotesResult(
            success=False,
            notes_path=None,
            metadata_path=None,
            metadata=None,
            message=f"No se encontró outline.json para {book_id}",
        )

    # Load units and find target unit
    with open(units_path) as f:
        units_data = json.load(f)

    unit = None
    for u in units_data.get("units", []):
        if u.get("unit_id") == unit_id:
            unit = u
            break

    if unit is None:
        return NotesResult(
            success=False,
            notes_path=None,
            metadata_path=None,
            metadata=None,
            message=f"Unidad no encontrada: {unit_id}",
        )

    # Load outline
    with open(outline_path) as f:
        outline = json.load(f)

    # Check output paths
    notes_dir = book_path / "artifacts" / "notes"
    notes_path = notes_dir / f"{unit_id}.md"
    metadata_path = notes_dir / f"{unit_id}.json"

    if notes_path.exists() and not force:
        return NotesResult(
            success=False,
            notes_path=notes_path,
            metadata_path=metadata_path,
            metadata=None,
            message=f"Apuntes ya existen. Usa --force para sobrescribir.",
        )

    # Get book title
    book_title = book_id
    if book_json_path.exists():
        try:
            with open(book_json_path) as f:
                book_data = json.load(f)
            book_title = book_data.get("title", book_id)
        except (json.JSONDecodeError, OSError):
            pass

    unit_title = unit.get("title", unit_id)

    # Initialize LLM client
    if client is None:
        config = LLMConfig.from_yaml()
        client = LLMClient(
            config=config,
            provider=provider,  # type: ignore
            model=model,
        )

    # Check LLM availability
    if not client.is_available():
        return NotesResult(
            success=False,
            notes_path=None,
            metadata_path=None,
            metadata=None,
            message=f"No se pudo conectar al servidor LLM ({client.config.provider})",
        )

    # Select text for this unit
    try:
        text_selection = select_unit_text(
            book_id=book_id,
            unit=unit,
            outline=outline,
            data_dir=data_dir,
        )
    except NotesGenerationError as e:
        return NotesResult(
            success=False,
            notes_path=None,
            metadata_path=None,
            metadata=None,
            message=str(e),
        )

    logger.info(
        "text_selected",
        unit_id=unit_id,
        chars=text_selection.total_chars,
        pages=f"{text_selection.start_page}-{text_selection.end_page}",
        source=text_selection.source,
    )

    if text_selection.source == "content":
        warnings.append("Usando content.txt (sin páginas individuales)")

    # Chunk the text
    chunks = chunk_text(
        text=text_selection.text,
        pages=text_selection.pages,
    )

    logger.info("text_chunked", unit_id=unit_id, chunks=len(chunks))

    # Phase 1: Generate chunk summaries
    summaries: list[ChunkSummary] = []
    for i, (chunk_text_content, chunk_pages) in enumerate(chunks):
        logger.debug("summarizing_chunk", chunk=i + 1, total=len(chunks))
        summary = _summarize_chunk(client, chunk_text_content, chunk_pages)
        summaries.append(summary)
        # Note: We'd track tokens here if client exposed them per call

    # Phase 2: Generate final notes
    logger.info("generating_final_notes", unit_id=unit_id)
    notes_content = _generate_final_notes(
        client=client,
        book_title=book_title,
        unit_title=unit_title,
        summaries=summaries,
        pages_range=(text_selection.start_page, text_selection.end_page),
    )

    # Create output directory
    notes_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize and write notes (remove any <think> tags from LLM output)
    notes_content = sanitize_output(notes_content)
    notes_path.write_text(notes_content, encoding="utf-8")

    # Calculate timing
    generation_time_ms = int((time.time() - start_time) * 1000)

    # Count chunk modes for tracking
    chunk_modes: dict[str, int] = {"json": 0, "text_fallback": 0, "error": 0}
    for summary in summaries:
        chunk_modes[summary.mode] = chunk_modes.get(summary.mode, 0) + 1

    # Add warning if fallbacks were used
    if chunk_modes.get("text_fallback", 0) > 0:
        warnings.append(f"Usó fallback texto en {chunk_modes['text_fallback']} chunk(s)")
    if chunk_modes.get("error", 0) > 0:
        warnings.append(f"Error en {chunk_modes['error']} chunk(s)")

    # Create metadata
    metadata = NotesMetadata(
        unit_id=unit_id,
        book_id=book_id,
        provider=client.config.provider,
        model=client.config.model,
        pages_used=text_selection.pages,
        start_page=text_selection.start_page,
        end_page=text_selection.end_page,
        chunks_processed=len(chunks),
        total_tokens=total_tokens,
        generation_time_ms=generation_time_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
        chunk_modes=chunk_modes,
    )

    # Write metadata
    with open(metadata_path, "w") as f:
        json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)

    # Update book.json
    if book_json_path.exists():
        try:
            with open(book_json_path) as f:
                book_data = json.load(f)

            notes_count = book_data.get("notes_generated_count", 0)
            book_data["notes_generated_count"] = notes_count + 1
            book_data["last_notes_generated_at"] = datetime.now(timezone.utc).isoformat()

            with open(book_json_path, "w") as f:
                json.dump(book_data, f, indent=2, ensure_ascii=False)

        except (json.JSONDecodeError, OSError) as e:
            warnings.append(f"No se pudo actualizar book.json: {e}")

    logger.info(
        "notes_generated",
        unit_id=unit_id,
        pages=f"{text_selection.start_page}-{text_selection.end_page}",
        chunks=len(chunks),
        time_ms=generation_time_ms,
    )

    return NotesResult(
        success=True,
        notes_path=notes_path,
        metadata_path=metadata_path,
        metadata=metadata,
        message=f"Apuntes generados: {notes_path.name}",
        warnings=warnings,
    )
