"""Unit tests for technology catalog and stack helpers."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.models.project_technology import TechnologyCategory, TechnologySource
from app.services.technology_catalog import (
    CATEGORY_DESCRIPTIONS,
    get_catalog_item,
    search_catalog,
)
from app.services.technology_stack import LLMStackResult, LLMStackSelection, _to_response


def test_search_catalog_matches_name():
    results = search_catalog("postgres")
    assert any(item.id == "postgresql" for item in results)


def test_get_catalog_item_unknown():
    assert get_catalog_item("missing-tech") is None


def test_catalog_items_include_summary_and_usage_hint():
    item = get_catalog_item("nextjs")
    assert item is not None
    assert item.summary
    assert item.usage_hint


def test_category_descriptions_cover_all_categories():
    for category in TechnologyCategory:
        assert category in CATEGORY_DESCRIPTIONS
        assert CATEGORY_DESCRIPTIONS[category]


def test_to_response_includes_catalog_metadata():
    catalog = get_catalog_item("nextjs")
    assert catalog is not None
    row = MagicMock()
    row.id = uuid.uuid4()
    row.project_id = uuid.uuid4()
    row.catalog_id = "nextjs"
    row.category = TechnologyCategory.FRONTEND
    row.source = TechnologySource.AI
    row.rationale = "Fits SEO landing page requirements."
    row.sort_order = 0
    row.created_at = datetime.now(timezone.utc)
    row.updated_at = datetime.now(timezone.utc)

    response = _to_response(row)
    assert response.summary == catalog.summary
    assert response.usage_hint == catalog.usage_hint
    assert response.rationale == "Fits SEO landing page requirements."


def test_llm_stack_deduplication_logic():
    selections = [
        LLMStackSelection(catalog_id="nextjs", rationale="SSR app"),
        LLMStackSelection(catalog_id="nextjs", rationale="duplicate"),
        LLMStackSelection(catalog_id="fastapi", rationale="Python API"),
    ]
    seen: set[str] = set()
    unique = []
    for selection in selections:
        if selection.catalog_id in seen:
            continue
        if get_catalog_item(selection.catalog_id) is None:
            continue
        seen.add(selection.catalog_id)
        unique.append(selection)

    assert len(unique) == 2
    assert unique[0].catalog_id == "nextjs"
    assert unique[1].catalog_id == "fastapi"


def test_llm_stack_rejects_unknown_ids():
    result = LLMStackResult(
        technologies=[
            LLMStackSelection(catalog_id="nextjs", rationale="valid"),
            LLMStackSelection(catalog_id="made-up-stack", rationale="invalid"),
        ]
    )
    valid = [
        item
        for item in result.technologies
        if get_catalog_item(item.catalog_id) is not None
    ]
    assert len(valid) == 1
    assert valid[0].catalog_id == "nextjs"
