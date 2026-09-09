from __future__ import annotations

import enum
from bisect import bisect_left
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
from photosort.landmark import sanitize_landmark_name
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoLandmarkDetection,
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

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 7:
# einzige bewusste Ausnahme vom sonst in api/*.py durchgehaltenen Prinzip, keine worker.py-
# Funktionen direkt zu importieren (api/projects.py-Kommentar bei _count_remote_category_
# candidates) - die Spec verlangt hier ausdruecklich einen SYNCHRONEN Aufruf im selben API-Request
# ("sofortige Wirkung", kein Hintergrund-Job), reassign_photo_category/derive_photo_category/
# _remote_category_evidence sind dafuer die einzig richtige, bereits bestehende
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
    """EINE Zugehoerigkeit eines Fotos zu einer Kategorie aus der Kriterien-/Rangfolgen-Pipeline
    (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md). Seit
    specs/features/0040-bewertungsdetails-info-popover.md auch im Standard-Listing-Zweig befuellt
    (vorher nur bei `top_n_per_category`), nicht mehr nur, wenn das Foto Teil des abgefragten
    Top-N-Ergebnisses ist. Getrennt von SuggestionOut, siehe dessen Docstring.

    specs/features/0300-nebenkategorien.md: ein Foto hat pro Lauf eine solche Zeile JE KATEGORIE,
    zu der es gehoert - siehe `PhotoOut.rankings`."""

    cluster_key: str
    category_key: str
    rank_score: float
    rank_position: int
    # Groesse der GESAMTEN Cluster x Kategorie-Partition (nicht nur der angeforderten top_n),
    # fuer "Rang M von N" im Info-Popover (specs/features/0040-bewertungsdetails-info-popover.md,
    # Architektur-Abschnitt) - lauf-global berechnet (siehe _partition_sizes), nicht
    # nutzerspezifisch gefiltert. Zaehlt seit Spec 0300 ALLE Zeilen der Partition, Haupt- wie
    # Nebenzeilen: die Frage lautet "wie viele Fotos stehen in dieser Kategorie dieses Clusters",
    # und dort steht ein Foto mit Nebenzugehoerigkeit tatsaechlich.
    partition_size: int
    # specs/features/0300-nebenkategorien.md: ob dies die HAUPTkategorie des Fotos ist. Genau eine
    # Zugehoerigkeit je Foto und Lauf traegt `true`. Die Oberflaeche liest die Rolle ausschliesslich
    # hier ab und bildet nirgends eine Schwelle nach.
    is_primary: bool
    # Der Platz DIESER Zugehoerigkeit in der ANGEZEIGTEN Auswahl ihrer Kategorie. `null`, wenn
    # diese Zugehoerigkeit nicht zur angeforderten Auswahl gehoert oder gar keine angefordert
    # wurde.
    #
    # specs/features/0357-voller-bildvorrat-kuratierung.md, ADR 0071 Entscheidung 2: Der
    # Ablehnungsfilter der Kuratierungs-Query ist entfallen, der Wert ist damit ENTWEDER `null`
    # ODER gleich `rank_position` - nicht mehr das um die eigenen Ablehnungen bereinigte
    # `row_number()`, und nicht mehr nutzerabhaengig.
    #
    # Das Feld bleibt trotz des Zusammenfallens bestehen, weil es eine ANDERE Frage beantwortet
    # als `rank_position`: jene ist die lauf-globale Rangaussage des Info-Popovers (unabhaengig
    # vom Query-Parameter), diese hier die Zugehoerigkeit zur angeforderten Auswahl ("unter
    # welchen seiner Kategorien ist dieses Foto zu zeigen"). Es ist seit
    # specs/features/0300-nebenkategorien.md die einzige Auskunft darueber; ohne sie muesste das
    # Frontend die Auswahlregel nachbilden.
    curation_position: int | None = None


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
    Modellantwort zeichensaniert worden (cloud_vision.py::_sanitize_label_text) und
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
    # specs/features/0299-kategorie-konfidenz-anzeigen.md, ADR 0067 Punkt 2: die
    # Selbsteinschaetzung des Modells zu DIESEM Schluessel. `None` heisst "keine Modellaussage",
    # nie `0.0` (das hiesse "das Modell war sich zu 0 % sicher").
    #
    # Ausdruecklich KEINE Wiederkehr des mit Spec 0289 entfallenen `score`-Felds: jenes war die
    # Rechengroesse der abgeschafften Zahlenvergleichs-Auswahl. Diese Zahl beeinflusst weder
    # Auswahl noch Sortierung noch irgendeine Schwelle im Backend - sie wird angezeigt und
    # ausgewertet, sonst nichts.
    #
    # Die Zahl folgt dem SCHLUESSEL, nicht der `origin`-Kennzeichnung: ein lokal UND remote
    # erkannter Schluessel wird unten zu `origin="local"` zusammengefasst (die spezifischere
    # Herkunftsaussage), traegt aber die Modellzahl weiter - es gibt eine Modellaussage zu diesem
    # Schluessel. Ein REIN lokaler Kandidat bekommt `None`.
    confidence: float | None = None


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


