"""The SQLite backend for real: seeds, CRUD, the resolver, runs, and the routes end to end."""
import asyncio
import pathlib

import pytest

from app import settings, storage
from app.models import GemCreate, GemUpdate
from app.services import gem_service
from app.storage.seeds import parse_seed_gems
from app.storage.sqlite_store import SQLiteStore
from conftest import TEST_API_KEY

KEY = {"X-API-Key": TEST_API_KEY}
SEEDS = pathlib.Path(__file__).resolve().parents[1] / "supabase" / "schema.sql"


@pytest.fixture
def sqlite(tmp_path, monkeypatch):
    """Point the app at a fresh SQLite file seeded from schema.sql."""
    monkeypatch.setattr(settings, "STORAGE", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", str(tmp_path / "lapidary.db"))
    monkeypatch.setattr(settings, "SEED_SQL_FILE", str(SEEDS))
    storage.reset_store()
    yield storage.get_store()
    storage.reset_store()


def run(coro):
    return asyncio.run(coro)


def test_seed_parser_reads_every_gem_from_schema_sql() -> None:
    gems = parse_seed_gems(SEEDS.read_text())
    names = [g["name"] for g in gems]
    assert names == ["study_buddy", "writing_coach", "research_assistant", "program_builder", "windows_operator", "rea_analyst", "gem_librarian", "base_assistant", "code_reviewer", "creative_writer", "summarizer", "engineering_lead", "prompt_enhancer"]
    builder = next(g for g in gems if g["name"] == "program_builder")
    assert builder["kind"] == "agent" and builder["tools"] == ["run_powershell"] and builder["provider"] == "auto"
    assert "writer's voice" in next(g for g in gems if g["name"] == "writing_coach")["system_prompt"]
    lib = next(g for g in gems if g["name"] == "gem_librarian")
    assert lib["kind"] == "agent" and lib["tools"] == ["search_gems", "get_gem", "resolve_gem"]
    cr = next(g for g in gems if g["name"] == "code_reviewer")
    assert cr["kind"] == "prompt" and cr["variables"] == ["language"] and "{{gem:base_assistant}}" in cr["system_prompt"]
    assert "don't tell" in next(g for g in gems if g["name"] == "creative_writer")["system_prompt"]   # '' escape handled


def test_fresh_database_is_seeded_once(sqlite) -> None:
    names = [g.name for g in run(sqlite.list_gems())]
    assert "base_assistant" in names and "rea_analyst" in names and len(names) == 13
    again = SQLiteStore(settings.SQLITE_PATH, seed_sql_file=str(SEEDS))   # reopening does not duplicate
    assert len(run(again.list_gems())) == 13
    again.close()


def test_crud_and_soft_delete_through_gem_service(sqlite) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="greeter", description="d", system_prompt="Hi {who}.", tags=["t"])))
    assert gem.variables == ["who"] and gem.kind == "prompt" and gem.provider == settings.DEFAULT_PROVIDER
    updated = run(gem_service.update_gem(gem.id, GemUpdate(system_prompt="Hi {who} from {where}.", kind="agent", tools=["get_gem"])))
    assert updated.variables == ["where", "who"] and updated.kind == "agent" and updated.tools == ["get_gem"]
    assert run(gem_service.get_gem_by_name("greeter")).id == gem.id
    run(gem_service.soft_delete_gem(gem.id))
    assert run(gem_service.get_gem_by_name("greeter")) is None
    assert run(gem_service.get_gem_by_id(gem.id)).is_active is False


def test_the_resolver_works_on_the_seeded_library(sqlite) -> None:
    result = run(gem_service.resolve_gem_detailed("engineering_lead", {"language": "Python", "team_size": "4"}))
    assert result.referenced_gems == ["code_reviewer", "base_assistant"]
    assert "You are a highly capable AI assistant" in result.resolved_prompt
    assert "follow Python conventions" in result.resolved_prompt and "Assume 4 engineers" in result.resolved_prompt
    assert result.variables_missing == []


def test_runs_events_and_state_round_trip(sqlite) -> None:
    r = run(sqlite.create_run(None, "gem_librarian", "m", "anthropic", "hello"))
    assert r.status == "running" and r.steps == 0
    run(sqlite.add_event(r.id, 1, "run_started", {"tools": ["get_gem"]}))
    run(sqlite.add_event(r.id, 2, "model_turn", {"text": "hi", "tool_calls": []}))
    paused = run(sqlite.update_run(r.id, status="waiting_approval", state={"messages": [{"role": "user", "content": "x"}], "pending": [{"id": "1"}]}))
    assert paused.status == "waiting_approval"
    assert run(sqlite.get_run_state(r.id)) == {"messages": [{"role": "user", "content": "x"}], "pending": [{"id": "1"}]}
    done = run(sqlite.update_run(r.id, status="finished", output="hi", steps=1, state=None, finished_at="2026-10-25T00:00:00+00:00"))
    assert done.finished_at is not None and run(sqlite.get_run_state(r.id)) is None
    got_run, events = run(sqlite.get_run(r.id))
    assert got_run.output == "hi" and [e.type for e in events] == ["run_started", "model_turn"] and events[0].data == {"tools": ["get_gem"]}
    assert run(sqlite.get_run("nope")) is None


def test_routes_end_to_end_on_sqlite(client, sqlite) -> None:
    names = [g["name"] for g in client.get("/gems/", headers=KEY).json()]
    assert "prompt_enhancer" in names and len(names) == 13
    created = client.post("/gems/", headers=KEY, json={"name": "haiku", "description": "", "system_prompt": "{{gem:base_assistant}} Write a haiku about {topic}."}).json()
    assert created["variables"] == ["topic"] and created["model"] == settings.DEFAULT_MODEL
    assert client.post("/gems/", headers=KEY, json={"name": "haiku", "system_prompt": "x"}).status_code == 400
    resolved = client.post("/gems/resolve", headers=KEY, json={"gem_name": "haiku", "variables": {"topic": "rain"}}).json()
    assert resolved["referenced_gems"] == ["base_assistant"] and resolved["resolved_prompt"].endswith("Write a haiku about rain.")
    assert client.put("/gems/haiku", headers=KEY, json={"description": "17 syllables"}).json()["description"] == "17 syllables"
    assert client.delete("/gems/haiku", headers=KEY).status_code == 200
    assert client.get("/gems/haiku", headers=KEY).status_code == 404
    models = client.get("/v1/models", headers=KEY).json()["data"]
    assert any(m["id"] == "rea_analyst" and m["lapidary"]["kind"] == "agent" for m in models)
