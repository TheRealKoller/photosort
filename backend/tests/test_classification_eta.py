from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from photosort.classification_eta import (
    MIN_ELAPSED_SECONDS,
    MIN_PROCESSED_UNITS,
    remaining_seconds,
)

# specs/features/0481-restdauer-klassifizierungslauf.md, decisions/0116-restdauer-als-
# servermessung-spanne-im-frontend-keine-gesamtrestzeit.md Punkt 2 und 3: die REINE Rechnung -
# ohne Datenbank, ohne Uhr, `now` als Parameter.

_START = datetime(2026, 9, 17, 10, 0, 0)


def _at(seconds: float) -> datetime:
    return _START + timedelta(seconds=seconds)


@pytest.mark.parametrize(
    ("processed", "total", "elapsed", "expected"),
    [
        # Nachgerechnet, nicht aus dem Code abgelesen: 10 von 50 in 60 s -> 40 verbleibende bei
        # 6 s je Einheit -> 240 s.
        pytest.param(10, 50, 60.0, 240.0, id="zehn-von-fuenfzig-in-einer-minute"),
        # Die Haelfte ist geschafft: es bleibt genau die bisherige Dauer.
        pytest.param(25, 50, 100.0, 100.0, id="haelfte-geschafft"),
        # Die erste erlaubte Messung ueberhaupt - drei Einheiten, fuenfzehn Sekunden.
        pytest.param(3, 9, 15.0, 30.0, id="genau-an-beiden-schwellen"),
        # Alles verarbeitet: die Restdauer ist null, nicht "unbekannt".
        pytest.param(50, 50, 200.0, 0.0, id="vollstaendig-verarbeitet"),
    ],
)
def test_the_throughput_since_the_phase_start_gives_the_remaining_time(
    processed: int, total: int, elapsed: float, expected: float
) -> None:
    assert (
        remaining_seconds(
            phase_started_at=_START, now=_at(elapsed), processed=processed, total=total
        )
        == expected
    )


@pytest.mark.parametrize(
    "total",
    [pytest.param(0, id="nenner-null"), pytest.param(None, id="nenner-unbekannt")],
)
def test_without_a_known_denominator_there_is_no_estimate(total: int | None) -> None:
    """Ohne bekannte Gesamtmenge gibt es nichts hochzurechnen. `0` und `None` fallen auf dasselbe
    Ergebnis, sind aber EINZELN geprueft: `None` heisst "nicht erfasst", `0` heisst "erfasst, es
    ist nichts zu tun" - eine truthy-Pruefung veraenderte die Aussage nicht, eine `is None`
    allein liesse die `0` in die Division laufen."""
    assert (
        remaining_seconds(phase_started_at=_START, now=_at(120.0), processed=5, total=total) is None
    )


@pytest.mark.parametrize(
    ("processed", "expected_none"),
    [
        pytest.param(0, True, id="null-verarbeitet"),
        pytest.param(1, True, id="eine-verarbeitet"),
        pytest.param(2, True, id="zwei-verarbeitet"),
        pytest.param(MIN_PROCESSED_UNITS, False, id="drei-verarbeitet-erster-erlaubter-wert"),
    ],
)
def test_the_processed_threshold_is_checked_inclusively(
    processed: int, expected_none: bool
) -> None:
    """Die Grenze EINSCHLIESSEND geprueft: `>` statt `>=` verschoebe die erste Messung um eine
    Einheit, und `processed = 0` liefe in eine Division durch null."""
    result = remaining_seconds(
        phase_started_at=_START, now=_at(120.0), processed=processed, total=50
    )

    assert (result is None) is expected_none


@pytest.mark.parametrize(
    ("elapsed", "expected_none"),
    [
        pytest.param(14.9, True, id="knapp-unter-der-zeitschwelle"),
        pytest.param(MIN_ELAPSED_SECONDS, False, id="genau-auf-der-zeitschwelle"),
    ],
)
def test_the_elapsed_threshold_is_checked_inclusively(elapsed: float, expected_none: bool) -> None:
    result = remaining_seconds(phase_started_at=_START, now=_at(elapsed), processed=5, total=50)

    assert (result is None) is expected_none


def test_a_missing_phase_start_yields_none_without_an_exception() -> None:
    """Der Altzeilen-Fall nach der Migration: `phase_started_at IS NULL` bei laufendem
    Teilschritt. Er ist ein REGULAERER Zweig, keine Ausnahme - eine geworfene Ausnahme naehme hier
    die gesamte Projektantwort mit (der Aufrufer ist der Lesepfad von `GET /projects`)."""
    assert remaining_seconds(phase_started_at=None, now=_at(600.0), processed=20, total=50) is None


def test_a_clock_step_backwards_yields_none_and_not_a_small_amount() -> None:
    """EIGENSTAENDIGER Fall, bewusst nicht mit der Zeitschwelle zusammengelegt: `now` vor dem
    Phasenbeginn heisst, dass die MESSGRUNDLAGE ungueltig ist - nicht, dass die Restdauer kurz
    ist. Eine spaetere Umstellung auf `abs()` waere hier sofort rot, waehrend sie mit einer
    blossen `elapsed < 15`-Pruefung unbemerkt durchginge."""
    assert (
        remaining_seconds(
            phase_started_at=_START, now=_START - timedelta(seconds=600), processed=20, total=50
        )
        is None
    )


def test_more_processed_than_total_yields_zero_and_not_none() -> None:
    """Festgelegt in der Spec: Ist die Arbeit faktisch fertig, ist die Restdauer `0.0`. "Wird noch
    ermittelt" waere hier die falschere Aussage - und ein negativer Betrag erst recht."""
    assert remaining_seconds(phase_started_at=_START, now=_at(200.0), processed=60, total=50) == 0.0


def test_an_unexpected_input_fails_loudly_instead_of_becoming_none() -> None:
    """DER Gegenfall zur Reihenfolge "Schwellenpruefung VOR der Division".

    Ohne ihn bliebe ein spaeteres `except Exception: return None` gruen - und genau das deckte
    jeden anderen Rechenfehler mit zu: Die Anzeige stuende dauerhaft auf "wird noch ermittelt",
    und die Ursache waere aus der Antwort nicht mehr zu erkennen. `None` darf ausschliesslich aus
    einer der benannten Bedingungen entstehen, nie aus einem verschluckten Fehler."""
    with pytest.raises(TypeError):
        remaining_seconds(
            phase_started_at=_START,
            now=_at(120.0),
            processed="20",  # type: ignore[arg-type]
            total=50,
        )


def test_an_unprocessed_counter_of_none_yields_none() -> None:
    """Die Landmark-Zaehler sind nullable: `NULL` heisst "Phase nicht betreten". Das ist eine
    fehlende Messgrundlage, kein Fehler - und ausdruecklich nicht `0`."""
    assert (
        remaining_seconds(phase_started_at=_START, now=_at(120.0), processed=None, total=50) is None
    )


def test_the_thresholds_are_named_constants_with_the_documented_values() -> None:
    """Die beiden Schwellen stehen in ADR 0116 Punkt 3 als Zahl. Der Test haelt sie fest, damit
    eine stillschweigende Verschiebung auffaellt - sie entscheidet, wie lange die Oberflaeche
    "wird noch ermittelt" zeigt."""
    assert MIN_PROCESSED_UNITS == 3
    assert MIN_ELAPSED_SECONDS == 15.0
