"""Der Scoring-Lauf: Metriken je Foto, Duplikat-/Cluster-Bildung, automatische Entscheidung."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image
from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

import photosort.worker._runs as runs
from photosort.config import settings
from photosort.db import async_session_factory
from photosort.models import (
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)
from photosort.run_cancel import RunCancelled
from photosort.scoring import (
    SHARPNESS_REJECT_THRESHOLD,
    ClusterCandidate,
    PhotoFingerprint,
    assign_clusters,
    assign_duplicate_groups,
    compute_dhash,
    compute_exposure,
    compute_fine_dhash,
    compute_gray_grid,
    compute_sharpness,
    taken_at_is_trusted,
)
from photosort.thumbnails import variant_path

# Wie oft ScoringRun.photos_processed waehrend der Verarbeitung zwischen-committet wird ("mind. alle
# 25 Fotos", damit ein pollender Client echten, monoton wachsenden Fortschritt sieht statt nur
# Start-/Endzustand). Modul-Konstante statt Default-Parameterwert, damit Tests sie per
# monkeypatch.setattr(worker, "SCORE_COMMIT_BATCH_SIZE", ...) verkleinern koennen, ohne echte 25+
# Testfotos anlegen zu muessen.
SCORE_COMMIT_BATCH_SIZE = 25


@dataclass(frozen=True)
class PhotoMetrics:
    """Alle Metriken EINES dekodierten `display`-Bildes - ein Oeffnen, keine zweite Dekodierung.

    `phash` bleibt der hex-codierte grobe dHash fuer `PhotoScore.phash`; die feinen Signaturen
    und das Grauwertgitter leben nur im Scoring-Lauf und werden nie persistiert."""

    sharpness: float
    exposure: float
    phash: str
    fine_phash: int
    gray_grid: bytes


def _compute_photo_metrics(path: Path) -> PhotoMetrics | None:
    """Best-effort wie thumbnails.py::generate_variants: ein nicht (mehr) dekodierbares oder
    ungewoehnliches Bild darf den ScoringRun nicht abbrechen, sondern wird fuer die Metrik-
    Berechnung übersprungen. SICHERHEIT: das deckt insbesondere den
    `DecompressionBombError` ab."""
    try:
        with Image.open(path) as opened:
            opened.load()
            image: Image.Image = opened
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            return PhotoMetrics(
                sharpness=compute_sharpness(image),
                exposure=compute_exposure(image),
                phash=compute_dhash(image),
                fine_phash=compute_fine_dhash(image),
                gray_grid=compute_gray_grid(image),
            )
    except Exception:
        return None


async def _take_over_or_start_scoring_run(
    session: AsyncSession, project: Project, run_id: int | None
) -> ScoringRun | None:
    """Uebernimmt den von der API angelegten, wartenden Lauf oder legt einen neuen an - `None`,
    wenn der wartende in der Warteschlange abgebrochen wurde."""
    if run_id is not None:
        taken_over = await runs._take_over_queued_run(session, ScoringRun, run_id)
        if taken_over is None:
            return None
        scoring_run = taken_over
    else:
        scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.RUNNING)
        session.add(scoring_run)
    # Ein neuer Lauf beginnt ohne automatische Entscheidung (ADR 0146 Punkt 3): Der Merker ist eine
    # Aussage UEBER DIESEN Lauf, keine Historie. Der projektweite Reset laeuft in derselben Anweisung
    # wie die Projektbindung - ein Foto eines anderen Projekts bleibt unberuehrt. Er steht hinter der
    # Uebernahme: ein in der Warteschlange abgebrochener Lauf setzt nichts zurueck.
    await session.execute(
        update(PhotoScore)
        .where(PhotoScore.photo_id.in_(select(Photo.id).where(Photo.project_id == project.id)))
        .values(auto_decided=False)
    )
    await session.commit()
    await session.refresh(scoring_run)
    return scoring_run


async def _compute_scores(
    session: AsyncSession,
    scoring_run: ScoringRun,
    photos: Sequence[Photo],
    existing_scores: dict[int, PhotoScore],
    cache_dir: Path,
) -> dict[int, PhotoMetrics]:
    """Die Metriken ALLER Fotos aus je EINER Dekodierung, inklusive der feinen Signatur.

    Bekannte, akzeptierte Lücke: wird die display-Cache-Datei eines bereits in einem frueheren Lauf
    erfolgreich gescorten Fotos bis zu diesem Lauf unlesbar, bleibt dessen alte PhotoScore-Zeile
    unveraendert stehen statt geloescht/invalidiert zu werden - dieser Zweig wird dann einfach nicht
    betreten. In der Praxis unwahrscheinlich (persistentes Cache-Volume ohne Eviction), aber
    relevant fuer Phase B, die auf phash/cluster_key aufbaut."""
    now = datetime.now(UTC).replace(tzinfo=None)
    computed: dict[int, PhotoMetrics] = {}
    processed = 0
    for photo in photos:
        if processed % SCORE_COMMIT_BATCH_SIZE == 0:
            await runs._raise_if_cancel_requested(session, scoring_run)
        path = variant_path(cache_dir, photo.id, photo.etag, "display")
        metrics = _compute_photo_metrics(path) if path.is_file() else None
        if metrics is not None:
            computed[photo.id] = metrics
            score = existing_scores.get(photo.id)
            if score is None:
                score = PhotoScore(photo_id=photo.id)
                session.add(score)
                existing_scores[photo.id] = score
            # Vollstaendig ueberschreiben statt nur einzelner Felder: alte
            # duplicate_of/cluster_key/suggested_status-Werte aus einem frueheren Lauf duerfen
            # nicht stehen bleiben, bevor der neue Cluster-Pass sie ggf. neu setzt.
            score.sharpness = metrics.sharpness
            score.exposure = metrics.exposure
            score.phash = metrics.phash
            score.duplicate_of = None
            score.cluster_key = None
            score.suggested_status = None
            score.computed_at = now

        processed += 1
        if processed % SCORE_COMMIT_BATCH_SIZE == 0:
            scoring_run.photos_processed = processed
            # Fortschritts-Watchdog (Schicht 2) - analog run_project_scan.
            scoring_run.last_progress_at = runs._now_utc()
            await session.commit()

    scoring_run.photos_processed = processed
    await session.commit()
    return computed


def _fingerprints(
    photos: Sequence[Photo], computed: dict[int, PhotoMetrics]
) -> list[PhotoFingerprint]:
    """Die Eingabe der Duplikat-Erkennung - um `taken_at` und Vertrauenswuerdigkeit ergaenzt, ohne
    zusaetzlichen Query: die `photos` liegen an dieser Stelle bereits vollstaendig vor."""
    fingerprints: list[PhotoFingerprint] = []
    for photo in photos:
        metrics = computed.get(photo.id)
        if metrics is None:
            continue
        # Die Fensterpruefung liest `taken_at` (kamerakorrigiert), die Herkunft entscheidet nur, ob
        # eine Zeit als Messung gilt: exakte Gleichheit, keine Toleranz.
        trusted = taken_at_is_trusted(photo.taken_at_original, photo.last_modified)
        fingerprints.append(
            PhotoFingerprint(
                photo_id=photo.id,
                phash=int(metrics.phash, 16),
                fine_phash=metrics.fine_phash,
                gray_grid=metrics.gray_grid,
                sharpness=metrics.sharpness,
                taken_at=photo.taken_at if trusted else None,
                taken_at_trusted=trusted,
                pixel_count=photo.pixel_count,
            )
        )
    return fingerprints


async def _assign_duplicates_and_clusters(
    session: AsyncSession,
    photos: Sequence[Photo],
    computed: dict[int, PhotoMetrics],
    existing_scores: dict[int, PhotoScore],
) -> tuple[set[int], set[int]]:
    """Projektweite Duplikat-/Cluster-Erkennung und die daraus abgeleiteten Zeilen.

    Liefert `(rejected_ids, auto_candidate_losers)`: `rejected_ids` ist die
    Vorschlagsmenge (Duplikat-Verlierer plus Schaerfe-Ausschuss), `auto_candidate_losers` sind die
    Kandidaten der automatischen Entscheidung (ein Durchgang-1-Stern, dessen Gewinner die
    Schaerfeschwelle erreicht und dessen Aufloesung fuer JEDES Mitglied bekannt ist - unbekannt
    heisst unbekannt: keine Schaetzung, keine automatische Entscheidung)."""
    assignment = assign_duplicate_groups(_fingerprints(photos, computed))
    duplicate_of_map = assignment.duplicate_of

    rejected_ids = set(duplicate_of_map)
    for photo_id, metrics in computed.items():
        if metrics.sharpness < SHARPNESS_REJECT_THRESHOLD:
            rejected_ids.add(photo_id)

    # Um die Koordinate erweitert - KEIN zusaetzlicher Query, die `photos` liegen an dieser Stelle
    # bereits vollstaendig vor.
    cluster_input_by_id = {
        photo.id: (photo.taken_at, photo.gps_lat, photo.gps_lon) for photo in photos
    }
    remaining_ids = [photo_id for photo_id in computed if photo_id not in rejected_ids]
    cluster_map = assign_clusters(
        [
            ClusterCandidate(
                photo_id=photo_id,
                taken_at=cluster_input_by_id[photo_id][0],
                gps_lat=cluster_input_by_id[photo_id][1],
                gps_lon=cluster_input_by_id[photo_id][2],
            )
            for photo_id in remaining_ids
        ]
    )

    for photo_id in computed:
        score = existing_scores[photo_id]
        if photo_id in rejected_ids:
            score.suggested_status = RatingStatus.REJECTED
            score.duplicate_of = duplicate_of_map.get(photo_id)
        else:
            score.cluster_key = cluster_map[photo_id]

    photos_by_id = {photo.id: photo for photo in photos}
    auto_candidate_losers: set[int] = set()
    for winner_id in assignment.identical_winners:
        winner_metrics = computed.get(winner_id)
        if winner_metrics is None or winner_metrics.sharpness < SHARPNESS_REJECT_THRESHOLD:
            continue
        losers = {
            loser for loser, star_winner in duplicate_of_map.items() if star_winner == winner_id
        }
        members = {winner_id, *losers}
        if any(photos_by_id[member_id].pixel_count is None for member_id in members):
            continue
        auto_candidate_losers.update(losers)
    return rejected_ids, auto_candidate_losers


async def _mark_auto_decided(session: AsyncSession, auto_candidate_losers: set[int]) -> set[int]:
    """Setzt den Merker der automatischen Entscheidung und liefert die tatsaechlich gesetzten Ids.

    Der NOT-EXISTS steht in DERSELBEN Anweisung wie das Setzen (Auflage S4): Eine Nutzerentscheidung,
    die waehrend des Laufs entsteht, gewinnt gegen den Automaten. Geprueft wird der Gewinner UND
    jedes Mitglied des Sterns; die Mitglieder sind ueber den soeben gesetzten `duplicate_of`-Stern
    erreichbar, ohne eine zweite Liste."""
    if not auto_candidate_losers:
        return set()
    await session.flush()
    member_score = aliased(PhotoScore)
    await session.execute(
        update(PhotoScore)
        .where(PhotoScore.photo_id.in_(auto_candidate_losers))
        .where(
            ~exists(
                select(PhotoDuplicateDecision.photo_id).where(
                    (PhotoDuplicateDecision.photo_id == PhotoScore.duplicate_of)
                    | PhotoDuplicateDecision.photo_id.in_(
                        select(member_score.photo_id).where(
                            member_score.duplicate_of == PhotoScore.duplicate_of
                        )
                    )
                )
            )
        )
        .values(auto_decided=True)
    )
    return set(
        (
            await session.execute(
                select(PhotoScore.photo_id).where(
                    PhotoScore.photo_id.in_(auto_candidate_losers),
                    PhotoScore.auto_decided.is_(True),
                )
            )
        ).scalars()
    )


async def run_project_scoring(
    session: AsyncSession,
    project: Project,
    cache_dir: Path,
    *,
    run_id: int | None = None,
) -> ScoringRun | None:
    """Scort alle Fotos eines Projekts neu (kein inkrementelles Scoring) auf Basis der bereits vom
    Scan gecachten display-Variante - kein erneuter OpenCloud-Download.

    Ablauf: ScoringRun anlegen -> photos_total setzen -> pro Foto Heuristiken berechnen,
    PhotoScore upserten, photos_processed periodisch committen -> projektweite
    Duplikat-/Cluster-Erkennung -> suggested_status setzen -> ScoringRun auf success/failed
    setzen. Ranking-Grundlage ist die Kriterien-/Rangfolgen-Schicht (criteria.py/ranking.py).

    Mit `run_id` uebernimmt er den von der API angelegten, wartenden Lauf (None, wenn der in der
    Warteschlange abgebrochen wurde). Ein Abbruchwunsch wird vor jedem Commit-Batch und vor dem
    Clustering gelesen: die geschriebenen `PhotoScore`-Zeilen bleiben, Clustering, automatische
    Entscheidung, Vorschlagszahl und Gate entfallen - ein abgebrochener Lauf bestaetigt den
    Ausschuss nie.
    """
    scoring_run = await _take_over_or_start_scoring_run(session, project, run_id)
    if scoring_run is None:
        return None

    try:
        photos = (
            (await session.execute(select(Photo).where(Photo.project_id == project.id)))
            .scalars()
            .all()
        )
        scoring_run.photos_total = len(photos)
        scoring_run.photos_processed = 0
        await session.commit()

        existing_scores: dict[int, PhotoScore] = {}
        if photos:
            existing_scores = {
                score.photo_id: score
                for score in (
                    await session.execute(
                        select(PhotoScore).where(
                            PhotoScore.photo_id.in_([photo.id for photo in photos])
                        )
                    )
                ).scalars()
            }

        computed = await _compute_scores(session, scoring_run, photos, existing_scores, cache_dir)

        # Letzter Pruefpunkt vor dem Clustering: danach ist der Lauf in einem Zug fertig.
        await runs._raise_if_cancel_requested(session, scoring_run)
        rejected_ids, auto_candidate_losers = await _assign_duplicates_and_clusters(
            session, photos, computed, existing_scores
        )
        auto_decided_ids = await _mark_auto_decided(session, auto_candidate_losers)

        scoring_run.suggestions_found = len(rejected_ids)
        scoring_run.status = ScanStatus.SUCCESS
        scoring_run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        # Ausschuss-Gate-Autoset: kein OFFENER Ausschuss -> nichts zu sichten, das Gate blockiert
        # dann nicht mit einer leeren Liste. Automatisch entschiedene Gruppen sind keine offene
        # Sichtung; erst wenn jede uebrige Empfehlung automatisch entschieden ist, oeffnet sich das
        # Gate. Ein nachfolgender expliziter confirm-ausschuss-gate-Aufruf bleibt trotzdem
        # fehlerfrei moeglich (Idempotenz, siehe api/projects.py).
        if len(rejected_ids - auto_decided_ids) == 0:
            scoring_run.gate_confirmed_at = runs._now_utc()
        await session.commit()
        return scoring_run
    except RunCancelled:
        await runs._finish_cancelled(session, scoring_run)
        return scoring_run
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs - analog run_project_scan.
        await runs._fail_run(
            session, scoring_run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."
        )
        raise
    except Exception as exc:
        # Kein Rollback bereits committeter PhotoScore-Zeilen/des letzten committeten
        # photos_processed-Stands - session.rollback() verwirft nur die seit dem letzten commit()
        # offene, noch nicht persistierte Transaktion, exakt wie im OpenCloudError-Pfad von
        # run_project_scan.
        await runs._fail_run(session, scoring_run, str(exc))
        return scoring_run


async def score_project(
    ctx: dict[str, Any], project_id: int, run_id: int | None = None
) -> int | None:
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        scoring_run = await run_project_scoring(
            session, project, cache_dir=Path(settings.photo_cache_dir), run_id=run_id
        )
        return scoring_run.id if scoring_run is not None else None
