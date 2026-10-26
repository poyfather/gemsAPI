"""Side-by-side runs (roadmap 30): versions and AIs in columns, on a question or the tests, on a real SQLite store with a faked model."""
import asyncio

import pytest

from app import settings
from app.models import CompareRequest, CompareVariant, EvalCaseCreate, GemCreate, GemUpdate
from app.services import compare_service, eval_service, gem_service, llm_service
from conftest import TEST_API_KEY

KEY = {"X-API-Key": TEST_API_KEY}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def model(monkeypatch):
    """Answers say which AI answered and with which prompt; 'boom' as a model fails; the judge passes answers that mention 'v2'."""
    calls = []

    async def complete(system_prompt, messages, model_name, provider, max_tokens=None):
        msg = messages[-1]["content"]
        calls.append({"provider": provider, "model": model_name, "system": system_prompt, "message": msg, "max_tokens": max_tokens})
        if model_name == "boom":
            raise RuntimeError("provider down")
        if "<criteria>" in msg:
            answer = msg.split("<answer>")[1].split("</answer>")[0]
            return "ok\nVERDICT: PASS" if "v2" in answer else "no\nVERDICT: FAIL"
        return f"[{provider}/{model_name}] {system_prompt} | {msg}"

    monkeypatch.setattr(llm_service, "complete", complete)
    return calls


def two_versions():
    gem = run(gem_service.create_gem(GemCreate(name="tone", system_prompt="v1 says {x}", provider="openai", model="gpt-old")))
    return run(gem_service.update_gem(gem.id, GemUpdate(system_prompt="v2 says {x}", provider="anthropic", model="claude-new")))


def test_a_past_version_and_the_current_one_answer_side_by_side(sqlite, model) -> None:
    gem = two_versions()
    req = CompareRequest(message="hello", variables={"x": "hi"}, variants=[CompareVariant(version=1), CompareVariant()])
    res = run(compare_service.compare(gem, req))
    a, b = res.columns
    assert (a.version, a.provider, a.model) == (1, "openai", "gpt-old") and a.output == "[openai/gpt-old] v1 says hi | hello"
    assert (b.version, b.provider, b.model) == (2, "anthropic", "claude-new") and b.output.startswith("[anthropic/claude-new] v2 says hi")
    assert a.label == "v1 · ChatGPT (gpt-old)" and b.label == "v2 · Claude (claude-new)" and a.error == "" and a.seconds >= 0


def test_the_same_version_on_two_ais(sqlite, model) -> None:
    gem = two_versions()
    req = CompareRequest(message="q", variants=[CompareVariant(label="fast", provider_override="anthropic", model_override="haiku"),
                                                CompareVariant(label="local", provider_override="local", model_override="qwen")])
    res = run(compare_service.compare(gem, req))
    assert [c.label for c in res.columns] == ["fast", "local"] and [c.model for c in res.columns] == ["haiku", "qwen"]
    assert all("v2 says" in c.output for c in res.columns)


def test_one_column_failing_does_not_hide_the_others(sqlite, model) -> None:
    gem = two_versions()
    res = run(compare_service.compare(gem, CompareRequest(message="q", variants=[CompareVariant(model_override="boom"), CompareVariant()])))
    assert "provider down" in res.columns[0].error and res.columns[0].output == "" and res.columns[1].output


def test_refusals(sqlite, model) -> None:
    gem = two_versions()
    with pytest.raises(compare_service.CompareError, match="no version 7"):
        run(compare_service.compare(gem, CompareRequest(message="q", variants=[CompareVariant(version=7), CompareVariant()])))
    with pytest.raises(compare_service.CompareError, match="Type the question"):
        run(compare_service.compare(gem, CompareRequest(message="  ", variants=[CompareVariant(), CompareVariant()])))
    with pytest.raises(ValueError):
        CompareRequest(message="q", variants=[CompareVariant()])
    agent = run(gem_service.create_gem(GemCreate(name="ag", system_prompt="a1", kind="agent")))
    agent = run(gem_service.update_gem(agent.id, GemUpdate(system_prompt="a2")))
    with pytest.raises(compare_service.CompareError, match="only the current version"):
        run(compare_service.compare(agent, CompareRequest(message="q", variants=[CompareVariant(version=1), CompareVariant()])))


def test_an_assistant_compares_two_ais_through_full_runs(sqlite, monkeypatch) -> None:
    from app.agents import runner
    from test_runner import fake_turns

    gem = run(gem_service.create_gem(GemCreate(name="ag2", system_prompt="Help.", kind="agent", provider="anthropic", model="m")))

    async def complete_turn(system_prompt, messages, model_name, provider, tools, max_tokens=None):
        fn, _ = fake_turns([(f"answer from {model_name}", [])])
        return await fn(system_prompt, messages, model_name, provider, tools, max_tokens)

    monkeypatch.setattr(runner, "complete_turn", complete_turn)
    res = run(compare_service.compare(gem, CompareRequest(message="go", variants=[CompareVariant(model_override="m1"), CompareVariant(model_override="m2")])))
    assert [c.output for c in res.columns] == ["answer from m1", "answer from m2"] and all(c.run_id for c in res.columns)


