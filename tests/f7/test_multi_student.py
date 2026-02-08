"""Tests for multi-student support (F7.3 Academia)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from teaching.cli.commands import app
from teaching.core.tutor import (
    StudentProfile,
    StudentsState,
    TutorState,
    load_students_state,
    save_students_state,
)


runner = CliRunner()


# =============================================================================
# Test: StudentProfile and StudentsState dataclasses
# =============================================================================


class TestStudentProfile:
    """Tests for StudentProfile dataclass."""

    def test_student_profile_creation(self):
        """StudentProfile se puede crear correctamente."""
        student = StudentProfile(
            student_id="stu01",
            name="Test User",
        )

        assert student.student_id == "stu01"
        assert student.name == "Test User"
        assert student.created_at  # Should be auto-set
        assert student.updated_at  # Should be auto-set

    def test_student_profile_has_tutor_state(self):
        """StudentProfile contiene un TutorState."""
        student = StudentProfile(
            student_id="stu01",
            name="Test User",
        )

        assert isinstance(student.tutor_state, TutorState)

    def test_student_profile_to_dict(self):
        """StudentProfile se serializa correctamente."""
        student = StudentProfile(
            student_id="stu01",
            name="Test User",
        )

        data = student.to_dict()

        assert data["student_id"] == "stu01"
        assert data["name"] == "Test User"
        assert "created_at" in data
        assert "tutor_state" in data


class TestStudentsState:
    """Tests for StudentsState dataclass."""

    def test_students_state_creation(self):
        """StudentsState se puede crear correctamente."""
        state = StudentsState()

        assert state.active_student_id is None
        assert state.students == []

    def test_add_student(self):
        """add_student crea un nuevo estudiante."""
        state = StudentsState()

        student = state.add_student("Test User")

        assert len(state.students) == 1
        assert student.name == "Test User"
        assert student.student_id == "stu01"
        assert student.tutor_state.user_name == "Test User"

    def test_add_multiple_students(self):
        """add_student genera IDs únicos."""
        state = StudentsState()

        s1 = state.add_student("User 1")
        s2 = state.add_student("User 2")
        s3 = state.add_student("User 3")

        assert s1.student_id == "stu01"
        assert s2.student_id == "stu02"
        assert s3.student_id == "stu03"

    def test_get_student_by_id(self):
        """get_student_by_id encuentra estudiante por ID."""
        state = StudentsState()
        state.add_student("User 1")
        state.add_student("User 2")

        found = state.get_student_by_id("stu02")

        assert found is not None
        assert found.name == "User 2"

    def test_get_student_by_name(self):
        """get_student_by_name encuentra estudiante por nombre."""
        state = StudentsState()
        state.add_student("Alice")
        state.add_student("Bob")

        found = state.get_student_by_name("bob")  # Case insensitive

        assert found is not None
        assert found.name == "Bob"

    def test_remove_student(self):
        """remove_student elimina un estudiante."""
        state = StudentsState()
        s1 = state.add_student("User 1")
        s2 = state.add_student("User 2")
        state.active_student_id = s1.student_id

        result = state.remove_student("stu01")

        assert result is True
        assert len(state.students) == 1
        assert state.students[0].name == "User 2"
        # Should auto-select another student
        assert state.active_student_id == "stu02"

    def test_remove_nonexistent_student(self):
        """remove_student retorna False si no existe."""
        state = StudentsState()
        state.add_student("User 1")

        result = state.remove_student("stu99")

        assert result is False
        assert len(state.students) == 1

    def test_get_active_student(self):
        """get_active_student retorna el estudiante activo."""
        state = StudentsState()
        s1 = state.add_student("User 1")
        state.add_student("User 2")
        state.active_student_id = s1.student_id

        active = state.get_active_student()

        assert active is not None
        assert active.name == "User 1"


# =============================================================================
# Test: Persistence
# =============================================================================


class TestStudentsStatePersistence:
    """Tests for loading and saving students state."""

    def test_save_and_load_roundtrip(self, tmp_path):
        """Guardar y cargar mantiene los datos."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        # Create state
        state = StudentsState()
        s1 = state.add_student("Alice")
        s1.tutor_state.active_book_id = "test-book"
        state.active_student_id = s1.student_id

        # Save
        save_students_state(state, data_dir)

        # Load
        loaded = load_students_state(data_dir)

        assert loaded.active_student_id == "stu01"
        assert len(loaded.students) == 1
        assert loaded.students[0].name == "Alice"
        assert loaded.students[0].tutor_state.active_book_id == "test-book"

    def test_migration_from_old_state(self, tmp_path):
        """Migra tutor_state_v1.json a students_v1.json."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        # Create old-format state
        old_state = {
            "$schema": "tutor_state_v1",
            "active_book_id": "test-book",
            "progress": {
                "test-book": {
                    "last_chapter_number": 2,
                    "completed_chapters": [1],
                    "last_session_at": "2026-01-01T00:00:00Z",
                    "chapter_attempts": {},
                }
            },
            "library_scan_paths": [],
            "user_name": "OldUser",
        }
        (data_dir / "state" / "tutor_state_v1.json").write_text(
            json.dumps(old_state, indent=2)
        )

        # Load should migrate
        loaded = load_students_state(data_dir)

        assert loaded.active_student_id == "stu01"
        assert len(loaded.students) == 1
        assert loaded.students[0].name == "OldUser"
        assert loaded.students[0].tutor_state.active_book_id == "test-book"

        # students_v1.json should now exist
        assert (data_dir / "state" / "students_v1.json").exists()

    def test_empty_state_returns_empty(self, tmp_path):
        """Sin archivos de estado, retorna estado vacío."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        loaded = load_students_state(data_dir)

        assert loaded.active_student_id is None
        assert loaded.students == []


