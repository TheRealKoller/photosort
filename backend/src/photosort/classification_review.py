"""Der Prueflauf zweier Klassifizierungsverfahren (Spec 0616, ADR 0139).

Der Job klassifiziert die eingefrorene Pruefmenge fuer BEIDE Seiten neu und schreibt
ausschliesslich in die sechs Prueftabellen. Geltende Motiv-Kopfzeilen, Kriterien,
Albumtauglichkeit, Rangfolge und die Kostenspalten der uebrigen Laeufe bleiben unberuehrt - die
Isolation ist die Zusage aus ADR 0139 Punkt 2 und wird von zwei Wachtern getragen (Syntaxbaum und
Bestandsvergleich).

Reihenfolge: erst die kostenfreien Seiten (Eye, dann lokal), danach die kostenpflichtige Cloud.
Faellt der Sidecar mitten im Lauf, ist noch nichts bezahlt.

Fehlerbild: Ein einzelnes Foto, das eine Seite nicht beurteilen kann, wird uebersprungen und
gezaehlt. Liefert eine Seite auf KEINEM Foto ein Ergebnis, endet die Pruefung `FAILED` statt mit
einer leeren Uebersicht. `error_message` traegt ausschliesslich einen festen deutschen Satz aus
`ERROR_MESSAGES` - nie `str(exc)` eines fremden Systems.

Zyklus: `worker.py` registriert diesen Job in `WorkerSettings.functions` und importiert das Modul
deshalb am Modulanfang. Der umgekehrte Import (zwei reine Helfer aus `worker.py`) steht deshalb
INNERHALB des Laufs, nicht am Modulanfang - sonst waere der Importring geschlossen.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.aesthetics import build_aesthetics_model
from photosort.classification import (
    build_face_detector,
    build_face_landmarker,
    build_object_detector,
    build_scene_classifier,
)
from photosort.classification_comparison import (
    PhotoComparison,
    compare_review,
)
from photosort.cloud_vision import TokenUsage
from photosort.config import settings
from photosort.duplicates import survives_ausschuss
from photosort.eye_client import (
    EyeClientLike,
    EyeImageUnreadableError,
    EyeServiceUnavailableError,
    build_eye_client,
)
from photosort.eye_mapping import MAPPING_VERSION, EyeMappingError
from photosort.eye_mapping import analyze as map_eye_analysis
from photosort.models import (
    ClassificationReview,
    ClassificationReviewCase,
    ClassificationReviewPurpose,
    ClassificationReviewResult,
    ClassificationReviewResultStrength,
    ClassificationReviewSide,
    ClassificationReviewSideKind,
    Photo,
    PhotoScore,
    Project,
    ReviewPhase,
    ScanStatus,
)
from photosort.motifs import local_motif_strengths
from photosort.pricing import compute_cost_usd
from photosort.remote_classification import (
    CategoryDetectionClientLike,
    RemoteClassification,
    build_category_classification_client,
)
from photosort.thumbnails import variant_path

# Der MIME-Typ des `display`-Bildes - dieselbe feste Angabe wie im uebrigen Cloud-Pfad.
_IMAGE_MIME_TYPE: Final = "image/jpeg"

# Fortschritts-Commit im sequenziellen Eye-/Lokal-Teil. Die Cloud-Seite committet je Block.
_PROGRESS_BATCH_SIZE: Final = 10

# Die geschlossene Menge der Meldungen. Nur diese Texte duerfen in `error_message` stehen.
ERROR_CANCELLED: Final = "Pruefung abgebrochen (Job-Timeout oder Worker-Shutdown)."
ERROR_EYE_UNAVAILABLE: Final = "Die Eye-Auswertung ist nicht erreichbar."
ERROR_NO_RESULTS: Final = "Eine Seite hat auf keinem Foto ein Ergebnis geliefert."
ERROR_NO_CONSENT: Final = "Die Cloud-Seite ist ohne Einwilligung im Projekt nicht ausfuehrbar."
ERROR_GENERIC: Final = "Die Pruefung konnte nicht abgeschlossen werden."

ERROR_MESSAGES: Final[frozenset[str]] = frozenset(
    {
        ERROR_CANCELLED,
        ERROR_EYE_UNAVAILABLE,
        ERROR_NO_RESULTS,
        ERROR_NO_CONSENT,
        ERROR_GENERIC,
    }
)


@dataclass(frozen=True)
class _SideStatements:
    """Die fertigen Aussagen einer Seite, gespeichert als Ergebnis- und Staerkezeilen."""

    strengths: Mapping[str, float]
    excluded_document: bool | None
    album_level: int | None


def _now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _set_side_phase(review: ClassificationReview, side: ClassificationReviewSide) -> None:
    review.phase = ReviewPhase.SIDE_A if side.side == "a" else ReviewPhase.SIDE_B


def _side_kind(side: ClassificationReviewSide) -> ClassificationReviewSideKind:
    return ClassificationReviewSideKind(side.kind)


async def _load_sides(
    session: AsyncSession, review: ClassificationReview
) -> dict[str, ClassificationReviewSide]:
    rows = (
        (
            await session.execute(
                select(ClassificationReviewSide).where(
                    ClassificationReviewSide.review_id == review.id
                )
            )
        )
        .scalars()
        .all()
    )
    sides = {row.side: row for row in rows}
    missing = {"a", "b"} - set(sides)
    if missing:
        raise ValueError(f"Pruefung {review.id} hat keine Seite(n) {sorted(missing)}")
    return sides


async def _load_photos(session: AsyncSession, project_id: int) -> list[Photo]:
    """Die eingefrorene Pruefmenge: alle Ausschuss-Ueberlebenden des Projekts, OHNE Skip-Kriterium
    und EINMAL geordnet. Aus dieser Reihenfolge entsteht `photo_position`."""
    return list(
        (
            await session.execute(
                select(Photo)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project_id, survives_ausschuss())
                .order_by(Photo.id)
            )
        )
        .scalars()
        .all()
    )


def _store_result(
    session: AsyncSession,
    *,
    review_id: int,
    side: str,
    photo_id: int,
    statements: _SideStatements,
    computed_at: datetime,
) -> None:
    session.add(
        ClassificationReviewResult(
            review_id=review_id,
            side=side,
            photo_id=photo_id,
            excluded_document=statements.excluded_document,
            album_level=statements.album_level,
            computed_at=computed_at,
        )
    )
    for motif_key, strength in statements.strengths.items():
        session.add(
            ClassificationReviewResultStrength(
                review_id=review_id,
                side=side,
                photo_id=photo_id,
                motif_key=motif_key,
                strength=float(strength),
            )
        )


async def _run_eye_sides(
    session: AsyncSession,
    review: ClassificationReview,
    photos: Sequence[Photo],
    sides: Sequence[ClassificationReviewSide],
    cache_dir: Path,
    *,
    build_client: Callable[[], EyeClientLike],
) -> set[int]:
    """Alle Eye-Seiten in EINEM Durchgang: ein Dienstaufruf je Foto, jede gewaehlte Fassung auf
    dieselbe Antwort im Speicher. Rueckgabe: die Fotos mit Ergebnis (auf jeder Eye-Seite gleich).
    """
    client = build_client()
    with_result: set[int] = set()
    try:
        if not await client.health():
            raise EyeServiceUnavailableError("Die Eye-Auswertung ist nicht gesund.")
        versions = [(side.side, side.eye_mapping_version or MAPPING_VERSION) for side in sides]
        review.photos_processed = 0
        await session.commit()
        for index, photo in enumerate(photos, start=1):
            path = variant_path(cache_dir, photo.id, photo.etag, "display")
            if not path.exists():
                continue
            try:
                payload = await client.analyze(path.read_bytes())
                analyses = {side: map_eye_analysis(payload, version) for side, version in versions}
            except (EyeImageUnreadableError, EyeMappingError):
                continue
            computed_at = _now_utc()
            for side_letter, analysis in analyses.items():
                side = next(row for row in sides if row.side == side_letter)
                _set_side_phase(review, side)
                _store_result(
                    session,
                    review_id=review.id,
                    side=side_letter,
                    photo_id=photo.id,
                    statements=_SideStatements(
                        strengths=analysis.motif_strengths,
                        excluded_document=analysis.excluded_document,
                        album_level=analysis.album_level,
                    ),
                    computed_at=computed_at,
                )
            with_result.add(photo.id)
            review.photos_processed = index
            if index % _PROGRESS_BATCH_SIZE == 0:
                review.last_progress_at = _now_utc()
                await session.commit()
        review.last_progress_at = _now_utc()
        await session.commit()
    finally:
        await client.aclose()
    return with_result


async def _run_local_sides(
    session: AsyncSession,
    review: ClassificationReview,
    photos: Sequence[Photo],
    sides: Sequence[ClassificationReviewSide],
    cache_dir: Path,
    *,
    compute_content_criteria: Callable[..., Any],
    try_build: Callable[[Callable[[], Any]], Any],
    build_detector: Callable[[], Any],
    build_animal_detector: Callable[[], Any],
    build_classifier: Callable[[], Any],
    build_aesthetics: Callable[[], Any],
    build_landmarker: Callable[[], Any],
) -> set[int]:
    """Die lokale Seite: `_compute_content_criteria` + `local_motif_strengths`, ohne
    Sehenswuerdigkeits-Beitrag und ohne eine Zeile in `photo_criterion_scores`.

    Die Detektoren werden EINMAL gebaut; ein einzelner Fehlschlag laesst nur die davon
    abhaengigen Kriterien fehlen (dieselbe Best-effort-Regel wie im Kriterienlauf). Ein Foto ohne
    `display`-Datei ergibt acht Nullen - das ist eine Beurteilung und kein fehlendes Ergebnis.
    """
    detector = try_build(build_detector)
    animal_detector = try_build(build_animal_detector)
    scene_classifier = try_build(build_classifier)
    aesthetics_model = try_build(build_aesthetics)
    face_landmarker = try_build(build_landmarker)
    review.photos_processed = 0
    await session.commit()
    with_result: set[int] = set()
    for index, photo in enumerate(photos, start=1):
        criteria = compute_content_criteria(
            cache_dir,
            photo,
            detector,
            animal_detector,
            scene_classifier,
            aesthetics_model,
            face_landmarker,
        )
        strengths = local_motif_strengths(criteria.values, criteria.area_fractions)
        computed_at = _now_utc()
        for side in sides:
            _set_side_phase(review, side)
            _store_result(
                session,
                review_id=review.id,
                side=side.side,
                photo_id=photo.id,
                statements=_SideStatements(
                    strengths=strengths, excluded_document=None, album_level=None
                ),
                computed_at=computed_at,
            )
        with_result.add(photo.id)
        review.photos_processed = index
        if index % _PROGRESS_BATCH_SIZE == 0:
            review.last_progress_at = _now_utc()
            await session.commit()
    review.last_progress_at = _now_utc()
    await session.commit()
    return with_result


async def _classify_for_review(
    client: CategoryDetectionClientLike, cache_dir: Path, photo: Photo
) -> RemoteClassification:
    """Der reine I/O-Teil einer Cloud-Seite - ohne Session, damit mehrere Aufrufe parallel per
    `asyncio.gather` laufen koennen. Nur die `display`-Variante, kein Pfad, kein Dateiname."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    return await client.classify(path.read_bytes(), _IMAGE_MIME_TYPE, photo.id)


