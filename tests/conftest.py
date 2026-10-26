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
# Cloud keys so gems that pin a provider are routed as pinned; no provider is ever called in tests.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app import settings  # noqa: E402
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


@pytest.fixture(autouse=True)
def no_local_probe(monkeypatch):
    """The local model server is never contacted in tests: its listing is pinned to empty."""
    from app.services import llm_service

    monkeypatch.setitem(settings.PINNED_MODELS, "local", [])
    llm_service.clear_model_cache()
    yield
    llm_service.clear_model_cache()


@pytest.fixture
def client():
    """A TestClient with the lifespan run (it checks GEMS_API_KEY)."""
    with TestClient(app) as c:
        yield c


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


@pytest.fixture
def fake_runs(monkeypatch):
    """In-memory stand-in for the runs and run_events tables."""
    from app.agents import run_service
    from app.models import Run, RunEvent

    store: dict[str, dict] = {"runs": {}, "events": {}}
    counter = {"n": 0}

    async def create_run(gem_id, gem_name, model, provider, input_text):
        counter["n"] += 1
        run = Run(id=f"run-{counter['n']}", gem_name=gem_name, status="running", model=model, provider=provider,
                  input=input_text, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        store["runs"][run.id] = run
        store["events"][run.id] = []
        return run

    async def add_event(run_id, seq, type_, data):
        ev = RunEvent(seq=seq, type=type_, data=data, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        store["events"][run_id].append(ev)
        return ev

    store["state"] = {}

    async def update_run(run_id, **fields):
        if "state" in fields:
            store["state"][run_id] = fields.pop("state")
        run = store["runs"][run_id].model_copy(update=fields)
        store["runs"][run_id] = run
        return run

    async def finish_run(run_id, **fields):
        fields.setdefault("finished_at", datetime(2026, 1, 1, tzinfo=timezone.utc))
        return await update_run(run_id, **fields)

    async def get_run(run_id):
        run = store["runs"].get(run_id)
        return (run, store["events"][run_id]) if run else None

    async def get_run_state(run_id):
        return store["state"].get(run_id)

    for name, fn in [("create_run", create_run), ("add_event", add_event), ("update_run", update_run),
                     ("finish_run", finish_run), ("get_run", get_run), ("get_run_state", get_run_state)]:
        monkeypatch.setattr(run_service, name, fn)
    return store


@pytest.fixture(autouse=True)
def fake_memory(monkeypatch):
    """In-memory stand-in for the memories table, so runs can record observations without a database. Search is a word match."""
    import uuid

    from app.models import Memory, MemoryCreate
    from app.services import memory_service

    rows: list[Memory] = []

    class FakeMemoryStore:
        async def add_memory(self, data: MemoryCreate) -> Memory:
            m = Memory(id=str(uuid.uuid4()), created_at=datetime(2026, 1, 2, tzinfo=timezone.utc), **data.model_dump())
            rows.append(m)
            return m

        async def search_memories(self, query, *, scope=None, kinds=None, limit=20):
            words = [w for w in query.lower().split() if len(w) > 1]
            out = [m for m in reversed(rows) if (not scope or m.scope == scope) and (not kinds or m.kind in kinds)]
            if words:
                out = [m for m in out if any(w in m.text.lower() or w in " ".join(m.tags) for w in words)]
            return out[:limit]

        async def get_memories(self, ids):
            by_id = {m.id: m for m in rows}
            return [by_id[i] for i in ids if i in by_id]

        async def delete_memory(self, memory_id):
            before = len(rows)
            rows[:] = [m for m in rows if m.id != memory_id]
            return len(rows) < before

    store = FakeMemoryStore()
    monkeypatch.setattr(memory_service, "_store", lambda: store)
    monkeypatch.setattr(settings, "MEMORY_SUMMARIZE", False)
    return rows


@pytest.fixture
def fake_pipelines(monkeypatch):
    """In-memory pipelines and pipeline_runs, replacing the store the pipeline runner and routes use."""
    import uuid

    from app.agents import pipeline as pipeline_mod
    from app.models import Pipeline, PipelineCreate, PipelineRun
    from app.routes import pipelines as pipelines_route

    data = {"pipelines": {}, "runs": {}, "state": {}}
    now = datetime(2026, 1, 3, tzinfo=timezone.utc)

    class FakePipelineStore:
        async def list_pipelines(self):
            return sorted(data["pipelines"].values(), key=lambda p: p.name)

        async def get_pipeline(self, name):
            return data["pipelines"].get(name)

        async def create_pipeline(self, pc: PipelineCreate):
            p = Pipeline(id=str(uuid.uuid4()), created_at=now, updated_at=now, **pc.model_dump())
            data["pipelines"][p.name] = p
            return p

        async def update_pipeline(self, name, updates):
            p = data["pipelines"][name].model_copy(update=updates)
            data["pipelines"][name] = p
            return p

        async def delete_pipeline(self, name):
            return data["pipelines"].pop(name, None) is not None

        async def create_pipeline_run(self, pipeline_name, input_text):
            r = PipelineRun(id=f"prun-{len(data['runs']) + 1}", pipeline_name=pipeline_name, status="running", input=input_text, created_at=now)
            data["runs"][r.id] = r
            return r

        async def update_pipeline_run(self, run_id, **fields):
            if "state" in fields:
                data["state"][run_id] = fields.pop("state")
            r = PipelineRun(**{**data["runs"][run_id].model_dump(), **fields})   # validated, as a real store would re-read it
            data["runs"][run_id] = r
            return r

        async def get_pipeline_run(self, run_id):
            return data["runs"].get(run_id)

        async def get_pipeline_run_state(self, run_id):
            return data["state"].get(run_id)

    store = FakePipelineStore()
    monkeypatch.setattr(pipeline_mod, "_store", lambda: store)
    monkeypatch.setattr(pipelines_route, "get_store", lambda: store)
    return data
