"""Kriterien-Lauf: lokale Motivbewertung, Nicht-Messbares, Altzeile, Qualitaetswert des Rangschritts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.album_suitability import normalize_level
from photosort.criteria import CRITERIA_REGISTRY
from photosort.landmark import (
    LandmarkDetection,
)
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    Project,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motif_strengths import load_effective_strengths, upsert_assessment
from photosort.motifs import MOTIF_REGISTRY
from photosort.quality import LOCAL_CORRECTION_SPAN
from photosort.thumbnails import display_path
from photosort.worker import run_criterion_scoring
from photosort.worker._criterion import local as worker_local
from tests.support import make_project as _make_project
from tests.support import write_display_variant
from tests.support.criterion_scoring import (
    FaceLandmarkerStub,
    NeutralAestheticsModel,
    NoAnimalDetector,
    NoFaceDetector,
    NoFaceLandmarker,
    NoSceneLabels,
    RecordingLandmarkClient,
    SingleFaceDetector,
    _add_album_suitability,
    _add_photo,
    _add_score,
    _add_successful_scoring_run,
    _animal_detector_stub,
    _criteria_of,
    _flat_image,
    _landscape_scene_classifier,
    _no_aesthetics_model,
    _no_animal_detector,
    _no_face_detector,
    _no_face_landmarker,
    _no_scene_classifier,
    _rotation_matrix_y,
    _run_with_landmark_client,
    _scene_classifier_stub,
)

# specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 4: der Kriterien-Lauf schreibt je Foto
# eine LOKALE Kopfzeile samt Stärkevektor. Rein additiv - die bestehende Kategorieableitung läuft
# unverändert daneben weiter (Ablösung erst in PR 3).
#
# Der tragende Fall dieses Abschnitts ist
# `test_a_small_face_weakens_the_people_motif_without_touching_content_people`: getrennt
# geschrieben bestünden beide Assertions auch dann, wenn die alte Präsenz-Berechnung
# stillschweigend zur neuen geworden ist - und damit wären Rangfolge und
# Landmark-Kandidatenwahl mitverändert.
_MOTIF_TEST_IMAGE_SIZE = 160


class SizedFaceDetector:
    """Faket den mediapipe FaceDetector so, dass GENAU EIN Gesicht mit konfigurierbarer
    Boxgroesse (in Pixeln des 160x160-Testbilds) gefunden wird - analog AnimalDetectorStub, aber
    mit steuerbarer FLAECHE: die Flaechengewichtung der Motivstaerken ist genau daran zu messen."""

    def __init__(self, size_px: int) -> None:
        self._size_px = size_px

    def detect(self, image: object) -> object:
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(score=0.9)],
                    bounding_box=SimpleNamespace(
                        origin_x=0, origin_y=0, width=self._size_px, height=self._size_px
                    ),
                )
            ]
        )


class SizedAnimalDetector:
    """Wie AnimalDetectorStub, aber mit konfigurierbarer Boxgroesse - fuer den
    Monotonie-Nachweis der Flaechengewichtung."""

    def __init__(self, size_px: int) -> None:
        self._size_px = size_px

    def detect(self, image: object) -> object:
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(category_name="dog", score=0.9)],
                    bounding_box=SimpleNamespace(
                        origin_x=0, origin_y=0, width=self._size_px, height=self._size_px
                    ),
                )
            ]
        )


async def _motif_strengths_of(session: AsyncSession, photo: Photo) -> dict[str, float]:
    rows = (
        await session.execute(
            select(PhotoMotifStrength).where(PhotoMotifStrength.photo_id == photo.id)
        )
    ).scalars()
    return {row.motif_key: row.strength for row in rows}


async def _criterion_values_of(session: AsyncSession, photo: Photo) -> dict[str, float]:
    rows = (
        await session.execute(
            select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
        )
    ).scalars()
    return {row.criterion_key: row.value for row in rows}


async def _one_photo_run(
    db_session: AsyncSession,
    tmp_path: Path,
    *,
    build_detector: object = _no_face_detector,
    build_animal_detector: object = _no_animal_detector,
    build_classifier: object = _no_scene_classifier,
) -> tuple[CriterionScoringRun, Photo]:
    project = await _make_project(db_session, name=f"Projekt {uuid4()}")
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", f"etag-{uuid4()}", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))
    # Der Regelfall seit Spec 0428: ein Ausschuss-Ueberlebender traegt die Modellbewertung aus
    # dem Cloud-Teilschritt, und erst damit entsteht ueberhaupt ein Qualitaetswert.
    await _add_album_suitability(db_session, photo)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=build_detector,  # type: ignore[arg-type]
        build_animal_detector=build_animal_detector,  # type: ignore[arg-type]
        build_classifier=build_classifier,  # type: ignore[arg-type]
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )
    return run, photo


async def test_a_criterion_run_writes_a_local_motif_assessment_header(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    run, photo = await _one_photo_run(db_session, tmp_path)

    assert run.status == ScanStatus.SUCCESS
    header = await db_session.get(PhotoMotifAssessment, photo.id)
    assert header is not None
    assert header.source == MotifAssessmentSource.LOCAL
    assert header.provider is None
    assert header.excluded_document is False
    assert header.computed_at is not None


async def test_the_local_header_carries_all_eight_motifs(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    _run, photo = await _one_photo_run(db_session, tmp_path)

    assert set(await _motif_strengths_of(db_session, photo)) == set(MOTIF_REGISTRY)


async def test_a_photo_without_any_detection_still_gets_a_header_with_eight_zeroes(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Sonst gilt das Foto als „noch nicht klassifiziert", obwohl es beurteilt wurde - und die
    Oberflaeche zeigte einen Satz statt der Liste."""
    _run, photo = await _one_photo_run(db_session, tmp_path)

    assert set((await _motif_strengths_of(db_session, photo)).values()) == {0.0}
    assert await db_session.get(PhotoMotifAssessment, photo.id) is not None


