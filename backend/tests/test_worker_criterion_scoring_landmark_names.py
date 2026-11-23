"""Kriterien-Lauf: Sehenswuerdigkeits-Namen in Ereignissen, Mengen-Schaetzung, grober Ortshinweis,
das Register.
"""

from __future__ import annotations

import ast
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NoReturn

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import events as events_module
from photosort.candidate_counts import count_landmark_candidates
from photosort.geonames import build_landmark_gazetteer
from photosort.landmark import (
    LANDMARK_CONFIDENCE_THRESHOLD,
    MAX_LANDMARK_NAME_LENGTH,
    LandmarkDetection,
    PlaceHint,
)
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    DuplicateDecision,
    Event,
    LandmarkName,
    Photo,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoRanking,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
)
from photosort.places import PlaceAnswer, PlaceResolver, landmark_place_cell, place_cell
from photosort.worker import run_criterion_scoring
from tests.import_closure import module_file
from tests.support import make_project as _make_project
from tests.support import write_display_variant
from tests.support.criterion_scoring import (
    PerPhotoLandmarkClient,
    RecordingLandmarkClient,
    _add_album_suitability,
    _add_photo,
    _add_score,
    _add_successful_scoring_run,
    _failing_landmark_client_builder,
    _flat_image,
    _landscape_scene_classifier,
    _no_aesthetics_model,
    _no_animal_detector,
    _no_face_detector,
    _no_face_landmarker,
    _no_scene_classifier,
)


# ADR 0087 Punkt 3: die Sehenswuerdigkeit ist ein TRENNSIGNAL, kein Gruppierungsmerkmal. Die
# Namen kommen aus `photo_landmark_detections`, NICHT aus einer laufinternen Abbildung der
# Cloud-Antworten - das Signal wirkt damit auch in einem Lauf ohne Cloud-Phase.
async def _add_landmark_detection(
    session: AsyncSession, photo: Photo, name: str, *, confidence: float = 0.9
) -> PhotoLandmarkDetection:
    """Eine Zeile, wie sie ein FRUEHERER Lauf hinterlassen hat - bewusst ohne jeden Cloud-Aufruf
    in diesem Test."""
    row = PhotoLandmarkDetection(
        photo_id=photo.id,
        name=name,
        confidence=confidence,
        provider="anthropic",
        computed_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    return row


# Ein Aufnahmeort fuer die Faelle, die einen Sehenswuerdigkeitsnamen am Event erwarten: Die
# Ortspruefung ist fail-closed, ein Name braucht eine gemessene Zelle und eine bestaetigende
# Auskunft (`_gazetteer_confirming_at`).
PARIS = (48.8584, 2.2945)


_AT_PARIS = {"gps_lat": PARIS[0], "gps_lon": PARIS[1]}


def _gazetteer_confirming_at(spot: tuple[float, float]) -> Callable[[object], object]:
    """Eine Namensverzeichnis-Fabrik, die JEDEN gefragten Namen am Ort `spot` bestaetigt - kein
    automatisierter Test liest den echten zweiten Auszug."""

    class _Gazetteer:
        def points(self, name: str) -> tuple[tuple[float, float], ...]:
            return (spot,)

    return lambda names: _Gazetteer()


async def _run_without_cloud(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    cache_dir: Path,
    *,
    confirm_landmarks_at: tuple[float, float] | None = None,
) -> CriterionScoringRun:
    """Ein Lauf ohne Cloud-Phase. Mit `confirm_landmarks_at` bestaetigt die Auskunft jeden Namen
    an diesem Ort; ohne bleibt die Vorgabefabrik, und ohne Auszug faellt jeder Name."""
    gazetteer_factory = (
        build_landmark_gazetteer
        if confirm_landmarks_at is None
        else _gazetteer_confirming_at(confirm_landmarks_at)
    )
    return await run_criterion_scoring(
        session,
        project,
        scoring_run_id,
        cache_dir=cache_dir,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_gazetteer=gazetteer_factory,  # type: ignore[arg-type]
    )


async def _event_ids_by_photo(session: AsyncSession, run_id: int) -> dict[int, set[int]]:
    rows = (
        await session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run_id)
        )
    ).scalars()
    event_ids: dict[int, set[int]] = {}
    for row in rows:
        event_ids.setdefault(row.photo_id, set()).add(row.event_id)
    return event_ids


