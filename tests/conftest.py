"""
Shared fixtures. Tests never touch Supabase or an LLM: `fake_library`
replaces the two lookup functions in gem_service with an in-memory dict.
"""
import os
from datetime import datetime, timezone

import pytest

# Set, not setdefault: CI exports its own placeholder key, and the route tests must send the one the app checks.
TEST_API_KEY = "test-key"
os.environ["GEMS_API_KEY"] = TEST_API_KEY

from app.models import Gem  # noqa: E402
from app.services import gem_service  # noqa: E402


def make_gem(name: str, system_prompt: str, **overrides) -> Gem:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = {
        "id": overrides.pop("id", f"00000000-0000-4000-8000-{abs(hash(name)) % 10**12:012d}"),
        "name": name,
        "description": overrides.pop("description", f"{name} gem"),
        "system_prompt": system_prompt,
        "model": "claude-opus-4-5",
        "provider": "anthropic",
        "tags": overrides.pop("tags", []),
        "variables": gem_service.extract_variables(system_prompt),
        "is_active": overrides.pop("is_active", True),
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return Gem(**data)


@pytest.fixture
def fake_library(monkeypatch):
    """A dict of name -> Gem that stands in for the gems table."""
    library: dict[str, Gem] = {}

    async def by_name(name: str):
        gem = library.get(name)
        return gem if gem and gem.is_active else None

    async def by_id(gem_id: str):
        return next((g for g in library.values() if g.id == gem_id), None)

    async def all_active():
        return sorted((g for g in library.values() if g.is_active), key=lambda g: g.name)

    monkeypatch.setattr(gem_service, "get_gem_by_name", by_name)
    monkeypatch.setattr(gem_service, "get_gem_by_id", by_id)
    monkeypatch.setattr(gem_service, "get_all_gems", all_active)
    return library
