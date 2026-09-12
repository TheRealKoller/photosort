from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from photosort.api.deps import get_current_user, get_session
from photosort.cameras import CameraIdentity, camera_label
from photosort.config import settings
from photosort.criteria import CRITERIA_REGISTRY, is_landmark_candidate
from photosort.events import EffectiveLocation, LocationEntry, infer_locations
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    Event,
    MotifAssessmentSource,
    Photo,
    PhotoCloudVisionError,
    PhotoFineLabel,
    PhotoMotifCorrection,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    User,
)
from photosort.motif_strengths import EffectiveStrength, load_effective_strengths
from photosort.motifs import MOTIF_REGISTRY, is_motif_key
from photosort.thumbnails import variant_path

# Bewusste Abweichung vom Router-Level-dependencies=[Depends(get_current_user)]-Muster aus
# projects.py/opencloud.py: jeder Endpunkt hier braucht das tatsächliche
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
    """Automatischer Vorschlag aus PhotoScore, bewusst getrennt von RatingOut/ratings[] -
    ein Vorschlag ist strukturell nie eine Rating-Zeile. `reason` ist regelbasiert aus
    duplicate_of abgeleitet, nicht separat in PhotoScore gespeichert.

    PhotoScore.suggested_status wird "praktisch nur noch REJECTED" gesetzt; die Rangfolge trägt
    die Kriterien-Pipeline (PhotoRanking, siehe RankingOut unten). `reason` traegt ausschliesslich
    `duplicate`/`low_quality` - die Rangfolgen-Information steht in `PhotoOut.rankings`, nie
    hier."""

    status: RatingStatus
    reason: Literal["duplicate", "low_quality"]
    duplicate_of: int | None
    sharpness: float
    exposure: float
    cluster_key: str | None
    computed_at: datetime


class RankingOut(BaseModel):
    """EINE Zugehörigkeit eines Fotos zu einer Kategorie aus der Kriterien-/Rangfolgen-Pipeline.

    Auch im Standard-Listing-Zweig befüllt, nicht nur, wenn das Foto Teil des abgefragten
    Top-N-Ergebnisses ist. Getrennt von SuggestionOut, siehe dessen Docstring.

    Ein Foto hat pro Lauf GENAU EINE solche Zeile - die Partition ist allein das Event."""

    event_id: int
    rank_score: float
    rank_position: int
    # Größe der GESAMTEN Event-Partition (nicht nur der angeforderten top_n), für "Rang M von N"
    # im Info-Popover - lauf-global berechnet (siehe _partition_sizes), nicht nutzerspezifisch
    # gefiltert.
    partition_size: int
    # Der Platz dieses Fotos in der ANGEZEIGTEN Auswahl seines Events. `null`, wenn das Foto nicht
    # zur angeforderten Auswahl gehoert oder gar keine angefordert wurde.
    #
    # Die Kuratierungs-Query hat KEINEN Ablehnungsfilter, der Wert ist damit ENTWEDER `null` ODER
    # gleich `rank_position`, und nicht nutzerabhaengig.
    #
    # Trotz des Zusammenfallens NICHT mit `rank_position` zusammenlegen: jene ist die lauf-globale
    # Rangaussage des Info-Popovers (unabhaengig vom Query-Parameter), diese hier die
    # Zugehoerigkeit zur angeforderten Auswahl ("ist dieses Foto zu zeigen") - die einzige
    # Auskunft darueber, die das Frontend sonst nachbilden muesste.
    curation_position: int | None = None


class CriterionScoreOut(BaseModel):
    """Ein einzelner, bereits normierter Kriterien-Wert eines Fotos
    - exponiert die `PhotoCriterionScore`-Tabelle.
    `display_name` kommt aus criteria.py::CRITERIA_REGISTRY (Fallback auf `criterion_key`, falls
    ein DB-Wert nicht im Register steht - defensiv gegen Registry-/Daten-Drift).

    `has_presence_threshold` ist `presence_threshold is not None` der Registry (Fallback False)
    und die alleinige Grundlage der Frontend-Gliederung in die Bloecke "Qualitaet"/"Bildinhalt" -
    bewusst kein zweites, redundantes Anzeige-Attribut. Die SCHWELLE selbst geht ausdruecklich
    NICHT in die Antwort: sie ist die Vorfilter-Grenze des Cloud-Aufrufs, keine Anzeigehilfe, und
    hat in der Oberflaeche nichts zu entscheiden."""

    criterion_key: str
    display_name: str
    value: float
    source: CriterionSource
    has_presence_threshold: bool


class FineLabelOut(BaseModel):
    """Ein frei formuliertes, auf einen kanonischen Eintrag aufgeloestes Feinlabel
    Immer eine Liste (0-2 Einträge), nie None, analog
    `ratings`/`criterion_scores`. Reine ZUSATZINFORMATION am Foto, keine Kategoriequelle.

    `display_name` und
    `raw_label` sind freier, extern erzeugter LLM-Text - sie sind beim Uebernehmen der
    Modellantwort zeichensaniert worden (cloud_vision.py::_sanitize_label_text) und
    duerfen im Frontend ausschliesslich als regulaerer Textknoten gerendert werden."""

    canonical_key: str
    display_name: str
    raw_label: str
    provider: str