async def _events_of_run(session: AsyncSession, run_id: int) -> list[Event]:
    return list(
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


def _in_its_own_event(after: datetime) -> datetime:
    """Ein Zeitpunkt, der ein EIGENES Event eroeffnet und darin bleibt.

    Jenseits von `MERGE_MAX_GAP`, nicht nur jenseits von `EVENT_TIME_GAP`: Stufe 3 schluege ein
    Ein-Bild-Segment sonst wieder dem Nachbarn zu, und der Fall zaehlte still ein Event statt
    zweier. Beide Abstaende kommen aus den Modulkonstanten, nie aus einer Zahl.

    Seit ADR 0118 trennt der Sehenswuerdigkeitsname nicht mehr; jeder Fall, der zwei Events
    braucht, holt sie sich hierueber."""
    return after + events_module.MERGE_MAX_GAP + timedelta(minutes=1)


async def test_the_landmark_names_of_a_run_without_any_cloud_phase_reach_their_events(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DER ROT-ANKER dieser Sektion: Einwilligung aus, keine Cloud-Phase, die Namen liegen NUR aus
    einem frueheren Lauf in `photo_landmark_detections`. Sie muessen trotzdem an ihren Events
    ankommen. Eine Umsetzung, die die Namen aus einer laufinternen Abbildung der Cloud-Antworten
    liest, ist hier rot und sonst nirgends.

    Die TRENNUNG kommt seit ADR 0118 aus der Zeitluecke, nicht mehr aus dem Namenswechsel; der
    Name wird hier nur noch getragen, nicht mehr gelesen, um eine Grenze zu setzen."""
    project = await _make_project(db_session)
    assert project.cloud_vision_detection_enabled is False
    scoring_run = await _add_successful_scoring_run(db_session, project)
    start = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    eiffel = await _add_photo(db_session, project, "a.jpg", "etag-a", start, **_AT_PARIS)
    trocadero = await _add_photo(
        db_session, project, "b.jpg", "etag-b", _in_its_own_event(start), **_AT_PARIS
    )
    for photo in (eiffel, trocadero):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, eiffel, "Eiffelturm")
    await _add_landmark_detection(db_session, trocadero, "Trocadero")

    run = await _run_without_cloud(
        db_session, project, scoring_run.id, tmp_path, confirm_landmarks_at=PARIS
    )

    assert run.status == ScanStatus.SUCCESS
    event_ids = await _event_ids_by_photo(db_session, run.id)
    assert event_ids[eiffel.id] != event_ids[trocadero.id]
    events = await _events_of_run(db_session, run.id)
    assert [(e.position, e.landmark_name) for e in events] == [
        (1, "Eiffelturm"),
        (2, "Trocadero"),
    ]


async def test_the_event_building_never_mutates_photo_score_cluster_key(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DIVERGENZ-REGRESSIONSTEST (Ownership-Grenze): `PhotoRanking.event_id` weicht von der
    Phase-A-Gliederung ab UND `PhotoScore.cluster_key` wird in derselben Pruefung explizit als
    unveraendert nachgewiesen. Die Divergenz beider Felder ist gewollt."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    start = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    eiffel = await _add_photo(db_session, project, "a.jpg", "etag-a", start)
    trocadero = await _add_photo(db_session, project, "b.jpg", "etag-b", _in_its_own_event(start))
    for photo in (eiffel, trocadero):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, eiffel, "Eiffelturm")
    await _add_landmark_detection(db_session, trocadero, "Trocadero")

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    event_ids = await _event_ids_by_photo(db_session, run.id)
    assert event_ids[eiffel.id] != event_ids[trocadero.id]
    scores = {s.photo_id: s for s in (await db_session.execute(select(PhotoScore))).scalars()}
    assert scores[eiffel.id].cluster_key == "cluster-0"
    assert scores[trocadero.id].cluster_key == "cluster-0"


async def test_without_any_landmark_row_all_photos_share_one_event(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """BACKWARD COMPATIBILITY: ohne Namen, ohne Koordinaten und ohne Zeitluecke bleibt es bei
    einem einzigen Event."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    await _add_score(db_session, photo, cluster_key="cluster-0")
    write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    events = await _events_of_run(db_session, run.id)
    assert [e.position for e in events] == [1]
    assert events[0].landmark_name is None
    assert events[0].place_kind is None


async def test_a_landmark_row_for_a_photo_without_a_candidate_row_has_no_effect(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Eine Zeile zu einem Foto, das am Ausschuss-Gate haengengeblieben ist, trennt nichts - es
    liegt gar nicht in der Kandidatenmenge."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    survivor = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    rejected = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
    )
    await _add_score(db_session, survivor, cluster_key="cluster-0")
    await _add_score(
        db_session, rejected, cluster_key="cluster-0", suggested_status=RatingStatus.REJECTED
    )
    for photo in (survivor, rejected):
        write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, survivor, "Eiffelturm")
    await _add_landmark_detection(db_session, rejected, "Trocadero")

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    event_ids = await _event_ids_by_photo(db_session, run.id)
    assert len(await _events_of_run(db_session, run.id)) == 1
    assert rejected.id not in event_ids


async def test_landmark_rows_of_mixed_origin_both_take_effect_in_one_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Foto A hat seine Zeile aus einem FRUEHEREN Lauf, Foto B bekommt sie in DIESEM. Beide Namen
    wirken - das belegt zugleich die Reihenfolge: gelesen wird NACH der Cloud-Phase, sonst fehlte
    B."""
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    start = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    older = await _add_photo(db_session, project, "a.jpg", "etag-a", start, **_AT_PARIS)
    fresh = await _add_photo(
        db_session, project, "b.jpg", "etag-b", _in_its_own_event(start), **_AT_PARIS
    )
    for photo in (older, fresh):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())
    # A: Ergebnis aus einem FRUEHEREN Lauf - Detection-Zeile plus die zugehoerige
    # `landmark`-Kriterienzeile, denn genau an ihr haengt das Skip-Verhalten aus ADR 0025 Punkt 3.
    await _add_landmark_detection(db_session, older, "Alexanderplatz")
    db_session.add(
        PhotoCriterionScore(
            photo_id=older.id,
            criterion_key="landmark",
            value=0.9,
            source=CriterionSource.CLOUD,
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    client = RecordingLandmarkClient(detection=LandmarkDetection(name="Zugspitze", confidence=0.8))
    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        build_landmark_gazetteer=_gazetteer_confirming_at(PARIS),  # type: ignore[arg-type]
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    # Nur B geht in die Cloud - A wird wegen seiner Bestandszeile uebersprungen (ADR 0025 Punkt 3).
    assert len(client.calls) == 1
    events = await _events_of_run(db_session, run.id)
    assert [(e.position, e.landmark_name) for e in events] == [
        (1, "Alexanderplatz"),
        (2, "Zugspitze"),
    ]


async def test_the_partition_ranking_uses_the_event(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Nachweis, dass die PARTITIONSBILDUNG das Event nutzt: ohne die Trennung laegen beide Fotos
    in derselben Partition und truegen die Positionen 1 und 2; mit ihr ist jedes Foto
    Erstplatziertes seiner eigenen Partition."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    start = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    eiffel = await _add_photo(db_session, project, "a.jpg", "etag-a", start)
    trocadero = await _add_photo(db_session, project, "b.jpg", "etag-b", _in_its_own_event(start))
    for photo in (eiffel, trocadero):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())
        await _add_album_suitability(db_session, photo)

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    positions = {
        row.photo_id: row.rank_position
        for row in (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        ).scalars()
    }
    assert positions == {eiffel.id: 1, trocadero.id: 1}


async def test_partitions_are_formed_over_the_event_alone(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Der Partitionsschluessel IST die `event_id` - zwei Fotos DESSELBEN Events bilden eine
    Partition und tragen die Positionen 1 und 2.

    Die Gegenprobe steht im Fall darueber (zwei Events, beide Fotos auf Position 1): getrennt
    bestuende jeder von beiden auch dann, wenn die Partition eine ganz andere Groesse haette."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photos = [
        await _add_photo(
            db_session,
            project,
            f"{index}.jpg",
            f"etag-{index}",
            datetime(2023, 1, 1, 10, index, tzinfo=UTC),
        )
        for index in range(2)
    ]
    for photo in photos:
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())
        await _add_album_suitability(db_session, photo)

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    rows = list(
        (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        ).scalars()
    )
    assert len({row.event_id for row in rows}) == 1
    assert sorted(row.rank_position for row in rows) == [1, 2]


async def test_the_run_persists_its_events_with_position_and_time_span(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    start = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    first = await _add_photo(db_session, project, "a.jpg", "etag-a", start)
    # Im selben Event wie `first` - der Abstand kommt aus `EVENT_TIME_GAP`, nicht aus einer Zahl.
    second = await _add_photo(
        db_session, project, "b.jpg", "etag-b", start + events_module.EVENT_TIME_GAP / 2
    )
    # Eigenes Event ueber die Zeitluecke - und weit genug, dass Stufe 3 es nicht wieder
    # zuschlaegt: der Abstand kommt aus `MERGE_MAX_GAP`, nicht aus einer Zahl.
    third = await _add_photo(
        db_session,
        project,
        "c.jpg",
        "etag-c",
        second.taken_at.replace(tzinfo=UTC) + events_module.MERGE_MAX_GAP + timedelta(minutes=1),
    )
    for photo in (first, second, third):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    events = await _events_of_run(db_session, run.id)
    assert [e.position for e in events] == [1, 2]
    assert (events[0].started_at, events[0].ended_at) == (first.taken_at, second.taken_at)
    assert (events[1].started_at, events[1].ended_at) == (third.taken_at, third.taken_at)
    assert events[0].ended_at <= events[1].started_at


async def test_the_event_place_comes_from_measured_coordinates(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session,
        project,
        "a.jpg",
        "etag-a",
        datetime(2023, 1, 1, 10, 0, tzinfo=UTC),
        gps_lat=48.858370,
        gps_lon=2.294481,
    )
    await _add_score(db_session, photo, cluster_key="cluster-0")
    write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    [event] = await _events_of_run(db_session, run.id)
    assert event.place_kind == "coordinate"
    # GERUNDET geschrieben, nie in voller Praezision.
    assert (event.place_lat, event.place_lon) == (48.86, 2.29)


async def test_an_event_without_any_measured_coordinate_has_no_place(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die uebernommenen Orte bestimmen die Grenzen mit, speisen den Ortsbezug aber nie."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    anchor = await _add_photo(
        db_session,
        project,
        "anchor.jpg",
        "etag-anchor",
        datetime(2023, 1, 1, 10, 0, tzinfo=UTC),
        gps_lat=48.85,
        gps_lon=2.29,
    )
    await _add_score(
        db_session, anchor, cluster_key="cluster-0", suggested_status=RatingStatus.REJECTED
    )
    candidate = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 1, tzinfo=UTC)
    )
    await _add_score(db_session, candidate, cluster_key="cluster-0")
    for photo in (anchor, candidate):
        write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    [event] = await _events_of_run(db_session, run.id)
    assert event.place_kind is None
    assert (event.place_lat, event.place_lon) == (None, None)


async def test_a_rejected_photo_anchors_the_inherited_location(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Inferenzbasis ist das GANZE Projekt, nicht die Kandidatenmenge: zwei weit
    auseinanderliegende, AUSSORTIERTE Anker trennen die beiden koordinatenlosen Kandidaten. Ohne
    die projektweite Bezugsmenge waeren beide ortslos und laegen in einem Event."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    for index, (lat, minute) in enumerate(((48.0, 0), (49.0, 2))):
        anchor = await _add_photo(
            db_session,
            project,
            f"anchor-{index}.jpg",
            f"etag-anchor-{index}",
            datetime(2023, 1, 1, 10, minute, tzinfo=UTC),
            gps_lat=lat,
            gps_lon=2.0,
        )
        await _add_score(
            db_session, anchor, cluster_key="cluster-0", suggested_status=RatingStatus.REJECTED
        )
        write_display_variant(tmp_path, anchor, _flat_image())
    candidates = [
        await _add_photo(
            db_session,
            project,
            f"{index}.jpg",
            f"etag-{index}",
            datetime(2023, 1, 1, 10, minute, tzinfo=UTC),
        )
        for index, minute in enumerate((0, 2))
    ]
    for photo in candidates:
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    assert len(await _events_of_run(db_session, run.id)) == 2


async def test_the_inference_base_is_bound_to_the_project(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """SICHERHEIT (M5): die Bindung an `Photo.project_id` steht im Worker ausgeschrieben. Ohne sie
    erbte ein Foto Koordinaten aus einem FREMDEN Projekt und die Event-Grenzen in Projekt A
    haengten an Fotos aus Projekt B."""
    foreign = await _make_project(db_session, name="Fremd")
    for index, lat in enumerate((48.0, 49.0)):
        await _add_photo(
            db_session,
            foreign,
            f"f-{index}.jpg",
            f"etag-f-{index}",
            datetime(2023, 1, 1, 10, index * 2, tzinfo=UTC),
            gps_lat=lat,
            gps_lon=2.0,
        )

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    for index, minute in enumerate((0, 2)):
        photo = await _add_photo(
            db_session,
            project,
            f"{index}.jpg",
            f"etag-{index}",
            datetime(2023, 1, 1, 10, minute, tzinfo=UTC),
        )
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    assert len(await _events_of_run(db_session, run.id)) == 1


async def test_an_unsanitised_legacy_name_does_not_split_against_its_sanitised_twin(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Altbestand aus Spec 0047: eine Zeile traegt unsanierten Rohtext (Zero-Width-Zeichen), eine
    zweite denselben Namen sauber. Ohne Sanitisierung im LESEPFAD waeren das zwei verschiedene
    Namen und das Event zerfiele in zwei Teile, die dieselbe Sehenswuerdigkeit meinen."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    legacy = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), **_AT_PARIS
    )
    clean = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC), **_AT_PARIS
    )
    for photo in (legacy, clean):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, legacy, "Eiffel​turm")
    await _add_landmark_detection(db_session, clean, "Eiffelturm")

    run = await _run_without_cloud(
        db_session, project, scoring_run.id, tmp_path, confirm_landmarks_at=PARIS
    )

    events = await _events_of_run(db_session, run.id)
    assert [(e.position, e.landmark_name) for e in events] == [(1, "Eiffelturm")]


async def test_an_overlong_legacy_name_is_discarded_and_causes_no_split(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Verworfen statt abgeschnitten: fuer dieses Foto gilt "kein Name", es loest keine Grenze aus
    und der Name landet nicht in `events.landmark_name`."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    overlong = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), **_AT_PARIS
    )
    normal = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC), **_AT_PARIS
    )
    for photo in (overlong, normal):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, overlong, "A" * (MAX_LANDMARK_NAME_LENGTH + 1))
    await _add_landmark_detection(db_session, normal, "Eiffelturm")

    run = await _run_without_cloud(
        db_session, project, scoring_run.id, tmp_path, confirm_landmarks_at=PARIS
    )

    events = await _events_of_run(db_session, run.id)
    assert [(e.position, e.landmark_name) for e in events] == [(1, "Eiffelturm")]


class TestTheLandmarkEstimateCountsWhatTheRunSends:
    """specs/features/0374-duplikate-vergleichen.md, Auflage S1 fuer den ZWEITEN Cloud-Teilschritt.

    MENGENGLEICHHEIT ueber demselben Datenbestand, nicht zwei getrennt hingeschriebene
    Erwartungswerte: Die Schaetzung ist eine eigene Anweisung in `api/projects.py` und folgt der
    Fotoauswahl des Laufs nicht von selbst. Nennt sie eine andere Zahl, als der Lauf sendet, beruht
    die Freigabe eines kostenpflichtigen Laufs auf einer Zahl, die nicht gilt - sichtbar erst an
    der Abrechnung des Anbieters."""

    async def _photo_with_variant(
        self,
        session: AsyncSession,
        project: Project,
        path: str,
        etag: str,
        second: int,
        cache_dir: Path,
        **score: object,
    ) -> Photo:
        photo = await _add_photo(
            session, project, path, etag, datetime(2023, 1, 1, 0, 0, second, tzinfo=UTC)
        )
        await _add_score(session, photo, **score)  # type: ignore[arg-type]
        write_display_variant(cache_dir, photo, _flat_image())
        return photo

    async def _run(
        self,
        session: AsyncSession,
        project: Project,
        scoring_run_id: int,
        cache_dir: Path,
        *,
        landmark_client: RecordingLandmarkClient | None = None,
    ) -> CriterionScoringRun:
        return await run_criterion_scoring(
            session,
            project,
            scoring_run_id,
            cache_dir=cache_dir,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=(
                (lambda _model: landmark_client) if landmark_client is not None else None
            ),
            use_cloud=landmark_client is not None,
        )

    async def test_the_estimate_equals_the_number_of_photos_the_run_actually_sends(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await db_session.commit()
        scoring_run = await _add_successful_scoring_run(db_session, project)
        winner = await self._photo_with_variant(
            db_session, project, "gewinner.jpg", "etag-1", 0, tmp_path
        )
        # Ausdruecklich behalten: ein Duplikat-Verlierer, den der Nutzer zurueckgeholt hat.
        await self._photo_with_variant(
            db_session,
            project,
            "behalten.jpg",
            "etag-2",
            1,
            tmp_path,
            cluster_key=None,
            suggested_status=RatingStatus.REJECTED,
            duplicate_of=winner.id,
            duplicate_decision=DuplicateDecision.KEEP,
        )
        # Ausdruecklich verworfen: eine Aufnahme, die ohne Entscheidung weitergelaufen waere.
        await self._photo_with_variant(
            db_session,
            project,
            "verworfen.jpg",
            "etag-3",
            2,
            tmp_path,
            duplicate_decision=DuplicateDecision.DISCARD,
        )

        # Erster Lauf OHNE Cloud: er legt die Kriterienwerte an, aus denen die Schaetzung ihre
        # Kandidaten ableitet. Sie ist strukturell eine Schaetzung, keine Vorausberechnung.
        await self._run(db_session, project, scoring_run.id, tmp_path)
        geschaetzt = await count_landmark_candidates(db_session, project.id)

        client = RecordingLandmarkClient()
        await self._run(db_session, project, scoring_run.id, tmp_path, landmark_client=client)

        assert geschaetzt == len(client.calls)
        # Gegenprobe zur Selbsterfuellung: Eine Umsetzung, die beide Seiten auf null zieht,
        # bestuende die Gleichheit oben, ohne irgendetwas zu zeigen.
        assert geschaetzt == 2


# specs/features/0469-verlaessliche-sehenswuerdigkeitsnamen.md, Teil 1 Schritt 3: die grobe
# Ortsangabe geht in die Erkennung ein. Ab hier die Verdrahtung im Worker.

# Zwei Zellen im Wettersteingebirge, rund 5 km auseinander: sie fallen in verschiedene
# `place_cell`-Zellen (die Koernung, mit der gefragt und abgelegt wird) und in DIESELBE
# `landmark_place_cell`-Zelle - die Vergroeberung ist damit an der Messlage sichtbar und nicht nur
# behauptet.
GARMISCH = (47.4917, 11.0953)


GRAINAU = (47.4764, 11.0289)


class _RecordingResolverFactory:
    """Die Auflöser-Fabrik, wie der Worker sie bekommt - zaehlend, ohne Netz und ohne Datensatz
    (Muster `test_worker_place_names.py::CountingResolver`)."""

    def __init__(
        self, answers: dict[tuple[float, float], PlaceAnswer | None] | None = None
    ) -> None:
        self.answers = answers or {}
        self.asked: list[tuple[float, float]] = []
        self.built_for: list[frozenset[tuple[float, float]]] = []

    def __call__(self, cells: object) -> PlaceResolver | None:
        self.built_for.append(frozenset(cells))  # type: ignore[arg-type]
        return self

    async def resolve(self, cell: tuple[float, float]) -> PlaceAnswer | None:
        self.asked.append(cell)
        return self.answers.get(cell)


def _no_resolver(cells: object) -> PlaceResolver | None:
    """Der Fall "Datensatz fehlt": Die Fabrik liefert keinen Auflöser. Das ist ein arbeitsfaehiger
    Zustand, kein Fehlerfall."""
    return None


def _locality_answer(locality: str) -> PlaceAnswer:
    return PlaceAnswer(
        neighbourhood=None,
        locality=locality,
        region="Bayern",
        country="Deutschland",
        matched_level="locality",
    )


async def run_landmark_phase(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    tmp_path: Path,
    client: object,
    build_place_resolver: object,
) -> CriterionScoringRun:
    return await run_criterion_scoring(
        session,
        project,
        scoring_run_id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,  # type: ignore[arg-type,return-value]
        build_place_resolver=build_place_resolver,  # type: ignore[arg-type]
        use_cloud=True,
    )


async def _cloud_project(session: AsyncSession, name: str = "Reise") -> Project:
    project = await _make_project(session, name=name)
    project.cloud_vision_detection_enabled = True
    await session.commit()
    return project


class TestTheLandmarkPhaseCarriesTheCoarsePlaceHint:
    """ADR 0106: Der Aufnahmeort geht als grobe Ortsangabe in die Erkennung ein - in den Prompt
    desselben Aufrufs, der das Foto traegt. Ein zweiter Empfaenger entsteht dabei nicht."""

    async def test_a_photo_with_a_resolved_locality_carries_its_name(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _cloud_project(db_session)
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session,
            project,
            "a.jpg",
            "etag-1",
            datetime(2023, 1, 1, tzinfo=UTC),
            gps_lat=GARMISCH[0],
            gps_lon=GARMISCH[1],
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())
        resolver = _RecordingResolverFactory(
            {place_cell(*GARMISCH): _locality_answer("Garmisch-Partenkirchen")}
        )
        client = RecordingLandmarkClient()

        run = await run_landmark_phase(
            db_session, project, scoring_run.id, tmp_path, client, resolver
        )

        assert run.status == ScanStatus.SUCCESS
        assert client.hints == [PlaceHint(locality="Garmisch-Partenkirchen")]

    async def test_a_photo_without_a_resolvable_locality_carries_the_coarse_coordinate(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Koordinatenstufe ist DAUERHAFT und kein Uebergangszustand - sie greift bevorzugt
        dort, wo sich kein Ortsname aufloesen liess."""
        project = await _cloud_project(db_session)
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session,
            project,
            "a.jpg",
            "etag-1",
            datetime(2023, 1, 1, tzinfo=UTC),
            gps_lat=GARMISCH[0],
            gps_lon=GARMISCH[1],
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())
        resolver = _RecordingResolverFactory(
            {
                place_cell(*GARMISCH): PlaceAnswer(
                    neighbourhood=None,
                    locality="Garmisch-Partenkirchen",
                    region="Bayern",
                    country="Deutschland",
                    # Ein Treffer auf Regionsebene gilt als "kein Name aufgeloest", auch wenn er
                    # eine Stadt nennt.
                    matched_level="region",
                )
            }
        )
        client = RecordingLandmarkClient()

        await run_landmark_phase(db_session, project, scoring_run.id, tmp_path, client, resolver)

        assert client.hints == [PlaceHint(cell=landmark_place_cell(*GARMISCH))]

    async def test_every_photo_gets_the_hint_of_its_own_cell(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Je Foto die EIGENE Zelle - nicht eine gemeinsame des Laufs."""
        project = await _cloud_project(db_session)
        scoring_run = await _add_successful_scoring_run(db_session, project)
        for index, (path, coords) in enumerate([("a.jpg", GARMISCH), ("b.jpg", GRAINAU)], start=1):
            photo = await _add_photo(
                db_session,
                project,
                path,
                f"etag-{index}",
                datetime(2023, 1, 1, 10, index, tzinfo=UTC),
                gps_lat=coords[0],
                gps_lon=coords[1],
            )
            await _add_score(db_session, photo)
            write_display_variant(tmp_path, photo, _flat_image())
        resolver = _RecordingResolverFactory(
            {
                place_cell(*GARMISCH): _locality_answer("Garmisch-Partenkirchen"),
                place_cell(*GRAINAU): _locality_answer("Grainau"),
            }
        )
        client = RecordingLandmarkClient()

        await run_landmark_phase(db_session, project, scoring_run.id, tmp_path, client, resolver)

        assert client.hints == [
            PlaceHint(locality="Garmisch-Partenkirchen"),
            PlaceHint(locality="Grainau"),
        ]

    async def test_a_photo_without_its_own_coordinate_carries_no_hint_at_all(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """SICHERHEIT (S3, ADR 0106 Punkt 4): Die Messlage ist so gebaut, dass
        `events.py::infer_locations` dem zweiten Foto sehr wohl eine Koordinate GAEBE - es liegt
        wenige Minuten nach dem ersten. Genau deshalb steht der Fall hier: Eine SCHAETZUNG truege
        Ortsdaten auch fuer Aufnahmen hinaus, die selbst nie eine hatten."""
        project = await _cloud_project(db_session)
        scoring_run = await _add_successful_scoring_run(db_session, project)
        with_gps = await _add_photo(
            db_session,
            project,
            "mit-ort.jpg",
            "etag-1",
            datetime(2023, 1, 1, 10, 0, tzinfo=UTC),
            gps_lat=GARMISCH[0],
            gps_lon=GARMISCH[1],
        )
        without_gps = await _add_photo(
            db_session, project, "ohne-ort.jpg", "etag-2", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
        )
        for photo in (with_gps, without_gps):
            await _add_score(db_session, photo)
            write_display_variant(tmp_path, photo, _flat_image())
        resolver = _RecordingResolverFactory(
            {place_cell(*GARMISCH): _locality_answer("Garmisch-Partenkirchen")}
        )
        client = RecordingLandmarkClient()

        await run_landmark_phase(db_session, project, scoring_run.id, tmp_path, client, resolver)

        assert client.hints == [PlaceHint(locality="Garmisch-Partenkirchen"), None]

    async def test_only_the_cells_of_photos_that_carry_one_are_ever_asked_for(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _cloud_project(db_session)
        scoring_run = await _add_successful_scoring_run(db_session, project)
        with_gps = await _add_photo(
            db_session,
            project,
            "mit-ort.jpg",
            "etag-1",
            datetime(2023, 1, 1, 10, 0, tzinfo=UTC),
            gps_lat=GARMISCH[0],
            gps_lon=GARMISCH[1],
        )
        without_gps = await _add_photo(
            db_session, project, "ohne-ort.jpg", "etag-2", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
        )
        for photo in (with_gps, without_gps):
            await _add_score(db_session, photo)
            write_display_variant(tmp_path, photo, _flat_image())
        resolver = _RecordingResolverFactory(
            {place_cell(*GARMISCH): _locality_answer("Garmisch-Partenkirchen")}
        )

        await run_landmark_phase(
            db_session, project, scoring_run.id, tmp_path, RecordingLandmarkClient(), resolver
        )

        assert resolver.asked == [place_cell(*GARMISCH)]

    async def test_the_landmark_phase_never_calls_infer_locations(self) -> None:
        """Ein SYNTAXBAUM-Waechter, und er hat einen Grund (S3): Ein hinzugefuegter
        `infer_locations`-Aufruf roetet keinen Verhaltenstest, solange die Messlage echte
        Koordinaten traegt - genau dann waere die Zusage aber gebrochen."""
        path = module_file("photosort.worker.criterion_scoring")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))
        phase = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_criterion_scoring"
        )

        called = {
            node.func.id
            for node in ast.walk(phase)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert "infer_locations" not in called
        # Gegenprobe: ohne sie bestuende der Fall auch dann, wenn der Walker nichts findet.
        assert "place_infos" in called

    async def test_without_a_resolver_the_coordinate_stage_takes_over_and_the_run_succeeds(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Fehlt der Ortsdatensatz, bleibt die Namensstufe leer und die Koordinatenstufe greift -
        kein Fehlerfall, keine Fehlerzeile, kein Laufabbruch."""
        project = await _cloud_project(db_session)
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session,
            project,
            "a.jpg",
            "etag-1",
            datetime(2023, 1, 1, tzinfo=UTC),
            gps_lat=GARMISCH[0],
            gps_lon=GARMISCH[1],
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())
        client = RecordingLandmarkClient()

        run = await run_landmark_phase(
            db_session, project, scoring_run.id, tmp_path, client, _no_resolver
        )

        assert run.status == ScanStatus.SUCCESS
        assert run.cloud_error_message is None
        assert client.hints == [PlaceHint(cell=landmark_place_cell(*GARMISCH))]
        assert (
            await db_session.execute(select(func.count()).select_from(PhotoCloudVisionError))
        ).scalar_one() == 0

    async def test_neither_the_locality_nor_the_coordinate_ever_reaches_a_log_or_an_error_row(
        self, db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """SICHERHEIT (S6): `str(exc)` eines fehlgeschlagenen Landmark-Aufrufs geht an ZWEI Senken
        - die WARNING-Zeile UND `photo_cloud_vision_errors.error_message`, das ueber
        `GET /projects/{id}/photos` an den Browser ausgeliefert wird. Weder Ortsname noch
        Koordinate gehoert in eine von beiden.

        Gesucht werden die einpraegsamen Zeichenfolgen DIESER Messlage, nie ein allgemeines
        Zahlenmuster."""
        project = await _cloud_project(db_session)
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session,
            project,
            "a.jpg",
            "etag-1",
            datetime(2023, 1, 1, tzinfo=UTC),
            gps_lat=GARMISCH[0],
            gps_lon=GARMISCH[1],
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())
        resolver = _RecordingResolverFactory(
            {place_cell(*GARMISCH): _locality_answer("Unverwechselbarshausen")}
        )
        client = RecordingLandmarkClient(raise_error=True)

        with caplog.at_level(logging.DEBUG):
            run = await run_landmark_phase(
                db_session, project, scoring_run.id, tmp_path, client, resolver
            )

        assert run.status == ScanStatus.SUCCESS
        error_row = (await db_session.execute(select(PhotoCloudVisionError))).scalar_one()
        # Die Logzeilen dieses Projekts, ueber `getMessage()` UND `args` - sonst rutschte ein
        # `%s`-Argument durch. Fremde Logger (der DB-Treiber der Testsuite) sind nicht der
        # Gegenstand der Auflage.
        own_log = "\n".join(
            record.getMessage() + repr(record.args)
            for record in caplog.records
            if record.name.split(".")[0] == "photosort"
        )
        haystack = "\n".join([own_log, error_row.error_message, run.cloud_error_message or ""])
        for forbidden in (
            "Unverwechselbarshausen",
            "47.4917",
            "11.0953",
            "47.5",
            "11.1",
            "Bayern",
            "Deutschland",
        ):
            assert forbidden not in haystack, forbidden
        # Gegenprobe: beide Senken tragen ueberhaupt etwas, der Fall oben ist nicht leer.
        assert "simulierter Cloud-Fehler" in own_log
        assert "simulierter Cloud-Fehler" in error_row.error_message


