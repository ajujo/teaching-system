"""Tests for exam attempt repository (F6)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestLoadExamSet:
    """Tests for load_exam_set function."""

    def test_load_exam_set_returns_dict(self, sample_book_multi_unit_chapter, sample_exam_set):
        """load_exam_set returns exam set dictionary."""
        from teaching.core.exam_attempt_repository import load_exam_set

        exam_set_id = sample_exam_set["exam_set_id"]
        result = load_exam_set(exam_set_id, sample_book_multi_unit_chapter)

        assert result is not None
        assert result["exam_set_id"] == exam_set_id
        assert "$schema" in result
        assert "questions" in result

    def test_load_exam_set_not_found_returns_none(self, sample_book_multi_unit_chapter):
        """load_exam_set returns None for non-existent exam."""
        from teaching.core.exam_attempt_repository import load_exam_set

        result = load_exam_set("nonexistent-exam", sample_book_multi_unit_chapter)

        assert result is None

    def test_load_exam_set_invalid_id_returns_none(self, sample_book_multi_unit_chapter):
        """load_exam_set returns None for invalid ID format."""
        from teaching.core.exam_attempt_repository import load_exam_set

        result = load_exam_set("invalid-format", sample_book_multi_unit_chapter)

        assert result is None


class TestLoadExamAttempt:
    """Tests for load_exam_attempt function."""

    def test_load_exam_attempt_returns_object(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt
    ):
        """load_exam_attempt returns ExamAttempt object."""
        from teaching.core.exam_attempt_repository import load_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = load_exam_attempt(exam_attempt_id, sample_book_multi_unit_chapter)

        assert result is not None
        assert result.exam_attempt_id == exam_attempt_id
        assert result.exam_set_id == sample_exam_set["exam_set_id"]
        assert len(result.answers) > 0

    def test_load_exam_attempt_not_found_returns_none(self, sample_book_multi_unit_chapter):
        """load_exam_attempt returns None for non-existent attempt."""
        from teaching.core.exam_attempt_repository import load_exam_attempt

        result = load_exam_attempt("test-book-ch01-exam01-a99", sample_book_multi_unit_chapter)

        assert result is None


class TestSubmitExamAttempt:
    """Tests for submit_exam_attempt function."""

    def test_submit_creates_attempt_file(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_answers_file
    ):
        """submit_exam_attempt creates attempt file."""
        from teaching.core.exam_attempt_repository import submit_exam_attempt

        exam_set_id = sample_exam_set["exam_set_id"]
        result = submit_exam_attempt(
            exam_set_id=exam_set_id,
            answers_path=sample_exam_answers_file,
            data_dir=sample_book_multi_unit_chapter,
        )

        assert result.success
        assert result.attempt_path is not None
        assert result.attempt_path.exists()

    def test_submit_returns_exam_attempt_object(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_answers_file
    ):
        """submit_exam_attempt returns ExamAttempt object."""
        from teaching.core.exam_attempt_repository import submit_exam_attempt

        exam_set_id = sample_exam_set["exam_set_id"]
        result = submit_exam_attempt(
            exam_set_id=exam_set_id,
            answers_path=sample_exam_answers_file,
            data_dir=sample_book_multi_unit_chapter,
        )

        assert result.success
        assert result.attempt is not None
        assert result.attempt.exam_set_id == exam_set_id
        assert result.attempt.status == "submitted"

    def test_submit_generates_deterministic_id(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_answers_file
    ):
        """Attempt ID follows pattern {exam_set_id}-a{NN}."""
        from teaching.core.exam_attempt_repository import submit_exam_attempt

        exam_set_id = sample_exam_set["exam_set_id"]

        # First submission
        result1 = submit_exam_attempt(
            exam_set_id=exam_set_id,
            answers_path=sample_exam_answers_file,
            data_dir=sample_book_multi_unit_chapter,
        )

        assert result1.success
        assert result1.attempt.exam_attempt_id == f"{exam_set_id}-a01"

        # Second submission
        result2 = submit_exam_attempt(
            exam_set_id=exam_set_id,
            answers_path=sample_exam_answers_file,
            data_dir=sample_book_multi_unit_chapter,
        )

        assert result2.success
        assert result2.attempt.exam_attempt_id == f"{exam_set_id}-a02"

    def test_submit_validates_question_ids(
        self, sample_book_multi_unit_chapter, sample_exam_set, tmp_path
    ):
        """submit_exam_attempt validates question IDs exist in exam."""
        from teaching.core.exam_attempt_repository import submit_exam_attempt

        exam_set_id = sample_exam_set["exam_set_id"]

        # Create answers with invalid question ID
        invalid_answers = {
            "answers": [
                {"question_id": "invalid-question-id", "response": 0}
            ]
        }
        answers_path = tmp_path / "invalid_answers.json"
        answers_path.write_text(json.dumps(invalid_answers))

        result = submit_exam_attempt(
            exam_set_id=exam_set_id,
            answers_path=answers_path,
            data_dir=sample_book_multi_unit_chapter,
        )

        assert not result.success
        assert "no encontrado" in result.message.lower() or "not found" in result.message.lower()

    def test_submit_accepts_response_key(
        self, sample_book_multi_unit_chapter, sample_exam_set, tmp_path
    ):
        """submit_exam_attempt accepts 'response' key in answers."""
        from teaching.core.exam_attempt_repository import submit_exam_attempt

        exam_set_id = sample_exam_set["exam_set_id"]
        questions = sample_exam_set["questions"]

        answers = {
            "answers": [
                {"question_id": questions[0]["question_id"], "response": 0}
            ]
        }
        answers_path = tmp_path / "response_answers.json"
        answers_path.write_text(json.dumps(answers))

        result = submit_exam_attempt(
            exam_set_id=exam_set_id,
            answers_path=answers_path,
            data_dir=sample_book_multi_unit_chapter,
        )

        assert result.success


class TestExamAttemptSchema:
    """Tests for exam_attempt_v1 schema compliance."""

    def test_attempt_file_has_correct_schema(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_answers_file
    ):
        """Attempt file has exam_attempt_v1 schema."""
        from teaching.core.exam_attempt_repository import submit_exam_attempt

        exam_set_id = sample_exam_set["exam_set_id"]
        result = submit_exam_attempt(
            exam_set_id=exam_set_id,
            answers_path=sample_exam_answers_file,
            data_dir=sample_book_multi_unit_chapter,
        )

        assert result.success
        assert result.attempt_path is not None

        with open(result.attempt_path) as f:
            attempt_data = json.load(f)

        assert attempt_data["$schema"] == "exam_attempt_v1"
        assert "exam_attempt_id" in attempt_data
        assert "exam_set_id" in attempt_data
        assert "chapter_id" in attempt_data
        assert "answers" in attempt_data


class TestSafetyNoRealData:
    """Tests ensuring real data is not touched."""

    def test_submit_does_not_touch_real_data(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_answers_file
    ):
        """submit_exam_attempt does not modify ./data directory."""
        from teaching.core.exam_attempt_repository import submit_exam_attempt

        real_data_dir = Path("data")
        real_data_existed = real_data_dir.exists()

        initial_count = 0
        if real_data_existed:
            initial_files = list(real_data_dir.rglob("*"))
            initial_count = len(initial_files)

        exam_set_id = sample_exam_set["exam_set_id"]
        submit_exam_attempt(
            exam_set_id=exam_set_id,
            answers_path=sample_exam_answers_file,
            data_dir=sample_book_multi_unit_chapter,
        )

        if real_data_existed:
            current_files = list(real_data_dir.rglob("*"))
            assert len(current_files) == initial_count, "Real data directory was modified"
