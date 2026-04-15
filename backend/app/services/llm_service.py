"""
LLM service — thin abstraction over Anthropic and OpenAI.
Supports single-shot and streaming completions.
"""
from __future__ import annotations
import os
from typing import AsyncGenerator

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

# Lazy singletons
_anthropic: AsyncAnthropic | None = None
_openai: AsyncOpenAI | None = None


def _get_anthropic() -> AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set.")
        _anthropic = AsyncAnthropic(api_key=key)
    return _anthropic


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise EnvironmentError("OPENAI_API_KEY is not set.")
        _openai = AsyncOpenAI(api_key=key)
    return _openai


# ─── Single completion ─────────────────────────────────────────────────────────

async def complete(
    system_prompt: str,
    messages: list[dict],
    model: str,
    provider: str,
    max_tokens: int = 4096,
) -> str:
    """Return a single non-streaming completion."""
    if provider == "anthropic":
        client = _get_anthropic()
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text

    elif provider == "openai":
        client = _get_openai()
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        response = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    else:
        raise ValueError(f"Unknown provider '{provider}'. Use 'anthropic' or 'openai'.")


# ─── Streaming completion ──────────────────────────────────────────────────────

async def complete_stream(
    system_prompt: str,
    messages: list[dict],
    model: str,
    provider: str,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Yield text chunks as they arrive from the LLM."""
    if provider == "anthropic":
        client = _get_anthropic()
        async with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    elif provider == "openai":
        client = _get_openai()
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        stream = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            stream=True,
            max_tokens=max_tokens,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    else:
        raise ValueError(f"Unknown provider '{provider}'.")


# ─── Available models ──────────────────────────────────────────────────────────

MODELS = {
    "anthropic": [
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
}
