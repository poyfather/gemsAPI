"""The tool registry: schemas from signatures, lookup, execution."""
import asyncio

import pytest

import app.agents.builtin  # noqa: F401
from app.agents import tools as registry
from app.agents.tools import Tool, all_tools, call_tool, get_tool, resolve_tools, tool
from conftest import make_gem


def test_builtin_tools_are_registered_with_schemas() -> None:
    names = [t.name for t in all_tools()]
    assert names == ["forget", "get_gem", "get_memories", "remember", "resolve_gem", "run_powershell", "search_gems", "search_memory"]
    search = get_tool("search_gems")
    assert search.parameters["type"] == "object"
    assert set(search.parameters["properties"]) == {"query", "tag"}
    assert search.parameters["properties"]["query"]["type"] == "string"
    assert "required" not in search.parameters  # both have defaults
    assert get_tool("get_gem").parameters["required"] == ["name"]
    assert not search.risky


def test_provider_shapes() -> None:
    t = get_tool("get_gem")
    a = t.to_anthropic()
    o = t.to_openai()
    assert a == {"name": "get_gem", "description": t.description, "input_schema": t.parameters}
    assert o["type"] == "function" and o["function"]["parameters"] == t.parameters


def test_resolve_tools_splits_known_and_unknown() -> None:
    found, unknown = resolve_tools(["get_gem", "launch_rockets"])
    assert [t.name for t in found] == ["get_gem"] and unknown == ["launch_rockets"]


def test_decorator_registers_risky_async_tools_and_rejects_sync(monkeypatch) -> None:
    monkeypatch.setattr(registry, "_REGISTRY", dict(registry._REGISTRY))

    @tool("delete_everything", risky=True)
    async def delete_everything(confirm: bool = False) -> str:
        """Deletes everything."""
        return "gone" if confirm else "no"

    t = get_tool("delete_everything")
    assert isinstance(t, Tool) and t.risky and t.description == "Deletes everything."
    assert asyncio.run(call_tool(t, {"confirm": True})) == "gone"

    with pytest.raises(TypeError):
        @tool()
        def not_async() -> str:
            return "x"


def test_builtin_tools_read_the_library(fake_library) -> None:
    fake_library["base"] = make_gem("base", "Be direct.", tags=["base"])
    fake_library["reviewer"] = make_gem("reviewer", "{{gem:base}} Review {language}.", tags=["code"])
    found = asyncio.run(call_tool(get_tool("search_gems"), {"tag": "code"}))
    assert '"reviewer"' in found and '"base"' not in found
    got = asyncio.run(call_tool(get_tool("get_gem"), {"name": "reviewer"}))
    assert '"gem_refs": ["base"]' in got
    resolved = asyncio.run(call_tool(get_tool("resolve_gem"), {"name": "reviewer", "variables": {"language": "Go"}}))
    assert "Be direct. Review Go." in resolved
    missing = asyncio.run(call_tool(get_tool("get_gem"), {"name": "nope"}))
    assert "not found" in missing
