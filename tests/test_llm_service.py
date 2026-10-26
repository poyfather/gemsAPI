"""Model listing, client construction and error wrapping in llm_service (no network)."""
import pytest

from app import settings
from app.services import llm_service


class _FakeModel:
    def __init__(self, id: str) -> None:
        self.id = id


class _FakeList:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    def __aiter__(self):
        async def gen():
            for i in self._ids:
                yield _FakeModel(i)
        return gen()


class _FakeClient:
    def __init__(self, ids: list[str], fail: bool = False) -> None:
        self._ids, self._fail = ids, fail

    @property
    def models(self):
        outer = self

        class _M:
            def list(self):
                if outer._fail:
                    raise RuntimeError("boom")
                return _FakeList(outer._ids)
        return _M()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    llm_service.clear_model_cache()
    monkeypatch.setattr(settings, "PINNED_MODELS", {"anthropic": [], "openai": [], "local": []})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield
    llm_service.clear_model_cache()


async def _models(**kw):
    return await llm_service.available_models(**kw)


def test_without_keys_the_fallback_lists_are_returned() -> None:
    import asyncio
    result = asyncio.run(_models())
    assert result == settings.FALLBACK_MODELS


def test_pinned_models_from_env_win_and_skip_lookup(monkeypatch) -> None:
    import asyncio
    monkeypatch.setattr(settings, "PINNED_MODELS", {"anthropic": ["claude-x"], "openai": ["gpt-y"], "local": ["llama"]})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(llm_service, "_get_anthropic", lambda: (_ for _ in ()).throw(AssertionError("looked up")))
    assert asyncio.run(_models()) == {"anthropic": ["claude-x"], "openai": ["gpt-y"], "local": ["llama"]}


def test_live_lists_are_fetched_filtered_and_cached(monkeypatch) -> None:
    import asyncio
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    calls = {"anthropic": 0, "openai": 0}

    def fake_anthropic():
        calls["anthropic"] += 1
        return _FakeClient(["claude-a", "claude-b"])

    def fake_openai():
        calls["openai"] += 1
        return _FakeClient(["gpt-5.5", "gpt-5.4-mini", "gpt-4o-realtime-preview", "text-embedding-3-large", "whisper-1", "o3", "gpt-image-1"])

    monkeypatch.setattr(llm_service, "_get_anthropic", fake_anthropic)
    monkeypatch.setattr(llm_service, "_get_openai", fake_openai)
    monkeypatch.setattr(llm_service, "_get_local", lambda: _FakeClient([], fail=True))
    first = asyncio.run(_models())
    assert first["anthropic"] == ["claude-b", "claude-a"]
    assert first["local"] == []
    assert first["openai"] == ["o3", "gpt-5.5", "gpt-5.4-mini"]
    second = asyncio.run(_models())
    assert second == first
    assert calls == {"anthropic": 1, "openai": 1}
    asyncio.run(_models(force_refresh=True))
    assert calls == {"anthropic": 2, "openai": 2}


def test_a_failed_refresh_keeps_the_last_list_or_falls_back(monkeypatch) -> None:
    import asyncio
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(llm_service, "_get_anthropic", lambda: _FakeClient([], fail=True))
    monkeypatch.setattr(llm_service, "_get_local", lambda: _FakeClient([], fail=True))
    assert asyncio.run(_models())["anthropic"] == settings.FALLBACK_MODELS["anthropic"]
    llm_service._cache["anthropic"] = (0.0, ["claude-old"])  # stale but known
    assert asyncio.run(_models())["anthropic"] == ["claude-old"]


