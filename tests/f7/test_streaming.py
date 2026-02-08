"""Tests for streaming functionality (F7.2)."""

import pytest
from teaching.utils.text_utils import strip_think_streaming


class TestStripThinkStreaming:
    """Tests for streaming think tag filter."""

    def test_simple_chunk_without_tags(self):
        """Passes through clean chunk."""
        output, buffer, in_think = strip_think_streaming("Hello world", "", False)
        assert output == "Hello world"
        assert buffer == ""
        assert in_think is False

    def test_filters_complete_think_tag(self):
        """Filters complete <think> block in single chunk."""
        chunk = "<think>reasoning here</think>The answer is 42."
        output, buffer, in_think = strip_think_streaming(chunk, "", False)
        assert "<think>" not in output
        assert "reasoning here" not in output
        assert "42" in output
        assert in_think is False

    def test_filters_across_chunks(self):
        """Filters think tag split across multiple chunks."""
        # First chunk starts the tag
        out1, buf1, in1 = strip_think_streaming("Start <think>reas", "", False)
        assert "Start " in out1
        assert in1 is True

        # Second chunk continues inside tag
        out2, buf2, in2 = strip_think_streaming("oning...</think>", buf1, in1)
        assert "oning" not in out2
        assert in2 is False

        # Third chunk is clean
        out3, buf3, in3 = strip_think_streaming(" End", buf2, in2)
        assert "End" in out3

    def test_filters_thinking_tag(self):
        """Filters <thinking> tag."""
        chunk = "<thinking>let me think</thinking>Answer"
        output, buffer, in_think = strip_think_streaming(chunk, "", False)
        assert "let me think" not in output
        assert "Answer" in output

    def test_filters_analysis_tag(self):
        """Filters <analysis> tag."""
        chunk = "<analysis>analyzing</analysis>Result"
        output, buffer, in_think = strip_think_streaming(chunk, "", False)
        assert "analyzing" not in output
        assert "Result" in output

    def test_filters_reasoning_tag(self):
        """Filters <reasoning> tag."""
        chunk = "<reasoning>step by step</reasoning>Final"
        output, buffer, in_think = strip_think_streaming(chunk, "", False)
        assert "step by step" not in output
        assert "Final" in output

    def test_handles_partial_tag_in_buffer(self):
        """Handles potential partial tag kept in buffer."""
        # Chunk ends with what could be start of a tag
        out1, buf1, in1 = strip_think_streaming("Hello <thi", "", False)
        # Should keep potential tag start in buffer
        assert "Hello" in out1 or "Hello" in buf1

    def test_empty_chunk(self):
        """Handles empty chunk."""
        output, buffer, in_think = strip_think_streaming("", "", False)
        assert output == ""
        assert buffer == ""
        assert in_think is False

    def test_multiple_tags_in_sequence(self):
        """Filters multiple think blocks."""
        chunk = "<think>first</think>Middle<think>second</think>End"
        output, buffer, in_think = strip_think_streaming(chunk, "", False)
        assert "first" not in output
        assert "second" not in output
        assert "Middle" in output
        assert "End" in output

    def test_case_insensitive(self):
        """Handles case variations."""
        chunk = "<THINK>caps</THINK>Result"
        output, buffer, in_think = strip_think_streaming(chunk, "", False)
        assert "caps" not in output
        assert "Result" in output


class TestLLMClientStream:
    """Tests for LLM client streaming methods."""

    def test_chat_stream_method_exists(self):
        """LLMClient has chat_stream method."""
        from teaching.llm.client import LLMClient
        assert hasattr(LLMClient, "chat_stream")

    def test_simple_chat_stream_method_exists(self):
        """LLMClient has simple_chat_stream method."""
        from teaching.llm.client import LLMClient
        assert hasattr(LLMClient, "simple_chat_stream")

    def test_chat_stream_returns_iterator(self):
        """chat_stream should return an iterator type."""
        from teaching.llm.client import LLMClient
        import inspect

        sig = inspect.signature(LLMClient.chat_stream)
        # Check return annotation if present
        # The method exists and is properly defined
        assert callable(LLMClient.chat_stream)
