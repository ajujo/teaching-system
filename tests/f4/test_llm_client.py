"""Tests for LLM client module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from teaching.llm.client import (
    LLMClient,
    LLMConfig,
    LLMConnectionError,
    LLMError,
    LLMResponse,
    LLMResponseError,
    Message,
)


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LLMConfig()

        assert config.provider == "lmstudio"
        assert config.base_url == "http://localhost:1234/v1"
        assert config.model == "default"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout == 120

    def test_from_yaml_missing_file(self, tmp_path):
        """Test loading config when file doesn't exist."""
        config = LLMConfig.from_yaml(tmp_path / "nonexistent.yaml")

        # Should return defaults
        assert config.provider == "lmstudio"
        assert config.model == "default"

    def test_from_yaml_valid_file(self, tmp_path):
        """Test loading config from valid YAML file."""
        yaml_content = """
llm:
  provider: openai
  base_url: https://api.openai.com/v1
  model: gpt-4
  temperature: 0.5
  max_tokens: 2048
  timeout: 60
"""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml_content)

        # Mock env var for API key
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = LLMConfig.from_yaml(config_path)

        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.timeout == 60
        assert config.api_key == "test-key"


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_to_dict(self):
        """Test message serialization."""
        msg = Message(role="user", content="Hello, world!")

        assert msg.to_dict() == {
            "role": "user",
            "content": "Hello, world!",
        }

    def test_message_roles(self):
        """Test different message roles."""
        system = Message(role="system", content="System prompt")
        user = Message(role="user", content="User message")
        assistant = Message(role="assistant", content="Assistant response")

        assert system.role == "system"
        assert user.role == "user"
        assert assistant.role == "assistant"


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_response_properties(self):
        """Test response property accessors."""
        response = LLMResponse(
            content="Test content",
            model="gpt-4",
            provider="openai",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
            latency_ms=500,
        )

        assert response.content == "Test content"
        assert response.model == "gpt-4"
        assert response.provider == "openai"
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 20
        assert response.total_tokens == 30
        assert response.latency_ms == 500

    def test_response_empty_usage(self):
        """Test response with no usage data."""
        response = LLMResponse(
            content="Test",
            model="test",
            provider="lmstudio",
        )

        assert response.prompt_tokens == 0
        assert response.completion_tokens == 0
        assert response.total_tokens == 0


