"""The run loop with the model faked: tool calls, results, the step cap, failures."""
import asyncio

import pytest

import app.agents.builtin  # noqa: F401
from app import settings
from app.agents import runner
from app.services.llm_service import ToolCall, ToolTurn
from conftest import make_gem


def fake_turns(script):
    """complete_turn stand-in that replays a script of (text, [ToolCall]) per step and records the messages it saw."""
    seen = []

    async def complete_turn(system_prompt, messages, model, provider, tools, max_tokens=None):
        seen.append({"system": system_prompt, "messages": list(messages), "tools": [t["name"] for t in tools], "model": model, "provider": provider})
        text, calls = script[min(len(seen) - 1, len(script) - 1)]
        assistant = {"role": "assistant", "content": text or None}
        if calls:
            assistant["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": "{}"}} for c in calls]
        return ToolTurn(text=text, tool_calls=calls, assistant_message=assistant, stop_reason="tool_use" if calls else "end_turn",
                        input_tokens=10, output_tokens=5)

    return complete_turn, seen


def run(coro):
    return asyncio.run(coro)


def test_a_prompt_gem_runs_as_a_single_turn(fake_library, fake_runs, monkeypatch) -> None:
    fake_library["g"] = make_gem("g", "Say hi to {who}.")
    fn, seen = fake_turns([("Hi Ada", [])])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = run(runner.run_agent("g", "hello", {"who": "Ada"}))
    assert result.run.status == "finished" and result.run.output == "Hi Ada" and result.run.steps == 1
    assert seen[0]["system"] == "Say hi to Ada." and seen[0]["tools"] == []
    assert [e.type for e in result.events] == ["run_started", "model_turn", "run_finished"]
    assert result.run.input_tokens == 10 and result.run.output_tokens == 5


def test_tool_calls_are_executed_and_fed_back(fake_library, fake_runs, monkeypatch) -> None:
    fake_library["base"] = make_gem("base", "BASE", tags=["base"])
    fake_library["lib"] = make_gem("lib", "You are a librarian.", kind="agent", tools=["search_gems", "get_gem"])
    fn, seen = fake_turns([
        ("Let me look.", [ToolCall(id="c1", name="search_gems", input={"tag": "base"})]),
        ("Found base.", []),
    ])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = run(runner.run_agent("lib", "what gems are tagged base?", provider_override="openai"))
    assert result.run.status == "finished" and result.run.output == "Found base." and result.run.steps == 2
    types = [e.type for e in result.events]
    assert types == ["run_started", "model_turn", "tool_call", "tool_result", "model_turn", "run_finished"]
    tool_result = next(e for e in result.events if e.type == "tool_result")
    assert '"name": "base"' in tool_result.data["output"] and tool_result.data["is_error"] is False
    # Second turn saw the assistant message and the tool message appended, OpenAI shape.
    second = seen[1]["messages"]
    assert second[1]["role"] == "assistant" and second[2] == {"role": "tool", "tool_call_id": "c1", "content": tool_result.data["output"]}
    assert seen[0]["tools"] == ["search_gems", "get_gem"]
    assert fake_runs["runs"][result.run.id].status == "finished"


def test_anthropic_results_go_back_in_one_user_message(fake_library, fake_runs, monkeypatch) -> None:
    fake_library["lib"] = make_gem("lib", "L", kind="agent", tools=["get_gem"])
    fake_library["x"] = make_gem("x", "X")
    fn, seen = fake_turns([
        ("", [ToolCall(id="a", name="get_gem", input={"name": "x"}), ToolCall(id="b", name="get_gem", input={"name": "nope"})]),
        ("done", []),
    ])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = run(runner.run_agent("lib", "go"))
    msgs = seen[1]["messages"]
    assert msgs[-1]["role"] == "user" and [c["tool_use_id"] for c in msgs[-1]["content"]] == ["a", "b"]
    assert result.run.status == "finished"


