"""
Tool registry for agent gems.

A tool is a Python coroutine registered with @tool. Its JSON schema is
derived from the signature (pydantic), its description from the docstring.
Tools marked risky are refused unless the run was started with
allow_risky=True. Tool names are the names an agent gem lists in `tools`.
"""
from __future__ import annotations
import inspect
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import create_model

Handler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict           # JSON schema for the arguments object
    handler: Handler
    risky: bool = False

    def to_anthropic(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.parameters}

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }

    @property
    def source(self) -> str:
        """'builtin' for Python tools, else the MCP server name (the part before the dot)."""
        return self.name.split(".", 1)[0] if "." in self.name else "builtin"

    def info(self) -> dict:
        return {"name": self.name, "description": self.description, "parameters": self.parameters,
                "risky": self.risky, "source": self.source}


_REGISTRY: dict[str, Tool] = {}


def _schema_from_signature(fn: Callable) -> dict:
    fields: dict[str, Any] = {}
    for name, param in inspect.signature(fn).parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else str
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[name] = (annotation, default)
    model = create_model(f"{fn.__name__}_args", **fields)
    schema = model.model_json_schema()
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
    schema.setdefault("properties", {})
    schema["type"] = "object"
    return schema


def tool(name: str | None = None, *, risky: bool = False) -> Callable[[Handler], Handler]:
    """Register an async function as a tool. The docstring is the description the model sees."""
    def decorate(fn: Handler) -> Handler:
        if not inspect.iscoroutinefunction(fn):
            raise TypeError(f"tool {fn.__name__} must be an async function")
        tool_name = name or fn.__name__
        description = inspect.getdoc(fn) or tool_name
        _REGISTRY[tool_name] = Tool(tool_name, description, _schema_from_signature(fn), fn, risky)
        return fn
    return decorate


def _combined() -> dict[str, Tool]:
    """Built-in tools plus the remote registry as last refreshed (see mcp_sources.refresh_remote_tools)."""
    from app.agents.mcp_sources import remote_tools  # local import: mcp_sources imports Tool from here

    return {**_REGISTRY, **remote_tools()}


def all_tools() -> list[Tool]:
    combined = _combined()
    return [combined[k] for k in sorted(combined)]


def get_tool(name: str) -> Tool | None:
    return _combined().get(name)


def resolve_tools(names: list[str]) -> tuple[list[Tool], list[str]]:
    """
    Split a gem's tool names into tools and unknown names. "<server>.*" expands
    to every tool of that server; a wildcard that matches nothing is unknown.
    """
    combined = _combined()
    found: list[Tool] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for n in names:
        if n.endswith(".*"):
            prefix = n[:-1]
            matches = [combined[k] for k in sorted(combined) if k.startswith(prefix)]
            if not matches:
                unknown.append(n)
            for t in matches:
                if t.name not in seen:
                    seen.add(t.name)
                    found.append(t)
            continue
        t = combined.get(n)
        if t is None:
            unknown.append(n)
        elif t.name not in seen:
            seen.add(t.name)
            found.append(t)
    return found, unknown


async def call_tool(t: Tool, arguments: dict) -> str:
    """Run a tool and render its result as text for the model."""
    result = await t.handler(**arguments)
    if isinstance(result, str):
        return result
    return json.dumps(result, default=str, ensure_ascii=False)
