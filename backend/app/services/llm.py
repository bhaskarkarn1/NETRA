"""
NETRA LLM Service — Multi-model routing with automatic fallback.

Model routing strategy:
1. Primary: Gemini 2.5 Flash (deep analysis, classification, generation)
2. Fast fallback: Groq Llama 3.3 70B (if Gemini fails or times out)
3. Ultra-fast: Groq Llama 3.1 8B (simple extraction, language detection)
4. Vision: Gemini 2.5 Flash → Gemini 2.0 Flash Lite (Groq Vision decommissioned)

Every call is logged to audit_logs with model used, latency, and fallback info.
"""

import asyncio
import time
import json
import logging
from typing import Any

from google import genai
from google.genai import types as genai_types
from groq import AsyncGroq

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMResponse:
    """Standardized response from any LLM provider."""

    def __init__(
        self,
        content: str,
        model_used: str,
        latency_ms: int,
        was_fallback: bool = False,
        fallback_reason: str | None = None,
        raw_response: Any = None,
    ):
        self.content = content
        self.model_used = model_used
        self.latency_ms = latency_ms
        self.was_fallback = was_fallback
        self.fallback_reason = fallback_reason
        self.raw_response = raw_response

    def parse_json(self) -> dict | list | None:
        """
        Robustly extract JSON from LLM responses.

        Handles multiple response formats:
        1. Clean JSON (ideal case)
        2. Markdown code blocks: ```json ... ```, ```JSON ... ```, ``` ... ```
        3. JSON embedded in prose text (finds the outermost { ... } or [ ... ])
        4. Multiple JSON objects (picks the largest/most complete)
        """
        import re

        text = self.content.strip()
        if not text:
            return None

        # Strategy 1: Direct parse (ideal case)
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: Extract from markdown code blocks (```json ... ```)
        # Handles: ```json, ```JSON, ```Json, ``` (no language tag)
        code_block_pattern = re.compile(
            r'```(?:json|JSON|Json)?\s*\n(.*?)```',
            re.DOTALL
        )
        matches = code_block_pattern.findall(text)
        for match in matches:
            try:
                return json.loads(match.strip())
            except (json.JSONDecodeError, ValueError):
                continue

        # Strategy 3: Find the outermost JSON object { ... } in the text
        # This handles cases where LLM adds prose before/after JSON
        brace_start = text.find('{')
        bracket_start = text.find('[')

        # Try object first, then array
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start_idx = text.find(start_char)
            if start_idx == -1:
                continue

            # Find the matching closing brace/bracket by counting depth
            depth = 0
            in_string = False
            escape_next = False
            end_idx = -1

            for i in range(start_idx, len(text)):
                c = text[i]

                if escape_next:
                    escape_next = False
                    continue

                if c == '\\' and in_string:
                    escape_next = True
                    continue

                if c == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if in_string:
                    continue

                if c == start_char:
                    depth += 1
                elif c == end_char:
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break

            if end_idx > start_idx:
                candidate = text[start_idx:end_idx + 1]
                try:
                    return json.loads(candidate)
                except (json.JSONDecodeError, ValueError):
                    pass

        # Strategy 4: Last resort — try to fix common LLM JSON errors
        # (trailing commas, single quotes, etc.)
        try:
            # Remove trailing commas before } or ]
            cleaned = re.sub(r',\s*([}\]])', r'\1', text)
            # Find JSON object in cleaned text
            brace_start = cleaned.find('{')
            if brace_start >= 0:
                # Simple greedy approach: find last }
                brace_end = cleaned.rfind('}')
                if brace_end > brace_start:
                    return json.loads(cleaned[brace_start:brace_end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

        logger.warning(f"JSON parse failed for response (first 200 chars): {text[:200]}")
        return None


class LLMService:
    """Unified interface for all LLM calls with automatic fallback chain."""

    def __init__(self):
        self.settings = get_settings()
        self._gemini_client: genai.Client | None = None
        self._groq_client: AsyncGroq | None = None

    @property
    def gemini_client(self) -> genai.Client:
        if self._gemini_client is None:
            self._gemini_client = genai.Client(api_key=self.settings.GOOGLE_API_KEY)
        return self._gemini_client

    @property
    def groq_client(self) -> AsyncGroq:
        if self._groq_client is None:
            self._groq_client = AsyncGroq(api_key=self.settings.GROQ_API_KEY)
        return self._groq_client

    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        response_format: str = "text",  # 'text' or 'json'
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tier: str = "primary",  # 'primary', 'fast', 'ultra_fast'
    ) -> LLMResponse:
        """
        Generate a response using the model routing chain.

        Tries models in order based on tier:
        - primary: Gemini → Groq 70B → Groq 8B
        - fast: Groq 70B → Groq 8B → Gemini
        - ultra_fast: Groq 8B → Groq 70B
        """
        chain = self._get_model_chain(tier)
        last_error = None

        for i, (provider, model) in enumerate(chain):
            try:
                start_time = time.monotonic()

                timeout_s = (
                    self.settings.PRIMARY_TIMEOUT_MS / 1000
                    if provider == "gemini"
                    else self.settings.FALLBACK_TIMEOUT_MS / 1000
                )

                if provider == "gemini":
                    content = await asyncio.wait_for(
                        self._call_gemini(
                            prompt=prompt,
                            model=model,
                            system_instruction=system_instruction,
                            response_format=response_format,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        ),
                        timeout=timeout_s,
                    )
                elif provider == "groq":
                    content = await asyncio.wait_for(
                        self._call_groq(
                            prompt=prompt,
                            model=model,
                            system_instruction=system_instruction,
                            response_format=response_format,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        ),
                        timeout=timeout_s,
                    )
                else:
                    raise ValueError(f"Unknown provider: {provider}")

                elapsed_ms = int((time.monotonic() - start_time) * 1000)

                return LLMResponse(
                    content=content,
                    model_used=model,
                    latency_ms=elapsed_ms,
                    was_fallback=i > 0,
                    fallback_reason=str(last_error) if i > 0 else None,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM call failed for {provider}/{model}: {e}. "
                    f"Trying next in chain ({i + 1}/{len(chain)})."
                )
                continue

        # All models failed
        raise RuntimeError(
            f"All LLM models in chain failed. Last error: {last_error}"
        )

    def _get_model_chain(self, tier: str) -> list[tuple[str, str]]:
        """Return ordered list of (provider, model) tuples for the given tier."""
        s = self.settings

        chains = {
            "primary": [
                ("gemini", s.GEMINI_MODEL),
                ("groq", s.GROQ_MODEL),
                ("groq", s.GROQ_FAST_MODEL),
            ],
            "fast": [
                ("groq", s.GROQ_MODEL),
                ("groq", s.GROQ_FAST_MODEL),
                ("gemini", s.GEMINI_MODEL),
            ],
            "ultra_fast": [
                ("groq", s.GROQ_FAST_MODEL),
                ("groq", s.GROQ_MODEL),
            ],
        }

        chain = chains.get(tier)
        if chain is None:
            raise ValueError(f"Unknown tier: {tier}. Must be: {list(chains.keys())}")

        # Filter out models with missing API keys
        filtered = []
        for provider, model in chain:
            if provider == "gemini" and s.GOOGLE_API_KEY:
                filtered.append((provider, model))
            elif provider == "groq" and s.GROQ_API_KEY:
                filtered.append((provider, model))

        if not filtered:
            raise RuntimeError("No LLM API keys configured. Set GOOGLE_API_KEY or GROQ_API_KEY.")

        return filtered

    async def _call_gemini(
        self,
        prompt: str,
        model: str,
        system_instruction: str | None,
        response_format: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Google Gemini API. Fails fast on 429 so the chain falls to Groq."""
        config = genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction
        if response_format == "json":
            config.response_mime_type = "application/json"

        response = await self.gemini_client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        if not response.text:
            raise ValueError("Gemini returned empty response")

        return response.text

    async def _call_groq(
        self,
        prompt: str,
        model: str,
        system_instruction: str | None,
        response_format: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call Groq API."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.groq_client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned empty response")

        return content

    async def _call_groq_vision(
        self,
        image_base64: str,
        prompt: str,
        system_instruction: str | None,
        mime_type: str,
        temperature: float,
        max_tokens: int,
        model: str = "llama-3.2-11b-vision-preview",
    ) -> str:
        """Call Groq Vision API with base64 image input."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}",
                    },
                },
            ],
        })

        response = await self.groq_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq Vision returned empty response")

        return content

    async def vision_analyze(
        self,
        image_base64: str,
        prompt: str,
        system_instruction: str | None = None,
        mime_type: str = "image/jpeg",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Analyze an image using vision models with automatic fallback.

        Chain: Gemini Vision → Groq Vision (llama-3.2-11b-vision-preview)
        If Gemini is rate-limited, seamlessly falls to Groq.
        """
        import base64

        start_time = time.monotonic()
        last_error = None

        # Vision fallback chain (Groq Vision decommissioned — use Gemini models only)
        vision_chain = []
        if self.settings.GOOGLE_API_KEY:
            vision_chain.append(("gemini", self.settings.GEMINI_MODEL))
            vision_chain.append(("gemini", self.settings.GEMINI_LITE_MODEL))

        for i, (provider, model) in enumerate(vision_chain):
            try:
                if provider == "gemini":
                    image_bytes = base64.b64decode(image_base64)
                    parts = [
                        genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        genai_types.Part.from_text(text=prompt),
                    ]

                    config = genai_types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    )
                    if system_instruction:
                        config.system_instruction = system_instruction

                    response = await asyncio.wait_for(
                        self.gemini_client.aio.models.generate_content(
                            model=model,
                            contents=parts,
                            config=config,
                        ),
                        timeout=self.settings.PRIMARY_TIMEOUT_MS / 1000,
                    )

                    content = response.text
                    if not content:
                        raise ValueError("Gemini Vision returned empty response")

                elif provider == "groq":
                    content = await asyncio.wait_for(
                        self._call_groq_vision(
                            image_base64=image_base64,
                            prompt=prompt,
                            system_instruction=system_instruction,
                            mime_type=mime_type,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            model=model,
                        ),
                        timeout=self.settings.FALLBACK_TIMEOUT_MS / 1000,
                    )
                else:
                    continue

                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                return LLMResponse(
                    content=content,
                    model_used=f"{model}-vision",
                    latency_ms=elapsed_ms,
                    was_fallback=i > 0,
                    fallback_reason=str(last_error) if i > 0 else None,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Vision call failed for {provider}/{model}: {e}. "
                    f"Trying next in chain ({i + 1}/{len(vision_chain)})."
                )
                continue

        raise RuntimeError(f"All vision models failed. Last error: {last_error}")

    async def embed(self, text: str, model: str = "text-embedding-004") -> list[float]:
        """
        Generate a text embedding vector using Gemini's embedding API.
        Used for cross-case intelligence (cosine similarity search).

        Returns a list of floats (768-dimensional vector).
        """
        try:
            result = await self.gemini_client.aio.models.embed_content(
                model=model,
                contents=text[:2000],  # Trim to stay within limits
            )
            # The response contains an embedding object
            if result and result.embeddings and len(result.embeddings) > 0:
                return list(result.embeddings[0].values)
            raise ValueError("Empty embedding response")
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            raise


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
