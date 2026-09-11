from __future__ import annotations

import logging
import sys

# Eigenes, sehr kleines Modul statt Anhaengsel an config.py (das nur die pydantic-Settings fuehrt,
# keine Prozess-Bootstrap-Logik) - konsistent mit dem im Projekt etablierten Prinzip, eine neue,
# isolierte Zustaendigkeit in ein eigenes kleines Modul zu legen (aesthetics.py, landmark.py,
# horizon.py).
#
# Aufgerufen an BEIDEN Prozess-Einstiegspunkten (main.py::create_app() fuer den API-Prozess,
# worker.py::WorkerSettings.on_startup fuer den Worker-Prozess) - beide Prozesse bekommen
# dieselbe Konfiguration, obwohl nur der Worker sie heute tatsaechlich braucht, damit ein
# kuenftiges Feature mit API-seitigem Logging-Bedarf nicht erneut eine Konfigurationsentscheidung
# treffen muss.


def configure_logging() -> None:
    """Konfiguriert das Root-Logging fuer den aktuellen Prozess: Level WARNING (der Skip eines
    einzelnen Fotos ist erwartetes best-effort-Verhalten, kein Lauf-Fehlschlag), einfaches
    Textformat mit Zeitstempel/Level/Modulname ueber stdout (kein JSON, `docker compose logs` ist
    der einzige Konsument).

    `logging.basicConfig()` ist ein No-op, sobald der Root-Logger bereits einen Handler hat -
    ein zweiter Aufruf (z.B. falls sowohl create_app() als auch der Worker-on_startup-Hook im
    selben Prozess liefen) erzeugt dadurch strukturell keinen doppelten Handler.

    `stream=sys.stdout` wird explizit gesetzt: ein `logging.StreamHandler()` ohne diesen
    Parameter nutzt sonst standardmaessig `sys.stderr` und wiche damit von der Festlegung
    "einfaches Textformat ueber stdout" ab."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
