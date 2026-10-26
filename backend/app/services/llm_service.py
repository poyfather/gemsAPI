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

PROVIDERS = ("anthropic", "openai", "local")

# Lazy singletons
_anthropic: AsyncAnthropic | None = None
_openai: AsyncOpenAI | None = None
_local: AsyncOpenAI | None = None


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


def _get_local() -> AsyncOpenAI:
    """Any OpenAI-compatible server on this machine or network: Ollama, oMLX, LM Studio, vLLM."""
    global _local
    if _local is None:
        _local = AsyncOpenAI(
            api_key=settings.LOCAL_OPENAI_API_KEY or "local",
            base_url=settings.LOCAL_OPENAI_BASE_URL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
    return _local


def _local_extra(provider: str) -> dict:
    """Extra request fields for a local server: how much a thinking model may reason (see settings)."""
    effort = settings.LOCAL_REASONING_EFFORT.strip()
    return {"reasoning_effort": effort} if provider == "local" and effort else {}


def _openai_like(provider: str) -> AsyncOpenAI:
    return _get_local() if provider == "local" else _get_openai()


def _check_provider(provider: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Use 'anthropic', 'openai' or 'local'.")


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

        client = _openai_like(provider)
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        response = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=max_tokens,
            **_local_extra(provider),
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

        client = _openai_like(provider)
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        stream = await client.chat.completions.create(
            model=model,
            messages=full_messages,
            stream=True,
            max_tokens=max_tokens,
            **_local_extra(provider),
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
    if provider == "local":
        return True   # a local server needs no key; reachability is checked by the listing itself
    return bool(os.environ.get("ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"))


async def _fetch_models(provider: str) -> list[str]:
    if provider == "anthropic":
        client = _get_anthropic()
        ids = [m.id async for m in client.models.list()]
        return sorted(ids, reverse=True)
    if provider == "local":
        client = _get_local()
        return sorted([m.id async for m in client.models.list()])
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


def reset_clients() -> None:
    """Drop the lazy clients (tests, and the console after settings change)."""
    global _anthropic, _openai, _local
    _anthropic = _openai = _local = None


# ─── Tool-use turns (agent harness, ADR-007) ───────────────────────────────────

from dataclasses import dataclass, field  # noqa: E402
import json  # noqa: E402


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class ToolTurn:
    """One model turn in a tool-use loop, in provider-neutral form."""
    text: str
    tool_calls: list[ToolCall]
    assistant_message: dict          # what to append to the conversation, in the provider's own shape
    stop_reason: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw: object = field(default=None, repr=False)


async def complete_turn(
    system_prompt: str,
    messages: list[dict],
    model: str,
    provider: str,
    tools: list[dict],
    max_tokens: int | None = None,
) -> ToolTurn:
    """
    One model call that may return tool calls.

    `tools` is a list of neutral {"name", "description", "parameters"} dicts
    (see app.agents.tools.Tool). `messages` must be in the provider's own
    shape; use tool_result_messages() to append results between turns.
    """
    _check_provider(provider)
    max_tokens = max_tokens or settings.LLM_MAX_TOKENS
    try:
        if provider == "anthropic":
            client = _get_anthropic()
            kwargs: dict = dict(model=model, max_tokens=max_tokens, system=system_prompt, messages=messages)
            if tools:
                kwargs["tools"] = [
                    {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools
                ]
            response = await client.messages.create(**kwargs)
            text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
            calls = [
                ToolCall(id=b.id, name=b.name, input=dict(b.input or {}))
                for b in response.content if getattr(b, "type", "") == "tool_use"
            ]
            assistant = {"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in response.content]}
            usage = getattr(response, "usage", None)
            return ToolTurn(
                text=text, tool_calls=calls, assistant_message=assistant,
                stop_reason=str(response.stop_reason or ""),
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                raw=response,
            )

        client = _openai_like(provider)
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        kwargs = dict(model=model, messages=full_messages, max_tokens=max_tokens, **_local_extra(provider))
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
                for t in tools
            ]
        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message
        calls = []
        tool_calls_out = []
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))
            tool_calls_out.append({"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}})
        assistant = {"role": "assistant", "content": msg.content}
        if tool_calls_out:
            assistant["tool_calls"] = tool_calls_out
        usage = getattr(response, "usage", None)
        return ToolTurn(
            text=msg.content or "", tool_calls=calls, assistant_message=assistant,
            stop_reason=str(choice.finish_reason or ""),
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            raw=response,
        )
    except EnvironmentError:
        raise
    except Exception as exc:
        raise ProviderError(f"{provider} tool turn with {model} failed: {exc}") from exc


def tool_result_messages(provider: str, results: list[tuple[ToolCall, str, bool]]) -> list[dict]:
    """
    Messages to append after executing a turn's tool calls.
    `results` is (call, output_text, is_error) per call. All of a turn's
    results go back together: one user message for Anthropic, one tool
    message per call for OpenAI.
    """
    _check_provider(provider)
    if provider == "anthropic":
        content = []
        for call, output, is_error in results:
            block = {"type": "tool_result", "tool_use_id": call.id, "content": output}
            if is_error:
                block["is_error"] = True
            content.append(block)
        return [{"role": "user", "content": content}]
    return [{"role": "tool", "tool_call_id": call.id, "content": output} for call, output, _ in results]
