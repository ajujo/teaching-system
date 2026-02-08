"""Tests for notes generator module."""

import json
from pathlib import Path

import pytest

from teaching.core.notes_generator import (
    NotesGenerationError,
    NotesMetadata,
    NotesResult,
    TextSelection,
    chunk_text,
    generate_notes,
    sanitize_output,
    select_unit_text,
)


class TestTextSelection:
    """Tests for text selection from book content."""

    def test_select_from_pages(self, sample_book_with_content):
        """Test text selection using individual page files."""
        book_id = "test-book"
        units_path = sample_book_with_content / "books" / book_id / "artifacts" / "units" / "units.json"
        outline_path = sample_book_with_content / "books" / book_id / "outline" / "outline.json"

        with open(units_path) as f:
            units_data = json.load(f)
        with open(outline_path) as f:
            outline = json.load(f)

        unit = units_data["units"][0]  # First unit

        selection = select_unit_text(
            book_id=book_id,
            unit=unit,
            outline=outline,
            data_dir=sample_book_with_content,
        )

        assert isinstance(selection, TextSelection)
        assert selection.source == "pages"
        assert selection.total_chars > 0
        assert len(selection.pages) > 0
        assert selection.start_page >= 1
        assert selection.end_page >= selection.start_page

    def test_select_fallback_to_content(self, sample_book_content_only):
        """Test fallback to content.txt when no pages directory."""
        book_id = "test-book-content"
        units_path = sample_book_content_only / "books" / book_id / "artifacts" / "units" / "units.json"
        outline_path = sample_book_content_only / "books" / book_id / "outline" / "outline.json"

        with open(units_path) as f:
            units_data = json.load(f)
        with open(outline_path) as f:
            outline = json.load(f)

        unit = units_data["units"][0]

        selection = select_unit_text(
            book_id=book_id,
            unit=unit,
            outline=outline,
            data_dir=sample_book_content_only,
        )

        assert selection.source == "content"
        assert selection.total_chars > 0

    def test_select_no_content_raises_error(self, tmp_path):
        """Test error when no content exists."""
        book_id = "empty-book"
        book_path = tmp_path / "data" / "books" / book_id
        book_path.mkdir(parents=True)

        unit = {"section_ids": []}
        outline = {"chapters": []}

        with pytest.raises(NotesGenerationError, match="No se encontró contenido"):
            select_unit_text(
                book_id=book_id,
                unit=unit,
                outline=outline,
                data_dir=tmp_path / "data",
            )


class TestChunking:
    """Tests for text chunking."""

    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        # Create text with clear paragraphs
        text = "Paragraph one content here.\n\nParagraph two more content.\n\nParagraph three."
        pages = [1, 2, 3]

        chunks = chunk_text(text, pages, chunk_size=(10, 50))

        assert len(chunks) > 0
        # Each chunk is (text, pages) tuple
        for chunk_text_content, chunk_pages in chunks:
            assert isinstance(chunk_text_content, str)
            assert isinstance(chunk_pages, list)
            assert len(chunk_text_content) > 0

    def test_chunk_text_empty(self):
        """Test chunking empty text."""
        chunks = chunk_text("", [], chunk_size=(100, 500))
        assert chunks == []

    def test_chunk_text_respects_max_size(self):
        """Test chunks don't exceed max size significantly."""
        # Create long text
        text = "\n\n".join(["This is paragraph number {}.".format(i) * 20 for i in range(50)])
        pages = list(range(1, 51))

        chunks = chunk_text(text, pages, chunk_size=(500, 1000))

        for chunk_text_content, _ in chunks:
            # Allow some overflow for paragraph completion
            assert len(chunk_text_content) < 1500

    def test_chunk_text_page_tracking(self):
        """Test that pages are tracked through chunks."""
        text = "First part.\n\nSecond part.\n\nThird part."
        pages = [1, 2, 3, 4, 5]

        chunks = chunk_text(text, pages, chunk_size=(5, 20))

        # All returned pages should be from original list
        all_chunk_pages = []
        for _, chunk_pages in chunks:
            all_chunk_pages.extend(chunk_pages)

        for page in all_chunk_pages:
            assert page in pages


