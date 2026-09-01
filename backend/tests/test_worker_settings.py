from __future__ import annotations

import pytest
from arq.cron import CronJob
from arq.worker import Function

from photosort import worker
from photosort.worker import (
    WorkerSettings,
    classify,
    reap_stalled_runs,
    scan_project,
    score_project,
)

# Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md, ADR 0019):
# job_timeout=86400 (24h) ist bewusst nur ein grosszuegiger Not-Anker (Schicht 2, der eigentliche
# 15-Minuten-Stillstands-Watchdog, greift fuer jeden echten Stillstand immer zuerst) - max_tries=1
# deaktiviert arqs automatischen Hintergrund-Retry vollstaendig, damit ein durch job_timeout
# abgebrochener Job keine zweite Run-Zeile erzeugt (verifiziert im arq-Quellcode, arq prueft
# job_try > max_tries VOR dem erneuten Coroutine-Aufruf, siehe ADR 0019).
_EXPECTED_TIMEOUT_S = 86400
_EXPECTED_MAX_TRIES = 1


def _registered_by_coroutine() -> dict[object, Function]:
    return {f.coroutine: f for f in WorkerSettings.functions if isinstance(f, Function)}


def test_scan_project_registered_with_generous_timeout_and_no_background_retry() -> None:
    by_coroutine = _registered_by_coroutine()

    assert by_coroutine[scan_project].timeout_s == _EXPECTED_TIMEOUT_S
    assert by_coroutine[scan_project].max_tries == _EXPECTED_MAX_TRIES


def test_score_project_registered_with_generous_timeout_and_no_background_retry() -> None:
    by_coroutine = _registered_by_coroutine()

    assert by_coroutine[score_project].timeout_s == _EXPECTED_TIMEOUT_S
    assert by_coroutine[score_project].max_tries == _EXPECTED_MAX_TRIES


def test_classify_registered_with_generous_timeout_and_no_background_retry() -> None:
    by_coroutine = _registered_by_coroutine()

    assert by_coroutine[classify].timeout_s == _EXPECTED_TIMEOUT_S
    assert by_coroutine[classify].max_tries == _EXPECTED_MAX_TRIES


def test_exactly_three_jobs_are_registered() -> None:
    """specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, AC "Ein Ausloeser":
    die frueheren Jobs `score_criteria` und `classify_categories_remote` sind durch den einen
    verketteten `classify`-Job ersetzt - es darf kein zweiter Weg zurueckbleiben, einen Teil der
    Klassifizierung anzustossen."""
    by_coroutine = _registered_by_coroutine()

    assert {f.__name__ for f in by_coroutine} == {"scan_project", "score_project", "classify"}


def test_reap_stalled_runs_registered_as_cron_job_every_five_minutes_at_startup() -> None:
    # Schicht 2 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
    # watchdog.md, ADR 0019): erste Nutzung von arqs Cron-Mechanismus im Projekt -
    # run_at_startup=True sorgt dafuer, dass ein Worker-Neustart sofort eine erste Pruefung
    # ausloest, statt bis zu 5 Minuten auf den naechsten regulaeren Tick zu warten.
    cron_jobs = list(WorkerSettings.cron_jobs)
    assert len(cron_jobs) == 1
    job = cron_jobs[0]
    assert isinstance(job, CronJob)
    assert job.coroutine == reap_stalled_runs
    assert job.run_at_startup is True
    assert job.minute == set(range(0, 60, 5))


async def test_on_startup_hook_configures_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    # specs/features/0056-structured-logging-cloud-vision-errors.md, ADR 0034 Punkt 2: einer der
    # beiden Prozess-Einstiegspunkte (Worker-Prozess) - derselbe Aufruf sitzt fuer den API-Prozess
    # in main.py::create_app(). arqs eigener on_startup-Vertrag verlangt eine Coroutine mit einem
    # ctx: dict-Positionalargument (verifiziert in arq.worker.Worker.main: `await self.on_startup
    # (self.ctx)`) - configure_logging() ist bewusst ein Null-Argument-Funktion (Spec-
    # Akzeptanzkriterium), deshalb ueber einen duennen Wrapper statt direkter Identitaet
    # verdrahtet; per Spy statt Identitaetsvergleich geprueft (Wiring-Nachweis analog der main.py-
    # Verdrahtung), da eine reine Identitaetspruefung die abweichende Signatur nicht abbilden
    # koennte.
    calls: list[None] = []
    monkeypatch.setattr(worker, "configure_logging", lambda: calls.append(None))

    assert WorkerSettings.on_startup is not None
    await WorkerSettings.on_startup({})  # type: ignore[arg-type]

    assert calls == [None]
