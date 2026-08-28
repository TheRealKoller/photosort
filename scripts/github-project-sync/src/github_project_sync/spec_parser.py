"""Parsing/Ersetzung von specs/features/*.md: Metadaten-Block + Inhalts-Zone ab "## ".

Siehe ADR decisions/0017-github-projects-v2-spec-sync.md, Abschnitt 4. Seit Spec 0065 / ADR 0041
ist der Content-Sync nur noch einseitig (Spec-Datei -> Issue-Body) - dieses Modul parst die
Spec-Datei weiterhin (Metadaten-Block + Inhalts-Zone) und schreibt die Status-Zeile fuer die
automatische PR-Merge-Erkennung zurueck (set_status_line()), ersetzt aber keine Inhalts-Zone mehr
aus zurueckgespieltem Issue-Inhalt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_SPEC_NUMBER_RE = re.compile(r"^\d{4}$")
_H1_RE = re.compile(r"^#\s+(\d{4})\s*-\s*(.+?)\s*$", re.MULTILINE)
# Nur das fuehrende Enum-Schluesselwort (Proposed/Accepted/Implemented/Superseded) erfassen,
# alles danach (Kommas, Klammern mit PR-Link/Datum, Gedankenstrich-Freitext) ignorieren. Real im
# Repo vorkommende Varianten: "Implemented ([PR #NN](...))", "Implemented ([PR #NN](...), Datum)",
# "Implemented — AK... umgesetzt in [PR #NN](...)", "Superseded, abgelöst durch [...](...)" -
# siehe tests/test_spec_parser.py fuer die vollstaendige, aus dem echten Bestand entnommene Liste.
# Bug gefunden im zweiten manuellen Sync-Lauf gegen echtes GitHub nach Merge von PR #117: die
# vorherige Fassung uebernahm die komplette Zeile, wodurch sync.py's Status-Validierung fuer
# praktisch den gesamten Bestand bereits abgeschlossener Specs scheiterte.
_STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*([A-Za-z]+)", re.MULTILINE)
# Fuer set_status_line(): die komplette Status-Zeile (nicht nur das fuehrende Schluesselwort wie
# bei _STATUS_RE oben), damit sie sich als Ganzes durch einen neuen Freitextwert ersetzen laesst
# (z.B. "Implemented ([PR #101](...))", siehe ADR decisions/0037, Abschnitt 5).
_STATUS_LINE_RE = re.compile(r"^\*\*Status:\*\*.*$", re.MULTILINE)
_CONTENT_ZONE_START_RE = re.compile(r"^## ", re.MULTILINE)


class SpecParseError(ValueError):
    """Eine Spec-Datei/ihr Inhalt konnte nicht wie erwartet geparst werden."""


@dataclass(frozen=True)
class ParsedSpec:
    number: str
    title: str
    status: str
    header: str
    content_zone: str
    full_text: str


def validate_spec_number(value: str) -> str:
    """Verteidigung in der Tiefe gegen Pfad-Traversal ueber die Spec-Nummer.

    Analog zum bestehenden _join()-Muster in backend/src/photosort/opencloud/client.py -
    vor jeder Dateipfad-Konstruktion aus einer extern/aus geparstem Text stammenden
    Spec-Nummer (siehe Security-Abschnitt der Spec 0031, Bedrohung 3).
    """
    if not _SPEC_NUMBER_RE.match(value):
        raise ValueError(f"Ungueltige Spec-Nummer: {value!r} (erwartet genau 4 Ziffern).")
    return value


def parse_spec_text(text: str, *, source: str = "<string>") -> ParsedSpec:
    h1_match = _H1_RE.search(text)
    if h1_match is None:
        raise SpecParseError(f"{source}: keine H1-Ueberschrift '# NNNN - Titel' gefunden.")

    status_match = _STATUS_RE.search(text)
    if status_match is None:
        raise SpecParseError(f"{source}: kein '**Status:**'-Metadaten-Feld gefunden.")

    content_match = _CONTENT_ZONE_START_RE.search(text)
    if content_match is None:
        raise SpecParseError(f"{source}: keine Inhalts-Zone (erste '## '-Ueberschrift) gefunden.")

    number = h1_match.group(1)
    title = h1_match.group(2)
    status = status_match.group(1)
    header = text[: content_match.start()].rstrip("\n") + "\n"
    content_zone = text[content_match.start() :]

    return ParsedSpec(
        number=number,
        title=title,
        status=status,
        header=header,
        content_zone=content_zone,
        full_text=text,
    )


def parse_spec_file(path: Path) -> ParsedSpec:
    filename_match = re.match(r"^(\d{4})-", path.name)
    if filename_match is None:
        raise SpecParseError(f"{path}: Dateiname beginnt nicht mit 'NNNN-'.")

    text = path.read_text(encoding="utf-8")
    parsed = parse_spec_text(text, source=str(path))

    if parsed.number != filename_match.group(1):
        raise SpecParseError(
            f"{path}: Spec-Nummer im Dateinamen ({filename_match.group(1)}) weicht von der "
            f"H1-Ueberschrift ({parsed.number}) ab."
        )

    return parsed


def set_status_line(original_text: str, new_status: str) -> str:
    """Ersetzt nur die '**Status:**'-Header-Zeile durch einen neuen Freitextwert.

    Genutzt von der automatischen PR-Merge-Erkennung (sync.py::_sync_one(), ADR decisions/0037,
    Abschnitt 5), um die Status-Zeile z.B. auf "Implemented ([PR #101](...))" umzuschreiben.
    new_status ist der komplette neue Wert (nicht nur ein Schluesselwort) - alles andere in der
    Datei bleibt unangetastet.

    Copilot-Review-Finding auf PR #229: Suche/Ersetzung muessen strikt auf den Header (den Teil
    VOR der ersten '## '-Ueberschrift) beschraenkt bleiben, analog zu parse_spec_text() - sonst
    wuerde ein '**Status:**'-Vorkommen in der Inhalts-Zone (z.B. ein zitiertes Beispiel eines
    Metadaten-Blocks) faelschlich getroffen, falls der Header selbst aus irgendeinem Grund kein
    gueltiges Feld enthaelt.
    """
    content_match = _CONTENT_ZONE_START_RE.search(original_text)
    if content_match is None:
        raise SpecParseError("keine Inhalts-Zone (erste '## '-Ueberschrift) gefunden.")

    header = original_text[: content_match.start()]
    rest = original_text[content_match.start() :]

    if _STATUS_LINE_RE.search(header) is None:
        raise SpecParseError("kein '**Status:**'-Metadaten-Feld im Header gefunden.")

    new_header = _STATUS_LINE_RE.sub(
        lambda _match: f"**Status:** {new_status}", header, count=1
    )
    return new_header + rest
