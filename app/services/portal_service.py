"""Client portal token validation and passcode checks."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client_portal_access import ClientPortalAccess
from app.models.project import Project
from app.utils.register import get_password_hash, verify_password


async def get_portal_access_by_token(
    db: AsyncSession,
    token: str,
) -> ClientPortalAccess:
    result = await db.execute(
        select(ClientPortalAccess).where(ClientPortalAccess.token == token)
    )
    access = result.scalar_one_or_none()
    if access is None or access.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Portal link not found or expired")
    return access


async def get_project_for_portal(
    db: AsyncSession,
    access: ClientPortalAccess,
) -> Project:
    project = await db.get(Project, access.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def portal_passcode_required(access: ClientPortalAccess) -> bool:
    return bool(access.passcode_hash)


def verify_portal_passcode(access: ClientPortalAccess, passcode: str | None) -> bool:
    if not access.passcode_hash:
        return True
    if not passcode:
        return False
    return verify_password(passcode, access.passcode_hash)


def hash_portal_passcode(passcode: str) -> str:
    return get_password_hash(passcode)


async def ensure_portal_access(
    db: AsyncSession,
    project_id: UUID,
) -> ClientPortalAccess:
    result = await db.execute(
        select(ClientPortalAccess).where(ClientPortalAccess.project_id == project_id)
    )
    access = result.scalar_one_or_none()
    if access is not None:
        access.revoked_at = None
        return access

    from app.services.sow_generator import generate_sow_token

    access = ClientPortalAccess(
        project_id=project_id,
        token=generate_sow_token(),
    )
    db.add(access)
    await db.flush()
    return access


async def rotate_portal_token(db: AsyncSession, project_id: UUID) -> ClientPortalAccess:
    access = await ensure_portal_access(db, project_id)
    from app.services.sow_generator import generate_sow_token

    access.token = generate_sow_token()
    access.revoked_at = None
    await db.flush()
    return access