class TestGenerateNotes:
    """Tests for the main generate_notes function."""

    def test_notes_path_created(self, sample_book_with_content, mock_llm_client):
        """Test that notes .md and .json files are created."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        result = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is True
        assert result.notes_path is not None
        assert result.metadata_path is not None
        assert result.notes_path.exists()
        assert result.metadata_path.exists()
        assert result.notes_path.suffix == ".md"
        assert result.metadata_path.suffix == ".json"

    def test_notes_content_structure(self, sample_book_with_content, mock_llm_client):
        """Test that generated notes have expected structure."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        result = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is True
        notes_content = result.notes_path.read_text()

        # Check for required sections
        assert "# Apuntes" in notes_content
        assert "## Resumen" in notes_content
        assert "## Conceptos clave" in notes_content
        assert "## Preguntas de repaso" in notes_content
        assert "Fuentes" in notes_content or "Páginas" in notes_content

    def test_metadata_structure(self, sample_book_with_content, mock_llm_client):
        """Test that metadata JSON has expected fields."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        result = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is True

        with open(result.metadata_path) as f:
            metadata = json.load(f)

        assert metadata["unit_id"] == unit_id
        assert metadata["book_id"] == book_id
        assert "provider" in metadata
        assert "model" in metadata
        assert "pages_used" in metadata
        assert "start_page" in metadata
        assert "end_page" in metadata
        assert "chunks_processed" in metadata
        assert "generation_time_ms" in metadata
        assert "created_at" in metadata

    def test_force_overwrite(self, sample_book_with_content, mock_llm_client):
        """Test that --force overwrites existing notes."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        # Generate first time
        result1 = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )
        assert result1.success is True

        # Try without force - should fail
        result2 = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
            force=False,
        )
        assert result2.success is False
        assert "ya existen" in result2.message or "force" in result2.message.lower()

        # Try with force - should succeed
        result3 = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
            force=True,
        )
        assert result3.success is True

    def test_unit_not_found_error(self, sample_book_with_content, mock_llm_client):
        """Test error when unit_id doesn't exist."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch99-u99"  # Non-existent unit

        result = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is False
        assert "no encontrada" in result.message.lower() or "not found" in result.message.lower()

    def test_invalid_unit_id_format(self, sample_book_with_content, mock_llm_client):
        """Test error for invalid unit_id format."""
        result = generate_notes(
            unit_id="invalid-format",
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is False
        assert "inválido" in result.message.lower() or "invalid" in result.message.lower()

    def test_book_not_found_error(self, tmp_path, mock_llm_client):
        """Test error when book doesn't exist."""
        result = generate_notes(
            unit_id="nonexistent-book-ch01-u01",
            data_dir=tmp_path,
            client=mock_llm_client,
        )

        assert result.success is False

    def test_missing_units_json_error(self, tmp_path, mock_llm_client):
        """Test error when units.json doesn't exist."""
        book_id = "test-book"
        book_path = tmp_path / "books" / book_id
        book_path.mkdir(parents=True)

        result = generate_notes(
            unit_id=f"{book_id}-ch01-u01",
            data_dir=tmp_path,
            client=mock_llm_client,
        )

        assert result.success is False
        assert "units.json" in result.message

    def test_no_pages_fallback_warning(self, sample_book_content_only, mock_llm_client):
        """Test warning when using content.txt fallback."""
        book_id = "test-book-content"
        unit_id = f"{book_id}-ch01-u01"

        result = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_content_only,
            client=mock_llm_client,
        )

        assert result.success is True
        # Should have warning about using content.txt
        assert any("content.txt" in w.lower() for w in result.warnings)

    def test_book_json_updated(self, sample_book_with_content, mock_llm_client):
        """Test that book.json is updated after notes generation."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"
        book_json_path = sample_book_with_content / "books" / book_id / "book.json"

        # Read initial state
        with open(book_json_path) as f:
            initial_data = json.load(f)
        initial_count = initial_data.get("notes_generated_count", 0)

        # Generate notes
        result = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )
        assert result.success is True

        # Check book.json was updated
        with open(book_json_path) as f:
            updated_data = json.load(f)

        assert updated_data.get("notes_generated_count", 0) == initial_count + 1
        assert "last_notes_generated_at" in updated_data

    def test_traceability_present(self, sample_book_with_content, mock_llm_client):
        """Test that notes contain source page traceability."""
        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        result = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is True

        # Check notes content for source reference
        notes_content = result.notes_path.read_text()
        assert "Fuentes" in notes_content or "Páginas" in notes_content

        # Check metadata has page info
        with open(result.metadata_path) as f:
            metadata = json.load(f)
        assert len(metadata["pages_used"]) > 0
        assert metadata["start_page"] >= 1
        assert metadata["end_page"] >= metadata["start_page"]


class TestLLMClientUnavailable:
    """Tests for handling unavailable LLM server."""

    def test_llm_unavailable_error(self, sample_book_with_content, mock_llm_client):
        """Test error when LLM server is not available."""
        mock_llm_client.is_available.return_value = False

        book_id = "test-book"
        unit_id = f"{book_id}-ch01-u01"

        result = generate_notes(
            unit_id=unit_id,
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is False
        assert "conectar" in result.message.lower() or "llm" in result.message.lower()


class TestNotesMetadata:
    """Tests for NotesMetadata dataclass."""

    def test_metadata_to_dict(self):
        """Test metadata serialization."""
        metadata = NotesMetadata(
            unit_id="test-ch01-u01",
            book_id="test",
            provider="lmstudio",
            model="test-model",
            pages_used=[1, 2, 3, 4, 5],
            start_page=1,
            end_page=5,
            chunks_processed=2,
            total_tokens=1000,
            generation_time_ms=5000,
            created_at="2024-01-01T00:00:00Z",
        )

        d = metadata.to_dict()

        assert d["unit_id"] == "test-ch01-u01"
        assert d["book_id"] == "test"
        assert d["provider"] == "lmstudio"
        assert d["pages_used"] == [1, 2, 3, 4, 5]
        assert d["chunks_processed"] == 2


class TestChunkSummaryFallback:
    """Tests for chunk summary fallback when JSON fails."""

    def test_chunk_summary_uses_text_fallback(self, sample_book_with_content):
        """If JSON fails, should use simple_chat and mark mode=text_fallback."""
        from unittest.mock import MagicMock
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True

        # simple_json fails, simple_chat works
        mock_client.simple_json.side_effect = LLMError("JSON mode not supported")
        mock_client.simple_chat.return_value = "Resumen en texto plano del contenido. Este es un resumen de prueba."

        result = generate_notes(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_content,
            client=mock_client,
        )

        assert result.success is True
        # Should have warning about fallback
        assert any("fallback" in w.lower() for w in result.warnings)

    def test_metadata_tracks_chunk_modes(self, sample_book_with_content, mock_llm_client):
        """Metadata should include count of modes used per chunk."""
        result = generate_notes(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is True
        with open(result.metadata_path) as f:
            metadata = json.load(f)

        assert "chunk_modes" in metadata
        # With mock_llm_client, all chunks use json mode
        assert metadata["chunk_modes"]["json"] >= 0

    def test_metadata_chunk_modes_with_fallback(self, sample_book_with_content):
        """Metadata should correctly track text_fallback mode."""
        from unittest.mock import MagicMock
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True

        # All JSON calls fail, text works
        mock_client.simple_json.side_effect = LLMError("JSON error")
        mock_client.simple_chat.return_value = "Texto fallback de resumen."

        result = generate_notes(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_content,
            client=mock_client,
        )

        assert result.success is True

        with open(result.metadata_path) as f:
            metadata = json.load(f)

        assert "chunk_modes" in metadata
        # All chunks should be text_fallback
        assert metadata["chunk_modes"]["text_fallback"] > 0
        assert metadata["chunk_modes"]["json"] == 0

    def test_notes_generated_despite_json_failures(self, sample_book_with_content):
        """Should still generate notes even if all JSON calls fail."""
        from unittest.mock import MagicMock
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test-model"
        mock_client.is_available.return_value = True

        # JSON fails, text works
        mock_client.simple_json.side_effect = LLMError("JSON error")
        mock_client.simple_chat.return_value = """# Apuntes — Test Book — Ch1

