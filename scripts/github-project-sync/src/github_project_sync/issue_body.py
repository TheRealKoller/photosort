"""Marker-Kommentar (technische Spec/Inbox<->Issue-Identitaet) und Issue-Body-Konstruktion.

Siehe ADR decisions/0017-github-projects-v2-spec-sync.md, Abschnitt 3: erste Zeile jedes
Issue-Bodys ist ein versteckter Marker `<!-- photosort-spec: NNNN -->`, danach der gespiegelte
Inhalts-Zone-Text der Spec (ab der ersten "## "-Ueberschrift).

Seit ADR decisions/0030-github-sync-natives-status-feld-inbox-einbindung.md, Abschnitt 4, gibt es
zwei getrennte, jeweils hart auf den Entitaets-String geankerte Marker-Regexe (`photosort-spec`
bzw. `photosort-inbox`) statt einer gemeinsamen, nur die Zahl extrahierenden Funktion - Inbox- und
Feature-Nummernkreise kollidieren real (z.B. inbox/0004 und features/0004 existieren gleichzeitig,
siehe Security-Abschnitt der Spec 0052). Eine gemeinsame Extraktionsfunktion wuerde diesen Schutz
aufheben, deshalb bewusst zwei unabhaengige Funktionspaare statt einer parametrisierten Variante.
"""

from __future__ import annotations

import re

_MARKER_LINE_RE = re.compile(r"^<!-- photosort-spec: (\d{4}) -->\s*$")
_INBOX_MARKER_LINE_RE = re.compile(r"^<!-- photosort-inbox: (\d{4}) -->\s*$")


def build_issue_body(spec_number: str, content_zone: str) -> str:
    zone = content_zone if content_zone.endswith("\n") else content_zone + "\n"
    return f"<!-- photosort-spec: {spec_number} -->\n\n{zone}"


def build_inbox_issue_body(inbox_number: str, content_zone: str) -> str:
    zone = content_zone if content_zone.endswith("\n") else content_zone + "\n"
    return f"<!-- photosort-inbox: {inbox_number} -->\n\n{zone}"


def parse_marker(body: str) -> str | None:
    """Erste Zeile des Issue-Bodys -> Spec-Nummer, oder None falls Marker fehlt/ungueltig ist.

    Matcht ausschliesslich den photosort-spec-Marker - ein photosort-inbox-Marker liefert
    bewusst None, auch bei korrekter Nummer (Cross-Namespace-Ablehnung).
    """
    first_line = body.split("\n", 1)[0]
    match = _MARKER_LINE_RE.match(first_line)
    return match.group(1) if match else None


def parse_inbox_marker(body: str) -> str | None:
    """Erste Zeile des Issue-Bodys -> Inbox-Nummer, oder None falls Marker fehlt/ungueltig ist.

    Matcht ausschliesslich den photosort-inbox-Marker - ein photosort-spec-Marker liefert
    bewusst None, auch bei korrekter Nummer (Cross-Namespace-Ablehnung).
    """
    first_line = body.split("\n", 1)[0]
    match = _INBOX_MARKER_LINE_RE.match(first_line)
    return match.group(1) if match else None


def extract_content_zone_from_issue_body(body: str) -> str:
    """Alles nach der Marker-Zeile, fuehrende Leerzeilen entfernt."""
    _, _, rest = body.partition("\n")
    return rest.lstrip("\n")
