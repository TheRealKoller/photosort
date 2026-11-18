"""Der Fortschritts-Watchdog (Schicht 2) samt Schwellen und Stall-Praedikaten."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import photosort.worker._runs as runs
from photosort.db import async_session_factory
from photosort.models import (
    ClassificationReview,
    CriterionScoringRun,
    ExportRun,
    ExportRunStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
)

# Fortschritts-Watchdog: grosszuegiger Not-Anker (24h), NICHT der primaere Terminierungsmechanismus
# - Schicht 2 (STALL_THRESHOLD, siehe reap_stalled_runs) greift fuer jeden echten Stillstand immer
# zuerst. Begrenzt nur den Ressourcenverbrauch eines Defekts in Schicht 2 selbst. Der arq-Default
# von 300s (5 Minuten) ist hier untauglich - er ist deutlich zu kurz fuer legitim lange Scans
# grosser Fotobibliotheken (bindende Stakeholder-Anforderung).
JOB_TIMEOUT_SECONDS = 86400


# Schicht 2 des Fortschritts-Watchdogs: der eigentliche, fortschrittsbasierte
# Stillstands-Schwellwert - ein RUNNING-Lauf, dessen last_progress_at strikt aelter als dieser Wert
# ist, gilt als haengend, unabhaengig von seiner Gesamtlaufzeit (bindende Stakeholder-Anforderung:
# "nur ein echter Stillstand ist ein Fehler, keine feste Obergrenze").
STALL_THRESHOLD = timedelta(minutes=15)


# Wartende Laeufe haben keinen Fortschritt, an dem man sie messen koennte: ihre `last_progress_at`
# steht auf dem Anlegezeitpunkt. Sie gelten deshalb erst nach der Job-Obergrenze als haengend -
# ein Job, der so lange nicht begonnen hat, kommt nicht mehr.
QUEUED_STALL_THRESHOLD = timedelta(seconds=JOB_TIMEOUT_SECONDS)


def _stalled_run_filter(
    status_column: Any,
    progress_column: Any,
    running_status: Any,
    queued_status: Any,
    *,
    running_threshold: datetime,
    queued_threshold: datetime,
) -> Any:
    """Eine Zeile gilt als haengend, wenn ein laufender Lauf den Fortschritts-Schwellwert reisst
    oder ein wartender den Warte-Schwellwert. Beide Bedingungen stehen in EINER Abfrage, damit
    die sechs Bloecke des Watchdogs gleich bleiben."""
    return or_(
        and_(status_column == running_status, progress_column < running_threshold),
        and_(status_column == queued_status, progress_column < queued_threshold),
    )


def _stall_message() -> str:
    # Die Minutenzahl wird aus STALL_THRESHOLD abgeleitet, NIE hart codiert - sonst veraltet die
    # Meldung beim naechsten Anpassen von STALL_THRESHOLD unbemerkt.
    minutes = int(STALL_THRESHOLD.total_seconds() // 60)
    return (
        f"Kein Fortschritt seit über {minutes} Minuten erkannt — "
        "vermutlich hängender Verarbeitungsschritt."
    )


async def _fail_if_stalled(
    session: AsyncSession,
    run: (
        ScanRun
        | ScoringRun
        | CriterionScoringRun
        | RemoteCategoryClassificationRun
        | ClassificationReview
    ),
) -> bool:
    """Setzt eine einzelne Zeile über fail_run auf FAILED, isoliert von den übrigen
    Zeilen/Tabellen: ein Fehler bei einer Zeile/Tabelle darf die Bereinigung der übrigen
    nicht blockieren - ein Fehlschlag hier (z.B. ein DB-Fehler beim
    Commit dieser einen Zeile) rollt nur die aktuelle, noch nicht committete Teiltransaktion
    zurueck, bereits zuvor erfolgreich committete Zeilen bleiben unberuehrt."""
    try:
        await runs.fail_run(session, run, _stall_message())
        return True
    except Exception:
        await session.rollback()
        return False


async def _fail_export_if_stalled(session: AsyncSession, run: ExportRun) -> bool:
    """Dasselbe wie `_fail_if_stalled`, aber fuer den eigenen Status-Enum des Exports."""
    try:
        await runs.fail_export_run(session, run, _stall_message())
        return True
    except Exception:
        await session.rollback()
        return False


async def reap_stalled_runs(
    ctx: dict[str, Any],
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> int:
    """Schicht 2 des Fortschritts-Watchdogs: periodischer arq-Cron-Job (alle 5 Minuten, siehe
    WorkerSettings.cron_jobs), unabhaengig von einer ggf. tatsaechlich noch haengenden Coroutine -
    deckt exakt den Fall ab, den reines Exception-Handling (Schicht 1, fail_run oben) strukturell
    nie schliessen kann (ein nie zurueckkehrender await liefert nie eine Exception, an die sich
    anknuepfen liesse). session_factory ist injizierbar (Default: die echte, produktive
    async_session_factory) - Tests uebergeben stattdessen eine an eine In-Memory-SQLite-
    Testdatenbank gebundene Factory, analog zu run_criterion_scoring's build_detector-Parameter.
    Jeder Block erfasst laufende Zeilen ueber STALL_THRESHOLD und wartende ueber
    QUEUED_STALL_THRESHOLD; ein gesetzter Abbruchwunsch gewinnt in beiden Faellen und endet
    `CANCELLED` (siehe fail_run).
    Die sechs Tabellen werden bewusst nacheinander in sechs eigenstaendigen Bloecken behandelt
    statt ueber eine generische Schleife (konsistent mit dem Rest dieser Datei: ScanRun/
    ScoringRun/CriterionScoringRun/RemoteCategoryClassificationRun/ClassificationReview/ExportRun
    bleiben sechs eigenstaendige Modelle ohne gemeinsame Basisklasse)."""
    reaped = 0
    threshold = runs.now_utc() - STALL_THRESHOLD
    queued_threshold = runs.now_utc() - QUEUED_STALL_THRESHOLD
    async with session_factory() as session:
        try:
            stalled_scan_runs = (
                (
                    await session.execute(
                        select(ScanRun).where(
                            _stalled_run_filter(
                                ScanRun.status,
                                ScanRun.last_progress_at,
                                ScanStatus.RUNNING,
                                ScanStatus.QUEUED,
                                running_threshold=threshold,
                                queued_threshold=queued_threshold,
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            # Ohne rollback() bliebe die Transaktion auf einer echten Postgres-Verbindung nach
            # einem fehlgeschlagenen SELECT im Zustand "current transaction is aborted" - die
            # nachfolgenden SELECTs fuer ScoringRun/CriterionScoringRun wuerden dann selbst
            # fehlschlagen, obwohl inhaltlich nichts mit ihnen falsch ist. Damit braeche die
            # Zusage "ein Fehler bei einer Tabelle blockiert die Bereinigung der uebrigen nicht"
            # in Produktion - im SQLite-Testsetup unsichtbar, da dort eine vor jedem DB-Zugriff
            # geworfene Python-Exception die DBAPI-Transaktion nie tatsaechlich invalidiert.
            await session.rollback()
            stalled_scan_runs = []
        for scan_run in stalled_scan_runs:
            if await _fail_if_stalled(session, scan_run):
                reaped += 1

        try:
            stalled_scoring_runs = (
                (
                    await session.execute(
                        select(ScoringRun).where(
                            _stalled_run_filter(
                                ScoringRun.status,
                                ScoringRun.last_progress_at,
                                ScanStatus.RUNNING,
                                ScanStatus.QUEUED,
                                running_threshold=threshold,
                                queued_threshold=queued_threshold,
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            await session.rollback()
            stalled_scoring_runs = []
        for scoring_run in stalled_scoring_runs:
            if await _fail_if_stalled(session, scoring_run):
                reaped += 1

        try:
            stalled_criterion_scoring_runs = (
                (
                    await session.execute(
                        select(CriterionScoringRun).where(
                            _stalled_run_filter(
                                CriterionScoringRun.status,
                                CriterionScoringRun.last_progress_at,
                                ScanStatus.RUNNING,
                                ScanStatus.QUEUED,
                                running_threshold=threshold,
                                queued_threshold=queued_threshold,
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            await session.rollback()
            stalled_criterion_scoring_runs = []
        for criterion_scoring_run in stalled_criterion_scoring_runs:
            if await _fail_if_stalled(session, criterion_scoring_run):
                reaped += 1

        try:
            stalled_remote_category_runs = (
                (
                    await session.execute(
                        select(RemoteCategoryClassificationRun).where(
                            _stalled_run_filter(
                                RemoteCategoryClassificationRun.status,
                                RemoteCategoryClassificationRun.last_progress_at,
                                ScanStatus.RUNNING,
                                ScanStatus.QUEUED,
                                running_threshold=threshold,
                                queued_threshold=queued_threshold,
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            await session.rollback()
            stalled_remote_category_runs = []
        for remote_category_run in stalled_remote_category_runs:
            if await _fail_if_stalled(session, remote_category_run):
                reaped += 1

        try:
            stalled_reviews = (
                (
                    await session.execute(
                        select(ClassificationReview).where(
                            _stalled_run_filter(
                                ClassificationReview.status,
                                ClassificationReview.last_progress_at,
                                ScanStatus.RUNNING,
                                ScanStatus.QUEUED,
                                running_threshold=threshold,
                                queued_threshold=queued_threshold,
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            await session.rollback()
            stalled_reviews = []
        for review in stalled_reviews:
            if await _fail_if_stalled(session, review):
                reaped += 1

        try:
            stalled_export_runs = (
                (
                    await session.execute(
                        select(ExportRun).where(
                            _stalled_run_filter(
                                ExportRun.status,
                                ExportRun.last_progress_at,
                                ExportRunStatus.RUNNING,
                                ExportRunStatus.QUEUED,
                                running_threshold=threshold,
                                queued_threshold=queued_threshold,
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            await session.rollback()
            stalled_export_runs = []
        for export_run in stalled_export_runs:
            if await _fail_export_if_stalled(session, export_run):
                reaped += 1

    return reaped