## Resumen
- Punto 1
- Punto 2

## Conceptos clave
| Concepto | Definición |
|----------|------------|
| Test | Prueba |

## Preguntas de repaso
1. ¿Qué es?

## Fuentes
Páginas utilizadas: 1-15
"""

        result = generate_notes(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_content,
            client=mock_client,
        )

        assert result.success is True
        assert result.notes_path.exists()

        # Notes should have content
        notes_content = result.notes_path.read_text()
        assert len(notes_content) > 100


class TestSanitization:
    """Tests for output sanitization."""

    def test_sanitize_removes_think_tags(self):
        """Removes <think>...</think> blocks."""
        from teaching.core.notes_generator import sanitize_output

        text = "Intro <think>internal reasoning</think> conclusion"
        result = sanitize_output(text)
        assert "<think>" not in result
        assert "internal reasoning" not in result
        assert "Intro" in result
        assert "conclusion" in result

    def test_sanitize_removes_multiline_think(self):
        """Removes multiline thinking blocks."""
        from teaching.core.notes_generator import sanitize_output

        text = """# Title
<think>
This is my reasoning
across multiple lines
</think>
Content here"""
        result = sanitize_output(text)
        assert "<think>" not in result
        assert "</think>" not in result
        assert "This is my reasoning" not in result
        assert "# Title" in result
        assert "Content here" in result

    def test_sanitize_removes_analysis_tags(self):
        """Removes <analysis>...</analysis> blocks."""
        from teaching.core.notes_generator import sanitize_output

        text = "Start <analysis>detailed analysis here</analysis> end"
        result = sanitize_output(text)
        assert "<analysis>" not in result
        assert "detailed analysis" not in result

    def test_sanitize_removes_reasoning_tags(self):
        """Removes <reasoning>...</reasoning> blocks."""
        from teaching.core.notes_generator import sanitize_output

        text = "Question <reasoning>step by step</reasoning> answer"
        result = sanitize_output(text)
        assert "<reasoning>" not in result
        assert "step by step" not in result

    def test_sanitize_case_insensitive(self):
        """Tag removal is case insensitive."""
        from teaching.core.notes_generator import sanitize_output

        text = "Start <THINK>uppercase</THINK> <Think>mixed</Think> end"
        result = sanitize_output(text)
        assert "<THINK>" not in result
        assert "<Think>" not in result
        assert "uppercase" not in result
        assert "mixed" not in result

    def test_sanitize_preserves_normal_content(self):
        """Content without thinking tags is preserved."""
        from teaching.core.notes_generator import sanitize_output

        text = """# Apuntes

