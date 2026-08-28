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


def push_state_hash(*, status: str, content_zone: str) -> str:
    """Hash aus (Status, Inhalts-Zone).

    Die Prioritaet geht seit ADR 0039 nicht mehr in den Hash ein - sie wird nativ im
    GitHub-Project-Board gepflegt und vom Sync-Tool weder gelesen noch geschrieben. Der Hash
    aendert sich damit nur noch bei einer Status- oder Inhalts-Zonen-Aenderung.
    """
    composite = f"STATUS:{status}\n---\n{content_zone}"
    return text_hash(composite)


def push_state_hash_inbox(*, status: str, typ: str, content_zone: str) -> str:
    """Hash aus (Status, Typ, Inhalts-Zone) fuer Inbox-Eintraege (Spec 0052).

    Eigene Funktion statt eines zusaetzlichen `typ`-Parameters an push_state_hash() - die beiden
    Zustandsschemata (Feature-Spec: Status + Inhalt; Inbox-Eintrag: Status + Typ + Inhalt) sind
    unabhaengig und sollen sich nicht ueber einen gemeinsam gedeuteten Parameter vermischen.
    Nutzt denselben text_hash()-Baustein wie push_state_hash(), keine Duplikation der
    eigentlichen Hash-/Normalisierungslogik. (Seit Spec 0059 ohne Aufrufer, bewusst nicht
    mit aufgeraeumt - ADR 0039.)
    """
    composite = f"STATUS:{status}\nTYP:{typ}\n---\n{content_zone}"
    return text_hash(composite)
