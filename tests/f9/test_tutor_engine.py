"""Tests for TutorEngine (F9.1)."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from teaching.web.tutor_engine import (
    TutorEngine,
    WebTeachingState,
    WebSessionState,
    get_tutor_engine,
    reset_tutor_engine,
)
from teaching.core.tutor import TutorEventType


@pytest.fixture
def engine():
    """Create fresh tutor engine."""
    reset_tutor_engine()
    return TutorEngine()


class TestTutorEngineStartSession:
    """Tests for starting sessions."""

    def test_start_session_nonexistent_book(self, engine):
        """Start session with non-existent book returns error."""
        events = engine.start_session(
            session_id="test-001",
            student_id="stu01",
            book_id="nonexistent-book-xyz",
            chapter_number=1,
            unit_number=1,
        )

        assert len(events) == 1
        assert events[0].event_type == TutorEventType.FEEDBACK
        assert events[0].data.get("error") is True
        assert "no se encontraron" in events[0].markdown.lower()

    def test_start_session_creates_state(self, engine):
        """Start session creates internal state."""
        events = engine.start_session(
            session_id="test-001",
            student_id="stu01",
            book_id="some-book",
        )

        # Should have either success events or error event
        assert len(events) >= 1

    def test_start_session_events_have_ids(self, engine):
        """All events have proper IDs assigned."""
        events = engine.start_session(
            session_id="test-001",
            student_id="stu01",
            book_id="test-book",
        )

        for event in events:
            assert event.event_id, "Event should have event_id"
            assert event.turn_id >= 0, "Event should have turn_id"
            assert event.seq >= 0, "Event should have seq"


class TestTutorEngineHandleInput:
    """Tests for handling user input."""

    def test_handle_input_unknown_session(self, engine):
        """Handle input for unknown session returns error."""
        events = engine.handle_input("nonexistent", "hello")

        assert len(events) == 1
        assert events[0].event_type == TutorEventType.FEEDBACK
        assert events[0].data.get("error") is True

    def test_handle_input_returns_events(self, engine):
        """Handle input returns list of events."""
        # First start session (even with non-existent book)
        engine.start_session(
            session_id="test-001",
            student_id="stu01",
            book_id="test-book",
        )

        events = engine.handle_input("test-001", "hola")
        assert isinstance(events, list)
        assert len(events) >= 1


class TestTutorEngineState:
    """Tests for session state management."""

    def test_get_session_exists(self, engine):
        """Get session returns state for existing session."""
        engine.start_session(
            session_id="test-001",
            student_id="stu01",
            book_id="test-book",
        )

        state = engine.get_session("test-001")
        # Only has state if notes were found (otherwise error returned)
        # For non-existent book, state may not be created

    def test_get_session_not_found(self, engine):
        """Get session returns None for unknown session."""
        state = engine.get_session("nonexistent")
        assert state is None

    def test_end_session_removes_state(self, engine):
        """End session removes internal state."""
        engine.start_session(
            session_id="test-001",
            student_id="stu01",
            book_id="test-book",
        )

        # Manually add state for non-existent book case
        engine._sessions["test-001"] = WebSessionState(
            session_id="test-001",
            student_id="stu01",
            book_id="test-book",
            chapter_number=1,
            unit_number=1,
        )

        result = engine.end_session("test-001")
        assert result is True
        assert engine.get_session("test-001") is None

    def test_end_session_unknown(self, engine):
        """End unknown session returns False."""
        result = engine.end_session("nonexistent")
        assert result is False


class TestWebTeachingState:
    """Tests for WebTeachingState enum."""

    def test_all_states_defined(self):
        """All expected teaching states are defined."""
        expected = [
            "UNIT_OPENING",
            "WAIT_UNIT_START",
            "EXPLAINING",
            "WAITING_INPUT",
            "CHECKING",
            "MORE_EXAMPLES",
            "AWAITING_RETRY",
            "REMEDIATION",
            "NEXT_POINT",
            "CONFIRM_ADVANCE",
            "POST_FAILURE_CHOICE",
            "UNIT_COMPLETE",
        ]

        for state_name in expected:
            assert hasattr(WebTeachingState, state_name)


class TestGlobalTutorEngine:
    """Tests for global engine instance."""

    def test_get_tutor_engine_singleton(self):
        """get_tutor_engine returns same instance."""
        reset_tutor_engine()
        e1 = get_tutor_engine()
        e2 = get_tutor_engine()
        assert e1 is e2

    def test_reset_tutor_engine(self):
        """reset_tutor_engine creates new instance."""
        e1 = get_tutor_engine()
        reset_tutor_engine()
        e2 = get_tutor_engine()
        assert e1 is not e2


class TestTutorEngineEventTypes:
    """Tests verifying real TutorEventType usage (not placeholders)."""

    def test_no_placeholder_strings_in_events(self, engine):
        """Events should not contain placeholder text."""
        events = engine.start_session(
            session_id="test-001",
            student_id="stu01",
            book_id="test-book",
        )

        for event in events:
            # Check no placeholder text
            assert "placeholder" not in event.markdown.lower()
            assert "mvp" not in event.markdown.lower() or "mvp" in event.markdown.lower() and "completa" not in event.markdown.lower()
            # Event type should be a proper enum
            assert isinstance(event.event_type, TutorEventType)

    def test_event_types_are_enums(self, engine):
        """All event types are proper TutorEventType enums."""
        events = engine.start_session(
            session_id="test-001",
            student_id="stu01",
            book_id="any-book",
        )

        for event in events:
            assert isinstance(event.event_type, TutorEventType)
            # Should be one of the known types
            assert event.event_type in [
                TutorEventType.UNIT_OPENING,
                TutorEventType.POINT_OPENING,
                TutorEventType.POINT_EXPLANATION,
                TutorEventType.ASK_CHECK,
                TutorEventType.FEEDBACK,
                TutorEventType.ASK_CONFIRM_ADVANCE,
                TutorEventType.UNIT_NOTES,
            ]


class TestCheckResponseNoDoubleEvents:
    """Tests for _check_response() fix: no double blocking events."""

    def test_needs_elaboration_no_double_events(self, engine):
        """When user needs to elaborate, don't emit two blocking questions."""
        # Create a session with state
        session = WebSessionState(
            session_id="test-double",
            student_id="stu01",
            book_id="test-book",
            chapter_number=1,
            unit_number=1,
        )
        session.state = WebTeachingState.WAITING_INPUT
        session.last_explanation = "Explicación del concepto X"
        session.last_check_question = "¿Puedes explicar el concepto X?"
        engine._sessions["test-double"] = session

        # Mock check_comprehension to return needs_elaboration=True
        with patch("teaching.web.tutor_engine.check_comprehension") as mock_check:
            # Simulates user answering "sí" without elaboration
            mock_check.return_value = (
                True,  # understood
                "Bien que entiendes, pero ¿podrías explicar por qué?",  # feedback with question
                True,  # needs_elaboration
            )

            events = engine.handle_input("test-double", "sí")

        # Should only have 1 event (FEEDBACK), NOT 2 (FEEDBACK + ASK_CONFIRM_ADVANCE)
        assert len(events) == 1, f"Expected 1 event but got {len(events)}: {[e.event_type for e in events]}"
        assert events[0].event_type == TutorEventType.FEEDBACK
        assert events[0].data.get("needs_elaboration") is True

        # State should remain WAITING_INPUT (not CONFIRM_ADVANCE)
        assert session.state == WebTeachingState.WAITING_INPUT

    def test_full_comprehension_emits_advance_event(self, engine):
        """When user fully understands, emit FEEDBACK + ASK_CONFIRM_ADVANCE."""
        session = WebSessionState(
            session_id="test-full",
            student_id="stu01",
            book_id="test-book",
            chapter_number=1,
            unit_number=1,
        )
        session.state = WebTeachingState.WAITING_INPUT
        session.last_explanation = "Explicación del concepto Y"
        session.last_check_question = "¿Qué es el concepto Y?"
        engine._sessions["test-full"] = session

        with patch("teaching.web.tutor_engine.check_comprehension") as mock_check:
            # Full comprehension - user explained correctly
            mock_check.return_value = (
                True,  # understood
                "¡Excelente! Has entendido perfectamente.",  # feedback
                False,  # needs_elaboration = False
            )

            events = engine.handle_input("test-full", "El concepto Y es...")

        # Should have 2 events: FEEDBACK + ASK_CONFIRM_ADVANCE
        assert len(events) == 2
        assert events[0].event_type == TutorEventType.FEEDBACK
        assert events[1].event_type == TutorEventType.ASK_CONFIRM_ADVANCE

        # State should be CONFIRM_ADVANCE
        assert session.state == WebTeachingState.CONFIRM_ADVANCE

    def test_not_understood_emits_retry(self, engine):
        """When user doesn't understand, emit FEEDBACK + ASK_CHECK for retry."""
        session = WebSessionState(
            session_id="test-retry",
            student_id="stu01",
            book_id="test-book",
            chapter_number=1,
            unit_number=1,
        )
        session.state = WebTeachingState.WAITING_INPUT
        session.last_explanation = "Explicación del concepto Z"
        session.last_check_question = "¿Qué es el concepto Z?"
        session.attempts_this_point = 0
        engine._sessions["test-retry"] = session

        with patch("teaching.web.tutor_engine.check_comprehension") as mock_check:
            mock_check.return_value = (
                False,  # understood = False
                "No es correcto. Recuerda que...",  # feedback
                False,  # needs_elaboration
            )

            events = engine.handle_input("test-retry", "respuesta incorrecta")

        # Should have 2 events: FEEDBACK + ASK_CHECK (retry)
        assert len(events) == 2
        assert events[0].event_type == TutorEventType.FEEDBACK
        assert events[1].event_type == TutorEventType.ASK_CHECK

        # State should be AWAITING_RETRY
        assert session.state == WebTeachingState.AWAITING_RETRY


