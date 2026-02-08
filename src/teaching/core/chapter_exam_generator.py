"""Chapter exam generation module.

Responsibilities (F6):
- Generate chapter-level exams aggregating content from ALL units in a chapter
- Include source tracking (unit_id, pages, rationale) per question
- Support question type distribution (MCQ, TF, SA)
- Persist exam sets to artifacts/exams/

Output structure (JSON):
- chapter_exam_set_v1 schema with questions array
- Deterministic IDs: {book_id}-ch{NN}-exam{XX}
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import structlog

from teaching.core.notes_generator import sanitize_output
from teaching.llm.client import LLMClient, LLMConfig, LLMError

logger = structlog.get_logger(__name__)

# =============================================================================
# TYPES
# =============================================================================

QuestionType = Literal["multiple_choice", "true_false", "short_answer"]
Difficulty = Literal["easy", "medium", "hard"]
SetDifficulty = Literal["intro", "mid", "adv"]
GenerationMode = Literal["json", "text_fallback", "error"]

# =============================================================================
# PROMPTS
# =============================================================================

SYSTEM_PROMPT_EXAM = """Eres un profesor universitario experto en crear examenes de capitulo.

REGLAS ESTRICTAS:
1. SIEMPRE responde en espanol
2. USA SOLO el contenido proporcionado - NO inventes informacion
3. Responde UNICAMENTE en formato JSON valido
4. Genera preguntas que cubran TODAS las unidades del capitulo
5. Incluye informacion de origen (source) para cada pregunta
6. Las respuestas correctas deben estar SOLO en correct_answer
7. Las explicaciones deben ser educativas y claras

El JSON debe tener esta estructura exacta:
{{
  "questions": [
    {{
      "type": "multiple_choice | true_false | short_answer",
      "difficulty": "easy | medium | hard",
      "question": "Pregunta clara y precisa en espanol",
      "options": ["opcion a", "opcion b", "opcion c", "opcion d"] | null,
      "correct_answer": "indice 0-3 para MC | true/false para TF | texto para SA",
      "explanation": "Explicacion educativa de por que esta es la respuesta correcta",
      "points": 1,
      "tags": ["concepto1", "concepto2"],
      "source": {{
        "unit_id": "ID de la unidad de origen",
        "pages": [lista de paginas relevantes],
        "section_ids": ["IDs de secciones"] | null,
        "rationale": "Una oracion explicando por que esta pregunta viene de esta unidad"
      }}
    }}
  ]
}}

Tipos de pregunta:
- multiple_choice: 4 opciones, correct_answer es indice 0-3
- true_false: sin options, correct_answer es true o false
- short_answer: sin options, correct_answer es la respuesta esperada (texto)

Distribucion sugerida para {n} preguntas:
- {mcq_count} preguntas multiple_choice (50%)
- {tf_count} preguntas true_false (25%)
- {sa_count} preguntas short_answer (25%)

IMPORTANTE: Asegura que las preguntas cubran todas las unidades proporcionadas de manera equilibrada."""

USER_PROMPT_EXAM = """Genera {n} preguntas de examen para el Capitulo {chapter_number}: "{chapter_title}"

Este capitulo contiene las siguientes unidades:
{units_summary}

---
CONTENIDO DEL CAPITULO:
{content}
---

Configuracion:
- Dificultad del examen: {difficulty}
- Distribucion de tipos:
  - {mcq_count} preguntas multiple_choice
  - {tf_count} preguntas true_false
  - {sa_count} preguntas short_answer

Genera el JSON con las {n} preguntas, asegurando cobertura de todas las unidades."""

# Fallback prompt
SYSTEM_PROMPT_EXAM_TEXT = """Eres un profesor experto en crear examenes.

REGLAS:
1. SIEMPRE responde en espanol
2. USA SOLO el contenido proporcionado
3. Genera preguntas claras y educativas
4. Incluye source para cada pregunta

