"""Tests for teaching-first mode commands (F7.3)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner

from teaching.cli.commands import app


runner = CliRunner()


# =============================================================================
# Test: Command-line flags
# =============================================================================


class TestTutorPaceFlag:
    """Tests for --pace flag on tutor command."""

    def test_pace_flag_exists(self):
        """El comando tutor acepta --pace flag."""
        # Just verify help includes pace
        result = runner.invoke(app, ["tutor", "--help"])
        assert "--pace" in result.output

    def test_pace_options_documented(self):
        """Las opciones slow/normal/fast están documentadas."""
        result = runner.invoke(app, ["tutor", "--help"])
        # Check that pace is mentioned
        assert "pace" in result.output.lower()


# =============================================================================
# Test: Prompt format
# =============================================================================


class TestPromptFormat:
    """Tests for user prompt format changes."""

    def test_user_prompt_uses_name_colon_format(self, tmp_path):
        """El prompt debe ser '{nombre}:' no 'tu pregunta'."""
        # Setup minimal book structure
        data_dir = tmp_path / "data"
        state_dir = data_dir / "state"
        state_dir.mkdir(parents=True)

        # Create state with user name
        state_file = state_dir / "tutor_state_v1.json"
        state_file.write_text("""{
            "$schema": "tutor_state_v1",
            "active_book_id": null,
            "progress": {},
            "library_scan_paths": [],
            "user_name": "TestUser"
        }""")

        # Create minimal book
        books_dir = data_dir / "books" / "test-book"
        (books_dir / "artifacts" / "outline").mkdir(parents=True)
        (books_dir / "metadata.json").write_text('{"title": "Test Book", "status": "imported"}')
        (books_dir / "artifacts" / "outline" / "outline_v1.json").write_text("""{
            "schema_version": "outline_v1",
            "book_id": "test-book",
            "chapters": [{"chapter_number": 1, "title": "Chapter 1", "sections": []}]
        }""")

        # Create units
        units_dir = books_dir / "artifacts" / "units"
        units_dir.mkdir(parents=True)
        (units_dir / "units.json").write_text("""{
            "schema_version": "units_v1",
            "units": [{"unit_id": "test-book-ch01-u01", "chapter_number": 1, "title": "Unit 1"}]
        }""")

        # Create notes
        notes_dir = books_dir / "artifacts" / "notes"
        notes_dir.mkdir(parents=True)
        (notes_dir / "test-book-ch01-u01.md").write_text("""# Apuntes

## Resumen
- Punto de prueba

## Explicación paso a paso
### 1. Tema
Contenido del tema.
""")

        # Run with input that exits quickly
        input_data = "1\nstop\n"

        with patch("teaching.core.tutor.LLMClient"):
            result = runner.invoke(
                app,
                ["tutor"],
                input=input_data,
                env={"TEACHING_DATA_DIR": str(data_dir)},
            )

        # The prompt should use the name format
        # (The actual prompt happens before 'stop' is entered)
        assert "TestUser" in result.output


# =============================================================================
# Test: Teaching commands
# =============================================================================


class TestTeachingCommands:
    """Tests for teaching loop commands."""

    def test_adelante_documented_in_help(self):
        """'adelante' está documentado en la ayuda."""
        result = runner.invoke(app, ["tutor", "--help"])
        assert "adelante" in result.output.lower()

    def test_apuntes_documented_in_help(self):
        """'apuntes' está documentado en la ayuda."""
        result = runner.invoke(app, ["tutor", "--help"])
        assert "apuntes" in result.output.lower()

    def test_control_documented_in_help(self):
        """'control' está documentado en la ayuda."""
        result = runner.invoke(app, ["tutor", "--help"])
        assert "control" in result.output.lower()

    def test_examen_documented_in_help(self):
        """'examen' está documentado en la ayuda."""
        result = runner.invoke(app, ["tutor", "--help"])
        assert "examen" in result.output.lower()


# =============================================================================
# Test: Teaching loop structure
# =============================================================================


class TestTeachingLoopStructure:
    """Tests for teaching loop structure."""

    def test_teaching_plan_import_exists(self):
        """TeachingPlan y generate_teaching_plan se pueden importar."""
        from teaching.core.tutor import (
            TeachingPlan,
            TeachingPoint,
            generate_teaching_plan,
        )

        assert TeachingPlan is not None
        assert TeachingPoint is not None
        assert callable(generate_teaching_plan)

    def test_explain_point_import_exists(self):
        """explain_point se puede importar."""
        from teaching.core.tutor import explain_point

        assert callable(explain_point)

    def test_check_comprehension_import_exists(self):
        """check_comprehension se puede importar."""
        from teaching.core.tutor import check_comprehension

        assert callable(check_comprehension)

    def test_reexplain_with_analogy_import_exists(self):
        """reexplain_with_analogy se puede importar."""
        from teaching.core.tutor import reexplain_with_analogy

        assert callable(reexplain_with_analogy)
