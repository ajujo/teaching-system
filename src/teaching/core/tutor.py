"""Tutor mode core module (F7).

Responsibilities:
- Manage tutor session state (persistence)
- Orchestrate chapter-by-chapter learning flow
- Provide Q&A functionality over chapter notes
- Handle exam generation with retry logic for invalid exams

State persistence:
- data/state/tutor_state_v1.json
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any

import structlog

from teaching.llm.client import LLMClient, LLMConfig
from teaching.utils.text_utils import strip_think
from teaching.utils.validators import get_available_book_ids

logger = structlog.get_logger(__name__)


# =============================================================================
# TUTOR PROMPT KIND ENUM (F7.4)
# =============================================================================


class TutorPromptKind(Enum):
    """Tipo de pregunta que hizo el tutor.

    Permite interpretar correctamente respuestas afirmativas (sí, vale, ok)
    según el contexto de la pregunta anterior.
    """

    ASK_DEEPEN = auto()  # "¿Quieres profundizar?"
    ASK_ADVANCE_CONFIRM = auto()  # "¿Avanzamos al siguiente punto?"
    ASK_COMPREHENSION = auto()  # Pregunta de verificación de comprensión
    ASK_MCQ = auto()  # Pregunta con opciones a/b/c
    ASK_POST_EXAMPLES = auto()  # Después de ejemplos: "(1) más, (2) comprobar, (3) avanzar"
    ASK_POST_FAILURE_CHOICE = auto()  # F8.2: "Avanzar [A] o Repasar [R]?"
    ASK_UNIT_START = auto()  # F8.3: "¿Empezamos?" al inicio de unidad
    NORMAL_QA = auto()  # Otros casos / sin pregunta específica


# =============================================================================
# TUTOR EVENT (F8.3) - Para futura webapp
# =============================================================================


class TutorEventType(Enum):
    """Tipos de eventos del tutor para renderizado."""

    UNIT_OPENING = auto()  # Apertura de unidad (contexto + objetivo + mapa)
    POINT_OPENING = auto()  # Título de punto nuevo
    POINT_EXPLANATION = auto()  # Explicación del punto
    ASK_CHECK = auto()  # Pregunta de verificación
    FEEDBACK = auto()  # Feedback a respuesta del estudiante
    ASK_CONFIRM_ADVANCE = auto()  # "¿Avanzamos?"
    UNIT_NOTES = auto()  # Apuntes completos de la unidad
    ASK_UNIT_NEXT = auto()  # "¿Control o siguiente unidad?"


@dataclass
class TutorEvent:
    """Evento emitido por el tutor (F8.3).

    Encapsula la información para renderizar en CLI o webapp.
    """

    event_type: TutorEventType
    title: str = ""  # Título opcional (ej: "Punto 1: Tokenización")
    markdown: str = ""  # Contenido principal en Markdown
    data: dict = field(default_factory=dict)  # Datos adicionales (ej: point_number, unit_id)

# =============================================================================
# CONSTANTS
# =============================================================================

STATE_SCHEMA = "tutor_state_v1"
STATE_FILENAME = "tutor_state_v1.json"

# Multi-student support (F7.3 Academia)
STUDENTS_SCHEMA = "students_v1"
STUDENTS_FILENAME = "students_v1.json"

# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class BookProgress:
    """Progress tracking for a single book."""

    book_id: str
    last_chapter_number: int = 0
    completed_chapters: list[int] = field(default_factory=list)
    last_session_at: str = ""
    chapter_attempts: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "last_chapter_number": self.last_chapter_number,
            "completed_chapters": self.completed_chapters,
            "last_session_at": self.last_session_at,
            "chapter_attempts": self.chapter_attempts,
        }


@dataclass
class TutorState:
    """Persistent tutor state across sessions."""

    active_book_id: str | None = None
    progress: dict[str, BookProgress] = field(default_factory=dict)
    library_scan_paths: list[str] = field(default_factory=list)
    user_name: str | None = None  # User's name for personalization

    def get_book_progress(self, book_id: str) -> BookProgress:
        """Get or create progress for a book."""
        if book_id not in self.progress:
            self.progress[book_id] = BookProgress(book_id=book_id)
        return self.progress[book_id]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": STATE_SCHEMA,
            "active_book_id": self.active_book_id,
            "progress": {
                book_id: prog.to_dict() for book_id, prog in self.progress.items()
            },
            "library_scan_paths": self.library_scan_paths,
            "user_name": self.user_name,
        }


# =============================================================================
# MULTI-STUDENT SUPPORT (F7.3 Academia)
# =============================================================================


# Email validation pattern
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_email(email: str) -> bool:
    """Validate email format. Empty string is valid (optional field).

    Args:
        email: Email address to validate

    Returns:
        True if valid email or empty string, False otherwise
    """
    if not email:
        return True
    return bool(EMAIL_PATTERN.match(email))


@dataclass
class StudentProfile:
    """Profile for a single student with their tutor state."""

    student_id: str  # e.g., "stu01", "stu02"
    name: str
    surname: str = ""  # F8: apellido
    email: str = ""  # F8: email (opcional)
    tutor_persona_id: str = "dra_vega"  # F8: persona del tutor
    needs_profile_completion: bool = False  # F8: migración pendiente
    created_at: str = ""
    updated_at: str = ""
    tutor_state: TutorState = field(default_factory=TutorState)

    def __post_init__(self):
        """Set timestamps if not provided."""
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @property
    def full_name(self) -> str:
        """Get full name (name + surname)."""
        if self.surname:
            return f"{self.name} {self.surname}"
        return self.name

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "student_id": self.student_id,
            "name": self.name,
            "surname": self.surname,
            "email": self.email,
            "tutor_persona_id": self.tutor_persona_id,
            "needs_profile_completion": self.needs_profile_completion,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tutor_state": self.tutor_state.to_dict(),
        }


@dataclass
class StudentsState:
    """Multi-student state container."""

    active_student_id: str | None = None
    students: list[StudentProfile] = field(default_factory=list)

    def get_active_student(self) -> StudentProfile | None:
        """Get the currently active student."""
        if not self.active_student_id:
            return None
        for student in self.students:
            if student.student_id == self.active_student_id:
                return student
        return None

    def get_student_by_id(self, student_id: str) -> StudentProfile | None:
        """Get student by ID."""
        for student in self.students:
            if student.student_id == student_id:
                return student
        return None

    def get_student_by_name(self, name: str) -> StudentProfile | None:
        """Get student by name (case-insensitive)."""
        name_lower = name.lower()
        for student in self.students:
            if student.name.lower() == name_lower:
                return student
        return None

    def generate_next_student_id(self) -> str:
        """Generate next available student ID."""
        existing_nums = []
        for student in self.students:
            if student.student_id.startswith("stu"):
                try:
                    num = int(student.student_id[3:])
                    existing_nums.append(num)
                except ValueError:
                    pass
        next_num = max(existing_nums, default=0) + 1
        return f"stu{next_num:02d}"

    def add_student(
        self,
        name: str,
        surname: str = "",
        email: str = "",
        tutor_persona_id: str = "dra_vega",
    ) -> StudentProfile:
        """Add a new student and return their profile.

        Args:
            name: Student's first name
            surname: Student's last name (optional)
            email: Student's email (optional)
            tutor_persona_id: ID of tutor persona to use (default: dra_vega)

        Returns:
            The newly created StudentProfile
        """
        student_id = self.generate_next_student_id()
        student = StudentProfile(
            student_id=student_id,
            name=name,
            surname=surname,
            email=email,
            tutor_persona_id=tutor_persona_id,
            needs_profile_completion=False,  # New student has all fields
        )
        # Set the user_name in the tutor_state as well
        student.tutor_state.user_name = name
        self.students.append(student)
        return student

    def remove_student(self, student_id: str) -> bool:
        """Remove a student by ID. Returns True if removed."""
        for i, student in enumerate(self.students):
            if student.student_id == student_id:
                self.students.pop(i)
                # If we removed the active student, clear active_student_id
                if self.active_student_id == student_id:
                    self.active_student_id = None
                    # Auto-select another student if available
                    if self.students:
                        self.active_student_id = self.students[0].student_id
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "$schema": STUDENTS_SCHEMA,
            "active_student_id": self.active_student_id,
            "students": [s.to_dict() for s in self.students],
        }


# =============================================================================
# STATE PERSISTENCE
# =============================================================================


def load_tutor_state(data_dir: Path | None = None) -> TutorState:
    """Load tutor state from disk, or return fresh state.

    Args:
        data_dir: Base data directory. Defaults to ./data

    Returns:
        TutorState object (fresh if file missing or corrupted)
    """
    if data_dir is None:
        data_dir = Path("data")

    state_path = data_dir / "state" / STATE_FILENAME

    if not state_path.exists():
        logger.debug("tutor_state_not_found", path=str(state_path))
        return TutorState()

    try:
        with open(state_path, encoding="utf-8") as f:
            data = json.load(f)

        # Validate schema
        if data.get("$schema") != STATE_SCHEMA:
            logger.warning(
                "tutor_state_invalid_schema",
                expected=STATE_SCHEMA,
                got=data.get("$schema"),
            )
            return TutorState()

        # Reconstruct state
        progress: dict[str, BookProgress] = {}
        for book_id, prog_data in data.get("progress", {}).items():
            progress[book_id] = BookProgress(
                book_id=book_id,
                last_chapter_number=prog_data.get("last_chapter_number", 0),
                completed_chapters=prog_data.get("completed_chapters", []),
                last_session_at=prog_data.get("last_session_at", ""),
                chapter_attempts=prog_data.get("chapter_attempts", {}),
            )

        return TutorState(
            active_book_id=data.get("active_book_id"),
            progress=progress,
            library_scan_paths=data.get("library_scan_paths", []),
            user_name=data.get("user_name"),
        )

    except (json.JSONDecodeError, OSError, KeyError) as e:
        logger.error("tutor_state_load_failed", error=str(e))
        return TutorState()


def save_tutor_state(state: TutorState, data_dir: Path | None = None) -> Path:
    """Persist tutor state to disk.

    Args:
        state: TutorState to save
        data_dir: Base data directory. Defaults to ./data

    Returns:
        Path to saved state file
    """
    if data_dir is None:
        data_dir = Path("data")

    state_dir = data_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / STATE_FILENAME

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info("tutor_state_saved", path=str(state_path))
    return state_path


# =============================================================================
# MULTI-STUDENT PERSISTENCE (F7.3 Academia)
# =============================================================================


def load_students_state(data_dir: Path | None = None) -> StudentsState:
    """Load multi-student state from disk.

    If students_v1.json doesn't exist but tutor_state_v1.json does,
    migrates the old state to a new students state with one default student.

    Args:
        data_dir: Base data directory. Defaults to ./data

    Returns:
        StudentsState object
    """
    if data_dir is None:
        data_dir = Path("data")

    students_path = data_dir / "state" / STUDENTS_FILENAME
    old_state_path = data_dir / "state" / STATE_FILENAME

    # Try to load existing students state
    if students_path.exists():
        try:
            with open(students_path, encoding="utf-8") as f:
                data = json.load(f)

            if data.get("$schema") != STUDENTS_SCHEMA:
                logger.warning(
                    "students_state_invalid_schema",
                    expected=STUDENTS_SCHEMA,
                    got=data.get("$schema"),
                )
                return _create_default_students_state()

            # Reconstruct students
            students: list[StudentProfile] = []
            for s_data in data.get("students", []):
                # Reconstruct tutor_state
                ts_data = s_data.get("tutor_state", {})
                progress: dict[str, BookProgress] = {}
                for book_id, prog_data in ts_data.get("progress", {}).items():
                    progress[book_id] = BookProgress(
                        book_id=book_id,
                        last_chapter_number=prog_data.get("last_chapter_number", 0),
                        completed_chapters=prog_data.get("completed_chapters", []),
                        last_session_at=prog_data.get("last_session_at", ""),
                        chapter_attempts=prog_data.get("chapter_attempts", {}),
                    )

                tutor_state = TutorState(
                    active_book_id=ts_data.get("active_book_id"),
                    progress=progress,
                    library_scan_paths=ts_data.get("library_scan_paths", []),
                    user_name=ts_data.get("user_name"),
                )

                # F8: Migration - check if new fields exist
                needs_migration = "surname" not in s_data
                students.append(
                    StudentProfile(
                        student_id=s_data.get("student_id", "stu01"),
                        name=s_data.get("name", "Estudiante"),
                        surname=s_data.get("surname", ""),
                        email=s_data.get("email", ""),
                        tutor_persona_id=s_data.get("tutor_persona_id", "dra_vega"),
                        needs_profile_completion=s_data.get(
                            "needs_profile_completion", needs_migration
                        ),
                        created_at=s_data.get("created_at", ""),
                        updated_at=s_data.get("updated_at", ""),
                        tutor_state=tutor_state,
                    )
                )

            return StudentsState(
                active_student_id=data.get("active_student_id"),
                students=students,
            )

        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.error("students_state_load_failed", error=str(e))
            return _create_default_students_state()

    # Migration: if old tutor_state exists, migrate it
    if old_state_path.exists():
        logger.info("migrating_tutor_state_to_students")
        old_state = load_tutor_state(data_dir)

        # Create a student from the old state
        name = old_state.user_name or "Estudiante"
        student = StudentProfile(
            student_id="stu01",
            name=name,
            surname="",  # F8: new field
            email="",  # F8: new field
            tutor_persona_id="dra_vega",  # F8: default persona
            needs_profile_completion=True,  # F8: mark for completion
            tutor_state=old_state,
        )
        student.tutor_state.user_name = name

        state = StudentsState(
            active_student_id="stu01",
            students=[student],
        )

        # Save the migrated state
        save_students_state(state, data_dir)
        logger.info("migration_complete", student_name=name)
        return state

    # No existing state - return default
    return _create_default_students_state()


def _create_default_students_state() -> StudentsState:
    """Create a fresh students state with no students."""
    return StudentsState()


def save_students_state(state: StudentsState, data_dir: Path | None = None) -> Path:
    """Persist multi-student state to disk.

    Args:
        state: StudentsState to save
        data_dir: Base data directory. Defaults to ./data

    Returns:
        Path to saved state file
    """
    if data_dir is None:
        data_dir = Path("data")

    state_dir = data_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / STUDENTS_FILENAME

    # Update timestamps on active student
    active = state.get_active_student()
    if active:
        active.updated_at = datetime.now(timezone.utc).isoformat()

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info("students_state_saved", path=str(state_path))
    return state_path


def save_student_progress(
    students_state: StudentsState,
    student: StudentProfile,
    data_dir: Path | None = None,
) -> Path:
    """Save progress for a specific student.

    Convenience function that updates timestamps and persists.

    Args:
        students_state: The multi-student state
        student: Student whose progress to save
        data_dir: Base data directory

    Returns:
        Path to saved state file
    """
    student.updated_at = datetime.now(timezone.utc).isoformat()
    return save_students_state(students_state, data_dir)


# =============================================================================
# BOOK HELPERS
# =============================================================================


def list_available_books_with_metadata(data_dir: Path) -> list[dict[str, Any]]:
    """Get list of books with title, chapters count, and progress info.

    Args:
        data_dir: Base data directory

    Returns:
        List of dicts with: book_id, title, authors, total_chapters, has_outline, has_units
    """
    books: list[dict[str, Any]] = []

    for book_id in get_available_book_ids(data_dir):
        book_path = data_dir / "books" / book_id
        book_json = book_path / "book.json"
        outline_path = book_path / "outline" / "outline.json"
        units_path = book_path / "artifacts" / "units" / "units.json"

        if not book_json.exists():
            continue

        try:
            with open(book_json, encoding="utf-8") as f:
                book_data = json.load(f)

            # Count chapters from outline if exists
            total_chapters = 0
            if outline_path.exists():
                with open(outline_path, encoding="utf-8") as f:
                    outline = json.load(f)
                total_chapters = len(outline.get("chapters", []))

            books.append(
                {
                    "book_id": book_id,
                    "title": book_data.get("title", book_id),
                    "authors": book_data.get("authors", []),
                    "total_chapters": total_chapters,
                    "has_outline": outline_path.exists(),
                    "has_units": units_path.exists(),
                }
            )
        except (json.JSONDecodeError, OSError):
            # Skip books with invalid metadata
            continue

    return books


def get_chapter_info(
    book_id: str, chapter_number: int, data_dir: Path
) -> dict[str, Any] | None:
    """Get chapter title, sections, and unit IDs for a chapter.

    Args:
        book_id: Book identifier
        chapter_number: 1-based chapter number
        data_dir: Base data directory

    Returns:
        Dict with chapter_id, chapter_number, title, sections, unit_ids
        or None if chapter not found
    """
    outline_path = data_dir / "books" / book_id / "outline" / "outline.json"
    units_path = data_dir / "books" / book_id / "artifacts" / "units" / "units.json"

    if not outline_path.exists():
        return None

    try:
        with open(outline_path, encoding="utf-8") as f:
            outline = json.load(f)

        # Find chapter by number
        chapter_id = f"{book_id}:ch:{chapter_number}"
        chapter = None
        for ch in outline.get("chapters", []):
            if ch.get("chapter_id") == chapter_id or ch.get("number") == chapter_number:
                chapter = ch
                break

        if chapter is None:
            return None

        # Get units for this chapter
        unit_ids: list[str] = []
        if units_path.exists():
            with open(units_path, encoding="utf-8") as f:
                units_data = json.load(f)
            for unit in units_data.get("units", []):
                if unit.get("chapter_id") == chapter_id or unit.get(
                    "chapter_number"
                ) == chapter_number:
                    unit_ids.append(unit["unit_id"])

        return {
            "chapter_id": chapter.get("chapter_id", chapter_id),
            "chapter_number": chapter_number,
            "title": chapter.get("title", f"Capítulo {chapter_number}"),
            "sections": chapter.get("sections", []),
            "unit_ids": unit_ids,
        }

    except (json.JSONDecodeError, OSError, KeyError):
        return None


def get_units_for_chapter(
    book_id: str, chapter_number: int, data_dir: Path
) -> list[str]:
    """Get list of unit_ids for a specific chapter.

    Args:
        book_id: Book identifier
        chapter_number: 1-based chapter number
        data_dir: Base data directory

    Returns:
        List of unit_id strings
    """
    chapter_info = get_chapter_info(book_id, chapter_number, data_dir)
    return chapter_info.get("unit_ids", []) if chapter_info else []


# =============================================================================
# Q&A FUNCTION
# =============================================================================

SYSTEM_PROMPT_QA = """Eres un tutor amigable y experto que dialoga con el estudiante.

