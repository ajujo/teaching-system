"""Session endpoints (F9)."""

import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from teaching.core.tutor import TutorEvent
from teaching.web.schemas import (
    SessionStartRequest,
    SessionResponse,
    TutorInputRequest,
    TutorEventResponse,
)
from teaching.web.sessions import get_session_manager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(request: SessionStartRequest) -> SessionResponse:
    """Start a new teaching session."""
    manager = get_session_manager()

    session = await manager.create_session(
        student_id=request.student_id,
        book_id=request.book_id,
        chapter_number=request.chapter_number,
        unit_number=request.unit_number,
    )

    return SessionResponse(
        session_id=session.session_id,
        student_id=session.student_id,
        book_id=session.book_id,
        chapter_number=session.chapter_number,
        unit_number=session.unit_number,
        created_at=session.created_at,
        status=session.status,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """Get session details."""
    manager = get_session_manager()
    session = await manager.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    return SessionResponse(
        session_id=session.session_id,
        student_id=session.student_id,
        book_id=session.book_id,
        chapter_number=session.chapter_number,
        unit_number=session.unit_number,
        created_at=session.created_at,
        status=session.status,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(session_id: str) -> None:
    """End a teaching session."""
    manager = get_session_manager()

    if not await manager.end_session(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )


@router.post("/{session_id}/input", response_model=list[TutorEventResponse])
async def send_input(session_id: str, request: TutorInputRequest) -> list[TutorEventResponse]:
    """Send user input to a session.

    Returns the events generated in response.
    """
    manager = get_session_manager()
    session = await manager.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    events = await manager.process_input(session_id, request.text)

    return [
        TutorEventResponse(
            event_id=e.event_id,
            event_type=e.event_type.name,
            turn_id=e.turn_id,
            seq=e.seq,
            title=e.title,
            markdown=e.markdown,
            data=e.data,
        )
        for e in events
    ]


async def _event_generator(session_id: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for a session."""
    manager = get_session_manager()
    session = await manager.get_session(session_id)

    if session is None:
        yield f"event: error\ndata: Session not found\n\n"
        return

    while True:
        try:
            # Wait for next event with timeout
            event = await asyncio.wait_for(
                session.event_queue.get(),
                timeout=30.0,  # Send keepalive every 30s
            )

            if event is None:
                # Session ended
                yield f"event: close\ndata: Session ended\n\n"
                return

            # Format as SSE
            import json
            event_data = {
                "event_id": event.event_id,
                "event_type": event.event_type.name,
                "turn_id": event.turn_id,
                "seq": event.seq,
                "title": event.title,
                "markdown": event.markdown,
                "data": event.data,
            }
            yield f"event: tutor_event\ndata: {json.dumps(event_data)}\n\n"

        except asyncio.TimeoutError:
            # Send keepalive
            yield f"event: keepalive\ndata: ping\n\n"


@router.get("/{session_id}/events")
async def stream_events(session_id: str) -> StreamingResponse:
    """Stream events from a session using Server-Sent Events.

    Connect to this endpoint to receive real-time tutor events.

    Events:
    - tutor_event: Contains TutorEvent data as JSON
    - keepalive: Sent every 30s to keep connection alive
    - close: Session has ended
    - error: An error occurred
    """
    manager = get_session_manager()
    session = await manager.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    return StreamingResponse(
        _event_generator(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
