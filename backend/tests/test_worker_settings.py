from __future__ import annotations

from arq.worker import Function

from photosort.worker import WorkerSettings, scan_project, score_project, select_top_photos

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


def test_select_top_photos_registered_with_generous_timeout_and_no_background_retry() -> None:
    by_coroutine = _registered_by_coroutine()

    assert by_coroutine[select_top_photos].timeout_s == _EXPECTED_TIMEOUT_S
    assert by_coroutine[select_top_photos].max_tries == _EXPECTED_MAX_TRIES
