"""Agent runs: start one (JSON or SSE), read one back, list the registered tools."""
from __future__ import annotations
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

import app.agents.builtin  # noqa: F401  (registers the built-in tools)
from app.agents import run_service
from app.agents.runner import run_agent
from app.agents.tools import all_tools
from app.auth import require_api_key
from app.models import RunEvent, RunRequest, RunResult, ToolInfo

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(require_api_key)])
runs_router = APIRouter(prefix="/runs", tags=["agents"], dependencies=[Depends(require_api_key)])


@router.get("/tools", response_model=list[ToolInfo], summary="List the tools an agent gem may use")
async def list_tools():
    return [t.info() for t in all_tools()]


@router.post("/{gem_name}/runs", summary="Run a gem as an agent")
async def start_run(gem_name: str, request: RunRequest):
    """
    Resolve the gem, then loop: model turn, execute any tool calls, feed results back,
    until the model answers without tools or AGENT_MAX_STEPS is reached.
    With stream=true the run's events arrive as Server-Sent Events as they happen,
    ending with a `run_finished` or `run_failed` event; otherwise the whole result is returned.
    """
    kwargs = dict(
        variables=request.variables, model_override=request.model_override,
        provider_override=request.provider_override, allow_risky=request.allow_risky,
    )
    if not request.stream:
        try:
            return await run_agent(gem_name, request.message, **kwargs)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    queue: asyncio.Queue[RunEvent | Exception | None] = asyncio.Queue()

    async def on_event(event: RunEvent) -> None:
        await queue.put(event)

    async def produce() -> None:
        try:
            await run_agent(gem_name, request.message, on_event=on_event, **kwargs)
        except Exception as exc:  # the loop reports provider failures as events; this catches resolution errors
            await queue.put(exc)
        finally:
            await queue.put(None)

    async def sse():
        task = asyncio.create_task(produce())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    yield f"event: error\ndata: {json.dumps({'error': str(item)})}\n\n"
                    break
                yield f"event: {item.type}\ndata: {item.model_dump_json()}\n\n"
        finally:
            await task
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@runs_router.get("/{run_id}", response_model=RunResult, summary="Read a run and its events")
async def get_run(run_id: str):
    found = await run_service.get_run(run_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    run, events = found
    return RunResult(run=run, events=events)
