import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.dependencies.rate_limit import QUERY_LIMIT, get_user_id_key, limiter
from app.models.conversation import Conversation, Message, MessageRole

from app.models.user import User
from app.schemas.query import QueryRequest, QueryResponse, Source
from app.services.qa_chain import llm_prompt
from app.services.retrieval import similarity_search

router = APIRouter()
logger = logging.getLogger(__name__)

# Sliding window size: how many messages (user + assistant combined) the
# LLM sees as prior context. N=10 means 5 full turns of back-and-forth.
HISTORY_WINDOW = 10


async def _get_or_create_conversation(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
) -> Conversation:
    """Return the existing conversation for this user+doc, or create one."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.document_id == document_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is not None:
        return conv

    conv = Conversation(user_id=user_id, document_id=document_id)
    db.add(conv)
    await db.flush()  # flush so conv.id is available; caller commits
    return conv


async def _fetch_history(
    db: AsyncSession,
    conversation_id: UUID,
) -> list[dict]:
    """Fetch the last HISTORY_WINDOW messages for the LLM prompt.

    Fetches the most recent N messages (ordered desc), then reverses so
    the oldest is first in the prompt (natural conversation order).
    Only includes assistant messages where has_answer=True — feeding
    "I don't know" turns into history adds noise.
    """
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_WINDOW)
    )
    rows = result.scalars().all()
    rows = list(reversed(rows))

    history = []
    for msg in rows:
        if msg.role == MessageRole.ASSISTANT and not msg.has_answer:
            continue
        history.append({"role": msg.role.value, "content": msg.content})
    return history


@router.post("/documents/query", response_model=QueryResponse)
@limiter.limit(QUERY_LIMIT, key_func=get_user_id_key)
async def query_document(
    request: Request,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id

    retrieved_chunks = await similarity_search(
        question=body.question,
        db=db,
        user_id=user_id,
        document_id=body.document_id,
        k=body.k,
    )

    if not retrieved_chunks:
        return QueryResponse(
            question=body.question,
            answer=(
                "No content found to search. "
                "Make sure your documents have finished processing, "
                "then try again."
            ),
            has_answer=False,
            sources=[],
        )

    # Resolve conversation. If conversation_id is provided, verify it
    # belongs to the user. If not, get-or-create based on document_id.
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
    elif body.document_id is not None:
        conv = await _get_or_create_conversation(db, user_id, body.document_id)
        conversation_id = conv.id
    else:
        conv = None

    # Fetch prior turns for the sliding window.
    history: list[dict] = []
    if conversation_id is not None:
        history = await _fetch_history(db, conversation_id)

    llm_answer = llm_prompt(body.question, retrieved_chunks, chat_history=history)

    sources = (
        [
            Source(
                chunk_id=str(chunk.id),
                content=chunk.content,
                page=(chunk.page_num or 0) + 1,
                bboxes=chunk.bboxes,
                page_width=chunk.page_width,
                page_height=chunk.page_height,
            )
            for chunk in retrieved_chunks
        ]
        if llm_answer.has_answer
        else []
    )

    # Persist the exchange to the conversation.
    if conversation_id is not None:
        question_text = body.question
        answer_text = llm_answer.answer
        answer_has = llm_answer.has_answer
        sources_json = (
            [s.model_dump() for s in sources] if llm_answer.has_answer else None
        )

        db.add(Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=question_text,
        ))
        db.add(Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=answer_text,
            sources=sources_json,
            has_answer=answer_has,
        ))

        # Bump conversation.updated_at so it sorts as most-recently-active.
        await db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.now(timezone.utc))
        )

        await db.commit()

    return QueryResponse(
        question=body.question,
        answer=llm_answer.answer,
        has_answer=llm_answer.has_answer,
        sources=sources,
        conversation_id=conversation_id,
    )