ESTILO DE RESPUESTA:
- Responde en español, de forma conversacional y cálida
- NO uses listas ni viñetas por defecto (solo si el estudiante lo pide explícitamente)
- Estructura tu respuesta así: 1-2 párrafos explicativos + un ejemplo concreto + una pregunta breve de verificación
- Si el tema es complejo, usa analogías del mundo real para hacerlo más accesible
- Termina con una pregunta corta para verificar que el estudiante entendió

REGLAS:
- Basa tus respuestas SOLO en los apuntes proporcionados
- Si la pregunta no puede responderse con los apuntes, dilo amablemente y sugiere qué temas sí puedes explicar
- Mantén un tono de mentor que guía, no de enciclopedia que recita

Apuntes del capítulo:
{notes_content}
"""


def answer_question(
    question: str,
    notes_content: str,
    provider: str | None = None,
    model: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Answer a question based on chapter notes content.

    Args:
        question: User's question
        notes_content: Combined notes content for the chapter
        provider: LLM provider override
        model: Model name override
        client: Pre-configured LLM client (for testing)

    Returns:
        Answer string from LLM
    """
    if client is None:
        config = LLMConfig.from_yaml()
        client = LLMClient(
            config=config,
            provider=provider if provider else config.provider,
            model=model if model else config.model,
        )

    # Limit context to avoid token limits
    max_context = 15000
    truncated_notes = notes_content[:max_context]
    if len(notes_content) > max_context:
        truncated_notes += "\n\n[... contenido truncado ...]"

    system = SYSTEM_PROMPT_QA.format(notes_content=truncated_notes)

    response = client.simple_chat(
        system_prompt=system,
        user_message=question,
        temperature=0.3,
    )

    return strip_think(response)


