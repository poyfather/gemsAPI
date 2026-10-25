"""The model policy: five modes, pins, overrides, fallbacks, and the /chat/policy endpoint."""
import asyncio

import pytest

from app import settings
from app.services import router
from conftest import TEST_API_KEY, make_gem


@pytest.fixture
def world(monkeypatch):
    """Control what is available: keys and the local server's models."""
    state = {"anthropic": True, "openai": False, "local": ["qwen3-coder:30b", "llama3.2"], "openai_models": ["gpt-5.5"]}

    async def fake_models():
        return {"anthropic": ["claude-opus-5-5"], "openai": state["openai_models"] if state["openai"] else [], "local": state["local"]}

    monkeypatch.setattr(router.llm_service, "available_models", fake_models)

    def apply():
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k") if state["anthropic"] else monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "k") if state["openai"] else monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    state["apply"] = apply
    apply()
    return state


def choose(gem, **kw):
    return asyncio.run(router.choose(gem, **kw))


def test_overrides_always_win(world) -> None:
    g = make_gem("g", "x")
    c = choose(g, provider_override="local", model_override="llama3.2", policy="online")
    assert (c.provider, c.model) == ("local", "llama3.2") and "override" in c.reason
    c = choose(g, model_override="claude-sonnet-5-5")
    assert (c.provider, c.model) == ("anthropic", "claude-sonnet-5-5")
    c = choose(g, provider_override="local")
    assert (c.provider, c.model) == ("local", "qwen3-coder:30b")   # first local model when none named


def test_manual_honours_the_pin_and_falls_back_for_auto_gems(world) -> None:
    pinned = make_gem("p", "x", provider="openai", model="gpt-x")
    assert choose(pinned, policy="manual").provider == "openai"   # even without a key: hand pick means hand pick
    auto = make_gem("a", "x", provider="auto", model="auto")
    c = choose(auto, policy="manual")
    assert (c.provider, c.model) == ("anthropic", settings.CLOUD_DEFAULT_MODEL)


def test_local_only(world) -> None:
    c = choose(make_gem("p", "x"), policy="local")                    # pinned to anthropic, policy says local
    assert (c.provider, c.model) == ("local", "qwen3-coder:30b") and "free one" in c.reason
    world["local"] = []
    c = choose(make_gem("a", "x", provider="auto"), policy="local")
    assert c.provider == "local" and "no local model server" in c.reason


def test_online_only(world) -> None:
    c = choose(make_gem("a", "x", provider="auto"), policy="online")
    assert (c.provider, c.model) == ("anthropic", "claude-opus-5-5")
    c = choose(make_gem("l", "x", provider="local", model="llama3.2"), policy="online")
    assert c.provider == "anthropic"                                 # pinned local, policy says online
    world["anthropic"] = False
    world["apply"]()
    c = choose(make_gem("a", "x", provider="auto"), policy="online")
    assert "no cloud key" in c.reason


def test_mix_sends_hard_thinking_online_and_volume_local(world) -> None:
    planner = make_gem("plan", "x", provider="auto", tags=["planning"])
    builder = make_gem("build", "x", provider="auto", kind="agent", tags=["builder"])
    plain = make_gem("plain", "x", provider="auto")
    assert choose(planner, policy="mix").provider == "anthropic"
    assert choose(builder, policy="mix").provider == "local"
    assert choose(plain, policy="mix").provider == "anthropic"       # a prompt gem counts as thinking
    world["local"] = []
    assert choose(builder, policy="mix").provider == "anthropic" and "no local model" in choose(builder, policy="mix").reason


def test_auto_decides_from_what_is_set_up(world) -> None:
    agent = make_gem("ops", "x", provider="auto", kind="agent")
    c = choose(agent, policy="auto")
    assert c.provider == "local" and "free one on this PC can do this" in c.reason
    thinker = make_gem("t", "x", provider="auto", tags=["reasoning"])
    assert choose(thinker, policy="auto").provider == "anthropic"
    world["local"] = []
    assert choose(agent, policy="auto").provider == "anthropic"
    world["anthropic"] = False
    world["apply"]()
    c = choose(agent, policy="auto")
    assert c.provider == "local" and "nothing is set up" in c.reason


def test_auto_reroutes_a_pinned_gem_whose_provider_is_unusable(world) -> None:
    world["anthropic"] = False
    world["apply"]()
    pinned = make_gem("p", "x")                                       # anthropic, no key
    c = choose(pinned, policy="auto")
    assert c.provider == "local" and "not usable right now" in c.reason
    world["anthropic"] = True
    world["apply"]()
    assert choose(pinned, policy="auto").provider == "anthropic"      # key back: the pin holds, no probe needed


def test_policy_endpoint_describes_the_world(client, world) -> None:
    body = client.get("/chat/policy", headers={"X-API-Key": TEST_API_KEY}).json()
    assert body["policy"] in router.POLICIES and body["available"]["local"] is True
    assert body["local_default"] == ["local", "qwen3-coder:30b"]
    assert body["cloud_default"] == ["anthropic", settings.CLOUD_DEFAULT_MODEL]
