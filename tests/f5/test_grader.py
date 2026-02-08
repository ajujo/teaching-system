"""Tests for grader module."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from teaching.core.grader import (
    ExerciseGrade,
    GradeReport,
    GradeResult,
    GradeSummary,
    GradingError,
    grade_attempt,
)


class TestGradeAttempt:
    """Tests for attempt grading."""

    def test_grade_creates_report_and_scores(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """Grading creates proper report with scores."""
        attempt_id = sample_attempt["attempt_id"]

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is True
        assert result.grade_path is not None
        assert result.grade_path.exists()
        assert "artifacts/grades" in str(result.grade_path)

        # Verify JSON structure
        with open(result.grade_path) as f:
            data = json.load(f)

        assert data["$schema"] == "grade_report_v1"
        assert data["attempt_id"] == attempt_id
        assert "results" in data
        assert "summary" in data
        assert "total_questions" in data["summary"]
        assert "percentage" in data["summary"]
        assert "passed" in data["summary"]

    def test_grade_updates_attempt_status(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """Grading updates attempt status to 'graded'."""
        attempt_id = sample_attempt["attempt_id"]
        book_id = sample_attempt["book_id"]

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is True

        # Check attempt file was updated
        attempt_path = (
            sample_book_with_notes
            / "books"
            / book_id
            / "artifacts"
            / "attempts"
            / f"{attempt_id}.json"
        )
        with open(attempt_path) as f:
            attempt_data = json.load(f)

        assert attempt_data["status"] == "graded"


class TestAutoGrading:
    """Tests for automatic grading of objective questions."""

    def test_grade_auto_multiple_choice_correct(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """Correct MC answer gets score 1.0."""
        attempt_id = sample_attempt["attempt_id"]

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is True

        # Find MC results (first and fourth exercises in our fixture)
        mc_results = [r for r in result.report.results if r.exercise_id.endswith("-q01") or r.exercise_id.endswith("-q04")]

        for r in mc_results:
            assert r.is_correct is True
            assert r.score == 1.0

    def test_grade_auto_multiple_choice_incorrect(
        self, sample_book_with_notes, sample_exercise_set, tmp_path, mock_llm_client_for_grading
    ):
        """Incorrect MC answer gets score 0.0."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]

        # Create attempt with wrong answer for MC
        wrong_answers = {
            "answers": [
                {
                    "exercise_id": exercises[0]["exercise_id"],  # MC, correct is 0
                    "response": 1,  # Wrong
                }
            ]
        }
        answers_path = tmp_path / "wrong_answers.json"
        answers_path.write_text(json.dumps(wrong_answers))

        # Create attempt
        attempt_id = f"{exercise_set_id}-a99"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": wrong_answers["answers"],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is True
        assert len(result.report.results) == 1
        assert result.report.results[0].is_correct is False
        assert result.report.results[0].score == 0.0

    def test_grade_auto_true_false_correct(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """Correct TF answer gets score 1.0."""
        attempt_id = sample_attempt["attempt_id"]

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is True

        # Find TF results (second and fifth exercises)
        tf_results = [r for r in result.report.results if r.exercise_id.endswith("-q02") or r.exercise_id.endswith("-q05")]

        for r in tf_results:
            assert r.is_correct is True
            assert r.score == 1.0


class TestLLMGrading:
    """Tests for LLM grading of subjective questions."""

    def test_grade_llm_short_answer(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """Short answer questions use LLM for grading."""
        attempt_id = sample_attempt["attempt_id"]

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is True

        # Find short answer result (third exercise)
        sa_results = [r for r in result.report.results if r.exercise_id.endswith("-q03")]
        assert len(sa_results) == 1

        sa_result = sa_results[0]
        # LLM was called, so we get partial score
        assert 0.0 <= sa_result.score <= 1.0
        assert sa_result.feedback  # Has feedback
        assert sa_result.confidence is not None

    def test_grade_llm_fallback_on_error(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt
    ):
        """LLM grading has fallback when JSON fails."""
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True

        # First call fails, second succeeds
        mock_client.simple_json.side_effect = LLMError("JSON error")
        mock_client.simple_chat.return_value = json.dumps({
            "is_correct": True,
            "score": 0.8,
            "feedback": "Buena respuesta.",
            "confidence": 0.85,
        })

        result = grade_attempt(
            attempt_id=sample_attempt["attempt_id"],
            data_dir=sample_book_with_notes,
            client=mock_client,
        )

        assert result.success is True
        # Should still have graded short answer with fallback
        sa_results = [r for r in result.report.results if r.exercise_id.endswith("-q03")]
        assert len(sa_results) == 1


class TestGradeSummary:
    """Tests for grade summary calculation."""

    def test_summary_calculates_percentage(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """Summary includes correct percentage calculation."""
        result = grade_attempt(
            attempt_id=sample_attempt["attempt_id"],
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is True
        summary = result.report.summary

        assert 0.0 <= summary.percentage <= 1.0
        assert summary.total_questions == 5
        assert summary.total_score <= summary.max_score

    def test_summary_passed_threshold(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """Passed is determined by passing_threshold."""
        result = grade_attempt(
            attempt_id=sample_attempt["attempt_id"],
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is True
        summary = result.report.summary

        # Default threshold is 0.7
        expected_passed = summary.percentage >= 0.7
        assert summary.passed == expected_passed


class TestGradeDataClasses:
    """Tests for grading data classes."""

    def test_exercise_grade_to_dict(self):
        """ExerciseGrade.to_dict() returns correct structure."""
        grade = ExerciseGrade(
            exercise_id="test-ex01-q01",
            is_correct=True,
            score=1.0,
            feedback="Correcto!",
            expected_answer="0",
            confidence=None,
        )

        d = grade.to_dict()

        assert d["exercise_id"] == "test-ex01-q01"
        assert d["is_correct"] is True
        assert d["score"] == 1.0
        assert d["feedback"] == "Correcto!"
        assert d["expected_answer"] == "0"

    def test_exercise_grade_with_confidence(self):
        """ExerciseGrade.to_dict() includes confidence when present."""
        grade = ExerciseGrade(
            exercise_id="test-ex01-q03",
            is_correct=True,
            score=0.85,
            feedback="Buena respuesta.",
            expected_answer="Expected text",
            confidence=0.9,
        )

        d = grade.to_dict()

        assert d["confidence"] == 0.9

    def test_grade_summary_to_dict(self):
        """GradeSummary.to_dict() returns correct structure."""
        summary = GradeSummary(
            total_questions=5,
            correct_count=4,
            total_score=4.5,
            max_score=6.0,
            percentage=0.75,
            passed=True,
        )

        d = summary.to_dict()

        assert d["total_questions"] == 5
        assert d["correct_count"] == 4
        assert d["total_score"] == 4.5
        assert d["max_score"] == 6.0
        assert d["percentage"] == 0.75
        assert d["passed"] is True

    def test_grade_report_to_dict(self):
        """GradeReport.to_dict() returns correct schema."""
        report = GradeReport(
            attempt_id="test-ex01-a01",
            exercise_set_id="test-ex01",
            unit_id="test-book-ch01-u01",
            book_id="test-book",
            graded_at="2026-02-02T12:00:00+00:00",
            provider="lmstudio",
            model="test-model",
            mode="mixed",
            strict=False,
            grading_time_ms=2000,
            results=[
                ExerciseGrade(
                    exercise_id="test-ex01-q01",
                    is_correct=True,
                    score=1.0,
                    feedback="OK",
                    expected_answer="0",
                )
            ],
            summary=GradeSummary(
                total_questions=1,
                correct_count=1,
                total_score=1.0,
                max_score=1.0,
                percentage=1.0,
                passed=True,
            ),
        )

        d = report.to_dict()

        assert d["$schema"] == "grade_report_v1"
        assert d["attempt_id"] == "test-ex01-a01"
        assert d["mode"] == "mixed"
        assert len(d["results"]) == 1
        assert d["summary"]["passed"] is True


class TestGradeErrors:
    """Tests for grading error handling."""

    def test_grade_attempt_not_found(self, sample_book_with_notes, mock_llm_client_for_grading):
        """Returns error when attempt doesn't exist."""
        result = grade_attempt(
            attempt_id="nonexistent-a01",
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is False
        assert "no encontrad" in result.message.lower()

    def test_grade_exercise_set_not_found(
        self, sample_book_with_notes, tmp_path, mock_llm_client_for_grading
    ):
        """Returns error when exercise set doesn't exist."""
        book_id = "test-book"

        # Create orphan attempt (no matching exercise set) with valid ID format
        attempt_id = f"{book_id}-ch01-u01-ex99-a01"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": f"{book_id}-ch01-u01-ex99",
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [],
            "total_questions": 0,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is False
        assert "no encontrad" in result.message.lower()

    def test_grade_llm_unavailable(self, sample_book_with_notes, sample_exercise_set, sample_attempt):
        """Returns error when LLM unavailable for subjective grading."""
        mock_client = MagicMock()
        mock_client.is_available.return_value = False
        mock_client.config.provider = "lmstudio"

        result = grade_attempt(
            attempt_id=sample_attempt["attempt_id"],
            data_dir=sample_book_with_notes,
            client=mock_client,
        )

        # Should fail because we need LLM for short_answer
        assert result.success is False
        assert "llm" in result.message.lower() or "conectar" in result.message.lower()


class TestDeterministicGrading:
    """Tests for deterministic MCQ/TF grading (F5 bugfix regression tests)."""

    def test_grader_deterministic_mcq_uses_correct_answer_index(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """MCQ grading uses correct_answer index deterministically, no LLM."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]
        mc_exercise = exercises[0]  # MC with correct_answer=0

        # Create attempt with correct answer (use valid format -aNN)
        attempt_id = f"{exercise_set_id}-a51"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": mc_exercise["exercise_id"], "response": 0}
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        # Grade WITHOUT LLM client (should work for MCQ-only)
        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=None,  # No LLM!
        )

        assert result.success is True
        assert len(result.report.results) == 1

        grade = result.report.results[0]
        assert grade.is_correct is True
        assert grade.score == 1.0
        assert grade.grading_path == "auto"
        assert grade.given_answer is not None
        assert "0" in grade.given_answer  # Contains the index

    def test_grader_mcq_handles_null_response(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """MCQ grading handles null/None response gracefully without crashing."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]
        mc_exercise = exercises[0]

        attempt_id = f"{exercise_set_id}-a52"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": mc_exercise["exercise_id"], "response": None}  # NULL!
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=None,
        )

        assert result.success is True
        grade = result.report.results[0]
        assert grade.is_correct is False
        assert grade.score == 0.0
        assert "(sin respuesta)" in grade.given_answer
        assert grade.grading_path == "auto"

    def test_grader_tf_handles_null_response(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """TF grading handles null/None response gracefully."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]
        tf_exercise = exercises[1]  # TF exercise

        attempt_id = f"{exercise_set_id}-a53"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": tf_exercise["exercise_id"], "response": None}
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=None,
        )

        assert result.success is True
        grade = result.report.results[0]
        assert grade.is_correct is False
        assert "(sin respuesta)" in grade.given_answer

    def test_grader_short_answer_empty_response_no_llm_call(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """Short answer with empty response doesn't call LLM."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]
        sa_exercise = exercises[2]  # short_answer

        attempt_id = f"{exercise_set_id}-a54"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": sa_exercise["exercise_id"], "response": ""}  # Empty
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        # Create mock client that would fail if called
        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True
        # If LLM is called, test fails
        mock_client.simple_json.side_effect = AssertionError("LLM should not be called for empty response")

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=mock_client,
        )

        assert result.success is True
        grade = result.report.results[0]
        assert grade.is_correct is False
        assert grade.score == 0.0
        assert "(sin respuesta)" in grade.given_answer
        assert grade.grading_path == "auto"  # Not "llm"

    def test_grader_includes_new_fields_in_report(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """Grade report includes given_answer, correct_option_text, grading_path."""
        result = grade_attempt(
            attempt_id=sample_attempt["attempt_id"],
            data_dir=sample_book_with_notes,
            client=mock_llm_client_for_grading,
        )

        assert result.success is True

        # Check MCQ result has all new fields
        mc_results = [r for r in result.report.results if r.exercise_id.endswith("-q01")]
        assert len(mc_results) == 1
        mc_grade = mc_results[0]

        assert mc_grade.given_answer is not None
        assert mc_grade.correct_option_text is not None
        assert mc_grade.grading_path == "auto"

        # Check report JSON includes new fields
        with open(result.grade_path) as f:
            data = json.load(f)

        mc_result_data = [r for r in data["results"] if r["exercise_id"].endswith("-q01")][0]
        assert "given_answer" in mc_result_data
        assert "correct_option_text" in mc_result_data
        assert "grading_path" in mc_result_data


class TestProviderModelInheritance:
    """Tests for provider/model inheritance from exercise_set."""

    def test_grade_inherits_provider_model_from_exercise_set(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """Grading inherits provider/model from exercise_set when not specified."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]

        # The fixture's exercise_set has provider="lmstudio", model="test-model"
        # Create MCQ-only attempt (no LLM needed)
        attempt_id = f"{exercise_set_id}-a55"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": exercises[0]["exercise_id"], "response": 0}
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            provider=None,  # Not specified
            model=None,     # Not specified
            client=None,    # No mock client
        )

        assert result.success is True
        # Report should show inherited values
        assert result.report.provider == "lmstudio"
        assert result.report.model == "test-model"


class TestBackwardCompatibility:
    """Tests for backward compatibility."""

    def test_load_attempt_supports_legacy_answer_field(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """Attempt loading supports legacy 'answer' field alongside 'response'."""
        from teaching.core.attempt_repository import load_attempt

        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]

        # Create attempt with legacy "answer" field instead of "response"
        attempt_id = f"{exercise_set_id}-a56"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": exercises[0]["exercise_id"], "answer": 0}  # Legacy!
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        loaded = load_attempt(attempt_id, sample_book_with_notes)

        assert loaded is not None
        assert len(loaded.answers) == 1
        assert loaded.answers[0].response == 0  # Should read from legacy field

    def test_grading_works_with_legacy_answer_field(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """Grading works correctly with legacy 'answer' field."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]

        attempt_id = f"{exercise_set_id}-a57"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": exercises[0]["exercise_id"], "answer": 0}  # Legacy!
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            client=None,
        )

        assert result.success is True
        assert result.report.results[0].is_correct is True  # correct_answer is 0


class TestStrictModeBinarization:
    """Tests for strict mode short_answer score binarization (F5 Polish)."""

    def test_strict_binarizes_score_above_threshold(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """Score >= 0.95 becomes 1.0 in strict mode."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]
        sa_exercise = exercises[2]  # short_answer

        # Create mock that returns score=0.96 (above 0.95 threshold)
        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True
        mock_client.simple_json.return_value = {
            "is_correct": True,
            "score": 0.96,  # Above threshold
            "feedback": "Almost perfect answer.",
            "confidence": 0.9,
        }

        # Create attempt with only short_answer
        attempt_id = f"{exercise_set_id}-a60"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": sa_exercise["exercise_id"], "response": "My detailed answer"}
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            strict=True,  # STRICT MODE
            client=mock_client,
        )

        assert result.success is True
        assert result.report.strict is True

        # Score should be binarized to 1.0 (was 0.96, above 0.95)
        assert result.report.results[0].score == 1.0
        assert result.report.results[0].is_correct is True

    def test_strict_binarizes_score_below_threshold(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """Score < 0.95 becomes 0.0 in strict mode."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]
        sa_exercise = exercises[2]  # short_answer

        # Create mock that returns score=0.80 (below 0.95 threshold)
        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True
        mock_client.simple_json.return_value = {
            "is_correct": True,  # LLM thinks it's correct but score is 0.8
            "score": 0.80,  # Below threshold
            "feedback": "Good answer but missing key points.",
            "confidence": 0.85,
        }

        attempt_id = f"{exercise_set_id}-a61"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": sa_exercise["exercise_id"], "response": "My partial answer"}
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            strict=True,  # STRICT MODE
            client=mock_client,
        )

        assert result.success is True
        assert result.report.strict is True

        # Score should be binarized to 0.0 (was 0.80, below 0.95)
        assert result.report.results[0].score == 0.0
        assert result.report.results[0].is_correct is False

    def test_non_strict_preserves_partial_scores(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """Without strict, partial scores are preserved."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]
        sa_exercise = exercises[2]  # short_answer

        # Create mock that returns score=0.75
        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True
        mock_client.simple_json.return_value = {
            "is_correct": None,  # Partial
            "score": 0.75,
            "feedback": "Decent answer.",
            "confidence": 0.8,
        }

        attempt_id = f"{exercise_set_id}-a62"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": sa_exercise["exercise_id"], "response": "Some answer"}
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            strict=False,  # NON-STRICT MODE
            client=mock_client,
        )

        assert result.success is True
        assert result.report.strict is False

        # Score should be preserved as 0.75
        assert result.report.results[0].score == 0.75

    def test_strict_reflected_in_grade_report_json(
        self, sample_book_with_notes, sample_exercise_set
    ):
        """Strict flag is correctly reflected in grade_report_v1 JSON."""
        book_id = "test-book"
        exercise_set_id = sample_exercise_set["exercise_set_id"]
        exercises = sample_exercise_set["exercises"]

        # Create MCQ-only attempt (no LLM needed)
        attempt_id = f"{exercise_set_id}-a63"
        attempt = {
            "$schema": "attempt_v1",
            "attempt_id": attempt_id,
            "exercise_set_id": exercise_set_id,
            "unit_id": f"{book_id}-ch01-u01",
            "book_id": book_id,
            "created_at": "2026-02-02T11:00:00+00:00",
            "status": "pending",
            "answers": [
                {"exercise_id": exercises[0]["exercise_id"], "response": 0}
            ],
            "total_questions": 1,
        }
        attempts_path = (
            sample_book_with_notes / "books" / book_id / "artifacts" / "attempts" / f"{attempt_id}.json"
        )
        attempts_path.write_text(json.dumps(attempt, indent=2))

        result = grade_attempt(
            attempt_id=attempt_id,
            data_dir=sample_book_with_notes,
            strict=True,
            client=None,
        )

        assert result.success is True

        # Verify JSON has strict=true
        with open(result.grade_path) as f:
            data = json.load(f)

        assert data["strict"] is True
