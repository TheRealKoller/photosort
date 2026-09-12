from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
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
from photosort.events import EffectiveLocation, LocationEntry, infer_locations
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    Event,
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
    NO_REMOTE_CATEGORY_EVIDENCE,
    _remote_category_evidence,
    derive_photo_category,
    reassign_photo_category,
)

# Einzige bewusste Ausnahme vom sonst in api/*.py durchgehaltenen Prinzip, keine worker.py-
# Funktionen direkt zu importieren: die Umkategorisierung wirkt SYNCHRON im selben API-Request
# ("sofortige Wirkung", kein Hintergrund-Job). reassign_photo_category/derive_photo_category/
# _remote_category_evidence leiten die Kategorie ueber denselben Codepfad ab wie
# run_criterion_scoring - kein zweiter, driftender Rechenweg.
# Voraussetzung dieses Imports: worker.py importiert mediapipe/tensorflow/onnxruntime
# ausschliesslich lokal innerhalb der jeweiligen build_*()-Funktionen, NIE auf Modulebene - sonst
# traegt der uvicorn-Importpfad ihr Gewicht.

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

    Ein Foto hat pro Lauf eine solche Zeile JE KATEGORIE, zu der es gehört - siehe
    `PhotoOut.rankings`."""

    event_id: int
    category_key: str
    rank_score: float
    rank_position: int
    # Größe der GESAMTEN Event x Kategorie-Partition (nicht nur der angeforderten top_n), für
    # "Rang M von N" im Info-Popover - lauf-global berechnet (siehe _partition_sizes), nicht
    # nutzerspezifisch gefiltert. Zählt ALLE Zeilen der Partition, Haupt- wie Nebenzeilen: die
    # Frage lautet "wie viele Fotos stehen in dieser Kategorie dieses Events".
    partition_size: int
    # Ob dies die HAUPTkategorie des Fotos ist. Genau eine
    # Zugehoerigkeit je Foto und Lauf traegt `true`. Die Oberflaeche liest die Rolle ausschliesslich
    # hier ab und bildet nirgends eine Schwelle nach.
    is_primary: bool
    # Der Platz DIESER Zugehoerigkeit in der ANGEZEIGTEN Auswahl ihrer Kategorie. `null`, wenn
    # diese Zugehoerigkeit nicht zur angeforderten Auswahl gehoert oder gar keine angefordert
    # wurde.
    #
    # Die Kuratierungs-Query hat KEINEN Ablehnungsfilter, der Wert ist damit ENTWEDER `null` ODER
    # gleich `rank_position`, und nicht nutzerabhaengig.
    #
    # Trotz des Zusammenfallens NICHT mit `rank_position` zusammenlegen: jene ist die lauf-globale
    # Rangaussage des Info-Popovers (unabhaengig vom Query-Parameter), diese hier die
    # Zugehoerigkeit zur angeforderten Auswahl ("unter welchen seiner Kategorien ist dieses Foto
    # zu zeigen") - die einzige Auskunft darueber, die das Frontend sonst nachbilden muesste.
    curation_position: int | None = None


class CriterionScoreOut(BaseModel):
    """Ein einzelner, bereits normierter Kriterien-Wert eines Fotos
    - exponiert die `PhotoCriterionScore`-Tabelle.
    `display_name` kommt aus criteria.py::CRITERIA_REGISTRY (Fallback auf `criterion_key`, falls
    ein DB-Wert nicht im Register steht - defensiv gegen Registry-/Daten-Drift). `category_eligible`
    spiegelt dasselbe Registry-Attribut (Fallback False) und ist die alleinige Grundlage der
    Frontend-Gliederung in die Bloecke "Qualitaet"/"Kategorien"
    - bewusst kein zweites, redundantes Anzeige-Attribut."""

    criterion_key: str
    display_name: str
    value: float
    source: CriterionSource
    category_eligible: bool


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


class CategoryCandidateOut(BaseModel):
    """Die fuer DIESES Foto tatsaechlich gueltige Kategorie-Kandidatenmenge - lokal qualifizierende
    Signale (Wert >= der jeweiligen `category_presence_threshold`) UND die remote genannten
    Kategorien zusammen; das Frontend bildet die Präsenz-Schwellenlogik nicht nach.

    `category_key` ist IMMER ein Key des festen Sets (categories.py). Es gibt KEIN `score`-Feld:
    die Auswahl entscheidet die feste Vorrangreihenfolge, nie ein Zahlenvergleich. `provider` ist
    nur bei `origin="remote"` gesetzt."""

    category_key: str
    origin: Literal["local", "remote"]
    provider: str | None = None
    # Die Selbsteinschätzung des Modells zu DIESEM Schlüssel. `None` heisst "keine Modellaussage",
    # nie `0.0` (das hiesse "das Modell war sich zu 0 % sicher").
    #
    # Diese Zahl beeinflusst weder
    # Auswahl noch Sortierung noch irgendeine Schwelle im Backend - sie wird angezeigt und
    # ausgewertet, sonst nichts.
    #
    # Die Zahl folgt dem SCHLUESSEL, nicht der `origin`-Kennzeichnung: ein lokal UND remote
    # erkannter Schluessel wird unten zu `origin="local"` zusammengefasst (die spezifischere
    # Herkunftsaussage), traegt aber die Modellzahl weiter - es gibt eine Modellaussage zu diesem
    # Schluessel. Ein REIN lokaler Kandidat bekommt `None`.
    confidence: float | None = None


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


class PhotoOut(BaseModel):
    id: int
    relative_path: str
    taken_at: datetime
    ratings: list[RatingOut]
    suggestion: SuggestionOut | None
    # ALLE Zugehoerigkeiten des Fotos im letzten erfolgreichen Lauf, in beiden Query-Modi. Immer
    # eine Liste, nie `null` (analog `ratings`) - leer, solange kein erfolgreicher Lauf existiert.
    #
    # REIHENFOLGE FESTGELEGT: Hauptzeile zuerst, danach die Nebenzeilen in
    # Registry-Anzeigereihenfolge. Sonst flackerte die Anzeige mit der Zeilenreihenfolge der
    # Datenbank.
    #
    # KEIN zweites Einzelfeld `ranking: RankingOut | None` daneben - das waere die zweite,
    # driftende Abbildung derselben Sache. Jede Lesestelle entscheidet sich, welche
    # Zugehoerigkeit sie meint.
    rankings: list[RankingOut]
    # Immer eine Liste, nie None (analog `ratings`) - best-effort: enthaelt nur Kriterien, fuer
    # die tatsaechlich eine PhotoCriterionScore-Zeile existiert, sortiert nach
    # CRITERIA_REGISTRY-Reihenfolge.
    criterion_scores: list[CriterionScoreOut]
    # Immer eine Liste (0-2 Einträge), nie None.
    fine_labels: list[FineLabelOut]
    # Die remote ermittelte Kategorie dieses Fotos (PhotoCategoryClassification.category_key),
    # None ohne Klassifikations-Zeile. Bewusst getrennt von `ranking.category_key`: dort steht die
    # im Lauf tatsaechlich VERGEBENE Kategorie (lokal + remote + Override), hier nur der
    # Remote-Beitrag.
    remote_category: str | None = None
    # Die Konfidenz zu `remote_category`
    # (PhotoCategoryClassification.category_confidence). Eigenes Feld statt einer clientseitigen
    # Ableitung aus `category_candidates`: `remote_category` kann `nicht_erkannt` lauten und steht
    # dann gar nicht in `detected_categories`. Dieses Feld traegt den Kuratierungsfilter.
    category_confidence: float | None = None
    # Dauerhafte manuelle Uebersteuerung (PhotoScore.category_override), None ohne aktiven
    # Override.
    category_override: str | None = None
    # Siehe CategoryCandidateOut-Docstring - sortiert in Registry-Anzeigereihenfolge (dieselbe
    # Reihenfolge wie GET /categories), damit die Liste ueberall im Produkt gleich aussieht.
    category_candidates: list[CategoryCandidateOut]
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
            # Grundlage von PhotoOut.remote_category/
            # category_candidates und des Remote-Erfolgssignals in _cloud_vision_status_out.
            selectinload(Photo.category_classification),
            # Eager geladen (analog criterion_scores/fine_labels oben), kein zusaetzliches Query
            # je Foto fuer _cloud_vision_status_out. Ohne dieses selectinload loest
            # photo.landmark_detection einen Lazy-Load aus und schlaegt im Async-Kontext mit
            # MissingGreenlet fehl.
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
    Reihenfolge; Zeilen, deren criterion_key nicht in der
    Registry steht (Registry-/Daten-Drift), landen ans Ende, sortiert nach ihrem eigenen Key fuer
    ein deterministisches Ergebnis, und bekommen den rohen Key als display_name-Fallback sowie
    `category_eligible=False` (identisch zum Registry-Default des Attributs). Fehlt umgekehrt ein
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
    """Die Liste ist reine ERKLAERUNG in der Oberflaeche ("das hat das System erkannt"): sie
    beschränkt NICHT, was manuell übersteuert werden darf - dafür gilt die staerkere Whitelist
    gegen das geschlossene Set (`is_known_category` in `set_category_override`).

    Lokal qualifizierende Signale (criteria.py-Schwelle erreicht, ueber LOCAL_CATEGORY_SIGNALS auf
    einen Set-Key abgebildet) und die remote genannten Set-Keys zusammen, sortiert in
    Registry-Anzeigereihenfolge; ein Key, der lokal UND remote Kandidat ist, erscheint einmal mit
    `origin="local"` - die spezifischere Herkunftsaussage."""
    origins: dict[str, tuple[Literal["local", "remote"], str | None]] = {}

    classification = photo.category_classification
    # Die Konfidenz-Abbildung wird GETRENNT von den Herkunftsangaben gefuehrt und erst ganz unten
    # je Schluessel nachgeschlagen - genau deshalb ueberlebt die Zahl das Zusammenfassen eines
    # lokal UND remote erkannten Schluessels zu `origin="local"`. `or {}` deckt beide "keine
    # Angabe"-Formen ab: keine Klassifizierungszeile und eine Altzeile mit `NULL`.
    confidences: dict[str, float] = {}
    if classification is not None:
        confidences = classification.detected_category_confidences or {}
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
            category_key=key,
            origin=origins[key][0],
            provider=origins[key][1],
            confidence=confidences.get(key),
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
    selectinload(Photo.criterion_scores/landmark_detection/category_classification/
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

    # Remote-Kategorie: kein "nichts gefunden"-Fall - ein Erfolg schreibt GENAU EINE
    # Klassifikations-Zeile, auch wenn die Kategorie `nicht_erkannt` lautet und keine Feinlabels
    # entstanden sind. Die PRAESENZ dieser Zeile ist damit das Erfolgssignal, nicht die Existenz
    # einer Feinlabel-Zeile.
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
    rankings_by_photo_id: Mapping[int, Sequence[PhotoRanking]],
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

    # Alle Rangzeilen EINES Fotos tragen dieselbe `event_id` (die Partitionen sind
    # Event x Kategorie, die Event-Zugehoerigkeit ist pro Foto eindeutig) - die erste genuegt.
    event_id_by_photo_id = {
        photo_id: rankings[0].event_id
        for photo_id, rankings in rankings_by_photo_id.items()
        if rankings
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


def _to_photo_out(
    photo: Photo,
    current_user_id: int,
    project: Project,
    rankings: Sequence[PhotoRanking] = (),
    partition_sizes: Mapping[tuple[int, str], int] | None = None,
    curation_positions: Mapping[tuple[int, str], int] | None = None,
    place: PhotoPlace = NO_PLACE,
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
        ratings=[
            RatingOut(user_id=r.user_id, username=r.user.username, status=r.status)
            for r in photo.ratings
        ],
        suggestion=suggestion,
        rankings=[
            RankingOut(
                event_id=ranking.event_id,
                category_key=ranking.category_key,
                rank_score=ranking.rank_score,
                rank_position=ranking.rank_position,
                partition_size=(partition_sizes or {}).get(
                    (ranking.event_id, ranking.category_key), 0
                ),
                is_primary=ranking.is_primary,
                curation_position=(curation_positions or {}).get(
                    (ranking.photo_id, ranking.category_key)
                ),
            )
            for ranking in rankings
        ],
        criterion_scores=_criterion_scores_out(photo),
        fine_labels=_fine_labels_out(photo),
        remote_category=(
            photo.category_classification.category_key
            if photo.category_classification is not None
            else None
        ),
        category_confidence=(
            photo.category_classification.category_confidence
            if photo.category_classification is not None
            else None
        ),
        category_override=photo.score.category_override if photo.score is not None else None,
        category_candidates=_category_candidates_out(photo),
        cloud_vision_status=_cloud_vision_status_out(photo, project),
        # Beide Felder kommen fertig aus `_event_and_location_by_photo_id`. Der Vorgabewert
        # `NO_PLACE` haelt die Ausfallrichtung fest: eine vergessene Durchreichung ergibt `null`,
        # nie einen falschen Ort.
        location=place.location,
        event=place.event,
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
    session: AsyncSession, project_id: int, top_n: int
) -> tuple[list[int], dict[tuple[int, str], int], int | None]:
    """Kategorie-Kuratierung, ohne Backfill: liefert je Partition (event_id x category_key)
    des LETZTEN erfolgreichen CriterionScoringRun die Zugehörigkeiten mit
    `rank_position <= top_n`.

    KEIN ABLEHNUNGSFILTER: die Query filtert die vom anfragenden Nutzer REJECTED-bewerteten
    Fotos NICHT aus, und damit ist auch keine Fensterfunktion nötig -
    `PhotoRanking.rank_position` ist je Partition lückenlos ab 1 vergeben
    (`ranking.py::rank_photos` liefert `index + 1` über die VOLLSTÄNDIGE Partition;
    `worker.py::run_criterion_scoring` ruft sie je Partition auf, Haupt- wie
    Nebenzugehörigkeiten in derselben Liste; `worker.py::reassign_photo_category` vergibt bei
    einem Override die Positionen beider betroffenen Partitionen vollständig neu).

    Folge: Welche Fotos die Ansicht zeigt, hängt ausschließlich vom LAUF ab, nicht vom
    Bewertungsstand des Betrachters. Ein verworfenes Foto bleibt an seiner Position und trägt
    seinen Zustand in `PhotoOut.ratings[]`.

    `top_n` wirkt JE PARTITION, Neben- wie Hauptzeilen zählen mit; EIN Foto kann in mehreren
    Partitionen unter die Top-N fallen. Rückgabe deshalb dreiteilig:

    * die Foto-Ids in Anzeigereihenfolge, jede höchstens EINMAL (`PhotoListOut.items` enthält
      jedes Foto weiterhin höchstens einmal),
    * die `curation_position` je (photo_id, category_key) - ohne Ablehnungsfilter identisch mit
      `rank_position` -, aus der die Kuratierungsansicht ablesen kann, in welchen Kategorien sie
      das Foto zeigen soll,
    * die Lauf-Id."""
    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        return [], {}, None

    result = await session.execute(
        select(
            PhotoRanking.photo_id,
            PhotoRanking.category_key,
            PhotoRanking.rank_position,
        )
        .where(
            PhotoRanking.criterion_scoring_run_id == latest_run_id,
            PhotoRanking.rank_position <= top_n,
        )
        .order_by(PhotoRanking.event_id, PhotoRanking.category_key, PhotoRanking.rank_position)
    )
    ordered_ids: list[int] = []
    seen: set[int] = set()
    curation_positions: dict[tuple[int, str], int] = {}
    for photo_id, category_key, rank_position in result.all():
        curation_positions[(photo_id, category_key)] = rank_position
        if photo_id not in seen:
            seen.add(photo_id)
            ordered_ids.append(photo_id)
    return ordered_ids, curation_positions, latest_run_id


async def _partition_sizes(
    session: AsyncSession, criterion_scoring_run_id: int
) -> dict[tuple[int, str], int]:
    """Größe jeder Event x Kategorie-Partition eines Laufs, für "Rang M von N" im
    Info-Popover - ein einzelner GROUP BY-Query pro list_photos-Aufruf (nicht pro Foto).
    Bewusst lauf-global, nicht
    nutzerspezifisch gefiltert - siehe RankingOut.partition_size-Docstring.

    SICHERHEIT (M1): das Lauf-Prädikat steht auch HIER - diese Zählabfrage liegt hinter `total`
    des Kandidaten-Endpunkts und ist damit eine Abfrage dieses Endpunkts wie jede andere.

    Zählt AUSDRÜCKLICH ALLE Zeilen der Partition, Haupt- wie Nebenzeilen - anders als die
    Kategorienverteilung der Statistikseite
    und `category_diff.py`, die auf `is_primary` filtern. Zwei Zaehlweisen, zwei Fragen: hier "wie
    viele Fotos stehen in dieser Kategorie dieses Events", dort "welche Kategorie hat dieses
    Foto"."""
    result = await session.execute(
        select(PhotoRanking.event_id, PhotoRanking.category_key, func.count())
        .where(PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id)
        .group_by(PhotoRanking.event_id, PhotoRanking.category_key)
    )
    return {(event_id, category_key): count for event_id, category_key, count in result.all()}