class TestLLMClientMocked:
    """Tests for LLMClient using mocks (no real API calls)."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        with patch("teaching.llm.client.OpenAI") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_client_initialization(self, mock_openai_client):
        """Test client initializes with config."""
        config = LLMConfig(
            provider="lmstudio",
            model="test-model",
        )
        client = LLMClient(config=config)

        assert client.config.provider == "lmstudio"
        assert client.config.model == "test-model"

    def test_client_provider_override(self, mock_openai_client):
        """Test provider can be overridden."""
        config = LLMConfig(provider="lmstudio")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            client = LLMClient(config=config, provider="openai")

        assert client.config.provider == "openai"

    def test_client_model_override(self, mock_openai_client):
        """Test model can be overridden."""
        config = LLMConfig(model="default")
        client = LLMClient(config=config, model="custom-model")

        assert client.config.model == "custom-model"

    def test_chat_success(self, mock_openai_client):
        """Test successful chat completion."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.model = "test-model"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig())
        messages = [
            Message(role="system", content="Be helpful"),
            Message(role="user", content="Hello"),
        ]

        response = client.chat(messages)

        assert response.content == "Test response"
        assert response.total_tokens == 30
        mock_openai_client.chat.completions.create.assert_called_once()

    def test_chat_empty_response(self, mock_openai_client):
        """Test handling of empty response."""
        mock_response = MagicMock()
        mock_response.choices = []  # Empty choices

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig())
        messages = [Message(role="user", content="Hello")]

        with pytest.raises(LLMResponseError, match="Respuesta vacía"):
            client.chat(messages)

    def test_chat_connection_error(self, mock_openai_client):
        """Test handling of connection error."""
        mock_openai_client.chat.completions.create.side_effect = Exception(
            "Connection refused"
        )

        client = LLMClient(config=LLMConfig())
        messages = [Message(role="user", content="Hello")]

        with pytest.raises(LLMConnectionError, match="No se pudo conectar"):
            client.chat(messages)

    def test_chat_json_success(self, mock_openai_client):
        """Test chat_json parses JSON response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"key": "value", "number": 42}'
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig())
        messages = [Message(role="user", content="Give me JSON")]

        result = client.chat_json(messages)

        assert result == {"key": "value", "number": 42}

    def test_chat_json_extracts_from_text(self, mock_openai_client):
        """Test chat_json can extract JSON from surrounding text."""
        mock_response = MagicMock()
        # JSON embedded in text
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            'Here is the result:\n{"data": "test"}\nEnd of response.'
        )
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig())
        messages = [Message(role="user", content="Give me JSON")]

        result = client.chat_json(messages)

        assert result == {"data": "test"}

    def test_chat_json_invalid(self, mock_openai_client):
        """Test chat_json raises error for invalid JSON."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Not valid JSON at all"
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig())
        messages = [Message(role="user", content="Give me JSON")]

        with pytest.raises(LLMResponseError, match="No se pudo obtener JSON válido"):
            client.chat_json(messages)

    def test_simple_chat(self, mock_openai_client):
        """Test simple_chat convenience method."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello there!"
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig())

        result = client.simple_chat(
            system_prompt="Be friendly",
            user_message="Hi!",
        )

        assert result == "Hello there!"

    def test_simple_json(self, mock_openai_client):
        """Test simple_json convenience method."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"greeting": "hello"}'
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig())

        result = client.simple_json(
            system_prompt="Return JSON",
            user_message="Give greeting",
        )

        assert result == {"greeting": "hello"}

    def test_is_available_true(self, mock_openai_client):
        """Test is_available when server responds."""
        mock_openai_client.models.list.return_value = []

        client = LLMClient(config=LLMConfig())

        assert client.is_available() is True

    def test_is_available_false(self, mock_openai_client):
        """Test is_available when server doesn't respond."""
        mock_openai_client.models.list.side_effect = Exception("Connection refused")

        client = LLMClient(config=LLMConfig())

        assert client.is_available() is False


class TestLMStudioCompatibility:
    """Tests for LM Studio compatibility (no response_format json_object)."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        with patch("teaching.llm.client.OpenAI") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance

    def test_chat_no_response_format_for_lmstudio(self, mock_openai_client):
        """LM Studio should NOT receive response_format json_object."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig(provider="lmstudio"))
        messages = [Message(role="user", content="test")]

        client.chat(messages, json_mode=True)

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        # Should NOT have response_format for lmstudio
        assert "response_format" not in call_kwargs

    def test_chat_has_response_format_for_openai(self, mock_openai_client):
        """OpenAI should receive response_format json_object."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_response.model = "gpt-4"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig(provider="openai"))
        messages = [Message(role="user", content="test")]

        client.chat(messages, json_mode=True)

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        # Should have response_format for openai
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"]["type"] == "json_object"

    def test_chat_json_extracts_from_markdown_block(self, mock_openai_client):
        """Should extract JSON from ```json ... ``` blocks."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''
