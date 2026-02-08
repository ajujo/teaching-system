"""Configuration package for teaching system."""

from teaching.config.app_config import (
    AppConfig,
    ProviderConfig,
    TutorConfig,
    get_provider_config,
    load_app_config,
)
from teaching.config.personas import (
    Persona,
    get_default_persona,
    get_persona,
    list_personas,
    load_personas,
)

__all__ = [
    "AppConfig",
    "ProviderConfig",
    "TutorConfig",
    "get_provider_config",
    "load_app_config",
    "Persona",
    "get_default_persona",
    "get_persona",
    "list_personas",
    "load_personas",
]
