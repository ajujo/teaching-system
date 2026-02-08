"""Attempt repository module.

Responsibilities (F5):
- Store and validate student attempts (answers to exercises)
- Persist attempts to artifacts/attempts/
- Load attempts and exercise sets from filesystem

Output structure (JSON):
- attempt_v1 schema with answers array
- Deterministic IDs: {exercise_set_id}-a{NN}
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
class Answer:
    """A single answer to an exercise."""

    exercise_id: str
    response: str | int | bool
    time_taken_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "exercise_id": self.exercise_id,
            "response": self.response,
        }
        if self.time_taken_seconds is not None:
            result["time_taken_seconds"] = self.time_taken_seconds
        return result


@dataclass
class Attempt:
    """A student attempt at an exercise set."""

    attempt_id: str
    exercise_set_id: str
    unit_id: str
    book_id: str
    answers: list[Answer]
    created_at: str
    status: Literal["pending", "graded"] = "pending"

    @property
    def total_questions(self) -> int:
        """Number of questions answered."""
        return len(self.answers)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": "attempt_v1",
            "attempt_id": self.attempt_id,
            "exercise_set_id": self.exercise_set_id,
            "unit_id": self.unit_id,
            "book_id": self.book_id,
            "created_at": self.created_at,
            "status": self.status,
            "answers": [a.to_dict() for a in self.answers],
            "total_questions": self.total_questions,
        }


@dataclass
class AttemptResult:
    """Result of attempt submission."""

    success: bool
    attempt_path: Path | None
    attempt: Attempt | None
    message: str
    warnings: list[str] = field(default_factory=list)


class AttemptValidationError(Exception):
    """Error validating attempt."""

    pass


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _extract_book_id_from_exercise_set_id(exercise_set_id: str) -> str | None:
    """Extract book_id from exercise_set_id.

    Format: {book_id}-ch{XX}-u{YY}-ex{NN}
    """
    # Remove -ex{NN} suffix
    match = re.match(r"(.+)-ex\d{2}$", exercise_set_id)
    if not match:
        return None

    unit_id = match.group(1)

    # Extract book_id from unit_id
    match2 = re.match(r"(.+)-ch\d{2}-u\d{2}$", unit_id)
    if not match2:
        return None

    return match2.group(1)


def _extract_unit_id_from_exercise_set_id(exercise_set_id: str) -> str | None:
    """Extract unit_id from exercise_set_id.

    Format: {book_id}-ch{XX}-u{YY}-ex{NN}
    """
    match = re.match(r"(.+)-ex\d{2}$", exercise_set_id)
    if match:
        return match.group(1)
    return None


def _generate_attempt_id(exercise_set_id: str, attempts_dir: Path) -> str:
    """Generate deterministic attempt_id.

    Counts existing attempts for this exercise set and increments.
    Format: {exercise_set_id}-a{NN}
    """
    existing = list(attempts_dir.glob(f"{exercise_set_id}-a*.json"))
    next_num = len(existing) + 1
    return f"{exercise_set_id}-a{next_num:02d}"


# =============================================================================
# LOAD FUNCTIONS
# =============================================================================


def load_exercise_set(
    exercise_set_id: str,
    data_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Load exercise set from filesystem.

    Args:
        exercise_set_id: Exercise set identifier
        data_dir: Base data directory

    Returns:
        Exercise set dict or None if not found
    """
    if data_dir is None:
        data_dir = Path("data")

    book_id = _extract_book_id_from_exercise_set_id(exercise_set_id)
    if not book_id:
        return None

    exercise_set_path = (
        data_dir / "books" / book_id / "artifacts" / "exercises" / f"{exercise_set_id}.json"
    )

    if not exercise_set_path.exists():
        return None

    try:
        with open(exercise_set_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_attempt(
    attempt_id: str,
    data_dir: Path | None = None,
) -> Attempt | None:
    """Load attempt from filesystem.

    Args:
        attempt_id: Attempt identifier
        data_dir: Base data directory

    Returns:
        Attempt object or None if not found
    """
    if data_dir is None:
        data_dir = Path("data")

    # Extract exercise_set_id from attempt_id
    # Format: {exercise_set_id}-a{NN}
    match = re.match(r"(.+)-a\d{2}$", attempt_id)
    if not match:
        return None

    exercise_set_id = match.group(1)
    book_id = _extract_book_id_from_exercise_set_id(exercise_set_id)
    if not book_id:
        return None

    attempt_path = (
        data_dir / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
    )

    if not attempt_path.exists():
        return None

    try:
        with open(attempt_path, encoding="utf-8") as f:
            data = json.load(f)

        answers = [
            Answer(
                exercise_id=a["exercise_id"],
                # Support both "response" (current) and "answer" (legacy) fields
                response=a.get("response", a.get("answer")),
                time_taken_seconds=a.get("time_taken_seconds"),
            )
            for a in data.get("answers", [])
        ]

        return Attempt(
            attempt_id=data["attempt_id"],
            exercise_set_id=data["exercise_set_id"],
            unit_id=data["unit_id"],
            book_id=data["book_id"],
            answers=answers,
            created_at=data["created_at"],
            status=data.get("status", "pending"),
        )
    except (json.JSONDecodeError, OSError, KeyError):
        return None


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def submit_attempt(
    exercise_set_id: str,
    answers_path: Path,
    data_dir: Path | None = None,
) -> AttemptResult:
    """Submit and validate an attempt.

    Args:
        exercise_set_id: Exercise set identifier
        answers_path: Path to answers JSON file
        data_dir: Base data directory

    Returns:
        AttemptResult with attempt path and data
    """
    if data_dir is None:
        data_dir = Path("data")

    warnings: list[str] = []

    # Extract book_id and unit_id
    book_id = _extract_book_id_from_exercise_set_id(exercise_set_id)
    unit_id = _extract_unit_id_from_exercise_set_id(exercise_set_id)

    if not book_id or not unit_id:
        return AttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message=f"Formato de exercise_set_id inválido: {exercise_set_id}",
        )

    # Load exercise set
    exercise_set = load_exercise_set(exercise_set_id, data_dir)
    if exercise_set is None:
        return AttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message=f"Set de ejercicios no encontrado: {exercise_set_id}",
        )

    # Load answers file
    if not answers_path.exists():
        return AttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message=f"Archivo de respuestas no encontrado: {answers_path}",
        )

    try:
        with open(answers_path, encoding="utf-8") as f:
            answers_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return AttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message=f"Error leyendo archivo de respuestas: {e}",
        )

    # Validate answers
    raw_answers = answers_data.get("answers", [])
    if not raw_answers:
        return AttemptResult(
            success=False,
            attempt_path=None,
            attempt=None,
            message="El archivo de respuestas no contiene respuestas",
        )

    # Get valid exercise IDs
    valid_exercise_ids = {ex["exercise_id"] for ex in exercise_set.get("exercises", [])}

    # Validate each answer
    validated_answers: list[Answer] = []
    for ans in raw_answers:
        exercise_id = ans.get("exercise_id", "")
        if exercise_id not in valid_exercise_ids:
            return AttemptResult(
                success=False,
                attempt_path=None,
                attempt=None,
                message=f"Exercise ID no encontrado en el set: {exercise_id}",
            )

        validated_answers.append(
            Answer(
                exercise_id=exercise_id,
                response=ans.get("response"),
                time_taken_seconds=ans.get("time_taken_seconds"),
            )
        )

    # Setup output directory
    attempts_dir = data_dir / "books" / book_id / "artifacts" / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)

    # Generate attempt_id
    attempt_id = _generate_attempt_id(exercise_set_id, attempts_dir)

    # Create attempt
    attempt = Attempt(
        attempt_id=attempt_id,
        exercise_set_id=exercise_set_id,
        unit_id=unit_id,
        book_id=book_id,
        answers=validated_answers,
        created_at=datetime.now(timezone.utc).isoformat(),
        status="pending",
    )

    # Write to file
    attempt_path = attempts_dir / f"{attempt_id}.json"
    with open(attempt_path, "w", encoding="utf-8") as f:
        json.dump(attempt.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info(
        "attempt_submitted",
        attempt_id=attempt_id,
        exercise_set_id=exercise_set_id,
        answers_count=len(validated_answers),
    )

    return AttemptResult(
        success=True,
        attempt_path=attempt_path,
        attempt=attempt,
        message=f"Intento guardado: {attempt_path.name}",
        warnings=warnings,
    )