Responde en JSON valido con la estructura de questions."""


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class QuestionSource:
    """Source tracking for an exam question."""

    unit_id: str
    pages: list[int]
    section_ids: list[str] | None = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "unit_id": self.unit_id,
            "pages": self.pages,
            "rationale": self.rationale,
        }
        if self.section_ids:
            result["section_ids"] = self.section_ids
        return result


@dataclass
class ExamQuestion:
    """A single exam question."""

    question_id: str
    type: QuestionType
    difficulty: Difficulty
    question: str
    correct_answer: str | int | bool
    explanation: str
    points: int = 1
    options: list[str] | None = None
    tags: list[str] = field(default_factory=list)
    source: QuestionSource | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "question_id": self.question_id,
            "type": self.type,
            "difficulty": self.difficulty,
            "question": self.question,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "points": self.points,
            "tags": self.tags,
        }
        if self.options is not None:
            result["options"] = self.options
        if self.source is not None:
            result["source"] = self.source.to_dict()
        return result


@dataclass
class ChapterExamSetMetadata:
    """Metadata for generated chapter exam set."""

    exam_set_id: str
    book_id: str
    chapter_id: str
    chapter_number: int
    chapter_title: str
    units_included: list[str]
    provider: str
    model: str
    generation_time_ms: int
    mode: GenerationMode
    created_at: str
    total_points: int
    difficulty: SetDifficulty = "mid"
    passing_threshold: float = 0.6
    pages_used: list[int] = field(default_factory=list)
    valid: bool = True
    validation_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": "chapter_exam_set_v1",
            "exam_set_id": self.exam_set_id,
            "book_id": self.book_id,
            "chapter_id": self.chapter_id,
            "chapter_number": self.chapter_number,
            "chapter_title": self.chapter_title,
            "units_included": self.units_included,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at,
            "generation_time_ms": self.generation_time_ms,
            "mode": self.mode,
            "difficulty": self.difficulty,
            "total_points": self.total_points,
            "passing_threshold": self.passing_threshold,
            "pages_used": self.pages_used,
            "valid": self.valid,
            "validation_warnings": self.validation_warnings,
        }


@dataclass
class ExamSetResult:
    """Result of exam generation."""

    success: bool
    exam_set_path: Path | None
    metadata: ChapterExamSetMetadata | None
    questions: list[ExamQuestion]
    message: str
    warnings: list[str] = field(default_factory=list)


class ExamGenerationError(Exception):
    """Error during exam generation."""

    pass


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _resolve_chapter_id(book_id: str, chapter: str) -> tuple[str, int]:
    """Resolve chapter string to chapter_id and number.

    Accepts:
    - "ch01" or "ch1" -> (book_id:ch:1, 1)
    - "1" -> (book_id:ch:1, 1)
    - "test-book:ch:1" -> (test-book:ch:1, 1)

    Returns:
        Tuple of (chapter_id, chapter_number)
    """
    # Full chapter_id format
    if f"{book_id}:ch:" in chapter:
        match = re.search(r":ch:(\d+)$", chapter)
        if match:
            num = int(match.group(1))
            return chapter, num

    # ch01 or ch1 format
    match = re.match(r"ch(\d+)$", chapter.lower())
    if match:
        num = int(match.group(1))
        return f"{book_id}:ch:{num}", num

    # Numeric format
    if chapter.isdigit():
        num = int(chapter)
        return f"{book_id}:ch:{num}", num

    # Fallback: try to extract any number
    match = re.search(r"(\d+)", chapter)
    if match:
        num = int(match.group(1))
        return f"{book_id}:ch:{num}", num

    raise ValueError(f"Cannot resolve chapter: {chapter}")


def _get_units_for_chapter(
    chapter_id: str,
    units_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Get all units belonging to a chapter.

    Args:
        chapter_id: Chapter ID to filter by
        units_data: Units.json data

    Returns:
        List of unit dicts for this chapter
    """
    return [
        u for u in units_data.get("units", [])
        if u.get("chapter_id") == chapter_id
    ]


