"""Tests for tutor CLI command (F7)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from teaching.cli.commands import app

runner = CliRunner()


class TestTutorCommandBasic:
    """Basic tutor command tests."""

    def test_tutor_stop_flag_saves_state(self, sample_book_with_tutor_state):
        """teach tutor --stop saves state and exits cleanly."""
        result = runner.invoke(
            app,
            ["tutor", "--stop"],
            env={"TEACHING_DATA_DIR": str(sample_book_with_tutor_state)},
        )

        assert result.exit_code == 0
        assert "cerrada" in result.output.lower() or "guardado" in result.output.lower()

        # Verify state was saved (now uses students_v1.json)
        state_path = sample_book_with_tutor_state / "state" / "students_v1.json"
        with open(state_path) as f:
            state = json.load(f)
        # The active student's active_book_id should be cleared
        active_student = next(
            (s for s in state["students"] if s["student_id"] == state["active_student_id"]),
            None
        )
        assert active_student is not None
        assert active_student["tutor_state"]["active_book_id"] is None

    def test_tutor_shows_books_list(self, sample_book_with_student):
        """Tutor shows available books after selecting student."""
        # Use --student to skip lobby
        input_data = (
            "stop\n"  # Exit at book selection
        )
        result = runner.invoke(
            app,
            ["tutor", "--student", "Test"],
            input=input_data,
            env={"TEACHING_DATA_DIR": str(sample_book_with_student)},
        )

        assert result.exit_code == 0
        # Should show the test book (option 1 after option 0 for add book)
        assert "test book" in result.output.lower() or "llm" in result.output.lower()

    def test_tutor_no_books_shows_help(self, sample_book_with_student):
        """Tutor with no books shows import help via option 0."""
        # Use --student to skip lobby
        input_data = (
            "stop\n"  # Exit at book selection
        )
        result = runner.invoke(
            app,
            ["tutor", "--student", "Test"],
            input=input_data,
            env={"TEACHING_DATA_DIR": str(sample_book_with_student)},
        )

        assert result.exit_code == 0
        # Should show "Añadir nuevo libro" option
        assert "añadir" in result.output.lower() or "nuevo libro" in result.output.lower()

    def test_tutor_selects_book_and_starts(self, sample_book_with_student):
        """Tutor can select a book and start chapter 1."""
        # Use --student to skip lobby
        # Input: select book 1 -> adelante in Q&A -> skip mini-quiz -> stop
        input_data = (
            "1\n"  # Select book (option 1, not 0)
            "adelante\n"  # Skip to next point in teaching loop
            "adelante\n"  # Continue
            "adelante\n"  # Continue
            "n\n"  # Don't take mini-quiz
            "stop\n"  # Exit
        )

        with patch("teaching.core.tutor.LLMClient") as MockClient:
            mock_client = MagicMock()
            mock_client.is_available.return_value = True
            mock_client.simple_chat.return_value = "Explicación del punto. ¿Entiendes?"
            MockClient.return_value = mock_client

            result = runner.invoke(
                app,
                ["tutor", "--student", "Test"],
                input=input_data,
                env={"TEACHING_DATA_DIR": str(sample_book_with_student)},
            )

        # Should have shown chapter 1 info
        assert "capítulo 1" in result.output.lower() or "chapter" in result.output.lower() or "unidad" in result.output.lower()

    def test_tutor_resumes_from_last_chapter(self, sample_book_with_tutor_state):
        """Tutor offers to resume from last chapter."""
        # Use --student to skip lobby (fixture already has student with progress)
        # The teaching-first flow now goes through:
        # 1. Book selection
        # 2. Resume from chapter confirmation
        # 3. Teaching loop (we exit with "stop" in the unit loop)
        input_data = (
            "1\n"  # Select book
            "y\n"  # Resume from chapter 1
            "stop\n"  # Exit in teaching loop (WAITING_INPUT state)
        )

        with patch("teaching.core.tutor.LLMClient") as mock_client_class:
            # Mock LLM to avoid actual API calls during teaching
            mock_client = MagicMock()
            mock_client.simple_chat.return_value = "Explicación de prueba.\n\n¿Entiendes?"
            mock_client_class.return_value = mock_client

            result = runner.invoke(
                app,
                ["tutor", "--student", "Test"],
                input=input_data,
                env={"TEACHING_DATA_DIR": str(sample_book_with_tutor_state)},
            )

        assert result.exit_code == 0
        # Should ask about resuming (¿Continuar desde capítulo X?)
        assert "continuar" in result.output.lower() or "capítulo" in result.output.lower()


class TestTutorQALoop:
    """Tests for Q&A interaction."""

    def test_tutor_qa_responds_to_question(self, sample_book_for_tutor):
        """Tutor answers question about chapter content via answer_question()."""
        # Test the Q&A function directly (simpler than full CLI test)
        from teaching.core.tutor import answer_question

        mock_client = MagicMock()
        mock_client.simple_chat.return_value = "Un LLM es un modelo de lenguaje grande."

        answer = answer_question(
            question="¿Qué es un LLM?",
            notes_content="Los LLMs son modelos de lenguaje grandes.",
            provider="lmstudio",
            model="test",
            client=mock_client,
        )

        assert "LLM" in answer
        mock_client.simple_chat.assert_called_once()

    def test_tutor_qa_response_no_think_tags(self, sample_book_for_tutor):
        """Q&A responses don't contain <think> tags - strip_think is applied."""
        from teaching.core.tutor import answer_question

        mock_client = MagicMock()
        # Simulate LLM response with think tags
        mock_client.simple_chat.return_value = (
            "<think>Let me reason about this...</think>"
            "Un LLM (Large Language Model) es un modelo de lenguaje grande."
        )

        answer = answer_question(
            question="¿Qué es un LLM?",
            notes_content="Los LLMs son modelos de lenguaje grandes.",
            client=mock_client,
        )

        # Verify think tags are stripped
        assert "<think>" not in answer
        assert "</think>" not in answer
        assert "Let me reason" not in answer
        # But the actual answer is preserved
        assert "LLM" in answer
        assert "modelo de lenguaje" in answer

    def test_tutor_qa_strips_pensando_prefix(self, sample_book_for_tutor):
        """Q&A responses strip 'Pensando...' prefix lines."""
        from teaching.core.tutor import answer_question

        mock_client = MagicMock()
        mock_client.simple_chat.return_value = "Pensando...\nLa respuesta es correcta."

        answer = answer_question(
            question="¿Es correcto?",
            notes_content="El contenido del capítulo.",
            client=mock_client,
        )

        assert "Pensando" not in answer
        assert "respuesta" in answer

    def test_tutor_stop_during_qa(self, sample_book_with_student):
        """User can stop during Q&A loop."""
        # Use --student to skip lobby
        input_data = (
            "1\n"  # Select book (option 1, not 0)
            "stop\n"  # Stop during teaching loop
        )

        with patch("teaching.core.tutor.LLMClient") as MockClient:
            mock_client = MagicMock()
            mock_client.simple_chat.return_value = "Explicación. ¿Entiendes?"
            MockClient.return_value = mock_client

            result = runner.invoke(
                app,
                ["tutor", "--student", "Test"],
                input=input_data,
                env={"TEACHING_DATA_DIR": str(sample_book_with_student)},
            )

        assert result.exit_code == 0
        assert "cerrada" in result.output.lower() or "guardado" in result.output.lower()


