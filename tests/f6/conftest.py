"""Fixtures for F6 tests - Chapter Exams."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_exam_response() -> dict[str, Any]:
    """Standard mock response for chapter exam generation with 12 questions.

    Distribution: 6 MCQ + 3 TF + 3 SA (50% + 25% + 25%)
    Includes source tracking for each question.
    """
    return {
        "questions": [
            # 6 MCQ questions
            {
                "type": "multiple_choice",
                "difficulty": "easy",
                "question": "Que significa LLM?",
                "options": [
                    "Large Language Model",
                    "Low Latency Memory",
                    "Linear Logic Machine",
                    "Language Learning Module",
                ],
                "correct_answer": 0,
                "explanation": "LLM significa Large Language Model.",
                "points": 1,
                "tags": ["llm", "definicion"],
                "source": {
                    "unit_id": "test-book-ch01-u01",
                    "pages": [1, 2],
                    "section_ids": ["test-book:ch:1:sec:1"],
                    "rationale": "Definicion basica de LLM en seccion 1.1.",
                },
            },
            {
                "type": "multiple_choice",
                "difficulty": "medium",
                "question": "Cual es el componente principal de un transformer?",
                "options": [
                    "Capa de pooling",
                    "Mecanismo de atencion",
                    "Red recurrente",
                    "Filtro convolucional",
                ],
                "correct_answer": 1,
                "explanation": "El mecanismo de atencion es el componente central.",
                "points": 1,
                "tags": ["transformer", "arquitectura"],
                "source": {
                    "unit_id": "test-book-ch01-u02",
                    "pages": [5, 6],
                    "section_ids": ["test-book:ch:1:sec:2"],
                    "rationale": "Arquitectura transformer explicada en seccion 1.2.",
                },
            },
            {
                "type": "multiple_choice",
                "difficulty": "medium",
                "question": "Cual NO es una capa tipica de un LLM?",
                "options": [
                    "Embedding",
                    "Transformer block",
                    "Pooling convolucional",
                    "Output layer",
                ],
                "correct_answer": 2,
                "explanation": "Pooling convolucional es de CNNs, no de LLMs.",
                "points": 1,
                "tags": ["llm", "arquitectura"],
                "source": {
                    "unit_id": "test-book-ch01-u01",
                    "pages": [3, 4],
                    "section_ids": ["test-book:ch:1:sec:1"],
                    "rationale": "Componentes de LLM listados en seccion 1.1.",
                },
            },
            {
                "type": "multiple_choice",
                "difficulty": "hard",
                "question": "Cual es el objetivo tipico de entrenamiento de un LLM?",
                "options": [
                    "Clasificacion de imagenes",
                    "Prediccion del siguiente token",
                    "Regresion lineal",
                    "Clustering",
                ],
                "correct_answer": 1,
                "explanation": "Language modeling predice el siguiente token.",
                "points": 1,
                "tags": ["entrenamiento", "llm"],
                "source": {
                    "unit_id": "test-book-ch01-u03",
                    "pages": [10, 11],
                    "section_ids": ["test-book:ch:1:sec:3"],
                    "rationale": "Proceso de entrenamiento en seccion 1.3.",
                },
            },
            {
                "type": "multiple_choice",
                "difficulty": "easy",
                "question": "En que ano se introdujo la arquitectura transformer?",
                "options": [
                    "2015",
                    "2017",
                    "2019",
                    "2020",
                ],
                "correct_answer": 1,
                "explanation": "Transformers fueron introducidos en 2017 en 'Attention is All You Need'.",
                "points": 1,
                "tags": ["transformer", "historia"],
                "source": {
                    "unit_id": "test-book-ch01-u02",
                    "pages": [5],
                    "section_ids": ["test-book:ch:1:sec:2"],
                    "rationale": "Historia de transformers en seccion 1.2.",
                },
            },
            {
                "type": "multiple_choice",
                "difficulty": "hard",
                "question": "Cuantos tokens tipicamente se usan para entrenar un LLM grande?",
                "options": [
                    "Miles",
                    "Millones",
                    "Miles de millones",
                    "Cientos",
                ],
                "correct_answer": 2,
                "explanation": "Los LLMs grandes se entrenan con miles de millones de tokens.",
                "points": 1,
                "tags": ["entrenamiento", "escala"],
                "source": {
                    "unit_id": "test-book-ch01-u03",
                    "pages": [11, 12],
                    "section_ids": ["test-book:ch:1:sec:3"],
                    "rationale": "Escala de entrenamiento en seccion 1.3.",
                },
            },
            # 3 TF questions
            {
                "type": "true_false",
                "difficulty": "easy",
                "question": "Los transformers procesan secuencias de forma secuencial como las RNNs.",
                "options": None,
                "correct_answer": False,
                "explanation": "Los transformers procesan todas las posiciones en paralelo.",
                "points": 1,
                "tags": ["transformer", "arquitectura"],
                "source": {
                    "unit_id": "test-book-ch01-u02",
                    "pages": [6, 7],
                    "section_ids": ["test-book:ch:1:sec:2"],
                    "rationale": "Diferencias con RNNs explicadas en seccion 1.2.",
                },
            },
            {
                "type": "true_false",
                "difficulty": "medium",
                "question": "El entrenamiento de LLMs tipicamente usa prediccion del siguiente token.",
                "options": None,
                "correct_answer": True,
                "explanation": "Language modeling es el objetivo tipico de entrenamiento.",
                "points": 1,
                "tags": ["entrenamiento", "llm"],
                "source": {
                    "unit_id": "test-book-ch01-u03",
                    "pages": [12, 13],
                    "section_ids": ["test-book:ch:1:sec:3"],
                    "rationale": "Objetivo de entrenamiento en seccion 1.3.",
                },
            },
            {
                "type": "true_false",
                "difficulty": "hard",
                "question": "El mecanismo de atencion permite capturar dependencias a larga distancia.",
                "options": None,
                "correct_answer": True,
                "explanation": "La atencion captura relaciones entre posiciones distantes.",
                "points": 1,
                "tags": ["atencion", "transformer"],
                "source": {
                    "unit_id": "test-book-ch01-u02",
                    "pages": [7, 8],
                    "section_ids": ["test-book:ch:1:sec:2"],
                    "rationale": "Capacidades de atencion en seccion 1.2.",
                },
            },
            # 3 SA questions
            {
                "type": "short_answer",
                "difficulty": "medium",
                "question": "Explica brevemente que es el mecanismo de atencion en transformers.",
                "options": None,
                "correct_answer": "El mecanismo de atencion permite al modelo enfocarse en partes relevantes de la entrada al generar cada parte de la salida.",
                "explanation": "La atencion es fundamental para capturar dependencias.",
                "points": 2,
                "tags": ["atencion", "transformer"],
                "source": {
                    "unit_id": "test-book-ch01-u02",
                    "pages": [6, 7, 8],
                    "section_ids": ["test-book:ch:1:sec:2"],
                    "rationale": "Mecanismo de atencion detallado en seccion 1.2.",
                },
            },
            {
                "type": "short_answer",
                "difficulty": "hard",
                "question": "Describe los tres componentes principales de un LLM basado en transformers.",
                "options": None,
                "correct_answer": "Los tres componentes principales son: 1) Capa de embedding que convierte tokens a vectores, 2) Bloques transformer con atencion y feedforward, 3) Capa de salida que genera distribuciones de probabilidad.",
                "explanation": "Estos componentes forman la estructura basica de un LLM.",
                "points": 2,
                "tags": ["llm", "arquitectura"],
                "source": {
                    "unit_id": "test-book-ch01-u01",
                    "pages": [2, 3, 4],
                    "section_ids": ["test-book:ch:1:sec:1"],
                    "rationale": "Arquitectura de LLM en seccion 1.1.",
                },
            },
            {
                "type": "short_answer",
                "difficulty": "medium",
                "question": "Por que el entrenamiento de LLMs requiere tantos recursos computacionales?",
                "options": None,
                "correct_answer": "El entrenamiento requiere muchos recursos porque: 1) Se usan datasets de miles de millones de tokens, 2) Los modelos tienen miles de millones de parametros, 3) Se necesitan miles de GPUs y semanas de entrenamiento.",
                "explanation": "La escala es clave para las capacidades emergentes.",
                "points": 2,
                "tags": ["entrenamiento", "escala"],
                "source": {
                    "unit_id": "test-book-ch01-u03",
                    "pages": [10, 11, 12, 13],
                    "section_ids": ["test-book:ch:1:sec:3"],
                    "rationale": "Recursos de entrenamiento en seccion 1.3.",
                },
            },
        ]
    }


@pytest.fixture
def mock_exam_grade_response() -> dict[str, Any]:
    """Standard mock response for LLM grading of short answer."""
    return {
        "is_correct": True,
        "score": 0.85,
        "feedback": "Buena explicacion. Capturas la idea principal.",
        "confidence": 0.9,
    }


@pytest.fixture
def mock_llm_client_for_exams(mock_exam_response, mock_exam_grade_response):
    """Mock LLM client for exam generation and grading."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"

    client.is_available.return_value = True
    client.simple_json.return_value = mock_exam_response
    client.simple_chat.return_value = json.dumps(mock_exam_response)

    return client


