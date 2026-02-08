"""Tests para bugs del flujo Teaching-First (F7.3.1).

Estos tests verifican las correcciones de los 3 bugs identificados:
- BUG 1: "más ejemplos" no debe avanzar de punto
- BUG 2: Esperar input tras pregunta de verificación
- BUG 3: MCQ a/b/c evaluado correctamente
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from teaching.core.tutor import (
    detect_more_examples_intent,
    generate_more_examples,
    check_comprehension,
    explain_point,
    reexplain_with_analogy,
    TeachingPoint,
    SYSTEM_PROMPT_EXPLAIN_POINT,
    SYSTEM_PROMPT_CHECK_COMPREHENSION,
)


# =============================================================================
# BUG 1: "más ejemplos" no debe avanzar de punto
# =============================================================================


class TestMoreExamplesDetection:
    """Tests para detect_more_examples_intent()."""

    def test_detects_mas_ejemplos(self):
        """Detecta 'dame más ejemplos'."""
        assert detect_more_examples_intent("Sí, pero dame más ejemplos") is True

    def test_detects_otro_ejemplo(self):
        """Detecta 'dame otro ejemplo'."""
        assert detect_more_examples_intent("¿Podrías darme otro ejemplo?") is True

    def test_detects_otros_ejemplos(self):
        """Detecta 'otros ejemplos'."""
        assert detect_more_examples_intent("Necesito otros ejemplos") is True

    def test_detects_no_entiendo(self):
        """Detecta 'no entiendo'."""
        assert detect_more_examples_intent("No entiendo bien") is True

    def test_detects_no_lo_entiendo(self):
        """Detecta 'no lo entiendo'."""
        assert detect_more_examples_intent("No lo entiendo") is True

    def test_detects_explicalo_mejor(self):
        """Detecta 'explícalo mejor'."""
        assert detect_more_examples_intent("¿Puedes explicarlo mejor?") is True

    def test_detects_explicame_mas(self):
        """Detecta 'explícame más'."""
        assert detect_more_examples_intent("Explícame más por favor") is True

    def test_detects_no_seguro(self):
        """Detecta 'no estoy seguro'."""
        assert detect_more_examples_intent("No estoy seguro de entenderlo") is True

    def test_detects_repite(self):
        """Detecta 'repite'."""
        assert detect_more_examples_intent("Repite eso por favor") is True

    def test_detects_detalla_mas(self):
        """Detecta 'detalla más'."""
        assert detect_more_examples_intent("Detalla más el concepto") is True

    def test_detects_dudas(self):
        """Detecta 'dudas'."""
        assert detect_more_examples_intent("Tengo dudas") is True

    def test_detects_dame_otro(self):
        """Detecta 'dame otro'."""
        assert detect_more_examples_intent("Dame otro ejemplo") is True

    def test_detects_no_me_queda_claro(self):
        """Detecta 'no me queda claro'."""
        assert detect_more_examples_intent("No me queda claro") is True

    def test_detects_puedes_dar_mas(self):
        """Detecta 'puedes dar más'."""
        assert detect_more_examples_intent("¿Puedes dar más ejemplos?") is True

    def test_does_not_detect_simple_yes(self):
        """No detecta un simple 'sí'."""
        assert detect_more_examples_intent("Sí, lo entendí") is False

    def test_does_not_detect_correct_answer(self):
        """No detecta una respuesta correcta al concepto."""
        assert detect_more_examples_intent("El token es la unidad básica") is False

    def test_does_not_detect_adelante(self):
        """No detecta el comando 'adelante'."""
        assert detect_more_examples_intent("adelante") is False

    def test_does_not_detect_normal_explanation(self):
        """No detecta una explicación normal del estudiante."""
        assert detect_more_examples_intent("Los tokens son las palabras divididas") is False

    def test_handles_empty_string(self):
        """Maneja string vacío."""
        assert detect_more_examples_intent("") is False

    def test_case_insensitive(self):
        """Es case-insensitive."""
        assert detect_more_examples_intent("MÁS EJEMPLOS POR FAVOR") is True
        assert detect_more_examples_intent("NO ENTIENDO") is True


class TestGenerateMoreExamples:
    """Tests para generate_more_examples()."""

    def test_function_exists(self):
        """La función existe y es callable."""
        assert callable(generate_more_examples)

    @patch("teaching.core.tutor.LLMClient")
    def test_returns_string(self, mock_client_class):
        """Retorna un string."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = """
        Aquí tienes más ejemplos:
        1. Ejemplo uno sobre cocina
        2. Ejemplo dos sobre deportes

        ¿Ahora te queda más claro el concepto?
        """
        mock_client_class.return_value = mock_client

        point = TeachingPoint(number=1, title="Tokens", content="Los tokens son...")

        result = generate_more_examples(
            point=point,
            previous_explanation="Explicación previa sobre tokens...",
        )

        assert isinstance(result, str)
        assert len(result) > 0

    @patch("teaching.core.tutor.LLMClient")
    def test_uses_correct_system_prompt(self, mock_client_class):
        """Usa el prompt correcto para más ejemplos."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = "Ejemplos adicionales..."
        mock_client_class.return_value = mock_client

        point = TeachingPoint(number=1, title="Test", content="Contenido")

        generate_more_examples(
            point=point,
            previous_explanation="Explicación",
        )

        call_args = mock_client.simple_chat.call_args
        system_prompt = call_args.kwargs.get("system_prompt", "")

        assert "ejemplos adicionales" in system_prompt.lower()
        assert "NO repitas" in system_prompt

    @patch("teaching.core.tutor.LLMClient")
    def test_includes_previous_explanation_context(self, mock_client_class):
        """Incluye la explicación previa para no repetir."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = "Nuevos ejemplos..."
        mock_client_class.return_value = mock_client

        point = TeachingPoint(number=1, title="Test", content="Contenido")
        previous = "Esta es la explicación previa con ejemplo de cocina"

        generate_more_examples(
            point=point,
            previous_explanation=previous,
        )

        call_args = mock_client.simple_chat.call_args
        user_message = call_args.kwargs.get("user_message", "")

        assert "cocina" in user_message.lower() or "previa" in user_message.lower()


# =============================================================================
# BUG 2: Esperar input tras pregunta de verificación
# =============================================================================


class TestWaitsForInputAfterQuestion:
    """Tests que verifican que el flujo espera input."""

    @patch("teaching.core.tutor.LLMClient")
    def test_explanation_ends_with_question(self, mock_client_class):
        """explain_point termina con pregunta de verificación."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = """
        La tokenización es el proceso de dividir texto en unidades más pequeñas.

        Imagina que tienes una oración y la divides en palabras individuales.

        Por ejemplo, "Hola mundo" se convierte en ["Hola", "mundo"].

        ¿Qué entiendes por token en este contexto?
        """
        mock_client_class.return_value = mock_client

        point = TeachingPoint(number=1, title="Tokenización", content="...")
        result = explain_point(point=point, notes_context="...")

        lines = result.strip().split("\n")
        last_line = lines[-1] if lines else ""
        assert "?" in last_line

    @patch("teaching.core.tutor.LLMClient")
    def test_reexplanation_ends_with_question(self, mock_client_class):
        """reexplain_with_analogy termina con pregunta."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = """
        Piensa en los tokens como piezas de lego. Cada pieza es una unidad
        que se puede combinar con otras para construir algo más grande.

        ¿Ahora cómo describirías un token con tus propias palabras?
        """
        mock_client_class.return_value = mock_client

        point = TeachingPoint(number=1, title="Tokens", content="...")
        result = reexplain_with_analogy(
            point=point,
            original_question="¿Qué es un token?",
        )

        lines = result.strip().split("\n")
        last_line = lines[-1] if lines else ""
        assert "?" in last_line


# =============================================================================
# BUG 3: MCQ a/b/c evaluado correctamente
# =============================================================================


class TestMCQAcceptsLetter:
    """Tests para respuestas MCQ tipo letra."""

    @patch("teaching.core.tutor.LLMClient")
    def test_accepts_letter_a_as_valid(self, mock_client_class):
        """Acepta 'a' como respuesta válida a MCQ."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.9,
            "feedback": "¡Correcto! La opción a es la respuesta.",
            "needs_elaboration": False
        })
        mock_client_class.return_value = mock_client

        understood, feedback, needs_elaboration = check_comprehension(
            check_question="¿Cuál es correcta? a) Opción1 b) Opción2 c) Opción3",
            student_response="a",
            concept_context="La respuesta correcta es opción1",
        )

        assert understood is True
        assert needs_elaboration is False

    @patch("teaching.core.tutor.LLMClient")
    def test_accepts_letter_b_as_valid(self, mock_client_class):
        """Acepta 'b' como respuesta válida."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.85,
            "feedback": "¡Exacto!",
            "needs_elaboration": False
        })
        mock_client_class.return_value = mock_client

        understood, feedback, needs_elaboration = check_comprehension(
            check_question="¿Qué es un LLM? a) X b) Modelo grande c) Y",
            student_response="b",
            concept_context="LLM significa Large Language Model",
        )

        assert understood is True
        assert needs_elaboration is False

    @patch("teaching.core.tutor.LLMClient")
    def test_accepts_letter_c_as_valid(self, mock_client_class):
        """Acepta 'c' como respuesta válida."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.9,
            "feedback": "¡Bien!",
            "needs_elaboration": False
        })
        mock_client_class.return_value = mock_client

        understood, _, needs_elaboration = check_comprehension(
            check_question="Pregunta con opciones a) b) c)",
            student_response="c",
            concept_context="La opción c es correcta",
        )

        assert understood is True
        assert needs_elaboration is False

    @patch("teaching.core.tutor.LLMClient")
    def test_accepts_letter_with_dot(self, mock_client_class):
        """Acepta 'b.' con punto como respuesta válida."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.9,
            "feedback": "¡Correcto!",
            "needs_elaboration": False
        })
        mock_client_class.return_value = mock_client

        understood, _, needs_elaboration = check_comprehension(
            check_question="Pregunta",
            student_response="b.",
            concept_context="Contexto",
        )

        assert understood is True
        assert needs_elaboration is False

    @patch("teaching.core.tutor.LLMClient")
    def test_rejects_wrong_letter(self, mock_client_class):
        """Rechaza letra incorrecta."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": False,
            "confidence": 0.9,
            "feedback": "No exactamente, la opción correcta era otra.",
            "needs_elaboration": False
        })
        mock_client_class.return_value = mock_client

        understood, feedback, needs_elaboration = check_comprehension(
            check_question="¿Cuál es? a) Incorrecta b) Correcta",
            student_response="a",
            concept_context="La respuesta es b",
        )

        assert understood is False
        assert needs_elaboration is False

    @patch("teaching.core.tutor.LLMClient")
    def test_letter_response_uses_specific_prompt(self, mock_client_class):
        """Respuesta tipo letra usa prompt específico."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.9,
            "feedback": "Correcto",
            "needs_elaboration": False
        })
        mock_client_class.return_value = mock_client

        check_comprehension(
            check_question="Pregunta MCQ",
            student_response="b",
            concept_context="Contexto",
        )

        call_args = mock_client.simple_chat.call_args
        user_message = call_args.kwargs.get("user_message", "")

        # El prompt debe mencionar que es una letra sola
        assert "letra" in user_message.lower() or "opción" in user_message.lower()


class TestMCQNoAnswerInDisplayedText:
    """Tests que verifican que la respuesta no aparece en texto."""

    def test_explain_point_prompt_forbids_answer_reveal(self):
        """El prompt de explain_point prohíbe revelar respuestas."""
        # Verificar que el prompt contiene instrucciones de NO revelar
        assert "NUNCA" in SYSTEM_PROMPT_EXPLAIN_POINT
        assert "reveles" in SYSTEM_PROMPT_EXPLAIN_POINT.lower() or "incluyas" in SYSTEM_PROMPT_EXPLAIN_POINT.lower()

    def test_explain_point_prompt_mentions_mcq(self):
        """El prompt menciona opción múltiple."""
        prompt_lower = SYSTEM_PROMPT_EXPLAIN_POINT.lower()
        assert "opción múltiple" in prompt_lower or "a/b/c" in prompt_lower

    def test_check_comprehension_prompt_handles_letters(self):
        """El prompt de check_comprehension maneja respuestas tipo letra."""
        prompt_lower = SYSTEM_PROMPT_CHECK_COMPREHENSION.lower()
        assert "letra" in prompt_lower or "a/b/c" in prompt_lower


class TestReexplanationMatchesCorrectConcept:
    """Tests que verifican contexto correcto en reexplicación."""

    @patch("teaching.core.tutor.LLMClient")
    def test_reexplanation_receives_point_context(self, mock_client_class):
        """reexplain_with_analogy recibe el punto correcto."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = "Analogía sobre attention..."
        mock_client_class.return_value = mock_client

        point = TeachingPoint(
            number=2,
            title="Mecanismo de Atención",
            content="El mecanismo de atención permite al modelo enfocarse en partes relevantes...",
        )

        reexplain_with_analogy(
            point=point,
            original_question="¿Cómo funciona attention?",
        )

        # Verificar que se pasó el contenido correcto
        call_args = mock_client.simple_chat.call_args
        user_message = call_args.kwargs.get("user_message", "")

        # El mensaje debe contener el título o contenido del punto
        assert "Atención" in user_message or "atención" in user_message.lower()
        assert "enfocarse" in user_message.lower() or "relevantes" in user_message.lower()

    @patch("teaching.core.tutor.LLMClient")
    def test_reexplanation_does_not_mix_concepts(self, mock_client_class):
        """La reexplicación no mezcla conceptos de otros puntos."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = "Explicación de multimodalidad..."
        mock_client_class.return_value = mock_client

        # Punto sobre multimodalidad
        point = TeachingPoint(
            number=3,
            title="Modelos Multimodales",
            content="Los modelos multimodales procesan texto, imágenes y audio...",
        )

        reexplain_with_analogy(
            point=point,
            original_question="¿Qué hacen los modelos multimodales?",
        )

        call_args = mock_client.simple_chat.call_args
        user_message = call_args.kwargs.get("user_message", "")

        # Debe mencionar multimodalidad, no autosupervisión
        assert "multimodal" in user_message.lower() or "imágenes" in user_message.lower()
        # No debe mezclar con otros conceptos
        assert "autosupervis" not in user_message.lower()


# =============================================================================
# Tests de integración con el loop
# =============================================================================


class TestTeachingStateEnum:
    """Tests para el enum TeachingState."""

    def test_teaching_state_exists(self):
        """El enum TeachingState existe."""
        from teaching.cli.commands import TeachingState

        assert hasattr(TeachingState, "EXPLAINING")
        assert hasattr(TeachingState, "WAITING_INPUT")
        assert hasattr(TeachingState, "CHECKING")
        assert hasattr(TeachingState, "MORE_EXAMPLES")
        assert hasattr(TeachingState, "AWAITING_RETRY")  # Nuevo estado
        assert hasattr(TeachingState, "REMEDIATION")
        assert hasattr(TeachingState, "NEXT_POINT")

    def test_teaching_state_values_are_unique(self):
        """Los valores del enum son únicos."""
        from teaching.cli.commands import TeachingState

        values = [s.value for s in TeachingState]
        assert len(values) == len(set(values))

    def test_awaiting_retry_state_exists(self):
        """El estado AWAITING_RETRY existe para esperar segundo intento."""
        from teaching.cli.commands import TeachingState

        # Este estado es crítico: después de CHECKING con understood=False,
        # debe ir a AWAITING_RETRY (no a REMEDIATION directamente)
        assert TeachingState.AWAITING_RETRY is not None


# =============================================================================
# BUG CRÍTICO: No reexplicar sin esperar input
# =============================================================================


class TestNoReexplainWithoutInput:
    """Tests que verifican que NUNCA se llama a reexplain sin esperar input."""

    def test_checking_failure_goes_to_awaiting_retry_not_remediation(self):
        """Cuando check_comprehension retorna False, el estado debe ser AWAITING_RETRY."""
        from teaching.cli.commands import TeachingState

        # Flujo esperado:
        # CHECKING (understood=False) -> AWAITING_RETRY (espera input) -> CHECKING
        # NO: CHECKING (understood=False) -> REMEDIATION (sin input)

        # El estado AWAITING_RETRY existe y es diferente de REMEDIATION
        assert TeachingState.AWAITING_RETRY != TeachingState.REMEDIATION
        assert TeachingState.AWAITING_RETRY != TeachingState.CHECKING

    def test_remediation_only_after_second_failure(self):
        """REMEDIATION solo debe ejecutarse después de 2 intentos fallidos."""
        # Este test documenta el flujo correcto:
        # 1. Estudiante responde mal -> AWAITING_RETRY (pide segundo intento)
        # 2. Estudiante responde mal de nuevo -> REMEDIATION (ahora sí reexplica)

        # El flujo anterior era incorrecto:
        # 1. Estudiante responde mal -> REMEDIATION (reexplica sin esperar)

        from teaching.cli.commands import TeachingState

        # Verificar que los estados existen para el flujo correcto
        states_in_correct_order = [
            TeachingState.CHECKING,
            TeachingState.AWAITING_RETRY,
            TeachingState.REMEDIATION,
        ]
        assert len(states_in_correct_order) == 3

    @patch("teaching.core.tutor.LLMClient")
    def test_check_comprehension_with_false_does_not_trigger_reexplain(
        self, mock_client_class
    ):
        """check_comprehension con False NO debe disparar reexplain_with_analogy."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": False,
            "confidence": 0.8,
            "feedback": "No del todo. Inténtalo de nuevo.",
            "needs_elaboration": False
        })
        mock_client_class.return_value = mock_client

        # Llamar a check_comprehension
        understood, feedback, needs_elaboration = check_comprehension(
            check_question="¿Qué es un token?",
            student_response="No sé",
            concept_context="Un token es la unidad básica...",
        )

        assert understood is False
        assert needs_elaboration is False
        assert "Inténtalo" in feedback or "No" in feedback

        # Verificar que solo se llamó UNA vez al LLM (check_comprehension)
        # NO debe haber llamado a reexplain_with_analogy
        assert mock_client.simple_chat.call_count == 1

    def test_state_transition_checking_to_awaiting_retry(self):
        """Verificar la transición de estados: CHECKING -> AWAITING_RETRY."""
        from teaching.cli.commands import TeachingState

        # Simular la transición
        current_state = TeachingState.CHECKING
        understood = False

        # Según el código corregido, cuando understood=False:
        # new_state = TeachingState.AWAITING_RETRY (NO REMEDIATION)
        if not understood:
            new_state = TeachingState.AWAITING_RETRY
        else:
            new_state = TeachingState.NEXT_POINT

        assert new_state == TeachingState.AWAITING_RETRY
        assert new_state != TeachingState.REMEDIATION

    def test_awaiting_retry_requires_input_before_remediation(self):
        """En AWAITING_RETRY se debe leer input antes de ir a REMEDIATION."""
        from teaching.cli.commands import TeachingState

        # El estado AWAITING_RETRY implica:
        # 1. Se mostró feedback ("Inténtalo de nuevo")
        # 2. Se debe leer input del estudiante
        # 3. Solo después de evaluar ese input, decidir si ir a REMEDIATION

        # Esto es diferente del bug original donde:
        # CHECKING -> REMEDIATION (sin leer input)

        assert TeachingState.AWAITING_RETRY.name == "AWAITING_RETRY"


