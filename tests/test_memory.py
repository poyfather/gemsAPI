"""Lapidary Memory (ADR-010): private text, the digest, recall, the tools, the routes, capture from runs, and the SQLite store's search."""
import asyncio
from datetime import datetime, timezone

import pytest

import app.agents.builtin  # noqa: F401
from app import settings
from app.agents import runner
import json

from app.agents.tools import call_tool, get_tool
from app.models import Run, RunEvent
from app.services import memory_service
from app.storage.sqlite_store import SQLiteStore
from conftest import TEST_API_KEY, make_gem
from test_runner import fake_turns

KEY = {"X-API-Key": TEST_API_KEY}


def run(coro):
    return asyncio.run(coro)


def test_private_text_is_never_stored() -> None:
    assert memory_service.strip_private("Keep this. <private>not this</private> And this.") == "Keep this. And this."
    assert memory_service.strip_private("<PRIVATE>only\nsecrets</PRIVATE>") == ""
    assert memory_service.strip_private("Keep. <private>unclosed and the rest goes too") == "Keep."
    assert memory_service.strip_private("<private>" * 5000 + "x") == "", "many tags cannot make it slow (CodeQL py/polynomial-redos)"
    assert run(memory_service.remember("<private>x</private>")) is None


def test_remember_checks_kind_and_source_and_trims_tags(fake_memory) -> None:
    m = run(memory_service.remember("Prefers short answers.", kind="preference", tags=[" Style ", ""], source="user"))
    assert m.kind == "preference" and m.tags == ["style"] and m.scope == "default"
    with pytest.raises(ValueError):
        run(memory_service.remember("x", kind="wish"))
    with pytest.raises(ValueError):
        run(memory_service.remember("x", source="elsewhere"))


def test_search_index_is_compact_and_get_returns_full_text(fake_memory) -> None:
    long = "First line about the budget spreadsheet\n" + "x" * 500
    m = run(memory_service.remember(long, kind="note"))
    run(memory_service.remember("Unrelated thing about cats"))
    idx = run(memory_service.search_index("budget"))
    assert [e.id for e in idx] == [m.id] and idx[0].line == "First line about the budget spreadsheet"
    full = run(memory_service.get([m.id, "missing"]))
    assert len(full) == 1 and full[0].text == long
    assert run(memory_service.forget(m.id)) is True and run(memory_service.forget(m.id)) is False


def test_recall_block_lists_matches_and_stays_within_the_cap(fake_memory) -> None:
    assert run(memory_service.recall_block("anything")) == ""
    run(memory_service.remember("Decided to keep the data folder under AppData.", kind="decision"))
    run(memory_service.remember("Lesson: docker compose needs Docker Desktop running first.", kind="lesson"))
    block = run(memory_service.recall_block("where is the data folder"))
    assert block.startswith("<memory>") and block.endswith("</memory>") and "[decision, 2026-01-02] Decided to keep" in block
    assert "docker" not in block
    capped = run(memory_service.recall_block("docker data folder", max_chars=60))
    assert capped.count("\n- [") == 1 and capped.rstrip("\n</memory>").endswith("...")


