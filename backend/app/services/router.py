"""
The model policy (ADR-011): which provider and model answer a call.

Five modes, chosen in the UI by "Which AI should we use?":
  local   the free one on this PC         (only local)
  online  the online ones                 (only cloud)
  mix     a mix: hard thinking online, high-volume building and reviewing local
  auto    decide for me                   (whatever is set up, with fallback)
  manual  I'll choose each time           (gems name their models; nothing is decided)

A gem may pin a provider and model, in which case the policy only steps
in when that provider is unusable (no key, local server down). An explicit
override on the call always wins. Every decision carries a reason.
"""
from __future__ import annotations
import os
from dataclasses import dataclass

from app import settings
from app.services import llm_service

POLICIES = ("local", "online", "mix", "auto", "manual")
CLOUD = ("anthropic", "openai")


@dataclass
class Choice:
    provider: str
    model: str
    reason: str
    policy: str


@dataclass
class Availability:
    anthropic: bool
    openai: bool
    local: bool
    local_models: list[str]
    openai_models: list[str]


async def availability(probe: bool = True) -> Availability:
    """Keys are read from the environment; the local server and the model lists are probed only when `probe` is set."""
    models = await llm_service.available_models() if probe else {}
    return Availability(
        anthropic=bool(os.environ.get("ANTHROPIC_API_KEY")),
        openai=bool(os.environ.get("OPENAI_API_KEY")),
        local=bool(models.get("local")),
        local_models=models.get("local", []),
        openai_models=models.get("openai", []),
    )


def _cloud_default(av: Availability) -> tuple[str, str] | None:
    pref = settings.CLOUD_DEFAULT_PROVIDER
    if pref == "anthropic" and av.anthropic:
        return "anthropic", settings.CLOUD_DEFAULT_MODEL
    if av.openai:
        model = settings.OPENAI_DEFAULT_MODEL or (av.openai_models[0] if av.openai_models else "")
        if model:
            return "openai", model
    if av.anthropic:
        return "anthropic", settings.CLOUD_DEFAULT_MODEL
    return None


def _local_default(av: Availability) -> tuple[str, str] | None:
    if not av.local:
        return None
    model = settings.LOCAL_DEFAULT_MODEL or av.local_models[0]
    return "local", model


def _usable(provider: str, av: Availability) -> bool:
    return {"anthropic": av.anthropic, "openai": av.openai, "local": av.local}.get(provider, False)


def _role(gem) -> str:
    """What kind of work a gem does, from its tags and kind: 'reasoning' or 'volume'."""
    tags = {t.lower() for t in (getattr(gem, "tags", None) or [])}
    if tags & {"planning", "reasoning", "architecture", "design", "hard"}:
        return "reasoning"
    if tags & {"builder", "build", "review", "reviewer", "fix", "test", "volume", "local"}:
        return "volume"
    return "volume" if getattr(gem, "kind", "prompt") == "agent" else "reasoning"


async def choose(gem, *, provider_override: str | None = None, model_override: str | None = None, policy: str | None = None) -> Choice:
    policy = policy or settings.MODEL_POLICY
    if policy not in POLICIES:
        policy = "auto"
    pinned = gem.provider not in ("auto", "", None)

    # 1. Explicit overrides on the call.
    if provider_override or model_override:
        prov = provider_override or (gem.provider if pinned else None) or "anthropic"
        model = model_override or (gem.model if pinned and not provider_override else "")
        if not model:
            model = _default_model_for(prov, await availability())
        return Choice(prov, model, "override on this call", policy)

    # 2. Manual: the gem names its models; an unusable pin is an error the provider will raise.
    if policy == "manual" and pinned:
        return Choice(gem.provider, gem.model, "the gem names its model (hand pick)", policy)

    # 3. A pinned cloud gem whose key is present needs no probe, unless the policy forbids it.
    cheap = await availability(probe=False)
    if pinned and gem.provider in CLOUD and _usable(gem.provider, cheap) and policy not in ("local",):
        return Choice(gem.provider, gem.model, "the gem names its model", policy)

    av = await availability()
    if policy == "manual":
        fallback = _cloud_default(av) or _local_default(av)
        if fallback:
            return Choice(*fallback, "hand pick, but the gem has no model; using the default", policy)
        return Choice("anthropic", settings.CLOUD_DEFAULT_MODEL, "hand pick, nothing set up; the call will fail until a key or a local server exists", policy)

    # 4. Pinned gems keep their choice when the provider is usable and the policy allows it.
    if pinned and _usable(gem.provider, av):
        if policy == "local" and gem.provider != "local":
            pass   # local only: fall through to the local default
        elif policy == "online" and gem.provider == "local":
            pass   # online only: fall through to the cloud default
        else:
            return Choice(gem.provider, gem.model, "the gem names its model", policy)

    local = _local_default(av)
    cloud = _cloud_default(av)
    role = _role(gem)

    if policy == "local":
        if local:
            return Choice(*local, "the free one on this PC", policy)
        return Choice("local", settings.LOCAL_DEFAULT_MODEL or "", "the free one on this PC, but no local model server answered; start Ollama or pick another AI", policy)
    if policy == "online":
        if cloud:
            return Choice(*cloud, "the online ones", policy)
        return Choice("anthropic", settings.CLOUD_DEFAULT_MODEL, "the online ones, but no cloud key is set; add one in Settings or pick another AI", policy)
    if policy == "mix":
        if role == "reasoning" and cloud:
            return Choice(*cloud, "a mix: hard thinking goes online", policy)
        if role == "volume" and local:
            return Choice(*local, "a mix: everyday work stays on this PC", policy)
        if cloud:
            return Choice(*cloud, "a mix: no local model answered, so online", policy)
        if local:
            return Choice(*local, "a mix: no cloud key, so on this PC", policy)
        return Choice("local", "", "a mix, but nothing is set up yet", policy)
    # auto: decide for me
    if pinned and not _usable(gem.provider, av):
        other = local if gem.provider in CLOUD else cloud
        if other:
            return Choice(*other, f"decide for me: {gem.provider} is not usable right now, so {other[0]}", policy)
    if role == "reasoning" and cloud:
        return Choice(*cloud, "decide for me: this looks like hard thinking, so online", policy)
    if local:
        return Choice(*local, "decide for me: the free one on this PC can do this", policy)
    if cloud:
        return Choice(*cloud, "decide for me: no local model answered, so online", policy)
    return Choice("local", "", "decide for me, but nothing is set up yet: start Ollama or add a key in Settings", policy)


def _default_model_for(provider: str, av: Availability) -> str:
    if provider == "anthropic":
        return settings.CLOUD_DEFAULT_MODEL
    if provider == "openai":
        return settings.OPENAI_DEFAULT_MODEL or (av.openai_models[0] if av.openai_models else "")
    return settings.LOCAL_DEFAULT_MODEL or (av.local_models[0] if av.local_models else "")


async def describe() -> dict:
    """What the policy is and what is available, for the UI and the first run."""
    av = await availability()
    return {
        "policy": settings.MODEL_POLICY,
        "policies": list(POLICIES),
        "available": {"anthropic": av.anthropic, "openai": av.openai, "local": av.local},
        "local_base_url": settings.LOCAL_OPENAI_BASE_URL,
        "local_models": av.local_models,
        "cloud_default": _cloud_default(av),
        "local_default": _local_default(av),
    }