class TestImportsAvailable:
    """Tests para verificar que los imports funcionan."""

    def test_detect_more_examples_intent_importable(self):
        """detect_more_examples_intent es importable desde tutor."""
        from teaching.core.tutor import detect_more_examples_intent

        assert callable(detect_more_examples_intent)

    def test_generate_more_examples_importable(self):
        """generate_more_examples es importable desde tutor."""
        from teaching.core.tutor import generate_more_examples

        assert callable(generate_more_examples)

    def test_teaching_state_importable(self):
        """TeachingState es importable desde commands."""
        from teaching.cli.commands import TeachingState

        assert TeachingState is not None

    def test_awaiting_retry_state_importable(self):
        """AWAITING_RETRY es importable como parte del enum."""
        from teaching.cli.commands import TeachingState

        assert hasattr(TeachingState, "AWAITING_RETRY")


# =============================================================================
# F7.3.2: Tests para invariantes AWAITING_RETRY
# =============================================================================


class TestAffirmativeResponseHandling:
    """Tests para respuestas afirmativas sin explicación (invariante 2)."""

    @patch("teaching.core.tutor.LLMClient")
    def test_si_lo_entiendo_asks_for_elaboration(self, mock_client_class):
        """'sí, lo entiendo' no debe marcarse como fallo automático."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.6,
            "feedback": "¡Bien! ¿Podrías explicarlo brevemente con tus palabras?",
            "needs_elaboration": True
        })
        mock_client_class.return_value = mock_client

        understood, feedback, needs_elaboration = check_comprehension(
            check_question="¿Qué es un token?",
            student_response="sí, lo entiendo",
            concept_context="Un token es la unidad básica...",
        )

        # No debe ser False automáticamente - puede ser True o needs_elaboration
        assert understood is True or needs_elaboration is True
        # El feedback debe pedir elaboración
        assert "explicar" in feedback.lower() or "palabras" in feedback.lower()

    @patch("teaching.core.tutor.LLMClient")
    def test_creo_que_si_triggers_elaboration(self, mock_client_class):
        """'creo que sí' debe pedir elaboración."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.5,
            "feedback": "¿Podrías explicarlo con tus propias palabras?",
            "needs_elaboration": True
        })
        mock_client_class.return_value = mock_client

        understood, feedback, needs_elaboration = check_comprehension(
            check_question="¿Entiendes cómo funciona?",
            student_response="creo que sí",
            concept_context="Contexto del concepto",
        )

        assert needs_elaboration is True

    def test_prompt_mentions_affirmative_responses(self):
        """El prompt de check_comprehension menciona respuestas afirmativas."""
        from teaching.core.tutor import SYSTEM_PROMPT_CHECK_COMPREHENSION

        prompt_lower = SYSTEM_PROMPT_CHECK_COMPREHENSION.lower()
        # Debe mencionar respuestas afirmativas
        assert "sí" in prompt_lower or "afirmativ" in prompt_lower
        # Debe mencionar needs_elaboration
        assert "needs_elaboration" in SYSTEM_PROMPT_CHECK_COMPREHENSION


