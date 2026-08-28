"""Hash-Bildung fuer die Drei-Wege-Push-Klassifikation (siehe classify.py).

Normalisiert CRLF/Trailing-Whitespace, um False-Positive-Aenderungen zu vermeiden. Seit Spec 0065
/ ADR 0041 ausschliesslich fuer den Push-Zweig (Spec-Inhalt -> Issue-Body) relevant - der frueher
parallel bestehende Pull-/Konflikt-Zweig entfaellt vollstaendig.
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


def push_state_hash(*, status: str, content_zone: str) -> str:
    """Hash aus (Status, Inhalts-Zone).

    Die Prioritaet geht seit ADR 0039 nicht mehr in den Hash ein - sie wird nativ im
    GitHub-Project-Board gepflegt und vom Sync-Tool weder gelesen noch geschrieben. Der Hash
    aendert sich damit nur noch bei einer Status- oder Inhalts-Zonen-Aenderung.
    """
    composite = f"STATUS:{status}\n---\n{content_zone}"
    return text_hash(composite)