async def _run_cloud_side(
    session: AsyncSession,
    review: ClassificationReview,
    project: Project,
    photos: Sequence[Photo],
    side: ClassificationReviewSide,
    cache_dir: Path,
    *,
    build_client: Callable[[str], CategoryDetectionClientLike],
) -> set[int]:
    """Die kostenpflichtige Seite. Der Client wird nur gebaut, wenn die Einwilligung des Projekts
    vorliegt - ein Fehlen ist ein fester Fehlersatz, kein stiller Rueckfall (ADR 0139 Punkt 5)."""
    if not project.cloud_vision_detection_enabled:
        raise _ReviewAbort(ERROR_NO_CONSENT)
    model = side.model
    if model is None:
        raise _ReviewAbort(ERROR_GENERIC)
    client = build_client(model)

    # VOR dem `try` gebunden: der `finally`-Block liest diese Namen auch dann, wenn die erste
    # Anweisung im `try` wirft.
    api_calls = 0
    failed_calls = 0
    input_tokens = 0
    output_tokens = 0
    with_result: set[int] = set()
    review.photos_processed = 0
    side.failed_calls = failed_calls
    await session.commit()
    try:
        concurrency = settings.remote_category_classification_concurrency
        processed = 0
        for start in range(0, len(photos), concurrency):
            block = photos[start : start + concurrency]
            results = await asyncio.gather(
                *[_classify_for_review(client, cache_dir, photo) for photo in block],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, asyncio.CancelledError):
                    raise result
            _set_side_phase(review, side)
            now = _now_utc()
            for photo, result in zip(block, results, strict=True):
                if isinstance(result, BaseException):
                    # Best-effort: kein Ergebnis, kein Fall, kein Fremdtext - nur gezaehlt.
                    failed_calls += 1
                    continue
                api_calls += 1
                if result.usage is not None:
                    input_tokens += result.usage.input_tokens
                    output_tokens += result.usage.output_tokens
                _store_result(
                    session,
                    review_id=review.id,
                    side=side.side,
                    photo_id=photo.id,
                    statements=_SideStatements(
                        strengths=result.motif_strengths,
                        excluded_document=result.excluded,
                        album_level=(
                            result.album_suitability.level
                            if result.album_suitability is not None
                            else None
                        ),
                    ),
                    computed_at=now,
                )
                with_result.add(photo.id)
            processed += len(block)
            review.photos_processed = processed
            side.failed_calls = failed_calls
            review.last_progress_at = _now_utc()
            await session.commit()
    finally:
        aclose = getattr(client, "aclose", None)
        if aclose is not None:
            await aclose()
        # Verbindlich im `finally`: nach begonnener Cloud-Nutzung ist das Geld ausgegeben, auch
        # wenn danach eine Exception nach oben laeuft. Der Betrag wird einmal eingefroren.
        side.api_calls = api_calls
        side.failed_calls = failed_calls
        side.input_tokens = input_tokens
        side.output_tokens = output_tokens
        side.cost_usd = compute_cost_usd(
            model, TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        )
        try:
            await session.commit()
        except Exception:
            await session.rollback()
    return with_result


