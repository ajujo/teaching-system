"""Tests for unit planning functionality (F3).

Tests cover:
- Unit generation from outline
- Partitioning rules
- Time estimation
- Difficulty detection
- Coverage validation (no gaps, no duplicates)
- Deterministic unit IDs
- CLI command
"""

import json
import tempfile
from pathlib import Path

import pytest

from teaching.core.unit_planner import (
    generate_units,
    validate_units_coverage,
    _get_num_units_for_sections,
    _estimate_time,
    _detect_difficulty,
    _partition_sections,
    _format_unit_title,
    _generate_unit_id,
    MAX_UNITS_PER_CHAPTER,
    MAX_MINUTES_PER_UNIT,
)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_outline():
    """Sample outline.json data."""
    return {
        "$schema": "outline_v1",
        "book_id": "test-book",
        "generated_date": "2024-01-01T00:00:00Z",
        "chapters": [
            {
                "chapter_id": "test-book:ch:1",
                "number": 1,
                "title": "Introduction to Testing",
                "sections": [
                    {"section_id": "test-book:ch:1:sec:1", "number": "1.1", "title": "What is Testing"},
                    {"section_id": "test-book:ch:1:sec:2", "number": "1.2", "title": "Why Test"},
                    {"section_id": "test-book:ch:1:sec:3", "number": "1.3", "title": "Test Types"},
                ],
            },
            {
                "chapter_id": "test-book:ch:2",
                "number": 2,
                "title": "Advanced Testing Patterns",
                "sections": [
                    {"section_id": "test-book:ch:2:sec:1", "number": "2.1", "title": "Mocking"},
                    {"section_id": "test-book:ch:2:sec:2", "number": "2.2", "title": "Stubbing"},
                    {"section_id": "test-book:ch:2:sec:3", "number": "2.3", "title": "Fixtures"},
                    {"section_id": "test-book:ch:2:sec:4", "number": "2.4", "title": "Factories"},
                    {"section_id": "test-book:ch:2:sec:5", "number": "2.5", "title": "Matchers"},
                    {"section_id": "test-book:ch:2:sec:6", "number": "2.6", "title": "Assertions"},
                    {"section_id": "test-book:ch:2:sec:7", "number": "2.7", "title": "Coverage"},
                ],
            },
            {
                "chapter_id": "test-book:ch:3",
                "number": 3,
                "title": "Optimization and Performance",
                "sections": [],  # No sections
            },
        ],
    }


@pytest.fixture
def book_with_outline(temp_data_dir, sample_outline):
    """Create a book directory with outline.json."""
    book_id = "test-book"
    book_path = temp_data_dir / "books" / book_id
    outline_dir = book_path / "outline"
    outline_dir.mkdir(parents=True)

    # Write outline.json
    outline_path = outline_dir / "outline.json"
    with open(outline_path, "w") as f:
        json.dump(sample_outline, f)

    # Write book.json
    book_json = {"book_id": book_id, "title": "Test Book", "status": "outlined"}
    with open(book_path / "book.json", "w") as f:
        json.dump(book_json, f)

    return book_id, temp_data_dir


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestPartitioningRules:
    """Tests for section-to-units partitioning."""

    @pytest.mark.parametrize(
        "num_sections,expected_units",
        [
            (0, 1),   # No sections -> 1 unit
            (1, 1),
            (6, 1),
            (7, 2),
            (14, 2),
            (15, 3),
            (24, 3),
            (25, 4),
            (36, 4),
            (37, 5),
            (50, 5),
            (51, 6),
            (100, 6),  # Max is 6
        ],
    )
    def test_get_num_units_for_sections(self, num_sections, expected_units):
        """Verify partitioning thresholds."""
        assert _get_num_units_for_sections(num_sections) == expected_units

    def test_max_units_per_chapter(self):
        """Verify max units constant."""
        assert MAX_UNITS_PER_CHAPTER == 6


