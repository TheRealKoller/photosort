"""specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 6: der Neuaufbau der
Gliederung des letzten erfolgreichen Kriterien-Laufs nach einer Versatz-Aenderung.

Die staerkste Zusage der Story steht hier: ein Neuaufbau mit Versatz `0` erzeugt DENSELBEN
Zustand wie der Lauf selbst. Sie ist der Nachweis, dass Neuaufbau und Lauf denselben Code gehen -
ohne sie gaebe es zwei Wege zur Gliederung und zur Hauptkategorie, und ein zwischenzeitlich
gesetzter Override koennte still verloren gehen (ADR 0090, Punkt 5).
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NoReturn

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import events as events_module
from photosort import worker
from photosort.cameras import shifted
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PhotoAlbumSuitability,
    PhotoRanking,
    PhotoScore,
    PlaceLookup,
    Project,
    ProjectCamera,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)
from photosort.thumbnails import display_path
from photosort.worker import rebuild_run_grouping, run_criterion_scoring
from tests.import_closure import module_file

_BASE = datetime(2026, 8, 12, 9, 0, 0)


def _section_gap() -> timedelta:
    """Der Abstand, der in der Fixture tatsaechlich ZWEI Abschnitte ergibt.

    Er muss `MERGE_MAX_GAP` ueberschreiten, nicht nur `EVENT_TIME_GAP`: Ein Abschnitt aus einem
    einzigen Foto wuerde sonst von Stufe 3 wieder zugeschlagen, und die Fixture haette still nur
    noch einen Abschnitt - waehrend jeder Fall darueber gruen bliebe. Als MODULATTRIBUT gelesen,
    nie als Zahl."""
    return events_module.MERGE_MAX_GAP + timedelta(minutes=30)


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
    cache_dir: Path | None = None,
    album_suitability_level: int | None = None,
) -> Photo:
    """Ein Foto samt `PhotoScore` - und, falls `cache_dir` gegeben, seiner display-Variante, damit
    der Kriterien-Lauf die Inhalts-Kriterien ueberhaupt berechnen kann.

    `album_suitability_level` legt die Modellbewertung gleich mit an: ohne sie traegt das Foto
    seit Spec 0428 keinen Qualitaetswert, und die Rangzeile steht mit `NULL` da."""
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
            computed_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    if album_suitability_level is not None:
        session.add(
            PhotoAlbumSuitability(
                photo_id=photo.id,
                level=album_suitability_level,
                reason="Modellbegruendung",
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

    # Abschnitt 1: zwei Fotos der Kamera, eines davon mit Koordinate.
    await _add_photo(
        session,
        project,
        "a1.jpg",
        _BASE,
        camera=camera,
        gps=_EIFFEL,
        cache_dir=cache_dir,
        album_suitability_level=5,
    )
    await _add_photo(
        session,
        project,
        "a2.jpg",
        _BASE + timedelta(minutes=5),
        camera=camera,
        cache_dir=cache_dir,
        album_suitability_level=2,
    )
    # Abschnitt 2: hinter einer Zeitluecke, ein Foto OHNE Kamera (damit ein Versatz die Grenze
    # tatsaechlich verschieben kann).
    await _add_photo(
        session,
        project,
        "b1.jpg",
        _BASE + _section_gap(),
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
    `(Event-position, rank_position)`. Die Ids MUESSEN heraus: ein Neuaufbau vergibt neue.

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
    # Sortierschluessel mit -1 statt `None`: beide Rangspalten sind seit Spec 0428 nullable, und
    # ein Tupelvergleich `(1, None, ...)` gegen `(1, 2, ...)` wuerfe einen TypeError. Der
    # SCHLUESSEL ist das Ersatzwerkzeug, die TUPEL selbst tragen weiterhin `None` - sonst waere
    # der Unterschied zwischen "kein Wert" und "Wert 0" im Schnappschuss verloren.
    ranking_tuples = sorted(
        (
            (
                position_by_event_id[ranking.event_id],
                ranking.rank_position,
                ranking.photo_id,
                ranking.rank_score,
            )
            for ranking in rankings
        ),
        key=lambda entry: (
            entry[0],
            -1 if entry[1] is None else entry[1],
            entry[2],
            -1.0 if entry[3] is None else entry[3],
        ),
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
        "Die Fixture muss mindestens zwei verschiedene Rangpositionen haben."
    )
    assert any(tuple_[3] is not None for tuple_ in before[1]), (
        "Die Fixture muss mindestens einen Qualitaetswert haben - mit lauter `NULL` waere die "
        "Gleichheit unten auch dann erfuellt, wenn der Neuaufbau gar nichts mehr rechnete."
    )
    assert any(tuple_[3] is None for tuple_ in before[1]), (
        "Die Fixture muss ein Foto OHNE Modellbewertung haben - sonst bliebe unbemerkt, wenn der "
        "Neuaufbau ihm einen erfundenen Wert gaebe."
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
    camera.offset_minutes = int(_section_gap().total_seconds() // 60)
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


async def test_every_candidate_photo_has_exactly_one_ranking_row_after_the_rebuild(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Rangzeilen werden NEU AUFGEBAUT, nicht aus den alten uebernommen - und danach gilt
    wieder "ein Foto je Lauf in genau einer Zeile". Ein Neuaufbau, der die alten Zeilen stehen
    liesse, fiele in den Unique-Constraint; einer, der sie doppelt anlegte, ebenso. GEZAEHLT
    statt nur der Constraint geprueft: die Aussage ist "GENAU eine", nicht "hoechstens eine"."""
    project, _camera, run = await _build_full_fixture(db_session, tmp_path)

    await rebuild_run_grouping(db_session, project.id)
    await db_session.commit()

    photo_ids = list(
        (
            await db_session.execute(
                select(PhotoRanking.photo_id).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        ).scalars()
    )

    assert len(photo_ids) == len(set(photo_ids))
    assert len(photo_ids) == 3


async def test_the_rebuild_does_not_commit(db_session: AsyncSession, tmp_path: Path) -> None:
    """Die Transaktionsgrenze gehoert dem AUFRUFER (Muster `project_deletion`): der
    Versatz-Endpunkt braucht genau EIN `commit` am Ende, sonst gaebe es einen Zwischenzustand mit
    verschobenen Zeiten und noch alter Gliederung."""
    project, _camera, _run = await _build_full_fixture(db_session, tmp_path)

    await rebuild_run_grouping(db_session, project.id)

    assert db_session.in_transaction()
    await db_session.rollback()


async def test_the_rebuild_names_from_stored_lookups_and_asks_nobody(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """specs/features/0434-ortsnamen-fuer-events.md, S10: Der Neuaufbau bildet die Namen NEU,
    aber ausschliesslich aus bereits abgelegten Auskuenften - er fragt niemanden und legt keine
    neue Auskunft an.

    BEIDE HAELFTEN in einem Fall: die Zelle MIT abgelegter Auskunft traegt danach ihren Namen, die
    Zelle OHNE bleibt namenlos. Die erste Haelfte allein bestuende auch dann, wenn dieser Pfad das
    Merkmal gar nicht mehr kennte; die zweite allein auch dann, wenn er nie einen Namen
    schriebe."""
    project, _camera, run = await _build_full_fixture(db_session, tmp_path)
    # Das Foto mit Koordinate der Fixture liegt am Eiffelturm; die Zelle des zweiten Abschnitts
    # bekommt bewusst KEINE Auskunft.
    db_session.add(
        PlaceLookup(
            project_id=project.id,
            cell_lat=round(_EIFFEL[0], 2),
            cell_lon=round(_EIFFEL[1], 2),
            locality="Paris",
            matched_level="locality",
            source="geonames",
            resolved_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    await db_session.flush()
    lookups_before = (
        await db_session.execute(
            select(func.count())
            .select_from(PlaceLookup)
            .where(PlaceLookup.project_id == project.id)
        )
    ).scalar_one()

    await rebuild_run_grouping(db_session, project.id)

    events = (
        (
            await db_session.execute(
                select(Event)
                .where(Event.criterion_scoring_run_id == run.id)
                .order_by(Event.position)
            )
        )
        .scalars()
        .all()
    )
    named = [event.place_name for event in events]
    assert "Paris" in named
    assert None in named
    assert (
        await db_session.execute(
            select(func.count())
            .select_from(PlaceLookup)
            .where(PlaceLookup.project_id == project.id)
        )
    ).scalar_one() == lookups_before


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


class TestTheRebuildLoadsNoEmbeddingModel:
    """specs/features/0469, SICHERHEIT S10 (ADR 0107 Punkt 5): Der Neuaufbau laeuft IN EINEM
    REQUEST (Versatz-Endpunkt). Ein 113-MB-Modell im Anfragepfad waere ein Speicher- und
    Laufzeitvielfaches, das eine authentifizierte Anfrage - auch eine mit gestohlenem JWT -
    wiederholt ausloesen koennte."""

    async def test_the_rebuild_never_calls_the_embedder_builder(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Der Verhaltensnachweis: der Bau des Modells bringt den Test zum Scheitern, statt nur
        einen Zaehler stehen zu lassen."""
        project, _camera, _run = await _build_full_fixture(db_session, tmp_path)

        def _explode() -> NoReturn:
            pytest.fail("rebuild_run_grouping darf kein Einbettungsmodell bauen (S10)")

        monkeypatch.setattr(worker, "build_label_embedder", _explode)

        await rebuild_run_grouping(db_session, project.id)

    def test_the_rebuild_mentions_no_embedder_at_all(self) -> None:
        """Dazu ein struktureller Waechter: Der Verhaltensnachweis oben haengt daran, dass der
        Bau ueber genau diesen Modulnamen laeuft. Ein direkt importierter zweiter Bauweg roetete
        ihn nicht."""
        path = module_file("photosort.worker")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rebuild = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "rebuild_run_grouping"
        )

        mentioned = {node.id for node in ast.walk(rebuild) if isinstance(node, ast.Name)}

        assert "build_label_embedder" not in mentioned
        assert "build_embedder" not in mentioned
        # Gegenprobe: ohne sie bestuende der Fall auch dann, wenn der Walker nichts findet.
        assert "_build_grouping_and_rankings" in mentioned
