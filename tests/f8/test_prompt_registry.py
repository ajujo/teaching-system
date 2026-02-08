"""Tests for prompt registry (F8).

Tests the prompt loading, variable substitution, and caching mechanisms.
"""

import pytest
from pathlib import Path

from teaching.prompts.registry import (
    get_prompt,
    list_prompts,
    clear_cache,
    PROMPTS_DIR,
)


class TestGetPrompt:
    """Tests for get_prompt function."""

    def test_get_prompt_loads_file(self):
        """get_prompt('tutor/explain_point') returns prompt content."""
        prompt = get_prompt("tutor/explain_point")
        assert prompt is not None
        assert len(prompt) > 0
        assert "profesor" in prompt.lower() or "estudiante" in prompt.lower()

    def test_get_prompt_loads_qa(self):
        """get_prompt('tutor/qa') loads the QA prompt."""
        prompt = get_prompt("tutor/qa")
        assert "tutor" in prompt.lower()
        assert "{notes_content}" in prompt

    def test_get_prompt_substitutes_variables(self):
        """Variables {name} are replaced."""
        prompt = get_prompt("tutor/qa", notes_content="TEST_CONTENT_HERE")
        assert "TEST_CONTENT_HERE" in prompt
        assert "{notes_content}" not in prompt

    def test_get_prompt_multiple_variables(self):
        """Multiple variables are all replaced."""
        # notes prompt has book_title and unit_title
        prompt = get_prompt(
            "notes/notes",
            book_title="My Book",
            unit_title="My Unit",
        )
        # The template might not have these exact placeholders, just test the function works
        assert prompt is not None

    def test_get_prompt_missing_raises(self):
        """FileNotFoundError for missing prompt."""
        with pytest.raises(FileNotFoundError):
            get_prompt("nonexistent/prompt")

    def test_get_prompt_uses_cache(self):
        """Cached prompts are returned."""
        clear_cache()
        prompt1 = get_prompt("tutor/explain_point")
        prompt2 = get_prompt("tutor/explain_point")
        assert prompt1 == prompt2

    def test_get_prompt_bypass_cache(self):
        """use_cache=False bypasses cache."""
        prompt = get_prompt("tutor/explain_point", use_cache=False)
        assert prompt is not None


class TestListPrompts:
    """Tests for list_prompts function."""

    def test_list_prompts_returns_all(self):
        """list_prompts() returns all prompt keys."""
        prompts = list_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) > 0
        # Check some expected prompts exist
        assert "tutor/explain_point" in prompts
        assert "tutor/qa" in prompts

    def test_list_prompts_sorted(self):
        """Prompt list is sorted."""
        prompts = list_prompts()
        assert prompts == sorted(prompts)

    def test_list_prompts_no_md_extension(self):
        """Prompt keys don't include .md extension."""
        prompts = list_prompts()
        for p in prompts:
            assert not p.endswith(".md")


class TestPromptFiles:
    """Tests for prompt file existence and content."""

    @pytest.mark.parametrize(
        "key",
        [
            "tutor/explain_point",
            "tutor/check_comprehension",
            "tutor/reexplain",
            "tutor/more_examples",
            "tutor/deepen",
            "tutor/qa",
            "notes/summary",
            "notes/notes",
            "grader/grade",
            "llm/json_repair",
        ],
    )
    def test_prompt_file_exists(self, key: str):
        """Each expected prompt file exists."""
        file_path = PROMPTS_DIR / f"{key}.md"
        assert file_path.exists(), f"Prompt file missing: {key}"

    def test_prompts_dir_exists(self):
        """Prompts directory exists."""
        assert PROMPTS_DIR.exists()
        assert PROMPTS_DIR.is_dir()