# =============================================================================
# Test: CLI Integration
# =============================================================================


class TestAcademiaLobby:
    """Tests for Academia lobby in CLI."""

    def test_lobby_shows_when_no_students(self, tmp_path):
        """Lobby se muestra cuando no hay estudiantes."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        # Exit immediately with S
        input_data = "s\n"

        result = runner.invoke(
            app,
            ["tutor"],
            input=input_data,
            env={"TEACHING_DATA_DIR": str(data_dir)},
        )

        assert "academia" in result.output.lower()
        assert "nuevo estudiante" in result.output.lower()

    def test_lobby_creates_new_student(self, tmp_path):
        """Lobby permite crear un nuevo estudiante."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        # Create new student then exit
        input_data = (
            "0\n"  # New student
            "TestUser\n"  # Name
            "s\n"  # Exit at book selection (no books)
        )

        result = runner.invoke(
            app,
            ["tutor"],
            input=input_data,
            env={"TEACHING_DATA_DIR": str(data_dir)},
        )

        assert "bienvenido" in result.output.lower() or "testuser" in result.output.lower()

        # Verify student was saved
        loaded = load_students_state(data_dir)
        assert len(loaded.students) == 1
        assert loaded.students[0].name == "TestUser"

    def test_lobby_selects_existing_student(self, tmp_path):
        """Lobby permite seleccionar un estudiante existente."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        # Pre-create students
        state = StudentsState()
        state.add_student("Alice")
        state.add_student("Bob")
        save_students_state(state, data_dir)

        # Select Bob (option 2), then exit
        input_data = (
            "2\n"  # Select Bob
            "s\n"  # Exit at book selection
        )

        result = runner.invoke(
            app,
            ["tutor"],
            input=input_data,
            env={"TEACHING_DATA_DIR": str(data_dir)},
        )

        assert "bob" in result.output.lower() or "hola" in result.output.lower()

        # Verify Bob is now active
        loaded = load_students_state(data_dir)
        assert loaded.active_student_id == "stu02"

    def test_list_students_flag(self, tmp_path):
        """--list-students muestra estudiantes registrados."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        # Pre-create students
        state = StudentsState()
        state.add_student("Alice")
        state.add_student("Bob")
        state.active_student_id = "stu01"
        save_students_state(state, data_dir)

        result = runner.invoke(
            app,
            ["tutor", "--list-students"],
            env={"TEACHING_DATA_DIR": str(data_dir)},
        )

        assert result.exit_code == 0
        assert "alice" in result.output.lower()
        assert "bob" in result.output.lower()
        assert "stu01" in result.output.lower()

    def test_student_flag_skips_lobby(self, tmp_path):
        """--student salta el lobby y selecciona directo."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        # Pre-create student
        state = StudentsState()
        state.add_student("TestUser")
        save_students_state(state, data_dir)

        # Use --student flag, then exit at book selection
        input_data = "s\n"

        result = runner.invoke(
            app,
            ["tutor", "--student", "TestUser"],
            input=input_data,
            env={"TEACHING_DATA_DIR": str(data_dir)},
        )

        # Should skip lobby and go directly to book selection
        assert "academia" not in result.output.lower()

    def test_student_flag_not_found(self, tmp_path):
        """--student con nombre no encontrado muestra error."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        result = runner.invoke(
            app,
            ["tutor", "--student", "NonExistent"],
            env={"TEACHING_DATA_DIR": str(data_dir)},
        )

        assert "no encontrado" in result.output.lower()


