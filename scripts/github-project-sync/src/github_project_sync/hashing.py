"""Hash-Bildung fuer die Vier-Wege-Konflikt-Klassifikation (siehe classify.py).

Normalisiert CRLF/Trailing-Whitespace, um False-Positive-Aenderungen zu vermeiden (Akzeptanz-
kriterium "Issue-Body -> Spec-Inhalt" in specs/features/0031-zweiwege-sync-specs-github-projekt.md).
"""

from __future__ import annotations

import hashlib


def normalize_text(text: str) -> str:
    """CRLF/CR -> LF, Trailing-Whitespace pro Zeile entfernt, kein abschliessender Zeilenumbruch."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).rstrip("\n")


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


_MISSING_PRIORITY_MARKER = "\x00__none__"


def push_state_hash(*, status: str, priority: str | None, content_zone: str) -> str:
    """Hash aus (Status, aus roadmap.md abgeleiteter Prioritaet, Inhalts-Zone).

    priority=None (Implemented/Superseded-Specs ohne Eintrag in den Prioritaets-Tabellen) wird
    bewusst von priority="" unterschieden (siehe Test), damit beide Faelle im Hash nicht
    kollidieren koennten.
    """
    priority_marker = _MISSING_PRIORITY_MARKER if priority is None else priority
    composite = f"STATUS:{status}\nPRIORITY:{priority_marker}\n---\n{content_zone}"
    return text_hash(composite)