@pytest.fixture
def mock_llm_client_for_exam_grading(mock_exam_grade_response):
    """Mock LLM client specifically for exam grading tests."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"

    client.is_available.return_value = True
    client.simple_json.return_value = mock_exam_grade_response
    client.simple_chat.return_value = json.dumps(mock_exam_grade_response)

    return client


@pytest.fixture
def sample_book_multi_unit_chapter(tmp_path) -> Path:
    """Create a sample book with ch01 containing 3 units (u01, u02, u03).

    This extends the F5 sample_book_with_notes pattern to have multiple units
    within the same chapter, which is required for testing chapter exams.
    """
    book_id = "test-book"
    book_path = tmp_path / "data" / "books" / book_id

    # Create directories
    (book_path / "source").mkdir(parents=True)
    (book_path / "normalized" / "pages").mkdir(parents=True)
    (book_path / "outline").mkdir(parents=True)
    (book_path / "artifacts" / "units").mkdir(parents=True)
    (book_path / "artifacts" / "notes").mkdir(parents=True)
    (book_path / "artifacts" / "exams").mkdir(parents=True)
    (book_path / "artifacts" / "exam_attempts").mkdir(parents=True)
    (book_path / "artifacts" / "exam_grades").mkdir(parents=True)

    # Create book.json
    book_json = {
        "book_id": book_id,
        "title": "Test Book",
        "authors": ["Test Author"],
        "language": "en",
        "source_format": "pdf",
    }
    (book_path / "book.json").write_text(json.dumps(book_json, indent=2))

    # Create outline.json with 3 sections for the chapter
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
                        "start_page": 1,
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
            {
                "chapter_id": f"{book_id}:ch:2",
                "number": 2,
                "title": "Advanced Topics",
                "start_page": 15,
                "sections": [
                    {
                        "section_id": f"{book_id}:ch:2:sec:1",
                        "number": "2.1",
                        "title": "Fine-tuning",
                        "start_page": 15,
                    },
                ],
            },
        ],
    }
    (book_path / "outline" / "outline.json").write_text(json.dumps(outline, indent=2))

    # Create units.json with 3 units in ch01 (plus 1 in ch02)
    units = {
        "$schema": "units_v1.1",
        "book_id": book_id,
        "units": [
            {
                "unit_id": f"{book_id}-ch01-u01",
                "chapter_id": f"{book_id}:ch:1",
                "chapter_number": 1,
                "title": "Ch1.1 - What are LLMs",
                "section_ids": [f"{book_id}:ch:1:sec:1"],
                "estimated_time_min": 10,
                "difficulty": "intro",
            },
            {
                "unit_id": f"{book_id}-ch01-u02",
                "chapter_id": f"{book_id}:ch:1",
                "chapter_number": 1,
                "title": "Ch1.2 - Transformer Architecture",
                "section_ids": [f"{book_id}:ch:1:sec:2"],
                "estimated_time_min": 12,
                "difficulty": "mid",
            },
            {
                "unit_id": f"{book_id}-ch01-u03",
                "chapter_id": f"{book_id}:ch:1",
                "chapter_number": 1,
                "title": "Ch1.3 - Training Process",
                "section_ids": [f"{book_id}:ch:1:sec:3"],
                "estimated_time_min": 15,
                "difficulty": "adv",
            },
            {
                "unit_id": f"{book_id}-ch02-u01",
                "chapter_id": f"{book_id}:ch:2",
                "chapter_number": 2,
                "title": "Ch2.1 - Fine-tuning",
                "section_ids": [f"{book_id}:ch:2:sec:1"],
                "estimated_time_min": 20,
                "difficulty": "adv",
            },
        ],
    }
    (book_path / "artifacts" / "units" / "units.json").write_text(
        json.dumps(units, indent=2)
    )

    # Create normalized page files with content (pages 1-15 for ch01)
    sample_content_u01 = """What are LLMs

