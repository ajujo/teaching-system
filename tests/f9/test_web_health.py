"""Tests for health endpoint (F9)."""

import pytest
from fastapi.testclient import TestClient

from teaching.web.api import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_ok(self, client):
        """Health endpoint returns status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_version(self, client):
        """Health endpoint returns version."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_health_returns_timestamp(self, client):
        """Health endpoint returns timestamp."""
        response = client.get("/health")
        data = response.json()
        assert "timestamp" in data
        # ISO format check
        assert "T" in data["timestamp"]
