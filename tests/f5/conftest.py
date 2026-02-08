"""Fixtures for F5 tests - Exercise Generation, Submission, and Grading."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_exercise_response() -> dict[str, Any]:
    """Standard mock response for exercise generation."""
    return {
        "exercises": [
            {
                "type": "multiple_choice",
                "difficulty": "easy",
                "question": "¿Qué significa LLM?",
                "options": [
                    "Large Language Model",
                    "Low Latency Memory",
                    "Linear Logic Machine",
                    "Language Learning Module",
                ],
                "correct_answer": 0,
                "explanation": "LLM significa Large Language Model (Modelo de Lenguaje Grande).",
                "points": 1,
                "tags": ["llm", "definición"],
            },
            {
                "type": "true_false",
                "difficulty": "easy",
                "question": "Los transformers procesan secuencias de forma secuencial como las RNNs.",
                "options": None,
                "correct_answer": False,
                "explanation": "Los transformers procesan todas las posiciones en paralelo, no secuencialmente.",
                "points": 1,
                "tags": ["transformer", "arquitectura"],
            },
            {
                "type": "short_answer",
                "difficulty": "medium",
                "question": "Explica brevemente qué es el mecanismo de atención en transformers.",
                "options": None,
                "correct_answer": "El mecanismo de atención permite al modelo enfocarse en partes relevantes de la entrada al generar cada parte de la salida.",
                "explanation": "La atención es fundamental para capturar dependencias a larga distancia.",
                "points": 2,
                "tags": ["atención", "transformer"],
            },
            {
                "type": "multiple_choice",
                "difficulty": "medium",
                "question": "¿Cuál de los siguientes NO es un componente típico de un LLM?",
                "options": [
                    "Capa de embedding",
                    "Bloques transformer",
                    "Capa de pooling convolucional",
                    "Capa de salida",
                ],
                "correct_answer": 2,
                "explanation": "Las capas de pooling convolucional son típicas de CNNs, no de LLMs basados en transformers.",
                "points": 1,
                "tags": ["llm", "arquitectura"],
            },
            {
                "type": "true_false",
                "difficulty": "hard",
                "question": "El entrenamiento de LLMs típicamente usa el objetivo de predecir el siguiente token.",
                "options": None,
                "correct_answer": True,
                "explanation": "Language modeling (predecir el siguiente token) es el objetivo típico de entrenamiento.",
                "points": 1,
                "tags": ["entrenamiento", "llm"],
            },
        ]
    }


@pytest.fixture
def mock_grade_response() -> dict[str, Any]:
    """Standard mock response for LLM grading of short answer."""
    return {
        "is_correct": True,
        "score": 0.85,
        "feedback": "Buena explicación. Capturas la idea principal del mecanismo de atención. Podrías mencionar también que permite capturar dependencias a larga distancia.",
        "confidence": 0.9,
    }


@pytest.fixture
def mock_llm_client(mock_exercise_response, mock_grade_response):
    """Mock LLM client for exercise generation and grading."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"

    # is_available returns True
    client.is_available.return_value = True

    # simple_json returns exercise set
    client.simple_json.return_value = mock_exercise_response

    # simple_chat returns text (for fallback scenarios)
    client.simple_chat.return_value = json.dumps(mock_exercise_response)

    return client


