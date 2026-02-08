"""Prompt Registry - Load prompts from external files.

This module provides a centralized way to load and manage prompts
from external Markdown files, supporting variable substitution.

Usage:
    from teaching.prompts.registry import get_prompt

    prompt = get_prompt(
        "tutor/explain_point",
        student_name="Ana",
        persona_name="Dra. Vega",
    )
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Default prompts directory (relative to project root)
PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


def _get_prompt_uncached(key: str) -> str:
    """Load raw prompt from file without caching.

    Args:
        key: Path-like key, e.g., "tutor/explain_point"

    Returns:
        Raw prompt content

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    file_path = PROMPTS_DIR / f"{key}.md"
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt not found: {key} (looked at {file_path})")

    return file_path.read_text(encoding="utf-8")


@lru_cache(maxsize=64)
def _get_cached_prompt(key: str) -> str:
    """Cached version of prompt loading."""
    return _get_prompt_uncached(key)


def get_prompt(key: str, use_cache: bool = True, **variables: str) -> str:
    """Load prompt from file and substitute variables.

    Variables are substituted using {variable_name} syntax.

    Args:
        key: Path-like key, e.g., "tutor/explain_point"
        use_cache: Whether to use cached version (default True)
        **variables: Variables to substitute, e.g., student_name="Ana"

    Returns:
        Prompt string with variables substituted

    Raises:
        FileNotFoundError: If prompt file doesn't exist

    Example:
        >>> prompt = get_prompt(
        ...     "tutor/explain_point",
        ...     student_name="Ana",
        ...     persona_name="Dra. Vega",
        ... )
    """
    if use_cache:
        content = _get_cached_prompt(key)
    else:
        content = _get_prompt_uncached(key)

    # Substitute variables: {name} -> value
    for var_name, var_value in variables.items():
        content = content.replace(f"{{{var_name}}}", str(var_value))

    return content


def list_prompts() -> list[str]:
    """List all available prompt keys.

    Returns:
        Sorted list of prompt keys (e.g., ["tutor/explain_point", "tutor/qa"])
    """
    if not PROMPTS_DIR.exists():
        logger.warning("prompts_dir_not_found", path=str(PROMPTS_DIR))
        return []

    prompts = []
    for path in PROMPTS_DIR.rglob("*.md"):
        # Convert path to key format: tutor/explain_point
        key = str(path.relative_to(PROMPTS_DIR)).replace(".md", "").replace("\\", "/")
        prompts.append(key)
    return sorted(prompts)


def clear_cache() -> None:
    """Clear the prompt cache.

    Useful for testing or when prompts are modified at runtime.
    """
    _get_cached_prompt.cache_clear()
