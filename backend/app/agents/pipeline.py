"""
Pipelines and gates (ADR-011, roadmap 45), modelled on Ratchet Loop: never let a
model decide it is done.

A pipeline is a builder gem followed by gate gems with roles (test, visual,
review, custom). The builder runs first; each gate gets the task and the
builder's output and must end its answer with VERDICT: PASS or VERDICT: FAIL,
findings first. A failure goes back to the builder as findings and the pipeline
tries again, up to max_attempts. When every gate passed and the pipeline asks
for acceptance, it pauses for a person. Every attempt and gate is an ordinary
agent run, so the record shows what failed and why, and a failed gate's
findings become a memory lesson.

A run that pauses for approval of a risky tool call pauses the pipeline too
(status waiting_approval, waiting_run_id); approve or deny that run, then
resume the pipeline.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timezone
from typing import Awaitable, Callable

from app.agents.runner import run_agent
from app.agents import run_service
from app.models import Attempt, GateResult, Pipeline, PipelineResult, PipelineRun, Run, RunEvent
from app.services import memory_service
from app.storage import get_store

logger = logging.getLogger(__name__)
OnEvent = Callable[[RunEvent], Awaitable[None]]
_VERDICT = re.compile(r"VERDICT\s*:\s*(PASS|FAIL)\b", re.IGNORECASE)


def _store():
    return get_store()


def parse_verdict(text: str | None) -> tuple[str, str]:
    """The last VERDICT line wins; everything before it is the findings. No verdict is a fail."""
    if not text:
        return "fail", "The gate gave no answer."
    matches = list(_VERDICT.finditer(text))
    if not matches:
        return "fail", text.strip()[:4000] + "\n(no VERDICT line, so treated as a fail)"
    m = matches[-1]
    findings = (text[: m.start()] + text[m.end():]).strip()
    return m.group(1).lower(), findings[:4000]


def gate_message(task: str, output: str | None, attempt: int, role: str, instructions: str) -> str:
    return (
        f"Task given to the builder:\n<task>\n{task}\n</task>\n\n"
        f"What the builder produced (attempt {attempt}):\n<output>\n{output or '(no output)'}\n</output>\n\n"
        f"You are the {role} gate. Do the work this takes (run tests, inspect, try to break it, review), "
        "write your findings, then end your answer with one line on its own: VERDICT: PASS or VERDICT: FAIL. "
        "Fail when anything the task asked for is missing, wrong or untested."
        + (f"\n\n{instructions}" if instructions else "")
    )


def builder_message(task: str, feedback: str, attempt: int, max_attempts: int) -> str:
    if not feedback:
        return task
    return f"{task}\n\nA previous attempt was checked and failed. Findings:\n{feedback}\n\nFix these and try again (attempt {attempt} of {max_attempts})."


class _Emitter:
    def __init__(self, run_id: str, seq: int, on_event: OnEvent | None) -> None:
        self.run_id, self.seq, self.on_event, self.events = run_id, seq, on_event, []

    async def emit(self, type_: str, data: dict) -> None:
        self.seq += 1
        ev = RunEvent(seq=self.seq, type=type_, data=data, created_at=datetime.now(timezone.utc))
        self.events.append(ev)
        if self.on_event:
            await self.on_event(ev)


async def _save(run_id: str, attempts: list[Attempt], **fields) -> PipelineRun:
    return await _store().update_pipeline_run(run_id, attempts=[a.model_dump() for a in attempts], **fields)


async def _run_gem(gem: str, message: str, *, variables, allow_risky, memory_scope, provider_override=None, model_override=None) -> Run:
    result = await run_agent(gem, message, variables, provider_override=provider_override, model_override=model_override,
                             allow_risky=allow_risky, memory_scope=memory_scope)
    return result.run


async def run_pipeline(name: str, message: str, variables: dict[str, str] | None = None, *, allow_risky: bool = False,
                       on_event: OnEvent | None = None, memory_scope: str = "default") -> PipelineResult:
    """Start a pipeline. Raises ValueError when the pipeline or its builder does not exist."""
    pipeline = await _store().get_pipeline(name)
    if pipeline is None:
        raise ValueError(f"Pipeline '{name}' not found.")
    prun = await _store().create_pipeline_run(pipeline.name, message)
    em = _Emitter(prun.id, 0, on_event)
    await em.emit("pipeline_started", {"pipeline_run_id": prun.id, "pipeline": pipeline.name, "builder": pipeline.builder,
                                       "gates": [g.model_dump() for g in pipeline.gates], "max_attempts": pipeline.max_attempts, "acceptance": pipeline.acceptance})
    state = {"attempt": 0, "gate_index": 0, "phase": "builder", "feedback": "", "variables": variables or {},
             "allow_risky": allow_risky, "memory_scope": memory_scope, "seq": 0}
    return await _drive(pipeline, prun, [], state, em)


async def resume_pipeline(run_id: str, *, accept: bool | None = None, note: str = "", on_event: OnEvent | None = None) -> PipelineResult:
    """
    Continue a paused pipeline: after the agent run it waited on was approved or denied
    (status waiting_approval), or with a decision (status waiting_acceptance).
    Raises LookupError when the run does not exist and ValueError when it is not waiting.
    """
    prun = await _store().get_pipeline_run(run_id)
    if prun is None:
        raise LookupError(f"Pipeline run '{run_id}' not found.")
    if prun.status not in ("waiting_approval", "waiting_acceptance"):
        raise ValueError(f"Pipeline run '{run_id}' is {prun.status}, not waiting.")
    pipeline = await _store().get_pipeline(prun.pipeline_name)
    if pipeline is None:
        raise ValueError(f"Pipeline '{prun.pipeline_name}' no longer exists.")
    state = await _store().get_pipeline_run_state(run_id) or {}
    attempts = [a if isinstance(a, Attempt) else Attempt(**a) for a in prun.attempts]
    em = _Emitter(prun.id, int(state.get("seq", 0)), on_event)
    if prun.status == "waiting_acceptance":
        if accept is None:
            raise ValueError("This pipeline run is waiting for your decision: pass accept=true or accept=false.")
        if accept:
            await em.emit("pipeline_accepted", {"attempt": attempts[-1].number if attempts else 0})
            run = await _save(prun.id, attempts, status="passed", state=None, waiting_run_id=None, finished_at=_now())
            await em.emit("pipeline_finished", {"status": "passed", "attempts": len(attempts)})
            return PipelineResult(run=run, events=em.events)
        state["feedback"] = f"Rejected by the person who checked it: {note or 'no reason given'}"
        state["phase"] = "builder"
        await em.emit("pipeline_rejected", {"attempt": attempts[-1].number if attempts else 0, "note": note})
        await memory_service.remember(f"{pipeline.name}: a result was rejected at acceptance. {note}".strip(), kind="lesson", scope=state.get("memory_scope", "default"),
                                      source="run", gem_name=pipeline.builder, run_id=attempts[-1].builder_run_id if attempts else None)
        return await _drive(pipeline, prun, attempts, state, em)
    # waiting_approval: the agent run must have moved on
    found = await run_service.get_run(prun.waiting_run_id or "")
    if found is None or found[0].status in ("running", "waiting_approval"):
        raise ValueError(f"Agent run '{prun.waiting_run_id}' is still waiting; approve or deny it first (POST /runs/{{id}}/approve).")
    state["resumed_run"] = found[0].model_dump(mode="json")
    await _store().update_pipeline_run(prun.id, status="running", waiting_run_id=None)
    return await _drive(pipeline, prun, attempts, state, em)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _pause(prun_id: str, attempts: list[Attempt], state: dict, em: _Emitter, run_id: str, phase: str) -> PipelineResult:
    state["phase"] = phase
    state["seq"] = em.seq
    await em.emit("pipeline_paused", {"status": "waiting_approval", "run_id": run_id, "phase": phase})
    run = await _save(prun_id, attempts, status="waiting_approval", waiting_run_id=run_id, state=state)
    return PipelineResult(run=run, events=em.events)


async def _drive(pipeline: Pipeline, prun: PipelineRun, attempts: list[Attempt], state: dict, em: _Emitter) -> PipelineResult:
    """The loop, written so it can be entered fresh or after a pause."""
    task = prun.input
    kw = dict(variables=state.get("variables") or {}, allow_risky=bool(state.get("allow_risky")), memory_scope=state.get("memory_scope", "default"))
    resumed: dict | None = state.pop("resumed_run", None)
    try:
        while True:
            # ---- builder
            if state["phase"] == "builder":
                if resumed is None:
                    state["attempt"] += 1
                    if state["attempt"] > pipeline.max_attempts:
                        run = await _save(prun.id, attempts, status="max_attempts", state=None, finished_at=_now(),
                                          output=attempts[-1].output if attempts else None)
                        await em.emit("pipeline_finished", {"status": "max_attempts", "attempts": len(attempts)})
                        return PipelineResult(run=run, events=em.events)
                    attempt = Attempt(number=state["attempt"], feedback=state.get("feedback", ""))
                    attempts.append(attempt)
                    await em.emit("attempt_started", {"attempt": attempt.number, "feedback": attempt.feedback})
                    await _save(prun.id, attempts, state=state)
                    brun = await _run_gem(pipeline.builder, builder_message(task, attempt.feedback, attempt.number, pipeline.max_attempts), **kw)
                else:
                    attempt = attempts[-1]
                    brun = Run(**resumed)
                    resumed = None
                attempt.builder_run_id, attempt.builder_status, attempt.output = brun.id, brun.status, brun.output
                if brun.status == "waiting_approval":
                    return await _pause(prun.id, attempts, state, em, brun.id, "builder")
                await em.emit("builder_finished", {"attempt": attempt.number, "run_id": brun.id, "status": brun.status})
                if brun.status == "failed":
                    state["feedback"] = f"The builder run failed: {brun.error or 'unknown error'}"
                    state["phase"] = "builder"
                    continue
                state["phase"], state["gate_index"] = "gate", 0
            # ---- gates
            attempt = attempts[-1]
            while state["gate_index"] < len(pipeline.gates):
                gate = pipeline.gates[state["gate_index"]]
                if resumed is None:
                    await em.emit("gate_started", {"attempt": attempt.number, "gem": gate.gem, "role": gate.role})
                    grun = await _run_gem(gate.gem, gate_message(task, attempt.output, attempt.number, gate.role, gate.instructions),
                                          provider_override=gate.provider_override, model_override=gate.model_override, **kw)
                else:
                    grun = Run(**resumed)
                    resumed = None
                if grun.status == "waiting_approval":
                    attempt.gates.append(GateResult(gem=gate.gem, role=gate.role, run_id=grun.id, verdict="waiting"))
                    return await _pause(prun.id, attempts, state, em, grun.id, "gate")
                verdict, findings = ("fail", f"The gate run failed: {grun.error or 'unknown error'}") if grun.status == "failed" else parse_verdict(grun.output)
                attempt.gates = [g for g in attempt.gates if not (g.gem == gate.gem and g.verdict == "waiting")]
                attempt.gates.append(GateResult(gem=gate.gem, role=gate.role, run_id=grun.id, verdict=verdict, findings=findings))
                await em.emit("gate_finished", {"attempt": attempt.number, "gem": gate.gem, "role": gate.role, "run_id": grun.id, "verdict": verdict, "findings": findings[:2000]})
                await _save(prun.id, attempts, state=state)
                if verdict == "fail":
                    await memory_service.remember(f"Lesson from {pipeline.name}, {gate.role} gate ({gate.gem}) failed attempt {attempt.number}: {findings}",
                                                  kind="lesson", scope=kw["memory_scope"], source="run", gem_name=gate.gem, run_id=grun.id)
                    state["feedback"] = f"{gate.role} gate ({gate.gem}) said:\n{findings}"
                    state["phase"] = "builder"
                    break
                state["gate_index"] += 1
            else:
                # every gate passed
                if pipeline.acceptance:
                    state["phase"], state["seq"] = "acceptance", em.seq
                    await em.emit("pipeline_paused", {"status": "waiting_acceptance", "attempt": attempt.number})
                    run = await _save(prun.id, attempts, status="waiting_acceptance", state=state, output=attempt.output)
                    return PipelineResult(run=run, events=em.events)
                run = await _save(prun.id, attempts, status="passed", state=None, output=attempt.output, finished_at=_now())
                await em.emit("pipeline_finished", {"status": "passed", "attempts": len(attempts)})
                return PipelineResult(run=run, events=em.events)
            # a gate failed: loop back to the builder
            continue
    except Exception as exc:  # noqa: BLE001 - the record must say why
        logger.exception("Pipeline run %s failed", prun.id)
        run = await _save(prun.id, attempts, status="failed", state=None, error=f"{type(exc).__name__}: {exc}"[:500], finished_at=_now())
        await em.emit("pipeline_finished", {"status": "failed", "error": type(exc).__name__})
        return PipelineResult(run=run, events=em.events)
