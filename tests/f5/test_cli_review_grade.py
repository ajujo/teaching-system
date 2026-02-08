"""Tests for review-grade command (F5 Polish)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from teaching.cli.commands import app

runner = CliRunner()


class TestReviewGradeCommand:
    """Tests for teach review-grade command."""

    def test_review_grade_displays_report(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """review-grade displays grade report with Rich formatting."""
        from teaching.core.grader import grade_attempt

        attempt_id = sample_attempt["attempt_id"]

        # First, create a grade report
        grade_result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )
        assert grade_result.success

        # Now run review-grade
        result = runner.invoke(
            app,
            ["review-grade", attempt_id],
            env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
        )

        assert result.exit_code == 0
        # Verify key information is displayed
        assert "%" in result.output  # Percentage shown
        assert "Archivo:" in result.output  # File path shown
        # Table elements should be visible
        assert "q0" in result.output.lower()  # Question IDs

    def test_review_grade_missing_suggests_grade_command(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt
    ):
        """review-grade for missing grade suggests running grade command."""
        attempt_id = sample_attempt["attempt_id"]

        # DON'T create grade report - it shouldn't exist yet
        # Verify grade doesn't exist
        book_id = "test-book"
        grade_path = sample_book_with_notes / "books" / book_id / "artifacts" / "grades" / f"{attempt_id}.json"
        if grade_path.exists():
            grade_path.unlink()

        result = runner.invoke(
            app,
            ["review-grade", attempt_id],
            env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
        )

        assert result.exit_code == 1
        assert "teach grade" in result.output

    def test_review_grade_invalid_id_format(self, sample_book_with_notes):
        """review-grade with invalid ID format shows error."""
        result = runner.invoke(
            app,
            ["review-grade", "invalid-id-format"],
            env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
        )

        assert result.exit_code == 1
        assert "Formato" in result.output or "inválido" in result.output.lower()

    def test_review_grade_shows_strict_indicator(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """review-grade shows ESTRICTO when strict mode was used."""
        from teaching.core.grader import grade_attempt

        attempt_id = sample_attempt["attempt_id"]

        # Create grade with strict=True
        grade_result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            strict=True,
            client=mock_llm_client_for_grading,
        )
        assert grade_result.success

        result = runner.invoke(
            app,
            ["review-grade", attempt_id],
            env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
        )

        assert result.exit_code == 0
        assert "ESTRICTO" in result.output

    def test_review_grade_shows_pass_status(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """review-grade shows APROBADO/NO APROBADO status."""
        from teaching.core.grader import grade_attempt

        attempt_id = sample_attempt["attempt_id"]

        # Create grade
        grade_result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )
        assert grade_result.success

        result = runner.invoke(
            app,
            ["review-grade", attempt_id],
            env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
        )

        assert result.exit_code == 0
        # Should show either APROBADO or NO APROBADO
        assert "APROBADO" in result.output or "NO APROBADO" in result.output

    def test_review_grade_does_not_touch_real_data(self, sample_book_with_notes):
        """review-grade command should not modify ./data directory."""
        # Get the actual data directory (not tmp_path)
        real_data_dir = Path("data")
        real_data_existed = real_data_dir.exists()

        # Count files if exists
        initial_count = 0
        if real_data_existed:
            initial_files = list(real_data_dir.rglob("*"))
            initial_count = len(initial_files)

        # Create a minimal grade report in tmp_path
        book_id = "test-book"
        grade_id = f"{book_id}-ch01-u01-ex01-a99"
        grades_dir = sample_book_with_notes / "books" / book_id / "artifacts" / "grades"
        grades_dir.mkdir(parents=True, exist_ok=True)

        grade_report = {
            "$schema": "grade_report_v1",
            "attempt_id": grade_id,
            "exercise_set_id": f"{book_id}-ch01-u01-ex01",
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "graded_at": "2026-02-02T12:00:00+00:00",
            "provider": "lmstudio",
            "model": "test-model",
            "mode": "auto",
            "strict": False,
            "grading_time_ms": 100,
            "results": [
                {
                    "exercise_id": f"{book_id}-ch01-u01-ex01-q01",
                    "is_correct": True,
                    "score": 1.0,
                    "feedback": "Correct!",
                    "expected_answer": "A",
                    "given_answer": "A",
                    "grading_path": "auto",
                }
            ],
            "summary": {
                "total_questions": 1,
                "correct_count": 1,
                "total_score": 1.0,
                "max_score": 1.0,
                "percentage": 1.0,
                "passed": True,
            },
        }
        grade_path = grades_dir / f"{grade_id}.json"
        grade_path.write_text(json.dumps(grade_report, indent=2))

        result = runner.invoke(
            app,
            ["review-grade", grade_id],
            env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
        )

        # Command should succeed
        assert result.exit_code == 0

        # Verify real data directory wasn't modified
        if real_data_existed:
            current_files = list(real_data_dir.rglob("*"))
            assert len(current_files) == initial_count, "Real data directory was modified"


class TestReviewGradeEdgeCases:
    """Edge case tests for review-grade command."""

    def test_review_grade_handles_null_is_correct(self, sample_book_with_notes):
        """review-grade shows ? for is_correct=null (grading error)."""
        book_id = "test-book"
        grade_id = f"{book_id}-ch01-u01-ex01-a98"
        grades_dir = sample_book_with_notes / "books" / book_id / "artifacts" / "grades"
        grades_dir.mkdir(parents=True, exist_ok=True)

        # Create grade report with is_correct=null
        grade_report = {
            "$schema": "grade_report_v1",
            "attempt_id": grade_id,
            "exercise_set_id": f"{book_id}-ch01-u01-ex01",
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "graded_at": "2026-02-02T12:00:00+00:00",
            "provider": "lmstudio",
            "model": "test-model",
            "mode": "llm",
            "strict": False,
            "grading_time_ms": 100,
            "results": [
                {
                    "exercise_id": f"{book_id}-ch01-u01-ex01-q01",
                    "is_correct": None,  # Null!
                    "score": 0.5,
                    "feedback": "Error evaluating response.",
                    "expected_answer": "Something",
                    "given_answer": "My answer",
                    "grading_path": "llm",
                }
            ],
            "summary": {
                "total_questions": 1,
                "correct_count": 0,
                "total_score": 0.5,
                "max_score": 1.0,
                "percentage": 0.5,
                "passed": False,
            },
        }
        grade_path = grades_dir / f"{grade_id}.json"
        grade_path.write_text(json.dumps(grade_report, indent=2))

        result = runner.invoke(
            app,
            ["review-grade", grade_id],
            env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
        )

        assert result.exit_code == 0
        # Should show "?" for null is_correct
        assert "?" in result.output

    def test_review_grade_truncates_long_feedback(self, sample_book_with_notes):
        """review-grade truncates feedback longer than 80 chars."""
        book_id = "test-book"
        grade_id = f"{book_id}-ch01-u01-ex01-a97"
        grades_dir = sample_book_with_notes / "books" / book_id / "artifacts" / "grades"
        grades_dir.mkdir(parents=True, exist_ok=True)

        long_feedback = "A" * 200  # Very long feedback

        grade_report = {
            "$schema": "grade_report_v1",
            "attempt_id": grade_id,
            "exercise_set_id": f"{book_id}-ch01-u01-ex01",
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "graded_at": "2026-02-02T12:00:00+00:00",
            "provider": "lmstudio",
            "model": "test-model",
            "mode": "auto",
            "strict": False,
            "grading_time_ms": 100,
            "results": [
                {
                    "exercise_id": f"{book_id}-ch01-u01-ex01-q01",
                    "is_correct": True,
                    "score": 1.0,
                    "feedback": long_feedback,
                    "expected_answer": "A",
                    "given_answer": "A",
                    "grading_path": "auto",
                }
            ],
            "summary": {
                "total_questions": 1,
                "correct_count": 1,
                "total_score": 1.0,
                "max_score": 1.0,
                "percentage": 1.0,
                "passed": True,
            },
        }
        grade_path = grades_dir / f"{grade_id}.json"
        grade_path.write_text(json.dumps(grade_report, indent=2))

        result = runner.invoke(
            app,
            ["review-grade", grade_id],
            env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
        )

        assert result.exit_code == 0
        # The 200-char feedback should be truncated
        assert long_feedback not in result.output  # Full string not shown
        # Rich Table uses Unicode ellipsis "…" (U+2026) for truncation
        assert "…" in result.output or "..." in result.output  # Ellipsis shown
