"""Parsing von specs/inbox/*.md - schlanke Ergaenzung zu spec_parser.py, keine Duplikation.

Das Markdown-Format von specs/inbox/*.md ist strukturell identisch zu dem der Feature-Specs
(H1 "# NNNN - Titel", Inhalts-Zone ab der ersten "## "-Ueberschrift) - die bereits bestehende,
generische Parsing-Funktion in spec_parser.py (parse_spec_text) wird direkt wiederverwendet statt
dupliziert. Neu ist nur die zusaetzliche "**Typ:**"-Extraktion (Idee/Bug (vermeintlich)) und eine
eigene Menge gueltiger Statuswerte (nur "Unrefined"). Kein "**Bezug:**"-Feld wird erwartet/geparst -
die bestehende Kernfunktion sucht dieses Feld ohnehin nicht.

Siehe specs/features/0052-github-sync-natives-status-feld-inbox-einbindung.md und
ADR decisions/0030-github-sync-natives-status-feld-inbox-einbindung.md, Abschnitt 8.

Semantische Validierung (unbekannter Typ/Status -> nicht-fataler Warnfall, Eintrag wird
uebersprungen statt den gesamten Lauf abzubrechen) passiert bewusst NICHT hier, sondern in
sync.py - exakt analog zum bestehenden Muster bei Feature-Specs: spec_parser.py validiert das
Status-Enum ebenfalls nicht selbst, sync.py::_sync_one prueft das erst nach erfolgreichem Parsen.
VALID_INBOX_STATUSES/VALID_INBOX_TYPES werden hier nur als Konstanten bereitgestellt, damit
sync.py sie nicht dupliziert.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from github_project_sync.spec_parser import SpecParseError, parse_spec_text

VALID_INBOX_STATUSES = frozenset({"Unrefined"})
VALID_INBOX_TYPES = frozenset({"Idee", "Bug (vermeintlich)"})

_TYPE_RE = re.compile(r"^\*\*Typ:\*\*\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ParsedInboxEntry:
    number: str
    title: str
    status: str
    typ: str
    header: str
    content_zone: str
    full_text: str


def parse_inbox_text(text: str, *, source: str = "<string>") -> ParsedInboxEntry:
    parsed = parse_spec_text(text, source=source)

    type_match = _TYPE_RE.search(text)
    if type_match is None:
        raise SpecParseError(f"{source}: kein '**Typ:**'-Metadaten-Feld gefunden.")

    return ParsedInboxEntry(
        number=parsed.number,
        title=parsed.title,
        status=parsed.status,
        typ=type_match.group(1),
        header=parsed.header,
        content_zone=parsed.content_zone,
        full_text=parsed.full_text,
    )


def parse_inbox_file(path: Path) -> ParsedInboxEntry:
    filename_match = re.match(r"^(\d{4})-", path.name)
    if filename_match is None:
        raise SpecParseError(f"{path}: Dateiname beginnt nicht mit 'NNNN-'.")

    text = path.read_text(encoding="utf-8")
    parsed = parse_inbox_text(text, source=str(path))

    if parsed.number != filename_match.group(1):
        raise SpecParseError(
            f"{path}: Nummer im Dateinamen ({filename_match.group(1)}) weicht von der "
            f"H1-Ueberschrift ({parsed.number}) ab."
        )

    return parsed