def _generate_exam_set_id(book_id: str, chapter_num: int, exams_dir: Path) -> str:
    """Generate deterministic exam_set_id.

    Counts existing exams for this chapter and increments.
    Format: {book_id}-ch{NN}-exam{XX}
    """
    pattern = f"{book_id}-ch{chapter_num:02d}-exam*.json"
    existing = list(exams_dir.glob(pattern))
    next_num = len(existing) + 1
    return f"{book_id}-ch{chapter_num:02d}-exam{next_num:02d}"


def _aggregate_chapter_text(
    book_id: str,
    units: list[dict[str, Any]],
    outline: dict[str, Any],
    data_dir: Path,
) -> tuple[str, list[int], dict[str, list[int]]]:
    """Aggregate text from all units in a chapter.

    Args:
        book_id: Book identifier
        units: List of unit dicts
        outline: Outline data
        data_dir: Base data directory

    Returns:
        Tuple of (combined_text, all_pages, unit_pages_map)
    """
    book_path = data_dir / "books" / book_id
    pages_dir = book_path / "normalized" / "pages"

    all_text_parts: list[str] = []
    all_pages: set[int] = set()
    unit_pages_map: dict[str, list[int]] = {}

    # Build section page ranges from outline
    section_pages: dict[str, tuple[int, int | None]] = {}
    for chapter in outline.get("chapters", []):
        sections = chapter.get("sections", [])
        for i, section in enumerate(sections):
            section_id = section.get("section_id", "")
            start_page = section.get("start_page", 1)
            # End page is start of next section or chapter end
            if i + 1 < len(sections):
                end_page = sections[i + 1].get("start_page", start_page) - 1
            else:
                # Last section in chapter - use next chapter start or a default
                end_page = start_page + 10  # Reasonable default
            section_pages[section_id] = (start_page, end_page)

    for unit in units:
        unit_id = unit.get("unit_id", "")
        section_ids = unit.get("section_ids", [])

        # Determine pages for this unit
        unit_page_set: set[int] = set()
        for section_id in section_ids:
            if section_id in section_pages:
                start, end = section_pages[section_id]
                unit_page_set.update(range(start, (end or start) + 1))

        # If no pages found, use a default range
        if not unit_page_set:
            unit_page_set = {1, 2, 3}

        unit_pages = sorted(unit_page_set)
        unit_pages_map[unit_id] = unit_pages
        all_pages.update(unit_pages)

        # Read page content
        unit_text_parts = [f"\n=== UNIDAD: {unit.get('title', unit_id)} ===\n"]
        for page_num in unit_pages:
            page_file = pages_dir / f"{page_num:04d}.txt"
            if page_file.exists():
                try:
                    content = page_file.read_text(encoding="utf-8")
                    unit_text_parts.append(f"[Página {page_num}]\n{content}\n")
                except OSError:
                    continue

        all_text_parts.append("".join(unit_text_parts))

    return "\n".join(all_text_parts), sorted(all_pages), unit_pages_map


def _try_parse_json_text(text: str) -> dict[str, Any] | None:
    """Try to parse JSON from text using multiple strategies.

    Strategies:
    1. Direct JSON parse
    2. Extract from ```json...``` blocks
    3. Extract first {...} object

    Returns dict or None if parsing fails OR result is not a dict.
    This prevents crashes when json.loads() returns str/list/int/etc.
    """
    # Sanitize first
    text = sanitize_output(text)

    # Strategy 1: Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract ```json...``` block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if json_match:
        try:
            result = json.loads(json_match.group(1).strip())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Strategy 3: Extract first {...}
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            result = json.loads(text[start:end])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return None


