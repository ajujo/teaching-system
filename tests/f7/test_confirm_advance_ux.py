"""Tests para Bug A: CONFIRM_ADVANCE UX fixes (F8.1).

Tests para los patrones extendidos y el parser de respuestas
al prompt "¿Avanzamos al siguiente punto? [Y/n]".
"""

import pytest

from teaching.core.tutor import (
    is_affirmative,
    is_advance_intent,
    is_negative,
    parse_confirm_advance_response,
)


class TestIsAffirmativeExtended:
    """Tests para patrones afirmativos extendidos."""

    def test_y_is_affirmative(self):
        """'y' debe ser reconocido como afirmativo."""
        assert is_affirmative("y") is True
        assert is_affirmative("Y") is True

    def test_yes_is_affirmative(self):
        """'yes' debe ser reconocido como afirmativo."""
        assert is_affirmative("yes") is True
        assert is_affirmative("Yes") is True

    def test_vamos_is_affirmative(self):
        """'vamos' debe ser reconocido como afirmativo."""
        assert is_affirmative("vamos") is True

    def test_adelante_is_affirmative(self):
        """'adelante' debe ser reconocido como afirmativo."""
        assert is_affirmative("adelante") is True

    def test_existing_patterns_still_work(self):
        """Patrones existentes siguen funcionando."""
        assert is_affirmative("sí") is True
        assert is_affirmative("si") is True
        assert is_affirmative("vale") is True
        assert is_affirmative("ok") is True
        assert is_affirmative("claro") is True


class TestIsAdvanceIntentExtended:
    """Tests para patrones de avance extendidos."""

    def test_avancemos_detected(self):
        """'avancemos' debe ser detectado como intent de avance."""
        assert is_advance_intent("avancemos") is True
        assert is_advance_intent("Avancemos") is True

    def test_avancemos_in_phrase(self):
        """'avancemos' en frase debe ser detectado."""
        assert is_advance_intent("Avancemos al siguiente punto") is True

    def test_pasemos_detected(self):
        """'pasemos' debe ser detectado."""
        assert is_advance_intent("pasemos") is True
        assert is_advance_intent("pasamos") is True

    def test_continuemos_detected(self):
        """'continuemos' debe ser detectado."""
        assert is_advance_intent("continuemos") is True
        assert is_advance_intent("continuamos") is True

    def test_sigamos_detected(self):
        """'sigamos' debe ser detectado."""
        assert is_advance_intent("sigamos") is True

    def test_existing_patterns_still_work(self):
        """Patrones existentes siguen funcionando."""
        assert is_advance_intent("avanzar") is True
        assert is_advance_intent("avanza") is True
        assert is_advance_intent("siguiente punto") is True
        assert is_advance_intent("adelante") is True


class TestIsNegative:
    """Tests para is_negative()."""

    def test_n_is_negative(self):
        """'n' debe ser negativo."""
        assert is_negative("n") is True
        assert is_negative("N") is True

    def test_no_is_negative(self):
        """'no' debe ser negativo."""
        assert is_negative("no") is True
        assert is_negative("No") is True

    def test_espera_is_negative(self):
        """'espera' debe ser negativo."""
        assert is_negative("espera") is True

    def test_aun_no_is_negative(self):
        """'aún no' debe ser negativo."""
        assert is_negative("aún no") is True
        assert is_negative("aun no") is True

    def test_todavia_no_is_negative(self):
        """'todavía no' debe ser negativo."""
        assert is_negative("todavía no") is True
        assert is_negative("todavia no") is True

    def test_repite_is_negative(self):
        """'repite' debe ser negativo."""
        assert is_negative("repite") is True

    def test_mas_lento_is_negative(self):
        """'más lento' debe ser negativo."""
        assert is_negative("más lento") is True
        assert is_negative("mas lento") is True

    def test_no_seguro_is_negative(self):
        """'no estoy seguro' debe ser negativo."""
        assert is_negative("no estoy seguro") is True
        assert is_negative("no seguro") is True

    def test_normal_text_not_negative(self):
        """Texto normal no es negativo."""
        assert is_negative("el token es una unidad") is False
        assert is_negative("sí, entiendo") is False