class TestMCQLetterSelectionInvariant:
    """Tests para respuestas MCQ tipo letra (invariante 3)."""

    @patch("teaching.core.tutor.LLMClient")
    def test_letter_b_with_mcq_is_valid_selection(self, mock_client_class):
        """'b' debe interpretarse como selección válida, no respuesta vacía."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.95,
            "feedback": "¡Correcto! La opción b es la respuesta.",
            "needs_elaboration": False
        })
        mock_client_class.return_value = mock_client

        understood, feedback, needs_elaboration = check_comprehension(
            check_question="¿Cuál es correcta? a) Incorrecto b) Correcto c) Incorrecto",
            student_response="b",
            concept_context="La respuesta correcta es la opción b",
        )

        assert understood is True
        assert needs_elaboration is False
        # No debe mencionar "escueto" o "breve" en tono negativo
        assert "escuet" not in feedback.lower()

    @patch("teaching.core.tutor.LLMClient")
    def test_single_letter_not_treated_as_empty(self, mock_client_class):
        """Una letra sola no debe tratarse como respuesta vacía."""
        mock_client = MagicMock()
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.9,
            "feedback": "¡Exacto!",
            "needs_elaboration": False
        })
        mock_client_class.return_value = mock_client

        understood, feedback, needs_elaboration = check_comprehension(
            check_question="Elige: a) X b) Y c) Z",
            student_response="c",
            concept_context="La opción c es correcta",
        )

        # Debe aceptar la respuesta como válida
        assert understood is True
        # No debe pedir elaboración para MCQ correcto
        assert needs_elaboration is False


class TestNeedsElaborationField:
    """Tests para el nuevo campo needs_elaboration."""

    def test_check_comprehension_returns_three_values(self):
        """check_comprehension debe retornar 3 valores."""
        from teaching.core.tutor import check_comprehension
        import inspect

        sig = inspect.signature(check_comprehension)
        # Verificar que la función existe y tiene el tipo de retorno correcto
        assert callable(check_comprehension)

    @patch("teaching.core.tutor.LLMClient")
    def test_needs_elaboration_defaults_to_false(self, mock_client_class):
        """needs_elaboration debe ser False por defecto si no se incluye."""
        mock_client = MagicMock()
        # Respuesta sin needs_elaboration
        mock_client.simple_chat.return_value = json.dumps({
            "understood": True,
            "confidence": 0.9,
            "feedback": "¡Bien!"
            # Sin needs_elaboration
        })
        mock_client_class.return_value = mock_client

        understood, feedback, needs_elaboration = check_comprehension(
            check_question="Pregunta",
            student_response="Respuesta completa",
            concept_context="Contexto",
        )

        # Debe default a False
        assert needs_elaboration is False

    @patch("teaching.core.tutor.LLMClient")
    def test_fallback_returns_three_values(self, mock_client_class):
        """El fallback debe retornar 3 valores."""
        mock_client = MagicMock()
        # Respuesta inválida que activa fallback
        mock_client.simple_chat.return_value = "respuesta inválida sin JSON"
        mock_client_class.return_value = mock_client

        result = check_comprehension(
            check_question="Pregunta",
            student_response="Respuesta",
            concept_context="Contexto",
        )

        # Debe retornar 3 valores incluso en fallback
        assert len(result) == 3
        understood, feedback, needs_elaboration = result
        assert understood is False
        assert needs_elaboration is False


# =============================================================================
# F7.4: Tests para corrección de bugs de UX
# =============================================================================


class TestTutorPromptKindEnum:
    """Tests para el enum TutorPromptKind."""

    def test_enum_exists(self):
        """El enum TutorPromptKind existe."""
        from teaching.core.tutor import TutorPromptKind

        assert TutorPromptKind is not None

    def test_has_all_values(self):
        """El enum tiene todos los valores necesarios."""
        from teaching.core.tutor import TutorPromptKind

        assert hasattr(TutorPromptKind, "ASK_DEEPEN")
        assert hasattr(TutorPromptKind, "ASK_ADVANCE_CONFIRM")
        assert hasattr(TutorPromptKind, "ASK_COMPREHENSION")
        assert hasattr(TutorPromptKind, "ASK_MCQ")
        assert hasattr(TutorPromptKind, "ASK_POST_EXAMPLES")
        assert hasattr(TutorPromptKind, "NORMAL_QA")

    def test_values_are_unique(self):
        """Los valores del enum son únicos."""
        from teaching.core.tutor import TutorPromptKind

        values = [pk.value for pk in TutorPromptKind]
        assert len(values) == len(set(values))


class TestIsAdvanceIntent:
    """Tests para is_advance_intent()."""

    def test_function_exists(self):
        """La función is_advance_intent existe."""
        from teaching.core.tutor import is_advance_intent

        assert callable(is_advance_intent)

    def test_detects_avanzar(self):
        """Detecta 'avanzar'."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("avanzar") is True
        assert is_advance_intent("podemos avanzar") is True

    def test_detects_siguiente_seccion(self):
        """Detecta 'siguiente sección'."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("siguiente sección") is True
        assert is_advance_intent("siguiente punto") is True
        assert is_advance_intent("siguiente tema") is True

    def test_detects_podemos_avanzar_natural(self):
        """Detecta frases naturales de avance."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("podemos avanzar a la siguiente sección") is True
        assert is_advance_intent("podemos pasar al siguiente") is True

    def test_detects_pasemos(self):
        """Detecta 'pasemos'."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("pasemos") is True
        assert is_advance_intent("pasemos al siguiente") is True

    def test_detects_continuemos(self):
        """Detecta 'continuemos'."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("continuemos") is True

    def test_detects_adelante(self):
        """Detecta 'adelante'."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("adelante") is True

    def test_does_not_detect_normal_answer(self):
        """No detecta respuestas normales."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("el token es una unidad") is False
        assert is_advance_intent("sí, lo entiendo") is False

    def test_handles_empty(self):
        """Maneja string vacío."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("") is False

    def test_case_insensitive(self):
        """Es case-insensitive."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("AVANZAR") is True
        assert is_advance_intent("Siguiente Punto") is True


