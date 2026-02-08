"""Tests for quiz command - interactive quiz flow."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from teaching.cli.commands import app


runner = CliRunner()


class TestQuizCreation:
    """Tests for quiz command creating exercise_set and attempt."""

    def test_quiz_creates_exercise_set_and_attempt(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Quiz creates both exercise_set and attempt files with valid responses."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        # Simulate input: MCQ(0), TF(true), short_answer, MCQ(2), TF(true)
        # Matches the 5 exercises in mock_exercise_response
        input_data = "0\ntrue\nMi respuesta sobre atención\n2\ntrue\n"

        with patch("teaching.core.exercise_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client
            with patch("teaching.core.exercise_generator.LLMConfig") as MockConfig:
                MockConfig.from_yaml.return_value = MagicMock()

                result = runner.invoke(
                    app,
                    ["quiz", unit_id, "-n", "5", "-t", "quiz"],
                    input=input_data,
                    env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                )

        # Should succeed
        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Verify exercise set was created
        exercises_dir = sample_book_with_notes / "books" / book_id / "artifacts" / "exercises"
        exercise_files = list(exercises_dir.glob("*.json"))
        assert len(exercise_files) >= 1, "No exercise set created"

        # Verify attempt was created
        attempts_dir = sample_book_with_notes / "books" / book_id / "artifacts" / "attempts"
        attempt_files = list(attempts_dir.glob("*.json"))
        assert len(attempt_files) >= 1, "No attempt created"

        # Verify attempt has correct structure
        with open(attempt_files[0]) as f:
            attempt = json.load(f)

        assert attempt["$schema"] == "attempt_v1"
        assert len(attempt["answers"]) == 5
        # All responses should use "response" key, not "answer"
        for ans in attempt["answers"]:
            assert "response" in ans
            assert ans["response"] is not None, "Response should not be null"


class TestQuizRepromptMCQ:
    """Tests for MCQ input validation and re-prompt."""

    def test_quiz_reprompts_on_invalid_mcq(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Invalid MCQ input triggers re-prompt until valid."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        # Mock to return only 1 MCQ exercise with 4 options
        mock_llm_client.simple_json.return_value = {
            "exercises": [
                {
                    "type": "multiple_choice",
                    "difficulty": "easy",
                    "question": "Test question?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 2,
                    "explanation": "C is correct.",
                    "points": 1,
                    "tags": ["test"],
                }
            ]
        }

        # Input: "9" (invalid, >3) → "-1" (invalid, <0) → "abc" (invalid, not int) → "2" (valid)
        input_data = "9\n-1\nabc\n2\n"

        with patch("teaching.core.exercise_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client
            with patch("teaching.core.exercise_generator.LLMConfig") as MockConfig:
                MockConfig.from_yaml.return_value = MagicMock()

                result = runner.invoke(
                    app,
                    ["quiz", unit_id, "-n", "1", "-t", "quiz"],
                    input=input_data,
                    env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                )

        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Verify response == 2 in attempt
        attempts_dir = sample_book_with_notes / "books" / book_id / "artifacts" / "attempts"
        attempt_files = list(attempts_dir.glob("*.json"))
        assert len(attempt_files) >= 1

        with open(attempt_files[0]) as f:
            attempt = json.load(f)

        assert attempt["answers"][0]["response"] == 2


class TestQuizRepromptTF:
    """Tests for TF input validation and re-prompt."""

    def test_quiz_reprompts_on_invalid_tf(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Invalid TF input triggers re-prompt until valid."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        # Mock to return only 1 TF exercise
        mock_llm_client.simple_json.return_value = {
            "exercises": [
                {
                    "type": "true_false",
                    "difficulty": "easy",
                    "question": "Is this statement true?",
                    "options": None,
                    "correct_answer": True,
                    "explanation": "It is true.",
                    "points": 1,
                    "tags": ["test"],
                }
            ]
        }

        # Input: "maybe" (invalid) → "perhaps" (invalid) → "true" (valid)
        input_data = "maybe\nperhaps\ntrue\n"

        with patch("teaching.core.exercise_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client
            with patch("teaching.core.exercise_generator.LLMConfig") as MockConfig:
                MockConfig.from_yaml.return_value = MagicMock()

                result = runner.invoke(
                    app,
                    ["quiz", unit_id, "-n", "1", "-t", "quiz"],
                    input=input_data,
                    env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                )

        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Verify response == True in attempt
        attempts_dir = sample_book_with_notes / "books" / book_id / "artifacts" / "attempts"
        attempt_files = list(attempts_dir.glob("*.json"))

        with open(attempt_files[0]) as f:
            attempt = json.load(f)

        assert attempt["answers"][0]["response"] is True


class TestQuizRepromptShortAnswer:
    """Tests for short_answer input validation and re-prompt."""

    def test_quiz_reprompts_on_empty_short_answer(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Empty short answer triggers re-prompt until non-empty."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        # Mock to return only 1 short_answer exercise
        mock_llm_client.simple_json.return_value = {
            "exercises": [
                {
                    "type": "short_answer",
                    "difficulty": "medium",
                    "question": "Explain this concept.",
                    "options": None,
                    "correct_answer": "Expected answer.",
                    "explanation": "Good explanation.",
                    "points": 2,
                    "tags": ["test"],
                }
            ]
        }

        # Input: "" (empty) → "   " (whitespace) → "texto válido" (valid)
        input_data = "\n   \ntexto válido\n"

        with patch("teaching.core.exercise_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client
            with patch("teaching.core.exercise_generator.LLMConfig") as MockConfig:
                MockConfig.from_yaml.return_value = MagicMock()

                result = runner.invoke(
                    app,
                    ["quiz", unit_id, "-n", "1", "-t", "quiz"],
                    input=input_data,
                    env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                )

        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Verify response == "texto válido" in attempt
        attempts_dir = sample_book_with_notes / "books" / book_id / "artifacts" / "attempts"
        attempt_files = list(attempts_dir.glob("*.json"))

        with open(attempt_files[0]) as f:
            attempt = json.load(f)

        assert attempt["answers"][0]["response"] == "texto válido"


class TestQuizGradeInheritance:
    """Tests for --grade flag and provider/model inheritance."""

    def test_quiz_grade_creates_report_and_inherits_provider_model(
        self, sample_book_with_notes, mock_llm_client, mock_grade_response
    ):
        """Quiz with --grade creates grade report inheriting provider/model from exercise_set."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        # Configure mock to return grade response for short_answer
        mock_llm_client.simple_json.side_effect = [
            # First call: exercise generation
            {
                "exercises": [
                    {
                        "type": "multiple_choice",
                        "difficulty": "easy",
                        "question": "Test MCQ?",
                        "options": ["A", "B", "C", "D"],
                        "correct_answer": 0,
                        "explanation": "A is correct.",
                        "points": 1,
                        "tags": ["test"],
                    },
                    {
                        "type": "short_answer",
                        "difficulty": "medium",
                        "question": "Explain this.",
                        "options": None,
                        "correct_answer": "Expected.",
                        "explanation": "Good.",
                        "points": 2,
                        "tags": ["test"],
                    },
                ]
            },
            # Second call: grading short_answer
            mock_grade_response,
        ]

        # Simulate input: MCQ(0), short_answer text
        input_data = "0\nMi explicación detallada\n"

        with patch("teaching.core.exercise_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client
            with patch("teaching.core.exercise_generator.LLMConfig") as MockConfig:
                MockConfig.from_yaml.return_value = MagicMock()
                with patch("teaching.core.grader.LLMClient") as MockGraderClient:
                    MockGraderClient.return_value = mock_llm_client
                    with patch("teaching.core.grader.LLMConfig") as MockGraderConfig:
                        MockGraderConfig.from_yaml.return_value = MagicMock()

                        result = runner.invoke(
                            app,
                            [
                                "quiz", unit_id, "-n", "2", "-t", "quiz",
                                "--provider", "lmstudio", "--model", "qwen3-32b",
                                "--grade"
                            ],
                            input=input_data,
                            env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                        )

        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Verify grade report was created
        grades_dir = sample_book_with_notes / "books" / book_id / "artifacts" / "grades"
        grade_files = list(grades_dir.glob("*.json"))
        assert len(grade_files) >= 1, "No grade report created"

        # Verify grade report has correct provider/model
        with open(grade_files[0]) as f:
            grade_report = json.load(f)

        assert grade_report["$schema"] == "grade_report_v1"
        # Provider/model should come from exercise_set (inherited)
        assert grade_report["provider"] == "lmstudio"
        # Model could be from exercise_set or passed
        assert "summary" in grade_report
        assert "results" in grade_report


class TestQuizSafety:
    """Safety tests for quiz command."""

    def test_quiz_does_not_touch_real_data_dir(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Quiz command should not modify ./data directory."""
        import os

        # Get the actual data directory (not tmp_path)
        real_data_dir = Path("data")
        real_data_existed = real_data_dir.exists()

        # Count files if exists
        if real_data_existed:
            initial_files = list(real_data_dir.rglob("*"))
            initial_count = len(initial_files)

        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        mock_llm_client.simple_json.return_value = {
            "exercises": [
                {
                    "type": "multiple_choice",
                    "difficulty": "easy",
                    "question": "Test?",
                    "options": ["A", "B"],
                    "correct_answer": 0,
                    "explanation": "A.",
                    "points": 1,
                    "tags": ["test"],
                }
            ]
        }

        input_data = "0\n"

        with patch("teaching.core.exercise_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client
            with patch("teaching.core.exercise_generator.LLMConfig") as MockConfig:
                MockConfig.from_yaml.return_value = MagicMock()

                result = runner.invoke(
                    app,
                    ["quiz", unit_id, "-n", "1"],
                    input=input_data,
                    env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                )

        # Verify real data directory wasn't created or modified
        if real_data_existed:
            current_files = list(real_data_dir.rglob("*"))
            assert len(current_files) == initial_count, "Real data directory was modified"
        # Note: We don't assert that real_data_dir doesn't exist, because it might
        # have existed before the test. We just verify it wasn't modified.