Large Language Models (LLMs) are a type of artificial intelligence model that have been
trained on vast amounts of text data. They are capable of understanding and generating
human-like text, making them useful for a variety of applications.

The key components of an LLM include:
1. An embedding layer that converts tokens to vectors
2. Multiple transformer blocks with attention and feedforward layers
3. A final output layer that generates probability distributions over the vocabulary
"""

    sample_content_u02 = """Transformer Architecture

The transformer architecture revolutionized natural language processing. Unlike RNNs,
transformers can process all positions of a sequence simultaneously, enabling much
faster training on modern hardware.

LLMs are based on the transformer architecture, which was introduced in the paper
"Attention is All You Need" by Vaswani et al. in 2017. This architecture uses
self-attention mechanisms to process input sequences in parallel.

The attention mechanism allows the model to focus on relevant parts of the input when
generating each part of the output. This is particularly useful for tasks like machine
translation, where understanding context is crucial.
"""

    sample_content_u03 = """Training Process

Training an LLM requires:
- Large datasets (billions of tokens)
- Significant computational resources (thousands of GPUs)
- Careful hyperparameter tuning
- Techniques like learning rate warmup and dropout

The training objective is typically to predict the next token in a sequence, which is
called language modeling. This simple objective, when applied at scale, leads to
emergent capabilities in understanding and reasoning.
"""

    # Write pages (1-4 for u01, 5-9 for u02, 10-14 for u03)
    for page_num in range(1, 5):
        content = sample_content_u01 if page_num == 1 else f"Page {page_num} content for unit 1"
        (book_path / "normalized" / "pages" / f"{page_num:04d}.txt").write_text(content)

    for page_num in range(5, 10):
        content = sample_content_u02 if page_num == 5 else f"Page {page_num} content for unit 2"
        (book_path / "normalized" / "pages" / f"{page_num:04d}.txt").write_text(content)

    for page_num in range(10, 15):
        content = sample_content_u03 if page_num == 10 else f"Page {page_num} content for unit 3"
        (book_path / "normalized" / "pages" / f"{page_num:04d}.txt").write_text(content)

    # Create content.txt as well
    full_content = sample_content_u01 + "\n\n" + sample_content_u02 + "\n\n" + sample_content_u03
    (book_path / "normalized" / "content.txt").write_text(full_content)

    # Create notes metadata for each unit (simulating F4 output)
    for unit_num, (pages, content) in enumerate(
        [
            (list(range(1, 5)), sample_content_u01),
            (list(range(5, 10)), sample_content_u02),
            (list(range(10, 15)), sample_content_u03),
        ],
        start=1,
    ):
        notes_metadata = {
            "unit_id": f"{book_id}-ch01-u{unit_num:02d}",
            "book_id": book_id,
            "provider": "lmstudio",
            "model": "test-model",
            "pages_used": pages,
            "start_page": pages[0],
            "end_page": pages[-1],
            "chunks_processed": 1,
            "total_tokens": None,
            "generation_time_ms": 3000,
            "created_at": "2026-02-02T10:00:00+00:00",
            "chunk_modes": {"json": 1, "text_fallback": 0, "error": 0},
        }
        (book_path / "artifacts" / "notes" / f"{book_id}-ch01-u{unit_num:02d}.json").write_text(
            json.dumps(notes_metadata, indent=2)
        )

    return tmp_path / "data"


@pytest.fixture
def sample_exam_set(sample_book_multi_unit_chapter, mock_exam_response) -> dict:
    """Create a pre-existing exam set for testing submissions and grading."""
    book_id = "test-book"
    exam_set_id = f"{book_id}-ch01-exam01"

    questions = []
    for i, q in enumerate(mock_exam_response["questions"], 1):
        questions.append(
            {
                "question_id": f"{exam_set_id}-q{i:02d}",
                **q,
            }
        )

    exam_set = {
        "$schema": "chapter_exam_set_v1",
        "exam_set_id": exam_set_id,
        "book_id": book_id,
        "chapter_id": f"{book_id}:ch:1",
        "chapter_number": 1,
        "chapter_title": "Introduction to LLMs",
        "units_included": [
            f"{book_id}-ch01-u01",
            f"{book_id}-ch01-u02",
            f"{book_id}-ch01-u03",
        ],
        "provider": "lmstudio",
        "model": "test-model",
        "created_at": "2026-02-02T10:00:00+00:00",
        "generation_time_ms": 5000,
        "mode": "json",
        "difficulty": "mid",
        "total_points": sum(q["points"] for q in questions),
        "passing_threshold": 0.6,
        "pages_used": list(range(1, 15)),
        "questions": questions,
    }

    # Save to file
    exams_path = (
        sample_book_multi_unit_chapter
        / "books"
        / book_id
        / "artifacts"
        / "exams"
        / f"{exam_set_id}.json"
    )
    exams_path.write_text(json.dumps(exam_set, indent=2))

    return exam_set


@pytest.fixture
def sample_exam_answers_file(tmp_path, sample_exam_set) -> Path:
    """Create a sample answers JSON file for exam submission."""
    questions = sample_exam_set["questions"]

    # Create answers for each question (mostly correct)
    answers = {
        "answers": [
            # 6 MCQ answers (all correct)
            {"question_id": questions[0]["question_id"], "response": 0},  # Correct
            {"question_id": questions[1]["question_id"], "response": 1},  # Correct
            {"question_id": questions[2]["question_id"], "response": 2},  # Correct
            {"question_id": questions[3]["question_id"], "response": 1},  # Correct
            {"question_id": questions[4]["question_id"], "response": 1},  # Correct
            {"question_id": questions[5]["question_id"], "response": 2},  # Correct
            # 3 TF answers (2 correct, 1 wrong)
            {"question_id": questions[6]["question_id"], "response": False},  # Correct
            {"question_id": questions[7]["question_id"], "response": True},  # Correct
            {"question_id": questions[8]["question_id"], "response": False},  # Wrong
            # 3 SA answers
            {"question_id": questions[9]["question_id"], "response": "La atencion permite enfocarse en partes relevantes de la entrada."},
            {"question_id": questions[10]["question_id"], "response": "Embedding, transformer blocks, output layer."},
            {"question_id": questions[11]["question_id"], "response": "Requiere muchos datos y GPUs."},
        ]
    }

    answers_path = tmp_path / "exam_answers.json"
    answers_path.write_text(json.dumps(answers, indent=2))

    return answers_path


@pytest.fixture
def sample_exam_attempt(sample_book_multi_unit_chapter, sample_exam_set, sample_exam_answers_file) -> dict:
    """Create a pre-existing exam attempt for grading tests."""
    book_id = "test-book"
    exam_set_id = sample_exam_set["exam_set_id"]
    exam_attempt_id = f"{exam_set_id}-a01"

    # Load answers
    with open(sample_exam_answers_file) as f:
        answers_data = json.load(f)

    attempt = {
        "$schema": "exam_attempt_v1",
        "exam_attempt_id": exam_attempt_id,
        "exam_set_id": exam_set_id,
        "book_id": book_id,
        "chapter_id": f"{book_id}:ch:1",
        "created_at": "2026-02-02T11:00:00+00:00",
        "status": "submitted",
        "answers": answers_data["answers"],
        "total_questions": len(answers_data["answers"]),
    }

    # Save to file
    attempts_path = (
        sample_book_multi_unit_chapter
        / "books"
        / book_id
        / "artifacts"
        / "exam_attempts"
        / f"{exam_attempt_id}.json"
    )
    attempts_path.write_text(json.dumps(attempt, indent=2))

    return attempt
