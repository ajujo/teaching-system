"""Text processing utilities.

Common text manipulation functions used across modules.
"""

import re

# Patterns for removing thinking/reasoning blocks from LLM output
THINK_PATTERNS = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<analysis>.*?</analysis>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE),
]


def strip_think(text: str) -> str:
    """Remove thinking/reasoning tags and prefixes from LLM output.

    Removes:
    - <think>...</think> blocks
    - <thinking>...</thinking> blocks
    - <analysis>...</analysis> blocks
    - <reasoning>...</reasoning> blocks
    - "Pensando..." prefix lines

    Args:
        text: Raw LLM output text

    Returns:
        Cleaned text without thinking artifacts
    """
    result = text
    for pattern in THINK_PATTERNS:
        result = pattern.sub("", result)

    # Remove "Pensando..." prefix if present
    lines = result.strip().split("\n")
    if lines and lines[0].strip().lower().startswith("pensando"):
        lines = lines[1:]

    return "\n".join(lines).strip()


def strip_think_streaming(
    chunk: str, buffer: str, in_think: bool
) -> tuple[str, str, bool]:
    """Process a streaming chunk, filtering out <think> tags in real-time.

    Handles <think>, <thinking>, <analysis>, <reasoning> tags.
    Maintains state across chunks to handle tags that span multiple chunks.

    Args:
        chunk: New text chunk from streaming
        buffer: Accumulated buffer from previous calls
        in_think: Whether we're currently inside a think tag

    Returns:
        Tuple of (output_text, new_buffer, new_in_think_state)
    """
    buffer += chunk
    output = ""

    # Tag patterns to filter (lowercase for comparison)
    open_tags = ["<think>", "<thinking>", "<analysis>", "<reasoning>"]
    close_tags = ["</think>", "</thinking>", "</analysis>", "</reasoning>"]

    while True:
        buffer_lower = buffer.lower()

        if in_think:
            # Look for any closing tag
            close_idx = -1
            close_len = 0
            for tag in close_tags:
                idx = buffer_lower.find(tag)
                if idx >= 0 and (close_idx < 0 or idx < close_idx):
                    close_idx = idx
                    close_len = len(tag)

            if close_idx >= 0:
                # Found closing tag - skip everything up to and including it
                buffer = buffer[close_idx + close_len :]
                in_think = False
            else:
                # No closing tag yet - keep waiting
                break
        else:
            # Look for any opening tag
            open_idx = -1
            open_len = 0
            for tag in open_tags:
                idx = buffer_lower.find(tag)
                if idx >= 0 and (open_idx < 0 or idx < open_idx):
                    open_idx = idx
                    open_len = len(tag)

            if open_idx >= 0:
                # Found opening tag - output everything before it
                output += buffer[:open_idx]
                buffer = buffer[open_idx + open_len :]
                in_think = True
            elif any(tag[:-1] in buffer_lower for tag in open_tags):
                # Partial tag might be forming - keep in buffer
                # Find the earliest partial match
                for i in range(len(buffer)):
                    remainder = buffer[i:].lower()
                    if any(tag.startswith(remainder) for tag in open_tags):
                        output += buffer[:i]
                        buffer = buffer[i:]
                        break
                break
            else:
                # No tags - output everything
                output += buffer
                buffer = ""
                break

    return output, buffer, in_think


# =============================================================================
# THROTTLED STREAMING (F7.3)
# =============================================================================


class ThrottledStreamer:
    """Wrapper para streaming con control de velocidad (typewriter effect).

    Permite controlar la velocidad de salida del texto para crear
    un efecto de máquina de escribir configurable.

    Usage:
        streamer = ThrottledStreamer(pace="normal")
        for char in streamer.stream(llm_chunks):
            print(char, end="", flush=True)
    """

    PACE_CONFIGS = {
        "slow": {"chars_per_sec": 30, "description": "Lectura pausada"},
        "normal": {"chars_per_sec": 60, "description": "Velocidad natural"},
        "fast": {"chars_per_sec": 120, "description": "Lectura rápida"},
    }

    def __init__(self, pace: str = "normal"):
        """Inicializa el streamer con la velocidad especificada.

        Args:
            pace: "slow", "normal", o "fast"
        """
        self.config = self.PACE_CONFIGS.get(pace, self.PACE_CONFIGS["normal"])
        self.skip = False
        self._delay = 1.0 / self.config["chars_per_sec"]

    def stream(self, chunks: "Iterator[str]") -> "Iterator[str]":
        """Yield caracteres con throttle configurable.

        Args:
            chunks: Iterator de chunks de texto del LLM

        Yields:
            Caracteres individuales con delay entre ellos
        """
        import time
        from typing import Iterator

        for chunk in chunks:
            if self.skip:
                # Si skip está activado, yield todo el chunk sin delay
                yield chunk
            else:
                # Yield caracter por caracter con delay
                for char in chunk:
                    yield char
                    time.sleep(self._delay)

    def skip_throttle(self) -> None:
        """Desactiva el throttle para imprimir todo inmediatamente."""
        self.skip = True

    @classmethod
    def get_pace_options(cls) -> list[str]:
        """Retorna las opciones de pace disponibles."""
        return list(cls.PACE_CONFIGS.keys())
