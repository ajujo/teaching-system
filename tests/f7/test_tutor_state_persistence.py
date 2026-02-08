"""Tests for tutor state persistence (F7)."""

import json
from pathlib import Path

import pytest

from teaching.core.tutor import (
    BookProgress,
    TutorState,
    get_chapter_info,
    get_units_for_chapter,
    list_available_books_with_metadata,
    load_chapter_notes,
    load_tutor_state,
    save_tutor_state,
)


class TestTutorStateDataclass:
    """Tests for TutorState dataclass."""

    def test_fresh_state_has_defaults(self):
        """Fresh TutorState has sensible defaults."""
        state = TutorState()
        assert state.active_book_id is None
        assert state.progress == {}
        assert state.library_scan_paths == []

    def test_get_book_progress_creates_if_missing(self):
        """get_book_progress creates BookProgress if not exists."""
        state = TutorState()
        prog = state.get_book_progress("test-book")

        assert prog.book_id == "test-book"
        assert "test-book" in state.progress
        assert prog.last_chapter_number == 0
        assert prog.completed_chapters == []

    def test_get_book_progress_returns_existing(self):
        """get_book_progress returns existing BookProgress."""
        state = TutorState()
        state.progress["my-book"] = BookProgress(
            book_id="my-book",
            last_chapter_number=5,
            completed_chapters=[1, 2, 3],
        )

        prog = state.get_book_progress("my-book")
        assert prog.last_chapter_number == 5
        assert prog.completed_chapters == [1, 2, 3]

    def test_book_progress_to_dict(self):
        """BookProgress.to_dict() serializes correctly."""
        prog = BookProgress(
            book_id="test-book",
            last_chapter_number=3,
            completed_chapters=[1, 2],
            last_session_at="2026-02-06T10:00:00Z",
            chapter_attempts={"exam01": ["attempt01"]},
        )

        data = prog.to_dict()
        assert data["last_chapter_number"] == 3
        assert data["completed_chapters"] == [1, 2]
        assert data["last_session_at"] == "2026-02-06T10:00:00Z"
        assert data["chapter_attempts"] == {"exam01": ["attempt01"]}

    def test_tutor_state_to_dict(self):
        """TutorState.to_dict() serializes correctly with schema."""
        state = TutorState(active_book_id="my-book")
        state.progress["my-book"] = BookProgress(
            book_id="my-book",
            last_chapter_number=2,
        )

        data = state.to_dict()
        assert data["$schema"] == "tutor_state_v1"
        assert data["active_book_id"] == "my-book"
        assert "my-book" in data["progress"]


