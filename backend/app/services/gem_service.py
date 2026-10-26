"""
Gem service — CRUD + recursive resolution.

Syntax in system_prompt:
  {variable_name}      — placeholder filled at call time
  {{gem:other_gem}}    — embed another gem recursively (depth-limited, cycle-safe)
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

from app.models import Gem, GemCreate, GemUpdate
from app.storage import get_store

# Patterns
_VAR_RE = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)\}')   # matches {variable}; identifier names only
_GEM_RE = re.compile(r'\{\{gem:([A-Za-z0-9_.-]+)\}\}')   # matches {{gem:name}}; names are identifiers only

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


# ─── CRUD (delegated to the storage backend) ───────────────────────────────────

async def get_all_gems() -> list[Gem]:
    return await get_store().list_gems()


async def get_gem_by_name(name: str) -> Optional[Gem]:
    return await get_store().get_gem_by_name(name)


async def get_gem_by_id(gem_id: str) -> Optional[Gem]:
    return await get_store().get_gem_by_id(gem_id)


async def create_gem(data: GemCreate, *, source: str = "api") -> Gem:
    from app.services import version_service

    gem = await get_store().create_gem(data, extract_variables(data.system_prompt))
    await version_service.record(gem, note="created", source=source)
    return gem


async def update_gem(gem_id: str, data: GemUpdate, *, source: str = "api") -> Gem:
    """Apply the fields that are set, then record the result as a new version (roadmap 14)."""
    from app.services import version_service

    updates = {k: v for k, v in data.model_dump().items() if v is not None and k != "note"}
    if "system_prompt" in updates:
        updates["variables"] = extract_variables(updates["system_prompt"])
    before = await get_store().get_gem_by_id(gem_id)
    if before is not None:
        await version_service.ensure_baseline(before)
    gem = await get_store().update_gem(gem_id, updates)
    await version_service.record(gem, note=data.note or "", source=source)
    return gem


async def soft_delete_gem(gem_id: str) -> bool:
    await get_store().soft_delete_gem(gem_id)
    return True


# ─── Recursive resolution ──────────────────────────────────────────────────────

@dataclass
class ResolvedGem:
    """Result of resolving a gem: the finished prompt plus what went into it."""
    gem_name: str
    resolved_prompt: str
    referenced_gems: list[str] = field(default_factory=list)
    variables_expected: list[str] = field(default_factory=list)   # placeholders present after expansion
    variables_used: list[str] = field(default_factory=list)       # expected and provided
    variables_missing: list[str] = field(default_factory=list)    # expected and not provided


async def _expand(name: str, visited: frozenset[str], depth: int) -> tuple[str, list[str]]:
    """
    Expand every {{gem:ref}} tag in `name`'s prompt, depth first, without touching variables.

    Returns (expanded_prompt, referenced_gem_names_in_first_seen_order).
    Raises ValueError on a missing gem, a cycle, or a tree deeper than MAX_DEPTH.
    """
    if depth > MAX_DEPTH:
        raise ValueError(
            f"Max recursion depth ({MAX_DEPTH}) exceeded while resolving gem '{name}'. "
            "Check for deep or circular references."
        )
    if name in visited:
        raise ValueError(
            f"Circular gem reference detected: '{name}' is already in the resolution chain "
            f"({' -> '.join(visited)} -> {name})."
        )

    gem = await get_gem_by_name(name)
    if not gem:
        raise ValueError(f"Gem '{name}' not found or is inactive.")

    prompt = gem.system_prompt
    new_visited = visited | {name}
    all_refs: list[str] = []

    for ref_name in _GEM_RE.findall(prompt):
        all_refs.append(ref_name)
        expanded_ref, sub_refs = await _expand(ref_name, new_visited, depth + 1)
        all_refs.extend(sub_refs)
        prompt = prompt.replace(f"{{{{gem:{ref_name}}}}}", expanded_ref)

    seen: set[str] = set()
    unique_refs = [r for r in all_refs if not (r in seen or seen.add(r))]  # type: ignore[func-returns-value]
    return prompt, unique_refs


def fill_variables(prompt: str, variables: dict[str, str]) -> str:
    """
    Fill {variable} placeholders in one pass.

    A single regex substitution means a value that itself contains braces is
    never re-substituted, and the result does not depend on dict order.
    Placeholders with no value are left as they are.
    """
    return _VAR_RE.sub(lambda m: variables.get(m.group(1), m.group(0)), prompt)


async def resolve_text(name: str, text: str, variables: dict[str, str] | None = None) -> str:
    """
    Resolve `text` as if it were gem `name`'s prompt, e.g. an earlier version from its history.
    Its {{gem:...}} references expand against the library as it is now; a reference back to
    `name` itself is a cycle, as it would be for the live gem.
    """
    prompt = text
    visited = frozenset({name})
    for ref_name in _GEM_RE.findall(text):
        expanded_ref, _ = await _expand(ref_name, visited, 1)
        prompt = prompt.replace(f"{{{{gem:{ref_name}}}}}", expanded_ref)
    return fill_variables(prompt, variables or {})


async def resolve_gem_detailed(name: str, variables: dict[str, str] | None = None) -> ResolvedGem:
    """
    Resolve a gem and report which variables it expected, used and is missing.

    Steps:
      1. Load the gem and expand all {{gem:other}} references recursively.
      2. Record the {variable} placeholders present in the expanded text.
      3. Fill them from `variables` in a single pass.
    """
    variables = variables or {}
    expanded, refs = await _expand(name, frozenset(), 0)
    expected = extract_variables(expanded)
    used = [v for v in expected if v in variables]
    missing = [v for v in expected if v not in variables]
    return ResolvedGem(
        gem_name=name,
        resolved_prompt=fill_variables(expanded, variables),
        referenced_gems=refs,
        variables_expected=expected,
        variables_used=used,
        variables_missing=missing,
    )


async def resolve_gem(name: str, variables: dict[str, str] | None = None) -> tuple[str, list[str]]:
    """
    Resolve a gem's system_prompt: expand {{gem:name}} references recursively,
    then fill {variable} placeholders.

    Returns (resolved_prompt, list_of_all_gem_names_referenced).
    Raises ValueError on circular references, missing gems, or depth exceeded.
    """
    result = await resolve_gem_detailed(name, variables)
    return result.resolved_prompt, result.referenced_gems