def test_unknown_and_risky_tools_return_errors_to_the_model(fake_library, fake_runs, monkeypatch) -> None:
    from app.agents import tools as registry

    monkeypatch.setattr(registry, "_REGISTRY", dict(registry._REGISTRY))

    @registry.tool("wipe", risky=True)
    async def wipe() -> str:
        """Wipe."""
        return "wiped"

    fake_library["lib"] = make_gem("lib", "L", kind="agent", tools=["wipe", "missing_tool"])
    fn, _ = fake_turns([
        ("", [ToolCall(id="1", name="wipe", input={}), ToolCall(id="2", name="nope", input={})]),
        ("ok", []),
    ])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = run(runner.run_agent("lib", "go"))
    results = [e.data for e in result.events if e.type == "tool_result"]
    assert results[0]["is_error"] and "risky" in results[0]["output"]
    assert results[1]["is_error"] and "Unknown tool" in results[1]["output"]
    started = result.events[0].data
    assert started["tools"] == ["wipe"] and started["unknown_tools"] == ["missing_tool"]

    fn2, _ = fake_turns([("", [ToolCall(id="1", name="wipe", input={})]), ("ok", [])])
    monkeypatch.setattr(runner, "complete_turn", fn2)
    result = run(runner.run_agent("lib", "go", allow_risky=True))
    assert [e.data["output"] for e in result.events if e.type == "tool_result"] == ["wiped"]


def test_step_cap_ends_the_run(fake_library, fake_runs, monkeypatch) -> None:
    fake_library["lib"] = make_gem("lib", "L", kind="agent", tools=["search_gems"])
    monkeypatch.setattr(settings, "AGENT_MAX_STEPS", 3)
    fn, seen = fake_turns([("looping", [ToolCall(id="c", name="search_gems", input={})])])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = run(runner.run_agent("lib", "go"))
    assert result.run.status == "max_steps" and result.run.steps == 3 and len(seen) == 3
    assert result.run.output == "looping"


def test_tool_exceptions_and_bad_arguments_stay_inside_the_run(fake_library, fake_runs, monkeypatch) -> None:
    from app.agents import tools as registry

    monkeypatch.setattr(registry, "_REGISTRY", dict(registry._REGISTRY))

    @registry.tool("boom")
    async def boom(n: int) -> str:
        """Boom."""
        raise RuntimeError("kaboom")

    fake_library["lib"] = make_gem("lib", "L", kind="agent", tools=["boom"])
    fn, _ = fake_turns([
        ("", [ToolCall(id="1", name="boom", input={"n": 1}), ToolCall(id="2", name="boom", input={"wrong": 1})]),
        ("recovered", []),
    ])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = run(runner.run_agent("lib", "go"))
    outs = [e.data["output"] for e in result.events if e.type == "tool_result"]
    assert "kaboom" in outs[0] and "Bad arguments" in outs[1]
    assert result.run.status == "finished" and result.run.output == "recovered"


def test_long_tool_results_are_truncated(fake_library, fake_runs, monkeypatch) -> None:
    from app.agents import tools as registry

    monkeypatch.setattr(registry, "_REGISTRY", dict(registry._REGISTRY))
    monkeypatch.setattr(settings, "AGENT_TOOL_RESULT_MAX_CHARS", 20)

    @registry.tool("big")
    async def big() -> str:
        """Big."""
        return "x" * 100

    fake_library["lib"] = make_gem("lib", "L", kind="agent", tools=["big"])
    fn, _ = fake_turns([("", [ToolCall(id="1", name="big", input={})]), ("ok", [])])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = run(runner.run_agent("lib", "go"))
    out = next(e.data["output"] for e in result.events if e.type == "tool_result")
    assert out.startswith("x" * 20) and "truncated, 80 more" in out


def test_provider_failure_fails_the_run_with_a_record(fake_library, fake_runs, monkeypatch) -> None:
    from app.services.llm_service import ProviderError

    fake_library["lib"] = make_gem("lib", "L", kind="agent", tools=[])

    async def failing(*a, **k):
        raise ProviderError("anthropic down")

    monkeypatch.setattr(runner, "complete_turn", failing)
    result = run(runner.run_agent("lib", "go"))
    assert result.run.status == "failed" and "ProviderError" in result.run.error
    assert [e.type for e in result.events] == ["run_started", "run_failed"]
    assert result.events[-1].data == {"step": 1, "error": "ProviderError"}


def test_unknown_gem_raises_before_a_run_is_created(fake_library, fake_runs) -> None:
    with pytest.raises(ValueError):
        run(runner.run_agent("ghost", "go"))
    assert fake_runs["runs"] == {}