class TestTutorStatePersistence:
    """Tests for save/load functions."""

    def test_save_creates_state_file(self, tmp_path):
        """save_tutor_state creates JSON file in state directory."""
        state = TutorState(active_book_id="test-book")
        path = save_tutor_state(state, tmp_path)

        assert path.exists()
        assert path.name == "tutor_state_v1.json"
        assert path.parent.name == "state"

    def test_save_creates_state_directory(self, tmp_path):
        """save_tutor_state creates state directory if not exists."""
        state = TutorState()
        path = save_tutor_state(state, tmp_path)

        assert (tmp_path / "state").is_dir()
        assert path.exists()

    def test_load_empty_returns_fresh_state(self, tmp_path):
        """load_tutor_state returns fresh state when file missing."""
        state = load_tutor_state(tmp_path)

        assert state.active_book_id is None
        assert state.progress == {}

    def test_save_load_roundtrip(self, tmp_path):
        """State survives save/load cycle."""
        original = TutorState(active_book_id="my-book")
        original.progress["my-book"] = BookProgress(
            book_id="my-book",
            last_chapter_number=3,
            completed_chapters=[1, 2],
            last_session_at="2026-02-06T10:00:00Z",
            chapter_attempts={"exam01": ["attempt01", "attempt02"]},
        )
        original.library_scan_paths = ["/path/to/books"]

        save_tutor_state(original, tmp_path)
        loaded = load_tutor_state(tmp_path)

        assert loaded.active_book_id == "my-book"
        assert loaded.library_scan_paths == ["/path/to/books"]
        assert loaded.progress["my-book"].last_chapter_number == 3
        assert loaded.progress["my-book"].completed_chapters == [1, 2]
        assert loaded.progress["my-book"].chapter_attempts == {
            "exam01": ["attempt01", "attempt02"]
        }

    def test_corrupted_schema_returns_fresh(self, tmp_path):
        """Invalid schema returns fresh state."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "tutor_state_v1.json").write_text('{"$schema": "wrong_schema"}')

        state = load_tutor_state(tmp_path)
        assert state.active_book_id is None
        assert state.progress == {}

    def test_invalid_json_returns_fresh(self, tmp_path):
        """Invalid JSON returns fresh state."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "tutor_state_v1.json").write_text("not valid json {{{")

        state = load_tutor_state(tmp_path)
        assert state.active_book_id is None

    def test_multiple_books_progress(self, tmp_path):
        """State can track progress for multiple books."""
        state = TutorState()
        state.progress["book1"] = BookProgress(
            book_id="book1", last_chapter_number=5, completed_chapters=[1, 2, 3, 4]
        )
        state.progress["book2"] = BookProgress(
            book_id="book2", last_chapter_number=2, completed_chapters=[1]
        )

        save_tutor_state(state, tmp_path)
        loaded = load_tutor_state(tmp_path)

        assert len(loaded.progress) == 2
        assert loaded.progress["book1"].last_chapter_number == 5
        assert loaded.progress["book2"].last_chapter_number == 2


class TestBookHelpers:
    """Tests for book listing and chapter info helpers."""

    def test_list_available_books_with_metadata(self, sample_book_for_tutor):
        """list_available_books_with_metadata returns book info."""
        books = list_available_books_with_metadata(sample_book_for_tutor)

        assert len(books) == 1
        assert books[0]["book_id"] == "test-book"
        assert books[0]["title"] == "Test Book on LLMs"
        assert books[0]["total_chapters"] == 2
        assert books[0]["has_outline"] is True
        assert books[0]["has_units"] is True

    def test_list_available_books_empty_dir(self, tmp_path):
        """list_available_books_with_metadata returns empty for no books."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        books = list_available_books_with_metadata(data_dir)
        assert books == []

    def test_get_chapter_info(self, sample_book_for_tutor):
        """get_chapter_info returns chapter details."""
        info = get_chapter_info("test-book", 1, sample_book_for_tutor)

        assert info is not None
        assert info["chapter_number"] == 1
        assert info["title"] == "Introduction to LLMs"
        assert len(info["sections"]) == 3
        assert len(info["unit_ids"]) == 3
        assert "test-book-ch01-u01" in info["unit_ids"]

    def test_get_chapter_info_not_found(self, sample_book_for_tutor):
        """get_chapter_info returns None for invalid chapter."""
        info = get_chapter_info("test-book", 99, sample_book_for_tutor)
        assert info is None

    def test_get_chapter_info_no_outline(self, tmp_path):
        """get_chapter_info returns None when no outline exists."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        info = get_chapter_info("nonexistent", 1, data_dir)
        assert info is None

    def test_get_units_for_chapter(self, sample_book_for_tutor):
        """get_units_for_chapter returns unit IDs."""
        unit_ids = get_units_for_chapter("test-book", 1, sample_book_for_tutor)

        assert len(unit_ids) == 3
        assert "test-book-ch01-u01" in unit_ids
        assert "test-book-ch01-u02" in unit_ids
        assert "test-book-ch01-u03" in unit_ids

    def test_get_units_for_chapter_different_chapter(self, sample_book_for_tutor):
        """get_units_for_chapter returns correct units for ch2."""
        unit_ids = get_units_for_chapter("test-book", 2, sample_book_for_tutor)

        assert len(unit_ids) == 1
        assert "test-book-ch02-u01" in unit_ids


class TestChapterNotesLoader:
    """Tests for loading chapter notes."""

    def test_load_chapter_notes(self, sample_book_for_tutor):
        """load_chapter_notes returns combined notes content."""
        content, units_with_notes = load_chapter_notes(
            "test-book", 1, sample_book_for_tutor
        )

        assert len(content) > 0
        assert "LLM" in content
        assert "Transformer" in content
        assert len(units_with_notes) == 3

    def test_load_chapter_notes_no_notes(self, sample_book_for_tutor):
        """load_chapter_notes handles missing notes gracefully."""
        # Delete notes files
        notes_dir = (
            sample_book_for_tutor / "books" / "test-book" / "artifacts" / "notes"
        )
        for f in notes_dir.glob("*.md"):
            f.unlink()

        content, units_with_notes = load_chapter_notes(
            "test-book", 1, sample_book_for_tutor
        )

        assert content == ""
        assert units_with_notes == []


class TestSafetyNoRealData:
    """Safety tests ensuring real data is not touched."""

    def test_does_not_touch_real_data_directory(self, sample_book_for_tutor):
        """Fixtures use tmp_path, not real ./data directory."""
        project_root = Path(__file__).parent.parent.parent
        real_data_dir = project_root / "data"

        # Verify tmp_path is different from project paths
        assert str(sample_book_for_tutor) != str(real_data_dir)
        assert not str(sample_book_for_tutor).startswith(str(project_root / "data"))
        # Check for temp directory indicators (macOS uses /var/folders/...)
        path_str = str(sample_book_for_tutor).lower()
        assert "pytest" in path_str or "/t/" in path_str or "tmp" in path_str
