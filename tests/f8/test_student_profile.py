"""Tests for StudentProfile changes (F8).

Tests the new fields, validation, and migration.
"""

import pytest
import tempfile
import json
from pathlib import Path

from teaching.core.tutor import (
    StudentProfile,
    StudentsState,
    validate_email,
    save_students_state,
    load_students_state,
)


class TestStudentProfileFields:
    """Tests for new StudentProfile fields."""

    def test_student_has_surname(self):
        """StudentProfile has surname field."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
            surname="García",
        )
        assert student.surname == "García"

    def test_student_has_email(self):
        """StudentProfile has email field."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
            email="ana@example.com",
        )
        assert student.email == "ana@example.com"

    def test_student_has_tutor_persona_id(self):
        """StudentProfile has tutor_persona_id field."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
            tutor_persona_id="profe_nico",
        )
        assert student.tutor_persona_id == "profe_nico"

    def test_student_default_persona(self):
        """Default tutor_persona_id is dra_vega."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
        )
        assert student.tutor_persona_id == "dra_vega"

    def test_student_has_needs_profile_completion(self):
        """StudentProfile has needs_profile_completion field."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
            needs_profile_completion=True,
        )
        assert student.needs_profile_completion is True

    def test_student_default_needs_completion_false(self):
        """Default needs_profile_completion is False."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
        )
        assert student.needs_profile_completion is False


class TestStudentFullName:
    """Tests for full_name property."""

    def test_full_name_with_surname(self):
        """full_name includes surname when present."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
            surname="García",
        )
        assert student.full_name == "Ana García"

    def test_full_name_without_surname(self):
        """full_name is just name when no surname."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
        )
        assert student.full_name == "Ana"


class TestEmailValidation:
    """Tests for email validation."""

    def test_validate_email_valid(self):
        """Valid emails pass validation."""
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.co.uk") is True
        assert validate_email("user+tag@example.org") is True

    def test_validate_email_empty(self):
        """Empty string is valid (optional field)."""
        assert validate_email("") is True

    def test_validate_email_invalid(self):
        """Invalid emails fail validation."""
        assert validate_email("not-an-email") is False
        assert validate_email("missing@tld") is False
        assert validate_email("@nodomain.com") is False


class TestStudentToDict:
    """Tests for StudentProfile serialization."""

    def test_to_dict_includes_new_fields(self):
        """to_dict includes surname, email, tutor_persona_id."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
            surname="García",
            email="ana@test.com",
            tutor_persona_id="profe_nico",
            needs_profile_completion=True,
        )
        data = student.to_dict()

        assert data["surname"] == "García"
        assert data["email"] == "ana@test.com"
        assert data["tutor_persona_id"] == "profe_nico"
        assert data["needs_profile_completion"] is True


class TestStudentsStateAddStudent:
    """Tests for StudentsState.add_student with new fields."""

    def test_add_student_with_surname(self):
        """add_student accepts surname parameter."""
        state = StudentsState()
        student = state.add_student("Ana", surname="García")
        assert student.surname == "García"

    def test_add_student_with_email(self):
        """add_student accepts email parameter."""
        state = StudentsState()
        student = state.add_student("Ana", email="ana@test.com")
        assert student.email == "ana@test.com"

    def test_add_student_with_persona(self):
        """add_student accepts tutor_persona_id parameter."""
        state = StudentsState()
        student = state.add_student("Ana", tutor_persona_id="ines")
        assert student.tutor_persona_id == "ines"

    def test_add_student_needs_completion_false(self):
        """New students don't need profile completion."""
        state = StudentsState()
        student = state.add_student("Ana")
        assert student.needs_profile_completion is False


class TestStudentMigration:
    """Tests for student data migration."""

    def test_migration_adds_missing_fields(self):
        """Loading old data adds new fields with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            state_dir = data_dir / "state"
            state_dir.mkdir(parents=True)

            # Create old format data (without new F8 fields)
            old_data = {
                "$schema": "students_v1",
                "active_student_id": "stu01",
                "students": [
                    {
                        "student_id": "stu01",
                        "name": "Ana",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                        "tutor_state": {
                            "$schema": "tutor_state_v1",
                            "active_book_id": None,
                            "progress": {},
                            "library_scan_paths": [],
                            "user_name": "Ana",
                        },
                    }
                ],
            }
            with open(state_dir / "students_v1.json", "w") as f:
                json.dump(old_data, f)

            # Load and check migration
            state = load_students_state(data_dir)
            student = state.get_student_by_id("stu01")

            assert student is not None
            assert student.surname == ""
            assert student.email == ""
            assert student.tutor_persona_id == "dra_vega"
            assert student.needs_profile_completion is True  # Migrated student

    def test_new_student_not_needs_completion(self):
        """Newly created students don't need completion."""
        state = StudentsState()
        student = state.add_student(
            "Ana",
            surname="García",
            email="ana@test.com",
        )
        assert student.needs_profile_completion is False
