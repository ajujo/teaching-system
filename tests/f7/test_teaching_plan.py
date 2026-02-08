"""Tests for Teaching Plan generation and explanation (F7.3)."""

import pytest
from unittest.mock import MagicMock, patch

from teaching.core.tutor import (
    TeachingPoint,
    TeachingPlan,
    generate_teaching_plan,
    explain_point,
    check_comprehension,
    reexplain_with_analogy,
    _extract_objective_from_summary,
)


# =============================================================================
# Sample Notes for Testing
# =============================================================================

SAMPLE_NOTES = """# Apuntes — Test Book — Unidad 1

## Resumen
- **Tokenización**: Proceso que divide textos en tokens para optimizar el vocabulario.
- **Modelos lingüísticos**: Dos tipos principales: enmascarados y autorregresivos.
- **Autosupervisión**: Técnica que elimina la necesidad de datos etiquetados.

---

## Conceptos clave
| Concepto | Definición |
|----------|------------|
| Tokenización | División del texto en unidades significativas. |
| Modelo enmascarado | Predice tokens faltantes. |

---

## Explicación paso a paso
### 1. Tokenización y vocabulario
- **Tokenización**: Los modelos dividen el texto en tokens.
- **Vocabulario**: El tamaño varía entre modelos.

### 2. Tipos de modelos lingüísticos
- **Enmascarados**: Procesan contextos bidireccionales.
- **Autorregresivos**: Generan texto secuencialmente.

### 3. Autosupervisión y entrenamiento
- **Autosupervisión**: Los modelos aprenden sin datos etiquetados.
- Uso de grandes corpora no anotados.

---

## Mini-ejemplo
Ejemplo de tokenización: "Hola mundo" → ["Hola", "mundo"]

---

## Preguntas de repaso
1. ¿Cuál es la diferencia entre modelos enmascarados y autorregresivos?
2. ¿Cómo reduce la tokenización la complejidad?
"""

SAMPLE_NOTES_NO_SUBSECTIONS = """# Apuntes — Test Book — Unidad 2

## Resumen
- Concepto básico de prueba.

## Explicación paso a paso
Este es contenido sin subsecciones numeradas.
Solo texto plano explicativo.
"""


# =============================================================================
# Test: generate_teaching_plan
# =============================================================================


class TestGenerateTeachingPlan:
    """Tests for generate_teaching_plan function."""

    def test_parses_subsections_from_notes(self):
        """Extrae ### 1., ### 2. de '## Explicación paso a paso'."""
        plan = generate_teaching_plan(SAMPLE_NOTES, "test-unit-01")

        assert isinstance(plan, TeachingPlan)
        assert plan.unit_id == "test-unit-01"
        assert len(plan.points) >= 1

    def test_generates_correct_number_of_points(self):
        """Plan tiene los puntos correctos de las subsecciones."""
        plan = generate_teaching_plan(SAMPLE_NOTES, "test-unit-01")

        # Las notas de ejemplo tienen 3 subsecciones
        assert len(plan.points) == 3

    def test_points_have_correct_structure(self):
        """Cada punto tiene number, title y content."""
        plan = generate_teaching_plan(SAMPLE_NOTES, "test-unit-01")

        for point in plan.points:
            assert isinstance(point, TeachingPoint)
            assert isinstance(point.number, int)
            assert isinstance(point.title, str)
            assert isinstance(point.content, str)
            assert point.number > 0
            assert len(point.title) > 0

    def test_point_titles_extracted_correctly(self):
        """Los títulos de los puntos se extraen correctamente."""
        plan = generate_teaching_plan(SAMPLE_NOTES, "test-unit-01")

        titles = [p.title for p in plan.points]
        assert "Tokenización y vocabulario" in titles
        assert "Tipos de modelos lingüísticos" in titles

    def test_fallback_when_no_subsections(self):
        """Crea punto genérico si no hay subsecciones parseables."""
        plan = generate_teaching_plan(SAMPLE_NOTES_NO_SUBSECTIONS, "test-unit-02")

        # Debe crear al menos un punto
        assert len(plan.points) >= 1
        # El punto debe tener contenido
        assert len(plan.points[0].content) > 0

    def test_objective_derived_from_summary(self):
        """Objetivo viene del Resumen de las notas."""
        plan = generate_teaching_plan(SAMPLE_NOTES, "test-unit-01")

        assert plan.objective
        assert "Tokenización" in plan.objective or "entenderás" in plan.objective


class TestExtractObjectiveFromSummary:
    """Tests for _extract_objective_from_summary helper."""

    def test_extracts_from_summary_section(self):
        """Extrae objetivo de la sección Resumen."""
        objective = _extract_objective_from_summary(SAMPLE_NOTES)

        assert objective
        assert len(objective) > 10

    def test_truncates_long_objectives(self):
        """Trunca objetivos muy largos."""
        long_notes = """## Resumen
- Este es un punto muy largo que contiene mucha información y debería ser truncado
porque excede el límite de caracteres permitido para un objetivo de aprendizaje."""

        objective = _extract_objective_from_summary(long_notes)

        # Debe estar truncado a ~150 chars
        assert len(objective) <= 200

    def test_default_when_no_summary(self):
        """Retorna objetivo por defecto si no hay Resumen."""
        notes_no_summary = "# Solo un título\nContenido sin resumen"
        objective = _extract_objective_from_summary(notes_no_summary)

        assert objective
        assert "conceptos" in objective.lower() or "explorar" in objective.lower()