class _ReviewAbort(RuntimeError):
    """Ein Abbruch mit einer Meldung aus der geschlossenen Menge."""

    def __init__(self, message: str) -> None:
        assert message in ERROR_MESSAGES
        super().__init__(message)


async def _load_statements(
    session: AsyncSession, review_id: int
) -> dict[str, dict[int, _SideStatements]]:
    results = (
        (
            await session.execute(
                select(ClassificationReviewResult).where(
                    ClassificationReviewResult.review_id == review_id
                )
            )
        )
        .scalars()
        .all()
    )
    strengths: dict[tuple[str, int], dict[str, float]] = {}
    for row in (
        (
            await session.execute(
                select(ClassificationReviewResultStrength).where(
                    ClassificationReviewResultStrength.review_id == review_id
                )
            )
        )
        .scalars()
        .all()
    ):
        strengths.setdefault((row.side, row.photo_id), {})[row.motif_key] = row.strength

    statements: dict[str, dict[int, _SideStatements]] = {}
    for result in results:
        statements.setdefault(result.side, {})[result.photo_id] = _SideStatements(
            strengths=strengths.get((result.side, result.photo_id), {}),
            excluded_document=result.excluded_document,
            album_level=result.album_level,
        )
    return {"a": statements.get("a", {}), "b": statements.get("b", {})}


