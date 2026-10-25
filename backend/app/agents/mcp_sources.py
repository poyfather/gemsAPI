"""
Tools from other MCP servers (roadmap item 32).

A JSON file in the same shape Claude Desktop uses lists the servers:

    {"mcpServers": {
        "rea":    {"command": "npx", "args": ["-y", "rea-agents@6.4.0", "mcp"], "risky": false},
        "remote": {"url": "https://example.com/mcp", "headers": {"Authorization": "Bearer ..."}}
    }}

Every tool a server offers becomes a registry tool named "<server>.<tool>";
a gem may list single tools or "<server>.*" for all of them. Tools are
risky unless the server entry says "risky": false or lists the risky ones
by name, because a server you did not write may do anything.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import pathlib
import time
from typing import Any

from app import settings
from app.agents.tools import Tool

logger = logging.getLogger(__name__)

_remote: dict[str, Tool] = {}
_loaded_at: float = 0.0
_lock = asyncio.Lock()


def config_path() -> pathlib.Path:
    return pathlib.Path(settings.MCP_SERVERS_FILE)


def load_config() -> dict[str, dict[str, Any]]:
    """The mcpServers map, or {} when the file is missing or empty."""
    p = config_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text() or "{}")
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse %s: %s", p, exc)
        return {}
    servers = data.get("mcpServers", data) if isinstance(data, dict) else {}
    return {name: cfg for name, cfg in servers.items() if isinstance(cfg, dict) and not cfg.get("disabled")}


def _transport(cfg: dict[str, Any]):
    from fastmcp.client.transports import StdioTransport, StreamableHttpTransport

    if "url" in cfg:
        return StreamableHttpTransport(cfg["url"], headers=cfg.get("headers"))
    env = {**os.environ, **cfg.get("env", {})} if cfg.get("env") else None
    return StdioTransport(cfg["command"], list(cfg.get("args", [])), env=env, cwd=cfg.get("cwd"))


def _connect(cfg: dict[str, Any]):
    """A fastmcp Client for the server; tests replace this."""
    from fastmcp import Client

    return Client(_transport(cfg), timeout=settings.MCP_CALL_TIMEOUT_SECONDS)


def _is_risky(cfg: dict[str, Any], tool_name: str) -> bool:
    risky = cfg.get("risky", True)
    if isinstance(risky, bool):
        return risky
    if isinstance(risky, list):
        return tool_name in risky
    return True


def _result_text(result: Any) -> str:
    """Render a CallToolResult as text for the model: text blocks, else the structured content, else nothing."""
    parts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    if parts:
        return "\n".join(parts)
    structured = getattr(result, "structured_content", None) or getattr(result, "data", None)
    if structured is not None:
        return json.dumps(structured, default=str, ensure_ascii=False)
    return ""


def _make_tool(server: str, cfg: dict[str, Any], remote_name: str, description: str, schema: dict) -> Tool:
    async def handler(**arguments: Any) -> str:
        async with _connect(cfg) as client:
            result = await client.call_tool(remote_name, arguments, raise_on_error=False)
        text = _result_text(result)
        if getattr(result, "is_error", False):
            raise RuntimeError(text or f"{server}.{remote_name} returned an error")
        return text

    schema = dict(schema or {})
    schema.setdefault("type", "object")
    schema.setdefault("properties", {})
    return Tool(f"{server}.{remote_name}", description or remote_name, schema, handler, _is_risky(cfg, remote_name))


async def _list_server(server: str, cfg: dict[str, Any]) -> list[Tool]:
    async with _connect(cfg) as client:
        listed = await client.list_tools()
    tools = []
    for t in listed:
        schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None) or {}
        tools.append(_make_tool(server, cfg, t.name, getattr(t, "description", "") or "", dict(schema)))
    return tools


async def refresh_remote_tools(force: bool = False) -> dict[str, Tool]:
    """
    Connect to each configured server and (re)build the remote registry,
    cached for MCP_TOOLS_TTL_SECONDS. A server that fails to answer is logged
    and skipped; its tools from the previous refresh are kept.
    """
    global _loaded_at
    async with _lock:
        if not force and _remote and time.monotonic() - _loaded_at < settings.MCP_TOOLS_TTL_SECONDS:
            return dict(_remote)
        servers = load_config()
        for server, cfg in servers.items():
            try:
                tools = await _list_server(server, cfg)
            except Exception as exc:
                logger.warning("MCP server %s unavailable: %s", server, exc)
                continue
            for name in [n for n in _remote if n.startswith(f"{server}.")]:
                del _remote[name]
            for t in tools:
                _remote[t.name] = t
        for name in [n for n in _remote if n.split(".", 1)[0] not in servers]:
            del _remote[name]
        _loaded_at = time.monotonic()
        return dict(_remote)


def remote_tools() -> dict[str, Tool]:
    """The remote registry as last refreshed (no connection)."""
    return dict(_remote)


def clear_remote_tools() -> None:
    global _loaded_at
    _remote.clear()
    _loaded_at = 0.0