@pytest.fixture
def mock_llm_client_for_grading(mock_grade_response):
    """Mock LLM client specifically for grading tests."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"

    client.is_available.return_value = True
    client.simple_json.return_value = mock_grade_response
    client.simple_chat.return_value = json.dumps(mock_grade_response)

    return client


@pytest.fixture
def sample_book_with_notes(tmp_path) -> Path:
    """Create a sample book structure with notes (extends F4 pattern for F5)."""
    book_id = "test-book"
    book_path = tmp_path / "data" / "books" / book_id

    # Create directories
    (book_path / "source").mkdir(parents=True)
    (book_path / "normalized" / "pages").mkdir(parents=True)
    (book_path / "outline").mkdir(parents=True)
    (book_path / "artifacts" / "units").mkdir(parents=True)
    (book_path / "artifacts" / "notes").mkdir(parents=True)
    (book_path / "artifacts" / "exercises").mkdir(parents=True)
    (book_path / "artifacts" / "attempts").mkdir(parents=True)
    (book_path / "artifacts" / "grades").mkdir(parents=True)

    # Create book.json
    book_json = {
        "book_id": book_id,
        "title": "Test Book",
        "authors": ["Test Author"],
        "language": "en",
        "source_format": "pdf",
    }
    (book_path / "book.json").write_text(json.dumps(book_json, indent=2))

    # Create outline.json with proper structure
    outline = {
        "$schema": "outline_v1",
        "book_id": book_id,
        "chapters": [
            {
                "chapter_id": f"{book_id}:ch:1",
                "number": 1,
                "title": "Introduction to LLMs",
                "start_page": 1,
                "sections": [
                    {
                        "section_id": f"{book_id}:ch:1:sec:1",
                        "number": "1.1",
                        "title": "What are LLMs",
                        "start_page": 2,
                    },
                    {
                        "section_id": f"{book_id}:ch:1:sec:2",
                        "number": "1.2",
                        "title": "Transformer Architecture",
                        "start_page": 5,
                    },
                    {
                        "section_id": f"{book_id}:ch:1:sec:3",
                        "number": "1.3",
                        "title": "Training Process",
                        "start_page": 10,
                    },
                ],
            },
        ],
    }
    (book_path / "outline" / "outline.json").write_text(json.dumps(outline, indent=2))

    # Create units.json
    units = {
        "$schema": "units_v1.1",
        "book_id": book_id,
        "units": [
            {
                "unit_id": f"{book_id}-ch01-u01",
                "chapter_id": f"{book_id}:ch:1",
                "chapter_number": 1,
                "title": "Ch1 — Introduction to LLMs",
                "section_ids": [
                    f"{book_id}:ch:1:sec:1",
                    f"{book_id}:ch:1:sec:2",
                    f"{book_id}:ch:1:sec:3",
                ],
                "estimated_time_min": 14,
                "difficulty": "intro",
            },
        ],
    }
    (book_path / "artifacts" / "units" / "units.json").write_text(
        json.dumps(units, indent=2)
    )

    # Create normalized page files with content
    sample_content = """
What are LLMs

Large Language Models (LLMs) are a type of artificial intelligence model that have been
trained on vast amounts of text data. They are capable of understanding and generating
human-like text, making them useful for a variety of applications.

LLMs are based on the transformer architecture, which was introduced in the paper
"Attention is All You Need" by Vaswani et al. in 2017. This architecture uses
self-attention mechanisms to process input sequences in parallel, making it much more
efficient than previous recurrent neural network approaches.

The key components of an LLM include:
1. An embedding layer that converts tokens to vectors
2. Multiple transformer blocks with attention and feedforward layers
3. A final output layer that generates probability distributions over the vocabulary

Transformer Architecture

The transformer architecture revolutionized natural language processing. Unlike RNNs,
transformers can process all positions of a sequence simultaneously, enabling much
faster training on modern hardware.

The attention mechanism allows the model to focus on relevant parts of the input when
generating each part of the output. This is particularly useful for tasks like machine
translation, where understanding context is crucial.

Training Process

Training an LLM requires:
- Large datasets (billions of tokens)
- Significant computational resources (thousands of GPUs)
- Careful hyperparameter tuning
- Techniques like learning rate warmup and dropout

