"""Pytest configuration for phased testing.

Tests are organized by phase (f2, f3, ..., f8).
Only tests for the current phase and completed phases should run.
Future phase tests are automatically skipped.
"""

import pytest

# Current implementation phase
CURRENT_PHASE = 8


def pytest_collection_modifyitems(config, items):
    """Skip tests from phases that haven't been implemented yet."""
    for item in items:
        # Extract phase from path (tests/f2/... -> 2)
        parts = item.fspath.strpath.split("/")
        for part in parts:
            if part.startswith("f") and part[1:].isdigit():
                test_phase = int(part[1:])
                if test_phase > CURRENT_PHASE:
                    item.add_marker(
                        pytest.mark.skip(
                            reason=f"Phase F{test_phase} not yet implemented (current: F{CURRENT_PHASE})"
                        )
                    )
                break
