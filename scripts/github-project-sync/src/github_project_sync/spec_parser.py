"""Parsing/Ersetzung von specs/features/*.md: Metadaten-Block + Inhalts-Zone ab "## ".

Siehe specs/features/0031-zweiwege-sync-specs-github-projekt.md, Akzeptanzkriterium
"Issue-Body -> Spec-Inhalt", und ADR decisions/0017-github-projects-v2-spec-sync.md, Abschnitt 4:
Nur der Teil ab der ersten "##"-Ueberschrift ist bidirektional, H1-Titel und Metadaten-Block
bleiben beim Zurueckspielen unangetastet.
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


def replace_content_zone(original_text: str, new_content_zone: str) -> str:
    """Ersetzt nur den Teil ab der ersten '## '-Ueberschrift, Header bleibt unangetastet.

    Ein im Issue versehentlich mitgeaenderter Metadaten-Block hat dadurch technisch keine
    Wirkung (ADR 0017, Abschnitt 4) - new_content_zone wird nicht auf einen Metadaten-Block hin
    untersucht, sondern schlicht nicht in den Header uebernommen.
    """
    content_match = _CONTENT_ZONE_START_RE.search(original_text)
    if content_match is None:
        raise SpecParseError("keine Inhalts-Zone (erste '## '-Ueberschrift) im Original gefunden.")

    header = original_text[: content_match.start()].rstrip("\n") + "\n"
    zone = new_content_zone if new_content_zone.endswith("\n") else new_content_zone + "\n"
    return header + "\n" + zone


def set_status_line(original_text: str, new_status: str) -> str:
    """Ersetzt nur die '**Status:**'-Header-Zeile durch einen neuen Freitextwert.

    Analog zu replace_content_zone(), aber fuer den Header statt die Inhalts-Zone - genutzt von
    der automatischen PR-Merge-Erkennung (sync.py::_sync_one(), ADR decisions/0037, Abschnitt 5),
    um die Status-Zeile z.B. auf "Implemented ([PR #101](...))" umzuschreiben. new_status ist der
    komplette neue Wert (nicht nur ein Schluesselwort) - alles andere in der Datei bleibt
    unangetastet.
    """
    if _STATUS_LINE_RE.search(original_text) is None:
        raise SpecParseError("kein '**Status:**'-Metadaten-Feld gefunden.")
    return _STATUS_LINE_RE.sub(lambda _match: f"**Status:** {new_status}", original_text, count=1)
