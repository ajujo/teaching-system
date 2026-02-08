"""Exercise generation module.

Responsibilities (F5):
- Generate practice exercises from unit content using LLM
- Support multiple exercise types (MC, TF, short_answer)
- Persist exercise sets to artifacts/exercises/
- Handle LLM JSON fallback mechanism

Output structure (JSON):
- exercise_set_v1 schema with exercises array
- Deterministic IDs: {unit_id}-ex{NN}
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

from teaching.core.notes_generator import sanitize_output, select_unit_text
from teaching.llm.client import LLMClient, LLMConfig, LLMError

logger = structlog.get_logger(__name__)

# =============================================================================
# TYPES
# =============================================================================

ExerciseType = Literal["multiple_choice", "true_false", "short_answer"]
Difficulty = Literal["easy", "medium", "hard"]
SetDifficulty = Literal["intro", "mid", "adv"]
GenerationMode = Literal["json", "text_fallback", "error"]

# =============================================================================
# PROMPTS
# =============================================================================

SYSTEM_PROMPT_EXERCISES = """Eres un profesor universitario experto en crear ejercicios de evaluación.

REGLAS ESTRICTAS:
1. SIEMPRE responde en español
2. USA SOLO el contenido proporcionado - NO inventes información
3. Responde ÚNICAMENTE en formato JSON válido
4. Genera ejercicios variados según los tipos solicitados
5. Las respuestas correctas deben estar SOLO en correct_answer
6. Las explicaciones deben ser educativas y claras

El JSON debe tener esta estructura exacta:
{
  "exercises": [
    {
      "type": "multiple_choice | true_false | short_answer",
      "difficulty": "easy | medium | hard",
      "question": "Pregunta clara y precisa en español",
      "options": ["opción a", "opción b", "opción c", "opción d"] | null,
      "correct_answer": "índice 0-3 para MC | true/false para TF | texto para SA",
      "explanation": "Explicación educativa de por qué esta es la respuesta correcta",
      "points": 1,
      "tags": ["concepto1", "concepto2"]
    }
  ]
}

Tipos de ejercicio:
- multiple_choice: 4 opciones, correct_answer es índice 0-3
- true_false: sin options, correct_answer es true o false
- short_answer: sin options, correct_answer es la respuesta esperada (texto)

Dificultad del set:
- intro: preguntas básicas de comprensión y memorización
- mid: preguntas que requieren análisis y síntesis
- adv: preguntas de aplicación, evaluación y casos complejos"""

USER_PROMPT_EXERCISES = """Genera {n} ejercicios para la unidad "{unit_title}" basándote SOLO en el siguiente contenido (páginas {start_page}-{end_page}):

---
{content}
---

Configuración:
- Dificultad del set: {difficulty}
- Tipos de ejercicio a incluir: {types_desc}
- Número total de ejercicios: {n}

Distribución sugerida de dificultad individual:
- Si el set es "intro": mayoría easy, algunos medium
- Si el set es "mid": mezcla de easy, medium, hard
- Si el set es "adv": mayoría medium y hard

Genera el JSON con los {n} ejercicios."""

# Fallback prompt for text response
SYSTEM_PROMPT_EXERCISES_TEXT = """Eres un profesor experto en crear ejercicios de evaluación.

REGLAS:
1. SIEMPRE responde en español
2. USA SOLO el contenido proporcionado
3. Genera ejercicios claros y educativos

