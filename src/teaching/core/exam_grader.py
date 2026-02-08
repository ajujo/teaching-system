"""Exam grading module.

Responsibilities (F6):
- Grade student exam attempts against chapter exam sets
- Auto-grade objective questions (MC, TF)
- LLM-grade subjective questions (short_answer)
- Persist grade reports to artifacts/exam_grades/
- Default to strict mode for exams (60% passing threshold)

Output structure (JSON):
- exam_grade_report_v1 schema with results and summary
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

from teaching.core.exam_attempt_repository import ExamAnswer, ExamAttempt, load_exam_attempt, load_exam_set
from teaching.core.grader import _normalize_mcq_response, _normalize_tf_response
from teaching.core.notes_generator import sanitize_output
from teaching.llm.client import LLMClient, LLMConfig, LLMError

logger = structlog.get_logger(__name__)

# =============================================================================
# TYPES
# =============================================================================

GradeMode = Literal["auto", "llm", "mixed"]

# =============================================================================
# PROMPTS (reuse from F5 grader)
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
class ExamQuestionGrade:
    """Grade for a single exam question."""

    question_id: str
    is_correct: bool | None
    score: float
    feedback: str
    expected_answer: str
    given_answer: str | None = None
    correct_option_text: str | None = None
    grading_path: Literal["auto", "llm"] = "auto"
    confidence: float | None = None
    source_unit_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "question_id": self.question_id,
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
        if self.source_unit_id is not None:
            result["source_unit_id"] = self.source_unit_id
        return result


@dataclass
class ExamGradeSummary:
    """Summary of exam grading results."""

    total_questions: int
    correct_count: int
    total_score: float
    max_score: float
    percentage: float
    passed: bool
    by_unit: dict[str, dict[str, float]] | None = None
    by_type: dict[str, dict[str, int]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "total_questions": self.total_questions,
            "correct_count": self.correct_count,
            "total_score": self.total_score,
            "max_score": self.max_score,
            "percentage": self.percentage,
            "passed": self.passed,
        }
        if self.by_unit is not None:
            result["by_unit"] = self.by_unit
        if self.by_type is not None:
            result["by_type"] = self.by_type
        return result


@dataclass
class ExamGradeReport:
    """Complete grading report for an exam attempt."""

    exam_attempt_id: str
    exam_set_id: str
    book_id: str
    chapter_id: str
    graded_at: str
    provider: str
    model: str
    mode: GradeMode
    strict: bool
    grading_time_ms: int
    results: list[ExamQuestionGrade]
    summary: ExamGradeSummary

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": "exam_grade_report_v1",
            "exam_attempt_id": self.exam_attempt_id,
            "exam_set_id": self.exam_set_id,
            "book_id": self.book_id,
            "chapter_id": self.chapter_id,
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
class ExamGradeResult:
    """Result of exam grading operation."""

    success: bool
    grade_path: Path | None
    report: ExamGradeReport | None
    message: str
    warnings: list[str] = field(default_factory=list)


class ExamGradingError(Exception):
    """Error during exam grading."""

    pass


# =============================================================================
# GRADING FUNCTIONS
# =============================================================================


def _auto_grade_exam(
    question: dict[str, Any],
    answer: ExamAnswer,
) -> ExamQuestionGrade:
    """Auto-grade objective exam questions (MC, TF).

    Uses deterministic comparison - NO LLM involved.
    """
    correct_answer = question.get("correct_answer")
    student_response = answer.response
    question_type = question.get("type", "")
    options = question.get("options", [])
    explanation = question.get("explanation", "")
    source = question.get("source", {})

    is_correct = False
    given_answer_str: str | None = None
    correct_option_text: str | None = None

    if question_type == "multiple_choice":
        student_int = _normalize_mcq_response(student_response)
        correct_int = _normalize_mcq_response(correct_answer)

        if student_int is not None:
            if options and 0 <= student_int < len(options):
                given_answer_str = f"{student_int}: {options[student_int]}"
            else:
                given_answer_str = str(student_int)
        else:
            given_answer_str = "(sin respuesta)"

        if correct_int is not None and options and 0 <= correct_int < len(options):
            correct_option_text = options[correct_int]

        if student_int is not None and correct_int is not None:
            is_correct = student_int == correct_int
        else:
            is_correct = False

    elif question_type == "true_false":
        student_bool = _normalize_tf_response(student_response)
        correct_bool = _normalize_tf_response(correct_answer)

        if student_bool is not None:
            given_answer_str = "Verdadero" if student_bool else "Falso"
        else:
            given_answer_str = "(sin respuesta)"

        if student_bool is not None and correct_bool is not None:
            is_correct = student_bool == correct_bool
        else:
            is_correct = False

    score = 1.0 if is_correct else 0.0

    # Build feedback
    if is_correct:
        feedback = f"¡Correcto! {explanation}"
    else:
        if question_type == "multiple_choice":
            correct_int = _normalize_mcq_response(correct_answer)
            if correct_option_text and correct_int is not None:
                feedback = f"Incorrecto. La respuesta correcta es ({correct_int}): {correct_option_text}. {explanation}"
            else:
                feedback = f"Incorrecto. {explanation}"
        elif question_type == "true_false":
            correct_bool = _normalize_tf_response(correct_answer)
            if correct_bool is not None:
                correct_str = "Verdadero" if correct_bool else "Falso"
                feedback = f"Incorrecto. La respuesta correcta es: {correct_str}. {explanation}"
            else:
                feedback = f"Incorrecto. {explanation}"
        else:
            feedback = f"Incorrecto. {explanation}"

    # Build expected_answer string
    if question_type == "multiple_choice":
        correct_int = _normalize_mcq_response(correct_answer)
        if correct_int is not None and correct_option_text:
            expected_answer_str = f"{correct_int}: {correct_option_text}"
        else:
            expected_answer_str = str(correct_answer)
    elif question_type == "true_false":
        correct_bool = _normalize_tf_response(correct_answer)
        if correct_bool is not None:
            expected_answer_str = "Verdadero" if correct_bool else "Falso"
        else:
            expected_answer_str = str(correct_answer)
    else:
        expected_answer_str = str(correct_answer)

    return ExamQuestionGrade(
        question_id=answer.question_id,
        is_correct=is_correct,
        score=score,
        feedback=feedback,
        expected_answer=expected_answer_str,
        given_answer=given_answer_str,
        correct_option_text=correct_option_text,
        grading_path="auto",
        confidence=None,
        source_unit_id=source.get("unit_id"),
    )


def _llm_grade_exam(
    client: LLMClient,
    question: dict[str, Any],
    answer: ExamAnswer,
    strict: bool,
) -> ExamQuestionGrade:
    """LLM-grade subjective exam questions (short_answer).

    Exams default to strict mode.
    """
    question_text = question.get("question", "")
    correct_answer = question.get("correct_answer", "")
    source = question.get("source", {})

    # Normalize response
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

    # Empty response = incorrect
    if not student_response:
        return ExamQuestionGrade(
            question_id=answer.question_id,
            is_correct=False,
            score=0.0,
            feedback="No se proporcionó una respuesta.",
            expected_answer=str(correct_answer),
            given_answer=given_answer_str,
            correct_option_text=None,
            grading_path="auto",
            confidence=1.0,
            source_unit_id=source.get("unit_id"),
        )

    strict_mode = "estricto (solo respuestas completas y precisas)" if strict else "flexible (acepta respuestas parcialmente correctas)"

    system_prompt = SYSTEM_PROMPT_GRADE.format(strict_mode=strict_mode)
    user_prompt = USER_PROMPT_GRADE.format(
        question=question_text,
        correct_answer=correct_answer,
        student_response=student_response,
    )

    try:
        result = client.simple_json(
            system_prompt=system_prompt,
            user_message=user_prompt,
            temperature=0.3,
        )
    except LLMError:
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
            logger.error("exam_llm_grading_failed", error=str(e))
            return ExamQuestionGrade(
                question_id=answer.question_id,
                is_correct=None,
                score=0.5,
                feedback="Error al evaluar la respuesta. Se requiere revisión manual.",
                expected_answer=str(correct_answer),
                given_answer=given_answer_str,
                correct_option_text=None,
                grading_path="llm",
                confidence=0.0,
                source_unit_id=source.get("unit_id"),
            )

    # Parse result
    is_correct = result.get("is_correct")
    score = float(result.get("score", 0.5))
    feedback = result.get("feedback", "")
    confidence = result.get("confidence")

    # Clamp score
    score = max(0.0, min(1.0, score))
    if confidence is not None:
        confidence = max(0.0, min(1.0, float(confidence)))

    # Binarize score in strict mode (exams default to strict)
    if strict:
        score = 1.0 if score >= 0.95 else 0.0
        is_correct = score == 1.0

    return ExamQuestionGrade(
        question_id=answer.question_id,
        is_correct=is_correct,
        score=score,
        feedback=feedback,
        expected_answer=str(correct_answer),
        given_answer=given_answer_str,
        correct_option_text=None,
        grading_path="llm",
        confidence=confidence,
        source_unit_id=source.get("unit_id"),
    )


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def grade_exam_attempt(
    exam_attempt_id: str,
    data_dir: Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    strict: bool = True,  # Exams default to strict!
    client: LLMClient | None = None,
) -> ExamGradeResult:
    """Grade an exam attempt.

    Args:
        exam_attempt_id: Exam attempt identifier
        data_dir: Base data directory
        provider: Override LLM provider
        model: Override LLM model
        strict: Use strict grading mode (default True for exams)
        client: Optional pre-configured LLM client (for testing)

    Returns:
        ExamGradeResult with grade report
    """
    if data_dir is None:
        data_dir = Path("data")

    start_time = time.time()
    warnings: list[str] = []
    has_subjective = False

    # Load attempt
    attempt = load_exam_attempt(exam_attempt_id, data_dir)
    if attempt is None:
        return ExamGradeResult(
            success=False,
            grade_path=None,
            report=None,
            message=f"Intento de examen no encontrado: {exam_attempt_id}",
        )

    # Load exam set
    exam_set = load_exam_set(attempt.exam_set_id, data_dir)
    if exam_set is None:
        return ExamGradeResult(
            success=False,
            grade_path=None,
            report=None,
            message=f"Examen no encontrado: {attempt.exam_set_id}",
        )

    # Check if exam set is valid for auto-grading
    exam_valid = exam_set.get("valid", True)
    exam_mode = exam_set.get("mode", "json")
    skip_auto_grading = not exam_valid or exam_mode == "text_fallback"

    if skip_auto_grading:
        logger.warning(
            "exam_auto_grading_skipped",
            valid=exam_valid,
            mode=exam_mode,
            exam_set_id=attempt.exam_set_id,
        )

    # Build question lookup
    questions_by_id = {q["question_id"]: q for q in exam_set.get("questions", [])}

    # Inherit provider/model from exam_set if not specified
    exam_set_provider = exam_set.get("provider")
    exam_set_model = exam_set.get("model")

    effective_provider = provider if provider else exam_set_provider
    effective_model = model if model else exam_set_model

    # Check if we need LLM for subjective questions
    for answer in attempt.answers:
        question = questions_by_id.get(answer.question_id)
        if question and question.get("type") == "short_answer":
            has_subjective = True
            break

    # Initialize LLM client if needed
    if has_subjective:
        if client is None:
            config = LLMConfig.from_yaml()
            client = LLMClient(
                config=config,
                provider=effective_provider,
                model=effective_model,
            )

        if not client.is_available():
            return ExamGradeResult(
                success=False,
                grade_path=None,
                report=None,
                message=f"No se pudo conectar al LLM para evaluar respuestas abiertas ({client.config.provider})",
            )

    # Grade each answer
    results: list[ExamQuestionGrade] = []
    used_llm = False

    # Track by_unit and by_type
    by_unit_scores: dict[str, dict[str, float]] = {}  # unit_id -> {score, max}
    by_type_counts: dict[str, dict[str, int]] = {
        "multiple_choice": {"correct": 0, "total": 0},
        "true_false": {"correct": 0, "total": 0},
        "short_answer": {"correct": 0, "total": 0},
    }

    for answer in attempt.answers:
        question = questions_by_id.get(answer.question_id)
        if question is None:
            warnings.append(f"Pregunta no encontrada: {answer.question_id}")
            continue

        question_type = question.get("type", "")
        source_unit_id = question.get("source", {}).get("unit_id", "unknown")
        points = question.get("points", 1)

        if question_type in ("multiple_choice", "true_false"):
            if skip_auto_grading:
                # Mark as needing review, don't use stored correct_answer
                grade = ExamQuestionGrade(
                    question_id=answer.question_id,
                    is_correct=None,
                    score=0.0,
                    feedback="Requiere revisión manual (exam set generado con fallback)",
                    expected_answer="N/A",
                    given_answer=str(answer.response) if answer.response is not None else "(sin respuesta)",
                    correct_option_text=None,
                    grading_path="skipped",
                    confidence=None,
                    source_unit_id=source_unit_id,
                )
            else:
                grade = _auto_grade_exam(question, answer)
        elif question_type == "short_answer":
            grade = _llm_grade_exam(client, question, answer, strict)
            used_llm = True
        else:
            warnings.append(f"Tipo de pregunta desconocido: {question_type}")
            grade = _auto_grade_exam(question, answer)

        results.append(grade)

        # Track by_unit
        if source_unit_id not in by_unit_scores:
            by_unit_scores[source_unit_id] = {"score": 0.0, "max": 0.0}
        by_unit_scores[source_unit_id]["score"] += grade.score * points
        by_unit_scores[source_unit_id]["max"] += points

        # Track by_type
        if question_type in by_type_counts:
            by_type_counts[question_type]["total"] += 1
            if grade.is_correct is True:
                by_type_counts[question_type]["correct"] += 1

    # Calculate summary
    total_questions = len(results)
    correct_count = sum(1 for r in results if r.is_correct is True)
    total_score = sum(
        r.score * questions_by_id.get(r.question_id, {}).get("points", 1)
        for r in results
    )
    max_score = sum(
        questions_by_id.get(r.question_id, {}).get("points", 1)
        for r in results
    )
    percentage = total_score / max_score if max_score > 0 else 0.0
    passing_threshold = exam_set.get("passing_threshold", 0.6)
    passed = percentage >= passing_threshold

    summary = ExamGradeSummary(
        total_questions=total_questions,
        correct_count=correct_count,
        total_score=total_score,
        max_score=max_score,
        percentage=percentage,
        passed=passed,
        by_unit=by_unit_scores,
        by_type=by_type_counts,
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

    # Get provider info
    if client:
        provider_name = client.config.provider
        model_name = client.config.model
    else:
        provider_name = effective_provider or "auto"
        model_name = effective_model or "auto"

    # Create report
    report = ExamGradeReport(
        exam_attempt_id=exam_attempt_id,
        exam_set_id=attempt.exam_set_id,
        book_id=attempt.book_id,
        chapter_id=attempt.chapter_id,
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
    grades_dir = data_dir / "books" / attempt.book_id / "artifacts" / "exam_grades"
    grades_dir.mkdir(parents=True, exist_ok=True)

    # Write grade report
    grade_path = grades_dir / f"{exam_attempt_id}.json"
    with open(grade_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    # Update attempt status
    attempt_path = data_dir / "books" / attempt.book_id / "artifacts" / "exam_attempts" / f"{exam_attempt_id}.json"
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
        "exam_attempt_graded",
        exam_attempt_id=exam_attempt_id,
        score=f"{percentage:.1%}",
        passed=passed,
        mode=mode,
        time_ms=grading_time_ms,
    )

    return ExamGradeResult(
        success=True,
        grade_path=grade_path,
        report=report,
        message=f"Calificación: {percentage:.1%} - {'Aprobado' if passed else 'No aprobado'}",
        warnings=warnings,
    )
