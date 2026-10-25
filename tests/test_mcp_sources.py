"""Tools from other MCP servers, with the fastmcp client faked."""
import asyncio
import json

import pytest

import app.agents.builtin  # noqa: F401
from app import settings
from app.agents import mcp_sources
from app.agents.tools import all_tools, call_tool, get_tool, resolve_tools


class _Block:
    def __init__(self, text): self.text = text


class _Result:
    def __init__(self, text=None, structured=None, is_error=False):
        self.content = [_Block(text)] if text is not None else []
        self.structured_content = structured
        self.is_error = is_error


class _ListedTool:
    def __init__(self, name, description, schema):
        self.name, self.description, self.inputSchema = name, description, schema


class FakeClient:
    """Stands in for fastmcp.Client: records calls, serves a fixed tool list."""
    calls: list[tuple[str, str, dict]] = []
    tools_by_server: dict[str, list[_ListedTool]] = {}
    fail_servers: set[str] = set()

    def __init__(self, server):
        self.server = server

    async def __aenter__(self):
        if self.server in self.fail_servers:
            raise ConnectionError("cannot start")
        return self

    async def __aexit__(self, *a):
        return False

    async def list_tools(self):
        return self.tools_by_server.get(self.server, [])

    async def call_tool(self, name, arguments, raise_on_error=True):
        self.calls.append((self.server, name, arguments))
        if name == "explode":
            return _Result(text="boom", is_error=True)
        if name == "structured":
            return _Result(structured={"ok": True, "n": 2})
        return _Result(text=f"{self.server}:{name}:{json.dumps(arguments, sort_keys=True)}")


@pytest.fixture
def servers(tmp_path, monkeypatch):
    """A config file with two stdio servers and one disabled one, and a fake client per server."""
    cfg = {"mcpServers": {
        "rea": {"command": "npx", "args": ["-y", "rea-agents", "mcp"], "risky": False},
        "ops": {"url": "https://ops.example/mcp", "headers": {"Authorization": "x"}, "risky": ["wipe"]},
        "off": {"command": "x", "disabled": True},
    }}
    path = tmp_path / "mcp_servers.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setattr(settings, "MCP_SERVERS_FILE", str(path))
    FakeClient.calls = []
    FakeClient.fail_servers = set()
    FakeClient.tools_by_server = {
        "rea": [_ListedTool("list_strings", "List strings.", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),
                _ListedTool("structured", "Structured result.", {})],
        "ops": [_ListedTool("wipe", "Wipe.", {"type": "object", "properties": {}}), _ListedTool("read", "Read.", {}), _ListedTool("explode", "", {})],
    }
    monkeypatch.setattr(mcp_sources, "_connect", lambda cfg: FakeClient(_server_of(cfg)))
    mcp_sources.clear_remote_tools()
    yield cfg
    mcp_sources.clear_remote_tools()


def _server_of(cfg):
    return "rea" if cfg.get("command") == "npx" else ("ops" if "url" in cfg else "off")


def test_config_parsing_skips_disabled_and_missing_file(tmp_path, monkeypatch, servers) -> None:
    assert sorted(mcp_sources.load_config()) == ["ops", "rea"]
    monkeypatch.setattr(settings, "MCP_SERVERS_FILE", str(tmp_path / "nope.json"))
    assert mcp_sources.load_config() == {}


def test_remote_tools_are_prefixed_typed_and_risky_by_config(servers) -> None:
    tools = asyncio.run(mcp_sources.refresh_remote_tools())
    assert sorted(tools) == ["ops.explode", "ops.read", "ops.wipe", "rea.list_strings", "rea.structured"]
    assert tools["rea.list_strings"].parameters["required"] == ["path"]
    assert tools["rea.list_strings"].risky is False          # server says risky: false
    assert tools["ops.wipe"].risky is True and tools["ops.read"].risky is False   # listed by name
    assert tools["ops.explode"].description == "explode"      # empty description falls back to the name
    assert get_tool("rea.list_strings").source == "rea" and get_tool("get_gem").source == "builtin"
    names = [t.name for t in all_tools()]
    assert names[:4] == ["forget", "get_gem", "get_memories", "ops.explode"]