Aquí está el resultado:
```json
{"key": "value", "number": 42}
```
Fin de la respuesta.
'''
        mock_response.model = "test-model"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig(provider="lmstudio"))
        result = client.chat_json([Message(role="user", content="test")])

        assert result == {"key": "value", "number": 42}

    def test_chat_json_retry_on_invalid_json(self, mock_openai_client):
        """Should retry with repair prompt if JSON is invalid."""
        # First response: invalid JSON
        bad_response = MagicMock()
        bad_response.choices = [MagicMock()]
        bad_response.choices[0].message.content = "This is not valid JSON at all"
        bad_response.model = "test"
        bad_response.usage = MagicMock()
        bad_response.usage.prompt_tokens = 10
        bad_response.usage.completion_tokens = 5
        bad_response.usage.total_tokens = 15

        # Second response: valid JSON
        good_response = MagicMock()
        good_response.choices = [MagicMock()]
        good_response.choices[0].message.content = '{"fixed": true, "value": 123}'
        good_response.model = "test"
        good_response.usage = MagicMock()
        good_response.usage.prompt_tokens = 15
        good_response.usage.completion_tokens = 8
        good_response.usage.total_tokens = 23

        mock_openai_client.chat.completions.create.side_effect = [bad_response, good_response]

        client = LLMClient(config=LLMConfig(provider="lmstudio"))
        result = client.chat_json([Message(role="user", content="test")])

        assert result == {"fixed": True, "value": 123}
        assert mock_openai_client.chat.completions.create.call_count == 2

    def test_chat_json_retry_includes_invalid_output_in_prompt(self, mock_openai_client):
        """Retry prompt should include the invalid output for correction."""
        bad_response = MagicMock()
        bad_response.choices = [MagicMock()]
        bad_response.choices[0].message.content = "Invalid output here"
        bad_response.model = "test"
        bad_response.usage = MagicMock()
        bad_response.usage.prompt_tokens = 10
        bad_response.usage.completion_tokens = 5
        bad_response.usage.total_tokens = 15

        good_response = MagicMock()
        good_response.choices = [MagicMock()]
        good_response.choices[0].message.content = '{"corrected": true}'
        good_response.model = "test"
        good_response.usage = MagicMock()
        good_response.usage.prompt_tokens = 15
        good_response.usage.completion_tokens = 5
        good_response.usage.total_tokens = 20

        mock_openai_client.chat.completions.create.side_effect = [bad_response, good_response]

        client = LLMClient(config=LLMConfig(provider="lmstudio"))
        client.chat_json([Message(role="user", content="original request")])

        # Check that the retry call includes the invalid output
        second_call = mock_openai_client.chat.completions.create.call_args_list[1]
        messages = second_call.kwargs["messages"]

        # Should have an extra user message with repair prompt containing invalid output
        repair_message = messages[-1]
        assert repair_message["role"] == "user"
        assert "Invalid output here" in repair_message["content"]

    def test_chat_json_fails_after_max_retries(self, mock_openai_client):
        """Should raise error after max retries exhausted."""
        bad_response = MagicMock()
        bad_response.choices = [MagicMock()]
        bad_response.choices[0].message.content = "Still not valid JSON"
        bad_response.model = "test"
        bad_response.usage = MagicMock()
        bad_response.usage.prompt_tokens = 10
        bad_response.usage.completion_tokens = 5
        bad_response.usage.total_tokens = 15

        mock_openai_client.chat.completions.create.return_value = bad_response

        client = LLMClient(config=LLMConfig(provider="lmstudio"))

        with pytest.raises(LLMResponseError, match="No se pudo obtener JSON válido"):
            client.chat_json([Message(role="user", content="test")], max_retries=1)

    def test_supports_json_object_config_override(self, mock_openai_client):
        """Config override should take precedence over provider defaults."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"test": true}'
        mock_response.model = "test"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_openai_client.chat.completions.create.return_value = mock_response

        # LMStudio with override to support json_object
        config = LLMConfig(provider="lmstudio", supports_json_object=True)
        client = LLMClient(config=config)
        client.chat([Message(role="user", content="test")], json_mode=True)

        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        # Should have response_format because of override
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"]["type"] == "json_object"

    def test_try_parse_json_removes_think_tags(self, mock_openai_client):
        """JSON parsing should work even with <think> tags in content."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """<think>
Let me analyze this request...
I should return a JSON object.
</think>
{"key": "value", "number": 42}"""
        mock_response.model = "test"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig(provider="lmstudio"))
        result = client.chat_json([Message(role="user", content="test")])

        assert result == {"key": "value", "number": 42}

    def test_try_parse_json_removes_think_around_json_block(self, mock_openai_client):
        """JSON extraction works when think tags surround a json markdown block."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """<think>Processing the request</think>
Here's the result:
```json
{"success": true}
```
<think>Done!</think>"""
        mock_response.model = "test"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_openai_client.chat.completions.create.return_value = mock_response

        client = LLMClient(config=LLMConfig(provider="lmstudio"))
        result = client.chat_json([Message(role="user", content="test")])

        assert result == {"success": True}