class CloudVisionStatus(enum.StrEnum):
    """Einer von sechs Zuständen je Foto x
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


class PhotoLocationOut(BaseModel):
    """Der Ort DIESES Fotos - in VOLLER EXIF-Präzision, ohne serverseitige Rundung (die Rundung
    auf zwei Nachkommastellen liegt allein in `ClusterPlaceOut`).

    `source` ist ein SICHERHEITSMERKMAL, kein Anzeigedetail (Muss-Kriterium des
    Sicherheitskonzepts): `GPS_CLUSTER_SPLIT_DISTANCE_METERS` begrenzt den SCHRITT zwischen zwei
    aufeinanderfolgenden Fotos, nicht den DURCHMESSER eines Clusters - ein Spaziergang in
    400-m-Schritten teilt nie und kann Kilometer ueberspannen. Eine `"derived"`-Koordinate kann
    deshalb beliebig weit von der tatsaechlichen Aufnahmestelle entfernt liegen; sie ist eine
    SCHAETZUNG, nie eine Messung. Kein kuenftiger Verbraucher (Kartenansicht, Export,
    Reverse-Geocoding) darf `derived` wie `exif` behandeln - genau dafuer existiert das Feld.

    Wird NIRGENDS persistiert."""

    lat: float
    lon: float
    source: Literal["exif", "derived"]


class EventPlaceOut(BaseModel):
    """Der bereits AUFGELÖSTE Ort des EVENTS - auf jedem Foto desselben Events identisch, `null`
    ohne jede Ortsinformation.

    Der Server liefert den fertigen ZUSTAND, nicht die Rohdaten fuer eine Rangfolge: `kind` benennt,
    welche Stufe (erkannte Sehenswuerdigkeit -> ungefaehre Koordinate -> mehrere Orte) tatsaechlich
    gilt. Das Frontend bildet die Rangfolge NICHT nach, es formatiert nur.

    `kind="multiple"` traegt STRUKTURELL keine Koordinate: es gibt den einen Ort, den sie
    repraesentieren muesste, gerade nicht.

    `landmark_name` ist freier, extern erzeugter LLM-Text (`Event.landmark_name`, ueber
    `sanitize_landmark_name` entstanden) - dieselbe Auflage wie bei `FineLabelOut.raw_label`:
    ausschliesslich als regulaerer React-Textknoten rendern, nie `dangerouslySetInnerHTML`, nie als
    HTML-String-Prop, nie in `href`/`src`/`style`, nie als React-`key`. Bricht in
    `frontend/src/pages/CurateCategoriesPage.test.tsx`, Fall
    `rendert einen HTML-artigen Sehenswuerdigkeit-Namen als Text, nicht als Markup`."""

    kind: Literal["landmark", "coordinate", "multiple"]
    landmark_name: str | None = None
    lat: float | None = None
    lon: float | None = None


class EventOut(BaseModel):
    """Das Event, zu dem dieses Foto im letzten erfolgreichen Lauf gehoert.

    Der Server liefert weiterhin KEINE fertige Ueberschrift, sondern ihre Teile: Nummer,
    Zeitspanne und den aufgeloesten Ort. Anders als die frueheren Cluster-Angaben haengt hier
    nichts mehr davon ab, welche Fotos eine Antwort gerade enthaelt - alle vier Werte stehen in
    der `events`-Zeile."""

    id: int
    position: int
    started_at: datetime
    ended_at: datetime
    place: EventPlaceOut | None = None


class CameraOut(BaseModel):
    """Die Kamera eines Fotos. `label` kommt vom SERVER (`cameras.py::camera_label`) - eine
    Stelle entscheidet, wie eine Kamera heisst, und der Wert ist dort bereits von Zeichen der
    Unicode-Kategorien Cc/Cf befreit."""

    id: int
    label: str


class MotifAssessmentOut(BaseModel):
    """Die Kopfzeile des Motiv-Staerkevektors eines Fotos - `null` heisst "noch nicht
    klassifiziert" und ist damit unterscheidbar von "nichts erkannt" (Kopfzeile vorhanden, alle
    acht Staerken niedrig). Genau dafuer gibt es dieses Feld getrennt von `motifs`: acht Nullzeilen
    sind von "nichts erkannt" nicht zu unterscheiden.

    `provider` ist `null` bei `source == "local"`. `excluded_document` ist von Hand NICHT
    korrigierbar - der Rueckweg ist allein ein erneuter Klassifizierungslauf, und die Oberflaeche
    benennt das, statt einen Schalter anzubieten."""

    source: Literal["cloud", "local"]
    provider: str | None
    excluded_document: bool
    computed_at: datetime


class MotifStrengthOut(BaseModel):
    """Die WIRKSAME Staerke eines Motivs an einem Foto samt ihrem Korrekturzustand.

    `strength` traegt die Korrektur bereits eingerechnet (motif_strengths.py::
    effective_strength_expression) - das Frontend rechnet nichts nach und kennt die Regel nicht.
    `correction` ist `null` ohne Korrekturzeile, sonst die Aussage des Nutzers; ohne dieses Feld
    waere eine Modellaussage von genau `1.0` von einer Korrektur nicht zu unterscheiden, und die
    Oberflaeche koennte das Korrekturwort nicht statt der Prozentzahl setzen."""

    # `key` wie in `MotifOut` von `GET /motifs` - dieselbe Sache heisst an beiden Stellen gleich,
    # und das Frontend schlaegt je Schluessel nach.
    key: str
    strength: float
    correction: bool | None


class PhotoOut(BaseModel):
    id: int
    relative_path: str
    # Behaelt Namen und Form und liefert seit Spec 0426 die KORRIGIERTE Zeit (ADR 0090, Punkt 1).
    # Der brechende Bedeutungswechsel ist beabsichtigt; die beiden Felder darunter treten daneben,
    # damit eine korrigierte Anzeige als korrigiert erkennbar bleibt.
    taken_at: datetime
    # Die aufgezeichnete Zeit (EXIF `DateTimeOriginal`, sonst `last_modified`).
    taken_at_original: datetime
    # Die Differenz der beiden Zeitstempel in ganzen Minuten - `0` heisst "nicht korrigiert".
    # Aus der Differenz gerechnet statt aus `ProjectCamera.offset_minutes` gelesen: so kann die
    # Anzeige nicht behaupten, eine Zeit sei um X verschoben, wenn sie es nicht ist (etwa bei
    # einem Foto, dessen Versatz beim Scan an einem Ueberlauf gescheitert ist).
    time_offset_minutes: int
    camera: CameraOut | None = None
    ratings: list[RatingOut]
    suggestion: SuggestionOut | None
    # Die Rangzeile des Fotos im letzten erfolgreichen Lauf, in beiden Query-Modi - `null`,
    # solange kein erfolgreicher Lauf existiert oder das Foto darin keine Zeile hat. EIN Feld und
    # keine Liste: ein Foto steht je Lauf in genau einer Zeile, seit die Partition allein das
    # Event ist.
    ranking: RankingOut | None = None
    # Immer eine Liste, nie None (analog `ratings`) - best-effort: enthaelt nur Kriterien, fuer
    # die tatsaechlich eine PhotoCriterionScore-Zeile existiert, sortiert nach
    # CRITERIA_REGISTRY-Reihenfolge.
    criterion_scores: list[CriterionScoreOut]
    # Immer eine Liste (0-2 Einträge), nie None.
    fine_labels: list[FineLabelOut]
    # Immer genau 2 Einträge (einer je
    # CloudVisionPhase), feste Reihenfolge [landmark, remote_category] - siehe
    # _cloud_vision_status_out.
    cloud_vision_status: list[CloudVisionStatusOut]
    # Zwei additive, OPTIONALE Felder mit Vorgabewert `null`. Beide werden einheitlich auf ALLEN
    # Lesepfaden ausgeliefert, nicht nur im Kuratierungsmodus: ein je Query-Modus divergierendes
    # `PhotoOut` waere genau die "zweite, driftende Abbildung", vor der der `rankings`-Kommentar
    # oben warnt.
    location: PhotoLocationOut | None = None
    event: EventOut | None = None
    # `motif_assessment` ist `null`, solange das Foto keinen Klassifizierungslauf gesehen hat -
    # dann ist `motifs` LEER und traegt ausdruecklich NICHT acht Eintraege mit Wert 0. Die
    # Oberflaeche zeigt an ihrer Stelle einen Satz; ein `?? 0` oder eine leere Standardliste im
    # Lesepfad machte "noch nicht klassifiziert" von "nichts erkannt" ununterscheidbar.
    motif_assessment: MotifAssessmentOut | None = None
    # Immer eine Liste, nie `null` (analog `ratings`): leer ohne Kopfzeile, sonst GENAU acht
    # Eintraege in Registry-Reihenfolge - auch bei unvollstaendigen Staerkezeilen. Die Reihenfolge
    # ist auf jedem Foto dieselbe; das Frontend schlaegt je Schluessel nach und nie ueber den Index.
    motifs: list[MotifStrengthOut]


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
    camera_id: int | None = None,
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
    if camera_id is not None:
        # SICHERHEIT (Projektgrenze): ein weiteres PRAEDIKAT neben dem vorhandenen
        # `Photo.project_id == project_id` - nie eine vorgeschaltete Aufloesung der Kamerazeile,
        # aus deren Fotos dann gelistet wird. Eine `camera_id` aus einem fremden Projekt trifft
        # damit kein Foto und ergibt eine LEERE Liste, ohne den Wert zu spiegeln.
        base = base.where(Photo.camera_id == camera_id)
    if rating_status is RatingFilter.UNRATED:
        base = base.where(own_rating.id.is_(None))
    elif rating_status is RatingFilter.SUGGESTED:
        # Bildet dieselbe Regel wie has_suggestion in _to_photo_out als SQL-Praedikat nach: kein
        # eigenes Rating des anfragenden Nutzers UND PhotoScore.suggested_status gesetzt. Bewusst
        # keine gemeinsame Codebasis mit has_suggestion (ORM-Query vs. Objekt-Praedikat) -
        # Konsistenz sichert stattdessen
        # `tests/test_api_photos.py::test_list_photos_suggested_filter_matches_has_suggestion_parity`.
        base = base.join(PhotoScore, PhotoScore.photo_id == Photo.id).where(
            own_rating.id.is_(None), PhotoScore.suggested_status.is_not(None)
        )
    elif rating_status is not None:
        base = base.where(own_rating.status == RatingStatus(rating_status.value))

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

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
            # statt eines Query pro Foto.
            selectinload(Photo.criterion_scores),
            # Analog
            # eager geladen, inkl. der verknuepften fine_labels-Zeile (fuer canonical_key/
            # display_name, ohne N+1-Query pro Feinlabel).
            selectinload(Photo.fine_labels).selectinload(PhotoFineLabel.fine_label),
            # Eager geladen (analog criterion_scores/fine_labels oben), kein zusaetzliches Query
            # je Foto fuer _cloud_vision_status_out. Ohne dieses selectinload loest
            # photo.landmark_detection einen Lazy-Load aus und schlaegt im Async-Kontext mit
            # MissingGreenlet fehl.
            selectinload(Photo.landmark_detection),
            selectinload(Photo.cloud_vision_errors),
            # Grundlage von `PhotoOut.camera`. EINE Abfrage mehr, unabhaengig von der
            # Fotoanzahl - ohne sie loeste `photo.camera` einen Lazy-Load aus und schluege im
            # Async-Kontext mit MissingGreenlet fehl.
            selectinload(Photo.camera),
            # Grundlage von `PhotoOut.motif_assessment`. Ohne dieses selectinload loeste
            # `photo.motif_assessment` einen Lazy-Load aus und schluege im Async-Kontext mit
            # MissingGreenlet fehl. Die STAERKEN kommen bewusst nicht ueber die Relationship,
            # sondern ueber `load_effective_strengths` - sonst muesste die Korrektur zweimal
            # ausgewertet werden.
            selectinload(Photo.motif_assessment),
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
    Reihenfolge; Zeilen, deren criterion_key nicht in der
    Registry steht (Registry-/Daten-Drift), landen ans Ende, sortiert nach ihrem eigenen Key fuer
    ein deterministisches Ergebnis, und bekommen den rohen Key als display_name-Fallback sowie
    `has_presence_threshold=False` (identisch zum Registry-Default). Fehlt umgekehrt ein
    Registry-Kriterium in der DB, taucht es einfach nicht auf - kein Platzhalter."""
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
            has_presence_threshold=(
                s.criterion_key in CRITERIA_REGISTRY
                and CRITERIA_REGISTRY[s.criterion_key].presence_threshold is not None
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


def _cloud_vision_status_for_phase(
    phase: CloudVisionPhase,
    *,
    success: tuple[CloudVisionStatus, datetime] | None,
    error: PhotoCloudVisionError | None,
    consent_enabled: bool,
    is_candidate: bool,
) -> CloudVisionStatusOut:
    """Wendet die 5-Ränge-Prioritäts-Kaskade für EINE Phase an - erster zutreffender Rang
    gewinnt, kein Merge mehrerer gleichzeitig zutreffender
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
    """Read-time abgeleiteter Cloud-Vision-Status für beide Phasen,
    IMMER genau 2 Eintraege in fester Reihenfolge [landmark, remote_category] (unabhaengig von
    DB-/Insert-Reihenfolge von photo.cloud_vision_errors). Erwartet, dass `photo` bereits ueber
    selectinload(Photo.criterion_scores/landmark_detection/motif_assessment/
    cloud_vision_errors) eager geladen ist (siehe _photos_by_id) - kein Lazy-Load hier."""
    errors_by_phase = {row.phase: row for row in photo.cloud_vision_errors}

    # Landmark: Erfolgssignal ist entweder eine tatsaechliche Detection ("gefunden", RESULT) oder
    # eine PhotoCriterionScore(criterion_key="landmark")-Zeile ohne Detection ("nichts gefunden",
    # NO_RESULT eigener Sonderfall) - die PRAESENZ der Score-Zeile entscheidet, nicht ihr
    # konkreter Wert.
    landmark_score = next(
        (score for score in photo.criterion_scores if score.criterion_key == "landmark"), None
    )
    landmark_success: tuple[CloudVisionStatus, datetime] | None = None
    if photo.landmark_detection is not None:
        landmark_success = (CloudVisionStatus.RESULT, photo.landmark_detection.computed_at)
    elif landmark_score is not None:
        landmark_success = (CloudVisionStatus.NO_RESULT, landmark_score.computed_at)

    # Remote-Kategorie: kein "nichts gefunden"-Fall - ein Erfolg schreibt GENAU EINE Kopfzeile
    # samt Staerkevektor, auch wenn alle acht Staerken 0 sind und keine Feinlabels entstanden
    # sind. Die PRAESENZ dieser Kopfzeile ist damit das Erfolgssignal, nicht die Existenz einer
    # Feinlabel-Zeile.
    #
    # SICHERHEITSAUFLAGE S14, auch hier: gepruaft wird auf `source='cloud'`, nicht auf das bloße
    # Vorhandensein der Kopfzeile. Der Kriterien-Lauf schreibt fuer jedes beurteilte Foto eine
    # LOKALE Kopfzeile; ein reiner Existenztest meldete jedes lokal beurteilte Foto als
    # erfolgreich cloud-klassifiziert, obwohl nie ein Cloud-Aufruf stattfand. Dieselbe Bedingung
    # steht in worker.py::select_remote_category_candidates und
    # api/projects.py::_count_remote_category_candidates.
    remote_category_success: tuple[CloudVisionStatus, datetime] | None = None
    assessment = photo.motif_assessment
    if assessment is not None and assessment.source == MotifAssessmentSource.CLOUD:
        remote_category_success = (CloudVisionStatus.RESULT, assessment.computed_at)

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
            # - kein PhotoScore vorhanden ODER bereits aussortiert -> kein
            # Kandidat.
            is_candidate=photo.score is not None and photo.score.suggested_status is None,
        ),
    ]


@dataclass(frozen=True)
class PhotoPlace:
    """Die beiden Ortsfelder EINES Fotos. `NO_PLACE` ist der Zustand "nichts bekannt" und zugleich
    die AUSFALLRICHTUNG, wenn kein Bezugslauf existiert oder ein Foto keine Rangzeile hat."""

    location: PhotoLocationOut | None = None
    event: EventOut | None = None


NO_PLACE = PhotoPlace()


def _event_place_out(event: Event) -> EventPlaceOut | None:
    """Der Ortsteil einer `events`-Zeile - `None` bei unbekanntem oder fehlendem `place_kind`.

    SICHERHEIT (M8): MITGLIEDSCHAFTSPRUEFUNG statt blindem Cast, sonst legt ein einzelner Wert
    ausserhalb des Vorrats die gesamte Listenantwort auf 500. Die drei Zweige sind einzeln
    ausgeschrieben und setzen dabei die Feldkombination ein zweites Mal durch: eine driftende
    Zeile kann so keine Koordinate unter `"multiple"` ausliefern."""
    if event.place_kind == "landmark":
        return EventPlaceOut(kind="landmark", landmark_name=event.landmark_name)
    if event.place_kind == "coordinate":
        return EventPlaceOut(kind="coordinate", lat=event.place_lat, lon=event.place_lon)
    if event.place_kind == "multiple":
        return EventPlaceOut(kind="multiple")
    return None


def _event_out(event: Event) -> EventOut:
    return EventOut(
        id=event.id,
        position=event.position,
        started_at=event.started_at,
        ended_at=event.ended_at,
        place=_event_place_out(event),
    )


def _location_out(location: EffectiveLocation | None) -> PhotoLocationOut | None:
    """`source` ist ein SICHERHEITSMERKMAL, kein Anzeigedetail: es entsteht ausschliesslich aus
    `EffectiveLocation.inferred` und wird nie aus einem anderen Signal nachgebildet."""
    if location is None:
        return None
    return PhotoLocationOut(
        lat=location.lat, lon=location.lon, source="derived" if location.inferred else "exif"
    )


async def _event_and_location_by_photo_id(
    session: AsyncSession,
    project_id: int,
    criterion_scoring_run_id: int | None,
    photos_by_id: Mapping[int, Photo],
    rankings_by_photo_id: Mapping[int, PhotoRanking],
) -> dict[int, PhotoPlace]:
    """Beide Ortsfelder aller Fotos einer Antwort aus ZWEI Abfragen - ihre Zahl ist fest und
    unabhaengig von der Zahl der Fotos.

    (a) Alle Fotos DIESES Projekts als Inferenzbasis von `events.py::infer_locations`. Die
    Bezugsmenge ist ausdruecklich nicht die Antwort und auch nicht die Kandidatenmenge: ein
    aussortiertes Foto traegt eine ebenso gueltige Koordinate. Dieselbe Funktion speist den
    Worker - zwei Herleitungen derselben Sache liefen an dem Tag auseinander, an dem eine ihre
    Bezugsmenge aendert.

    (b) Die Events der Rangzeilen dieser Antwort.

    SICHERHEIT - zwei GETRENNTE Bindungen, beide ausgeschrieben:

    * (M5) Die Inferenzbasis haengt an `Photo.project_id`. Ohne sie erbte ein Foto Koordinaten aus
      einem fremden Projekt.
    * (M1) Die Event-Abfrage haengt an `Event.criterion_scoring_run_id` - `event_id` ist ein
      GLOBALER Surrogatschluessel, und eine Id aus Projekt B identifiziert unter `/projects/A/...`
      eindeutig ein fremdes Event. Die Lauf-Id wird EINMAL PRO REQUEST aufgeloest und hierher
      durchgereicht, nie in dieser Funktion neu bestimmt; fehlt sie, bleibt `event` `None`. Die
      Ausfallrichtung ist "nichts anzeigen", nie "aus irgendeinem Lauf herleiten".

    `_photos_by_id` filtert nur nach Id und ist ausdruecklich KEINE zweite Verteidigungslinie."""
    if not photos_by_id:
        return {}

    location_rows = (
        await session.execute(
            select(Photo.id, Photo.taken_at, Photo.gps_lat, Photo.gps_lon).where(
                Photo.project_id == project_id
            )
        )
    ).all()
    effective_locations = infer_locations(
        LocationEntry(photo_id=photo_id, taken_at=taken_at, gps_lat=gps_lat, gps_lon=gps_lon)
        for photo_id, taken_at, gps_lat, gps_lon in location_rows
    )

    event_id_by_photo_id = {
        photo_id: ranking.event_id for photo_id, ranking in rankings_by_photo_id.items()
    }
    events_by_id: dict[int, EventOut] = {}
    if criterion_scoring_run_id is not None and event_id_by_photo_id:
        events_by_id = {
            event.id: _event_out(event)
            for event in (
                await session.execute(
                    select(Event).where(
                        # SICHERHEIT: das Pflichtpraedikat, siehe Docstring. Nie die Id allein.
                        Event.criterion_scoring_run_id == criterion_scoring_run_id,
                        Event.id.in_(set(event_id_by_photo_id.values())),
                    )
                )
            )
            .scalars()
            .all()
        }

    return {
        photo_id: PhotoPlace(
            location=_location_out(effective_locations.get(photo_id)),
            event=events_by_id.get(event_id_by_photo_id.get(photo_id, 0)),
        )
        for photo_id in photos_by_id
    }


def _motif_assessment_out(photo: Photo) -> MotifAssessmentOut | None:
    assessment = photo.motif_assessment
    if assessment is None:
        return None
    return MotifAssessmentOut(
        # `.value` und nicht das Enum selbst: das Antwortfeld ist ein `Literal["cloud", "local"]`,
        # damit der erzeugte OpenAPI-Typ zwei Zeichenketten nennt und nicht einen Enum-Namen, den
        # das Frontend nachbilden muesste.
        source=assessment.source.value,
        provider=assessment.provider,
        excluded_document=assessment.excluded_document,
        computed_at=assessment.computed_at,
    )


def _motifs_out(
    photo: Photo, effective: Mapping[str, EffectiveStrength] | None
) -> list[MotifStrengthOut]:
    """Die acht Motive eines Fotos in Registry-Reihenfolge - oder eine LEERE Liste, wenn das Foto
    keine Kopfzeile hat.

    Die Iteration laeuft ueber `MOTIF_REGISTRY` und nicht ueber die geladenen Zeilen: das liefert
    die Anzeigereihenfolge ohne Nachsortieren, ergaenzt eine fehlende Staerkezeile mit `0.0` (der
    Vektor ist dann trotzdem vollstaendig) und ist zugleich die Verteidigung gegen einen
    Altschluessel ausserhalb des Sets - er kann hier nicht durchfallen.

    Die leere Liste OHNE Kopfzeile ist die eigentliche Zusage: acht Eintraege mit Wert 0 waeren von
    "nichts erkannt" nicht zu unterscheiden."""
    if photo.motif_assessment is None:
        return []
    strengths = effective or {}
    return [
        MotifStrengthOut(
            key=motif_key,
            strength=strengths[motif_key].strength if motif_key in strengths else 0.0,
            correction=strengths[motif_key].correction if motif_key in strengths else None,
        )
        for motif_key in MOTIF_REGISTRY
    ]


def _to_photo_out(
    photo: Photo,
    current_user_id: int,
    project: Project,
    ranking: PhotoRanking | None = None,
    partition_sizes: Mapping[int, int] | None = None,
    curation_positions: Mapping[int, int] | None = None,
    place: PhotoPlace = NO_PLACE,
    motifs: Mapping[str, EffectiveStrength] | None = None,
) -> PhotoOut:
    """Baut die Antwortdarstellung EINES Fotos.

    SICHERHEIT - die Antwort ist eine Funktion des ANFRAGENDEN Nutzers:

    Bekommen `GET /projects/{id}/photos` oder `GET /projects/{id}/curation-candidates` je eine
    Antwort-Zwischenspeicherung, ein `ETag` oder ein `Cache-Control` ueber `no-store` hinaus, MUSS
    der Schluessel den Nutzer enthalten. Grund ist `PhotoOut.suggestion`: es wird unten genau dann
    gesetzt, wenn der anfragende Nutzer noch keine eigene Rating-Zeile hat (`has_own_rating`) -
    zwei Nutzer bekommen fuer dasselbe Foto verschiedene Antwortkoerper. Die Regel gilt in BEIDEN
    Query-Modi. Nicht theoretisch: das Frontend ist eine PWA mit Workbox
    (`registerType: 'autoUpdate'`), heute ohne `runtimeCaching` fuer API-Antworten; der
    Service-Worker-Cache ist pro Browserprofil geteilt, und das JWT liegt in `localStorage`.

    `PhotoOut.ratings[]` traegt diese Auflage AUSDRUECKLICH NICHT: die Liste enthaelt beide
    Bewertungen und ist fuer beide Anfragenden identisch - sichtbare Fremdbewertung ist gewollt.
    Tragend ist allein `suggestion`.

    `curation_position` trägt sie ebenfalls nicht (kein Ablehnungsfilter, kein
    Nutzerbezug)."""
    # Anzeigeregel: ein Vorschlag ist nur sichtbar, wenn (a) PhotoScore.suggested_status gesetzt
    # ist UND (b) der anfragende Nutzer noch KEINE eigene Rating-Zeile fuer dieses Foto hat -
    # unabhaengig davon, ob eine ANDERE Person das Foto schon bewertet hat; die eigene Bewertung
    # hat immer Vorrang.
    has_own_rating = any(rating.user_id == current_user_id for rating in photo.ratings)
    has_suggestion = (
        photo.score is not None and photo.score.suggested_status is not None and not has_own_rating
    )
    suggestion = _to_suggestion_out(photo.score) if has_suggestion and photo.score else None
    return PhotoOut(
        id=photo.id,
        relative_path=photo.relative_path,
        taken_at=photo.taken_at,
        taken_at_original=photo.taken_at_original,
        # Ganze Minuten VON KONSTRUKTION WEGEN: der Versatz ist eine Ganzzahl Minuten, beide
        # Zeitstempel entstehen aus derselben Rechnung, und die Division bleibt damit ohne Rest.
        time_offset_minutes=round((photo.taken_at - photo.taken_at_original).total_seconds() / 60),
        camera=(
            None
            if photo.camera is None
            else CameraOut(
                id=photo.camera.id,
                label=camera_label(
                    CameraIdentity(make=photo.camera.make, model=photo.camera.model)
                ),
            )
        ),
        ratings=[
            RatingOut(user_id=r.user_id, username=r.user.username, status=r.status)
            for r in photo.ratings
        ],
        suggestion=suggestion,
        ranking=(
            None
            if ranking is None
            else RankingOut(
                event_id=ranking.event_id,
                rank_score=ranking.rank_score,
                rank_position=ranking.rank_position,
                partition_size=(partition_sizes or {}).get(ranking.event_id, 0),
                curation_position=(curation_positions or {}).get(ranking.photo_id),
            )
        ),
        criterion_scores=_criterion_scores_out(photo),
        fine_labels=_fine_labels_out(photo),
        cloud_vision_status=_cloud_vision_status_out(photo, project),
        # Beide Felder kommen fertig aus `_event_and_location_by_photo_id`. Der Vorgabewert
        # `NO_PLACE` haelt die Ausfallrichtung fest: eine vergessene Durchreichung ergibt `null`,
        # nie einen falschen Ort.
        location=place.location,
        event=place.event,
        motif_assessment=_motif_assessment_out(photo),
        motifs=_motifs_out(photo, motifs),
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


async def _top_n_per_event_photo_ids(
    session: AsyncSession, project_id: int, top_n: int
) -> tuple[list[int], dict[int, int], int | None]:
    """Kuratierung ohne Backfill: liefert je Partition (`event_id`) des LETZTEN erfolgreichen
    CriterionScoringRun die Fotos mit `rank_position <= top_n`.

    KEIN ABLEHNUNGSFILTER: die Query filtert die vom anfragenden Nutzer REJECTED-bewerteten
    Fotos NICHT aus, und damit ist auch keine Fensterfunktion nötig -
    `PhotoRanking.rank_position` ist je Partition lückenlos ab 1 vergeben
    (`ranking.py::rank_photos` liefert `index + 1` über die VOLLSTÄNDIGE Partition;
    `worker.py::_build_grouping_and_rankings` ruft sie je Event auf).

    Folge: Welche Fotos die Ansicht zeigt, hängt ausschließlich vom LAUF ab, nicht vom
    Bewertungsstand des Betrachters. Ein verworfenes Foto bleibt an seiner Position und trägt
    seinen Zustand in `PhotoOut.ratings[]`.

    `top_n` wirkt JE EVENT. Rückgabe dreiteilig: die Foto-Ids in Anzeigereihenfolge, die
    `curation_position` je Foto (ohne Ablehnungsfilter identisch mit `rank_position`) und die
    Lauf-Id."""
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        return [], {}, None

    result = await session.execute(
        select(PhotoRanking.photo_id, PhotoRanking.rank_position)
        .where(
            PhotoRanking.criterion_scoring_run_id == latest_run_id,
            PhotoRanking.rank_position <= top_n,
        )
        .order_by(PhotoRanking.event_id, PhotoRanking.rank_position)
    )
    ordered_ids: list[int] = []
    curation_positions: dict[int, int] = {}
    for photo_id, rank_position in result.all():
        curation_positions[photo_id] = rank_position
        ordered_ids.append(photo_id)
    return ordered_ids, curation_positions, latest_run_id


async def _partition_sizes(session: AsyncSession, criterion_scoring_run_id: int) -> dict[int, int]:
    """Größe jeder Event-Partition eines Laufs, für "Rang M von N" im Info-Popover - ein einzelner
    GROUP BY-Query pro Aufruf (nicht pro Foto). Bewusst lauf-global, nicht nutzerspezifisch
    gefiltert - siehe RankingOut.partition_size-Docstring.

    SICHERHEIT (M1): das Lauf-Prädikat steht auch HIER - diese Zählabfrage liegt hinter `total`
    des Kandidaten-Endpunkts und ist damit eine Abfrage dieses Endpunkts wie jede andere."""
    result = await session.execute(
        select(PhotoRanking.event_id, func.count())
        .where(PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id)
        .group_by(PhotoRanking.event_id)
    )
    return {event_id: count for event_id, count in result.all()}


async def _ranking_by_photo_id(
    session: AsyncSession, criterion_scoring_run_id: int, photo_ids: list[int]
) -> dict[int, PhotoRanking]:
    """Die Rangzeile je Foto - GENAU EINE, durch den Unique-Constraint `(Lauf, Foto)` garantiert.

    `scalar_one_or_none()` je Foto waere ein Query pro Foto; die Abbildung entsteht deshalb aus
    einer Abfrage."""
    if not photo_ids:
        return {}
    result = await session.execute(
        select(PhotoRanking).where(
            PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
            PhotoRanking.photo_id.in_(photo_ids),
        )
    )
    return {row.photo_id: row for row in result.scalars()}


# SICHERHEIT - Obergrenze von `after_rank`/`offset`/`camera_id`: ein Pydantic-`int` ist
# unbeschraenkt und landet direkt im SQL-Vergleich; unter SQLite (Testlauf und lokale Entwicklung)
# wirft ein Wert jenseits von 2^63 einen `OverflowError` und damit eine 500 statt einer leeren
# Liste. Der Wert liegt weit ueber jeder realistischen Partitionsgroesse - er begrenzt einen
# Missbrauchsfall, nicht die Benutzung.
#
# Steht VOR `list_photos`, nicht erst vor dem Kandidaten-Endpunkt: `Query(...)`-Vorgabewerte
# werden zur DEFINITIONSZEIT ausgewertet, eine spaeter definierte Konstante bricht den Import.
_MAX_QUERY_POSITION = 1_000_000_000


@router.get("/projects/{project_id}/photos", response_model=PhotoListOut)
async def list_photos(
    project_id: int,
    rating_status: RatingFilter | None = None,
    # Kuratierung: serverseitig deklarativ begrenzt (Field(ge=1, le=10)) -
    # Robustheits-/Ressourcen-Kriterium, kein Sicherheitskriterium. Wenn gesetzt, ersetzt dieser
    # Query-Modus rating_status vollstaendig (eigenstaendige Kuratierungs-Ansicht) - limit/offset
    # werden in diesem Modus ignoriert, da der volle Partitions-Pool (N x Partitionsanzahl) fuer
    # ein Zwei-Personen-Familienprojekt naturgemaess klein bleibt.
    top_n_per_event: int | None = Query(None, ge=1, le=10),
    # Ohne diesen Filter kann die Oberflaeche die beiden Fotos fuer den Versatz-Vorschlag nicht
    # anbieten. `ge=1` schliesst `0` und negative Werte aus, `le` verhindert, dass ein Wert
    # jenseits von 2^63 unter SQLite einen OverflowError und damit eine 500 statt einer leeren
    # Liste erzeugt (Muster `_MAX_QUERY_POSITION`).
    camera_id: int | None = Query(None, ge=1, le=_MAX_QUERY_POSITION),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoListOut:
    project = await _get_project_or_404(project_id, session)

    if top_n_per_event is not None:
        ids, curation_positions, criterion_scoring_run_id = await _top_n_per_event_photo_ids(
            session, project_id, top_n_per_event
        )
        photos_by_id = await _photos_by_id(session, ids)
        rankings_by_id = (
            await _ranking_by_photo_id(session, criterion_scoring_run_id, ids)
            if criterion_scoring_run_id is not None
            else {}
        )
        partition_sizes = (
            await _partition_sizes(session, criterion_scoring_run_id)
            if criterion_scoring_run_id is not None
            else {}
        )
        place_by_id = await _event_and_location_by_photo_id(
            session, project_id, criterion_scoring_run_id, photos_by_id, rankings_by_id
        )
        motifs_by_id = await load_effective_strengths(session, ids)
        items = [
            _to_photo_out(
                photos_by_id[photo_id],
                current_user.id,
                project,
                rankings_by_id.get(photo_id),
                partition_sizes,
                curation_positions,
                place_by_id.get(photo_id, NO_PLACE),
                motifs_by_id.get(photo_id),
            )
            for photo_id in ids
        ]
        return PhotoListOut(items=items, total=len(items))

    ids, total = await _filtered_photo_ids(
        session, project_id, current_user.id, rating_status, limit, offset, camera_id
    )
    photos_by_id = await _photos_by_id(session, ids)
    # RankingOut wird AUCH hier im Standard-Listing-Zweig befüllt, nicht nur bei
    # top_n_per_event - Grid-/Detailansicht sollen ebenfalls Rang-Score/-Position zeigen
    # koennen, unabhaengig vom top_n_per_event-Kuratierungsmodus.
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    rankings_by_id = (
        await _ranking_by_photo_id(session, latest_run_id, ids)
        if latest_run_id is not None
        else {}
    )
    partition_sizes = (
        await _partition_sizes(session, latest_run_id) if latest_run_id is not None else {}
    )
    place_by_id = await _event_and_location_by_photo_id(
        session, project_id, latest_run_id, photos_by_id, rankings_by_id
    )
    motifs_by_id = await load_effective_strengths(session, ids)
    items = [
        _to_photo_out(
            photos_by_id[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id),
            partition_sizes,
            # Ohne angeforderte Auswahl traegt JEDE Zugehoerigkeit `curation_position = null` - es
            # gibt in diesem Modus keine Auswahl, zu der sie eine Position haben koennte.
            None,
            place_by_id.get(photo_id, NO_PLACE),
            motifs_by_id.get(photo_id),
        )
        for photo_id in ids
    ]
    return PhotoListOut(items=items, total=total)


@router.get("/projects/{project_id}/curation-candidates", response_model=PhotoListOut)
async def curation_candidates(
    project_id: int,
    # SICHERHEIT (M3): eine Objekt-Id statt eines Freitextschlüssels. `ge=1` schließt `0` und
    # negative Werte aus, `le` verhindert, dass ein Wert jenseits von 2^63 unter SQLite einen
    # `OverflowError` und damit eine 500 statt einer leeren Liste erzeugt. FastAPI spiegelt bei
    # `422` den Rohwert im `input`-Feld zurück - er wird ausschließlich als React-Textknoten
    # gerendert, nie geloggt.
    event_id: int = Query(..., ge=1, le=_MAX_QUERY_POSITION),
    after_rank: int = Query(0, ge=0, le=_MAX_QUERY_POSITION),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0, le=_MAX_QUERY_POSITION),
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT: ausgeschriebene Auth-Dependency. Dieser Router trägt bewusst KEINE
    # Router-weite
    # `dependencies`-Liste (siehe Kopfkommentar der Datei) - ein Endpunkt, der diesen Parameter
    # vergisst, waere hier STILL OEFFENTLICH: kein Fehler, keine 401, nur Daten. `current_user.id`
    # geht unveraendert an `_to_photo_out` (nie ein Platzhalter wie `0` - der liesse
    # `PhotoOut.suggestion` auch fuer laengst bewertete Fotos wieder aufblitzen).
    current_user: User = Depends(get_current_user),
) -> PhotoListOut:
    """Die weiteren Kandidaten EINER Partition, auf Abruf: die Zugehörigkeiten mit
    `rank_position > after_rank`, aufsteigend nach `rank_position`, seitenweise ueber
    `limit`/`offset`. `total` ist die RESTMENGE der Partition (`max(partition_size - after_rank,
    0)`) und damit unabhaengig von `limit`/`offset` - sonst waere der Vorrat bei einer grossen
    Kategorie wieder nur teilweise einsehbar.

    Bezugslauf ist derselbe wie in der Hauptabfrage (letzter erfolgreicher CriterionScoringRun);
    verworfene Fotos sind enthalten und tragen ihren Zustand in `ratings[]`.
    Kein erfolgreicher Lauf, ein `event_id` aus einem anderen Projekt oder einem aelteren Lauf,
    oder ein `after_rank` jenseits der Partitionsgroesse liefern
    `200` mit leerem `PhotoListOut` (`items: []` UND `total: 0`) - kein Fehler und ausdruecklich
    keine Rueckspiegelung der uebergebenen Werte in einer Fehlermeldung.

    SICHERHEIT - Projektbindung (M1): `PhotoRanking` traegt KEINE `project_id`, und `event_id` ist
    ein GLOBALER Surrogatschluessel - eine Id aus Projekt B identifiziert hier eindeutig FREMDE
    Rangzeilen. Ohne das Lauf-Praedikat liefe der Endpunkt nicht in eine erkennbar falsche
    Kollisionsmenge, sondern lieferte KOHAERENTE Fotos eines fremden Projekts: die Ausfallrichtung
    wird unauffaelliger, nicht harmloser. Die einzige Bindung an das Projekt des Pfadparameters ist
    `criterion_scoring_run_id` aus `_latest_successful_criterion_scoring_run_id(session,
    project_id)`. Dieses Praedikat steht deshalb in JEDER Abfrage dieses Endpunkts - der
    Zaehlabfrage hinter `total` (ueber `_partition_sizes`) eingeschlossen - und wird nie aus einem
    Query-Parameter abgeleitet. `_photos_by_id` filtert nur nach Id und ist ausdruecklich KEINE
    zweite Verteidigungslinie."""
    project = await _get_project_or_404(project_id, session)

    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        return PhotoListOut(items=[], total=0)

    partition_sizes = await _partition_sizes(session, latest_run_id)
    total = max(partition_sizes.get(event_id, 0) - after_rank, 0)

    rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.rank_position)
            .where(
                PhotoRanking.criterion_scoring_run_id == latest_run_id,
                PhotoRanking.event_id == event_id,
                PhotoRanking.rank_position > after_rank,
            )
            .order_by(PhotoRanking.rank_position)
            .offset(offset)
            .limit(limit)
        )
    ).all()

    ids = [photo_id for photo_id, _ in rows]
    curation_positions = {photo_id: rank_position for photo_id, rank_position in rows}
    photos_by_id = await _photos_by_id(session, ids)
    rankings_by_id = await _ranking_by_photo_id(session, latest_run_id, ids)
    place_by_id = await _event_and_location_by_photo_id(
        session, project_id, latest_run_id, photos_by_id, rankings_by_id
    )
    motifs_by_id = await load_effective_strengths(session, ids)
    items = [
        _to_photo_out(
            photos_by_id[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id),
            partition_sizes,
            curation_positions,
            place_by_id.get(photo_id, NO_PLACE),
            motifs_by_id.get(photo_id),
        )
        for photo_id in ids
    ]
    return PhotoListOut(items=items, total=total)


@router.get("/photos/{photo_id}/image")
async def get_photo_image(
    photo_id: int,
    # Literal["thumbnail", "display"] statt ein freier str-Parameter: FastAPI/Pydantic validiert
    # gegen genau diese Allowlist und liefert 422 fuer alles andere, BEVOR der Wert unten in eine
    # Datei-Pfadoperation einfließt - Muss-Kriterium gegen Path-Traversal über den
    # variant-Parameter.
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

    # SICHERHEIT: Content-Type explizit gesetzt (immer JPEG, siehe thumbnails.py), nicht vom
    # Dateisystem erraten; X-Content-Type-Options verhindert MIME-Sniffing-XSS bei falsch
    # benannten Dateien.
    return FileResponse(
        path, media_type="image/jpeg", headers={"X-Content-Type-Options": "nosniff"}
    )


async def _get_photo_or_404(photo_id: int, session: AsyncSession) -> Photo:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    return photo


class MotifCorrectionIn(BaseModel):
    """SICHERHEIT (S5): der Body traegt AUSSCHLIESSLICH `applies`.

    Kein `user_id`, `photo_id`, `motif_key`, `strength` oder `updated_at` im Eingabeschema -
    Massenzuweisung ist strukturell ausgeschlossen statt im Handler herausgefiltert. Ein Feld,
    ueber das ein Client eine Staerke setzen koennte, hebt die Unterscheidung zwischen
    Modellaussage und Korrektur auf, und ein `user_id` im Body liesse Nutzer A unter dem Namen von
    B schreiben. Ein spaeter ergaenztes Feld bricht in
    tests/test_api_motif_corrections.py::TestTheRequestBody."""

    applies: bool


class MotifCorrectionOut(BaseModel):
    photo_id: int
    motif_key: str
    applies: bool


def _validated_motif_key(motif_key: str) -> str:
    """SICHERHEIT (S4): reine Mitgliedschaftspruefung im geschlossenen Achter-Schluesselraum, VOR
    jeder Schreib- und Loeschaktion, fuer `PUT` UND `DELETE`.

    Kein `startswith`, kein Regex, keine Normalisierung des Eingabewerts - der Client schickt den
    Schluessel exakt so zurueck, wie `GET /motifs` ihn geliefert hat. `EXCLUSION_KEY` ist kein
    gueltiger Wert und kann ueber diese Pruefung nicht hereinkommen: `is_motif_key` sieht
    ausschliesslich in `MOTIF_REGISTRY`, und dort steht er nicht.

    Angriffsmodell: ein erratener oder aus der Laufhistorie bekannter Schluessel. Untersagte
    Alternative ist eine auf die vorhandenen Staerkezeilen DIESES Fotos skopierte Existenzpruefung
    - sie haengt an Daten statt am Vokabular und wiese das Korrigieren eines nie erkannten Motivs
    zu Unrecht ab."""
    if not is_motif_key(motif_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="motif_key gehoert nicht zum festen Motivset.",
        )
    return motif_key


@router.put("/photos/{photo_id}/motif-corrections/{motif_key}", response_model=MotifCorrectionOut)
async def set_motif_correction(
    photo_id: int,
    motif_key: str,
    payload: MotifCorrectionIn,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S2): ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # Router-weite `dependencies`-Liste und hat deshalb auch keinen Vollstaendigkeitstest - ein
    # hier vergessener Parameter waere STILL OEFFENTLICH: kein Fehler, keine 401, nur Daten.
    current_user: User = Depends(get_current_user),
) -> MotifCorrectionOut:
    """Markiert ein Motiv fuer dieses Foto als zutreffend oder als nicht zutreffend: `404` bei
    fehlendem Foto, `422` bei einem `motif_key` ausserhalb des festen Achter-Sets (auch fuer
    `dokument_screenshot` und fuer einen entfallenen Kategorieschluessel), `409` bei einem
    gleichzeitigen Schreibversuch auf dasselbe Paar.

    Die Korrektur traegt nie eine Zahl - der Nutzer schaetzt nichts ein, er waehlt ein Motiv ab
    oder zu. Die WIRKSAME Staerke entsteht erst im Lesepfad und wird nicht in die Staerkezeile
    materialisiert; sie ueberlebt damit jeden weiteren Klassifizierungslauf ohne Sonderfallcode.

    AUSDRUECKLICH ERLAUBT ist ein Motiv, das fuer dieses Foto nie erkannt wurde, und ein Foto ohne
    Kopfzeile: die Tabelle ist lauf-unabhaengig, und die Korrektur greift dann beim ersten Lauf.

    Eine Korrektur je Foto und Motiv, letzter Zugriff gewinnt: korrigiert der zweite Nutzer
    dasselbe Paar, UEBERSCHREIBT er die Aussage des ersten. `user_id` haelt fest, wer zuletzt
    geschrieben hat - es gibt keine Historie und keinen Hinweis an die erste Person. Eine
    wirkungslose Korrektur (`applies=false` auf einem Motiv, dessen Staerke schon 0 ist) wird
    trotzdem gespeichert; sie ist eine Nutzeraussage, keine Zwischenspeicherung."""
    await _get_photo_or_404(photo_id, session)
    _validated_motif_key(motif_key)

    # SICHERHEIT (S6): die Aufsuch-Bedingung lautet `(photo_id, motif_key)` und filtert BEWUSST
    # NICHT zusaetzlich auf `user_id`. Mit dem Nutzer im Filter entstuenden zwei widersprueckliche
    # Zeilen fuer dasselbe Paar, und welche gilt, entschiede die Sortierung.
    existing = (
        await session.execute(
            select(PhotoMotifCorrection).where(
                PhotoMotifCorrection.photo_id == photo_id,
                PhotoMotifCorrection.motif_key == motif_key,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        # SICHERHEIT (S6): `user_id` stammt AUSSCHLIESSLICH aus `current_user.id` - nie aus Body
        # oder Query. Es ist ein Auditfeld und kein Zugriffsschluessel.
        session.add(
            PhotoMotifCorrection(
                photo_id=photo_id,
                user_id=current_user.id,
                motif_key=motif_key,
                applies=payload.applies,
            )
        )
    else:
        existing.applies = payload.applies
        existing.user_id = current_user.id
        # `updated_at` traegt `onupdate=func.now()` und wird nie von Hand gesetzt.

    # SICHERHEIT (S7): der `flush` VOR dem `commit` bringt den Unique-Constraint hier zum Tragen,
    # damit ein gleichzeitiger Schreibversuch beider Nutzer als `409` herauskommt und nie als
    # `500`. Eine Sperre (`with_for_update()`) ist nicht noetig und ausdruecklich nicht
    # vorzusehen: die Korrektur schreibt eine Zeile und leitet nichts ab, sie hat keinen
    # Schreibzugriff auf die Rangfolge.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Die Korrektur dieses Motivs wurde gerade veraendert. Bitte erneut versuchen.",
        ) from exc
    await session.commit()

    return MotifCorrectionOut(photo_id=photo_id, motif_key=motif_key, applies=payload.applies)


@router.delete(
    "/photos/{photo_id}/motif-corrections/{motif_key}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_motif_correction(
    photo_id: int,
    motif_key: str,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S2): siehe set_motif_correction - der 401-Nachweis ist fuer BEIDE Endpunkte
    # Pflicht, weil dieser Router keinen Vollstaendigkeitstest hat.
    current_user: User = Depends(get_current_user),
) -> None:
    """Nimmt die Korrektur eines Motivs zurueck - die wirksame Staerke ist danach wieder die der
    Grundlage. `404` bei fehlendem Foto, `422` bei einem `motif_key` ausserhalb des festen Sets.

    IDEMPOTENT (`204` auch ohne bestehende Zeile) und ohne Body. Auch die jeweils andere Person
    darf eine Korrektur zuruecknehmen: die Aussage gehoert zum Foto, nicht zu einem Geschmack."""
    await _get_photo_or_404(photo_id, session)
    _validated_motif_key(motif_key)

    await session.execute(
        delete(PhotoMotifCorrection).where(
            PhotoMotifCorrection.photo_id == photo_id,
            PhotoMotifCorrection.motif_key == motif_key,
        )
    )
    await session.commit()
