from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.api.motifs import StrengthBandsOut
from photosort.config import settings
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    MotifAssessmentSource,
    Photo,
    PhotoCloudVisionError,
    PhotoLandmarkDetection,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motif_strengths import effective_strength_expression
from photosort.motifs import (
    MOTIF_REGISTRY,
    MOTIF_STRENGTH_BAND_MEDIUM,
    MOTIF_STRENGTH_BAND_STRONG,
)
from photosort.thumbnails import measure_cache_usage

# EIN aggregierender Nur-Lese-Endpunkt je Projekt. Ein Endpunkt statt mehrerer, weil die Seite eine
# Momentaufnahme ohne Filter ist - mehrere Endpunkte erzeugten mehrere Ladezustaende fuer einen
# fachlich atomaren Stand.
#
# Auth doppelt (Security-Abschnitt der Spec, Punkt 1): `current_user` als expliziter Parameter,
# weil der Bewertungsstand das User-Objekt braucht, UND `dependencies=[Depends(get_current_user)]`
# am Router. FastAPI cached die Dependency innerhalb eines Requests (identischer Callable), der
# Torwaechter kostet also weder eine zweite JWT-Pruefung noch ein zweites session.get(User, ...).
# Er ist noetig, weil dies ein NEU angelegtes Modul ist: ohne Router-Ebene hinge die Absicherung
# eines kuenftigen zweiten Endpunkts allein daran, dass niemand den Parameter vergisst.
router = APIRouter(prefix="/projects", tags=["stats"], dependencies=[Depends(get_current_user)])


class StorageOut(BaseModel):
    """`local_database_bytes_estimate` ist `None`, wenn die Groesse nicht ermittelbar ist (kein
    PostgreSQL) - die Oberflaeche unterscheidet das sichtbar von `0`."""

    opencloud_bytes: int
    local_cache_bytes: int
    local_database_bytes_estimate: int | None


class MotifEntryOut(BaseModel):
    """Eine Zeile der Motivverteilung: drei Bandzahlen und der Mittelwert.

    `display_name` kommt vom Server - es gibt bewusst KEINE TypeScript-Spiegelung des Motivsets im
    Frontend.

    Die drei Bandzahlen sind DISJUNKT und ERSCHOEPFEND: ihre Summe je Motiv ist die Zahl der
    beurteilten Fotos. Gezaehlt wird ueber der WIRKSAMEN Staerke (Korrektur schlaegt Modellaussage,
    motif_strengths.py::effective_strength_expression), nicht ueber der gespeicherten.

    `average_strength` ist das arithmetische Mittel genau dieser wirksamen Staerken und `None`
    ohne ein einziges beurteiltes Foto, NIE `0.0`: "nicht erhoben" und "das Modell sieht das Motiv
    nicht" sind verschiedene Aussagen. Ueberall mit `is None` statt truthy zu pruefen.

    KEIN `share`-Feld: ein Anteil setzte eine Grundmenge voraus, zu der die Zahlen sich summieren -
    und genau das tun sie seit diesem Motivset nicht mehr."""

    motif_key: str
    display_name: str
    strong_photo_count: int
    medium_photo_count: int
    weak_photo_count: int
    average_strength: float | None


class CostByPurposeOut(BaseModel):
    """`has_unrecorded_runs` ist wahr, wenn mindestens einer der beiden Befunde zutrifft. Es wird
    nichts geschaetzt und nichts hochgerechnet; der Betrag bleibt die Summe des tatsaechlich
    Erfassten."""

    purpose: CloudVisionPhase
    cost_usd: float
    has_unrecorded_runs: bool


class CostOut(BaseModel):
    """`total_usd` wird UNGERUNDET ausgeliefert und erst im Frontend formatiert, damit die
    angezeigte Summe exakt der Summe der angezeigten Einzelposten entspricht."""

    currency: str
    total_usd: float
    by_purpose: list[CostByPurposeOut]


class ProgressOut(BaseModel):
    """Die fuenf Verarbeitungsstufen aus Akzeptanzkriterium F1. Bezugsgroesse ist ueberall
    `photo_count`.

    Bewusst OHNE eine sechste Kennzahl "Kriterien berechnet" (`photo_criterion_scores`), die die
    Response-Skizze des Architekturabschnitts noch mitfuehrte: F1 zaehlt genau fuenf Stufen auf,
    und das Akzeptanzkriterium "Darstellung und Abgrenzung" schliesst Kennzahlen ueber diesen
    Katalog hinaus ausdruecklich aus. Fuer den Leser waere sie zudem inhaltlich redundant zu
    `ranked` (beide entstehen im selben Lauf)."""

    scanned: int
    thumbnails_ready: int
    ausschuss_scored: int
    ranked: int
    remote_classified: int


