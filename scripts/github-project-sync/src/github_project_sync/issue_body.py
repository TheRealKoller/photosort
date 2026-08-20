"""Marker-Kommentar (technische Spec<->Issue-Identitaet) und Issue-Body-Konstruktion.

Siehe ADR decisions/0017-github-projects-v2-spec-sync.md, Abschnitt 3: erste Zeile jedes
Issue-Bodys ist ein versteckter Marker `<!-- photosort-spec: NNNN -->`, danach der gespiegelte
Inhalts-Zone-Text der Spec (ab der ersten "## "-Ueberschrift).
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


def extract_content_zone_from_issue_body(body: str) -> str:
    """Alles nach der Marker-Zeile, fuehrende Leerzeilen entfernt."""
    _, _, rest = body.partition("\n")
    return rest.lstrip("\n")