The training objective is typically to predict the next token in a sequence, which is
called language modeling. This simple objective, when applied at scale, leads to
emergent capabilities in understanding and reasoning.
"""

    # Create multiple page files
    lines = sample_content.strip().split("\n")
    lines_per_page = 10

    for page_num in range(1, 16):
        start_idx = (page_num - 1) * lines_per_page
        end_idx = start_idx + lines_per_page
        page_content = (
            "\n".join(lines[start_idx:end_idx]) if start_idx < len(lines) else ""
        )
        page_file = book_path / "normalized" / "pages" / f"{page_num:04d}.txt"
        page_file.write_text(page_content)

    # Create content.txt as well
    (book_path / "normalized" / "content.txt").write_text(sample_content)

    # Create notes metadata (simulating F4 output)
    notes_metadata = {
        "unit_id": f"{book_id}-ch01-u01",
        "book_id": book_id,
        "provider": "lmstudio",
        "model": "test-model",
        "pages_used": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        "start_page": 1,
        "end_page": 15,
        "chunks_processed": 2,
        "total_tokens": None,
        "generation_time_ms": 5000,
        "created_at": "2026-02-02T10:00:00+00:00",
        "chunk_modes": {"json": 2, "text_fallback": 0, "error": 0},
    }
    (book_path / "artifacts" / "notes" / f"{book_id}-ch01-u01.json").write_text(
        json.dumps(notes_metadata, indent=2)
    )

    return tmp_path / "data"


@pytest.fixture
def sample_exercise_set(sample_book_with_notes, mock_exercise_response) -> dict:
    """Create a pre-existing exercise set for testing submissions."""
    book_id = "test-book"
    exercise_set_id = f"{book_id}-ch01-u01-ex01"

    exercises = []
    for i, ex in enumerate(mock_exercise_response["exercises"], 1):
        exercises.append(
            {
                "exercise_id": f"{exercise_set_id}-q{i:02d}",
                **ex,
            }
        )

    exercise_set = {
        "$schema": "exercise_set_v1",
        "exercise_set_id": exercise_set_id,
        "unit_id": f"{book_id}-ch01-u01",
        "book_id": book_id,
        "created_at": "2026-02-02T10:00:00+00:00",
        "provider": "lmstudio",
        "model": "test-model",
        "difficulty": "mid",
        "types": ["quiz"],
        "generation_time_ms": 3000,
        "mode": "json",
        "pages_used": list(range(1, 16)),
        "exercises": exercises,
        "total_points": sum(ex["points"] for ex in exercises),
        "passing_threshold": 0.7,
    }

    # Save to file
    exercises_path = (
        sample_book_with_notes
        / "books"
        / book_id
        / "artifacts"
        / "exercises"
        / f"{exercise_set_id}.json"
    )
    exercises_path.write_text(json.dumps(exercise_set, indent=2))

    return exercise_set


@pytest.fixture
def sample_answers_file(tmp_path, sample_exercise_set) -> Path:
    """Create a sample answers JSON file for submission."""
    exercise_set_id = sample_exercise_set["exercise_set_id"]
    exercises = sample_exercise_set["exercises"]

    # Create answers for each exercise
    answers = {
        "answers": [
            {
                "exercise_id": exercises[0]["exercise_id"],  # MC - correct
                "response": 0,
                "time_taken_seconds": 30,
            },
            {
                "exercise_id": exercises[1]["exercise_id"],  # TF - correct
                "response": False,
                "time_taken_seconds": 15,
            },
            {
                "exercise_id": exercises[2]["exercise_id"],  # Short answer
                "response": "El mecanismo de atención permite al modelo enfocarse en partes relevantes de la entrada.",
                "time_taken_seconds": 120,
            },
            {
                "exercise_id": exercises[3]["exercise_id"],  # MC - correct
                "response": 2,
                "time_taken_seconds": 45,
            },
            {
                "exercise_id": exercises[4]["exercise_id"],  # TF - correct
                "response": True,
                "time_taken_seconds": 20,
            },
        ]
    }

    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(answers, indent=2))

    return answers_path


@pytest.fixture
def sample_attempt(sample_book_with_notes, sample_exercise_set, sample_answers_file) -> dict:
    """Create a pre-existing attempt for grading tests."""
    import json

    book_id = "test-book"
    exercise_set_id = sample_exercise_set["exercise_set_id"]
    attempt_id = f"{exercise_set_id}-a01"

    # Load answers
    with open(sample_answers_file) as f:
        answers_data = json.load(f)

    attempt = {
        "$schema": "attempt_v1",
        "attempt_id": attempt_id,
        "exercise_set_id": exercise_set_id,
        "unit_id": f"{book_id}-ch01-u01",
        "book_id": book_id,
        "created_at": "2026-02-02T11:00:00+00:00",
        "status": "pending",
        "answers": answers_data["answers"],
        "total_questions": len(answers_data["answers"]),
    }

    # Save to file
    attempts_path = (
        sample_book_with_notes
        / "books"
        / book_id
        / "artifacts"
        / "attempts"
        / f"{attempt_id}.json"
    )
    attempts_path.write_text(json.dumps(attempt, indent=2))

    return attempt
