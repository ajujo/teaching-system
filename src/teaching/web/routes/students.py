"""Student endpoints (F9)."""

from fastapi import APIRouter, HTTPException, status
from pathlib import Path

from teaching.core.tutor import (
    StudentsState,
    load_students_state,
    save_students_state,
    validate_email,
)
from teaching.web.schemas import (
    StudentCreate,
    StudentResponse,
    StudentListResponse,
)

router = APIRouter(prefix="/api/students", tags=["students"])


def _get_students_state() -> StudentsState:
    """Load students state from disk."""
    return load_students_state()


def _save_students_state(state: StudentsState) -> None:
    """Save students state to disk."""
    save_students_state(state)


@router.get("", response_model=StudentListResponse)
async def list_students() -> StudentListResponse:
    """List all students."""
    state = _get_students_state()
    students = [
        StudentResponse(
            student_id=s.student_id,
            name=s.name,
            surname=s.surname,
            email=s.email,
            tutor_persona_id=s.tutor_persona_id,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in state.students
    ]
    return StudentListResponse(students=students, count=len(students))


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(student_id: str) -> StudentResponse:
    """Get a specific student by ID."""
    state = _get_students_state()
    student = state.get_student_by_id(student_id)

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' not found",
        )

    return StudentResponse(
        student_id=student.student_id,
        name=student.name,
        surname=student.surname,
        email=student.email,
        tutor_persona_id=student.tutor_persona_id,
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(student_data: StudentCreate) -> StudentResponse:
    """Create a new student."""
    # Validate email if provided
    if student_data.email and not validate_email(student_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    state = _get_students_state()

    # Check for duplicate name
    existing = state.get_student_by_name(student_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with name '{student_data.name}' already exists",
        )

    # Create student
    student = state.add_student(
        name=student_data.name,
        surname=student_data.surname,
        email=student_data.email,
        tutor_persona_id=student_data.tutor_persona_id,
    )

    _save_students_state(state)

    return StudentResponse(
        student_id=student.student_id,
        name=student.name,
        surname=student.surname,
        email=student.email,
        tutor_persona_id=student.tutor_persona_id,
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(student_id: str) -> None:
    """Delete a student by ID."""
    state = _get_students_state()

    if not state.remove_student(student_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' not found",
        )

    _save_students_state(state)
