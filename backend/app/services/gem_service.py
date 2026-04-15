"""
Gem service — CRUD + recursive resolution.

Syntax in system_prompt:
  {variable_name}      — placeholder filled at call time
  {{gem:other_gem}}    — embed another gem recursively (depth-limited, cycle-safe)
"""
from __future__ import annotations
import re
from typing import Optional

from app.database import get_supabase
from app.models import Gem, GemCreate, GemUpdate

# Patterns
_VAR_RE = re.compile(r'\{([^{}]+)\}')           # matches {variable}
_GEM_RE = re.compile(r'\{\{gem:([^}]+)\}\}')    # matches {{gem:name}}

MAX_DEPTH = 10  # prevent runaway recursion


# ─── Helpers ───────────────────────────────────────────────────────────────────

def extract_variables(prompt: str) -> list[str]:
    """Return unique variable names from {variable} placeholders, ignoring {{gem:…}}."""
    # Blank out gem refs so we don't falsely capture 'gem' as a variable
    sanitized = _GEM_RE.sub('', prompt)
    return sorted(set(_VAR_RE.findall(sanitized)))


def extract_gem_refs(prompt: str) -> list[str]:
    """Return unique gem names referenced in {{gem:name}} tags."""
    return sorted(set(ref.strip() for ref in _GEM_RE.findall(prompt)))


def _row_to_gem(row: dict) -> Gem:
    return Gem(**row)


# ─── CRUD ──────────────────────────────────────────────────────────────────────

async def get_all_gems() -> list[Gem]:
    db = get_supabase()
    result = db.table("gems").select("*").eq("is_active", True).order("name").execute()
    return [_row_to_gem(r) for r in result.data]


async def get_gem_by_name(name: str) -> Optional[Gem]:
    db = get_supabase()
    result = (
        db.table("gems")
        .select("*")
        .eq("name", name)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return _row_to_gem(result.data[0]) if result.data else None


async def get_gem_by_id(gem_id: str) -> Optional[Gem]:
    db = get_supabase()
    result = db.table("gems").select("*").eq("id", gem_id).limit(1).execute()
    return _row_to_gem(result.data[0]) if result.data else None


async def create_gem(data: GemCreate) -> Gem:
    db = get_supabase()
    variables = extract_variables(data.system_prompt)
    row = {**data.model_dump(), "variables": variables}
    result = db.table("gems").insert(row).execute()
    return _row_to_gem(result.data[0])


async def update_gem(gem_id: str, data: GemUpdate) -> Gem:
    db = get_supabase()
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if "system_prompt" in updates:
        updates["variables"] = extract_variables(updates["system_prompt"])
    result = db.table("gems").update(updates).eq("id", gem_id).execute()
    return _row_to_gem(result.data[0])


async def soft_delete_gem(gem_id: str) -> bool:
    db = get_supabase()
    db.table("gems").update({"is_active": False}).eq("id", gem_id).execute()
    return True


# ─── Recursive resolution ──────────────────────────────────────────────────────

async def resolve_gem(
    name: str,
    variables: dict[str, str] | None = None,
    _visited: frozenset[str] | None = None,
    _depth: int = 0,
) -> tuple[str, list[str]]:
    """
    Recursively resolve a gem's system_prompt.

    Steps:
      1. Load the gem.
      2. Find all {{gem:other}} references and recursively resolve them,
         replacing the tag with the resolved text.
      3. Fill in {variable} placeholders with the provided values.

    Returns:
      (resolved_prompt, list_of_all_gem_names_referenced)

    Raises:
      ValueError on circular references, missing gems, or depth exceeded.
    """
    if variables is None:
        variables = {}
    if _visited is None:
        _visited = frozenset()

    if _depth > MAX_DEPTH:
        raise ValueError(
            f"Max recursion depth ({MAX_DEPTH}) exceeded while resolving gem '{name}'. "
            "Check for deep or circular references."
        )

    if name in _visited:
        raise ValueError(
            f"Circular gem reference detected: '{name}' is already in the resolution chain "
            f"({' -> '.join(_visited)} -> {name})."
        )

    gem = await get_gem_by_name(name)
    if not gem:
        raise ValueError(f"Gem '{name}' not found or is inactive.")

    prompt = gem.system_prompt
    new_visited = _visited | {name}
    all_refs: list[str] = []

    # Resolve {{gem:ref}} tags first
    gem_refs = _GEM_RE.findall(prompt)
    for ref_name in gem_refs:
        ref_name = ref_name.strip()
        all_refs.append(ref_name)
        resolved_ref, sub_refs = await resolve_gem(
            ref_name, variables, new_visited, _depth + 1
        )
        all_refs.extend(sub_refs)
        prompt = prompt.replace(f"{{{{gem:{ref_name}}}}}", resolved_ref)

    # Fill {variable} placeholders
    for key, value in variables.items():
        prompt = prompt.replace(f"{{{key}}}", value)

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique_refs = [r for r in all_refs if not (r in seen or seen.add(r))]  # type: ignore[func-returns-value]

    return prompt, unique_refs
