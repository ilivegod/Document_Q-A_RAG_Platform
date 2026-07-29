"""Non-destructive merge of LLM requirement extraction into existing rows."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.requirement import Requirement, RequirementCategory, RequirementStatus


class ExtractedRequirementItem(BaseModel):
    stable_id: str = Field(description="Stable id like REQ-001")
    title: str
    description: str
    category: str
    priority: str = "unknown"
    acceptance_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    source_citation_indexes: list[int] = Field(default_factory=list)


class ExtractedOpenQuestion(BaseModel):
    title: str
    description: str
    source_citation_indexes: list[int] = Field(default_factory=list)


class RequirementsExtractionResult(BaseModel):
    requirements: list[ExtractedRequirementItem] = Field(default_factory=list)
    open_questions: list[ExtractedOpenQuestion] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


@dataclass
class ExtractMergeSummary:
    added: int = 0
    updated: int = 0
    preserved: int = 0


class ChunkLike(Protocol):
    id: Any
    doc_id: Any
    page_num: int | None
    content: str | None


def normalize_title(title: str) -> str:
    return " ".join((title or "").lower().split())


def chunk_source_ref(chunk: ChunkLike) -> dict[str, Any]:
    return {
        "document_id": str(chunk.doc_id),
        "chunk_id": str(chunk.id),
        "page": (chunk.page_num or 0) + 1,
        "excerpt": (chunk.content or "")[:300],
    }


def source_refs_from_indexes(
    indexes: list[int],
    chunks: list,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for idx in indexes:
        if 1 <= idx <= len(chunks):
            refs.append(chunk_source_ref(chunks[idx - 1]))
    return refs


def next_numeric_stable_id(existing_ids: set[str], prefix: str) -> str:
    max_num = 0
    for sid in existing_ids:
        if not sid.startswith(f"{prefix}-"):
            continue
        try:
            max_num = max(max_num, int(sid.split("-")[-1]))
        except ValueError:
            continue
    return f"{prefix}-{max_num + 1:03d}"


def merge_extraction_into_requirements(
    existing: list[Requirement],
    result: RequirementsExtractionResult,
    *,
    project_id: UUID,
    chunks: list,
) -> tuple[list[Requirement], list[Requirement], ExtractMergeSummary]:
    """Merge LLM extraction into existing requirements without wiping reviewed work.

    Returns (added_rows, updated_rows, summary).

    - New items are inserted as proposed.
    - Proposed items matching by stable_id (or title) are updated.
    - Confirmed / rejected items are left unchanged.
    - Existing items missing from the extraction are never deleted.
    """
    from app.services.requirements import _map_category, _map_priority

    summary = ExtractMergeSummary()
    added_rows: list[Requirement] = []
    updated_rows: list[Requirement] = []

    by_stable: dict[str, Requirement] = {}
    by_title: dict[str, Requirement] = {}
    open_by_title: dict[str, Requirement] = {}
    used_stable_ids: set[str] = set()

    for req in existing:
        used_stable_ids.add(req.stable_id)
        by_stable[req.stable_id] = req
        key = normalize_title(req.title)
        if req.category == RequirementCategory.OPEN_QUESTION:
            open_by_title[key] = req
        else:
            by_title[key] = req

    sort_order = max((req.sort_order for req in existing), default=-1) + 1

    for item in result.requirements:
        source_refs = source_refs_from_indexes(item.source_citation_indexes, chunks)
        title_key = normalize_title(item.title)
        match = by_stable.get(item.stable_id) or by_title.get(title_key)

        if match is not None and match.category == RequirementCategory.OPEN_QUESTION:
            match = None

        if match is None:
            stable_id = item.stable_id
            if stable_id in used_stable_ids:
                stable_id = next_numeric_stable_id(used_stable_ids, "REQ")
            req = Requirement(
                project_id=project_id,
                stable_id=stable_id,
                title=item.title,
                description=item.description,
                category=_map_category(item.category),
                priority=_map_priority(item.priority),
                status=RequirementStatus.PROPOSED,
                acceptance_criteria=item.acceptance_criteria or [],
                assumptions=item.assumptions or [],
                source_refs=source_refs,
                sort_order=sort_order,
            )
            sort_order += 1
            used_stable_ids.add(stable_id)
            by_stable[stable_id] = req
            by_title[title_key] = req
            added_rows.append(req)
            summary.added += 1
            continue

        if match.status in (RequirementStatus.CONFIRMED, RequirementStatus.REJECTED):
            summary.preserved += 1
            continue

        match.title = item.title
        match.description = item.description
        match.category = _map_category(item.category)
        match.priority = _map_priority(item.priority)
        match.acceptance_criteria = item.acceptance_criteria or []
        match.assumptions = item.assumptions or []
        match.source_refs = source_refs
        by_title[title_key] = match
        updated_rows.append(match)
        summary.updated += 1

    for q in result.open_questions:
        source_refs = source_refs_from_indexes(q.source_citation_indexes, chunks)
        title_key = normalize_title(q.title)
        match = open_by_title.get(title_key)

        if match is None:
            stable_id = next_numeric_stable_id(used_stable_ids, "Q")
            req = Requirement(
                project_id=project_id,
                stable_id=stable_id,
                title=q.title,
                description=q.description,
                category=RequirementCategory.OPEN_QUESTION,
                status=RequirementStatus.PROPOSED,
                source_refs=source_refs,
                sort_order=sort_order,
            )
            sort_order += 1
            used_stable_ids.add(stable_id)
            open_by_title[title_key] = req
            added_rows.append(req)
            summary.added += 1
            continue

        if match.status in (RequirementStatus.CONFIRMED, RequirementStatus.REJECTED):
            summary.preserved += 1
            continue

        match.title = q.title
        match.description = q.description
        match.source_refs = source_refs
        updated_rows.append(match)
        summary.updated += 1

    return added_rows, updated_rows, summary