class RatingsOut(BaseModel):
    """AUSSCHLIESSLICH die Bewertungen des angemeldeten Nutzers (Security-Abschnitt der Spec,
    Punkt 2). `unrated` ist die Differenz zur Fotoanzahl, NIE `photos_total - COUNT(ratings)` -
    letzteres zaehlte die Bewertungen der anderen Person mit und machte deren Fortschritt aus der
    Differenz rekonstruierbar.

    DIE VIER WERTE ZERLEGEN DEN BESTAND NICHT: `favorite` ist seit ADR 0098 eine eigene Spalte
    und steht NEBEN der Albumentscheidung - dasselbe Foto kann in `favorite` und in
    `album_worthy` zaehlen. Erschoepfend und ueberschneidungsfrei sind allein die drei Zahlen der
    Albumentscheidung: `album_worthy + rejected + unrated == photo_count`. Die Oberflaeche darf
    keine Aufteilung des Bestands ueber alle vier behaupten."""

    favorite: int
    album_worthy: int
    rejected: int
    unrated: int


class LastSuccessfulRunsOut(BaseModel):
    """Jeweils `finished_at` des zuletzt ERFOLGREICH beendeten Laufs; `None` heisst "noch nie
    gelaufen". Ein laufender oder fehlgeschlagener Lauf veraendert den Wert nicht."""

    scan: datetime | None
    scoring: datetime | None
    classification: datetime | None
    remote_category_classification: datetime | None


class RemoteFailureOut(BaseModel):
    """IST-Zustand, keine Historie (ein erfolgreicher Retry loescht die Zeile) - die
    Oberflaeche formuliert das entsprechend."""

    purpose: CloudVisionPhase
    photo_count: int


class DiagnosticsOut(BaseModel):
    """`last_scan_files_skipped` ist `None`, wenn nie gescannt wurde - ausdruecklich nicht `0`."""

    last_scan_files_skipped: int | None
    duplicate_photo_count: int
    remote_failures: list[RemoteFailureOut]


class ProjectStatsOut(BaseModel):
    """Die vollstaendige Momentaufnahme eines Projekts. Ausschliesslich explizite Pydantic-
    Modelle, kein Durchreichen von ORM-Objekten (Security-Muss-Kriterium der Spec)."""

    photo_count: int
    storage: StorageOut
    taken_at_earliest: datetime | None
    taken_at_latest: datetime | None
    # EIN Block statt der beiden Kategorie-Bloecke: eine Zeile je Motiv in Registry-Reihenfolge,
    # immer alle acht. Die Summe ueber alle Zeilen ist ausdruecklich NICHT die Fotoanzahl - ein
    # Foto traegt alle acht Motive mit unterschiedlicher Staerke und zaehlt in mehreren Zeilen.
    motifs: list[MotifEntryOut]
    # Die Anzeigebaender der Tabelle gehen mit, damit das Frontend sie nicht hinterlegt. Sie sind
    # KEINE Zugehoerigkeitsschwelle.
    strength_bands: StrengthBandsOut
    # Fotos ganz ohne Kopfzeile - sie fehlen in JEDER Zahl der Tabelle und stehen deshalb als
    # eigene Kennzahl daneben, nicht als achtes Nullband.
    unassessed_photo_count: int
    # Als Dokument/Screenshot ausgeschlossene Fotos. Projektweit, weil das die einzige Stelle ist,
    # an der ein systematisch ueberschiessendes Modell auffaellt statt fotoweise entdeckt zu
    # werden; der Ausschluss hat keinen Korrekturpfad.
    excluded_photo_count: int
    # Korrektur-ZEILEN, nicht Fotos: ein Foto kann bis zu acht tragen. Gezaehlt werden auch
    # Korrekturen auf einem Foto ohne Kopfzeile - die Tabelle ist lauf-unabhaengig.
    motif_correction_count: int
    cost: CostOut
    progress: ProgressOut
    ratings: RatingsOut
    last_successful_runs: LastSuccessfulRunsOut
    diagnostics: DiagnosticsOut


COST_CURRENCY = "USD"

