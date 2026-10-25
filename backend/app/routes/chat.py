import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.models import ChatRequest, ChatResponse
from app.services import gem_service, memory_service
from app.services import router as model_router
from app.services.llm_service import available_models, complete, complete_stream
from app.auth import require_api_key

logger = logging.getLogger(__name__)

_PROVIDER_ERROR = "The LLM provider returned an error. Check the server log for details."

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_api_key)])


@router.get("/policy", summary="The model policy: which AI we use, and what is available")
async def policy():
    """Answers \"Which AI should we use?\" for the UI: the policy, which providers are usable, and the defaults it would pick."""
    return await model_router.describe()


@router.get("/models", summary="List available models")
async def list_models():
    """Return the models each provider currently offers (live list, cached; see llm_service.available_models)."""
    return await available_models()


@router.post("/", summary="Chat with a gem")
async def chat(request: ChatRequest):
    """
    Send a conversation to an LLM using a gem as the system prompt.
    The gem is resolved first (variables filled, {{gem:}} refs expanded).
    Set stream=true to receive a Server-Sent Events stream.
    """
    # Resolve gem
    try:
        resolved_prompt, _ = await gem_service.resolve_gem(request.gem_name, request.variables)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Get defaults from gem
    gem = await gem_service.get_gem_by_name(request.gem_name)
    if gem.memory and request.messages:
        last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
        block = await memory_service.recall_block(last_user, scope=request.memory_scope)
        if block:
            resolved_prompt += "\n\n" + block
    choice = await model_router.choose(gem, provider_override=request.provider_override, model_override=request.model_override)
    model, provider = choice.model, choice.provider

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Streaming response
    if request.stream:
        async def sse_generator():
            try:
                async for chunk in complete_stream(resolved_prompt, messages, model, provider):
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            except Exception:
                logger.exception("Streaming chat failed for gem %s", request.gem_name)
                yield f"data: {json.dumps({'error': _PROVIDER_ERROR})}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Non-streaming response
    try:
        content = await complete(resolved_prompt, messages, model, provider)
    except Exception:
        logger.exception("Chat failed for gem %s", request.gem_name)
        raise HTTPException(status_code=502, detail=_PROVIDER_ERROR)

    return ChatResponse(content=content, model=model, provider=provider, gem_name=request.gem_name, reason=choice.reason)
