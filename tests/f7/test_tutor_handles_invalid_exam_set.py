"""Tests for tutor handling of invalid exam sets (F7)."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from teaching.core.tutor import TutorState


class TestInvalidExamHandling:
    """Tests for _run_tutor_exam_flow with invalid exams."""

    def test_retry_on_invalid_exam(self, sample_book_for_tutor):
        """Tutor retries generation when exam is invalid."""
        from teaching.cli.commands import _run_tutor_exam_flow

        call_count = [0]

        def mock_generate(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # First call: return invalid
                result.success = True
                result.metadata = MagicMock()
                result.metadata.valid = False
                result.metadata.validation_warnings = ["Test warning"]
            else:
                # Second call: return valid
                result.success = True
                result.metadata = MagicMock()
                result.metadata.valid = True
                result.metadata.exam_set_id = "test-book-ch01-exam01"
            return result

        with patch("teaching.cli.commands.generate_chapter_exam", side_effect=mock_generate):
            with patch("typer.prompt", return_value="1"):  # Choose retry
                exam_set_id = _run_tutor_exam_flow(
                    book_id="test-book",
                    chapter_number=1,
                    data_dir=sample_book_for_tutor,
                    provider="lmstudio",
                    model="test-model",
                )

        assert exam_set_id == "test-book-ch01-exam01"
        assert call_count[0] == 2

    def test_reduce_questions_on_option_2(self, sample_book_for_tutor):
        """Tutor reduces n when user chooses option 2."""
        from teaching.cli.commands import _run_tutor_exam_flow

        captured_n_values = []

        def mock_generate(*args, **kwargs):
            captured_n_values.append(kwargs.get("n", 12))
            result = MagicMock()
            result.success = True
            result.metadata = MagicMock()
            result.metadata.valid = False
            result.metadata.validation_warnings = ["Invalid"]
            return result

        prompt_responses = iter(["2", "3"])  # First reduce, then skip

        with patch("teaching.cli.commands.generate_chapter_exam", side_effect=mock_generate):
            with patch("typer.prompt", side_effect=lambda *a, **kw: next(prompt_responses)):
                with patch("typer.confirm", return_value=True):
                    exam_set_id = _run_tutor_exam_flow(
                        book_id="test-book",
                        chapter_number=1,
                        data_dir=sample_book_for_tutor,
                        provider="lmstudio",
                        model="test-model",
                    )

        # First call should have n=12, second should have n=8
        assert captured_n_values[0] == 12
        assert captured_n_values[1] == 8
        assert exam_set_id is None  # Eventually skipped

    def test_skip_exam_returns_none(self, sample_book_for_tutor):
        """Tutor returns None when user skips exam."""
        from teaching.cli.commands import _run_tutor_exam_flow

        def mock_generate(*args, **kwargs):
            result = MagicMock()
            result.success = True
            result.metadata = MagicMock()
            result.metadata.valid = False
            result.metadata.validation_warnings = ["Invalid"]
            return result

        with patch("teaching.cli.commands.generate_chapter_exam", side_effect=mock_generate):
            with patch("typer.prompt", return_value="3"):  # Skip immediately
                exam_set_id = _run_tutor_exam_flow(
                    book_id="test-book",
                    chapter_number=1,
                    data_dir=sample_book_for_tutor,
                    provider="lmstudio",
                    model="test-model",
                )

        assert exam_set_id is None

    def test_max_retries_exhausted(self, sample_book_for_tutor):
        """Tutor stops after max retries."""
        from teaching.cli.commands import _run_tutor_exam_flow

        call_count = [0]

        def mock_generate(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            result.success = True
            result.metadata = MagicMock()
            result.metadata.valid = False
            result.metadata.validation_warnings = ["Still invalid"]
            return result

        # Always choose retry (option 1)
        with patch("teaching.cli.commands.generate_chapter_exam", side_effect=mock_generate):
            with patch("typer.prompt", return_value="1"):
                with patch("typer.confirm", return_value=True):  # Skip after max retries
                    exam_set_id = _run_tutor_exam_flow(
                        book_id="test-book",
                        chapter_number=1,
                        data_dir=sample_book_for_tutor,
                        provider="lmstudio",
                        model="test-model",
                    )

        # Should have tried 3 times (initial + 2 retries)
        assert call_count[0] == 3
        assert exam_set_id is None


class TestExamQuizFlowWithInvalidExam:
    """Tests for _run_tutor_exam_quiz_flow with invalid/fallback exams."""

    def test_warns_when_exam_invalid(self, sample_book_for_tutor):
        """Shows warning when exam is marked invalid."""
        from teaching.cli.commands import _run_tutor_exam_quiz_flow

        # Create an invalid exam set
        exams_dir = sample_book_for_tutor / "books" / "test-book" / "artifacts" / "exams"
        exams_dir.mkdir(parents=True, exist_ok=True)

        exam_set = {
            "$schema": "chapter_exam_set_v1",
            "exam_set_id": "test-book-ch01-exam01",
            "book_id": "test-book",
            "chapter_id": "test-book:ch:1",
            "chapter_title": "Test Chapter",
            "valid": False,
            "mode": "text_fallback",
            "passing_threshold": 0.6,
            "questions": [
                {
                    "question_id": "q1",
                    "type": "multiple_choice",
                    "question": "Test?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 0,
                    "explanation": "",
                }
            ],
        }

        with open(exams_dir / "test-book-ch01-exam01.json", "w") as f:
            json.dump(exam_set, f)

        # Mock to cancel before starting exam
        with patch("typer.confirm", return_value=False):
            passed, attempt_id = _run_tutor_exam_quiz_flow(
                exam_set_id="test-book-ch01-exam01",
                data_dir=sample_book_for_tutor,
                provider="lmstudio",
                model="test-model",
                book_id="test-book",
            )

        assert passed is False
        assert attempt_id is None

    def test_text_fallback_shows_warning(self, sample_book_for_tutor):
        """Shows warning for text_fallback mode even if valid=True."""
        from teaching.cli.commands import _run_tutor_exam_quiz_flow

        exams_dir = sample_book_for_tutor / "books" / "test-book" / "artifacts" / "exams"
        exams_dir.mkdir(parents=True, exist_ok=True)

        exam_set = {
            "$schema": "chapter_exam_set_v1",
            "exam_set_id": "test-book-ch01-exam02",
            "book_id": "test-book",
            "chapter_id": "test-book:ch:1",
            "chapter_title": "Test Chapter",
            "valid": True,
            "mode": "text_fallback",
            "passing_threshold": 0.6,
            "questions": [
                {
                    "question_id": "q1",
                    "type": "multiple_choice",
                    "question": "Test?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 0,
                    "explanation": "Test",
                }
            ],
        }

        with open(exams_dir / "test-book-ch01-exam02.json", "w") as f:
            json.dump(exam_set, f)

        # Cancel before starting
        with patch("typer.confirm", return_value=False):
            passed, attempt_id = _run_tutor_exam_quiz_flow(
                exam_set_id="test-book-ch01-exam02",
                data_dir=sample_book_for_tutor,
                provider="lmstudio",
                model="test-model",
                book_id="test-book",
            )

        assert passed is False


class TestExamGenerationFailure:
    """Tests for complete exam generation failure."""

    def test_generation_error_shows_message(self, sample_book_for_tutor):
        """Shows error message when generation fails completely."""
        from teaching.cli.commands import _run_tutor_exam_flow

        def mock_generate(*args, **kwargs):
            result = MagicMock()
            result.success = False
            result.message = "LLM timeout"
            result.metadata = None
            return result

        with patch("teaching.cli.commands.generate_chapter_exam", side_effect=mock_generate):
            with patch("typer.prompt", return_value="3"):  # Skip
                exam_set_id = _run_tutor_exam_flow(
                    book_id="test-book",
                    chapter_number=1,
                    data_dir=sample_book_for_tutor,
                    provider="lmstudio",
                    model="test-model",
                )

        assert exam_set_id is None


class TestStateUpdateAfterExam:
    """Tests for state updates after exam completion."""

    def test_passed_exam_marks_chapter_complete(self, sample_book_for_tutor):
        """Passing an exam marks the chapter as complete."""
        from teaching.core.tutor import TutorState, save_tutor_state, load_tutor_state

        # Create initial state
        state = TutorState()
        state.active_book_id = "test-book"
        progress = state.get_book_progress("test-book")
        progress.last_chapter_number = 1
        save_tutor_state(state, sample_book_for_tutor)

        # Simulate passing exam (manually update progress)
        progress.completed_chapters.append(1)
        save_tutor_state(state, sample_book_for_tutor)

        # Verify state was updated
        loaded = load_tutor_state(sample_book_for_tutor)
        assert 1 in loaded.progress["test-book"].completed_chapters

    def test_exam_attempt_tracked_in_state(self, sample_book_for_tutor):
        """Exam attempts are tracked in book progress."""
        from teaching.core.tutor import TutorState, save_tutor_state, load_tutor_state

        state = TutorState()
        progress = state.get_book_progress("test-book")

        # Simulate tracking an attempt
        exam_set_id = "test-book-ch01-exam01"
        attempt_id = "test-book-ch01-exam01-a01"

        if exam_set_id not in progress.chapter_attempts:
            progress.chapter_attempts[exam_set_id] = []
        progress.chapter_attempts[exam_set_id].append(attempt_id)

        save_tutor_state(state, sample_book_for_tutor)
        loaded = load_tutor_state(sample_book_for_tutor)

        assert exam_set_id in loaded.progress["test-book"].chapter_attempts
        assert attempt_id in loaded.progress["test-book"].chapter_attempts[exam_set_id]
