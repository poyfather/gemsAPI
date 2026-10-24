"""
gemsAPI MCP Server

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
      "gemsAPI": {
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
  search_gems          — filter gems by tag or keyword
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
    extract_variables,
    extract_gem_refs,
)
from app.services.llm_service import complete, MODELS
from app.models import GemCreate

mcp = FastMCP(
    name="gemsAPI",
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
        resolved, refs = await resolve_gem(name, variables)
        remaining = extract_variables(resolved)
        missing = [v for v in remaining if v not in variables]
        return {
            "gem_name":       name,
            "resolved_prompt": resolved,
            "referenced_gems": refs,
            "variables_missing": missing,
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

        model    = model_override    or gem.model
        provider = provider_override or gem.provider

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
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def create_gem(
    name: str,
    description: str,
    system_prompt: str,
    model: str = "claude-opus-4-5",
    provider: str = "anthropic",
    tags: list[str] | None = None,
) -> dict:
    """
    Create a new gem in the library.

    Args:
        name:          Unique snake_case name (e.g. 'my_assistant').
        description:   What this gem does.
        system_prompt: The prompt. Use {variable} for placeholders, {{gem:name}} to embed other gems.
        model:         Default LLM model.
        provider:      'anthropic' or 'openai'.
        tags:          Optional list of tags.

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
            model=model,
            provider=provider,
            tags=tags,
        ))
        return {"success": True, "id": gem.id, "name": gem.name, "variables": gem.variables}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
async def list_available_models() -> dict:
    """
    Return the models available for each provider.
    Useful when creating or updating gems.
    """
    return MODELS


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
