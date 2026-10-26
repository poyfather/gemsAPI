"""
Version history for gems (roadmap item 14).

Every create and every save that changes something records the gem's fields as
a new numbered version. The app records them, not a database trigger, so
SQLite and Supabase behave the same. A gem that existed before history was
kept (a seed, or anything saved by an older Lapidary) gets its pre-edit state
stored as version 1 the first time it is changed, so the first diff is real.
Reverting writes the old fields back as a new version; history only grows.

Recording never stops an edit: a failure is logged and the save goes through.
"""
from __future__ import annotations
import difflib
import logging
from datetime import datetime, timezone

from app.models import VERSIONED_FIELDS, Gem, GemDiff, GemVersion, GemVersionSummary
from app.storage import get_store

logger = logging.getLogger(__name__)
BASELINE_NOTE = "as it was before history was kept"


def _store():
    return get_store()


def snapshot(gem: Gem) -> dict:
    data = gem.model_dump()
    return {f: data.get(f) for f in VERSIONED_FIELDS}


def changed_fields(before: dict | None, after: dict) -> list[str]:
    if before is None:
        return []
    return [f for f in VERSIONED_FIELDS if before.get(f) != after.get(f) and f != "variables"]


async def versions(gem_id: str) -> list[GemVersion]:
    found = await _store().list_gem_versions(gem_id)
    for v in found:   # versions saved before typed blanks existed had none
        v.snapshot.setdefault("variable_specs", {})
    return found


async def record(gem: Gem, *, note: str = "", source: str = "api") -> GemVersion | None:
    """Store the gem as a new version unless it equals the latest one. Returns the version, or None when nothing changed or recording failed."""
    try:
        existing = await versions(gem.id)
        snap = snapshot(gem)
        if existing and existing[-1].snapshot == snap:
            return None
        number = existing[-1].version + 1 if existing else 1
        return await _store().add_gem_version(gem.id, number, snap, (note or "").strip()[:500], source)
    except Exception:  # noqa: BLE001 - history must never block a save
        logger.exception("could not record a version of gem %s", gem.name)
        return None


async def ensure_baseline(gem: Gem) -> None:
    """Before the first recorded change to a gem with no history, keep how it looked."""
    try:
        if not await versions(gem.id):
            await _store().add_gem_version(gem.id, 1, snapshot(gem), BASELINE_NOTE, "baseline")
    except Exception:  # noqa: BLE001
        logger.exception("could not record a baseline for gem %s", gem.name)


async def history(gem: Gem) -> list[GemVersionSummary]:
    """Newest first, each with the fields that changed from the version before. A gem with no history shows its current state as version 1."""
    found = await versions(gem.id)
    if not found:
        return [GemVersionSummary(version=1, note=BASELINE_NOTE, source="baseline", created_at=gem.updated_at, current=True)]
    out, before = [], None
    for v in found:
        out.append(GemVersionSummary(version=v.version, note=v.note, source=v.source, created_at=v.created_at, changed=changed_fields(before, v.snapshot)))
        before = v.snapshot
    out[-1].current = snapshot(gem) == found[-1].snapshot
    return list(reversed(out))


async def get(gem: Gem, number: int) -> GemVersion | None:
    found = await versions(gem.id)
    if not found and number == 1:
        return GemVersion(gem_id=gem.id, version=1, snapshot=snapshot(gem), note=BASELINE_NOTE, source="baseline", created_at=gem.updated_at)
    return next((v for v in found if v.version == number), None)


async def diff(gem: Gem, from_version: int | None = None, to_version: int | None = None) -> GemDiff:
    """What changed between two versions; by default the latest against the one before. Raises LookupError for a missing version."""
    found = await versions(gem.id)
    latest = found[-1].version if found else 1
    to_version = to_version or latest
    from_version = from_version or max(1, to_version - 1)
    a, b = await get(gem, from_version), await get(gem, to_version)
    if a is None or b is None:
        raise LookupError(f"'{gem.name}' has no version {from_version if a is None else to_version} (latest is {latest}).")
    changed = changed_fields(a.snapshot, b.snapshot)
    fields = {f: {"from": a.snapshot.get(f), "to": b.snapshot.get(f)} for f in changed if f != "system_prompt"}
    prompt_diff = ""
    if "system_prompt" in changed:
        prompt_diff = "\n".join(difflib.unified_diff(
            (a.snapshot.get("system_prompt") or "").splitlines(), (b.snapshot.get("system_prompt") or "").splitlines(),
            fromfile=f"{gem.name} v{from_version}", tofile=f"{gem.name} v{to_version}", lineterm=""))
    return GemDiff(gem_name=gem.name, from_version=from_version, to_version=to_version, changed=changed, fields=fields, prompt_diff=prompt_diff)


async def revert(gem: Gem, number: int, note: str = "") -> Gem:
    """Write version `number`'s fields back as a new version. The name stays as it is, so references to the gem keep working."""
    from app.models import GemUpdate
    from app.services import gem_service

    old = await get(gem, number)
    if old is None:
        raise LookupError(f"'{gem.name}' has no version {number}.")
    fields = {f: old.snapshot.get(f) for f in VERSIONED_FIELDS if f not in ("name", "variables")}
    reason = f"restored version {number}" + (f": {note.strip()}" if note and note.strip() else "")
    return await gem_service.update_gem(gem.id, GemUpdate(**fields, note=reason), source="revert")


def now() -> datetime:
    return datetime.now(timezone.utc)
