"""Der Worker-Prozess: Einstiegspunkt, Job-Registrierung und die Namen, die von aussen adressiert
werden.

Das Paket ist die EINE Adresse fuer den Einstiegspunkt (`python -m arq photosort.worker.
WorkerSettings`, unveraendert): `WorkerSettings` steht hier, die fuenf Jobs, der eine Cron und der
Logging-Hook ebenfalls. Die Laeufe selbst liegen in je einer Datei, die gemeinsame Schicht in
`_runs`, die Kriterien-Phasen in `_criterion/`.

`__all__` ist die Zusage an die Aussenwelt: jeder Name, den `src/` und `tests/` ueber
`photosort.worker.<name>` erreichen, steht hier und ist aufloesbar
(`tests/test_worker_package_boundary.py` haelt beides fest). Die Namen der gemeinsamen Schicht sind
bewusst mit dabei - gelesen werden sie ueber das Paket, GEPATCHT wird dagegen immer an der Stelle,
an der sie nachgeschlagen werden (ADR 0149 Punkt 3).
"""

from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings
from arq.cron import cron
from arq.worker import func as arq_func

from photosort.classification_review import run_classification_review
from photosort.config import settings
from photosort.eye_client import EyeImageUnreadableError, EyeServiceUnavailableError
from photosort.logging_config import configure_logging
from photosort.worker._criterion.eye import _run_eye_phase
from photosort.worker._criterion.landmark import (
    _detect_landmark_for_photo,
    _landmark_place_cells,
    _landmark_place_hints,
    _select_landmark_candidates,
    _upsert_landmark_detection,
)
from photosort.worker._criterion.local import (
    _IMAGE_ANALYSIS_CRITERION_SOURCES,
    CRITERION_SCORING_COMMIT_BATCH_SIZE,
    _compute_content_criteria,
)
from photosort.worker._criterion.persons import _recognize_persons
from photosort.worker._criterion.ranking import (
    LandmarkGazetteerFactory,
    PlaceResolverFactory,
    _apply_run_selection,
    _build_grouping_and_rankings,
    _landmark_points_by_name,
    _place_infos,
)
from photosort.worker._runs import (
    _CLOUD_VISION_IMAGE_MIME_TYPE,
    _append_cloud_error,
    _clear_cloud_vision_error,
    _commit_phase_costs,
    _fail_export_run,
    _fail_run,
    _finish_cancelled,
    _finish_if_cancel_requested,
    _log_cloud_vision_failure,
    _log_cloud_vision_throttling,
    _now_utc,
    _raise_if_cancel_requested,
    _record_cloud_vision_error,
    _set_phase,
    _take_over_queued_run,
    _try_build,
    logger,
)
from photosort.worker.classification import classify, run_classification
from photosort.worker.criterion_scoring import (
    CriterionScoringReferenceError,
    _start_criterion_scoring_run,
    rebuild_run_grouping,
    rebuild_run_selection,
    run_criterion_scoring,
)
from photosort.worker.export import (
    build_export_folder_name,
    export_project,
    run_export,
    sanitize_project_name,
)
from photosort.worker.remote_categories import (
    run_remote_category_classification,
    select_remote_category_candidates,
)
from photosort.worker.scan import SkipReason, _classify_scan_entries, run_project_scan, scan_project
from photosort.worker.scoring import run_project_scoring, score_project
from photosort.worker.stall_reaper import (
    JOB_TIMEOUT_SECONDS,
    QUEUED_STALL_THRESHOLD,
    STALL_THRESHOLD,
    reap_stalled_runs,
)

