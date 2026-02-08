"""Pydantic schemas for Web API (F9).

Serialization models for Student, Persona, Session, and TutorEvent.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# STUDENT SCHEMAS
# =============================================================================


class StudentCreate(BaseModel):
    """Request body for creating a student."""

    name: str = Field(..., min_length=1, max_length=100)
    surname: str = Field(default="", max_length=100)
    email: str = Field(default="", max_length=200)
    tutor_persona_id: str = Field(default="dra_vega")


class StudentResponse(BaseModel):
    """Response for a student."""

    student_id: str
    name: str
    surname: str
    email: str
    tutor_persona_id: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class StudentListResponse(BaseModel):
    """Response for list of students."""

    students: list[StudentResponse]
    count: int


# =============================================================================
# PERSONA SCHEMAS
# =============================================================================


class TeachingPolicyResponse(BaseModel):
    """Teaching policy configuration."""

    max_attempts_per_point: int = 2
    remediation_style: str = "both"
    allow_advance_on_failure: bool = True
    default_after_failure: str = "stay"
    max_followups_per_point: int = 1


class PersonaResponse(BaseModel):
    """Response for a persona."""

    id: str
    name: str
    short_title: str
    background: str
    default: bool = False
    teaching_policy: TeachingPolicyResponse | None = None


class PersonaListResponse(BaseModel):
    """Response for list of personas."""

    personas: list[PersonaResponse]
    count: int


# =============================================================================
# SESSION SCHEMAS
# =============================================================================


class SessionStartRequest(BaseModel):
    """Request to start a teaching session."""

    student_id: str
    book_id: str
    chapter_number: int = Field(default=1, ge=1)
    unit_number: int = Field(default=1, ge=1)


class SessionResponse(BaseModel):
    """Response for a session."""

    session_id: str
    student_id: str
    book_id: str
    chapter_number: int
    unit_number: int
    created_at: str
    status: str = "active"  # active | paused | completed


class TutorInputRequest(BaseModel):
    """Request to send input to a session."""

    text: str = Field(..., max_length=2000)


# =============================================================================
# EVENT SCHEMAS
# =============================================================================


class TutorEventTypeSchema(str, Enum):
    """Event types for the tutor."""

    UNIT_OPENING = "UNIT_OPENING"
    POINT_OPENING = "POINT_OPENING"
    POINT_EXPLANATION = "POINT_EXPLANATION"
    ASK_CHECK = "ASK_CHECK"
    FEEDBACK = "FEEDBACK"
    ASK_CONFIRM_ADVANCE = "ASK_CONFIRM_ADVANCE"
    UNIT_NOTES = "UNIT_NOTES"
    ASK_UNIT_NEXT = "ASK_UNIT_NEXT"


class TutorEventResponse(BaseModel):
    """Response for a tutor event."""

    event_id: str
    event_type: str
    turn_id: int
    seq: int
    title: str = ""
    markdown: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# HEALTH SCHEMAS
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = "0.1.0"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