class PhotoLocationOut(BaseModel):
    """Der Ort DIESES Fotos (specs/features/0051-gps-landmark-cluster-bildung.md, ADR 0072
    Entscheidung 1) - in VOLLER EXIF-Praezision, ohne serverseitige Rundung (Daniels Entscheidung;
    die Rundung auf zwei Nachkommastellen liegt allein in `ClusterPlaceOut`, weil dort dieselbe
    Zahl ueber "coordinate" vs. "multiple" entscheidet).

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


class ClusterPlaceOut(BaseModel):
    """Der bereits AUFGELOESTE Ort des CLUSTERS (specs/features/0051-gps-landmark-cluster-
    bildung.md, ADR 0072 Entscheidung 1) - auf jedem Foto desselben Clusters identisch, `null`
    ohne jede Ortsinformation.

    Der Server liefert den fertigen ZUSTAND, nicht die Rohdaten fuer eine Rangfolge: `kind` benennt,
    welche Stufe (erkannte Sehenswuerdigkeit -> ungefaehre Koordinate -> mehrere Orte) tatsaechlich
    gilt. Das Frontend bildet die Rangfolge NICHT nach, es formatiert nur.

    Warum das nicht im Frontend entstehen kann: die Kuratierungsansicht sieht je Partition nur
    `rank_position <= topN` (ADR 0071), die nachgeladenen Kandidaten laufen ueber eine eigene
    Abfrage und fliessen nie in `items` zurueck. Jede Aussage, die eine AGGREGATION ueber den
    Cluster ist, waere dort dauerhaft eine Aussage ueber die Top-N - sowohl "Mehrere Orte" als auch
    der Sehenswuerdigkeit-Name.

    `kind="multiple"` traegt STRUKTURELL keine Koordinate: es gibt den einen Ort, den sie
    repraesentieren muesste, gerade nicht. Zwei Felder statt einer stellvertretenden Zahl zu
    fuehren waere eine zweite, stille Wahrheit.

    `landmark_name` ist freier, extern erzeugter LLM-Text (`PhotoLandmarkDetection.name`, Spec
    0047) - dieselbe Auflage wie bei `FineLabelOut.raw_label`: ausschliesslich als regulaerer
    React-Textknoten rendern, nie `dangerouslySetInnerHTML`, nie als HTML-String-Prop, nie in
    `href`/`src`/`style`, nie als React-`key`.

    Wird NIRGENDS persistiert."""

    kind: Literal["landmark", "coordinate", "multiple"]
    landmark_name: str | None = None
    lat: float | None = None
    lon: float | None = None


class PhotoOut(BaseModel):
    id: int
    relative_path: str
    taken_at: datetime
    ratings: list[RatingOut]
    suggestion: SuggestionOut | None
    # ALLE Zugehoerigkeiten des Fotos im letzten erfolgreichen Lauf, in beiden Query-Modi
    # (specs/features/0300-nebenkategorien.md, ADR 0069 Punkt 7). Immer eine Liste, nie `null`
    # (analog `ratings`) - leer, solange kein erfolgreicher Lauf existiert.
    #
    # REIHENFOLGE FESTGELEGT: Hauptzeile zuerst, danach die Nebenzeilen in
    # Registry-Anzeigereihenfolge. Sonst flackerte die Anzeige mit der Zeilenreihenfolge der
    # Datenbank.
    #
    # Ersetzt das entfallene `ranking: RankingOut | None`. Der brechende Feldwechsel ist
    # beabsichtigt: der Compiler soll an jeder Lesestelle erzwingen, dass sie sich entscheidet,
    # welche Zugehoerigkeit sie meint - ein beibehaltenes `ranking` neben `rankings` waere genau
    # die zweite, driftende Abbildung derselben Sache.
    rankings: list[RankingOut]
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
    # specs/features/0299-kategorie-konfidenz-anzeigen.md: die Konfidenz zu `remote_category`
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
    # specs/features/0058-cloud-vision-status-transparenz.md: immer genau 2 Eintraege (einer je
    # CloudVisionPhase), feste Reihenfolge [landmark, remote_category] - siehe
    # _cloud_vision_status_out.
    cloud_vision_status: list[CloudVisionStatusOut]
    # specs/features/0051-gps-landmark-cluster-bildung.md, ADR 0072 Entscheidung 1: zwei additive,
    # OPTIONALE Felder mit Vorgabewert `null` - damit bleiben bestehende Testfixturen unveraendert.
    # Beide werden einheitlich auf ALLEN Lesepfaden ausgeliefert (Daniels Entscheidung, 2026-09-09),
    # nicht nur im Kuratierungsmodus: ein je Query-Modus divergierendes `PhotoOut` waere genau die
    # "zweite, driftende Abbildung", vor der der `rankings`-Kommentar oben warnt.
    location: PhotoLocationOut | None = None
    cluster_place: ClusterPlaceOut | None = None


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
    # specs/features/0299-kategorie-konfidenz-anzeigen.md: die Konfidenz-Abbildung wird GETRENNT
    # von den Herkunftsangaben gefuehrt und erst ganz unten je Schluessel nachgeschlagen - genau
    # deshalb ueberlebt die Zahl das Zusammenfassen eines lokal UND remote erkannten Schluessels
    # zu `origin="local"`. `or {}` deckt beide "keine Angabe"-Formen ab: keine
    # Klassifizierungszeile und eine Altzeile mit `NULL` (Akzeptanzkriterium 9).
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


# Anzeigerundung der Cluster-Koordinate: zwei Nachkommastellen entsprechen rund 1,1 km
# (specs/features/0051-gps-landmark-cluster-bildung.md, Daniels Entscheidung "grob, ~1 km").
# Die Rundung liegt im BACKEND, weil dieselbe Zahl hier ueber `"coordinate"` vs. `"multiple"`
# entscheidet - eine Rundung im Frontend koennte die Stufe gar nicht bestimmen, ohne den
# vollstaendigen Cluster zu kennen. Das Frontend formatiert den bereits gerundeten Wert nur noch.
_CLUSTER_PLACE_COORDINATE_DIGITS = 2


def _rounded(value: float) -> float:
    """Auf die Anzeigegenauigkeit gerundet, mit `-0.0` normalisiert auf `0.0`.

    `-0.0` waere im JSON `-0.0` und im Frontend `"-0.00"` - eine Himmelsrichtung, die es nicht
    gibt. Die Addition von `0.0` erledigt das nach IEEE 754 ohne Sonderfallzweig
    (`-0.0 + 0.0 == +0.0`) und laesst jeden anderen Wert unveraendert."""
    return round(value, _CLUSTER_PLACE_COORDINATE_DIGITS) + 0.0


@dataclass(frozen=True)
class _ClusterMember:
    """Ein Foto des vollstaendigen Clusters, soweit es zur Ortsaussage beitraegt."""

    photo_id: int
    taken_at: datetime
    gps_lat: float | None
    gps_lon: float | None
    landmark_name: str | None


@dataclass(frozen=True)
class PhotoPlace:
    """Das Ergebnis der Ortsherleitung fuer EIN Foto - beide Antwortfelder aus derselben
    Cluster-Abfrage. `NO_PLACE` ist der Zustand "kein Ort bekannt"; er ist auch die
    AUSFALLRICHTUNG, wenn kein Bezugslauf existiert oder ein Foto keine Kandidatenzeile hat."""

    location: PhotoLocationOut | None = None
    cluster_place: ClusterPlaceOut | None = None


NO_PLACE = PhotoPlace()


def _cluster_place_of(members: list[_ClusterMember]) -> ClusterPlaceOut | None:
    """Die Stufenentscheidung ueber den VOLLSTAENDIGEN Cluster (ADR 0072 Entscheidung 1).

    Rangfolge: erkannte Sehenswuerdigkeit -> genau eine gerundete Koordinate -> mehrere Orte ->
    `None`. Der Name hat Vorrang auch dann, wenn zusaetzlich abweichende Koordinaten vorliegen.

    `members` ist bereits nach `(taken_at, photo_id)` sortiert: nach der Verfeinerung traegt ein
    Cluster hoechstens EINEN Namen - defensiv gewinnt der des chronologisch fruehesten Fotos, damit
    die Anzeige auch bei einem Altbestand deterministisch bleibt."""
    for member in members:
        if member.landmark_name is not None:
            return ClusterPlaceOut(kind="landmark", landmark_name=member.landmark_name)

    # VERGLICHEN WIRD DIE GERUNDETE Stelle, nicht der Rohwert: ein Vergleich der ungerundeten
    # Werte schluege schon bei zwei 40 m auseinanderliegenden Aufnahmen zu und machte aus einem
    # einzelnen Ortsbesuch "Mehrere Orte".
    cells = {
        (_rounded(member.gps_lat), _rounded(member.gps_lon))
        for member in members
        if member.gps_lat is not None and member.gps_lon is not None
    }
    if not cells:
        return None
    if len(cells) > 1:
        # Traegt STRUKTURELL keine Koordinate - es gibt den einen Ort, den sie repraesentieren
        # muesste, gerade nicht.
        return ClusterPlaceOut(kind="multiple")
    [(lat, lon)] = cells
    return ClusterPlaceOut(kind="coordinate", lat=lat, lon=lon)


def _derived_location_of(
    photo: Photo, anchors: list[_ClusterMember]
) -> PhotoLocationOut | None:
    """Der Ort EINES Fotos: die eigene Koordinate in voller Praezision, sonst die des zeitlich
    naechstgelegenen Fotos MIT Koordinate im selben Cluster.

    `anchors` sind die koordinatentragenden Mitglieder, aufsteigend nach `(taken_at, photo_id)`.
    Tie-Break (deterministisch, sonst haenge die angezeigte Koordinate an der Zeilenreihenfolge der
    Datenbank): bei gleichem Abstand gewinnt der FRUEHERE Zeitpunkt, bei identischem `taken_at` die
    kleinere `photo_id` - beides ergibt sich aus der Sortierung plus dem `<=`-Vergleich unten."""
    if photo.gps_lat is not None and photo.gps_lon is not None:
        return PhotoLocationOut(lat=photo.gps_lat, lon=photo.gps_lon, source="exif")
    if not anchors:
        return None

    index = bisect_left([anchor.taken_at for anchor in anchors], photo.taken_at)
    nearest = anchors[min(index, len(anchors) - 1)]
    if index > 0:
        earlier = anchors[index - 1]
        if index >= len(anchors) or (photo.taken_at - earlier.taken_at) <= (
            nearest.taken_at - photo.taken_at
        ):
            nearest = earlier

    assert nearest.gps_lat is not None and nearest.gps_lon is not None
    return PhotoLocationOut(lat=nearest.gps_lat, lon=nearest.gps_lon, source="derived")


async def _place_by_photo_id(
    session: AsyncSession,
    criterion_scoring_run_id: int | None,
    photos_by_id: Mapping[int, Photo],
    rankings_by_photo_id: Mapping[int, Sequence[PhotoRanking]],
) -> dict[int, PhotoPlace]:
    """Beide Ortsfelder aller Fotos einer Antwort - aus EINER Abfrage ueber den VOLLSTAENDIGEN
    Cluster des Bezugslaufs (specs/features/0051-gps-landmark-cluster-bildung.md, ADR 0072
    Entscheidung 1/7).

    Die Bezugsmenge ist ausdruecklich NICHT die Antwort: die Kuratierungsansicht liefert je
    Partition nur `rank_position <= topN`, und die nachgeladenen Kandidaten fliessen nie in `items`
    zurueck (eigene Abfrage in `CurationCandidates.tsx`). Ueber die Fotos der Antwort hergeleitet
    waere der Cluster-Ort deshalb nicht "springend", sondern DAUERHAFT eine Aussage ueber die
    Top-N - und `topN` ist zusaetzlich ein Suchparameter der Seite (1-10).

    SICHERHEIT - Laufbindung (Muss-Kriterium der Spec, gilt fuer BEIDE Felder): `cluster_key` ist
    `cluster-<n>`, je Lauf neu vergeben und IN JEDEM PROJEKT DERSELBE STRING; `photo_rankings`
    traegt keine `project_id`. Die einzige Bindung eines Clusters an sein Projekt ist
    `criterion_scoring_run_id` aus `_latest_successful_criterion_scoring_run_id(session,
    project_id)`. Dieses Praedikat steht deshalb AUSGESCHRIEBEN in der Abfrage unten - ohne es
    ordnete die Herleitung SYSTEMATISCH (nicht im Grenzfall) Koordinaten aus fremden Projekten zu
    und benennte ein Cluster nach einer Sehenswuerdigkeit aus einem fremden Projekt, weil die
    Schluesselkollision garantiert ist. `_photos_by_id` filtert nur nach Id und ist ausdruecklich
    KEINE zweite Verteidigungslinie.

    Die Lauf-Id wird EINMAL PRO REQUEST aufgeloest und hierher durchgereicht, nie innerhalb dieser
    Funktion neu bestimmt - sonst traefen Rangzeilen aus Lauf A auf Cluster-Mitgliedschaften aus
    Lauf B, sobald zwischen zwei Queries ein Lauf fertig wird. Fehlt sie, bleibt es bei der EIGENEN
    EXIF-Koordinate: die Ausfallrichtung ist "nichts anzeigen", nie "aus irgendeinem Lauf
    herleiten".

    Gelesen wird `PhotoRanking.cluster_key` (der landmark-VERFEINERTE Schluessel), nicht
    `PhotoScore.cluster_key` - der groebere fuehrte den Ort ueber genau die Landmark-Grenze hinweg,
    die dieses Feature gerade zieht.

    VERFUEGBARKEIT: EIN Query pro Request, nicht einer pro Foto (Praezedenz `_partition_sizes`).
    Die Ergebnismenge ist durch die Projektgroesse begrenzt - dieselbe Schranke, unter der
    `_partition_sizes` bereits laeuft."""
    # Alle Rangzeilen EINES Fotos tragen denselben cluster_key (die Partitionen sind
    # cluster x kategorie, die Cluster-Zugehoerigkeit ist pro Foto eindeutig) - die erste genuegt.
    cluster_key_by_photo_id = {
        photo_id: rankings[0].cluster_key
        for photo_id, rankings in rankings_by_photo_id.items()
        if rankings
    }
    cluster_keys = set(cluster_key_by_photo_id.values())
    if criterion_scoring_run_id is None or not cluster_keys:
        return {
            photo_id: PhotoPlace(location=_derived_location_of(photo, []))
            for photo_id, photo in photos_by_id.items()
        }

    landmark = aliased(PhotoLandmarkDetection)
    rows = (
        await session.execute(
            select(
                PhotoRanking.cluster_key,
                Photo.id,
                Photo.taken_at,
                Photo.gps_lat,
                Photo.gps_lon,
                landmark.name,
            )
            .join(Photo, Photo.id == PhotoRanking.photo_id)
            .join(landmark, landmark.photo_id == Photo.id, isouter=True)
            .where(
                # SICHERHEIT: das Pflichtpraedikat, siehe Docstring. Nie `cluster_key` allein.
                PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
                PhotoRanking.cluster_key.in_(cluster_keys),
                # Nur Zeilen, die ueberhaupt etwas zur Ortsaussage beitragen - die Ergebnismenge
                # bleibt damit deutlich unter der Partitionsgroesse.
                (Photo.gps_lat.is_not(None)) | (landmark.name.is_not(None)),
            )
            # Ein Foto hat je Kategorie eine eigene Rangzeile - ohne `distinct` erschiene es
            # mehrfach im selben Cluster und verzerrte den Tie-Break der Herleitung.
            .distinct()
        )
    ).all()

    members_by_cluster: dict[str, list[_ClusterMember]] = {}
    for cluster_key, photo_id, taken_at, gps_lat, gps_lon, landmark_name in rows:
        members_by_cluster.setdefault(cluster_key, []).append(
            _ClusterMember(
                photo_id=photo_id,
                taken_at=taken_at,
                gps_lat=gps_lat,
                gps_lon=gps_lon,
                # SANITISIERUNG IM LESEPFAD (Muss-Kriterium des Sicherheitskonzepts, Abschnitt
                # "Standortdaten"): `sanitize_landmark_name` wirkt hier ein ZWEITES Mal, obwohl
                # `landmark.py::_landmark_detection_from_json` sie bereits an der Quelle anwendet.
                # Das ist KEIN Redundanz-Fehlgriff, sondern die einzige Deckung des Altbestands:
                # unter Spec 0047 sind bereits reale, kostenpflichtig erzeugte Zeilen mit
                # unsaniertem Rohtext entstanden - sie neu zu erkennen kostet Geld, sie zu loeschen
                # vernichtet bezahlte Daten, und einen kostenlosen Migrationsweg gibt es nicht
                # (anders als beim Feinlabel-Fall, der mit einem UPDATE zu heilen war).
                # BITTE NICHT als vermeintliche Dopplung entfernen.
                landmark_name=sanitize_landmark_name(landmark_name),
            )
        )

    place_by_cluster: dict[str, tuple[ClusterPlaceOut | None, list[_ClusterMember]]] = {}
    for cluster_key, members in members_by_cluster.items():
        members.sort(key=lambda member: (member.taken_at, member.photo_id))
        anchors = [
            member
            for member in members
            if member.gps_lat is not None and member.gps_lon is not None
        ]
        place_by_cluster[cluster_key] = (_cluster_place_of(members), anchors)

    result: dict[int, PhotoPlace] = {}
    for photo_id, photo in photos_by_id.items():
        cluster_key = cluster_key_by_photo_id.get(photo_id)
        cluster_place, anchors = place_by_cluster.get(cluster_key or "", (None, []))
        result[photo_id] = PhotoPlace(
            location=_derived_location_of(photo, anchors), cluster_place=cluster_place
        )
    return result


def _to_photo_out(
    photo: Photo,
    current_user_id: int,
    project: Project,
    rankings: Sequence[PhotoRanking] = (),
    partition_sizes: Mapping[tuple[str, str], int] | None = None,
    curation_positions: Mapping[tuple[int, str], int] | None = None,
    place: PhotoPlace = NO_PLACE,
) -> PhotoOut:
    """Baut die Antwortdarstellung EINES Fotos.

    SICHERHEIT - die Antwort ist eine Funktion des ANFRAGENDEN Nutzers
    (specs/features/0357-voller-bildvorrat-kuratierung.md, ADR 0071 Entscheidung 2; die Auflage
    stand vor dieser Spec am Feld `RankingOut.curation_position` und ist mit ihrer Begruendung
    hierher gewandert, nicht entfallen):

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

    `curation_position` traegt sie seit ADR 0071 ebenfalls nicht mehr (kein Ablehnungsfilter, kein
    Nutzerbezug)."""
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
        rankings=[
            RankingOut(
                cluster_key=ranking.cluster_key,
                category_key=ranking.category_key,
                rank_score=ranking.rank_score,
                rank_position=ranking.rank_position,
                partition_size=(partition_sizes or {}).get(
                    (ranking.cluster_key, ranking.category_key), 0
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
        # specs/features/0051-gps-landmark-cluster-bildung.md: beide Felder kommen fertig aus
        # `_place_by_photo_id` (EINE Abfrage ueber den vollstaendigen Cluster des Bezugslaufs).
        # Der Vorgabewert `NO_PLACE` haelt die Ausfallrichtung fest: eine vergessene Durchreichung
        # ergibt `null`, nie einen falschen Ort.
        location=place.location,
        cluster_place=place.cluster_place,
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
    """Kategorie-Kuratierung (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
    backfill.md, seit specs/features/0357-voller-bildvorrat-kuratierung.md ohne Backfill):
    liefert je Partition (cluster_key x category_key) des LETZTEN erfolgreichen
    CriterionScoringRun die Zugehoerigkeiten mit `rank_position <= top_n`.

    DER ABLEHNUNGSFILTER IST MIT ADR 0071 ENTFALLEN (Entscheidung 1). Die Query filterte bis
    dahin die vom anfragenden Nutzer REJECTED-bewerteten Fotos per Outer-Join aus und berechnete
    das `row_number()` erst danach - genau das war der Backfill aus ADR 0021 Punkt 4. Ohne den
    Filter ist die Fensterfunktion ueberfluessig: `PhotoRanking.rank_position` ist je Partition
    lueckenlos ab 1 vergeben (`ranking.py::rank_photos` liefert `index + 1` ueber die
    VOLLSTAENDIGE Partition; `worker.py::run_criterion_scoring` ruft sie je Partition auf, Haupt-
    wie Nebenzugehoerigkeiten in derselben Liste; `worker.py::reassign_photo_category` vergibt bei
    einem Override die Positionen beider betroffenen Partitionen vollstaendig neu). Ein
    `row_number()` ueber dieselbe Sortierung lieferte per Konstruktion denselben Wert - es hat
    ausschliesslich die Luecken geschlossen, die der Ablehnungsfilter riss.

    Folge: Welche Fotos die Ansicht zeigt, haengt ausschliesslich vom LAUF ab, nicht mehr vom
    Bewertungsstand des Betrachters. Ein verworfenes Foto bleibt an seiner Position und traegt
    seinen Zustand in `PhotoOut.ratings[]` (ADR 0071 Entscheidung 3).

    `top_n` wirkt weiterhin JE PARTITION, Neben- wie Hauptzeilen zaehlen mit
    (specs/features/0300-nebenkategorien.md); EIN Foto kann in mehreren Partitionen unter die
    Top-N fallen. Rueckgabe deshalb dreiteilig:

    * die Foto-Ids in Anzeigereihenfolge, jede hoechstens EINMAL (`PhotoListOut.items` enthaelt
      jedes Foto weiterhin hoechstens einmal),
    * die `curation_position` je (photo_id, category_key) - nach dem Wegfall des Filters
      identisch mit `rank_position` -, aus der die Kuratierungsansicht ablesen kann, in welchen
      Kategorien sie das Foto zeigen soll,
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
        .order_by(
            PhotoRanking.cluster_key, PhotoRanking.category_key, PhotoRanking.rank_position
        )
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
) -> dict[tuple[str, str], int]:
    """Groesse jeder Cluster x Kategorie-Partition eines Laufs, fuer "Rang M von N" im Info-
    Popover (specs/features/0040-bewertungsdetails-info-popover.md, Architektur-Abschnitt) - ein
    einzelner GROUP BY-Query pro list_photos-Aufruf (nicht pro Foto). Bewusst lauf-global, nicht
    nutzerspezifisch gefiltert - siehe RankingOut.partition_size-Docstring.

    Zaehlt AUSDRUECKLICH ALLE Zeilen der Partition, Haupt- wie Nebenzeilen (specs/features/0300-
    nebenkategorien.md, ADR 0069 Punkt 8) - anders als die Kategorienverteilung der Statistikseite
    und `category_diff.py`, die auf `is_primary` filtern. Zwei Zaehlweisen, zwei Fragen: hier "wie
    viele Fotos stehen in dieser Kategorie dieses Clusters", dort "welche Kategorie hat dieses
    Foto"."""
    result = await session.execute(
        select(PhotoRanking.cluster_key, PhotoRanking.category_key, func.count())
        .where(PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id)
        .group_by(PhotoRanking.cluster_key, PhotoRanking.category_key)
    )
    return {(cluster_key, category_key): count for cluster_key, category_key, count in result.all()}