# Statisches SQL-Literal mit `current_database()` - NIE ein per f-String zusammengesetzter
# Datenbankname (Security-Abschnitt der Spec, Punkt 3).
_DATABASE_SIZE_SQL = text("SELECT pg_database_size(current_database())")


def database_share_bytes(
    total_database_bytes: int, project_photo_count: int, total_photo_count: int
) -> int:
    """Der geschaetzte Datenbank-Anteil EINES Projekts: die Gesamtgroesse, anteilig nach seinem
    Anteil an allen Fotos der Instanz.

    Reine Funktion, damit der einzige rechnerische Sonderfall (keine Fotos in der gesamten
    Instanz - Division durch null) ohne DB testbar ist. Ergebnis dann `0`: wo keine Fotos sind,
    entfaellt auf kein Projekt ein Foto-Anteil."""
    if total_photo_count <= 0:
        return 0
    return round(total_database_bytes * project_photo_count / total_photo_count)


async def _local_database_bytes_estimate(
    session: AsyncSession, project_photo_count: int
) -> int | None:
    """Dialekt-Weiche ueber `dialect.name`, BEWUSST nicht ueber ein try/except um fehlschlagendes
    SQL: ein DBAPI-Fehlertext kann Datenbank-, Host- und Verbindungsangaben enthalten
    (Security-Abschnitt der Spec, Punkt 3). Ausserhalb Postgres wird gar kein SQL abgesetzt und
    der Wert ist `None` ("nicht ermittelbar"), nicht `0`."""
    if session.get_bind().dialect.name != "postgresql":
        return None
    total_database_bytes = (await session.execute(_DATABASE_SIZE_SQL)).scalar_one()
    total_photo_count = (await session.execute(select(func.count(Photo.id)))).scalar_one()
    return database_share_bytes(
        int(total_database_bytes), project_photo_count, int(total_photo_count)
    )


