"""Fixtures for F7 tests - Tutor Mode."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_book_for_tutor(tmp_path) -> Path:
    """Create a sample book with ch01 containing 3 units for tutor testing.

    This is similar to F6's sample_book_multi_unit_chapter but includes
    pre-generated notes for Q&A testing.
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

    # Create state directory
    (tmp_path / "data" / "state").mkdir(parents=True)

    # Create book.json
    book_json = {
        "$schema": "book_v1",
        "book_id": book_id,
        "title": "Test Book on LLMs",
        "authors": ["Test Author"],
        "language": "en",
        "source_format": "pdf",
        "total_chapters": 2,
    }
    (book_path / "book.json").write_text(json.dumps(book_json, indent=2))

    # Create outline.json with 2 chapters
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

    # Create units.json with 3 units in ch01, 1 in ch02
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

    # Create pre-generated notes for each unit in ch01
    notes_content = {
        f"{book_id}-ch01-u01": """# Apuntes - What are LLMs

## Resumen
Los LLMs (Large Language Models) son modelos de inteligencia artificial
entrenados con grandes cantidades de texto.

## Conceptos clave
| Concepto | Definición |
|----------|------------|
| LLM | Large Language Model |
| Token | Unidad básica de texto |
| Embedding | Representación vectorial |

## Detalles
Los componentes principales de un LLM son:
1. Capa de embedding
2. Bloques transformer
3. Capa de salida
""",
        f"{book_id}-ch01-u02": """# Apuntes - Transformer Architecture

## Resumen
La arquitectura transformer usa mecanismos de atención para procesar
secuencias en paralelo.

## Conceptos clave
| Concepto | Definición |
|----------|------------|
| Attention | Mecanismo para enfocarse en partes relevantes |
| Self-attention | Atención de una secuencia consigo misma |

## Detalles
El mecanismo de atención permite capturar dependencias a larga distancia.
""",
        f"{book_id}-ch01-u03": """# Apuntes - Training Process

## Resumen
El entrenamiento de LLMs requiere grandes recursos computacionales.

## Conceptos clave
| Concepto | Definición |
|----------|------------|
| Next token prediction | Objetivo típico de entrenamiento |
| Scaling laws | Leyes que relacionan tamaño y rendimiento |

## Detalles
Se necesitan miles de GPUs y datasets de miles de millones de tokens.
""",
    }

    for unit_id, content in notes_content.items():
        notes_path = book_path / "artifacts" / "notes" / f"{unit_id}.md"
        notes_path.write_text(content)

        # Also create metadata JSON
        notes_meta = {
            "unit_id": unit_id,
            "book_id": book_id,
            "provider": "lmstudio",
            "model": "test-model",
            "created_at": "2026-02-02T10:00:00+00:00",
        }
        (book_path / "artifacts" / "notes" / f"{unit_id}.json").write_text(
            json.dumps(notes_meta, indent=2)
        )

    # Create normalized content files
    for page_num in range(1, 15):
        (book_path / "normalized" / "pages" / f"{page_num:04d}.txt").write_text(
            f"Page {page_num} content about LLMs and transformers."
        )

    return tmp_path / "data"


@pytest.fixture
def sample_book_with_tutor_state(sample_book_for_tutor) -> Path:
    """Create sample book with existing tutor state (multi-student format)."""
    # Create students_v1.json with one student
    students_state = {
        "$schema": "students_v1",
        "active_student_id": "stu01",
        "students": [
            {
                "student_id": "stu01",
                "name": "Test",
                "created_at": "2026-02-02T10:00:00+00:00",
                "updated_at": "2026-02-02T10:00:00+00:00",
                "tutor_state": {
                    "$schema": "tutor_state_v1",
                    "active_book_id": "test-book",
                    "progress": {
                        "test-book": {
                            "last_chapter_number": 1,
                            "completed_chapters": [],
                            "last_session_at": "2026-02-02T10:00:00+00:00",
                            "chapter_attempts": {},
                        }
                    },
                    "library_scan_paths": [],
                    "user_name": "Test",
                }
            }
        ],
    }

    state_path = sample_book_for_tutor / "state" / "students_v1.json"
    state_path.write_text(json.dumps(students_state, indent=2))

    return sample_book_for_tutor


