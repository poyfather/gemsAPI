"""Typed blanks (roadmap 29): specs on save, defaults and checks on resolve, the JSON schema, routes, MCP, history and compare."""
import asyncio

import pytest

from app.models import CompareRequest, CompareVariant, GemCreate, GemUpdate, VariableSpec
from app.services import compare_service, gem_service, llm_service, version_service
from conftest import TEST_API_KEY

KEY = {"X-API-Key": TEST_API_KEY}
PROMPT = "Write a {tone} note for {audience} in {words} words. Formal: {formal}. Topic: {topic}"
SPECS = {
    "tone": {"description": "How it should sound", "type": "choice", "options": ["warm", "neutral", "firm"], "default": "neutral"},
    "audience": {"description": "Who reads it"},
    "words": {"type": "number", "default": "100"},
    "formal": {"type": "boolean", "required": False},
    "topic": {"type": "long_text", "required": False},
    "gone": {"description": "not in the prompt"},
}


def run(coro):
    return asyncio.run(coro)


def make(sqlite_name="note"):
    return run(gem_service.create_gem(GemCreate(name=sqlite_name, system_prompt=PROMPT, variable_specs=SPECS)))


def test_specs_are_cleaned_on_save(sqlite) -> None:
    gem = make()
    assert sorted(gem.variable_specs) == ["audience", "formal", "tone", "topic", "words"], "a spec for a blank the prompt does not have is dropped"
    assert gem.variable_specs["tone"].options == ["warm", "neutral", "firm"] and gem.variable_specs["audience"].required is True
    with pytest.raises(ValueError, match="choice but has no options"):
        gem_service.clean_specs({"tone": {"type": "choice"}}, PROMPT)
    with pytest.raises(ValueError, match="default for \\{words\\} does not fit"):
        gem_service.clean_specs({"words": {"type": "number", "default": "many"}}, PROMPT)
    with pytest.raises(ValueError, match="use one of"):
        gem_service.clean_specs({"words": {"type": "date"}}, PROMPT)
    updated = run(gem_service.update_gem(gem.id, GemUpdate(system_prompt="A {tone} line about {topic}.")))
    assert sorted(updated.variable_specs) == ["tone", "topic"], "editing the prompt drops specs for blanks it removed"


def test_defaults_fill_in_and_wrong_values_are_refused(sqlite) -> None:
    make()
    r = run(gem_service.resolve_gem_detailed("note", {"audience": "the team"}))
    assert "Write a neutral note for the team in 100 words." in r.resolved_prompt
    assert sorted(r.variables_defaulted) == ["tone", "words"] and r.variables_used == ["audience"] and r.variable_errors == []
    assert sorted(r.variables_missing) == ["formal", "topic"], "optional blanks with no value stay as they are"
    with pytest.raises(gem_service.VariableError) as err:
        run(gem_service.resolve_gem_detailed("note", {"tone": "angry", "words": "lots", "formal": "maybe"}))
    msg = str(err.value)
    assert "{audience} is required: Who reads it" in msg and "{tone} should be one of warm, neutral, firm" in msg
    assert "{words} should be a number" in msg and "{formal} should be yes or no" in msg
    lenient = run(gem_service.resolve_gem_detailed("note", {"tone": "angry"}, strict=False))
    assert len(lenient.variable_errors) == 2 and "Write a angry note" in lenient.resolved_prompt, "a preview shows the value as typed, with the errors beside it"
    yes = run(gem_service.resolve_gem_detailed("note", {"audience": "x", "formal": "TRUE"}))
    assert "Formal: yes." in yes.resolved_prompt


def test_gems_without_specs_behave_as_before(sqlite) -> None:
    run(gem_service.create_gem(GemCreate(name="plain", system_prompt="Hi {who}.")))
    r = run(gem_service.resolve_gem_detailed("plain", {}))
    assert r.variables_missing == ["who"] and r.variable_errors == [] and r.resolved_prompt == "Hi {who}."


def test_specs_of_embedded_gems_apply_and_the_outer_gem_wins(sqlite) -> None:
    run(gem_service.create_gem(GemCreate(name="inner", system_prompt="Use {lang} and {style}.", variable_specs={"lang": {"default": "English"}, "style": {"default": "plain"}})))
    run(gem_service.create_gem(GemCreate(name="outer", system_prompt="{{gem:inner}} Style {style}.", variable_specs={"style": {"default": "bold"}})))
    r = run(gem_service.resolve_gem_detailed("outer", {}))
    assert r.resolved_prompt == "Use English and bold. Style bold." and sorted(r.variables_defaulted) == ["lang", "style"]