async def _get_project_or_404(project_id: int, session: AsyncSession) -> Project:
    """Reine Existenzpruefung (dasselbe Muster wie in api/projects.py/api/photos.py) - KEINE
    Autorisierungsgrenze: es gibt kein projektbezogenes Berechtigungsmodell, beide Nutzer duerfen
    alle Projekte sehen. Die Authentifizierung sitzt am Router."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


def _photos_of_project(project_id: int) -> Select[tuple[int]]:
    return select(Photo.id).where(Photo.project_id == project_id)


async def _latest_successful_criterion_scoring_run_id(
    session: AsyncSession, project_id: int
) -> int | None:
    """Bewusst identisch zu api/photos.py::_latest_successful_criterion_scoring_run_id (dort
    ebenfalls lokal gehalten): sortiert nach `started_at DESC`, damit ein neuerer FEHLGESCHLAGENER
    Lauf den aelteren erfolgreichen nicht verdraengt."""
    return (
        await session.execute(
            select(CriterionScoringRun.id)
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.started_at.desc(), CriterionScoringRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _ranked_photo_count(session: AsyncSession, latest_run_id: int | None) -> int:
    """Wie viele Fotos im letzten erfolgreichen Kriterien-Lauf eine Rangzeile haben - eine Zaehlung
    statt einer Gruppierung, weil ein Foto je Lauf in genau EINER Zeile steht.

    Die Rangfolge-Zeilen eines Laufs gehoeren strukturell zu den Fotos genau dieses Projekts, eine
    zusaetzliche Projekt-Einschraenkung waere redundant."""
    if latest_run_id is None:
        return 0
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(PhotoRanking)
                .where(PhotoRanking.criterion_scoring_run_id == latest_run_id)
            )
        ).scalar_one()
    )


def _assessed_photo_ids(project_id: int) -> Select[tuple[int]]:
    """Die BEURTEILTEN Fotos eines Projekts: Kopfzeile vorhanden UND nicht als Dokument/
    Screenshot ausgeschlossen.

    Der Ausschluss ist hier eine Einschraenkung der GRUNDMENGE und keine Nachfilterung einzelner
    Staerken: ein ausgeschlossenes Foto zaehlt in keinem Band, seine Staerken bleiben aber
    gespeichert und werden nicht auf 0 gesetzt."""
    return select(PhotoMotifAssessment.photo_id).where(
        PhotoMotifAssessment.photo_id.in_(_photos_of_project(project_id)),
        PhotoMotifAssessment.excluded_document.is_(False),
    )


async def _motif_band_stats(
    session: AsyncSession, project_id: int
) -> dict[str, tuple[int, int, int, float | None]]:
    """Je Motiv: (stark, mittel, schwach, Mittelwert) - EINE GROUP-BY-Abfrage, ausdruecklich kein
    Query je Motiv und keine Zeile, die nach Python geladen wird.

    GERECHNET WIRD UEBER DER WIRKSAMEN STAERKE, nicht ueber der gespeicherten: der `CASE` aus
    `motif_strengths.py::effective_strength_expression` steht genau einmal im Repository, und die
    Aggregation bezieht ihn von dort. Der LEFT JOIN auf die Korrekturzeile laeuft ueber BEIDE
    Spalten `(photo_id, motif_key)` - allein ueber `motif_key` liefe die Korrektur eines Fotos in
    die Staerken aller anderen.

    Die drei Baender sind als `>=`-Kette formuliert und damit disjunkt und erschoepfend: jede
    Staerkezeile faellt in genau eines. Beide Grenzen inklusiv, und die Konstanten stehen nur in
    `motifs.py`.

    Projekt-Skopierung ueber `_assessed_photo_ids` ist Muss-Kriterium mit eigenem Test: keine der
    drei Motiv-Tabellen traegt eine eigene `project_id`, die Einschraenkung ist die einzige
    Trennung zwischen zwei Projekten.

    `func.avg` liefert `NULL`, wenn es keine Zeile gibt - daraus wird `None` und nie `0.0`.
    Defensiv nach `float` gecastet: SQLite und PostgreSQL liefern hier unterschiedliche
    Python-Typen (u.a. `Decimal`)."""
    effective = effective_strength_expression()
    rows = await session.execute(
        select(
            PhotoMotifStrength.motif_key,
            func.count().filter(effective >= MOTIF_STRENGTH_BAND_STRONG),
            func.count().filter(
                and_(
                    effective >= MOTIF_STRENGTH_BAND_MEDIUM,
                    effective < MOTIF_STRENGTH_BAND_STRONG,
                )
            ),
            func.count().filter(effective < MOTIF_STRENGTH_BAND_MEDIUM),
            func.avg(effective),
        )
        .select_from(PhotoMotifStrength)
        .outerjoin(
            PhotoMotifCorrection,
            (PhotoMotifCorrection.photo_id == PhotoMotifStrength.photo_id)
            & (PhotoMotifCorrection.motif_key == PhotoMotifStrength.motif_key),
        )
        .where(PhotoMotifStrength.photo_id.in_(_assessed_photo_ids(project_id)))
        .group_by(PhotoMotifStrength.motif_key)
    )
    return {
        key: (int(strong), int(medium), int(weak), None if average is None else float(average))
        for key, strong, medium, weak, average in rows.all()
    }


def _motifs_out(
    stats_by_key: dict[str, tuple[int, int, int, float | None]],
) -> list[MotifEntryOut]:
    """Reine Funktion ueber dem Aggregatergebnis - die Registry gibt Reihenfolge und Anzeigenamen
    vor, das Aggregat nur die Zahlen. Es entsteht IMMER ein Eintrag je Motiv, auch mit drei Nullen:
    eine fehlende Zeile machte die Tabelle unvollstaendig statt leer."""
    return [
        MotifEntryOut(
            motif_key=definition.key,
            display_name=definition.display_name,
            strong_photo_count=stats_by_key.get(definition.key, (0, 0, 0, None))[0],
            medium_photo_count=stats_by_key.get(definition.key, (0, 0, 0, None))[1],
            weak_photo_count=stats_by_key.get(definition.key, (0, 0, 0, None))[2],
            average_strength=stats_by_key.get(definition.key, (0, 0, 0, None))[3],
        )
        for definition in MOTIF_REGISTRY.values()
    ]


async def _cost_out(
    session: AsyncSession, project_id: int, landmark_results: int, remote_results: int
) -> CostOut:
    """Ist-Kosten je Zweck. Summiert ueber ALLE Laeufe des Projekts - auch ueber
    fehlgeschlagene: ein Lauf, der nach der Cloud-Phase gescheitert ist, hat das Geld trotzdem
    ausgegeben. Die Vorab-Schaetzung (`COST_PER_IMAGE_USD`) fliesst an keiner Stelle ein.

    `has_unrecorded_runs` ist wahr, wenn mindestens einer der beiden Befunde zutrifft:

    (a) es existiert ein Lauf ohne erfassten Betrag (`cost_usd IS NULL`, also aus der Zeit vor der
        Migration) UND das Projekt besitzt mindestens ein Ergebnis dieser Art. Die zweite
        Teilbedingung verhindert den haeufigsten Fehlalarm: ein Projekt, das die Cloud nie
        aktiviert hatte, hat zwar Altlaeufe, aber nachweislich nichts ausgegeben.
    (b) es existiert ein Lauf mit `api_calls > 0`, dessen Betrag `NULL` oder `0` ist. Bei
        Token-Preisen groesser null ist das strukturell unmoeglich und damit ein zuverlaessiger
        Indikator fuer eine Erfassungsluecke, kein heuristischer Verdacht.

    Bewusst getragene Grenze von Befund (a) beim Zweck `landmark`: ein Altlauf, der Aufrufe
    abgesetzt, aber keine Sehenswuerdigkeit gefunden hat, hinterlaesst keine
    `photo_landmark_detections`-Zeile und loest den Hinweis nicht aus. Fuer Laeufe nach der
    Migration schliesst Befund (b) die Luecke; fuer Altlaeufe ist sie nicht schliessbar, weil die
    Aufrufzahl von damals nirgends existiert."""
    landmark_cost, landmark_null_runs, landmark_gap_runs = (
        await session.execute(
            select(
                func.coalesce(func.sum(CriterionScoringRun.landmark_cost_usd), 0.0),
                func.count().filter(CriterionScoringRun.landmark_cost_usd.is_(None)),
                func.count().filter(
                    and_(
                        CriterionScoringRun.landmark_api_calls > 0,
                        or_(
                            CriterionScoringRun.landmark_cost_usd.is_(None),
                            CriterionScoringRun.landmark_cost_usd == 0,
                        ),
                    )
                ),
            ).where(CriterionScoringRun.project_id == project_id)
        )
    ).one()

    remote_cost, remote_null_runs, remote_gap_runs = (
        await session.execute(
            select(
                func.coalesce(func.sum(RemoteCategoryClassificationRun.cost_usd), 0.0),
                func.count().filter(RemoteCategoryClassificationRun.cost_usd.is_(None)),
                func.count().filter(
                    and_(
                        RemoteCategoryClassificationRun.api_calls > 0,
                        or_(
                            RemoteCategoryClassificationRun.cost_usd.is_(None),
                            RemoteCategoryClassificationRun.cost_usd == 0,
                        ),
                    )
                ),
            ).where(RemoteCategoryClassificationRun.project_id == project_id)
        )
    ).one()

    by_purpose = [
        CostByPurposeOut(
            purpose=CloudVisionPhase.LANDMARK,
            cost_usd=landmark_cost,
            has_unrecorded_runs=bool(landmark_null_runs and landmark_results)
            or bool(landmark_gap_runs),
        ),
        CostByPurposeOut(
            purpose=CloudVisionPhase.REMOTE_CATEGORY,
            cost_usd=remote_cost,
            has_unrecorded_runs=bool(remote_null_runs and remote_results) or bool(remote_gap_runs),
        ),
    ]
    return CostOut(
        currency=COST_CURRENCY,
        # Ungerundet: die Summe entspricht dadurch exakt der Summe der beiden Einzelposten.
        total_usd=sum(entry.cost_usd for entry in by_purpose),
        by_purpose=by_purpose,
    )


async def _ratings_out(
    session: AsyncSession, project_id: int, user_id: int, photo_count: int
) -> RatingsOut:
    """Ausschliesslich ueber `Rating.user_id == current_user.id` (Security-Muss-Kriterium): die
    `user_id` stammt allein aus dem JWT, der Endpunkt hat keinen `user_id`-Parameter in Pfad,
    Query oder Body.

    DREI GEFILTERTE ZAEHLUNGEN STATT EINES `group_by(Rating.status)`, und das ist keine
    Kosmetik: Seit `status` nullable ist, haette die Gruppierung eine `NULL`-Gruppe, und ein
    `sum(counts.values())` darueber zaehlte eine reine Favoritenzeile als "bewertet" mit -
    `unrated` waere zu klein, ohne dass irgendetwas bricht. `favorite` kommt aus der SPALTE, nie
    aus dem Status: der entfallene Statuswert liest sich sonst still als `0` und behauptet, es
    gebe keine Favoriten."""
    album_worthy, rejected, favorite = (
        await session.execute(
            select(
                func.count().filter(Rating.status == RatingStatus.ALBUM_WORTHY),
                func.count().filter(Rating.status == RatingStatus.REJECTED),
                func.count().filter(Rating.favorite.is_(True)),
            )
            .select_from(Rating)
            .where(Rating.photo_id.in_(_photos_of_project(project_id)), Rating.user_id == user_id)
        )
    ).one()
    return RatingsOut(
        favorite=int(favorite),
        album_worthy=int(album_worthy),
        rejected=int(rejected),
        # Abwesenheit einer eigenen ALBUMENTSCHEIDUNG - nicht Abwesenheit der Zeile. Differenz
        # zur Fotoanzahl und nie ueber COUNT(ratings) ohne User-Filter (das zaehlte die andere
        # Person mit).
        unrated=photo_count - int(album_worthy) - int(rejected),
    )


async def _last_successful_runs_out(
    session: AsyncSession, project_id: int
) -> LastSuccessfulRunsOut:
    scan, scoring, classification, remote_category = (
        await session.execute(
            select(
                *[
                    select(func.max(run_model.finished_at))
                    .where(
                        run_model.project_id == project_id,
                        run_model.status == ScanStatus.SUCCESS,
                    )
                    .scalar_subquery()
                    for run_model in (
                        ScanRun,
                        ScoringRun,
                        CriterionScoringRun,
                        RemoteCategoryClassificationRun,
                    )
                ]
            )
        )
    ).one()
    return LastSuccessfulRunsOut(
        scan=scan,
        scoring=scoring,
        classification=classification,
        remote_category_classification=remote_category,
    )


async def _diagnostics_out(
    session: AsyncSession,
    project_id: int,
    duplicate_photo_count: int,
    last_scan_files_skipped: int | None,
) -> DiagnosticsOut:
    failure_rows = await session.execute(
        select(PhotoCloudVisionError.phase, func.count())
        .where(PhotoCloudVisionError.photo_id.in_(_photos_of_project(project_id)))
        .group_by(PhotoCloudVisionError.phase)
    )
    failures_by_phase = {phase: count for phase, count in failure_rows.all()}
    return DiagnosticsOut(
        last_scan_files_skipped=last_scan_files_skipped,
        duplicate_photo_count=duplicate_photo_count,
        # Immer beide Zwecke, in Enum-Reihenfolge, auch mit 0.
        remote_failures=[
            RemoteFailureOut(purpose=phase, photo_count=failures_by_phase.get(phase, 0))
            for phase in CloudVisionPhase
        ],
    )


@router.get("/{project_id}/stats", response_model=ProjectStatsOut)
async def get_project_stats(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProjectStatsOut:
    """Momentaufnahme des Projektzustands.

    Reine Leseleistung: der Endpunkt loest keinen Lauf aus, schreibt nichts und verursacht keine
    Provider-Kosten."""
    await _get_project_or_404(project_id, session)

    # Eine Abfrage ueber `photos` LEFT JOIN `photo_scores` (1:1, `photo_id` ist dort Primary Key -
    # der Join vervielfacht keine Zeile) statt zwei: Umfang, Speicher, Aufnahmezeitraum und die
    # drei Kennzahlen aus der Ausschuss-Schicht auf einer gemeinsamen FROM-Klausel.
    (
        photo_count,
        opencloud_bytes,
        taken_at_earliest,
        taken_at_latest,
        ausschuss_scored,
        duplicate_photo_count,
    ) = (
        await session.execute(
            select(
                func.count(Photo.id),
                # SUM liefert bei 0 Fotos NULL, nicht 0 - serverseitig normalisiert.
                func.coalesce(func.sum(Photo.content_length), 0),
                func.min(Photo.taken_at),
                func.max(Photo.taken_at),
                func.count().filter(PhotoScore.photo_id.is_not(None)),
                func.count().filter(PhotoScore.duplicate_of.is_not(None)),
            )
            .select_from(Photo)
            .outerjoin(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(Photo.project_id == project_id)
        )
    ).one()

    # Gebuendelte Einzelwerte ueber verschiedene Tabellen in EINER Abfrage (Skalar-Subqueries auf
    # gemeinsamer, FROM-loser SELECT-Liste) - dieselben Werte einzeln abzufragen waeren vier
    # zusaetzliche Rundreisen. `last_scan_files_skipped` bezieht sich auf den zuletzt GESTARTETEN
    # Scan-Lauf, unabhaengig von dessen Status (Akzeptanzkriterium D2); `id` als Zweitkriterium
    # loest zwei Laeufe mit identischem Zeitstempel deterministisch auf.
    (
        landmark_results,
        remote_classified,
        assessment_count,
        excluded_photo_count,
        motif_correction_count,
        last_scan_files_skipped,
    ) = (
        await session.execute(
            select(
                select(func.count())
                .select_from(PhotoLandmarkDetection)
                .where(PhotoLandmarkDetection.photo_id.in_(_photos_of_project(project_id)))
                .scalar_subquery(),
                # "Von der Cloud beurteilt" ist eine Kopfzeile MIT `source='cloud'`, nicht das
                # bloesse Vorhandensein einer Kopfzeile: der Kriterien-Lauf schreibt fuer jedes
                # beurteilte Foto eine LOKALE Kopfzeile, und die ist kein Cloud-Ergebnis.
                select(func.count())
                .select_from(PhotoMotifAssessment)
                .where(
                    PhotoMotifAssessment.photo_id.in_(_photos_of_project(project_id)),
                    PhotoMotifAssessment.source == MotifAssessmentSource.CLOUD,
                )
                .scalar_subquery(),
                select(func.count())
                .select_from(PhotoMotifAssessment)
                .where(PhotoMotifAssessment.photo_id.in_(_photos_of_project(project_id)))
                .scalar_subquery(),
                select(func.count())
                .select_from(PhotoMotifAssessment)
                .where(
                    PhotoMotifAssessment.photo_id.in_(_photos_of_project(project_id)),
                    PhotoMotifAssessment.excluded_document.is_(True),
                )
                .scalar_subquery(),
                select(func.count())
                .select_from(PhotoMotifCorrection)
                .where(PhotoMotifCorrection.photo_id.in_(_photos_of_project(project_id)))
                .scalar_subquery(),
                select(ScanRun.files_skipped)
                .where(ScanRun.project_id == project_id)
                .order_by(ScanRun.started_at.desc(), ScanRun.id.desc())
                .limit(1)
                .scalar_subquery(),
            )
        )
    ).one()

    latest_run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    ranked_photo_count = await _ranked_photo_count(session, latest_run_id)

    cache_entries = (
        await session.execute(select(Photo.id, Photo.etag).where(Photo.project_id == project_id))
    ).all()
    # Ueber to_thread, damit die Event-Loop bei zwei os.stat je Foto nicht blockiert
    # (Security-Abschnitt der Spec, Punkt 3 "Selbst-DoS begrenzen"; die zweite Haelfte der
    # Gegenmassnahme sitzt am Frontend-Hook: kein Polling, staleTime > 0).
    cache_usage = await asyncio.to_thread(
        measure_cache_usage,
        Path(settings.photo_cache_dir),
        [(photo_id, etag) for photo_id, etag in cache_entries],
    )

    return ProjectStatsOut(
        photo_count=photo_count,
        storage=StorageOut(
            opencloud_bytes=opencloud_bytes,
            local_cache_bytes=cache_usage.total_bytes,
            local_database_bytes_estimate=await _local_database_bytes_estimate(
                session, photo_count
            ),
        ),
        taken_at_earliest=taken_at_earliest,
        taken_at_latest=taken_at_latest,
        motifs=_motifs_out(await _motif_band_stats(session, project_id)),
        strength_bands=StrengthBandsOut(
            strong=MOTIF_STRENGTH_BAND_STRONG, medium=MOTIF_STRENGTH_BAND_MEDIUM
        ),
        unassessed_photo_count=photo_count - assessment_count,
        excluded_photo_count=excluded_photo_count,
        motif_correction_count=motif_correction_count,
        cost=await _cost_out(session, project_id, landmark_results, remote_classified),
        progress=ProgressOut(
            scanned=photo_count,
            thumbnails_ready=cache_usage.complete_photo_count,
            ausschuss_scored=ausschuss_scored,
            # `ranked` zaehlt die Rangzeilen des letzten erfolgreichen Laufs - eine je Foto.
            ranked=ranked_photo_count,
            remote_classified=remote_classified,
        ),
        ratings=await _ratings_out(session, project_id, current_user.id, photo_count),
        last_successful_runs=await _last_successful_runs_out(session, project_id),
        diagnostics=await _diagnostics_out(
            session, project_id, duplicate_photo_count, last_scan_files_skipped
        ),
    )
