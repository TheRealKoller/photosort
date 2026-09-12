"""specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 6: der Neuaufbau der
Gliederung des letzten erfolgreichen Kriterien-Laufs nach einer Versatz-Aenderung.

Die staerkste Zusage der Story steht hier: ein Neuaufbau mit Versatz `0` erzeugt DENSELBEN
Zustand wie der Lauf selbst. Sie ist der Nachweis, dass Neuaufbau und Lauf denselben Code gehen -
ohne sie gaebe es zwei Wege zur Gliederung und zur Hauptkategorie, und ein zwischenzeitlich
gesetzter Override koennte still verloren gehen (ADR 0088, Punkt 5).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.cameras import shifted
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PhotoCategoryClassification,
    PhotoRanking,
    PhotoScore,
    Project,
    ProjectCamera,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)
from photosort.scoring import TIME_CLUSTER_GAP
from photosort.thumbnails import display_path
from photosort.worker import rebuild_run_grouping, run_criterion_scoring

_BASE = datetime(2026, 8, 12, 9, 0, 0)
# Eiffelturm - eine bekannte Referenzkoordinate statt eines "plausibel aussehenden" Floats.
_EIFFEL = (48.858093, 2.294694)


async def _make_project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=name)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(
    session: AsyncSession,
    project: Project,
    path: str,
    taken_at: datetime,
    *,
    camera: ProjectCamera | None = None,
    gps: tuple[float, float] | None = None,
    suggested_status: RatingStatus | None = None,
    category_override: str | None = None,
    remote_category: str | None = None,
    cache_dir: Path | None = None,
) -> Photo:
    """Ein Foto samt `PhotoScore` - und, falls `cache_dir` gegeben, seiner display-Variante, damit
    der Kriterien-Lauf die Inhalts-Kriterien ueberhaupt berechnen kann."""
    offset = 0 if camera is None else camera.offset_minutes
    corrected = shifted(taken_at, offset)
    assert corrected is not None
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=corrected,
        taken_at_original=taken_at,
        camera_id=None if camera is None else camera.id,
        camera_probed=True,
        last_modified=taken_at,
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )
    session.add(photo)
    await session.flush()
    session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=100.0,
            exposure=0.0,
            cluster_key="cluster-0",
            suggested_status=suggested_status,
            category_override=category_override,
            computed_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    if remote_category is not None:
        session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key=remote_category,
                detected_categories=[remote_category],
                detected_category_confidences={remote_category: 0.9},
                category_confidence=0.9,
                provider="anthropic",
                computed_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
    await session.commit()
    await session.refresh(photo)
    if cache_dir is not None:
        path_on_disk = display_path(cache_dir, photo.id, photo.etag)
        path_on_disk.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (160, 160), color=(100, 100, 100)).save(path_on_disk, format="JPEG")
    return photo


class _NoDetections:
    """Faket die mediapipe-/Keras-Modelle so, dass nie etwas gefunden wird - kein echtes Modell in
    Tests (Teststrategie des Projekts)."""

    def detect(self, image: object) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(detections=[])

    def classify(self, image: object) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(classifications=[SimpleNamespace(categories=[])])


def _no_model() -> _NoDetections:
    return _NoDetections()


class _NeutralAesthetics:
    def predict(self, batch: object) -> object:
        import numpy as np

        return np.array([[0.1] * 10], dtype="float32")


def _no_aesthetics() -> _NeutralAesthetics:
    return _NeutralAesthetics()


class _NoLandmarker:
    def detect(self, image: object) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(face_landmarks=[], facial_transformation_matrixes=[])


def _no_landmarker() -> _NoLandmarker:
    return _NoLandmarker()


async def _run_criterion_scoring(
    session: AsyncSession, project: Project, cache_dir: Path
) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.commit()
    await session.refresh(scoring_run)
    return await run_criterion_scoring(
        session,
        project,
        scoring_run_id=scoring_run.id,
        cache_dir=cache_dir,
        build_detector=_no_model,
        build_animal_detector=_no_model,
        build_classifier=_no_model,
        build_aesthetics=_no_aesthetics,
        build_landmarker=_no_landmarker,
    )


async def _build_full_fixture(
    session: AsyncSession, cache_dir: Path, *, offset_minutes: int = 0
) -> tuple[Project, ProjectCamera, CriterionScoringRun]:
    """Die Fixture der staerksten Zusage: MINDESTENS ZWEI Abschnitte (getrennt durch eine
    Zeitluecke), ZWEI Kategorien, eine Hauptzeile mit gesetztem Override, ein Foto mit Koordinate
    und ein am Ausschuss-Gate aussortiertes Foto.

    Ueber einer Fixture mit einem Abschnitt und einer Kategorie waere die Gleichheit unten fast
    trivial und der Fall leer."""
    project = await _make_project(session)
    camera = ProjectCamera(
        project_id=project.id, make="Canon", model="EOS 5D", offset_minutes=offset_minutes
    )
    session.add(camera)
    await session.commit()
    await session.refresh(camera)

    # Abschnitt 1: zwei Fotos der Kamera, eines davon mit Koordinate und mit Override.
    await _add_photo(
        session,
        project,
        "a1.jpg",
        _BASE,
        camera=camera,
        gps=_EIFFEL,
        category_override="landschaft",
        cache_dir=cache_dir,
    )
    await _add_photo(
        session,
        project,
        "a2.jpg",
        _BASE + timedelta(minutes=5),
        camera=camera,
        remote_category="menschen",
        cache_dir=cache_dir,
    )
    # Abschnitt 2: hinter einer Zeitluecke, ein Foto OHNE Kamera (damit ein Versatz die Grenze
    # tatsaechlich verschieben kann).
    await _add_photo(
        session,
        project,
        "b1.jpg",
        _BASE + TIME_CLUSTER_GAP + timedelta(minutes=30),
        remote_category="menschen",
        cache_dir=cache_dir,
    )
    # Am Ausschuss-Gate aussortiert: gehoert NICHT in die Kandidatenmenge, traegt aber eine
    # gueltige Koordinate fuer die Ortsherleitung.
    await _add_photo(
        session,
        project,
        "weg.jpg",
        _BASE + timedelta(minutes=2),
        camera=camera,
        gps=_EIFFEL,
        suggested_status=RatingStatus.REJECTED,
        cache_dir=cache_dir,
    )

    run = await _run_criterion_scoring(session, project, cache_dir)
    assert run.status == ScanStatus.SUCCESS
    return project, camera, run


async def _snapshot(
    session: AsyncSession, run_id: int
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    """Events und Rangzeilen als Tupel OHNE Ids - Events nach `position`, Rangzeilen nach
    `(Event-position, category_key, rank_position)`. Die Ids MUESSEN heraus: ein Neuaufbau
    vergibt neue.

    `run_id` als `int`, nicht als ORM-Objekt: nach einem `rollback` sind ORM-Objekte expired, und
    ein Attributzugriff liefe in einen Lazy-Load ausserhalb des greenlet-Kontexts."""
    events = (
        (
            await session.execute(
                select(Event)
                .where(Event.criterion_scoring_run_id == run_id)
                .order_by(Event.position)
            )
        )
        .scalars()
        .all()
    )
    position_by_event_id = {event.id: event.position for event in events}
    event_tuples = [
        (
            event.position,
            event.started_at,
            event.ended_at,
            event.landmark_name,
            event.place_kind,
            event.place_lat,
            event.place_lon,
        )
        for event in events
    ]

    rankings = (
        (
            await session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run_id)
            )
        )
        .scalars()
        .all()
    )
    ranking_tuples = sorted(
        (
            position_by_event_id[ranking.event_id],
            ranking.category_key,
            ranking.rank_position,
            ranking.photo_id,
            ranking.rank_score,
            ranking.is_primary,
        )
        for ranking in rankings
    )
    return event_tuples, ranking_tuples


async def _id_sets(session: AsyncSession, run_id: int) -> tuple[set[int], set[int]]:
    event_ids = set(
        (await session.execute(select(Event.id).where(Event.criterion_scoring_run_id == run_id)))
        .scalars()
        .all()
    )
    ranking_ids = set(
        (
            await session.execute(
                select(PhotoRanking.id).where(PhotoRanking.criterion_scoring_run_id == run_id)
            )
        )
        .scalars()
        .all()
    )
    return event_ids, ranking_ids


async def _mark_every_event(session: AsyncSession, run_id: int, marker: str) -> None:
    """Schreibt einen Marker in ein Feld, das der Neuaufbau NEU ABLEITET.

    Er ersetzt die von der Spec vorgesehene Pruefung auf disjunkte Id-Mengen, die in der
    Testdatenbank nicht zu haben ist: SQLite vergibt nach einem `DELETE` dieselben `rowid`s
    erneut (kein `AUTOINCREMENT`), zwei aufeinanderfolgende Aufbauten bekommen dort also
    dieselben Ids - unter PostgreSQL mit seinen Sequenzen nicht. Der Marker traegt dieselbe
    Aussage DATENBANKUNABHAENGIG: ueberlebt er, wurden die Zeilen nicht ersetzt, und genau das
    wuerde ein `return` am Funktionsanfang tun."""
    events = (
        (await session.execute(select(Event).where(Event.criterion_scoring_run_id == run_id)))
        .scalars()
        .all()
    )
    assert events, "Ohne Event gibt es nichts zu markieren - die Fixture waere leer."
    for event in events:
        event.landmark_name = marker
    await session.flush()


async def test_a_project_without_a_successful_run_is_left_alone(
    db_session: AsyncSession,
) -> None:
    project = await _make_project(db_session)

    await rebuild_run_grouping(db_session, project.id)

    assert (
        await db_session.execute(select(func.count()).select_from(Event.__table__))
    ).scalar_one() == 0


async def test_a_run_without_a_single_ranking_row_is_left_alone(
    db_session: AsyncSession,
) -> None:
    """Ein erfolgreicher Lauf ueber einem leeren Kandidatenpool - es gibt nichts neu aufzubauen,
    und die Funktion darf daran nicht scheitern."""
    project = await _make_project(db_session)
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    db_session.add(scoring_run)
    await db_session.commit()
    db_session.add(
        CriterionScoringRun(
            project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
        )
    )
    await db_session.commit()

    await rebuild_run_grouping(db_session, project.id)

    assert (
        await db_session.execute(select(func.count()).select_from(Event.__table__))
    ).scalar_one() == 0


async def test_a_rebuild_with_offset_zero_produces_the_same_state_as_the_run_itself(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DIE staerkste Zusage der Story: derselbe Zustand, und die Zeilen sind dabei tatsaechlich
    ersetzt worden.

    Der zweite Teil ist nicht Beiwerk - ohne ihn bestuende ein `return` am Funktionsanfang die
    Zusage, ohne je etwas aufgebaut zu haben. Getragen wird er hier vom Marker statt von
    disjunkten Id-Mengen (Begruendung in `_mark_every_event`)."""
    project, _camera, run = await _build_full_fixture(db_session, tmp_path)
    run_id = run.id
    before = await _snapshot(db_session, run_id)
    assert len(before[0]) >= 2, "Die Fixture muss mindestens zwei Abschnitte haben."
    assert len({tuple_[1] for tuple_ in before[1]}) >= 2, (
        "Die Fixture muss mindestens zwei Kategorien haben."
    )
    await _mark_every_event(db_session, run_id, "NEUAUFBAU-MARKER")

    await rebuild_run_grouping(db_session, project.id)
    await db_session.commit()

    assert await _snapshot(db_session, run_id) == before
    surviving_markers = (
        await db_session.execute(
            select(func.count())
            .select_from(Event.__table__)
            .where(
                Event.criterion_scoring_run_id == run_id,
                Event.landmark_name == "NEUAUFBAU-MARKER",
            )
        )
    ).scalar_one()
    assert surviving_markers == 0