def _parse_questions_from_llm(
    raw_data: dict[str, Any],
    exam_set_id: str,
    units: list[dict[str, Any]],
    unit_pages_map: dict[str, list[int]],
) -> list[ExamQuestion]:
    """Parse questions from LLM response."""
    questions = []

    # Defensive guard: ensure raw_data is dict
    if not isinstance(raw_data, dict):
        logger.error(
            "parse_questions_received_non_dict",
            received_type=type(raw_data).__name__,
        )
        return []

    raw_questions = raw_data.get("questions", [])

    # Guard: ensure raw_questions is a list
    if not isinstance(raw_questions, list):
        logger.warning(
            "raw_questions_not_list",
            received_type=type(raw_questions).__name__,
        )
        raw_questions = []

    # Build unit lookup for validation
    valid_unit_ids = {u["unit_id"] for u in units}
    default_unit_id = units[0]["unit_id"] if units else ""

    for i, q_data in enumerate(raw_questions, 1):
        # Guard: skip non-dict entries (e.g., if LLM returns ["Q1", "Q2"])
        if not isinstance(q_data, dict):
            logger.warning(
                "question_entry_not_dict",
                index=i,
                received_type=type(q_data).__name__,
                preview=str(q_data)[:100] if q_data else "",
            )
            continue

        question_id = f"{exam_set_id}-q{i:02d}"

        # Normalize type
        q_type = q_data.get("type", "multiple_choice")
        if q_type not in ("multiple_choice", "true_false", "short_answer"):
            q_type = "multiple_choice"

        # Normalize difficulty
        difficulty = q_data.get("difficulty", "medium")
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"

        # Normalize correct_answer based on type
        correct_answer = q_data.get("correct_answer", "")
        options = q_data.get("options")

        if q_type == "multiple_choice":
            if isinstance(correct_answer, str) and correct_answer.isdigit():
                correct_answer = int(correct_answer)
            elif not isinstance(correct_answer, int):
                correct_answer = 0

            if options:
                max_valid_index = len(options) - 1
                if correct_answer < 0 or correct_answer > max_valid_index:
                    correct_answer = max(0, min(correct_answer, max_valid_index))

        elif q_type == "true_false":
            if isinstance(correct_answer, str):
                correct_answer = correct_answer.lower() in ("true", "verdadero", "sí", "si")
            elif not isinstance(correct_answer, bool):
                correct_answer = bool(correct_answer)

        # Parse source
        source_data = q_data.get("source", {})
        # Guard: ensure source_data is dict (LLM might return "source": "string")
        if not isinstance(source_data, dict):
            logger.warning(
                "source_data_not_dict",
                index=i,
                received_type=type(source_data).__name__,
                preview=str(source_data)[:100] if source_data else "",
            )
            source_data = {}

        source_unit_id = source_data.get("unit_id", default_unit_id)

        # Validate unit_id
        if source_unit_id not in valid_unit_ids:
            source_unit_id = default_unit_id

        source_pages = source_data.get("pages", unit_pages_map.get(source_unit_id, [1]))
        source_section_ids = source_data.get("section_ids")
        source_rationale = source_data.get("rationale", "")

        source = QuestionSource(
            unit_id=source_unit_id,
            pages=source_pages if source_pages else [1],
            section_ids=source_section_ids,
            rationale=source_rationale,
        )

        # Determine points (SA questions get 2 points)
        points = q_data.get("points", 2 if q_type == "short_answer" else 1)

        question = ExamQuestion(
            question_id=question_id,
            type=q_type,
            difficulty=difficulty,
            question=q_data.get("question", "Pregunta no disponible"),
            correct_answer=correct_answer,
            explanation=q_data.get("explanation", ""),
            points=points,
            options=options if q_type == "multiple_choice" else None,
            tags=q_data.get("tags", []),
            source=source,
        )
        questions.append(question)

    return questions