# specs/features/0469, Teil 2 Schritt 4: das Namensregister in der Landmark-Phase.
class ConstantEmbedder:
    """Ein Einbetter, der jeden Text auf denselben Vektor abbildet - damit entscheidet allein die
    Ortsnamen-Sperre, ob zwei Namen zusammenfallen (Aehnlichkeit 1.0, maximale Gegenkraft)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0]


class ExplodingEmbedderBuilder:
    """Ein Builder, dessen Aufruf den Test zum Scheitern bringt - so wird "es wurde gar nicht erst
    versucht" zu einer beweisbaren Aussage statt zu einer Zaehlerbeobachtung."""

    def __call__(self) -> NoReturn:
        pytest.fail("build_embedder darf an dieser Stelle nie aufgerufen werden")


def _no_embedder() -> NoReturn:
    """Der Fall "Modell nicht ladbar": `try_build` faengt die Ausnahme und liefert `None`."""
    raise RuntimeError("Einbettungsmodell nicht ladbar")


async def _run_with_embedder(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    tmp_path: Path,
    client: object,
    build_place_resolver: object,
    build_embedder: object,
    *,
    build_landmark_gazetteer: object = build_landmark_gazetteer,
) -> CriterionScoringRun:
    return await run_criterion_scoring(
        session,
        project,
        scoring_run_id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,  # type: ignore[arg-type,return-value]
        build_place_resolver=build_place_resolver,  # type: ignore[arg-type]
        build_landmark_gazetteer=build_landmark_gazetteer,  # type: ignore[arg-type]
        build_embedder=build_embedder,  # type: ignore[arg-type]
        use_cloud=True,
    )


