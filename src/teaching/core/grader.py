"""Grading module.

Responsibilities (F5):
- Grade student attempts against exercise sets
- Auto-grade objective questions (MC, TF)
- LLM-grade subjective questions (short_answer)
- Persist grade reports to artifacts/grades/

Output structure (JSON):
- grade_report_v1 schema with results and summary
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

from teaching.core.attempt_repository import Answer, Attempt, load_attempt, load_exercise_set
from teaching.core.notes_generator import sanitize_output
from teaching.llm.client import LLMClient, LLMConfig, LLMError

logger = structlog.get_logger(__name__)

# =============================================================================
# TYPES
# =============================================================================

GradeMode = Literal["auto", "llm", "mixed"]

# =============================================================================
# PROMPTS
# =============================================================================

SYSTEM_PROMPT_GRADE = """Eres un profesor universitario experto en evaluar respuestas de estudiantes.

REGLAS ESTRICTAS:
1. SIEMPRE responde en español
2. Evalúa basándote SOLO en la respuesta esperada y la rúbrica (si aplica)
3. Responde ÚNICAMENTE en formato JSON válido
4. Sé justo pero {strict_mode}
5. Proporciona feedback constructivo y educativo

El JSON debe tener esta estructura exacta:
{{
  "is_correct": true | false | null,
  "score": 0.0 a 1.0,
  "feedback": "Retroalimentación constructiva y educativa",
  "confidence": 0.0 a 1.0
}}

Criterios de puntuación:
- 1.0: Respuesta completamente correcta y completa
- 0.75-0.99: Respuesta mayormente correcta con pequeños errores u omisiones
- 0.5-0.74: Respuesta parcialmente correcta, falta información importante
- 0.25-0.49: Respuesta con algunos elementos correctos pero mayormente incompleta
- 0.0-0.24: Respuesta incorrecta o irrelevante"""

USER_PROMPT_GRADE = """Evalúa la siguiente respuesta del estudiante:

**Pregunta:**
{question}

**Respuesta esperada:**
{correct_answer}

**Respuesta del estudiante:**
{student_response}

Evalúa y proporciona el JSON con la calificación."""

# Fallback prompt
SYSTEM_PROMPT_GRADE_TEXT = """Eres un profesor experto en evaluar respuestas.

REGLAS:
1. Responde en español
2. Evalúa basándote en la respuesta esperada
3. Responde en JSON válido

