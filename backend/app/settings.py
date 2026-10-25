"""
One place for runtime settings read from the environment.

Everything here has a sensible default so the app starts with only the
required secrets set. See README.md ("Configuration") for the full list.
"""
from __future__ import annotations
import os


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


# Default provider and model for new gems (REST, UI and MCP all read these).
DEFAULT_PROVIDER: str = _env("GEMS_DEFAULT_PROVIDER", "anthropic")
DEFAULT_MODEL: str = _env("GEMS_DEFAULT_MODEL", "claude-opus-5-5")

# Models offered in the UI and by the list_available_models tool when a
# provider's live model list cannot be fetched (no key, network error).
# GEMS_MODELS_ANTHROPIC and GEMS_MODELS_OPENAI, comma separated, override
# these and also skip the live lookup for that provider.
FALLBACK_MODELS: dict[str, list[str]] = {
    "anthropic": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"],
    "openai": [],
}
PINNED_MODELS: dict[str, list[str]] = {
    "anthropic": _env_list("GEMS_MODELS_ANTHROPIC"),
    "openai": _env_list("GEMS_MODELS_OPENAI"),
}

# How long a fetched model list is reused before asking the provider again.
MODEL_LIST_TTL_SECONDS: float = float(_env("GEMS_MODEL_LIST_TTL_SECONDS", "600"))

# Provider HTTP behaviour. Both SDKs retry connection errors, 408, 409, 429
# and 5xx with backoff; the timeout is per attempt.
LLM_TIMEOUT_SECONDS: float = float(_env("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_RETRIES: int = int(_env("LLM_MAX_RETRIES", "2"))
LLM_MAX_TOKENS: int = int(_env("LLM_MAX_TOKENS", "4096"))

# Agent runs (ADR-007): the loop stops after this many model turns, and a
# tool result longer than this many characters is truncated before it is
# sent back to the model.
AGENT_MAX_STEPS: int = int(_env("AGENT_MAX_STEPS", "8"))
AGENT_TOOL_RESULT_MAX_CHARS: int = int(_env("AGENT_TOOL_RESULT_MAX_CHARS", "8000"))

# Tools from other MCP servers (roadmap item 32): a JSON file in Claude
# Desktop's mcpServers shape. Default: configs/mcp_servers.json at the repo root.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MCP_SERVERS_FILE: str = _env("GEMS_MCP_SERVERS_FILE", os.path.join(_REPO_ROOT, "configs", "mcp_servers.json"))
MCP_TOOLS_TTL_SECONDS: float = float(_env("GEMS_MCP_TOOLS_TTL_SECONDS", "300"))
MCP_CALL_TIMEOUT_SECONDS: float = float(_env("GEMS_MCP_CALL_TIMEOUT_SECONDS", "120"))
