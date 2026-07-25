"""Unit tests for technology catalog and stack helpers."""
from app.services.technology_catalog import get_catalog_item, search_catalog
from app.services.technology_stack import LLMStackResult, LLMStackSelection


def test_search_catalog_matches_name():
    results = search_catalog("postgres")
    assert any(item.id == "postgresql" for item in results)


def test_get_catalog_item_unknown():
    assert get_catalog_item("missing-tech") is None


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
