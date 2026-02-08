"""Tests for exam CLI commands (F6)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from teaching.cli.commands import app

runner = CliRunner()


class TestExamCommand:
    """Tests for teach exam command."""

    def test_exam_command_generates_file(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """exam command generates exam set file."""
        with patch("teaching.core.chapter_exam_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client_for_exams
            with patch("teaching.core.chapter_exam_generator.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "test-model"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["exam", "test-book", "--chapter", "ch01", "-n", "12"],
                        env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
                    )

        assert result.exit_code == 0
        assert "exam" in result.output.lower()

    def test_exam_command_shows_llm_info(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """exam command shows LLM provider/model info."""
        with patch("teaching.core.chapter_exam_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client_for_exams
            with patch("teaching.core.chapter_exam_generator.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "test-model"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["exam", "test-book", "--chapter", "ch01"],
                        env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
                    )

        assert result.exit_code == 0
        assert "LLM:" in result.output


class TestExamQuizCommand:
    """Tests for teach exam-quiz command."""

    def test_exam_quiz_interactive_creates_attempt(
        self, sample_book_multi_unit_chapter, sample_exam_set, mock_llm_client_for_exam_grading
    ):
        """exam-quiz interactive mode creates attempt."""
        exam_set_id = sample_exam_set["exam_set_id"]

        # Input for 12 questions: 6 MCQ + 3 TF + 3 SA
        input_data = (
            # 6 MCQ answers (0-3)
            "0\n1\n2\n1\n1\n2\n"
            # 3 TF answers
            "false\ntrue\nfalse\n"
            # 3 SA answers
            "La atencion permite enfocarse en partes relevantes.\n"
            "Embedding, transformer blocks, output layer.\n"
            "Requiere muchos datos y GPUs.\n"
        )

        with patch("teaching.core.exam_grader.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client_for_exam_grading
            with patch("teaching.core.exam_grader.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "test-model"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["exam-quiz", exam_set_id, "--grade"],
                        input=input_data,
                        env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
                    )

        assert result.exit_code == 0

    def test_exam_quiz_reprompt_on_invalid_mcq(
        self, sample_book_multi_unit_chapter, sample_exam_set, mock_llm_client_for_exam_grading
    ):
        """exam-quiz re-prompts on invalid MCQ input."""
        exam_set_id = sample_exam_set["exam_set_id"]

        # First answer is invalid (5 out of range), then valid (0)
        # Then complete rest of questions
        input_data = (
            "5\n0\n"  # Invalid then valid for first MCQ
            "1\n2\n1\n1\n2\n"  # Rest of MCQ
            "false\ntrue\nfalse\n"  # TF
            "Answer 1\nAnswer 2\nAnswer 3\n"  # SA
        )

        with patch("teaching.core.exam_grader.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client_for_exam_grading
            with patch("teaching.core.exam_grader.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "test-model"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["exam-quiz", exam_set_id, "--grade"],
                        input=input_data,
                        env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
                    )

        # Should complete successfully despite initial invalid input
        assert result.exit_code == 0


class TestExamSubmitCommand:
    """Tests for teach exam-submit command."""

    def test_exam_submit_from_file(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_answers_file
    ):
        """exam-submit creates attempt from JSON file."""
        exam_set_id = sample_exam_set["exam_set_id"]

        result = runner.invoke(
            app,
            ["exam-submit", exam_set_id, "--answers", str(sample_exam_answers_file)],
            env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
        )

        assert result.exit_code == 0
        assert "guardado" in result.output.lower() or "submit" in result.output.lower()


class TestExamGradeCommand:
    """Tests for teach exam-grade command."""

    def test_exam_grade_creates_report(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """exam-grade creates grade report."""
        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]

        with patch("teaching.core.exam_grader.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client_for_exam_grading
            with patch("teaching.core.exam_grader.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "test-model"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["exam-grade", exam_attempt_id],
                        env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
                    )

        assert result.exit_code == 0
        assert "%" in result.output  # Should show percentage

    def test_exam_grade_default_strict(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """exam-grade defaults to strict mode."""
        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]

        with patch("teaching.core.exam_grader.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client_for_exam_grading
            with patch("teaching.core.exam_grader.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "test-model"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["exam-grade", exam_attempt_id],
                        env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
                    )

        assert result.exit_code == 0
        # Strict mode indicator should be shown
        assert "ESTRICTO" in result.output or "strict" in result.output.lower()


class TestExamReviewCommand:
    """Tests for teach exam-review command."""

    def test_exam_review_displays_summary(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """exam-review displays grade summary."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]

        # First, create a grade report
        grade_result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )
        assert grade_result.success

        # Now run exam-review
        result = runner.invoke(
            app,
            ["exam-review", exam_attempt_id],
            env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
        )

        assert result.exit_code == 0
        assert "%" in result.output

    def test_exam_review_shows_by_unit_breakdown(
        self, sample_book_multi_unit_chapter, sample_exam_set, sample_exam_attempt, mock_llm_client_for_exam_grading
    ):
        """exam-review shows breakdown by unit."""
        from teaching.core.exam_grader import grade_exam_attempt

        exam_attempt_id = sample_exam_attempt["exam_attempt_id"]

        grade_result = grade_exam_attempt(
            exam_attempt_id=exam_attempt_id,
            data_dir=sample_book_multi_unit_chapter,
            client=mock_llm_client_for_exam_grading,
        )
        assert grade_result.success

        result = runner.invoke(
            app,
            ["exam-review", exam_attempt_id],
            env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
        )

        assert result.exit_code == 0
        # Should show unit breakdown
        assert "u01" in result.output.lower() or "unidad" in result.output.lower()


class TestInheritDefaults:
    """Tests for provider/model defaults."""

    def test_exam_uses_config_defaults(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """exam command uses config defaults when no flags provided."""
        with patch("teaching.core.chapter_exam_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client_for_exams
            with patch("teaching.core.chapter_exam_generator.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "config-model"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["exam", "test-book", "--chapter", "ch01"],
                        env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
                    )

        assert result.exit_code == 0
        assert "lmstudio" in result.output


class TestSafetyNoRealData:
    """Tests ensuring real data is not touched."""

    def test_exam_command_does_not_touch_real_data(self, sample_book_multi_unit_chapter):
        """exam command does not modify ./data directory."""
        real_data_dir = Path("data")
        real_data_existed = real_data_dir.exists()

        initial_count = 0
        if real_data_existed:
            initial_files = list(real_data_dir.rglob("*"))
            initial_count = len(initial_files)

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"
        mock_client.simple_json.return_value = {"questions": []}

        with patch("teaching.core.chapter_exam_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_client
            with patch("teaching.core.chapter_exam_generator.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "test"
                mock_config.model = "test"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    runner.invoke(
                        app,
                        ["exam", "test-book", "--chapter", "ch01"],
                        env={"TEACHING_DATA_DIR": str(sample_book_multi_unit_chapter)},
                    )

        if real_data_existed:
            current_files = list(real_data_dir.rglob("*"))
            assert len(current_files) == initial_count, "Real data directory was modified"