# Registry-Anzeigereihenfolge als Rang - dieselbe Reihenfolge wie `GET /categories` und die
# Kandidatenliste, damit kategoriale Listen ueberall im Produkt gleich aussehen.
_CATEGORY_DISPLAY_ORDER = {key: index for index, key in enumerate(CATEGORY_REGISTRY)}


def _ranking_sort_key(ranking: PhotoRanking) -> tuple[int, int, str]:
    """Hauptzeile zuerst, danach die Nebenzeilen in Registry-Anzeigereihenfolge (siehe
    `PhotoOut.rankings`).

    Ein `category_key` außerhalb des festen Sets (Altbestand; der Lesepfad ist bewusst tolerant)
    landet hinten und dort alphabetisch stabil, statt die Sortierung zu sprengen."""
    return (
        0 if ranking.is_primary else 1,
        _CATEGORY_DISPLAY_ORDER.get(ranking.category_key, len(_CATEGORY_DISPLAY_ORDER)),
        ranking.category_key,
    )


async def _rankings_by_photo_id(
    session: AsyncSession, criterion_scoring_run_id: int, photo_ids: list[int]
) -> dict[int, list[PhotoRanking]]:
    """ALLE Zugehörigkeiten je Foto, nicht genau eine: bei der Kardinalität 1:N ist ein
    `dict[int, PhotoRanking]` hier eine stille Datenverlustquelle - die zweite Zeile eines Fotos
    ueberschriebe die erste ohne jedes Signal."""
    if not photo_ids:
        return {}
    result = await session.execute(
        select(PhotoRanking).where(
            PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
            PhotoRanking.photo_id.in_(photo_ids),
        )
    )
    rankings_by_photo_id: dict[int, list[PhotoRanking]] = {}
    for row in result.scalars():
        rankings_by_photo_id.setdefault(row.photo_id, []).append(row)
    for rows in rankings_by_photo_id.values():
        rows.sort(key=_ranking_sort_key)
    return rankings_by_photo_id


