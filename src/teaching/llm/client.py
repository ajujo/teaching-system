"""LLM client for LM Studio / Cloud providers.

Provides a unified interface for LLM interactions,
compatible with LM Studio local server and cloud providers.

Supported providers:
- lmstudio: Local LM Studio server (OpenAI-compatible API)
- openai: OpenAI API
- anthropic: Anthropic API (via OpenAI-compatible endpoint)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Literal

import structlog
import yaml
from openai import OpenAI

logger = structlog.get_logger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

Provider = Literal["lmstudio", "openai", "anthropic"]

DEFAULT_CONFIG_PATH = Path("configs/models.yaml")

# Provider-specific defaults
PROVIDER_DEFAULTS: dict[Provider, dict[str, Any]] = {
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "api_key": "lm-studio",  # LM Studio doesn't need real API key
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
}

# Provider capabilities (configurable via YAML)
# Default: lmstudio no soporta json_object, openai sí
PROVIDER_CAPABILITIES_DEFAULTS: dict[Provider, dict[str, bool]] = {
    "lmstudio": {
        "supports_json_object": False,  # NO soporta {"type": "json_object"}
    },
    "openai": {
        "supports_json_object": True,  # Soporta json_object nativo
    },
    "anthropic": {
        "supports_json_object": False,  # No usa response_format de OpenAI
    },
}

# JSON repair prompt template
JSON_REPAIR_PROMPT = """Corrige y devuelve SOLO JSON válido a partir de este texto:
<<<
{invalid_output}
>>>

Responde ÚNICAMENTE con el JSON corregido, sin explicaciones ni markdown."""

# Patterns to sanitize from LLM output (thinking tags, etc.)
# Some models emit <think>...</think> blocks that can interfere with JSON parsing
SANITIZE_PATTERNS = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<analysis>.*?</analysis>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE),
]


def _sanitize_for_json(text: str) -> str:
    """Remove thinking/reasoning tags before JSON parsing.

    Some models emit <think>...</think> blocks that can interfere
    with JSON extraction. This removes them before parsing.
    """
    result = text
    for pattern in SANITIZE_PATTERNS:
        result = pattern.sub("", result)
    return result.strip()


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class LLMConfig:
    """Configuration for LLM client."""

    provider: Provider = "lmstudio"
    base_url: str = "http://localhost:1234/v1"
    model: str = "default"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 120
    api_key: str | None = None
    # Capability override (from config)
    supports_json_object: bool | None = None

    @classmethod
    def from_yaml(cls, config_path: Path | None = None) -> LLMConfig:
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = DEFAULT_CONFIG_PATH

        if not config_path.exists():
            logger.warning("config_not_found", path=str(config_path))
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f)

        llm_config = data.get("llm", {})

        provider = llm_config.get("provider", "lmstudio")
        defaults = PROVIDER_DEFAULTS.get(provider, {})

        # Get API key from environment if needed
        api_key = None
        if "api_key_env" in defaults:
            api_key = os.environ.get(defaults["api_key_env"])
        elif "api_key" in defaults:
            api_key = defaults["api_key"]

        # Check for capability override in config
        supports_json_object = llm_config.get("supports_json_object", None)

        return cls(
            provider=provider,
            base_url=llm_config.get("base_url", defaults.get("base_url", "")),
            model=llm_config.get("model", "default"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 4096),
            timeout=llm_config.get("timeout", 120),
            api_key=api_key,
            supports_json_object=supports_json_object,
        )


@dataclass
class Message:
    """A chat message."""

    role: Literal["system", "user", "assistant"]
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for API call."""
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """Response from LLM."""

    content: str
    model: str
    provider: Provider
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0

    @property
    def prompt_tokens(self) -> int:
        """Get prompt token count."""
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        """Get completion token count."""
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        """Get total token count."""
        return self.usage.get("total_tokens", 0)


class LLMError(Exception):
    """Error during LLM interaction."""

    pass


class LLMConnectionError(LLMError):
    """Error connecting to LLM server."""

    pass


class LLMResponseError(LLMError):
    """Error in LLM response."""

    pass


# =============================================================================
# LLM CLIENT
# =============================================================================


