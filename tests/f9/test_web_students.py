"""Tests for students endpoints (F9)."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import json

from teaching.web.api import create_app
from teaching.core.tutor import StudentsState, save_students_state


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create test client with isolated state."""
    # Create state directory
    state_dir = tmp_path / "data" / "state"
    state_dir.mkdir(parents=True)

    # Patch the data directory
    monkeypatch.chdir(tmp_path)

    # Initialize empty students state
    empty_state = StudentsState()
    state_file = state_dir / "students_v1.json"
    state_file.write_text(json.dumps(empty_state.to_dict()))

    app = create_app()
    return TestClient(app)


class TestListStudents:
    """Tests for GET /api/students."""

    def test_list_students_empty(self, client):
        """List returns empty array when no students."""
        response = client.get("/api/students")
        assert response.status_code == 200
        data = response.json()
        assert data["students"] == []
        assert data["count"] == 0

    def test_list_students_after_create(self, client):
        """List returns created students."""
        # Create a student
        client.post("/api/students", json={"name": "Ana"})

        response = client.get("/api/students")
        data = response.json()
        assert data["count"] == 1
        assert data["students"][0]["name"] == "Ana"


class TestCreateStudent:
    """Tests for POST /api/students."""

    def test_create_student_minimal(self, client):
        """Create student with just name."""
        response = client.post("/api/students", json={"name": "Pedro"})
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Pedro"
        assert data["student_id"].startswith("stu")

    def test_create_student_full(self, client):
        """Create student with all fields."""
        response = client.post(
            "/api/students",
            json={
                "name": "María",
                "surname": "García",
                "email": "maria@example.com",
                "tutor_persona_id": "profe_nico",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "María"
        assert data["surname"] == "García"
        assert data["email"] == "maria@example.com"
        assert data["tutor_persona_id"] == "profe_nico"

    def test_create_student_invalid_email(self, client):
        """Create student with invalid email fails."""
        response = client.post(
            "/api/students",
            json={"name": "Carlos", "email": "not-an-email"},
        )
        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()

    def test_create_student_duplicate_name(self, client):
        """Create student with duplicate name fails."""
        client.post("/api/students", json={"name": "Ana"})
        response = client.post("/api/students", json={"name": "Ana"})
        assert response.status_code == 409

    def test_create_student_empty_name(self, client):
        """Create student with empty name fails."""
        response = client.post("/api/students", json={"name": ""})
        assert response.status_code == 422  # Validation error


class TestGetStudent:
    """Tests for GET /api/students/{id}."""

    def test_get_student_exists(self, client):
        """Get existing student returns data."""
        create_resp = client.post("/api/students", json={"name": "Luis"})
        student_id = create_resp.json()["student_id"]

        response = client.get(f"/api/students/{student_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Luis"

    def test_get_student_not_found(self, client):
        """Get non-existent student returns 404."""
        response = client.get("/api/students/stu99")
        assert response.status_code == 404


class TestDeleteStudent:
    """Tests for DELETE /api/students/{id}."""

    def test_delete_student_exists(self, client):
        """Delete existing student succeeds."""
        create_resp = client.post("/api/students", json={"name": "ToDelete"})
        student_id = create_resp.json()["student_id"]

        response = client.delete(f"/api/students/{student_id}")
        assert response.status_code == 204

        # Verify deleted
        get_resp = client.get(f"/api/students/{student_id}")
        assert get_resp.status_code == 404

    def test_delete_student_not_found(self, client):
        """Delete non-existent student returns 404."""
        response = client.delete("/api/students/stu99")
        assert response.status_code == 404