JSON: {{"is_correct": bool, "score": 0.0-1.0, "feedback": "...", "confidence": 0.0-1.0}}"""


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ExerciseGrade:
    """Grade for a single exercise."""

    exercise_id: str
    is_correct: bool | None
    score: float
    feedback: str
    expected_answer: str
    given_answer: str | None = None  # Student's answer (for debugging)
    correct_option_text: str | None = None  # MCQ: text of correct option
    grading_path: Literal["auto", "llm"] = "auto"  # How it was graded
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "exercise_id": self.exercise_id,
            "is_correct": self.is_correct,
            "score": self.score,
            "feedback": self.feedback,
            "expected_answer": self.expected_answer,
        }
        if self.given_answer is not None:
            result["given_answer"] = self.given_answer
        if self.correct_option_text is not None:
            result["correct_option_text"] = self.correct_option_text
        result["grading_path"] = self.grading_path
        if self.confidence is not None:
            result["confidence"] = self.confidence
        return result


@dataclass
class GradeSummary:
    """Summary of grading results."""

    total_questions: int
    correct_count: int
    total_score: float
    max_score: float
    percentage: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_questions": self.total_questions,
            "correct_count": self.correct_count,
            "total_score": self.total_score,
            "max_score": self.max_score,
            "percentage": self.percentage,
            "passed": self.passed,
        }


@dataclass
class GradeReport:
    """Complete grading report for an attempt."""

    attempt_id: str
    exercise_set_id: str
    unit_id: str
    book_id: str
    graded_at: str
    provider: str
    model: str
    mode: GradeMode
    strict: bool
    grading_time_ms: int
    results: list[ExerciseGrade]
    summary: GradeSummary

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": "grade_report_v1",
            "attempt_id": self.attempt_id,
            "exercise_set_id": self.exercise_set_id,
            "unit_id": self.unit_id,
            "book_id": self.book_id,
            "graded_at": self.graded_at,
            "provider": self.provider,
            "model": self.model,
            "mode": self.mode,
            "strict": self.strict,
            "grading_time_ms": self.grading_time_ms,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary.to_dict(),
        }


@dataclass
class GradeResult:
    """Result of grading operation."""

    success: bool
    grade_path: Path | None
    report: GradeReport | None
    message: str
    warnings: list[str] = field(default_factory=list)


class GradingError(Exception):
    """Error during grading."""

    pass


# =============================================================================
# GRADING FUNCTIONS
# =============================================================================


def _normalize_mcq_response(response: Any) -> int | None:
    """Normalize MCQ response to int index or None if invalid/empty.

    Args:
        response: Student's raw response (int, str, or None)

    Returns:
        Integer index or None if response is empty/invalid
    """
    if response is None:
        return None
    if isinstance(response, int):
        return response
    if isinstance(response, str):
        stripped = response.strip().lower()
        if stripped == "" or stripped in ("null", "none"):
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _normalize_tf_response(response: Any) -> bool | None:
    """Normalize TF response to bool or None if invalid/empty.

    Args:
        response: Student's raw response (bool, str, int, or None)

    Returns:
        Boolean or None if response is empty/invalid
    """
    if response is None:
        return None
    if isinstance(response, bool):
        return response
    if isinstance(response, str):
        stripped = response.strip().lower()
        if stripped == "" or stripped in ("null", "none"):
            return None
        if stripped in ("true", "verdadero", "sí", "si", "1", "yes"):
            return True
        if stripped in ("false", "falso", "no", "0"):
            return False
        return None
    if isinstance(response, int):
        return response != 0
    return None


def _auto_grade(
    exercise: dict[str, Any],
    answer: Answer,
) -> ExerciseGrade:
    """Auto-grade objective exercises (MC, TF).

    Uses deterministic comparison - NO LLM involved.
    Handles null/empty responses gracefully.

    Args:
        exercise: Exercise dict from exercise set
        answer: Student answer

    Returns:
        ExerciseGrade with score and feedback
    """
    correct_answer = exercise.get("correct_answer")
    student_response = answer.response
    exercise_type = exercise.get("type", "")
    options = exercise.get("options", [])
    explanation = exercise.get("explanation", "")

    is_correct = False
    given_answer_str: str | None = None
    correct_option_text: str | None = None

    if exercise_type == "multiple_choice":
        # Normalize both values using helper
        student_int = _normalize_mcq_response(student_response)
        correct_int = _normalize_mcq_response(correct_answer)

        # Build given_answer string
        if student_int is not None:
            if options and 0 <= student_int < len(options):
                given_answer_str = f"{student_int}: {options[student_int]}"
            else:
                given_answer_str = str(student_int)
        else:
            given_answer_str = "(sin respuesta)"

        # Build correct_option_text
        if correct_int is not None and options and 0 <= correct_int < len(options):
            correct_option_text = options[correct_int]

        # Compare - only if both are valid
        if student_int is not None and correct_int is not None:
            is_correct = student_int == correct_int
        else:
            is_correct = False

    elif exercise_type == "true_false":
        # Normalize both values using helper
        student_bool = _normalize_tf_response(student_response)
        correct_bool = _normalize_tf_response(correct_answer)

        # Build given_answer string
        if student_bool is not None:
            given_answer_str = "Verdadero" if student_bool else "Falso"
        else:
            given_answer_str = "(sin respuesta)"

        # Compare - only if both are valid
        if student_bool is not None and correct_bool is not None:
            is_correct = student_bool == correct_bool
        else:
            is_correct = False

    score = 1.0 if is_correct else 0.0

    # Build feedback
    if is_correct:
        feedback = f"¡Correcto! {explanation}"
    else:
        if exercise_type == "multiple_choice":
            correct_int = _normalize_mcq_response(correct_answer)
            if correct_option_text and correct_int is not None:
                feedback = f"Incorrecto. La respuesta correcta es ({correct_int}): {correct_option_text}. {explanation}"
            else:
                feedback = f"Incorrecto. {explanation}"
        elif exercise_type == "true_false":
            correct_bool = _normalize_tf_response(correct_answer)
            if correct_bool is not None:
                correct_str = "Verdadero" if correct_bool else "Falso"
                feedback = f"Incorrecto. La respuesta correcta es: {correct_str}. {explanation}"
            else:
                feedback = f"Incorrecto. {explanation}"
        else:
            feedback = f"Incorrecto. {explanation}"

    # Build expected_answer string (includes index AND text for MCQ)
    if exercise_type == "multiple_choice":
        correct_int = _normalize_mcq_response(correct_answer)
        if correct_int is not None and correct_option_text:
            expected_answer_str = f"{correct_int}: {correct_option_text}"
        else:
            expected_answer_str = str(correct_answer)
    elif exercise_type == "true_false":
        correct_bool = _normalize_tf_response(correct_answer)
        if correct_bool is not None:
            expected_answer_str = "Verdadero" if correct_bool else "Falso"
        else:
            expected_answer_str = str(correct_answer)
    else:
        expected_answer_str = str(correct_answer)

    return ExerciseGrade(
        exercise_id=answer.exercise_id,
        is_correct=is_correct,
        score=score,
        feedback=feedback,
        expected_answer=expected_answer_str,
        given_answer=given_answer_str,
        correct_option_text=correct_option_text,
        grading_path="auto",
        confidence=None,  # Auto-grading has no confidence
    )


def _llm_grade(
    client: LLMClient,
    exercise: dict[str, Any],
    answer: Answer,
    strict: bool,
) -> ExerciseGrade:
    """LLM-grade subjective exercises (short_answer).

    Handles empty/null responses without calling LLM (returns 0 directly).

    Args:
        client: LLM client
        exercise: Exercise dict from exercise set
        answer: Student answer
        strict: Whether to use strict grading

    Returns:
        ExerciseGrade with score and feedback
    """
    question = exercise.get("question", "")
    correct_answer = exercise.get("correct_answer", "")

    # Normalize response: None or empty string = no response
    raw_response = answer.response
    if raw_response is None:
        student_response = ""
        given_answer_str = "(sin respuesta)"
    elif isinstance(raw_response, str):
        student_response = raw_response.strip()
        given_answer_str = student_response if student_response else "(sin respuesta)"
    else:
        student_response = str(raw_response)
        given_answer_str = student_response

    # If response is empty, return incorrect directly (no LLM call needed)
    if not student_response:
        return ExerciseGrade(
            exercise_id=answer.exercise_id,
            is_correct=False,
            score=0.0,
            feedback="No se proporcionó una respuesta.",
            expected_answer=str(correct_answer),
            given_answer=given_answer_str,
            correct_option_text=None,
            grading_path="auto",  # Empty responses are auto-graded
            confidence=1.0,
        )

    strict_mode = "estricto (solo respuestas completas y precisas)" if strict else "flexible (acepta respuestas parcialmente correctas)"

    system_prompt = SYSTEM_PROMPT_GRADE.format(strict_mode=strict_mode)
    user_prompt = USER_PROMPT_GRADE.format(
        question=question,
        correct_answer=correct_answer,
        student_response=student_response,
    )

    try:
        # Try JSON mode first
        result = client.simple_json(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.3,
        )
    except LLMError:
        # Fallback to text + parse
        try:
            text_response = client.simple_chat(
                system_prompt=SYSTEM_PROMPT_GRADE_TEXT,
                user_message=user_prompt,
                temperature=0.3,
            )
            text_response = sanitize_output(text_response)

            try:
                result = json.loads(text_response)
            except json.JSONDecodeError:
                json_match = re.search(r"\{[\s\S]*\}", text_response)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    raise LLMError("No se pudo extraer JSON de la respuesta")

        except (LLMError, json.JSONDecodeError) as e:
            logger.error("llm_grading_failed", error=str(e))
            # Return a neutral grade on error
            return ExerciseGrade(
                exercise_id=answer.exercise_id,
                is_correct=None,
                score=0.5,  # Neutral score
                feedback="Error al evaluar la respuesta. Se requiere revisión manual.",
                expected_answer=str(correct_answer),
                given_answer=given_answer_str,
                correct_option_text=None,
                grading_path="llm",
                confidence=0.0,
            )

    # Parse result
    is_correct = result.get("is_correct")
    score = float(result.get("score", 0.5))
    feedback = result.get("feedback", "")
    confidence = result.get("confidence")

    # Clamp score to 0-1
    score = max(0.0, min(1.0, score))
    if confidence is not None:
        confidence = max(0.0, min(1.0, float(confidence)))

    # Binarize score in strict mode (short_answer only)
    # Threshold: >= 0.95 = full credit, otherwise 0
    if strict:
        score = 1.0 if score >= 0.95 else 0.0
        is_correct = score == 1.0

    return ExerciseGrade(
        exercise_id=answer.exercise_id,
        is_correct=is_correct,
        score=score,
        feedback=feedback,
        expected_answer=str(correct_answer),
        given_answer=given_answer_str,
        correct_option_text=None,
        grading_path="llm",
        confidence=confidence,
    )


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def grade_attempt(
    attempt_id: str,
    data_dir: Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    strict: bool = False,
    client: LLMClient | None = None,
) -> GradeResult:
    """Grade an attempt.

    Args:
        attempt_id: Attempt identifier
        data_dir: Base data directory
        provider: Override LLM provider
        model: Override LLM model
        strict: Use strict grading mode
        client: Optional pre-configured LLM client (for testing)

    Returns:
        GradeResult with grade report
    """
    if data_dir is None:
        data_dir = Path("data")

    start_time = time.time()
    warnings: list[str] = []
    has_subjective = False

    # Load attempt
    attempt = load_attempt(attempt_id, data_dir)
    if attempt is None:
        return GradeResult(
            success=False,
            grade_path=None,
            report=None,
            message=f"Intento no encontrado: {attempt_id}",
        )

    # Load exercise set
    exercise_set = load_exercise_set(attempt.exercise_set_id, data_dir)
    if exercise_set is None:
        return GradeResult(
            success=False,
            grade_path=None,
            report=None,
            message=f"Set de ejercicios no encontrado: {attempt.exercise_set_id}",
        )

    # Build exercise lookup
    exercises_by_id = {ex["exercise_id"]: ex for ex in exercise_set.get("exercises", [])}

    # Inherit provider/model from exercise_set if not specified
    exercise_set_provider = exercise_set.get("provider")
    exercise_set_model = exercise_set.get("model")

    # Use exercise_set values as defaults (CLI args override if provided)
    effective_provider = provider if provider else exercise_set_provider
    effective_model = model if model else exercise_set_model

    # Check if we need LLM for subjective questions
    for answer in attempt.answers:
        exercise = exercises_by_id.get(answer.exercise_id)
        if exercise and exercise.get("type") == "short_answer":
            has_subjective = True
            break

    # Initialize LLM client if needed for subjective questions
    if has_subjective:
        if client is None:
            config = LLMConfig.from_yaml()
            client = LLMClient(
                config=config,
                provider=effective_provider,
                model=effective_model,
            )

        if not client.is_available():
            return GradeResult(
                success=False,
                grade_path=None,
                report=None,
                message=f"No se pudo conectar al LLM para evaluar respuestas abiertas ({client.config.provider})",
            )

    # Grade each answer
    results: list[ExerciseGrade] = []
    used_llm = False

    for answer in attempt.answers:
        exercise = exercises_by_id.get(answer.exercise_id)
        if exercise is None:
            # Skip unknown exercise
            warnings.append(f"Ejercicio no encontrado: {answer.exercise_id}")
            continue

        exercise_type = exercise.get("type", "")

        if exercise_type in ("multiple_choice", "true_false"):
            # Auto-grade
            grade = _auto_grade(exercise, answer)
        elif exercise_type == "short_answer":
            # LLM-grade
            grade = _llm_grade(client, exercise, answer, strict)
            used_llm = True
        else:
            # Unknown type - try auto-grade
            warnings.append(f"Tipo de ejercicio desconocido: {exercise_type}")
            grade = _auto_grade(exercise, answer)

        results.append(grade)

    # Calculate summary
    total_questions = len(results)
    correct_count = sum(1 for r in results if r.is_correct is True)
    total_score = sum(r.score * exercises_by_id.get(r.exercise_id, {}).get("points", 1) for r in results)
    max_score = sum(exercises_by_id.get(r.exercise_id, {}).get("points", 1) for r in results)
    percentage = total_score / max_score if max_score > 0 else 0.0
    passing_threshold = exercise_set.get("passing_threshold", 0.7)
    passed = percentage >= passing_threshold

    summary = GradeSummary(
        total_questions=total_questions,
        correct_count=correct_count,
        total_score=total_score,
        max_score=max_score,
        percentage=percentage,
        passed=passed,
    )

    # Determine grading mode
    if used_llm and correct_count < total_questions:
        mode: GradeMode = "mixed"
    elif used_llm:
        mode = "llm"
    else:
        mode = "auto"

    # Calculate timing
    grading_time_ms = int((time.time() - start_time) * 1000)

    # Get provider info - use effective values (inherited or from client)
    if client:
        provider_name = client.config.provider
        model_name = client.config.model
    else:
        # For pure auto-grading mode, use effective values (inherited from exercise_set)
        provider_name = effective_provider or "auto"
        model_name = effective_model or "auto"

    # Create report
    report = GradeReport(
        attempt_id=attempt_id,
        exercise_set_id=attempt.exercise_set_id,
        unit_id=attempt.unit_id,
        book_id=attempt.book_id,
        graded_at=datetime.now(timezone.utc).isoformat(),
        provider=provider_name,
        model=model_name,
        mode=mode,
        strict=strict,
        grading_time_ms=grading_time_ms,
        results=results,
        summary=summary,
    )

    # Setup output directory
    grades_dir = data_dir / "books" / attempt.book_id / "artifacts" / "grades"
    grades_dir.mkdir(parents=True, exist_ok=True)

    # Write grade report
    grade_path = grades_dir / f"{attempt_id}.json"
    with open(grade_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    # Update attempt status
    attempt_path = data_dir / "books" / attempt.book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
    if attempt_path.exists():
        try:
            with open(attempt_path, encoding="utf-8") as f:
                attempt_data = json.load(f)
            attempt_data["status"] = "graded"
            with open(attempt_path, "w", encoding="utf-8") as f:
                json.dump(attempt_data, f, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, OSError) as e:
            warnings.append(f"No se pudo actualizar status del intento: {e}")

    logger.info(
        "attempt_graded",
        attempt_id=attempt_id,
        score=f"{percentage:.1%}",
        passed=passed,
        mode=mode,
        time_ms=grading_time_ms,
    )

    return GradeResult(
        success=True,
        grade_path=grade_path,
        report=report,
        message=f"Calificación: {percentage:.1%} - {'Aprobado' if passed else 'No aprobado'}",
        warnings=warnings,
    )