class LLMClient:
    """Unified client for LLM interactions.

    Supports LM Studio, OpenAI, and Anthropic via OpenAI-compatible API.
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        provider: Provider | None = None,
        model: str | None = None,
    ):
        """Initialize LLM client.

        Args:
            config: LLM configuration (loads from YAML if not provided)
            provider: Override provider from config
            model: Override model from config
        """
        if config is None:
            config = LLMConfig.from_yaml()

        self.config = config

        # Allow overrides
        if provider is not None:
            self.config.provider = provider
            # Update defaults for new provider
            defaults = PROVIDER_DEFAULTS.get(provider, {})
            if "base_url" in defaults:
                self.config.base_url = defaults["base_url"]
            if "api_key_env" in defaults:
                self.config.api_key = os.environ.get(defaults["api_key_env"])
            elif "api_key" in defaults:
                self.config.api_key = defaults["api_key"]

        if model is not None:
            self.config.model = model

        # Initialize OpenAI client
        self._client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key or "not-needed",
            timeout=self.config.timeout,
        )

        logger.info(
            "llm_client_initialized",
            provider=self.config.provider,
            model=self.config.model,
            base_url=self.config.base_url,
        )

    def _supports_json_object(self) -> bool:
        """Check if current provider supports response_format json_object.

        Uses config override if set, otherwise falls back to provider defaults.
        """
        # Config override takes precedence
        if self.config.supports_json_object is not None:
            return self.config.supports_json_object

        # Fall back to provider defaults
        caps = PROVIDER_CAPABILITIES_DEFAULTS.get(self.config.provider, {})
        return caps.get("supports_json_object", False)

    def chat(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Send chat completion request.

        Args:
            messages: List of messages in conversation
            temperature: Override default temperature
            max_tokens: Override default max tokens
            json_mode: Request JSON response format (only if provider supports it)

        Returns:
            LLMResponse with content and metadata

        Raises:
            LLMConnectionError: If cannot connect to server
            LLMResponseError: If response is invalid
        """
        if temperature is None:
            temperature = self.config.temperature
        if max_tokens is None:
            max_tokens = self.config.max_tokens

        # Build request
        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Only add response_format if provider supports it
        if json_mode and self._supports_json_object():
            request_kwargs["response_format"] = {"type": "json_object"}

        # Make request with timing
        start_time = time.time()

        try:
            response = self._client.chat.completions.create(**request_kwargs)
        except Exception as e:
            error_msg = str(e)
            if "Connection" in error_msg or "connect" in error_msg.lower():
                raise LLMConnectionError(
                    f"No se pudo conectar a {self.config.provider} en {self.config.base_url}: {e}"
                ) from e
            raise LLMError(f"Error en llamada LLM: {e}") from e

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract response
        if not response.choices:
            raise LLMResponseError("Respuesta vacía del LLM")

        content = response.choices[0].message.content or ""

        # Extract usage
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        logger.debug(
            "llm_response",
            provider=self.config.provider,
            model=response.model,
            tokens=usage.get("total_tokens", 0),
            latency_ms=latency_ms,
        )

        return LLMResponse(
            content=content,
            model=response.model,
            provider=self.config.provider,
            usage=usage,
            latency_ms=latency_ms,
        )

    def chat_stream(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Send chat completion request with streaming.

        Yields content chunks as they arrive from the LLM.
        Falls back to non-streaming on error.

        Args:
            messages: List of messages in conversation
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Yields:
            Content chunks as strings
        """
        if temperature is None:
            temperature = self.config.temperature
        if max_tokens is None:
            max_tokens = self.config.max_tokens

        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            stream = self._client.chat.completions.create(**request_kwargs)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            # Fall back to non-streaming on error
            logger.warning("streaming_failed_fallback", error=str(e))
            try:
                response = self.chat(messages, temperature, max_tokens)
                yield response.content
            except Exception as fallback_error:
                logger.error("streaming_fallback_failed", error=str(fallback_error))
                yield f"[Error: {fallback_error}]"

    def simple_chat_stream(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Simple streaming chat with system prompt and user message.

        Convenience wrapper for chat_stream with standard message format.

        Args:
            system_prompt: System message content
            user_message: User message content
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Yields:
            Content chunks as strings
        """
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message),
        ]
        yield from self.chat_stream(messages, temperature, max_tokens)

    def _try_parse_json(self, content: str) -> dict[str, Any] | None:
        """Try to parse JSON from content, with multiple extraction strategies.

        Tries:
        1. Direct parse
        2. Extract from ```json ... ``` blocks
        3. Extract first {...} object

        Also sanitizes thinking tags (<think>, etc.) before parsing.

        Returns parsed dict or None if all strategies fail.
        """
        # Sanitize thinking tags that some models emit
        content = _sanitize_for_json(content)

        # 1. Direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 2. Extract from markdown ```json ... ``` blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 3. Extract first {...} object
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass

        return None

    def chat_json(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """Send chat request expecting JSON response.

        Uses robust parsing with retry on failure.

        Args:
            messages: List of messages
            temperature: Override temperature
            max_tokens: Override max tokens
            max_retries: Number of retry attempts on parse failure

        Returns:
            Parsed JSON as dictionary

        Raises:
            LLMResponseError: If response is not valid JSON after retries
        """
        # First attempt
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        # Try to parse
        parsed = self._try_parse_json(response.content)
        if parsed is not None:
            return parsed

        # Retry with repair prompt
        if max_retries > 0:
            logger.warning(
                "json_parse_failed_retrying",
                content=response.content[:100],
                provider=self.config.provider,
            )

            # Build repair prompt with invalid output embedded
            repair_prompt = JSON_REPAIR_PROMPT.format(
                invalid_output=response.content[:1000]  # Limit size
            )

            retry_messages = messages + [
                Message(role="user", content=repair_prompt),
            ]

            retry_response = self.chat(
                retry_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )

            parsed = self._try_parse_json(retry_response.content)
            if parsed is not None:
                logger.info("json_parse_recovered_after_retry")
                return parsed

        # Final failure
        raise LLMResponseError(
            f"No se pudo obtener JSON válido: {response.content[:200]}..."
        )

    def simple_chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Simple chat with system prompt and user message.

        Convenience method for single-turn conversations.

        Args:
            system_prompt: System prompt
            user_message: User message
            temperature: Override temperature
            max_tokens: Override max tokens

        Returns:
            Response content as string
        """
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message),
        ]

        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.content

    def simple_json(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Simple chat expecting JSON response.

        Convenience method for single-turn JSON conversations.

        Args:
            system_prompt: System prompt
            user_message: User message
            temperature: Override temperature
            max_tokens: Override max tokens

        Returns:
            Parsed JSON as dictionary
        """
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message),
        ]

        return self.chat_json(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def is_available(self) -> bool:
        """Check if LLM server is available.

        Returns:
            True if server responds, False otherwise
        """
        try:
            # Try a minimal request
            self._client.models.list()
            return True
        except Exception:
            return False
