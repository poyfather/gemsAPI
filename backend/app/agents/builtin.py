"""
Built-in tools: read-only access to the gem library itself.

Importing this module registers them. They are deliberately boring: the
first agent shipped with Lapidary is a librarian for its own prompts.
"""
from __future__ import annotations
import asyncio
import shutil
import sys

from app import settings
from app.agents.tools import tool
from app.services import gem_service, memory_service


@tool()
async def search_gems(query: str = "", tag: str = "") -> list[dict]:
    """Find gems by a keyword in the name or description, and optionally by tag. Returns name, description, tags, variables and kind for each match."""
    gems = await gem_service.get_all_gems()
    q, t = query.lower(), tag.lower()
    out = []
    for g in gems:
        text_match = (q in g.name.lower() or q in g.description.lower()) if q else True
        tag_match = (t in [x.lower() for x in g.tags]) if t else True
        if text_match and tag_match:
            out.append({"name": g.name, "description": g.description, "tags": g.tags, "variables": g.variables, "kind": g.kind})
    return out


@tool()
async def get_gem(name: str) -> dict:
    """Read one gem by exact name: its raw system prompt, variables, gem references, model and provider."""
    g = await gem_service.get_gem_by_name(name)
    if not g:
        return {"error": f"Gem '{name}' not found."}
    return {
        "name": g.name,
        "description": g.description,
        "system_prompt": g.system_prompt,
        "variables": g.variables,
        "gem_refs": gem_service.extract_gem_refs(g.system_prompt),
        "model": g.model,
        "provider": g.provider,
        "kind": g.kind,
        "tools": g.tools,
        "variables_schema": gem_service.variables_schema(g),
        "examples": [e.model_dump() for e in g.examples],
    }


@tool()
async def resolve_gem(name: str, variables: dict[str, str] | None = None) -> dict:
    """Expand a gem's {{gem:name}} references and fill its {variable} placeholders. Returns the resolved prompt, the gems it referenced, and any variables still missing."""
    try:
        r = await gem_service.resolve_gem_detailed(name, variables or {}, strict=False)
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "name": r.gem_name,
        "resolved_prompt": r.resolved_prompt,
        "referenced_gems": r.referenced_gems,
        "variables_missing": r.variables_missing,
        "variable_errors": r.variable_errors,
    }


# ─── Memory (ADR-010): search, then fetch, then remember ───────────────────────

@tool()
async def search_memory(query: str, scope: str = "default", limit: int = 10) -> list[dict]:
    """Search what was remembered from earlier runs, chats and notes. Returns a compact index (id, kind, date, one line each); call get_memories with the ids that matter to read them in full."""
    return [e.model_dump(mode="json") for e in await memory_service.search_index(query, scope=scope, limit=limit)]


@tool()
async def get_memories(ids: list[str]) -> list[dict]:
    """Read memories in full by id (from search_memory). Returns kind, text, tags, source, date."""
    return [m.model_dump(mode="json") for m in await memory_service.get(ids)]


@tool()
async def remember(text: str, kind: str = "note", tags: list[str] | None = None, scope: str = "default") -> dict:
    """Store something worth keeping for later runs: a decision, a preference the user stated, a lesson from a failure, a handoff for the next session, or a plain note. Kind is one of observation, summary, decision, preference, lesson, handoff, note. Anything inside <private>...</private> is dropped."""
    try:
        m = await memory_service.remember(text, kind=kind, tags=tags or [], scope=scope, source="run")
    except ValueError as exc:
        return {"error": str(exc)}
    return m.model_dump(mode="json") if m else {"error": "nothing to remember once <private> text is removed"}


@tool(risky=True)
async def forget(memory_id: str) -> dict:
    """Delete one memory by id. This cannot be undone, so it waits for the user's approval."""
    return {"deleted": await memory_service.forget(memory_id), "id": memory_id}


# ─── PowerShell 7 ──────────────────────────────────────────────────────────────

def _powershell_program() -> str | None:
    """pwsh (PowerShell 7) wherever it is installed; Windows PowerShell 5 as the fallback on Windows."""
    return shutil.which("pwsh") or (shutil.which("powershell") if sys.platform == "win32" else None)


async def _run_process(program: str, args: list[str], timeout: float) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(program, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", f"stopped after {timeout:.0f} seconds"
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


def _cap(text: str) -> str:
    limit = settings.POWERSHELL_MAX_OUTPUT_CHARS
    return text if len(text) <= limit else f"[{len(text) - limit} characters dropped]\n" + text[-limit:]


@tool(risky=True)
async def run_powershell(script: str) -> str:
    """Run a PowerShell script on the machine that runs Lapidary (PowerShell 7 when installed, Windows PowerShell 5 otherwise) and return its output and exit code. It runs with the backend's own user account and can change the system, so prefer read-only cmdlets, explain what a script does before calling this, and never disable security features or delete data without being told to."""
    program = _powershell_program()
    if not program:
        return "PowerShell is not installed on the machine that runs Lapidary. Install PowerShell 7 (winget install Microsoft.PowerShell) or run this from Lapidary Console."
    args = ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script]
    code, out, err = await _run_process(program, args, settings.POWERSHELL_TIMEOUT_SECONDS)
    text = _cap(out.rstrip())
    if err.strip():
        text += ("\n" if text else "") + "[stderr]\n" + _cap(err.rstrip())
    return f"{text}\n[exit {code}]" if text else f"[exit {code}]"
