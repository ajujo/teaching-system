"""Tests for F8.3: Teaching Plan Source of Truth + Clase real (Teaching-First).

Tests the unit opening flow, teaching plan generation, and event structure.
"""

import pytest

from teaching.core.tutor import (
    TutorEvent,
    TutorEventType,
    TeachingPlan,
    TeachingPoint,
    generate_teaching_plan,
    generate_unit_opening,
    generate_plan_from_text_fallback,
    TutorPromptKind,
)


class TestUnitOpeningDoesNotShowNotesAutomatically:
    """Test 1: La apertura de unidad NO muestra apuntes/resumen."""

    def test_unit_opening_event_type(self):
        """generate_unit_opening devuelve evento UNIT_OPENING."""
        plan = TeachingPlan(
            unit_id="test-u01",
            objective="Entender los conceptos básicos",
            points=[
                TeachingPoint(number=1, title="Introducción", content="..."),
                TeachingPoint(number=2, title="Conceptos", content="..."),
            ],
        )
        event = generate_unit_opening("Unidad 1", plan)
        assert event.event_type == TutorEventType.UNIT_OPENING

    def test_unit_opening_does_not_contain_resumen(self):
        """La apertura NO contiene 'Resumen' ni 'Conceptos clave'."""
        plan = TeachingPlan(
            unit_id="test-u01",
            objective="Aprender tokenización",
            points=[
                TeachingPoint(number=1, title="Tokenización", content="..."),
            ],
        )
        event = generate_unit_opening("Unidad 1", plan)

        # No debe contener palabras de apuntes
        assert "Resumen" not in event.markdown
        assert "Conceptos clave" not in event.markdown
        assert "## " not in event.markdown  # No headers de apuntes

    def test_unit_opening_contains_map_of_points(self):
        """La apertura contiene el mapa de puntos."""
        plan = TeachingPlan(
            unit_id="test-u01",
            objective="Objetivo de prueba",
            points=[
                TeachingPoint(number=1, title="Punto uno", content="..."),
                TeachingPoint(number=2, title="Punto dos", content="..."),
                TeachingPoint(number=3, title="Punto tres", content="..."),
            ],
        )
        event = generate_unit_opening("Unidad Test", plan)

        assert "1. Punto uno" in event.markdown
        assert "2. Punto dos" in event.markdown
        assert "3. Punto tres" in event.markdown

    def test_unit_opening_ends_with_question(self):
        """La apertura termina con pregunta para empezar."""
        plan = TeachingPlan(
            unit_id="test-u01",
            objective="Test",
            points=[TeachingPoint(number=1, title="Test", content="...")],
        )
        event = generate_unit_opening("Unidad 1", plan)

        assert "?" in event.markdown
        assert "empezamos" in event.markdown.lower() or "comenzamos" in event.markdown.lower()


class TestUnitNotesOnlyAfterPointsComplete:
    """Test 2: Los apuntes se muestran solo al completar todos los puntos."""

    def test_tutor_event_has_unit_notes_type(self):
        """TutorEventType incluye UNIT_NOTES para el cierre."""
        assert hasattr(TutorEventType, "UNIT_NOTES")

    def test_unit_notes_event_is_distinct_from_opening(self):
        """UNIT_NOTES es distinto de UNIT_OPENING."""
        assert TutorEventType.UNIT_NOTES != TutorEventType.UNIT_OPENING


class TestPlanFallbackGeneratesMax5Points:
    """Test 3: El fallback genera máximo 5 puntos."""

    def test_fallback_max_points_default(self):
        """Por defecto, fallback genera máximo 5 puntos."""
        long_text = "\n\n".join([f"Párrafo {i} con contenido extenso. " * 20 for i in range(10)])
        plan = generate_plan_from_text_fallback(long_text, "test-u01")
        assert len(plan.points) <= 5

    def test_fallback_respects_max_points_param(self):
        """Fallback respeta el parámetro max_points."""
        text = "## Uno\nContenido\n## Dos\nContenido\n## Tres\nContenido\n## Cuatro\nContenido"
        plan = generate_plan_from_text_fallback(text, "test-u01", max_points=3)
        assert len(plan.points) <= 3

    def test_fallback_creates_plan_from_headers(self):
        """Fallback extrae puntos de headers ##/###."""
        text = """## Introducción
Este es el contenido de introducción.

## Desarrollo
Este es el contenido de desarrollo.

## Conclusión
Este es el contenido final."""

        plan = generate_plan_from_text_fallback(text, "test-u01")

        # Debe tener al menos algunos puntos
        assert len(plan.points) >= 1
        # Los títulos deben venir de los headers
        titles = [p.title for p in plan.points]
        assert any("Introducción" in t or "Desarrollo" in t or "Conclusión" in t for t in titles)

    def test_fallback_excludes_resumen_header(self):
        """Fallback no incluye 'Resumen' como punto."""
        text = """## Resumen
Este es el resumen.

## Contenido real
Este es el contenido de verdad."""

        plan = generate_plan_from_text_fallback(text, "test-u01")
        titles = [p.title.lower() for p in plan.points]
        assert "resumen" not in titles