def _purpose(value: str) -> ClassificationReviewPurpose:
    return ClassificationReviewPurpose(value)


async def _write_cases(
    session: AsyncSession,
    review: ClassificationReview,
    photos: Sequence[Photo],
    statements: Mapping[str, Mapping[int, _SideStatements]],
) -> None:
    position = {photo.id: index for index, photo in enumerate(photos, start=1)}
    comparisons = [
        PhotoComparison(
            photo_id=photo.id,
            a_motifs=statements["a"][photo.id].strengths if photo.id in statements["a"] else None,
            b_motifs=statements["b"][photo.id].strengths if photo.id in statements["b"] else None,
            a_excluded_document=(
                statements["a"][photo.id].excluded_document if photo.id in statements["a"] else None
            ),
            b_excluded_document=(
                statements["b"][photo.id].excluded_document if photo.id in statements["b"] else None
            ),
            a_album_level=(
                statements["a"][photo.id].album_level if photo.id in statements["a"] else None
            ),
            b_album_level=(
                statements["b"][photo.id].album_level if photo.id in statements["b"] else None
            ),
        )
        for photo in photos
    ]
    comparison = compare_review(comparisons, seed=review.seed, limit=review.sample_size)
    for case in comparison.cases:
        session.add(
            ClassificationReviewCase(
                review_id=review.id,
                photo_id=case.photo_id,
                photo_position=position[case.photo_id],
                purpose=_purpose(case.purpose),
                motif_key=case.motif_key,
            )
        )
    await session.commit()


