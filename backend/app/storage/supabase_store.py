"""The hosted backend: Supabase Postgres through supabase-py, service role key only (ADR-006)."""
from __future__ import annotations
from datetime import datetime, timezone

from app.database import get_supabase
from app.models import Gem, GemCreate, GemVersion, Memory, MemoryCreate, Pipeline, PipelineCreate, PipelineRun, Run, RunEvent


class SupabaseStore:
    # ---- gems
    async def list_gems(self) -> list[Gem]:
        result = get_supabase().table("gems").select("*").eq("is_active", True).order("name").execute()
        return [Gem(**r) for r in result.data]

    async def get_gem_by_name(self, name: str) -> Gem | None:
        result = get_supabase().table("gems").select("*").eq("name", name).eq("is_active", True).limit(1).execute()
        return Gem(**result.data[0]) if result.data else None

    async def get_gem_by_id(self, gem_id: str) -> Gem | None:
        result = get_supabase().table("gems").select("*").eq("id", gem_id).limit(1).execute()
        return Gem(**result.data[0]) if result.data else None

    async def create_gem(self, data: GemCreate, variables: list[str]) -> Gem:
        row = {**data.model_dump(), "variables": variables}
        result = get_supabase().table("gems").insert(row).execute()
        return Gem(**result.data[0])

    async def update_gem(self, gem_id: str, updates: dict) -> Gem:
        result = get_supabase().table("gems").update(updates).eq("id", gem_id).execute()
        return Gem(**result.data[0])

    async def soft_delete_gem(self, gem_id: str) -> None:
        get_supabase().table("gems").update({"is_active": False}).eq("id", gem_id).execute()

    # ---- gem versions (roadmap 14)
    async def add_gem_version(self, gem_id, version, snapshot, note, source) -> GemVersion:
        row = {"gem_id": gem_id, "version": version, "snapshot": snapshot, "note": note or "", "source": source}
        result = get_supabase().table("gem_versions").insert(row).execute()
        return GemVersion(**result.data[0])

    async def list_gem_versions(self, gem_id) -> list[GemVersion]:
        result = get_supabase().table("gem_versions").select("gem_id, version, snapshot, note, source, created_at").eq("gem_id", gem_id).order("version").execute()
        return [GemVersion(**r) for r in result.data]

    # ---- runs
    async def create_run(self, gem_id, gem_name, model, provider, input_text) -> Run:
        row = {"gem_id": gem_id, "gem_name": gem_name, "model": model, "provider": provider, "input": input_text, "status": "running"}
        result = get_supabase().table("runs").insert(row).execute()
        return Run(**result.data[0])

    async def add_event(self, run_id, seq, type_, data) -> RunEvent:
        result = get_supabase().table("run_events").insert({"run_id": run_id, "seq": seq, "type": type_, "data": data}).execute()
        return RunEvent(**result.data[0])

    async def update_run(self, run_id, **fields) -> Run:
        result = get_supabase().table("runs").update(fields).eq("id", run_id).execute()
        return Run(**result.data[0])

    async def get_run(self, run_id):
        db = get_supabase()
        result = db.table("runs").select("*").eq("id", run_id).limit(1).execute()
        if not result.data:
            return None
        events = db.table("run_events").select("*").eq("run_id", run_id).order("seq").execute()
        return Run(**result.data[0]), [RunEvent(**e) for e in events.data]

    async def get_run_state(self, run_id):
        result = get_supabase().table("runs").select("state").eq("id", run_id).limit(1).execute()
        return result.data[0].get("state") if result.data else None


    # ---- memory (ADR-010)
    async def add_memory(self, data: MemoryCreate) -> Memory:
        result = get_supabase().table("memories").insert(data.model_dump()).execute()
        return Memory(**result.data[0])

    async def search_memories(self, query: str, *, scope: str | None = None, kinds: list[str] | None = None, limit: int = 20) -> list[Memory]:
        q = get_supabase().table("memories").select("id, kind, text, source, gem_name, run_id, tags, scope, created_at")
        if scope:
            q = q.eq("scope", scope)
        if kinds:
            q = q.in_("kind", kinds)
        if query and query.strip():
            q = q.text_search("search", query.strip(), options={"config": "english", "type": "websearch"})
        result = q.order("created_at", desc=True).limit(limit).execute()
        return [Memory(**r) for r in result.data]

    async def get_memories(self, ids: list[str]) -> list[Memory]:
        if not ids:
            return []
        result = get_supabase().table("memories").select("id, kind, text, source, gem_name, run_id, tags, scope, created_at").in_("id", ids).execute()
        by_id = {r["id"]: Memory(**r) for r in result.data}
        return [by_id[i] for i in ids if i in by_id]

    async def delete_memory(self, memory_id: str) -> bool:
        result = get_supabase().table("memories").delete().eq("id", memory_id).execute()
        return bool(result.data)


    # ---- pipelines (ADR-011)
    async def list_pipelines(self) -> list[Pipeline]:
        result = get_supabase().table("pipelines").select("*").order("name").execute()
        return [Pipeline(**r) for r in result.data]

    async def get_pipeline(self, name: str) -> Pipeline | None:
        result = get_supabase().table("pipelines").select("*").eq("name", name).limit(1).execute()
        return Pipeline(**result.data[0]) if result.data else None

    async def create_pipeline(self, data: PipelineCreate) -> Pipeline:
        result = get_supabase().table("pipelines").insert(data.model_dump()).execute()
        return Pipeline(**result.data[0])

    async def update_pipeline(self, name: str, updates: dict) -> Pipeline:
        result = get_supabase().table("pipelines").update(updates).eq("name", name).execute()
        return Pipeline(**result.data[0])

    async def delete_pipeline(self, name: str) -> bool:
        result = get_supabase().table("pipelines").delete().eq("name", name).execute()
        return bool(result.data)

    async def create_pipeline_run(self, pipeline_name: str, input_text: str) -> PipelineRun:
        result = get_supabase().table("pipeline_runs").insert({"pipeline_name": pipeline_name, "input": input_text, "status": "running"}).execute()
        return PipelineRun(**result.data[0])

    async def update_pipeline_run(self, run_id: str, **fields) -> PipelineRun:
        result = get_supabase().table("pipeline_runs").update(fields).eq("id", run_id).execute()
        return PipelineRun(**result.data[0])

    async def get_pipeline_run(self, run_id: str) -> PipelineRun | None:
        result = get_supabase().table("pipeline_runs").select("*").eq("id", run_id).limit(1).execute()
        return PipelineRun(**result.data[0]) if result.data else None

    async def get_pipeline_run_state(self, run_id: str) -> dict | None:
        result = get_supabase().table("pipeline_runs").select("state").eq("id", run_id).limit(1).execute()
        return result.data[0].get("state") if result.data else None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