# =============================================================================
# CHAPTER NOTES LOADER
# =============================================================================


def load_chapter_notes(
    book_id: str, chapter_number: int, data_dir: Path
) -> tuple[str, list[str]]:
    """Load all notes for a chapter's units.

    Args:
        book_id: Book identifier
        chapter_number: 1-based chapter number
        data_dir: Base data directory

    Returns:
        Tuple of (combined_notes_content, list_of_unit_ids_with_notes)
    """
    unit_ids = get_units_for_chapter(book_id, chapter_number, data_dir)
    notes_dir = data_dir / "books" / book_id / "artifacts" / "notes"

    combined_notes = ""
    units_with_notes: list[str] = []

    for unit_id in unit_ids:
        notes_path = notes_dir / f"{unit_id}.md"
        if notes_path.exists():
            try:
                content = notes_path.read_text(encoding="utf-8")
                combined_notes += f"\n\n## {unit_id}\n\n{content}"
                units_with_notes.append(unit_id)
            except OSError:
                continue

    return combined_notes.strip(), units_with_notes


def get_missing_notes_units(
    book_id: str, chapter_number: int, data_dir: Path
) -> list[str]:
    """Get list of units that don't have notes generated yet.

    Args:
        book_id: Book identifier
        chapter_number: 1-based chapter number
        data_dir: Base data directory

    Returns:
        List of unit_ids without notes
    """
    unit_ids = get_units_for_chapter(book_id, chapter_number, data_dir)
    notes_dir = data_dir / "books" / book_id / "artifacts" / "notes"

    missing: list[str] = []
    for unit_id in unit_ids:
        notes_path = notes_dir / f"{unit_id}.md"
        if not notes_path.exists():
            missing.append(unit_id)

    return missing