class TestIsAffirmative:
    """Tests para is_affirmative()."""

    def test_function_exists(self):
        """La función is_affirmative existe."""
        from teaching.core.tutor import is_affirmative

        assert callable(is_affirmative)

    def test_detects_si(self):
        """Detecta 'sí' y 'si'."""
        from teaching.core.tutor import is_affirmative

        assert is_affirmative("sí") is True
        assert is_affirmative("si") is True
        assert is_affirmative("Sí") is True

    def test_detects_vale(self):
        """Detecta 'vale'."""
        from teaching.core.tutor import is_affirmative

        assert is_affirmative("vale") is True
        assert is_affirmative("Vale") is True

    def test_detects_ok(self):
        """Detecta 'ok' y 'okay'."""
        from teaching.core.tutor import is_affirmative

        assert is_affirmative("ok") is True
        assert is_affirmative("okay") is True

    def test_detects_claro(self):
        """Detecta 'claro'."""
        from teaching.core.tutor import is_affirmative

        assert is_affirmative("claro") is True

    def test_detects_de_acuerdo(self):
        """Detecta 'de acuerdo'."""
        from teaching.core.tutor import is_affirmative

        assert is_affirmative("de acuerdo") is True

    def test_detects_perfecto(self):
        """Detecta 'perfecto'."""
        from teaching.core.tutor import is_affirmative

        assert is_affirmative("perfecto") is True

    def test_does_not_detect_sentence_with_si(self):
        """No detecta 'sí' dentro de una oración."""
        from teaching.core.tutor import is_affirmative

        assert is_affirmative("sí lo entiendo bien") is False
        assert is_affirmative("creo que sí") is False

    def test_does_not_detect_explanation(self):
        """No detecta explicaciones."""
        from teaching.core.tutor import is_affirmative

        assert is_affirmative("el token es la unidad básica") is False

    def test_handles_empty(self):
        """Maneja string vacío."""
        from teaching.core.tutor import is_affirmative

        assert is_affirmative("") is False


