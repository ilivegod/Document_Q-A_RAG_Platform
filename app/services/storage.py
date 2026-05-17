"""Cloudflare R2 object storage service.

Abstracts all storage operations behind a clean interface. In production,
files live in R2. In development (when R2_BUCKET_NAME is empty), operations
fall back to local disk so dev works without R2 credentials.

The S3-compatible API means we can use aioboto3 (async boto3) with
Cloudflare's endpoint URL as a drop-in.

Key design choices:
- Presigned URLs for serving PDFs (5-minute TTL). The frontend fetches
  the PDF directly from R2, not proxied through the API server. This
  keeps serving fast and cheap.
- Download-to-tempfile for parsing. The Celery worker downloads the file
  to a temp path, parses it, then deletes the temp file. PyMuPDF and
  python-docx need a real file path, not a stream.
- Storage key format: {user_id}/{document_id}{extension}. Namespaced by
  user so it's easy to audit or bulk-delete a user's files if needed.
"""
import logging
import tempfile
from pathlib import Path

import aioboto3
from botocore.config import Config

from app.config import settings

logger = logging.getLogger(__name__)


def _is_r2_configured() -> bool:
    return bool(settings.r2_bucket_name and settings.r2_endpoint_url)


def _session():
    return aioboto3.Session(
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
    )


def _client_kwargs() -> dict:
    return {
        "service_name": "s3",
        "endpoint_url": settings.r2_endpoint_url,
        # R2 doesn't use AWS regions but boto3 requires one.
        "region_name": "auto",
        "config": Config(signature_version="s3v4"),
    }


def make_storage_key(user_id: str, document_id: str, extension: str) -> str:
    """Build the R2 object key for a document file.

    Format: {user_id}/{document_id}{extension}
    e.g. "abc-123/def-456.pdf"
    """
    return f"{user_id}/{document_id}{extension}"


async def upload_file(local_path: str, storage_key: str) -> None:
    """Upload a file from local_path to R2 at storage_key.

    No-op if R2 is not configured (dev mode).
    """
    if not _is_r2_configured():
        logger.debug("R2 not configured, skipping upload (dev mode)")
        return

    async with _session().client(**_client_kwargs()) as s3:
        await s3.upload_file(
            Filename=local_path,
            Bucket=settings.r2_bucket_name,
            Key=storage_key,
        )
    logger.info("Uploaded to R2: %s", storage_key)


async def download_to_tempfile(storage_key: str, suffix: str) -> str:
    """Download an R2 object to a temporary local file. Returns the temp path.

    Caller is responsible for deleting the temp file after use.

    In dev mode (R2 not configured), storage_key is treated as a local path
    and returned as-is — no temp file created.
    """
    if not _is_r2_configured():
        logger.debug("R2 not configured, treating key as local path (dev mode)")
        return storage_key

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_path = tmp.name
    tmp.close()

    async with _session().client(**_client_kwargs()) as s3:
        await s3.download_file(
            Bucket=settings.r2_bucket_name,
            Key=storage_key,
            Filename=tmp_path,
        )
    logger.info("Downloaded from R2: %s → %s", storage_key, tmp_path)
    return tmp_path


async def delete_file(storage_key: str) -> None:
    """Delete an object from R2.

    Best-effort — logs on failure but doesn't raise. This mirrors the
    local-file cleanup pattern where missing files are silently ignored.

    No-op if R2 is not configured.
    """
    if not _is_r2_configured():
        return

    try:
        async with _session().client(**_client_kwargs()) as s3:
            await s3.delete_object(
                Bucket=settings.r2_bucket_name,
                Key=storage_key,
            )
        logger.info("Deleted from R2: %s", storage_key)
    except Exception:
        logger.exception("Failed to delete R2 object: %s", storage_key)


async def generate_presigned_url(storage_key: str, expires_in: int = 300) -> str | None:
    """Generate a presigned URL for a document. TTL defaults to 5 minutes.

    Returns None if R2 is not configured — callers fall back to the
    /documents/{id}/file proxy endpoint in that case.
    """
    if not _is_r2_configured():
        return None

    async with _session().client(**_client_kwargs()) as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.r2_bucket_name,
                "Key": storage_key,
            },
            ExpiresIn=expires_in,
        )
    return url