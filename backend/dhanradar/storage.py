"""
DhanRadar — Cloudflare R2 object storage helper (boto3, S3-compatible).

Shared, lazily-initialised client. boto3 is imported INSIDE the factory so the
application/test process can import this module (and anything that depends on it,
e.g. the Notification share-card service) without boto3 installed — it is only
needed when an object is actually written. R2 needs `region_name="auto"` and the
account-level endpoint with the bucket passed separately (infra-notes R2 block).
"""

from __future__ import annotations

from typing import Any, Optional

from dhanradar.config import settings

_client: Any = None


class StorageNotConfigured(RuntimeError):
    """R2 credentials/endpoint are not set — callers fail-closed (no silent no-op)."""


def get_r2_client() -> Any:
    """Return (or lazily build) the shared boto3 S3 client pointed at R2."""
    global _client
    if _client is None:
        if not (settings.R2_ENDPOINT and settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY):
            raise StorageNotConfigured("R2 endpoint/credentials missing")
        import boto3  # lazy — not needed unless we actually upload

        _client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
    return _client


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    get_r2_client().put_object(
        Bucket=settings.R2_BUCKET, Key=key, Body=data, ContentType=content_type
    )


def presigned_url(key: str, expires_seconds: int = 3600) -> str:
    """A time-limited GET URL — used for PRIVATE cards (portfolio data)."""
    return get_r2_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET, "Key": key},
        ExpiresIn=expires_seconds,
    )


def public_url(key: str) -> Optional[str]:
    """A non-expiring URL via the configured public base — used for PUBLIC cards
    (mood/badge). Returns None if no public base is configured (caller then signs)."""
    base = settings.R2_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/{key}" if base else None