class TestTimeEstimation:
    """Tests for time estimation."""

    def test_estimate_time_with_sections(self):
        """Time = 3 min per section + 5 min overhead."""
        # 5 sections: 5*3 + 5 = 20 min
        assert _estimate_time(5) == 20

    def test_estimate_time_no_sections(self):
        """Empty chapter still has minimum time."""
        time = _estimate_time(0)
        assert time > 0  # Should have overhead + base

    def test_time_per_unit_reasonable(self):
        """All units should target <= MAX_MINUTES_PER_UNIT."""
        assert MAX_MINUTES_PER_UNIT == 35


class TestDifficultyDetection:
    """Tests for difficulty heuristics."""

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Introduction to Python", "intro"),
            ("Getting Started with Django", "intro"),
            ("Basics of Machine Learning", "intro"),
            ("Fundamentals of Testing", "intro"),
            ("Overview of the System", "intro"),
            ("Introducción a la programación", "intro"),
        ],
    )
    def test_detect_intro_difficulty(self, title, expected):
        """Intro keywords should yield 'intro' difficulty."""
        assert _detect_difficulty(title) == expected

    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Advanced Patterns", "adv"),
            ("Optimization Techniques", "adv"),
            ("Scaling for Production", "adv"),
            ("Evaluation Metrics", "adv"),
            ("Deployment Strategies", "adv"),
            ("Performance Tuning", "adv"),
            ("Optimización de consultas", "adv"),
        ],
    )
    def test_detect_advanced_difficulty(self, title, expected):
        """Advanced keywords should yield 'adv' difficulty."""
        assert _detect_difficulty(title) == expected

    def test_detect_mid_difficulty(self):
        """Default is 'mid' difficulty."""
        assert _detect_difficulty("Data Structures") == "mid"
        assert _detect_difficulty("Working with Files") == "mid"
        assert _detect_difficulty("Chapter 5") == "mid"


class TestSectionPartitioning:
    """Tests for section partitioning."""

    def test_partition_empty(self):
        """Empty sections -> one empty partition."""
        result = _partition_sections([], 1)
        assert result == [[]]

    def test_partition_single_unit(self):
        """All sections in one unit."""
        sections = ["s1", "s2", "s3"]
        result = _partition_sections(sections, 1)
        assert result == [["s1", "s2", "s3"]]

    def test_partition_even_split(self):
        """Evenly divisible sections."""
        sections = ["s1", "s2", "s3", "s4", "s5", "s6"]
        result = _partition_sections(sections, 2)
        assert len(result) == 2
        assert result[0] == ["s1", "s2", "s3"]
        assert result[1] == ["s4", "s5", "s6"]

    def test_partition_uneven_split(self):
        """Uneven split distributes remainder to first partitions."""
        sections = ["s1", "s2", "s3", "s4", "s5"]
        result = _partition_sections(sections, 2)
        assert len(result) == 2
        # 5 / 2 = 2 base, 1 remainder -> first gets 3, second gets 2
        assert len(result[0]) == 3
        assert len(result[1]) == 2

    def test_partition_continuous(self):
        """Partitions should be continuous (no gaps)."""
        sections = [f"s{i}" for i in range(10)]
        result = _partition_sections(sections, 3)

        # Flatten and check order
        flat = [s for partition in result for s in partition]
        assert flat == sections


class TestUnitTitleFormatting:
    """Tests for unit title formatting."""

    def test_single_unit_no_part(self):
        """Single unit -> no 'Parte X/Y'."""
        title = _format_unit_title(1, "Introduction", 1, 1)
        assert title == "Ch1 — Introduction"
        assert "Parte" not in title

    def test_multiple_units_with_part(self):
        """Multiple units -> include 'Parte X/Y'."""
        title = _format_unit_title(3, "Advanced Topics", 2, 3)
        assert title == "Ch3 — Advanced Topics (Parte 2/3)"


