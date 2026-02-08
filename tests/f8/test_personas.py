"""Tests for personas configuration (F8).

Tests the persona loading, default selection, and configuration.
"""

import pytest
from pathlib import Path

from teaching.config.personas import (
    Persona,
    load_personas,
    get_persona,
    get_default_persona,
    list_personas,
    clear_personas_cache,
    PERSONAS_FILE,
)


class TestLoadPersonas:
    """Tests for load_personas function."""

    def test_load_personas_from_yaml(self):
        """Loads personas from YAML."""
        clear_personas_cache()
        personas = load_personas()
        assert isinstance(personas, dict)
        assert len(personas) >= 1

    def test_load_personas_has_dra_vega(self):
        """Default persona dra_vega exists."""
        personas = load_personas()
        assert "dra_vega" in personas

    def test_load_personas_four_personas(self):
        """Loads 4 personas from YAML."""
        personas = load_personas()
        # We expect 4 personas: dra_vega, profe_nico, ines, capitan_ortega
        expected_ids = ["dra_vega", "profe_nico", "ines", "capitan_ortega"]
        for pid in expected_ids:
            assert pid in personas, f"Missing persona: {pid}"


class TestGetPersona:
    """Tests for get_persona function."""

    def test_get_persona_by_id(self):
        """Get specific persona by ID."""
        persona = get_persona("dra_vega")
        assert persona is not None
        assert persona.id == "dra_vega"
        assert "Vega" in persona.name

    def test_get_persona_not_found(self):
        """Returns None for unknown persona."""
        persona = get_persona("unknown_persona")
        assert persona is None

    def test_get_persona_has_all_fields(self):
        """Persona has all required fields."""
        persona = get_persona("dra_vega")
        assert persona.id
        assert persona.name
        assert persona.short_title
        assert persona.background
        assert persona.style_rules


class TestGetDefaultPersona:
    """Tests for get_default_persona function."""

    def test_get_default_persona(self):
        """Returns dra_vega as default."""
        persona = get_default_persona()
        assert persona is not None
        assert persona.id == "dra_vega"
        assert persona.default is True

    def test_default_persona_is_dra_vega(self):
        """Default persona is Dra. Vega."""
        persona = get_default_persona()
        assert "Vega" in persona.name


class TestListPersonas:
    """Tests for list_personas function."""

    def test_list_personas_returns_list(self):
        """Returns list of Persona objects."""
        personas = list_personas()
        assert isinstance(personas, list)
        assert all(isinstance(p, Persona) for p in personas)

    def test_list_personas_not_empty(self):
        """List is not empty."""
        personas = list_personas()
        assert len(personas) >= 1


class TestPersonaFields:
    """Tests for persona field content."""

    @pytest.mark.parametrize(
        "persona_id",
        ["dra_vega", "profe_nico", "ines", "capitan_ortega"],
    )
    def test_persona_has_required_fields(self, persona_id: str):
        """Each persona has id, name, style_rules."""
        persona = get_persona(persona_id)
        if persona is None:
            pytest.skip(f"Persona {persona_id} not found")
        assert persona.id == persona_id
        assert len(persona.name) > 0
        assert len(persona.style_rules) > 0

    def test_personas_file_exists(self):
        """Personas YAML file exists."""
        assert PERSONAS_FILE.exists(), f"Missing: {PERSONAS_FILE}"
