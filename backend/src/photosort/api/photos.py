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
from photosort.categories import (
    CATEGORY_REGISTRY,
    LOCAL_CATEGORY_SIGNALS,
    is_known_category,
)
from photosort.config import settings
from photosort.criteria import CRITERIA_REGISTRY, is_landmark_candidate
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    User,
)
from photosort.thumbnails import variant_path
from photosort.worker import (
    _remote_category_candidates,
    derive_photo_category,
    reassign_photo_category,
)

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 7:
# einzige bewusste Ausnahme vom sonst in api/*.py durchgehaltenen Prinzip, keine worker.py-
# Funktionen direkt zu importieren (api/projects.py-Kommentar bei _count_remote_category_
# candidates) - die Spec verlangt hier ausdruecklich einen SYNCHRONEN Aufruf im selben API-Request
# ("sofortige Wirkung", kein Hintergrund-Job), reassign_photo_category/derive_photo_category/
# _remote_category_candidates sind dafuer die einzig richtige, bereits bestehende
# Implementierungsstelle (DRY mit run_criterion_scoring - beide Stellen leiten die Kategorie
# ueber denselben Codepfad ab). Der Import selbst ist unproblematisch, da worker.py mediapipe/
# tensorflow/onnxruntime ausschliesslich lokal innerhalb der jeweiligen build_*()-Funktionen
# importiert (nicht auf Modulebene) - kein zusaetzliches Gewicht im uvicorn-Importpfad.

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
    (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md). Seit
    specs/features/0040-bewertungsdetails-info-popover.md auch im Standard-Listing-Zweig befuellt
    (vorher nur bei `top_n_per_category`), nicht mehr nur, wenn das Foto Teil des abgefragten
    Top-N-Ergebnisses ist. Getrennt von SuggestionOut, siehe dessen Docstring."""

    cluster_key: str
    category_key: str
    rank_score: float
    rank_position: int
    # Groesse der GESAMTEN Cluster x Kategorie-Partition (nicht nur der angeforderten top_n),
    # fuer "Rang M von N" im Info-Popover (specs/features/0040-bewertungsdetails-info-popover.md,
    # Architektur-Abschnitt) - lauf-global berechnet (siehe _partition_sizes), nicht
    # nutzerspezifisch gefiltert.
    partition_size: int


class CriterionScoreOut(BaseModel):
    """Ein einzelner, bereits normierter Kriterien-Wert eines Fotos
    (specs/features/0040-bewertungsdetails-info-popover.md) - exponiert die seit Spec 0037
    bereits vorhandene, aber bisher nicht ueber die API sichtbare `PhotoCriterionScore`-Tabelle.
    `display_name` kommt aus criteria.py::CRITERIA_REGISTRY (Fallback auf `criterion_key`, falls
    ein DB-Wert nicht im Register steht - defensiv gegen Registry-/Daten-Drift). `category_eligible`
    spiegelt dasselbe Registry-Attribut (Fallback False) und ist die alleinige Grundlage der
    Frontend-Gliederung in die Bloecke "Qualitaet"/"Kategorien"
    (specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
    Architektur-Entscheidung 1) - bewusst kein zweites, redundantes Anzeige-Attribut."""

    criterion_key: str
    display_name: str
    value: float
    source: CriterionSource
    category_eligible: bool


class FineLabelOut(BaseModel):
    """Ein frei formuliertes, auf einen kanonischen Eintrag aufgeloestes Feinlabel
    (specs/features/0289-feste-kategorien.md, Umsetzungsschritt 6 - ersetzt
    `RemoteCategoryLabelOut`): immer eine Liste (0-2 Eintraege), nie None, analog
    `ratings`/`criterion_scores`. Reine ZUSATZINFORMATION am Foto, keine Kategoriequelle.

    `confidence` ist ersatzlos entfallen (ADR 0049 Entwurfsentscheidung 7). `display_name` und
    `raw_label` sind freier, extern erzeugter LLM-Text - sie sind beim Uebernehmen der
    Modellantwort zeichensaniert worden (remote_classification.py::_sanitize_label_text) und
    duerfen im Frontend ausschliesslich als regulaerer Textknoten gerendert werden."""

    canonical_key: str
    display_name: str
    raw_label: str
    provider: str


class CategoryCandidateOut(BaseModel):
    """Die fuer DIESES Foto tatsaechlich gueltige Kategorie-Kandidatenmenge - lokal qualifizierende
    Signale (Wert >= der jeweiligen `category_presence_threshold`) UND die remote genannten
    Kategorien zusammen (UI/UX-Abschnitt der Spec 0055, "Datenbedarf"-Hinweis: verhindert, dass das
    Frontend die Praesenz-Schwellenlogik selbst nachbilden muesste).

    specs/features/0289-feste-kategorien.md, Umsetzungsschritt 6: `category_key` ist seit dieser
    Spec IMMER ein Key des festen Sets (categories.py), und das frueher mitgelieferte `score`-Feld
    ist ersatzlos entfallen - die Auswahl entscheidet die feste Vorrangreihenfolge, nicht mehr ein
    Zahlenvergleich, und eine angezeigte Zahl ohne Wirkung waere irrefuehrend. `provider` ist nur
    bei `origin="remote"` gesetzt."""

    category_key: str
    origin: Literal["local", "remote"]
    provider: str | None = None


class CloudVisionStatus(enum.StrEnum):
    """specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-
    attempt-fehler-persistierung.md Punkt 1: einer von sechs Zustaenden je Foto x
    CloudVisionPhase, zur Anfragezeit aus bereits vorhandenen Signalen abgeleitet (siehe
    _cloud_vision_status_out)."""

    NOT_RUN = "not_run"
    NOT_CANDIDATE = "not_candidate"
    CONSENT_DISABLED = "consent_disabled"
    ERROR = "error"
    NO_RESULT = "no_result"
    RESULT = "result"


class CloudVisionStatusOut(BaseModel):
    """Ein Eintrag von `PhotoOut.cloud_vision_status` (immer genau zwei, einer je
    CloudVisionPhase, feste Reihenfolge [landmark, remote_category])."""

    phase: CloudVisionPhase
    status: CloudVisionStatus
    # Nur bei status == ERROR gesetzt.
    error_message: str | None = None
    # Nur bei status in {ERROR, NO_RESULT, RESULT} gesetzt.
    attempted_at: datetime | None = None


class PhotoOut(BaseModel):
    id: int
    relative_path: str
    taken_at: datetime
    ratings: list[RatingOut]
    suggestion: SuggestionOut | None
    ranking: RankingOut | None = None
    # Immer eine Liste, nie None (analog `ratings`) - best-effort: enthaelt nur Kriterien, fuer
    # die tatsaechlich eine PhotoCriterionScore-Zeile existiert, sortiert nach
    # CRITERIA_REGISTRY-Reihenfolge (specs/features/0040-bewertungsdetails-info-popover.md).
    criterion_scores: list[CriterionScoreOut]
    # specs/features/0289-feste-kategorien.md: immer eine Liste (0-2 Eintraege), nie None.
    fine_labels: list[FineLabelOut]
    # Die remote ermittelte Kategorie dieses Fotos (PhotoCategoryClassification.category_key),
    # None ohne Klassifikations-Zeile. Bewusst getrennt von `ranking.category_key`: dort steht die
    # im Lauf tatsaechlich VERGEBENE Kategorie (lokal + remote + Override), hier nur der
    # Remote-Beitrag.
    remote_category: str | None = None
    # Dauerhafte manuelle Uebersteuerung (PhotoScore.category_override), None ohne aktiven
    # Override.
    category_override: str | None = None
    # Siehe CategoryCandidateOut-Docstring - sortiert in Registry-Anzeigereihenfolge (dieselbe
    # Reihenfolge wie GET /categories), damit die Liste ueberall im Produkt gleich aussieht.
    category_candidates: list[CategoryCandidateOut]
    # specs/features/0058-cloud-vision-status-transparenz.md: immer genau 2 Eintraege (einer je
    # CloudVisionPhase), feste Reihenfolge [landmark, remote_category] - siehe
    # _cloud_vision_status_out.
    cloud_vision_status: list[CloudVisionStatusOut]


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
            # Photo.criterion_scores ist bereits eine ORM-Relationship (models.py) - eager laden
            # statt eines Query pro Foto (specs/features/0040-bewertungsdetails-info-popover.md,
            # Architektur-Abschnitt).
            selectinload(Photo.criterion_scores),
            # specs/features/0055, umbenannt in specs/features/0289-feste-kategorien.md: analog
            # eager geladen, inkl. der verknuepften fine_labels-Zeile (fuer canonical_key/
            # display_name, ohne N+1-Query pro Feinlabel).
            selectinload(Photo.fine_labels).selectinload(PhotoFineLabel.fine_label),
            # specs/features/0289-feste-kategorien.md: Grundlage von PhotoOut.remote_category/
            # category_candidates und des Remote-Erfolgssignals in _cloud_vision_status_out.
            selectinload(Photo.category_classification),
            # specs/features/0058-cloud-vision-status-transparenz.md: eager geladen (analog
            # criterion_scores/fine_labels oben), kein zusaetzliches Query je Foto
            # fuer _cloud_vision_status_out. Photo.landmark_detection war zuvor NIE eager geladen
            # (kein bestehender Aufrufer griff bislang darauf zu) - ohne dieses selectinload
            # loest photo.landmark_detection ein Lazy-Load aus und schlaegt im Async-Kontext mit
            # MissingGreenlet fehl (Review-verifiziert).
            selectinload(Photo.landmark_detection),
            selectinload(Photo.cloud_vision_errors),
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


def _criterion_scores_out(photo: Photo) -> list[CriterionScoreOut]:
    """Sortiert die vorhandenen PhotoCriterionScore-Zeilen des Fotos nach CRITERIA_REGISTRY-
    Reihenfolge (Akzeptanzkriterium 7 der Spec); Zeilen, deren criterion_key nicht in der
    Registry steht (Registry-/Daten-Drift), landen ans Ende, sortiert nach ihrem eigenen Key fuer
    ein deterministisches Ergebnis, und bekommen den rohen Key als display_name-Fallback sowie
    `category_eligible=False` (identisch zum Registry-Default des Attributs). Fehlt
    umgekehrt ein Registry-Kriterium in der DB, taucht es einfach nicht auf (kein Platzhalter,
    Akzeptanzkriterium 8)."""
    registry_order = {key: index for index, key in enumerate(CRITERIA_REGISTRY)}
    sorted_scores = sorted(
        photo.criterion_scores,
        key=lambda s: (registry_order.get(s.criterion_key, len(registry_order)), s.criterion_key),
    )
    return [
        CriterionScoreOut(
            criterion_key=s.criterion_key,
            display_name=(
                CRITERIA_REGISTRY[s.criterion_key].display_name
                if s.criterion_key in CRITERIA_REGISTRY
                else s.criterion_key
            ),
            value=s.value,
            source=s.source,
            category_eligible=(
                CRITERIA_REGISTRY[s.criterion_key].category_eligible
                if s.criterion_key in CRITERIA_REGISTRY
                else False
            ),
        )
        for s in sorted_scores
    ]


def _fine_labels_out(photo: Photo) -> list[FineLabelOut]:
    return [
        FineLabelOut(
            canonical_key=row.fine_label.canonical_key,
            display_name=row.fine_label.display_name,
            raw_label=row.raw_label,
            provider=row.provider,
        )
        for row in photo.fine_labels
    ]


def _category_candidates_out(photo: Photo) -> list[CategoryCandidateOut]:
    """specs/features/0055, UI/UX-Abschnitt "Datenbedarf"; auf das feste Set umgestellt in
    specs/features/0289-feste-kategorien.md: die fuer DIESES Foto gueltige Kandidatenmenge - lokal
    qualifizierende Signale (criteria.py-Schwelle erreicht, ueber LOCAL_CATEGORY_SIGNALS auf einen
    Set-Key abgebildet) UND die remote genannten Set-Keys.

    Die Liste ist reine ERKLAERUNG in der Oberflaeche ("das hat das System erkannt"): sie
    beschraenkt seit Spec 0289 NICHT mehr, was manuell uebersteuert werden darf - dafuer gilt die
    staerkere Whitelist gegen das geschlossene Set (`is_known_category` in
    `set_category_override`). Sortiert in Registry-Anzeigereihenfolge; ein Key, der lokal UND
    remote Kandidat ist, erscheint einmal mit `origin="local"` (die lokale Herkunft ist die
    spezifischere Aussage: sie beruht auf einem nachvollziehbaren Messwert)."""
    origins: dict[str, tuple[Literal["local", "remote"], str | None]] = {}

    classification = photo.category_classification
    if classification is not None:
        for category_key in classification.detected_categories:
            origins[category_key] = ("remote", classification.provider)

    values = {score.criterion_key: score.value for score in photo.criterion_scores}
    for category_key, criterion_keys in LOCAL_CATEGORY_SIGNALS.items():
        for criterion_key in criterion_keys:
            definition = CRITERIA_REGISTRY.get(criterion_key)
            if definition is None or definition.category_presence_threshold is None:
                continue
            if values.get(criterion_key, 0.0) >= definition.category_presence_threshold:
                origins[category_key] = ("local", None)
                break

    return [
        CategoryCandidateOut(
            category_key=key, origin=origins[key][0], provider=origins[key][1]
        )
        for key in CATEGORY_REGISTRY
        if key in origins
    ]


def _cloud_vision_status_for_phase(
    phase: CloudVisionPhase,
    *,
    success: tuple[CloudVisionStatus, datetime] | None,
    error: PhotoCloudVisionError | None,
    consent_enabled: bool,
    is_candidate: bool,
) -> CloudVisionStatusOut:
    """Wendet die 5-Raenge-Prioritaets-Kaskade fuer EINE Phase an (specs/features/0058-cloud-
    vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-fehler-persistierung.md
    Punkt 1) - erster zutreffender Rang gewinnt, kein Merge mehrerer gleichzeitig zutreffender
    Signale. `success` ist bereits das fertige (Status, attempted_at)-Paar der jeweils
    aufrufenden Phase (RESULT/NO_RESULT unterscheiden sich nur bei landmark, siehe
    _cloud_vision_status_out)."""
    if success is not None:
        status, attempted_at = success
        return CloudVisionStatusOut(phase=phase, status=status, attempted_at=attempted_at)
    if error is not None:
        return CloudVisionStatusOut(
            phase=phase,
            status=CloudVisionStatus.ERROR,
            error_message=error.error_message,
            attempted_at=error.attempted_at,
        )
    if not consent_enabled:
        return CloudVisionStatusOut(phase=phase, status=CloudVisionStatus.CONSENT_DISABLED)
    if not is_candidate:
        return CloudVisionStatusOut(phase=phase, status=CloudVisionStatus.NOT_CANDIDATE)
    return CloudVisionStatusOut(phase=phase, status=CloudVisionStatus.NOT_RUN)


def _cloud_vision_status_out(photo: Photo, project: Project) -> list[CloudVisionStatusOut]:
    """specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-
    attempt-fehler-persistierung.md: read-time abgeleiteter Cloud-Vision-Status fuer beide Phasen,
    IMMER genau 2 Eintraege in fester Reihenfolge [landmark, remote_category] (unabhaengig von
    DB-/Insert-Reihenfolge von photo.cloud_vision_errors). Erwartet, dass `photo` bereits ueber
    selectinload(Photo.criterion_scores/landmark_detection/category_classification/
    cloud_vision_errors) eager geladen ist (siehe _photos_by_id) - kein Lazy-Load hier."""
    errors_by_phase = {row.phase: row for row in photo.cloud_vision_errors}

    # Landmark: Erfolgssignal ist entweder eine tatsaechliche Detection ("gefunden", RESULT) oder
    # eine PhotoCriterionScore(criterion_key="landmark")-Zeile ohne Detection ("nichts gefunden",
    # NO_RESULT eigener Sonderfall, ADR 0035 Punkt 1) - die PRAESENZ der Score-Zeile entscheidet,
    # nicht ihr konkreter Wert (Datenanomalie-Regressionstest der Teststrategie).
    landmark_score = next(
        (score for score in photo.criterion_scores if score.criterion_key == "landmark"), None
    )
    landmark_success: tuple[CloudVisionStatus, datetime] | None = None
    if photo.landmark_detection is not None:
        landmark_success = (CloudVisionStatus.RESULT, photo.landmark_detection.computed_at)
    elif landmark_score is not None:
        landmark_success = (CloudVisionStatus.NO_RESULT, landmark_score.computed_at)

    # Remote-Kategorie: kein "nichts gefunden"-Fall - ein Erfolg schreibt seit
    # specs/features/0289-feste-kategorien.md immer GENAU EINE Klassifikations-Zeile, auch wenn die
    # Kategorie `nicht_erkannt` lautet und keine Feinlabels entstanden sind. Die PRAESENZ dieser
    # Zeile ist damit das Erfolgssignal (vorher: mindestens eine Feinlabel-Zeile, was einen
    # legitimen "nichts Bekanntes genannt"-Ausgang faelschlich als "nicht gelaufen" gezeigt haette).
    remote_category_success: tuple[CloudVisionStatus, datetime] | None = None
    if photo.category_classification is not None:
        remote_category_success = (
            CloudVisionStatus.RESULT,
            photo.category_classification.computed_at,
        )

    return [
        _cloud_vision_status_for_phase(
            CloudVisionPhase.LANDMARK,
            success=landmark_success,
            error=errors_by_phase.get(CloudVisionPhase.LANDMARK),
            consent_enabled=project.cloud_vision_detection_enabled,
            is_candidate=is_landmark_candidate(
                {score.criterion_key: score.value for score in photo.criterion_scores}
            ),
        ),
        _cloud_vision_status_for_phase(
            CloudVisionPhase.REMOTE_CATEGORY,
            success=remote_category_success,
            error=errors_by_phase.get(CloudVisionPhase.REMOTE_CATEGORY),
            consent_enabled=project.cloud_vision_detection_enabled,
            # Spiegelt exakt die WHERE-Klausel von worker.py::select_remote_category_candidates
            # (ADR 0035 Punkt 1) - kein PhotoScore vorhanden ODER bereits aussortiert -> kein
            # Kandidat.
            is_candidate=photo.score is not None and photo.score.suggested_status is None,
        ),
    ]


def _to_photo_out(
    photo: Photo,
    current_user_id: int,
    project: Project,
    ranking: PhotoRanking | None = None,
    partition_size: int = 0,
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
                partition_size=partition_size,
            )
            if ranking is not None
            else None
        ),
        criterion_scores=_criterion_scores_out(photo),
        fine_labels=_fine_labels_out(photo),
        remote_category=(
            photo.category_classification.category_key
            if photo.category_classification is not None
            else None
        ),
        category_override=photo.score.category_override if photo.score is not None else None,
        category_candidates=_category_candidates_out(photo),
        cloud_vision_status=_cloud_vision_status_out(photo, project),
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


async def _partition_sizes(
    session: AsyncSession, criterion_scoring_run_id: int
) -> dict[tuple[str, str], int]:
    """Groesse jeder Cluster x Kategorie-Partition eines Laufs, fuer "Rang M von N" im Info-
    Popover (specs/features/0040-bewertungsdetails-info-popover.md, Architektur-Abschnitt) - ein
    einzelner GROUP BY-Query pro list_photos-Aufruf (nicht pro Foto). Bewusst lauf-global, nicht
    nutzerspezifisch gefiltert - siehe RankingOut.partition_size-Docstring."""
    result = await session.execute(
        select(PhotoRanking.cluster_key, PhotoRanking.category_key, func.count())
        .where(PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id)
        .group_by(PhotoRanking.cluster_key, PhotoRanking.category_key)
    )
    return {(cluster_key, category_key): count for cluster_key, category_key, count in result.all()}


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


def _partition_size_for(
    ranking: PhotoRanking | None, partition_sizes: dict[tuple[str, str], int]
) -> int:
    if ranking is None:
        return 0
    return partition_sizes.get((ranking.cluster_key, ranking.category_key), 0)


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
    project = await _get_project_or_404(project_id, session)

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
        partition_sizes = (
            await _partition_sizes(session, criterion_scoring_run_id)
            if criterion_scoring_run_id is not None
            else {}
        )
        items = [
            _to_photo_out(
                photos_by_id[photo_id],
                current_user.id,
                project,
                rankings_by_id.get(photo_id),
                _partition_size_for(rankings_by_id.get(photo_id), partition_sizes),
            )
            for photo_id in ids
        ]
        return PhotoListOut(items=items, total=len(items))

    ids, total = await _filtered_photo_ids(
        session, project_id, current_user.id, rating_status, limit, offset
    )
    photos_by_id = await _photos_by_id(session, ids)
    # RankingOut wird seit specs/features/0040-bewertungsdetails-info-popover.md AUCH hier im
    # Standard-Listing-Zweig befuellt (vorher nur bei top_n_per_category, siehe Architektur-
    # Abschnitt der Spec) - Grid-/Detailansicht sollen ebenfalls Rang-Score/-Position zeigen
    # koennen, unabhaengig vom top_n_per_category-Kuratierungsmodus.
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    rankings_by_id = (
        await _rankings_by_photo_id(session, latest_run_id, ids)
        if latest_run_id is not None
        else {}
    )
    partition_sizes = (
        await _partition_sizes(session, latest_run_id) if latest_run_id is not None else {}
    )
    items = [
        _to_photo_out(
            photos_by_id[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id),
            _partition_size_for(rankings_by_id.get(photo_id), partition_sizes),
        )
        for photo_id in ids
    ]
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


class CategoryOverrideIn(BaseModel):
    """specs/features/0289-feste-kategorien.md: `category_key` muss ein Eintrag des festen
    13er-Sets sein (categories.py::CATEGORY_REGISTRY) - reine Whitelist-Mitgliedschaftspruefung
    ueber `is_known_category`, kein Praefix-/Regex-/startswith-Vergleich und keine Normalisierung
    des Eingabewerts (der Client schickt den Key exakt so zurueck, wie GET /categories ihn
    geliefert hat).

    Das ersetzt die frueher hier beschriebene foto-skopierte Existenzpruefung (Spec 0055/ADR 0032
    Punkt 6.3) und ist gegenueber ihr STRIKT STAERKER: eine geschlossene 13-Werte-Menge statt
    "irgendein fuer dieses Foto persistierter canonical_key". Die damit ebenfalls entfallene
    Cross-Photo-Isolation wird dadurch gegenstandslos - ein Set-Key ist kein fremder Fotobezug."""

    category_key: str


class CategoryOverrideOut(BaseModel):
    photo_id: int
    category_key: str


async def _get_photo_or_404(photo_id: int, session: AsyncSession) -> Photo:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    return photo


async def _current_ranking_for_photo(
    session: AsyncSession, project_id: int, photo_id: int
) -> tuple[int, PhotoRanking] | None:
    """`None`, wenn kein erfolgreicher CriterionScoringRun existiert ODER dieses Foto darin keine
    PhotoRanking-Zeile hat (409-Faelle des PUT-Endpunkts, ADR 0032 Punkt 6.3) - sonst
    `(criterion_scoring_run_id, ranking)`."""
    run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if run_id is None:
        return None
    ranking = (
        await session.execute(
            select(PhotoRanking).where(
                PhotoRanking.criterion_scoring_run_id == run_id,
                PhotoRanking.photo_id == photo_id,
            )
        )
    ).scalar_one_or_none()
    if ranking is None:
        return None
    return run_id, ranking


@router.put("/photos/{photo_id}/category-override", response_model=CategoryOverrideOut)
async def set_category_override(
    photo_id: int,
    payload: CategoryOverrideIn,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CategoryOverrideOut:
    """specs/features/0055, Akzeptanzkriterium "Manuelle Übernahme (Override) mit sofortiger
    Wirkung"; Verhaltensumkehr in specs/features/0289-feste-kategorien.md: `404` bei fehlendem
    Foto, `422` bei einem `category_key` ausserhalb des festen Sets (auch bei einem Altwert aus
    der Laufhistorie wie "unerkannt"), `409` ohne `PhotoRanking`-Zeile im aktuellen Lauf.

    AUSDRUECKLICH ERLAUBT ist seit Spec 0289 ein Set-Key, der fuer dieses Foto NIE Kandidat war
    (bisher `409`) - die Kandidatenliste ist nur noch Erklaerung, die manuelle Uebersteuerung darf
    jeden der 13 Eintraege setzen. Wirkt SOFORT im selben Request
    (`worker.py::reassign_photo_category`) - kein neuer Ranking-Algorithmus, kein voller
    Re-Scoring-Lauf."""
    photo = await _get_photo_or_404(photo_id, session)

    # Whitelist-Pruefung VOR jeder Schreibaktion (Security-Abschnitt der Spec 0289, Punkt 2) -
    # nicht erst beim Bauen der Antwort.
    if not is_known_category(payload.category_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="category_key gehoert nicht zum festen Kategorien-Set.",
        )

    current = await _current_ranking_for_photo(session, photo.project_id, photo_id)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kein aktueller Rangfolgen-Eintrag fuer dieses Foto.",
        )
    run_id, ranking = current

    await reassign_photo_category(
        session, run_id, photo_id, ranking.cluster_key, payload.category_key
    )

    score = await session.get(PhotoScore, photo_id)
    if score is not None:
        score.category_override = payload.category_key
        await session.commit()

    return CategoryOverrideOut(photo_id=photo_id, category_key=payload.category_key)


@router.delete("/photos/{photo_id}/category-override", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_override(
    photo_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """specs/features/0055, Akzeptanzkriterium "Manuelle Übernahme (Override) mit sofortiger
    Wirkung": nimmt die Uebernahme zurueck und rekonstruiert den automatisch abgeleiteten
    `category_key` ueber DIESELBE Ableitung wie der Lauf selbst
    (`worker.py::_remote_category_candidates` + `derive_photo_category`) - kein zweiter,
    driftender Rechenweg. Idempotent (`204` auch ohne aktiven Override).

    specs/features/0289-feste-kategorien.md: die Rekonstruktion braucht seit dieser Spec nur noch
    die Werte DIESES Fotos - die abgeloeste Ableitung war laufweit aggregierend und musste dafuer
    den vollstaendigen Kandidatenpool laden (ADR 0032 Punkt 6.4)."""
    await _get_photo_or_404(photo_id, session)

    score = await session.get(PhotoScore, photo_id)
    if score is None or score.category_override is None:
        return

    photo = await session.get(Photo, photo_id)
    assert photo is not None
    current = await _current_ranking_for_photo(session, photo.project_id, photo_id)
    if current is None:
        # Kein aktiver Lauf/keine Rangfolgen-Zeile (mehr) - Override trotzdem zuruecksetzen
        # (dokumentierter, sicherer Fallback), aber keine Neusortierung ohne Kontext moeglich.
        score.category_override = None
        await session.commit()
        return
    run_id, ranking = current

    criterion_values = {
        row.criterion_key: row.value
        for row in (
            await session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo_id)
            )
        ).scalars()
    }
    remote_candidates = await _remote_category_candidates(session, [photo_id])
    new_category_key = derive_photo_category(
        criterion_values, remote_candidates.get(photo_id, [])
    )

    await reassign_photo_category(session, run_id, photo_id, ranking.cluster_key, new_category_key)

    score.category_override = None
    await session.commit()
