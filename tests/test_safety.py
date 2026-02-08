"""Safety tests to ensure test suite doesn't modify production data.

These tests verify that running the test suite does NOT touch:
- ./data directory (user's books and artifacts)
- ./db directory (user's database)

All tests MUST use temporary directories via pytest fixtures.
"""

import hashlib
import os
from pathlib import Path

import pytest


def _hash_directory(path: Path) -> str | None:
    """Create a hash of directory structure and file contents.

    Returns None if directory doesn't exist.
    """
    if not path.exists():
        return None

    hasher = hashlib.sha256()

    for root, dirs, files in os.walk(path):
        # Sort for consistent ordering
        dirs.sort()
        files.sort()

        for filename in files:
            filepath = Path(root) / filename
            # Hash relative path
            rel_path = filepath.relative_to(path)
            hasher.update(str(rel_path).encode())

            # Hash file size and mtime (not content for speed)
            stat = filepath.stat()
            hasher.update(str(stat.st_size).encode())
            hasher.update(str(int(stat.st_mtime)).encode())

    return hasher.hexdigest()


class TestDataDirectorySafety:
    """Tests ensuring ./data is never modified by test suite."""

    @pytest.fixture(scope="class")
    def data_dir_state_before(self):
        """Capture state of ./data before tests."""
        data_path = Path("data")
        return {
            "exists": data_path.exists(),
            "hash": _hash_directory(data_path),
        }

    def test_data_directory_not_created(self, data_dir_state_before):
        """Test suite should not create ./data if it didn't exist."""
        data_path = Path("data")

        if not data_dir_state_before["exists"]:
            # If data/ didn't exist before, it shouldn't exist now
            # (unless user created it manually during test run)
            if data_path.exists():
                pytest.fail(
                    "./data directory was created during test run. "
                    "All tests MUST use temporary directories."
                )

    def test_data_directory_not_modified(self, data_dir_state_before):
        """Test suite should not modify ./data if it existed."""
        data_path = Path("data")

        if data_dir_state_before["exists"]:
            current_hash = _hash_directory(data_path)
            if current_hash != data_dir_state_before["hash"]:
                pytest.fail(
                    "./data directory was modified during test run. "
                    "All tests MUST use temporary directories. "
                    "Never import, extract, or normalize to ./data in tests."
                )


class TestDatabaseDirectorySafety:
    """Tests ensuring ./db is never modified by test suite."""

    @pytest.fixture(scope="class")
    def db_dir_state_before(self):
        """Capture state of ./db before tests."""
        db_path = Path("db")
        return {
            "exists": db_path.exists(),
            "hash": _hash_directory(db_path),
        }

    def test_db_directory_not_created(self, db_dir_state_before):
        """Test suite should not create ./db if it didn't exist."""
        db_path = Path("db")

        if not db_dir_state_before["exists"]:
            if db_path.exists():
                pytest.fail(
                    "./db directory was created during test run. "
                    "All tests MUST use temporary directories for databases."
                )

    def test_db_directory_not_modified(self, db_dir_state_before):
        """Test suite should not modify ./db if it existed."""
        db_path = Path("db")

        if db_dir_state_before["exists"]:
            current_hash = _hash_directory(db_path)
            if current_hash != db_dir_state_before["hash"]:
                pytest.fail(
                    "./db directory was modified during test run. "
                    "All tests MUST use temporary directories for databases."
                )


class TestTestIsolation:
    """Meta-tests ensuring test fixtures use temp directories."""

    def test_f2_tests_use_temp_fixtures(self):
        """Verify F2 test files use temp_dir fixtures, not ./data."""
        import ast

        test_files = [
            Path("tests/f2/test_importer.py"),
            Path("tests/f2/test_extractors.py"),
            Path("tests/f2/test_normalizer.py"),
            Path("tests/f2/test_outline.py"),
        ]

        violations = []

        for test_file in test_files:
            if not test_file.exists():
                continue

            content = test_file.read_text()

            # Check for hardcoded data/ or db/ paths
            if 'Path("data")' in content or "Path('data')" in content:
                if "temp_dir" not in content and "tmp_path" not in content:
                    violations.append(f"{test_file}: Uses Path('data') without temp fixtures")

            if 'Path("db")' in content or "Path('db')" in content:
                if "temp_dir" not in content and "tmp_path" not in content:
                    violations.append(f"{test_file}: Uses Path('db') without temp fixtures")

            # Check for init_db without temp path
            if "init_db()" in content:  # No arguments = default path
                violations.append(f"{test_file}: Calls init_db() without explicit temp path")

        if violations:
            pytest.fail(
                "Test files may not be properly isolated:\n" +
                "\n".join(f"  - {v}" for v in violations)
            )
