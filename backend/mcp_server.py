"""
Lapidary MCP Server

Exposes your prompt library to any MCP client (Claude Desktop, Cursor, etc.)
via the Model Context Protocol.

USAGE
─────
  # Run via fastmcp CLI
  fastmcp run mcp_server.py

  # Or directly
  python mcp_server.py

  # Add to Claude Desktop (~/.claude_desktop_config.json)
  {
    "mcpServers": {
      "Lapidary": {
        "command": "python",
        "args": ["/absolute/path/to/backend/mcp_server.py"]
      }
    }
  }

TOOLS
─────
  list_gems            — browse the library
  get_gem              — read a gem's raw prompt
  resolve_gem_prompt   — fully resolve a gem (expand refs + fill variables)
  chat_with_gem        — send a message to an LLM using a gem as system prompt
  create_gem           — add a new gem to the library
  update_gem           — change a gem; the change is kept in its history
  gem_history          — a gem's versions, newest first
  diff_gem_versions    — what changed between two versions
  revert_gem           — restore an earlier version as a new one
  add_gem_eval         — add a test case to a gem
  run_gem_evals        — score a gem against its test cases, or estimate the cost
  compare_gem          — two to four versions or AIs side by side, on a question or the tests
  search_gems          — filter gems by tag or keyword
  run_agent            — run an agent gem: a tool-using loop, with the run record
  approve_run          — continue a run that paused at a risky tool call
"""
from __future__ import annotations
import os
import sys

# Make sure the app package is importable when run from the backend/ directory
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP
from app.services.gem_service import (
    get_all_gems,
    get_gem_by_name,
    resolve_gem,
    resolve_gem_detailed,
    extract_gem_refs,
    variables_schema,
)
from app import settings
from app.services.llm_service import available_models, complete
from app.services import memory_service
import app.agents.builtin  # noqa: F401
from app.agents import run_service
from app.agents.runner import resume_run as _resume_run, run_agent as _run_agent
from app.agents.mcp_sources import refresh_remote_tools
from app.agents.tools import all_tools
from app.models import GemCreate

mcp = FastMCP(
    name="lapidary",
    instructions=(
        "Access and manage your prompt library (gems). "
        "Gems support {variable} placeholders and {{gem:name}} recursive composition — "
        "one gem can embed another. Use resolve_gem_prompt to get the fully expanded "
        "system prompt before passing it to an LLM, or use chat_with_gem to do it all at once."
    ),
)


# ─── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_gems() -> list[dict]:
    """
    List all gems in the library.

    Returns a summary of each gem: name, description, tags, variables, provider, and model.
    Use get_gem to read the full prompt text.
    """
    gems = await get_all_gems()
    return [
        {
            "name":        g.name,
            "description": g.description,
            "tags":        g.tags,
            "variables":   g.variables,
            "variables_schema": variables_schema(g),
            "provider":    g.provider,
            "model":       g.model,
        }
        for g in gems
    ]


@mcp.tool()
async def search_gems(query: str = "", tag: str = "") -> list[dict]:
    """
    Search gems by keyword or tag.

    Args:
        query: Text to match against name or description (case-insensitive).
        tag:   Filter to gems that include this tag.

    Returns matching gems with name, description, tags, and variables.
    """
    gems = await get_all_gems()
    results = []
    for g in gems:
        name_match  = query.lower() in g.name.lower()        if query else True
        desc_match  = query.lower() in g.description.lower() if query else True
        tag_match   = tag.lower() in [t.lower() for t in g.tags] if tag else True
        if (name_match or desc_match) and tag_match:
            results.append({
                "name":        g.name,
                "description": g.description,
                "tags":        g.tags,
                "variables":   g.variables,
                "provider":    g.provider,
                "model":       g.model,
            })
    return results


@mcp.tool()
async def get_gem(name: str) -> dict:
    """
    Get a gem by name, including its full raw system_prompt.

    Args:
        name: The gem's unique name (e.g. 'code_reviewer').

    The raw prompt may contain {{gem:other_name}} and {variable} tags.
    Use resolve_gem_prompt to expand these.
    """
    gem = await get_gem_by_name(name)
    if not gem:
        return {"error": f"Gem '{name}' not found."}
    return {
        "id":            gem.id,
        "name":          gem.name,
        "description":   gem.description,
        "system_prompt": gem.system_prompt,
        "model":         gem.model,
        "provider":      gem.provider,
        "tags":          gem.tags,
        "variables":     gem.variables,
        "variables_schema": variables_schema(gem),
        "gem_refs":      extract_gem_refs(gem.system_prompt),
        "created_at":    gem.created_at.isoformat(),
        "updated_at":    gem.updated_at.isoformat(),
    }


