"""
DhanRadar — Admin news CRUD router (B56-f4).

Every route is gated by ``RequireAdmin()`` (404 to ALL non-admins, including
authenticated non-admins — surface-hiding, mirrors B26 admin pattern).

Workflow: admins create items as drafts (is_active=False), review them, and
publish via PATCH {"is_active": true}.  This replaces hand-edited curated seed
rows as the operations workflow for news.news_items.

Idempotency-Key (non-neg #6) is deferred for this slice:
  - POST is conflict-guarded on canonical_url (second POST with same URL → 409)
    so duplicate-submit safety holds without a key.
  - Tracked as a B56-f4 residual for a future hardening pass (same class as B26/B30).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from dhanradar.audit.service import record_admin_action
from dhanradar.db import get_db
from dhanradar.deps import RequireAdmin, UserContext
from dhanradar.news import service
from dhanradar.news.schemas import AdminNewsItem, CreateNewsItemRequest, UpdateNewsItemRequest
from dhanradar.news.service import DuplicateUrlError

router = APIRouter(prefix="/admin/news", tags=["admin"])


@router.get("", response_model=list[AdminNewsItem])
async def list_admin_news(
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    scope: str | None = None,
    is_active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminNewsItem]:
    """Return all news items for admin review — no recency cutoff, all provenance."""
    rows = await service.admin_list_news(
        db, scope=scope, is_active=is_active, limit=limit, offset=offset
    )
    return [AdminNewsItem.model_validate(r) for r in rows]


@router.post("", response_model=AdminNewsItem, status_code=status.HTTP_201_CREATED)
async def create_news_item(
    body: CreateNewsItemRequest,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminNewsItem:
    """Create a new news item as a draft (is_active=False).

    Conflict-guarded: same canonical_url → 409 news_url_exists.
    Audit action: create_news_item.
    """
    try:
        row = await service.create_news_item(
            db,
            title=body.title,
            source=body.source,
            canonical_url=body.canonical_url,
            category=body.category,
            scope=body.scope,
            published_at=body.published_at,
        )
    except DuplicateUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="news_url_exists",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_news_item: {exc}",
        ) from exc

    # Fire-and-forget audit — failure MUST NOT break the handler.
    await record_admin_action(
        admin_id=admin.user_id,
        action="create_news_item",
        target_type="news_item",
        target_id=row.id,
        result="success",
        request_id=getattr(request.state, "request_id", None),
    )
    return AdminNewsItem.model_validate(row)


@router.patch("/{item_id}", response_model=AdminNewsItem)
async def update_news_item(
    item_id: str,
    body: UpdateNewsItemRequest,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminNewsItem:
    """Partially update a news item.

    item_id must be a valid UUID — malformed IDs return 404 (surface-hiding,
    mirrors RequireAdmin: never 422/500 for a non-admin-visible endpoint).
    Empty body (no fields set) returns 400 no_fields_to_update.
    Audit action: update_news_item.
    """
    # Malformed UUID → 404 (surface-hiding, consistent with RequireAdmin pattern).
    try:
        uuid.UUID(item_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not_found",
        )

    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no_fields_to_update",
        )

    try:
        row = await service.update_news_item(db, item_id, **fields)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="news_item_not_found",
        ) from exc
    except DuplicateUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="news_url_exists",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_news_item: {exc}",
        ) from exc

    # Fire-and-forget audit.
    await record_admin_action(
        admin_id=admin.user_id,
        action="update_news_item",
        target_type="news_item",
        target_id=item_id,
        result="success",
        request_id=getattr(request.state, "request_id", None),
    )
    return AdminNewsItem.model_validate(row)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news_item(
    item_id: str,
    request: Request,
    admin: Annotated[UserContext, Depends(RequireAdmin())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Hard-delete a news item.

    Malformed UUID → 404 (surface-hiding).
    Missing item → 404.
    Audit action: delete_news_item.
    """
    try:
        uuid.UUID(item_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not_found",
        )

    try:
        await service.delete_news_item(db, item_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="news_item_not_found",
        ) from exc

    # Fire-and-forget audit.
    await record_admin_action(
        admin_id=admin.user_id,
        action="delete_news_item",
        target_type="news_item",
        target_id=item_id,
        result="success",
        request_id=getattr(request.state, "request_id", None),
    )
