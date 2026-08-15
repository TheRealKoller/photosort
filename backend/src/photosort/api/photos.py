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
from photosort.models import (
    CriterionScoringRun,
    Photo,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    User,
)
from photosort.thumbnails import variant_path

# Bewusste Abweichung vom Router-Level-dependencies=[Depends(get_current_user)]-Muster aus
# projects.py/opencloud.py (Architektur-Review-Fund): jeder Endpunkt hier braucht das tatsaechliche
# User-Objekt (fuer die eigene Bewertung/den Datenzugriff), nicht nur die Auth-Pruefung als reinen
# Torwaechter - deshalb current_user als normaler Depends()-Parameter statt Router-weiter
# dependencies-Liste. Sicherheitswirkung ist identisch (jeder Endpunkt bleibt auth-pflichtig).
router = APIRouter(tags=["photos"])


class RatingFilter(enum.StrEnum):
    UNRATED = "unrated"
    SUGGESTED = "suggested"
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
    Rating-Zeile. `reason` ist regelbasiert aus duplicate_of abgeleitet (Akzeptanzkriterium der
    Spec), nicht separat in PhotoScore gespeichert.

    "top_pick"/`category` sind mit specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
    backfill.md entfallen: PhotoScore.suggested_status wird seitdem "praktisch nur noch REJECTED"
    gesetzt (ADR 0021) - der fruehere Top-Pick-Mechanismus (Spec 0024, select_top_photos-Job) ist
    durch die neue Kriterien-/Rangfolgen-Pipeline (PhotoRanking, siehe RankingOut unten) ersetzt.
    Technische Umsetzungsentscheidung des developer-Agenten (von der Spec explizit an dieser
    Stelle delegiert): statt `reason` um einen dritten Wert ("Rang-Vorschlag") zu erweitern, lebt
    die Rangfolgen-Information in einem eigenen, additiven `PhotoOut.ranking`-Feld - strukturell
    sauberer getrennt, da "Top-N-Kandidat einer Partition" kein Duplikat-/Qualitaets-Ausschuss-
    Urteil ist, sondern eine andere Art von Information (Kuratierungs-Kontext statt
    Ausschluss-Begruendung)."""

    status: RatingStatus
    reason: Literal["duplicate", "low_quality"]
    duplicate_of: int | None
    sharpness: float
    exposure: float
    cluster_key: str | None
    computed_at: datetime


class RankingOut(BaseModel):
    """Kuratierungs-Kontext eines Fotos aus der Kriterien-/Rangfolgen-Pipeline
    (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md) - nur gesetzt, wenn das
    Foto Teil des per `top_n_per_category` abgefragten Top-N-Ergebnisses ist (siehe
    list_photos unten). Getrennt von SuggestionOut, siehe dessen Docstring."""

    cluster_key: str
    category_key: str
    rank_score: float
    rank_position: int


class PhotoOut(BaseModel):
    id: int
    relative_path: str
    taken_at: datetime
    ratings: list[RatingOut]
    suggestion: SuggestionOut | None
    ranking: RankingOut | None = None


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
    elif rating_status is RatingFilter.SUGGESTED:
        # Bildet dieselbe Regel wie has_suggestion in _to_photo_out als SQL-Praedikat nach
        # (Architektur-Abschnitt, specs/features/0027-vorgeschlagene-fotos-filterbar-anzeigen.md):
        # kein eigenes Rating des anfragenden Nutzers UND PhotoScore.suggested_status gesetzt.
        # Bewusst keine gemeinsame Codebasis mit has_suggestion (ORM-Query vs. Objekt-Praedikat) -
        # Konsistenz wird stattdessen ueber den Paritaets-Test in test_api_photos.py sichergestellt.
        base = base.join(PhotoScore, PhotoScore.photo_id == Photo.id).where(
            own_rating.id.is_(None), PhotoScore.suggested_status.is_not(None)
        )
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


def _suggestion_reason(score: PhotoScore) -> Literal["duplicate", "low_quality"]:
    return "duplicate" if score.duplicate_of is not None else "low_quality"


def _to_suggestion_out(score: PhotoScore) -> SuggestionOut:
    return SuggestionOut(
        status=score.suggested_status,  # type: ignore[arg-type]  # caller already checked not None
        reason=_suggestion_reason(score),
        duplicate_of=score.duplicate_of,
        sharpness=score.sharpness,
        exposure=score.exposure,
        cluster_key=score.cluster_key,
        computed_at=score.computed_at,
    )


def _to_photo_out(
    photo: Photo, current_user_id: int, ranking: PhotoRanking | None = None
) -> PhotoOut:
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
        ranking=(
            RankingOut(
                cluster_key=ranking.cluster_key,
                category_key=ranking.category_key,
                rank_score=ranking.rank_score,
                rank_position=ranking.rank_position,
            )
            if ranking is not None
            else None
        ),
    )


async def _latest_successful_criterion_scoring_run_id(
    session: AsyncSession, project_id: int
) -> int | None:
    return (
        await session.execute(
            select(CriterionScoringRun.id)
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _top_n_per_category_photo_ids(
    session: AsyncSession, project_id: int, current_user_id: int, top_n: int
) -> tuple[list[int], int | None]:
    """Kategorie-Kuratierung + Backfill (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
    backfill.md): liefert je Partition (cluster_key x category_key) des LETZTEN erfolgreichen
    CriterionScoringRun die besten `top_n` nach rank_position, serverseitig um vom aktuellen
    Nutzer REJECTED-bewertete Fotos gefiltert. Backfill ist dabei reiner Query-Effekt (kein
    Server-Code "rueckt aktiv nach", ADR 0021 Punkt 4): row_number() wird ERST NACH dem Ausschluss
    der abgelehnten Fotos berechnet, ein abgelehntes Foto rueckt darin also automatisch fuer das
    naechste, bisher nicht gezeigte Foto derselben Partition Platz."""
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        return [], None

    own_rejection = aliased(Rating)
    ranked = (
        select(
            PhotoRanking.photo_id,
            PhotoRanking.cluster_key,
            PhotoRanking.category_key,
            PhotoRanking.rank_position,
            func.row_number()
            .over(
                partition_by=(PhotoRanking.cluster_key, PhotoRanking.category_key),
                order_by=PhotoRanking.rank_position,
            )
            .label("rn"),
        )
        .select_from(PhotoRanking)
        .outerjoin(
            own_rejection,
            and_(
                own_rejection.photo_id == PhotoRanking.photo_id,
                own_rejection.user_id == current_user_id,
                own_rejection.status == RatingStatus.REJECTED,
            ),
        )
        .where(
            PhotoRanking.criterion_scoring_run_id == latest_run_id,
            own_rejection.id.is_(None),
        )
        .subquery()
    )
    result = await session.execute(
        select(ranked.c.photo_id)
        .where(ranked.c.rn <= top_n)
        .order_by(ranked.c.cluster_key, ranked.c.category_key, ranked.c.rank_position)
    )
    return [row[0] for row in result.all()], latest_run_id


async def _rankings_by_photo_id(
    session: AsyncSession, criterion_scoring_run_id: int, photo_ids: list[int]
) -> dict[int, PhotoRanking]:
    if not photo_ids:
        return {}
    result = await session.execute(
        select(PhotoRanking).where(
            PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
            PhotoRanking.photo_id.in_(photo_ids),
        )
    )
    return {row.photo_id: row for row in result.scalars()}


@router.get("/projects/{project_id}/photos", response_model=PhotoListOut)
async def list_photos(
    project_id: int,
    rating_status: RatingFilter | None = None,
    # Kategorie-Kuratierung + Backfill (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
    # backfill.md): serverseitig deklarativ begrenzt (Field(ge=1, le=10), analog zum bisherigen
    # top_n_per_cluster-Muster aus Spec 0024) - Robustheits-/Ressourcen-Kriterium, kein
    # Sicherheitskriterium (Security-Abschnitt der Spec). Wenn gesetzt, ersetzt dieser
    # Query-Modus rating_status vollstaendig (eigenstaendige Kuratierungs-Ansicht, siehe UI/UX-
    # Abschnitt der Spec: eigene Route /curate statt einer Kombination mit dem bestehenden
    # Grid-Filter) - limit/offset werden in diesem Modus ignoriert, da der volle Partitions-Pool
    # (N x Partitionsanzahl) fuer ein Zwei-Personen-Familienprojekt naturgemaess klein bleibt.
    top_n_per_category: int | None = Query(None, ge=1, le=10),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoListOut:
    await _get_project_or_404(project_id, session)

    if top_n_per_category is not None:
        ids, criterion_scoring_run_id = await _top_n_per_category_photo_ids(
            session, project_id, current_user.id, top_n_per_category
        )
        photos_by_id = await _photos_by_id(session, ids)
        rankings_by_id = (
            await _rankings_by_photo_id(session, criterion_scoring_run_id, ids)
            if criterion_scoring_run_id is not None
            else {}
        )
        items = [
            _to_photo_out(photos_by_id[photo_id], current_user.id, rankings_by_id.get(photo_id))
            for photo_id in ids
        ]
        return PhotoListOut(items=items, total=len(items))

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