## Resumen
- Punto importante
- Otro punto

## Conceptos
| Concepto | Definición |
|----------|------------|
| Test | Prueba |"""

        result = sanitize_output(text)
        assert result == text.strip()

    def test_generated_markdown_no_think_tags(self, sample_book_with_content):
        """Generated markdown must not contain <think> tags."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.config.provider = "lmstudio"
        mock_client.config.model = "test"
        mock_client.is_available.return_value = True

        # Mock returns content with think tags
        mock_client.simple_json.return_value = {
            "resumen": "Test summary",
            "puntos_clave": ["punto 1"],
            "conceptos_definidos": [],
        }
        mock_client.simple_chat.return_value = """# Apuntes
<think>Let me analyze this document...</think>
## Resumen
- Punto importante

<think>Now for concepts...</think>
## Conceptos clave
| Concepto | Definición |
|----------|------------|

## Fuentes
Páginas utilizadas: 1-5"""

        result = generate_notes(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_content,
            client=mock_client,
        )

        assert result.success is True
        content = result.notes_path.read_text()
        assert "<think>" not in content
        assert "</think>" not in content
        assert "Let me analyze" not in content
        assert "Now for concepts" not in content
        # But regular content is preserved
        assert "# Apuntes" in content
        assert "Resumen" in content


class TestTokensMetadata:
    """Tests for tokens tracking in metadata."""

    def test_total_tokens_null_when_no_usage(self, sample_book_with_content, mock_llm_client):
        """total_tokens should be null (not 0) when usage unavailable."""
        result = generate_notes(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is True
        with open(result.metadata_path) as f:
            metadata = json.load(f)

        # Should be null (None in Python), not 0
        assert metadata["total_tokens"] is None

    def test_metadata_total_tokens_type(self, sample_book_with_content, mock_llm_client):
        """NotesMetadata.total_tokens accepts None value."""
        result = generate_notes(
            unit_id="test-book-ch01-u01",
            data_dir=sample_book_with_content,
            client=mock_llm_client,
        )

        assert result.success is True
        # Metadata object should have None for total_tokens when no usage tracked
        assert result.metadata.total_tokens is None
