"""Tests for personas endpoints (F9)."""

import pytest
from fastapi.testclient import TestClient

from teaching.web.api import create_app
from teaching.config.personas import clear_personas_cache


@pytest.fixture
def client():
    """Create test client."""
    clear_personas_cache()
    app = create_app()
    return TestClient(app)


class TestListPersonas:
    """Tests for GET /api/personas."""

    def test_list_personas_returns_array(self, client):
        """List returns array of personas."""
        response = client.get("/api/personas")
        assert response.status_code == 200
        data = response.json()
        assert "personas" in data
        assert "count" in data
        assert isinstance(data["personas"], list)

    def test_list_personas_has_default(self, client):
        """List includes at least one default persona."""
        response = client.get("/api/personas")
        data = response.json()
        defaults = [p for p in data["personas"] if p.get("default")]
        assert len(defaults) >= 1

    def test_list_personas_includes_teaching_policy(self, client):
        """Personas include teaching policy."""
        response = client.get("/api/personas")
        data = response.json()
        for persona in data["personas"]:
            assert "teaching_policy" in persona
            policy = persona["teaching_policy"]
            assert "max_attempts_per_point" in policy
            assert "allow_advance_on_failure" in policy


class TestGetPersona:
    """Tests for GET /api/personas/{id}."""

    def test_get_persona_dra_vega(self, client):
        """Get dra_vega persona."""
        response = client.get("/api/personas/dra_vega")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "dra_vega"
        assert "Elena" in data["name"] or "Vega" in data["name"]

    def test_get_persona_not_found(self, client):
        """Get non-existent persona returns 404."""
        response = client.get("/api/personas/unknown_persona")
        assert response.status_code == 404

    def test_get_persona_includes_policy(self, client):
        """Get persona includes teaching policy."""
        response = client.get("/api/personas/dra_vega")
        data = response.json()
        assert "teaching_policy" in data
        assert data["teaching_policy"]["max_attempts_per_point"] >= 1


class TestPersonaFields:
    """Tests for persona response fields."""

    def test_persona_has_required_fields(self, client):
        """Persona response has all required fields."""
        response = client.get("/api/personas/dra_vega")
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "short_title" in data
        assert "background" in data
        assert "default" in data
        assert "teaching_policy" in data

    def test_teaching_policy_has_all_fields(self, client):
        """Teaching policy has all fields."""
        response = client.get("/api/personas/dra_vega")
        policy = response.json()["teaching_policy"]
        assert "max_attempts_per_point" in policy
        assert "remediation_style" in policy
        assert "allow_advance_on_failure" in policy
        assert "default_after_failure" in policy
        assert "max_followups_per_point" in policy