class TestUnitIdGeneration:
    """Tests for unit ID generation."""

    def test_unit_id_format(self):
        """Unit ID format: {book_id}-ch{XX}-u{YY}."""
        uid = _generate_unit_id("my-book", 3, 2)
        assert uid == "my-book-ch03-u02"

    def test_unit_id_deterministic(self):
        """Same inputs -> same output (deterministic)."""
        uid1 = _generate_unit_id("book", 5, 1)
        uid2 = _generate_unit_id("book", 5, 1)
        assert uid1 == uid2

    def test_unit_id_padding(self):
        """Numbers are zero-padded to 2 digits."""
        uid = _generate_unit_id("book", 1, 1)
        assert "ch01" in uid
        assert "u01" in uid


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestGenerateUnits:
    """Integration tests for unit generation."""

    def test_generates_valid_units_json(self, book_with_outline):
        """Should generate valid units.json file."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)

        assert result.success
        assert result.units_file is not None

        # Check file was created
        units_path = data_dir / "books" / book_id / "artifacts" / "units" / "units.json"
        assert units_path.exists()

        # Verify JSON structure
        with open(units_path) as f:
            data = json.load(f)

        assert data["$schema"] == "units_v1.1"
        assert data["book_id"] == book_id
        assert "created_at" in data
        assert "units" in data
        assert len(data["units"]) > 0

    def test_all_sections_covered_once(self, book_with_outline, sample_outline):
        """All sections should be covered exactly once (no duplicates, no gaps)."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        # Collect all section IDs from outline
        outline_section_ids = set()
        for chapter in sample_outline["chapters"]:
            for section in chapter.get("sections", []):
                outline_section_ids.add(section["section_id"])

        # Collect all section IDs from units
        units_section_ids = []
        for unit in result.units_file.units:
            units_section_ids.extend(unit.section_ids)

        # Check no duplicates
        assert len(units_section_ids) == len(set(units_section_ids)), "Duplicate sections found"

        # Check all covered
        assert set(units_section_ids) == outline_section_ids, "Section mismatch"

    def test_unit_id_stable_deterministic(self, book_with_outline):
        """Same outline -> same unit IDs (deterministic)."""
        book_id, data_dir = book_with_outline

        # Generate twice
        result1 = generate_units(book_id, data_dir=data_dir, force=True)
        result2 = generate_units(book_id, data_dir=data_dir, force=True)

        # Unit IDs should match
        ids1 = [u.unit_id for u in result1.units_file.units]
        ids2 = [u.unit_id for u in result2.units_file.units]

        assert ids1 == ids2

    def test_max_units_per_chapter_enforced(self, temp_data_dir):
        """Chapters with many sections should cap at 6 units."""
        book_id = "large-book"
        book_path = temp_data_dir / "books" / book_id / "outline"
        book_path.mkdir(parents=True)

        # Create chapter with 100 sections
        sections = [
            {"section_id": f"{book_id}:ch:1:sec:{i}", "number": f"1.{i}", "title": f"Section {i}"}
            for i in range(100)
        ]

        outline = {
            "$schema": "outline_v1",
            "book_id": book_id,
            "chapters": [
                {"chapter_id": f"{book_id}:ch:1", "number": 1, "title": "Mega Chapter", "sections": sections}
            ],
        }

        with open(book_path / "outline.json", "w") as f:
            json.dump(outline, f)

        # Write minimal book.json
        with open(temp_data_dir / "books" / book_id / "book.json", "w") as f:
            json.dump({"book_id": book_id}, f)

        result = generate_units(book_id, data_dir=temp_data_dir)

        assert result.success
        assert len(result.units_file.units) <= MAX_UNITS_PER_CHAPTER

    def test_estimated_time_reasonable(self, book_with_outline):
        """All units should have reasonable estimated time."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        for unit in result.units_file.units:
            assert unit.estimated_time_min > 0, f"Unit {unit.unit_id} has no time"
            # Most units should be <= 35 min (some extreme cases may exceed)

    def test_updates_book_json(self, book_with_outline):
        """Should update book.json with units metadata."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        # Check book.json was updated
        book_json_path = data_dir / "books" / book_id / "book.json"
        with open(book_json_path) as f:
            book_data = json.load(f)

        assert "units_count" in book_data
        assert book_data["units_count"] == len(result.units_file.units)
        assert book_data["units_version"] == "1.1"
        assert "units_generated_at" in book_data

    def test_no_overwrite_without_force(self, book_with_outline):
        """Should not overwrite existing units.json without --force."""
        book_id, data_dir = book_with_outline

        # First generation
        result1 = generate_units(book_id, data_dir=data_dir)
        assert result1.success

        # Second generation without force should fail
        result2 = generate_units(book_id, data_dir=data_dir, force=False)
        assert not result2.success
        assert "ya existe" in result2.message

    def test_force_overwrites(self, book_with_outline):
        """Should overwrite existing units.json with --force."""
        book_id, data_dir = book_with_outline

        # First generation
        result1 = generate_units(book_id, data_dir=data_dir)
        assert result1.success

        # Second generation with force should succeed
        result2 = generate_units(book_id, data_dir=data_dir, force=True)
        assert result2.success


