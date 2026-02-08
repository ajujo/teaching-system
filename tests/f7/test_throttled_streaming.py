"""Tests for ThrottledStreamer (F7.3)."""

import pytest
import time
from unittest.mock import patch

from teaching.utils.text_utils import ThrottledStreamer


# =============================================================================
# Test: ThrottledStreamer
# =============================================================================


class TestThrottledStreamer:
    """Tests for ThrottledStreamer class."""

    def test_class_exists(self):
        """ThrottledStreamer existe y se puede instanciar."""
        streamer = ThrottledStreamer()
        assert streamer is not None

    def test_default_pace_is_normal(self):
        """El pace por defecto es 'normal'."""
        streamer = ThrottledStreamer()
        assert streamer.config == ThrottledStreamer.PACE_CONFIGS["normal"]

    def test_slow_pace_config(self):
        """Pace 'slow' tiene configuración correcta."""
        streamer = ThrottledStreamer(pace="slow")
        assert streamer.config["chars_per_sec"] == 30

    def test_normal_pace_config(self):
        """Pace 'normal' tiene configuración correcta."""
        streamer = ThrottledStreamer(pace="normal")
        assert streamer.config["chars_per_sec"] == 60

    def test_fast_pace_config(self):
        """Pace 'fast' tiene configuración correcta."""
        streamer = ThrottledStreamer(pace="fast")
        assert streamer.config["chars_per_sec"] == 120

    def test_invalid_pace_uses_normal(self):
        """Pace inválido usa 'normal' como fallback."""
        streamer = ThrottledStreamer(pace="invalid_pace")
        assert streamer.config == ThrottledStreamer.PACE_CONFIGS["normal"]

    def test_stream_yields_all_content(self):
        """stream() yield todo el contenido."""
        streamer = ThrottledStreamer(pace="fast")
        streamer.skip = True  # Skip throttle for faster test

        chunks = ["Hello", " ", "World"]
        result = "".join(streamer.stream(iter(chunks)))

        assert result == "Hello World"

    def test_skip_throttle_method(self):
        """skip_throttle() desactiva el throttle."""
        streamer = ThrottledStreamer()
        assert streamer.skip is False

        streamer.skip_throttle()

        assert streamer.skip is True

    def test_get_pace_options(self):
        """get_pace_options() retorna las opciones disponibles."""
        options = ThrottledStreamer.get_pace_options()

        assert "slow" in options
        assert "normal" in options
        assert "fast" in options
        assert len(options) == 3

    def test_stream_with_skip_yields_full_chunks(self):
        """Con skip=True, yield chunks completos sin delay."""
        streamer = ThrottledStreamer(pace="slow")
        streamer.skip = True

        chunks = ["ABC", "DEF"]
        result = list(streamer.stream(iter(chunks)))

        # Should yield full chunks, not char by char
        assert result == ["ABC", "DEF"]

    def test_stream_without_skip_yields_chars(self):
        """Sin skip, yield caracteres individuales."""
        streamer = ThrottledStreamer(pace="fast")
        # Use fast pace and mock sleep to avoid slow test

        with patch("time.sleep"):
            chunks = ["AB"]
            result = list(streamer.stream(iter(chunks)))

        # Should yield individual chars
        assert result == ["A", "B"]

    def test_delay_calculation(self):
        """El delay se calcula correctamente basado en chars_per_sec."""
        streamer = ThrottledStreamer(pace="normal")

        expected_delay = 1.0 / 60  # 60 chars per second
        assert abs(streamer._delay - expected_delay) < 0.001


class TestThrottledStreamerTiming:
    """Tests for throttle timing (with mocked sleep)."""

    def test_slow_pace_has_longer_delay(self):
        """Pace slow tiene delay más largo que fast."""
        slow = ThrottledStreamer(pace="slow")
        fast = ThrottledStreamer(pace="fast")

        assert slow._delay > fast._delay

    def test_stream_calls_sleep_per_char(self):
        """stream() llama sleep por cada caracter cuando no skip."""
        streamer = ThrottledStreamer(pace="fast")

        with patch("time.sleep") as mock_sleep:
            chunks = ["ABC"]
            list(streamer.stream(iter(chunks)))

        # Should call sleep 3 times (once per char)
        assert mock_sleep.call_count == 3

    def test_stream_skip_does_not_call_sleep(self):
        """stream() no llama sleep cuando skip=True."""
        streamer = ThrottledStreamer(pace="slow")
        streamer.skip = True

        with patch("time.sleep") as mock_sleep:
            chunks = ["ABC", "DEF"]
            list(streamer.stream(iter(chunks)))

        # Should not call sleep at all
        assert mock_sleep.call_count == 0


class TestThrottledStreamerIntegration:
    """Integration tests for ThrottledStreamer."""

    def test_works_with_empty_input(self):
        """Maneja input vacío correctamente."""
        streamer = ThrottledStreamer()
        streamer.skip = True

        result = list(streamer.stream(iter([])))
        assert result == []

    def test_works_with_empty_chunks(self):
        """Maneja chunks vacíos correctamente."""
        streamer = ThrottledStreamer()
        streamer.skip = True

        chunks = ["", "Hello", ""]
        result = "".join(streamer.stream(iter(chunks)))
        assert result == "Hello"

    def test_preserves_special_characters(self):
        """Preserva caracteres especiales."""
        streamer = ThrottledStreamer()
        streamer.skip = True

        chunks = ["¡Hola!", " 你好 ", "🎉"]
        result = "".join(streamer.stream(iter(chunks)))
        assert result == "¡Hola! 你好 🎉"

    def test_preserves_newlines(self):
        """Preserva saltos de línea."""
        streamer = ThrottledStreamer()
        streamer.skip = True

        chunks = ["Line1\n", "Line2\n"]
        result = "".join(streamer.stream(iter(chunks)))
        assert result == "Line1\nLine2\n"
