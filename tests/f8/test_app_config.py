"""Tests for app configuration (F8).

Tests the configuration loading, provider configs, and fallbacks.
"""

import pytest
from pathlib import Path

from teaching.config.app_config import (
    AppConfig,
    ProviderConfig,
    TutorConfig,
    load_app_config,
    get_provider_config,
    clear_config_cache,
    CONFIG_FILE,
)


class TestLoadAppConfig:
    """Tests for load_app_config function."""

    def test_load_config_from_yaml(self):
        """Loads config from app_config_v1.yaml."""
        clear_config_cache()
        config = load_app_config()
        assert isinstance(config, AppConfig)

    def test_config_has_providers(self):
        """Config includes provider settings."""
        config = load_app_config()
        assert len(config.providers) > 0
        assert "lmstudio" in config.providers

    def test_config_has_tutor_settings(self):
        """Config includes tutor defaults."""
        config = load_app_config()
        assert isinstance(config.tutor, TutorConfig)
        assert config.tutor.default_provider
        assert config.tutor.default_persona

    def test_config_has_paths(self):
        """Config includes path settings."""
        config = load_app_config()
        assert isinstance(config.paths, dict)


class TestGetProviderConfig:
    """Tests for get_provider_config function."""

    def test_get_provider_config_lmstudio(self):
        """Returns ProviderConfig for lmstudio."""
        config = get_provider_config("lmstudio")
        assert config is not None
        assert isinstance(config, ProviderConfig)
        assert config.base_url is not None

    def test_get_provider_config_openai(self):
        """Returns ProviderConfig for openai."""
        config = get_provider_config("openai")
        assert config is not None
        assert config.api_key_env == "OPENAI_API_KEY"

    def test_get_provider_config_unknown(self):
        """Returns None for unknown provider."""
        config = get_provider_config("unknown_provider")
        assert config is None


class TestProviderConfig:
    """Tests for ProviderConfig dataclass."""

    def test_provider_config_has_model(self):
        """Each provider has a default model."""
        for provider in ["lmstudio", "openai", "anthropic"]:
            config = get_provider_config(provider)
            if config:
                assert config.default_model is not None
                assert len(config.default_model) > 0

    def test_provider_get_api_key_no_env(self):
        """get_api_key returns None when env not set."""
        config = get_provider_config("lmstudio")
        # lmstudio doesn't require API key
        if config and config.api_key_env is None:
            assert config.get_api_key() is None


class TestTutorConfig:
    """Tests for TutorConfig defaults."""

    def test_tutor_default_provider(self):
        """Tutor has default provider."""
        config = load_app_config()
        assert config.tutor.default_provider == "lmstudio"

    def test_tutor_default_persona(self):
        """Tutor has default persona."""
        config = load_app_config()
        assert config.tutor.default_persona == "dra_vega"

    def test_tutor_max_retries(self):
        """Tutor has max_retries setting."""
        config = load_app_config()
        assert config.tutor.max_retries >= 1


class TestConfigFile:
    """Tests for config file existence."""

    def test_config_file_exists(self):
        """Config file exists."""
        assert CONFIG_FILE.exists(), f"Missing: {CONFIG_FILE}"