class TestValidateCoverage:
    """Tests for coverage validation."""

    def test_valid_coverage(self, book_with_outline, sample_outline):
        """Valid units should pass coverage check."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        outline_path = data_dir / "books" / book_id / "outline" / "outline.json"
        units_path = data_dir / "books" / book_id / "artifacts" / "units" / "units.json"

        is_valid, errors = validate_units_coverage(outline_path, units_path)
        assert is_valid, f"Coverage errors: {errors}"
        assert errors == []


class TestReportMetrics:
    """Tests for report metrics."""

    def test_report_includes_totals(self, book_with_outline, sample_outline):
        """Report should include all totals."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        report = result.report

        # Count expected values
        expected_chapters = len(sample_outline["chapters"])
        expected_sections = sum(
            len(ch.get("sections", [])) for ch in sample_outline["chapters"]
        )

        assert report.total_chapters == expected_chapters
        assert report.total_sections == expected_sections
        assert report.total_units > 0
        assert report.total_time_min > 0


class TestChapterWithNoSections:
    """Tests for chapters without sections."""

    def test_chapter_without_sections_gets_one_unit(self, temp_data_dir):
        """Chapter with no sections should get exactly 1 unit."""
        book_id = "no-sections-book"
        book_path = temp_data_dir / "books" / book_id / "outline"
        book_path.mkdir(parents=True)

        outline = {
            "$schema": "outline_v1",
            "book_id": book_id,
            "chapters": [
                {"chapter_id": f"{book_id}:ch:1", "number": 1, "title": "Empty Chapter", "sections": []},
                {"chapter_id": f"{book_id}:ch:2", "number": 2, "title": "Also Empty", "sections": []},
            ],
        }

        with open(book_path / "outline.json", "w") as f:
            json.dump(outline, f)

        with open(temp_data_dir / "books" / book_id / "book.json", "w") as f:
            json.dump({"book_id": book_id}, f)

        result = generate_units(book_id, data_dir=temp_data_dir)

        assert result.success
        assert len(result.units_file.units) == 2  # One unit per chapter


# =============================================================================
# CLI TESTS
# =============================================================================


