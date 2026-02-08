"""Tutor Engine for Web API (F9.1).

Orchestrates the teaching logic for web sessions, reusing core tutor functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any

import structlog

from teaching.config.personas import get_persona, get_default_persona, Persona
from teaching.core.tutor import (
    TutorEvent,
    TutorEventType,
    TutorTurnContext,
    generate_event_id,
    # Student/state management
    load_students_state,
    save_student_progress,
    StudentProfile,
    # Book/content helpers
    list_available_books_with_metadata,
    get_chapter_info,
    load_chapter_notes,
    # Teaching functions
    generate_teaching_plan,
    generate_plan_from_text_fallback,
    generate_unit_opening,
    explain_point,
    check_comprehension,
    reexplain_with_analogy,
    generate_more_examples,
    TeachingPlan,
    TeachingPoint,
)
from teaching.llm.client import LLMClient, LLMConfig

logger = structlog.get_logger(__name__)

# Default data directory
DATA_DIR = Path("data")


class WebTeachingState(Enum):
    """Teaching states for web sessions."""

    UNIT_OPENING = auto()
    WAIT_UNIT_START = auto()
    EXPLAINING = auto()
    WAITING_INPUT = auto()
    CHECKING = auto()
    MORE_EXAMPLES = auto()
    AWAITING_RETRY = auto()
    REMEDIATION = auto()
    NEXT_POINT = auto()
    CONFIRM_ADVANCE = auto()
    POST_FAILURE_CHOICE = auto()
    UNIT_COMPLETE = auto()


@dataclass
class WebSessionState:
    """State for a web teaching session."""

    session_id: str
    student_id: str
    book_id: str
    chapter_number: int
    unit_number: int
    persona_id: str = "dra_vega"

    # Teaching state
    state: WebTeachingState = WebTeachingState.UNIT_OPENING
    plan: TeachingPlan | None = None
    current_point_index: int = 0
    attempts_this_point: int = 0
    followups_this_point: int = 0

    # Context for LLM
    last_explanation: str = ""
    last_check_question: str = ""
    notes_text: str = ""

    # Turn tracking
    turn_context: TutorTurnContext = field(default_factory=TutorTurnContext)


class TutorEngine:
    """Engine for managing web teaching sessions."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self._sessions: dict[str, WebSessionState] = {}
        self._llm_client: LLMClient | None = None

    def _get_llm_client(self) -> LLMClient:
        """Get or create LLM client."""
        if self._llm_client is None:
            config = LLMConfig.from_yaml()
            self._llm_client = LLMClient(config)
        return self._llm_client

    def _get_persona(self, persona_id: str) -> Persona:
        """Get persona by ID or default."""
        persona = get_persona(persona_id)
        if persona is None:
            return get_default_persona()
        return persona

    def _get_unit_id(self, book_id: str, chapter: int, unit: int) -> str:
        """Generate unit ID from book/chapter/unit."""
        return f"{book_id}-ch{chapter:02d}-u{unit:02d}"

    def _load_notes(self, book_id: str, chapter: int, unit: int) -> str:
        """Load notes for a unit."""
        unit_id = self._get_unit_id(book_id, chapter, unit)
        notes_path = (
            self.data_dir / "books" / book_id / "artifacts" / "notes" / f"{unit_id}.md"
        )
        if notes_path.exists():
            return notes_path.read_text(encoding="utf-8")
        return ""

    def _get_teaching_policy(self, persona_id: str):
        """Get teaching policy from persona."""
        persona = self._get_persona(persona_id)
        return persona.get_teaching_policy()

    def start_session(
        self,
        session_id: str,
        student_id: str,
        book_id: str,
        chapter_number: int = 1,
        unit_number: int = 1,
        persona_id: str = "dra_vega",
    ) -> list[TutorEvent]:
        """Start a new teaching session.

        Returns initial events (unit opening, etc.)
        """
        # Load notes
        notes_text = self._load_notes(book_id, chapter_number, unit_number)
        if not notes_text:
            # Return error event if no notes
            return [
                TutorEvent(
                    event_type=TutorEventType.FEEDBACK,
                    event_id=generate_event_id(),
                    turn_id=0,
                    seq=1,
                    title="Error",
                    markdown=f"No se encontraron apuntes para la unidad {chapter_number}.{unit_number} del libro '{book_id}'.",
                    data={"error": True},
                )
            ]

        # Generate teaching plan
        unit_id = self._get_unit_id(book_id, chapter_number, unit_number)
        unit_title = f"Capítulo {chapter_number}, Unidad {unit_number}"

        try:
            plan = generate_teaching_plan(notes_text, unit_id, unit_title)
        except Exception:
            # Fallback plan generation
            plan = generate_plan_from_text_fallback(notes_text, unit_id, unit_title)

        if not plan.points:
            return [
                TutorEvent(
                    event_type=TutorEventType.FEEDBACK,
                    event_id=generate_event_id(),
                    turn_id=0,
                    seq=1,
                    title="Error",
                    markdown="No se pudo generar un plan de enseñanza para esta unidad.",
                    data={"error": True},
                )
            ]

        # Get student name
        student_name = ""
        try:
            students_state = load_students_state(self.data_dir)
            student = students_state.get_student_by_id(student_id)
            if student:
                student_name = student.name
        except Exception:
            pass

        # Get persona
        persona = self._get_persona(persona_id)

        # Create session state
        session_state = WebSessionState(
            session_id=session_id,
            student_id=student_id,
            book_id=book_id,
            chapter_number=chapter_number,
            unit_number=unit_number,
            persona_id=persona_id,
            plan=plan,
            notes_text=notes_text,
            state=WebTeachingState.WAIT_UNIT_START,
        )
        self._sessions[session_id] = session_state

        # Generate unit opening event
        opening_event = generate_unit_opening(
            unit_title=unit_title,
            plan=plan,
            student_name=student_name,
            persona_name=persona.name,
        )

        # Add event IDs
        session_state.turn_context.advance_turn()
        opening_event.event_id = generate_event_id()
        opening_event.turn_id = session_state.turn_context.turn_id
        opening_event.seq = 1

        # Save session start to student progress
        self._save_session_start(session_state)

        logger.info(
            "session_started",
            session_id=session_id,
            student_id=student_id,
            book_id=book_id,
            num_points=len(plan.points),
        )

        return [opening_event]

    def handle_input(self, session_id: str, text: str) -> list[TutorEvent]:
        """Handle user input and return response events."""
        session = self._sessions.get(session_id)
        if session is None:
            return [
                TutorEvent(
                    event_type=TutorEventType.FEEDBACK,
                    event_id=generate_event_id(),
                    turn_id=0,
                    seq=1,
                    markdown="Sesión no encontrada.",
                    data={"error": True},
                )
            ]

        # Advance turn
        session.turn_context.advance_turn()
        events: list[TutorEvent] = []

        # Handle based on current state
        if session.state == WebTeachingState.WAIT_UNIT_START:
            events = self._handle_unit_start(session, text)

        elif session.state == WebTeachingState.WAITING_INPUT:
            events = self._handle_waiting_input(session, text)

        elif session.state == WebTeachingState.AWAITING_RETRY:
            events = self._handle_retry(session, text)

        elif session.state == WebTeachingState.POST_FAILURE_CHOICE:
            events = self._handle_post_failure_choice(session, text)

        elif session.state == WebTeachingState.CONFIRM_ADVANCE:
            events = self._handle_confirm_advance(session, text)

        else:
            # Default: try to continue
            events = self._continue_teaching(session)

        # Assign event IDs
        for i, event in enumerate(events, start=1):
            if not event.event_id:
                event.event_id = generate_event_id()
            event.turn_id = session.turn_context.turn_id
            event.seq = i

        return events

    def _handle_unit_start(
        self, session: WebSessionState, text: str
    ) -> list[TutorEvent]:
        """Handle input during WAIT_UNIT_START state."""
        text_lower = text.strip().lower()

        # Check for affirmative response
        affirmative_patterns = [
            "sí", "si", "yes", "ok", "vale", "empezamos", "comenzamos",
            "adelante", "vamos", "claro", "por supuesto", "dale",
        ]

        is_affirmative = any(p in text_lower for p in affirmative_patterns)

        if is_affirmative:
            # Move to explaining first point
            session.state = WebTeachingState.EXPLAINING
            return self._explain_current_point(session)

        # Not ready, ask again
        return [
            TutorEvent(
                event_type=TutorEventType.ASK_CHECK,
                markdown="Cuando estés listo, escribe 'sí' o 'empezamos' para comenzar.",
            )
        ]

    def _handle_waiting_input(
        self, session: WebSessionState, text: str
    ) -> list[TutorEvent]:
        """Handle input during WAITING_INPUT state."""
        text_lower = text.strip().lower()

        # Check for special commands
        if self._is_advance_intent(text_lower):
            return self._advance_to_next_point(session)

        if self._is_more_examples_intent(text_lower):
            return self._generate_more_examples(session)

        # Regular response - check comprehension
        return self._check_response(session, text)

    def _handle_retry(
        self, session: WebSessionState, text: str
    ) -> list[TutorEvent]:
        """Handle input during AWAITING_RETRY state."""
        text_lower = text.strip().lower()

        # Check for advance intent
        if self._is_advance_intent(text_lower):
            policy = self._get_teaching_policy(session.persona_id)
            if policy.allow_advance_on_failure:
                return self._advance_to_next_point(session)
            else:
                return [
                    TutorEvent(
                        event_type=TutorEventType.FEEDBACK,
                        markdown="Necesitas responder correctamente antes de avanzar. Inténtalo de nuevo.",
                    )
                ]

        # Check response again
        return self._check_response(session, text, is_retry=True)

    def _handle_post_failure_choice(
        self, session: WebSessionState, text: str
    ) -> list[TutorEvent]:
        """Handle input during POST_FAILURE_CHOICE state."""
        text_lower = text.strip().lower()

        # Check for advance
        if "a" in text_lower or self._is_advance_intent(text_lower):
            return self._advance_to_next_point(session)

        # Stay and get remediation
        session.state = WebTeachingState.REMEDIATION
        return self._do_remediation(session)

    def _handle_confirm_advance(
        self, session: WebSessionState, text: str
    ) -> list[TutorEvent]:
        """Handle input during CONFIRM_ADVANCE state."""
        text_lower = text.strip().lower()

        if self._is_affirmative(text_lower) or self._is_advance_intent(text_lower):
            return self._advance_to_next_point(session)

        # Stay and continue
        session.state = WebTeachingState.WAITING_INPUT
        return [
            TutorEvent(
                event_type=TutorEventType.ASK_CHECK,
                markdown=session.last_check_question or "¿Tienes alguna pregunta?",
            )
        ]

    def _continue_teaching(self, session: WebSessionState) -> list[TutorEvent]:
        """Continue teaching from current state."""
        if session.state == WebTeachingState.EXPLAINING:
            return self._explain_current_point(session)
        elif session.state == WebTeachingState.NEXT_POINT:
            return self._advance_to_next_point(session)
        elif session.state == WebTeachingState.REMEDIATION:
            return self._do_remediation(session)
        else:
            return []

    def _explain_current_point(self, session: WebSessionState) -> list[TutorEvent]:
        """Explain the current teaching point."""
        if session.plan is None or session.current_point_index >= len(session.plan.points):
            # No more points
            session.state = WebTeachingState.UNIT_COMPLETE
            return [
                TutorEvent(
                    event_type=TutorEventType.UNIT_NOTES,
                    title="¡Unidad completada!",
                    markdown="Has completado todos los puntos de esta unidad. ¡Buen trabajo!",
                )
            ]

        point = session.plan.points[session.current_point_index]
        client = self._get_llm_client()

        # Generate explanation
        explanation = explain_point(
            point=point,
            notes_context=session.notes_text[:2000],
            client=client,
        )

        # Extract question from explanation
        check_question = self._extract_question(explanation)
        session.last_explanation = explanation
        session.last_check_question = check_question
        session.attempts_this_point = 0
        session.followups_this_point = 0
        session.state = WebTeachingState.WAITING_INPUT

        events = [
            TutorEvent(
                event_type=TutorEventType.POINT_OPENING,
                title=f"Punto {point.number}: {point.title}",
                markdown="",
            ),
            TutorEvent(
                event_type=TutorEventType.POINT_EXPLANATION,
                markdown=explanation,
                data={"point_number": point.number},
            ),
        ]

        return events

    def _check_response(
        self, session: WebSessionState, text: str, is_retry: bool = False
    ) -> list[TutorEvent]:
        """Check student response for comprehension."""
        client = self._get_llm_client()
        policy = self._get_teaching_policy(session.persona_id)

        session.attempts_this_point += 1

        understood, feedback, needs_elaboration = check_comprehension(
            check_question=session.last_check_question,
            student_response=text,
            concept_context=session.last_explanation[:1000],
            client=client,
        )

        events = [
            TutorEvent(
                event_type=TutorEventType.FEEDBACK,
                markdown=feedback,
                data={"understood": understood, "needs_elaboration": needs_elaboration},
            )
        ]

        if understood and not needs_elaboration:
            # Full comprehension! Offer to advance
            session.state = WebTeachingState.CONFIRM_ADVANCE
            events.append(
                TutorEvent(
                    event_type=TutorEventType.ASK_CONFIRM_ADVANCE,
                    markdown="¿Avanzamos al siguiente punto?",
                )
            )
        elif understood and needs_elaboration:
            # Understands but needs to elaborate (e.g., answered "sí" without explanation)
            # Stay in WAITING_INPUT - the FEEDBACK already contains the elaboration question
            session.state = WebTeachingState.WAITING_INPUT
            # Don't add another event - avoid double blocking questions
        else:
            # Not understood
            if session.attempts_this_point >= policy.max_attempts_per_point:
                # Max attempts reached
                if policy.allow_advance_on_failure:
                    session.state = WebTeachingState.POST_FAILURE_CHOICE
                    events.append(
                        TutorEvent(
                            event_type=TutorEventType.ASK_CHECK,
                            markdown="Escribe [A] para avanzar o [R] para repasar con una analogía.",
                        )
                    )
                else:
                    # Must do remediation
                    session.state = WebTeachingState.REMEDIATION
                    events.extend(self._do_remediation(session))
            else:
                # Allow retry
                session.state = WebTeachingState.AWAITING_RETRY
                events.append(
                    TutorEvent(
                        event_type=TutorEventType.ASK_CHECK,
                        markdown="Inténtalo de nuevo. " + session.last_check_question,
                    )
                )

        return events

    def _do_remediation(self, session: WebSessionState) -> list[TutorEvent]:
        """Generate remediation with analogy."""
        if session.plan is None or session.current_point_index >= len(session.plan.points):
            return []

        point = session.plan.points[session.current_point_index]
        client = self._get_llm_client()

        remediation = reexplain_with_analogy(
            point=point,
            original_explanation=session.last_explanation,
            notes_context=session.notes_text[:1500],
            client=client,
        )

        # Extract new question
        new_question = self._extract_question(remediation)
        session.last_explanation = remediation
        session.last_check_question = new_question
        session.attempts_this_point = 0  # Reset attempts after remediation
        session.state = WebTeachingState.WAITING_INPUT

        return [
            TutorEvent(
                event_type=TutorEventType.POINT_EXPLANATION,
                title="Explicación con analogía",
                markdown=remediation,
            )
        ]

    def _generate_more_examples(self, session: WebSessionState) -> list[TutorEvent]:
        """Generate more examples for current point."""
        if session.plan is None or session.current_point_index >= len(session.plan.points):
            return []

        policy = self._get_teaching_policy(session.persona_id)
        if session.followups_this_point >= policy.max_followups_per_point:
            return [
                TutorEvent(
                    event_type=TutorEventType.FEEDBACK,
                    markdown="Ya hemos visto varios ejemplos. Intenta responder la pregunta.",
                )
            ]

        point = session.plan.points[session.current_point_index]
        client = self._get_llm_client()

        examples = generate_more_examples(
            point=point,
            previous_explanation=session.last_explanation,
            notes_context=session.notes_text[:1500],
            client=client,
        )

        session.followups_this_point += 1

        return [
            TutorEvent(
                event_type=TutorEventType.POINT_EXPLANATION,
                title="Más ejemplos",
                markdown=examples,
            ),
            TutorEvent(
                event_type=TutorEventType.ASK_CHECK,
                markdown=session.last_check_question,
            ),
        ]

    def _advance_to_next_point(self, session: WebSessionState) -> list[TutorEvent]:
        """Advance to the next teaching point."""
        session.current_point_index += 1
        session.attempts_this_point = 0
        session.followups_this_point = 0

        if session.plan and session.current_point_index >= len(session.plan.points):
            # Unit complete
            session.state = WebTeachingState.UNIT_COMPLETE
            return [
                TutorEvent(
                    event_type=TutorEventType.UNIT_NOTES,
                    title="¡Unidad completada!",
                    markdown="Has completado todos los puntos de esta unidad. ¡Excelente trabajo!",
                    data={"unit_complete": True},
                )
            ]

        session.state = WebTeachingState.EXPLAINING
        return self._explain_current_point(session)

    def _extract_question(self, text: str) -> str:
        """Extract the last question from explanation text."""
        import re
        # Find questions (lines ending with ?)
        questions = re.findall(r"[^\n.!?]*\?", text)
        if questions:
            return questions[-1].strip()
        return "¿Qué has entendido de esto?"

    def _is_advance_intent(self, text: str) -> bool:
        """Check if text indicates intent to advance."""
        patterns = [
            "adelante", "siguiente", "avanzar", "continuar",
            "next", "skip", "saltar", "paso",
        ]
        return any(p in text.lower() for p in patterns)

    def _is_more_examples_intent(self, text: str) -> bool:
        """Check if text indicates request for more examples."""
        patterns = [
            "más ejemplos", "otro ejemplo", "ejemplos",
            "no entiendo", "no comprendo", "me explicas",
            "more examples", "example",
        ]
        return any(p in text.lower() for p in patterns)

    def _is_affirmative(self, text: str) -> bool:
        """Check if text is affirmative."""
        patterns = ["sí", "si", "yes", "ok", "vale", "claro", "dale"]
        return any(p in text.lower() for p in patterns)

    def get_session(self, session_id: str) -> WebSessionState | None:
        """Get session state by ID."""
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> bool:
        """End a session, save progress, and clean up."""
        session = self._sessions.get(session_id)
        if session:
            # Save progress before removing session
            self._save_session_progress(session)
            del self._sessions[session_id]
            return True
        return False

    def _save_session_start(self, session: WebSessionState) -> None:
        """Save session start to student progress."""
        try:
            students_state = load_students_state(self.data_dir)
            student = students_state.get_student_by_id(session.student_id)
            if student:
                book_progress = student.tutor_state.get_book_progress(session.book_id)
                book_progress.last_chapter_number = session.chapter_number
                book_progress.last_session_at = datetime.now(timezone.utc).isoformat()
                save_student_progress(students_state, student, self.data_dir)
                logger.info(
                    "session_progress_saved",
                    event="start",
                    student_id=session.student_id,
                    book_id=session.book_id,
                    chapter=session.chapter_number,
                )
        except Exception as e:
            logger.warning("failed_to_save_session_start", error=str(e))

    def _save_session_progress(self, session: WebSessionState) -> None:
        """Save session progress when ending."""
        try:
            students_state = load_students_state(self.data_dir)
            student = students_state.get_student_by_id(session.student_id)
            if student:
                book_progress = student.tutor_state.get_book_progress(session.book_id)
                book_progress.last_session_at = datetime.now(timezone.utc).isoformat()
                # Track unit completion if applicable
                if session.state == WebTeachingState.UNIT_COMPLETE:
                    logger.info(
                        "unit_completed",
                        student_id=session.student_id,
                        book_id=session.book_id,
                        chapter=session.chapter_number,
                        unit=session.unit_number,
                    )
                save_student_progress(students_state, student, self.data_dir)
                logger.info(
                    "session_progress_saved",
                    event="end",
                    student_id=session.student_id,
                    book_id=session.book_id,
                    state=session.state.name,
                )
        except Exception as e:
            logger.warning("failed_to_save_session_progress", error=str(e))


# Global engine instance
_tutor_engine: TutorEngine | None = None


def get_tutor_engine() -> TutorEngine:
    """Get the global tutor engine instance."""
    global _tutor_engine
    if _tutor_engine is None:
        _tutor_engine = TutorEngine()
    return _tutor_engine


def reset_tutor_engine() -> None:
    """Reset the tutor engine (for testing)."""
    global _tutor_engine
    _tutor_engine = None
