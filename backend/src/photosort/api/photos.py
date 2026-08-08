from __future__ import annotations

import enum
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from photosort.api.deps import get_current_user, get_session
from photosort.config import settings
from photosort.models import Photo, PhotoCategory, PhotoScore, Project, Rating, RatingStatus, User
from photosort.thumbnails import variant_path

# Bewusste Abweichung vom Router-Level-dependencies=[Depends(get_current_user)]-Muster aus
# projects.py/opencloud.py (Architektur-Review-Fund): jeder Endpunkt hier braucht das tatsaechliche
# User-Objekt (fuer die eigene Bewertung/den Datenzugriff), nicht nur die Auth-Pruefung als reinen
# Torwaechter - deshalb current_user als normaler Depends()-Parameter statt Router-weiter
# dependencies-Liste. Sicherheitswirkung ist identisch (jeder Endpunkt bleibt auth-pflichtig).
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


class SuggestionOut(BaseModel):
    """Automatischer Vorschlag aus PhotoScore, bewusst getrennt von RatingOut/ratings[] (ADR 0006,
    decisions/0006-local-scoring-datamodel.md) - ein Vorschlag ist strukturell nie eine
    Rating-Zeile. `reason` ist regelbasiert aus duplicate_of/suggested_status abgeleitet
    (Akzeptanzkriterium der Spec), nicht separat in PhotoScore gespeichert. "top_pick" (additiv,
    specs/features/0024-top-photo-selection-category-mix.md) gilt fuer jeden ALBUM_WORTHY-Vorschlag
    - dieser Status wird ausschliesslich vom neuen select_top_photos-Job gesetzt, Phase A setzt
    praktisch nur REJECTED (siehe models.py::PhotoScore-Docstring)."""

    status: RatingStatus
    reason: Literal["duplicate", "low_quality", "top_pick"]
    duplicate_of: int | None
    local_quality_score: float | None
    sharpness: float
    exposure: float
    cluster_key: str | None
    category: PhotoCategory | None
    computed_at: datetime


class PhotoOut(BaseModel):
    id: int
    relative_path: str
    taken_at: datetime
    ratings: list[RatingOut]
    suggestion: SuggestionOut | None


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
        .options(
            selectinload(Photo.ratings).selectinload(Rating.user),
            selectinload(Photo.score),
        )
    )
    return {photo.id: photo for photo in result.scalars()}


def _suggestion_reason(score: PhotoScore) -> Literal["duplicate", "low_quality", "top_pick"]:
    if score.suggested_status == RatingStatus.ALBUM_WORTHY:
        return "top_pick"
    return "duplicate" if score.duplicate_of is not None else "low_quality"


def _to_suggestion_out(score: PhotoScore) -> SuggestionOut:
    return SuggestionOut(
        status=score.suggested_status,  # type: ignore[arg-type]  # caller already checked not None
        reason=_suggestion_reason(score),
        duplicate_of=score.duplicate_of,
        local_quality_score=score.local_quality_score,
        sharpness=score.sharpness,
        exposure=score.exposure,
        cluster_key=score.cluster_key,
        category=score.category,
        computed_at=score.computed_at,
    )


def _to_photo_out(photo: Photo, current_user_id: int) -> PhotoOut:
    # Anzeigeregel (Akzeptanzkriterium der Spec): ein Vorschlag ist nur sichtbar, wenn (a)
    # PhotoScore.suggested_status gesetzt ist UND (b) der anfragende Nutzer noch KEINE eigene
    # Rating-Zeile fuer dieses Foto hat - unabhaengig davon, ob eine ANDERE Person das Foto schon
    # bewertet hat (eigene Bewertung hat immer Vorrang, siehe UI/UX-Abschnitt der Spec).
    has_own_rating = any(rating.user_id == current_user_id for rating in photo.ratings)
    has_suggestion = (
        photo.score is not None and photo.score.suggested_status is not None and not has_own_rating
    )
    suggestion = _to_suggestion_out(photo.score) if has_suggestion and photo.score else None
    return PhotoOut(
        id=photo.id,
        relative_path=photo.relative_path,
        taken_at=photo.taken_at,
        ratings=[
            RatingOut(user_id=r.user_id, username=r.user.username, status=r.status)
            for r in photo.ratings
        ],
        suggestion=suggestion,
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
    items = [_to_photo_out(photos_by_id[photo_id], current_user.id) for photo_id in ids]
    return PhotoListOut(items=items, total=total)


@router.get("/photos/{photo_id}/image")
async def get_photo_image(
    photo_id: int,
    # Literal["thumbnail", "display"] statt ein freier str-Parameter: FastAPI/Pydantic validiert
    # gegen genau diese Allowlist und liefert 422 fuer alles andere, BEVOR der Wert unten in eine
    # Datei-Pfadoperation einfliesst - Muss-Kriterium gegen Path-Traversal ueber den
    # variant-Parameter (specs/features/0002-manual-categorization.md, architecture/
    # 0003-securitykonzept.md).
    variant: Literal["thumbnail", "display"],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")

    path = variant_path(Path(settings.photo_cache_dir), photo.id, photo.etag, variant)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bild wird noch verarbeitet."
        )

    # Content-Type explizit gesetzt (immer JPEG, siehe thumbnails.py), nicht vom Dateisystem
    # erraten; X-Content-Type-Options verhindert MIME-Sniffing-XSS bei falsch benannten Dateien
    # (architecture/0003-securitykonzept.md).
    return FileResponse(
        path, media_type="image/jpeg", headers={"X-Content-Type-Options": "nosniff"}
    )
