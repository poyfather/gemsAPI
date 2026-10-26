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

from app.models import VARIABLE_TYPES, Gem, GemCreate, GemUpdate, VariableSpec
from app.storage import get_store


class VariableError(ValueError):
    """Values that do not fit the gem's blanks: a wrong type, a value outside a choice, a required blank left empty."""

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


# ─── Typed blanks (roadmap 29) ─────────────────────────────────────────────────

_TRUE, _FALSE = {"true", "yes", "y", "1", "on"}, {"false", "no", "n", "0", "off"}


def clean_specs(specs: dict, prompt: str) -> dict[str, dict]:
    """Keep specs only for blanks the prompt still has, and refuse ones that cannot work. Raises ValueError."""
    names = set(extract_variables(prompt))
    out: dict[str, dict] = {}
    for name, raw in (specs or {}).items():
        if name not in names:
            continue
        spec = raw if isinstance(raw, VariableSpec) else VariableSpec(**(raw or {}))
        if spec.type not in VARIABLE_TYPES:
            raise ValueError(f"The blank {{{name}}} has type '{spec.type}'; use one of {', '.join(VARIABLE_TYPES)}.")
        if spec.type == "choice":
            spec.options = [o.strip() for o in spec.options if o and o.strip()]
            if not spec.options:
                raise ValueError(f"The blank {{{name}}} is a choice but has no options.")
        if spec.default not in (None, ""):
            problem = check_value(name, spec, spec.default)
            if problem:
                raise ValueError(f"The default for {{{name}}} does not fit: {problem}")
        else:
            spec.default = None
        out[name] = spec.model_dump()
    return out


def check_value(name: str, spec: VariableSpec, value: str) -> str | None:
    """Why `value` does not fit the blank, or None when it does."""
    v = (value or "").strip()
    if spec.type == "number":
        try:
            float(v)
        except ValueError:
            return f"{{{name}}} should be a number, not “{value}”"
    if spec.type == "choice" and v not in spec.options:
        return f"{{{name}}} should be one of {', '.join(spec.options)}, not “{value}”"
    if spec.type == "boolean" and v.lower() not in _TRUE | _FALSE:
        return f"{{{name}}} should be yes or no, not “{value}”"
    return None


def apply_specs(specs: dict[str, VariableSpec], expected: list[str], values: dict[str, str]) -> tuple[dict[str, str], list[str], list[str]]:
    """Fill defaults and check values for the expected blanks. Returns (values, defaulted, errors)."""
    filled = dict(values)
    defaulted, errors = [], []
    for name in expected:
        spec = specs.get(name)
        if spec is None:
            continue
        given = filled.get(name)
        if given in (None, "") and spec.default not in (None, ""):
            filled[name] = spec.default
            defaulted.append(name)
            continue
        if given in (None, ""):
            if spec.required:
                errors.append(f"{{{name}}} is required" + (f": {spec.description}" if spec.description else ""))
            continue
        problem = check_value(name, spec, given)
        if problem:
            errors.append(problem)
        elif spec.type == "boolean":
            filled[name] = "yes" if given.strip().lower() in _TRUE else "no"
    return filled, defaulted, errors


def _specs_of(gem: Gem | None) -> dict[str, VariableSpec]:
    if gem is None:
        return {}
    return {k: (v if isinstance(v, VariableSpec) else VariableSpec(**v)) for k, v in (gem.variable_specs or {}).items()}


def variables_schema(gem: Gem) -> dict:
    """The gem's blanks as a JSON schema, so an MCP client knows what to fill."""
    specs = _specs_of(gem)
    props, required = {}, []
    for name in gem.variables:
        spec = specs.get(name, VariableSpec())
        prop: dict = {"type": {"number": "number", "boolean": "boolean"}.get(spec.type, "string")}
        if spec.description:
            prop["description"] = spec.description
        if spec.type == "choice":
            prop["enum"] = spec.options
        if spec.default not in (None, ""):
            prop["default"] = spec.default
        props[name] = prop
        if spec.required and spec.default in (None, ""):
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


# ─── CRUD (delegated to the storage backend) ───────────────────────────────────

async def get_all_gems() -> list[Gem]:
    return await get_store().list_gems()


async def get_gem_by_name(name: str) -> Optional[Gem]:
    return await get_store().get_gem_by_name(name)


async def get_gem_by_id(gem_id: str) -> Optional[Gem]:
    return await get_store().get_gem_by_id(gem_id)


async def create_gem(data: GemCreate, *, source: str = "api") -> Gem:
    from app.services import version_service

    data = GemCreate(**{**data.model_dump(), "variable_specs": clean_specs(data.variable_specs, data.system_prompt)})
    gem = await get_store().create_gem(data, extract_variables(data.system_prompt))
    await version_service.record(gem, note="created", source=source)
    return gem


async def update_gem(gem_id: str, data: GemUpdate, *, source: str = "api") -> Gem:
    """Apply the fields that are set, then record the result as a new version (roadmap 14)."""
    from app.services import version_service

    updates = {k: v for k, v in data.model_dump().items() if v is not None and k != "note"}
    before = await get_store().get_gem_by_id(gem_id)
    if "system_prompt" in updates:
        updates["variables"] = extract_variables(updates["system_prompt"])
    if "variable_specs" in updates or "system_prompt" in updates:
        prompt = updates.get("system_prompt", before.system_prompt if before else "")
        specs = updates.get("variable_specs", before.variable_specs if before else {})
        updates["variable_specs"] = clean_specs(specs, prompt)
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
    variables_defaulted: list[str] = field(default_factory=list)  # filled from the blank's default
    variable_errors: list[str] = field(default_factory=list)      # values that do not fit their blank


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


async def resolve_text(name: str, text: str, variables: dict[str, str] | None = None, specs: dict | None = None) -> str:
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
    typed = {k: (v if isinstance(v, VariableSpec) else VariableSpec(**v)) for k, v in (specs or {}).items()}
    filled, _, _ = apply_specs(typed, extract_variables(prompt), variables or {})
    return fill_variables(prompt, filled)


async def resolve_gem_detailed(name: str, variables: dict[str, str] | None = None, *, strict: bool = True) -> ResolvedGem:
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
    # Specs from the embedded gems, then the gem's own (which win for a shared name).
    specs: dict[str, VariableSpec] = {}
    for ref in reversed(refs):
        specs.update(_specs_of(await get_gem_by_name(ref)))
    specs.update(_specs_of(await get_gem_by_name(name)))
    variables, defaulted, errors = apply_specs(specs, expected, variables)
    if errors and strict:
        raise VariableError("Fill in the blanks: " + "; ".join(errors) + ".")
    used = [v for v in expected if v in variables and v not in defaulted]
    missing = [v for v in expected if v not in variables]
    return ResolvedGem(
        gem_name=name,
        resolved_prompt=fill_variables(expanded, variables),
        referenced_gems=refs,
        variables_expected=expected,
        variables_used=used,
        variables_missing=missing,
        variables_defaulted=defaulted,
        variable_errors=errors,
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
