"""
LLM Client Service

Unified interface for LLM providers (OpenAI, Anthropic, Google Gemini).
Handles authentication, retries, timeouts, and error handling.
"""
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    model: str
    provider: LLMProvider
    usage: dict[str, int]  # input_tokens, output_tokens, total_tokens
    request_id: str
    raw_response: Optional[dict] = None


@dataclass
class LLMError(Exception):
    """LLM client error with provider-specific details."""
    message: str
    code: str
    provider: Optional[LLMProvider] = None
    status_code: Optional[int] = None
    retryable: bool = False
    details: Optional[dict] = None

    def __str__(self) -> str:
        return f"[{self.provider or 'unknown'}] {self.code}: {self.message}"


class BaseLLMClient(ABC):
    """Abstract base class for LLM provider clients."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=timeout)

    @abstractmethod
    async def _make_request(
        self,
        messages: list[dict[str, str]],
        **kwargs,
    ) -> LLMResponse:
        """Make a request to the provider's API."""
        pass

    @abstractmethod
    def _format_messages(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
    ) -> list[dict[str, str]]:
        """Format messages for the provider's API."""
        pass

    async def complete(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        """
        Generate a completion.

        Args:
            user_prompt: User message
            system_prompt: Optional system message
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            LLMResponse with content and metadata

        Raises:
            LLMError: On API errors, timeouts, or authentication failures
        """
        messages = self._format_messages(system_prompt, user_prompt)

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self._make_request(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
            except LLMError as e:
                last_error = e
                if not e.retryable or attempt == self.max_retries:
                    raise

                # Exponential backoff
                wait_time = (2**attempt) * 1.0
                logger.warning(
                    f"LLM request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            except Exception as e:
                logger.exception("Unexpected error in LLM request")
                raise LLMError(
                    message=f"Unexpected error: {e}",
                    code="UNEXPECTED_ERROR",
                    provider=self.provider,
                    retryable=False,
                )

        # Should not reach here, but just in case
        raise last_error or LLMError(
            message="Max retries exceeded",
            code="MAX_RETRIES_EXCEEDED",
            provider=self.provider,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    @property
    @abstractmethod
    def provider(self) -> LLMProvider:
        """Return the provider enum."""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""

    BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
        max_retries: int = 2,
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key, model, timeout, max_retries)
        self.base_url = base_url or self.BASE_URL

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OPENAI

    def _format_messages(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
    ) -> list[dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def _make_request(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException:
            raise LLMError(
                message="Request timed out",
                code="TIMEOUT",
                provider=self.provider,
                retryable=True,
            )
        except httpx.ConnectError:
            raise LLMError(
                message="Failed to connect to OpenAI API",
                code="CONNECTION_ERROR",
                provider=self.provider,
                retryable=True,
            )

        if response.status_code == 401:
            raise LLMError(
                message="Invalid API key",
                code="AUTHENTICATION_ERROR",
                provider=self.provider,
                status_code=401,
                retryable=False,
            )
        elif response.status_code == 429:
            raise LLMError(
                message="Rate limit exceeded",
                code="RATE_LIMIT",
                provider=self.provider,
                status_code=429,
                retryable=True,
            )
        elif response.status_code >= 500:
            raise LLMError(
                message=f"OpenAI server error: {response.status_code}",
                code="SERVER_ERROR",
                provider=self.provider,
                status_code=response.status_code,
                retryable=True,
            )
        elif response.status_code != 200:
            try:
                error_data = await response.json()
                msg = error_data.get("error", {}).get("message", response.text)
            except Exception:
                msg = response.text
            raise LLMError(
                message=f"API error: {msg}",
                code="API_ERROR",
                provider=self.provider,
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            )

        try:
            data = await response.json()
        except Exception as e:
            raise LLMError(
                message=f"Failed to parse response: {e}",
                code="PARSE_ERROR",
                provider=self.provider,
            )

        # Extract content
        try:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
        except (KeyError, IndexError) as e:
            raise LLMError(
                message=f"Unexpected response format: {e}",
                code="INVALID_RESPONSE",
                provider=self.provider,
            )

        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            request_id=data.get("id", str(uuid4())),
            raw_response=data,
        )


class AnthropicClient(BaseLLMClient):
    """Anthropic (Claude) API client."""

    BASE_URL = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-haiku-20240307",
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key, model, timeout, max_retries)

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.ANTHROPIC

    def _format_messages(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
    ) -> list[dict[str, str]]:
        messages = []
        if system_prompt:
            # Anthropic uses system parameter, not system message
            # We'll prepend to user prompt
            messages.append({"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"})
        else:
            messages.append({"role": "user", "content": user_prompt})
        return messages

    async def _make_request(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

        # Extract system prompt if present
        system = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)

        payload = {
            "model": self.model,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
        }

        if system:
            payload["system"] = system

        # Note: Anthropic doesn't support response_format like OpenAI
        # Structured output must be handled via prompting

        try:
            response = await self.client.post(
                f"{self.BASE_URL}/messages",
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException:
            raise LLMError(
                message="Request timed out",
                code="TIMEOUT",
                provider=self.provider,
                retryable=True,
            )
        except httpx.ConnectError:
            raise LLMError(
                message="Failed to connect to Anthropic API",
                code="CONNECTION_ERROR",
                provider=self.provider,
                retryable=True,
            )

        if response.status_code == 401:
            raise LLMError(
                message="Invalid API key",
                code="AUTHENTICATION_ERROR",
                provider=self.provider,
                status_code=401,
                retryable=False,
            )
        elif response.status_code == 429:
            raise LLMError(
                message="Rate limit exceeded",
                code="RATE_LIMIT",
                provider=self.provider,
                status_code=429,
                retryable=True,
            )
        elif response.status_code >= 500:
            raise LLMError(
                message=f"Anthropic server error: {response.status_code}",
                code="SERVER_ERROR",
                provider=self.provider,
                status_code=response.status_code,
                retryable=True,
            )
        elif response.status_code != 200:
            try:
                error_data = await response.json()
                msg = error_data.get("error", {}).get("message", response.text)
            except Exception:
                msg = response.text
            raise LLMError(
                message=f"API error: {msg}",
                code="API_ERROR",
                provider=self.provider,
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            )

        try:
            data = await response.json()
        except Exception as e:
            raise LLMError(
                message=f"Failed to parse response: {e}",
                code="PARSE_ERROR",
                provider=self.provider,
            )

        try:
            content = data["content"][0]["text"]
            usage = data.get("usage", {})
        except (KeyError, IndexError) as e:
            raise LLMError(
                message=f"Unexpected response format: {e}",
                code="INVALID_RESPONSE",
                provider=self.provider,
            )

        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider,
            usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            },
            request_id=data.get("id", str(uuid4())),
            raw_response=data,
        )


class GeminiClient(BaseLLMClient):
    """Google Gemini API client."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key, model, timeout, max_retries)

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.GEMINI

    def _format_messages(
        self,
        system_prompt: Optional[str],
        user_prompt: str,
    ) -> list[dict[str, str]]:
        # Gemini uses a different format: contents with parts
        # We'll combine system and user for simplicity
        content = user_prompt
        if system_prompt:
            content = f"{system_prompt}\n\n{content}"

        return [{"role": "user", "parts": [{"text": content}]}]

    async def _make_request(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        url = f"{self.BASE_URL}/models/{self.model}:generateContent"

        params = {"key": self.api_key}

        # Convert to Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            parts = []
            for key, value in msg.items():
                if key == "parts":
                    parts = value
                elif key == "content":
                    parts = [{"text": value}]
            if parts:
                contents.append({"role": role, "parts": parts})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        # Note: Gemini supports response_mime_type for JSON
        if response_format and response_format.get("type") == "json_object":
            payload["generationConfig"]["responseMimeType"] = "application/json"

        try:
            response = await self.client.post(
                url,
                params=params,
                json=payload,
            )
        except httpx.TimeoutException:
            raise LLMError(
                message="Request timed out",
                code="TIMEOUT",
                provider=self.provider,
                retryable=True,
            )
        except httpx.ConnectError:
            raise LLMError(
                message="Failed to connect to Gemini API",
                code="CONNECTION_ERROR",
                provider=self.provider,
                retryable=True,
            )

        if response.status_code == 400:
            try:
                error_data = response.json()
                msg = error_data.get("error", {}).get("message", response.text)
                if "API_KEY_INVALID" in msg or "API key" in msg:
                    raise LLMError(
                        message="Invalid API key",
                        code="AUTHENTICATION_ERROR",
                        provider=self.provider,
                        status_code=400,
                        retryable=False,
                    )
            except LLMError:
                raise
            except Exception:
                pass
            raise LLMError(
                message=f"API error: {response.text}",
                code="API_ERROR",
                provider=self.provider,
                status_code=400,
            )
        elif response.status_code == 429:
            raise LLMError(
                message="Rate limit exceeded",
                code="RATE_LIMIT",
                provider=self.provider,
                status_code=429,
                retryable=True,
            )
        elif response.status_code >= 500:
            raise LLMError(
                message=f"Gemini server error: {response.status_code}",
                code="SERVER_ERROR",
                provider=self.provider,
                status_code=response.status_code,
                retryable=True,
            )
        elif response.status_code != 200:
            try:
                error_data = response.json()
                msg = error_data.get("error", {}).get("message", response.text)
            except Exception:
                msg = response.text
            raise LLMError(
                message=f"API error: {msg}",
                code="API_ERROR",
                provider=self.provider,
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            )

        try:
            data = response.json()
        except Exception as e:
            raise LLMError(
                message=f"Failed to parse response: {e}",
                code="PARSE_ERROR",
                provider=self.provider,
            )

        try:
            candidate = data["candidates"][0]
            content = candidate["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
        except (KeyError, IndexError) as e:
            raise LLMError(
                message=f"Unexpected response format: {e}",
                code="INVALID_RESPONSE",
                provider=self.provider,
            )

        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider,
            usage={
                "input_tokens": usage.get("promptTokenCount", 0),
                "output_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0),
            },
            request_id=str(uuid4()),
            raw_response=data,
        )


class LLMClientFactory:
    """Factory for creating LLM clients."""

    _clients = {
        LLMProvider.OPENAI: OpenAIClient,
        LLMProvider.ANTHROPIC: AnthropicClient,
        LLMProvider.GEMINI: GeminiClient,
    }

    @classmethod
    def create(
        cls,
        provider: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 2,
        **kwargs,
    ) -> BaseLLMClient:
        """
        Create an LLM client for the specified provider.

        Args:
            provider: Provider name ("openai", "anthropic", "gemini")
            api_key: Provider API key
            model: Model name
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            **kwargs: Provider-specific options (e.g., base_url for OpenAI)

        Returns:
            BaseLLMClient instance

        Raises:
            ValueError: If provider is not supported
        """
        try:
            provider_enum = LLMProvider(provider.lower())
        except ValueError:
            raise ValueError(
                f"Unsupported LLM provider: {provider}. "
                f"Supported: {[p.value for p in LLMProvider]}"
            )

        client_class = cls._clients.get(provider_enum)
        if not client_class:
            raise ValueError(f"No client implementation for {provider}")

        return client_class(
            api_key=api_key,
            model=model,
            timeout=timeout,
            max_retries=max_retries,
            **kwargs,
        )


# Global client instance (lazy initialization)
_global_client: Optional[BaseLLMClient] = None


def get_llm_client() -> BaseLLMClient:
    """
    Get the global LLM client instance.

    Creates client from environment configuration on first call.

    Returns:
        BaseLLMClient instance

    Raises:
        ValueError: If LLM is not configured
    """
    global _global_client

    if _global_client is None:
        settings = get_settings()

        if not settings.has_llm_config:
            raise ValueError(
                "LLM not configured. Set LLM_PROVIDER, LLM_API_KEY, and LLM_MODEL in .env"
            )

        _global_client = LLMClientFactory.create(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=60.0,
            max_retries=2,
        )

    return _global_client


async def close_llm_client() -> None:
    """Close the global LLM client."""
    global _global_client
    if _global_client:
        await _global_client.close()
        _global_client = None