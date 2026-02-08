"""Persona endpoints (F9)."""

from fastapi import APIRouter, HTTPException, status

from teaching.config.personas import get_persona, list_personas
from teaching.web.schemas import (
    PersonaResponse,
    PersonaListResponse,
    TeachingPolicyResponse,
)

router = APIRouter(prefix="/api/personas", tags=["personas"])


def _persona_to_response(persona) -> PersonaResponse:
    """Convert Persona to PersonaResponse."""
    policy = persona.get_teaching_policy()
    return PersonaResponse(
        id=persona.id,
        name=persona.name,
        short_title=persona.short_title,
        background=persona.background,
        default=persona.default,
        teaching_policy=TeachingPolicyResponse(
            max_attempts_per_point=policy.max_attempts_per_point,
            remediation_style=policy.remediation_style,
            allow_advance_on_failure=policy.allow_advance_on_failure,
            default_after_failure=policy.default_after_failure,
            max_followups_per_point=policy.max_followups_per_point,
        ),
    )


@router.get("", response_model=PersonaListResponse)
async def list_all_personas() -> PersonaListResponse:
    """List all available personas."""
    personas = list_personas()
    responses = [_persona_to_response(p) for p in personas]
    return PersonaListResponse(personas=responses, count=len(responses))


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona_by_id(persona_id: str) -> PersonaResponse:
    """Get a specific persona by ID."""
    persona = get_persona(persona_id)

    if persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona '{persona_id}' not found",
        )

    return _persona_to_response(persona)