# =============================================================================
# Test: explain_point
# =============================================================================


class TestExplainPoint:
    """Tests for explain_point function."""

    def test_function_exists(self):
        """La función explain_point existe."""
        assert callable(explain_point)

    def test_returns_string(self):
        """explain_point retorna un string."""
        point = TeachingPoint(
            number=1,
            title="Test Point",
            content="Test content about a concept.",
        )

        with patch("teaching.core.tutor.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.simple_chat.return_value = "Explicación del concepto..."
            mock_client_class.return_value = mock_client

            result = explain_point(
                point=point,
                notes_context="Context notes",
                provider="lmstudio",
                model="test",
            )

        assert isinstance(result, str)

    def test_uses_conversational_prompt(self):
        """El prompt del sistema indica tono conversacional."""
        from teaching.core.tutor import SYSTEM_PROMPT_EXPLAIN_POINT

        assert "conversacional" in SYSTEM_PROMPT_EXPLAIN_POINT.lower()
        assert "párrafo" in SYSTEM_PROMPT_EXPLAIN_POINT.lower()


# =============================================================================
# Test: check_comprehension
# =============================================================================


class TestCheckComprehension:
    """Tests for check_comprehension function."""

    def test_function_exists(self):
        """La función check_comprehension existe."""
        assert callable(check_comprehension)

    def test_returns_tuple(self):
        """check_comprehension retorna tupla (bool, str)."""
        with patch("teaching.core.tutor.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.simple_chat.return_value = '{"understood": true, "confidence": 0.9, "feedback": "Bien!", "needs_elaboration": false}'
            mock_client_class.return_value = mock_client

            result = check_comprehension(
                check_question="¿Qué es X?",
                student_response="X es...",
                concept_context="Context",
                provider="lmstudio",
                model="test",
            )

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)
        assert isinstance(result[2], bool)

    def test_parses_json_response(self):
        """Parsea correctamente respuesta JSON del LLM."""
        with patch("teaching.core.tutor.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.simple_chat.return_value = '{"understood": true, "confidence": 0.85, "feedback": "Correcto!", "needs_elaboration": false}'
            mock_client_class.return_value = mock_client

            understood, feedback, needs_elaboration = check_comprehension(
                check_question="¿Qué es X?",
                student_response="X es una cosa",
                concept_context="Context",
                provider="lmstudio",
                model="test",
            )

        assert understood is True
        assert feedback == "Correcto!"
        assert needs_elaboration is False

    def test_handles_invalid_json(self):
        """Maneja respuestas JSON inválidas sin crashear."""
        with patch("teaching.core.tutor.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.simple_chat.return_value = "Invalid response without JSON"
            mock_client_class.return_value = mock_client

            understood, feedback, needs_elaboration = check_comprehension(
                check_question="¿Qué es X?",
                student_response="Respuesta",
                concept_context="Context",
                provider="lmstudio",
                model="test",
            )

        # Debe retornar valores por defecto sin crashear
        assert isinstance(understood, bool)
        assert isinstance(feedback, str)
        assert isinstance(needs_elaboration, bool)


# =============================================================================
# Test: reexplain_with_analogy
# =============================================================================


class TestReexplainWithAnalogy:
    """Tests for reexplain_with_analogy function."""

    def test_function_exists(self):
        """La función reexplain_with_analogy existe."""
        assert callable(reexplain_with_analogy)

    def test_returns_string(self):
        """reexplain_with_analogy retorna un string."""
        point = TeachingPoint(
            number=1,
            title="Test Point",
            content="Test content",
        )

        with patch("teaching.core.tutor.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.simple_chat.return_value = "Nueva explicación con analogía..."
            mock_client_class.return_value = mock_client

            result = reexplain_with_analogy(
                point=point,
                original_question="¿Qué es X?",
                provider="lmstudio",
                model="test",
            )

        assert isinstance(result, str)

    def test_uses_analogy_prompt(self):
        """El prompt del sistema indica usar analogías."""
        from teaching.core.tutor import SYSTEM_PROMPT_REEXPLAIN

        assert "analogía" in SYSTEM_PROMPT_REEXPLAIN.lower()
        assert "cotidiana" in SYSTEM_PROMPT_REEXPLAIN.lower()


# =============================================================================
# Test: TeachingPoint and TeachingPlan dataclasses
# =============================================================================


class TestDataclasses:
    """Tests for TeachingPoint and TeachingPlan dataclasses."""

    def test_teaching_point_creation(self):
        """TeachingPoint se puede crear correctamente."""
        point = TeachingPoint(
            number=1,
            title="Título del punto",
            content="Contenido explicativo",
        )

        assert point.number == 1
        assert point.title == "Título del punto"
        assert point.content == "Contenido explicativo"

    def test_teaching_plan_creation(self):
        """TeachingPlan se puede crear correctamente."""
        points = [
            TeachingPoint(number=1, title="Punto 1", content="Contenido 1"),
            TeachingPoint(number=2, title="Punto 2", content="Contenido 2"),
        ]

        plan = TeachingPlan(
            unit_id="test-unit-01",
            objective="Aprender conceptos básicos",
            points=points,
        )

        assert plan.unit_id == "test-unit-01"
        assert plan.objective == "Aprender conceptos básicos"
        assert len(plan.points) == 2
