"""Befehlsform der `gh`-Zeilen: Freitext nur als Datei, Ziel geschlossen, Reihenfolge der Kette.

Drei Aussagen, die Haertungsregeln tragen - nicht die Schreibweise einer Option:

- `freitext-nur-als-datei` - jede Option, die Freitext traegt, verweist auf eine Datei
  (`--body-file`, `-F …=@…`, `"$(cat <pfad>)"`, `"$(<pfad)"`); Inline-Inhalt ist ein Befund.
- `ziel-geschlossen` - jeder schreibende Aufruf nennt sein Ziel selbst, und es ist dieses
  Repository.
- `reihenfolge-ausfuehrung` - im `refinement`-Ablauf folgt die Kette Body -> Titel -> Bereich ->
  Board, und `Ready` ist das letzte Glied.

Ein Aufruf, den der Leser nicht klassifizieren kann, ist ein Befund - nie ein Ueberspringen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

from waechter import Befund, Bestand, Invariante, befund, codebloecke

REPO = "TheRealKoller/photosort"
ANWEISUNGSRAUM = (".claude", "CLAUDE.md")
SCHREIBENDE_VERBEN = frozenset({"create", "edit", "close", "comment"})
LESENDE_VERBEN = frozenset({"view", "list", "checks"})

INVARIANTEN = (
    Invariante(
        "freitext-nur-als-datei",
        "Jede Option eines `gh`-Aufrufs, die Freitext traegt, referenziert eine Datei; "
        "Inline-Inhalt ist ein Befund.",
    ),
    Invariante(
        "ziel-geschlossen",
        "Jeder schreibende Aufruf nennt sein Ziel selbst - ueber `--repo`, `-R` oder das "
        f"Repo-Segment im API-Pfad - und es ist `{REPO}`.",
    ),
    Invariante(
        "reihenfolge-ausfuehrung",
        "Die Ausfuehrungsstellen des `refinement`-Ablaufs folgen Body -> Titel -> Bereich -> "
        "Board; `Ready` ist das letzte Glied.",
    ),
)

INVARIANTEN_IDS = frozenset(invariante.id for invariante in INVARIANTEN)

_AUFRUF = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?:`[^`\n]*`:[ \t]*)?[`$]?[ \t]*(?P<befehl>gh [a-z][a-z-]*[^\n]*)",
    re.MULTILINE,
)
_REPO_OPTION = re.compile(r"(?:--repo|-R)[ =](?P<ziel>\S+)")
_API_ZIEL = re.compile(r"\brepos/(?P<ziel>[^/\s]+/[^/\s]+)")
_INLINE = re.compile(
    r"(?<![\w-])(?P<option>--body|--title|-F|-f)(?:\s+|=)"
    r"(?P<wert>\"[^\"]*\"|'[^']*'|\S+)"
)
_FREITEXT_DATEI = re.compile(r'^(?:"?\$\((?:cat|<)\s*[^)\s]+\)"?|(?:[^=\s]*=)?@\S+)$')
_AUSFUEHRUNGSSTELLE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+|\d+\.[ \t]+)?`(?P<id>[a-z][a-z-]*)`(?P<rest>[^\n]*)",
    re.MULTILINE,
)
REFINEMENT = ".claude/skills/refinement/SKILL.md"
BODY, TITEL, BEREICH, STATUS = (
    "issue-body-schreiben",
    "issue-titel-schreiben",
    "issue-bereich-setzen",
    "board-status-setzen",
)
BOARD_PRAEFIX = "board-"
READY = "`Ready`"


@dataclass(frozen=True)
class Aufruf:
    """Eine `gh`-Befehlszeile samt Ziel und Zeile."""

    datei: str
    zeile: int
    befehl: str
    verb: str
    ziel: str | None

    @property
    def ort(self) -> str:
        return f"{self.datei}:{self.zeile}"


def _befehlszeilen(text: str) -> list[tuple[int, str]]:
    """Codeblock-Zeilen, die mit `gh ` beginnen - Prosa mit `gh` ist keine Befehlszeile."""
    zeilen: list[tuple[int, str]] = []
    for block in codebloecke(text):
        for zeile in block.split("\n"):
            if zeile.strip().startswith("gh "):
                zeilen.append((0, zeile.strip()))
    return zeilen


def aufrufe(datei: str, text: str) -> list[Aufruf]:
    """Alle `gh`-Aufrufe eines Textes - aus Codebloecken und aus Befehlszeilen mit ID-Etikett."""
    ergebnis: list[Aufruf] = []
    for treffer in _AUFRUF.finditer(text):
        befehl = treffer.group("befehl").strip()
        if not re.match(r"^gh [a-z]", befehl):
            continue
        teile = befehl.split()
        bereich = teile[1] if len(teile) > 1 else ""
        if bereich == "api":
            verb = "api"
        elif bereich in {"issue", "pr"} and len(teile) > 2:
            verb = teile[2]
        else:
            continue  # `gh project …` und fremde Bereiche traegt `board-werte`.
        option = _REPO_OPTION.search(befehl)
        pfad = _API_ZIEL.search(befehl)
        ziel = option.group("ziel") if option else (pfad.group("ziel") if pfad else None)
        ergebnis.append(
            Aufruf(
                datei=datei,
                zeile=text.count("\n", 0, treffer.start()) + 1,
                befehl=befehl,
                verb=verb,
                ziel=ziel,
            )
        )
    return ergebnis


def _freitext(aufruf: Aufruf) -> list[Befund]:
    befunde: list[Befund] = []
    for treffer in _INLINE.finditer(aufruf.befehl):
        wert = treffer.group("wert").strip("\"'")
        if treffer.group("option") == "--body":
            befunde.append(
                befund(
                    aufruf.datei,
                    aufruf.zeile,
                    "freitext-nur-als-datei",
                    "`--body` traegt Inline-Freitext - Bodies gehen ausschliesslich ueber "
                    "`--body-file`.",
                )
            )
        elif not _FREITEXT_DATEI.match(wert):
            befunde.append(
                befund(
                    aufruf.datei,
                    aufruf.zeile,
                    "freitext-nur-als-datei",
                    f"`{treffer.group('option')}` traegt den Inline-Wert {wert!r} - Freitext nur "
                    'als Dateiverweis (`@pfad`, `"$(cat <pfad>)"`, `"$(<pfad)"`).',
                )
            )
    return befunde


SCHREIB_MARKER = re.compile(r"(?:--input|-X\s*[A-Z]+|--method)")


def _schreibend(aufruf: Aufruf) -> bool:
    """Ein Aufruf, der Inhalt in ein GitHub-Artefakt schreibt."""
    if aufruf.verb in SCHREIBENDE_VERBEN:
        return True
    return aufruf.verb == "api" and bool(SCHREIB_MARKER.search(aufruf.befehl))


def _ziel(aufruf: Aufruf) -> list[Befund]:
    if not _schreibend(aufruf):
        if aufruf.verb in LESENDE_VERBEN or aufruf.verb == "api":
            return []
        return [
            befund(
                aufruf.datei,
                aufruf.zeile,
                "ziel-geschlossen",
                f"`gh {aufruf.verb}` ist weder als lesend noch als schreibend klassifizierbar - "
                "ein unklassifizierbarer Aufruf ist ein Befund.",
            )
        ]
    if aufruf.ziel is None:
        return [
            befund(
                aufruf.datei,
                aufruf.zeile,
                "ziel-geschlossen",
                "schreibender Aufruf ohne eigenes Ziel - er loest ueber den Arbeitsbaum auf.",
            )
        ]
    if aufruf.ziel != REPO:
        return [
            befund(
                aufruf.datei,
                aufruf.zeile,
                "ziel-geschlossen",
                f"Ziel {aufruf.ziel!r} statt {REPO!r}.",
            )
        ]
    return []


def _reihenfolge(bestand: Bestand) -> list[Befund]:
    if REFINEMENT not in bestand:
        return [
            Befund(
                ort="Bestand",
                invariante="reihenfolge-ausfuehrung",
                text=f"{REFINEMENT} fehlt - die Reihenfolge-Aussage waere leer wahr.",
            )
        ]
    text = bestand[REFINEMENT]
    stellen = [
        (text.count("\n", 0, treffer.start()) + 1, treffer.group("id"), treffer.group("rest"))
        for treffer in _AUSFUEHRUNGSSTELLE.finditer(text)
    ]
    befunde: list[Befund] = []
    for kennung in (BODY, TITEL, BEREICH):
        if not any(id_ == kennung for _, id_, _ in stellen):
            befunde.append(
                befund(
                    REFINEMENT,
                    1,
                    "reihenfolge-ausfuehrung",
                    f"keine Ausfuehrungsstelle von `{kennung}` - die Kette waere unvollstaendig.",
                )
            )
    if not any(id_.startswith(BOARD_PRAEFIX) for _, id_, _ in stellen):
        befunde.append(
            befund(
                REFINEMENT,
                1,
                "reihenfolge-ausfuehrung",
                f"keine Ausfuehrungsstelle einer `{BOARD_PRAEFIX}`-Operation.",
            )
        )
    if befunde:
        return befunde

    def erste(kennung: str) -> int:
        return next(zeile for zeile, id_, _ in stellen if id_ == kennung)

    ready = [zeile for zeile, id_, rest in stellen if id_ == STATUS and READY in rest]
    if not ready:
        return [
            befund(
                REFINEMENT,
                erste(STATUS) if any(id_ == STATUS for _, id_, _ in stellen) else 1,
                "reihenfolge-ausfuehrung",
                f"keine Ausfuehrungsstelle von `{STATUS}` mit Wert {READY}.",
            )
        ]
    kette = [
        (BODY, erste(BODY)),
        (TITEL, erste(TITEL)),
        (BEREICH, erste(BEREICH)),
        ("Board", min(zeile for zeile, id_, _ in stellen if id_.startswith(BOARD_PRAEFIX))),
        (STATUS + " Ready", min(ready)),
    ]
    for (frueher, zeile), (spaeter, spaeter_zeile) in pairwise(kette):
        if zeile >= spaeter_zeile:
            befunde.append(
                befund(
                    REFINEMENT,
                    spaeter_zeile,
                    "reihenfolge-ausfuehrung",
                    f"`{spaeter}` steht nicht hinter `{frueher}` ({REFINEMENT}:{zeile}).",
                )
            )
    return befunde


def pruefe(bestand: Bestand) -> list[Befund]:
    """Alle Befehlsform-Invarianten ueber einem Bestand."""
    alle: list[Aufruf] = []
    for datei in sorted(bestand):
        if not any(datei == ort or datei.startswith(f"{ort}/") for ort in ANWEISUNGSRAUM):
            continue
        alle.extend(aufrufe(datei, bestand[datei]))
    befunde: list[Befund] = []
    if not alle:
        befunde.append(
            Befund(
                ort="Bestand",
                invariante="freitext-nur-als-datei",
                text="kein `gh`-Aufruf im Anweisungsraum - der Suchraum traegt keine Befehle.",
            )
        )
    for aufruf in alle:
        if _schreibend(aufruf):
            befunde.extend(_freitext(aufruf))
        befunde.extend(_ziel(aufruf))
    befunde.extend(_reihenfolge(bestand))
    return befunde


def test_der_bestand_erfuellt_alle_invarianten() -> None:
    """Der lebende Bestand haelt jede Invariante; die Verletzungsfaelle belegt `mutationen.py`."""
    befunde = pruefe(Bestand.aus_arbeitsbaum())

    assert not befunde, "Befehlsform-Befunde: " + "; ".join(f.meldung for f in befunde)
