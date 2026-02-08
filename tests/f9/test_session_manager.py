"""Tests for SessionManager (F9)."""

import pytest
import asyncio

from teaching.web.sessions import (
    SessionManager,
    Session,
    get_session_manager,
    reset_session_manager,
)
from teaching.core.tutor import TutorEvent, TutorEventType


@pytest.fixture
def manager():
    """Create fresh session manager."""
    return SessionManager()


class TestSessionManagerCreate:
    """Tests for session creation."""

    @pytest.mark.asyncio
    async def test_create_session_returns_session(self, manager):
        """Create returns Session object."""
        session = await manager.create_session(
            student_id="stu01",
            book_id="test-book",
        )
        assert isinstance(session, Session)
        assert session.student_id == "stu01"
        assert session.book_id == "test-book"

    @pytest.mark.asyncio
    async def test_create_session_unique_ids(self, manager):
        """Each session has unique ID."""
        s1 = await manager.create_session("stu01", "book1")
        s2 = await manager.create_session("stu01", "book1")
        assert s1.session_id != s2.session_id

    @pytest.mark.asyncio
    async def test_create_session_defaults(self, manager):
        """Session has correct defaults."""
        session = await manager.create_session("stu01", "book1")
        assert session.chapter_number == 1
        assert session.unit_number == 1
        assert session.status == "active"


class TestSessionManagerGet:
    """Tests for session retrieval."""

    @pytest.mark.asyncio
    async def test_get_session_exists(self, manager):
        """Get returns existing session."""
        created = await manager.create_session("stu01", "book1")
        fetched = await manager.get_session(created.session_id)
        assert fetched is not None
        assert fetched.session_id == created.session_id

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, manager):
        """Get returns None for unknown session."""
        result = await manager.get_session("nonexistent")
        assert result is None


class TestSessionManagerEnd:
    """Tests for ending sessions."""

    @pytest.mark.asyncio
    async def test_end_session_removes(self, manager):
        """End removes session from manager."""
        session = await manager.create_session("stu01", "book1")
        result = await manager.end_session(session.session_id)
        assert result is True

        fetched = await manager.get_session(session.session_id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_end_session_not_found(self, manager):
        """End returns False for unknown session."""
        result = await manager.end_session("nonexistent")
        assert result is False


class TestSessionManagerEvents:
    """Tests for event emission."""

    @pytest.mark.asyncio
    async def test_emit_event_adds_to_queue(self, manager):
        """Emit adds event to session queue."""
        session = await manager.create_session("stu01", "book1")

        event = TutorEvent(
            event_type=TutorEventType.FEEDBACK,
            markdown="Test",
        )
        result = await manager.emit_event(session.session_id, event)
        assert result is True

        # Check queue
        queued = await asyncio.wait_for(
            session.event_queue.get(),
            timeout=1.0,
        )
        assert queued.markdown == "Test"

    @pytest.mark.asyncio
    async def test_emit_event_session_not_found(self, manager):
        """Emit returns False for unknown session."""
        event = TutorEvent(event_type=TutorEventType.FEEDBACK)
        result = await manager.emit_event("nonexistent", event)
        assert result is False


class TestSessionManagerInput:
    """Tests for input processing."""

    @pytest.mark.asyncio
    async def test_process_input_returns_events(self, manager):
        """Process input returns list of events."""
        session = await manager.create_session("stu01", "book1")
        events = await manager.process_input(session.session_id, "Hola")

        assert isinstance(events, list)
        assert len(events) >= 1
        assert events[0].event_type == TutorEventType.FEEDBACK

    @pytest.mark.asyncio
    async def test_process_input_advances_turn(self, manager):
        """Process input advances turn context."""
        session = await manager.create_session("stu01", "book1")

        events1 = await manager.process_input(session.session_id, "First")
        events2 = await manager.process_input(session.session_id, "Second")

        assert events2[0].turn_id > events1[0].turn_id

    @pytest.mark.asyncio
    async def test_process_input_session_not_found(self, manager):
        """Process input returns empty for unknown session."""
        events = await manager.process_input("nonexistent", "text")
        assert events == []


class TestSessionManagerList:
    """Tests for listing sessions."""

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, manager):
        """List returns empty when no sessions."""
        sessions = await manager.list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_list_sessions_returns_all(self, manager):
        """List returns all active sessions."""
        await manager.create_session("stu01", "book1")
        await manager.create_session("stu02", "book2")

        sessions = await manager.list_sessions()
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_get_session_count(self, manager):
        """Count returns correct number."""
        assert await manager.get_session_count() == 0

        await manager.create_session("stu01", "book1")
        assert await manager.get_session_count() == 1


class TestGlobalSessionManager:
    """Tests for global session manager."""

    def test_get_session_manager_singleton(self):
        """get_session_manager returns same instance."""
        reset_session_manager()
        m1 = get_session_manager()
        m2 = get_session_manager()
        assert m1 is m2

    def test_reset_session_manager(self):
        """reset_session_manager creates new instance."""
        m1 = get_session_manager()
        reset_session_manager()
        m2 = get_session_manager()
        assert m1 is not m2