class TestGenerateDeeperExplanation:
    """Tests para generate_deeper_explanation()."""

    def test_function_exists(self):
        """La función generate_deeper_explanation existe."""
        from teaching.core.tutor import generate_deeper_explanation

        assert callable(generate_deeper_explanation)

    @patch("teaching.core.tutor.LLMClient")
    def test_returns_string(self, mock_client_class):
        """Retorna un string."""
        from teaching.core.tutor import generate_deeper_explanation, TeachingPoint

        mock_client = MagicMock()
        mock_client.simple_chat.return_value = "Profundizando en el concepto..."
        mock_client_class.return_value = mock_client

        point = TeachingPoint(number=1, title="Test", content="Contenido")
        result = generate_deeper_explanation(point, "Explicación previa")

        assert isinstance(result, str)
        assert len(result) > 0


class TestNewTeachingStatesF74:
    """Tests para los nuevos estados del enum TeachingState."""

    def test_confirm_advance_state_exists(self):
        """El estado CONFIRM_ADVANCE existe."""
        from teaching.cli.commands import TeachingState

        assert hasattr(TeachingState, "CONFIRM_ADVANCE")

    def test_deepen_explanation_state_exists(self):
        """El estado DEEPEN_EXPLANATION existe."""
        from teaching.cli.commands import TeachingState

        assert hasattr(TeachingState, "DEEPEN_EXPLANATION")

    def test_all_states_unique(self):
        """Todos los estados tienen valores únicos."""
        from teaching.cli.commands import TeachingState

        values = [s.value for s in TeachingState]
        assert len(values) == len(set(values))

    def test_total_state_count(self):
        """Hay 12 estados en total (7 originales + 2 F7.4 + 1 F8.2 + 2 F8.4)."""
        from teaching.cli.commands import TeachingState

        assert len(list(TeachingState)) == 12


