"""Evals per gem over REST (roadmap 28): cases, the cost estimate, runs, the baseline. And side-by-side runs (roadmap 30)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_api_key
from app.models import (CompareEstimate, CompareRequest, CompareResult, CompareTestsResult, EvalCase, EvalCaseCreate,
                        EvalCaseUpdate, EvalEstimate, EvalRun, EvalRunReport, EvalRunRequest)
from app.routes.gems import _find_gem
from app.services import compare_service, eval_service

router = APIRouter(prefix="/gems", tags=["evals"], dependencies=[Depends(require_api_key)])


async def _gem(gem_id: str):
    gem = await _find_gem(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    return gem


@router.get("/{gem_id}/evals", response_model=list[EvalCase], summary="A gem's eval cases")
async def list_cases(gem_id: str):
    return await eval_service.cases(await _gem(gem_id))


@router.post("/{gem_id}/evals", response_model=EvalCase, status_code=201, summary="Add an eval case")
async def add_case(gem_id: str, data: EvalCaseCreate):
    """An input, values for the blanks, and a check: contains, not_contains, all_of, equals, json or judge."""
    try:
        return await eval_service.add_case(await _gem(gem_id), data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/{gem_id}/evals/{case_id}", response_model=EvalCase, summary="Change an eval case")
async def update_case(gem_id: str, case_id: str, data: EvalCaseUpdate):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    try:
        case = await eval_service.update_case(await _gem(gem_id), case_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if case is None:
        raise HTTPException(status_code=404, detail=f"Eval case '{case_id}' not found.")
    return case


@router.delete("/{gem_id}/evals/{case_id}", status_code=204, summary="Remove an eval case")
async def delete_case(gem_id: str, case_id: str):
    if not await eval_service.delete_case(await _gem(gem_id), case_id):
        raise HTTPException(status_code=404, detail=f"Eval case '{case_id}' not found.")


@router.get("/{gem_id}/evals/estimate", response_model=EvalEstimate, summary="What a run would cost")
async def estimate(gem_id: str, provider_override: str | None = None, model_override: str | None = None):
    """Model calls, rough tokens, which AI, and whether it is free (runs on this PC). Nothing is called."""
    return await eval_service.estimate(await _gem(gem_id), provider_override, model_override)


@router.post("/{gem_id}/evals/run", response_model=EvalRunReport, summary="Run the evals")
async def run_evals(gem_id: str, request: EvalRunRequest | None = None):
    """
    Answers every case with the gem as it is now, scores it, records the run against the gem's
    version, and lists regressions and fixes against the baseline. Calls the model, so it costs
    money unless the AI runs on this PC; refused when it would exceed the call cap.
    """
    req = request or EvalRunRequest()
    try:
        return await eval_service.run(await _gem(gem_id), req.provider_override, req.model_override, req.max_calls)
    except eval_service.EvalError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{gem_id}/evals/runs", response_model=list[EvalRun], summary="Past eval runs")
async def list_runs(gem_id: str, limit: int = 50):
    return await eval_service.runs(await _gem(gem_id), limit)


@router.post("/{gem_id}/evals/runs/{run_id}/baseline", response_model=EvalRun, summary="Make a run the baseline")
async def set_baseline(gem_id: str, run_id: str):
    """Later runs list their regressions and fixes against this one. The first run of a gem is the baseline until you pick another."""
    run = await eval_service.set_baseline(await _gem(gem_id), run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found.")
    return run


# ─── Side-by-side runs (roadmap 30) ───────────────────────────────────────────

@router.post("/{gem_id}/compare/estimate", response_model=CompareEstimate, summary="What a comparison would cost")
async def compare_estimate(gem_id: str, request: CompareRequest, tests: bool = False):
    """Which version and AI each column uses, how many model calls it takes, and whether it is all free on this PC. Nothing is called."""
    try:
        return await compare_service.estimate(await _gem(gem_id), request, on_tests=tests)
    except compare_service.CompareError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{gem_id}/compare", response_model=CompareResult, summary="One question, two to four columns")
async def compare(gem_id: str, request: CompareRequest):
    """Each column is a version of the gem (from its history) and an AI; all of them answer the same message at the same time."""
    try:
        return await compare_service.compare(await _gem(gem_id), request)
    except compare_service.CompareError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{gem_id}/compare/tests", response_model=CompareTestsResult, summary="The gem's tests through every column")
async def compare_tests(gem_id: str, request: CompareRequest):
    """A pass and fail grid with totals per column. Calls the model for every test in every column; refused above the call cap."""
    try:
        return await compare_service.compare_tests(await _gem(gem_id), request)
    except compare_service.CompareError as exc:
        raise HTTPException(status_code=409 if "cap" in str(exc) or "no tests" in str(exc) else 400, detail=str(exc))
