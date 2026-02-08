"""Exam attempt repository module.

Responsibilities (F6):
- Store and validate student exam attempts (answers to exam questions)
- Persist attempts to artifacts/exam_attempts/
- Load exam sets and attempts from filesystem

Output structure (JSON):
- exam_attempt_v1 schema with answers array
- Deterministic IDs: {exam_set_id}-a{NN}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ExamAnswer:
    """A single answer to an exam question."""

    question_id: str
    response: str | int | bool | None
    time_taken_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "question_id": self.question_id,
            "response": self.response,
        }
        if self.time_taken_seconds is not None:
            result["time_taken_seconds"] = self.time_taken_seconds
        return result


@dataclass
class ExamAttempt:
    """A student attempt at a chapter exam."""

    exam_attempt_id: str
    exam_set_id: str
    book_id: str
    chapter_id: str
    answers: list[ExamAnswer]
    created_at: str
    status: Literal["submitted", "graded"] = "submitted"

    @property
    def total_questions(self) -> int:
        """Number of questions answered."""
        return len(self.answers)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": "exam_attempt_v1",
            "exam_attempt_id": self.exam_attempt_id,
            "exam_set_id": self.exam_set_id,
            "book_id": self.book_id,
            "chapter_id": self.chapter_id,
            "created_at": self.created_at,
            "status": self.status,
            "answers": [a.to_dict() for a in self.answers],
            "total_questions": self.total_questions,
        }


@dataclass
class ExamAttemptResult:
    """Result of exam attempt submission."""

    success: bool
    attempt_path: Path | None
    attempt: ExamAttempt | None
    message: str
    warnings: list[str] = field(default_factory=list)


class ExamAttemptValidationError(Exception):
    """Error validating exam attempt."""

    pass


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _extract_book_id_from_exam_set_id(exam_set_id: str) -> str | None:
    """Extract book_id from exam_set_id.

    Format: {book_id}-ch{NN}-exam{XX}
    """
    # Remove -exam{XX} suffix
    match = re.match(r"(.+)-ch\d{2}-exam\d{2}$", exam_set_id)
    if not match:
        return None

    # Extract book_id (everything before -ch{NN})
    prefix = match.group(0)
    book_match = re.match(r"(.+)-ch\d{2}-exam\d{2}$", prefix)
    if book_match:
        full_prefix = book_match.group(1)
        # Remove the -chNN part to get just book_id
        book_id_match = re.match(r"(.+)-ch\d{2}$", full_prefix + "-ch00")
        if not book_id_match:
            # Fallback: split on -ch
            parts = full_prefix.rsplit("-ch", 1)
            if parts:
                return parts[0]
        return full_prefix.rsplit("-ch", 1)[0] if "-ch" in full_prefix else full_prefix

    return None


def _extract_chapter_id_from_exam_set_id(exam_set_id: str, book_id: str) -> str | None:
    """Extract chapter_id from exam_set_id.

    Format: {book_id}-ch{NN}-exam{XX}
    Returns: {book_id}:ch:{N}
    """
    match = re.search(r"-ch(\d{2})-exam\d{2}$", exam_set_id)
    if match:
        chapter_num = int(match.group(1))
        return f"{book_id}:ch:{chapter_num}"
    return None


def _generate_exam_attempt_id(exam_set_id: str, attempts_dir: Path) -> str:
    """Generate deterministic exam_attempt_id.

    Counts existing attempts for this exam set and increments.
    Format: {exam_set_id}-a{NN}
    """
    existing = list(attempts_dir.glob(f"{exam_set_id}-a*.json"))
    next_num = len(existing) + 1
    return f"{exam_set_id}-a{next_num:02d}"


# =============================================================================
# LOAD FUNCTIONS
# =============================================================================


def load_exam_set(
    exam_set_id: str,
    data_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Load exam set from filesystem.

    Args:
        exam_set_id: Exam set identifier
        data_dir: Base data directory

    Returns:
        Exam set dict or None if not found
    """
    if data_dir is None:
        data_dir = Path("data")

    book_id = _extract_book_id_from_exam_set_id(exam_set_id)
    if not book_id:
        return None

    exam_set_path = (
        data_dir / "books" / book_id / "artifacts" / "exams" / f"{exam_set_id}.json"
    )

    if not exam_set_path.exists():
        return None

    try:
        with open(exam_set_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_exam_attempt(
    exam_attempt_id: str,
    data_dir: Path | None = None,
) -> ExamAttempt | None:
    """Load exam attempt from filesystem.

    Args:
        exam_attempt_id: Exam attempt identifier
        data_dir: Base data directory

    Returns:
        ExamAttempt object or None if not found
    """
    if data_dir is None:
        data_dir = Path("data")

    # Extract exam_set_id from exam_attempt_id
    # Format: {exam_set_id}-a{NN}
    match = re.match(r"(.+)-a\d{2}$", exam_attempt_id)
    if not match:
        return None

    exam_set_id = match.group(1)
    book_id = _extract_book_id_from_exam_set_id(exam_set_id)
    if not book_id:
        return None

    attempt_path = (
        data_dir / "books" / book_id / "artifacts" / "exam_attempts" / f"{exam_attempt_id}.json"
    )

    if not attempt_path.exists():
        return None

    try:
        with open(attempt_path, encoding="utf-8") as f:
            data = json.load(f)

        answers = [
            ExamAnswer(
                question_id=a["question_id"],
                response=a.get("response", a.get("answer")),
                time_taken_seconds=a.get("time_taken_seconds"),
            )
            for a in data.get("answers", [])
        ]

        return ExamAttempt(
            exam_attempt_id=data["exam_attempt_id"],
            exam_set_id=data["exam_set_id"],
            book_id=data["book_id"],
            chapter_id=data["chapter_id"],
            answers=answers,
            created_at=data["created_at"],
            status=data.get("status", "submitted"),
        )
    except (json.JSONDecodeError, OSError, KeyError):
        return None


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def submit_exam_attempt(
    exam_set_id: str,
    answers_path: Path,
    data_dir: Path | None = None,
) -> ExamAttemptResult:
    """Submit and validate an exam attempt.

    Args:
        exam_set_id: Exam set identifier
        answers_path: Path to answers JSON file
        data_dir: Base data directory

    Returns:
        ExamAttemptResult with attempt path and data
    """
    if data_dir is None:
        data_dir = Path("data")

    warnings: list[str] = []

    # Extract book_id and chapter_id
    book_id = _extract_book_id_from_exam_set_id(exam_set_id)
    if not book_id:
        return ExamAttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message=f"Formato de exam_set_id inválido: {exam_set_id}",
        )

    chapter_id = _extract_chapter_id_from_exam_set_id(exam_set_id, book_id)
    if not chapter_id:
        return ExamAttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message=f"No se pudo extraer chapter_id de: {exam_set_id}",
        )

    # Load exam set
    exam_set = load_exam_set(exam_set_id, data_dir)
    if exam_set is None:
        return ExamAttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message=f"Examen no encontrado: {exam_set_id}",
        )

    # Load answers file
    if not answers_path.exists():
        return ExamAttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message=f"Archivo de respuestas no encontrado: {answers_path}",
        )

    try:
        with open(answers_path, encoding="utf-8") as f:
            answers_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return ExamAttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message=f"Error leyendo archivo de respuestas: {e}",
        )

    # Validate answers
    raw_answers = answers_data.get("answers", [])
    if not raw_answers:
        return ExamAttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message="El archivo de respuestas no contiene respuestas",
        )

    # Get valid question IDs
    valid_question_ids = {q["question_id"] for q in exam_set.get("questions", [])}

    # Validate each answer
    validated_answers: list[ExamAnswer] = []
    for ans in raw_answers:
        question_id = ans.get("question_id", "")
        if question_id not in valid_question_ids:
            return ExamAttemptResult(
                success=False,
                attempt_path=None,
                attempt=None,
                message=f"Question ID no encontrado en el examen: {question_id}",
            )

        validated_answers.append(
            ExamAnswer(
                question_id=question_id,
                response=ans.get("response"),
                time_taken_seconds=ans.get("time_taken_seconds"),
            )
        )

    # Setup output directory
    attempts_dir = data_dir / "books" / book_id / "artifacts" / "exam_attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)

    # Generate exam_attempt_id
    exam_attempt_id = _generate_exam_attempt_id(exam_set_id, attempts_dir)

    # Create attempt
    attempt = ExamAttempt(
        exam_attempt_id=exam_attempt_id,
        exam_set_id=exam_set_id,
        book_id=book_id,
        chapter_id=chapter_id,
        answers=validated_answers,
        created_at=datetime.now(timezone.utc).isoformat(),
        status="submitted",
    )

    # Write to file
    attempt_path = attempts_dir / f"{exam_attempt_id}.json"
    with open(attempt_path, "w", encoding="utf-8") as f:
        json.dump(attempt.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info(
        "exam_attempt_submitted",
        exam_attempt_id=exam_attempt_id,
        exam_set_id=exam_set_id,
        answers_count=len(validated_answers),
    )

    return ExamAttemptResult(
        success=True,
        attempt_path=attempt_path,
        attempt=attempt,
        message=f"Intento guardado: {attempt_path.name}",
        warnings=warnings,
    )
