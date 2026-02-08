"""Application configuration loader.

Loads centralized configuration from data/config/app_config_v1.yaml
with fallback to legacy configs/models.yaml format.

Usage:
    from teaching.config.app_config import load_app_config, get_provider_config

    config = load_app_config()
    provider = get_provider_config("lmstudio")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)

# Config file paths (relative to project root)
CONFIG_FILE = Path("data/config/app_config_v1.yaml")
LEGACY_CONFIG = Path("configs/models.yaml")


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""

    base_url: str | None
    default_model: str
    api_key_env: str | None = None

    def get_api_key(self) -> str | None:
        """Get API key from environment variable."""
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        return None


@dataclass
class TutorConfig:
    """Configuration for tutor defaults."""

    default_provider: str = "lmstudio"
    default_persona: str = "dra_vega"
    max_retries: int = 3


@dataclass
class AppConfig:
    """Application-wide configuration."""

    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    tutor: TutorConfig = field(default_factory=TutorConfig)
    paths: dict[str, str] = field(default_factory=dict)


# Module-level cache
_cached_config: AppConfig | None = None


def _get_defaults() -> dict[str, Any]:
    """Get default configuration values."""
    return {
        "providers": {
            "lmstudio": {
                "base_url": "http://localhost:1234/v1",
                "default_model": "llama-3.2-3b-instruct",
                "api_key_env": None,
            },
            "openai": {
                "base_url": None,
                "default_model": "gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY",
            },
            "anthropic": {
                "base_url": None,
                "default_model": "claude-sonnet-4-20250514",
                "api_key_env": "ANTHROPIC_API_KEY",
            },
        },
        "tutor": {
            "default_provider": "lmstudio",
            "default_persona": "dra_vega",
            "max_retries": 3,
        },
        "paths": {
            "state_dir": "data/state",
            "config_dir": "data/config",
            "prompts_dir": "prompts",
        },
    }


def _convert_legacy_config(legacy: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy configs/models.yaml to new format."""
    result = _get_defaults()

    # Extract provider info from legacy format
    if "provider" in legacy:
        provider = legacy["provider"]
        if provider in result["providers"]:
            result["tutor"]["default_provider"] = provider

    if "base_url" in legacy:
        provider = legacy.get("provider", "lmstudio")
        if provider in result["providers"]:
            result["providers"][provider]["base_url"] = legacy["base_url"]

    if "model" in legacy:
        provider = legacy.get("provider", "lmstudio")
        if provider in result["providers"]:
            result["providers"][provider]["default_model"] = legacy["model"]

    return result


def _parse_config(data: dict[str, Any]) -> AppConfig:
    """Parse configuration dictionary into AppConfig object."""
    providers = {}
    for name, pconfig in data.get("providers", {}).items():
        providers[name] = ProviderConfig(
            base_url=pconfig.get("base_url"),
            default_model=pconfig.get("default_model", "default"),
            api_key_env=pconfig.get("api_key_env"),
        )

    tutor_data = data.get("tutor", {})
    tutor = TutorConfig(
        default_provider=tutor_data.get("default_provider", "lmstudio"),
        default_persona=tutor_data.get("default_persona", "dra_vega"),
        max_retries=tutor_data.get("max_retries", 3),
    )

    paths = data.get("paths", {})

    return AppConfig(providers=providers, tutor=tutor, paths=paths)


def load_app_config(force_reload: bool = False) -> AppConfig:
    """Load application config with fallback to legacy.

    Args:
        force_reload: If True, ignore cached config and reload from file.

    Returns:
        AppConfig object with all settings.
    """
    global _cached_config

    if _cached_config is not None and not force_reload:
        return _cached_config

    data: dict[str, Any]

    if CONFIG_FILE.exists():
        logger.debug("loading_app_config", source=str(CONFIG_FILE))
        data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    elif LEGACY_CONFIG.exists():
        logger.info("loading_legacy_config", source=str(LEGACY_CONFIG))
        legacy = yaml.safe_load(LEGACY_CONFIG.read_text(encoding="utf-8"))
        data = _convert_legacy_config(legacy)
    else:
        logger.info("using_default_config")
        data = _get_defaults()

    _cached_config = _parse_config(data)
    return _cached_config


def get_provider_config(provider: str) -> ProviderConfig | None:
    """Get configuration for a specific provider.

    Args:
        provider: Provider name (e.g., "lmstudio", "openai")

    Returns:
        ProviderConfig or None if provider not found.
    """
    config = load_app_config()
    return config.providers.get(provider)


def clear_config_cache() -> None:
    """Clear the configuration cache.

    Useful for testing or when config is modified at runtime.
    """
    global _cached_config
    _cached_config = None