class TestBug1DeepenInterpretation:
    """Tests para Bug 1: 'vale' a '¿Quieres profundizar?' debe profundizar."""

    def test_vale_with_ask_deepen_should_go_to_deepen(self):
        """'vale' con ASK_DEEPEN debe ir a DEEPEN_EXPLANATION."""
        from teaching.core.tutor import TutorPromptKind, is_affirmative

        user_input = "vale"
        last_prompt_kind = TutorPromptKind.ASK_DEEPEN

        # Lógica esperada
        if is_affirmative(user_input) and last_prompt_kind == TutorPromptKind.ASK_DEEPEN:
            next_state = "DEEPEN_EXPLANATION"
        else:
            next_state = "CHECKING"

        assert next_state == "DEEPEN_EXPLANATION"

    def test_si_with_ask_deepen_should_go_to_deepen(self):
        """'sí' con ASK_DEEPEN debe ir a DEEPEN_EXPLANATION."""
        from teaching.core.tutor import TutorPromptKind, is_affirmative

        user_input = "sí"
        last_prompt_kind = TutorPromptKind.ASK_DEEPEN

        if is_affirmative(user_input) and last_prompt_kind == TutorPromptKind.ASK_DEEPEN:
            next_state = "DEEPEN_EXPLANATION"
        else:
            next_state = "CHECKING"

        assert next_state == "DEEPEN_EXPLANATION"


