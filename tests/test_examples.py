"""Worked examples as data (roadmap 31): cleaning, rendering at the marker or the end, literal text, embedding, history, Compare, routes and MCP."""
import asyncio

import pytest

from app.models import MAX_EXAMPLES, CompareRequest, CompareVariant, Example, GemCreate, GemUpdate
from app.services import compare_service, gem_service, llm_service, version_service
from conftest import TEST_API_KEY

KEY = {"X-API-Key": TEST_API_KEY}
EXAMPLES = [
    {"input": "Summarise: the meeting moved to Friday.", "output": "Meeting now Friday.", "note": "short one"},
    {"input": "Fill {name} in this JSON: {\"a\": 1}", "output": "{\"a\": 1, \"name\": \"{name}\"}"},
]


def run(coro):
    return asyncio.run(coro)


def test_examples_are_cleaned_on_save(sqlite) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="ex", system_prompt="Be brief.", examples=[*EXAMPLES, {"input": " ", "output": ""}])))
    assert len(gem.examples) == 2 and gem.examples[0].note == "short one", "an empty example is dropped"
    with pytest.raises(ValueError, match="both an input and the answer"):
        gem_service.clean_examples([{"input": "only a question", "output": " "}])
    with pytest.raises(ValueError, match=f"at most {MAX_EXAMPLES}"):
        gem_service.clean_examples([{"input": "q", "output": "a"}] * (MAX_EXAMPLES + 1))


def test_examples_render_at_the_end_without_a_marker_and_stay_literal(sqlite) -> None:
    run(gem_service.create_gem(GemCreate(name="ex", system_prompt="Answer for {name}.", examples=EXAMPLES)))
    r = run(gem_service.resolve_gem_detailed("ex", {"name": "Ada"}))
    assert r.resolved_prompt.startswith("Answer for Ada.\n\n<examples>\n<example>\n<input>\nSummarise: the meeting moved to Friday.\n</input>")
    assert "Fill {name} in this JSON: {\"a\": 1}" in r.resolved_prompt, "blanks inside an example are not filled"
    assert r.resolved_prompt.endswith("</example>\n</examples>") and r.examples_used == 2
    assert r.variables_expected == ["name"], "the {name} inside an example is not a blank of the gem"
    assert "short one" not in r.resolved_prompt, "notes are for people"


def test_the_marker_places_them_and_is_not_a_blank(sqlite) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="mk", system_prompt="Rules first.\n{{examples}}\nNow answer {q}.", examples=EXAMPLES[:1])))
    assert gem.variables == ["q"], "{{examples}} is not a blank"
    r = run(gem_service.resolve_gem_detailed("mk", {"q": "this"}))
    assert r.resolved_prompt.startswith("Rules first.\n<examples>") and r.resolved_prompt.endswith("</examples>\nNow answer this.")
    run(gem_service.create_gem(GemCreate(name="mk2", system_prompt="A\n{{examples}}\nB")))
    assert run(gem_service.resolve_gem_detailed("mk2")).resolved_prompt == "A\n\nB", "a marker with no examples disappears"
    plain = run(gem_service.create_gem(GemCreate(name="none", system_prompt="Just this.")))
    assert run(gem_service.resolve_gem_detailed(plain.name)).resolved_prompt == "Just this.", "no examples, no change"


def test_embedded_gems_bring_their_own_examples(sqlite) -> None:
    run(gem_service.create_gem(GemCreate(name="inner", system_prompt="Inner rules. {{examples}}", examples=[{"input": "in", "output": "out"}])))
    run(gem_service.create_gem(GemCreate(name="outer", system_prompt="{{gem:inner}}\nOuter.", examples=[{"input": "x", "output": "y"}])))
    r = run(gem_service.resolve_gem_detailed("outer"))
    assert r.examples_used == 2
    assert r.resolved_prompt.index("<input>\nin\n</input>") < r.resolved_prompt.index("Outer.") < r.resolved_prompt.index("<input>\nx\n</input>")


def test_examples_are_versioned_and_compare_uses_a_past_versions_own(sqlite, monkeypatch) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="v", system_prompt="P.", examples=[{"input": "a", "output": "first"}])))
    gem = run(gem_service.update_gem(gem.id, GemUpdate(examples=[Example(input="a", output="second")], note="better example")))
    hist = run(version_service.history(gem))
    assert hist[0].changed == ["examples"] and hist[0].note == "better example"
    restored = run(version_service.revert(gem, 1))
    assert restored.examples[0].output == "first"

    async def complete(system_prompt, messages, model, provider, max_tokens=None):
        return system_prompt

    monkeypatch.setattr(llm_service, "complete", complete)
    res = run(compare_service.compare(restored, CompareRequest(message="q", variants=[CompareVariant(version=2), CompareVariant()])))
    assert "second" in res.columns[0].output and "first" in res.columns[1].output


def test_routes(client, sqlite) -> None:
    r = client.post("/gems/", headers=KEY, json={"name": "web", "system_prompt": "Be kind.", "examples": EXAMPLES})
    assert r.status_code == 201 and len(r.json()["examples"]) == 2
    assert client.post("/gems/", headers=KEY, json={"name": "bad", "system_prompt": "x", "examples": [{"input": "q", "output": ""}]}).status_code == 400
    res = client.post("/gems/resolve", headers=KEY, json={"gem_name": "web"}).json()
    assert res["examples_used"] == 2 and "<examples>" in res["resolved_prompt"]
    case = client.post("/gems/web/examples/0/test", headers=KEY)
    assert case.status_code == 201 and case.json()["check"] == "judge" and case.json()["input"] == EXAMPLES[0]["input"]
    assert "Meeting now Friday." in case.json()["expected"] and case.json()["name"] == "example: short one"
    assert client.post("/gems/web/examples/5/test", headers=KEY).status_code == 404
    assert client.put("/gems/web", headers=KEY, json={"examples": []}).json()["examples"] == []


def test_mcp(sqlite) -> None:
    import mcp_server

    run(mcp_server.create_gem(name="m", description="", system_prompt="Reply."))
    assert run(mcp_server.add_gem_example("m", "hello", "hi there", note="greeting")) == {"name": "m", "examples": 1}
    got = run(mcp_server.get_gem("m"))
    assert got["examples"] == [{"input": "hello", "output": "hi there", "note": "greeting"}]
    assert run(mcp_server.resolve_gem_prompt("m"))["examples_used"] == 1
    assert "error" in run(mcp_server.add_gem_example("m", "q", " "))
    assert "error" in run(mcp_server.add_gem_example("nope", "q", "a"))