# =============================================================================
# CHAPTER OPENING & NOTES SUMMARY
# =============================================================================


def generate_chapter_opening(
    book_id: str, chapter_number: int, data_dir: Path
) -> dict[str, Any] | None:
    """Generate chapter opening info for display.

    Uses UNITS instead of sections for cleaner display.
    Sections from outline often have garbage data (% symbols, partial sentences).

    F8.1 Fixes:
    - Detect and fallback truncated chapter titles
    - Detect and replace duplicate unit titles
    - Estimate time if missing

    Args:
        book_id: Book identifier
        chapter_number: 1-based chapter number
        data_dir: Base data directory

    Returns:
        Dict with: book_title, chapter_number, chapter_title, overview, objectives, units
        or None if chapter not found
    """
    import re

    # Load book metadata
    book_json = data_dir / "books" / book_id / "book.json"
    if not book_json.exists():
        return None

    try:
        with open(book_json, encoding="utf-8") as f:
            book_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    chapter_info = get_chapter_info(book_id, chapter_number, data_dir)
    if not chapter_info:
        return None

    # F8.1: Detect truncated chapter titles (ending in preposition/article)
    chapter_title = chapter_info.get("title", f"Capítulo {chapter_number}")
    TRUNCATION_INDICATORS = [
        r"\s+(?:de|del|la|el|los|las|a|con|en|para|por|sobre|como|que)\s*$",
    ]
    is_truncated = any(
        re.search(p, chapter_title, re.IGNORECASE) for p in TRUNCATION_INDICATORS
    )
    if is_truncated:
        chapter_title = f"Capítulo {chapter_number}"

    # Load units for this chapter (cleaner than outline sections)
    units_path = data_dir / "books" / book_id / "artifacts" / "units" / "units.json"
    chapter_units: list[dict[str, Any]] = []

    if units_path.exists():
        try:
            with open(units_path, encoding="utf-8") as f:
                units_data = json.load(f)

            # F8.1: First pass - count title occurrences to detect duplicates
            seen_titles: dict[str, int] = {}
            raw_units: list[dict[str, Any]] = []

            for unit in units_data.get("units", []):
                if unit.get("chapter_number") == chapter_number:
                    # Clean up unit title (remove "Parte X/Y" suffix, "ChX - " prefix)
                    unit_title = unit.get("title", "")
                    clean_title = re.sub(r"\s*\(Parte \d+/\d+\)$", "", unit_title)
                    clean_title = re.sub(r"^Ch\d+\s*[-—]\s*", "", clean_title)
                    clean_title = clean_title.strip()

                    seen_titles[clean_title] = seen_titles.get(clean_title, 0) + 1
                    raw_units.append({"unit": unit, "clean_title": clean_title})

            # F8.1: Second pass - use fallback for duplicates/empty titles
            for idx, raw in enumerate(raw_units):
                unit = raw["unit"]
                clean_title = raw["clean_title"]
                unit_num = unit.get("unit_number_in_chapter", idx + 1)

                # If duplicate (>=2) or empty -> fallback to "Unidad X.Y"
                if seen_titles.get(clean_title, 0) >= 2 or not clean_title:
                    display_title = f"Unidad {chapter_number}.{unit_num}"
                else:
                    display_title = clean_title

                # F8.1: Estimate time if missing
                estimated_time = unit.get("estimated_time_min", 0)
                if estimated_time <= 0:
                    section_count = len(unit.get("section_ids", []))
                    estimated_time = max(10, section_count * 4)

                chapter_units.append({
                    "unit_id": unit.get("unit_id"),
                    "number": f"{chapter_number}.{unit_num}",
                    "title": display_title,
                    "estimated_time_min": estimated_time,
                })

        except (json.JSONDecodeError, OSError):
            pass

    # Extract learning objectives if available in units
    objectives: list[str] = []
    for unit in chapter_units:
        if "learning_objectives" in unit:
            objectives.extend(unit["learning_objectives"])

    return {
        "book_title": book_data.get("title", book_id),
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,  # F8.1: Use validated title
        "overview": chapter_info.get("description", ""),
        "objectives": objectives,
        "units": chapter_units,  # Use units instead of sections
    }