@router.get("/projects/{project_id}/photos", response_model=PhotoListOut)
async def list_photos(
    project_id: int,
    rating_status: RatingFilter | None = None,
    # Kategorie-Kuratierung: serverseitig deklarativ begrenzt (Field(ge=1, le=10)) -
    # Robustheits-/Ressourcen-Kriterium, kein Sicherheitskriterium. Wenn gesetzt, ersetzt dieser
    # Query-Modus rating_status vollstaendig (eigenstaendige Kuratierungs-Ansicht) - limit/offset
    # werden in diesem Modus ignoriert, da der volle Partitions-Pool (N x Partitionsanzahl) fuer
    # ein Zwei-Personen-Familienprojekt naturgemaess klein bleibt.
    top_n_per_category: int | None = Query(None, ge=1, le=10),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoListOut:
    project = await _get_project_or_404(project_id, session)

    if top_n_per_category is not None:
        ids, curation_positions, criterion_scoring_run_id = await _top_n_per_category_photo_ids(
            session, project_id, top_n_per_category
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
        place_by_id = await _event_and_location_by_photo_id(
            session, project_id, criterion_scoring_run_id, photos_by_id, rankings_by_id
        )
        items = [
            _to_photo_out(
                photos_by_id[photo_id],
                current_user.id,
                project,
                rankings_by_id.get(photo_id, []),
                partition_sizes,
                curation_positions,
                place_by_id.get(photo_id, NO_PLACE),
            )
            for photo_id in ids
        ]
        return PhotoListOut(items=items, total=len(items))

    ids, total = await _filtered_photo_ids(
        session, project_id, current_user.id, rating_status, limit, offset
    )
    photos_by_id = await _photos_by_id(session, ids)
    # RankingOut wird AUCH hier im Standard-Listing-Zweig befüllt, nicht nur bei
    # top_n_per_category - Grid-/Detailansicht sollen ebenfalls Rang-Score/-Position zeigen
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
    place_by_id = await _event_and_location_by_photo_id(
        session, project_id, latest_run_id, photos_by_id, rankings_by_id
    )
    items = [
        _to_photo_out(
            photos_by_id[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id, []),
            partition_sizes,
            # Ohne angeforderte Auswahl traegt JEDE Zugehoerigkeit `curation_position = null` - es
            # gibt in diesem Modus keine Auswahl, zu der sie eine Position haben koennte.
            None,
            place_by_id.get(photo_id, NO_PLACE),
        )
        for photo_id in ids
    ]
    return PhotoListOut(items=items, total=total)


# SICHERHEIT - Obergrenze des verbliebenen freien Partitionsschlüssels: `category_key` wird
# bewusst NICHT gegen CATEGORY_REGISTRY geprüft - der Lesepfad ist tolerant gegenüber Altbestand,
# und eine Allowlist waere hier ein Produkt-, kein Sicherheitsentscheid (422 statt leerer Liste).
# Die Laengengrenze ist Verteidigung in der Tiefe, damit ein entarteter Wert gar nicht erst bis
# zum Datenbankvergleich kommt. Der zweite Teil des Schlüssels ist seit Spec 0425 eine Objekt-Id
# und braucht sie nicht mehr: `ge`/`le` plus Typprüfung sind enger.
_MAX_PARTITION_KEY_LENGTH = 200

# SICHERHEIT - Obergrenze von `after_rank`/`offset`: ein Pydantic-`int` ist
# unbeschraenkt und landet direkt im SQL-Vergleich; unter SQLite (Testlauf und lokale Entwicklung)
# wirft ein Wert jenseits von 2^63 einen `OverflowError` und damit eine 500 statt einer leeren
# Liste. Der Wert liegt weit ueber jeder realistischen Partitionsgroesse - er begrenzt einen
# Missbrauchsfall, nicht die Benutzung.
_MAX_QUERY_POSITION = 1_000_000_000


@router.get("/projects/{project_id}/curation-candidates", response_model=PhotoListOut)
async def curation_candidates(
    project_id: int,
    # SICHERHEIT (M3): eine Objekt-Id statt eines Freitextschlüssels. `ge=1` schließt `0` und
    # negative Werte aus, `le` verhindert, dass ein Wert jenseits von 2^63 unter SQLite einen
    # `OverflowError` und damit eine 500 statt einer leeren Liste erzeugt. FastAPI spiegelt bei
    # `422` den Rohwert im `input`-Feld zurück - er wird ausschließlich als React-Textknoten
    # gerendert, nie geloggt.
    event_id: int = Query(..., ge=1, le=_MAX_QUERY_POSITION),
    category_key: str = Query(..., max_length=_MAX_PARTITION_KEY_LENGTH),
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
    `curation_position` wird AUSSCHLIESSLICH für die angefragte Zugehörigkeit
    gesetzt - sonst erschiene ein nachgeladenes Foto zusaetzlich unter seinen anderen Kategorien,
    in denen niemand aufgeklappt hat.

    Kein erfolgreicher Lauf, ein `event_id` aus einem anderen Projekt oder einem aelteren Lauf,
    ein unbekannter `category_key` oder ein `after_rank` jenseits der Partitionsgroesse liefern
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
    total = max(partition_sizes.get((event_id, category_key), 0) - after_rank, 0)

    rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.rank_position)
            .where(
                PhotoRanking.criterion_scoring_run_id == latest_run_id,
                PhotoRanking.event_id == event_id,
                PhotoRanking.category_key == category_key,
                PhotoRanking.rank_position > after_rank,
            )
            .order_by(PhotoRanking.rank_position)
            .offset(offset)
            .limit(limit)
        )
    ).all()

    ids = [photo_id for photo_id, _ in rows]
    # Nur die ANGEFRAGTE Zugehoerigkeit traegt eine curation_position; alle anderen
    # Zugehoerigkeiten desselben Fotos bleiben `null`.
    curation_positions = {
        (photo_id, category_key): rank_position for photo_id, rank_position in rows
    }
    photos_by_id = await _photos_by_id(session, ids)
    rankings_by_id = await _rankings_by_photo_id(session, latest_run_id, ids)
    place_by_id = await _event_and_location_by_photo_id(
        session, project_id, latest_run_id, photos_by_id, rankings_by_id
    )
    items = [
        _to_photo_out(
            photos_by_id[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id, []),
            partition_sizes,
            curation_positions,
            place_by_id.get(photo_id, NO_PLACE),
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


class CategoryOverrideIn(BaseModel):
    """SICHERHEIT: `category_key` muss ein Eintrag des festen 13er-Sets sein
    (categories.py::CATEGORY_REGISTRY) - reine Whitelist-Mitgliedschaftsprüfung über
    `is_known_category`, kein Präfix-/Regex-/startswith-Vergleich und keine Normalisierung
    des Eingabewerts (der Client schickt den Key exakt so zurück, wie GET /categories ihn
    geliefert hat).

    Die geschlossene 13-Werte-Menge ist strikt stärker als eine foto-skopierte
    Existenzprüfung über "irgendeinen für dieses Foto persistierten canonical_key"; eine
    Cross-Photo-Isolation braucht es daneben nicht - ein Set-Key ist kein fremder
    Fotobezug."""

    category_key: str


class CategoryOverrideOut(BaseModel):
    photo_id: int
    category_key: str


async def _get_photo_or_404(photo_id: int, session: AsyncSession) -> Photo:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    return photo


async def _lock_photo_score(session: AsyncSession, photo_id: int) -> PhotoScore | None:
    """SICHERHEIT: sperrt die `photo_scores`-Zeile des Fotos für die Dauer der Transaktion.

    Muss VOR dem Lesen der Ranking-Zeilen laufen: `reassign_photo_category` leitet die
    gesamte Zugehörigkeitsmenge neu ab und schreibt und LÖSCHT dabei Zeilen im Request-Pfad. Der
    Unique-Constraint verhindert nur die doppelte Zugehoerigkeitszeile, nicht das Wettrennen
    um "genau eine `is_primary`-Zeile je (Lauf, Foto)". Zwei ueberlappende Overrides desselben
    Fotos (zwei Nutzer, realistischer: ein Doppelklick auf lahmer Verbindung) koennten sonst zwei
    Hauptzeilen oder keine hinterlassen und damit still die Zusage brechen, dass die Summe ueber
    alle Kategorien die Fotoanzahl ergibt.

    Unter PostgreSQL serialisiert `FOR UPDATE` konkurrierende Overrides desselben Fotos; unter
    SQLite ist die Schreibtransaktion ohnehin serialisiert (der SQLite-Dialekt rendert die Klausel
    gar nicht) - testneutral. `photo_scores` ist der Anker, weil dort der Override selbst steht.

    `None`, wenn das Foto keine `photo_scores`-Zeile hat (dann gibt es auch nichts zu sperren und
    keinen Override zu setzen)."""
    return (
        await session.execute(
            select(PhotoScore).where(PhotoScore.photo_id == photo_id).with_for_update()
        )
    ).scalar_one_or_none()


async def _reassign_or_conflict(
    session: AsyncSession,
    run_id: int,
    photo_id: int,
    event_id: int,
    new_category_key: str,
) -> None:
    """SICHERHEIT: führt die Neuableitung aus und bildet einen `IntegrityError` aus dem
    `(Lauf, Foto, Kategorie)`-Constraint auf `409` ab - NIE auf eine 500.

    Der Regelfall "Override auf eine bereits bestehende Nebenkategorie" laeuft ausdruecklich NICHT
    hier hinein: dort fuehrt `reassign_photo_category` beide Zeilen zu einer Hauptzeile zusammen.
    Diese Abbildung deckt den Rest ab - insbesondere zwei tatsaechlich gleichzeitige Schreibversuche
    fuer dasselbe Foto, bei denen die Sperre nicht greifen konnte."""
    try:
        await reassign_photo_category(session, run_id, photo_id, event_id, new_category_key)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Die Kategorien dieses Fotos wurden gerade veraendert. Bitte erneut versuchen.",
        ) from exc


async def _current_ranking_for_photo(
    session: AsyncSession, project_id: int, photo_id: int
) -> tuple[int, PhotoRanking] | None:
    """`None`, wenn kein erfolgreicher CriterionScoringRun existiert ODER dieses Foto darin keine
    PhotoRanking-Zeile hat (409-Faelle des PUT-Endpunkts) - sonst
    `(criterion_scoring_run_id, ranking)` der HAUPTZEILE.

    Der `is_primary`-Filter ist nicht optional: `scalar_one_or_none()` wirft ab der zweiten
    Zeile, und ein Foto hat bis zu vier.
    Gemeint ist hier ausschliesslich die Hauptzeile - aus ihr kommt die `event_id` fuer die
    Neuableitung. SICHERHEIT (M4): SERVERSEITIG aus der Zeile des aufgeloesten Laufs, nie aus
    Body oder Query."""
    run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if run_id is None:
        return None
    ranking = (
        await session.execute(
            select(PhotoRanking).where(
                PhotoRanking.criterion_scoring_run_id == run_id,
                PhotoRanking.photo_id == photo_id,
                PhotoRanking.is_primary.is_(True),
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
    """Manuelle Übernahme (Override) mit sofortiger Wirkung: `404` bei fehlendem Foto, `422`
    bei einem `category_key` außerhalb des festen Sets (auch bei einem Altwert aus der
    Laufhistorie wie "unerkannt"), `409` ohne `PhotoRanking`-Zeile im aktuellen Lauf.

    AUSDRÜCKLICH ERLAUBT ist ein Set-Key, der für dieses Foto NIE Kandidat war - die
    Kandidatenliste ist nur Erklärung, die manuelle Übersteuerung darf jeden der 13
    Einträge setzen. Wirkt SOFORT im selben Request
    (`worker.py::reassign_photo_category`) - kein neuer Ranking-Algorithmus, kein voller
    Re-Scoring-Lauf.

    Zielt der Override auf eine Kategorie, die für dieses Foto bereits NEBENkategorie ist,
    gibt es KEIN `409` - die Hauptzeile ersetzt die Nebenzeile.
    Die uebrigen Nebenkategorien werden aus der unveraenderten Modellaussage neu abgeleitet."""
    photo = await _get_photo_or_404(photo_id, session)

    # SICHERHEIT: Whitelist-Prüfung VOR jeder Schreibaktion, nicht erst beim Bauen der
    # Antwort.
    if not is_known_category(payload.category_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="category_key gehoert nicht zum festen Kategorien-Set.",
        )

    score = await _lock_photo_score(session, photo_id)

    current = await _current_ranking_for_photo(session, photo.project_id, photo_id)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kein aktueller Rangfolgen-Eintrag fuer dieses Foto.",
        )
    run_id, ranking = current

    # Der Override wird VOR der Neuableitung gesetzt: `reassign_photo_category` leitet die
    # Zugehoerigkeitsmenge aus dem persistierten Zustand ab und muss dort den neuen Wert sehen -
    # sonst wuerde die frisch gesetzte Hauptzeile mit der Modellzahl gedaempft, obwohl sie eine
    # menschliche Festlegung ist. Beides liegt in derselben Transaktion;
    # scheitert die Neuableitung, ist auch der Override nicht geschrieben.
    if score is not None:
        score.category_override = payload.category_key

    await _reassign_or_conflict(session, run_id, photo_id, ranking.event_id, payload.category_key)
    # Zweites `commit()` fuer den Fall, dass die Neuableitung ein No-op war (Override auf die
    # bereits geltende Hauptkategorie, ohne Aenderung an den Nebenzeilen): der Override selbst ist
    # trotzdem eine Festlegung des Nutzers und muss persistiert werden - er ueberlebt damit auch
    # jeden kuenftigen Lauf.
    await session.commit()

    return CategoryOverrideOut(photo_id=photo_id, category_key=payload.category_key)


@router.delete("/photos/{photo_id}/category-override", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_override(
    photo_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Nimmt die manuelle Übernahme zurück und rekonstruiert den automatisch abgeleiteten
    `category_key` über DIESELBE Ableitung wie der Lauf selbst
    (`worker.py::_remote_category_evidence` + `derive_photo_category`) - kein zweiter,
    driftender Rechenweg. Idempotent (`204` auch ohne aktiven Override).

    Die Rekonstruktion braucht nur die Werte DIESES Fotos, keinen laufweiten
    Kandidatenpool, und stellt die gesamte Zugehörigkeitsmenge des automatischen Laufs
    wieder her - Haupt- wie Nebenzeilen."""
    await _get_photo_or_404(photo_id, session)

    # SICHERHEIT: Sperre vor dem Lesen der Ranking-Zeilen, siehe _lock_photo_score.
    score = await _lock_photo_score(session, photo_id)
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
    evidence = (await _remote_category_evidence(session, [photo_id])).get(
        photo_id, NO_REMOTE_CATEGORY_EVIDENCE
    )
    new_category_key = derive_photo_category(criterion_values, evidence.candidates)

    # Wie beim Setzen: erst der persistierte Zustand, dann die Neuableitung darauf. Sonst hielte
    # `reassign_photo_category` die rekonstruierte Hauptzeile faelschlich fuer eine manuelle
    # Festlegung und liesse sie ungedaempft.
    score.category_override = None
    await _reassign_or_conflict(session, run_id, photo_id, ranking.event_id, new_category_key)
    await session.commit()
