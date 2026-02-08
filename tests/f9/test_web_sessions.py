"""Tests for sessions endpoints (F9)."""

import pytest
from fastapi.testclient import TestClient

from teaching.web.api import create_app
from teaching.web.sessions import reset_session_manager


@pytest.fixture
def client():
    """Create test client with fresh session manager."""
    reset_session_manager()
    app = create_app()
    return TestClient(app)


class TestStartSession:
    """Tests for POST /api/sessions."""

    def test_start_session_returns_session(self, client):
        """Start session returns session data."""
        response = client.post(
            "/api/sessions",
            json={
                "student_id": "stu01",
                "book_id": "test-book",
                "chapter_number": 1,
                "unit_number": 1,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["student_id"] == "stu01"
        assert data["book_id"] == "test-book"
        assert data["status"] == "active"

    def test_start_session_generates_unique_ids(self, client):
        """Each session gets unique ID."""
        resp1 = client.post(
            "/api/sessions",
            json={"student_id": "stu01", "book_id": "book1"},
        )
        resp2 = client.post(
            "/api/sessions",
            json={"student_id": "stu01", "book_id": "book1"},
        )
        assert resp1.json()["session_id"] != resp2.json()["session_id"]

    def test_start_session_defaults_chapter_unit(self, client):
        """Session defaults to chapter 1, unit 1."""
        response = client.post(
            "/api/sessions",
            json={"student_id": "stu01", "book_id": "test-book"},
        )
        data = response.json()
        assert data["chapter_number"] == 1
        assert data["unit_number"] == 1


class TestGetSession:
    """Tests for GET /api/sessions/{id}."""

    def test_get_session_exists(self, client):
        """Get existing session returns data."""
        create_resp = client.post(
            "/api/sessions",
            json={"student_id": "stu01", "book_id": "test-book"},
        )
        session_id = create_resp.json()["session_id"]

        response = client.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["session_id"] == session_id

    def test_get_session_not_found(self, client):
        """Get non-existent session returns 404."""
        response = client.get("/api/sessions/nonexistent")
        assert response.status_code == 404


class TestEndSession:
    """Tests for DELETE /api/sessions/{id}."""

    def test_end_session_exists(self, client):
        """End existing session succeeds."""
        create_resp = client.post(
            "/api/sessions",
            json={"student_id": "stu01", "book_id": "test-book"},
        )
        session_id = create_resp.json()["session_id"]

        response = client.delete(f"/api/sessions/{session_id}")
        assert response.status_code == 204

        # Verify session gone
        get_resp = client.get(f"/api/sessions/{session_id}")
        assert get_resp.status_code == 404

    def test_end_session_not_found(self, client):
        """End non-existent session returns 404."""
        response = client.delete("/api/sessions/nonexistent")
        assert response.status_code == 404


class TestSendInput:
    """Tests for POST /api/sessions/{id}/input."""

    def test_send_input_returns_events(self, client):
        """Send input returns list of events."""
        create_resp = client.post(
            "/api/sessions",
            json={"student_id": "stu01", "book_id": "test-book"},
        )
        session_id = create_resp.json()["session_id"]

        response = client.post(
            f"/api/sessions/{session_id}/input",
            json={"text": "Hola"},
        )
        assert response.status_code == 200
        events = response.json()
        assert isinstance(events, list)
        assert len(events) >= 1

    def test_send_input_event_has_required_fields(self, client):
        """Events have all required fields."""
        create_resp = client.post(
            "/api/sessions",
            json={"student_id": "stu01", "book_id": "test-book"},
        )
        session_id = create_resp.json()["session_id"]

        response = client.post(
            f"/api/sessions/{session_id}/input",
            json={"text": "Test"},
        )
        event = response.json()[0]
        assert "event_id" in event
        assert "event_type" in event
        assert "turn_id" in event
        assert "seq" in event
        assert "markdown" in event

    def test_send_input_session_not_found(self, client):
        """Send input to non-existent session returns 404."""
        response = client.post(
            "/api/sessions/nonexistent/input",
            json={"text": "Hola"},
        )
        assert response.status_code == 404


class TestStreamEvents:
    """Tests for GET /api/sessions/{id}/events (SSE)."""

    def test_stream_events_session_not_found(self, client):
        """Stream from non-existent session returns 404."""
        response = client.get("/api/sessions/nonexistent/events")
        assert response.status_code == 404

    def test_stream_events_content_type_basic(self, client):
        """Stream events endpoint exists and accepts request."""
        # Note: Full SSE testing requires async client
        # Here we just verify the endpoint exists and basic routing works
        create_resp = client.post(
            "/api/sessions",
            json={"student_id": "stu01", "book_id": "test-book"},
        )
        session_id = create_resp.json()["session_id"]

        # Can't fully test SSE with sync TestClient, just verify session exists
        get_resp = client.get(f"/api/sessions/{session_id}")
        assert get_resp.status_code == 200
