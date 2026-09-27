"""Die Phase `persons` des Klassifizierungslaufs.

Der Analyzer ist durchweg der Fake aus `tests/face_fakes.py`; er erkennt ein Foto an der Vollfarbe
seiner geschriebenen Display-Variante. Alle Merkmale liegen fern jeder Schwelle (Kosinus 1 bzw.
nahe 0), damit eine Kalibrierung der Regel hier nichts roetet.
"""

from __future__ import annotations

import ast
import hashlib
import logging
import sqlite3
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker as worker
from photosort.api.stats import get_project_stats
from photosort.db import Base, make_engine, make_session_factory
from photosort.face_analysis import MODEL_KEY, FaceAnalyzerLike
from photosort.label_embedding import LabelEmbedderLike
from photosort.landmark import LandmarkDetection, PlaceHint
from photosort.models import (
    ClassificationPhase,
    CriterionScoringRun,
    Person,
    PersonReference,
    Photo,
    PhotoMotifStrength,
    PhotoPersonCorrection,
    PhotoPersonDetection,
    PhotoRanking,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motifs import MOTIF_REGISTRY
from photosort.persons import (
    PersonAssignment,
    add_reference,
    create_person,
    delete_person,
    load_effective_persons,
    set_correction,
)
from photosort.remote_classification import RemoteClassification
from photosort.worker import run_classification
from tests.face_fakes import (
    SENTINEL_TEXT,
    Color,
    ExplodingAnalyzer,
    FakeFaceAnalyzer,
    face_embedding,
    write_display_variant,
)
from tests.import_closure import module_file
from tests.phase_binding import assert_phase_binding

ANNA = "Annabell-Merkname"
BERTA = "Bertrude-Merkname"
TAKEN = datetime(2023, 1, 1, tzinfo=UTC)

RED: Color = (220, 20, 20)
GREEN: Color = (20, 220, 20)
BLUE: Color = (20, 20, 220)
GREY: Color = (120, 120, 120)
ANCHOR: Color = (240, 240, 20)

UNKNOWN_FACES = [face_embedding(10), face_embedding(11), face_embedding(12)]


# --- Aufbau -----------------------------------------------------------------------------------


class _NoDetections:
    def detect(self, image: object) -> object:
        return SimpleNamespace(detections=[], face_landmarks=[], facial_transformation_matrixes=[])


class _NoSceneLabels:
    def classify(self, image: object) -> object:
        return SimpleNamespace(classifications=[SimpleNamespace(categories=[])])


class _LandscapeSceneLabels:
    def classify(self, image: object) -> object:
        return SimpleNamespace(
            classifications=[
                SimpleNamespace(categories=[SimpleNamespace(category_name="valley", score=0.7)])
            ]
        )


class _NeutralAesthetics:
    def predict(self, batch: object) -> object:
        return np.array([[0.1] * 10], dtype="float32")


class _FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        return [digest[0] / 255.0, digest[1] / 255.0]


def _fake_embedder() -> LabelEmbedderLike:
    return _FakeEmbedder()


class RecordingCategoryClient:
    def __init__(self, calls: list[tuple[str, str, int]]) -> None:
        self.calls = calls

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        self.calls.append((hashlib.sha256(image_bytes).hexdigest(), mime_type, photo_id))
        _assert_payload_is_clean(image_bytes, repr(photo_id))
        return RemoteClassification(
            motif_strengths={key: 0.0 for key in MOTIF_REGISTRY}, fine_labels=("Hund",)
        )


class RecordingLandmarkClient:
    def __init__(self, calls: list[tuple[str, str, str]]) -> None:
        self.calls = calls

    async def detect(
        self, image_bytes: bytes, mime_type: str, hint: PlaceHint | None
    ) -> LandmarkDetection:
        self.calls.append((hashlib.sha256(image_bytes).hexdigest(), mime_type, repr(hint)))
        _assert_payload_is_clean(image_bytes, repr(hint))
        return LandmarkDetection(name="Kölner Dom", confidence=0.9)


def _assert_payload_is_clean(image_bytes: bytes, text: str) -> None:
    for secret in (ANNA, BERTA, SENTINEL_TEXT):
        assert secret.encode() not in image_bytes
        assert secret not in text


@asynccontextmanager
async def _fresh_session(url: str = "sqlite+aiosqlite:///:memory:") -> AsyncIterator[AsyncSession]:
    engine = make_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with make_session_factory(engine)() as session:
        yield session
    await engine.dispose()


async def _user(session: AsyncSession) -> User:
    user = User(username="daniel", password_hash="hashed-value")
    session.add(user)
    await session.commit()
    return user


async def _project(session: AsyncSession, name: str, *, cloud_consent: bool = False) -> Project:
    project = Project(
        name=name,
        opencloud_drive_id=f"drive-{name}",
        opencloud_path=name,
        cloud_vision_detection_enabled=cloud_consent,
        cloud_vision_consent_at=datetime(2026, 1, 1) if cloud_consent else None,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _scoring_run(session: AsyncSession, project: Project) -> ScoringRun:
    run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _photo(
    session: AsyncSession,
    project: Project,
    cache_dir: Path,
    name: str,
    color: Color | None,
    *,
    rejected: bool = False,
) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=f"{project.name}/{name}.jpg",
        etag=f"etag-{project.name}-{name}",
        content_length=100,
        taken_at=TAKEN,
        taken_at_original=TAKEN,
        last_modified=TAKEN,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=100.0,
            exposure=0.0,
            cluster_key="cluster-0",
            suggested_status=RatingStatus.REJECTED if rejected else None,
            computed_at=TAKEN,
        )
    )
    await session.commit()
    if color is not None:
        write_display_variant(cache_dir, photo.id, photo.etag, color)
    return photo


