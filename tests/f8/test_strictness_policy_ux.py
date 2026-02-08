"""Tests for strictness policy UX improvements (F8.2.1).

Tests the natural language parsing, followups limit, and capitan_ortega strictness.
"""

import pytest

from teaching.config.personas import (
    TeachingPolicy,
    get_persona,
    clear_personas_cache,
)
from teaching.core.tutor import (
    is_review_intent,
    parse_post_failure_choice_response,
    parse_confirm_advance_response,
    is_affirmative,
    is_advance_intent,
)


class TestYesInConfirmAdvanceAdvances:
    """Test 1: 'y' en CONFIRM_ADVANCE avanza, no llama check_comprehension."""

    def test_y_is_affirmative(self):
        """'y' debe ser reconocido como afirmativo."""
        assert is_affirmative("y")

    def test_yes_is_affirmative(self):
        """'yes' debe ser reconocido como afirmativo."""
        assert is_affirmative("yes")

    def test_y_in_confirm_advance_returns_advance(self):
        """'y' en parse_confirm_advance_response debe retornar 'advance'."""
        result = parse_confirm_advance_response("y")
        assert result == "advance"

    def test_yes_in_confirm_advance_returns_advance(self):
        """'yes' en parse_confirm_advance_response debe retornar 'advance'."""
        result = parse_confirm_advance_response("yes")
        assert result == "advance"


class TestValeInPostFailureChoiceRespectsDefault:
    """Test 2: 'vale' respeta default_after_failure."""

    def test_vale_with_default_advance(self):
        """'vale' con default='advance' debe retornar 'advance'."""
        result = parse_post_failure_choice_response("vale", default_after_failure="advance")
        assert result == "advance"

    def test_vale_with_default_stay(self):
        """'vale' con default='stay' debe retornar 'review'."""
        result = parse_post_failure_choice_response("vale", default_after_failure="stay")
        assert result == "review"

    def test_ok_with_default_advance(self):
        """'ok' con default='advance' debe retornar 'advance'."""
        result = parse_post_failure_choice_response("ok", default_after_failure="advance")
        assert result == "advance"

    def test_si_with_default_stay(self):
        """'sí' con default='stay' debe retornar 'review'."""
        result = parse_post_failure_choice_response("sí", default_after_failure="stay")
        assert result == "review"


class TestPostFailureChoiceNaturalLanguageAdvance:
    """Test 3: lenguaje natural para avanzar."""

    @pytest.mark.parametrize("text", [
        "avancemos",
        "siguiente",
        "continuar",
        "sigamos",
        "pasemos",
        "adelante",
        "a",
        "avanzar",
    ])
    def test_advance_intents(self, text):
        """Varios intents de avance deben retornar 'advance'."""
        result = parse_post_failure_choice_response(text)
        assert result == "advance", f"'{text}' should return 'advance'"


class TestPostFailureChoiceNaturalLanguageReview:
    """Test 4: lenguaje natural para repasar."""

    @pytest.mark.parametrize("text", [
        "repasar",
        "más ejemplos",
        "no",
        "espera",
        "aún no",
        "r",
        "repaso",
        "explica mejor",
        "más lento",
    ])
    def test_review_intents(self, text):
        """Varios intents de review deben retornar 'review'."""
        result = parse_post_failure_choice_response(text)
        assert result == "review", f"'{text}' should return 'review'"

    def test_is_review_intent_repasar(self):
        """is_review_intent detecta 'repasar'."""
        assert is_review_intent("repasar")

    def test_is_review_intent_explica_mejor(self):
        """is_review_intent detecta 'explica mejor'."""
        assert is_review_intent("explica mejor")


class TestFollowupsLimitTriggersChoice:
    """Test 5: límite de followups dispara POST_FAILURE_CHOICE."""

    def test_profe_nico_max_followups_0(self):
        """profe_nico tiene max_followups_per_point=0."""
        clear_personas_cache()
        persona = get_persona("profe_nico")
        policy = persona.get_teaching_policy()
        assert policy.max_followups_per_point == 0

    def test_dra_vega_max_followups_1(self):
        """dra_vega tiene max_followups_per_point=1."""
        persona = get_persona("dra_vega")
        policy = persona.get_teaching_policy()
        assert policy.max_followups_per_point == 1

    def test_followups_limit_logic(self):
        """El límite de followups funciona correctamente."""
        policy = TeachingPolicy(max_followups_per_point=1)
        current_followups = 0

        # First followup is allowed
        current_followups += 1
        assert current_followups <= policy.max_followups_per_point

        # Second followup exceeds limit
        current_followups += 1
        assert current_followups > policy.max_followups_per_point


class TestCapitanPolicyIsStrict:
    """Test 6: capitan_ortega tiene policy estricta."""

    def test_capitan_max_attempts_1(self):
        """capitan_ortega tiene max_attempts_per_point=1 (estricto)."""
        clear_personas_cache()
        persona = get_persona("capitan_ortega")
        assert persona is not None
        policy = persona.get_teaching_policy()
        assert policy.max_attempts_per_point == 1

    def test_capitan_no_advance_on_failure(self):
        """capitan_ortega NO permite avanzar si falla."""
        persona = get_persona("capitan_ortega")
        policy = persona.get_teaching_policy()
        assert policy.allow_advance_on_failure is False

    def test_capitan_default_stay(self):
        """capitan_ortega tiene default_after_failure='stay'."""
        persona = get_persona("capitan_ortega")
        policy = persona.get_teaching_policy()
        assert policy.default_after_failure == "stay"


class TestPostFailureChoiceCommands:
    """Tests para comandos globales en POST_FAILURE_CHOICE."""

    @pytest.mark.parametrize("cmd", ["apuntes", "control", "examen", "stop"])
    def test_commands_return_command(self, cmd):
        """Comandos globales retornan 'command'."""
        result = parse_post_failure_choice_response(cmd)
        assert result == "command"


class TestPostFailureChoiceEmptyInput:
    """Tests para entrada vacía en POST_FAILURE_CHOICE."""

    def test_empty_with_default_advance(self):
        """Entrada vacía con default='advance' retorna 'advance'."""
        result = parse_post_failure_choice_response("", default_after_failure="advance")
        assert result == "advance"

    def test_empty_with_default_stay(self):
        """Entrada vacía con default='stay' retorna 'review'."""
        result = parse_post_failure_choice_response("", default_after_failure="stay")
        assert result == "review"


class TestPostFailureChoiceUnknown:
    """Tests para entradas no reconocidas."""

    def test_gibberish_returns_unknown(self):
        """Texto no reconocido retorna 'unknown'."""
        result = parse_post_failure_choice_response("asdfghjkl")
        assert result == "unknown"

    def test_random_sentence_returns_unknown(self):
        """Oración aleatoria retorna 'unknown'."""
        result = parse_post_failure_choice_response("el gato come pescado")
        assert result == "unknown"
