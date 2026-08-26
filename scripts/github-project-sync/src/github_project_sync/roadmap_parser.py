"""Parsing der Prioritaets-Tabellen im Abschnitt "Status auf einen Blick" von specs/roadmap.md.

Nur die Tabellen unter den "### Offen — <Prioritaet>"-Unterueberschriften werden ausgewertet -
NICHT der freitextige Abschnitt "Priorisierung" (ADR decisions/0017-github-projects-v2-spec-sync.md,
Abschnitt 5: "fuer menschliche Begruendung gedacht, nicht maschinell robust parsbar").

Seit Spec 0059 / ADR decisions/0036-github-issue-natives-story-refinement-inbox-entfaellt.md,
Abschnitt 5: zweite Erkennungsregel fuer issue-referenzierte Zeilen der Form
"[#NNN](<Issue-URL>)" (Stories ohne eigene Spec-Datei) innerhalb derselben Unterabschnitte -
Ergebnis-Keys bekommen ein "issue:"-Praefix, kollisionsfrei zu den bestehenden vierstelligen
Spec-Nummern-Keys.
"""

from __future__ import annotations

import re

_STATUS_SECTION_RE = re.compile(
    r"^## Status auf einen Blick\s*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)
_PRIORITY_SUBSECTION_RE = re.compile(
    r"^### Offen — (Hoch|Mittel|Niedrig)\s*\n(.*?)(?=^### |\Z)", re.MULTILINE | re.DOTALL
)
_TABLE_ROW_SPEC_RE = re.compile(r"^\|\s*\[(\d{4})\]\(", re.MULTILINE)
_TABLE_ROW_ISSUE_RE = re.compile(r"^\|\s*\[#(\d+)\]\(", re.MULTILINE)
_ISSUE_KEY_PREFIX = "issue:"


def parse_roadmap_priorities(text: str) -> dict[str, str]:
    """Liefert {spec_nummer|"issue:NNN": priorität} fuer alle Zeilen in den
    "Offen — <Priorität>"-Tabellen (sowohl Spec-Datei- als auch Issue-referenzierte Zeilen)."""
    section_match = _STATUS_SECTION_RE.search(text)
    if section_match is None:
        return {}

    section_text = section_match.group(1)
    priorities: dict[str, str] = {}
    for sub_match in _PRIORITY_SUBSECTION_RE.finditer(section_text):
        priority = sub_match.group(1)
        table_text = sub_match.group(2)
        for row_match in _TABLE_ROW_SPEC_RE.finditer(table_text):
            priorities[row_match.group(1)] = priority
        for issue_row_match in _TABLE_ROW_ISSUE_RE.finditer(table_text):
            priorities[f"{_ISSUE_KEY_PREFIX}{issue_row_match.group(1)}"] = priority

    return priorities
