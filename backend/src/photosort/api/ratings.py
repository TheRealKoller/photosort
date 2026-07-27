from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.models import Photo, Rating, RatingStatus, User

router = APIRouter(tags=["ratings"])


class RatingUpdate(BaseModel):
    status: RatingStatus


class RatingOut(BaseModel):
    photo_id: int
    status: RatingStatus
    updated_at: datetime


async def _get_photo_or_404(photo_id: int, session: AsyncSession) -> Photo:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    return photo


async def _get_own_rating(
    session: AsyncSession, photo_id: int, user_id: int
) -> Rating | None:
    result = await session.execute(
        select(Rating).where(Rating.photo_id == photo_id, Rating.user_id == user_id)
    )
    return result.scalar_one_or_none()


@router.put("/photos/{photo_id}/rating", response_model=RatingOut)
async def set_rating(
    photo_id: int,
    payload: RatingUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RatingOut:
    await _get_photo_or_404(photo_id, session)

    # Security-Muss-Kriterium (specs/features/0002-manual-categorization.md,
    # architecture/0003-securitykonzept.md): user_id kommt ausschliesslich aus dem
    # current_user-Claim, nie aus Body/Query - sonst koennte Nutzer A per manipuliertem Request
    # die Bewertung von Nutzer B ueberschreiben (Broken Object-Level Authorization).
    rating = await _get_own_rating(session, photo_id, current_user.id)
    if rating is None:
        rating = Rating(photo_id=photo_id, user_id=current_user.id, status=payload.status)
        session.add(rating)
    else:
        rating.status = payload.status
    await session.commit()
    await session.refresh(rating)
    return RatingOut(photo_id=photo_id, status=rating.status, updated_at=rating.updated_at)


@router.delete("/photos/{photo_id}/rating", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rating(
    photo_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    await _get_photo_or_404(photo_id, session)

    rating = await _get_own_rating(session, photo_id, current_user.id)
    if rating is not None:
        await session.delete(rating)
        await session.commit()
