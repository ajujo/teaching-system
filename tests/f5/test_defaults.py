"""Tests for provider/model defaults resolution (F5 Polish)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from teaching.cli.commands import app, _resolve_provider_model

runner = CliRunner()


class TestResolveProviderModel:
    """Unit tests for _resolve_provider_model helper."""

    def test_resolve_returns_config_defaults_when_none_provided(self):
        """When both None, returns config defaults."""
        with patch("teaching.cli.commands.LLMConfig") as MockConfig:
            mock_config = MagicMock()
            mock_config.provider = "lmstudio"
            mock_config.model = "qwen3-32b"
            MockConfig.from_yaml.return_value = mock_config

            provider, model = _resolve_provider_model(None, None)

            assert provider == "lmstudio"
            assert model == "qwen3-32b"
            MockConfig.from_yaml.assert_called_once()

    def test_resolve_uses_provided_values_over_defaults(self):
        """Provided values override config defaults."""
        with patch("teaching.cli.commands.LLMConfig") as MockConfig:
            mock_config = MagicMock()
            mock_config.provider = "lmstudio"
            mock_config.model = "default"
            MockConfig.from_yaml.return_value = mock_config

            provider, model = _resolve_provider_model("openai", "gpt-4")

            assert provider == "openai"
            assert model == "gpt-4"

    def test_resolve_partial_override_provider_only(self):
        """Can override just provider, keep model from config."""
        with patch("teaching.cli.commands.LLMConfig") as MockConfig:
            mock_config = MagicMock()
            mock_config.provider = "lmstudio"
            mock_config.model = "qwen3-32b"
            MockConfig.from_yaml.return_value = mock_config

            provider, model = _resolve_provider_model("anthropic", None)

            assert provider == "anthropic"
            assert model == "qwen3-32b"  # From config

    def test_resolve_partial_override_model_only(self):
        """Can override just model, keep provider from config."""
        with patch("teaching.cli.commands.LLMConfig") as MockConfig:
            mock_config = MagicMock()
            mock_config.provider = "lmstudio"
            mock_config.model = "default"
            MockConfig.from_yaml.return_value = mock_config

            provider, model = _resolve_provider_model(None, "llama-3.1-70b")

            assert provider == "lmstudio"  # From config
            assert model == "llama-3.1-70b"


class TestExerciseCommandDefaults:
    """Test exercise command uses resolved defaults."""

    def test_exercise_uses_config_defaults_when_no_flags(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Exercise command uses config defaults when no --provider/--model passed."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        with patch("teaching.core.exercise_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client
            with patch("teaching.core.exercise_generator.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "test-model"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["exercise", unit_id, "-n", "2"],
                        env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                    )

        assert result.exit_code == 0
        # Verify output shows LLM info
        assert "LLM:" in result.output
        assert "lmstudio" in result.output

    def test_exercise_uses_flags_over_defaults(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Exercise command respects --provider/--model flags over defaults."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        with patch("teaching.core.exercise_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client
            with patch("teaching.core.exercise_generator.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "default"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        [
                            "exercise", unit_id, "-n", "2",
                            "--provider", "openai", "--model", "gpt-4"
                        ],
                        env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                    )

        assert result.exit_code == 0
        # Verify output shows overridden values
        assert "openai" in result.output
        assert "gpt-4" in result.output


class TestGradeCommandDefaults:
    """Test grade command uses resolved defaults."""

    def test_grade_uses_config_defaults_when_no_flags(
        self, sample_book_with_notes, sample_exercise_set, sample_attempt, mock_llm_client_for_grading
    ):
        """Grade command uses config defaults when no --provider/--model passed."""
        attempt_id = sample_attempt["attempt_id"]

        with patch("teaching.core.grader.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client_for_grading
            with patch("teaching.core.grader.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "test-grader"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["grade", attempt_id],
                        env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                    )

        assert result.exit_code == 0
        # Verify output shows LLM info
        assert "LLM:" in result.output


class TestQuizCommandDefaults:
    """Test quiz command uses resolved defaults."""

    def test_quiz_uses_config_defaults_when_no_flags(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Quiz command uses config defaults when no --provider/--model passed."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        # Input for 5 exercises (from default mock_exercise_response)
        input_data = "0\ntrue\nMi respuesta\n2\ntrue\n"

        with patch("teaching.core.exercise_generator.LLMClient") as MockLLMClient:
            MockLLMClient.return_value = mock_llm_client
            with patch("teaching.core.exercise_generator.LLMConfig") as MockConfig:
                mock_config = MagicMock()
                mock_config.provider = "lmstudio"
                mock_config.model = "quiz-model"
                MockConfig.from_yaml.return_value = mock_config
                with patch("teaching.cli.commands.LLMConfig") as MockCLIConfig:
                    MockCLIConfig.from_yaml.return_value = mock_config

                    result = runner.invoke(
                        app,
                        ["quiz", unit_id, "-n", "5"],
                        input=input_data,
                        env={"TEACHING_DATA_DIR": str(sample_book_with_notes)},
                    )

        assert result.exit_code == 0
        # Verify output shows LLM info
        assert "LLM:" in result.output
        assert "lmstudio" in result.output
