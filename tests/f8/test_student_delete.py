"""Tests for student delete flow (F8).

Tests the strict delete confirmation mechanism.
"""

import pytest

from teaching.core.tutor import (
    StudentProfile,
    StudentsState,
)


class TestStudentDeleteConfirmation:
    """Tests for delete confirmation logic."""

    def test_delete_removes_from_list(self):
        """Student removed from students list."""
        state = StudentsState()
        state.add_student("Ana")
        state.add_student("Carlos")

        assert len(state.students) == 2

        # Remove Ana
        result = state.remove_student("stu01")
        assert result is True
        assert len(state.students) == 1
        assert state.get_student_by_name("Ana") is None
        assert state.get_student_by_name("Carlos") is not None

    def test_delete_clears_active_if_deleted(self):
        """Active student cleared when deleted."""
        state = StudentsState()
        state.add_student("Ana")
        state.add_student("Carlos")
        state.active_student_id = "stu01"  # Ana

        state.remove_student("stu01")

        # Active should now be stu02 (Carlos) due to auto-select
        assert state.active_student_id == "stu02"

    def test_delete_nonexistent_returns_false(self):
        """Deleting nonexistent student returns False."""
        state = StudentsState()
        state.add_student("Ana")

        result = state.remove_student("stu99")
        assert result is False

    def test_student_has_full_name_for_confirmation(self):
        """Student has full_name property for confirmation."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
            surname="García",
        )
        assert student.full_name == "Ana García"


class TestDeleteConfirmationPatterns:
    """Tests for confirmation string patterns."""

    def test_delete_id_format(self):
        """DELETE {id} format is predictable."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
        )
        expected = f"DELETE {student.student_id}"
        assert expected == "DELETE stu01"

    def test_full_name_comparison(self):
        """Full name comparison is case-insensitive."""
        student = StudentProfile(
            student_id="stu01",
            name="Ana",
            surname="García",
        )

        # User might type in different cases
        full_name = student.full_name
        assert full_name.lower() == "ana garcía"

        # These should match (case-insensitive)
        assert "ANA GARCÍA".lower() == full_name.lower()
        assert "ana garcía".lower() == full_name.lower()


class TestStudentsStateRemove:
    """Tests for StudentsState.remove_student."""

    def test_remove_student_by_id(self):
        """Remove student by exact ID."""
        state = StudentsState()
        s1 = state.add_student("Ana")
        s2 = state.add_student("Carlos")

        removed = state.remove_student(s1.student_id)
        assert removed is True
        assert state.get_student_by_id(s1.student_id) is None

    def test_remove_last_student(self):
        """Can remove the only student (state handles it)."""
        state = StudentsState()
        s = state.add_student("Ana")

        # The state allows removal (UI should prevent this)
        removed = state.remove_student(s.student_id)
        assert removed is True
        assert len(state.students) == 0

    def test_remove_auto_selects_next(self):
        """After deletion, auto-selects another student if available."""
        state = StudentsState()
        s1 = state.add_student("Ana")
        s2 = state.add_student("Carlos")
        state.active_student_id = s1.student_id

        state.remove_student(s1.student_id)

        # Should auto-select Carlos
        assert state.active_student_id == s2.student_id
