import uuid

from fastapi import APIRouter, Depends, HTTPException
from app.models import Gem, GemCreate, GemDiff, GemUpdate, GemVersion, GemVersionSummary, ResolveRequest, ResolveResponse, RevertRequest
from app.services import gem_service, version_service
from app.auth import require_api_key

router = APIRouter(prefix="/gems", tags=["gems"], dependencies=[Depends(require_api_key)])


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


async def _find_gem(identifier: str):
    """Look a gem up by name, then by UUID. A value that is neither is simply not found."""
    gem = await gem_service.get_gem_by_name(identifier)
    if gem is None and _is_uuid(identifier):
        gem = await gem_service.get_gem_by_id(identifier)
    return gem


@router.get("/", response_model=list[Gem], summary="List all gems")
async def list_gems():
    """Return all active gems, ordered by name."""
    return await gem_service.get_all_gems()


@router.post("/", response_model=Gem, status_code=201, summary="Create a gem")
async def create_gem(data: GemCreate):
    """Create a new gem. Name must be unique."""
    existing = await gem_service.get_gem_by_name(data.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"A gem named '{data.name}' already exists.")
    try:
        return await gem_service.create_gem(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/resolve", response_model=ResolveResponse, summary="Resolve a gem")
async def resolve_gem(request: ResolveRequest):
    """
    Resolve a gem's system prompt — expand {{gem:name}} references
    recursively and fill in {variable} placeholders.
    """
    try:
        result = await gem_service.resolve_gem_detailed(request.gem_name, request.variables, strict=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ResolveResponse(
        gem_name=result.gem_name,
        resolved_prompt=result.resolved_prompt,
        referenced_gems=result.referenced_gems,
        variables_used=result.variables_used,
        variables_missing=result.variables_missing,
        variables_defaulted=result.variables_defaulted,
        variable_errors=result.variable_errors,
        examples_used=result.examples_used,
    )


@router.get("/{gem_id}", response_model=Gem, summary="Get a gem")
async def get_gem(gem_id: str):
    """Fetch a gem by name or UUID."""
    gem = await _find_gem(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    return gem


@router.put("/{gem_id}", response_model=Gem, summary="Update a gem")
async def update_gem(gem_id: str, data: GemUpdate):
    """Update a gem by name or UUID. Only provided fields are changed."""
    gem = await _find_gem(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    try:
        return await gem_service.update_gem(gem.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{gem_id}/versions", response_model=list[GemVersionSummary], summary="A gem's history")
async def list_versions(gem_id: str):
    """Every saved version, newest first, with the fields that changed from the one before (roadmap 14)."""
    gem = await _find_gem(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    return await version_service.history(gem)


@router.get("/{gem_id}/versions/{version}", response_model=GemVersion, summary="One version of a gem")
async def get_version(gem_id: str, version: int):
    gem = await _find_gem(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    found = await version_service.get(gem, version)
    if found is None:
        raise HTTPException(status_code=404, detail=f"'{gem.name}' has no version {version}.")
    return found


@router.get("/{gem_id}/diff", response_model=GemDiff, summary="What changed between two versions")
async def diff_versions(gem_id: str, from_version: int | None = None, to_version: int | None = None):
    """Defaults to the latest version against the one before. The prompt comes back as a unified diff, other fields as from and to."""
    gem = await _find_gem(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    try:
        return await version_service.diff(gem, from_version, to_version)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{gem_id}/versions/{version}/revert", response_model=Gem, summary="Restore an earlier version")
async def revert_version(gem_id: str, version: int, request: RevertRequest | None = None):
    """Writes that version's fields back as a new version; nothing in the history is lost. The name is kept."""
    gem = await _find_gem(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    try:
        return await version_service.revert(gem, version, (request.note if request else ""))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{gem_id}", summary="Delete a gem")
async def delete_gem(gem_id: str):
    """Soft-delete a gem by name or UUID (sets is_active=false)."""
    gem = await _find_gem(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    await gem_service.soft_delete_gem(gem.id)
    return {"message": f"Gem '{gem.name}' deleted."}
