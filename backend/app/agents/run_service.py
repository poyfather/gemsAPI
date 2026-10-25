"""Run records: the `runs` and `run_events` tables. Tests replace these four functions with an in-memory store."""
from __future__ import annotations
from datetime import datetime, timezone

from app.database import get_supabase
from app.models import Run, RunEvent


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_run(gem_id: str | None, gem_name: str, model: str, provider: str, input_text: str) -> Run:
    db = get_supabase()
    row = {"gem_id": gem_id, "gem_name": gem_name, "model": model, "provider": provider, "input": input_text, "status": "running"}
    result = db.table("runs").insert(row).execute()
    return Run(**result.data[0])


async def add_event(run_id: str, seq: int, type_: str, data: dict) -> RunEvent:
    db = get_supabase()
    row = {"run_id": run_id, "seq": seq, "type": type_, "data": data}
    result = db.table("run_events").insert(row).execute()
    return RunEvent(**result.data[0])


async def finish_run(run_id: str, **fields) -> Run:
    db = get_supabase()
    fields.setdefault("finished_at", _now().isoformat())
    result = db.table("runs").update(fields).eq("id", run_id).execute()
    return Run(**result.data[0])


async def get_run(run_id: str) -> tuple[Run, list[RunEvent]] | None:
    db = get_supabase()
    result = db.table("runs").select("*").eq("id", run_id).limit(1).execute()
    if not result.data:
        return None
    events = db.table("run_events").select("*").eq("run_id", run_id).order("seq").execute()
    return Run(**result.data[0]), [RunEvent(**e) for e in events.data]
