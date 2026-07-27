from __future__ import annotations

import enum
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from photosort.api.deps import get_current_user, get_session
from photosort.models import Photo, Project, Rating, RatingStatus, User

router = APIRouter(tags=["photos"])


class RatingFilter(enum.StrEnum):
    UNRATED = "unrated"
    FAVORITE = "favorite"
    ALBUM_WORTHY = "album_worthy"
    REJECTED = "rejected"


class RatingOut(BaseModel):
    user_id: int
    username: str
    status: RatingStatus


class PhotoOut(BaseModel):
    id: int
    relative_path: str
    taken_at: datetime
    ratings: list[RatingOut]


class PhotoListOut(BaseModel):
    items: list[PhotoOut]
    total: int


async def _get_project_or_404(project_id: int, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


async def _filtered_photo_ids(
    session: AsyncSession,
    project_id: int,
    current_user_id: int,
    rating_status: RatingFilter | None,
    limit: int,
    offset: int,
) -> tuple[list[int], int]:
    own_rating = aliased(Rating)
    base = (
        select(Photo.id)
        .where(Photo.project_id == project_id)
        .outerjoin(
            own_rating,
            and_(own_rating.photo_id == Photo.id, own_rating.user_id == current_user_id),
        )
    )
    if rating_status is RatingFilter.UNRATED:
        base = base.where(own_rating.id.is_(None))
    elif rating_status is not None:
        base = base.where(own_rating.status == RatingStatus(rating_status.value))

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    paged = base.order_by(Photo.taken_at, Photo.id).offset(offset).limit(limit)
    ids = [row[0] for row in (await session.execute(paged)).all()]
    return ids, total


async def _photos_by_id(session: AsyncSession, ids: list[int]) -> dict[int, Photo]:
    if not ids:
        return {}
    result = await session.execute(
        select(Photo)
        .where(Photo.id.in_(ids))
        .options(selectinload(Photo.ratings).selectinload(Rating.user))
    )
    return {photo.id: photo for photo in result.scalars()}


def _to_photo_out(photo: Photo) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        relative_path=photo.relative_path,
        taken_at=photo.taken_at,
        ratings=[
            RatingOut(user_id=r.user_id, username=r.user.username, status=r.status)
            for r in photo.ratings
        ],
    )


@router.get("/projects/{project_id}/photos", response_model=PhotoListOut)
async def list_photos(
    project_id: int,
    rating_status: RatingFilter | None = None,
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoListOut:
    await _get_project_or_404(project_id, session)

    ids, total = await _filtered_photo_ids(
        session, project_id, current_user.id, rating_status, limit, offset
    )
    photos_by_id = await _photos_by_id(session, ids)
    items = [_to_photo_out(photos_by_id[photo_id]) for photo_id in ids]
    return PhotoListOut(items=items, total=total)
