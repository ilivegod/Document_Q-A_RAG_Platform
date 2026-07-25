from uuid import UUID

from limits import parse as parse_limit
from pydantic import BaseModel, Field, create_model
from sqlalchemy import select

from app.agent.context import AgentContext
from app.agent.registry import (
    GET_PAGE_CONTENT,
    KEYWORD_SEARCH,
    LIST_USER_DOCUMENTS,
    SEARCH_DOCUMENTS,
    WEB_RESEARCH,
    ToolSpec,
)
from app.agent.web_agent import format_findings_for_tool_message, run_web_agent
from app.config import settings
from app.dependencies.rate_limit import WEB_RESEARCH_LIMIT, limiter
from app.models.document import Document
from app.models.user import UserTier
from app.services.retrieval import (
    get_page_content,
    hybrid_search,
    similarity_search,
)
_WEB_RESEARCH_LIMIT_ITEM = parse_limit(WEB_RESEARCH_LIMIT)

_TOOL_ALLOWED_KEYS: dict[str, set[str]] = {
    SEARCH_DOCUMENTS: {"query", "k", "document_id"},
    KEYWORD_SEARCH: {"query", "k", "document_id"},
    GET_PAGE_CONTENT: {"document_id", "page_number"},
    WEB_RESEARCH: {"query", "prefer"},
}


def sanitize_tool_arguments(
    tool_name: str,
    arguments: dict | None,
    ctx: AgentContext,
) -> dict:
    """Normalize LLM tool-call payloads before invoking handlers."""
    args = dict(arguments or {})

    # Some models/bindings nest args under a literal "kwargs" key.
    for _ in range(3):
        if "kwargs" in args and isinstance(args.get("kwargs"), dict):
            nested = args.pop("kwargs")
            args = {**nested, **args}
        else:
            break
    args.pop("kwargs", None)

    if "page" in args and "page_number" not in args:
        args["page_number"] = args.pop("page")

    allowed = _TOOL_ALLOWED_KEYS.get(tool_name)
    if allowed:
        args = {k: v for k, v in args.items() if k in allowed}

    if tool_name in (SEARCH_DOCUMENTS, KEYWORD_SEARCH, GET_PAGE_CONTENT):
        if not args.get("document_id") and ctx.document_id:
            args["document_id"] = str(ctx.document_id)

    return args


def build_args_schema(spec: ToolSpec) -> type[BaseModel]:
    """Build a Pydantic args schema for LangChain StructuredTool."""
    props = spec.parameters.get("properties", {})
    required = set(spec.parameters.get("required", []))
    type_map = {"string": str, "integer": int, "number": float, "boolean": bool}
    fields: dict = {}

    for name, meta in props.items():
        json_type = meta.get("type", "string")
        py_type = type_map.get(json_type, str)
        desc = meta.get("description", "")
        if name in required:
            fields[name] = (py_type, Field(..., description=desc))
        elif "default" in meta:
            fields[name] = (py_type, Field(default=meta["default"], description=desc))
        else:
            fields[name] = (py_type | None, Field(default=None, description=desc))

    model_name = "".join(part.capitalize() for part in spec.name.split("_")) + "Args"
    if not fields:
        return create_model(model_name)
    return create_model(model_name, **fields)


async def _search_documents(
    ctx: AgentContext,
    query: str,
    k: int = 5,
    document_id: str | None = None,
) -> str:
    doc_uuid = UUID(document_id) if document_id else ctx.document_id
    chunks = await similarity_search(
        question=query,
        db=ctx.db,
        user_id=ctx.user_id,
        document_id=doc_uuid,
        project_id=ctx.project_id,
        k=min(k, 10),
    )
    ctx.collected_chunks.extend(chunks)
    if not chunks:
        return "No matching chunks found."
    lines = []
    for i, c in enumerate(chunks, 1):
        page = (c.page_num or 0) + 1
        preview = c.content[:300].replace("\n", " ")
        lines.append(f"[{i}] page {page}: {preview}...")
    return f"Found {len(chunks)} chunks:\n" + "\n".join(lines)


async def _keyword_search(
    ctx: AgentContext,
    query: str,
    k: int = 5,
    document_id: str | None = None,
) -> str:
    doc_uuid = UUID(document_id) if document_id else ctx.document_id
    chunks = await hybrid_search(
        question=query,
        db=ctx.db,
        user_id=ctx.user_id,
        document_id=doc_uuid,
        project_id=ctx.project_id,
        k=min(k, 10),
    )
    ctx.collected_chunks.extend(chunks)
    if not chunks:
        return "No keyword matches found."
    lines = []
    for i, c in enumerate(chunks, 1):
        page = (c.page_num or 0) + 1
        preview = c.content[:300].replace("\n", " ")
        lines.append(f"[{i}] page {page}: {preview}...")
    return f"Found {len(chunks)} chunks (hybrid search):\n" + "\n".join(lines)