def test_the_json_schema_for_mcp_clients(sqlite) -> None:
    schema = gem_service.variables_schema(make())
    assert schema["required"] == ["audience"]
    assert schema["properties"]["tone"] == {"type": "string", "description": "How it should sound", "enum": ["warm", "neutral", "firm"], "default": "neutral"}
    assert schema["properties"]["words"] == {"type": "number", "default": "100"} and schema["properties"]["formal"] == {"type": "boolean"}
    bare = run(gem_service.create_gem(GemCreate(name="bare", system_prompt="Hi {who}.")))
    assert gem_service.variables_schema(bare) == {"type": "object", "properties": {"who": {"type": "string"}}, "required": ["who"]}


def test_routes(client, sqlite, monkeypatch) -> None:
    created = client.post("/gems/", headers=KEY, json={"name": "note", "system_prompt": PROMPT, "variable_specs": SPECS})
    assert created.status_code == 201 and created.json()["variable_specs"]["words"]["type"] == "number"
    assert client.post("/gems/", headers=KEY, json={"name": "bad", "system_prompt": "{x}", "variable_specs": {"x": {"type": "choice"}}}).status_code == 400
    assert client.put("/gems/note", headers=KEY, json={"variable_specs": {"tone": {"type": "choice", "options": []}}}).status_code == 400
    res = client.post("/gems/resolve", headers=KEY, json={"gem_name": "note", "variables": {"tone": "angry"}}).json()
    assert res["variables_defaulted"] == ["words"] and any("{tone}" in e for e in res["variable_errors"])

    async def complete(system_prompt, messages, model, provider, max_tokens=None):
        return "ok"

    from app.routes import chat as chat_route
    monkeypatch.setattr(chat_route, "complete", complete)
    bad = client.post("/chat/", headers=KEY, json={"gem_name": "note", "messages": [{"role": "user", "content": "go"}], "variables": {"tone": "angry"}})
    assert bad.status_code == 400 and "Fill in the blanks" in bad.json()["detail"]
    good = client.post("/chat/", headers=KEY, json={"gem_name": "note", "messages": [{"role": "user", "content": "go"}], "variables": {"audience": "us"}})
    assert good.status_code == 200
    run_bad = client.post("/agents/note/runs", headers=KEY, json={"message": "go", "variables": {}})
    assert run_bad.status_code == 400 and "{audience} is required" in run_bad.json()["detail"]


def test_mcp_exposes_the_schema_and_takes_specs(sqlite) -> None:
    import mcp_server

    run(mcp_server.create_gem(name="m", description="", system_prompt="Hi {who}, in {lang}.", variable_specs={"lang": {"type": "choice", "options": ["en", "fr"], "default": "en"}}))
    got = run(mcp_server.get_gem("m"))
    assert got["variables_schema"]["required"] == ["who"] and got["variables_schema"]["properties"]["lang"]["enum"] == ["en", "fr"]
    listed = next(g for g in run(mcp_server.list_gems()) if g["name"] == "m")
    assert listed["variables_schema"]["properties"]["lang"]["default"] == "en"
    out = run(mcp_server.update_gem("m", variable_specs={"who": {"description": "a name", "default": "friend"}}, note="default name"))
    assert out["variables_schema"]["required"] == []
    resolved = run(mcp_server.resolve_gem_prompt("m"))
    assert resolved["resolved_prompt"] == "Hi friend, in {lang}." or resolved["resolved_prompt"] == "Hi friend, in en."
    assert "error" in run(mcp_server.update_gem("m", variable_specs={"lang": {"type": "choice"}}))


def test_history_keeps_specs_and_old_versions_compare_with_their_own(sqlite, monkeypatch) -> None:
    gem = run(gem_service.create_gem(GemCreate(name="h", system_prompt="Say {x}.", variable_specs={"x": {"default": "hello"}})))
    gem = run(gem_service.update_gem(gem.id, GemUpdate(variable_specs={"x": {"default": "goodbye"}}, note="new default")))
    hist = run(version_service.history(gem))
    assert [h.version for h in hist] == [2, 1] and hist[0].changed == ["variable_specs"]
    run(gem_service.update_gem(gem.id, GemUpdate(description="same specs")))
    assert len(run(version_service.versions(gem.id))) == 3

    async def complete(system_prompt, messages, model, provider, max_tokens=None):
        return system_prompt

    monkeypatch.setattr(llm_service, "complete", complete)
    res = run(compare_service.compare(gem, CompareRequest(message="q", variants=[CompareVariant(version=1), CompareVariant()])))
    assert [c.output for c in res.columns] == ["Say hello.", "Say goodbye."]
    assert VariableSpec().type == "text"