async def test_an_offset_that_pushes_a_photo_across_a_time_gap_changes_the_grouping(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Der Wirkungsnachweis: derselbe Datensatz, ein gesetzter Versatz - und die Abschnittszahl
    bzw. die Zugehoerigkeit fallen anders aus als mit der aufgezeichneten Zeit."""
    project, camera, run = await _build_full_fixture(db_session, tmp_path)
    run_id = run.id
    events_before, _rankings_before = await _snapshot(db_session, run_id)

    # Die Kamerafotos um die Zeitluecke nach vorne schieben, sodass sie mit dem kameralosen Foto
    # des zweiten Abschnitts zusammenfallen. Geschrieben wird wie am Endpunkt: `taken_at` aus
    # `taken_at_original` plus Versatz.
    camera.offset_minutes = int(TIME_CLUSTER_GAP.total_seconds() // 60) + 30
    photos = (
        (await db_session.execute(select(Photo).where(Photo.camera_id == camera.id)))
        .scalars()
        .all()
    )
    for photo in photos:
        corrected = shifted(photo.taken_at_original, camera.offset_minutes)
        assert corrected is not None
        photo.taken_at = corrected
    await db_session.flush()

    await rebuild_run_grouping(db_session, project.id)
    await db_session.commit()

    events_after, _rankings_after = await _snapshot(db_session, run_id)
    assert events_after != events_before
    assert len(events_after) < len(events_before)


async def test_a_category_override_survives_the_rebuild(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Kategorie-Zugehoerigkeiten werden NEU ABGELEITET, nicht aus den alten Zeilen
    uebernommen - genau deshalb muss der Override, der in `photo_scores` steht, danach wieder die
    Hauptzeile bestimmen."""
    project, _camera, run = await _build_full_fixture(db_session, tmp_path)
    overridden = (
        await db_session.execute(select(Photo).where(Photo.relative_path == "a1.jpg"))
    ).scalar_one()

    await rebuild_run_grouping(db_session, project.id)
    await db_session.commit()

    primary = (
        await db_session.execute(
            select(PhotoRanking).where(
                PhotoRanking.criterion_scoring_run_id == run.id,
                PhotoRanking.photo_id == overridden.id,
                PhotoRanking.is_primary.is_(True),
            )
        )
    ).scalar_one()
    assert primary.category_key == "landschaft"


async def test_the_rebuild_does_not_commit(db_session: AsyncSession, tmp_path: Path) -> None:
    """Die Transaktionsgrenze gehoert dem AUFRUFER (Muster `project_deletion`): der
    Versatz-Endpunkt braucht genau EIN `commit` am Ende, sonst gaebe es einen Zwischenzustand mit
    verschobenen Zeiten und noch alter Gliederung."""
    project, _camera, _run = await _build_full_fixture(db_session, tmp_path)

    await rebuild_run_grouping(db_session, project.id)

    assert db_session.in_transaction()
    await db_session.rollback()


async def test_a_rollback_after_the_rebuild_restores_the_previous_grouping(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Kehrseite derselben Zusage, und der Grund fuer sie: ein Fehler NACH dem Neuaufbau darf
    keine Gliederung ohne Rangzeilen hinterlassen - diesen Zustand weist keine Ansicht als
    fehlerhaft aus."""
    project, _camera, run = await _build_full_fixture(db_session, tmp_path)
    run_id = run.id
    before = await _snapshot(db_session, run_id)
    event_ids_before, _ranking_ids_before = await _id_sets(db_session, run_id)

    await rebuild_run_grouping(db_session, project.id)
    await db_session.rollback()

    assert await _snapshot(db_session, run_id) == before
    event_ids_after, _ranking_ids_after = await _id_sets(db_session, run_id)
    assert event_ids_after == event_ids_before