def extract_notes_summary(notes_content: str, max_lines: int = 15) -> str:
    """Extract a brief summary from notes for inline display.

    Extracts first meaningful paragraphs up to max_lines.
    Skips unit ID headers that we add when combining notes.

    Args:
        notes_content: Combined notes content
        max_lines: Maximum number of content lines to include

    Returns:
        Summary string suitable for Markdown display
    """
    if not notes_content:
        return ""

    lines: list[str] = []
    current_lines = 0

    for line in notes_content.split("\n"):
        # Skip unit ID headers we added (e.g., "## book-ch01-u01")
        if line.startswith("## ") and "-ch" in line and "-u" in line:
            continue
        # Include content lines
        lines.append(line)
        if line.strip():  # Non-empty line counts
            current_lines += 1
        if current_lines >= max_lines:
            break

    summary = "\n".join(lines).strip()

    # Add continuation hint if truncated
    if len(notes_content) > len(summary) + 50:
        summary += "\n\n*... (escribe una pregunta para explorar más)*"

    return summary


# =============================================================================
# TEACHING-FIRST MODE (F7.3)
# =============================================================================


@dataclass
class TeachingPoint:
    """Un punto del plan de enseñanza."""

    number: int
    title: str
    content: str  # Texto de la subsección de las notas


@dataclass
class TeachingPlan:
    """Plan de enseñanza para una unidad."""

    unit_id: str
    objective: str  # Derivado del Resumen
    points: list[TeachingPoint]  # 4-6 puntos extraídos


def generate_teaching_plan(
    notes_content: str, unit_id: str, unit_title: str = ""
) -> TeachingPlan:
    """Genera teaching plan parseando la sección '## Explicación paso a paso'.

    Las notas tienen estructura:
    ## Explicación paso a paso
    ### 1. Tokenización y vocabulario
    - contenido...
    ### 2. Tipos de modelos
    - contenido...

    Extrae estas subsecciones como TeachingPoints.

    Args:
        notes_content: Contenido markdown de las notas de la unidad
        unit_id: ID de la unidad
        unit_title: Título de la unidad (opcional)

    Returns:
        TeachingPlan con objetivo y lista de puntos
    """
    import re

    # Extraer objetivo del Resumen
    objective = _extract_objective_from_summary(notes_content)

    # Encontrar sección "## Explicación paso a paso"
    exp_match = re.search(
        r"## Explicaci[oó]n paso a paso\s*\n(.*?)(?=\n## |\n---|\Z)",
        notes_content,
        re.DOTALL | re.IGNORECASE,
    )

    points: list[TeachingPoint] = []

    if exp_match:
        exp_section = exp_match.group(1)
        # Buscar subsecciones ### N. Título
        subsections = re.findall(
            r"### (\d+)\.\s*(.+?)\n(.*?)(?=\n### \d+\.|\Z)",
            exp_section,
            re.DOTALL,
        )

        for num_str, title, content in subsections:
            points.append(
                TeachingPoint(
                    number=int(num_str),
                    title=title.strip(),
                    content=content.strip(),
                )
            )

    # F8.3: Si no hay puntos de "Explicación paso a paso", usar fallback
    if not points:
        logger.debug("no_paso_a_paso_section_using_fallback", unit_id=unit_id)
        return generate_plan_from_text_fallback(
            unit_text=notes_content,
            unit_id=unit_id,
            unit_title=unit_title,
            max_points=5,
        )

    return TeachingPlan(
        unit_id=unit_id,
        objective=objective,
        points=points,
    )


def _extract_objective_from_summary(notes_content: str) -> str:
    """Extrae objetivo de aprendizaje del Resumen de las notas.

    Busca la sección ## Resumen y genera un objetivo basado en los puntos.
    """
    import re

    # Buscar sección Resumen
    summary_match = re.search(
        r"## Resumen\s*\n(.*?)(?=\n## |\n---|\Z)",
        notes_content,
        re.DOTALL | re.IGNORECASE,
    )

    if summary_match:
        summary_text = summary_match.group(1).strip()
        # Tomar el primer punto del resumen
        lines = [line.strip() for line in summary_text.split("\n") if line.strip()]
        if lines:
            first_point = lines[0].lstrip("-•* ")
            # Limitar longitud
            if len(first_point) > 150:
                first_point = first_point[:147] + "..."
            return f"Al terminar, entenderás: {first_point}"

    return "Explorar los conceptos clave de esta unidad."


# =============================================================================
# UNIT OPENING (F8.3) - Apertura tipo clase
# =============================================================================


def generate_unit_opening(
    unit_title: str,
    plan: "TeachingPlan",
    student_name: str = "",
    persona_name: str = "tu tutor",
) -> TutorEvent:
    """Genera la apertura de una unidad como lo haría un profesor en clase.

    NO muestra apuntes ni resumen. Solo contexto + objetivo + mapa de puntos.

    Args:
        unit_title: Título de la unidad
        plan: TeachingPlan con objetivo y puntos
        student_name: Nombre del estudiante (opcional)
        persona_name: Nombre de la persona del tutor

    Returns:
        TutorEvent con tipo UNIT_OPENING y markdown de la apertura
    """
    # Construir mapa de puntos
    points_lines = []
    for p in plan.points:
        points_lines.append(f"{p.number}. {p.title}")
    points_map = "\n".join(points_lines)

    # Generar markdown de apertura (sin llamar a LLM para mantenerlo simple)
    greeting = f"Hola{', ' + student_name if student_name else ''}."

    markdown = f"""{greeting} Hoy vamos a trabajar en **{unit_title}**.

{plan.objective}

Veremos estos puntos:
{points_map}

¿Empezamos?"""

    return TutorEvent(
        event_type=TutorEventType.UNIT_OPENING,
        title=unit_title,
        markdown=markdown,
        data={
            "unit_id": plan.unit_id,
            "objective": plan.objective,
            "num_points": len(plan.points),
        },
    )


def generate_plan_from_text_fallback(
    unit_text: str,
    unit_id: str,
    unit_title: str = "",
    max_points: int = 5,
) -> "TeachingPlan":
    """Genera plan de enseñanza cuando no hay estructura '## Explicación paso a paso'.

    Divide el texto en chunks y crea puntos basados en párrafos o secciones.
    NO llama a LLM para mantener el flujo rápido.

    Args:
        unit_text: Texto de la unidad
        unit_id: ID de la unidad
        unit_title: Título de la unidad
        max_points: Máximo de puntos a generar (default 5)

    Returns:
        TeachingPlan con puntos extraídos del texto
    """
    import re

    # Intentar extraer objetivo del texto
    objective = _extract_objective_from_summary(unit_text)

    # Buscar cualquier encabezado ### o ##
    headers = re.findall(r"^#{2,3}\s+(.+?)$", unit_text, re.MULTILINE)

    points: list[TeachingPoint] = []

    if headers:
        # Usar headers como puntos
        for idx, header in enumerate(headers[:max_points], 1):
            # Limpiar header
            clean_header = header.strip().lstrip("0123456789. ")
            if clean_header and clean_header.lower() not in ("resumen", "conceptos clave"):
                # Encontrar contenido después del header
                pattern = rf"#{2,3}\s+{re.escape(header)}\s*\n(.*?)(?=\n#{2,3}|\Z)"
                content_match = re.search(pattern, unit_text, re.DOTALL)
                content = content_match.group(1).strip() if content_match else ""

                points.append(
                    TeachingPoint(
                        number=len(points) + 1,
                        title=clean_header[:60],  # Limitar longitud
                        content=content[:1500] if content else unit_text[:500],
                    )
                )

    # Si no hay headers, dividir por párrafos
    if not points:
        paragraphs = [p.strip() for p in unit_text.split("\n\n") if len(p.strip()) > 100]
        for idx, para in enumerate(paragraphs[:max_points], 1):
            # Generar título del primer contenido
            first_line = para.split(".")[0][:50] if "." in para else para[:50]
            points.append(
                TeachingPoint(
                    number=idx,
                    title=f"Parte {idx}: {first_line}...",
                    content=para[:1500],
                )
            )

    # Fallback final si no hay nada
    if not points:
        points.append(
            TeachingPoint(
                number=1,
                title=unit_title or "Contenido de la unidad",
                content=unit_text[:2000],
            )
        )

    return TeachingPlan(
        unit_id=unit_id,
        objective=objective,
        points=points[:max_points],
    )