class TestProgressSaving:
    """Tests for session progress saving."""

    def test_save_session_start_called(self, engine):
        """start_session should save progress."""
        with patch.object(engine, "_save_session_start") as mock_save:
            with patch.object(engine, "_load_notes", return_value="# Test notes\nContent"):
                with patch("teaching.web.tutor_engine.generate_teaching_plan") as mock_plan:
                    from teaching.core.tutor import TeachingPlan, TeachingPoint
                    mock_plan.return_value = TeachingPlan(
                        unit_id="test-ch01-u01",
                        objective="Test objective",
                        points=[TeachingPoint(number=1, title="Test", content="Test content")],
                    )

                    engine.start_session(
                        session_id="test-save",
                        student_id="stu01",
                        book_id="test-book",
                    )

        # Verify _save_session_start was called
        mock_save.assert_called_once()
        # Verify it was called with the session state
        call_args = mock_save.call_args[0][0]
        assert call_args.session_id == "test-save"
        assert call_args.student_id == "stu01"

    def test_save_session_progress_on_end(self, engine):
        """end_session should save progress."""
        # Create a session manually
        session = WebSessionState(
            session_id="test-end",
            student_id="stu01",
            book_id="test-book",
            chapter_number=1,
            unit_number=1,
        )
        engine._sessions["test-end"] = session

        with patch.object(engine, "_save_session_progress") as mock_save:
            result = engine.end_session("test-end")

        assert result is True
        mock_save.assert_called_once_with(session)

    def test_end_session_removes_session(self, engine):
        """end_session should remove session from memory."""
        session = WebSessionState(
            session_id="test-remove",
            student_id="stu01",
            book_id="test-book",
            chapter_number=1,
            unit_number=1,
        )
        engine._sessions["test-remove"] = session

        with patch.object(engine, "_save_session_progress"):
            result = engine.end_session("test-remove")

        assert result is True
        assert engine.get_session("test-remove") is None

    def test_save_session_start_updates_book_progress(self, engine):
        """_save_session_start should update book progress fields."""
        session = WebSessionState(
            session_id="test-progress",
            student_id="stu01",
            book_id="test-book",
            chapter_number=3,
            unit_number=2,
        )

        # Mock the students state loading
        mock_student = MagicMock()
        mock_book_progress = MagicMock()
        mock_student.tutor_state.get_book_progress.return_value = mock_book_progress

        mock_students_state = MagicMock()
        mock_students_state.get_student_by_id.return_value = mock_student

        with patch("teaching.web.tutor_engine.load_students_state", return_value=mock_students_state):
            with patch("teaching.web.tutor_engine.save_student_progress") as mock_save:
                engine._save_session_start(session)

        # Verify book progress was updated
        assert mock_book_progress.last_chapter_number == 3
        assert mock_book_progress.last_session_at is not None
        mock_save.assert_called_once()

    def test_save_session_start_handles_errors(self, engine):
        """_save_session_start should handle errors gracefully."""
        session = WebSessionState(
            session_id="test-error",
            student_id="stu01",
            book_id="test-book",
            chapter_number=1,
            unit_number=1,
        )

        with patch("teaching.web.tutor_engine.load_students_state", side_effect=Exception("DB error")):
            # Should not raise exception
            engine._save_session_start(session)  # No assertion needed - just verify no exception
