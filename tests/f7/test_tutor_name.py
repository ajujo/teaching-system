"""Tests for user name personalization (F7.2)."""

import json
import pytest
from pathlib import Path

from teaching.core.tutor import TutorState, load_tutor_state, save_tutor_state


class TestUserNameInState:
    """Tests for user_name field in TutorState."""

    def test_tutor_state_has_user_name_field(self):
        """TutorState has user_name field."""
        state = TutorState()
        assert hasattr(state, "user_name")
        assert state.user_name is None

    def test_tutor_state_with_user_name(self):
        """TutorState can be created with user_name."""
        state = TutorState(user_name="Sergio")
        assert state.user_name == "Sergio"

    def test_to_dict_includes_user_name(self):
        """to_dict includes user_name."""
        state = TutorState(user_name="Ana")
        d = state.to_dict()
        assert "user_name" in d
        assert d["user_name"] == "Ana"

    def test_to_dict_with_none_user_name(self):
        """to_dict includes user_name even when None."""
        state = TutorState()
        d = state.to_dict()
        assert "user_name" in d
        assert d["user_name"] is None


class TestUserNamePersistence:
    """Tests for user_name save/load."""

    def test_save_and_load_user_name(self, tmp_path):
        """User name survives save/load cycle."""
        # Save state with user_name
        state = TutorState(user_name="Carlos")
        save_tutor_state(state, tmp_path)

        # Load state
        loaded = load_tutor_state(tmp_path)
        assert loaded.user_name == "Carlos"

    def test_load_without_user_name_returns_none(self, tmp_path):
        """Loading state without user_name field returns None."""
        # Create state file without user_name (legacy format)
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "tutor_state_v1.json"

        legacy_data = {
            "$schema": "tutor_state_v1",
            "active_book_id": None,
            "progress": {},
            "library_scan_paths": [],
            # No user_name field
        }
        with open(state_file, "w") as f:
            json.dump(legacy_data, f)

        # Load should handle missing field gracefully
        loaded = load_tutor_state(tmp_path)
        assert loaded.user_name is None

    def test_user_name_in_json_file(self, tmp_path):
        """User name is persisted in JSON file."""
        state = TutorState(user_name="María")
        save_tutor_state(state, tmp_path)

        # Read raw JSON
        state_file = tmp_path / "state" / "tutor_state_v1.json"
        with open(state_file) as f:
            data = json.load(f)

        assert data["user_name"] == "María"


class TestUserNameWithProgress:
    """Tests for user_name combined with other state."""

    def test_user_name_with_book_progress(self, tmp_path):
        """User name works alongside book progress."""
        state = TutorState(user_name="Pedro")
        state.active_book_id = "test-book"
        prog = state.get_book_progress("test-book")
        prog.last_chapter_number = 3

        save_tutor_state(state, tmp_path)
        loaded = load_tutor_state(tmp_path)

        assert loaded.user_name == "Pedro"
        assert loaded.active_book_id == "test-book"
        assert loaded.progress["test-book"].last_chapter_number == 3
