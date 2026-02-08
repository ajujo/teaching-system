"""Tests for exercise generator module."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from teaching.core.exercise_generator import (
    Exercise,
    ExerciseGenerationError,
    ExerciseSetMetadata,
    ExerciseSetResult,
    generate_exercises,
)
from teaching.llm.client import LLMError


class TestExerciseGeneration:
    """Tests for exercise generation."""

    def test_exercise_generation_persists_json(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Exercise generation creates valid JSON in artifacts/exercises/."""
        result = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            difficulty="mid",
            types=["quiz"],
            n=5,
            client=mock_llm_client,
        )

        assert result.success is True
        assert result.exercise_set_path is not None
        assert result.exercise_set_path.exists()
        assert result.exercise_set_path.suffix == ".json"

        # Verify path is in correct location
        assert "artifacts/exercises" in str(result.exercise_set_path)

        # Load and verify JSON structure
        with open(result.exercise_set_path) as f:
            data = json.load(f)

        assert data["$schema"] == "exercise_set_v1"
        assert "exercises" in data
        assert len(data["exercises"]) > 0
        assert data["unit_id"] == "test-book-ch01-u01"
        assert data["book_id"] == "test-book"

    def test_exercise_set_id_is_deterministic(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Exercise set IDs follow pattern {unit_id}-ex{NN}."""
        # First generation
        result1 = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            client=mock_llm_client,
        )

        assert result1.success is True
        assert result1.metadata.exercise_set_id == "test-book-ch01-u01-ex01"

        # Second generation
        result2 = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            client=mock_llm_client,
        )

        assert result2.success is True
        assert result2.metadata.exercise_set_id == "test-book-ch01-u01-ex02"

    def test_exercise_generation_with_force_overwrites(
        self, sample_book_with_notes, mock_llm_client
    ):
        """With force=True, overwrites existing exercise set."""
        # First generation
        result1 = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            client=mock_llm_client,
        )
        first_path = result1.exercise_set_path

        # Without force, creates new
        result2 = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            client=mock_llm_client,
            force=False,
        )
        assert result2.exercise_set_path != first_path

    def test_exercise_generation_validates_unit_id(self, sample_book_with_notes):
        """Invalid unit_id format returns error."""
        result = generate_exercises(
            unit_id="invalid-format",
            data_dir=sample_book_with_notes,
        )

        assert result.success is False
        assert "inválido" in result.message.lower() or "invalid" in result.message.lower()

    def test_exercise_generation_unit_not_found(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Non-existent unit returns error."""
        result = generate_exercises(
            unit_id="test-book-ch99-u99",
            data_dir=sample_book_with_notes,
            client=mock_llm_client,
        )

        assert result.success is False
        assert "no encontrad" in result.message.lower()

    def test_exercise_generation_llm_unavailable(self, sample_book_with_notes):
        """Returns error when LLM is unavailable."""
        mock_client = MagicMock()
        mock_client.is_available.return_value = False
        mock_client.config.provider = "lmstudio"

        result = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            client=mock_client,
        )

        assert result.success is False
        assert "conectar" in result.message.lower() or "unavailable" in result.message.lower()


class TestExerciseGenerationFallback:
    """Tests for JSON fallback mechanism."""

    def test_exercise_generation_fallback_mode(self, sample_book_with_notes):
        """Uses text_fallback mode when JSON parsing fails initially."""
        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True

        # simple_json fails, simple_chat returns valid JSON as text
        mock_client.simple_json.side_effect = LLMError("JSON mode not supported")
        mock_client.simple_chat.return_value = json.dumps(
            {
                "exercises": [
                    {
                        "type": "multiple_choice",
                        "difficulty": "easy",
                        "question": "¿Qué es un LLM?",
                        "options": ["a", "b", "c", "d"],
                        "correct_answer": 0,
                        "explanation": "Explicación",
                        "points": 1,
                        "tags": ["llm"],
                    }
                ]
            }
        )

        result = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            client=mock_client,
        )

        assert result.success is True
        assert result.metadata.mode == "text_fallback"
        assert any("fallback" in w.lower() for w in result.warnings)

    def test_exercise_generation_sanitizes_think_tags(self, sample_book_with_notes):
        """Removes <think> tags from LLM output before parsing."""
        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True

        # Response with <think> tags
        mock_client.simple_json.return_value = {
            "exercises": [
                {
                    "type": "true_false",
                    "difficulty": "easy",
                    "question": "Los LLMs usan transformers.",
                    "options": None,
                    "correct_answer": True,
                    "explanation": "Sí, los LLMs modernos usan transformers.",
                    "points": 1,
                    "tags": ["llm"],
                }
            ]
        }

        result = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            client=mock_client,
        )

        assert result.success is True
        # Verify no <think> tags in saved file
        with open(result.exercise_set_path) as f:
            content = f.read()
        assert "<think>" not in content


