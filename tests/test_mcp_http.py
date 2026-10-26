"""The MCP server over HTTP (roadmap item 41) and per-client keys (item 10)."""
import json

import pytest

from app.auth import accepted_keys, check_key
from conftest import TEST_API_KEY

KEY = {"X-API-Key": TEST_API_KEY}
MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}


def _result(response):
    """A streamable HTTP answer is JSON or an SSE body with one data line; return the JSON-RPC result either way."""
    text = response.text
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        text = next(line[5:].strip() for line in text.splitlines() if line.startswith("data:"))
    return json.loads(text)


def test_mcp_over_http_needs_the_key(client) -> None:
    r = client.post("/mcp/", json=INIT, headers=MCP_HEADERS)
    assert r.status_code == 401 and "API key" in r.json()["detail"] and r.headers["www-authenticate"] == "ApiKey"
    assert client.post("/mcp/", json=INIT, headers={**MCP_HEADERS, "Authorization": "Bearer nope"}).status_code == 401


def test_mcp_over_http_initializes_and_lists_the_tools(client) -> None:
    r = client.post("/mcp/", json=INIT, headers={**MCP_HEADERS, **KEY})
    assert r.status_code == 200, r.text
    init = _result(r)["result"]
    assert init["serverInfo"]["name"] == "lapidary" and "protocolVersion" in init
    r = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, headers={**MCP_HEADERS, "Authorization": f"Bearer {TEST_API_KEY}"})
    assert r.status_code == 200, r.text
    names = {t["name"] for t in _result(r)["result"]["tools"]}
    assert {"list_gems", "run_agent", "search_memory", "run_pipeline", "approve_run"} <= names


def test_mcp_tool_call_over_http(client, fake_library, monkeypatch) -> None:
    import mcp_server
    from app.services import gem_service
    from conftest import make_gem
    fake_library["hello"] = make_gem("hello", "Say hello to {name}.", tags=["greeting"])
    monkeypatch.setattr(mcp_server, "get_all_gems", gem_service.get_all_gems)   # the MCP module imported the function by name
    call = {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_gems", "arguments": {"tag": "greeting"}}}
    r = client.post("/mcp/", json=call, headers={**MCP_HEADERS, **KEY})
    assert r.status_code == 200, r.text
    result = _result(r)["result"]
    assert result.get("isError") is not True
    found = result.get("structuredContent", {}).get("result") or json.loads(result["content"][0]["text"])
    assert [g["name"] for g in found] == ["hello"]


def test_per_client_keys(client, monkeypatch) -> None:
    monkeypatch.setenv("GEMS_CLIENT_KEYS", "chatgpt:ck-1, cursor:ck-2,broken,:nokey,noname:")
    assert accepted_keys() == {TEST_API_KEY: "default", "ck-1": "chatgpt", "ck-2": "cursor"}
    assert check_key("ck-2") == "cursor" and check_key(TEST_API_KEY) == "default" and check_key("ck-9") is None and check_key("") is None
    assert client.get("/gems/", headers={"X-API-Key": "ck-1"}).status_code == 200
    assert client.get("/gems/", headers={"Authorization": "Bearer ck-2"}).status_code == 200
    assert client.get("/gems/", headers={"X-API-Key": "ck-9"}).status_code == 401
    assert client.post("/mcp/", json=INIT, headers={**MCP_HEADERS, "X-API-Key": "ck-1"}).status_code == 200
    monkeypatch.delenv("GEMS_CLIENT_KEYS")
    assert client.get("/gems/", headers={"X-API-Key": "ck-1"}).status_code == 401


@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
def test_both_spellings_of_the_path_reach_the_server(client, path) -> None:
    r = client.post(path, json=INIT, headers={**MCP_HEADERS, **KEY}, follow_redirects=True)
    assert r.status_code == 200, r.text
