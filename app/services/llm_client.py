"""LLM client abstraction for multiple vendors."""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from app.core.config import Settings, get_settings
from app.models.execution import TokenUsage

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Error from LLM client."""

    pass


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        document: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Tuple[str, TokenUsage]:
        """Generate response from LLM.

        Args:
            prompt: System/instruction prompt.
            document: Document content to process.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.

        Returns:
            Tuple of (response_text, token_usage).
        """
        pass

    @abstractmethod
    async def extract_json(
        self,
        prompt: str,
        document: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Tuple[Dict[str, Any], TokenUsage]:
        """Generate and parse JSON response.

        Args:
            prompt: System/instruction prompt.
            document: Document content to process.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.

        Returns:
            Tuple of (parsed_dict, token_usage).
        """
        pass

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text response, handling markdown code blocks."""
        # Try to find JSON in code blocks first
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            text = json_match.group(1)

        # Clean up and parse
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMClientError(f"Failed to parse JSON response: {e}")


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client."""

    def __init__(self, api_key: str, model: str):
        self.model = model
        try:
            import anthropic

            self.client = anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError:
            raise LLMClientError("anthropic package not installed")

    async def generate(
        self,
        prompt: str,
        document: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Tuple[str, TokenUsage]:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=prompt,
                messages=[{"role": "user", "content": document}],
            )

            text = response.content[0].text
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            )
            return text, usage

        except Exception as e:
            raise LLMClientError(f"Anthropic API error: {e}")

    async def extract_json(
        self,
        prompt: str,
        document: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Tuple[Dict[str, Any], TokenUsage]:
        json_prompt = f"{prompt}\n\nRespond with valid JSON only, no markdown or explanations."
        text, usage = await self.generate(json_prompt, document, temperature, max_tokens)
        data = self._extract_json_from_text(text)
        return data, usage


class OpenAIClient(BaseLLMClient):
    """OpenAI client."""

    def __init__(self, api_key: str, model: str):
        self.model = model
        try:
            import openai

            self.client = openai.AsyncOpenAI(api_key=api_key)
        except ImportError:
            raise LLMClientError("openai package not installed")

    async def generate(
        self,
        prompt: str,
        document: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Tuple[str, TokenUsage]:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": document},
                ],
            )

            text = response.choices[0].message.content or ""
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            )
            return text, usage

        except Exception as e:
            raise LLMClientError(f"OpenAI API error: {e}")

    async def extract_json(
        self,
        prompt: str,
        document: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Tuple[Dict[str, Any], TokenUsage]:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": f"{prompt}\n\nRespond with valid JSON."},
                    {"role": "user", "content": document},
                ],
            )

            text = response.choices[0].message.content or "{}"
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            )
            data = json.loads(text)
            return data, usage

        except json.JSONDecodeError as e:
            raise LLMClientError(f"Failed to parse JSON response: {e}")
        except Exception as e:
            raise LLMClientError(f"OpenAI API error: {e}")


class GeminiClient(BaseLLMClient):
    """Google Gemini client."""

    def __init__(self, api_key: str, model: str):
        self.model = model
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self.genai = genai
        except ImportError:
            raise LLMClientError("google-generativeai package not installed")

    async def generate(
        self,
        prompt: str,
        document: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Tuple[str, TokenUsage]:
        try:
            model = self.genai.GenerativeModel(
                self.model,
                system_instruction=prompt,
                generation_config=self.genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            response = await model.generate_content_async(document)

            text = response.text
            # Gemini token counting
            usage = TokenUsage(
                input_tokens=response.usage_metadata.prompt_token_count
                if response.usage_metadata
                else 0,
                output_tokens=response.usage_metadata.candidates_token_count
                if response.usage_metadata
                else 0,
                total_tokens=response.usage_metadata.total_token_count
                if response.usage_metadata
                else 0,
            )
            return text, usage

        except Exception as e:
            raise LLMClientError(f"Gemini API error: {e}")

    async def extract_json(
        self,
        prompt: str,
        document: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Tuple[Dict[str, Any], TokenUsage]:
        json_prompt = f"{prompt}\n\nRespond with valid JSON only, no markdown or explanations."
        text, usage = await self.generate(json_prompt, document, temperature, max_tokens)
        data = self._extract_json_from_text(text)
        return data, usage


class LLMClientFactory:
    """Factory for creating LLM clients."""

    _clients: Dict[str, BaseLLMClient] = {}

    @classmethod
    def get_client(
        cls,
        vendor: str,
        model: Optional[str] = None,
        settings: Optional[Settings] = None,
    ) -> BaseLLMClient:
        """Get or create an LLM client.

        Args:
            vendor: LLM vendor (anthropic, openai, gemini).
            model: Model name override.
            settings: Settings instance.

        Returns:
            LLM client instance.
        """
        settings = settings or get_settings()

        # Determine model
        if vendor == "anthropic":
            model = model or settings.anthropic_model
            api_key = settings.anthropic_api_key
            if not api_key:
                raise LLMClientError("ANTHROPIC_API_KEY not configured")
            client_cls = AnthropicClient
        elif vendor == "openai":
            model = model or settings.openai_model
            api_key = settings.openai_api_key
            if not api_key:
                raise LLMClientError("OPENAI_API_KEY not configured")
            client_cls = OpenAIClient
        elif vendor == "gemini":
            model = model or settings.gemini_model
            api_key = settings.google_api_key
            if not api_key:
                raise LLMClientError("GOOGLE_API_KEY not configured")
            client_cls = GeminiClient
        else:
            raise LLMClientError(f"Unknown vendor: {vendor}")

        # Cache key
        key = f"{vendor}:{model}"

        if key not in cls._clients:
            cls._clients[key] = client_cls(api_key, model)
            logger.info(f"Created LLM client: {vendor}/{model}")

        return cls._clients[key]

    @classmethod
    def clear_cache(cls) -> None:
        """Clear client cache."""
        cls._clients.clear()