# -----------------------------------------------------------------------------
# LLM Prompts for Teaching Mode
# -----------------------------------------------------------------------------

SYSTEM_PROMPT_EXPLAIN_POINT = """Eres un profesor cercano explicando un concepto a un estudiante.

ESTILO:
- Tono conversacional, tutea al estudiante
- 2-4 párrafos máximo
- NO uses listas con viñetas ni tablas
- Incluye un ejemplo breve al final

ESTRUCTURA:
1. Párrafo de contexto/motivación (¿por qué importa?)
2. Párrafo con la explicación principal
3. Ejemplo corto y concreto

PREGUNTA DE VERIFICACIÓN:
- Al final, haz UNA pregunta corta (máximo 15 palabras)
- Puede ser pregunta abierta o de opción múltiple (a/b/c)
- Si es opción múltiple:
  - Presenta las opciones claramente
  - NUNCA incluyas "(Respuesta: X)" ni nada similar
  - NUNCA reveles cuál es la respuesta correcta
- Termina SIEMPRE con la pregunta, sin texto adicional después
"""

SYSTEM_PROMPT_CHECK_COMPREHENSION = """Evalúa si la respuesta del estudiante demuestra comprensión del concepto.

Responde SOLO en JSON válido:
{
  "understood": true o false,
  "confidence": número entre 0.0 y 1.0,
  "feedback": "Comentario breve y amigable",
  "needs_elaboration": true o false
}

CRITERIOS:
- understood=true si la respuesta muestra comprensión básica (no necesita ser perfecta)
- understood=false si hay confusión clara o la respuesta es incorrecta
- confidence indica qué tan seguro estás de tu evaluación
- feedback debe ser breve, positivo si entendió, orientador si no
- needs_elaboration=true si el estudiante debe dar más detalles

RESPUESTAS AFIRMATIVAS SIN EXPLICACIÓN ("sí", "lo entiendo", "creo que sí"):
- NO marques como understood=false automáticamente
- Usa needs_elaboration=true y feedback pidiendo una breve explicación
- Ejemplo: needs_elaboration=true, feedback="¡Bien! ¿Podrías explicarlo brevemente con tus palabras?"

RESPUESTAS TIPO LETRA (a/b/c/d):
- Si el estudiante responde solo con una letra, evalúa si eligió la opción correcta
- Usa el contexto del concepto para determinar cuál es la opción correcta
- NO penalices por respuesta breve si eligió la opción correcta
- Si eligió incorrectamente, explica brevemente por qué en el feedback

NO incluyas texto fuera del JSON.
"""

SYSTEM_PROMPT_REEXPLAIN = """El estudiante no entendió la explicación anterior.
Reexplica el concepto usando una ANALOGÍA del mundo real.

REGLAS:
- Usa una analogía cotidiana (cocina, deportes, música, viajes, etc.)
- Máximo 2 párrafos
- Tono amigable y paciente
- Termina con la misma pregunta de verificación pero reformulada de manera más simple

NO repitas la explicación anterior, usa un enfoque completamente diferente.
"""

# Prompt para generar más ejemplos
SYSTEM_PROMPT_MORE_EXAMPLES = """Genera 2-3 ejemplos adicionales para clarificar el concepto.

REGLAS:
- Ejemplos concretos y variados
- Progresión de simple a más complejo
- Tono conversacional, tutea al estudiante

Termina con: "Ahora puedes: (1) pedirme más ejemplos, (2) explicarme con tus palabras, o (3) avanzar."

NO hagas pregunta de verificación al final.
NO repitas ejemplos ya dados. Usa contextos diferentes (vida cotidiana, trabajo, tecnología).
"""

# Patrones para detectar solicitud de más ejemplos/clarificación
MORE_EXAMPLES_PATTERNS = [
    r"\bm[aá]s\s+ejemplos?\b",
    r"\botro[s]?\s+ejemplos?\b",
    r"\bexpl[ií]ca(?:r?lo|me)?\s+(?:mejor|m[aá]s)\b",  # explica/explicalo/explicarlo mejor
    r"\bno\s+(?:lo\s+)?entiendo\b",
    r"\brepite\b",
    r"\bdetalla\s+m[aá]s\b",
    r"\bno\s+(?:estoy\s+)?seguro\b",
    r"\bdudas?\b",
    r"\bpuedes\s+(?:explicar|dar)\b.*\b(?:m[aá]s|mejor)\b",  # puedes explicar... más/mejor
    r"\bdame\s+(?:otro|más)\b",
    r"\bno\s+me\s+queda\s+claro\b",
    r"\bme\s+(?:puedes|podrías)\s+(?:dar|explicar)\b",
]


def detect_more_examples_intent(text: str) -> bool:
    """Detecta si el estudiante pide más ejemplos o clarificación.

    Args:
        text: Respuesta del estudiante

    Returns:
        True si el estudiante pide más ejemplos/clarificación
    """
    text_lower = text.lower().strip()

    for pattern in MORE_EXAMPLES_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


# =============================================================================
# PATRONES DE INTENT ADICIONALES (F7.4)
# =============================================================================

# Patrones para detectar intención de avanzar
ADVANCE_INTENT_PATTERNS = [
    r"\bavan[zc](?:ar?|amos|emos)\b",  # avanzar, avanza, avanzamos, avancemos (z->c)
    r"\bpas(?:ar|emos|amos)\b",         # pasar, pasemos, pasamos
    r"\bsiguiente\s+(?:punto|secci[oó]n|tema)\b",
    r"^siguiente$",                      # F8.2.1: "siguiente" solo
    r"\bpodemos\s+(?:pasar|avanzar|seguir)\b",
    r"\bvamos\s+(?:al\s+)?siguiente\b",
    r"\bcontinu(?:ar|emos|amos)\b",     # continuar, continuemos, continuamos
    r"\badelante\b",
    r"\bsig(?:o|amos)\b",               # sigo, sigamos
]