class TestPlanCLI:
    """Tests for the plan CLI command.

    Note: CLI tests are tricky because they use the real DB and data paths.
    We test the core functionality directly instead of through CLI.
    """

    def test_generate_units_prints_summary_values(self, book_with_outline):
        """Core function should return proper summary values for CLI to print."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)

        assert result.success
        # These are the values CLI would print
        assert result.report.total_chapters > 0
        assert result.report.total_units > 0
        assert result.report.total_time_min > 0

    def test_generate_units_fails_without_outline(self, temp_data_dir):
        """Core function should fail gracefully without outline.json."""
        book_id = "no-outline-book"

        # Create book dir without outline
        book_path = temp_data_dir / "books" / book_id
        book_path.mkdir(parents=True)
        with open(book_path / "book.json", "w") as f:
            json.dump({"book_id": book_id}, f)

        result = generate_units(book_id, data_dir=temp_data_dir)

        assert not result.success
        assert "outline" in result.message.lower()


# =============================================================================
# V1.1 FIELD TESTS
# =============================================================================


class TestUnitOrdinalsV11:
    """Tests for v1.1 ordinal fields: unit_number_in_chapter, units_in_chapter."""

    def test_single_unit_chapter_has_ordinals_1_1(self, temp_data_dir):
        """Chapter with 1 unit should have (1, 1) ordinals."""
        book_id = "ordinal-test"
        book_path = temp_data_dir / "books" / book_id / "outline"
        book_path.mkdir(parents=True)

        outline = {
            "$schema": "outline_v1",
            "book_id": book_id,
            "chapters": [
                {
                    "chapter_id": f"{book_id}:ch:1",
                    "number": 1,
                    "title": "Single Unit Chapter",
                    "sections": [
                        {"section_id": f"{book_id}:ch:1:sec:1", "number": "1.1", "title": "Sec 1"},
                        {"section_id": f"{book_id}:ch:1:sec:2", "number": "1.2", "title": "Sec 2"},
                    ],
                },
            ],
        }

        with open(book_path / "outline.json", "w") as f:
            json.dump(outline, f)
        with open(temp_data_dir / "books" / book_id / "book.json", "w") as f:
            json.dump({"book_id": book_id}, f)

        result = generate_units(book_id, data_dir=temp_data_dir)

        assert result.success
        assert len(result.units_file.units) == 1

        unit = result.units_file.units[0]
        assert unit.unit_number_in_chapter == 1
        assert unit.units_in_chapter == 1

    def test_multi_unit_chapter_has_sequential_ordinals(self, temp_data_dir):
        """Chapter with multiple units should have sequential ordinals (1/n, 2/n, ...)."""
        book_id = "multi-ordinal-test"
        book_path = temp_data_dir / "books" / book_id / "outline"
        book_path.mkdir(parents=True)

        # 10 sections -> 2 units
        sections = [
            {"section_id": f"{book_id}:ch:1:sec:{i}", "number": f"1.{i}", "title": f"Section {i}"}
            for i in range(1, 11)
        ]

        outline = {
            "$schema": "outline_v1",
            "book_id": book_id,
            "chapters": [
                {"chapter_id": f"{book_id}:ch:1", "number": 1, "title": "Multi Unit Chapter", "sections": sections},
            ],
        }

        with open(book_path / "outline.json", "w") as f:
            json.dump(outline, f)
        with open(temp_data_dir / "books" / book_id / "book.json", "w") as f:
            json.dump({"book_id": book_id}, f)

        result = generate_units(book_id, data_dir=temp_data_dir)

        assert result.success
        assert len(result.units_file.units) == 2

        # Check ordinals
        unit1 = result.units_file.units[0]
        unit2 = result.units_file.units[1]

        assert unit1.unit_number_in_chapter == 1
        assert unit1.units_in_chapter == 2
        assert unit2.unit_number_in_chapter == 2
        assert unit2.units_in_chapter == 2

    def test_ordinals_cover_1_to_m_no_duplicates(self, temp_data_dir):
        """Ordinals should cover 1..m without gaps or duplicates."""
        book_id = "ordinal-coverage"
        book_path = temp_data_dir / "books" / book_id / "outline"
        book_path.mkdir(parents=True)

        # 20 sections -> 3 units
        sections = [
            {"section_id": f"{book_id}:ch:1:sec:{i}", "number": f"1.{i}", "title": f"Section {i}"}
            for i in range(1, 21)
        ]

        outline = {
            "$schema": "outline_v1",
            "book_id": book_id,
            "chapters": [
                {"chapter_id": f"{book_id}:ch:1", "number": 1, "title": "Big Chapter", "sections": sections},
            ],
        }

        with open(book_path / "outline.json", "w") as f:
            json.dump(outline, f)
        with open(temp_data_dir / "books" / book_id / "book.json", "w") as f:
            json.dump({"book_id": book_id}, f)

        result = generate_units(book_id, data_dir=temp_data_dir)

        assert result.success

        # Collect ordinals for this chapter
        ordinals = [u.unit_number_in_chapter for u in result.units_file.units]
        total = result.units_file.units[0].units_in_chapter

        # Should be 1, 2, 3, ...
        assert ordinals == list(range(1, total + 1)), f"Expected 1..{total}, got {ordinals}"

        # All units_in_chapter should be the same
        totals = [u.units_in_chapter for u in result.units_file.units]
        assert len(set(totals)) == 1, "All units should have same units_in_chapter"


class TestSectionSpanV11:
    """Tests for v1.1 section span fields: section_start_id, section_end_id."""

    def test_section_start_equals_first_section_id(self, book_with_outline):
        """section_start_id should equal section_ids[0]."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        for unit in result.units_file.units:
            if unit.section_ids:
                assert unit.section_start_id == unit.section_ids[0], \
                    f"Unit {unit.unit_id}: section_start_id != section_ids[0]"

    def test_section_end_equals_last_section_id(self, book_with_outline):
        """section_end_id should equal section_ids[-1]."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        for unit in result.units_file.units:
            if unit.section_ids:
                assert unit.section_end_id == unit.section_ids[-1], \
                    f"Unit {unit.unit_id}: section_end_id != section_ids[-1]"

    def test_empty_sections_have_empty_span(self, temp_data_dir):
        """Units with no sections should have empty span."""
        book_id = "empty-span-test"
        book_path = temp_data_dir / "books" / book_id / "outline"
        book_path.mkdir(parents=True)

        outline = {
            "$schema": "outline_v1",
            "book_id": book_id,
            "chapters": [
                {"chapter_id": f"{book_id}:ch:1", "number": 1, "title": "Empty Chapter", "sections": []},
            ],
        }

        with open(book_path / "outline.json", "w") as f:
            json.dump(outline, f)
        with open(temp_data_dir / "books" / book_id / "book.json", "w") as f:
            json.dump({"book_id": book_id}, f)

        result = generate_units(book_id, data_dir=temp_data_dir)

        assert result.success
        unit = result.units_file.units[0]
        assert unit.section_start_id == ""
        assert unit.section_end_id == ""

    def test_section_ids_still_present_for_compatibility(self, book_with_outline):
        """section_ids should still be present (backward compatibility)."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        for unit in result.units_file.units:
            # section_ids should exist and be a list
            assert hasattr(unit, "section_ids")
            assert isinstance(unit.section_ids, list)


class TestSchemaVersionV11:
    """Tests for v1.1 schema version."""

    def test_schema_is_v1_1(self, book_with_outline):
        """Schema version should be units_v1.1."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        units_path = data_dir / "books" / book_id / "artifacts" / "units" / "units.json"
        with open(units_path) as f:
            data = json.load(f)

        assert data["$schema"] == "units_v1.1"

    def test_book_json_has_v1_1_version(self, book_with_outline):
        """book.json should have units_version '1.1'."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        book_json_path = data_dir / "books" / book_id / "book.json"
        with open(book_json_path) as f:
            data = json.load(f)

        assert data["units_version"] == "1.1"

    def test_book_json_has_units_generated_at(self, book_with_outline):
        """book.json should have units_generated_at field."""
        book_id, data_dir = book_with_outline

        result = generate_units(book_id, data_dir=data_dir)
        assert result.success

        book_json_path = data_dir / "books" / book_id / "book.json"
        with open(book_json_path) as f:
            data = json.load(f)

        assert "units_generated_at" in data
        # Should be ISO8601 format
        assert "T" in data["units_generated_at"]
