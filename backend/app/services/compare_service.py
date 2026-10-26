"""
Side-by-side runs (roadmap item 30).

One input, two to four columns. Each column is a version of the gem from its
history (item 14) and an AI (a provider and model override, or the gem's own
choice through the model policy). Either one question goes through every
column, or the gem's tests (item 28) do, giving a pass and fail grid.

A past version is rebuilt from its stored fields: its own prompt, provider and
model; the prompts it embeds with {{gem:...}} resolve as they are now. An
assistant (agent gem) runs its full loop, and only its current version can be
compared, since a run needs the live gem. Columns run at the same time.
Every column is a model call and costs money unless it runs on this PC, so the
call cap from evals applies, and the estimate says what a comparison will use.
"""
from __future__ import annotations
import asyncio
import time

from app import settings
from app.models import CompareColumn, CompareEstimate, CompareRequest, CompareResult, CompareTestsResult, CompareVariant, EvalCase, Gem
from app.services import eval_service, gem_service, version_service
from app.services import router as model_router


class CompareError(ValueError):
    """A comparison that should not run: a missing version, an old version of an assistant, no tests, or over the cap."""


class _Plan:
    """What one column will do: the prompt to use (None for an assistant) and which AI."""

    def __init__(self, variant: CompareVariant, version: int, prompt_text: str | None, provider: str, model: str, reason: str, label: str,
                 specs: dict | None = None, examples: list | None = None) -> None:
        self.variant, self.version, self.prompt_text, self.specs, self.examples = variant, version, prompt_text, specs or {}, examples or []
        self.provider, self.model, self.reason, self.label = provider, model, reason, label


def _ai_words(provider: str) -> str:
    return {"anthropic": "Claude", "openai": "ChatGPT", "local": "on this PC"}.get(provider, provider)


async def _plan(gem: Gem, variants: list[CompareVariant]) -> list[_Plan]:
    history = await version_service.versions(gem.id)
    current = history[-1].version if history else 1
    plans = []
    for v in variants:
        number = v.version or current
        if number == current:
            source = gem
            prompt_text = gem.system_prompt
            specs = gem.variable_specs
            examples = [e.model_dump() for e in gem.examples]
        else:
            found = next((h for h in history if h.version == number), None)
            if found is None:
                raise CompareError(f"'{gem.name}' has no version {number} (latest is {current}).")
            if gem.kind == "agent":
                raise CompareError("For an assistant only the current version can be compared; compare different AIs instead.")
            snap = found.snapshot
            source = gem.model_copy(update={"provider": snap.get("provider", gem.provider), "model": snap.get("model", gem.model)})
            prompt_text = snap.get("system_prompt", "")
            specs = snap.get("variable_specs") or {}
            examples = snap.get("examples") or []
        choice = await model_router.choose(source, provider_override=v.provider_override, model_override=v.model_override)
        label = v.label.strip() or f"v{number} · {_ai_words(choice.provider)} ({choice.model})"
        plans.append(_Plan(v, number, None if gem.kind == "agent" else prompt_text, choice.provider, choice.model, choice.reason, label, specs, examples))
    return plans


async def _answer(gem: Gem, plan: _Plan, message: str, variables: dict[str, str], max_tokens: int | None) -> tuple[str, str | None]:
    """The column's answer, and the agent run id for an assistant."""
    from app.services import llm_service

    if gem.kind == "agent":
        from app.agents.runner import run_agent
        result = await run_agent(gem.name, message, variables, provider_override=plan.provider, model_override=plan.model)
        if result.run.status == "waiting_approval":
            raise RuntimeError("the assistant stopped to ask for approval of a tool that can change things; open its run to decide")
        if result.run.status == "failed":
            raise RuntimeError(result.run.error or "the run failed")
        return result.run.output or "", result.run.id
    prompt = await gem_service.resolve_text(gem.name, plan.prompt_text or "", variables, plan.specs, plan.examples)
    return await llm_service.complete(prompt, [{"role": "user", "content": message}], plan.model, plan.provider, max_tokens=max_tokens), None


async def estimate(gem: Gem, req: CompareRequest, on_tests: bool = False) -> CompareEstimate:
    plans = await _plan(gem, req.variants)
    tests = await eval_service.cases(gem) if on_tests else []
    per_column = (len(tests) + sum(1 for c in tests if c.check == "judge")) if on_tests else 1
    columns = [{"label": p.label, "version": p.version, "provider": p.provider, "model": p.model, "free": p.provider == "local"} for p in plans]
    return CompareEstimate(calls=per_column * len(plans), tests=len(tests), columns=columns,
                           free=all(c["free"] for c in columns), max_calls=settings.EVAL_MAX_CALLS)


async def compare(gem: Gem, req: CompareRequest) -> CompareResult:
    """One question through every column, at the same time."""
    if not req.message.strip():
        raise CompareError("Type the question every column should answer.")
    plans = await _plan(gem, req.variants)

    async def column(plan: _Plan) -> CompareColumn:
        started = time.monotonic()
        col = CompareColumn(label=plan.label, version=plan.version, provider=plan.provider, model=plan.model, reason=plan.reason)
        try:
            col.output, col.run_id = await _answer(gem, plan, req.message, req.variables, None)
        except Exception as exc:  # noqa: BLE001 - one column failing must not hide the others
            col.error = f"{type(exc).__name__}: {exc}"[:300]
        col.seconds = round(time.monotonic() - started, 2)
        return col

    return CompareResult(gem_name=gem.name, message=req.message, columns=list(await asyncio.gather(*(column(p) for p in plans))))


async def compare_tests(gem: Gem, req: CompareRequest, max_calls: int | None = None) -> CompareTestsResult:
    """The gem's tests through every column: a pass and fail grid with totals. Not recorded as eval runs."""
    tests: list[EvalCase] = await eval_service.cases(gem)
    if not tests:
        raise CompareError(f"'{gem.name}' has no tests yet; add some on its page first.")
    est = await estimate(gem, req, on_tests=True)
    cap = min(max_calls or settings.EVAL_MAX_CALLS, settings.EVAL_MAX_CALLS)
    if est.calls > cap:
        raise CompareError(f"this comparison needs {est.calls} model calls and the cap is {cap}; use fewer columns or tests, or raise GEMS_EVAL_MAX_CALLS.")
    plans = await _plan(gem, req.variants)

    async def score(plan: _Plan, case: EvalCase) -> tuple[bool, str]:
        try:
            output, _ = await _answer(gem, plan, case.input, case.variables, settings.EVAL_MAX_TOKENS)
            if case.check == "judge":
                return await eval_service._judge(case, output, plan.provider, plan.model)
            return eval_service.check_answer(case.check, case.expected, output)
        except Exception as exc:  # noqa: BLE001
            return False, f"could not get an answer: {exc}"[:300]

    grid = await asyncio.gather(*(asyncio.gather(*(score(p, c) for c in tests)) for p in plans))
    cases = [{"name": c.name or c.input[:60], "results": [{"passed": grid[i][j][0], "detail": grid[i][j][1]} for i in range(len(plans))]}
             for j, c in enumerate(tests)]
    totals = [sum(1 for passed, _ in col if passed) for col in grid]
    columns = [CompareColumn(label=p.label, version=p.version, provider=p.provider, model=p.model, reason=p.reason) for p in plans]
    return CompareTestsResult(gem_name=gem.name, columns=columns, cases=cases, totals=totals)