async def _define(session: AsyncSession, name: str, axis: int, anchor: Photo, user: User) -> Person:
    person = await create_person(
        session,
        name=name,
        embedding=face_embedding(axis),
        model_key=MODEL_KEY,
        photo_id=anchor.id,
        user_id=user.id,
    )
    await session.commit()
    return person


async def _run(
    session: AsyncSession,
    project: Project,
    scoring_run: ScoringRun,
    cache_dir: Path,
    build_face_analyzer: Callable[[], FaceAnalyzerLike],
    *,
    use_cloud: bool = False,
    build_classifier: object = _NoSceneLabels,
    build_category_client: object = None,
    build_landmark_client: object = None,
) -> CriterionScoringRun:
    kwargs: dict[str, Any] = {}
    if build_category_client is not None:
        kwargs["build_category_client"] = build_category_client
    if build_landmark_client is not None:
        kwargs["build_landmark_client"] = build_landmark_client
    return await run_classification(
        session,
        project,
        scoring_run.id,
        cache_dir,
        use_cloud=use_cloud,
        build_detector=_NoDetections,
        build_animal_detector=_NoDetections,
        build_classifier=build_classifier,  # type: ignore[arg-type]
        build_aesthetics=_NeutralAesthetics,
        build_landmarker=_NoDetections,
        build_embedder=_fake_embedder,
        build_face_analyzer=build_face_analyzer,
        **kwargs,
    )


async def _detections(session: AsyncSession) -> set[tuple[int, int]]:
    rows = (
        await session.execute(select(PhotoPersonDetection.photo_id, PhotoPersonDetection.person_id))
    ).all()
    return {(photo_id, person_id) for photo_id, person_id in rows}


def _normalised(value: object) -> object:
    return "<zeit>" if isinstance(value, datetime) else value


async def _table_snapshot(
    session: AsyncSession, *, skip: frozenset[str] = frozenset()
) -> dict[str, list[tuple[object, ...]]]:
    """JEDE Tabelle aus `Base.metadata.sorted_tables`, Zeitstempel ausgeblendet."""
    return {
        table.name: sorted(
            (
                tuple(_normalised(value) for value in row)
                for row in (await session.execute(select(table))).all()
            ),
            key=repr,
        )
        for table in Base.metadata.sorted_tables
        if table.name not in skip
    }


