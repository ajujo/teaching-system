"""Tests for books endpoints (F9.1)."""

import pytest
from fastapi.testclient import TestClient

from teaching.web.api import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


class TestListBooks:
    """Tests for GET /api/books."""

    def test_list_books_returns_list(self, client):
        """List books returns a list."""
        response = client.get("/api/books")
        assert response.status_code == 200
        data = response.json()
        assert "books" in data
        assert "count" in data
        assert isinstance(data["books"], list)
        assert data["count"] == len(data["books"])

    def test_list_books_have_required_fields(self, client):
        """Each book has required fields."""
        response = client.get("/api/books")
        data = response.json()

        # May be empty if no books in data dir
        if data["books"]:
            book = data["books"][0]
            assert "id" in book
            assert "title" in book
            assert "authors" in book
            assert "total_chapters" in book
            assert "has_outline" in book
            assert "has_units" in book

    def test_list_books_unique_ids(self, client):
        """Book IDs are unique."""
        response = client.get("/api/books")
        data = response.json()

        if len(data["books"]) > 1:
            ids = [b["id"] for b in data["books"]]
            assert len(ids) == len(set(ids)), "Book IDs must be unique"


class TestBooksDebug:
    """Tests for GET /api/books/debug."""

    def test_debug_returns_diagnostic_info(self, client):
        """Debug endpoint returns diagnostic data."""
        response = client.get("/api/books/debug")
        assert response.status_code == 200
        data = response.json()

        # Check all expected fields
        assert "source" in data
        assert "data_dir" in data
        assert "data_dir_exists" in data
        assert "books_dir_exists" in data
        assert "book_dirs_found" in data
        assert "books_with_metadata" in data
        assert "book_ids" in data
        assert "cwd" in data

        # Validate types
        assert isinstance(data["data_dir_exists"], bool)
        assert isinstance(data["books_dir_exists"], bool)
        assert isinstance(data["book_dirs_found"], int)
        assert isinstance(data["books_with_metadata"], int)
        assert isinstance(data["book_ids"], list)

    def test_debug_counts_match_list(self, client):
        """Debug book count matches list endpoint count."""
        debug_response = client.get("/api/books/debug")
        list_response = client.get("/api/books")

        debug_data = debug_response.json()
        list_data = list_response.json()

        assert debug_data["books_with_metadata"] == list_data["count"]


class TestGetBook:
    """Tests for GET /api/books/{book_id}."""

    def test_get_book_not_found(self, client):
        """Get non-existent book returns 404."""
        response = client.get("/api/books/nonexistent-book-12345")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_book_existing(self, client):
        """Get existing book returns details."""
        # First list books to find an existing one
        list_response = client.get("/api/books")
        books = list_response.json()["books"]

        if books:
            book_id = books[0]["id"]
            response = client.get(f"/api/books/{book_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == book_id
            assert "chapters" in data
            assert isinstance(data["chapters"], list)

    def test_get_book_returns_chapters(self, client):
        """Book detail includes chapter information."""
        list_response = client.get("/api/books")
        books = list_response.json()["books"]

        if books:
            # Find a book with chapters
            for book in books:
                if book["total_chapters"] > 0:
                    response = client.get(f"/api/books/{book['id']}")
                    data = response.json()

                    # Should have chapters
                    if data["chapters"]:
                        chapter = data["chapters"][0]
                        assert "number" in chapter
                        assert "title" in chapter
                        assert "unit_count" in chapter
                    break
