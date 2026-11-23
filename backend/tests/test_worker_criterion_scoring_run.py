"""Kriterien-Lauf: Waechter, bester Versuch der Inhaltskriterien, Motiv-Gruppierung, Zielgroesse und
Vorschlag.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import events, selection, worker
from photosort import events as events_module
from photosort.event_inputs import read_event_inputs
from photosort.landmark import (
    LandmarkDetection,
)
from photosort.models import (
    CategoryMethod,
    ClassificationMode,
    CriterionScoringRun,
    DuplicateDecision,
    Event,
    MotifAssessmentSource,
    Photo,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoRanking,
    PhotoScore,
    Project,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanStatus,
    ScoringRun,
)
from photosort.motif_strengths import load_effective_strengths, upsert_assessment
from photosort.motifs import MOTIF_REGISTRY
from photosort.worker import criterion_scoring as worker_criterion_scoring
from photosort.worker import rebuild_run_grouping, run_criterion_scoring
from tests.support import make_project as _make_project
from tests.support import write_display_variant
from tests.support.criterion_scoring import (
    RecordingLandmarkClient,
    _add_album_suitability,
    _add_photo,
    _add_score,
    _add_successful_scoring_run,
    _criteria_of,
    _flat_image,
    _landscape_scene_classifier,
    _no_aesthetics_model,
    _no_animal_detector,
    _no_face_detector,
    _no_face_landmarker,
    _no_scene_classifier,
)


async def test_guard_fails_run_when_scoring_run_id_does_not_exist(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Spec 0350/AK3: Beruf sich ein Kriterien-Lauf auf einen ScoringRun, den es NICHT gibt, legt
    # er gar nichts mehr an. Frueher entstand hier ein FAILED-Lauf als "sauberer Fehlschlag" - auf
    # der Zieldatenbank haette das INSERT keine Zeile gehabt, auf die sein Fremdschluessel zeigen
    # kann, und die Transaktion abgerissen (ADR 0122 Punkt 4). Die Ausnahme verlaesst die Funktion.
    project = await _make_project(db_session)

    with pytest.raises(worker.CriterionScoringReferenceError, match="999"):
        await run_criterion_scoring(
            db_session,
            project,
            scoring_run_id=999,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
        )

    # Die vier Zeilentypen, die AK3 namentlich als leer fordert: der Abbruch passiert VOR jeder
    # Zeile, statt wie frueher eine FAILED-Zeile zu hinterlassen.
    assert (
        await db_session.execute(select(func.count()).select_from(CriterionScoringRun))
    ).scalar_one() == 0
    assert (
        await db_session.execute(select(func.count()).select_from(RemoteCategoryClassificationRun))
    ).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(Event))).scalar_one() == 0
    assert (
        await db_session.execute(select(func.count()).select_from(PhotoRanking))
    ).scalar_one() == 0


async def test_guard_fails_run_when_scoring_run_id_is_stale(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # ADR 0021 Punkt 7 / Akzeptanzkriterium der Spec: ein Re-Scan/Re-Scoring waehrend der
    # Kuratierung erzeugt einen NEUEN erfolgreichen ScoringRun - ein Aufruf mit der ALTEN id wird
    # als stale abgelehnt, kein CriterionScoringRun-Erfolg auf veraltetem cluster_key-Stand.
    project = await _make_project(db_session)
    stale_run = await _add_successful_scoring_run(
        db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    )
    await _add_successful_scoring_run(
        db_session, project, started_at=datetime(2023, 1, 2, tzinfo=UTC).replace(tzinfo=None)
    )

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run_id=stale_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.FAILED


async def test_guard_fails_run_when_latest_scoring_run_is_not_successful(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    run_row = ScoringRun(project_id=project.id, status=ScanStatus.FAILED)
    db_session.add(run_row)
    await db_session.commit()
    await db_session.refresh(run_row)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run_id=run_row.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.FAILED


async def test_writes_sharpness_and_exposure_criteria_from_existing_photo_score(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.1)
    write_display_variant(tmp_path, photo, _flat_image())

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
    criteria = {
        c.criterion_key: c
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["sharpness"].value == 0.5  # 100.0 / 200.0 ceiling
    assert criteria["exposure"].value == 0.9  # 1.0 - 0.1
    assert criteria["content_landscape"].value > 0.9  # flat image
    assert criteria["content_people"].value == 0.0  # no face detector
    assert criteria["symmetrie"].value == 1.0  # flat image, keine Asymmetrie messbar


async def test_symmetrie_criterion_is_written_unconditionally_like_content_landscape(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md, ADR 0026: keine
    # Modell-/Detektor-Abhaengigkeit fuer symmetrie - wird wie content_landscape UNCONDITIONAL
    # berechnet, unabhaengig davon, ob irgendein Detektor/Modell erfolgreich gebaut wurde.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

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
    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["symmetrie"] == 1.0


async def test_horizont_criterion_is_written_unconditionally_like_content_landscape(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md, ADR 0026 Punkt 2:
    # klassischer cv2-Algorithmus ohne trainiertes Modell - keine Detektor-Abhaengigkeit, wird wie
    # content_landscape/symmetrie UNCONDITIONAL berechnet. Ein voellig flaechiges Testbild hat
    # keine Kanten/Linien -> neutraler Fallback-Wert 0.5 (kein Kandidat gefunden).
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

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
    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["horizont"] == 0.5


async def test_upserts_existing_criterion_score_instead_of_duplicating(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

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
    # Zweiter Lauf mit geaenderten Rohwerten - der bestehende Wert wird ueberschrieben (Upsert),
    # keine zweite Zeile (UniqueConstraint(photo_id, criterion_key)).
    photo_score = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    photo_score.sharpness = 200.0
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

    rows = (
        (
            await db_session.execute(
                select(PhotoCriterionScore).where(
                    PhotoCriterionScore.photo_id == photo.id,
                    PhotoCriterionScore.criterion_key == "sharpness",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].value == 1.0  # 200.0 / 200.0 ceiling, geklemmt


async def test_only_considers_ausschuss_survivors(db_session: AsyncSession, tmp_path: Path) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    rejected = await _add_photo(
        db_session, project, "rejected.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, rejected, cluster_key=None, suggested_status=RatingStatus.REJECTED)
    write_display_variant(tmp_path, rejected, _flat_image())

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
    assert run.photos_total == 0
    criteria = (
        (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == rejected.id)
            )
        )
        .scalars()
        .all()
    )
    assert criteria == []


async def test_a_keep_decision_pulls_a_duplicate_loser_back_into_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """specs/features/0374-duplikate-vergleichen.md, Auflage S1 an der ersten der vier
    cloud-bestimmenden Stellen: Die Fotoauswahl dieses Laufs speist zugleich den
    Sehenswuerdigkeits-Teilschritt. Ohne sie fehlte eine ausdruecklich behaltene Aufnahme in der
    Bewertung - und damit spaeter im Album."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    winner = await _add_photo(
        db_session, project, "gewinner.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, winner)
    write_display_variant(tmp_path, winner, _flat_image())
    behalten = await _add_photo(
        db_session, project, "behalten.jpg", "etag-2", datetime(2023, 1, 1, 0, 0, 1, tzinfo=UTC)
    )
    await _add_score(
        db_session,
        behalten,
        cluster_key=None,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
        duplicate_decision=DuplicateDecision.KEEP,
    )
    write_display_variant(tmp_path, behalten, _flat_image())

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
    assert run.photos_total == 2
    assert await _criteria_of(db_session, behalten) != {}


