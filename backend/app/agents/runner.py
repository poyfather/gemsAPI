"""
The run loop (ADR-007).

run_agent() resolves the gem, calls the model with the gem's tools, executes
every tool call the model makes, feeds the results back, and repeats until
the model answers without tools or the step cap is reached. Every turn,
tool call and tool result is recorded as a run event and handed to the
optional on_event callback as it happens (the SSE route uses that).
"""
from __future__ import annotations
import logging
from typing import Awaitable, Callable

from app import settings
from app.agents import run_service
from app.agents.tools import Tool, call_tool, resolve_tools
from app.models import RunEvent, RunResult
from app.services import gem_service
from app.services.llm_service import ToolCall, complete_turn, tool_result_messages

logger = logging.getLogger(__name__)

OnEvent = Callable[[RunEvent], Awaitable[None]]


class _Recorder:
    def __init__(self, run_id: str, on_event: OnEvent | None) -> None:
        self.run_id, self.on_event, self.seq, self.events = run_id, on_event, 0, []

    async def emit(self, type_: str, data: dict) -> RunEvent:
        self.seq += 1
        event = await run_service.add_event(self.run_id, self.seq, type_, data)
        self.events.append(event)
        if self.on_event:
            await self.on_event(event)
        return event


def _truncate(text: str) -> str:
    limit = settings.AGENT_TOOL_RESULT_MAX_CHARS
    return text if len(text) <= limit else text[:limit] + f"\n[truncated, {len(text) - limit} more characters]"


async def _execute(call: ToolCall, tools: dict[str, Tool], allow_risky: bool) -> tuple[str, bool]:
    """Run one tool call. Returns (output_for_the_model, is_error). Errors go back to the model, never up."""
    t = tools.get(call.name)
    if t is None:
        return f"Unknown tool '{call.name}'. Available: {', '.join(sorted(tools)) or 'none'}.", True
    if t.risky and not allow_risky:
        return f"Tool '{call.name}' is marked risky and this run was not started with allow_risky.", True
    try:
        return _truncate(await call_tool(t, call.input)), False
    except TypeError as exc:   # wrong or missing arguments
        return f"Bad arguments for '{call.name}': {exc}", True
    except Exception as exc:
        logger.exception("Tool %s failed", call.name)
        return f"Tool '{call.name}' failed: {type(exc).__name__}: {exc}", True


async def run_agent(
    gem_name: str,
    message: str,
    variables: dict[str, str] | None = None,
    *,
    model_override: str | None = None,
    provider_override: str | None = None,
    allow_risky: bool = False,
    on_event: OnEvent | None = None,
) -> RunResult:
    """Run a gem as an agent. Raises ValueError if the gem cannot be resolved; provider errors fail the run."""
    resolved = await gem_service.resolve_gem_detailed(gem_name, variables or {})
    gem = await gem_service.get_gem_by_name(gem_name)
    if gem is None:
        raise ValueError(f"Gem '{gem_name}' not found or is inactive.")
    model = model_override or gem.model
    provider = provider_override or gem.provider
    tools, unknown = resolve_tools(gem.tools)
    tool_map = {t.name: t for t in tools}
    neutral_tools = [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools]

    run = await run_service.create_run(gem.id, gem.name, model, provider, message)
    rec = _Recorder(run.id, on_event)
    await rec.emit("run_started", {
        "run_id": run.id, "gem": gem.name, "kind": gem.kind, "model": model, "provider": provider,
        "tools": [t.name for t in tools], "unknown_tools": unknown,
        "variables_missing": resolved.variables_missing, "max_steps": settings.AGENT_MAX_STEPS,
    })

    messages: list[dict] = [{"role": "user", "content": message}]
    steps = in_tok = out_tok = 0
    last_text = ""
    status = "max_steps"
    try:
        while steps < settings.AGENT_MAX_STEPS:
            steps += 1
            turn = await complete_turn(resolved.resolved_prompt, messages, model, provider, neutral_tools)
            in_tok += turn.input_tokens
            out_tok += turn.output_tokens
            last_text = turn.text or last_text
            await rec.emit("model_turn", {
                "step": steps, "text": turn.text, "stop_reason": turn.stop_reason,
                "tool_calls": [{"id": c.id, "name": c.name, "input": c.input} for c in turn.tool_calls],
                "input_tokens": turn.input_tokens, "output_tokens": turn.output_tokens,
            })
            messages.append(turn.assistant_message)
            if not turn.tool_calls:
                status = "finished"
                break
            results = []
            for call in turn.tool_calls:
                await rec.emit("tool_call", {"step": steps, "id": call.id, "name": call.name, "input": call.input})
                output, is_error = await _execute(call, tool_map, allow_risky)
                await rec.emit("tool_result", {"step": steps, "id": call.id, "name": call.name, "output": output, "is_error": is_error})
                results.append((call, output, is_error))
            messages.extend(tool_result_messages(provider, results))
    except Exception as exc:
        logger.exception("Run %s failed", run.id)
        await rec.emit("run_failed", {"step": steps, "error": type(exc).__name__})
        run = await run_service.finish_run(run.id, status="failed", steps=steps, input_tokens=in_tok, output_tokens=out_tok,
                                           error=f"{type(exc).__name__}: {exc}"[:500], output=last_text or None)
        return RunResult(run=run, events=rec.events)

    await rec.emit("run_finished", {"run_id": run.id, "status": status, "steps": steps, "input_tokens": in_tok, "output_tokens": out_tok})
    run = await run_service.finish_run(run.id, status=status, steps=steps, input_tokens=in_tok, output_tokens=out_tok, output=last_text)
    return RunResult(run=run, events=rec.events)
