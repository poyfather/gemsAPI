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

    def info(self) -> dict:
        return {"name": self.name, "description": self.description, "parameters": self.parameters, "risky": self.risky}


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


def all_tools() -> list[Tool]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def get_tool(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def resolve_tools(names: list[str]) -> tuple[list[Tool], list[str]]:
    """Split a gem's tool names into registered tools and unknown names."""
    found, unknown = [], []
    for n in names:
        t = _REGISTRY.get(n)
        (found if t else unknown).append(t or n)
    return found, unknown


async def call_tool(t: Tool, arguments: dict) -> str:
    """Run a tool and render its result as text for the model."""
    result = await t.handler(**arguments)
    if isinstance(result, str):
        return result
    return json.dumps(result, default=str, ensure_ascii=False)
