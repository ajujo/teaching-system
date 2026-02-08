"""Learning unit generation module.

Responsibilities (F3):
- Generate units.json from outline.json (NO LLM)
- Partition chapters into digestible learning units
- Apply heuristic rules for time and difficulty estimation
- Update book.json with units metadata

Partitioning rules:
- 0-6 sections -> 1 unit
- 7-14 sections -> 2 units
- 15-24 sections -> 3 units
- 25-36 sections -> 4 units
- 37-50 sections -> 5 units
- >50 sections -> 6 units (max per chapter)

Time estimation:
- base = 3 min per section + 5 min overhead
- cap per unit: 35 min (subdivide if exceeded)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Partitioning thresholds: (max_sections, num_units)
PARTITION_THRESHOLDS = [
    (6, 1),
    (14, 2),
    (24, 3),
    (36, 4),
    (50, 5),
]
MAX_UNITS_PER_CHAPTER = 6

# Time estimation
MINUTES_PER_SECTION = 3
OVERHEAD_MINUTES = 5
MAX_MINUTES_PER_UNIT = 35

# Difficulty keywords
INTRO_KEYWORDS = {
    "introduction", "overview", "basics", "fundamentals", "getting started",
    "introducción", "introduccion", "visión general", "vision general",
    "fundamentos", "conceptos básicos", "conceptos basicos",
}
ADVANCED_KEYWORDS = {
    "advanced", "optimization", "scaling", "evaluation", "deployment",
    "performance", "production", "best practices", "architecture",
    "avanzado", "optimización", "optimizacion", "escalabilidad",
    "evaluación", "evaluacion", "despliegue", "producción", "produccion",
    "rendimiento", "arquitectura",
}

Difficulty = Literal["intro", "mid", "adv"]


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class Unit:
    """A learning unit covering part of a chapter."""

    unit_id: str
    chapter_id: str
    chapter_number: int
    title: str
    section_ids: list[str]
    estimated_time_min: int
    difficulty: Difficulty
    # v1.1 fields: ordinals
    unit_number_in_chapter: int = 1
    units_in_chapter: int = 1
    # v1.1 fields: section span
    section_start_id: str = ""
    section_end_id: str = ""
    learning_objectives: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "unit_id": self.unit_id,
            "chapter_id": self.chapter_id,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "section_ids": self.section_ids,
            "section_start_id": self.section_start_id,
            "section_end_id": self.section_end_id,
            "unit_number_in_chapter": self.unit_number_in_chapter,
            "units_in_chapter": self.units_in_chapter,
            "estimated_time_min": self.estimated_time_min,
            "difficulty": self.difficulty,
            "learning_objectives": self.learning_objectives,
        }


@dataclass
class UnitsFile:
    """Complete units file for a book."""

    book_id: str
    units: list[Unit]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": "units_v1.1",
            "book_id": self.book_id,
            "created_at": self.created_at,
            "units": [u.to_dict() for u in self.units],
        }


@dataclass
class PlanReport:
    """Report from unit planning."""

    total_chapters: int
    total_units: int
    total_sections: int
    total_time_min: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class PlanResult:
    """Result of unit planning."""

    success: bool
    units_file: UnitsFile | None
    report: PlanReport
    message: str


class UnitPlanningError(Exception):
    """Error during unit planning."""
    pass


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_num_units_for_sections(num_sections: int) -> int:
    """Determine number of units based on section count."""
    if num_sections == 0:
        return 1  # Chapter with no sections = 1 unit

    for threshold, units in PARTITION_THRESHOLDS:
        if num_sections <= threshold:
            return units

    return MAX_UNITS_PER_CHAPTER


def _estimate_time(num_sections: int) -> int:
    """Estimate time in minutes for a set of sections."""
    if num_sections == 0:
        return OVERHEAD_MINUTES + MINUTES_PER_SECTION  # Minimum for empty chapter
    return num_sections * MINUTES_PER_SECTION + OVERHEAD_MINUTES


def _detect_difficulty(title: str) -> Difficulty:
    """Detect difficulty from title using keyword matching."""
    title_lower = title.lower()

    # Check intro keywords
    for keyword in INTRO_KEYWORDS:
        if keyword in title_lower:
            return "intro"

    # Check advanced keywords
    for keyword in ADVANCED_KEYWORDS:
        if keyword in title_lower:
            return "adv"

    return "mid"


def _partition_sections(
    section_ids: list[str],
    num_units: int,
) -> list[list[str]]:
    """Partition sections into num_units continuous groups.

    Distributes sections as evenly as possible.
    """
    if not section_ids:
        return [[]]  # One empty unit for chapter with no sections

    if num_units <= 1:
        return [section_ids]

    # Distribute sections evenly
    n = len(section_ids)
    base_size = n // num_units
    remainder = n % num_units

    partitions = []
    start = 0

    for i in range(num_units):
        # Add one extra section to first 'remainder' partitions
        size = base_size + (1 if i < remainder else 0)
        if size > 0:
            partitions.append(section_ids[start:start + size])
            start += size
        else:
            # Empty partition - shouldn't happen with proper thresholds
            partitions.append([])

    return partitions


def _maybe_subdivide_for_time(
    section_ids: list[str],
    num_units: int,
    chapter_number: int,
) -> tuple[list[list[str]], list[str]]:
    """Subdivide partitions if any exceeds time cap.

    Returns (partitions, warnings).
    """
    warnings = []
    partitions = _partition_sections(section_ids, num_units)

    # Check if any partition exceeds time cap
    needs_more_units = False
    for partition in partitions:
        time = _estimate_time(len(partition))
        if time > MAX_MINUTES_PER_UNIT and num_units < MAX_UNITS_PER_CHAPTER:
            needs_more_units = True
            break

    if needs_more_units and num_units < MAX_UNITS_PER_CHAPTER:
        # Try with one more unit
        new_num_units = min(num_units + 1, MAX_UNITS_PER_CHAPTER)
        partitions, sub_warnings = _maybe_subdivide_for_time(
            section_ids, new_num_units, chapter_number
        )
        warnings.extend(sub_warnings)

    # Final check - if still exceeding, add warning
    for partition in partitions:
        time = _estimate_time(len(partition))
        if time > MAX_MINUTES_PER_UNIT:
            warnings.append(
                f"Chapter {chapter_number}: unit exceeds {MAX_MINUTES_PER_UNIT} min "
                f"({time} min with {len(partition)} sections)"
            )

    return partitions, warnings


def _format_unit_title(
    chapter_number: int,
    chapter_title: str,
    part_num: int,
    total_parts: int,
) -> str:
    """Format unit title.

    Format: "Ch{n} — {chapter_title} (Parte k/m)" if m>1
    If m==1: "Ch{n} — {chapter_title}"
    """
    # Clean chapter title
    clean_title = chapter_title.strip()

    if total_parts > 1:
        return f"Ch{chapter_number} — {clean_title} (Parte {part_num}/{total_parts})"
    return f"Ch{chapter_number} — {clean_title}"


def _generate_unit_id(book_id: str, chapter_number: int, unit_num: int) -> str:
    """Generate deterministic unit ID.

    Format: {book_id}-ch{XX}-u{YY}
    """
    return f"{book_id}-ch{chapter_number:02d}-u{unit_num:02d}"


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================


def generate_units(
    book_id: str,
    data_dir: Path | None = None,
    force: bool = False,
) -> PlanResult:
    """Generate units.json from outline.json.

    Args:
        book_id: Book identifier
        data_dir: Base data directory (default: ./data)
        force: Overwrite existing units.json

    Returns:
        PlanResult with units file and report
    """
    if data_dir is None:
        data_dir = Path("data")

    book_path = data_dir / "books" / book_id
    outline_path = book_path / "outline" / "outline.json"
    units_dir = book_path / "artifacts" / "units"
    units_path = units_dir / "units.json"
    book_json_path = book_path / "book.json"

    # Validate outline exists
    if not outline_path.exists():
        return PlanResult(
            success=False,
            units_file=None,
            report=PlanReport(0, 0, 0, 0, ["outline.json no encontrado"]),
            message=f"No se encontró outline.json en {outline_path}",
        )

    # Check if units already exist
    if units_path.exists() and not force:
        return PlanResult(
            success=False,
            units_file=None,
            report=PlanReport(0, 0, 0, 0, ["units.json ya existe"]),
            message=f"units.json ya existe. Usa --force para sobrescribir.",
        )

    # Load outline
    try:
        with open(outline_path) as f:
            outline_data = json.load(f)
    except json.JSONDecodeError as e:
        return PlanResult(
            success=False,
            units_file=None,
            report=PlanReport(0, 0, 0, 0, [f"Error parsing outline: {e}"]),
            message=f"Error al leer outline.json: {e}",
        )

    # Generate units
    units: list[Unit] = []
    warnings: list[str] = []
    total_sections = 0
    total_time = 0

    chapters = outline_data.get("chapters", [])

    for chapter in chapters:
        chapter_id = chapter.get("chapter_id", "")
        chapter_number = chapter.get("number", 0)
        chapter_title = chapter.get("title", "")
        sections = chapter.get("sections", [])

        # Extract section IDs
        section_ids = [s.get("section_id", "") for s in sections if s.get("section_id")]
        num_sections = len(section_ids)
        total_sections += num_sections

        # Determine number of units
        num_units = _get_num_units_for_sections(num_sections)

        # Partition sections (may subdivide if time exceeds cap)
        partitions, time_warnings = _maybe_subdivide_for_time(
            section_ids, num_units, chapter_number
        )
        warnings.extend(time_warnings)

        # Detect difficulty from chapter title
        difficulty = _detect_difficulty(chapter_title)

        # Create units for this chapter
        total_units_in_chapter = len(partitions)

        for unit_idx, partition_section_ids in enumerate(partitions):
            unit_num = unit_idx + 1

            unit_id = _generate_unit_id(book_id, chapter_number, unit_num)
            title = _format_unit_title(
                chapter_number, chapter_title, unit_num, total_units_in_chapter
            )
            time_min = _estimate_time(len(partition_section_ids))
            total_time += time_min

            # v1.1: section span (first and last section_id)
            section_start = partition_section_ids[0] if partition_section_ids else ""
            section_end = partition_section_ids[-1] if partition_section_ids else ""

            unit = Unit(
                unit_id=unit_id,
                chapter_id=chapter_id,
                chapter_number=chapter_number,
                title=title,
                section_ids=partition_section_ids,
                estimated_time_min=time_min,
                difficulty=difficulty,
                unit_number_in_chapter=unit_num,
                units_in_chapter=total_units_in_chapter,
                section_start_id=section_start,
                section_end_id=section_end,
                learning_objectives=[],
            )
            units.append(unit)

    # Create units file
    units_file = UnitsFile(
        book_id=book_id,
        units=units,
    )

    # Create output directory
    units_dir.mkdir(parents=True, exist_ok=True)

    # Write units.json
    with open(units_path, "w") as f:
        json.dump(units_file.to_dict(), f, indent=2, ensure_ascii=False)

    # Update book.json
    if book_json_path.exists():
        try:
            with open(book_json_path) as f:
                book_data = json.load(f)

            book_data["units_count"] = len(units)
            book_data["units_version"] = "1.1"
            book_data["units_generated_at"] = datetime.now(timezone.utc).isoformat()

            with open(book_json_path, "w") as f:
                json.dump(book_data, f, indent=2, ensure_ascii=False)

        except (json.JSONDecodeError, OSError) as e:
            warnings.append(f"No se pudo actualizar book.json: {e}")

    # Create report
    report = PlanReport(
        total_chapters=len(chapters),
        total_units=len(units),
        total_sections=total_sections,
        total_time_min=total_time,
        warnings=warnings,
    )

    logger.info(
        "units_generated",
        book_id=book_id,
        chapters=report.total_chapters,
        units=report.total_units,
        sections=report.total_sections,
        time_min=report.total_time_min,
    )

    return PlanResult(
        success=True,
        units_file=units_file,
        report=report,
        message=f"Generados {len(units)} unidades para {len(chapters)} capítulos",
    )


def validate_units_coverage(
    outline_path: Path,
    units_path: Path,
) -> tuple[bool, list[str]]:
    """Validate that all sections are covered exactly once.

    Returns (is_valid, errors).
    """
    errors = []

    # Load outline
    with open(outline_path) as f:
        outline_data = json.load(f)

    # Load units
    with open(units_path) as f:
        units_data = json.load(f)

    # Collect all section IDs from outline
    outline_section_ids = set()
    for chapter in outline_data.get("chapters", []):
        for section in chapter.get("sections", []):
            section_id = section.get("section_id")
            if section_id:
                outline_section_ids.add(section_id)

    # Collect all section IDs from units
    units_section_ids = []
    for unit in units_data.get("units", []):
        units_section_ids.extend(unit.get("section_ids", []))

    # Check for duplicates
    seen = set()
    duplicates = set()
    for sid in units_section_ids:
        if sid in seen:
            duplicates.add(sid)
        seen.add(sid)

    if duplicates:
        errors.append(f"Secciones duplicadas: {duplicates}")

    # Check for missing sections
    units_section_set = set(units_section_ids)
    missing = outline_section_ids - units_section_set
    if missing:
        errors.append(f"Secciones no cubiertas: {missing}")

    # Check for extra sections
    extra = units_section_set - outline_section_ids
    if extra:
        errors.append(f"Secciones extra (no en outline): {extra}")

    return len(errors) == 0, errors
