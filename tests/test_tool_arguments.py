import uuid

from app.agent.context import AgentContext
from app.agent.registry import GET_PAGE_CONTENT, SEARCH_DOCUMENTS, WEB_RESEARCH
from app.agent.tools.handlers import sanitize_tool_arguments


def _ctx(document_id=None):
    return AgentContext(
        db=None,  # type: ignore[arg-type]
        user_id=uuid.uuid4(),
        document_id=document_id,
    )


def test_unwrap_nested_kwargs():
    doc_id = uuid.uuid4()
    ctx = _ctx(document_id=doc_id)
    raw = {"kwargs": {"query": "contracts", "k": 3}}
    args = sanitize_tool_arguments(SEARCH_DOCUMENTS, raw, ctx)
    assert args == {"query": "contracts", "k": 3, "document_id": str(doc_id)}


def test_page_alias_maps_to_page_number():
    doc_id = uuid.uuid4()
    ctx = _ctx(document_id=doc_id)
    args = sanitize_tool_arguments(
        GET_PAGE_CONTENT,
        {"page": 2},
        ctx,
    )
    assert args == {"page_number": 2, "document_id": str(doc_id)}


def test_strips_unknown_keys():
    ctx = _ctx()
    args = sanitize_tool_arguments(
        WEB_RESEARCH,
        {"query": "weather paris", "prefer": "duckduckgo", "kwargs": "bad"},
        ctx,
    )
    assert args == {"query": "weather paris", "prefer": "duckduckgo"}
