"""
The run loop (ADR-007), with approval gates (roadmap item 33).

run_agent() resolves the gem, calls the model with the gem's tools, executes
every tool call the model makes, feeds the results back, and repeats until
the model answers without tools or the step cap is reached. Every turn,
tool call and tool result is recorded as a run event and handed to the
optional on_event callback as it happens.

A call to a tool marked risky pauses the run unless it was started with
allow_risky: the conversation and the calls still to execute are saved on
the run (status waiting_approval), and resume_run() continues from that
exact point once someone approves or denies the call.
"""
from __future__ import annotations
import logging
from dataclasses import asdict, dataclass, field
from typing import Awaitable, Callable

from app import settings
from app.agents import run_service
from app.agents.mcp_sources import refresh_remote_tools
from app.agents.tools import Tool, call_tool, resolve_tools
from app.models import RunEvent, RunResult
from app.services import gem_service
from app.services.llm_service import ToolCall, complete_turn, tool_result_messages

logger = logging.getLogger(__name__)

OnEvent = Callable[[RunEvent], Awaitable[None]]


@dataclass
class LoopState:
    """Everything needed to continue a run later, stored on the run row while it waits."""
    gem_name: str
    system_prompt: str
    model: str
    provider: str
    tool_names: list[str]
    allow_risky: bool
    messages: list[dict]
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    last_text: str = ""
    seq: int = 0
    # Mid-turn: calls not executed yet, and results already collected for this turn.
    pending: list[dict] = field(default_factory=list)          # [{"id", "name", "input"}]
    results: list[dict] = field(default_factory=list)          # [{"id", "name", "input", "output", "is_error"}]

    @classmethod
    def from_dict(cls, data: dict) -> "LoopState":
        return cls(**data)


class _Paused(Exception):
    """Raised inside the loop to stop at a risky call; carries the call that needs a decision."""
    def __init__(self, call: ToolCall) -> None:
        super().__init__(call.name)
        self.call = call


class _Recorder:
    def __init__(self, run_id: str, seq: int, on_event: OnEvent | None) -> None:
        self.run_id, self.seq, self.on_event, self.events = run_id, seq, on_event, []

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


async def _execute(call: ToolCall, tools: dict[str, Tool]) -> tuple[str, bool]:
    """Run one tool call. Returns (output_for_the_model, is_error). Errors go back to the model, never up."""
    t = tools.get(call.name)
    if t is None:
        return f"Unknown tool '{call.name}'. Available: {', '.join(sorted(tools)) or 'none'}.", True
    try:
        return _truncate(await call_tool(t, call.input)), False
    except TypeError as exc:   # wrong or missing arguments
        return f"Bad arguments for '{call.name}': {exc}", True
    except Exception as exc:
        logger.exception("Tool %s failed", call.name)
        return f"Tool '{call.name}' failed: {type(exc).__name__}: {exc}", True


async def _process_calls(
    state: LoopState, tools: dict[str, Tool], rec: _Recorder,
    decided: tuple[str, bool] | None,
) -> None:
    """
    Execute state.pending in order, collecting into state.results, then append
    the turn's results to the conversation. `decided` is (call_id, approved)
    for the one call a person just ruled on. Raises _Paused at the first
    risky call that has no decision and no blanket allow_risky.
    """
    while state.pending:
        raw = state.pending[0]
        call = ToolCall(id=raw["id"], name=raw["name"], input=raw["input"])
        t = tools.get(call.name)
        if t is not None and t.risky and not state.allow_risky:
            if decided is None or decided[0] != call.id:
                raise _Paused(call)
            if not decided[1]:
                output, is_error = f"Tool '{call.name}' was denied by the user.", True
                await rec.emit("approval_decided", {"step": state.steps, "id": call.id, "name": call.name, "approved": False})
                state.results.append({"id": call.id, "name": call.name, "input": call.input, "output": output, "is_error": is_error})
                await rec.emit("tool_result", {"step": state.steps, "id": call.id, "name": call.name, "output": output, "is_error": True})
                state.pending.pop(0)
                decided = None
                continue
            await rec.emit("approval_decided", {"step": state.steps, "id": call.id, "name": call.name, "approved": True})
            decided = None
        await rec.emit("tool_call", {"step": state.steps, "id": call.id, "name": call.name, "input": call.input})
        output, is_error = await _execute(call, tools)
        await rec.emit("tool_result", {"step": state.steps, "id": call.id, "name": call.name, "output": output, "is_error": is_error})
        state.results.append({"id": call.id, "name": call.name, "input": call.input, "output": output, "is_error": is_error})
        state.pending.pop(0)

    if state.results:
        results = [(ToolCall(id=r["id"], name=r["name"], input=r["input"]), r["output"], r["is_error"]) for r in state.results]
        state.messages.extend(tool_result_messages(state.provider, results))
        state.results = []


