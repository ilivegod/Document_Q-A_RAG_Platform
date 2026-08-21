"""Prospecting search jobs and prospect CRUD."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.project import PipelineStage, Project, ProjectType
from app.models.prospect import Prospect, ProspectSearch, ProspectStatus
from app.models.user import User
from app.schemas.prospect import (
    PlaceAutocompleteSuggestion,
    ProspectConvertResponse,
    ProspectResponse,
    ProspectSearchCreate,
    ProspectSearchResponse,
    ProspectUpdate,
)
from app.services.prospect_discovery import autocomplete_locations
from app.services.prospect_service import (
    cancel_prospect_search,
    delete_prospect_search,
    get_active_prospect_search,
    get_prospect_or_404,
    score_prospect_with_ai,
)
from app.workers.tasks import discover_prospects_task

router = APIRouter(tags=["prospecting"])


def _search_to_response(search: ProspectSearch) -> ProspectSearchResponse:
    return ProspectSearchResponse(
        id=search.id,
        location_query=search.location_query,
        industry_keywords=search.industry_keywords,
        radius_km=search.radius_km,
        filter_no_website=search.filter_no_website,
        filter_poor_website=search.filter_poor_website,
        max_candidates=search.max_candidates,
        niche_notes=search.niche_notes,
        status=search.status,
        result_count=search.result_count,
        error_message=search.error_message,
        cancel_requested=search.cancel_requested,
        current_step=search.current_step,
        progress_log=list(search.progress_log or []),
        created_at=search.created_at,
        completed_at=search.completed_at,
    )


def _prospect_to_response(prospect: Prospect) -> ProspectResponse:
    return ProspectResponse(
        id=prospect.id,
        search_id=prospect.search_id,
        project_id=prospect.project_id,
        place_id=prospect.place_id,
        business_name=prospect.business_name,
        address=prospect.address,
        phone=prospect.phone,
        website_url=prospect.website_url,
        website_status=prospect.website_status,
        audit_signals=prospect.audit_signals,
        fit_score=prospect.fit_score,
        fit_summary=prospect.fit_summary,
        pitch_angle=prospect.pitch_angle,
        contact_email=prospect.contact_email,
        status=prospect.status,
        created_at=prospect.created_at,
        updated_at=prospect.updated_at,
    )


@router.post(
    "/prospecting/searches",
    response_model=ProspectSearchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_prospect_search(
    body: ProspectSearchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active = await get_active_prospect_search(current_user.id, db)
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A lead search is already running. Stop it or wait for it to finish.",
        )
    search = ProspectSearch(
        user_id=current_user.id,
        location_query=body.location_query,
        industry_keywords=body.industry_keywords,
        radius_km=body.radius_km,
        filter_no_website=body.filter_no_website,
        filter_poor_website=body.filter_poor_website,
        max_candidates=body.max_candidates,
        niche_notes=body.niche_notes,
    )
    db.add(search)
    await db.commit()
    await db.refresh(search)
    discover_prospects_task.delay(str(search.id))
    return _search_to_response(search)


@router.get("/prospecting/searches/active", response_model=ProspectSearchResponse | None)
async def get_active_prospect_search_route(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    search = await get_active_prospect_search(current_user.id, db)
    if search is None:
        return None
    return _search_to_response(search)


@router.get("/prospecting/searches", response_model=list[ProspectSearchResponse])
async def list_prospect_searches(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProspectSearch)
        .where(ProspectSearch.user_id == current_user.id)
        .order_by(ProspectSearch.created_at.desc())
        .limit(limit)
    )
    return [_search_to_response(search) for search in result.scalars().all()]


@router.get(
    "/prospecting/places/autocomplete",
    response_model=list[PlaceAutocompleteSuggestion],
)
async def autocomplete_prospect_locations(
    input: str = Query(..., min_length=2, max_length=200),
    current_user: User = Depends(get_current_user),
):
    suggestions = await autocomplete_locations(input)
    return [PlaceAutocompleteSuggestion(**item) for item in suggestions]


@router.get("/prospecting/searches/{search_id}", response_model=ProspectSearchResponse)
async def get_prospect_search(
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    search = await db.get(ProspectSearch, search_id)
    if not search or search.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Search not found")
    return _search_to_response(search)


@router.post(
    "/prospecting/searches/{search_id}/cancel",
    response_model=ProspectSearchResponse,
)
async def cancel_prospect_search_route(
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    search = await cancel_prospect_search(search_id, current_user.id, db)
    return _search_to_response(search)


@router.delete("/prospecting/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prospect_search_route(
    search_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await delete_prospect_search(search_id, current_user.id, db)


@router.get("/prospects", response_model=list[ProspectResponse])
async def list_prospects(
    search_id: UUID | None = Query(None),
    status_filter: ProspectStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Prospect).where(Prospect.user_id == current_user.id)
    if search_id:
        query = query.where(Prospect.search_id == search_id)
    if status_filter:
        query = query.where(Prospect.status == status_filter)
    query = query.order_by(
        Prospect.fit_score.desc().nullslast(),
        Prospect.created_at.desc(),
    )
    result = await db.execute(query)
    return [_prospect_to_response(p) for p in result.scalars().all()]


@router.get("/prospects/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prospect = await get_prospect_or_404(prospect_id, current_user.id, db)
    return _prospect_to_response(prospect)


@router.post("/prospects/{prospect_id}/score-with-ai", response_model=ProspectResponse)
async def score_prospect_with_ai_route(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prospect = await score_prospect_with_ai(prospect_id, current_user.id, db)
    return _prospect_to_response(prospect)


@router.patch("/prospects/{prospect_id}", response_model=ProspectResponse)
async def update_prospect(
    prospect_id: UUID,
    body: ProspectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prospect = await get_prospect_or_404(prospect_id, current_user.id, db)
    if body.contact_email is not None:
        prospect.contact_email = body.contact_email
    if body.status is not None:
        prospect.status = body.status
    await db.commit()
    await db.refresh(prospect)
    return _prospect_to_response(prospect)


@router.post(
    "/prospects/{prospect_id}/convert",
    response_model=ProspectConvertResponse,
)
async def convert_prospect(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prospect = await get_prospect_or_404(prospect_id, current_user.id, db)
    if prospect.project_id:
        return ProspectConvertResponse(
            prospect=_prospect_to_response(prospect),
            project_id=prospect.project_id,
        )

    project = Project(
        user_id=current_user.id,
        name=prospect.business_name,
        client_name=prospect.business_name,
        description=prospect.fit_summary,
        project_type=ProjectType.CLIENT,
        pipeline_stage=PipelineStage.LEAD,
    )
    db.add(project)
    await db.flush()

    prospect.project_id = project.id
    prospect.status = ProspectStatus.CONVERTED
    await db.commit()
    await db.refresh(prospect)
    return ProspectConvertResponse(
        prospect=_prospect_to_response(prospect),
        project_id=project.id,
    )
