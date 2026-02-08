"""Tests for attempt repository module."""

import json
from pathlib import Path

import pytest

from teaching.core.attempt_repository import (
    Answer,
    Attempt,
    AttemptResult,
    AttemptValidationError,
    load_attempt,
    load_exercise_set,
    submit_attempt,
)


class TestSubmitAttempt:
    """Tests for attempt submission."""

    def test_submit_validates_and_persists_attempt(
        self, sample_book_with_notes, sample_exercise_set, sample_answers_file
    ):
        """Submit validates exercise_ids and persists attempt."""
        exercise_set_id = sample_exercise_set["exercise_set_id"]

        result = submit_attempt(
            exercise_set_id=exercise_set_id,
            answers_path=sample_answers_file,
            data_dir=sample_book_with_notes,
        )

        assert result.success is True
        assert result.attempt_path is not None
        assert result.attempt_path.exists()
        assert "artifacts/attempts" in str(result.attempt_path)

        # Verify JSON structure
        with open(result.attempt_path) as f:
            data = json.load(f)

        assert data["$schema"] == "attempt_v1"
        assert data["exercise_set_id"] == exercise_set_id
        assert data["status"] == "pending"
        assert len(data["answers"]) > 0

    def test_submit_rejects_invalid_exercise_ids(
        self, sample_book_with_notes, sample_exercise_set, tmp_path
    ):
        """Rejects answers with invalid exercise_ids."""
        exercise_set_id = sample_exercise_set["exercise_set_id"]

        # Create answers with invalid exercise_id
        invalid_answers = {
            "answers": [
                {
                    "exercise_id": "invalid-exercise-id",
                    "response": 0,
                }
            ]
        }
        answers_path = tmp_path / "invalid_answers.json"
        answers_path.write_text(json.dumps(invalid_answers))

        result = submit_attempt(
            exercise_set_id=exercise_set_id,
            answers_path=answers_path,
            data_dir=sample_book_with_notes,
        )

        assert result.success is False
        assert "no encontrad" in result.message.lower() or "not found" in result.message.lower()

    def test_attempt_id_is_deterministic(
        self, sample_book_with_notes, sample_exercise_set, sample_answers_file
    ):
        """Attempt IDs follow pattern {exercise_set_id}-a{NN}."""
        exercise_set_id = sample_exercise_set["exercise_set_id"]

        # First submission
        result1 = submit_attempt(
            exercise_set_id=exercise_set_id,
            answers_path=sample_answers_file,
            data_dir=sample_book_with_notes,
        )

        assert result1.success is True
        assert result1.attempt.attempt_id == f"{exercise_set_id}-a01"

        # Second submission
        result2 = submit_attempt(
            exercise_set_id=exercise_set_id,
            answers_path=sample_answers_file,
            data_dir=sample_book_with_notes,
        )

        assert result2.success is True
        assert result2.attempt.attempt_id == f"{exercise_set_id}-a02"

    def test_submit_exercise_set_not_found(self, sample_book_with_notes, sample_answers_file):
        """Returns error when exercise set doesn't exist."""
        # Use a valid format but nonexistent exercise set
        result = submit_attempt(
            exercise_set_id="test-book-ch01-u01-ex99",
            answers_path=sample_answers_file,
            data_dir=sample_book_with_notes,
        )

        assert result.success is False
        assert "no encontrad" in result.message.lower()

    def test_submit_answers_file_not_found(self, sample_book_with_notes, sample_exercise_set):
        """Returns error when answers file doesn't exist."""
        result = submit_attempt(
            exercise_set_id=sample_exercise_set["exercise_set_id"],
            answers_path=Path("/nonexistent/answers.json"),
            data_dir=sample_book_with_notes,
        )

        assert result.success is False
        assert "no encontr" in result.message.lower() or "not found" in result.message.lower()

    def test_submit_partial_answers(
        self, sample_book_with_notes, sample_exercise_set, tmp_path
    ):
        """Can submit partial answers (not all questions answered)."""
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]

        # Only answer first 2 questions
        partial_answers = {
            "answers": [
                {"exercise_id": exercises[0]["exercise_id"], "response": 0},
                {"exercise_id": exercises[1]["exercise_id"], "response": True},
            ]
        }
        answers_path = tmp_path / "partial_answers.json"
        answers_path.write_text(json.dumps(partial_answers))

        result = submit_attempt(
            exercise_set_id=exercise_set_id,
            answers_path=answers_path,
            data_dir=sample_book_with_notes,
        )

        assert result.success is True
        assert result.attempt.total_questions == 2


class TestLoadFunctions:
    """Tests for loading functions."""

    def test_load_exercise_set(self, sample_book_with_notes, sample_exercise_set):
        """Can load exercise set from filesystem."""
        exercise_set_id = sample_exercise_set["exercise_set_id"]

        loaded = load_exercise_set(exercise_set_id, sample_book_with_notes)

        assert loaded is not None
        assert loaded["exercise_set_id"] == exercise_set_id
        assert "exercises" in loaded

    def test_load_exercise_set_not_found(self, sample_book_with_notes):
        """Returns None when exercise set doesn't exist."""
        loaded = load_exercise_set("nonexistent-ex01", sample_book_with_notes)

        assert loaded is None

    def test_load_attempt(self, sample_book_with_notes, sample_attempt):
        """Can load attempt from filesystem."""
        attempt_id = sample_attempt["attempt_id"]

        loaded = load_attempt(attempt_id, sample_book_with_notes)

        assert loaded is not None
        assert loaded.attempt_id == attempt_id
        assert loaded.status == "pending"

    def test_load_attempt_not_found(self, sample_book_with_notes):
        """Returns None when attempt doesn't exist."""
        loaded = load_attempt("nonexistent-a01", sample_book_with_notes)

        assert loaded is None


class TestAttemptDataClasses:
    """Tests for attempt data classes."""

    def test_answer_to_dict(self):
        """Answer.to_dict() returns correct structure."""
        answer = Answer(
            exercise_id="test-ex01-q01",
            response=0,
            time_taken_seconds=30,
        )

        d = answer.to_dict()

        assert d["exercise_id"] == "test-ex01-q01"
        assert d["response"] == 0
        assert d["time_taken_seconds"] == 30

    def test_answer_to_dict_without_time(self):
        """Answer.to_dict() handles None time."""
        answer = Answer(
            exercise_id="test-ex01-q01",
            response="text answer",
            time_taken_seconds=None,
        )

        d = answer.to_dict()

        assert d["exercise_id"] == "test-ex01-q01"
        assert d["response"] == "text answer"
        assert "time_taken_seconds" not in d or d["time_taken_seconds"] is None

    def test_attempt_to_dict(self):
        """Attempt.to_dict() returns correct schema."""
        attempt = Attempt(
            attempt_id="test-ex01-a01",
            exercise_set_id="test-ex01",
            unit_id="test-book-ch01-u01",
            book_id="test-book",
            answers=[
                Answer(exercise_id="test-ex01-q01", response=0),
                Answer(exercise_id="test-ex01-q02", response=True),
            ],
            created_at="2026-02-02T10:00:00+00:00",
            status="pending",
        )

        d = attempt.to_dict()

        assert d["$schema"] == "attempt_v1"
        assert d["attempt_id"] == "test-ex01-a01"
        assert d["exercise_set_id"] == "test-ex01"
        assert d["status"] == "pending"
        assert d["total_questions"] == 2
        assert len(d["answers"]) == 2