class TestStudentProgress:
    """Tests for separate progress per student."""

    def test_students_have_separate_progress(self, tmp_path):
        """Cada estudiante tiene su propio progreso."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        state = StudentsState()
        alice = state.add_student("Alice")
        bob = state.add_student("Bob")

        # Set different progress
        alice.tutor_state.active_book_id = "book-1"
        alice.tutor_state.get_book_progress("book-1").last_chapter_number = 5

        bob.tutor_state.active_book_id = "book-2"
        bob.tutor_state.get_book_progress("book-2").last_chapter_number = 2

        save_students_state(state, data_dir)

        # Reload and verify
        loaded = load_students_state(data_dir)

        loaded_alice = loaded.get_student_by_name("Alice")
        loaded_bob = loaded.get_student_by_name("Bob")

        assert loaded_alice.tutor_state.active_book_id == "book-1"
        assert loaded_alice.tutor_state.progress["book-1"].last_chapter_number == 5

        assert loaded_bob.tutor_state.active_book_id == "book-2"
        assert loaded_bob.tutor_state.progress["book-2"].last_chapter_number == 2


class TestDeleteStudent:
    """Tests for student deletion."""

    def test_cannot_delete_last_student(self, tmp_path):
        """No se puede eliminar el último estudiante."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        state = StudentsState()
        state.add_student("OnlyOne")
        save_students_state(state, data_dir)

        # Try to delete
        input_data = (
            "d\n"  # Try delete
            "s\n"  # Exit
        )

        result = runner.invoke(
            app,
            ["tutor"],
            input=input_data,
            env={"TEACHING_DATA_DIR": str(data_dir)},
        )

        # Should show error about last student
        assert "último" in result.output.lower() or "no puedes" in result.output.lower()

        # Student should still exist
        loaded = load_students_state(data_dir)
        assert len(loaded.students) == 1

    def test_delete_with_confirmation(self, tmp_path):
        """Eliminar estudiante requiere confirmación estricta."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        state = StudentsState()
        state.add_student("ToKeep")
        state.add_student("ToDelete")
        save_students_state(state, data_dir)

        # Delete second student with exact name confirmation
        input_data = (
            "d\n"  # Delete option
            "2\n"  # Select ToDelete
            "ToDelete\n"  # Confirm with exact name
            "s\n"  # Exit
        )

        result = runner.invoke(
            app,
            ["tutor"],
            input=input_data,
            env={"TEACHING_DATA_DIR": str(data_dir)},
        )

        # Student should be deleted
        loaded = load_students_state(data_dir)
        assert len(loaded.students) == 1
        assert loaded.students[0].name == "ToKeep"

    def test_delete_cancelled_wrong_confirmation(self, tmp_path):
        """Eliminar se cancela con confirmación incorrecta."""
        data_dir = tmp_path / "data"
        (data_dir / "state").mkdir(parents=True)

        state = StudentsState()
        state.add_student("Keep1")
        state.add_student("Keep2")
        save_students_state(state, data_dir)

        # Try delete but cancel
        input_data = (
            "d\n"  # Delete option
            "2\n"  # Select Keep2
            "wrong\n"  # Wrong confirmation
            "s\n"  # Exit
        )

        result = runner.invoke(
            app,
            ["tutor"],
            input=input_data,
            env={"TEACHING_DATA_DIR": str(data_dir)},
        )

        # Both students should still exist
        loaded = load_students_state(data_dir)
        assert len(loaded.students) == 2