Responde en JSON válido con la estructura de exercises."""


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class Exercise:
    """A single exercise."""

    exercise_id: str
    type: ExerciseType
    difficulty: Difficulty
    question: str
    correct_answer: str | int | bool
    explanation: str
    points: int = 1
    options: list[str] | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "exercise_id": self.exercise_id,
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
        return result


@dataclass
class ExerciseSetMetadata:
    """Metadata for generated exercise set."""

    exercise_set_id: str
    unit_id: str
    book_id: str
    provider: str
    model: str
    difficulty: SetDifficulty
    types: list[str]
    generation_time_ms: int
    mode: GenerationMode
    pages_used: list[int]
    created_at: str
    total_points: int
    passing_threshold: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": "exercise_set_v1",
            "exercise_set_id": self.exercise_set_id,
            "unit_id": self.unit_id,
            "book_id": self.book_id,
            "provider": self.provider,
            "model": self.model,
            "difficulty": self.difficulty,
            "types": self.types,
            "generation_time_ms": self.generation_time_ms,
            "mode": self.mode,
            "pages_used": self.pages_used,
            "created_at": self.created_at,
            "total_points": self.total_points,
            "passing_threshold": self.passing_threshold,
        }


@dataclass
class ExerciseSetResult:
    """Result of exercise generation."""

    success: bool
    exercise_set_path: Path | None
    metadata: ExerciseSetMetadata | None
    exercises: list[Exercise]
    message: str
    warnings: list[str] = field(default_factory=list)


class ExerciseGenerationError(Exception):
    """Error during exercise generation."""

    pass


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _generate_exercise_set_id(unit_id: str, exercises_dir: Path) -> str:
    """Generate deterministic exercise_set_id.

    Counts existing exercise sets for this unit and increments.
    Format: {unit_id}-ex{NN}
    """
    existing = list(exercises_dir.glob(f"{unit_id}-ex*.json"))
    next_num = len(existing) + 1
    return f"{unit_id}-ex{next_num:02d}"


def _get_types_description(types: list[str]) -> str:
    """Get human-readable description of exercise types."""
    if "mixed" in types or set(types) == {"quiz", "practical"}:
        return "mezcla de multiple_choice, true_false y short_answer"
    elif "quiz" in types:
        return "principalmente multiple_choice y true_false, algunos short_answer"
    elif "practical" in types:
        return "principalmente short_answer con algunos multiple_choice"
    else:
        return ", ".join(types)


def _parse_exercises_from_llm(
    raw_data: dict[str, Any],
    exercise_set_id: str,
) -> list[Exercise]:
    """Parse exercises from LLM response."""
    exercises = []
    raw_exercises = raw_data.get("exercises", [])

    for i, ex_data in enumerate(raw_exercises, 1):
        exercise_id = f"{exercise_set_id}-q{i:02d}"

        # Normalize type
        ex_type = ex_data.get("type", "multiple_choice")
        if ex_type not in ("multiple_choice", "true_false", "short_answer"):
            ex_type = "multiple_choice"

        # Normalize difficulty
        difficulty = ex_data.get("difficulty", "medium")
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"

        # Normalize correct_answer based on type
        correct_answer = ex_data.get("correct_answer", "")
        options = ex_data.get("options")

        if ex_type == "multiple_choice":
            # Ensure it's an integer
            if isinstance(correct_answer, str) and correct_answer.isdigit():
                correct_answer = int(correct_answer)
            elif not isinstance(correct_answer, int):
                correct_answer = 0

            # Validate correct_answer is in valid range [0, len(options)-1]
            if options:
                max_valid_index = len(options) - 1
                if correct_answer < 0 or correct_answer > max_valid_index:
                    logger.warning(
                        "invalid_correct_answer_index",
                        exercise_id=exercise_id,
                        correct_answer=correct_answer,
                        max_valid_index=max_valid_index,
                    )
                    # Clamp to valid range
                    correct_answer = max(0, min(correct_answer, max_valid_index))

        elif ex_type == "true_false":
            # Ensure it's a boolean
            if isinstance(correct_answer, str):
                correct_answer = correct_answer.lower() in ("true", "verdadero", "sí", "si")
            elif not isinstance(correct_answer, bool):
                correct_answer = bool(correct_answer)

        exercise = Exercise(
            exercise_id=exercise_id,
            type=ex_type,
            difficulty=difficulty,
            question=ex_data.get("question", "Pregunta no disponible"),
            correct_answer=correct_answer,
            explanation=ex_data.get("explanation", ""),
            points=ex_data.get("points", 1),
            options=options if ex_type == "multiple_choice" else None,
            tags=ex_data.get("tags", []),
        )
        exercises.append(exercise)

    return exercises


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def generate_exercises(
    unit_id: str,
    data_dir: Path | None = None,
    difficulty: str = "mid",
    types: list[str] | None = None,
    n: int = 10,
    provider: str | None = None,
    model: str | None = None,
    force: bool = False,
    client: LLMClient | None = None,
) -> ExerciseSetResult:
    """Generate practice exercises for a unit.

    Args:
        unit_id: Unit identifier (e.g., "book-id-ch01-u01")
        data_dir: Base data directory (default: ./data)
        difficulty: Set difficulty (intro, mid, adv)
        types: Exercise types to include (quiz, practical, mixed)
        n: Number of exercises to generate
        provider: Override LLM provider
        model: Override LLM model
        force: Overwrite existing (creates new set if False)
        client: Optional pre-configured LLM client (for testing)

    Returns:
        ExerciseSetResult with path and exercises
    """
    if data_dir is None:
        data_dir = Path("data")

    if types is None:
        types = ["mixed"]

    # Normalize difficulty
    if difficulty not in ("intro", "mid", "adv"):
        difficulty = "mid"

    start_time = time.time()
    warnings: list[str] = []
    mode: GenerationMode = "json"

    # Extract book_id from unit_id
    # Format: {book_id}-ch{XX}-u{YY}
    match = re.match(r"(.+)-ch\d{2}-u\d{2}$", unit_id)
    if not match:
        return ExerciseSetResult(
            success=False,
            exercise_set_path=None,
            metadata=None,
            exercises=[],
            message=f"Formato de unit_id inválido: {unit_id}",
        )

    book_id = match.group(1)
    book_path = data_dir / "books" / book_id

    # Load required files
    units_path = book_path / "artifacts" / "units" / "units.json"
    outline_path = book_path / "outline" / "outline.json"
    book_json_path = book_path / "book.json"

    if not units_path.exists():
        return ExerciseSetResult(
            success=False,
            exercise_set_path=None,
            metadata=None,
            exercises=[],
            message=f"No se encontró units.json para {book_id}",
        )

    if not outline_path.exists():
        return ExerciseSetResult(
            success=False,
            exercise_set_path=None,
            metadata=None,
            exercises=[],
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
        return ExerciseSetResult(
            success=False,
            exercise_set_path=None,
            metadata=None,
            exercises=[],
            message=f"Unidad no encontrada: {unit_id}",
        )

    # Load outline
    with open(outline_path) as f:
        outline = json.load(f)

    # Setup output directory
    exercises_dir = book_path / "artifacts" / "exercises"
    exercises_dir.mkdir(parents=True, exist_ok=True)

    # Generate exercise_set_id
    exercise_set_id = _generate_exercise_set_id(unit_id, exercises_dir)

    # Get book and unit titles
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
            provider=provider,
            model=model,
        )

    # Check LLM availability
    if not client.is_available():
        return ExerciseSetResult(
            success=False,
            exercise_set_path=None,
            metadata=None,
            exercises=[],
            message=f"No se pudo conectar al servidor LLM ({client.config.provider})",
        )

    # Select text for this unit (reuse from notes_generator)
    try:
        text_selection = select_unit_text(
            book_id=book_id,
            unit=unit,
            outline=outline,
            data_dir=data_dir,
        )
    except Exception as e:
        return ExerciseSetResult(
            success=False,
            exercise_set_path=None,
            metadata=None,
            exercises=[],
            message=str(e),
        )

    logger.info(
        "text_selected_for_exercises",
        unit_id=unit_id,
        chars=text_selection.total_chars,
        pages=f"{text_selection.start_page}-{text_selection.end_page}",
    )

    # Build prompt
    types_desc = _get_types_description(types)
    user_prompt = USER_PROMPT_EXERCISES.format(
        n=n,
        unit_title=unit_title,
        start_page=text_selection.start_page,
        end_page=text_selection.end_page,
        content=text_selection.text[:15000],  # Limit content size
        difficulty=difficulty,
        types_desc=types_desc,
    )

    # Generate exercises with LLM
    exercises: list[Exercise] = []

    try:
        # Try JSON mode first
        raw_result = client.simple_json(
            system_prompt=SYSTEM_PROMPT_EXERCISES,
            user_message=user_prompt,
            temperature=0.5,
        )
        exercises = _parse_exercises_from_llm(raw_result, exercise_set_id)
        mode = "json"

    except LLMError as e:
        logger.warning("exercise_json_failed_trying_text", error=str(e))
        warnings.append(f"JSON fallback usado: {e}")

        # Fallback to text + parse
        try:
            text_response = client.simple_chat(
                system_prompt=SYSTEM_PROMPT_EXERCISES_TEXT,
                user_message=user_prompt,
                temperature=0.5,
            )
            # Sanitize and try to parse
            text_response = sanitize_output(text_response)

            # Try to extract JSON from text
            try:
                raw_result = json.loads(text_response)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                json_match = re.search(r"\{[\s\S]*\}", text_response)
                if json_match:
                    raw_result = json.loads(json_match.group(0))
                else:
                    raise LLMError("No se pudo extraer JSON de la respuesta")

            exercises = _parse_exercises_from_llm(raw_result, exercise_set_id)
            mode = "text_fallback"

        except (LLMError, json.JSONDecodeError) as e2:
            logger.error("exercise_generation_failed", error=str(e2))
            return ExerciseSetResult(
                success=False,
                exercise_set_path=None,
                metadata=None,
                exercises=[],
                message=f"Error generando ejercicios: {e2}",
            )

    if not exercises:
        return ExerciseSetResult(
            success=False,
            exercise_set_path=None,
            metadata=None,
            exercises=[],
            message="No se generaron ejercicios",
        )

    # Calculate total points
    total_points = sum(ex.points for ex in exercises)

    # Calculate timing
    generation_time_ms = int((time.time() - start_time) * 1000)

    # Create metadata
    metadata = ExerciseSetMetadata(
        exercise_set_id=exercise_set_id,
        unit_id=unit_id,
        book_id=book_id,
        provider=client.config.provider,
        model=client.config.model,
        difficulty=difficulty,
        types=types,
        generation_time_ms=generation_time_ms,
        mode=mode,
        pages_used=text_selection.pages,
        created_at=datetime.now(timezone.utc).isoformat(),
        total_points=total_points,
        passing_threshold=0.7,
    )

    # Build complete exercise set
    exercise_set = metadata.to_dict()
    exercise_set["exercises"] = [ex.to_dict() for ex in exercises]

    # Write to file
    exercise_set_path = exercises_dir / f"{exercise_set_id}.json"
    with open(exercise_set_path, "w", encoding="utf-8") as f:
        json.dump(exercise_set, f, indent=2, ensure_ascii=False)

    logger.info(
        "exercises_generated",
        exercise_set_id=exercise_set_id,
        count=len(exercises),
        total_points=total_points,
        time_ms=generation_time_ms,
        mode=mode,
    )

    return ExerciseSetResult(
        success=True,
        exercise_set_path=exercise_set_path,
        metadata=metadata,
        exercises=exercises,
        message=f"Ejercicios generados: {exercise_set_path.name}",
        warnings=warnings,
    )
