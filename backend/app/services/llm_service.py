"""
LLM service: a thin abstraction over Anthropic and OpenAI.

Supports single-shot and streaming completions, and lists the models each
provider currently offers. Clients are built lazily with explicit timeouts
and retry counts from app.settings.
"""
from __future__ import annotations
import logging
import os
import re
import time
from typing import AsyncGenerator

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app import settings

logger = logging.getLogger(__name__)

PROVIDERS = ("anthropic", "openai")

# Lazy singletons
_anthropic: AsyncAnthropic | None = None
_openai: AsyncOpenAI | None = None


class ProviderError(RuntimeError):
    """A provider call failed after the SDK's own retries. The message is safe to log, not to return."""


def _get_anthropic() -> AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set.")
        _anthropic = AsyncAnthropic(
            api_key=key,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
    return _anthropic


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise EnvironmentError("OPENAI_API_KEY is not set.")
        _openai = AsyncOpenAI(
            api_key=key,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
    return _openai


def _check_provider(provider: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Use 'anthropic' or 'openai'.")


# ─── Single completion ─────────────────────────────────────────────────────────

async def complete(
    system_prompt: str,
    messages: list[dict],
    model: str,
    provider: str,
    max_tokens: int | None = None,
) -> str:
    """Return a single non-streaming completion."""
    _check_provider(provider)
    max_tokens = max_tokens or settings.LLM_MAX_TOKENS
    try:
        if provider == "anthropic":
            client = _get_anthropic()
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )
            return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")

        client = _get_openai()
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        response = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except EnvironmentError:
        raise
    except Exception as exc:  # the SDKs raise many types; callers get one
        raise ProviderError(f"{provider} completion with {model} failed: {exc}") from exc


# ─── Streaming completion ──────────────────────────────────────────────────────

async def complete_stream(
    system_prompt: str,
    messages: list[dict],
    model: str,
    provider: str,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """Yield text chunks as they arrive from the LLM."""
    _check_provider(provider)
    max_tokens = max_tokens or settings.LLM_MAX_TOKENS
    try:
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
            return

        client = _get_openai()
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        stream = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            stream=True,
            max_tokens=max_tokens,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except EnvironmentError:
        raise
    except Exception as exc:
        raise ProviderError(f"{provider} stream with {model} failed: {exc}") from exc


# ─── Available models ──────────────────────────────────────────────────────────

# OpenAI's list endpoint returns every model (embeddings, audio, images, ...).
# Keep the chat-capable families and drop the obvious non-chat variants.
_OPENAI_CHAT_RE = re.compile(r"^(gpt-|o\d)")
_OPENAI_EXCLUDE_RE = re.compile(
    r"(realtime|audio|transcribe|tts|search|image|embedding|moderation|instruct|codex|preview-\d{4})"
)

_cache: dict[str, tuple[float, list[str]]] = {}


def _has_key(provider: str) -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"))


async def _fetch_models(provider: str) -> list[str]:
    if provider == "anthropic":
        client = _get_anthropic()
        ids = [m.id async for m in client.models.list()]
        return sorted(ids, reverse=True)
    client = _get_openai()
    ids = [m.id async for m in client.models.list()]
    chat = [i for i in ids if _OPENAI_CHAT_RE.match(i) and not _OPENAI_EXCLUDE_RE.search(i)]
    return sorted(chat, reverse=True)


async def available_models(force_refresh: bool = False) -> dict[str, list[str]]:
    """
    Models per provider, in this order of preference:
      1. GEMS_MODELS_<PROVIDER> from the environment (pinned, no lookup).
      2. The provider's live model list, cached for MODEL_LIST_TTL_SECONDS.
      3. The last fetched list if a refresh fails, else the static fallback.
    A provider with no API key gets its fallback list.
    """
    result: dict[str, list[str]] = {}
    now = time.monotonic()
    for provider in PROVIDERS:
        pinned = settings.PINNED_MODELS[provider]
        if pinned:
            result[provider] = pinned
            continue
        cached = _cache.get(provider)
        if cached and not force_refresh and now - cached[0] < settings.MODEL_LIST_TTL_SECONDS:
            result[provider] = cached[1]
            continue
        if not _has_key(provider):
            result[provider] = settings.FALLBACK_MODELS[provider]
            continue
        try:
            models = await _fetch_models(provider)
            _cache[provider] = (now, models)
            result[provider] = models
        except Exception as exc:
            logger.warning("Could not list %s models: %s", provider, exc)
            result[provider] = cached[1] if cached else settings.FALLBACK_MODELS[provider]
    return result


def clear_model_cache() -> None:
    _cache.clear()