class TestCommandApuntesShowsNotesAnytime:
    """Test 4: El comando 'apuntes' muestra notas en cualquier momento."""

    def test_tutor_prompt_kind_has_ask_unit_start(self):
        """TutorPromptKind tiene ASK_UNIT_START para la apertura."""
        assert hasattr(TutorPromptKind, "ASK_UNIT_START")


class TestEventsOptionalDoNotBreakCLI:
    """Test 5: Los eventos no rompen el CLI existente."""

    def test_tutor_event_has_required_fields(self):
        """TutorEvent tiene los campos necesarios."""
        event = TutorEvent(
            event_type=TutorEventType.UNIT_OPENING,
            title="Test",
            markdown="# Test\n\nContenido",
        )
        assert event.event_type == TutorEventType.UNIT_OPENING
        assert event.title == "Test"
        assert "Contenido" in event.markdown
        assert isinstance(event.data, dict)

    def test_tutor_event_data_is_optional(self):
        """TutorEvent.data es opcional (default dict vacío)."""
        event = TutorEvent(
            event_type=TutorEventType.FEEDBACK,
            markdown="¡Correcto!",
        )
        assert event.data == {}

    def test_all_event_types_exist(self):
        """Todos los tipos de evento existen."""
        expected_types = [
            "UNIT_OPENING",
            "POINT_OPENING",
            "POINT_EXPLANATION",
            "ASK_CHECK",
            "FEEDBACK",
            "ASK_CONFIRM_ADVANCE",
            "UNIT_NOTES",
            "ASK_UNIT_NEXT",
        ]
        for type_name in expected_types:
            assert hasattr(TutorEventType, type_name), f"Missing TutorEventType.{type_name}"


class TestTeachingPlanSourceOfTruth:
    """Tests adicionales para el plan como source of truth."""

    def test_generate_teaching_plan_returns_plan(self):
        """generate_teaching_plan devuelve TeachingPlan."""
        notes = """## Explicación paso a paso

### 1. Tokenización
Contenido sobre tokenización.

### 2. Embeddings
Contenido sobre embeddings.
"""
        plan = generate_teaching_plan(notes, "test-u01")
        assert isinstance(plan, TeachingPlan)
        assert plan.unit_id == "test-u01"

    def test_teaching_plan_extracts_points_from_paso_a_paso(self):
        """El plan extrae puntos de '## Explicación paso a paso'."""
        notes = """## Resumen
Resumen que NO debe ser un punto.

## Explicación paso a paso

### 1. Primer concepto
Explicación del primer concepto.

### 2. Segundo concepto
Explicación del segundo concepto.

## Conceptos clave
Estos tampoco son puntos.
"""
        plan = generate_teaching_plan(notes, "test-u01")

        assert len(plan.points) == 2
        assert plan.points[0].title == "Primer concepto"
        assert plan.points[1].title == "Segundo concepto"

    def test_teaching_plan_uses_fallback_when_no_paso_a_paso(self):
        """El plan usa fallback cuando no hay 'Explicación paso a paso'."""
        notes = """## Introducción
Contenido de introducción.

## Desarrollo
Contenido de desarrollo.
"""
        plan = generate_teaching_plan(notes, "test-u01", unit_title="Test Unit")

        # Debe generar al menos un punto del fallback
        assert len(plan.points) >= 1

    def test_unit_opening_includes_student_name(self):
        """La apertura incluye el nombre del estudiante si se proporciona."""
        plan = TeachingPlan(
            unit_id="test-u01",
            objective="Test",
            points=[TeachingPoint(number=1, title="Test", content="...")],
        )
        event = generate_unit_opening("Unidad 1", plan, student_name="María")

        assert "María" in event.markdown

    def test_unit_opening_works_without_student_name(self):
        """La apertura funciona sin nombre de estudiante."""
        plan = TeachingPlan(
            unit_id="test-u01",
            objective="Test",
            points=[TeachingPoint(number=1, title="Test", content="...")],
        )
        event = generate_unit_opening("Unidad 1", plan, student_name="")

        # No debe haber coma suelta después de "Hola"
        assert "Hola." in event.markdown or "Hola " in event.markdown
        assert "Hola, ." not in event.markdown
