"""
Evals per gem (roadmap item 28).

A gem carries test cases: an input, values for its blanks, and a check on the
answer. Running them scores the gem as it is now, records the run against the
gem's version in its history, and compares it with a baseline so a change that
makes things worse shows up as a list of regressions instead of a feeling.

Checks: contains, not_contains, all_of (one phrase per line), equals, json (the
answer is JSON matching a small schema subset: type, required, properties,
items, enum), and judge (an AI reads the answer against your criteria and ends
with VERDICT: PASS or FAIL). There is deliberately no regular-expression check:
a pattern typed into the UI and run on the server is an injection risk.

Every run calls a model, so it costs money unless the AI runs on this PC. The
estimate comes first, a run that would exceed GEMS_EVAL_MAX_CALLS is refused,
and each answer is capped at GEMS_EVAL_MAX_TOKENS.
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone

from app import settings
from app.models import EVAL_CHECKS, EvalCase, EvalCaseCreate, EvalCaseResult, EvalEstimate, EvalRun, EvalRunReport, Gem
from app.storage import get_store

logger = logging.getLogger(__name__)
JUDGE_MAX_TOKENS = 400


def _strip_fence(text: str) -> str:
    """An answer wrapped in a ```json fence is judged on what is inside it. Plain string handling, no regex."""
    t = (text or "").strip()
    if len(t) >= 6 and t.startswith("```") and t.endswith("```"):
        inner = t[3:-3]
        if inner.lower().startswith("json"):
            inner = inner[4:]
        return inner.strip()
    return text or ""


def _store():
    return get_store()


class EvalError(ValueError):
    """A run that should not happen: no cases, or over the call cap."""


# ─── checks ────────────────────────────────────────────────────────────────────

def _schema_errors(value, schema: dict, path: str = "$") -> list[str]:
    """A small JSON schema subset: type, required, properties, items, enum. Enough to say 'the shape is right'."""
    errors: list[str] = []
    types = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool, "null": type(None)}
    t = schema.get("type")
    if t:
        allowed = t if isinstance(t, list) else [t]
        ok = any(isinstance(value, types[x]) and not (x in ("integer", "number") and isinstance(value, bool)) for x in allowed if x in types)
        if not ok:
            return [f"{path} should be {' or '.join(allowed)}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} should be one of {schema['enum']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path} is missing '{key}'")
        for key, sub in (schema.get("properties") or {}).items():
            if key in value and isinstance(sub, dict):
                errors += _schema_errors(value[key], sub, f"{path}.{key}")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            errors += _schema_errors(item, schema["items"], f"{path}[{i}]")
    return errors


def check_answer(check: str, expected: str, output: str) -> tuple[bool, str]:
    """Every check except judge. Returns passed and a one-sentence reason."""
    out = output or ""
    if check == "contains":
        ok = expected.strip().lower() in out.lower()
        return ok, f"{'found' if ok else 'did not find'} “{expected.strip()}”"
    if check == "not_contains":
        ok = expected.strip().lower() not in out.lower()
        return ok, f"{'did not find' if ok else 'found'} “{expected.strip()}”"
    if check == "all_of":
        phrases = [p.strip() for p in expected.splitlines() if p.strip()]
        missing = [p for p in phrases if p.lower() not in out.lower()]
        return not missing, ("found all " + str(len(phrases))) if not missing else ("missing " + ", ".join(f"“{m}”" for m in missing))
    if check == "equals":
        ok = out.strip() == expected.strip()
        return ok, "matches exactly" if ok else "differs from the expected text"
    if check == "json":
        text = _strip_fence(out)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            return False, f"not valid JSON ({exc.msg} at line {exc.lineno})"
        if not expected.strip():
            return True, "valid JSON"
        try:
            schema = json.loads(expected)
        except json.JSONDecodeError:
            return False, "the expected schema is not valid JSON; fix the case"
        errors = _schema_errors(value, schema if isinstance(schema, dict) else {})
        return not errors, "valid JSON with the expected shape" if not errors else "; ".join(errors[:5])
    raise ValueError(f"unknown check {check}")


async def _judge(case: EvalCase, output: str, provider: str, model: str) -> tuple[bool, str]:
    from app.agents.pipeline import parse_verdict
    from app.services import llm_service

    system = ("You judge one answer against criteria. Read the question, the answer and the criteria. "
              "Write one or two sentences on whether the answer meets every criterion, then end with one line: VERDICT: PASS or VERDICT: FAIL.")
    message = f"Question:\n<question>\n{case.input}\n</question>\n\nAnswer:\n<answer>\n{output}\n</answer>\n\nCriteria:\n<criteria>\n{case.expected}\n</criteria>"
    text = await llm_service.complete(system, [{"role": "user", "content": message}], model, provider, max_tokens=JUDGE_MAX_TOKENS)
    verdict, reason = parse_verdict(text)
    return verdict == "pass", (reason.splitlines()[0] if reason else verdict)[:300]


# ─── cases ─────────────────────────────────────────────────────────────────────

def validate(data: EvalCaseCreate | dict) -> None:
    check = data["check"] if isinstance(data, dict) else data.check
    expected = data.get("expected", "") if isinstance(data, dict) else data.expected
    if check not in EVAL_CHECKS:
        raise ValueError(f"check must be one of {', '.join(EVAL_CHECKS)}")
    if check in ("contains", "not_contains", "all_of", "judge") and not (expected or "").strip():
        raise ValueError(f"a {check} check needs something in expected")
    if check == "json" and (expected or "").strip():
        try:
            json.loads(expected)
        except json.JSONDecodeError:
            raise ValueError("expected must be a JSON schema for a json check, or empty to only require valid JSON")


async def cases(gem: Gem) -> list[EvalCase]:
    return await _store().list_eval_cases(gem.id)


async def add_case(gem: Gem, data: EvalCaseCreate) -> EvalCase:
    validate(data)
    return await _store().add_eval_case(gem.id, data)


async def update_case(gem: Gem, case_id: str, updates: dict) -> EvalCase | None:
    current = next((c for c in await cases(gem) if c.id == case_id), None)
    if current is None:
        return None
    validate({**current.model_dump(), **updates})
    return await _store().update_eval_case(case_id, updates)


async def delete_case(gem: Gem, case_id: str) -> bool:
    if not any(c.id == case_id for c in await cases(gem)):
        return False
    return await _store().delete_eval_case(case_id)


# ─── estimate and run ──────────────────────────────────────────────────────────

async def _choice(gem: Gem, provider_override: str | None, model_override: str | None):
    from app.services import router as model_router
    return await model_router.choose(gem, provider_override=provider_override, model_override=model_override)


async def estimate(gem: Gem, provider_override: str | None = None, model_override: str | None = None) -> EvalEstimate:
    from app.services import gem_service

    found = await cases(gem)
    choice = await _choice(gem, provider_override, model_override)
    calls = len(found) + sum(1 for c in found if c.check == "judge")
    chars = 0
    for c in found:
        try:
            prompt, _ = await gem_service.resolve_gem(gem.name, c.variables)
        except ValueError:
            prompt = gem.system_prompt
        chars += len(prompt) + len(c.input)
        if c.check == "judge":
            chars += len(c.input) + len(c.expected) + settings.EVAL_MAX_TOKENS * 4
    max_out = len(found) * settings.EVAL_MAX_TOKENS + sum(JUDGE_MAX_TOKENS for c in found if c.check == "judge")
    return EvalEstimate(cases=len(found), calls=calls, provider=choice.provider, model=choice.model, free=choice.provider == "local",
                        input_tokens=chars // 4, max_output_tokens=max_out, max_calls=settings.EVAL_MAX_CALLS)


async def _answer(gem: Gem, case: EvalCase, provider: str, model: str) -> str:
    """The gem's answer to one case: one model call for a prompt gem, a full run for an agent gem."""
    from app.services import gem_service, llm_service

    if gem.kind == "agent":
        from app.agents.runner import run_agent
        result = await run_agent(gem.name, case.input, case.variables, provider_override=provider, model_override=model)
        if result.run.status == "waiting_approval":
            raise RuntimeError("the assistant stopped to ask for approval of a tool that can change things; evals do not approve tools")
        if result.run.status == "failed":
            raise RuntimeError(result.run.error or "the run failed")
        return result.run.output or ""
    prompt, _ = await gem_service.resolve_gem(gem.name, case.variables)
    return await llm_service.complete(prompt, [{"role": "user", "content": case.input}], model, provider, max_tokens=settings.EVAL_MAX_TOKENS)


async def _current_version(gem: Gem) -> int:
    from app.services import version_service
    found = await version_service.versions(gem.id)
    return found[-1].version if found else 1


async def run(gem: Gem, provider_override: str | None = None, model_override: str | None = None, max_calls: int | None = None) -> EvalRunReport:
    """Run every case, score it, store it, and compare with the baseline. Raises EvalError for no cases or a run over the cap."""
    found = await cases(gem)
    if not found:
        raise EvalError(f"'{gem.name}' has no eval cases yet; add one first.")
    est = await estimate(gem, provider_override, model_override)
    cap = min(max_calls or settings.EVAL_MAX_CALLS, settings.EVAL_MAX_CALLS)
    if est.calls > cap:
        raise EvalError(f"this run needs {est.calls} model calls and the cap is {cap}; remove cases or raise GEMS_EVAL_MAX_CALLS.")
    results: list[EvalCaseResult] = []
    for case in found:
        try:
            output = await _answer(gem, case, est.provider, est.model)
            if case.check == "judge":
                passed, detail = await _judge(case, output, est.provider, est.model)
            else:
                passed, detail = check_answer(case.check, case.expected, output)
        except Exception as exc:  # noqa: BLE001 - one broken case must not lose the others
            logger.info("eval case %s of %s failed to run: %s", case.id, gem.name, exc)
            output, passed, detail = "", False, f"could not get an answer: {exc}"[:300]
        results.append(EvalCaseResult(case_id=case.id, name=case.name or case.input[:60], passed=passed, output=output[:4000], detail=detail))
    previous = await _store().list_eval_runs(gem.id, 200)
    record = EvalRun(id=str(uuid.uuid4()), gem_id=gem.id, gem_version=await _current_version(gem), provider=est.provider, model=est.model,
                     passed=sum(r.passed for r in results), total=len(results), results=results,
                     baseline=not any(p.baseline for p in previous), created_at=datetime.now(timezone.utc))
    await _store().add_eval_run(record)
    return await report(gem, record, previous)


def compare(run: EvalRun, baseline: EvalRun | None) -> tuple[list[str], list[str]]:
    if baseline is None or baseline.id == run.id:
        return [], []
    before = {r.case_id: r.passed for r in baseline.results}
    names = {r.case_id: r.name for r in run.results}
    regressions = [names[r.case_id] for r in run.results if before.get(r.case_id) is True and not r.passed]
    fixed = [names[r.case_id] for r in run.results if before.get(r.case_id) is False and r.passed]
    return regressions, fixed


async def report(gem: Gem, run: EvalRun, runs: list[EvalRun] | None = None) -> EvalRunReport:
    runs = runs if runs is not None else await _store().list_eval_runs(gem.id, 200)
    baseline = next((r for r in runs if r.baseline and r.id != run.id), None)
    regressions, fixed = compare(run, baseline)
    return EvalRunReport(run=run, baseline=baseline, regressions=regressions, fixed=fixed)


async def runs(gem: Gem, limit: int = 50) -> list[EvalRun]:
    return await _store().list_eval_runs(gem.id, limit)


async def set_baseline(gem: Gem, run_id: str) -> EvalRun | None:
    return await _store().set_eval_baseline(gem.id, run_id)
