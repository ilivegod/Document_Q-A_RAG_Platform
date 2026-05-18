import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.conversation import Conversation, Message
from app.models.document import Document
from app.models.user import User
from app.schemas.conversation import ConversationResponse, MessageResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])
logger = logging.getLogger(__name__)


async def _get_conversation_or_404(
    conversation_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Conversation:
    """Fetch a conversation, verifying it belongs to the user."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.get("", response_model=ConversationResponse | None)
async def get_conversation(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the conversation for a document, or None if it doesn't exist yet.

    The frontend calls this on document open. If None is returned, the
    frontend waits for the first user message before creating one.
    """
    # Verify the document belongs to the user.
    doc = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    if doc.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(Conversation).where(
            Conversation.user_id == current_user.id,
            Conversation.document_id == document_id,
        )
    )
    return result.scalar_one_or_none()


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a conversation for a document.

    Returns 409 if one already exists (the caller should GET first).
    The query endpoint calls this internally on the first message.
    """
    # Verify document ownership.
    doc = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    if doc.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check for existing conversation.
    existing = await db.execute(
        select(Conversation).where(
            Conversation.user_id == current_user.id,
            Conversation.document_id == document_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation already exists for this document",
        )

    user_id = current_user.id
    conv = Conversation(user_id=user_id, document_id=document_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all messages for a conversation, oldest first."""
    await _get_conversation_or_404(conversation_id, current_user.id, db)

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a conversation and all its messages.

    Called when the user clicks 'Clear conversation'. The frontend
    then creates a fresh conversation on the next message.
    """
    conv = await _get_conversation_or_404(conversation_id, current_user.id, db)
    await db.delete(conv)
    await db.commit()
    return None