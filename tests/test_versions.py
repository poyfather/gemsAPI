"""Version history (roadmap 14): recording, the lazy baseline, history, diffs, revert, the routes and the MCP tools, on a real SQLite store."""
import asyncio
import pathlib

import pytest

from app.models import GemCreate, GemUpdate
from app.services import gem_service, version_service
from conftest import TEST_API_KEY

KEY = {"X-API-Key": TEST_API_KEY}
SEEDS = pathlib.Path(__file__).resolve().parents[1] / "supabase" / "schema.sql"


def run(coro):
    return asyncio.run(coro)


def test_create_records_version_one_and_each_real_change_records_another(sqlite) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="tone", description="d", system_prompt="Be kind.", tags=["x"])))
    run(gem_service.update_gem(gem.id, GemUpdate(system_prompt="Be kind.\nBe brief.", note="shorter answers")))
    run(gem_service.update_gem(gem.id, GemUpdate(description="d")))           # no change: no new version
    run(gem_service.update_gem(gem.id, GemUpdate(tags=["x", "style"])))
    found = run(version_service.versions(gem.id))
    assert [v.version for v in found] == [1, 2, 3]
    assert [v.note for v in found] == ["created", "shorter answers", ""]
    assert found[1].snapshot["system_prompt"] == "Be kind.\nBe brief." and found[2].snapshot["tags"] == ["x", "style"]
    history = run(version_service.history(run(gem_service.get_gem_by_id(gem.id))))
    assert [h.version for h in history] == [3, 2, 1] and history[0].current and not history[1].current
    assert history[0].changed == ["tags"] and history[1].changed == ["system_prompt"] and history[2].changed == []


def test_a_gem_from_before_history_gets_a_baseline_on_its_first_change(sqlite) -> None:
    seed = run(gem_service.get_gem_by_name("summarizer"))
    assert run(version_service.versions(seed.id)) == []
    shown = run(version_service.history(seed))
    assert len(shown) == 1 and shown[0].source == "baseline" and shown[0].current
    original = seed.system_prompt
    run(gem_service.update_gem(seed.id, GemUpdate(system_prompt=original + "\nAlways end with one question.", note="engagement")))
    found = run(version_service.versions(seed.id))
    assert [(v.version, v.source) for v in found] == [(1, "baseline"), (2, "api")]
    assert found[0].snapshot["system_prompt"] == original and found[0].note == version_service.BASELINE_NOTE


def test_diff_shows_the_prompt_as_a_unified_diff_and_other_fields_as_from_and_to(sqlite) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="d1", system_prompt="line one\nline two\nline three", model="m1", provider="anthropic")))
    run(gem_service.update_gem(gem.id, GemUpdate(system_prompt="line one\nline 2\nline three", model="m2")))
    d = run(version_service.diff(run(gem_service.get_gem_by_id(gem.id))))
    assert (d.from_version, d.to_version) == (1, 2) and d.changed == ["system_prompt", "model"]
    assert d.fields == {"model": {"from": "m1", "to": "m2"}}
    assert "--- d1 v1" in d.prompt_diff and "+++ d1 v2" in d.prompt_diff and "-line two" in d.prompt_diff and "+line 2" in d.prompt_diff
    same = run(version_service.diff(run(gem_service.get_gem_by_id(gem.id)), 2, 2))
    assert same.changed == [] and same.prompt_diff == ""
    with pytest.raises(LookupError):
        run(version_service.diff(gem, 1, 9))


def test_revert_restores_the_fields_as_a_new_version_and_keeps_the_name(sqlite) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="rv", system_prompt="v1 text {a}", tags=["one"])))
    run(gem_service.update_gem(gem.id, GemUpdate(system_prompt="v2 text {b}", tags=["two"])))
    restored = run(version_service.revert(run(gem_service.get_gem_by_id(gem.id)), 1, "v2 broke the tests"))
    assert restored.system_prompt == "v1 text {a}" and restored.tags == ["one"] and restored.variables == ["a"] and restored.name == "rv"
    found = run(version_service.versions(gem.id))
    assert [v.version for v in found] == [1, 2, 3] and found[2].source == "revert" and found[2].note == "restored version 1: v2 broke the tests"
    with pytest.raises(LookupError):
        run(version_service.revert(restored, 7))


def test_recording_failures_never_block_a_save(sqlite, monkeypatch) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="sturdy", system_prompt="a")))

    async def boom(*a, **k):
        raise RuntimeError("table missing")

    monkeypatch.setattr(sqlite, "add_gem_version", boom)
    assert run(gem_service.update_gem(gem.id, GemUpdate(system_prompt="b"))).system_prompt == "b"


def test_version_routes(client, sqlite) -> None:
    client.post("/gems/", headers=KEY, json={"name": "web", "system_prompt": "Hello {who}."})
    client.put("/gems/web", headers=KEY, json={"system_prompt": "Hello {who}, welcome.", "note": "warmer"})
    hist = client.get("/gems/web/versions", headers=KEY).json()
    assert [h["version"] for h in hist] == [2, 1] and hist[0]["note"] == "warmer" and hist[0]["changed"] == ["system_prompt"] and hist[0]["current"]
    v1 = client.get("/gems/web/versions/1", headers=KEY).json()
    assert v1["snapshot"]["system_prompt"] == "Hello {who}." and v1["note"] == "created"
    d = client.get("/gems/web/diff", headers=KEY).json()
    assert d["from_version"] == 1 and d["to_version"] == 2 and "+Hello {who}, welcome." in d["prompt_diff"]
    assert client.get("/gems/web/diff?from_version=1&to_version=5", headers=KEY).status_code == 404
    r = client.post("/gems/web/versions/1/revert", headers=KEY, json={"note": "too long"})
    assert r.status_code == 200 and r.json()["system_prompt"] == "Hello {who}."
    assert client.post("/gems/web/versions/9/revert", headers=KEY).status_code == 404
    assert client.get("/gems/web/versions/9", headers=KEY).status_code == 404
    assert client.get("/gems/nope/versions", headers=KEY).status_code == 404
    assert [h["version"] for h in client.get("/gems/web/versions", headers=KEY).json()] == [3, 2, 1]
    assert client.get("/gems/web/versions", headers={}).status_code == 401


def test_mcp_history_tools(sqlite) -> None:
    import mcp_server

    run(mcp_server.create_gem(name="mcpg", description="", system_prompt="one"))
    out = run(mcp_server.update_gem(name="mcpg", system_prompt="two", note="from Claude"))
    assert out["name"] == "mcpg"
    hist = run(mcp_server.gem_history("mcpg"))
    assert [h["version"] for h in hist] == [2, 1] and hist[0]["source"] == "mcp" and hist[0]["note"] == "from Claude" and hist[1]["source"] == "mcp"
    assert "+two" in run(mcp_server.diff_gem_versions("mcpg"))["prompt_diff"]
    assert run(mcp_server.revert_gem("mcpg", 1))["restored_version"] == 1
    assert run(mcp_server.get_gem("mcpg"))["system_prompt"] == "one"
    assert "error" in run(mcp_server.revert_gem("mcpg", 99)) and "error" in run(mcp_server.gem_history("nope"))[0]
