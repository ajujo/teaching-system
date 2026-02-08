"""Tests for chapter exam generation (F6)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGenerateChapterExam:
    """Tests for generate_chapter_exam function."""

    def test_generate_exam_creates_file(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """generate_chapter_exam creates exam set file."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        book_id = "test-book"
        result = generate_chapter_exam(
            book_id=book_id,
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result.success
        assert result.exam_set_path is not None
        assert result.exam_set_path.exists()
        assert result.exam_set_path.suffix == ".json"

    def test_exam_set_id_is_deterministic(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """Exam set ID follows pattern {book_id}-ch{NN}-exam{XX}."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        book_id = "test-book"
        result = generate_chapter_exam(
            book_id=book_id,
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result.success
        assert result.metadata is not None
        assert result.metadata.exam_set_id == f"{book_id}-ch01-exam01"

        # Generate second exam
        result2 = generate_chapter_exam(
            book_id=book_id,
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result2.success
        assert result2.metadata.exam_set_id == f"{book_id}-ch01-exam02"

    def test_exam_includes_source_tracking(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """Each question has source field with unit_id and pages."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        book_id = "test-book"
        result = generate_chapter_exam(
            book_id=book_id,
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result.success
        assert len(result.questions) > 0

        for q in result.questions:
            assert q.source is not None
            assert q.source.unit_id is not None
            assert len(q.source.pages) > 0

    def test_exam_schema_is_chapter_exam_set_v1(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """Exam set file has correct schema."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        book_id = "test-book"
        result = generate_chapter_exam(
            book_id=book_id,
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result.success
        assert result.exam_set_path is not None

        with open(result.exam_set_path) as f:
            exam_data = json.load(f)

        assert exam_data["$schema"] == "chapter_exam_set_v1"
        assert "exam_set_id" in exam_data
        assert "chapter_id" in exam_data
        assert "units_included" in exam_data
        assert "questions" in exam_data

    def test_exam_includes_all_chapter_units(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """Exam includes all units from the chapter."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        book_id = "test-book"
        result = generate_chapter_exam(
            book_id=book_id,
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result.success
        assert result.metadata is not None
        assert len(result.metadata.units_included) == 3
        assert f"{book_id}-ch01-u01" in result.metadata.units_included
        assert f"{book_id}-ch01-u02" in result.metadata.units_included
        assert f"{book_id}-ch01-u03" in result.metadata.units_included

    def test_exam_passing_threshold_default_60(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """Exam passing threshold defaults to 0.6 (60%)."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        book_id = "test-book"
        result = generate_chapter_exam(
            book_id=book_id,
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result.success
        assert result.metadata is not None
        assert result.metadata.passing_threshold == 0.6


class TestChapterResolution:
    """Tests for chapter ID resolution."""

    def test_accepts_ch01_format(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """Accepts chapter='ch01' format."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result.success

    def test_accepts_numeric_format(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """Accepts chapter='1' numeric format."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="1",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result.success

    def test_invalid_chapter_returns_error(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """Invalid chapter returns error."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch99",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert not result.success
        # Message should indicate no units found for the chapter
        assert "encontr" in result.message.lower() or "no units" in result.message.lower()


class TestQuestionDistribution:
    """Tests for question type distribution."""

    def test_default_distribution_6_3_3(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams, mock_exam_response
    ):
        """Default 12 questions: 6 MCQ + 3 TF + 3 SA."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert result.success
        # The mock returns 12 questions with 6 MCQ, 3 TF, 3 SA
        mcq_count = sum(1 for q in result.questions if q.type == "multiple_choice")
        tf_count = sum(1 for q in result.questions if q.type == "true_false")
        sa_count = sum(1 for q in result.questions if q.type == "short_answer")

        assert mcq_count == 6
        assert tf_count == 3
        assert sa_count == 3


class TestExamGenerationErrors:
    """Tests for error handling."""

    def test_book_not_found_returns_error(
        self, sample_book_multi_unit_chapter, mock_llm_client_for_exams
    ):
        """Non-existent book returns error."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        result = generate_chapter_exam(
            book_id="nonexistent-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_llm_client_for_exams,
        )

        assert not result.success
        assert "no encontr" in result.message.lower() or "not found" in result.message.lower()

    def test_llm_unavailable_returns_error(
        self, sample_book_multi_unit_chapter
    ):
        """LLM unavailable returns error."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        mock_client = MagicMock()
        mock_client.is_available.return_value = False
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        assert not result.success
        assert "conectar" in result.message.lower() or "llm" in result.message.lower()

    def test_json_timeout_text_fallback_returns_str_no_crash(
        self, sample_book_multi_unit_chapter, mock_exam_response
    ):
        """When JSON times out and text fallback returns str, should not crash."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        # First call (simple_json) raises timeout
        mock_client.simple_json.side_effect = LLMError("Request timed out.")
        # Second call (simple_chat) returns valid JSON as string
        mock_client.simple_chat.return_value = json.dumps(mock_exam_response)

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        assert result.success
        assert len(result.questions) > 0

    def test_json_timeout_text_fallback_json_in_markdown_parses(
        self, sample_book_multi_unit_chapter, mock_exam_response
    ):
        """Text fallback with ```json...``` block should parse correctly."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        mock_client.simple_json.side_effect = LLMError("Request timed out.")
        # Return JSON wrapped in markdown
        mock_client.simple_chat.return_value = f"Aqui tienes el examen:\n```json\n{json.dumps(mock_exam_response)}\n```"

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        assert result.success
        assert len(result.questions) > 0

    def test_json_timeout_text_fallback_unparseable_returns_error(
        self, sample_book_multi_unit_chapter
    ):
        """When text fallback is not parseable, should return error not crash."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        mock_client.simple_json.side_effect = LLMError("Request timed out.")
        # Return completely unparseable text
        mock_client.simple_chat.return_value = "Lo siento, no puedo generar el examen en este momento."

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        assert not result.success
        assert "JSON" in result.message or "extraer" in result.message
        # Should NOT raise AttributeError

    def test_json_timeout_fallback_json_loads_string_no_crash(
        self, sample_book_multi_unit_chapter
    ):
        """When fallback parses to a JSON string (not dict), should not crash."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        mock_client.simple_json.side_effect = LLMError("Request timed out.")
        # Return a valid JSON string that parses to a string, not dict
        mock_client.simple_chat.return_value = '"Lo siento, no puedo generar el examen"'

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        assert not result.success
        # Should NOT raise AttributeError

    def test_json_timeout_fallback_json_loads_list_no_crash(
        self, sample_book_multi_unit_chapter
    ):
        """When fallback parses to a JSON list (not dict), should not crash."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        mock_client.simple_json.side_effect = LLMError("Request timed out.")
        # Return a valid JSON that parses to a list, not dict
        mock_client.simple_chat.return_value = '["pregunta1", "pregunta2"]'

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        assert not result.success
        # Should NOT raise AttributeError

    def test_simple_json_returns_non_dict_handled(
        self, sample_book_multi_unit_chapter
    ):
        """When simple_json returns non-dict, should handle gracefully."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        # simple_json returns a list instead of dict
        mock_client.simple_json.return_value = ["not", "a", "dict"]
        # Fallback also returns unparseable text
        mock_client.simple_chat.return_value = "Cannot generate exam"

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        # Should handle gracefully - either fallback works or returns error
        # But should NOT raise AttributeError
        assert not result.success

    def test_questions_array_contains_strings_no_crash(
        self, sample_book_multi_unit_chapter
    ):
        """When questions array contains strings instead of dicts, should not crash.

        This is the root cause of the 'str' object has no attribute 'get' bug.
        The LLM might return {"questions": ["Q1?", "Q2?"]} instead of proper dicts.
        """
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        mock_client.simple_json.side_effect = LLMError("Request timed out.")
        # Return JSON where questions is array of strings (not dicts)
        mock_client.simple_chat.return_value = '{"questions": ["Question 1?", "Question 2?"]}'

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        # Should NOT crash with AttributeError
        # Returns success=False because no valid questions were generated
        assert not result.success
        assert "No se generaron preguntas" in result.message

    def test_questions_not_a_list_no_crash(
        self, sample_book_multi_unit_chapter
    ):
        """When questions is not a list (e.g., string), should not crash."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        mock_client.simple_json.side_effect = LLMError("Request timed out.")
        # Return JSON where questions is a string (not list)
        mock_client.simple_chat.return_value = '{"questions": "No pude generar preguntas"}'

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        # Should NOT crash with any error
        assert not result.success

    def test_question_source_is_string_no_crash(
        self, sample_book_multi_unit_chapter
    ):
        """When question source is a string instead of dict, should not crash.

        This is the REAL root cause of the 'str' object has no attribute 'get' bug.
        The LLM returns "source": "Chapter 1" instead of "source": {"unit_id": ...}
        """
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        # LLM returns question with source as string instead of dict
        bad_response = {
            "questions": [{
                "type": "multiple_choice",
                "question": "What is LLM?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": 0,
                "explanation": "LLM is Large Language Model",
                "source": "Chapter 1"  # <-- STRING instead of dict!
            }]
        }

        mock_client.simple_json.side_effect = LLMError("Request timed out.")
        mock_client.simple_chat.return_value = json.dumps(bad_response)

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        # Should NOT crash with AttributeError
        # Should succeed with 1 question (source gets default values)
        assert result.success
        assert len(result.questions) == 1


class TestExamSetValidation:
    """Tests for exam set quality validation."""

    def test_text_fallback_all_empty_explanations_marked_invalid(
        self, sample_book_multi_unit_chapter
    ):
        """Exam set with text_fallback mode and all empty explanations should be invalid."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        # LLM timeout forces text_fallback
        mock_client.simple_json.side_effect = LLMError("Request timed out.")

        # Fallback returns garbage data: all MCQ with correct_answer=0, empty explanations
        garbage_response = {
            "questions": [
                {
                    "type": "multiple_choice",
                    "question": f"Q{i}?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 0,
                    "explanation": "",
                    "source": {"unit_id": "test-book:ch:1:u:1", "pages": [1]},
                }
                for i in range(6)
            ]
        }
        mock_client.simple_chat.return_value = json.dumps(garbage_response)

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=6,
            client=mock_client,
        )

        # Should fail validation (empty explanations + suspicious distribution in text_fallback)
        assert not result.success
        assert "inválido" in result.message.lower() or "invalid" in result.message.lower()

    def test_text_fallback_suspicious_mcq_distribution_marked_invalid(
        self, sample_book_multi_unit_chapter
    ):
        """Exam set with 80%+ MCQs having same correct_answer in fallback should be invalid."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam
        from teaching.llm.client import LLMError

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        mock_client.simple_json.side_effect = LLMError("Request timed out.")

        # All 5 MCQs have correct_answer=0 (100% > 80% threshold)
        suspicious_response = {
            "questions": [
                {
                    "type": "multiple_choice",
                    "question": f"Q{i}?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 0,  # All same!
                    "explanation": f"Explanation {i}",
                    "source": {"unit_id": "test-book:ch:1:u:1", "pages": [1]},
                }
                for i in range(5)
            ]
        }
        mock_client.simple_chat.return_value = json.dumps(suspicious_response)

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=5,
            client=mock_client,
        )

        # Should fail validation (suspicious distribution in text_fallback)
        assert not result.success
        assert "sospechosa" in result.message.lower() or "distribución" in result.message.lower()

    def test_json_mode_with_warnings_still_valid(
        self, sample_book_multi_unit_chapter, mock_exam_response
    ):
        """Exam set in JSON mode with warnings should still be valid."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"

        # JSON mode succeeds but with all MCQs having same answer
        # (warning but not invalid since not text_fallback)
        suspicious_response = {
            "questions": [
                {
                    "type": "multiple_choice",
                    "question": f"Q{i}?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 0,  # All same
                    "explanation": f"Explanation {i}",
                    "source": {"unit_id": "test-book:ch:1:u:1", "pages": [1]},
                }
                for i in range(5)
            ]
        }
        mock_client.simple_json.return_value = suspicious_response

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=5,
            client=mock_client,
        )

        # Should succeed but have warnings
        assert result.success
        assert len(result.warnings) > 0
        assert any("sospechosa" in w.lower() or "distribución" in w.lower() for w in result.warnings)

    def test_metadata_contains_validation_fields(
        self, sample_book_multi_unit_chapter, mock_exam_response
    ):
        """Exam metadata should contain valid and validation_warnings fields."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"
        mock_client.simple_json.return_value = mock_exam_response

        result = generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        assert result.success
        assert result.metadata is not None
        assert hasattr(result.metadata, "valid")
        assert hasattr(result.metadata, "validation_warnings")


class TestExamGraderValidation:
    """Tests for exam grader handling of invalid/fallback exams."""

    def test_grader_skips_autograde_for_invalid_exam(
        self, sample_book_multi_unit_chapter
    ):
        """Grader should skip auto-grading and mark for review when exam is invalid."""
        from teaching.core.exam_grader import grade_exam_attempt

        # Create exam set marked as invalid
        exams_dir = sample_book_multi_unit_chapter / "books" / "test-book" / "artifacts" / "exams"
        exams_dir.mkdir(parents=True, exist_ok=True)

        exam_set = {
            "$schema": "chapter_exam_set_v1",
            "exam_set_id": "test-book-ch01-exam01",
            "book_id": "test-book",
            "chapter_id": "ch01",
            "valid": False,
            "mode": "text_fallback",
            "passing_threshold": 0.6,
            "questions": [
                {
                    "question_id": "q1",
                    "type": "multiple_choice",
                    "question": "What is LLM?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 0,
                    "explanation": "",
                    "points": 1,
                    "source": {"unit_id": "test-book-ch01-u01", "pages": [1]},
                },
                {
                    "question_id": "q2",
                    "type": "true_false",
                    "question": "Is Python interpreted?",
                    "correct_answer": True,
                    "explanation": "",
                    "points": 1,
                    "source": {"unit_id": "test-book-ch01-u01", "pages": [1]},
                },
            ],
        }

        with open(exams_dir / "test-book-ch01-exam01.json", "w") as f:
            json.dump(exam_set, f)

        # Create exam attempt with correct ID format: {exam_set_id}-a{NN}
        attempts_dir = sample_book_multi_unit_chapter / "books" / "test-book" / "artifacts" / "exam_attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)

        attempt = {
            "$schema": "exam_attempt_v1",
            "exam_attempt_id": "test-book-ch01-exam01-a01",
            "exam_set_id": "test-book-ch01-exam01",
            "book_id": "test-book",
            "chapter_id": "test-book:ch:1",
            "created_at": "2024-01-01T00:00:00Z",
            "status": "submitted",
            "answers": [
                {"question_id": "q1", "response": 0},
                {"question_id": "q2", "response": True},
            ],
        }

        with open(attempts_dir / "test-book-ch01-exam01-a01.json", "w") as f:
            json.dump(attempt, f)

        # Grade the attempt
        result = grade_exam_attempt(
            exam_attempt_id="test-book-ch01-exam01-a01",
            data_dir=sample_book_multi_unit_chapter,
        )

        assert result.success
        assert result.report is not None

        # All MCQ/TF should have grading_path="skipped" and is_correct=None
        for grade_result in result.report.results:
            assert grade_result.grading_path == "skipped"
            assert grade_result.is_correct is None
            assert "revisión manual" in grade_result.feedback.lower()

    def test_grader_skips_autograde_for_text_fallback_mode(
        self, sample_book_multi_unit_chapter
    ):
        """Grader should skip auto-grading when mode=text_fallback even if valid=True."""
        from teaching.core.exam_grader import grade_exam_attempt

        exams_dir = sample_book_multi_unit_chapter / "books" / "test-book" / "artifacts" / "exams"
        exams_dir.mkdir(parents=True, exist_ok=True)

        # valid=True but mode=text_fallback -> still skip
        exam_set = {
            "$schema": "chapter_exam_set_v1",
            "exam_set_id": "test-book-ch01-exam02",
            "book_id": "test-book",
            "chapter_id": "ch01",
            "valid": True,
            "mode": "text_fallback",
            "passing_threshold": 0.6,
            "questions": [
                {
                    "question_id": "q1",
                    "type": "multiple_choice",
                    "question": "Test question?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 2,
                    "explanation": "Test",
                    "points": 1,
                    "source": {"unit_id": "test-book-ch01-u01", "pages": [1]},
                },
            ],
        }

        with open(exams_dir / "test-book-ch01-exam02.json", "w") as f:
            json.dump(exam_set, f)

        attempts_dir = sample_book_multi_unit_chapter / "books" / "test-book" / "artifacts" / "exam_attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)

        attempt = {
            "$schema": "exam_attempt_v1",
            "exam_attempt_id": "test-book-ch01-exam02-a01",
            "exam_set_id": "test-book-ch01-exam02",
            "book_id": "test-book",
            "chapter_id": "test-book:ch:1",
            "created_at": "2024-01-01T00:00:00Z",
            "status": "submitted",
            "answers": [{"question_id": "q1", "response": 2}],
        }

        with open(attempts_dir / "test-book-ch01-exam02-a01.json", "w") as f:
            json.dump(attempt, f)

        result = grade_exam_attempt(
            exam_attempt_id="test-book-ch01-exam02-a01",
            data_dir=sample_book_multi_unit_chapter,
        )

        assert result.success
        assert result.report.results[0].grading_path == "skipped"
        assert result.report.results[0].is_correct is None

    def test_grader_autogrades_valid_json_mode_exam(
        self, sample_book_multi_unit_chapter
    ):
        """Grader should auto-grade normally when valid=True and mode=json."""
        from teaching.core.exam_grader import grade_exam_attempt

        exams_dir = sample_book_multi_unit_chapter / "books" / "test-book" / "artifacts" / "exams"
        exams_dir.mkdir(parents=True, exist_ok=True)

        exam_set = {
            "$schema": "chapter_exam_set_v1",
            "exam_set_id": "test-book-ch01-exam03",
            "book_id": "test-book",
            "chapter_id": "ch01",
            "valid": True,
            "mode": "json",
            "passing_threshold": 0.6,
            "questions": [
                {
                    "question_id": "q1",
                    "type": "multiple_choice",
                    "question": "Test question?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 2,
                    "explanation": "Correct explanation",
                    "points": 1,
                    "source": {"unit_id": "test-book-ch01-u01", "pages": [1]},
                },
            ],
        }

        with open(exams_dir / "test-book-ch01-exam03.json", "w") as f:
            json.dump(exam_set, f)

        attempts_dir = sample_book_multi_unit_chapter / "books" / "test-book" / "artifacts" / "exam_attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)

        attempt = {
            "$schema": "exam_attempt_v1",
            "exam_attempt_id": "test-book-ch01-exam03-a01",
            "exam_set_id": "test-book-ch01-exam03",
            "book_id": "test-book",
            "chapter_id": "test-book:ch:1",
            "created_at": "2024-01-01T00:00:00Z",
            "status": "submitted",
            "answers": [{"question_id": "q1", "response": 2}],  # Correct answer
        }

        with open(attempts_dir / "test-book-ch01-exam03-a01.json", "w") as f:
            json.dump(attempt, f)

        result = grade_exam_attempt(
            exam_attempt_id="test-book-ch01-exam03-a01",
            data_dir=sample_book_multi_unit_chapter,
        )

        assert result.success
        # Should auto-grade normally
        assert result.report.results[0].grading_path == "auto"
        assert result.report.results[0].is_correct is True
        assert result.report.results[0].score == 1.0


class TestSafetyNoRealData:
    """Tests ensuring real data is not touched."""

    def test_does_not_touch_real_data_directory(self, sample_book_multi_unit_chapter):
        """generate_chapter_exam does not modify ./data directory."""
        from teaching.core.chapter_exam_generator import generate_chapter_exam

        real_data_dir = Path("data")
        real_data_existed = real_data_dir.exists()

        initial_count = 0
        if real_data_existed:
            initial_files = list(real_data_dir.rglob("*"))
            initial_count = len(initial_files)

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.config = MagicMock()
        mock_client.config.provider = "test"
        mock_client.config.model = "test"
        mock_client.simple_json.return_value = {"questions": []}

        # This should use tmp_path, not real data
        generate_chapter_exam(
            book_id="test-book",
            chapter="ch01",
            data_dir=sample_book_multi_unit_chapter,
            n=12,
            client=mock_client,
        )

        if real_data_existed:
            current_files = list(real_data_dir.rglob("*"))
            assert len(current_files) == initial_count, "Real data directory was modified"
