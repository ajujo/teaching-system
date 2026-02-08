"""Tests para Bug B: Chapter opening UX fixes (F8.1).

Tests para:
- Títulos de capítulo truncados (terminan en preposición)
- Títulos de unidades duplicados
- Tiempo estimado faltante
"""

import json
import pytest
from pathlib import Path

from teaching.core.tutor import generate_chapter_opening


def _create_book_structure(tmp_path: Path, book_id: str, chapter_data: dict, units_data: list):
    """Helper para crear estructura de libro para tests."""
    book_dir = tmp_path / "books" / book_id
    book_dir.mkdir(parents=True)

    # book.json
    (book_dir / "book.json").write_text(
        json.dumps({"title": "Test Book", "book_id": book_id}),
        encoding="utf-8",
    )

    # outline/outline.json
    outline_dir = book_dir / "outline"
    outline_dir.mkdir()
    (outline_dir / "outline.json").write_text(
        json.dumps({
            "chapters": [chapter_data]
        }),
        encoding="utf-8",
    )

    # artifacts/units/units.json
    units_dir = book_dir / "artifacts" / "units"
    units_dir.mkdir(parents=True)
    (units_dir / "units.json").write_text(
        json.dumps({"units": units_data}),
        encoding="utf-8",
    )


class TestChapterTitleNotTruncated:
    """Tests para títulos de capítulo no truncados."""

    def test_truncated_title_ending_in_de_uses_fallback(self, tmp_path):
        """Título terminando en 'de' usa fallback genérico."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Introducción a la creación de",  # Truncado!
            },
            units_data=[],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        assert result["chapter_title"] == "Capítulo 1"

    def test_truncated_title_ending_in_la_uses_fallback(self, tmp_path):
        """Título terminando en 'la' usa fallback genérico."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Configuración de la",  # Truncado!
            },
            units_data=[],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        assert result["chapter_title"] == "Capítulo 1"

    def test_truncated_title_ending_in_con_uses_fallback(self, tmp_path):
        """Título terminando en 'con' usa fallback genérico."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Trabajando con",  # Truncado!
            },
            units_data=[],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        assert result["chapter_title"] == "Capítulo 1"

    def test_complete_title_preserved(self, tmp_path):
        """Título completo se preserva."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Introducción a los Modelos de Lenguaje",
            },
            units_data=[],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        assert result["chapter_title"] == "Introducción a los Modelos de Lenguaje"

    def test_title_ending_in_noun_preserved(self, tmp_path):
        """Título terminando en sustantivo se preserva."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Tokenización y Embeddings",
            },
            units_data=[],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        assert result["chapter_title"] == "Tokenización y Embeddings"


class TestUnitsTitlesNotRepeated:
    """Tests para títulos de unidades no repetidos."""

    def test_duplicate_titles_use_fallback(self, tmp_path):
        """Unidades con títulos duplicados usan fallback."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Capítulo Uno",
            },
            units_data=[
                {
                    "unit_id": "u1",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 1,
                    "title": "Ch1 — Introducción (Parte 1/3)",
                    "estimated_time_min": 20,
                },
                {
                    "unit_id": "u2",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 2,
                    "title": "Ch1 — Introducción (Parte 2/3)",
                    "estimated_time_min": 20,
                },
                {
                    "unit_id": "u3",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 3,
                    "title": "Ch1 — Introducción (Parte 3/3)",
                    "estimated_time_min": 20,
                },
            ],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        units = result["units"]
        assert len(units) == 3

        # Todos deben tener títulos únicos (fallback)
        titles = [u["title"] for u in units]
        assert titles == ["Unidad 1.1", "Unidad 1.2", "Unidad 1.3"]

    def test_unique_titles_preserved(self, tmp_path):
        """Unidades con títulos únicos se preservan."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Capítulo Uno",
            },
            units_data=[
                {
                    "unit_id": "u1",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 1,
                    "title": "Tokenización",
                    "estimated_time_min": 15,
                },
                {
                    "unit_id": "u2",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 2,
                    "title": "Embeddings",
                    "estimated_time_min": 20,
                },
            ],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        units = result["units"]
        titles = [u["title"] for u in units]
        assert titles == ["Tokenización", "Embeddings"]

    def test_empty_title_uses_fallback(self, tmp_path):
        """Unidad con título vacío usa fallback."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Capítulo Uno",
            },
            units_data=[
                {
                    "unit_id": "u1",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 1,
                    "title": "",  # Vacío
                    "estimated_time_min": 15,
                },
                {
                    "unit_id": "u2",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 2,
                    "title": "Embeddings",
                    "estimated_time_min": 20,
                },
            ],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        units = result["units"]
        assert units[0]["title"] == "Unidad 1.1"
        assert units[1]["title"] == "Embeddings"


class TestDurationEstimation:
    """Tests para estimación de duración."""

    def test_missing_duration_gets_estimate(self, tmp_path):
        """Unidades sin duración reciben estimación."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Capítulo Uno",
            },
            units_data=[
                {
                    "unit_id": "u1",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 1,
                    "title": "Única Unidad",
                    "section_ids": ["s1", "s2", "s3"],  # 3 secciones
                    # Sin estimated_time_min!
                },
            ],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        units = result["units"]
        assert len(units) == 1
        # Debe tener tiempo estimado >= 10 min (3 secciones * 4 = 12 min)
        assert units[0]["estimated_time_min"] >= 10

    def test_zero_duration_gets_estimate(self, tmp_path):
        """Duración 0 recibe estimación."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Capítulo Uno",
            },
            units_data=[
                {
                    "unit_id": "u1",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 1,
                    "title": "Única Unidad",
                    "section_ids": ["s1", "s2"],  # 2 secciones
                    "estimated_time_min": 0,  # Cero!
                },
            ],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        units = result["units"]
        # Mínimo 10 min
        assert units[0]["estimated_time_min"] >= 10

    def test_existing_duration_preserved(self, tmp_path):
        """Duración existente se preserva."""
        _create_book_structure(
            tmp_path,
            "test-book",
            chapter_data={
                "chapter_id": "test:ch:1",
                "number": 1,
                "title": "Capítulo Uno",
            },
            units_data=[
                {
                    "unit_id": "u1",
                    "chapter_number": 1,
                    "unit_number_in_chapter": 1,
                    "title": "Única Unidad",
                    "estimated_time_min": 25,
                },
            ],
        )

        result = generate_chapter_opening("test-book", 1, tmp_path)

        assert result is not None
        units = result["units"]
        assert units[0]["estimated_time_min"] == 25
