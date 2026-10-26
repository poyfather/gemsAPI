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


# Storage (roadmap item 38): sqlite unless a Supabase project is configured.
STORAGE: str = _env("GEMS_STORAGE", "supabase" if os.environ.get("SUPABASE_URL") else "sqlite")
SQLITE_PATH: str = _env("GEMS_SQLITE_PATH", os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "data", "lapidary.db"))
SEED_SQL_FILE: str = _env("GEMS_SEED_SQL_FILE", os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "supabase", "schema.sql"))

# Default provider and model for new gems (REST, UI and MCP all read these).
# "auto" means the model policy decides at call time (see router.py).
DEFAULT_PROVIDER: str = _env("GEMS_DEFAULT_PROVIDER", "auto")
DEFAULT_MODEL: str = _env("GEMS_DEFAULT_MODEL", "auto")
# The cloud defaults the policy falls back to for a gem that does not pin a model.
CLOUD_DEFAULT_PROVIDER: str = _env("GEMS_CLOUD_DEFAULT_PROVIDER", "anthropic")
CLOUD_DEFAULT_MODEL: str = _env("GEMS_CLOUD_DEFAULT_MODEL", "claude-opus-5-5")
OPENAI_DEFAULT_MODEL: str = _env("GEMS_OPENAI_DEFAULT_MODEL", "")   # empty: first model the API lists

# Local models (ADR-011): any OpenAI-compatible server. Ollama's default, LM Studio uses 1234, vLLM 8000.
LOCAL_OPENAI_BASE_URL: str = _env("LOCAL_OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
LOCAL_OPENAI_API_KEY: str = _env("LOCAL_OPENAI_API_KEY", "ollama")
LOCAL_DEFAULT_MODEL: str = _env("GEMS_LOCAL_DEFAULT_MODEL", "")      # empty: first model the server lists

# The model policy, answered in the UI by "Which AI should we use?":
#   local  = the free one on this PC      online = the online ones
#   mix    = a mix (hard thinking online, volume local)
#   auto   = decide for me               manual = I'll choose each time (gems name their models)
MODEL_POLICY: str = _env("GEMS_MODEL_POLICY", "auto")

# Models offered in the UI and by the list_available_models tool when a
# provider's live model list cannot be fetched (no key, network error).
# GEMS_MODELS_ANTHROPIC and GEMS_MODELS_OPENAI, comma separated, override
# these and also skip the live lookup for that provider.
FALLBACK_MODELS: dict[str, list[str]] = {
    "anthropic": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"],
    "openai": [],
    "local": [],
}
PINNED_MODELS: dict[str, list[str]] = {
    "anthropic": _env_list("GEMS_MODELS_ANTHROPIC"),
    "openai": _env_list("GEMS_MODELS_OPENAI"),
    "local": _env_list("GEMS_MODELS_LOCAL"),
}

# How long a fetched model list is reused before asking the provider again.
MODEL_LIST_TTL_SECONDS: float = float(_env("GEMS_MODEL_LIST_TTL_SECONDS", "600"))

# Provider HTTP behaviour. Both SDKs retry connection errors, 408, 409, 429
# and 5xx with backoff; the timeout is per attempt.
LLM_TIMEOUT_SECONDS: float = float(_env("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_RETRIES: int = int(_env("LLM_MAX_RETRIES", "2"))
LLM_MAX_TOKENS: int = int(_env("LLM_MAX_TOKENS", "4096"))

# The MCP server over HTTP (roadmap item 41): mounted on the API at this path,
# behind the same keys. Hosts other than localhost (a tunnel's domain, so
# ChatGPT can reach it) must be listed, comma separated, or "*".
MCP_HTTP_PATH: str = _env("GEMS_MCP_HTTP_PATH", "/mcp")
MCP_ALLOWED_HOSTS: list[str] = _env_list("GEMS_MCP_ALLOWED_HOSTS")

# Evals per gem (roadmap 28): the most model calls one run may make, and the
# longest answer each case may produce. Every run shows its estimate first.
EVAL_MAX_CALLS: int = int(_env("GEMS_EVAL_MAX_CALLS", "50"))
EVAL_MAX_TOKENS: int = int(_env("GEMS_EVAL_MAX_TOKENS", "1024"))

# Lapidary Memory (ADR-010). Capture stores an observation when a run finishes;
# summarize asks the memory_summarizer gem to write it (the plain digest is the
# fallback and the only option without a model). Recall is what a gem with
# memory on gets before its prompt.
MEMORY_CAPTURE: bool = _env("GEMS_MEMORY_CAPTURE", "on").lower() not in ("off", "0", "false", "no")
MEMORY_SUMMARIZE: bool = _env("GEMS_MEMORY_SUMMARIZE", "on").lower() not in ("off", "0", "false", "no")
MEMORY_MAX_CHARS: int = int(_env("GEMS_MEMORY_MAX_CHARS", "4000"))
MEMORY_RECALL_LIMIT: int = int(_env("GEMS_MEMORY_RECALL_LIMIT", "6"))
MEMORY_RECALL_MAX_CHARS: int = int(_env("GEMS_MEMORY_RECALL_MAX_CHARS", "2500"))

# Agent runs (ADR-007): the loop stops after this many model turns, and a
# tool result longer than this many characters is truncated before it is
# sent back to the model.
AGENT_MAX_STEPS: int = int(_env("AGENT_MAX_STEPS", "8"))
AGENT_TOOL_RESULT_MAX_CHARS: int = int(_env("AGENT_TOOL_RESULT_MAX_CHARS", "8000"))

# The run_powershell tool (risky): per-call timeout and output cap.
POWERSHELL_TIMEOUT_SECONDS: float = float(_env("POWERSHELL_TIMEOUT_SECONDS", "120"))
POWERSHELL_MAX_OUTPUT_CHARS: int = int(_env("POWERSHELL_MAX_OUTPUT_CHARS", "20000"))

# Tools from other MCP servers (roadmap item 32): a JSON file in Claude
# Desktop's mcpServers shape. Default: configs/mcp_servers.json at the repo root.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MCP_SERVERS_FILE: str = _env("GEMS_MCP_SERVERS_FILE", os.path.join(_REPO_ROOT, "configs", "mcp_servers.json"))
MCP_TOOLS_TTL_SECONDS: float = float(_env("GEMS_MCP_TOOLS_TTL_SECONDS", "300"))
MCP_CALL_TIMEOUT_SECONDS: float = float(_env("GEMS_MCP_CALL_TIMEOUT_SECONDS", "120"))
