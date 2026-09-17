"""Der eine naive-UTC-Zeitpunkt des Projekts.

Jede Zeitspalte des Datenmodells ist naives UTC (`TIMESTAMP WITHOUT TIME ZONE` in sqlite wie in
Postgres). Gebraucht wird der Wert an zwei Stellen mit verschiedenen Zustaendigkeiten: der Worker
SCHREIBT ihn (`phase_started_at`), der Lesepfad der Projektantwort RECHNET gegen ihn (die
Restdauer des laufenden Teilschritts).

Genau eine Definition, weil zwei Uhren mit verschiedener Zeitzonenbehandlung eine Restdauer
ergaeben, die um den Zonenversatz danebenliegt - ohne Ausnahme, ohne Fehlermeldung und ohne roten
Test (ADR 0116, Konsequenzen).
"""

from __future__ import annotations

from datetime import UTC, datetime


def now_utc() -> datetime:
    """Jetzt, als naives UTC - also OHNE `tzinfo`, aber in UTC gerechnet.

    Nie `datetime.now()` ohne Zone: das liefert lokale Zeit ohne Kennzeichnung und ist von diesem
    Wert nicht zu unterscheiden."""
    return datetime.now(UTC).replace(tzinfo=None)
