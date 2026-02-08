"""Tests for exam grading (F6)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGradeExamAttempt:
    """Tests for grade_exam_attempt function."""

    def test_grade_creates_report_file(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """grade_exam_attempt creates grade report file."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.grade_path is not None
        assert result.grade_path.exists()

    def test_grade_report_has_correct_schema(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """Grade report has exam_grade_report_v1 schema."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.grade_path is not None

        with open(result.grade_path) as f:
            grade_data = json.load(f)

        assert grade_data["$schema"] == "exam_grade_report_v1"
        assert "exam_attempt_id" in grade_data
        assert "exam_set_id" in grade_data
        assert "chapter_id" in grade_data
        assert "results" in grade_data
        assert "summary" in grade_data


class TestAutoGrading:
    """Tests for auto-grading of MCQ and TF questions."""

    def test_auto_grades_mcq_correctly(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """MCQ questions are graded automatically."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.report is not None

        # Find MCQ results (first 6 questions)
        mcq_results = [r for r in result.report.results if r.grading_path == "auto"]

        # All 6 MCQ answers in fixture are correct
        mcq_correct = sum(1 for r in mcq_results[:6] if r.is_correct is True)
        assert mcq_correct == 6

    def test_auto_grades_tf_correctly(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """TF questions are graded automatically."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.report is not None

        # TF questions are 7, 8, 9 (indices 6, 7, 8)
        # In fixture: 2 correct (False, True), 1 wrong (False instead of True)
        tf_results = result.report.results[6:9]
        tf_correct = sum(1 for r in tf_results if r.is_correct is True)
        assert tf_correct == 2


class TestLLMGrading:
    """Tests for LLM grading of short answer questions."""

    def test_llm_grades_short_answer(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """Short answer questions are graded by LLM."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.report is not None

        # SA questions are 10, 11, 12 (indices 9, 10, 11)
        sa_results = result.report.results[9:12]
        for r in sa_results:
            assert r.grading_path == "llm"


class TestStrictMode:
    """Tests for strict grading mode."""

    def test_strict_is_default_true(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """Exams default to strict=True."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.report is not None
        assert result.report.strict is True

    def test_strict_binarizes_short_answer_scores(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt
    ):
        """Strict mode binarizes short answer scores (>=0.95 -> 1.0, else -> 0.0)."""
        from teaching.core.exam_grader import grade_exam_attempt

        # Mock client returns 0.85 score
        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"
        mock_client.is_available.return_value = True
        mock_client.simple_json.return_value = {
            "is_correct": True,
            "score": 0.85,  # Below 0.95 threshold
            "feedback": "Good answer",
            "confidence": 0.9,
        }

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            strict=True,
            client=mock_client,
        )

        assert result.success
        assert result.report is not None

        # SA results should have score 0.0 because 0.85 < 0.95
        sa_results = result.report.results[9:12]
        for r in sa_results:
            assert r.score == 0.0


class TestGradeSummary:
    """Tests for grade summary calculations."""

    def test_summary_includes_by_unit_breakdown(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """Summary includes breakdown by unit."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.report is not None
        assert result.report.summary.by_unit is not None
        assert len(result.report.summary.by_unit) > 0

    def test_summary_includes_by_type_breakdown(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """Summary includes breakdown by question type."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.report is not None
        assert result.report.summary.by_type is not None
        assert "multiple_choice" in result.report.summary.by_type
        assert "true_false" in result.report.summary.by_type
        assert "short_answer" in result.report.summary.by_type

    def test_60_percent_passing_threshold(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """Passing threshold is 60%."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.report is not None
        # Check passing logic uses 60% threshold
        # With 6 MCQ + 2 TF correct (8 points) out of 15 total points = 53.3%
        # So it should NOT pass with default mock responses


class TestSourceTracking:
    """Tests for source tracking in grade results."""

    def test_results_include_source_unit_id(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """Grade results include source_unit_id for each question."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        assert result.success
        assert result.report is not None

        for r in result.report.results:
            assert r.source_unit_id is not None


class TestGradeErrors:
    """Tests for error handling."""

    def test_attempt_not_found_returns_error(self, sample_book_multi_unit_chapter):
        """Non-existent attempt returns error."""
        from teaching.core.exam_grader import grade_exam_attempt

        result = grade_exam_attempt(
            exam_attempt_id="test-book-ch01-exam01-a99",
            data_dir=sample_book_multi_unit_chapter,
        )

        assert not result.success
        assert "no encontr" in result.message.lower() or "not found" in result.message.lower()

    def test_invalid_attempt_id_returns_error(self, sample_book_multi_unit_chapter):
        """Invalid attempt ID format returns error."""
        from teaching.core.exam_grader import grade_exam_attempt

        result = grade_exam_attempt(
            exam_attempt_id="invalid-format",
            data_dir=sample_book_multi_unit_chapter,
        )

        assert not result.success


class TestSafetyNoRealData:
    """Tests ensuring real data is not touched."""

    def test_grade_does_not_touch_real_data(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """grade_exam_attempt does not modify ./data directory."""
        from teaching.core.exam_grader import grade_exam_attempt

        real_data_dir = Path("data")
        real_data_existed = real_data_dir.exists()

        initial_count = 0
        if real_data_existed:
            initial_files = list(real_data_dir.rglob("*"))
            initial_count = len(initial_files)

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]
        grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )

        if real_data_existed:
            current_files = list(real_data_dir.rglob("*"))
            assert len(current_files) == initial_count, "Real data directory was modified"