async def _get_page_content(
    ctx: AgentContext,
    page_number: int,
    document_id: str | None = None,
) -> str:
    doc_uuid = UUID(document_id) if document_id else ctx.document_id
    if doc_uuid is None:
        return "document_id is required when not in a single-document chat."
    text = await get_page_content(
        db=ctx.db,
        user_id=ctx.user_id,
        document_id=doc_uuid,
        page_number=page_number,
    )
    if not text:
        return f"No content on page {page_number}."
    return f"Page {page_number} content:\n{text[:4000]}"


async def _list_user_documents(ctx: AgentContext) -> str:
    query = select(Document).where(Document.user_id == ctx.user_id)
    if ctx.project_id is not None:
        query = query.where(Document.project_id == ctx.project_id)
    result = await ctx.db.execute(query.order_by(Document.created_at.desc()))
    docs = result.scalars().all()
    if not docs:
        return "No documents uploaded."
    lines = []
    for d in docs:
        status = d.status.value if hasattr(d.status, "value") else str(d.status)
        lines.append(f"- {d.file_name} (id={d.id}, status={status})")
    return "Your documents:\n" + "\n".join(lines)


async def _web_research(
    ctx: AgentContext,
    query: str,
    prefer: str = "auto",
) -> str:
    # Ensure document grounding before web — auto-search if the model skipped it.
    if not ctx.collected_chunks:
        await _search_documents(ctx, query=query, k=5)

    if not ctx.collected_chunks:
        return (
            "No matching content found in uploaded documents for this topic. "
            "Web search is only available to supplement topics that appear in the user's files."
        )

    limit_key = f"web-research:{ctx.user_id}"
    allowed = limiter.limiter.hit(_WEB_RESEARCH_LIMIT_ITEM, limit_key)
    if not allowed:
        return "Daily web research limit reached. Try again tomorrow."

    if not settings.mcp_web_enabled:
        return "Web search is disabled (MCP_WEB_ENABLED=false)."

    summary, findings, sub_steps = await run_web_agent(query, prefer=prefer)
    ctx.collected_web_sources.extend(findings)
    ctx.last_web_sub_steps = sub_steps
    if findings:
        return format_findings_for_tool_message(findings)
    return summary


async def execute_tool(
    ctx: AgentContext,
    tool_name: str,
    arguments: dict,
) -> str:
    args = sanitize_tool_arguments(tool_name, arguments, ctx)
    if tool_name == SEARCH_DOCUMENTS:
        return await _search_documents(ctx, **args)
    if tool_name == KEYWORD_SEARCH:
        return await _keyword_search(ctx, **args)
    if tool_name == GET_PAGE_CONTENT:
        return await _get_page_content(ctx, **args)
    if tool_name == LIST_USER_DOCUMENTS:
        return await _list_user_documents(ctx)
    if tool_name == WEB_RESEARCH:
        return await _web_research(ctx, **args)
    return f"Unknown tool: {tool_name}"


def build_tool_specs(tier: UserTier) -> list[ToolSpec]:
    from app.agent.registry import tools_for_tier

    allowed = tools_for_tier(tier)
    all_specs: list[ToolSpec] = [
        ToolSpec(
            name=SEARCH_DOCUMENTS,
            description=(
                "Semantic search over the user's documents. "
                "Use for conceptual questions and paraphrased queries."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "k": {"type": "integer", "description": "Number of chunks", "default": 5},
                    "document_id": {
                        "type": "string",
                        "description": "Optional document UUID to scope search",
                    },
                },
                "required": ["query"],
            },
            handler=_search_documents,
            min_tier=UserTier.FREE,
        ),
        ToolSpec(
            name=KEYWORD_SEARCH,
            description=(
                "Hybrid keyword + semantic search for exact terms, dates, names, or phrases."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 5},
                    "document_id": {"type": "string"},
                },
                "required": ["query"],
            },
            handler=_keyword_search,
            min_tier=UserTier.PRO,
        ),
        ToolSpec(
            name=GET_PAGE_CONTENT,
            description=(
                "Fetch full text of a specific page (1-indexed). "
                "Use when the user asks what is on page N. "
                "document_id is optional in single-document chat."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "1-indexed page number",
                    },
                    "document_id": {
                        "type": "string",
                        "description": "Document UUID (optional in single-document chat)",
                    },
                },
                "required": ["page_number"],
            },
            handler=_get_page_content,
            min_tier=UserTier.PRO,
        ),
        ToolSpec(
            name=LIST_USER_DOCUMENTS,
            description="List all documents the user has uploaded with IDs and status.",
            parameters={"type": "object", "properties": {}},
            handler=_list_user_documents,
            min_tier=UserTier.FREE,
        ),
        ToolSpec(
            name=WEB_RESEARCH,
            description=(
                "Search the web to supplement a document-grounded answer. "
                "Automatically searches documents first. Use when a term or concept from "
                "the files (e.g. 'critical thinking') needs external explanation. "
                "Never for weather, news, or topics not in the user's files."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Web search query"},
                    "prefer": {
                        "type": "string",
                        "enum": ["auto", "wikipedia", "duckduckgo"],
                        "default": "auto",
                        "description": "Preferred search provider",
                    },
                },
                "required": ["query"],
            },
            handler=_web_research,
            min_tier=UserTier.PRO,
        ),
    ]
    return [s for s in all_specs if s.name in allowed]