async def _loop(run_id: str, state: LoopState, rec: _Recorder, decided: tuple[str, bool] | None) -> RunResult:
    tools_found, _ = resolve_tools(state.tool_names)
    tools = {t.name: t for t in tools_found}
    neutral_tools = [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools_found]
    status = "max_steps"
    try:
        # Finish a turn that was interrupted by an approval, if any.
        await _process_calls(state, tools, rec, decided)
        while state.steps < settings.AGENT_MAX_STEPS:
            state.steps += 1
            turn = await complete_turn(state.system_prompt, state.messages, state.model, state.provider, neutral_tools)
            state.input_tokens += turn.input_tokens
            state.output_tokens += turn.output_tokens
            state.last_text = turn.text or state.last_text
            await rec.emit("model_turn", {
                "step": state.steps, "text": turn.text, "stop_reason": turn.stop_reason,
                "tool_calls": [{"id": c.id, "name": c.name, "input": c.input} for c in turn.tool_calls],
                "input_tokens": turn.input_tokens, "output_tokens": turn.output_tokens,
            })
            state.messages.append(turn.assistant_message)
            if not turn.tool_calls:
                status = "finished"
                break
            state.pending = [{"id": c.id, "name": c.name, "input": c.input} for c in turn.tool_calls]
            await _process_calls(state, tools, rec, None)
    except _Paused as paused:
        await rec.emit("approval_requested", {
            "step": state.steps, "id": paused.call.id, "name": paused.call.name, "input": paused.call.input,
        })
        state.seq = rec.seq
        run = await run_service.update_run(
            run_id, status="waiting_approval", steps=state.steps,
            input_tokens=state.input_tokens, output_tokens=state.output_tokens,
            output=state.last_text or None, state=asdict(state),
        )
        return RunResult(run=run, events=rec.events)
    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        await rec.emit("run_failed", {"step": state.steps, "error": type(exc).__name__})
        run = await run_service.finish_run(
            run_id, status="failed", steps=state.steps, input_tokens=state.input_tokens,
            output_tokens=state.output_tokens, error=f"{type(exc).__name__}: {exc}"[:500],
            output=state.last_text or None, state=None,
        )
        return RunResult(run=run, events=rec.events)

    await rec.emit("run_finished", {
        "run_id": run_id, "status": status, "steps": state.steps,
        "input_tokens": state.input_tokens, "output_tokens": state.output_tokens,
    })
    run = await run_service.finish_run(
        run_id, status=status, steps=state.steps, input_tokens=state.input_tokens,
        output_tokens=state.output_tokens, output=state.last_text, state=None,
    )
    return RunResult(run=run, events=rec.events)


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
    if any("." in n or n.endswith("*") for n in gem.tools):
        await refresh_remote_tools()
    tools, unknown = resolve_tools(gem.tools)

    run = await run_service.create_run(gem.id, gem.name, model, provider, message)
    rec = _Recorder(run.id, 0, on_event)
    await rec.emit("run_started", {
        "run_id": run.id, "gem": gem.name, "kind": gem.kind, "model": model, "provider": provider,
        "tools": [t.name for t in tools], "unknown_tools": unknown, "allow_risky": allow_risky,
        "variables_missing": resolved.variables_missing, "max_steps": settings.AGENT_MAX_STEPS,
    })
    state = LoopState(
        gem_name=gem.name, system_prompt=resolved.resolved_prompt, model=model, provider=provider,
        tool_names=[t.name for t in tools], allow_risky=allow_risky,
        messages=[{"role": "user", "content": message}],
    )
    return await _loop(run.id, state, rec, None)


async def resume_run(run_id: str, approve: bool, *, on_event: OnEvent | None = None) -> RunResult:
    """
    Continue a run that is waiting for a decision on a risky tool call.
    Raises LookupError if the run does not exist and ValueError if it is not waiting.
    """
    found = await run_service.get_run(run_id)
    if found is None:
        raise LookupError(f"Run '{run_id}' not found.")
    run, _ = found
    if run.status != "waiting_approval":
        raise ValueError(f"Run '{run_id}' is {run.status}, not waiting for approval.")
    raw = await run_service.get_run_state(run_id)
    if not raw or not raw.get("pending"):
        raise ValueError(f"Run '{run_id}' has no pending tool call to decide on.")
    state = LoopState.from_dict(raw)
    if any("." in n for n in state.tool_names):
        await refresh_remote_tools()
    pending_call_id = state.pending[0]["id"]
    rec = _Recorder(run_id, state.seq, on_event)
    await run_service.update_run(run_id, status="running")
    return await _loop(run_id, state, rec, (pending_call_id, approve))
