"""Evals per gem (roadmap 28): the checks, the estimate and cap, runs with a faked model, the judge, baselines and regressions, routes and MCP, on a real SQLite store."""
import asyncio
import json
import pathlib

import pytest

from app import settings, storage
from app.models import EvalCaseCreate, GemCreate, GemUpdate
from app.services import eval_service, gem_service, llm_service
from conftest import TEST_API_KEY

KEY = {"X-API-Key": TEST_API_KEY}
SEEDS = pathlib.Path(__file__).resolve().parents[1] / "supabase" / "schema.sql"


@pytest.fixture
def sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", str(tmp_path / "lapidary.db"))
    monkeypatch.setattr(settings, "SEED_SQL_FILE", str(SEEDS))
    storage.reset_store()
    yield storage.get_store()
    storage.reset_store()


@pytest.fixture
def model(monkeypatch):
    """llm_service.complete stand-in: answers from a dict keyed by the user message; the judge passes when the answer says 'good'."""
    answers: dict[str, str] = {}
    calls: list[dict] = []

    async def complete(system_prompt, messages, model_name, provider, max_tokens=None):
        msg = messages[-1]["content"]
        calls.append({"system": system_prompt, "message": msg, "max_tokens": max_tokens, "provider": provider})
        if "<criteria>" in msg:
            return "It meets the criteria.\nVERDICT: PASS" if "good" in msg.split("<answer>")[1] else "It does not.\nVERDICT: FAIL"
        return answers.get(msg, "")

    monkeypatch.setattr(llm_service, "complete", complete)
    return answers, calls


def run(coro):
    return asyncio.run(coro)


def test_the_checks() -> None:
    c = eval_service.check_answer
    assert c("contains", "Paris", "The capital is paris.")[0] and not c("contains", "Rome", "Paris")[0]
    assert c("not_contains", "sorry", "Here you go")[0] and not c("not_contains", "sorry", "Sorry, no")[0]
    ok, why = c("all_of", "TL;DR\nbullet\n\n", "TL;DR: x\n- bullet")
    assert ok and why == "found all 2"
    ok, why = c("all_of", "TL;DR\nquestion", "TL;DR only")
    assert not ok and "question" in why
    assert c("equals", " yes ", "yes\n")[0] and not c("equals", "yes", "yes!")[0]
    schema = json.dumps({"type": "object", "required": ["title", "tags"], "properties": {"title": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}, "level": {"enum": ["low", "high"]}}})
    assert c("json", schema, '```json\n{"title": "x", "tags": ["a"], "level": "low"}\n```')[0]
    ok, why = c("json", schema, '{"title": 3, "tags": ["a", 2], "level": "mid"}')
    assert not ok and "$.title should be string" in why and "$.tags[1] should be string" in why and "$.level should be one of" in why
    assert "missing 'tags'" in c("json", schema, '{"title": "x"}')[1]
    assert not c("json", "", "not json")[0] and c("json", "", "[1, 2]")[0]
    assert c("json", json.dumps({"type": "integer"}), "true")[0] is False, "a boolean is not an integer"


def test_case_validation(sqlite) -> None:
    gem = run(gem_service.get_gem_by_name("summarizer"))
    with pytest.raises(ValueError, match="check must be one of"):
        run(eval_service.add_case(gem, EvalCaseCreate(input="x", check="regex", expected="a+")))
    with pytest.raises(ValueError, match="needs something in expected"):
        run(eval_service.add_case(gem, EvalCaseCreate(input="x", check="contains", expected="  ")))
    with pytest.raises(ValueError, match="JSON schema"):
        run(eval_service.add_case(gem, EvalCaseCreate(input="x", check="json", expected="{not json")))
    assert run(eval_service.add_case(gem, EvalCaseCreate(input="x", check="json", expected=""))).check == "json"


