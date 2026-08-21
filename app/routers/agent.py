import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import AgentContext
from app.agent.orchestrator import run_agent
from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.dependencies.rate_limit import QUERY_LIMIT, get_user_id_key, limiter
from app.models.conversation import Conversation, Message, MessageRole
from app.models.document import Document
from app.models.user import User
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse, AgentStep, SuggestedAction
from app.mcp.schemas import WebFinding
from app.schemas.query import Source
router = APIRouter()
logger = logging.getLogger(__name__)

HISTORY_WINDOW = 10


async def _get_or_create_conversation(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID | None,
    project_id: UUID | None = None,
) -> Conversation:
    if document_id is None and project_id is None:
        raise HTTPException(
            status_code=400,
            detail="Provide document_id or project_id for chat",
        )

    if document_id is not None:
        result = await db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.document_id == document_id,
            )
        )
    else:
        result = await db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.project_id == project_id,
                Conversation.document_id.is_(None),
            )
        )
    conv = result.scalar_one_or_none()
    if conv is not None:
        return conv

    conv = Conversation(
        user_id=user_id,
        document_id=document_id,
        project_id=project_id,
    )
    db.add(conv)
    await db.flush()
    return conv


async def _fetch_history(
    db: AsyncSession,
    conversation_id: UUID,
) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_WINDOW)
    )
    rows = list(reversed(result.scalars().all()))
    history = []
    for msg in rows:
        if msg.role == MessageRole.ASSISTANT and not msg.has_answer:
            continue
        history.append({"role": msg.role.value, "content": msg.content})
    return history


def _chunks_to_sources(chunks: list) -> list[Source]:
    return [
        Source(
            source_type="document",
            chunk_id=str(chunk.id),
            content=chunk.content,
            page=(chunk.page_num or 0) + 1,
            bboxes=chunk.bboxes,
            page_width=chunk.page_width,
            page_height=chunk.page_height,
        )
        for chunk in chunks
    ]


def _web_findings_to_sources(findings: list[WebFinding]) -> list[Source]:
    return [
        Source(
            source_type="web",
            content=finding.snippet,
            url=finding.url or None,
            title=finding.title,
            provider=finding.provider,
        )
        for finding in findings
    ]


def _build_sources(chunks: list, web_findings: list[WebFinding]) -> list[Source]:
    return _chunks_to_sources(chunks) + _web_findings_to_sources(web_findings)


async def _resolve_project_id(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID | None,
    project_id: UUID | None,
) -> UUID | None:
    if project_id is not None:
        return project_id
    if document_id is None:
        return None
    doc = await db.get(Document, document_id)
    if doc is None or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc.project_id


async def _run_agent_query(
    body: AgentQueryRequest,
    db: AsyncSession,
    current_user: User,
) -> AgentQueryResponse:
    user_id = current_user.id
    if body.document_id is None and body.project_id is None:
        raise HTTPException(
            status_code=400,
            detail="Chat requires a project_id or document_id",
        )
    project_id = await _resolve_project_id(
        db, user_id, body.document_id, body.project_id
    )
    ctx = AgentContext(
        db=db,
        user_id=user_id,
        document_id=body.document_id,
        project_id=project_id,
    )

    conversation_id: UUID | None = body.conversation_id
    if conversation_id is not None:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = await _get_or_create_conversation(
            db, user_id, body.document_id, project_id
        )
        conversation_id = conv.id

    history: list[dict] = []
    if conversation_id is not None:
        history = await _fetch_history(db, conversation_id)

    llm_answer, agent_trace, chunks, web_findings, suggested_actions = await run_agent(
        question=body.question,
        ctx=ctx,
        tier=current_user.tier,
        chat_history=history,
    )

    sources = (
        _build_sources(chunks, web_findings)
        if llm_answer.has_answer and (chunks or web_findings)
        else []
    )
    steps = [AgentStep(**s) for s in agent_trace if s.get("tool") != "suggested_actions"]
    action_models = [SuggestedAction(**a) for a in suggested_actions]

    if conversation_id is not None:
        db.add(
            Message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=body.question,
            )
        )
        db.add(
            Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=llm_answer.answer,
                sources=[s.model_dump() for s in sources] if sources else None,
                has_answer=llm_answer.has_answer,
                agent_trace=agent_trace,
            )
        )
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await db.commit()

    return AgentQueryResponse(
        question=body.question,
        answer=llm_answer.answer,
        has_answer=llm_answer.has_answer,
        sources=sources,
        conversation_id=conversation_id,
        agent_steps=steps,
        suggested_actions=action_models,
    )


async def _stream_agent_events(
    body: AgentQueryRequest,
    db: AsyncSession,
    current_user: User,
):
    """SSE generator: tool steps then final answer."""
    user_id = current_user.id
    project_id = await _resolve_project_id(
        db, user_id, body.document_id, body.project_id
    )
    ctx = AgentContext(
        db=db,
        user_id=user_id,
        document_id=body.document_id,
        project_id=project_id,
    )

    conversation_id: UUID | None = body.conversation_id
    if conversation_id is not None:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Conversation not found'})}\n\n"
            return
    else:
        conv = await _get_or_create_conversation(
            db, user_id, body.document_id, project_id
        )
        conversation_id = conv.id
        await db.flush()

    history = await _fetch_history(db, conversation_id) if conversation_id else []

    yield f"data: {json.dumps({'type': 'start', 'conversation_id': str(conversation_id)})}\n\n"

    llm_answer, agent_trace, chunks, web_findings, suggested_actions = await run_agent(
        question=body.question,
        ctx=ctx,
        tier=current_user.tier,
        chat_history=history,
    )

    for step in agent_trace:
        if step.get("tool") == "suggested_actions":
            continue
        yield f"data: {json.dumps({'type': 'tool_step', 'step': step})}\n\n"

    sources = (
        _build_sources(chunks, web_findings)
        if llm_answer.has_answer and (chunks or web_findings)
        else []
    )

    # Stream cumulative answer text for progressive UI render
    words = llm_answer.answer.split(" ")
    cumulative = ""
    for i, word in enumerate(words):
        cumulative += (" " if i > 0 else "") + word
        if i % 3 == 0 or i == len(words) - 1:
            yield f"data: {json.dumps({'type': 'token', 'content': cumulative})}\n\n"

    payload = {
        "type": "done",
        "answer": llm_answer.answer,
        "has_answer": llm_answer.has_answer,
        "sources": [s.model_dump() for s in sources],
        "conversation_id": str(conversation_id),
        "agent_steps": [s for s in agent_trace if s.get("tool") != "suggested_actions"],
        "suggested_actions": suggested_actions,
    }
    yield f"data: {json.dumps(payload)}\n\n"

    db.add(
        Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=body.question,
        )
    )
    db.add(
        Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=llm_answer.answer,
            sources=[s.model_dump() for s in sources] if sources else None,
            has_answer=llm_answer.has_answer,
            agent_trace=agent_trace,
        )
    )
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=datetime.now(timezone.utc))
    )
    await db.commit()


@router.post("/documents/agent/query", response_model=AgentQueryResponse)
@limiter.limit(QUERY_LIMIT, key_func=get_user_id_key)
async def agent_query(
    request: Request,
    body: AgentQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.stream:
        return StreamingResponse(
            _stream_agent_events(body, db, current_user),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    return await _run_agent_query(body, db, current_user)
