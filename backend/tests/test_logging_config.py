from __future__ import annotations

import contextlib
import logging
import sys
from collections.abc import Iterator

import pytest

from photosort import main as main_module
from photosort.logging_config import configure_logging

_EXPECTED_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


@contextlib.contextmanager
def _reset_root_handlers() -> Iterator[None]:
    """`logging.basicConfig()` ist laut Python-Doku ein No-op, sobald der Root-Logger bereits
    mindestens einen Handler hat - pytest's eigenes `logging`-Plugin haengt fuer JEDE Testphase
    (setup/call/teardown) eigene Capture-Handler an den Root-Logger, unabhaengig davon, ob
    `caplog` im jeweiligen Test ueberhaupt benutzt wird (siehe specs/architecture/0002-
    testkonzept.md, Abschnitt zu ADR 0034). Verifizierte Testbarkeits-Falle: ein normaler
    PYTEST-FIXTURE-Reset (Code vor einem `yield` in einer Fixture) laeuft waehrend der "setup"-
    Phase - pytest haengt beim anschliessenden Eintritt in die "call"-Phase aber unabhaengig davon
    erneut zwei frische Handler an, sodass ein Fixture-Reset zum Zeitpunkt des eigentlichen
    Testkoerpers bereits wieder wirkungslos ist. Deshalb hier bewusst ein Context-Manager, der
    innerhalb des Testkoerpers selbst (also waehrend der "call"-Phase) aufgerufen wird, statt
    einer Fixture."""
    saved_handlers = list(logging.root.handlers)
    saved_level = logging.root.level
    logging.root.handlers = []
    try:
        yield
    finally:
        logging.root.handlers = saved_handlers
        logging.root.setLevel(saved_level)


def test_configure_logging_sets_warning_level_and_expected_format() -> None:
    with _reset_root_handlers():
        configure_logging()

        assert logging.root.level == logging.WARNING
        assert len(logging.root.handlers) == 1
        handler = logging.root.handlers[0]
        formatter = handler.formatter
        assert formatter is not None
        assert formatter._fmt == _EXPECTED_FORMAT
        # ADR 0034 Punkt 4 ("Format: einfacher Text ueber stdout, kein JSON") - ein
        # logging.StreamHandler() ohne expliziten stream=-Parameter nutzt sonst standardmaessig
        # sys.stderr statt sys.stdout (Copilot-Review-Fund, PR #247).
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stdout


def test_configure_logging_is_idempotent_no_duplicate_handler_on_second_call() -> None:
    with _reset_root_handlers():
        configure_logging()
        configure_logging()

        assert len(logging.root.handlers) == 1


def test_create_app_calls_configure_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[None] = []
    monkeypatch.setattr(main_module, "configure_logging", lambda: calls.append(None))

    main_module.create_app()

    assert calls == [None]
