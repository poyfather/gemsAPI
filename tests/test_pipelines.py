"""Pipelines and gates (ADR-011): verdicts, retries with feedback, lessons, the step cap, pauses for approval and acceptance, routes and seeds."""
import asyncio
from datetime import datetime, timezone

import pytest

import app.agents.builtin  # noqa: F401
from app.agents import pipeline, runner
from app.agents.tools import tool
from app.models import Pipeline, PipelineCreate, PipelineGate
from app.services.llm_service import ToolCall, ToolTurn
from app.storage.seeds import load_seed_pipelines, parse_seed_rows
from app.storage.sqlite_store import SQLiteStore
from conftest import TEST_API_KEY, make_gem

KEY = {"X-API-Key": TEST_API_KEY}
SEEDS = __import__("pathlib").Path(__file__).resolve().parents[1] / "supabase" / "schema.sql"


def run(coro):
    return asyncio.run(coro)


def fake_model(answers, monkeypatch):
    """
    complete_turn stand-in that answers by which gem is running (its system prompt names it)
    and how many times that gem has been asked, so a gate can fail first and pass later.
    `answers` maps gem name -> list of (text, [ToolCall]) per call, last one repeating.
    """
    calls = {}
    seen = []

    async def complete_turn(system_prompt, messages, model, provider, tools, max_tokens=None):
        gem = next((g for g in answers if system_prompt.startswith(f"[{g}]")), None)
        n = calls.get(gem, 0)
        calls[gem] = n + 1
        script = answers[gem]
        text, tool_calls = script[min(n, len(script) - 1)]
        seen.append({"gem": gem, "user": messages[-1]["content"] if messages[-1]["role"] == "user" else "", "provider": provider})
        assistant = {"role": "assistant", "content": text or None}
        if tool_calls:
            assistant["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": "{}"}} for c in tool_calls]
        return ToolTurn(text=text, tool_calls=tool_calls, assistant_message=assistant, stop_reason="tool_use" if tool_calls else "end_turn",
                        input_tokens=1, output_tokens=1)

    monkeypatch.setattr(runner, "complete_turn", complete_turn)
    return seen


def setup(fake_library, fake_pipelines, *, gates=None, acceptance=False, max_attempts=3):
    fake_library["builder"] = make_gem("builder", "[builder] Build it.")
    fake_library["tester"] = make_gem("tester", "[tester] Test it.")
    fake_library["reviewer"] = make_gem("reviewer", "[reviewer] Review it.", provider="openai", model="gpt-x")
    gates = gates if gates is not None else [PipelineGate(gem="tester", role="test"), PipelineGate(gem="reviewer", role="review", provider_override="openai")]
    p = Pipeline(id="p1", name="bc", description="", builder="builder", gates=gates, max_attempts=max_attempts, acceptance=acceptance,
                 created_at=datetime(2026, 1, 3, tzinfo=timezone.utc), updated_at=datetime(2026, 1, 3, tzinfo=timezone.utc))
    fake_pipelines["pipelines"]["bc"] = p
    return p


def test_verdict_parsing_takes_the_last_line_and_treats_silence_as_a_fail() -> None:
    assert pipeline.parse_verdict("Looks fine.\nVERDICT: PASS") == ("pass", "Looks fine.")
    assert pipeline.parse_verdict("1. x is wrong\nverdict: fail\n") == ("fail", "1. x is wrong")
    assert pipeline.parse_verdict("VERDICT: PASS earlier\nactually\nVERDICT: FAIL")[0] == "fail"
    assert pipeline.parse_verdict("no verdict here")[0] == "fail" and "no VERDICT line" in pipeline.parse_verdict("no verdict here")[1]
    assert pipeline.parse_verdict(None) == ("fail", "The gate gave no answer.")


def test_every_gate_passes_first_time(fake_library, fake_runs, fake_memory, fake_pipelines, monkeypatch) -> None:
    setup(fake_library, fake_pipelines)
    seen = fake_model({"builder": [("built v1", [])], "tester": [("all green\nVERDICT: PASS", [])], "reviewer": [("fine\nVERDICT: PASS", [])]}, monkeypatch)
    result = run(pipeline.run_pipeline("bc", "make a clock"))
    r = result.run
    assert r.status == "passed" and r.output == "built v1" and len(r.attempts) == 1
    a = r.attempts[0]
    assert a.builder_status == "finished" and [g.verdict for g in a.gates] == ["pass", "pass"] and a.gates[1].findings == "fine"
    assert [e.type for e in result.events] == ["pipeline_started", "attempt_started", "builder_finished", "gate_started", "gate_finished", "gate_started", "gate_finished", "pipeline_finished"]
    assert seen[0]["user"] == "make a clock"
    assert "<task>\nmake a clock\n</task>" in seen[1]["user"] and "<output>\nbuilt v1\n</output>" in seen[1]["user"] and "test gate" in seen[1]["user"]
    assert seen[2]["provider"] == "openai", "the review gate ran on the overridden provider"
    assert fake_memory and all(m.kind == "observation" for m in fake_memory), "runs leave observations, passes leave no lesson"


