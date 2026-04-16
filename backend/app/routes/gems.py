from fastapi import APIRouter, Depends, HTTPException
from app.models import Gem, GemCreate, GemUpdate, ResolveRequest, ResolveResponse
from app.services import gem_service
from app.auth import require_api_key

router = APIRouter(prefix="/gems", tags=["gems"], dependencies=[Depends(require_api_key)])


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
    return await gem_service.create_gem(data)


@router.post("/resolve", response_model=ResolveResponse, summary="Resolve a gem")
async def resolve_gem(request: ResolveRequest):
    """
    Resolve a gem's system prompt — expand {{gem:name}} references
    recursively and fill in {variable} placeholders.
    """
    try:
        resolved, refs = await gem_service.resolve_gem(request.gem_name, request.variables)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Detect any variables still unfilled in the resolved output
    remaining_vars = gem_service.extract_variables(resolved)
    provided = set(request.variables.keys())
    missing = [v for v in remaining_vars if v not in provided]

    return ResolveResponse(
        gem_name=request.gem_name,
        resolved_prompt=resolved,
        referenced_gems=refs,
        variables_used=sorted(provided & set(remaining_vars + list(provided))),
        variables_missing=missing,
    )


@router.get("/{gem_id}", response_model=Gem, summary="Get a gem")
async def get_gem(gem_id: str):
    """Fetch a gem by name or UUID."""
    gem = await gem_service.get_gem_by_name(gem_id) or await gem_service.get_gem_by_id(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    return gem


@router.put("/{gem_id}", response_model=Gem, summary="Update a gem")
async def update_gem(gem_id: str, data: GemUpdate):
    """Update a gem by UUID. Only provided fields are changed."""
    gem = await gem_service.get_gem_by_id(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    return await gem_service.update_gem(gem_id, data)


@router.delete("/{gem_id}", summary="Delete a gem")
async def delete_gem(gem_id: str):
    """Soft-delete a gem (sets is_active=false)."""
    gem = await gem_service.get_gem_by_id(gem_id)
    if not gem:
        raise HTTPException(status_code=404, detail=f"Gem '{gem_id}' not found.")
    await gem_service.soft_delete_gem(gem_id)
    return {"message": f"Gem '{gem.name}' deleted."}
