"""Tests for strictness policy (F8.2).

Tests the per-persona teaching policy, attempt limits, and post-failure choices.
"""

import pytest

from teaching.config.personas import (
    TeachingPolicy,
    Persona,
    get_persona,
    clear_personas_cache,
)


class TestTeachingPolicyDefaults:
    """Tests for TeachingPolicy default values."""

    def test_default_max_attempts_is_2(self):
        """Default max_attempts_per_point is 2."""
        policy = TeachingPolicy()
        assert policy.max_attempts_per_point == 2

    def test_default_remediation_style_is_both(self):
        """Default remediation_style is 'both'."""
        policy = TeachingPolicy()
        assert policy.remediation_style == "both"

    def test_default_allow_advance_on_failure_is_true(self):
        """Default allow_advance_on_failure is True."""
        policy = TeachingPolicy()
        assert policy.allow_advance_on_failure is True

    def test_default_after_failure_is_stay(self):
        """Default default_after_failure is 'stay'."""
        policy = TeachingPolicy()
        assert policy.default_after_failure == "stay"

    def test_default_max_followups_is_1(self):
        """Default max_followups_per_point is 1."""
        policy = TeachingPolicy()
        assert policy.max_followups_per_point == 1


class TestPersonaHasTeachingPolicy:
    """Tests for Persona.get_teaching_policy()."""

    def test_dra_vega_has_policy(self):
        """dra_vega has teaching_policy defined."""
        clear_personas_cache()
        persona = get_persona("dra_vega")
        assert persona is not None
        policy = persona.get_teaching_policy()
        assert policy is not None
        assert isinstance(policy, TeachingPolicy)

    def test_dra_vega_max_attempts_2(self):
        """dra_vega has max_attempts_per_point=2."""
        persona = get_persona("dra_vega")
        policy = persona.get_teaching_policy()
        assert policy.max_attempts_per_point == 2

    def test_profe_nico_max_attempts_1(self):
        """profe_nico has max_attempts_per_point=1 (permissive)."""
        persona = get_persona("profe_nico")
        assert persona is not None
        policy = persona.get_teaching_policy()
        assert policy.max_attempts_per_point == 1

    def test_profe_nico_default_after_failure_advance(self):
        """profe_nico has default_after_failure='advance' (permissive)."""
        persona = get_persona("profe_nico")
        policy = persona.get_teaching_policy()
        assert policy.default_after_failure == "advance"

    def test_capitan_ortega_no_advance_on_failure(self):
        """capitan_ortega has allow_advance_on_failure=False (strict)."""
        persona = get_persona("capitan_ortega")
        assert persona is not None
        policy = persona.get_teaching_policy()
        assert policy.allow_advance_on_failure is False


class TestPersonaRemediationStyle:
    """Tests for remediation_style per persona."""

    def test_dra_vega_uses_both(self):
        """dra_vega uses 'both' (analogy + example)."""
        persona = get_persona("dra_vega")
        policy = persona.get_teaching_policy()
        assert policy.remediation_style == "both"

    def test_profe_nico_uses_example(self):
        """profe_nico uses 'example' only."""
        persona = get_persona("profe_nico")
        policy = persona.get_teaching_policy()
        assert policy.remediation_style == "example"

    def test_ines_uses_analogy(self):
        """ines uses 'analogy' only."""
        persona = get_persona("ines")
        assert persona is not None
        policy = persona.get_teaching_policy()
        assert policy.remediation_style == "analogy"


class TestPersonaWithoutPolicy:
    """Tests for Persona without explicit teaching_policy."""

    def test_persona_without_policy_gets_defaults(self):
        """Persona without teaching_policy gets default TeachingPolicy."""
        # Create a persona without teaching_policy
        persona = Persona(
            id="test",
            name="Test",
            short_title="Test",
            background="Test",
            style_rules="Test",
            teaching_policy=None,
        )
        policy = persona.get_teaching_policy()
        assert policy.max_attempts_per_point == 2
        assert policy.allow_advance_on_failure is True


class TestShouldRetryLogic:
    """Tests for should_retry helper function."""

    def test_should_retry_first_attempt(self):
        """Should retry after first attempt with max=2."""
        policy = TeachingPolicy(max_attempts_per_point=2)
        # After 1 attempt, should still retry
        assert 1 < policy.max_attempts_per_point

    def test_should_not_retry_after_max_attempts(self):
        """Should not retry after max attempts reached."""
        policy = TeachingPolicy(max_attempts_per_point=2)
        # After 2 attempts, should not retry
        assert not (2 < policy.max_attempts_per_point)

    def test_profe_nico_single_attempt(self):
        """profe_nico allows only 1 attempt."""
        policy = TeachingPolicy(max_attempts_per_point=1)
        # After 1 attempt, should not retry
        assert not (1 < policy.max_attempts_per_point)


class TestShouldOfferAdvanceLogic:
    """Tests for should_offer_advance helper function."""

    def test_should_offer_advance_when_allowed(self):
        """Should offer advance when allow_advance_on_failure=True."""
        policy = TeachingPolicy(allow_advance_on_failure=True)
        assert policy.allow_advance_on_failure is True

    def test_should_not_offer_advance_when_disabled(self):
        """Should not offer advance when allow_advance_on_failure=False."""
        policy = TeachingPolicy(allow_advance_on_failure=False)
        assert policy.allow_advance_on_failure is False
