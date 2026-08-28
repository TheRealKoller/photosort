"""Marker-Kommentar (technische Spec<->Issue-Identitaet) und Issue-Body-Konstruktion.

Siehe ADR decisions/0017-github-projects-v2-spec-sync.md, Abschnitt 3: erste Zeile jedes
Issue-Bodys ist ein versteckter Marker `<!-- photosort-spec: NNNN -->`, danach der gespiegelte
Inhalts-Zone-Text der Spec (ab der ersten "## "-Ueberschrift). Seit Spec 0065 / ADR 0041 ist
dieser Spiegel-Vorgang nur noch einseitig (Spec-Datei -> Issue-Body) - ein Rueckfluss aus dem
Issue-Body in die Spec-Datei findet nicht mehr statt, deshalb gibt es hier keine Extraktions-
Funktion mehr.

Der frueher parallel bestehende `photosort-inbox`-Marker (ADR decisions/0030-github-sync-natives-
status-feld-inbox-einbindung.md, Abschnitt 4) wurde mit Spec 0059 / ADR decisions/0036-github-
issue-natives-story-refinement-inbox-entfaellt.md ersatzlos entfernt: Stories ab Spec 0059 haben
keinen eigenen Nummernkreis mehr (die GitHub-Issue-Nummer selbst ist die Identitaet, siehe ADR
0036 Abschnitt 1) und brauchen deshalb keinen Marker-Kommentar - ein Marker entsteht fuer eine
Story-Nummer erst beim Uebergang zu einer Feature-Spec (`sync.py::_adopt_story_and_push_first_
content`, wiederverwendet den bereits bestehenden `photosort-spec`-Marker).
"""

from __future__ import annotations

import re

_MARKER_LINE_RE = re.compile(r"^<!-- photosort-spec: (\d{4}) -->\s*$")


def build_issue_body(spec_number: str, content_zone: str) -> str:
    zone = content_zone if content_zone.endswith("\n") else content_zone + "\n"
    return f"<!-- photosort-spec: {spec_number} -->\n\n{zone}"


def parse_marker(body: str) -> str | None:
    """Erste Zeile des Issue-Bodys -> Spec-Nummer, oder None falls Marker fehlt/ungueltig ist."""
    first_line = body.split("\n", 1)[0]
    match = _MARKER_LINE_RE.match(first_line)
    return match.group(1) if match else None