async def _landmark_photo(
    session: AsyncSession,
    project: Project,
    tmp_path: Path,
    path: str,
    etag: str,
    taken_at: datetime,
    *,
    coords: tuple[float, float] | None = None,
) -> Photo:
    photo = await _add_photo(
        session,
        project,
        path,
        etag,
        taken_at,
        gps_lat=None if coords is None else coords[0],
        gps_lon=None if coords is None else coords[1],
    )
    await _add_score(session, photo)
    write_display_variant(tmp_path, photo, _flat_image())
    return photo


async def _register_rows(session: AsyncSession, project_id: int) -> list[LandmarkName]:
    return list(
        (
            await session.execute(
                select(LandmarkName)
                .where(LandmarkName.project_id == project_id)
                .order_by(LandmarkName.id)
            )
        )
        .scalars()
        .all()
    )


class TestTheRegisterMakesTheNamesUniform:
    async def test_a_first_hit_creates_a_register_row_and_its_canonical_name(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _cloud_project(db_session, "register-erst")
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _landmark_photo(
            db_session,
            project,
            tmp_path,
            "a.jpg",
            "etag-1",
            datetime(2023, 1, 1, tzinfo=UTC),
            coords=GARMISCH,
        )
        client = RecordingLandmarkClient(
            detection=LandmarkDetection(name="Zugspitze", confidence=0.9)
        )
        resolver = _RecordingResolverFactory({place_cell(*GARMISCH): _locality_answer("Grainau")})

        await _run_with_embedder(
            db_session, project, scoring_run.id, tmp_path, client, resolver, ConstantEmbedder
        )

        [entry] = await _register_rows(db_session, project.id)
        assert entry.normalized_name == "zugspitze"
        assert entry.display_name == "Zugspitze"
        assert entry.locality == "Grainau"
        detection_row = (
            await db_session.execute(
                select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
            )
        ).scalar_one()
        assert detection_row.canonical_name == "Zugspitze"

    async def test_two_spellings_end_up_in_one_event_instead_of_two(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Das eigentliche Ziel der Story: Zwei Erkennungszeilen mit verschiedenem `name`, aber
        gleichem `canonical_name`, ergeben EIN Event statt zweier."""
        project = await _cloud_project(db_session, "ein-event")
        scoring_run = await _add_successful_scoring_run(db_session, project)
        for index, path in enumerate(["a.jpg", "b.jpg"], start=1):
            await _landmark_photo(
                db_session,
                project,
                tmp_path,
                path,
                f"etag-{index}",
                datetime(2023, 1, 1, 10, index, tzinfo=UTC),
                coords=GARMISCH,
            )
        client = PerPhotoLandmarkClient(
            [
                LandmarkDetection(name="Zugspitze", confidence=0.9),
                LandmarkDetection(name="Zugspitzgipfel", confidence=0.9),
            ]
        )
        resolver = _RecordingResolverFactory({place_cell(*GARMISCH): _locality_answer("Grainau")})

        run = await _run_with_embedder(
            db_session,
            project,
            scoring_run.id,
            tmp_path,
            client,
            resolver,
            ConstantEmbedder,
            build_landmark_gazetteer=_gazetteer_confirming_at(GARMISCH),
        )

        events = (
            (
                await db_session.execute(
                    select(Event).where(Event.criterion_scoring_run_id == run.id)
                )
            )
            .scalars()
            .all()
        )
        assert [event.landmark_name for event in events] == ["Zugspitze"]
        assert len(await _register_rows(db_session, project.id)) == 1

    async def test_a_hit_below_the_threshold_never_enters_the_register(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Kanonisiert wird nur ein Name, der die Grenze erreicht (ADR 0107 Punkt 5): Ein
        unsicherer und wahrscheinlich falscher Name soll nicht die Anzeigeform eines Eintrags
        besetzen, dem sich spaeter der richtige anschliesst."""
        project = await _cloud_project(db_session, "unter-der-grenze")
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _landmark_photo(
            db_session,
            project,
            tmp_path,
            "a.jpg",
            "etag-1",
            datetime(2023, 1, 1, tzinfo=UTC),
            coords=GARMISCH,
        )
        client = RecordingLandmarkClient(
            detection=LandmarkDetection(
                name="Vermutung", confidence=LANDMARK_CONFIDENCE_THRESHOLD - 0.01
            )
        )
        embedder = ConstantEmbedder()

        await _run_with_embedder(
            db_session,
            project,
            scoring_run.id,
            tmp_path,
            client,
            _no_resolver,
            lambda: embedder,
        )

        assert await _register_rows(db_session, project.id) == []
        assert embedder.calls == []
        detection_row = (
            await db_session.execute(
                select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
            )
        ).scalar_one()
        # Die Zeile selbst entsteht unveraendert vollstaendig - die Antwort ist bezahlt.
        assert detection_row.name == "Vermutung"
        assert detection_row.canonical_name is None

    async def test_a_later_run_never_asks_a_discarded_photo_again(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Das Skip-bereits-gescorter-Fotos-Verhalten gilt providerunabhaengig und unabhaengig
        davon, ob der Treffer verwendbar war - sonst kostete jede Wiederholung erneut Geld."""
        project = await _cloud_project(db_session, "kein-zweiter-aufruf")
        scoring_run = await _add_successful_scoring_run(db_session, project)
        await _landmark_photo(
            db_session,
            project,
            tmp_path,
            "a.jpg",
            "etag-1",
            datetime(2023, 1, 1, tzinfo=UTC),
            coords=GARMISCH,
        )
        detection = LandmarkDetection(
            name="Vermutung", confidence=LANDMARK_CONFIDENCE_THRESHOLD - 0.01
        )

        first = RecordingLandmarkClient(detection=detection)
        await _run_with_embedder(
            db_session, project, scoring_run.id, tmp_path, first, _no_resolver, ConstantEmbedder
        )
        second = RecordingLandmarkClient(detection=detection)
        await _run_with_embedder(
            db_session, project, scoring_run.id, tmp_path, second, _no_resolver, ConstantEmbedder
        )

        assert len(first.calls) == 1
        assert second.calls == []

    async def test_without_an_embedder_the_run_completes_without_canonical_names(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Kein Einbetter, kein kanonischer Name, KEIN Laufabbruch: Die Erkennungszeilen entstehen
        unveraendert, und jede verhaelt sich wie vor dem Register - bestaetigt die Auskunft den
        Namen am Aufnahmeort, benennt er sein Event."""
        project = await _cloud_project(db_session, "ohne-einbetter")
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _landmark_photo(
            db_session,
            project,
            tmp_path,
            "a.jpg",
            "etag-1",
            datetime(2023, 1, 1, tzinfo=UTC),
            coords=GARMISCH,
        )
        client = RecordingLandmarkClient(
            detection=LandmarkDetection(name="Zugspitze", confidence=0.9)
        )

        run = await _run_with_embedder(
            db_session,
            project,
            scoring_run.id,
            tmp_path,
            client,
            _no_resolver,
            _no_embedder,
            build_landmark_gazetteer=_gazetteer_confirming_at(GARMISCH),
        )

        assert run.status == ScanStatus.SUCCESS
        assert await _register_rows(db_session, project.id) == []
        detection_row = (
            await db_session.execute(
                select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
            )
        ).scalar_one()
        assert detection_row.name == "Zugspitze"
        assert detection_row.canonical_name is None
        [event] = (
            (
                await db_session.execute(
                    select(Event).where(Event.criterion_scoring_run_id == run.id)
                )
            )
            .scalars()
            .all()
        )
        assert event.landmark_name == "Zugspitze"

    async def test_the_embedder_is_never_built_without_a_landmark_phase(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Ohne Einwilligung faellt die ganze Cloud-Phase aus - dann gibt es auch nichts zu
        kanonisieren, und ein 113-MB-Modell zu laden waere reine Arbeit."""
        project = await _make_project(db_session, name="ohne-einwilligung")
        scoring_run = await _add_successful_scoring_run(db_session, project)
        await _landmark_photo(
            db_session, project, tmp_path, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
        )

        run = await _run_with_embedder(
            db_session,
            project,
            scoring_run.id,
            tmp_path,
            _failing_landmark_client_builder,
            _no_resolver,
            ExplodingEmbedderBuilder(),
        )

        assert run.status == ScanStatus.SUCCESS

    async def test_the_embedder_is_never_built_without_a_single_candidate(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Phase wird betreten, aber es gibt nichts zu tun: Im ZWEITEN Lauf ueber dasselbe
        Projekt sind alle Fotos bereits gescort, `select_landmark_candidates` liefert die leere
        Liste, und die Blockschleife laeuft null Mal.

        Dieselbe Begruendung wie beim danebenstehenden `place_infos` ("ein Durchgang durch den
        Ortsdatensatz ohne offene Zelle waere reine Arbeit"): Ein 113-MB-Modell zu laden, um es
        ungenutzt zu verwerfen, ist Arbeit ohne Gegenwert."""
        project = await _cloud_project(db_session, "kein-kandidat-mehr")
        scoring_run = await _add_successful_scoring_run(db_session, project)
        await _landmark_photo(
            db_session,
            project,
            tmp_path,
            "a.jpg",
            "etag-1",
            datetime(2023, 1, 1, tzinfo=UTC),
            coords=GARMISCH,
        )

        first = RecordingLandmarkClient(
            detection=LandmarkDetection(name="Zugspitze", confidence=0.9)
        )
        await _run_with_embedder(
            db_session, project, scoring_run.id, tmp_path, first, _no_resolver, ConstantEmbedder
        )
        assert len(first.calls) == 1

        second = RecordingLandmarkClient()
        run = await _run_with_embedder(
            db_session,
            project,
            scoring_run.id,
            tmp_path,
            second,
            _no_resolver,
            ExplodingEmbedderBuilder(),
        )

        assert run.status == ScanStatus.SUCCESS
        assert second.calls == []

    async def test_the_register_of_one_project_is_never_read_for_another(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Kreuzfall (S8): Zwei Projekte, derselbe normalisierte Name - zwei Zeilen, keine
        Constraint-Verletzung, und die Zeile des einen wird fuer das andere nicht gelesen."""
        register_rows: list[LandmarkName] = []
        for name in ("projekt-a", "projekt-b"):
            project = await _cloud_project(db_session, name)
            scoring_run = await _add_successful_scoring_run(db_session, project)
            await _landmark_photo(
                db_session,
                project,
                tmp_path,
                f"{name}.jpg",
                f"etag-{name}",
                datetime(2023, 1, 1, tzinfo=UTC),
                coords=GARMISCH,
            )
            client = RecordingLandmarkClient(
                detection=LandmarkDetection(name="Zugspitze", confidence=0.9)
            )
            await _run_with_embedder(
                db_session,
                project,
                scoring_run.id,
                tmp_path,
                client,
                _no_resolver,
                ConstantEmbedder,
            )
            register_rows.extend(await _register_rows(db_session, project.id))

        assert len(register_rows) == 2
        assert {row.project_id for row in register_rows} == {
            row.project_id for row in register_rows
        }
        assert all(row.normalized_name == "zugspitze" for row in register_rows)
        assert register_rows[0].project_id != register_rows[1].project_id
