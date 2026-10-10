"""
LLM Client Tests
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm.llm_client import (
    BaseLLMClient,
    LLMClientFactory,
    LLMProvider,
    LLMResponse,
    LLMError,
    OpenAIClient,
    AnthropicClient,
    GeminiClient,
    get_llm_client,
    close_llm_client,
)
from app.config import Settings


class TestLLMProvider:
    """Tests for LLM provider enum."""

    def test_provider_values(self):
        """Test provider enum values."""
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.GEMINI.value == "gemini"

    def test_provider_from_string(self):
        """Test creating provider from string."""
        assert LLMProvider("openai") == LLMProvider.OPENAI
        assert LLMProvider("anthropic") == LLMProvider.ANTHROPIC
        assert LLMProvider("gemini") == LLMProvider.GEMINI


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_llm_response_creation(self):
        """Test creating LLMResponse."""
        response = LLMResponse(
            content="Test response",
            model="gpt-4o-mini",
            provider=LLMProvider.OPENAI,
            usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            request_id="req-123",
        )

        assert response.content == "Test response"
        assert response.provider == LLMProvider.OPENAI
        assert response.usage["total_tokens"] == 30


class TestLLMError:
    """Tests for LLMError."""

    def test_llm_error_creation(self):
        """Test creating LLMError."""
        error = LLMError(
            message="Rate limited",
            code="RATE_LIMIT",
            provider=LLMProvider.OPENAI,
            status_code=429,
            retryable=True,
        )

        assert error.message == "Rate limited"
        assert error.retryable is True
        assert "RATE_LIMIT" in str(error)


class TestLLMClientFactory:
    """Tests for LLM client factory."""

    def test_create_openai_client(self):
        """Test creating OpenAI client."""
        client = LLMClientFactory.create(
            provider="openai",
            api_key="test-key",
            model="gpt-4o-mini",
        )
        assert isinstance(client, OpenAIClient)
        assert client.model == "gpt-4o-mini"

    def test_create_anthropic_client(self):
        """Test creating Anthropic client."""
        client = LLMClientFactory.create(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-haiku-20240307",
        )
        assert isinstance(client, AnthropicClient)
        assert client.model == "claude-3-haiku-20240307"

    def test_create_gemini_client(self):
        """Test creating Gemini client."""
        client = LLMClientFactory.create(
            provider="gemini",
            api_key="test-key",
            model="gemini-1.5-flash",
        )
        assert isinstance(client, GeminiClient)
        assert client.model == "gemini-1.5-flash"

    def test_create_invalid_provider(self):
        """Test creating client with invalid provider raises error."""
        with pytest.raises(ValueError) as exc:
            LLMClientFactory.create(
                provider="invalid",
                api_key="test-key",
                model="test-model",
            )
        assert "Unsupported LLM provider" in str(exc.value)

    def test_create_case_insensitive(self):
        """Test provider name is case insensitive."""
        client = LLMClientFactory.create(
            provider="OPENAI",
            api_key="test-key",
            model="gpt-4o-mini",
        )
        assert isinstance(client, OpenAIClient)


class TestOpenAIClient:
    """Tests for OpenAI client (mocked)."""

    @pytest.fixture
    def client(self):
        """Create OpenAI client with test config."""
        return OpenAIClient(
            api_key="test-key",
            model="gpt-4o-mini",
            timeout=5.0,
        )

    def test_format_messages_with_system(self, client):
        """Test formatting messages with system prompt."""
        messages = client._format_messages(
            system_prompt="You are helpful",
            user_prompt="Hello",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_format_messages_without_system(self, client):
        """Test formatting messages without system prompt."""
        messages = client._format_messages(
            system_prompt=None,
            user_prompt="Hello",
        )
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_complete_success(self, client):
        """Test successful completion."""
        response_data = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"content": "Hello there!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": "gpt-4o-mini",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(side_effect=[response_data, response_data])
        client.client.post = AsyncMock(return_value=mock_response)

        response = await client.complete("Hello")

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello there!"
        assert response.provider == LLMProvider.OPENAI

    @pytest.mark.asyncio
    async def test_complete_auth_error(self, client):
        """Test authentication error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json = AsyncMock(return_value={"error": {"message": "Invalid API key"}})
        client.client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(LLMError) as exc:
            await client.complete("Hello")

        assert exc.value.code == "AUTHENTICATION_ERROR"
        assert exc.value.retryable is False

    @pytest.mark.asyncio
    async def test_complete_rate_limit(self, client):
        """Test rate limit error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json = AsyncMock(return_value={"error": {"message": "Rate limit exceeded"}})
        client.client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(LLMError) as exc:
            await client.complete("Hello")

        assert exc.value.code == "RATE_LIMIT"
        assert exc.value.retryable is True

    @pytest.mark.asyncio
    async def test_complete_timeout(self, client):
        """Test timeout handling."""
        import httpx
        client.client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(LLMError) as exc:
            await client.complete("Hello")

        assert exc.value.code == "TIMEOUT"
        assert exc.value.retryable is True

    @pytest.mark.asyncio
    async def test_complete_connection_error(self, client):
        """Test connection error handling."""
        import httpx
        client.client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        with pytest.raises(LLMError) as exc:
            await client.complete("Hello")

        assert exc.value.code == "CONNECTION_ERROR"
        assert exc.value.retryable is True


class TestAnthropicClient:
    """Tests for Anthropic client (mocked)."""

    @pytest.fixture
    def client(self):
        """Create Anthropic client with test config."""
        return AnthropicClient(
            api_key="test-key",
            model="claude-3-haiku-20240307",
            timeout=5.0,
        )

    def test_format_messages(self, client):
        """Test formatting messages for Anthropic."""
        messages = client._format_messages(
            system_prompt="You are helpful",
            user_prompt="Hello",
        )
        # Anthropic combines system + user into one message
        assert len(messages) == 1
        assert "You are helpful" in messages[0]["content"]
        assert "Hello" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_complete_success(self, client):
        """Test successful completion."""
        response_data = {
            "id": "msg_123",
            "content": [{"text": "Hello there!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "model": "claude-3-haiku-20240307",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(side_effect=[response_data, response_data])
        client.client.post = AsyncMock(return_value=mock_response)

        response = await client.complete("Hello")

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello there!"
        assert response.provider == LLMProvider.ANTHROPIC


class TestGeminiClient:
    """Tests for Gemini client (mocked)."""

    @pytest.fixture
    def client(self):
        """Create Gemini client with test config."""
        return GeminiClient(
            api_key="test-key",
            model="gemini-1.5-flash",
            timeout=5.0,
        )

    def test_format_messages(self, client):
        """Test formatting messages for Gemini."""
        messages = client._format_messages(
            system_prompt="You are helpful",
            user_prompt="Hello",
        )
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "You are helpful" in messages[0]["parts"][0]["text"]
        assert "Hello" in messages[0]["parts"][0]["text"]

    @pytest.mark.asyncio
    async def test_complete_success(self, client):
        """Test successful completion."""
        response_data = {
            "candidates": [{"content": {"parts": [{"text": "Hello there!"}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(side_effect=[response_data, response_data])
        client.client.post = AsyncMock(return_value=mock_response)

        response = await client.complete("Hello")

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello there!"
        assert response.provider == LLMProvider.GEMINI

    @pytest.mark.asyncio
    async def test_complete_invalid_key(self, client):
        """Test invalid API key handling."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json = AsyncMock(return_value={
            "error": {"message": "API_KEY_INVALID"}
        })
        client.client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(LLMError) as exc:
            await client.complete("Hello")

        assert exc.value.code == "AUTHENTICATION_ERROR"
        assert exc.value.retryable is False


class TestGlobalLLMClient:
    """Tests for global LLM client management."""

    def test_get_llm_client_not_configured(self):
        """Test getting client when not configured raises error."""
        # Mock settings without LLM config
        with patch("app.services.llm.llm_client.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                llm_provider=None,
                llm_api_key=None,
                llm_model=None,
            )
            with pytest.raises(ValueError) as exc:
                get_llm_client()
            assert "LLM not configured" in str(exc.value)

    @pytest.mark.asyncio
    async def test_close_llm_client(self):
        """Test closing global client."""
        mock_client = AsyncMock()
        with patch("app.services.llm.llm_client._global_client", mock_client):
            await close_llm_client()
            mock_client.close.assert_called_once()