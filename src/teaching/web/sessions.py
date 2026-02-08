"""Session management for Web API (F9).

Manages active teaching sessions with event queues.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from teaching.core.tutor import (
    TutorEvent,
    TutorEventType,
    TutorTurnContext,
    generate_event_id,
)

logger = structlog.get_logger(__name__)


@dataclass
class Session:
    """An active teaching session."""

    session_id: str
    student_id: str
    book_id: str
    chapter_number: int
    unit_number: int
    created_at: str = ""
    status: str = "active"  # active | paused | completed
    # Event queue for SSE
    event_queue: asyncio.Queue[TutorEvent | None] = field(
        default_factory=lambda: asyncio.Queue()
    )
    # Turn context for event tracking
    turn_context: TutorTurnContext = field(default_factory=TutorTurnContext)
    # Teaching state (simplified for MVP)
    current_point_index: int = 0
    last_prompt_kind: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "student_id": self.student_id,
            "book_id": self.book_id,
            "chapter_number": self.chapter_number,
            "unit_number": self.unit_number,
            "created_at": self.created_at,
            "status": self.status,
        }


class SessionManager:
    """Manages active teaching sessions.

    Thread-safe session management with event queues for SSE.
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        student_id: str,
        book_id: str,
        chapter_number: int = 1,
        unit_number: int = 1,
    ) -> Session:
        """Create a new teaching session.

        Args:
            student_id: ID of the student
            book_id: ID of the book to teach
            chapter_number: Starting chapter (default 1)
            unit_number: Starting unit (default 1)

        Returns:
            The created Session object
        """
        session_id = str(uuid.uuid4())[:8]  # Short UUID for convenience

        session = Session(
            session_id=session_id,
            student_id=student_id,
            book_id=book_id,
            chapter_number=chapter_number,
            unit_number=unit_number,
        )

        async with self._lock:
            self._sessions[session_id] = session

        logger.info(
            "session_created",
            session_id=session_id,
            student_id=student_id,
            book_id=book_id,
        )

        return session

    async def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        async with self._lock:
            return self._sessions.get(session_id)

    async def end_session(self, session_id: str) -> bool:
        """End a session and clean up resources.

        Args:
            session_id: ID of the session to end

        Returns:
            True if session was ended, False if not found
        """
        async with self._lock:
            session = self._sessions.pop(session_id, None)

        if session is None:
            return False

        # Signal end of event stream
        session.status = "completed"
        await session.event_queue.put(None)

        logger.info("session_ended", session_id=session_id)
        return True

    async def emit_event(self, session_id: str, event: TutorEvent) -> bool:
        """Emit an event to a session's queue.

        Args:
            session_id: ID of the session
            event: The TutorEvent to emit

        Returns:
            True if event was emitted, False if session not found
        """
        async with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            return False

        await session.event_queue.put(event)
        logger.debug(
            "event_emitted",
            session_id=session_id,
            event_type=event.event_type.name,
            event_id=event.event_id,
        )
        return True

    async def process_input(self, session_id: str, text: str) -> list[TutorEvent]:
        """Process user input and generate response events.

        This is a simplified MVP implementation. The full implementation
        would integrate with the CLI teaching loop.

        Args:
            session_id: ID of the session
            text: User input text

        Returns:
            List of TutorEvents generated
        """
        async with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            return []

        # Advance turn context
        session.turn_context.advance_turn()

        # MVP: Simple echo response + placeholder
        # In full implementation, this would call the teaching logic
        events = []

        # Create a feedback event
        feedback_event = session.turn_context.next_event(
            TutorEventType.FEEDBACK,
            markdown=f"Recibido: '{text}'\n\n_[MVP placeholder - integrar con tutor logic]_",
        )
        events.append(feedback_event)
        await session.event_queue.put(feedback_event)

        return events

    async def list_sessions(self) -> list[Session]:
        """List all active sessions."""
        async with self._lock:
            return list(self._sessions.values())

    async def get_session_count(self) -> int:
        """Get count of active sessions."""
        async with self._lock:
            return len(self._sessions)


# Global session manager instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def reset_session_manager() -> None:
    """Reset the session manager (for testing)."""
    global _session_manager
    _session_manager = None
