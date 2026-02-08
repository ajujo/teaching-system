"""Tests for mini-quiz per unit functionality (F7.2)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console


class TestMiniQuizFunction:
    """Tests for _run_unit_mini_quiz function."""

    def test_mini_quiz_function_exists(self):
        """The mini-quiz function is defined in commands module."""
        # Import to verify it exists
        from teaching.cli.commands import _run_unit_mini_quiz
        assert callable(_run_unit_mini_quiz)

    def test_mini_quiz_signature(self):
        """Mini-quiz has expected parameters."""
        import inspect
        from teaching.cli.commands import _run_unit_mini_quiz

        sig = inspect.signature(_run_unit_mini_quiz)
        params = list(sig.parameters.keys())

        assert "unit_id" in params
        assert "data_dir" in params
        assert "provider" in params
        assert "model" in params
        assert "console_obj" in params
        assert "n_questions" in params

    def test_mini_quiz_default_5_questions(self):
        """Mini-quiz defaults to 5 questions."""
        import inspect
        from teaching.cli.commands import _run_unit_mini_quiz

        sig = inspect.signature(_run_unit_mini_quiz)
        n_questions_param = sig.parameters.get("n_questions")

        assert n_questions_param is not None
        assert n_questions_param.default == 5


class TestMiniQuizIntegration:
    """Integration tests for mini-quiz with mocked dependencies."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return MagicMock(spec=Console)

    @pytest.fixture
    def mock_exercise_result(self):
        """Create mock exercise generation result."""
        from dataclasses import dataclass

        @dataclass
        class MockExercise:
            exercise_id: str
            question: str
            correct_answer: str
            type: str = "multiple_choice"
            options: list = None

            def __post_init__(self):
                if self.options is None:
                    self.options = ["A", "B", "C", "D"]

        @dataclass
        class MockMetadata:
            exercise_set_id: str = "test-set-01"

        @dataclass
        class MockResult:
            success: bool = True
            exercises: list = None
            metadata: MockMetadata = None
            message: str = ""

            def __post_init__(self):
                if self.exercises is None:
                    self.exercises = [
                        MockExercise(
                            exercise_id=f"ex-{i}",
                            question=f"Question {i}?",
                            correct_answer="A",
                        )
                        for i in range(5)
                    ]
                if self.metadata is None:
                    self.metadata = MockMetadata()

        return MockResult()

    @pytest.fixture
    def mock_grade_result(self):
        """Create mock grade result."""
        from dataclasses import dataclass

        @dataclass
        class MockGradeSummary:
            total_questions: int = 5
            correct_count: int = 4
            total_score: float = 4.0
            max_score: float = 5.0
            percentage: float = 0.8
            passed: bool = True

        @dataclass
        class MockGradeItem:
            exercise_id: str
            is_correct: bool
            score: float = 1.0
            feedback: str = ""
            student_response: str = "A"

        @dataclass
        class MockReport:
            summary: MockGradeSummary = None
            results: list = None

            def __post_init__(self):
                if self.summary is None:
                    self.summary = MockGradeSummary()
                if self.results is None:
                    self.results = [
                        MockGradeItem(exercise_id=f"ex-{i}", is_correct=True)
                        for i in range(5)
                    ]

        @dataclass
        class MockGradeResult:
            success: bool = True
            report: MockReport = None
            message: str = ""

            def __post_init__(self):
                if self.report is None:
                    self.report = MockReport()

        return MockGradeResult()

    def test_mini_quiz_calls_generate_exercises_with_n_5(
        self, mock_console, mock_exercise_result, mock_grade_result, tmp_path
    ):
        """Mini-quiz generates exactly 5 questions."""
        from teaching.cli.commands import _run_unit_mini_quiz

        # Patch at the module where they're imported inside the function
        with patch("teaching.core.exercise_generator.generate_exercises") as mock_gen, \
             patch("teaching.core.grader.grade_attempt") as mock_grade, \
             patch("teaching.cli.commands._ask_question") as mock_ask, \
             patch("teaching.cli.commands._submit_interactive_attempt") as mock_submit:

            mock_gen.return_value = mock_exercise_result
            mock_grade.return_value = mock_grade_result
            mock_ask.return_value = 0  # Answer "A"
            mock_submit.return_value = {"attempt_id": "test-attempt-01"}

            _run_unit_mini_quiz(
                unit_id="test-book-ch01-u01",
                data_dir=tmp_path,
                provider="lmstudio",
                model="test-model",
                console_obj=mock_console,
            )

            # Verify generate_exercises was called with n=5
            mock_gen.assert_called_once()
            call_kwargs = mock_gen.call_args.kwargs
            assert call_kwargs.get("n") == 5

    def test_mini_quiz_uses_strict_grading(
        self, mock_console, mock_exercise_result, mock_grade_result, tmp_path
    ):
        """Mini-quiz uses strict=True for grading."""
        from teaching.cli.commands import _run_unit_mini_quiz

        with patch("teaching.core.exercise_generator.generate_exercises") as mock_gen, \
             patch("teaching.core.grader.grade_attempt") as mock_grade, \
             patch("teaching.cli.commands._ask_question") as mock_ask, \
             patch("teaching.cli.commands._submit_interactive_attempt") as mock_submit:

            mock_gen.return_value = mock_exercise_result
            mock_grade.return_value = mock_grade_result
            mock_ask.return_value = 0
            mock_submit.return_value = {"attempt_id": "test-attempt-01"}

            _run_unit_mini_quiz(
                unit_id="test-book-ch01-u01",
                data_dir=tmp_path,
                provider="lmstudio",
                model="test-model",
                console_obj=mock_console,
            )

            # Verify grade_attempt was called with strict=True
            mock_grade.assert_called_once()
            call_kwargs = mock_grade.call_args.kwargs
            assert call_kwargs.get("strict") is True

    def test_mini_quiz_returns_true_when_passed(
        self, mock_console, mock_exercise_result, mock_grade_result, tmp_path
    ):
        """Mini-quiz returns True when student passes."""
        from teaching.cli.commands import _run_unit_mini_quiz

        with patch("teaching.core.exercise_generator.generate_exercises") as mock_gen, \
             patch("teaching.core.grader.grade_attempt") as mock_grade, \
             patch("teaching.cli.commands._ask_question") as mock_ask, \
             patch("teaching.cli.commands._submit_interactive_attempt") as mock_submit:

            mock_gen.return_value = mock_exercise_result
            mock_grade.return_value = mock_grade_result  # passed=True
            mock_ask.return_value = 0
            mock_submit.return_value = {"attempt_id": "test-attempt-01"}

            result = _run_unit_mini_quiz(
                unit_id="test-book-ch01-u01",
                data_dir=tmp_path,
                provider="lmstudio",
                model="test-model",
                console_obj=mock_console,
            )

            assert result is True

    def test_mini_quiz_returns_false_when_failed(
        self, mock_console, mock_exercise_result, tmp_path
    ):
        """Mini-quiz returns False when student fails."""
        from teaching.cli.commands import _run_unit_mini_quiz
        from dataclasses import dataclass

        # Create failed grade result
        @dataclass
        class FailedSummary:
            total_questions: int = 5
            correct_count: int = 2
            percentage: float = 0.4
            passed: bool = False

        @dataclass
        class FailedReport:
            summary: FailedSummary = None
            results: list = None

            def __post_init__(self):
                if self.summary is None:
                    self.summary = FailedSummary()
                if self.results is None:
                    self.results = []

        @dataclass
        class FailedGradeResult:
            success: bool = True
            report: FailedReport = None
            message: str = ""

            def __post_init__(self):
                if self.report is None:
                    self.report = FailedReport()

        with patch("teaching.core.exercise_generator.generate_exercises") as mock_gen, \
             patch("teaching.core.grader.grade_attempt") as mock_grade, \
             patch("teaching.cli.commands._ask_question") as mock_ask, \
             patch("teaching.cli.commands._submit_interactive_attempt") as mock_submit:

            mock_gen.return_value = mock_exercise_result
            mock_grade.return_value = FailedGradeResult()
            mock_ask.return_value = 0
            mock_submit.return_value = {"attempt_id": "test-attempt-01"}

            result = _run_unit_mini_quiz(
                unit_id="test-book-ch01-u01",
                data_dir=tmp_path,
                provider="lmstudio",
                model="test-model",
                console_obj=mock_console,
            )

            assert result is False
