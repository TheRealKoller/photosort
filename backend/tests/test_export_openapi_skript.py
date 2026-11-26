"""Der Erzeuger `backend/scripts/export_openapi.py` laeuft als Subprozess.

Er belegt drei Dinge, die der Vertragstest nicht sieht:
1. Das Skript setzt seine Vorgaben SELBST und laeuft ohne `SECRET_KEY`,
   `RATE_LIMIT_STORAGE_URI`, `DATABASE_URL` und `REDIS_URL` - sonst waere der Nachfuehrschritt an
   eine Umgebung gebunden, die niemand dokumentiert hat.
2. Es schreibt ueber ein Zielargument, damit dieser Test nie in den Arbeitsbaum schreibt; zwei
   Laeufe sind byte-gleich.
3. Die kanonische Form stimmt: zwei Leerzeichen, sortierte Schluessel, UTF-8 mit literalen
   Umlauten, abschliessender Zeilenumbruch. Ohne diese Form erzeugte `openapi-typescript` bei
   jedem Lauf einen anderen Diff.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ARTEFAKT = Path(__file__).resolve().parents[1] / "openapi.json"
SKRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_openapi.py"
GEHEIM_VARIABLEN = (
    "SECRET_KEY",
    "RATE_LIMIT_STORAGE_URI",
    "DATABASE_URL",
    "REDIS_URL",
    "ANTHROPIC_API_KEY",
    "OPENCLOUD_BASE_URL",
    "OPENCLOUD_USERNAME",
    "OPENCLOUD_APP_TOKEN",
    "AUTH_SEED_USER1_PASSWORD",
    "AUTH_SEED_USER2_PASSWORD",
)


def _umgebung() -> dict[str, str]:
    return {name: wert for name, wert in os.environ.items() if name not in GEHEIM_VARIABLEN}


def _lauf(ziel: Path, arbeitsverzeichnis: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SKRIPT), str(ziel)],
        cwd=arbeitsverzeichnis,
        env=_umgebung(),
        capture_output=True,
        text=True,
        check=False,
    )


def _kanonisch(inhalt: dict[str, object]) -> str:
    return json.dumps(inhalt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_the_script_runs_without_environment_and_is_deterministic(tmp_path: Path) -> None:
    ziel_a = tmp_path / "a.json"
    ziel_b = tmp_path / "b.json"

    erster = _lauf(ziel_a, tmp_path)
    zweiter = _lauf(ziel_b, tmp_path)

    assert erster.returncode == 0, erster.stderr
    assert zweiter.returncode == 0, zweiter.stderr
    assert ziel_a.read_bytes() == ziel_b.read_bytes()


def test_the_written_form_is_canonical_utf8(tmp_path: Path) -> None:
    ziel = tmp_path / "openapi.json"

    ergebnis = _lauf(ziel, tmp_path)

    assert ergebnis.returncode == 0, ergebnis.stderr
    roh = ziel.read_bytes().decode("utf-8")
    geparst = json.loads(roh)
    assert roh == _kanonisch(geparst)
    assert roh.endswith("\n")
    assert "\r" not in roh
    # Literale Umlaute statt \uXXXX-Escapes: der Diff bleibt lesbar.
    assert "\\u00" not in roh
    assert any(zeichen in roh for zeichen in "äöüÄÖÜß")


def test_the_default_target_is_the_checked_in_artifact() -> None:
    """Das Zielargument ist die Ausnahme fuer den Test; die Vorgabe ist der Arbeitsbaum-Pfad."""
    quelle = SKRIPT.read_text(encoding="utf-8")

    assert "openapi.json" in quelle


def test_the_checked_in_artifact_is_canonical() -> None:
    roh = ARTEFAKT.read_bytes().decode("utf-8")

    assert roh == _kanonisch(json.loads(roh))
    assert "\\u00" not in roh