async def test_a_discard_decision_takes_a_survivor_out_of_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die zweite Richtung. Ohne sie bestuende der Fall darueber auch gegen ein Praedikat, das
    schlicht alles durchlaesst - und gerade diese Richtung ist die, die den abfliessenden Bestand
    verkleinert."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    verworfen = await _add_photo(
        db_session, project, "raus.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, verworfen, duplicate_decision=DuplicateDecision.DISCARD)
    write_display_variant(tmp_path, verworfen, _flat_image())

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
    assert run.photos_total == 0
    assert await _criteria_of(db_session, verworfen) == {}


async def test_best_effort_content_criteria_failure_does_not_fail_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    broken = await _add_photo(
        db_session, project, "broken.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, broken, sharpness=100.0, exposure=0.0)
    # broken.jpg hat KEINE lesbare display-Cache-Datei (fehlt) - Inhalts-Kriterien scheitern
    # best-effort, sharpness/exposure werden trotzdem geschrieben (kein erneuter Bildzugriff
    # noetig).

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
    criteria = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == broken.id)
            )
        ).scalars()
    }
    assert criteria == {"sharpness", "exposure"}


# specs/features/0289-feste-kategorien.md, ADR 0049 ab hier: die Kategorie eines Fotos ist eine
# reine PRO-FOTO-Funktion ueber einem geschlossenen Set. Die frueher hier getesteten
# haeufigkeitsabhaengigen Faelle (derive_active_categories-Ein-Aufruf-Spy, "identischer tier-Score
# landet je nach Lauf in einer anderen Kategorie") sind mit der abgeloesten Aggregation
# ersatzlos entfallen - ihr fachlicher Kern ("welches Foto bekommt welche Kategorie") wird jetzt
# durch die Vereinigungs-/Herkunftsneutralitaets-Tests weiter unten abgedeckt.