# Registry-Anzeigereihenfolge als Rang - dieselbe Reihenfolge wie `GET /categories` und die
# Kandidatenliste, damit kategoriale Listen ueberall im Produkt gleich aussehen.
_CATEGORY_DISPLAY_ORDER = {key: index for index, key in enumerate(CATEGORY_REGISTRY)}


def _ranking_sort_key(ranking: PhotoRanking) -> tuple[int, int, str]:
    """Hauptzeile zuerst, danach die Nebenzeilen in Registry-Anzeigereihenfolge
    (specs/features/0300-nebenkategorien.md, ADR 0069 Punkt 7) - ohne diese feste Ordnung
    flackerte die Anzeige mit der Zeilenreihenfolge der Datenbank.

    Ein `category_key` ausserhalb des festen Sets (Altbestand; der Lesepfad ist seit Spec 0289
    bewusst tolerant) landet hinten und dort alphabetisch stabil, statt die Sortierung zu
    sprengen."""
    return (
        0 if ranking.is_primary else 1,
        _CATEGORY_DISPLAY_ORDER.get(ranking.category_key, len(_CATEGORY_DISPLAY_ORDER)),
        ranking.category_key,
    )


async def _rankings_by_photo_id(
    session: AsyncSession, criterion_scoring_run_id: int, photo_ids: list[int]
) -> dict[int, list[PhotoRanking]]:
    """ALLE Zugehoerigkeiten je Foto, nicht mehr genau eine (specs/features/0300-
    nebenkategorien.md): seit dem Kardinalitaetswechsel 1:1 -> 1:N ist ein
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
        place_by_id = await _place_by_photo_id(
            session, criterion_scoring_run_id, photos_by_id, rankings_by_id
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
    place_by_id = await _place_by_photo_id(session, latest_run_id, photos_by_id, rankings_by_id)
    items = [
        _to_photo_out(
            photos_by_id[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id, []),
            partition_sizes,
            # Ohne angeforderte Auswahl traegt JEDE Zugehoerigkeit `curation_position = null`
            # (specs/features/0300-nebenkategorien.md, Akzeptanzkriterium 23) - es gibt in diesem
            # Modus keine Auswahl, zu der sie eine Position haben koennte.
            None,
            place_by_id.get(photo_id, NO_PLACE),
        )
        for photo_id in ids
    ]
    return PhotoListOut(items=items, total=total)


# Obergrenze der beiden freien Partitionsschluessel (specs/features/0357-voller-bildvorrat-
# kuratierung.md, Security-Punkt 3): `cluster_key`/`category_key` werden bewusst NICHT gegen
# CATEGORY_REGISTRY geprueft - der Lesepfad ist seit Spec 0289 tolerant gegenueber Altbestand, und
# eine Allowlist waere hier ein Produkt-, kein Sicherheitsentscheid (422 statt leerer Liste). Die
# Laengengrenze ist Verteidigung in der Tiefe (Praezedenz: api/auth.py::_MAX_LOGIN_FIELD_LENGTH,
# api/projects.py::confirm_name), damit ein entarteter Wert gar nicht erst bis zum
# Datenbankvergleich kommt.
_MAX_PARTITION_KEY_LENGTH = 200

# Obergrenze von `after_rank`/`offset` (Security-Punkt 4 der Spec 0357): ein Pydantic-`int` ist
# unbeschraenkt und landet direkt im SQL-Vergleich; unter SQLite (Testlauf und lokale Entwicklung)
# wirft ein Wert jenseits von 2^63 einen `OverflowError` und damit eine 500 statt einer leeren
# Liste. Der Wert liegt weit ueber jeder realistischen Partitionsgroesse - er begrenzt einen
# Missbrauchsfall, nicht die Benutzung.
_MAX_QUERY_POSITION = 1_000_000_000


@router.get("/projects/{project_id}/curation-candidates", response_model=PhotoListOut)
async def curation_candidates(
    project_id: int,
    cluster_key: str = Query(..., max_length=_MAX_PARTITION_KEY_LENGTH),
    category_key: str = Query(..., max_length=_MAX_PARTITION_KEY_LENGTH),
    after_rank: int = Query(0, ge=0, le=_MAX_QUERY_POSITION),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0, le=_MAX_QUERY_POSITION),
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (Muss-Kriterium 2 der specs/features/0357-voller-bildvorrat-kuratierung.md):
    # ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE Router-weite
    # `dependencies`-Liste (siehe Kopfkommentar der Datei) - ein Endpunkt, der diesen Parameter
    # vergisst, waere hier STILL OEFFENTLICH: kein Fehler, keine 401, nur Daten. `current_user.id`
    # geht unveraendert an `_to_photo_out` (nie ein Platzhalter wie `0` - der liesse
    # `PhotoOut.suggestion` auch fuer laengst bewertete Fotos wieder aufblitzen).
    current_user: User = Depends(get_current_user),
) -> PhotoListOut:
    """Die weiteren Kandidaten EINER Partition, auf Abruf (specs/features/0357-voller-bildvorrat-
    kuratierung.md, ADR 0071 Entscheidung 5): die Zugehoerigkeiten mit
    `rank_position > after_rank`, aufsteigend nach `rank_position`, seitenweise ueber
    `limit`/`offset`. `total` ist die RESTMENGE der Partition (`max(partition_size - after_rank,
    0)`) und damit unabhaengig von `limit`/`offset` - sonst waere der Vorrat bei einer grossen
    Kategorie wieder nur teilweise einsehbar.

    Bezugslauf ist derselbe wie in der Hauptabfrage (letzter erfolgreicher CriterionScoringRun);
    verworfene Fotos sind enthalten und tragen ihren Zustand in `ratings[]` (ADR 0071
    Entscheidung 3). `curation_position` wird AUSSCHLIESSLICH fuer die angefragte Zugehoerigkeit
    gesetzt - sonst erschiene ein nachgeladenes Foto zusaetzlich unter seinen anderen Kategorien,
    in denen niemand aufgeklappt hat.

    Kein erfolgreicher Lauf, unbekannter `cluster_key`/`category_key` oder ein `after_rank`
    jenseits der Partitionsgroesse liefern `200` mit leerem `PhotoListOut` - kein Fehler und
    ausdruecklich keine Rueckspiegelung der uebergebenen Schluessel in einer Fehlermeldung.

    SICHERHEIT - Projektbindung (Muss-Kriterium 2 der Spec): `PhotoRanking` traegt KEINE
    `project_id`; `cluster_key` ist `cluster-<n>`, je Lauf neu vergeben und in jedem Projekt
    derselbe String, `category_key` stammt aus einem global gleichen Set. Die einzige Bindung an
    das Projekt des Pfadparameters ist `criterion_scoring_run_id` aus
    `_latest_successful_criterion_scoring_run_id(session, project_id)`. Dieses Praedikat steht
    deshalb in JEDER Abfrage dieses Endpunkts - der Zaehlabfrage hinter `total` (ueber
    `_partition_sizes`) eingeschlossen - und wird nie aus einem Query-Parameter abgeleitet.
    `_photos_by_id` filtert nur nach Id und ist ausdruecklich KEINE zweite Verteidigungslinie."""
    project = await _get_project_or_404(project_id, session)

    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        return PhotoListOut(items=[], total=0)

    partition_sizes = await _partition_sizes(session, latest_run_id)
    total = max(partition_sizes.get((cluster_key, category_key), 0) - after_rank, 0)

    rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.rank_position)
            .where(
                PhotoRanking.criterion_scoring_run_id == latest_run_id,
                PhotoRanking.cluster_key == cluster_key,
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
    # Zugehoerigkeiten desselben Fotos bleiben `null` (Akzeptanzkriterium 30).
    curation_positions = {
        (photo_id, category_key): rank_position for photo_id, rank_position in rows
    }
    photos_by_id = await _photos_by_id(session, ids)
    rankings_by_id = await _rankings_by_photo_id(session, latest_run_id, ids)
    place_by_id = await _place_by_photo_id(session, latest_run_id, photos_by_id, rankings_by_id)
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


async def _lock_photo_score(session: AsyncSession, photo_id: int) -> PhotoScore | None:
    """Sperrt die `photo_scores`-Zeile des Fotos fuer die Dauer der Transaktion
    (specs/features/0300-nebenkategorien.md, Security-Muss-Kriterium 5).

    Muss VOR dem Lesen der Ranking-Zeilen laufen: `reassign_photo_category` leitet ab Spec 0300 die
    gesamte Zugehoerigkeitsmenge neu ab und schreibt und LOESCHT dabei Zeilen im Request-Pfad. Der
    neue Unique-Constraint verhindert nur die doppelte Zugehoerigkeitszeile, nicht das Wettrennen
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
    cluster_key: str,
    new_category_key: str,
) -> None:
    """Fuehrt die Neuableitung aus und bildet einen `IntegrityError` aus dem
    `(Lauf, Foto, Kategorie)`-Constraint auf `409` ab - NIE auf eine 500
    (specs/features/0300-nebenkategorien.md, Security-Muss-Kriterium 5).

    Der Regelfall "Override auf eine bereits bestehende Nebenkategorie" laeuft ausdruecklich NICHT
    hier hinein: dort fuehrt `reassign_photo_category` beide Zeilen zu einer Hauptzeile zusammen.
    Diese Abbildung deckt den Rest ab - insbesondere zwei tatsaechlich gleichzeitige Schreibversuche
    fuer dasselbe Foto, bei denen die Sperre nicht greifen konnte."""
    try:
        await reassign_photo_category(session, run_id, photo_id, cluster_key, new_category_key)
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
    PhotoRanking-Zeile hat (409-Faelle des PUT-Endpunkts, ADR 0032 Punkt 6.3) - sonst
    `(criterion_scoring_run_id, ranking)` der HAUPTZEILE.

    Der `is_primary`-Filter ist seit specs/features/0300-nebenkategorien.md nicht optional:
    `scalar_one_or_none()` wirft ab der zweiten Zeile, und ein Foto hat ab jetzt bis zu vier.
    Gemeint ist hier ausschliesslich die Hauptzeile - aus ihr kommt der `cluster_key` fuer die
    Neuableitung."""
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
    """specs/features/0055, Akzeptanzkriterium "Manuelle Übernahme (Override) mit sofortiger
    Wirkung"; Verhaltensumkehr in specs/features/0289-feste-kategorien.md: `404` bei fehlendem
    Foto, `422` bei einem `category_key` ausserhalb des festen Sets (auch bei einem Altwert aus
    der Laufhistorie wie "unerkannt"), `409` ohne `PhotoRanking`-Zeile im aktuellen Lauf.

    AUSDRUECKLICH ERLAUBT ist seit Spec 0289 ein Set-Key, der fuer dieses Foto NIE Kandidat war
    (bisher `409`) - die Kandidatenliste ist nur noch Erklaerung, die manuelle Uebersteuerung darf
    jeden der 13 Eintraege setzen. Wirkt SOFORT im selben Request
    (`worker.py::reassign_photo_category`) - kein neuer Ranking-Algorithmus, kein voller
    Re-Scoring-Lauf.

    specs/features/0300-nebenkategorien.md: zielt der Override auf eine Kategorie, die fuer dieses
    Foto bereits NEBENkategorie ist, gibt es KEIN `409` - die Hauptzeile ersetzt die Nebenzeile.
    Die uebrigen Nebenkategorien werden aus der unveraenderten Modellaussage neu abgeleitet."""
    photo = await _get_photo_or_404(photo_id, session)

    # Whitelist-Pruefung VOR jeder Schreibaktion (Security-Abschnitt der Spec 0289, Punkt 2) -
    # nicht erst beim Bauen der Antwort.
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
    # menschliche Festlegung ist (ADR 0069 Punkt 6). Beides liegt in derselben Transaktion;
    # scheitert die Neuableitung, ist auch der Override nicht geschrieben.
    if score is not None:
        score.category_override = payload.category_key

    await _reassign_or_conflict(
        session, run_id, photo_id, ranking.cluster_key, payload.category_key
    )
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
    """specs/features/0055, Akzeptanzkriterium "Manuelle Übernahme (Override) mit sofortiger
    Wirkung": nimmt die Uebernahme zurueck und rekonstruiert den automatisch abgeleiteten
    `category_key` ueber DIESELBE Ableitung wie der Lauf selbst
    (`worker.py::_remote_category_evidence` + `derive_photo_category`) - kein zweiter,
    driftender Rechenweg. Idempotent (`204` auch ohne aktiven Override).

    specs/features/0289-feste-kategorien.md: die Rekonstruktion braucht seit dieser Spec nur noch
    die Werte DIESES Fotos - die abgeloeste Ableitung war laufweit aggregierend und musste dafuer
    den vollstaendigen Kandidatenpool laden (ADR 0032 Punkt 6.4).

    specs/features/0300-nebenkategorien.md: die Ruecknahme stellt die gesamte
    Zugehoerigkeitsmenge des automatischen Laufs wieder her - Haupt- wie Nebenzeilen."""
    await _get_photo_or_404(photo_id, session)

    # Sperre vor dem Lesen der Ranking-Zeilen (Security-Muss-Kriterium 5 der Spec 0300), siehe
    # _lock_photo_score.
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
    await _reassign_or_conflict(session, run_id, photo_id, ranking.cluster_key, new_category_key)
    await session.commit()