@mcp.tool()
async def resolve_gem_prompt(
    name: str,
    variables: dict[str, str] | None = None,
) -> dict:
    """
    Resolve a gem's system prompt — expand all {{gem:name}} references
    recursively and fill in {variable} placeholders.

    Args:
        name:      The gem's unique name.
        variables: Key-value pairs for any {variable} placeholders in the gem.

    Returns the fully resolved prompt, the list of gems referenced, and any
    variables that were expected but not provided.

    Example:
        resolve_gem_prompt("code_reviewer", {"language": "Python"})
    """
    if variables is None:
        variables = {}
    try:
        result = await resolve_gem_detailed(name, variables, strict=False)
        return {
            "gem_name":            result.gem_name,
            "resolved_prompt":     result.resolved_prompt,
            "referenced_gems":     result.referenced_gems,
            "variables_used":      result.variables_used,
            "variables_missing":   result.variables_missing,
            "variables_defaulted": result.variables_defaulted,
            "variable_errors":     result.variable_errors,
        }
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def chat_with_gem(
    gem_name: str,
    message: str,
    variables: dict[str, str] | None = None,
    model_override: str | None = None,
    provider_override: str | None = None,
) -> dict:
    """
    Send a single user message to an LLM using a gem as the system prompt.

    The gem is resolved (refs expanded, variables filled) before the call.

    Args:
        gem_name:          Name of the gem to use.
        message:           The user message to send.
        variables:         Values for {variable} placeholders in the gem.
        model_override:    Override the gem's default model.
        provider_override: Override the provider ('anthropic' or 'openai').

    Returns the LLM response along with metadata.
    """
    if variables is None:
        variables = {}
    try:
        resolved, _ = await resolve_gem(gem_name, variables)
        gem = await get_gem_by_name(gem_name)
        if not gem:
            return {"error": f"Gem '{gem_name}' not found."}

        from app.services import router as model_router
        choice = await model_router.choose(gem, provider_override=provider_override, model_override=model_override)
        model, provider = choice.model, choice.provider

        response = await complete(
            system_prompt=resolved,
            messages=[{"role": "user", "content": message}],
            model=model,
            provider=provider,
        )
        return {
            "gem_name": gem_name,
            "response": response,
            "model":    model,
            "provider": provider,
            "reason":   choice.reason,
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def create_gem(
    name: str,
    description: str,
    system_prompt: str,
    model: str | None = None,
    provider: str | None = None,
    tags: list[str] | None = None,
    variable_specs: dict[str, dict] | None = None,
) -> dict:
    """
    Create a new gem in the library.

    Args:
        name:          Unique snake_case name (e.g. 'my_assistant').
        description:   What this gem does.
        system_prompt: The prompt. Use {variable} for placeholders, {{gem:name}} to embed other gems.
        model:         LLM model; defaults to the server's GEMS_DEFAULT_MODEL.
        provider:      'anthropic', 'openai', 'local', or 'auto' (the model policy decides); defaults to GEMS_DEFAULT_PROVIDER.
        tags:          Optional list of tags.
        variable_specs: Optional, by blank name: {"description", "type" (text, long_text, number, choice, boolean),
                       "options" (for a choice), "default", "required"}.

    Example system_prompt with composition:
        "{{gem:base_assistant}}\\n\\nYou specialize in {domain} tasks."
    """
    if tags is None:
        tags = []
    try:
        from app.services.gem_service import create_gem as _create
        gem = await _create(GemCreate(
            name=name,
            description=description,
            system_prompt=system_prompt,
            model=model or settings.DEFAULT_MODEL,
            provider=provider or settings.DEFAULT_PROVIDER,
            tags=tags,
            variable_specs=variable_specs or {},
        ), source="mcp")
        return {"success": True, "id": gem.id, "name": gem.name, "variables": gem.variables}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def update_gem(name: str, system_prompt: str | None = None, description: str | None = None,
                     tags: list[str] | None = None, variable_specs: dict[str, dict] | None = None, note: str = "") -> dict:
    """
    Change a gem and keep the change in its history (roadmap 14). Only the fields you pass change.
    `variable_specs` is merged per blank: pass {"tone": {...}} to describe one blank and keep the
    others (see variables_schema in get_gem). Say in `note` what you changed and why.
    """
    from app.models import GemUpdate
    from app.services.gem_service import update_gem as _update
    gem = await get_gem_by_name(name)
    if not gem:
        return {"error": f"Gem '{name}' not found."}
    merged = None
    if variable_specs is not None:
        merged = {k: v.model_dump() for k, v in gem.variable_specs.items()}
        merged.update(variable_specs)
    try:
        updated = await _update(gem.id, GemUpdate(system_prompt=system_prompt, description=description, tags=tags,
                                                  variable_specs=merged, note=note or None), source="mcp")
    except ValueError as exc:
        return {"error": str(exc)}
    return {"name": updated.name, "variables": updated.variables, "variables_schema": variables_schema(updated), "updated_at": str(updated.updated_at)}


@mcp.tool()
async def gem_history(name: str) -> list[dict]:
    """A gem's saved versions, newest first: number, date, note, and which fields changed from the version before."""
    from app.services import version_service
    gem = await get_gem_by_name(name)
    if not gem:
        return [{"error": f"Gem '{name}' not found."}]
    return [v.model_dump(mode="json") for v in await version_service.history(gem)]


@mcp.tool()
async def diff_gem_versions(name: str, from_version: int | None = None, to_version: int | None = None) -> dict:
    """What changed between two versions of a gem (default: the latest against the one before). The prompt comes back as a unified diff."""
    from app.services import version_service
    gem = await get_gem_by_name(name)
    if not gem:
        return {"error": f"Gem '{name}' not found."}
    try:
        return (await version_service.diff(gem, from_version, to_version)).model_dump(mode="json")
    except LookupError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def revert_gem(name: str, version: int, note: str = "") -> dict:
    """Restore an earlier version of a gem. It is saved as a new version, so nothing in the history is lost; the name stays."""
    from app.services import version_service
    gem = await get_gem_by_name(name)
    if not gem:
        return {"error": f"Gem '{name}' not found."}
    try:
        restored = await version_service.revert(gem, version, note)
    except LookupError as exc:
        return {"error": str(exc)}
    return {"name": restored.name, "restored_version": version, "updated_at": str(restored.updated_at)}


@mcp.tool()
async def run_agent(
    gem_name: str,
    message: str,
    variables: dict[str, str] | None = None,
    allow_risky: bool = False,
) -> dict:
    """
    Run a gem as an agent: the model may call the gem's tools in a loop
    until it answers. Returns the final answer, the run id, the steps taken
    and every tool call with its result. Costs provider credit per turn.

    Args:
        gem_name:    Name of an agent gem (kind = 'agent'; prompt gems run as a single turn).
        message:     The user message that starts the run.
        variables:   Values for {variable} placeholders in the gem.
        allow_risky: Let the run call tools marked risky. Off by default.
    """
    try:
        result = await _run_agent(gem_name, message, variables or {}, allow_risky=allow_risky)
    except ValueError as exc:
        return {"error": str(exc)}
    run = result.run
    waiting = next((e.data for e in result.events if e.type == "approval_requested"), None)
    return {
        "run_id": run.id,
        "status": run.status,
        "waiting_on": waiting,
        "output": run.output,
        "steps": run.steps,
        "model": run.model,
        "provider": run.provider,
        "tool_calls": [e.data for e in result.events if e.type == "tool_result"],
        "error": run.error,
    }


@mcp.tool()
async def approve_run(run_id: str, approve: bool = True) -> dict:
    """
    Continue a run that is waiting for approval of a risky tool call.

    Args:
        run_id:  The run id returned by run_agent (status waiting_approval).
        approve: True to let the pending call run, False to deny it; the loop continues either way.
    """
    try:
        result = await _resume_run(run_id, approve)
    except (LookupError, ValueError) as exc:
        return {"error": str(exc)}
    run = result.run
    waiting = next((e.data for e in result.events if e.type == "approval_requested"), None)
    return {
        "run_id": run.id, "status": run.status, "waiting_on": waiting, "output": run.output,
        "steps": run.steps, "tool_calls": [e.data for e in result.events if e.type == "tool_result"], "error": run.error,
    }


@mcp.tool()
async def search_memory(query: str, scope: str = "default", limit: int = 10) -> list[dict]:
    """
    Search Lapidary Memory (ADR-010): what was remembered from earlier runs, chats
    and notes, shared by every client on this machine. Returns a compact index
    (id, kind, date, one line each); call get_memories with the ids that matter.
    """
    return [e.model_dump(mode="json") for e in await memory_service.search_index(query, scope=scope, limit=limit)]


@mcp.tool()
async def get_memories(ids: list[str]) -> list[dict]:
    """Read memories in full by id (from search_memory): kind, text, tags, source, date."""
    return [m.model_dump(mode="json") for m in await memory_service.get(ids)]


@mcp.tool()
async def remember(text: str, kind: str = "note", tags: list[str] | None = None, scope: str = "default") -> dict:
    """
    Store something for later: a decision, a preference the user stated, a lesson
    from a failure, a handoff for the next session, or a note. Kind is one of
    observation, summary, decision, preference, lesson, handoff, note. Anything
    inside <private>...</private> is dropped before storing.
    """
    try:
        m = await memory_service.remember(text, kind=kind, tags=tags or [], scope=scope, source="mcp")
    except ValueError as exc:
        return {"error": str(exc)}
    return m.model_dump(mode="json") if m else {"error": "nothing to remember once <private> text is removed"}


@mcp.tool()
async def forget(memory_id: str) -> dict:
    """Delete one memory by id. Cannot be undone."""
    return {"deleted": await memory_service.forget(memory_id), "id": memory_id}


@mcp.tool()
async def list_pipelines() -> list[dict]:
    """Pipelines (ADR-011): a builder gem followed by gate gems that pass or fail its output, with retries and acceptance."""
    from app.storage import get_store
    return [p.model_dump(mode="json") for p in await get_store().list_pipelines()]


@mcp.tool()
async def run_pipeline(name: str, message: str, variables: dict[str, str] | None = None, allow_risky: bool = False, memory_scope: str = "default") -> dict:
    """
    Run a pipeline: the builder works on the message, each gate checks the output,
    failures go back to the builder up to max_attempts, then the run waits for
    acceptance or finishes. Returns the pipeline run with its attempts and gate
    verdicts; use resume_pipeline to accept, reject or continue after an approval.
    """
    from app.agents.pipeline import run_pipeline as _run_pipeline
    try:
        result = await _run_pipeline(name, message, variables or {}, allow_risky=allow_risky, memory_scope=memory_scope)
    except ValueError as exc:
        return {"error": str(exc)}
    return result.run.model_dump(mode="json")


@mcp.tool()
async def resume_pipeline(run_id: str, accept: bool | None = None, note: str = "") -> dict:
    """Continue a paused pipeline run: accept=true or false (with a note) when it waits for acceptance; no accept when it waited for an approval you have since given."""
    from app.agents.pipeline import resume_pipeline as _resume_pipeline
    try:
        result = await _resume_pipeline(run_id, accept=accept, note=note)
    except (LookupError, ValueError) as exc:
        return {"error": str(exc)}
    return result.run.model_dump(mode="json")


@mcp.tool()
async def add_gem_eval(name: str, input: str, check: str = "contains", expected: str = "", case_name: str = "",
                       variables: dict[str, str] | None = None) -> dict:
    """
    Add a test case to a gem (roadmap 28): the input it is given, values for its blanks, and a check on
    the answer: contains, not_contains, all_of (one phrase per line), equals, json (a JSON schema, or
    empty for any valid JSON), or judge (criteria an AI checks the answer against).
    """
    from app.models import EvalCaseCreate
    from app.services import eval_service
    gem = await get_gem_by_name(name)
    if not gem:
        return {"error": f"Gem '{name}' not found."}
    try:
        case = await eval_service.add_case(gem, EvalCaseCreate(name=case_name, input=input, variables=variables or {}, check=check, expected=expected))
    except ValueError as exc:
        return {"error": str(exc)}
    return case.model_dump(mode="json")


@mcp.tool()
async def run_gem_evals(name: str, provider_override: str | None = None, model_override: str | None = None, estimate_only: bool = False) -> dict:
    """
    Run a gem's test cases and score it, or with estimate_only just say what a run would cost (model
    calls, rough tokens, whether it is free on this PC). A run is recorded against the gem's version
    and lists regressions and fixes against the baseline. Running calls the model, so it costs money
    unless the AI runs on this PC.
    """
    from app.services import eval_service
    gem = await get_gem_by_name(name)
    if not gem:
        return {"error": f"Gem '{name}' not found."}
    if estimate_only:
        return (await eval_service.estimate(gem, provider_override, model_override)).model_dump(mode="json")
    try:
        return (await eval_service.run(gem, provider_override, model_override)).model_dump(mode="json")
    except eval_service.EvalError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def compare_gem(name: str, variants: list[dict], message: str = "", variables: dict[str, str] | None = None,
                      on_tests: bool = False, estimate_only: bool = False) -> dict:
    """
    Side by side (roadmap 30): run a gem in two to four columns and compare. Each variant is
    {"version": n or null for the current one, "provider_override": ..., "model_override": ..., "label": ...}.
    With a message, every column answers it; with on_tests, the gem's tests run in every column and
    you get a pass and fail grid. estimate_only says how many model calls it takes and whether it is free.
    """
    from app.models import CompareRequest
    from app.services import compare_service
    gem = await get_gem_by_name(name)
    if not gem:
        return {"error": f"Gem '{name}' not found."}
    try:
        req = CompareRequest(message=message, variables=variables or {}, variants=variants)
        if estimate_only:
            return (await compare_service.estimate(gem, req, on_tests=on_tests)).model_dump(mode="json")
        if on_tests:
            return (await compare_service.compare_tests(gem, req)).model_dump(mode="json")
        return (await compare_service.compare(gem, req)).model_dump(mode="json")
    except (compare_service.CompareError, ValueError) as exc:
        return {"error": str(exc)}


@mcp.tool()
async def list_agent_tools() -> list[dict]:
    """List the tools an agent gem may be given, built in and from configured MCP servers, with their argument schemas."""
    await refresh_remote_tools()
    return [t.info() for t in all_tools()]


@mcp.tool()
async def list_available_models() -> dict:
    """
    Return the models each provider currently offers (live list, cached ten minutes).
    Useful when creating or updating gems.
    """
    return await available_models()


# ─── Resources ─────────────────────────────────────────────────────────────────
# Expose each gem as an MCP resource so clients can read prompts directly.

@mcp.resource("gems://list")
async def gems_resource() -> str:
    """All gems as a formatted text list."""
    gems = await get_all_gems()
    if not gems:
        return "No gems in library."
    lines = ["# Gems Library\n"]
    for g in gems:
        lines.append(f"## {g.name}")
        lines.append(f"_{g.description}_")
        if g.tags:
            lines.append(f"Tags: {', '.join(g.tags)}")
        if g.variables:
            lines.append(f"Variables: {', '.join('{' + v + '}' for v in g.variables)}")
        lines.append(f"Provider: {g.provider} / {g.model}")
        lines.append("")
    return "\n".join(lines)


@mcp.resource("runs://{run_id}")
async def run_resource(run_id: str) -> str:
    """A run and its events, as text."""
    found = await run_service.get_run(run_id)
    if not found:
        return f"Run '{run_id}' not found."
    run, events = found
    lines = [f"# Run {run.id}", f"gem: {run.gem_name}  status: {run.status}  steps: {run.steps}  model: {run.provider}/{run.model}", ""]
    for e in events:
        lines.append(f"[{e.seq}] {e.type}: {e.data}")
    lines += ["", "## Output", run.output or ""]
    return "\n".join(lines)


@mcp.resource("gems://{name}")
async def gem_resource(name: str) -> str:
    """Read a specific gem's system prompt as a resource."""
    gem = await get_gem_by_name(name)
    if not gem:
        return f"Gem '{name}' not found."
    return f"# {gem.name}\n\n{gem.description}\n\n---\n\n{gem.system_prompt}"


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
