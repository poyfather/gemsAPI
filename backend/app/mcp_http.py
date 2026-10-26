"""
Lapidary's MCP server over HTTP (roadmap item 41).

The same FastMCP server that speaks stdio in mcp_server.py is mounted on the
API as streamable HTTP, stateless, behind the API keys, so clients that take a
URL (Claude Desktop and Claude Code connectors, Cursor, VS Code, ChatGPT
through a public HTTPS address) reach the gems, agents, memory and pipelines
without a local process of their own.
"""
from __future__ import annotations
import json

from app import settings
from app.auth import check_key


class KeyGuard:
    """ASGI wrapper: X-API-Key or a bearer token must match an accepted key, or the request gets 401."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        presented = headers.get("x-api-key") or ""
        auth = headers.get("authorization", "")
        if not presented and auth.lower().startswith("bearer "):
            presented = auth[7:].strip()
        client = check_key(presented)
        if client is None:
            body = json.dumps({"detail": "Invalid or missing API key. Pass your key in the X-API-Key header or as a bearer token."}).encode()
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"ApiKey"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return
        scope.setdefault("state", {})["mcp_client"] = client
        await self.app(scope, receive, send)


def build_mcp_app():
    """The mounted ASGI app and its lifespan (FastMCP needs the lifespan to run)."""
    from mcp_server import mcp   # the stdio server module; importing it registers every tool and resource

    hosts = settings.MCP_ALLOWED_HOSTS or None
    inner = mcp.http_app(path="/", transport="http", stateless_http=True, allowed_hosts=hosts)
    return KeyGuard(inner), inner.lifespan