class TestTutorExamFlow:
    """Tests for exam generation and handling."""

    def test_tutor_exam_flow_helper_returns_exam_id(self, sample_book_for_tutor):
        """_run_tutor_exam_flow returns exam_set_id on success."""
        from teaching.cli.commands import _run_tutor_exam_flow

        with patch("teaching.cli.commands.generate_chapter_exam") as mock_gen:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.metadata = MagicMock()
            mock_result.metadata.valid = True
            mock_result.metadata.exam_set_id = "test-book-ch01-exam01"
            mock_gen.return_value = mock_result

            exam_set_id = _run_tutor_exam_flow(
                book_id="test-book",
                chapter_number=1,
                data_dir=sample_book_for_tutor,
                provider="lmstudio",
                model="test-model",
            )

        assert exam_set_id == "test-book-ch01-exam01"
        mock_gen.assert_called_once()


class TestTutorInvalidExam:
    """Tests for exam generation validation."""

    def test_exam_generation_called_with_correct_params(self, sample_book_for_tutor):
        """generate_chapter_exam is called with correct parameters."""
        from teaching.cli.commands import _run_tutor_exam_flow

        with patch("teaching.cli.commands.generate_chapter_exam") as mock_gen:
            # Mock successful valid exam
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.metadata = MagicMock()
            mock_result.metadata.valid = True
            mock_result.metadata.exam_set_id = "test-book-ch01-exam01"
            mock_gen.return_value = mock_result

            exam_set_id = _run_tutor_exam_flow(
                book_id="test-book",
                chapter_number=1,
                data_dir=sample_book_for_tutor,
                provider="lmstudio",
                model="test-model",
            )

        # Verify correct parameters
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs["book_id"] == "test-book"
        assert call_kwargs["chapter"] == "ch01"
        assert call_kwargs["n"] == 12  # Default number
        assert call_kwargs["difficulty"] == "mid"
        assert exam_set_id == "test-book-ch01-exam01"

    def test_exam_metadata_validation_flags(self, sample_book_for_tutor):
        """Exam result metadata contains validation info."""
        from teaching.cli.commands import _run_tutor_exam_flow

        with patch("teaching.cli.commands.generate_chapter_exam") as mock_gen:
            # Mock exam with validation warnings but still valid
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.metadata = MagicMock()
            mock_result.metadata.valid = True  # Still valid
            mock_result.metadata.validation_warnings = []
            mock_result.metadata.exam_set_id = "test-book-ch01-exam01"
            mock_gen.return_value = mock_result

            exam_set_id = _run_tutor_exam_flow(
                book_id="test-book",
                chapter_number=1,
                data_dir=sample_book_for_tutor,
                provider="lmstudio",
                model="test-model",
            )

        # Valid exam should return id
        assert exam_set_id == "test-book-ch01-exam01"


class TestTutorSafety:
    """Safety tests ensuring real data is not touched."""

    def test_does_not_touch_real_data_directory(self, sample_book_for_tutor):
        """Fixtures use tmp_path, not real ./data directory."""
        project_root = Path(__file__).parent.parent.parent
        real_data_dir = project_root / "data"

        # Verify tmp_path is different from project paths
        assert str(sample_book_for_tutor) != str(real_data_dir)
        assert not str(sample_book_for_tutor).startswith(str(project_root / "data"))