async def test_the_two_locally_unassessable_motifs_stay_at_zero_after_a_real_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """`aktivitaet` und `detail_stimmung` sind ohne Cloud-Aussage strukturell nicht erreichbar -
    die bewusst akzeptierte Grenze der lokalen Grundlage, kein Fehlerfall."""
    _run, photo = await _one_photo_run(
        db_session,
        tmp_path,
        build_detector=lambda: SizedFaceDetector(size_px=120),
        build_animal_detector=lambda: SizedAnimalDetector(size_px=140),
        build_classifier=_landscape_scene_classifier,
    )

    strengths = await _motif_strengths_of(db_session, photo)

    assert strengths["aktivitaet"] == 0.0
    assert strengths["detail_stimmung"] == 0.0


async def test_a_small_face_weakens_the_people_motif_without_touching_content_people(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DER Fall, der die Flaechengewichtung von der bestehenden Praesenz-Berechnung trennt: EIN
    Aufbau, ZWEI Assertions. Ein kleines Gesicht ergibt eine Menschen-Staerke < 1.0, und
    `content_people` desselben Fotos ist weiter GENAU 1.0.

    Getrennt geschrieben bestuenden beide Assertions auch dann, wenn die alte Praesenz-Berechnung
    stillschweigend zur neuen geworden ist - und damit waeren Rangfolge (rank_score ueber
    `content_people`) und Landmark-Kandidatenwahl mitveraendert, ohne dass ein Test darueber
    brach."""
    # 16 von 160 Pixeln Kantenlaenge -> 1 % der Bildflaeche, deutlich unter dem
    # Saettigungsanteil von `menschen`.
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_detector=lambda: SizedFaceDetector(size_px=16)
    )

    strengths = await _motif_strengths_of(db_session, photo)
    criteria = await _criterion_values_of(db_session, photo)

    assert 0.0 < strengths["menschen"] < 1.0
    assert criteria["content_people"] == 1.0


async def test_a_full_frame_face_saturates_the_people_motif(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Gegenprobe zum Fall oben - ohne sie bestuende auch eine Berechnung, die nie 1.0
    erreicht."""
    _run, photo = await _one_photo_run(
        db_session,
        tmp_path,
        build_detector=lambda: SizedFaceDetector(size_px=_MOTIF_TEST_IMAGE_SIZE),
    )

    assert (await _motif_strengths_of(db_session, photo))["menschen"] == 1.0


@pytest.mark.parametrize(("smaller_px", "larger_px"), [(16, 40), (40, 60)])
async def test_a_larger_animal_yields_a_higher_animal_motif_strength(
    db_session: AsyncSession, tmp_path: Path, smaller_px: int, larger_px: int
) -> None:
    """Ein bildfuellender Hund ergibt eine hohe Tier-Staerke, ein Hund am Bildrand eine niedrige -
    gemessen am LAUF, nicht nur an der reinen Funktion."""
    _run, small_photo = await _one_photo_run(
        db_session, tmp_path, build_animal_detector=lambda: SizedAnimalDetector(smaller_px)
    )
    small = (await _motif_strengths_of(db_session, small_photo))["tiere"]

    _run2, large_photo = await _one_photo_run(
        db_session, tmp_path, build_animal_detector=lambda: SizedAnimalDetector(larger_px)
    )
    large = (await _motif_strengths_of(db_session, large_photo))["tiere"]

    assert 0.0 < small < large


async def test_the_animal_confidence_alone_does_not_raise_the_animal_motif(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Gegenprobe zur Monotonie: die bloße Anwesenheit wirkt nicht. Das `tier`-KRITERIUM traegt
    weiter die Konfidenz - die MOTIVSTAERKE die Flaeche."""
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_animal_detector=lambda: SizedAnimalDetector(size_px=8)
    )

    criteria = await _criterion_values_of(db_session, photo)
    strengths = await _motif_strengths_of(db_session, photo)

    assert criteria["tier"] == 0.9
    assert strengths["tiere"] < 0.1


async def test_the_scene_confidence_feeds_the_landscape_motif_unweighted(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Szenen-Klassifikation liefert keine Boxen - ihre Konfidenz ist bereits eine Aussage
    ueber das ganze Bild, und es gibt dort keine Flaechengewichtung zu berechnen."""
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_classifier=_landscape_scene_classifier
    )

    assert (await _motif_strengths_of(db_session, photo))["landschaft"] == pytest.approx(0.8)


async def test_the_architecture_confidence_feeds_the_building_motif(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_classifier=_scene_classifier_stub
    )

    strengths = await _motif_strengths_of(db_session, photo)

    assert strengths["bauwerk_sehenswuerdigkeit"] == pytest.approx(0.8)


async def test_a_recognised_landmark_strengthens_the_building_motif(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Eine erkannte Sehenswuerdigkeit ist kein eigenes Motiv: sie VERSTAERKT „Bauwerk und
    Sehenswuerdigkeit". Der Wert entsteht erst in der Landmark-Phase - die lokale Kopfzeile muss
    also NACH ihr geschrieben werden, sonst fehlte der gerade bezahlte Beitrag."""
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))
    client = RecordingLandmarkClient(LandmarkDetection(name="Tal-Kapelle", confidence=0.95))

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert client.calls, (
        "der Landmark-Aufruf muss stattgefunden haben, sonst prueft der Fall nichts"
    )
    criteria = await _criterion_values_of(db_session, photo)
    strengths = await _motif_strengths_of(db_session, photo)
    # Der Szenen-Stub liefert `valley` (0.8) fuer `landschaft`, `gebaeude` bleibt 0.0 - der
    # Bauwerk-Wert kann also nur aus der Sehenswuerdigkeit kommen.
    assert criteria["landmark"] == pytest.approx(0.95)
    assert criteria.get("gebaeude", 0.0) == 0.0
    assert strengths["bauwerk_sehenswuerdigkeit"] == pytest.approx(0.95)


async def test_a_local_run_does_not_overwrite_an_existing_cloud_header(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Liegt eine Modellaussage vor, bestimmt allein sie die Motivstaerken - Herkunft,
    Zeitstempel und alle acht Werte bleiben unveraendert. Ohne diesen Fall bestuende auch ein
    bedingungsloses Ueberschreiben."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))
    cloud_time = datetime(2026, 9, 1, 8, 0, 0)
    cloud_vector = dict.fromkeys(MOTIF_REGISTRY, 0.0) | {"aktivitaet": 0.77, "menschen": 0.33}
    await upsert_assessment(
        db_session,
        photo.id,
        source=MotifAssessmentSource.CLOUD,
        strengths=cloud_vector,
        excluded_document=False,
        provider="anthropic",
        computed_at=cloud_time,
    )
    await db_session.commit()

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=lambda: SizedFaceDetector(size_px=_MOTIF_TEST_IMAGE_SIZE),
        build_animal_detector=lambda: SizedAnimalDetector(size_px=_MOTIF_TEST_IMAGE_SIZE),
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    header = await db_session.get(PhotoMotifAssessment, photo.id)
    assert header is not None
    assert header.source == MotifAssessmentSource.CLOUD
    assert header.provider == "anthropic"
    assert header.computed_at == cloud_time
    assert await _motif_strengths_of(db_session, photo) == cloud_vector


async def test_a_correction_survives_the_criterion_run_and_still_wins(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Korrigieren, danach klassifizieren: die Korrekturzeile haengt an keinem Lauf und greift
    bereits im ersten."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))
    user = User(username="daniel", password_hash="hashed-value")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        PhotoMotifCorrection(photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True)
    )
    await db_session.commit()

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert len((await db_session.execute(select(PhotoMotifCorrection))).scalars().all()) == 1
    effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
    assert effective["menschen"].strength == 1.0
    assert effective["menschen"].correction is True
    # Die gespeicherte Zahl bleibt die Beurteilung des Laufs - die Korrektur wirkt im Lesepfad.
    assert (await _motif_strengths_of(db_session, photo))["menschen"] == 0.0


async def test_the_area_fractions_never_become_a_criterion_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Keine neue Kriterien-Spalte und keine persistierte Box: die Flaechenanteile leben
    ausschliesslich im Lauf und gehen in die Staerke ein."""
    _run, photo = await _one_photo_run(
        db_session,
        tmp_path,
        build_detector=lambda: SizedFaceDetector(size_px=40),
        build_animal_detector=lambda: SizedAnimalDetector(size_px=40),
        build_classifier=_landscape_scene_classifier,
    )

    written = set(await _criterion_values_of(db_session, photo))

    assert written <= set(CRITERIA_REGISTRY), f"unbekannte Kriterien-Schluessel: {written}"


async def test_a_photo_gets_its_motif_strengths_and_exactly_one_ranking_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Beides in EINEM Fall: derselbe Lauf schreibt den Staerkevektor UND genau eine Rangzeile.

    Getrennt geschrieben bestuende jede Haelfte auch dann, wenn der Ranking-Teilschritt wieder
    eine Zeile je Motiv anlegte - die Zahl der Zeilen waere in einem reinen Staerketest
    unsichtbar, und der Unique-Constraint griffe nur bei zwei Zeilen desselben PAARES."""
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_animal_detector=_animal_detector_stub
    )

    ranking = (
        await db_session.execute(select(PhotoRanking).where(PhotoRanking.photo_id == photo.id))
    ).scalar_one()
    strengths = await _motif_strengths_of(db_session, photo)

    assert ranking.rank_position == 1
    assert set(strengths) == set(MOTIF_REGISTRY)
    assert strengths["tiere"] > 0.0


async def test_a_photo_whose_display_variant_is_missing_still_gets_a_header(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Best-effort wie ueberall im Lauf: ohne Bilddatei gibt es keine Detektion, aber das Foto ist
    beurteilt - acht Nullen, kein fehlender Vektor."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.SUCCESS
    assert await db_session.get(PhotoMotifAssessment, photo.id) is not None
    assert set((await _motif_strengths_of(db_session, photo)).values()) == {0.0}


async def test_a_second_run_replaces_the_local_vector_without_duplicating_rows(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))

    for detector_size in (16, _MOTIF_TEST_IMAGE_SIZE):
        await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=lambda size=detector_size: SizedFaceDetector(size),  # type: ignore[misc]
            build_animal_detector=_no_animal_detector,
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
        )

    strengths = await _motif_strengths_of(db_session, photo)

    assert len(strengths) == len(MOTIF_REGISTRY)
    assert strengths["menschen"] == 1.0


async def test_an_ausschuss_photo_gets_no_motif_header(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Der Lauf beurteilt genau die Ausschuss-Ueberlebenden - ein aussortiertes Foto bleibt ohne
    Kopfzeile und damit „noch nicht klassifiziert"."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    survivor = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
    )
    rejected = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 0, 5, tzinfo=UTC)
    )
    await _add_score(db_session, survivor)
    await _add_score(db_session, rejected, suggested_status=RatingStatus.REJECTED)
    for photo in (survivor, rejected):
        write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert await db_session.get(PhotoMotifAssessment, survivor.id) is not None
    assert await db_session.get(PhotoMotifAssessment, rejected.id) is None


# specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 6: `compute_content_criteria`
# unterscheidet ab hier zwei Faelle, die vorher beide `0.0` ergaben - NICHT MESSBAR (die Detektion
# lief, das Foto traegt das Merkmal nicht) und NICHT BERECHENBAR (Detektor fehlte, Ausnahme,
# Bild unlesbar). Nur der erste landet in `not_measurable`.
class BrokenFaceDetectorForContent:
    def detect(self, image: object) -> NoReturn:
        raise RuntimeError("simulierter Detektorfehler")


class BrokenLandmarkerForContent:
    def detect(self, image: object) -> NoReturn:
        raise RuntimeError("simulierter Landmarker-Fehler")


async def _criterion_row(
    session: AsyncSession, photo: Photo, criterion_key: str
) -> PhotoCriterionScore | None:
    return (
        await session.execute(
            select(PhotoCriterionScore).where(
                PhotoCriterionScore.photo_id == photo.id,
                PhotoCriterionScore.criterion_key == criterion_key,
            )
        )
    ).scalar_one_or_none()


async def _rankings_of(session: AsyncSession, run_id: int) -> list[PhotoRanking]:
    return list(
        (
            await session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run_id)
            )
        )
        .scalars()
        .all()
    )


class TestWhatIsNotMeasurable:
    def _content(
        self,
        cache_dir: Path,
        photo: Photo,
        *,
        face_detector: object | None,
        face_landmarker: object | None,
        animal_detector: object | None = None,
    ) -> worker_local.ContentCriteria:
        return worker_local.compute_content_criteria(
            cache_dir,
            photo,
            face_detector,  # type: ignore[arg-type]
            animal_detector if animal_detector is not None else NoAnimalDetector(),  # type: ignore[arg-type]
            NoSceneLabels(),  # type: ignore[arg-type]
            NeutralAestheticsModel(),  # type: ignore[arg-type]
            face_landmarker,  # type: ignore[arg-type]
        )

    async def test_a_ran_detection_without_the_feature_marks_both_criteria_not_measurable(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Detektion lief und fand nichts: `goldener_schnitt` ohne Subjekt und `freiraum` ohne
        Gesicht liefern KEINEN Wert statt `0.0` - ein Foto ohne Personen wird nicht mehr fuer
        das abgewertet, was ihm fehlt."""
        project = await _make_project(db_session)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        write_display_variant(tmp_path, photo, _flat_image())

        content = self._content(
            tmp_path,
            photo,
            face_detector=NoFaceDetector(),
            face_landmarker=NoFaceLandmarker(),
        )

        assert "goldener_schnitt" not in content.values
        assert "freiraum" not in content.values
        assert content.not_measurable == frozenset({"goldener_schnitt", "freiraum"})

    async def test_a_missing_detector_is_not_the_same_as_not_measurable(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """NICHT BERECHENBAR: der Detektor stand nicht zur Verfuegung. Das Kriterium bleibt
        ungeschrieben UND ausserhalb von `not_measurable` - ein Infrastrukturproblem darf keinen
        gueltigen Messwert eines frueheren Laufs vernichten."""
        project = await _make_project(db_session)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        write_display_variant(tmp_path, photo, _flat_image())

        content = self._content(tmp_path, photo, face_detector=None, face_landmarker=None)

        assert "goldener_schnitt" not in content.values
        assert "freiraum" not in content.values
        assert content.not_measurable == frozenset()

    async def test_a_throwing_detector_is_not_the_same_as_not_measurable(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _make_project(db_session)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        write_display_variant(tmp_path, photo, _flat_image())

        content = self._content(
            tmp_path,
            photo,
            face_detector=BrokenFaceDetectorForContent(),
            face_landmarker=BrokenLandmarkerForContent(),
        )

        assert content.not_measurable == frozenset()

    async def test_a_measured_feature_is_a_value_and_not_in_the_not_measurable_set(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _make_project(db_session)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        write_display_variant(tmp_path, photo, _flat_image())

        content = self._content(
            tmp_path,
            photo,
            face_detector=SingleFaceDetector(),
            face_landmarker=FaceLandmarkerStub(matrix=_rotation_matrix_y(30.0)),
        )

        assert "goldener_schnitt" in content.values
        assert "freiraum" in content.values
        assert content.not_measurable == frozenset()

    async def test_an_unreadable_cache_file_marks_nothing_not_measurable(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """DER gefaehrlichste Fall, und er traegt keinen Kriteriennamen: fehlt die
        `display`-Cache-Datei oder ist sie unlesbar, verlaesst die Funktion sich frueh. Waere
        `not_measurable` dort voreingestellt ("alles, was nicht in `values` steht"), loeschte der
        Lauf den GESAMTEN Kriteriensatz des Fotos - lautlos."""
        project = await _make_project(db_session)
        missing = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        broken = await _add_photo(
            db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, tzinfo=UTC)
        )
        broken_path = display_path(tmp_path, broken.id, broken.etag)
        broken_path.parent.mkdir(parents=True, exist_ok=True)
        broken_path.write_bytes(b"kein JPEG")

        for photo in (missing, broken):
            content = self._content(
                tmp_path,
                photo,
                face_detector=NoFaceDetector(),
                face_landmarker=NoFaceLandmarker(),
            )

            assert content.values == {}
            assert content.not_measurable == frozenset(), photo.relative_path


# specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 9: der Ranking-Teilschritt bildet
# den Qualitaetswert aus Modellstufe und lokaler Korrektur, schreibt `NULL` fuer ein Foto ohne
# Modellbewertung - und der Kriterien-Lauf LOESCHT eine Altzeile, die nicht mehr messbar ist.
async def _prepare_photo(
    session: AsyncSession, tmp_path: Path, *, image: Image.Image | None = None
) -> tuple[Project, ScoringRun, Photo]:
    project = await _make_project(session)
    scoring_run = await _add_successful_scoring_run(session, project)
    photo = await _add_photo(session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC))
    await _add_score(session, photo)
    write_display_variant(tmp_path, photo, image if image is not None else _flat_image())
    return project, scoring_run, photo


async def _add_stale_criterion(
    session: AsyncSession, photo: Photo, criterion_key: str
) -> PhotoCriterionScore:
    """Eine Altzeile aus einem frueheren Lauf - genau der Wert, den die abgeloeste
    `0.0`-Setzung hinterlassen hat."""
    row = PhotoCriterionScore(
        photo_id=photo.id,
        criterion_key=criterion_key,
        value=0.0,
        source=CriterionSource.LOCAL_HEURISTIC,
        computed_at=datetime(2020, 1, 1, tzinfo=UTC).replace(tzinfo=None),
    )
    session.add(row)
    await session.commit()
    return row


class TestTheStaleRowOfANoLongerMeasurableCriterion:
    """Der gefaehrlichste Umbau dieser Story: "nicht messbar" LOESCHT eine Altzeile, "nicht
    berechenbar" laesst sie unberuehrt. Beide Haelften stehen bewusst in EINEM Fall mit einer
    Assertion darauf, dass sich die beiden Datenbankzustaende UNTERSCHEIDEN muessen - getrennt
    geschrieben bestuenden sie auch ein `_delete_criterion`, das immer oder nie loescht, und genau
    das ist der naheliegende Fehler."""

    async def _run(
        self,
        session: AsyncSession,
        project: Project,
        scoring_run: ScoringRun,
        tmp_path: Path,
        *,
        detector: object,
        landmarker: object,
    ) -> None:
        await run_criterion_scoring(
            session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=lambda: detector,  # type: ignore[arg-type,return-value]
            build_animal_detector=_no_animal_detector,
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=lambda: landmarker,  # type: ignore[arg-type,return-value]
        )

    @pytest.mark.parametrize(
        ("criterion_key", "detector", "landmarker"),
        [
            ("goldener_schnitt", NoFaceDetector(), NoFaceLandmarker()),
            ("freiraum", NoFaceDetector(), NoFaceLandmarker()),
        ],
    )
    async def test_not_measurable_deletes_the_stale_row_while_not_computable_keeps_it(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        criterion_key: str,
        detector: object,
        landmarker: object,
    ) -> None:
        measurable_project, measurable_run, measured_photo = await _prepare_photo(
            db_session, tmp_path
        )
        await _add_stale_criterion(db_session, measured_photo, criterion_key)
        broken_project = await _make_project(db_session, name="Zweitprojekt")
        broken_run = await _add_successful_scoring_run(db_session, broken_project)
        broken_photo = await _add_photo(
            db_session, broken_project, "b.jpg", "etag-2", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, broken_photo)
        write_display_variant(tmp_path, broken_photo, _flat_image())
        stale_of_broken = await _add_stale_criterion(db_session, broken_photo, criterion_key)
        stale_value, stale_source, stale_time = (
            stale_of_broken.value,
            stale_of_broken.source,
            stale_of_broken.computed_at,
        )

        # (1) NICHT MESSBAR: die Detektion lief, das Merkmal fehlt.
        await self._run(
            db_session,
            measurable_project,
            measurable_run,
            tmp_path,
            detector=detector,
            landmarker=landmarker,
        )
        # (2) NICHT BERECHENBAR: der Detektor stand gar nicht zur Verfuegung.
        await self._run(
            db_session,
            broken_project,
            broken_run,
            tmp_path,
            detector=BrokenFaceDetectorForContent(),
            landmarker=BrokenLandmarkerForContent(),
        )

        deleted = await _criterion_row(db_session, measured_photo, criterion_key)
        kept = await _criterion_row(db_session, broken_photo, criterion_key)
        # DIE tragende Assertion: die beiden Zustaende muessen sich unterscheiden.
        assert (deleted is None) != (kept is None), criterion_key
        assert deleted is None, criterion_key
        assert kept is not None, criterion_key
        assert (kept.value, kept.source, kept.computed_at) == (
            stale_value,
            stale_source,
            stale_time,
        ), "Ein Infrastrukturproblem darf keinen gueltigen Messwert veraendern."

    async def test_a_measurable_feature_writes_a_value_and_deletes_nothing(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project, scoring_run, photo = await _prepare_photo(db_session, tmp_path)
        await _add_stale_criterion(db_session, photo, "goldener_schnitt")

        await self._run(
            db_session,
            project,
            scoring_run,
            tmp_path,
            detector=SingleFaceDetector(),
            landmarker=FaceLandmarkerStub(matrix=_rotation_matrix_y(30.0)),
        )

        for criterion_key in ("goldener_schnitt", "freiraum"):
            row = await _criterion_row(db_session, photo, criterion_key)
            assert row is not None, criterion_key

    async def test_two_consecutive_runs_leave_no_resurrected_row_behind(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """`_delete_criterion` raeumt die Zeile UND den In-Memory-Cache ab: ein spaeteres
        `_upsert_criterion` im selben Lauf darf kein verwaistes ORM-Objekt wiederbeleben, und der
        zweite Lauf darf die Zeile nicht aus dem Cache heraus neu anlegen."""
        project, scoring_run, photo = await _prepare_photo(db_session, tmp_path)
        await _add_stale_criterion(db_session, photo, "goldener_schnitt")
        await _add_stale_criterion(db_session, photo, "freiraum")

        for _ in range(2):
            await self._run(
                db_session,
                project,
                scoring_run,
                tmp_path,
                detector=NoFaceDetector(),
                landmarker=NoFaceLandmarker(),
            )

        assert await _criterion_row(db_session, photo, "goldener_schnitt") is None
        assert await _criterion_row(db_session, photo, "freiraum") is None
        # Der Lauf hat trotzdem gearbeitet - sonst bestuende dieser Fall auch ein No-op.
        assert await _criterion_row(db_session, photo, "sharpness") is not None


class TestTheQualityScoreOfTheRankingStep:
    async def _run(
        self, session: AsyncSession, project: Project, scoring_run: ScoringRun, tmp_path: Path
    ) -> CriterionScoringRun:
        return await run_criterion_scoring(
            session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
        )

    async def test_a_photo_with_a_model_level_gets_a_score_inside_its_level_band(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project, scoring_run, photo = await _prepare_photo(db_session, tmp_path)
        await _add_album_suitability(db_session, photo, level=4)

        run = await self._run(db_session, project, scoring_run, tmp_path)

        rankings = await _rankings_of(db_session, run.id)
        assert len(rankings) == 1
        score = rankings[0].rank_score
        assert score is not None
        assert abs(score - normalize_level(4)) <= LOCAL_CORRECTION_SPAN
        assert rankings[0].rank_position == 1

    async def test_a_photo_without_a_model_level_carries_null_but_keeps_its_event(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Kein stiller Rueckfall auf einen lokal gebildeten Wert - und trotzdem faellt das Foto
        nicht aus der Gliederung: es behaelt seine Event-Zugehoerigkeit und bleibt im einsehbaren
        Vorrat."""
        project, scoring_run, photo = await _prepare_photo(db_session, tmp_path)

        run = await self._run(db_session, project, scoring_run, tmp_path)

        rankings = await _rankings_of(db_session, run.id)
        assert [entry.photo_id for entry in rankings] == [photo.id]
        assert rankings[0].rank_score is None
        assert rankings[0].rank_position is None
        assert rankings[0].event_id is not None

    async def test_the_rank_positions_are_gapless_over_the_rated_subset(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die unbewerteten Fotos stehen mit `NULL` daneben und verschieben die Zaehlung der
        bewerteten nicht - sonst entstuende eine Rangfolge mit Luecken."""
        project = await _make_project(db_session)
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photos = []
        for index in range(4):
            photo = await _add_photo(
                db_session,
                project,
                f"{index}.jpg",
                f"etag-{index}",
                datetime(2023, 1, 1, 0, index, tzinfo=UTC),
            )
            await _add_score(db_session, photo)
            write_display_variant(tmp_path, photo, _flat_image())
            photos.append(photo)
        await _add_album_suitability(db_session, photos[0], level=5)
        await _add_album_suitability(db_session, photos[2], level=2)

        run = await self._run(db_session, project, scoring_run, tmp_path)

        rankings = await _rankings_of(db_session, run.id)
        rated = {
            entry.photo_id: entry.rank_position
            for entry in rankings
            if entry.rank_position is not None
        }
        unrated = [entry for entry in rankings if entry.rank_position is None]
        assert sorted(rated.values()) == [1, 2]
        assert rated[photos[0].id] == 1
        assert rated[photos[2].id] == 2
        assert {entry.photo_id for entry in unrated} == {photos[1].id, photos[3].id}
        assert all(entry.rank_score is None for entry in unrated)

    async def test_without_cloud_approval_nothing_is_rated_and_the_local_values_are_identical(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """ "Kein stiller Rueckfall": eine Assertion NUR auf `NULL` bestuende auch, wenn der lokale
        Pfad nebenbei etwas anderes gerechnet haette. Deshalb die Gleichheit der lokalen
        Kriterienwerte gegen denselben Bestand MIT Bewertung - und dazu, dass ohne Freigabe keine
        einzige Albumtauglichkeitszeile entsteht."""
        without = await _prepare_photo(db_session, tmp_path)
        assert without[0].cloud_vision_detection_enabled is False
        with_project = await _make_project(db_session, name="Mit Freigabe")
        with_project.cloud_vision_detection_enabled = True
        await db_session.commit()
        with_run = await _add_successful_scoring_run(db_session, with_project)
        with_photo = await _add_photo(
            db_session, with_project, "a.jpg", "etag-2", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, with_photo)
        write_display_variant(tmp_path, with_photo, _flat_image())
        await _add_album_suitability(db_session, with_photo, level=3)

        run_without = await self._run(db_session, without[0], without[1], tmp_path)
        await self._run(db_session, with_project, with_run, tmp_path)

        rankings_without = await _rankings_of(db_session, run_without.id)
        assert all(entry.rank_score is None for entry in rankings_without)
        assert all(entry.rank_position is None for entry in rankings_without)
        assert all(entry.event_id is not None for entry in rankings_without)
        assert (
            await db_session.execute(
                select(func.count())
                .select_from(PhotoAlbumSuitability.__table__)
                .where(PhotoAlbumSuitability.photo_id == without[2].id)
            )
        ).scalar_one() == 0
        assert await _criteria_of(db_session, without[2]) == await _criteria_of(
            db_session, with_photo
        )