def test_resolve_text_expands_references_as_the_library_is_now(sqlite) -> None:
    out = run(gem_service.resolve_text("mine", "{{gem:base_assistant}}\nNow {task}.", {"task": "sing"}))
    assert out.startswith("You are a highly capable AI assistant") and out.endswith("Now sing.")
    with pytest.raises(ValueError, match="Circular"):
        run(gem_service.resolve_text("base_assistant", "{{gem:base_assistant}}"))


def test_comparing_on_the_tests_gives_a_grid_with_totals(sqlite, model) -> None:
    gem = two_versions()
    run(eval_service.add_case(gem, EvalCaseCreate(name="mentions v2", input="which?", variables={"x": "y"}, check="contains", expected="v2 says")))
    run(eval_service.add_case(gem, EvalCaseCreate(name="judged", input="rate", variables={"x": "y"}, check="judge", expected="mentions v2")))
    req = CompareRequest(variants=[CompareVariant(version=1), CompareVariant(version=2)])
    est = run(compare_service.estimate(gem, req, on_tests=True))
    assert est.calls == 6 and est.tests == 2 and est.free is False and [c["version"] for c in est.columns] == [1, 2]
    res = run(compare_service.compare_tests(gem, req))
    assert res.totals == [0, 2] and [c["name"] for c in res.cases] == ["mentions v2", "judged"]
    assert [r["passed"] for r in res.cases[0]["results"]] == [False, True]
    assert all(c.output == "" for c in res.columns), "the grid does not carry answers"
    assert run(eval_service.runs(gem)) == [], "a comparison is not recorded as an eval run"
    model_calls = [c for c in model if "<criteria>" not in c["message"]]
    assert all(c["max_tokens"] == settings.EVAL_MAX_TOKENS for c in model_calls)


def test_the_cap_and_no_tests(sqlite, model, monkeypatch) -> None:
    gem = two_versions()
    req = CompareRequest(variants=[CompareVariant(), CompareVariant(), CompareVariant()])
    with pytest.raises(compare_service.CompareError, match="no tests"):
        run(compare_service.compare_tests(gem, req))
    for i in range(3):
        run(eval_service.add_case(gem, EvalCaseCreate(input=f"q{i}", check="contains", expected="x")))
    monkeypatch.setattr(settings, "EVAL_MAX_CALLS", 8)
    with pytest.raises(compare_service.CompareError, match="needs 9 model calls and the cap is 8"):
        run(compare_service.compare_tests(gem, req))
    local = run(compare_service.estimate(gem, CompareRequest(message="q", variants=[CompareVariant(provider_override="local", model_override="a"), CompareVariant(provider_override="local", model_override="b")])))
    assert local.free is True and local.calls == 2


def test_compare_routes(client, sqlite, model) -> None:
    client.post("/gems/", headers=KEY, json={"name": "r", "system_prompt": "first", "provider": "anthropic", "model": "m"})
    client.put("/gems/r", headers=KEY, json={"system_prompt": "second"})
    body = {"message": "hi", "variants": [{"version": 1}, {}]}
    res = client.post("/gems/r/compare", headers=KEY, json=body)
    assert res.status_code == 200 and [c["version"] for c in res.json()["columns"]] == [1, 2]
    assert "first" in res.json()["columns"][0]["output"] and "second" in res.json()["columns"][1]["output"]
    assert client.post("/gems/r/compare/estimate", headers=KEY, json=body).json()["calls"] == 2
    assert client.post("/gems/r/compare", headers=KEY, json={"message": "hi", "variants": [{"version": 9}, {}]}).status_code == 400
    assert client.post("/gems/r/compare", headers=KEY, json={"message": "hi", "variants": [{}]}).status_code == 422
    assert client.post("/gems/r/compare/tests", headers=KEY, json=body).status_code == 409
    client.post("/gems/r/evals", headers=KEY, json={"input": "q", "check": "contains", "expected": "second"})
    grid = client.post("/gems/r/compare/tests", headers=KEY, json=body).json()
    assert grid["totals"] == [0, 1]
    assert client.post("/gems/nope/compare", headers=KEY, json=body).status_code == 404


def test_mcp_compare_tool(sqlite, model) -> None:
    import mcp_server

    two_versions()
    est = run(mcp_server.compare_gem("tone", [{"version": 1}, {"version": 2}], message="q", estimate_only=True))
    assert est["calls"] == 2
    res = run(mcp_server.compare_gem("tone", [{"version": 1}, {}], message="q", variables={"x": "z"}))
    assert "v1 says z" in res["columns"][0]["output"] and "v2 says z" in res["columns"][1]["output"]
    assert "error" in run(mcp_server.compare_gem("tone", [{}], message="q"))
    assert "error" in run(mcp_server.compare_gem("nope", [{}, {}], message="q"))