def test_default_risky_when_the_server_does_not_say(tmp_path, monkeypatch, servers) -> None:
    cfg = {"mcpServers": {"ops": {"url": "https://ops.example/mcp"}}}
    (tmp_path / "mcp_servers.json").write_text(json.dumps(cfg))
    tools = asyncio.run(mcp_sources.refresh_remote_tools(force=True))
    assert all(t.risky for t in tools.values())


def test_wildcards_expand_and_unknown_wildcards_are_reported(servers) -> None:
    asyncio.run(mcp_sources.refresh_remote_tools())
    found, unknown = resolve_tools(["rea.*", "get_gem", "ghost.*", "rea.list_strings"])
    assert [t.name for t in found] == ["rea.list_strings", "rea.structured", "get_gem"]
    assert unknown == ["ghost.*"]


def test_calls_go_to_the_server_and_results_come_back_as_text(servers) -> None:
    asyncio.run(mcp_sources.refresh_remote_tools())
    out = asyncio.run(call_tool(get_tool("rea.list_strings"), {"path": "/bin/x"}))
    assert out == 'rea:list_strings:{"path": "/bin/x"}'
    assert FakeClient.calls == [("rea", "list_strings", {"path": "/bin/x"})]
    assert asyncio.run(call_tool(get_tool("rea.structured"), {})) == '{"ok": true, "n": 2}'
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(call_tool(get_tool("ops.explode"), {}))


def test_an_unreachable_server_is_skipped_and_cached_tools_survive(servers) -> None:
    asyncio.run(mcp_sources.refresh_remote_tools())
    FakeClient.fail_servers = {"ops"}
    tools = asyncio.run(mcp_sources.refresh_remote_tools(force=True))
    assert "ops.read" in tools and "rea.list_strings" in tools   # previous listing kept


def test_the_listing_is_cached_until_forced(servers, monkeypatch) -> None:
    counter = {"n": 0}
    orig = FakeClient.list_tools

    async def counting(self):
        counter["n"] += 1
        return await orig(self)

    monkeypatch.setattr(FakeClient, "list_tools", counting)
    asyncio.run(mcp_sources.refresh_remote_tools())
    asyncio.run(mcp_sources.refresh_remote_tools())
    assert counter["n"] == 2        # one per server, once
    asyncio.run(mcp_sources.refresh_remote_tools(force=True))
    assert counter["n"] == 4


def test_an_agent_gem_can_use_remote_tools_through_the_loop(servers, fake_library, fake_runs, monkeypatch) -> None:
    from app.agents import runner
    from app.services.llm_service import ToolCall
    from conftest import make_gem
    from test_runner import fake_turns

    fake_library["re"] = make_gem("re", "Analyse {target_app}.", kind="agent", tools=["rea.*", "ops.wipe"])
    fn, seen = fake_turns([
        ("", [ToolCall(id="1", name="rea.list_strings", input={"path": "/app"}), ToolCall(id="2", name="ops.wipe", input={})]),
        ("done", []),
    ])
    monkeypatch.setattr(runner, "complete_turn", fn)
    result = asyncio.run(runner.run_agent("re", "go", {"target_app": "Notion"}))
    assert seen[0]["tools"] == ["rea.list_strings", "rea.structured", "ops.wipe"]
    assert result.run.status == "waiting_approval"          # ops.wipe is risky: the run pauses at it
    outputs = [e.data["output"] for e in result.events if e.type == "tool_result"]
    assert outputs == ['rea:list_strings:{"path": "/app"}']
    assert result.events[0].data["tools"] == ["rea.list_strings", "rea.structured", "ops.wipe"]