__all__ = [
    "CRITERION_SCORING_COMMIT_BATCH_SIZE",
    "CriterionScoringReferenceError",
    "EyeImageUnreadableError",
    "EyeServiceUnavailableError",
    "JOB_TIMEOUT_SECONDS",
    "LandmarkGazetteerFactory",
    "PlaceResolverFactory",
    "QUEUED_STALL_THRESHOLD",
    "STALL_THRESHOLD",
    "SkipReason",
    "WorkerSettings",
    "_CLOUD_VISION_IMAGE_MIME_TYPE",
    "_IMAGE_ANALYSIS_CRITERION_SOURCES",
    "_append_cloud_error",
    "_apply_run_selection",
    "_build_grouping_and_rankings",
    "_classify_scan_entries",
    "_clear_cloud_vision_error",
    "_commit_phase_costs",
    "_compute_content_criteria",
    "_detect_landmark_for_photo",
    "_fail_export_run",
    "_fail_run",
    "_finish_cancelled",
    "_finish_if_cancel_requested",
    "_landmark_place_cells",
    "_landmark_place_hints",
    "_landmark_points_by_name",
    "_log_cloud_vision_failure",
    "_log_cloud_vision_throttling",
    "_now_utc",
    "_place_infos",
    "_raise_if_cancel_requested",
    "_recognize_persons",
    "_record_cloud_vision_error",
    "_run_eye_phase",
    "_select_landmark_candidates",
    "_set_phase",
    "_start_criterion_scoring_run",
    "_take_over_queued_run",
    "_try_build",
    "_upsert_landmark_detection",
    "build_export_folder_name",
    "classify",
    "export_project",
    "logger",
    "rebuild_run_grouping",
    "rebuild_run_selection",
    "reap_stalled_runs",
    "run_classification",
    "run_classification_review",
    "run_criterion_scoring",
    "run_export",
    "run_project_scan",
    "run_project_scoring",
    "run_remote_category_classification",
    "sanitize_project_name",
    "scan_project",
    "score_project",
    "select_remote_category_candidates",
    "settings",
]


async def _configure_worker_logging(ctx: dict[Any, Any]) -> None:
    """arq-`on_startup`-Hook - dünner Wrapper, NIE die direkte Zuweisung
    `on_startup = configure_logging`: arq ruft on_startup immer mit einem ctx-Positionalargument
    auf, waehrend `configure_logging()` eine Null-Argument-Funktion ist (identisch zum Aufruf in
    main.py::create_app()). Eine direkte Zuweisung braeche erst beim tatsaechlichen Worker-Start
    mit einem TypeError durch."""
    configure_logging()


class WorkerSettings:
    # arq.worker.func(...) statt nackter Funktionsreferenzen: max_tries=1 deaktiviert arqs
    # automatischen Hintergrund-Retry vollstaendig - ein durch job_timeout abgebrochener Job
    # erzeugt dadurch KEINE zweite Run-Zeile (arq prueft job_try > max_tries VOR dem erneuten
    # Coroutine-Aufruf). Damit gilt strukturell: ein Nutzer-Trigger -> genau ein Lauf -> ein
    # eindeutiger Endzustand, sichtbar ueber die "Erneut versuchen"-UI statt eines unsichtbaren
    # automatischen Wiederholungsversuchs.
    functions = (
        arq_func(scan_project, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
        arq_func(score_project, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
        # EIN verketteter Job (Remote-Kategorisierung -> Kriterien-Bewertung), nicht zwei
        # einzelne - die Reihenfolge steckt in run_classification, nicht in einer Bedienanweisung.
        arq_func(classify, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
        # Der Export: "ein Trigger -> genau ein Lauf" (ADR 0136 Punkt 5), wie die anderen Jobs.
        arq_func(export_project, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
        # Der Prueflauf (Spec 0616, ADR 0139 Punkt 2): eigener Lauf mit eigenen Tabellen. Auch er
        # kennt genau einen Versuch - ein Fehlschlag ist ein Endzustand mit fester Meldung, kein
        # automatischer Hintergrund-Retry.
        arq_func(run_classification_review, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
    )
    # Schicht 2 des Fortschritts-Watchdogs: run_at_startup=True sorgt dafuer, dass ein
    # Worker-Neustart sofort eine erste Pruefung ausloest, statt bis zu 5 Minuten auf den
    # naechsten regulaeren Tick zu warten - eine bereits vor dem Neustart haengende Zeile soll
    # nicht unnoetig lang unentdeckt bleiben.
    cron_jobs = (cron(reap_stalled_runs, minute=set(range(0, 60, 5)), run_at_startup=True),)
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # Einer der beiden Prozess-Einstiegspunkte (Worker-Prozess) - derselbe Aufruf sitzt fuer den
    # API-Prozess in main.py::create_app().
    on_startup = _configure_worker_logging