def test_a_run_scores_records_the_version_and_the_first_run_is_the_baseline(sqlite, model) -> None:
    answers, calls = model
    gem = run(gem_service.create_gem(GemCreate(name="capitals", system_prompt="Answer with the capital of {country} only.", provider="anthropic", model="m")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="france", input="France?", variables={"country": "France"}, check="contains", expected="Paris")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="japan", input="Japan?", variables={"country": "Japan"}, check="equals", expected="Tokyo")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="polite", input="Thanks!", check="judge", expected="Is it good and polite?")))
    answers.update({"France?": "Paris", "Japan?": "Tokyo.", "Thanks!": "good, you are welcome"})
    est = run(eval_service.estimate(gem))
    assert est.cases == 3 and est.calls == 4 and est.free is False and est.provider == "anthropic" and est.max_output_tokens == 3 * settings.EVAL_MAX_TOKENS + eval_service.JUDGE_MAX_TOKENS
    report = run(eval_service.run(gem))
    r = report.run
    assert (r.passed, r.total, r.gem_version, r.baseline) == (2, 3, 1, True) and report.baseline is None
    assert [x.passed for x in r.results] == [True, False, True] and r.results[1].detail == "differs from the expected text"
    assert calls[0]["system"] == "Answer with the capital of France only." and calls[0]["max_tokens"] == settings.EVAL_MAX_TOKENS
    assert len(calls) == 4, "three answers and one judge call"


def test_a_later_run_lists_regressions_and_fixes_against_the_baseline(sqlite, model) -> None:
    answers, _ = model
    gem = run(gem_service.create_gem(GemCreate(name="g", system_prompt="v1", provider="anthropic", model="m")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="a", input="A", check="contains", expected="alpha")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="b", input="B", check="contains", expected="beta")))
    answers.update({"A": "alpha", "B": "nope"})
    first = run(eval_service.run(gem)).run
    gem = run(gem_service.update_gem(gem.id, GemUpdate(system_prompt="v2", note="rewrite")))
    answers.update({"A": "nope", "B": "beta"})
    second = run(eval_service.run(gem))
    assert second.run.gem_version == 2 and second.run.baseline is False and second.baseline.id == first.id
    assert second.regressions == ["a"] and second.fixed == ["b"]
    assert run(eval_service.set_baseline(gem, second.run.id)).baseline is True
    listed = run(eval_service.runs(gem))
    assert [x.id for x in listed] == [second.run.id, first.id] and [x.baseline for x in listed] == [True, False]


def test_the_call_cap_refuses_a_run_and_no_cases_is_an_error(sqlite, model, monkeypatch) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="capped", system_prompt="x", provider="anthropic", model="m")))
    with pytest.raises(eval_service.EvalError, match="no eval cases"):
        run(eval_service.run(gem))
    for i in range(3):
        run(eval_service.add_case(gem, EvalCaseCreate(input=f"q{i}", check="judge", expected="good")))
    with pytest.raises(eval_service.EvalError, match="needs 6 model calls and the cap is 5"):
        run(eval_service.run(gem, max_calls=5))
    monkeypatch.setattr(settings, "EVAL_MAX_CALLS", 4)
    with pytest.raises(eval_service.EvalError, match="cap is 4"):
        run(eval_service.run(gem, max_calls=100)), "a request cannot raise the cap"


def test_a_case_that_errors_fails_alone(sqlite, model, monkeypatch) -> None:
    answers, _ = model
    gem = run(gem_service.create_gem(GemCreate(name="flaky", system_prompt="x", provider="anthropic", model="m")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="ok", input="fine", check="contains", expected="yes")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="boom", input="explode", check="contains", expected="yes")))
    answers["fine"] = "yes"
    real = llm_service.complete

    async def sometimes(system_prompt, messages, model_name, provider, max_tokens=None):
        if messages[-1]["content"] == "explode":
            raise RuntimeError("provider down")
        return await real(system_prompt, messages, model_name, provider, max_tokens)

    monkeypatch.setattr(llm_service, "complete", sometimes)
    r = run(eval_service.run(gem)).run
    assert [x.passed for x in r.results] == [True, False] and "provider down" in r.results[1].detail


def test_local_runs_are_marked_free(sqlite) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="loc", system_prompt="x", provider="local", model="qwen3:4b")))
    run(eval_service.add_case(gem, EvalCaseCreate(input="hi", check="contains", expected="hello")))
    est = run(eval_service.estimate(gem, provider_override="local", model_override="qwen3:4b"))
    assert est.free is True and est.provider == "local"


