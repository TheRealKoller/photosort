"""Die Personen-Phase: Erkennung auf der Display-Variante, eine Box je Person."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker._runs as runs
from photosort.face_analysis import (
    MODEL_KEY,
    FaceAnalyzerLike,
    FaceBox,
    is_valid_face_box,
    load_image,
)
from photosort.models import (
    ClassificationPhase,
    CriterionScoringRun,
    Photo,
    PhotoPersonDetection,
)
from photosort.person_matching import decide_assignments, similarities_to
from photosort.persons import current_centroids
from photosort.thumbnails import variant_path

# Analog, fuer CriterionScoringRun.persons_photos_processed: je Block werden die Erkennungen der
# verarbeiteten Fotos geschrieben und committet. Ein Block ist zugleich die Einheit, die ein
# Fremdschluesselfehler nach einer Personenloeschung verwirft.
PERSONS_COMMIT_BATCH_SIZE = 5


def _persons_on_photo(
    analyzer: FaceAnalyzerLike,
    cache_dir: Path,
    photo_id: int,
    etag: str,
    centroids: Mapping[int, Sequence[float]],
) -> dict[int, FaceBox] | None:
    """Die auf einem Foto sicher erkannten Personen, je mit der Box ihres EINEN Kandidatengesichts
    - oder `None`, wenn das Foto NICHT verarbeitet wurde (keine Display-Variante, Analyzer wirft).
    Merkmale und Aehnlichkeiten leben nur hier im Speicher; zurueck geht allein je Person eine
    Box. Fuer unbekannte Gesichter entsteht damit nichts.

    Eine Box, die `is_valid_face_box` nicht besteht, benennt die Person auf diesem Foto NICHT:
    Ein uebersehenes Foto ist zulaessig, eine Erkennung, deren Gesicht in "Ohne Namen" steht,
    nicht.

    LOG-HYGIENE (S11): Eine Ausnahme erscheint nur als Typname samt `photo_id` - nie ihr Text, der
    einen Wert tragen koennte."""
    image = load_image(variant_path(cache_dir, photo_id, etag, "display"))
    if image is None:
        return None
    try:
        faces = analyzer.detect(image)
        similarities = [similarities_to(analyzer.embed(image, face), centroids) for face in faces]
    except Exception as exc:
        runs.logger.warning(
            "Personen-Erkennung: Foto %s uebersprungen (%s).", photo_id, type(exc).__name__
        )
        return None
    return {
        person_id: faces[index].box
        for person_id, index in decide_assignments(similarities).items()
        if is_valid_face_box(faces[index].box)
    }


async def _recognize_persons(
    session: AsyncSession,
    run: CriterionScoringRun,
    project_id: int,
    cache_dir: Path,
    build_analyzer: Callable[[], FaceAnalyzerLike],
) -> None:
    """Die letzte Phase `persons`: ueber ALLE Fotos des Projekts (auch den Ausschuss), auf der
    Display-Variante, immer lokal - unabhaengig von `use_cloud` und Einwilligung.

    Sie laeuft NICHT, wenn keine Person eine gueltige Referenz des geladenen Modells hat oder der
    Adapter nicht baubar ist; dann bleiben die Zaehler `NULL` und die vorhandenen Erkennungen
    stehen. Die Schwerpunkte entstehen einmal zu Beginn frisch aus der Datenbank; gelesen werden
    nur Id und Merkmal, NIE der Name.

    Ersetzt werden die Erkennungen eines Fotos nur, wenn die Phase es tatsaechlich verarbeitet hat.
    Korrekturen fasst sie nie an. Wird waehrend des Laufs eine Person geloescht, scheitert das
    Schreiben eines Blocks am Fremdschluessel: verworfen wird nur dieser Block, alte Zeilen bleiben
    stehen, und der Lauf geht weiter."""
    centroids = await current_centroids(session, model_key=MODEL_KEY)
    if not centroids:
        runs.logger.info("Personen-Erkennung entfaellt: keine gezeigten Gesichter des Modells.")
        return
    analyzer = runs._try_build(build_analyzer)
    if analyzer is None:
        runs.logger.warning("Personen-Erkennung entfaellt: Modell nicht ladbar.")
        return

    photos = (
        await session.execute(
            select(Photo.id, Photo.etag).where(Photo.project_id == project_id).order_by(Photo.id)
        )
    ).all()
    runs._set_phase(run, ClassificationPhase.PERSONS)
    run.persons_photos_total = len(photos)
    run.persons_photos_processed = 0
    await session.commit()

    processed = 0
    discarded_blocks = 0
    for start in range(0, len(photos), PERSONS_COMMIT_BATCH_SIZE):
        block = photos[start : start + PERSONS_COMMIT_BATCH_SIZE]
        recognised = {
            photo_id: persons
            for photo_id, etag in block
            if (persons := _persons_on_photo(analyzer, cache_dir, photo_id, etag, centroids))
            is not None
        }
        now = runs._now_utc()
        if recognised:
            await session.execute(
                delete(PhotoPersonDetection).where(
                    PhotoPersonDetection.photo_id.in_(list(recognised))
                )
            )
            session.add_all(
                PhotoPersonDetection(
                    photo_id=photo_id,
                    person_id=person_id,
                    computed_at=now,
                    face_box_x=box.x,
                    face_box_y=box.y,
                    face_box_width=box.width,
                    face_box_height=box.height,
                )
                for photo_id, persons in recognised.items()
                for person_id, box in sorted(persons.items())
            )
        processed += len(block)
        run.persons_photos_processed = processed
        run.last_progress_at = now
        try:
            await session.commit()
        except IntegrityError:
            # Eine Person wurde inzwischen entfernt. Nur dieser Block faellt; das Rollback hat
            # jedes Objekt der Session expired, die Lauf-Zeile wird deshalb frisch gelesen.
            await session.rollback()
            await session.refresh(run)
            discarded_blocks += 1
            run.persons_photos_processed = processed
            run.last_progress_at = runs._now_utc()
            await session.commit()
    runs.logger.info(
        "Personen-Erkennung: %d von %d Fotos durchlaufen, %d Bloecke verworfen.",
        processed,
        len(photos),
        discarded_blocks,
    )