def test_a_failed_gate_feeds_the_builder_and_leaves_a_lesson(fake_library, fake_runs, fake_memory, fake_pipelines, monkeypatch) -> None:
    setup(fake_library, fake_pipelines)
    seen = fake_model({
        "builder": [("built v1", []), ("built v2", [])],
        "tester": [("test_add fails: expected 4 got 5\nVERDICT: FAIL", []), ("green\nVERDICT: PASS", [])],
        "reviewer": [("ok\nVERDICT: PASS", [])],
    }, monkeypatch)
    r = run(pipeline.run_pipeline("bc", "make an adder")).run
    assert r.status == "passed" and r.output == "built v2" and len(r.attempts) == 2
    assert r.attempts[0].gates[0].verdict == "fail" and len(r.attempts[0].gates) == 1, "the review gate did not run after the test gate failed"
    assert r.attempts[1].feedback.startswith("test gate (tester) said:\ntest_add fails")
    second_builder_message = [s for s in seen if s["gem"] == "builder"][1]["user"]
    assert "make an adder" in second_builder_message and "expected 4 got 5" in second_builder_message and "attempt 2 of 3" in second_builder_message
    lessons = [m for m in fake_memory if m.kind == "lesson"]
    assert len(lessons) == 1 and "test gate (tester) failed attempt 1" in lessons[0].text and lessons[0].gem_name == "tester"


def test_the_pipeline_gives_up_after_max_attempts(fake_library, fake_runs, fake_memory, fake_pipelines, monkeypatch) -> None:
    setup(fake_library, fake_pipelines, max_attempts=2)
    fake_model({"builder": [("built", [])], "tester": [("nope\nVERDICT: FAIL", [])], "reviewer": [("ok\nVERDICT: PASS", [])]}, monkeypatch)
    result = run(pipeline.run_pipeline("bc", "x"))
    assert result.run.status == "max_attempts" and len(result.run.attempts) == 2 and result.run.output == "built"
    assert result.events[-1].data == {"status": "max_attempts", "attempts": 2}
    assert len([m for m in fake_memory if m.kind == "lesson"]) == 2


def test_acceptance_pauses_then_accept_or_reject(fake_library, fake_runs, fake_memory, fake_pipelines, monkeypatch) -> None:
    setup(fake_library, fake_pipelines, gates=[PipelineGate(gem="tester", role="test")], acceptance=True)
    fake_model({"builder": [("v1", []), ("v2", [])], "tester": [("ok\nVERDICT: PASS", [])]}, monkeypatch)
    first = run(pipeline.run_pipeline("bc", "x")).run
    assert first.status == "waiting_acceptance" and first.output == "v1"
    with pytest.raises(ValueError):
        run(pipeline.resume_pipeline(first.id))
    rejected = run(pipeline.resume_pipeline(first.id, accept=False, note="wrong colour")).run
    assert rejected.status == "waiting_acceptance" and rejected.output == "v2" and len(rejected.attempts) == 2
    assert rejected.attempts[1].feedback == "Rejected by the person who checked it: wrong colour"
    assert any(m.kind == "lesson" and "rejected at acceptance. wrong colour" in m.text for m in fake_memory)
    done = run(pipeline.resume_pipeline(first.id, accept=True))
    assert done.run.status == "passed" and done.run.finished_at is not None
    assert [e.type for e in done.events] == ["pipeline_accepted", "pipeline_finished"]
    with pytest.raises(ValueError):
        run(pipeline.resume_pipeline(first.id, accept=True))
    with pytest.raises(LookupError):
        run(pipeline.resume_pipeline("nope"))


def test_a_risky_call_pauses_the_pipeline_until_the_run_is_decided(fake_library, fake_runs, fake_memory, fake_pipelines, monkeypatch) -> None:
    setup(fake_library, fake_pipelines, gates=[PipelineGate(gem="tester", role="test")])
    from app.agents import tools as tools_mod
    monkeypatch.setattr(tools_mod, "_REGISTRY", dict(tools_mod._REGISTRY))   # the test tool is gone again afterwards

    @tool(name="write_file_t", risky=True)
    async def write_file_t(path: str = "") -> str:
        """Writes a file (test double)."""
        return "written"

    fake_library["builder"] = make_gem("builder", "[builder] Build it.", kind="agent", tools=["write_file_t"])
    fake_model({"builder": [("let me write the file", [ToolCall(id="c1", name="write_file_t", input={"path": "x"})]), ("wrote it", [])],
                "tester": [("ok\nVERDICT: PASS", [])]}, monkeypatch)
    paused = run(pipeline.run_pipeline("bc", "x")).run
    assert paused.status == "waiting_approval" and paused.waiting_run_id == paused.attempts[0].builder_run_id
    with pytest.raises(ValueError, match="still waiting"):
        run(pipeline.resume_pipeline(paused.id))
    agent_run = run(runner.resume_run(paused.waiting_run_id, True)).run
    assert agent_run.status == "finished" and agent_run.output == "wrote it"
    finished = run(pipeline.resume_pipeline(paused.id)).run
    assert finished.status == "passed" and finished.attempts[0].output == "wrote it" and finished.attempts[0].gates[0].verdict == "pass"


