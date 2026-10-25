"""
Built-in tools: read-only access to the gem library itself.

Importing this module registers them. They are deliberately boring: the
first agent shipped with Lapidary is a librarian for its own prompts.
"""
from __future__ import annotations

from app.agents.tools import tool
from app.services import gem_service


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
    }


@tool()
async def resolve_gem(name: str, variables: dict[str, str] | None = None) -> dict:
    """Expand a gem's {{gem:name}} references and fill its {variable} placeholders. Returns the resolved prompt, the gems it referenced, and any variables still missing."""
    try:
        r = await gem_service.resolve_gem_detailed(name, variables or {})
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "name": r.gem_name,
        "resolved_prompt": r.resolved_prompt,
        "referenced_gems": r.referenced_gems,
        "variables_missing": r.variables_missing,
    }
