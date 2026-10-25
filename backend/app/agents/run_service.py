"""Run records, delegated to the storage backend. Tests replace these functions with an in-memory store."""
from __future__ import annotations

from app.models import Run, RunEvent
from app.storage import get_store


async def create_run(gem_id: str | None, gem_name: str, model: str, provider: str, input_text: str) -> Run:
    return await get_store().create_run(gem_id, gem_name, model, provider, input_text)


async def add_event(run_id: str, seq: int, type_: str, data: dict) -> RunEvent:
    return await get_store().add_event(run_id, seq, type_, data)


async def update_run(run_id: str, **fields) -> Run:
    """Update columns on a run without marking it finished (used when a run pauses or resumes)."""
    return await get_store().update_run(run_id, **fields)


async def finish_run(run_id: str, **fields) -> Run:
    from datetime import datetime, timezone

    fields.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
    return await update_run(run_id, **fields)


async def get_run(run_id: str) -> tuple[Run, list[RunEvent]] | None:
    return await get_store().get_run(run_id)


async def get_run_state(run_id: str) -> dict | None:
    """The saved loop state of a waiting run (not part of the public Run shape)."""
    return await get_store().get_run_state(run_id)
