"""Persona configuration loader.

Loads tutor personas from data/config/personas_v1.yaml.

Usage:
    from teaching.config.personas import get_persona, list_personas

    persona = get_persona("dra_vega")
    all_personas = list_personas()
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger(__name__)

# Config file path (relative to project root)
PERSONAS_FILE = Path("data/config/personas_v1.yaml")


@dataclass
class TeachingPolicy:
    """Teaching strictness policy for a persona (F8.2).

    Controls how strict the tutor is with comprehension checks
    and what happens when a student fails.
    """

    max_attempts_per_point: int = 2  # 1 or 2 attempts before remediation
    remediation_style: str = "both"  # "analogy" | "example" | "both"
    allow_advance_on_failure: bool = True  # Offer escape hatch after failure
    default_after_failure: str = "stay"  # "advance" | "stay" (default choice)
    max_followups_per_point: int = 1  # 0 or 1 followup question after remediation


@dataclass
class Persona:
    """A tutor persona with personality traits and style."""

    id: str
    name: str
    short_title: str
    background: str
    style_rules: str
    default: bool = False
    teaching_policy: TeachingPolicy | None = None

    def get_teaching_policy(self) -> TeachingPolicy:
        """Get teaching policy, with defaults if not specified."""
        if self.teaching_policy is None:
            return TeachingPolicy()
        return self.teaching_policy


# Module-level cache
_cached_personas: dict[str, Persona] | None = None


def _get_default_personas() -> dict[str, Persona]:
    """Get default personas when config file is missing."""
    return {
        "dra_vega": Persona(
            id="dra_vega",
            name="Dra. Elena Vega",
            short_title="Profesora universitaria",
            background="Catedrática con 20 años de experiencia.",
            style_rules="- Tutea al estudiante\n- Usa ejemplos de la vida real",
            default=True,
            teaching_policy=TeachingPolicy(),
        ),
    }


def _parse_teaching_policy(data: dict | None) -> TeachingPolicy | None:
    """Parse teaching_policy from YAML data."""
    if data is None:
        return None
    return TeachingPolicy(
        max_attempts_per_point=data.get("max_attempts_per_point", 2),
        remediation_style=data.get("remediation_style", "both"),
        allow_advance_on_failure=data.get("allow_advance_on_failure", True),
        default_after_failure=data.get("default_after_failure", "stay"),
        max_followups_per_point=data.get("max_followups_per_point", 1),
    )


def load_personas(force_reload: bool = False) -> dict[str, Persona]:
    """Load all personas from config file.

    Args:
        force_reload: If True, ignore cache and reload from file.

    Returns:
        Dictionary mapping persona ID to Persona object.
    """
    global _cached_personas

    if _cached_personas is not None and not force_reload:
        return _cached_personas

    if not PERSONAS_FILE.exists():
        logger.warning("personas_file_not_found", path=str(PERSONAS_FILE))
        _cached_personas = _get_default_personas()
        return _cached_personas

    try:
        data = yaml.safe_load(PERSONAS_FILE.read_text(encoding="utf-8"))
        personas_data = data.get("personas", {})

        _cached_personas = {}
        for pid, pdata in personas_data.items():
            _cached_personas[pid] = Persona(
                id=pdata.get("id", pid),
                name=pdata.get("name", pid),
                short_title=pdata.get("short_title", ""),
                background=pdata.get("background", ""),
                style_rules=pdata.get("style_rules", ""),
                default=pdata.get("default", False),
                teaching_policy=_parse_teaching_policy(pdata.get("teaching_policy")),
            )

        logger.debug("loaded_personas", count=len(_cached_personas))
        return _cached_personas

    except Exception as e:
        logger.error("failed_to_load_personas", error=str(e))
        _cached_personas = _get_default_personas()
        return _cached_personas


def get_persona(persona_id: str) -> Persona | None:
    """Get a specific persona by ID.

    Args:
        persona_id: The persona identifier (e.g., "dra_vega")

    Returns:
        Persona object or None if not found.
    """
    personas = load_personas()
    return personas.get(persona_id)


def get_default_persona() -> Persona:
    """Get the default persona.

    Returns:
        The persona marked as default, or the first available persona.
    """
    personas = load_personas()

    # Find persona marked as default
    for persona in personas.values():
        if persona.default:
            return persona

    # Fallback to first persona
    if personas:
        return list(personas.values())[0]

    # Ultimate fallback
    return _get_default_personas()["dra_vega"]


def list_personas() -> list[Persona]:
    """List all available personas.

    Returns:
        List of all Persona objects.
    """
    return list(load_personas().values())


def clear_personas_cache() -> None:
    """Clear the personas cache.

    Useful for testing or when personas are modified at runtime.
    """
    global _cached_personas
    _cached_personas = None