def test_clients_get_timeout_and_retries(monkeypatch) -> None:
    seen: dict[str, dict] = {}

    class FakeAnthropic:
        def __init__(self, **kw):
            seen["anthropic"] = kw

    class FakeOpenAI:
        def __init__(self, **kw):
            seen["openai"] = kw

    monkeypatch.setattr(llm_service, "AsyncAnthropic", FakeAnthropic)
    monkeypatch.setattr(llm_service, "AsyncOpenAI", FakeOpenAI)
    monkeypatch.setattr(llm_service, "_anthropic", None)
    monkeypatch.setattr(llm_service, "_openai", None)
    monkeypatch.setattr(llm_service, "_local", None)
    monkeypatch.setattr(settings, "LLM_TIMEOUT_SECONDS", 12.5)
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 4)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    llm_service._get_anthropic()
    llm_service._get_openai()
    llm_service._anthropic = None
    llm_service._openai = None
    assert seen["anthropic"] == {"api_key": "a", "timeout": 12.5, "max_retries": 4}
    assert seen["openai"] == {"api_key": "o", "timeout": 12.5, "max_retries": 4}
    monkeypatch.setattr(settings, "LOCAL_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    llm_service._get_local()
    llm_service._local = None
    assert seen["openai"] == {"api_key": "ollama", "base_url": "http://127.0.0.1:1234/v1", "timeout": 12.5, "max_retries": 4}


def test_missing_key_is_an_environment_error_not_a_provider_error(monkeypatch) -> None:
    import asyncio
    monkeypatch.setattr(llm_service, "_anthropic", None)
    with pytest.raises(EnvironmentError):
        asyncio.run(llm_service.complete("s", [], "m", "anthropic"))


def test_unknown_provider_is_a_value_error() -> None:
    import asyncio
    with pytest.raises(ValueError):
        asyncio.run(llm_service.complete("s", [], "m", "cohere"))


def test_sdk_failures_become_provider_error(monkeypatch) -> None:
    import asyncio

    class Boom:
        @property
        def messages(self):
            class _C:
                async def create(self, **kw):
                    raise RuntimeError("rate limited")
            return _C()

    monkeypatch.setattr(llm_service, "_get_anthropic", lambda: Boom())
    with pytest.raises(llm_service.ProviderError, match="anthropic completion"):
        asyncio.run(llm_service.complete("s", [], "m", "anthropic"))


def test_new_gems_default_to_the_configured_model_and_provider(monkeypatch) -> None:
    from app.models import GemCreate
    monkeypatch.setattr(settings, "DEFAULT_MODEL", "claude-test")
    monkeypatch.setattr(settings, "DEFAULT_PROVIDER", "anthropic")
    gem = GemCreate(name="x")
    assert (gem.model, gem.provider) == ("claude-test", "anthropic")
    monkeypatch.setattr(settings, "DEFAULT_MODEL", "auto")
    monkeypatch.setattr(settings, "DEFAULT_PROVIDER", "auto")
    assert GemCreate(name="y").provider == "auto"


def test_a_local_server_that_answers_lists_its_models_sorted(monkeypatch) -> None:
    import asyncio
    monkeypatch.setattr(llm_service, "_get_local", lambda: _FakeClient(["qwen3:4b", "llama3.2", "gemma3"]))
    assert asyncio.run(_models())["local"] == ["gemma3", "llama3.2", "qwen3:4b"]


class _Recorder:
    """An OpenAI-shaped client that records what was sent and answers 'ok'."""
    def __init__(self) -> None:
        self.sent: dict = {}

    @property
    def chat(self):
        outer = self

        class _Completions:
            async def create(self, **kw):
                outer.sent = kw
                msg = type("M", (), {"content": "ok", "tool_calls": None})()
                return type("R", (), {"choices": [type("C", (), {"message": msg, "finish_reason": "stop"})()], "usage": None})()

        return type("Chat", (), {"completions": _Completions()})()


def test_local_servers_are_asked_not_to_think_by_default(monkeypatch) -> None:
    import asyncio
    rec = _Recorder()
    monkeypatch.setattr(llm_service, "_get_local", lambda: rec)
    assert asyncio.run(llm_service.complete("s", [{"role": "user", "content": "hi"}], "qwen3:4b", "local", max_tokens=64)) == "ok"
    assert rec.sent["reasoning_effort"] == "none" and rec.sent["max_tokens"] == 64


def test_reasoning_effort_is_configurable_and_never_sent_to_openai(monkeypatch) -> None:
    import asyncio
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    rec_local, rec_openai = _Recorder(), _Recorder()
    monkeypatch.setattr(llm_service, "_get_local", lambda: rec_local)
    monkeypatch.setattr(llm_service, "_get_openai", lambda: rec_openai)
    monkeypatch.setattr(settings, "LOCAL_REASONING_EFFORT", "")
    asyncio.run(llm_service.complete("s", [], "qwen3:4b", "local"))
    assert "reasoning_effort" not in rec_local.sent
    monkeypatch.setattr(settings, "LOCAL_REASONING_EFFORT", "low")
    asyncio.run(llm_service.complete("s", [], "qwen3:4b", "local"))
    assert rec_local.sent["reasoning_effort"] == "low"
    asyncio.run(llm_service.complete("s", [], "gpt-x", "openai"))
    assert "reasoning_effort" not in rec_openai.sent