# Patrones para respuestas afirmativas simples
AFFIRMATIVE_PATTERNS = [
    r"^s[ií]$",
    r"^y(?:es)?$",       # y, yes
    r"^vale$",
    r"^ok(?:ay)?$",
    r"^claro$",
    r"^dale$",
    r"^venga$",
    r"^perfecto$",
    r"^de\s+acuerdo$",
    r"^genial$",
    r"^bueno$",
    r"^vamos$",
    r"^adelante$",
]


def is_advance_intent(text: str) -> bool:
    """Detecta si el usuario quiere avanzar al siguiente punto.

    Args:
        text: Respuesta del usuario

    Returns:
        True si el usuario quiere avanzar
    """
    text_lower = text.lower().strip()

    for pattern in ADVANCE_INTENT_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def is_affirmative(text: str) -> bool:
    """Detecta respuestas afirmativas simples (sí, vale, ok).

    Solo detecta respuestas que son SOLO afirmativas, no frases
    que contienen "sí" como parte de una oración.

    Args:
        text: Respuesta del usuario

    Returns:
        True si es una respuesta afirmativa simple
    """
    text_lower = text.lower().strip()

    for pattern in AFFIRMATIVE_PATTERNS:
        if re.match(pattern, text_lower):
            return True
    return False


# =============================================================================
# PATRONES NEGATIVOS (F8.1)
# =============================================================================

# Patrones para respuestas negativas simples
NEGATIVE_PATTERNS = [
    r"^no?$",              # n, no
    r"^espera$",
    r"^a[úu]n\s+no$",      # aún no, aun no
    r"^todav[ií]a\s+no$",  # todavía no
    r"^repite$",
    r"^m[áa]s\s+lento$",
    r"^no\s+(?:estoy\s+)?seguro$",
]


def is_negative(text: str) -> bool:
    """Detecta respuestas negativas simples (n, no, espera, aún no).

    Args:
        text: Respuesta del usuario

    Returns:
        True si es una respuesta negativa simple
    """
    text_lower = text.lower().strip()

    for pattern in NEGATIVE_PATTERNS:
        if re.match(pattern, text_lower):
            return True
    return False


def parse_confirm_advance_response(text: str) -> str:
    """Parsea respuesta a '¿Avanzamos al siguiente punto?'.

    Args:
        text: Respuesta del usuario

    Returns:
        'advance' - usuario quiere avanzar
        'stay' - usuario quiere quedarse/profundizar
        'command' - es un comando global (apuntes, control, etc)
        'unknown' - no reconocido, repreguntarse
    """
    text_lower = text.lower().strip()

    # Comandos globales - manejar aparte
    if text_lower in ("apuntes", "control", "examen", "stop"):
        return "command"

    # YES intents -> advance
    if is_affirmative(text_lower) or is_advance_intent(text_lower):
        return "advance"

    # NO intents -> stay
    if is_negative(text_lower) or detect_more_examples_intent(text_lower):
        return "stay"

    return "unknown"


# =============================================================================
# PATRONES PARA POST_FAILURE_CHOICE (F8.2.1)
# =============================================================================

# Patrones explícitos de "quiero repasar/revisar"
REVIEW_INTENT_PATTERNS = [
    r"\brepas(?:ar|o|emos)\b",        # repasar, repaso, repasemos
    r"\brevisa(?:r|mos)\b",           # revisar, revisamos
    r"\brepite\b",                     # repite
    r"\bexplica\s+(?:mejor|m[áa]s)\b",  # explica mejor/más
    r"\bno\s+entiendo\b",
    r"\bm[áa]s\s+lento\b",
]


def is_review_intent(text: str) -> bool:
    """Detecta si el usuario quiere repasar/revisar.

    Args:
        text: Respuesta del usuario

    Returns:
        True si quiere repasar
    """
    text_lower = text.lower().strip()

    for pattern in REVIEW_INTENT_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def parse_post_failure_choice_response(text: str, default_after_failure: str = "stay") -> str:
    """Parsea respuesta a POST_FAILURE_CHOICE: '[A]vanzar | [R]epasar'.

    Acepta lenguaje natural además de A/R.

    Args:
        text: Respuesta del usuario
        default_after_failure: 'advance' o 'stay' (para Enter vacío o ambiguo)

    Returns:
        'advance' - usuario quiere avanzar
        'review' - usuario quiere repasar
        'command' - es un comando global
        'unknown' - no reconocido
    """
    text_lower = text.lower().strip()

    # Comandos globales
    if text_lower in ("apuntes", "control", "examen", "stop"):
        return "command"

    # Entrada vacía -> usar default
    if text_lower == "":
        return "advance" if default_after_failure == "advance" else "review"

    # Explícito A/R
    if text_lower in ("a", "avanzar", "adelante"):
        return "advance"
    if text_lower in ("r", "repasar", "repaso"):
        return "review"

    # Intents de avance (avancemos, siguiente, continuar, etc.)
    if is_advance_intent(text_lower):
        return "advance"

    # Intents de review (repasar, explica mejor, más lento, etc.)
    if is_review_intent(text_lower):
        return "review"

    # "más ejemplos" -> review
    if detect_more_examples_intent(text_lower):
        return "review"

    # Negativos (no, espera, aún no) -> review
    if is_negative(text_lower):
        return "review"

    # Afirmativos ambiguos (sí, vale, ok) -> usar default
    if is_affirmative(text_lower):
        return "advance" if default_after_failure == "advance" else "review"

    return "unknown"