def _free_and_paid_sides(
    sides: Mapping[str, ClassificationReviewSide],
) -> tuple[
    list[ClassificationReviewSide], list[ClassificationReviewSide], list[ClassificationReviewSide]
]:
    ordered = sorted(sides.values(), key=lambda row: row.side)
    eye = [row for row in ordered if _side_kind(row) == ClassificationReviewSideKind.EYE]
    local = [row for row in ordered if _side_kind(row) == ClassificationReviewSideKind.LOCAL]
    cloud = [row for row in ordered if _side_kind(row) == ClassificationReviewSideKind.CLOUD]
    return eye, local, cloud


async def execute_classification_review(
    session: AsyncSession,
    review: ClassificationReview,
    cache_dir: Path,
    *,
    project: Project | None = None,
    build_eye_client: Callable[[], EyeClientLike] = build_eye_client,
    build_cloud_client: Callable[
        [str], CategoryDetectionClientLike
    ] = build_category_classification_client,
    build_detector: Callable[[], Any] | None = None,
    build_animal_detector: Callable[[], Any] | None = None,
    build_classifier: Callable[[], Any] | None = None,
    build_aesthetics: Callable[[], Any] | None = None,
    build_landmarker: Callable[[], Any] | None = None,
) -> ClassificationReview:
    """Der pruefbare Kern des Jobs. `review` ist der bereits angelegte Lauf (`RUNNING`).

    Die Modell-Builder der lokalen Seite sind injizierbar; ohne Angabe kommen die echten Builder
    aus `worker.py` - in keinem automatisierten Test werden sie aufgerufen.
    """
    # Zyklus: worker.py importiert dieses Modul fuer `WorkerSettings.functions`. Der Gegenimport
    # steht deshalb hier drin - und NUR fuer diese zwei reinen Helfer.
    from photosort.worker import (  # noqa: PLC0415
        _compute_content_criteria,
        _try_build,
    )

    if project is None:
        loaded_project = await session.get(Project, review.project_id)
        if loaded_project is None:
            raise ValueError(f"Projekt {review.project_id} nicht gefunden")
        project = loaded_project

    sides = await _load_sides(session, review)
    eye_sides, local_sides, cloud_sides = _free_and_paid_sides(sides)
    photos = await _load_photos(session, project.id)
    review.photo_count = len(photos)
    review.photos_processed = 0
    review.error_message = None
    await session.commit()

    results_by_side: dict[str, set[int]] = {"a": set(), "b": set()}
    try:
        if eye_sides:
            eye_results = await _run_eye_sides(
                session, review, photos, eye_sides, cache_dir, build_client=build_eye_client
            )
            for side in eye_sides:
                results_by_side[side.side] = eye_results
        if local_sides:
            local_results = await _run_local_sides(
                session,
                review,
                photos,
                local_sides,
                cache_dir,
                compute_content_criteria=_compute_content_criteria,
                try_build=_try_build,
                build_detector=build_detector or build_face_detector,
                build_animal_detector=build_animal_detector or build_object_detector,
                build_classifier=build_classifier or build_scene_classifier,
                build_aesthetics=build_aesthetics or build_aesthetics_model,
                build_landmarker=build_landmarker or build_face_landmarker,
            )
            for side in local_sides:
                results_by_side[side.side] = local_results
        for side in cloud_sides:
            results_by_side[side.side] = await _run_cloud_side(
                session,
                review,
                project,
                photos,
                side,
                cache_dir,
                build_client=build_cloud_client,
            )

        if any(not ids for ids in results_by_side.values()):
            raise _ReviewAbort(ERROR_NO_RESULTS)

        review.phase = ReviewPhase.CASES
        review.last_progress_at = _now_utc()
        await session.commit()
        statements = await _load_statements(session, review.id)
        await _write_cases(session, review, photos, statements)

        complete = results_by_side["a"] & results_by_side["b"]
        review.unclassifiable_photo_count = len(photos) - len(complete)
        review.photos_processed = len(photos)
        review.status = ScanStatus.SUCCESS
        review.phase = None
        review.finished_at = _now_utc()
        review.last_progress_at = _now_utc()
        await session.commit()
        return review
    except asyncio.CancelledError:
        await _fail(session, review, ERROR_CANCELLED)
        raise
    except _ReviewAbort as abort:
        await _fail(session, review, str(abort))
        return review
    except EyeServiceUnavailableError:
        await _fail(session, review, ERROR_EYE_UNAVAILABLE)
        return review
    except Exception:
        await _fail(session, review, ERROR_GENERIC)
        return review