# Beliebige, von der Standard-Testbildgroesse (160) abweichende Bildgroesse - dient als
# deterministischer Marker fuer "dieses Foto soll ein Tier enthalten", unabhaengig von der
# (nicht garantierten) DB-Verarbeitungsreihenfolge - robuster als ein reiner Aufruf-Counter im
# Fake-Detektor, der implizit von der Zeilenreihenfolge abhinge.
_ANIMAL_MARKER_SIZE = 168


def _animal_marked_image() -> Image.Image:
    # Textur statt einer flachen Farbe (Abgrenzung zu _flat_image): ein Marker-Foto soll NICHT
    # gleichzeitig ein anderes Signal ausloesen.
    from PIL import ImageDraw

    image = Image.new("RGB", (_ANIMAL_MARKER_SIZE, _ANIMAL_MARKER_SIZE), color=(30, 60, 120))
    draw = ImageDraw.Draw(image)
    for offset in range(0, _ANIMAL_MARKER_SIZE, 8):
        draw.line(
            (offset, 0, _ANIMAL_MARKER_SIZE - offset, _ANIMAL_MARKER_SIZE),
            fill=(220, 180, 90),
            width=2,
        )
    return image


# --------------------------------------------------------------------------------------
# Die VERDRAHTUNG des Motivwechsels (Spec 0477). Die Regel selbst steht DB-frei in
# tests/test_events_motif_change.py; hier wird ausschliesslich geprueft, dass wirksame Staerken
# tatsaechlich an `build_events` ankommen - und dass sie die Gliederung seit ADR 0119 nicht mehr
# bewegen. Was der Kandidat aus der Datenbank traegt (fehlende Kopfzeile gegen leeres Motivbild,
# Dokument-Ausschluss, Handkorrektur), steht in tests/test_event_inputs.py: Seit dem Umzug nach
# `event_inputs.py` ist das die Aufrufstelle, und ueber die Gliederung ist es nicht mehr
# beobachtbar.
# --------------------------------------------------------------------------------------
_MOTIF_GROUPING_BASE = datetime(2026, 8, 12, 9, 0, 0)


def _confirming_window() -> int:
    """Die Fensterlaenge als MODULATTRIBUT - die Faelle bauen ihre Folgen daraus, nie aus dem
    Zahlwert."""
    return events.MOTIF_CHANGE_CONFIRMING_PHOTOS


def _motif_vector(*carried: str) -> dict[str, float]:
    """Ein VOLLSTAENDIGER Staerkevektor ueber alle acht Motive - genau die genannten liegen ueber
    der Praesenzgrenze. `_motif_vector()` ist damit die vorhandene Kopfzeile ohne ein einziges
    getragenes Motiv und etwas anderes als eine fehlende Kopfzeile."""
    return dict.fromkeys(MOTIF_REGISTRY, 0.0) | dict.fromkeys(carried, 1.0)


