"""Fixtures for F4 tests - Notes Generation."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_llm_response() -> dict[str, Any]:
    """Standard mock response for chunk summary."""
    return {
        "resumen": "Este fragmento explica los conceptos básicos de LLMs.",
        "puntos_clave": [
            "Los LLMs usan arquitectura transformer",
            "El entrenamiento requiere grandes datasets",
            "Fine-tuning permite especialización",
        ],
        "conceptos_definidos": [
            {"concepto": "LLM", "definicion": "Large Language Model, modelo de lenguaje grande"},
            {"concepto": "Transformer", "definicion": "Arquitectura de red neuronal con atención"},
        ],
    }


@pytest.fixture
def mock_llm_client(mock_llm_response):
    """Mock LLM client that returns fixed responses without calling real LLM."""
    client = MagicMock()
    client.config = MagicMock()
    client.config.provider = "lmstudio"
    client.config.model = "test-model"

    # is_available returns True
    client.is_available.return_value = True

    # simple_json returns chunk summary
    client.simple_json.return_value = mock_llm_response

    # simple_chat returns markdown notes
    client.simple_chat.return_value = """# Apuntes — Test Book — Ch1 — Introduction

## Resumen
- Los LLMs son modelos de lenguaje grandes
- Usan arquitectura transformer
- Requieren mucho entrenamiento
- Se pueden especializar con fine-tuning
- Son la base de ChatGPT y similares

## Conceptos clave
| Concepto | Definición |
|----------|------------|
| LLM | Large Language Model, modelo de lenguaje grande |
| Transformer | Arquitectura de red neuronal con atención |

## Explicación paso a paso

### Introducción a LLMs
Los modelos de lenguaje grandes representan un avance significativo.

### Arquitectura
Los transformers son la base de los LLMs modernos.

## Preguntas de repaso
1. ¿Qué significa LLM?
2. ¿Qué es un transformer?
3. ¿Qué es fine-tuning?
4. ¿Por qué se necesitan grandes datasets?
5. ¿Cuáles son las aplicaciones de LLMs?

## Fuentes
Páginas utilizadas: 1-15
"""

    return client


@pytest.fixture
def sample_book_with_content(tmp_path) -> Path:
    """Create a sample book structure with all required files for notes generation."""
    book_id = "test-book"
    book_path = tmp_path / "data" / "books" / book_id

    # Create directories
    (book_path / "source").mkdir(parents=True)
    (book_path / "normalized" / "pages").mkdir(parents=True)
    (book_path / "outline").mkdir(parents=True)
    (book_path / "artifacts" / "units").mkdir(parents=True)
    (book_path / "artifacts" / "notes").mkdir(parents=True)

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
            {
                "chapter_id": f"{book_id}:ch:2",
                "number": 2,
                "title": "Advanced Topics",
                "start_page": 20,
                "sections": [
                    {
                        "section_id": f"{book_id}:ch:2:sec:1",
                        "number": "2.1",
                        "title": "Fine-tuning",
                        "start_page": 21,
                    },
                ],
            },
        ],
    }
    (book_path / "outline" / "outline.json").write_text(
        json.dumps(outline, indent=2)
    )

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
                "section_start_id": f"{book_id}:ch:1:sec:1",
                "section_end_id": f"{book_id}:ch:1:sec:3",
                "unit_number_in_chapter": 1,
                "units_in_chapter": 1,
                "estimated_time_min": 14,
                "difficulty": "intro",
            },
            {
                "unit_id": f"{book_id}-ch02-u01",
                "chapter_id": f"{book_id}:ch:2",
                "chapter_number": 2,
                "title": "Ch2 — Advanced Topics",
                "section_ids": [f"{book_id}:ch:2:sec:1"],
                "section_start_id": f"{book_id}:ch:2:sec:1",
                "section_end_id": f"{book_id}:ch:2:sec:1",
                "unit_number_in_chapter": 1,
                "units_in_chapter": 1,
                "estimated_time_min": 8,
                "difficulty": "adv",
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
        page_content = "\n".join(lines[start_idx:end_idx]) if start_idx < len(lines) else ""

        page_file = book_path / "normalized" / "pages" / f"{page_num:04d}.txt"
        page_file.write_text(page_content)

    # Create content.txt as well
    (book_path / "normalized" / "content.txt").write_text(sample_content)

    return tmp_path / "data"


@pytest.fixture
def sample_book_content_only(tmp_path) -> Path:
    """Create a sample book with only content.txt (no individual pages)."""
    book_id = "test-book-content"
    book_path = tmp_path / "data" / "books" / book_id

    # Create directories (no pages/ directory)
    (book_path / "source").mkdir(parents=True)
    (book_path / "normalized").mkdir(parents=True)
    (book_path / "outline").mkdir(parents=True)
    (book_path / "artifacts" / "units").mkdir(parents=True)

    # Create book.json
    book_json = {
        "book_id": book_id,
        "title": "Test Book Content Only",
        "authors": ["Test Author"],
        "language": "en",
    }
    (book_path / "book.json").write_text(json.dumps(book_json, indent=2))

    # Create outline.json
    outline = {
        "$schema": "outline_v1",
        "book_id": book_id,
        "chapters": [
            {
                "chapter_id": f"{book_id}:ch:1",
                "number": 1,
                "title": "Chapter One",
                "start_page": 1,
                "sections": [
                    {
                        "section_id": f"{book_id}:ch:1:sec:1",
                        "number": "1.1",
                        "title": "Section One",
                        "start_page": 1,
                    },
                ],
            },
        ],
    }
    (book_path / "outline" / "outline.json").write_text(
        json.dumps(outline, indent=2)
    )

    # Create units.json
    units = {
        "$schema": "units_v1.1",
        "book_id": book_id,
        "units": [
            {
                "unit_id": f"{book_id}-ch01-u01",
                "chapter_id": f"{book_id}:ch:1",
                "chapter_number": 1,
                "title": "Ch1 — Chapter One",
                "section_ids": [f"{book_id}:ch:1:sec:1"],
                "section_start_id": f"{book_id}:ch:1:sec:1",
                "section_end_id": f"{book_id}:ch:1:sec:1",
                "unit_number_in_chapter": 1,
                "units_in_chapter": 1,
                "estimated_time_min": 8,
                "difficulty": "mid",
            },
        ],
    }
    (book_path / "artifacts" / "units" / "units.json").write_text(
        json.dumps(units, indent=2)
    )

    # Create only content.txt (no pages/)
    content = "This is sample content " * 3000  # ~15000 chars
    (book_path / "normalized" / "content.txt").write_text(content)

    return tmp_path / "data"
