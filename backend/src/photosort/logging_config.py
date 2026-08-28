from __future__ import annotations

import logging
import sys

# specs/features/0056-structured-logging-cloud-vision-errors.md, decisions/0034-strukturiertes-
# logging-cloud-vision-fehler.md: erste Logging-Einfuehrung im Projekt. Eigenes, sehr kleines
# Modul statt Anhaengsel an config.py (das nur die pydantic-Settings fuehrt, keine Prozess-
# Bootstrap-Logik) - konsistent mit dem im Projekt etablierten Prinzip, eine neue, isolierte
# Zustaendigkeit in ein eigenes kleines Modul zu legen (aesthetics.py, landmark.py, horizon.py).
#
# Aufgerufen an BEIDEN Prozess-Einstiegspunkten (main.py::create_app() fuer den API-Prozess,
# worker.py::WorkerSettings.on_startup fuer den Worker-Prozess) - beide Prozesse bekommen
# dieselbe Konfiguration, obwohl nur der Worker sie fuer Spec 0056 tatsaechlich braucht, damit ein
# kuenftiges Feature mit API-seitigem Logging-Bedarf nicht erneut eine Konfigurationsentscheidung
# treffen muss (ADR 0034 Punkt 2).


def configure_logging() -> None:
    """Konfiguriert das Root-Logging fuer den aktuellen Prozess: Level WARNING (ADR 0034 Punkt 3
    - der Skip eines einzelnen Fotos ist erwartetes best-effort-Verhalten, kein Lauf-Fehlschlag),
    einfaches Textformat mit Zeitstempel/Level/Modulname ueber stdout (ADR 0034 Punkt 4 - kein
    JSON, `docker compose logs` ist der einzige Konsument).

    `logging.basicConfig()` ist ein No-op, sobald der Root-Logger bereits einen Handler hat -
    ein zweiter Aufruf (z.B. falls sowohl create_app() als auch der Worker-on_startup-Hook im
    selben Prozess liefen) erzeugt dadurch strukturell keinen doppelten Handler.

    `stream=sys.stdout` wird explizit gesetzt (Copilot-Review-Fund, PR #247): ein
    `logging.StreamHandler()` ohne diesen Parameter nutzt sonst standardmaessig `sys.stderr`,
    was von der in ADR 0034 Punkt 4 dokumentierten Entscheidung "einfaches Textformat ueber
    stdout" abweichen wuerde."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