def _finished_run(**over) -> Run:
    base = dict(id="run-9", gem_name="windows_operator", status="finished", model="m", provider="local", input="How much disk space is free? <private>my password is x</private>",
                output="About 120 GB free on C:.", steps=2, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    base.update(over)
    return Run(**base)


def _ev(seq, type_, **data) -> RunEvent:
    return RunEvent(seq=seq, type=type_, data=data, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_digest_names_tools_errors_denials_and_the_outcome() -> None:
    events = [_ev(1, "tool_call", name="run_powershell"), _ev(2, "tool_result", name="run_powershell", is_error=True),
              _ev(3, "tool_call", name="run_powershell"), _ev(4, "approval_decided", name="run_powershell", approved=False)]
    text = memory_service.digest(_finished_run(status="max_steps"), events)
    assert "windows_operator was asked: How much disk space is free?" in text and "password" not in text
    assert "Tools used: run_powershell x2. 1 tool error. 1 call denied." in text
    assert "Outcome: stopped at the step limit after 2 steps." in text and "It said: About 120 GB" in text
    failed = memory_service.digest(_finished_run(status="failed", error="ProviderError: boom", output=None), [])
    assert "failed (ProviderError: boom)" in failed and "It said" not in failed


def test_a_finished_run_leaves_an_observation(fake_library, fake_runs, fake_memory, monkeypatch) -> None:
    fake_library["g"] = make_gem("g", "Be brief.")
    fn, _ = fake_turns([("Done: moved the files.", [])])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = run(runner.run_agent("g", "move my files", memory_scope="home"))
    assert result.run.status == "finished"
    assert len(fake_memory) == 1
    m = fake_memory[0]
    assert m.kind == "observation" and m.source == "run" and m.gem_name == "g" and m.run_id == result.run.id and m.scope == "home"
    assert "g was asked: move my files" in m.text and "It said: Done: moved the files." in m.text


def test_capture_can_be_switched_off_and_never_breaks_a_run(fake_library, fake_runs, fake_memory, monkeypatch) -> None:
    fake_library["g"] = make_gem("g", "Be brief.")
    fn, _ = fake_turns([("ok", [])])
    monkeypatch.setattr(runner, "complete_turn", fn)
    monkeypatch.setattr(settings, "MEMORY_CAPTURE", False)
    assert run(runner.run_agent("g", "hi")).run.status == "finished" and fake_memory == []
    monkeypatch.setattr(settings, "MEMORY_CAPTURE", True)

    async def boom(*a, **k):
        raise RuntimeError("db gone")

    monkeypatch.setattr(memory_service, "remember", boom)
    assert run(runner.run_agent("g", "hi")).run.status == "finished"


def test_a_gem_with_memory_on_gets_the_matches_in_its_prompt(fake_library, fake_runs, fake_memory, monkeypatch) -> None:
    run(memory_service.remember("The project folder is D:\\work\\shop.", kind="decision"))
    fake_library["g"] = make_gem("g", "Help with files.", memory=True)
    fake_library["plain"] = make_gem("plain", "Help with files.")
    fn, seen = fake_turns([("ok", [])])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = run(runner.run_agent("g", "open the project folder"))
    assert "<memory>" in seen[0]["system"] and "D:\\work\\shop" in seen[0]["system"]
    assert [e.type for e in result.events][:2] == ["run_started", "memory_recalled"]
    run(runner.run_agent("plain", "open the project folder"))
    assert "<memory>" not in seen[1]["system"]


def test_the_summarizer_writes_the_observation_when_it_can(fake_library, fake_runs, fake_memory, monkeypatch) -> None:
    fake_library["g"] = make_gem("g", "Be brief.")
    fake_library["memory_summarizer"] = make_gem("memory_summarizer", "Summarize.")
    fn, _ = fake_turns([("ok", [])])
    monkeypatch.setattr(runner, "complete_turn", fn)
    monkeypatch.setattr(settings, "MEMORY_SUMMARIZE", True)

    async def fake_complete(system_prompt, messages, model, provider, max_tokens=None):
        assert "Transcript:" in messages[0]["content"]
        return "The user asked g to say hi; it answered ok. <private>drop</private>"

    from app.services import llm_service
    monkeypatch.setattr(llm_service, "complete", fake_complete)
    run(runner.run_agent("g", "hi"))
    assert fake_memory[0].text == "The user asked g to say hi; it answered ok." and fake_memory[0].tags == ["summarized"]

    async def broken(*a, **k):
        raise RuntimeError("no model")

    monkeypatch.setattr(llm_service, "complete", broken)
    run(runner.run_agent("g", "hi again"))
    assert fake_memory[1].text.startswith("g was asked: hi again") and fake_memory[1].tags == []


def test_the_memory_tools_search_fetch_remember_and_forget(fake_memory) -> None:
    call = lambda name, args: json.loads(run(call_tool(get_tool(name), args)))  # noqa: E731 - tools render JSON for the model
    out = call("remember", {"text": "Use tabs, not spaces.", "kind": "preference", "tags": ["style"]})
    assert out["kind"] == "preference" and out["source"] == "run"
    idx = call("search_memory", {"query": "tabs"})
    assert len(idx) == 1 and idx[0]["line"] == "Use tabs, not spaces."
    full = call("get_memories", {"ids": [idx[0]["id"]]})
    assert full[0]["text"] == "Use tabs, not spaces."
    assert get_tool("forget").risky is True
    assert call("forget", {"memory_id": idx[0]["id"]}) == {"deleted": True, "id": idx[0]["id"]}
    assert call("remember", {"text": "x", "kind": "nope"})["error"].startswith("kind must be")


def test_memory_routes(client, fake_memory) -> None:
    r = client.post("/memory/", json={"text": "Prefers dark mode. <private>pin 1234</private>", "kind": "preference", "tags": ["ui"]}, headers=KEY)
    assert r.status_code == 201 and r.json()["text"] == "Prefers dark mode." and r.json()["tags"] == ["ui"]
    mid = r.json()["id"]
    assert client.post("/memory/", json={"text": "<private>all secret</private>"}, headers=KEY).status_code == 400
    assert client.post("/memory/", json={"text": "x", "kind": "wish"}, headers=KEY).status_code == 400
    assert [m["id"] for m in client.get("/memory/?q=dark", headers=KEY).json()] == [mid]
    assert client.get("/memory/?kind=lesson", headers=KEY).json() == []
    idx = client.get("/memory/search?q=mode", headers=KEY).json()
    assert idx[0]["line"] == "Prefers dark mode." and "text" not in idx[0]
    assert client.get(f"/memory/{mid}", headers=KEY).json()["kind"] == "preference"
    assert client.delete(f"/memory/{mid}", headers=KEY).status_code == 204
    assert client.delete(f"/memory/{mid}", headers=KEY).status_code == 404
    assert client.get("/memory/", headers={}).status_code == 401


def test_a_chat_with_a_memory_gem_recalls_for_the_last_user_message(client, fake_library, fake_memory, monkeypatch) -> None:
    run(memory_service.remember("The customer's name is Ada Lovelace.", kind="note"))
    fake_library["m"] = make_gem("m", "Answer briefly.", memory=True)
    seen = {}

    async def fake_complete(system_prompt, messages, model, provider, max_tokens=None):
        seen["system"] = system_prompt
        return "Ada."

    from app.routes import chat as chat_route
    monkeypatch.setattr(chat_route, "complete", fake_complete)
    r = client.post("/chat/", json={"gem_name": "m", "messages": [{"role": "user", "content": "who is the customer?"}]}, headers=KEY)
    assert r.status_code == 200 and "<memory>" in seen["system"] and "Ada Lovelace" in seen["system"]


def test_sqlite_memories_have_full_text_search(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path / "m.db"))
    from app.models import MemoryCreate

    a = run(store.add_memory(MemoryCreate(text="Installed Ollama and pulled qwen3:4b for the private chat.", kind="observation", tags=["setup"], source="run")))
    b = run(store.add_memory(MemoryCreate(text="Prefers answers in British English.", kind="preference", scope="writing")))
    run(store.add_memory(MemoryCreate(text="Docker Desktop must be running before compose up (lesson).", kind="lesson")))
    hits = run(store.search_memories("ollama private chat", scope="default", kinds=None, limit=10))
    assert [m.id for m in hits] == [a.id]
    assert [m.id for m in run(store.search_memories("", scope="writing", kinds=None, limit=10))] == [b.id]
    assert run(store.search_memories("english", scope="default", kinds=None, limit=10)) == []     # scoped out
    assert [m.kind for m in run(store.search_memories("", scope=None, kinds=["lesson"], limit=10))] == ["lesson"]
    assert run(store.search_memories('"unbalanced OR (', scope=None, kinds=None, limit=5)) == []  # syntax in the query cannot break it
    assert [m.id for m in run(store.get_memories([b.id, a.id]))] == [b.id, a.id]
    assert run(store.delete_memory(a.id)) is True and run(store.search_memories("ollama", scope=None, kinds=None, limit=5)) == []
    gem = run(store.create_gem(__import__("app.models", fromlist=["GemCreate"]).GemCreate(name="mem", system_prompt="x", memory=True), []))
    assert gem.memory is True and run(store.update_gem(gem.id, {"memory": False})).memory is False
    store.close()
