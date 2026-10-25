"""Lapidary Memory over REST (ADR-010): search, read, write and forget."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_api_key
from app.models import Memory, MemoryCreate, MemoryIndexEntry
from app.services import memory_service

router = APIRouter(prefix="/memory", tags=["memory"], dependencies=[Depends(require_api_key)])


@router.get("/", response_model=list[Memory], summary="List or search memories")
async def list_memories(
    q: str = Query(default="", description="Words to look for; empty lists the newest"),
    scope: str = Query(default="default"),
    kind: list[str] | None = Query(default=None, description="observation, summary, decision, preference, lesson, handoff, note"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Full records, newest first or ranked by match. The web UI's Memory page reads this."""
    return await memory_service.search(q, scope=scope or None, kinds=kind, limit=limit)


@router.get("/search", response_model=list[MemoryIndexEntry], summary="Search memory: the compact index")
async def search_memory(q: str = Query(default=""), scope: str = Query(default="default"), limit: int = Query(default=10, ge=1, le=100)):
    """Step one of recall: ids, kinds, dates and one line each. Fetch the ones that matter with GET /memory/{id}."""
    return await memory_service.search_index(q, scope=scope or None, limit=limit)


@router.post("/", response_model=Memory, status_code=201, summary="Remember something")
async def remember(data: MemoryCreate):
    """Store a note, decision, preference, lesson or handoff. Text inside <private>...</private> is dropped."""
    try:
        memory = await memory_service.remember(data.text, kind=data.kind, tags=data.tags, scope=data.scope, source=data.source,
                                               gem_name=data.gem_name, run_id=data.run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if memory is None:
        raise HTTPException(status_code=400, detail="Nothing to remember once <private> text is removed.")
    return memory


@router.get("/{memory_id}", response_model=Memory, summary="Read one memory")
async def get_memory(memory_id: str):
    found = await memory_service.get([memory_id])
    if not found:
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found.")
    return found[0]


@router.delete("/{memory_id}", status_code=204, summary="Forget one memory")
async def forget(memory_id: str):
    if not await memory_service.forget(memory_id):
        raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found.")