class TestParseConfirmAdvanceResponse:
    """Tests para parse_confirm_advance_response()."""

    def test_y_returns_advance(self):
        """'y' debe retornar 'advance'."""
        assert parse_confirm_advance_response("y") == "advance"
        assert parse_confirm_advance_response("Y") == "advance"

    def test_yes_returns_advance(self):
        """'yes' debe retornar 'advance'."""
        assert parse_confirm_advance_response("yes") == "advance"

    def test_avancemos_returns_advance(self):
        """'avancemos' debe retornar 'advance'."""
        assert parse_confirm_advance_response("avancemos") == "advance"

    def test_si_returns_advance(self):
        """'sí' debe retornar 'advance'."""
        assert parse_confirm_advance_response("sí") == "advance"
        assert parse_confirm_advance_response("si") == "advance"

    def test_vale_returns_advance(self):
        """'vale' debe retornar 'advance'."""
        assert parse_confirm_advance_response("vale") == "advance"

    def test_n_returns_stay(self):
        """'n' debe retornar 'stay'."""
        assert parse_confirm_advance_response("n") == "stay"

    def test_no_returns_stay(self):
        """'no' debe retornar 'stay'."""
        assert parse_confirm_advance_response("no") == "stay"

    def test_espera_returns_stay(self):
        """'espera' debe retornar 'stay'."""
        assert parse_confirm_advance_response("espera") == "stay"

    def test_mas_ejemplos_returns_stay(self):
        """'más ejemplos' debe retornar 'stay'."""
        assert parse_confirm_advance_response("más ejemplos") == "stay"

    def test_command_returns_command(self):
        """Comandos globales retornan 'command'."""
        assert parse_confirm_advance_response("apuntes") == "command"
        assert parse_confirm_advance_response("control") == "command"
        assert parse_confirm_advance_response("examen") == "command"
        assert parse_confirm_advance_response("stop") == "command"

    def test_unknown_returns_unknown(self):
        """Texto no reconocido retorna 'unknown'."""
        assert parse_confirm_advance_response("blah blah") == "unknown"
        assert parse_confirm_advance_response("el token es una unidad") == "unknown"


class TestConfirmAdvanceInvariants:
    """Tests para invariantes del flujo CONFIRM_ADVANCE."""

    def test_y_does_not_require_check_comprehension(self):
        """Responder 'y' no debe evaluar comprensión conceptual."""
        # El parser debe retornar 'advance' directamente
        result = parse_confirm_advance_response("y")
        assert result == "advance"
        # Si retorna 'advance', commands.py va a NEXT_POINT sin CHECKING

    def test_avancemos_does_not_require_check_comprehension(self):
        """Responder 'avancemos' no debe evaluar comprensión conceptual."""
        result = parse_confirm_advance_response("avancemos")
        assert result == "advance"

    def test_all_advance_intents_return_advance(self):
        """Todos los intents de avance retornan 'advance'."""
        advance_inputs = [
            "y", "Y", "yes", "sí", "si", "vale", "ok", "claro",
            "avancemos", "pasemos", "continuemos", "sigamos",
            "adelante", "vamos", "siguiente punto",
        ]
        for inp in advance_inputs:
            result = parse_confirm_advance_response(inp)
            assert result == "advance", f"'{inp}' should return 'advance', got '{result}'"

    def test_all_stay_intents_return_stay(self):
        """Todos los intents de quedarse retornan 'stay'."""
        stay_inputs = [
            "n", "no", "espera", "aún no", "repite",
            "más ejemplos", "dame otro ejemplo",
        ]
        for inp in stay_inputs:
            result = parse_confirm_advance_response(inp)
            assert result == "stay", f"'{inp}' should return 'stay', got '{result}'"
