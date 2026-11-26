#!/usr/bin/env python3
"""Schreibt `create_app().openapi()` als `backend/openapi.json`.

Die Datei ist eingecheckt und entsteht ausschliesslich aus dem Quelltext - nie aus einer laufenden
Instanz und nie durch Handbearbeitung. Vor dem Import werden dieselben Test-Vorgaben gesetzt wie
in `backend/tests/conftest.py`: der Erzeuger laeuft ohne Datenbank, ohne Redis und ohne
Produktionsgeheimnisse.

Aufruf: `python backend/scripts/export_openapi.py [ZIEL]` - ohne Ziel schreibt er das eingecheckte
Artefakt. Nach jeder Aenderung an einer Antwortstruktur folgt
`npm --prefix frontend run api:generate`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
VORGABE_ZIEL = BACKEND / "openapi.json"
# Lang genug fuer den secret_key-Startwaechter; nur fuer die Erzeugung, nie fuer einen Betrieb.
TEST_SECRET_KEY = "openapi-export-test-key-not-for-production-use"


def _vorgaben_setzen() -> None:
    """Zuweisend vor dem Import - `photosort.config` liest die Umgebung beim Modulimport."""
    os.environ.setdefault("SECRET_KEY", TEST_SECRET_KEY)
    os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")


def _ziel(argumente: list[str]) -> Path:
    return Path(argumente[0]).resolve() if argumente else VORGABE_ZIEL


def main(argumente: list[str] | None = None) -> int:
    _vorgaben_setzen()
    sys.path.insert(0, str(BACKEND / "src"))

    from photosort.main import create_app

    beschreibung = create_app().openapi()
    text = json.dumps(beschreibung, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ziel = _ziel(sys.argv[1:] if argumente is None else argumente)
    ziel.write_text(text, encoding="utf-8")
    print(f"{len(text)} Zeichen nach {ziel} geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
