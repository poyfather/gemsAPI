"""
OpenAI-compatible API (roadmap item 36): gems and agents as models.

Open WebUI and most desktop and editor clients speak the OpenAI chat
completions API. These two routes make every gem a model:

  GET  /v1/models            -> one model per active gem (id = gem name)
  POST /v1/chat/completions  -> the gem's resolved prompt as the system
                                prompt, the client's messages after it,
                                answered by the gem's provider and model

Prompt gems answer in one model call (streamed in OpenAI's chunk format
when asked). Agent gems run the loop (tools, approvals, run record) with
the conversation as context and return the final answer; while streaming,
tool calls appear as short status lines before the answer.
"""
from __future__ import annotations
import json
import time
import uuid
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.runner import run_agent
from app.auth import require_api_key
from app.models import RunEvent
from app.services import gem_service
from app.services.llm_service import complete, complete_stream

router = APIRouter(prefix="/v1", tags=["openai-compatible"], dependencies=[Depends(require_api_key)])


class OAIMessage(BaseModel):
    role: str
    content: Any = None   # string, or OpenAI's list of content parts


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="A gem name")
    messages: list[OAIMessage]
    stream: bool = False
    # Accepted and ignored, so strict clients do not fail validation.
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    user: Optional[str] = None


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")
    return "" if content is None else str(content)


def _split(messages: list[OAIMessage]) -> tuple[str, list[dict]]:
    """Client system messages become an addendum after the gem's prompt; the rest is the conversation."""
    system_parts, convo = [], []
    for m in messages:
        if m.role == "system":
            system_parts.append(_text(m.content))
        elif m.role in ("user", "assistant"):
            convo.append({"role": m.role, "content": _text(m.content)})
    return "\n\n".join(p for p in system_parts if p), convo


def _completion(model: str, text: str, finish: str = "stop") -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _chunk(cid: str, model: str, delta: dict, finish: str | None = None) -> str:
    body = {
        "id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(body)}\n\n"


@router.get("/models", summary="List gems as OpenAI-style models")
async def list_models():
    gems = await gem_service.get_all_gems()
    return {
        "object": "list",
        "data": [
            {
                "id": g.name, "object": "model", "created": int(g.created_at.timestamp()), "owned_by": "lapidary",
                "lapidary": {"kind": g.kind, "provider": g.provider, "model": g.model, "description": g.description, "tools": g.tools},
            }
            for g in gems
        ],
    }


@router.get("/models/{model_id}", summary="One gem as an OpenAI-style model")
async def get_model(model_id: str):
    g = await gem_service.get_gem_by_name(model_id)
    if not g:
        raise HTTPException(status_code=404, detail={"message": f"The model '{model_id}' does not exist", "type": "invalid_request_error"})
    return {"id": g.name, "object": "model", "created": int(g.created_at.timestamp()), "owned_by": "lapidary"}


@router.post("/chat/completions", summary="Chat with a gem through the OpenAI API shape")
async def chat_completions(request: ChatCompletionRequest):
    gem = await gem_service.get_gem_by_name(request.model)
    if not gem:
        raise HTTPException(status_code=404, detail={"message": f"The model '{request.model}' does not exist", "type": "invalid_request_error"})
    addendum, convo = _split(request.messages)
    if not convo or convo[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail={"message": "The last message must be from the user", "type": "invalid_request_error"})
    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"

    if gem.kind == "agent":
        history, last = convo[:-1], convo[-1]["content"]

        if not request.stream:
            try:
                result = await run_agent(gem.name, last, history=history, system_addendum=addendum)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail={"message": str(exc), "type": "invalid_request_error"})
            text = result.run.output or ""
            if result.run.status == "waiting_approval":
                text = (text + "\n\n" if text else "") + f"[Paused: this run is waiting for approval of a risky tool call. Run id {result.run.id}.]"
            return _completion(gem.name, text, "stop" if result.run.status in ("finished", "waiting_approval") else "length")

        async def agent_stream() -> AsyncGenerator[str, None]:
            yield _chunk(cid, gem.name, {"role": "assistant", "content": ""})
            final: dict[str, str] = {}

            async def on_event(event: RunEvent) -> None:
                pass

            # Collect events, then stream: tool activity as status lines, the answer last.
            try:
                result = await run_agent(gem.name, last, history=history, system_addendum=addendum, on_event=on_event)
            except ValueError as exc:
                yield _chunk(cid, gem.name, {"content": f"Error: {exc}"}, "stop")
                yield "data: [DONE]\n\n"
                return
            for e in result.events:
                if e.type == "tool_call":
                    yield _chunk(cid, gem.name, {"content": f"[tool: {e.data.get('name')}]\n"})
                elif e.type == "approval_requested":
                    yield _chunk(cid, gem.name, {"content": f"[paused: approval needed for {e.data.get('name')}, run {result.run.id}]\n"})
            final["text"] = result.run.output or ""
            if final["text"]:
                yield _chunk(cid, gem.name, {"content": ("\n" if any(e.type == "tool_call" for e in result.events) else "") + final["text"]})
            yield _chunk(cid, gem.name, {}, "stop")
            yield "data: [DONE]\n\n"

        return StreamingResponse(agent_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # Prompt gem: one model call with the resolved prompt (plus any client system text) in front.
    try:
        resolved = await gem_service.resolve_gem_detailed(gem.name, {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc), "type": "invalid_request_error"})
    system = resolved.resolved_prompt + (f"\n\n{addendum}" if addendum else "")

    if not request.stream:
        try:
            text = await complete(system, convo, gem.model, gem.provider, request.max_tokens)
        except Exception:
            raise HTTPException(status_code=502, detail={"message": "The LLM provider returned an error.", "type": "server_error"})
        return _completion(gem.name, text)

    async def prompt_stream() -> AsyncGenerator[str, None]:
        yield _chunk(cid, gem.name, {"role": "assistant", "content": ""})
        try:
            async for piece in complete_stream(system, convo, gem.model, gem.provider, request.max_tokens):
                yield _chunk(cid, gem.name, {"content": piece})
        except Exception:
            yield _chunk(cid, gem.name, {"content": "\n[The LLM provider returned an error.]"}, "stop")
            yield "data: [DONE]\n\n"
            return
        yield _chunk(cid, gem.name, {}, "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(prompt_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
