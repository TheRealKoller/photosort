"""Aufbau eines Projekts mit je einer Zeile in ALLEN am Projekt haengenden Tabellen.

Bewusst kein `test_*`-Modul (wird nicht eingesammelt): der Aufbau wird von
`test_project_deletion.py` (Modulebene) und `test_api_projects.py` (API-Ebene) gemeinsam
gebraucht - specs/features/0044-projekte-loeschen.md verlangt an beiden Stellen einen VOLLEN
Datengraphen und je Tabelle eine eigene Zeilenzaehlungs-Assertion.

Die Zaehlungen selbst stehen bewusst NICHT hier, sondern tabellenweise ausgeschrieben im
jeweiligen Test - nur so nennt die Fehlermeldung die vergessene Tabelle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.db import Base
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    DuplicateDecision,
    Event,
    FeedbackEvent,
    FeedbackEventKind,
    FinalSelectionDecision,
    FineLabel,
    LandmarkName,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoDuplicateDecision,
    PhotoFineLabel,
    PhotoLandmarkDetection,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    PhotoScore,
    PlaceLookup,
    Project,
    ProjectCamera,
    Rating,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)


@dataclass(frozen=True)
class ProjectGraph:
    """Die Bezugspunkte eines aufgebauten Projekts, die ein Test danach braucht."""

    project_id: int
    project_name: str
    photo_id: int
    photo_etag: str
    scan_run_id: int
    scoring_run_id: int
    criterion_scoring_run_id: int
    remote_run_id: int
    fine_label_id: int
    event_id: int
    camera_id: int


async def get_or_create_user(session: AsyncSession, username: str = "graph-user") -> User:
    existing = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    user = User(username=username, password_hash="hashed-value")
    session.add(user)
    await session.flush()
    return user


async def get_or_create_fine_label(
    session: AsyncSession, canonical_key: str = "strand"
) -> FineLabel:
    """Der projektuebergreifende Vokabular-Eintrag (ADR 0032) - bewusst wiederverwendbar, damit
    ein Test zwei Projekte auf DENSELBEN `fine_labels`-Eintrag zeigen lassen kann."""
    existing = (
        await session.execute(select(FineLabel).where(FineLabel.canonical_key == canonical_key))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    fine_label = FineLabel(
        canonical_key=canonical_key, display_name=canonical_key.capitalize(), embedding=[0.1, 0.2]
    )
    session.add(fine_label)
    await session.flush()
    return fine_label


async def build_project_graph(
    session: AsyncSession, name: str, *, fine_label_key: str = "strand"
) -> ProjectGraph:
    """Legt ein Projekt mit genau einer Zeile in jeder der fuenfzehn abhaengigen Tabellen an."""
    now = datetime.now(UTC).replace(tzinfo=None)
    user = await get_or_create_user(session)
    fine_label = await get_or_create_fine_label(session, fine_label_key)

    project = Project(
        name=name, opencloud_drive_id="drive-1", opencloud_path=f"/{name.replace(' ', '')}"
    )
    session.add(project)
    await session.flush()

    # specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 1: die Kamerazeile steht
    # ZWISCHEN Projekt und Foto und wird deshalb vor ihm angelegt und von ihm referenziert - ohne
    # diese Verknuepfung pruefte kein Vollstaendigkeitstest der Suite die neue Kante
    # `photos -> project_cameras -> projects`.
    camera = ProjectCamera(project_id=project.id, make="Canon", model="EOS 5D")
    session.add(camera)
    await session.flush()

    photo = Photo(
        project_id=project.id,
        relative_path=f"{name}/img001.jpg",
        etag=f"etag-{name}",
        content_length=1234,
        taken_at=now,
        taken_at_original=now,
        camera_id=camera.id,
        camera_probed=True,
        last_modified=now,
    )
    scan_run = ScanRun(project_id=project.id, status=ScanStatus.SUCCESS)
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    remote_run = RemoteCategoryClassificationRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add_all([photo, scan_run, scoring_run, remote_run])
    await session.flush()

    criterion_run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=ScanStatus.SUCCESS,
        # specs/features/0348-klassifizierungs-transparenz.md, ADR 0068 Punkt 3: der Graph bildet
        # den Fremdschluessel zwischen den beiden Lauf-Tabellen mit ab - sonst pruefte kein Test
        # der Suite die mit ihm entstandene Loeschreihenfolgen-Kante.
        remote_category_classification_run_id=remote_run.id,
    )
    session.add(criterion_run)
    await session.flush()

    # Das Event steht ZWISCHEN Lauf und Rangzeile und wird deshalb vor ihr angelegt und von ihr
    # referenziert - ohne diese Verknuepfung pruefte kein Vollstaendigkeitstest der Suite die neue
    # Kante `photo_rankings -> events -> criterion_scoring_runs`.
    event = Event(
        criterion_scoring_run_id=criterion_run.id,
        position=1,
        started_at=now,
        ended_at=now,
        landmark_name="Eiffelturm",
        place_kind="landmark",
    )
    session.add(event)
    await session.flush()

    session.add_all(
        [
            Rating(
                photo_id=photo.id,
                user_id=user.id,
                status=RatingStatus.ALBUM_WORTHY,
                favorite=True,
            ),
            PhotoScore(photo_id=photo.id, sharpness=0.8, exposure=0.5, computed_at=now),
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="sharpness",
                value=0.8,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=now,
            ),
            PhotoRanking(
                criterion_scoring_run_id=criterion_run.id,
                photo_id=photo.id,
                event_id=event.id,
                rank_score=0.9,
                rank_position=1,
            ),
            PhotoLandmarkDetection(
                photo_id=photo.id, name="Eiffelturm", confidence=0.9, computed_at=now
            ),
            PhotoFineLabel(
                photo_id=photo.id,
                fine_label_id=fine_label.id,
                raw_label=fine_label.display_name,
                provider="anthropic",
                computed_at=now,
            ),
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.LANDMARK,
                error_type="TimeoutError",
                error_message="zu langsam",
                attempted_at=now,
            ),
            # specs/features/0427-motive-mit-staerke.md, Auflage S16: der Graph legt in ALLEN DREI
            # Motiv-Tabellen je eine Zeile an. Der Verhaltenstest der Projektloeschung zaehlt
            # Zeilen und bestuende mit null Zeilen stillschweigend - ohne diese Zeilen prueft die
            # Loeschung der Motivdaten nichts.
            PhotoMotifAssessment(
                photo_id=photo.id,
                source=MotifAssessmentSource.CLOUD,
                excluded_document=False,
                provider="anthropic",
                computed_at=now,
            ),
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True
            ),
            # Aus demselben Grund wie die drei Motivzeilen darueber: der Verhaltenstest der
            # Projektloeschung zaehlt Zeilen und bestuende mit null Zeilen stillschweigend.
            PhotoAlbumSuitability(
                photo_id=photo.id,
                level=4,
                reason="Alle schauen in die Kamera.",
                provider="anthropic",
                computed_at=now,
            ),
            # specs/features/0431-endauswahl-gemeinsam.md: aus demselben Grund wie die Zeilen
            # darueber - der Verhaltenstest der Projektloeschung zaehlt Zeilen und bestuende mit
            # null Zeilen stillschweigend. Ohne diese Zeile prueft die Loeschung der gemeinsamen
            # Entscheidungen nichts.
            FinalSelectionDecision(photo_id=photo.id, included=True),
            # specs/features/0374-duplikate-vergleichen.md: dasselbe wie oben. Ohne diese Zeile
            # prueft die Loeschung der Ausschuss-Entscheidungen nichts - und sie sind die Menge,
            # die mitbestimmt, welche Bilddaten den Homeserver verlassen.
            PhotoDuplicateDecision(photo_id=photo.id, decision=DuplicateDecision.KEEP),
            # specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md: dasselbe wie oben.
            # Das Ereignis-Log ist append-only, die Projektloeschung ist seine EINZIGE Ausnahme
            # (S13) - ohne diese Zeile prueft sie dort nichts. `event_id` steht bewusst gesetzt
            # UND ohne Fremdschluessel: Die Spalte sieht wie eine Referenz aus und ist keine.
            # specs/features/0434-ortsnamen-fuer-events.md, Teil 2: die Ortsauskunft haengt am
            # PROJEKT und nicht am Lauf. Ohne diese Zeile pruefen die beiden
            # Vollstaendigkeitstests der Projektloeschung die neue Kante nicht, und "mit dem
            # Projekt verschwindet die Ortsspur" (S6) waere unbelegt.
            # specs/features/0469-verlaessliche-sehenswuerdigkeitsnamen.md, S8: das Namensregister
            # haengt am PROJEKT und nicht am Lauf. Ohne diese Zeile pruefen die beiden
            # Vollstaendigkeitstests der Projektloeschung die neue Kante nicht, und "mit dem
            # Projekt verschwinden die Namen der besuchten Orte" waere unbelegt.
            LandmarkName(
                project_id=project.id,
                normalized_name="zugspitze",
                display_name="Zugspitze",
                embedding=[0.3, 0.4],
                locality="Grainau",
            ),
            PlaceLookup(
                project_id=project.id,
                cell_lat=47.51,
                cell_lon=11.09,
                neighbourhood="Partenkirchen",
                locality="Garmisch-Partenkirchen",
                region="Bayern",
                country="Deutschland",
                matched_level="neighbourhood",
                source="geonames",
                resolved_at=now,
            ),
            FeedbackEvent(
                project_id=project.id,
                user_id=user.id,
                photo_id=photo.id,
                kind=FeedbackEventKind.PHOTO_REMOVED,
                criterion_scoring_run_id=criterion_run.id,
                event_id=event.id,
                level=4,
                quality=0.61,
            ),
        ]
    )
    await session.flush()

    # NACH dem `flush` der Kopfzeile: der Fremdschluessel der Staerkezeile zeigt auf
    # `photo_motif_assessments.photo_id`, nicht auf `photos.id`.
    session.add(PhotoMotifStrength(photo_id=photo.id, motif_key="menschen", strength=0.9))
    await session.flush()

    return ProjectGraph(
        project_id=project.id,
        project_name=name,
        photo_id=photo.id,
        photo_etag=photo.etag,
        scan_run_id=scan_run.id,
        scoring_run_id=scoring_run.id,
        criterion_scoring_run_id=criterion_run.id,
        remote_run_id=remote_run.id,
        fine_label_id=fine_label.id,
        event_id=event.id,
        camera_id=camera.id,
    )


async def count_rows(session: AsyncSession, table_name: str) -> int:
    """Zeilenzahl einer Tabelle ueber ihren Metadaten-Namen.

    Ueber `Base.metadata` statt ueber die Modellklasse, damit ein Test ueber die aus den
    Metadaten abgeleitete Tabellenmenge iterieren kann, ohne eine eigene Liste zu fuehren."""
    table = Base.metadata.tables[table_name]
    return (await session.execute(select(func.count()).select_from(table))).scalar_one()


def tables_reachable_from_projects() -> set[str]:
    """Alle Tabellen, die `projects` ueber Fremdschluesselkanten erreichen (transitiv).

    Gelaufen wird von Eltern zu Kindern: eine Tabelle ist erreichbar, wenn sie selbst einen
    Fremdschluessel auf eine bereits erreichbare Tabelle traegt. `users` und `fine_labels` sind
    reine Fremdschluessel-ELTERN und tauchen deshalb nie auf - es braucht keine Ausnahmeliste.

    Abgeleitet aus `Base.metadata`, damit weder Test noch Modul eine zweite Tabellenliste fuehrt
    (specs/features/0044-projekte-loeschen.md, ADR 0062)."""
    children_by_parent: dict[str, set[str]] = {}
    for table in Base.metadata.sorted_tables:
        for foreign_key in table.foreign_keys:
            children_by_parent.setdefault(foreign_key.column.table.name, set()).add(table.name)

    reachable: set[str] = set()
    stack = [Project.__tablename__]
    while stack:
        for child in children_by_parent.get(stack.pop(), ()):
            if child not in reachable:
                reachable.add(child)
                stack.append(child)
    return reachable