@pytest.fixture
def sample_book_with_student(sample_book_for_tutor) -> Path:
    """Create sample book with a pre-existing student (no progress yet)."""
    students_state = {
        "$schema": "students_v1",
        "active_student_id": "stu01",
        "students": [
            {
                "student_id": "stu01",
                "name": "Test",
                "created_at": "2026-02-02T10:00:00+00:00",
                "updated_at": "2026-02-02T10:00:00+00:00",
                "tutor_state": {
                    "$schema": "tutor_state_v1",
                    "active_book_id": None,
                    "progress": {},
                    "library_scan_paths": [],
                    "user_name": "Test",
                }
            }
        ],
    }

    state_path = sample_book_for_tutor / "state" / "students_v1.json"
    state_path.write_text(json.dumps(students_state, indent=2))

    return sample_book_for_tutor


@pytest.fixture
def mock_llm_client_for_qa() -> MagicMock:
    """Mock LLM client for Q&A responses."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"
    client.is_available.return_value = True
    client.simple_chat.return_value = (
        "Un LLM es un modelo de lenguaje grande entrenado "
        "con grandes cantidades de texto para comprender y generar lenguaje natural."
    )
    return client


@pytest.fixture
def mock_llm_client_for_notes() -> MagicMock:
    """Mock LLM client for notes generation."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"
    client.is_available.return_value = True
    client.simple_json.return_value = {
        "summary": "Resumen del contenido",
        "key_concepts": [{"concept": "LLM", "definition": "Large Language Model"}],
        "details": "Detalles adicionales sobre el tema.",
    }
    return client


@pytest.fixture
def mock_exam_response_valid() -> dict[str, Any]:
    """Valid exam response with good distribution."""
    return {
        "questions": [
            {
                "type": "multiple_choice",
                "question": f"Pregunta MCQ {i}?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": i % 4,  # Varied distribution
                "explanation": f"Explicación {i}",
                "points": 1,
                "source": {"unit_id": "test-book-ch01-u01", "pages": [1]},
            }
            for i in range(6)
        ]
        + [
            {
                "type": "true_false",
                "question": f"Pregunta TF {i}?",
                "options": None,
                "correct_answer": i % 2 == 0,
                "explanation": f"Explicación TF {i}",
                "points": 1,
                "source": {"unit_id": "test-book-ch01-u02", "pages": [5]},
            }
            for i in range(3)
        ]
        + [
            {
                "type": "short_answer",
                "question": f"Pregunta SA {i}?",
                "options": None,
                "correct_answer": f"Respuesta esperada {i}",
                "explanation": f"Explicación SA {i}",
                "points": 2,
                "source": {"unit_id": "test-book-ch01-u03", "pages": [10]},
            }
            for i in range(3)
        ]
    }


@pytest.fixture
def mock_llm_client_for_exam(mock_exam_response_valid) -> MagicMock:
    """Mock LLM client for valid exam generation."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"
    client.is_available.return_value = True
    client.simple_json.return_value = mock_exam_response_valid
    client.simple_chat.return_value = json.dumps(mock_exam_response_valid)
    return client


@pytest.fixture
def mock_llm_client_invalid_exam() -> MagicMock:
    """Mock LLM client that returns invalid exam (all same answers, empty explanations)."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"
    client.is_available.return_value = True

    # Invalid response: all MCQ have same correct_answer=0 and empty explanations
    invalid_response = {
        "questions": [
            {
                "type": "multiple_choice",
                "question": f"Q{i}?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": 0,  # All same!
                "explanation": "",  # Empty!
                "points": 1,
                "source": {"unit_id": "test-book-ch01-u01", "pages": [1]},
            }
            for i in range(6)
        ]
    }
    client.simple_json.return_value = invalid_response
    client.simple_chat.return_value = json.dumps(invalid_response)
    return client


@pytest.fixture
def mock_grade_response() -> dict[str, Any]:
    """Standard mock response for LLM grading."""
    return {
        "is_correct": True,
        "score": 0.85,
        "feedback": "Buena respuesta.",
        "confidence": 0.9,
    }


@pytest.fixture
def mock_llm_client_for_grading(mock_grade_response) -> MagicMock:
    """Mock LLM client for exam grading."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"
    client.is_available.return_value = True
    client.simple_json.return_value = mock_grade_response
    return client
