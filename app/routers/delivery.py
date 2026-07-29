"""Project delivery API: QA runs, releases, and handoffs."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.user import User
from app.schemas.delivery import (
    DeliveryBoardResponse,
    HandoffCreate,
    HandoffResponse,
    HandoffUpdate,
    QaCheckItemResponse,
    QaCheckItemUpdate,
    QaRunCreate,
    QaRunResponse,
    QaRunUpdate,
    ReleaseCreate,
    ReleaseResponse,
    ReleaseUpdate,
)
from app.services.delivery import (
    build_coverage,
    create_handoff,
    create_qa_run,
    create_release,
    delete_handoff,
    delete_qa_run,
    delete_release,
    generate_handoff_summary,
    generate_release_notes,
    get_handoff_or_404,
    get_qa_item_or_404,
    get_qa_run_or_404,
    get_release_or_404,
    handoff_to_response,
    list_handoffs,
    list_qa_items,
    list_qa_runs,
    list_releases,
    qa_item_to_response,
    qa_run_to_response,
    release_to_response,
    update_handoff,
    update_qa_item,
    update_qa_run,
    update_release,
)
from app.services.project_access import get_project_or_404

router = APIRouter(prefix="/projects/{project_id}", tags=["delivery"])


@router.get("/delivery", response_model=DeliveryBoardResponse)
async def get_delivery_board(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    runs = await list_qa_runs(db, project_id)
    qa_responses = []
    for run in runs:
        items = await list_qa_items(db, run.id)
        qa_responses.append(qa_run_to_response(run, items))

    return DeliveryBoardResponse(
        qa_runs=qa_responses,
        releases=[release_to_response(r) for r in await list_releases(db, project_id)],
        handoffs=[handoff_to_response(h) for h in await list_handoffs(db, project_id)],
        coverage=await build_coverage(db, project_id),
    )


# --- QA runs ---


@router.get("/qa-runs", response_model=list[QaRunResponse])
async def get_qa_runs(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    responses = []
    for run in await list_qa_runs(db, project_id):
        items = await list_qa_items(db, run.id)
        responses.append(qa_run_to_response(run, items))
    return responses


@router.post("/qa-runs", response_model=QaRunResponse, status_code=201)
async def post_qa_run(
    project_id: UUID,
    body: QaRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run, items = await create_qa_run(
        db,
        current_user.id,
        project_id,
        title=body.title,
        notes=body.notes,
        seed_from_requirements=body.seed_from_requirements,
    )
    return qa_run_to_response(run, items)


@router.get("/qa-runs/{qa_run_id}", response_model=QaRunResponse)
async def get_qa_run(
    project_id: UUID,
    qa_run_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    run = await get_qa_run_or_404(db, project_id, qa_run_id)
    items = await list_qa_items(db, run.id)
    return qa_run_to_response(run, items)


@router.patch("/qa-runs/{qa_run_id}", response_model=QaRunResponse)
async def patch_qa_run(
    project_id: UUID,
    qa_run_id: UUID,
    body: QaRunUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    run = await get_qa_run_or_404(db, project_id, qa_run_id)
    run = await update_qa_run(
        db,
        project_id,
        run,
        title=body.title,
        notes=body.notes,
        status=body.status,
    )
    items = await list_qa_items(db, run.id)
    return qa_run_to_response(run, items)


@router.delete("/qa-runs/{qa_run_id}", status_code=204)
async def remove_qa_run(
    project_id: UUID,
    qa_run_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    run = await get_qa_run_or_404(db, project_id, qa_run_id)
    await delete_qa_run(db, project_id, run)


@router.patch(
    "/qa-runs/{qa_run_id}/items/{item_id}",
    response_model=QaCheckItemResponse,
)
async def patch_qa_item(
    project_id: UUID,
    qa_run_id: UUID,
    item_id: UUID,
    body: QaCheckItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    run = await get_qa_run_or_404(db, project_id, qa_run_id)
    item = await get_qa_item_or_404(db, qa_run_id, item_id)
    run, items = await update_qa_item(
        db,
        project_id,
        run,
        item,
        status=body.status,
        evidence_note=body.evidence_note,
        title=body.title,
        description=body.description,
    )
    updated = next(i for i in items if i.id == item_id)
    return qa_item_to_response(updated)


# --- Releases ---


@router.get("/releases", response_model=list[ReleaseResponse])
async def get_releases(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    return [release_to_response(r) for r in await list_releases(db, project_id)]


@router.post("/releases", response_model=ReleaseResponse, status_code=201)
async def post_release(
    project_id: UUID,
    body: ReleaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    release = await create_release(
        db,
        current_user.id,
        project_id,
        version=body.version,
        title=body.title,
        qa_run_id=body.qa_run_id,
        notes=body.notes,
    )
    return release_to_response(release)


@router.patch("/releases/{release_id}", response_model=ReleaseResponse)
async def patch_release(
    project_id: UUID,
    release_id: UUID,
    body: ReleaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    release = await get_release_or_404(db, project_id, release_id)
    release = await update_release(
        db,
        project_id,
        release,
        version=body.version,
        title=body.title,
        notes=body.notes,
        qa_run_id=body.qa_run_id,
        status=body.status,
    )
    return release_to_response(release)


@router.post(
    "/releases/{release_id}/generate-notes",
    response_model=ReleaseResponse,
)
async def post_generate_release_notes(
    project_id: UUID,
    release_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    release = await get_release_or_404(db, project_id, release_id)
    release = await generate_release_notes(
        db, current_user.id, project_id, release
    )
    return release_to_response(release)


@router.delete("/releases/{release_id}", status_code=204)
async def remove_release(
    project_id: UUID,
    release_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    release = await get_release_or_404(db, project_id, release_id)
    await delete_release(db, project_id, release)


# --- Handoffs ---


@router.get("/handoffs", response_model=list[HandoffResponse])
async def get_handoffs(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    return [handoff_to_response(h) for h in await list_handoffs(db, project_id)]


@router.post("/handoffs", response_model=HandoffResponse, status_code=201)
async def post_handoff(
    project_id: UUID,
    body: HandoffCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    handoff = await create_handoff(
        db,
        current_user.id,
        project_id,
        title=body.title,
        release_id=body.release_id,
        summary=body.summary,
    )
    return handoff_to_response(handoff)


@router.patch("/handoffs/{handoff_id}", response_model=HandoffResponse)
async def patch_handoff(
    project_id: UUID,
    handoff_id: UUID,
    body: HandoffUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    handoff = await get_handoff_or_404(db, project_id, handoff_id)
    handoff = await update_handoff(
        db,
        project_id,
        handoff,
        title=body.title,
        summary=body.summary,
        release_id=body.release_id,
        status=body.status,
    )
    return handoff_to_response(handoff)


@router.post(
    "/handoffs/{handoff_id}/generate-summary",
    response_model=HandoffResponse,
)
async def post_generate_handoff_summary(
    project_id: UUID,
    handoff_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    handoff = await get_handoff_or_404(db, project_id, handoff_id)
    handoff = await generate_handoff_summary(
        db, current_user.id, project_id, handoff
    )
    return handoff_to_response(handoff)


@router.delete("/handoffs/{handoff_id}", status_code=204)
async def remove_handoff(
    project_id: UUID,
    handoff_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    handoff = await get_handoff_or_404(db, project_id, handoff_id)
    await delete_handoff(db, project_id, handoff)
