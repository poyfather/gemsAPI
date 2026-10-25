"""Pipelines and gates over REST (ADR-011): define, run, read, resume."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.agents.pipeline import resume_pipeline, run_pipeline
from app.auth import require_api_key
from app.models import Pipeline, PipelineCreate, PipelineResult, PipelineResumeRequest, PipelineRun, PipelineRunRequest, PipelineUpdate
from app.routes.agents import _stream
from app.storage import get_store

router = APIRouter(prefix="/pipelines", tags=["pipelines"], dependencies=[Depends(require_api_key)])


@router.get("/", response_model=list[Pipeline], summary="List pipelines")
async def list_pipelines():
    return await get_store().list_pipelines()


@router.post("/", response_model=Pipeline, status_code=201, summary="Create a pipeline")
async def create_pipeline(data: PipelineCreate):
    """A builder gem, then gate gems with roles; gates answer with findings and a VERDICT line."""
    if await get_store().get_pipeline(data.name):
        raise HTTPException(status_code=400, detail=f"A pipeline named '{data.name}' already exists.")
    return await get_store().create_pipeline(data)


@router.get("/runs/{run_id}", response_model=PipelineRun, summary="Read a pipeline run")
async def get_pipeline_run(run_id: str):
    run = await get_store().get_pipeline_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found.")
    return run


@router.post("/runs/{run_id}/resume", summary="Continue a paused pipeline run")
async def resume(run_id: str, request: PipelineResumeRequest):
    """
    For status waiting_approval: approve or deny the agent run named by waiting_run_id first
    (POST /runs/{id}/approve), then call this. For status waiting_acceptance: pass accept=true
    to finish, or accept=false with a note to send it back to the builder.
    """
    kwargs = dict(accept=request.accept, note=request.note)
    if not request.stream:
        try:
            return await resume_pipeline(run_id, **kwargs)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
    return _stream(lambda on_event: resume_pipeline(run_id, on_event=on_event, **kwargs))


@router.get("/{name}", response_model=Pipeline, summary="Read a pipeline")
async def get_pipeline(name: str):
    p = await get_store().get_pipeline(name)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found.")
    return p


@router.put("/{name}", response_model=Pipeline, summary="Update a pipeline")
async def update_pipeline(name: str, data: PipelineUpdate):
    if await get_store().get_pipeline(name) is None:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found.")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    return await get_store().update_pipeline(name, updates)


@router.delete("/{name}", status_code=204, summary="Delete a pipeline")
async def delete_pipeline(name: str):
    if not await get_store().delete_pipeline(name):
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found.")


@router.post("/{name}/runs", summary="Run a pipeline")
async def start_pipeline_run(name: str, request: PipelineRunRequest):
    """
    The builder runs on the message; each gate checks its output; a failed gate's findings go
    back to the builder, up to max_attempts; when every gate passes the run waits for acceptance
    (if the pipeline asks for it) or finishes as passed. With stream=true the pipeline's events
    arrive as Server-Sent Events; the agent runs themselves are at /runs/{id}.
    """
    kwargs = dict(variables=request.variables, allow_risky=request.allow_risky, memory_scope=request.memory_scope)
    if not request.stream:
        try:
            return await run_pipeline(name, request.message, **kwargs)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
    return _stream(lambda on_event: run_pipeline(name, request.message, on_event=on_event, **kwargs))


__all__ = ["router", "PipelineResult"]
