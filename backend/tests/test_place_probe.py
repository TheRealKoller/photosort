"""Tests fuer das rein lesende Messkommando (specs/features/0434-ortsnamen-fuer-events.md,
decisions/0102-ortsauskunft-je-zelle-projektgebunden-eventname-als-laufartefakt.md).

Aufbau nach architecture/0002-testkonzept.md, Sektion "Ein rein lesendes Kommando im
Produktivpaket": die Zaehlbloecke rein und ohne DB, die duenne Leseschicht gegen die
`db_session`-Fixture, `main()` synchron gegen eine dateibasierte SQLite in `tmp_path`.
"""

from __future__ import annotations

import socket

import pytest

from tests.conftest import NetworkAccessInTestError


class TestTheNetworkIsLockedForEveryTest:
    """Die Zusage "kein automatisierter Test erreicht je ein Netz" ist ab dieser Auslieferung eine
    SPERRE, keine Konvention mehr (autouse-Fixture in conftest.py). Ein Test, der einen echten
    Auflöser baut, wird dadurch laut rot, statt still online zu gehen."""

    def test_connecting_a_socket_raises(self) -> None:
        with pytest.raises(NetworkAccessInTestError):
            socket.socket().connect(("example.invalid", 80))

    def test_connect_ex_raises_too(self) -> None:
        # `connect_ex` meldet einen Fehler sonst als Rueckgabewert statt als Ausnahme - ohne
        # eigene Sperre ginge ein Verbindungsversuch darueber still hinaus.
        with pytest.raises(NetworkAccessInTestError):
            socket.socket().connect_ex(("example.invalid", 80))

    def test_create_connection_raises_too(self) -> None:
        # Der bequeme Weg der Standardbibliothek; er legt seinen Socket selbst an, und ein Patch
        # allein auf die Methode oben liefe bei einer kuenftigen Implementierung ins Leere.
        with pytest.raises(NetworkAccessInTestError):
            socket.create_connection(("example.invalid", 80))
