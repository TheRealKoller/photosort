"""Haelt fest, dass die Adresse der selbst gehosteten Penpot-Instanz nicht ins Repository geraet.

Seit ADR 0065 ist die Penpot-Datei „PhotoSort — Dark Utility Register" die Design-Quelle. Das
Repository ist **oeffentlich**, die Instanz ist **privat und selbst gehostet**: Im Repository steht
deshalb ausschliesslich der *Dateiname* - nirgends Adresse, Hostname, Port, Instanz-ID,
Datei-/Projekt-ID, Benutzername oder Token.

**Warum das ein Test ist und nicht nur eine Zeile Prosa.** Die Regel gilt fuer Dateien, die
kuenftig von Agenten bearbeitet werden, ihr Erfolgsfall ist „nichts gefunden" - und ihr Bruch ist
in einem oeffentlichen Repository nicht zurueckzunehmen. Das ist genau die Klasse Regel, die still
verfaellt.

Drei Zusicherungen:

* Unter `design/penpot/**`, `frontend/penpot/**`, `.claude/skills/penpot-design/**`,
  `.claude/skills/penpot-entwurfsrunden/**` und `.claude/skills/ship-entwurf/**` steht kein
  `://` ausser den beiden bekannten, harmlosen Praefixen (SVG-Namensraum, dieses GitHub-Projekt).
* Dieselben Pfade tragen keine IP-Adresse.
* `.env.example` traegt keinen `PENPOT_`-Eintrag - ausdruecklich benannt, weil das die
  naheliegendste Stelle waere, an der eine Instanzadresse als „Vorlage" doch noch hineingeriete.

Der Suchraum kommt aus `git ls-files`, nicht aus einem Verzeichnis-Walk: Eine nicht verwaltete
Arbeitskopie soll den Test weder rot noch gruen faerben. Diese Datei selbst ist ausgenommen - sie
fuehrt die Suchmuster im Text.

**Der Bestand ist sauber, dieser Test startet also gruen - ein Rot-Lauf belegt hier nichts.**
Tragender Beleg ist die Mutationsprobe: am 2026-09-11 probeweise eine Instanzadresse in
`.claude/skills/ship-entwurf/SKILL.md` gesetzt (der neu aufgenommene fuenfte Pfad), den Test rot
gesehen und die Zeile zurueckgenommen. Wer den Suchraum aendert, wiederholt diese Probe, statt sie
zu glauben.

Kein Netzwerk - gelesen werden ausschliesslich Dateien dieses Repositories.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

SUCHRAUM_PRAEFIXE = (
    "design/penpot/",
    "frontend/penpot/",
    ".claude/skills/penpot-design/",
    # Der Rundenablauf beschreibt Arbeit an derselben privaten, selbst gehosteten Instanz -
    # er gehoert in denselben Suchraum wie `penpot-design`.
    ".claude/skills/penpot-entwurfsrunden/",
    # Der Auslieferpfad eines Entwurfslaufs benennt Werte, die aus derselben privaten Instanz
    # stammen, und macht aus ihnen ein oeffentliches, nicht zurueckzunehmendes Artefakt.
    ".claude/skills/ship-entwurf/",
)

SELBST = "scripts/tests/test_penpot_ohne_instanzadresse.py"

# Genau zwei erlaubte Schema-Praefixe, beide begruendet und beide ortsunabhaengig:
#   - der SVG-Namensraum steht im erzeugten Symbol-Markup und ist eine Konstante des Formats,
#   - Verweise auf dieses Projekt sind oeffentlich und verraten nichts ueber die Instanz.
ERLAUBTE_SCHEMA_PRAEFIXE = (
    "http://www.w3.org/",
    "https://github.com/TheRealKoller/photosort",
)

_SCHEMA = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://\S*")

# Punktierte Vierergruppe als eigenstaendiges Wort. Die Verankerung ist noetig, weil der
# Suchraum SVG-Pfaddaten enthaelt: dort stehen Zahlenfolgen wie `.53.53 0 0 1` dicht an dicht.
_IP = re.compile(r"(?<![\w.])\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?![\w.])")

# Selbstschutz: Ein leerer Suchraum (falsches Arbeitsverzeichnis, kaputter Praefix) liesse jede
# Abwesenheitszusage leer wahr werden. Untergrenze bewusst weit unter dem Ist-Stand.
MINDESTZAHL_DATEIEN = 8


def suchraum() -> dict[str, str]:
    """Reine Funktion: die von Git verwalteten Dateien der fuenf Penpot-Pfade."""
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", *SUCHRAUM_PRAEFIXE],
        cwd=REPO_WURZEL,
        capture_output=True,
        check=True,
    )
    pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]
    return {
        pfad: (REPO_WURZEL / pfad).read_text(encoding="utf-8") for pfad in pfade if pfad != SELBST
    }


def schema_funde(abbild: dict[str, str]) -> list[str]:
    """Reine Funktion: alle `schema://`-Fundstellen ausserhalb der beiden Freigaben."""
    befunde: list[str] = []
    for pfad, inhalt in sorted(abbild.items()):
        for nummer, zeile in enumerate(inhalt.splitlines(), start=1):
            for treffer in _SCHEMA.findall(zeile):
                if treffer.startswith(ERLAUBTE_SCHEMA_PRAEFIXE):
                    continue
                befunde.append(f"{pfad}:{nummer}: {treffer}")
    return befunde


def ip_funde(abbild: dict[str, str]) -> list[str]:
    """Reine Funktion: alle IP-artigen Fundstellen."""
    befunde: list[str] = []
    for pfad, inhalt in sorted(abbild.items()):
        for nummer, zeile in enumerate(inhalt.splitlines(), start=1):
            for treffer in _IP.findall(zeile):
                befunde.append(f"{pfad}:{nummer}: {treffer}")
    return befunde


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    abbild = suchraum()

    assert len(abbild) >= MINDESTZAHL_DATEIEN, (
        f"Nur {len(abbild)} Dateien im Penpot-Suchraum gefunden. Entweder ist die Pfadliste "
        "kaputt oder das Arbeitsverzeichnis falsch - eine Abwesenheitszusage ueber einen leeren "
        "Suchraum sagt nichts."
    )


def test_keine_instanzadresse_im_penpot_suchraum() -> None:
    befunde = schema_funde(suchraum())

    assert not befunde, (
        "Adresse im Penpot-Suchraum gefunden. Im Repository steht ausschliesslich der DATEINAME "
        "der Penpot-Datei, nie Adresse, Hostname, Port oder ID (ADR 0065): " + "; ".join(befunde)
    )


def test_keine_ip_adresse_im_penpot_suchraum() -> None:
    befunde = ip_funde(suchraum())

    assert not befunde, "IP-Adresse im Penpot-Suchraum gefunden: " + "; ".join(befunde)


def test_env_example_traegt_keinen_penpot_eintrag() -> None:
    """Die naheliegendste Stelle, an der eine Instanzadresse als "Vorlage" hineingeriete."""
    inhalt = (REPO_WURZEL / ".env.example").read_text(encoding="utf-8")

    assert "PENPOT" not in inhalt.upper(), (
        ".env.example traegt einen PENPOT-Eintrag. Der Penpot-MCP-Server ist in Daniels lokaler "
        "Werkzeugkonfiguration eingerichtet, nicht in einer Repo-Datei (ADR 0065)."
    )


def test_es_entsteht_keine_mcp_konfiguration_im_repository() -> None:
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", ".mcp.json", "**/.mcp.json"],
        cwd=REPO_WURZEL,
        capture_output=True,
        check=True,
    )

    assert ergebnis.stdout == b"", (
        "Es ist eine .mcp.json ins Repository geraten. MCP-Server werden ausserhalb des "
        "Repositories konfiguriert (ADR 0061 fuer GitHub, ADR 0065 fuer Penpot)."
    )


# --- Gegenproben an synthetischem Text ----------------------------------------------------


@pytest.mark.parametrize(
    "zeile",
    [
        "const ziel = 'https://penpot.example.invalid'",
        "  # erreichbar unter http://penpot.lan:9001",
        "siehe ws://irgendwo/plugin",
    ],
)
def test_eine_adresse_wird_gefunden(zeile: str) -> None:
    assert schema_funde({"design/penpot/probe.js": zeile})


@pytest.mark.parametrize(
    "zeile",
    [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">',
        "siehe https://github.com/TheRealKoller/photosort/issues/352",
        "Die Instanzadresse steht nicht im Repository.",
    ],
)
def test_das_erlaubte_gilt_nicht_als_befund(zeile: str) -> None:
    assert schema_funde({"design/penpot/probe.js": zeile}) == []


def test_eine_ip_adresse_wird_gefunden() -> None:
    assert ip_funde({"design/penpot/probe.js": "host = '192.168.10.4'"})


@pytest.mark.parametrize(
    "zeile",
    [
        '"star": "<path d=\\"M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679\\"></path>"',
        '  "value": "-1.28"',
        "  const stufen = ['2xl', '3xl']",
    ],
)
def test_pfaddaten_gelten_nicht_als_ip_adresse(zeile: str) -> None:
    assert ip_funde({"design/penpot/probe.json": zeile}) == []