class _Lay:
    """Ein Projekt "Reise" mit einem Anker-Projekt fuer die Festlegung."""

    def __init__(self, session: AsyncSession, cache_dir: Path) -> None:
        self.session = session
        self.cache_dir = cache_dir

    async def build(self, *, cloud_consent: bool = False) -> _Lay:
        self.user = await _user(self.session)
        anchor_project = await _project(self.session, "Anker")
        self.anchor = await _photo(self.session, anchor_project, self.cache_dir, "anker", ANCHOR)
        self.project = await _project(self.session, "Reise", cloud_consent=cloud_consent)
        self.scoring_run = await _scoring_run(self.session, self.project)
        return self


# --- Reihenfolge, Umfang, Fortschritt ---------------------------------------------------------


async def test_the_phase_runs_after_ranking_and_before_success(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lay = await _Lay(db_session, tmp_path).build()
    photo = await _photo(db_session, lay.project, tmp_path, "a", RED)
    anna = await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    order: list[str] = []
    observed: list[tuple[ClassificationPhase | None, ScanStatus]] = []

    original_rankings = worker._build_grouping_and_rankings

    async def recording_rankings(*args: Any, **kwargs: Any) -> Any:
        order.append("ranking")
        return await original_rankings(*args, **kwargs)

    monkeypatch.setattr(worker, "_build_grouping_and_rankings", recording_rankings)

    def on_detect(color: Color) -> None:
        order.append("persons")
        run = worker_run_of(db_session)
        observed.append((run.phase, run.status))

    analyzer = FakeFaceAnalyzer({RED: [face_embedding(0)]}, on_detect=on_detect)

    run = await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    assert order == ["ranking", "persons"]
    assert observed == [(ClassificationPhase.PERSONS, ScanStatus.RUNNING)]
    assert run.status is ScanStatus.SUCCESS
    assert run.phase is None
    assert_phase_binding(run)
    assert await _detections(db_session) == {(photo.id, anna.id)}


def worker_run_of(session: AsyncSession) -> CriterionScoringRun:
    """Die laufende Lauf-Zeile aus der Identitaetsabbildung - ohne Datenbankzugriff, damit der
    synchrone Haken des Fakes sie lesen kann."""
    [run] = [
        obj
        for obj in session.identity_map.values()
        if isinstance(obj, CriterionScoringRun) and obj.status is ScanStatus.RUNNING
    ]
    return run


async def test_every_photo_of_the_project_is_recognised_including_the_ausschuss(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    lay = await _Lay(db_session, tmp_path).build()
    kept = await _photo(db_session, lay.project, tmp_path, "a", RED)
    rejected = await _photo(db_session, lay.project, tmp_path, "b", GREEN, rejected=True)
    anna = await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    analyzer = FakeFaceAnalyzer({RED: [face_embedding(0)], GREEN: [face_embedding(0)]})

    run = await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    assert await _detections(db_session) == {(kept.id, anna.id), (rejected.id, anna.id)}
    assert run.persons_photos_total == 2
    assert run.persons_photos_processed == 2


async def test_progress_and_watchdog_are_written_per_block(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker, "PERSONS_COMMIT_BATCH_SIZE", 1)
    lay = await _Lay(db_session, tmp_path).build()
    for index, color in enumerate((RED, GREEN, BLUE)):
        await _photo(db_session, lay.project, tmp_path, f"p{index}", color)
    await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    seen: list[tuple[int | None, int | None, datetime]] = []

    def on_detect(color: Color) -> None:
        run = worker_run_of(db_session)
        seen.append((run.persons_photos_processed, run.persons_photos_total, run.last_progress_at))

    analyzer = FakeFaceAnalyzer(
        {RED: [face_embedding(0)], GREEN: [], BLUE: [face_embedding(0)]}, on_detect=on_detect
    )

    run = await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    assert [(processed, total) for processed, total, _ in seen] == [(0, 3), (1, 3), (2, 3)]
    assert seen[1][2] <= seen[2][2]
    assert (run.persons_photos_processed, run.persons_photos_total) == (3, 3)


# --- Die Phase laeuft nicht -------------------------------------------------------------------


async def _old_detection(session: AsyncSession, photo: Photo, person: Person) -> None:
    session.add(PhotoPersonDetection(photo_id=photo.id, person_id=person.id, computed_at=TAKEN))
    await session.commit()


@pytest.mark.parametrize("lage", ["ohne-person", "nur-fremdes-modell", "builder-scheitert"])
async def test_the_phase_does_not_run_and_leaves_old_detections(
    db_session: AsyncSession, tmp_path: Path, lage: str
) -> None:
    lay = await _Lay(db_session, tmp_path).build()
    photo = await _photo(db_session, lay.project, tmp_path, "a", RED)
    builder: Callable[[], FaceAnalyzerLike] = ExplodingAnalyzer
    expected: set[tuple[int, int]] = set()
    if lage != "ohne-person":
        anna = await _define(db_session, ANNA, 0, lay.anchor, lay.user)
        await _old_detection(db_session, photo, anna)
        expected = {(photo.id, anna.id)}
    if lage == "nur-fremdes-modell":
        await db_session.execute(PersonReference.__table__.update().values(model_key="alt"))
        await db_session.commit()
    if lage == "builder-scheitert":

        def builder() -> FaceAnalyzerLike:
            raise RuntimeError("Modell nicht ladbar")

    run = await _run(db_session, lay.project, lay.scoring_run, tmp_path, builder)

    assert run.status is ScanStatus.SUCCESS
    assert run.persons_photos_total is None
    assert run.persons_photos_processed is None
    assert await _detections(db_session) == expected


# --- Nur verarbeitete Fotos werden ersetzt ----------------------------------------------------


async def test_only_processed_photos_have_their_detections_replaced(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    lay = await _Lay(db_session, tmp_path).build()
    processed = await _photo(db_session, lay.project, tmp_path, "a", RED)
    without_cache = await _photo(db_session, lay.project, tmp_path, "b", None)
    failing = await _photo(db_session, lay.project, tmp_path, "c", BLUE)
    anna = await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    for photo in (processed, without_cache, failing):
        await _old_detection(db_session, photo, anna)
    analyzer = FakeFaceAnalyzer({RED: [], BLUE: [face_embedding(0)]}, failing=frozenset({BLUE}))

    run = await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    assert run.status is ScanStatus.SUCCESS
    assert await _detections(db_session) == {(without_cache.id, anna.id), (failing.id, anna.id)}


# --- Person mitten im Lauf geloescht ----------------------------------------------------------


async def test_a_person_deleted_mid_run_leaves_no_row_and_the_other_blocks_are_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S10: Die Loeschung laeuft ueber eine ZWEITE Verbindung, waehrend der Lauf rechnet. Das
    Schreiben des Blocks scheitert am echten Fremdschluessel; die Phase verwirft nur ihn."""
    monkeypatch.setattr(worker, "PERSONS_COMMIT_BATCH_SIZE", 1)
    database = tmp_path / "lauf.db"
    cache_dir = tmp_path / "cache"
    async with _fresh_session(f"sqlite+aiosqlite:///{database}") as session:
        lay = await _Lay(session, cache_dir).build()
        await _photo(session, lay.project, cache_dir, "a", RED)
        await _photo(session, lay.project, cache_dir, "b", GREEN)
        third = await _photo(session, lay.project, cache_dir, "c", BLUE)
        anna = await _define(session, ANNA, 0, lay.anchor, lay.user)
        berta = await _define(session, BERTA, 1, lay.anchor, lay.user)
        anna_id, berta_id, third_id = anna.id, berta.id, third.id

        def delete_anna_on_green(color: Color) -> None:
            if color != GREEN:
                return
            connection = sqlite3.connect(database)
            connection.execute("PRAGMA foreign_keys=ON")
            for table in (
                "photo_person_corrections",
                "photo_person_detections",
                "person_references",
            ):
                connection.execute(f"DELETE FROM {table} WHERE person_id = ?", (anna_id,))
            connection.execute("DELETE FROM persons WHERE id = ?", (anna_id,))
            connection.commit()
            connection.close()

        analyzer = FakeFaceAnalyzer(
            {
                RED: [face_embedding(0)],
                GREEN: [face_embedding(0)],
                BLUE: [face_embedding(1)],
            },
            on_detect=delete_anna_on_green,
        )

        run = await _run(session, lay.project, lay.scoring_run, cache_dir, lambda: analyzer)

        assert run.status is ScanStatus.SUCCESS
        rows = await _detections(session)
        assert all(person_id != anna_id for _, person_id in rows)
        assert rows == {(third_id, berta_id)}


# --- Korrekturen --------------------------------------------------------------------------------


async def test_no_run_writes_or_deletes_a_correction(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    lay = await _Lay(db_session, tmp_path).build()
    removed = await _photo(db_session, lay.project, tmp_path, "a", RED)
    added = await _photo(db_session, lay.project, tmp_path, "b", GREEN)
    anna = await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    await set_correction(
        db_session, photo_id=removed.id, person_id=anna.id, applies=False, user_id=lay.user.id
    )
    await set_correction(
        db_session, photo_id=added.id, person_id=anna.id, applies=True, user_id=lay.user.id
    )
    await db_session.commit()
    snapshot_query = select(
        PhotoPersonCorrection.id,
        PhotoPersonCorrection.photo_id,
        PhotoPersonCorrection.person_id,
        PhotoPersonCorrection.user_id,
        PhotoPersonCorrection.applies,
        PhotoPersonCorrection.updated_at,
    ).order_by(PhotoPersonCorrection.id)
    before = (await db_session.execute(snapshot_query)).all()
    analyzer = FakeFaceAnalyzer({RED: [face_embedding(0)], GREEN: []})

    for _ in range(2):
        await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    assert (await db_session.execute(snapshot_query)).all() == before


def test_the_worker_names_the_correction_table_nowhere() -> None:
    """Kein Lauf schreibt oder loescht `photo_person_corrections` - der Worker nennt das Modell
    nicht einmal."""
    path = module_file("photosort.worker")
    assert path is not None
    names = {
        node.id
        for node in ast.walk(ast.parse(path.read_text("utf-8")))
        if isinstance(node, ast.Name)
    }

    assert "PhotoPersonCorrection" not in names
    assert "photo_person_corrections" not in path.read_text("utf-8")


def test_the_worker_never_reads_a_person_name() -> None:
    """S6: `worker.py` importiert beide Seiten. Die Phase liest nur Id und Schwerpunkt ueber
    `current_centroids` - das Modell `Person` kommt im Worker nicht vor."""
    path = module_file("photosort.worker")
    assert path is not None
    tree = ast.parse(path.read_text("utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "photosort.models"
        for alias in node.names
    }

    assert "Person" not in imported
    assert "current_centroids" in {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "photosort.persons"
        for alias in node.names
    }


async def test_a_correction_outranks_the_recognition_over_runs(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    lay = await _Lay(db_session, tmp_path).build()
    removed = await _photo(db_session, lay.project, tmp_path, "a", RED)
    added = await _photo(db_session, lay.project, tmp_path, "b", GREEN)
    anna = await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    await set_correction(
        db_session, photo_id=removed.id, person_id=anna.id, applies=False, user_id=lay.user.id
    )
    await set_correction(
        db_session, photo_id=added.id, person_id=anna.id, applies=True, user_id=lay.user.id
    )
    await db_session.commit()
    analyzer = FakeFaceAnalyzer({RED: [face_embedding(0)], GREEN: []})

    async def effective() -> dict[int, list[PersonAssignment]]:
        return await load_effective_persons(db_session, [removed.id, added.id])

    await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)
    assert await _detections(db_session) == {(removed.id, anna.id)}
    assert await effective() == {added.id: [PersonAssignment(anna.id, "corrected")]}

    await add_reference(
        db_session,
        person_id=anna.id,
        embedding=face_embedding(0),
        model_key=MODEL_KEY,
        photo_id=lay.anchor.id,
        user_id=lay.user.id,
    )
    await db_session.commit()
    await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    assert await effective() == {added.id: [PersonAssignment(anna.id, "corrected")]}


# --- Unbekannte Gesichter ---------------------------------------------------------------------


async def _twin(cache_dir: Path, faces: list[list[float]]) -> dict[str, list[tuple[object, ...]]]:
    async with _fresh_session() as session:
        lay = await _Lay(session, cache_dir).build()
        for index, color in enumerate((RED, GREEN)):
            await _photo(session, lay.project, cache_dir, f"p{index}", color)
        await _define(session, ANNA, 0, lay.anchor, lay.user)
        analyzer = FakeFaceAnalyzer({RED: faces, GREEN: faces})
        await _run(session, lay.project, lay.scoring_run, cache_dir, lambda: analyzer)
        return await _table_snapshot(session)


async def test_unknown_faces_leave_the_same_data_as_no_faces(tmp_path: Path) -> None:
    """Zwillingslauf: drei unbekannte Gesichter je Foto gegen kein Gesicht."""
    with_unknown = await _twin(tmp_path / "u", UNKNOWN_FACES)
    without = await _twin(tmp_path / "n", [])

    assert with_unknown == without
    assert with_unknown["criterion_scoring_runs"], "der Schnappschuss prueft etwas"


async def test_the_sentinel_of_a_face_appears_only_in_the_shown_reference(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="photosort")
    lay = await _Lay(db_session, tmp_path).build()
    await _photo(db_session, lay.project, tmp_path, "a", RED)
    await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    analyzer = FakeFaceAnalyzer({RED: [face_embedding(0), *UNKNOWN_FACES]})

    await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    snapshot = await _table_snapshot(db_session)
    stored_elsewhere = repr(
        {name: rows for name, rows in snapshot.items() if name != "person_references"}
    )
    assert SENTINEL_TEXT not in stored_elsewhere
    assert SENTINEL_TEXT not in caplog.text
    # Gegenprobe: dieselbe Suche findet den Wert im gezeigten Gesicht - sonst waere sie leer.
    assert SENTINEL_TEXT in repr(snapshot["person_references"])


async def test_the_log_carries_no_name_and_no_embedding_value(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """S11: Lauf mit einpraegsamen Namen und Merkmalswerten, darunter ein werfendes Foto."""
    caplog.set_level(logging.DEBUG, logger="photosort")
    lay = await _Lay(db_session, tmp_path).build()
    await _photo(db_session, lay.project, tmp_path, "a", RED)
    failing = await _photo(db_session, lay.project, tmp_path, "b", GREEN)
    await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    await _define(db_session, BERTA, 1, lay.anchor, lay.user)
    analyzer = FakeFaceAnalyzer(
        {RED: [face_embedding(0), face_embedding(1)], GREEN: []}, failing=frozenset({GREEN})
    )

    await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    for secret in (ANNA, BERTA, SENTINEL_TEXT, "0.99992"):
        assert secret not in caplog.text
    assert "RuntimeError" in caplog.text
    assert str(failing.id) in caplog.text


# --- Nur lokal ----------------------------------------------------------------------------------


async def _cloud_twin(cache_dir: Path, *, with_persons: bool) -> tuple[list[Any], list[Any]]:
    category_calls: list[tuple[str, str, int]] = []
    landmark_calls: list[tuple[str, str, str]] = []
    async with _fresh_session() as session:
        lay = await _Lay(session, cache_dir).build(cloud_consent=True)
        for index, color in enumerate((RED, GREEN)):
            await _photo(session, lay.project, cache_dir, f"p{index}", color)
        if with_persons:
            await _define(session, ANNA, 0, lay.anchor, lay.user)
            await _define(session, BERTA, 1, lay.anchor, lay.user)
        analyzer = FakeFaceAnalyzer(
            {RED: [face_embedding(0), face_embedding(1)], GREEN: [face_embedding(1)]}
        )

        run = await _run(
            session,
            lay.project,
            lay.scoring_run,
            cache_dir,
            lambda: analyzer,
            use_cloud=True,
            build_classifier=_LandscapeSceneLabels,
            build_category_client=lambda _model: RecordingCategoryClient(category_calls),
            build_landmark_client=lambda _model: RecordingLandmarkClient(landmark_calls),
        )
        assert run.status is ScanStatus.SUCCESS
        if with_persons:
            assert len(await _detections(session)) == 3
    return category_calls, landmark_calls


async def test_the_cloud_sees_the_same_requests_with_and_without_persons(tmp_path: Path) -> None:
    """S6: Mit Einwilligung und zwei festgelegten Personen gehen dieselben Anfragen an beide
    Cloud-Pfade wie ohne Personen - und keine traegt einen Namen oder einen Merkmalswert (die
    Doubles pruefen jede Nutzlast)."""
    with_persons = await _cloud_twin(tmp_path / "mit", with_persons=True)
    without_persons = await _cloud_twin(tmp_path / "ohne", with_persons=False)

    assert with_persons == without_persons
    assert with_persons[0], "die Kategorie-Doubles wurden gerufen"
    assert with_persons[1], "die Sehenswuerdigkeits-Doubles wurden gerufen"


# --- Kein Motiv ---------------------------------------------------------------------------------


async def _motif_twin(cache_dir: Path, *, recognised: bool) -> tuple[object, ...]:
    async with _fresh_session() as session:
        lay = await _Lay(session, cache_dir).build()
        photos = [
            await _photo(session, lay.project, cache_dir, f"p{index}", color)
            for index, color in enumerate((RED, GREEN, BLUE))
        ]
        await _define(session, ANNA, 0, lay.anchor, lay.user)
        faces = [face_embedding(0)] if recognised else UNKNOWN_FACES
        analyzer = FakeFaceAnalyzer({RED: faces, GREEN: faces, BLUE: []})
        await _run(session, lay.project, lay.scoring_run, cache_dir, lambda: analyzer)
        assert bool(await _detections(session)) is recognised

        strengths = (
            await session.execute(
                select(
                    PhotoMotifStrength.photo_id,
                    PhotoMotifStrength.motif_key,
                    PhotoMotifStrength.strength,
                ).order_by(PhotoMotifStrength.id)
            )
        ).all()
        rankings = (
            await session.execute(
                select(
                    PhotoRanking.photo_id,
                    PhotoRanking.rank_score,
                    PhotoRanking.rank_position,
                    PhotoRanking.selection_position,
                ).order_by(PhotoRanking.photo_id)
            )
        ).all()
        stats = await get_project_stats(lay.project.id, session=session, current_user=lay.user)
        dumped = stats.model_dump(mode="json")
        # Speicherbedarf und Laufzeitpunkte haengen am Bestand, nicht an der Aussage.
        comparable = {
            key: value
            for key, value in dumped.items()
            if key not in {"storage", "last_successful_runs"}
        }
        return tuple(strengths), tuple(rankings), comparable, len(photos)


async def test_a_recognised_person_is_no_motif(tmp_path: Path) -> None:
    assert await _motif_twin(tmp_path / "mit", recognised=True) == await _motif_twin(
        tmp_path / "ohne", recognised=False
    )


# --- Bestand und global -----------------------------------------------------------------------


async def test_an_existing_project_gets_its_names_with_the_next_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    lay = await _Lay(db_session, tmp_path).build()
    photo = await _photo(db_session, lay.project, tmp_path, "a", RED)
    analyzer = FakeFaceAnalyzer({RED: [face_embedding(0)]})
    await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)
    assert await _detections(db_session) == set()

    anna = await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    assert await _detections(db_session) == {(photo.id, anna.id)}


async def test_a_face_shown_in_project_a_recognises_the_person_in_project_b(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Festlegung gilt global: gezeigt wurde im Anker-Projekt, erkannt wird in "Reise"."""
    lay = await _Lay(db_session, tmp_path).build()
    photo = await _photo(db_session, lay.project, tmp_path, "a", RED)
    anna = await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    analyzer = FakeFaceAnalyzer({RED: [face_embedding(0)]})

    await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    assert await _detections(db_session) == {(photo.id, anna.id)}
    assert lay.anchor.project_id != lay.project.id


async def test_after_deleting_a_person_it_is_no_longer_recognised(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    lay = await _Lay(db_session, tmp_path).build()
    await _photo(db_session, lay.project, tmp_path, "a", RED)
    anna = await _define(db_session, ANNA, 0, lay.anchor, lay.user)
    await delete_person(db_session, anna.id)
    await db_session.commit()
    await _define(db_session, BERTA, 1, lay.anchor, lay.user)
    analyzer = FakeFaceAnalyzer({RED: [face_embedding(0)]})

    await _run(db_session, lay.project, lay.scoring_run, tmp_path, lambda: analyzer)

    assert await _detections(db_session) == set()
