"""Persistent editable project technology stack."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.project_technology import (
    ProjectTechnology,
    TechnologyCategory,
    TechnologySource,
)
from app.schemas.technology import (
    ProjectTechnologyCreate,
    ProjectTechnologyResponse,
    TechnologyCatalogItemResponse,
    TechnologyStackResponse,
)
from app.services.llm_errors import raise_llm_http_error
from app.services.project_access import get_project_or_404
from app.services.requirements import list_working_requirements
from app.services.technology_catalog import (
    CATEGORY_DESCRIPTIONS,
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    get_catalog_item,
    search_catalog,
    catalog_ids_by_category,
)

logger = logging.getLogger(__name__)


class LLMStackSelection(BaseModel):
    catalog_id: str
    rationale: str = ""


class LLMStackResult(BaseModel):
    technologies: list[LLMStackSelection] = Field(default_factory=list)


def _format_requirements(requirements) -> str:
    if not requirements:
        return "No structured requirements yet."
    lines = []
    for req in requirements:
        lines.append(
            f"- {req.stable_id}: {req.title} "
            f"({req.category.value}, {req.priority.value}) — "
            f"{req.description or ''}"
        )
    return "\n".join(lines)


def _to_response(row: ProjectTechnology) -> ProjectTechnologyResponse:
    catalog = get_catalog_item(row.catalog_id)
    if catalog is None:
        raise HTTPException(status_code=500, detail="Unknown catalog item in stack")

    return ProjectTechnologyResponse(
        id=row.id,
        project_id=row.project_id,
        catalog_id=row.catalog_id,
        name=catalog.name,
        category=row.category,
        docs_url=catalog.docs_url,
        icon_slug=catalog.icon_slug,
        summary=catalog.summary,
        usage_hint=catalog.usage_hint,
        source=row.source,
        rationale=row.rationale,
        sort_order=row.sort_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_project_stack(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> TechnologyStackResponse:
    await get_project_or_404(project_id, user_id, db)
    result = await db.execute(
        select(ProjectTechnology)
        .where(ProjectTechnology.project_id == project_id)
        .order_by(
            ProjectTechnology.category.asc(),
            ProjectTechnology.sort_order.asc(),
            ProjectTechnology.created_at.asc(),
        )
    )
    items = [_to_response(row) for row in result.scalars().all()]
    grouped: dict[str, list[ProjectTechnologyResponse]] = {}
    category_descriptions: dict[str, str] = {}
    for category in CATEGORY_ORDER:
        category_items = [item for item in items if item.category == category]
        if category_items:
            grouped[category.value] = category_items
            category_descriptions[category.value] = CATEGORY_DESCRIPTIONS[category]
    return TechnologyStackResponse(
        categories=grouped,
        category_descriptions=category_descriptions,
    )


async def add_technology_to_stack(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    body: ProjectTechnologyCreate,
) -> ProjectTechnologyResponse:
    await get_project_or_404(project_id, user_id, db)
    catalog = get_catalog_item(body.catalog_id)
    if catalog is None:
        raise HTTPException(status_code=400, detail="Unknown technology in catalog")

    existing = await db.execute(
        select(ProjectTechnology).where(
            ProjectTechnology.project_id == project_id,
            ProjectTechnology.catalog_id == body.catalog_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Technology already in stack")

    count_result = await db.execute(
        select(func.count())
        .select_from(ProjectTechnology)
        .where(ProjectTechnology.project_id == project_id)
    )
    sort_order = int(count_result.scalar_one())

    row = ProjectTechnology(
        project_id=project_id,
        catalog_id=catalog.id,
        category=catalog.category,
        source=TechnologySource.MANUAL,
        rationale=body.rationale,
        sort_order=sort_order,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_response(row)


async def remove_technology_from_stack(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    item_id: UUID,
) -> None:
    await get_project_or_404(project_id, user_id, db)
    row = await db.get(ProjectTechnology, item_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Technology item not found")
    await db.delete(row)
    await db.commit()


async def generate_project_stack(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    force: bool = False,
) -> list[ProjectTechnology]:
    await get_project_or_404(project_id, user_id, db)

    count_result = await db.execute(
        select(func.count())
        .select_from(ProjectTechnology)
        .where(ProjectTechnology.project_id == project_id)
    )
    if int(count_result.scalar_one()) > 0 and not force:
        return []

    requirements, _ = await list_working_requirements(db, project_id)
    if not requirements:
        raise HTTPException(
            status_code=400,
            detail="Extract requirements before generating a technology stack.",
        )

    allowed = catalog_ids_by_category()
    allowed_text = "\n".join(
        f"{category}: {', '.join(ids)}" for category, ids in allowed.items()
    )

    prompt = PromptTemplate.from_template(
        """You are a senior solutions architect helping a freelance developer choose a
practical technology stack for their project.

Given the project requirements below, select technologies ONLY from the allowed catalog IDs.
Pick 6-12 technologies that best fit the project across relevant categories.
Each entry must use a valid catalog_id and a short project-specific rationale (1 sentence)
explaining why this technology fits the requirements — not generic marketing copy.

Allowed catalog IDs by category:
{allowed}

Project requirements:
{requirements}

Return only technologies from the allowed list. Do not invent new IDs.
"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(LLMStackResult)

    try:
        result: LLMStackResult = await (prompt | model).ainvoke(
            {
                "allowed": allowed_text,
                "requirements": _format_requirements(requirements),
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="generate technology stack")

    if force:
        await db.execute(
            delete(ProjectTechnology).where(ProjectTechnology.project_id == project_id)
        )

    created: list[ProjectTechnology] = []
    seen: set[str] = set()
    sort_order = 0

    for selection in result.technologies:
        if selection.catalog_id in seen:
            continue
        catalog = get_catalog_item(selection.catalog_id)
        if catalog is None:
            logger.warning("LLM returned unknown catalog_id: %s", selection.catalog_id)
            continue
        seen.add(selection.catalog_id)
        row = ProjectTechnology(
            project_id=project_id,
            catalog_id=catalog.id,
            category=catalog.category,
            source=TechnologySource.AI,
            rationale=selection.rationale.strip() or None,
            sort_order=sort_order,
        )
        sort_order += 1
        db.add(row)
        created.append(row)

    if created:
        await db.commit()
        for row in created:
            await db.refresh(row)

    return created


def search_technology_catalog(query: str) -> list[TechnologyCatalogItemResponse]:
    return [
        TechnologyCatalogItemResponse(
            id=item.id,
            name=item.name,
            category=item.category,
            docs_url=item.docs_url,
            icon_slug=item.icon_slug,
            summary=item.summary,
            usage_hint=item.usage_hint,
        )
        for item in search_catalog(query)
    ]


async def format_project_stack_context(
    db: AsyncSession,
    project_id: UUID,
) -> str:
    result = await db.execute(
        select(ProjectTechnology)
        .where(ProjectTechnology.project_id == project_id)
        .order_by(
            ProjectTechnology.category.asc(),
            ProjectTechnology.sort_order.asc(),
        )
    )
    rows = result.scalars().all()
    if not rows:
        return ""

    lines = ["Selected technology stack:"]
    current_category: TechnologyCategory | None = None
    for row in rows:
        if row.category != current_category:
            current_category = row.category
            label = CATEGORY_LABELS.get(current_category, current_category.value)
            lines.append(f"\n{label}:")
        catalog = get_catalog_item(row.catalog_id)
        name = catalog.name if catalog else row.catalog_id
        rationale = f" — {row.rationale}" if row.rationale else ""
        lines.append(f"- {name}{rationale}")
    return "\n".join(lines)