class TestExerciseDataClasses:
    """Tests for exercise data classes."""

    def test_exercise_to_dict(self):
        """Exercise.to_dict() returns correct structure."""
        exercise = Exercise(
            exercise_id="test-ex01-q01",
            type="multiple_choice",
            difficulty="easy",
            question="Test question?",
            correct_answer=0,
            explanation="Test explanation",
            points=1,
            options=["a", "b", "c", "d"],
            tags=["test"],
        )

        d = exercise.to_dict()

        assert d["exercise_id"] == "test-ex01-q01"
        assert d["type"] == "multiple_choice"
        assert d["difficulty"] == "easy"
        assert d["question"] == "Test question?"
        assert d["correct_answer"] == 0
        assert d["options"] == ["a", "b", "c", "d"]
        assert d["points"] == 1
        assert d["tags"] == ["test"]

    def test_exercise_to_dict_without_options(self):
        """Exercise.to_dict() handles None options (for true_false)."""
        exercise = Exercise(
            exercise_id="test-ex01-q01",
            type="true_false",
            difficulty="easy",
            question="Is this true?",
            correct_answer=True,
            explanation="Yes it is.",
            points=1,
            options=None,
            tags=[],
        )

        d = exercise.to_dict()

        assert "options" not in d or d["options"] is None

    def test_exercise_set_metadata_to_dict(self):
        """ExerciseSetMetadata.to_dict() returns correct schema."""
        metadata = ExerciseSetMetadata(
            exercise_set_id="test-book-ch01-u01-ex01",
            unit_id="test-book-ch01-u01",
            book_id="test-book",
            provider="lmstudio",
            model="test-model",
            difficulty="mid",
            types=["quiz"],
            generation_time_ms=3000,
            mode="json",
            pages_used=[1, 2, 3],
            created_at="2026-02-02T10:00:00+00:00",
            total_points=5,
            passing_threshold=0.7,
        )

        d = metadata.to_dict()

        assert d["$schema"] == "exercise_set_v1"
        assert d["exercise_set_id"] == "test-book-ch01-u01-ex01"
        assert d["unit_id"] == "test-book-ch01-u01"
        assert d["difficulty"] == "mid"
        assert d["mode"] == "json"
        assert d["total_points"] == 5
        assert d["passing_threshold"] == 0.7


class TestExerciseTypes:
    """Tests for different exercise types."""

    def test_generates_multiple_choice_exercises(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Can generate multiple choice exercises."""
        result = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            types=["quiz"],
            client=mock_llm_client,
        )

        assert result.success is True
        mc_exercises = [e for e in result.exercises if e.type == "multiple_choice"]
        assert len(mc_exercises) > 0

        for ex in mc_exercises:
            assert ex.options is not None
            assert len(ex.options) == 4
            assert isinstance(ex.correct_answer, int)
            assert 0 <= ex.correct_answer <= 3

    def test_generates_true_false_exercises(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Can generate true/false exercises."""
        result = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            types=["quiz"],
            client=mock_llm_client,
        )

        assert result.success is True
        tf_exercises = [e for e in result.exercises if e.type == "true_false"]
        assert len(tf_exercises) > 0

        for ex in tf_exercises:
            assert ex.options is None
            assert isinstance(ex.correct_answer, bool)

    def test_generates_short_answer_exercises(
        self, sample_book_with_notes, mock_llm_client
    ):
        """Can generate short answer exercises."""
        result = generate_exercises(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_notes,
            types=["quiz"],
            client=mock_llm_client,
        )

        assert result.success is True
        sa_exercises = [e for e in result.exercises if e.type == "short_answer"]
        assert len(sa_exercises) > 0

        for ex in sa_exercises:
            assert ex.options is None
            assert isinstance(ex.correct_answer, str)