def test_eval_routes(client, sqlite, model) -> None:
    answers, _ = model
    client.post("/gems/", headers=KEY, json={"name": "r1", "system_prompt": "Say hi.", "provider": "anthropic", "model": "m"})
    r = client.post("/gems/r1/evals", headers=KEY, json={"name": "greets", "input": "hello", "check": "contains", "expected": "hi"})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert client.post("/gems/r1/evals", headers=KEY, json={"input": "x", "check": "regex", "expected": "a"}).status_code == 400
    assert client.put(f"/gems/r1/evals/{cid}", headers=KEY, json={"expected": "hi there"}).json()["expected"] == "hi there"
    assert client.put(f"/gems/r1/evals/{cid}", headers=KEY, json={"check": "contains", "expected": ""}).status_code == 400
    assert client.put("/gems/r1/evals/nope", headers=KEY, json={"name": "x"}).status_code == 404
    assert [c["name"] for c in client.get("/gems/r1/evals", headers=KEY).json()] == ["greets"]
    est = client.get("/gems/r1/evals/estimate", headers=KEY).json()
    assert est["cases"] == 1 and est["calls"] == 1
    answers["hello"] = "hi there, friend"
    rep = client.post("/gems/r1/evals/run", headers=KEY, json={}).json()
    assert rep["run"]["passed"] == 1 and rep["run"]["baseline"] is True
    runs = client.get("/gems/r1/evals/runs", headers=KEY).json()
    assert len(runs) == 1
    assert client.post(f"/gems/r1/evals/runs/{runs[0]['id']}/baseline", headers=KEY).status_code == 200
    assert client.post("/gems/r1/evals/runs/nope/baseline", headers=KEY).status_code == 404
    assert client.delete(f"/gems/r1/evals/{cid}", headers=KEY).status_code == 204
    assert client.post("/gems/r1/evals/run", headers=KEY).status_code == 409
    assert client.get("/gems/nope/evals", headers=KEY).status_code == 404
    assert client.get("/gems/r1/evals", headers={}).status_code == 401


def test_mcp_eval_tools(sqlite, model) -> None:
    import mcp_server

    answers, _ = model
    run(mcp_server.create_gem(name="m1", description="", system_prompt="x", provider="anthropic", model="m"))
    assert "error" in run(mcp_server.add_gem_eval("m1", "q", check="bogus", expected="x"))
    assert run(mcp_server.add_gem_eval("m1", "q", check="contains", expected="ok", case_name="basic"))["name"] == "basic"
    assert run(mcp_server.run_gem_evals("m1", estimate_only=True))["calls"] == 1
    answers["q"] = "ok"
    assert run(mcp_server.run_gem_evals("m1"))["run"]["passed"] == 1
    assert "error" in run(mcp_server.run_gem_evals("nope"))


def test_agent_gems_are_answered_by_a_run_and_an_approval_stop_fails_the_case(sqlite, monkeypatch) -> None:
    from app.agents import runner
    from app.agents.tools import tool
    from app.agents import tools as tools_mod
    from app.services.llm_service import ToolCall
    from test_runner import fake_turns

    monkeypatch.setattr(tools_mod, "_REGISTRY", dict(tools_mod._REGISTRY))

    @tool(name="dangerous_t", risky=True)
    async def dangerous_t() -> str:
        """Changes things (test double)."""
        return "done"

    gem = run(gem_service.create_gem(GemCreate(name="ag", system_prompt="Help.", kind="agent", tools=["dangerous_t"], provider="anthropic", model="m")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="plain", input="hi", check="contains", expected="hello")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="risky", input="change it", check="contains", expected="done")))
    script = {"hi": [("hello there", [])], "change it": [("", [ToolCall(id="c1", name="dangerous_t", input={})])]}

    async def complete_turn(system_prompt, messages, model_name, provider, tools, max_tokens=None):
        fn, _ = fake_turns(script[messages[0]["content"]])
        return await fn(system_prompt, messages, model_name, provider, tools, max_tokens)

    monkeypatch.setattr(runner, "complete_turn", complete_turn)
    r = run(eval_service.run(gem)).run
    assert [x.passed for x in r.results] == [True, False]
    assert r.results[0].output == "hello there" and "approval" in r.results[1].detail
