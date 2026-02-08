"""Tests for strip_think() function (F7.1)."""

import pytest

from teaching.utils.text_utils import strip_think


class TestStripThink:
    """Tests for removing think tags from LLM output."""

    def test_removes_think_tags(self):
        """Removes <think>...</think> blocks."""
        text = "<think>Internal reasoning here</think>The actual answer."
        result = strip_think(text)
        assert "<think>" not in result
        assert "Internal reasoning" not in result
        assert "actual answer" in result

    def test_removes_thinking_tags(self):
        """Removes <thinking>...</thinking> blocks."""
        text = "Intro <thinking>Let me think...</thinking> conclusion"
        result = strip_think(text)
        assert "<thinking>" not in result
        assert "Let me think" not in result
        assert "Intro" in result
        assert "conclusion" in result

    def test_removes_analysis_tags(self):
        """Removes <analysis>...</analysis> blocks."""
        text = "<analysis>Analyzing the problem</analysis>Here's my answer."
        result = strip_think(text)
        assert "<analysis>" not in result
        assert "Analyzing" not in result
        assert "answer" in result

    def test_removes_reasoning_tags(self):
        """Removes <reasoning>...</reasoning> blocks."""
        text = "Start <reasoning>step by step</reasoning> End"
        result = strip_think(text)
        assert "<reasoning>" not in result
        assert "step by step" not in result

    def test_removes_multiline_think(self):
        """Removes multiline think blocks."""
        text = """<think>
Line 1
Line 2
Line 3
</think>
The answer is 42."""
        result = strip_think(text)
        assert "<think>" not in result
        assert "Line 1" not in result
        assert "Line 2" not in result
        assert "42" in result

    def test_removes_pensando_prefix(self):
        """Removes 'Pensando...' prefix line."""
        text = "Pensando...\nLa respuesta es correcta."
        result = strip_think(text)
        assert "Pensando" not in result
        assert "respuesta" in result

    def test_removes_pensando_with_variations(self):
        """Removes Pensando prefix with different casing."""
        text = "PENSANDO...\nRespuesta aquí."
        result = strip_think(text)
        assert "PENSANDO" not in result
        assert "Respuesta" in result

    def test_preserves_clean_text(self):
        """Preserves text without think tags."""
        text = "This is a clean response without any tags."
        result = strip_think(text)
        assert result == text

    def test_case_insensitive(self):
        """Handles case variations of tags."""
        text = "<THINK>caps</THINK><Think>Mixed</Think>Result"
        result = strip_think(text)
        assert "caps" not in result
        assert "Mixed" not in result
        assert "Result" in result

    def test_multiple_think_blocks(self):
        """Removes multiple think blocks."""
        text = "<think>first</think>Middle<think>second</think>End"
        result = strip_think(text)
        assert "first" not in result
        assert "second" not in result
        assert "Middle" in result
        assert "End" in result

    def test_nested_content_preserved(self):
        """Content between think blocks is preserved."""
        text = "<think>hidden</think>Visible content here.<think>also hidden</think>"
        result = strip_think(text)
        assert "Visible content here" in result
        assert "hidden" not in result

    def test_empty_string(self):
        """Handles empty string."""
        result = strip_think("")
        assert result == ""

    def test_only_think_block(self):
        """Handles text that is only a think block."""
        text = "<think>Only thinking here</think>"
        result = strip_think(text)
        assert result == ""

    def test_whitespace_handling(self):
        """Strips leading/trailing whitespace after removing tags."""
        text = "   <think>thinking</think>  Answer here  "
        result = strip_think(text)
        assert result == "Answer here"

    def test_mixed_tags(self):
        """Handles mix of different tag types."""
        text = "<think>t1</think><analysis>a1</analysis><reasoning>r1</reasoning>Final"
        result = strip_think(text)
        assert "<think>" not in result
        assert "<analysis>" not in result
        assert "<reasoning>" not in result
        assert "Final" in result