async def _motif_grouping_run(
    session: AsyncSession,
    *,
    vectors: Sequence[Mapping[str, float] | None],
    name: str,
) -> tuple[Project, CriterionScoringRun, list[Photo]]:
    """Ein bereits erfolgreicher Kriterien-Lauf samt Rangzeilen, bereit fuer
    `rebuild_run_grouping` - derselbe Weg zur Gliederung wie der Lauf selbst, aber ohne
    Bildverarbeitung.

    Die Fotos liegen eine Minute auseinander, ohne Ort und ohne Namen: kein anderes Trennsignal
    spricht mit, gleich wie lang die Folge wird. `vectors[i] is None` heisst "dieses Foto bekommt
    gar keine Motiv-Kopfzeile"."""
    project = await _make_project(session, name=name)
    scoring_run = await _add_successful_scoring_run(session, project)
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()
    placeholder = Event(
        criterion_scoring_run_id=run.id,
        position=1,
        started_at=_MOTIF_GROUPING_BASE,
        ended_at=_MOTIF_GROUPING_BASE,
    )
    session.add(placeholder)
    await session.flush()

    photos: list[Photo] = []
    for index, vector in enumerate(vectors):
        photo = await _add_photo(
            session,
            project,
            f"{name}-{index}.jpg",
            f"etag-{name}-{index}",
            _MOTIF_GROUPING_BASE + timedelta(minutes=index),
        )
        await _add_score(session, photo)
        session.add(
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo.id,
                event_id=placeholder.id,
                rank_score=0.5,
                rank_position=index + 1,
            )
        )
        if vector is not None:
            await upsert_assessment(
                session,
                photo.id,
                source=MotifAssessmentSource.CLOUD,
                strengths=dict(vector),
                excluded_document=False,
                provider="testanbieter",
                computed_at=_MOTIF_GROUPING_BASE,
            )
        photos.append(photo)
    await session.commit()
    return project, run, photos


async def _event_membership(session: AsyncSession, run_id: int) -> list[tuple[int, ...]]:
    """Die Fotos je Event eines Laufs, Events nach `position`, Fotos nach `photo_id`."""
    rows = (
        await session.execute(
            select(Event.position, PhotoRanking.photo_id)
            .join(PhotoRanking, PhotoRanking.event_id == Event.id)
            .where(Event.criterion_scoring_run_id == run_id)
            .order_by(Event.position, PhotoRanking.photo_id)
        )
    ).all()
    grouped: dict[int, list[int]] = {}
    for position, photo_id in rows:
        grouped.setdefault(position, []).append(photo_id)
    return [tuple(grouped[position]) for position in sorted(grouped)]


async def test_a_motif_change_no_longer_splits_the_grouping_of_a_run(
    db_session: AsyncSession,
) -> None:
    """Seit ADR 0119 bewegt der Motivwechsel keine Grenze mehr - auch nicht durch den
    Kriterien-Lauf hindurch. Ruinenbesuch, danach Mittagessen um die Ecke: Minutenabstand, kein
    Ort, derselbe Kalendertag - kein Signal trennt, und die Gliederung ist EIN Event.

    DER ROT-ANKER STEHT DAVOR, und er misst zugleich das Verdrahten: Die Kandidatenmenge, die der
    Lauf baut, traegt einen BESTAETIGTEN Wechsel. Ohne ihn bestuende der Fall auch dann, wenn die
    Motivstaerken den Durchlauf gar nicht erst erreichten.

    Der Zwilling ohne Motiv-Kopfzeilen steht daneben: Er gliedert identisch, und genau das ist die
    Zusage "die Gliederung haengt nicht mehr an der ersten Stufe" in ihrer Integrationsform."""
    window = _confirming_window()
    ruins = _motif_vector("bauwerk_sehenswuerdigkeit")
    lunch = _motif_vector("essen_trinken")
    with_motifs, run, photos = await _motif_grouping_run(
        db_session, vectors=[ruins, ruins] + [lunch] * window, name="mit-motiven"
    )
    without_motifs, plain_run, plain_photos = await _motif_grouping_run(
        db_session, vectors=[None] * (window + 2), name="ohne-motive"
    )

    inputs = await read_event_inputs(db_session, with_motifs.id, [photo.id for photo in photos])
    assert events_module.motif_change_starts(inputs.candidates) == frozenset({2}), (
        "sonst misst der Fall nichts"
    )

    await rebuild_run_grouping(db_session, with_motifs.id)
    await rebuild_run_grouping(db_session, without_motifs.id)
    await db_session.commit()

    assert await _event_membership(db_session, plain_run.id) == [
        tuple(photo.id for photo in plain_photos)
    ]
    assert await _event_membership(db_session, run.id) == [tuple(photo.id for photo in photos)]


