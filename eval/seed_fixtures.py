#!/usr/bin/env python3
"""Seed eval fixture: user, project, and processed sample document."""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.document import Document, Document_Status
from app.models.project import PipelineStage, Project, ProjectStatus, ProjectType
from app.models.user import User, UserTier
from app.services.pipeline import process_document
from app.utils.register import get_password_hash
from eval.fixture_content import write_agency_sample_docx
from eval.paths import (
    EVAL_PROJECT_NAME,
    EVAL_USER_EMAIL,
    FIXTURES_DIR,
    FIXTURE_DOCX_NAME,
)
from eval.state import load_fixture_state, save_fixture_state

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def _get_or_create_eval_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == EVAL_USER_EMAIL))
    user = result.scalar_one_or_none()
    if user is not None:
        user.is_approved = True
        user.email_verified = True
        user.tier = UserTier.PRO
        await db.commit()
        await db.refresh(user)
        return user

    user = User(
        username="eval_harness",
        email=EVAL_USER_EMAIL,
        hashed_password=get_password_hash("eval-harness-password-not-for-production"),
        tier=UserTier.PRO,
        email_verified=True,
        is_approved=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _get_or_create_eval_project(db: AsyncSession, user: User) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.user_id == user.id,
            Project.name == EVAL_PROJECT_NAME,
        )
    )
    project = result.scalar_one_or_none()
    if project is not None:
        return project

    project = Project(
        user_id=user.id,
        name=EVAL_PROJECT_NAME,
        client_name="Acme Corp",
        description="Automated RAG eval harness fixture project",
        project_type=ProjectType.CLIENT,
        status=ProjectStatus.ACTIVE,
        pipeline_stage=PipelineStage.LEAD,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def _delete_existing_eval_documents(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(Document).where(
            Document.user_id == user_id,
            Document.project_id == project_id,
            Document.file_name == FIXTURE_DOCX_NAME,
        )
    )
    for doc in result.scalars().all():
        await db.delete(doc)
    await db.commit()


async def _create_and_process_document(
    db: AsyncSession,
    user: User,
    project: Project,
    fixture_path: Path,
) -> Document:
    doc_id = uuid.uuid4()
    stored_name = f"{doc_id}.docx"
    dest = UPLOAD_DIR / stored_name
    dest.write_bytes(fixture_path.read_bytes())

    document = Document(
        id=doc_id,
        user_id=user.id,
        project_id=project.id,
        file_name=FIXTURE_DOCX_NAME,
        file_type=".docx",
        file_path=str(dest),
        status=Document_Status.UPLOADED,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    await process_document(str(document.id))

    await db.refresh(document)
    if document.status != Document_Status.READY:
        raise RuntimeError(
            f"Fixture document failed processing (status={document.status.value})"
        )
    return document


async def _list_chunk_ids(db: AsyncSession, document_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        text("SELECT id FROM chunk WHERE doc_id = :doc_id ORDER BY chunk_index"),
        {"doc_id": str(document_id)},
    )
    return [str(row[0]) for row in result.fetchall()]


async def seed_fixtures(force: bool = False) -> dict:
    existing = load_fixture_state()
    if existing and not force:
        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine)
        async with session_factory() as db:
            doc = await db.get(Document, uuid.UUID(existing["document_id"]))
            if doc and doc.status == Document_Status.READY:
                await engine.dispose()
                print("Fixture already seeded; use --force to re-seed.")
                return existing
        await engine.dispose()

    fixture_path = FIXTURES_DIR / FIXTURE_DOCX_NAME
    write_agency_sample_docx(fixture_path)

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)

    async with session_factory() as db:
        user = await _get_or_create_eval_user(db)
        project = await _get_or_create_eval_project(db, user)
        if force:
            await _delete_existing_eval_documents(db, user.id, project.id)
        document = await _create_and_process_document(db, user, project, fixture_path)
        chunk_ids = await _list_chunk_ids(db, document.id)

    await engine.dispose()

    state = {
        "user_id": str(user.id),
        "project_id": str(project.id),
        "document_id": str(document.id),
        "chunk_ids": chunk_ids,
        "fixture_path": str(fixture_path),
    }
    save_fixture_state(state)
    print(f"Seeded eval fixture: {len(chunk_ids)} chunks, document {document.id}")
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed eval harness fixtures")
    parser.add_argument("--force", action="store_true", help="Re-ingest fixture document")
    args = parser.parse_args()
    asyncio.run(seed_fixtures(force=args.force))


if __name__ == "__main__":
    main()