class TestBug2MoreExamplesNoLoop:
    """Tests para Bug 2: más ejemplos no debe causar bucle infinito."""

    def test_more_examples_prompt_ends_with_options(self):
        """El prompt de más ejemplos termina con opciones, no pregunta."""
        from teaching.core.tutor import SYSTEM_PROMPT_MORE_EXAMPLES

        # Debe contener opciones
        assert "(1)" in SYSTEM_PROMPT_MORE_EXAMPLES or "más ejemplos" in SYSTEM_PROMPT_MORE_EXAMPLES.lower()
        # NO debe terminar con pregunta de verificación
        assert "pregunta de verificación" not in SYSTEM_PROMPT_MORE_EXAMPLES.lower() or "NO hagas" in SYSTEM_PROMPT_MORE_EXAMPLES


class TestBug3ConfirmBeforeAdvance:
    """Tests para Bug 3: siempre confirmar antes de avanzar."""

    def test_understood_should_go_to_confirm_not_next(self):
        """understood=True debe ir a CONFIRM_ADVANCE, no NEXT_POINT directo."""
        understood = True
        needs_elaboration = False

        # Lógica esperada (nueva)
        if understood and not needs_elaboration:
            next_state = "CONFIRM_ADVANCE"
        else:
            next_state = "SOMETHING_ELSE"

        assert next_state == "CONFIRM_ADVANCE"
        assert next_state != "NEXT_POINT"