def test_a_failed_builder_run_counts_as_an_attempt(fake_library, fake_runs, fake_memory, fake_pipelines, monkeypatch) -> None:
    setup(fake_library, fake_pipelines, gates=[], max_attempts=2)

    async def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(runner, "complete_turn", boom)
    r = run(pipeline.run_pipeline("bc", "x")).run
    assert r.status == "max_attempts" and all(a.builder_status == "failed" for a in r.attempts) and "provider down" in r.attempts[1].feedback


def test_pipeline_routes(client, fake_library, fake_runs, fake_memory, fake_pipelines, monkeypatch) -> None:
    body = {"name": "bc", "builder": "builder", "gates": [{"gem": "tester", "role": "test"}], "max_attempts": 2, "acceptance": False}
    assert client.post("/pipelines/", json=body, headers=KEY).status_code == 201
    assert client.post("/pipelines/", json=body, headers=KEY).status_code == 400
    assert [p["name"] for p in client.get("/pipelines/", headers=KEY).json()] == ["bc"]
    assert client.put("/pipelines/bc", json={"max_attempts": 3}, headers=KEY).json()["max_attempts"] == 3
    assert client.get("/pipelines/nope", headers=KEY).status_code == 404
    fake_library["builder"] = make_gem("builder", "[builder] Build it.")
    fake_library["tester"] = make_gem("tester", "[tester] Test it.")
    fake_model({"builder": [("v1", [])], "tester": [("ok\nVERDICT: PASS", [])]}, monkeypatch)
    r = client.post("/pipelines/bc/runs", json={"message": "go"}, headers=KEY)
    assert r.status_code == 200 and r.json()["run"]["status"] == "passed"
    rid = r.json()["run"]["id"]
    assert client.get(f"/pipelines/runs/{rid}", headers=KEY).json()["attempts"][0]["gates"][0]["verdict"] == "pass"
    assert client.post(f"/pipelines/runs/{rid}/resume", json={"accept": True}, headers=KEY).status_code == 409
    assert client.post("/pipelines/runs/nope/resume", json={}, headers=KEY).status_code == 404
    assert client.post("/pipelines/nope/runs", json={"message": "go"}, headers=KEY).status_code == 404
    with client.stream("POST", "/pipelines/bc/runs", json={"message": "again", "stream": True}, headers=KEY) as s:
        text = "".join(s.iter_text())
    assert "event: pipeline_started" in text and "event: pipeline_finished" in text and text.rstrip().endswith("data: [DONE]")
    assert client.delete("/pipelines/bc", headers=KEY).status_code == 204
    assert client.get("/pipelines/", headers={}).status_code == 401


def test_seed_pipeline_parses_and_sqlite_seeds_it(tmp_path) -> None:
    rows = load_seed_pipelines(SEEDS)
    assert [r["name"] for r in rows] == ["build_and_check"]
    assert rows[0]["builder"] == "program_builder" and rows[0]["max_attempts"] == 3 and rows[0]["acceptance"] is True
    assert [g["gem"] for g in rows[0]["gates"]] == ["test_runner", "adversarial_reviewer"]
    assert parse_seed_rows("INSERT INTO t (a, b, c) VALUES ('x'::jsonb, -2, NULL) ON CONFLICT", "t") == [{"a": "x", "b": -2, "c": None}]
    store = SQLiteStore(str(tmp_path / "p.db"), seed_sql_file=str(SEEDS))
    seeded = run(store.get_pipeline("build_and_check"))
    assert seeded and seeded.gates[0].role == "test" and seeded.acceptance is True
    assert {g.name for g in run(store.list_gems())} >= {"test_runner", "adversarial_reviewer", "program_builder"}
    created = run(store.create_pipeline(PipelineCreate(name="mine", builder="program_builder", gates=[PipelineGate(gem="adversarial_reviewer")], acceptance=False)))
    assert run(store.update_pipeline("mine", {"max_attempts": 5, "acceptance": True})).max_attempts == 5
    prun = run(store.create_pipeline_run("mine", "do it"))
    updated = run(store.update_pipeline_run(prun.id, status="waiting_acceptance", attempts=[{"number": 1, "gates": []}], state={"phase": "acceptance"}))
    assert updated.attempts[0].number == 1 and run(store.get_pipeline_run_state(prun.id)) == {"phase": "acceptance"}
    assert run(store.delete_pipeline("mine")) is True and run(store.delete_pipeline("mine")) is False
    assert created.name == "mine"
    store.close()