def _validate_exam_set(
    questions: list[ExamQuestion],
    mode: GenerationMode,
) -> tuple[bool, list[str]]:
    """Validate exam set quality after generation.

    Returns:
        Tuple of (is_valid, warnings)

    Validation rules:
    1. empty_explanations_ratio: if == 1.0 and mode == text_fallback -> invalid
    2. mcq_answer_distribution: if one value (0-3) appears in >= 80% of MCQs
       with >= 4 MCQs -> strong warning, invalid if text_fallback
    3. All MCQs should have exactly 4 options
    """
    validation_warnings: list[str] = []
    is_valid = True

    if not questions:
        return False, ["No hay preguntas en el examen"]

    # 1. Check empty explanations
    empty_explanations = sum(1 for q in questions if not q.explanation.strip())
    empty_ratio = empty_explanations / len(questions)

    if empty_ratio == 1.0:
        validation_warnings.append(
            f"Todas las explicaciones están vacías ({len(questions)}/{len(questions)})"
        )
        if mode == "text_fallback":
            is_valid = False
    elif empty_ratio > 0.5:
        validation_warnings.append(
            f"Mayoría de explicaciones vacías ({empty_explanations}/{len(questions)})"
        )

    # 2. Check MCQ answer distribution
    mcq_questions = [q for q in questions if q.type == "multiple_choice"]
    if len(mcq_questions) >= 4:
        answer_counts: dict[Any, int] = {}
        for q in mcq_questions:
            ans = q.correct_answer
            answer_counts[ans] = answer_counts.get(ans, 0) + 1

        max_count = max(answer_counts.values())
        max_ratio = max_count / len(mcq_questions)

        if max_ratio >= 0.8:
            dominant_answer = [k for k, v in answer_counts.items() if v == max_count][0]
            validation_warnings.append(
                f"Distribución sospechosa: {max_count}/{len(mcq_questions)} MCQs "
                f"tienen correct_answer={dominant_answer} ({max_ratio:.0%})"
            )
            if mode == "text_fallback":
                is_valid = False

    # 3. Check MCQ options
    for i, q in enumerate(mcq_questions, 1):
        if q.options is None or len(q.options) != 4:
            validation_warnings.append(f"MCQ #{i} no tiene 4 opciones")

    return is_valid, validation_warnings


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def generate_chapter_exam(
    book_id: str,
    chapter: str,
    data_dir: Path | None = None,
    n: int = 12,
    mcq_ratio: float = 0.5,
    tf_ratio: float = 0.25,
    sa_ratio: float = 0.25,
    difficulty: str = "mid",
    provider: str | None = None,
    model: str | None = None,
    force: bool = False,
    client: LLMClient | None = None,
) -> ExamSetResult:
    """Generate a chapter exam.

    Args:
        book_id: Book identifier
        chapter: Chapter identifier (ch01, 1, or full ID)
        data_dir: Base data directory (default: ./data)
        n: Total number of questions (default: 12)
        mcq_ratio: Ratio of MCQ questions (default: 0.5)
        tf_ratio: Ratio of TF questions (default: 0.25)
        sa_ratio: Ratio of SA questions (default: 0.25)
        difficulty: Exam difficulty (intro, mid, adv)
        provider: Override LLM provider
        model: Override LLM model
        force: Overwrite existing (creates new exam if False)
        client: Optional pre-configured LLM client (for testing)

    Returns:
        ExamSetResult with path and questions
    """
    if data_dir is None:
        data_dir = Path("data")

    # Normalize difficulty
    if difficulty not in ("intro", "mid", "adv"):
        difficulty = "mid"

    start_time = time.time()
    warnings: list[str] = []
    mode: GenerationMode = "json"

    book_path = data_dir / "books" / book_id

    # Check book exists
    if not book_path.exists():
        return ExamSetResult(
            success=False,
            exam_set_path=None,
            metadata=None,
            questions=[],
            message=f"Libro no encontrado: {book_id}",
        )

    # Load required files
    units_path = book_path / "artifacts" / "units" / "units.json"
    outline_path = book_path / "outline" / "outline.json"
    book_json_path = book_path / "book.json"

    if not units_path.exists():
        return ExamSetResult(
            success=False,
            exam_set_path=None,
            metadata=None,
            questions=[],
            message=f"No se encontró units.json para {book_id}",
        )

    if not outline_path.exists():
        return ExamSetResult(
            success=False,
            exam_set_path=None,
            metadata=None,
            questions=[],
            message=f"No se encontró outline.json para {book_id}",
        )

    # Resolve chapter
    try:
        chapter_id, chapter_num = _resolve_chapter_id(book_id, chapter)
    except ValueError as e:
        return ExamSetResult(
            success=False,
            exam_set_path=None,
            metadata=None,
            questions=[],
            message=str(e),
        )

    # Load units and outline
    with open(units_path) as f:
        units_data = json.load(f)

    with open(outline_path) as f:
        outline = json.load(f)

    # Get units for this chapter
    units = _get_units_for_chapter(chapter_id, units_data)

    if not units:
        return ExamSetResult(
            success=False,
            exam_set_path=None,
            metadata=None,
            questions=[],
            message=f"No se encontraron unidades para el capítulo: {chapter_id}",
        )

    # Get chapter title from outline
    chapter_title = f"Capítulo {chapter_num}"
    for ch in outline.get("chapters", []):
        if ch.get("chapter_id") == chapter_id:
            chapter_title = ch.get("title", chapter_title)
            break

    # Setup output directory
    exams_dir = book_path / "artifacts" / "exams"
    exams_dir.mkdir(parents=True, exist_ok=True)

    # Generate exam_set_id
    exam_set_id = _generate_exam_set_id(book_id, chapter_num, exams_dir)

    # Initialize LLM client
    if client is None:
        config = LLMConfig.from_yaml()
        client = LLMClient(
            config=config,
            provider=provider,
            model=model,
        )

    # Check LLM availability
    if not client.is_available():
        return ExamSetResult(
            success=False,
            exam_set_path=None,
            metadata=None,
            questions=[],
            message=f"No se pudo conectar al servidor LLM ({client.config.provider})",
        )

    # Aggregate chapter text
    chapter_text, all_pages, unit_pages_map = _aggregate_chapter_text(
        book_id=book_id,
        units=units,
        outline=outline,
        data_dir=data_dir,
    )

    logger.info(
        "chapter_text_aggregated",
        chapter_id=chapter_id,
        units=len(units),
        pages=len(all_pages),
        chars=len(chapter_text),
    )

    # Calculate question distribution
    mcq_count = int(n * mcq_ratio)
    tf_count = int(n * tf_ratio)
    sa_count = n - mcq_count - tf_count  # Remainder goes to SA

    # Build units summary for prompt
    units_summary = "\n".join([
        f"- {u['unit_id']}: {u.get('title', 'Sin título')} (páginas {unit_pages_map.get(u['unit_id'], [])})"
        for u in units
    ])

    # Build prompts
    system_prompt = SYSTEM_PROMPT_EXAM.format(
        n=n,
        mcq_count=mcq_count,
        tf_count=tf_count,
        sa_count=sa_count,
    )

    user_prompt = USER_PROMPT_EXAM.format(
        n=n,
        chapter_number=chapter_num,
        chapter_title=chapter_title,
        units_summary=units_summary,
        content=chapter_text[:20000],  # Limit content size
        difficulty=difficulty,
        mcq_count=mcq_count,
        tf_count=tf_count,
        sa_count=sa_count,
    )

    # Generate questions with LLM
    questions: list[ExamQuestion] = []

    try:
        raw_result = client.simple_json(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.5,
        )

        # Guard: ensure simple_json returned a dict
        if not isinstance(raw_result, dict):
            logger.warning(
                "simple_json_returned_non_dict",
                received_type=type(raw_result).__name__,
            )
            raise LLMError("El LLM no devolvió un objeto JSON válido")

        questions = _parse_questions_from_llm(raw_result, exam_set_id, units, unit_pages_map)
        mode = "json"

    except LLMError as e:
        logger.warning("exam_json_failed_trying_text", error=str(e))
        warnings.append(f"JSON fallback usado: {e}")

        try:
            text_response = client.simple_chat(
                system_prompt=SYSTEM_PROMPT_EXAM_TEXT,
                user_message=user_prompt,
                temperature=0.5,
            )

            # Use robust JSON parsing
            raw_result = _try_parse_json_text(text_response)

            if raw_result is None:
                logger.error(
                    "exam_text_fallback_not_parseable",
                    response_preview=text_response[:200] if text_response else "",
                )
                return ExamSetResult(
                    success=False,
                    exam_set_path=None,
                    metadata=None,
                    questions=[],
                    message="No se pudo extraer JSON de la respuesta del LLM",
                )

            # Debug log for troubleshooting
            questions_val = raw_result.get("questions") if isinstance(raw_result, dict) else None
            logger.debug(
                "exam_fallback_parsed",
                raw_type=type(raw_result).__name__,
                has_questions="questions" in raw_result if isinstance(raw_result, dict) else False,
                questions_type=type(questions_val).__name__ if questions_val is not None else "N/A",
                questions_len=len(questions_val) if isinstance(questions_val, list) else 0,
            )

            questions = _parse_questions_from_llm(raw_result, exam_set_id, units, unit_pages_map)
            mode = "text_fallback"

        except LLMError as e2:
            logger.error("exam_generation_failed", error=str(e2))
            return ExamSetResult(
                success=False,
                exam_set_path=None,
                metadata=None,
                questions=[],
                message=f"Error generando examen: {e2}",
            )

    if not questions:
        return ExamSetResult(
            success=False,
            exam_set_path=None,
            metadata=None,
            questions=[],
            message="No se generaron preguntas",
        )

    # Validate exam set quality
    is_valid, validation_warnings = _validate_exam_set(questions, mode)

    if not is_valid:
        logger.error(
            "exam_set_invalid",
            warnings=validation_warnings,
            mode=mode,
        )
        return ExamSetResult(
            success=False,
            exam_set_path=None,
            metadata=None,
            questions=[],
            message=f"Exam set inválido: {'; '.join(validation_warnings)}",
            warnings=validation_warnings,
        )

    # Add validation warnings to general warnings
    warnings.extend(validation_warnings)

    # Calculate total points
    total_points = sum(q.points for q in questions)

    # Calculate timing
    generation_time_ms = int((time.time() - start_time) * 1000)

    # Create metadata
    metadata = ChapterExamSetMetadata(
        exam_set_id=exam_set_id,
        book_id=book_id,
        chapter_id=chapter_id,
        chapter_number=chapter_num,
        chapter_title=chapter_title,
        units_included=[u["unit_id"] for u in units],
        provider=client.config.provider,
        model=client.config.model,
        generation_time_ms=generation_time_ms,
        mode=mode,
        created_at=datetime.now(timezone.utc).isoformat(),
        total_points=total_points,
        difficulty=difficulty,
        passing_threshold=0.6,
        pages_used=all_pages,
        valid=is_valid,
        validation_warnings=validation_warnings,
    )

    # Build complete exam set
    exam_set = metadata.to_dict()
    exam_set["questions"] = [q.to_dict() for q in questions]

    # Write to file
    exam_set_path = exams_dir / f"{exam_set_id}.json"
    with open(exam_set_path, "w", encoding="utf-8") as f:
        json.dump(exam_set, f, indent=2, ensure_ascii=False)

    logger.info(
        "chapter_exam_generated",
        exam_set_id=exam_set_id,
        chapter_id=chapter_id,
        questions=len(questions),
        total_points=total_points,
        time_ms=generation_time_ms,
        mode=mode,
    )

    return ExamSetResult(
        success=True,
        exam_set_path=exam_set_path,
        metadata=metadata,
        questions=questions,
        message=f"Examen generado: {exam_set_path.name}",
        warnings=warnings,
    )