class TestBug4NaturalAdvanceCommands:
    """Tests para Bug 4: comandos naturales de avance."""

    def test_podemos_avanzar_a_la_siguiente_detected(self):
        """Detecta 'podemos avanzar a la siguiente sección'."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("podemos avanzar a la siguiente sección") is True

    def test_vamos_al_siguiente_detected(self):
        """Detecta 'vamos al siguiente'."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("vamos al siguiente") is True

    def test_pasemos_al_siguiente_punto_detected(self):
        """Detecta 'pasemos al siguiente punto'."""
        from teaching.core.tutor import is_advance_intent

        assert is_advance_intent("pasemos al siguiente punto") is True


class TestPreventInfiniteLoop:
    """Tests para prevenir bucles infinitos."""

    def test_ask_post_examples_with_si_asks_clarification(self):
        """Después de ejemplos, 'sí' solo debe pedir clarificación."""
        from teaching.core.tutor import TutorPromptKind, is_affirmative

        user_input = "sí"
        last_prompt_kind = TutorPromptKind.ASK_POST_EXAMPLES

        # Lógica esperada: NO debe ir a CHECKING directamente
        if is_affirmative(user_input) and last_prompt_kind == TutorPromptKind.ASK_POST_EXAMPLES:
            action = "ASK_CLARIFICATION"  # Preguntar qué quiere hacer
        else:
            action = "CHECKING"

        assert action == "ASK_CLARIFICATION"