def generate_more_examples(
    point: TeachingPoint,
    previous_explanation: str,
    provider: str | None = None,
    model: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Genera ejemplos adicionales sin avanzar de punto.

    Args:
        point: El punto actual siendo explicado
        previous_explanation: Explicación ya dada (para no repetir)
        provider: Provider LLM (opcional)
        model: Modelo LLM (opcional)
        client: Cliente LLM existente (opcional)

    Returns:
        2-3 ejemplos nuevos + pregunta de verificación
    """
    if client is None:
        config = LLMConfig(provider=provider or "lmstudio", model=model or "default")
        client = LLMClient(config)

    user_prompt = f"""Concepto: {point.title}

Contenido de referencia:
{point.content[:1000]}

Ya explicaste (NO repitas estos ejemplos):
{previous_explanation[:500]}

Genera 2-3 ejemplos NUEVOS y diferentes.
"""

    response = client.simple_chat(
        system_prompt=SYSTEM_PROMPT_MORE_EXAMPLES,
        user_message=user_prompt,
        temperature=0.8,
    )

    return strip_think(response)


# Prompt para profundizar en explicación
SYSTEM_PROMPT_DEEPEN = """Profundiza en el concepto explicado.
El estudiante quiere saber más detalles.

REGLAS:
- Expande la explicación anterior con 2-3 detalles adicionales
- Incluye 1-2 ejemplos nuevos
- Máximo 3 párrafos
- Tono conversacional
- NO repitas lo ya dicho

Termina con: "Ahora puedes: (1) pedirme más ejemplos, (2) explicarme con tus palabras, o (3) avanzar."
"""


def generate_deeper_explanation(
    point: TeachingPoint,
    previous_explanation: str,
    provider: str | None = None,
    model: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Genera explicación más profunda del concepto.

    Se usa cuando el estudiante responde "sí" o "vale" a una pregunta
    tipo "¿Quieres profundizar en esto?"

    Args:
        point: El punto actual siendo explicado
        previous_explanation: Explicación ya dada (para expandir)
        provider: Provider LLM (opcional)
        model: Modelo LLM (opcional)
        client: Cliente LLM existente (opcional)

    Returns:
        Explicación más profunda + opciones claras
    """
    if client is None:
        config = LLMConfig(provider=provider or "lmstudio", model=model or "default")
        client = LLMClient(config)

    user_prompt = f"""Concepto: {point.title}

Contenido de referencia:
{point.content[:1000]}

Ya explicaste esto:
{previous_explanation[:800]}

Profundiza con más detalles y ejemplos adicionales. NO repitas lo ya dicho.
"""

    response = client.simple_chat(
        system_prompt=SYSTEM_PROMPT_DEEPEN,
        user_message=user_prompt,
        temperature=0.8,
    )

    return strip_think(response)


def explain_point(
    point: TeachingPoint,
    notes_context: str,
    provider: str | None = None,
    model: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Genera explicación conversacional de un punto con ejemplo y pregunta.

    Args:
        point: El punto a explicar
        notes_context: Contexto de las notas para referencia
        provider: Provider LLM (opcional)
        model: Modelo LLM (opcional)
        client: Cliente LLM existente (opcional)

    Returns:
        Explicación en formato conversacional
    """
    if client is None:
        config = LLMConfig(provider=provider or "lmstudio", model=model or "default")
        client = LLMClient(config)

    user_prompt = f"""Explica el siguiente punto de la lección:

**Punto {point.number}: {point.title}**

Contenido de referencia:
{point.content[:1500]}

Recuerda: tono conversacional, 2-4 párrafos, un ejemplo breve, y una pregunta de verificación al final.
"""

    response = client.simple_chat(
        system_prompt=SYSTEM_PROMPT_EXPLAIN_POINT,
        user_message=user_prompt,
        temperature=0.7,
    )

    return strip_think(response)


def check_comprehension(
    check_question: str,
    student_response: str,
    concept_context: str,
    provider: str | None = None,
    model: str | None = None,
    client: LLMClient | None = None,
) -> tuple[bool, str, bool]:
    """Evalúa si la respuesta del estudiante demuestra comprensión.

    Soporta:
    - Respuestas libres: evaluación por LLM
    - Respuestas MCQ (a/b/c/d): evaluación con contexto de opciones
    - Respuestas afirmativas sin explicación: pide elaboración

    Args:
        check_question: La pregunta de verificación original
        student_response: Respuesta del estudiante
        concept_context: Contexto del concepto explicado
        provider: Provider LLM (opcional)
        model: Modelo LLM (opcional)
        client: Cliente LLM existente (opcional)

    Returns:
        Tupla (understood: bool, feedback: str, needs_elaboration: bool)
    """
    import json as json_module
    import re

    if client is None:
        config = LLMConfig(provider=provider or "lmstudio", model=model or "default")
        client = LLMClient(config)

    # Normalizar respuesta
    response_normalized = student_response.strip().lower()

    # Detectar si es respuesta tipo letra MCQ (a, b, c, d, o con punto)
    is_letter_response = bool(re.match(r"^[a-d]\.?$", response_normalized))

    if is_letter_response:
        # Prompt específico para respuestas tipo letra
        letter = response_normalized[0]
        user_prompt = f"""Pregunta de verificación: {check_question}

Respuesta del estudiante: "{student_response}" (eligió la opción {letter})

Contexto del concepto: {concept_context[:500]}

El estudiante eligió la opción '{letter}'. Evalúa si esa es la opción correcta basándote en el concepto explicado.
NO penalices por respuesta breve; solo evalúa si la opción elegida es correcta.

Responde SOLO en JSON.
"""
    else:
        # Prompt para respuestas libres
        user_prompt = f"""Pregunta de verificación: {check_question}

Respuesta del estudiante: {student_response}

Contexto del concepto: {concept_context[:500]}

Evalúa si el estudiante entendió. Responde SOLO en JSON.
"""

    response = client.simple_chat(
        system_prompt=SYSTEM_PROMPT_CHECK_COMPREHENSION,
        user_message=user_prompt,
        temperature=0.3,
    )

    # Limpiar respuesta
    response = strip_think(response).strip()

    # Intentar parsear JSON
    try:
        # Buscar JSON en la respuesta
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            result = json_module.loads(json_match.group())
            understood = result.get("understood", False)
            feedback = result.get("feedback", "")
            needs_elaboration = result.get("needs_elaboration", False)
            return understood, feedback, needs_elaboration
    except (json_module.JSONDecodeError, AttributeError):
        pass

    # Fallback: asumir que no entendió si no podemos parsear
    return False, "Veamos esto de otra manera...", False


def reexplain_with_analogy(
    point: TeachingPoint,
    original_question: str,
    provider: str | None = None,
    model: str | None = None,
    client: LLMClient | None = None,
) -> str:
    """Reexplica un punto usando una analogía del mundo real.

    Args:
        point: El punto a reexplicar
        original_question: La pregunta de verificación original
        provider: Provider LLM (opcional)
        model: Modelo LLM (opcional)
        client: Cliente LLM existente (opcional)

    Returns:
        Nueva explicación con analogía
    """
    if client is None:
        config = LLMConfig(provider=provider or "lmstudio", model=model or "default")
        client = LLMClient(config)

    user_prompt = f"""Concepto a reexplicar: {point.title}

Contenido original: {point.content[:800]}

Pregunta de verificación original: {original_question}

Reexplica usando una analogía cotidiana y termina con una versión más simple de la pregunta.
"""

    response = client.simple_chat(
        system_prompt=SYSTEM_PROMPT_REEXPLAIN,
        user_message=user_prompt,
        temperature=0.8,  # Más creatividad para analogías
    )

    return strip_think(response)