async def _fail(session: AsyncSession, review: ClassificationReview, message: str) -> None:
    """Setzt den Lauf auf `FAILED` mit einem Satz aus der geschlossenen Menge und raeumt den
    Teilschritt. Scheitert der Commit, bleibt die urspruengliche Ursache sichtbar (derselbe
    Grundsatz wie `worker.py::_commit_phase_costs`)."""
    assert message in ERROR_MESSAGES
    try:
        await session.rollback()
        review.status = ScanStatus.FAILED
        review.phase = None
        review.error_message = message
        review.finished_at = _now_utc()
        review.last_progress_at = _now_utc()
        await session.commit()
    except Exception:
        await session.rollback()


async def run_classification_review(ctx: dict[str, Any], review_id: int) -> int:
    """Der arq-Job. `max_tries=1`: eine Pruefung wird nie automatisch wiederholt (ADR 0139
    Punkt 6); ein Fehlschlag ist ein Endzustand mit fester Meldung."""
    from photosort.db import async_session_factory  # noqa: PLC0415

    async with async_session_factory() as session:
        review = await session.get(ClassificationReview, review_id)
        if review is None:
            raise ValueError(f"Pruefung {review_id} nicht gefunden")
        await execute_classification_review(session, review, Path(settings.photo_cache_dir))
        return review.id