class _AnimalOnlyInMarkedPhotos:
    """Faket den ObjectDetector so, dass NUR das Markerbild ein bildfuellendes Tier liefert.

    Bildfuellend, damit die Flaechengewichtung die Praesenzgrenze sicher erreicht; die Steuerung
    ueber die Bildgroesse statt ueber einen Aufrufzaehler haengt nicht an der
    Verarbeitungsreihenfolge der Zeilen."""

    def detect(self, image: object) -> object:
        if getattr(image, "width", None) != _ANIMAL_MARKER_SIZE:
            return SimpleNamespace(detections=[])
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(category_name="dog", score=0.9)],
                    bounding_box=SimpleNamespace(
                        origin_x=0,
                        origin_y=0,
                        width=_ANIMAL_MARKER_SIZE,
                        height=_ANIMAL_MARKER_SIZE,
                    ),
                )
            ]
        )


async def test_the_local_motif_basis_reaches_the_run_without_moving_a_boundary(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Eine Cloud-Klassifizierung wird NICHT vorausgesetzt: die Motivbilder dieses Laufs entstehen
    aus dem echten `local_motif_strengths` ueber die eingespielten Detektoren.

    Gemessen wird das VERDRAHTEN, nicht mehr eine Trennung: Die lokal gerechneten Staerken stehen
    an den Fotos, und die Gliederung bleibt trotzdem ein einziges Event (ADR 0119)."""
    window = _confirming_window()
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photos: list[Photo] = []
    for index in range(window + 2):
        photo = await _add_photo(
            db_session,
            project,
            f"lokal-{index}.jpg",
            f"etag-lokal-{index}",
            _MOTIF_GROUPING_BASE + timedelta(minutes=index),
        )
        await _add_score(db_session, photo)
        write_display_variant(
            tmp_path, photo, _flat_image() if index < 2 else _animal_marked_image()
        )
        photos.append(photo)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_AnimalOnlyInMarkedPhotos,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.SUCCESS
    strengths = await load_effective_strengths(db_session, [photo.id for photo in photos])
    assert [strengths[photo.id]["tiere"].strength for photo in photos] == [0.0, 0.0] + [1.0] * (
        window
    ), "ohne zwei verschiedene LOKALE Motivbilder prueft der Fall nichts"
    assert await _event_membership(db_session, run.id) == [tuple(photo.id for photo in photos)]


# specs/features/0567-richtwert-vor-klassifizierung.md: der Richtwert vor dem ersten Lauf, sein
# Fortbestand ueber weitere Laeufe und das Ende der Uebergangszeit nach ADR 0131.
_TARGET_LAY_PHOTOS = 6


async def _target_lay(
    session: AsyncSession, cache_dir: Path, *, target: int | None
) -> tuple[Project, ScoringRun]:
    """Sechs bewertete Fotos im Minutenabstand - EIN Event, also bestimmt allein der Richtwert die
    Vorschlagsgroesse, bis die Kandidaten ausgehen."""
    project = await _make_project(session)
    project.selection_target = target
    await session.commit()
    scoring_run = await _add_successful_scoring_run(session, project)
    for index in range(_TARGET_LAY_PHOTOS):
        photo = await _add_photo(
            session,
            project,
            f"{index}.jpg",
            f"etag-{index}",
            datetime(2023, 1, 1, 10, index, tzinfo=UTC),
        )
        await _add_score(session, photo, sharpness=float(50 + index * 10))
        write_display_variant(cache_dir, photo, _flat_image())
        await _add_album_suitability(session, photo)
    return project, scoring_run


async def _run_classification(
    session: AsyncSession, project: Project, scoring_run: ScoringRun, cache_dir: Path
) -> CriterionScoringRun:
    return await run_criterion_scoring(
        session,
        project,
        scoring_run.id,
        cache_dir=cache_dir,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )


async def _proposal_size(session: AsyncSession, run_id: int) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(PhotoRanking)
            .where(
                PhotoRanking.criterion_scoring_run_id == run_id,
                PhotoRanking.selection_position.is_not(None),
            )
        )
    ).scalar_one()


async def test_a_target_set_before_the_first_run_sizes_its_proposal(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """T != Vorbelegung und T > Eventzahl - sonst waere der Fall von der Vorbelegung bzw. von der
    Mindestabdeckung nicht zu unterscheiden."""
    target = 4
    project, scoring_run = await _target_lay(db_session, tmp_path, target=target)

    run = await _run_classification(db_session, project, scoring_run, tmp_path)

    assert run.status == ScanStatus.SUCCESS
    events_in_run = len(await _event_membership(db_session, run.id))
    assert events_in_run < target < _TARGET_LAY_PHOTOS
    assert target != selection.DEFAULT_TARGET
    assert await _proposal_size(db_session, run.id) == target


async def test_a_further_run_keeps_the_target_and_after_a_reset_uses_the_default(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    target = 4
    project, scoring_run = await _target_lay(db_session, tmp_path, target=target)
    await _run_classification(db_session, project, scoring_run, tmp_path)

    second = await _run_classification(db_session, project, scoring_run, tmp_path)
    assert await _proposal_size(db_session, second.id) == target

    project.selection_target = None
    await db_session.commit()
    third = await _run_classification(db_session, project, scoring_run, tmp_path)

    # Die Vorbelegung liegt ueber dem Bestand: der Vorschlag nimmt alle Kandidaten.
    assert _TARGET_LAY_PHOTOS < selection.DEFAULT_TARGET
    assert await _proposal_size(db_session, third.id) == _TARGET_LAY_PHOTOS


async def _seed_old_default_proposal(session: AsyncSession, run_id: int, size: int) -> None:
    """Der Bestandsvorschlag eines Laufs aus der Zeit der alten Vorbelegung: direkt geseedet."""
    await session.execute(
        update(PhotoRanking)
        .where(PhotoRanking.criterion_scoring_run_id == run_id)
        .values(selection_position=None)
    )
    photo_ids = (
        (
            await session.execute(
                select(PhotoRanking.photo_id)
                .where(PhotoRanking.criterion_scoring_run_id == run_id)
                .order_by(PhotoRanking.photo_id)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    await session.execute(
        update(PhotoRanking)
        .where(
            PhotoRanking.criterion_scoring_run_id == run_id,
            PhotoRanking.photo_id.in_(photo_ids),
        )
        .values(selection_position=1)
    )
    await session.commit()


async def _positions_of(session: AsyncSession, run_id: int) -> dict[int, int | None]:
    rows = await session.execute(
        select(PhotoRanking.photo_id, PhotoRanking.selection_position).where(
            PhotoRanking.criterion_scoring_run_id == run_id
        )
    )
    return {photo_id: position for photo_id, position in rows.all()}


async def test_a_failed_run_leaves_the_old_default_proposal_untouched(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ende der Uebergangszeit, Fall (a): ein gescheiterter Lauf ist kein Ausloeser. Er scheitert
    hier in seiner letzten Phase - nach den eigenen Rangzeilen, vor dem Auswahlvorschlag."""

    async def failing_phase(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Phase gescheitert")

    project, scoring_run = await _target_lay(db_session, tmp_path, target=None)
    first = await _run_classification(db_session, project, scoring_run, tmp_path)
    first_id, project_id = first.id, project.id
    await _seed_old_default_proposal(db_session, first_id, 1)
    before = await _positions_of(db_session, first_id)
    monkeypatch.setattr(worker_criterion_scoring, "recognize_persons", failing_phase)

    await _run_classification(db_session, project, scoring_run, tmp_path)

    latest = (
        await db_session.execute(
            select(CriterionScoringRun)
            .where(CriterionScoringRun.project_id == project_id)
            .order_by(CriterionScoringRun.id.desc())
            .limit(1)
        )
    ).scalar_one()
    assert latest.status == ScanStatus.FAILED
    assert await _positions_of(db_session, first_id) == before


async def test_a_successful_run_ends_the_transition_with_the_default(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Ende der Uebergangszeit, Fall (b): der naechste erfolgreiche Lauf rechnet nach 150."""
    project, scoring_run = await _target_lay(db_session, tmp_path, target=None)
    first = await _run_classification(db_session, project, scoring_run, tmp_path)
    await _seed_old_default_proposal(db_session, first.id, 1)

    second = await _run_classification(db_session, project, scoring_run, tmp_path)

    assert await _proposal_size(db_session, second.id) == min(
        selection.DEFAULT_TARGET, _TARGET_LAY_PHOTOS
    )


async def test_the_landmark_phase_uses_the_project_model_not_the_installation_default(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0143 Punkt 2: die Landmark-Phase bekommt das aufgeloeste Modell des Projekts und leitet
    daraus Anbieter, Client, Preis und die `provider`-Spalte ab - die Installationsvorgabe gilt
    nur noch fuer Projekte ohne eigene Wahl. Ein zweiter Anbieter in derselben Installation
    belegt, dass der Wert wirklich durchgereicht wird und nicht aus `settings` kommt."""
    from photosort.cloud_vision import ANTHROPIC_VISION_MODEL

    monkeypatch.setattr(worker.settings, "landmark_provider", "mistral")
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    client = RecordingLandmarkClient(detection=LandmarkDetection(name="Eiffelturm", confidence=0.9))
    built_models: list[str] = []

    def recording_builder(model: str) -> RecordingLandmarkClient:
        built_models.append(model)
        return client

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
        build_landmark_client=recording_builder,
        use_cloud=True,
        landmark_model=ANTHROPIC_VISION_MODEL,
    )

    assert run.status == ScanStatus.SUCCESS
    assert built_models == [ANTHROPIC_VISION_MODEL]
    assert run.landmark_model == ANTHROPIC_VISION_MODEL
    detection_row = (
        await db_session.execute(
            select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
        )
    ).scalar_one()
    assert detection_row.provider == "anthropic"


async def test_without_a_landmark_model_argument_the_phase_resolves_the_installation_default(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Ein Job aus der Zeit vor dem Update traegt das Keyword nicht - dann gilt unveraendert die
    Installationsvorgabe, kein Fehlschlag."""
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    client = RecordingLandmarkClient(detection=LandmarkDetection(name="Eiffelturm", confidence=0.9))
    built_models: list[str] = []

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
        build_landmark_client=lambda model: (built_models.append(model), client)[1],
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert built_models == [worker.settings.resolved_landmark_model()]
    assert run.landmark_model == worker.settings.resolved_landmark_model()


@pytest.mark.parametrize("category_method", list(CategoryMethod))
@pytest.mark.parametrize("mode", [None, *ClassificationMode])
async def test_the_run_freezes_the_project_category_method_as_its_album_level_source(
    db_session: AsyncSession,
    mode: ClassificationMode | None,
    category_method: CategoryMethod,
) -> None:
    """ADR 0144 Punkt 1: die Quelle der zaehlenden Stufe folgt der Projekteinstellung beim
    Laufstart - fuer JEDEN Weg, auch `local`, weil auch ein lokaler Lauf Rangwerte bildet."""
    project = await _make_project(db_session)
    project.category_method = category_method
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)

    run = await worker_criterion_scoring.start_criterion_scoring_run(
        db_session, project, scoring_run.id, cloud_requested=False, mode=mode
    )

    assert run.album_level_source is category_method
