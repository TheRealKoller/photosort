"""Der CI-Wartepunkt: blockierend, endlich, ohne Filter, ohne Pipe - Zahlen tragen nichts.

`timeout 540` ist eine Betriebszahl und darf sich aendern; `--watch`, ein endliches `timeout`,
das Fehlen von `--required` und der Verzicht auf eine Pipe tragen die Aussage. Gelesen wird der
Befehl selbst, nicht sein Satz daneben: Ein umformulierter Abschnitt bleibt gruen, ein
entfernter Wartepunkt wird rot.

Seit Spec 0505 traegt derselbe Waechter vier weitere Aussagen. Der Wartepunkt ist der eine Ort,
an dem ein Lauf den Endstand feststellt; seit dieser Spec liest er dort zusaetzlich die offenen
Nicht-Check-Befunde am Pull Request - einmal je Lauf, hinter dem Rundenblock, als eigener
Berichtsblock, rein lesend und ohne dass ein Befund etwas ausloest.

- `befundlesung-einmal-je-pfad`: beide Auslieferpfade nennen beide Operations-IDs je genau
  einmal, hinter dem Block, der in die naechste Nachbesserungsrunde zurueckfuehrt, und vor dem
  Bericht; beide Berichte nennen den Block.
- `befundbefehle-verengt`: je Operation genau ein `gh`-Aufruf mit `--jq`, beide in der Fangform,
  die Query als Literal in einfachen Anfuehrungszeichen, die Nummer nur als typisierte Variable,
  `first: 100`/`totalCount` bzw. `pr=`, `state=open` und `--paginate`; herkunftsoffen, in der
  Befundzahl ungekuerzt und mit unmaskiertem Exit-Code.
- `befund-kein-schreibweg`: kein Schreibverb, keine Methode, keine Body- oder Dateiausgabe.
- `berichtblock-einmal`: beide Berichtsbloecke je genau einmal definiert; der Befundstand ist der
  geschlossene Dreiklang und traegt keinen Wert aus dem CI-Ergebnis.

Dazu die Wirkungspruefung: Der `--jq`-Ausdruck ist ein ausfuehrbares Literal und wird mit `jq`
gegen Fixtures ausgefuehrt, nicht auf die Zeichen `200`, `Cc` und `Cf` durchsucht. Fehlt `jq`,
wird der Pruefer rot statt uebersprungen.

Jeder Befund nennt die Stelle, an der er entsteht, in Dateikoordinaten - nicht die Zeile im
ausgeschnittenen Befehlsblock. Sonst zeigte ein Befund neben die Aenderung, und die Mutation, die
ihn ausloest, liesse sich nicht belegen.
"""

from __future__ import annotations

import json
import re
import subprocess

from waechter import Befund, Bestand, Invariante, befund, codebloecke, zeile_an

KATALOG = ".claude/skills/github-access"
WARTEN_PFAD = f"{KATALOG}/operationen/pr-pruefstand-abwarten.md"
LESEN_PFAD = f"{KATALOG}/operationen/pr-pruefstand-lesen.md"
WARTEN = "pr-pruefstand-abwarten"
LESEN = "pr-pruefstand-lesen"
FELDAUSWAHL = "bucket,name,state,workflow"
ENTWICKLER = ".claude/agents/developer.md"
ANKER = (
    "## Abschlussbericht (Folgeauftrag: CI-Fehlschlag behoben)",
    "## Blockiert: CI-Fehlschlag außerhalb der zulässigen Klasse",
)

# Die beiden Befundlesungen und die Pfade, die sie einmal je Lauf aufrufen.
BEFUND_OPERATIONEN = ("pr-reviewbefunde-lesen", "pr-scanbefunde-lesen")
BEFUND_PFADE = {ident: f"{KATALOG}/operationen/{ident}.md" for ident in BEFUND_OPERATIONEN}

# Je Auslieferpfad: die Lesemarke (erste Zeile des Absatzes, der die beiden Aufrufe traegt), die
# letzte Zeile des Blocks, der in die naechste Nachbesserungsrunde zurueckfuehrt, und die
# Ueberschrift des Berichts. Alle drei sind Teil der Zusage - die Lesung gehoert hinter den
# Rundenblock (in der Runde wird nicht gelesen) und vor den Bericht (der sie traegt).
LESEMARKE = "**Befunde am Pull Request lesen — einmal, nach dem Endstand.**"
AUSLIEFERPFADE: dict[str, tuple[str, str]] = {
    ".claude/skills/ship-feature/SKILL.md": (
        "ist das kein Fall für den Subagenten",
        "## Abschlussbericht an den Nutzer",
    ),
    ".claude/skills/ship-entwurf/SKILL.md": (
        "nie weiterversuchen",
        "## Bericht an Daniel",
    ),
}

BEFUNDBLOCK = "## Befunde am Pull Request"
CIBLOCK = "## CI-Ergebnis"
BEFUNDSTAENDE = ("keine offen", "offen", "nicht festgestellt")
ERGEBNISWERTE = ("gruen", "rot", "laeuft-noch", "unbestimmt")

# Gelesen wird der Anweisungsraum. `specs/` zitiert dieselben Bloecke als Beleg und ist keine
# zweite Definitionsstelle - eine Zaehlung ueber den ganzen Bestand faende dort das Zitat und
# meldete eine Drift, die es nicht gibt.
ANWEISUNGSRAUM = (".claude", "docs", "CLAUDE.md")

INVARIANTEN = (
    Invariante(
        "pruefstand-blockierend",
        "Der Wartepunkt wartet blockierend (`--watch`), ist endlich begrenzt, filtert nicht auf "
        "erforderliche Checks, laeuft nicht durch eine Pipe und liest die Feldauswahl als ganzen "
        "Optionswert. Im Katalog gibt es genau einen blockierenden Wartebefehl, und die "
        "Ergebnistabelle fuehrt genau die vier Ergebniswerte.",
    ),
    Invariante(
        "anker-protokoll",
        "Beide CI-Anker sind als Ueberschrift genau einmal definiert - ein Ablauf liest sie.",
    ),
    Invariante(
        "befundlesung-einmal-je-pfad",
        "Beide Auslieferpfade nennen beide Befundlesungen je genau einmal, hinter dem "
        "Rundenblock und vor dem Bericht; beide Berichte nennen den Block.",
    ),
    Invariante(
        "befundbefehle-verengt",
        "Je Befundlesung genau ein `gh`-Aufruf mit `--jq` in der Fangform, die Query als Literal "
        "in einfachen Anfuehrungszeichen, die Nummer nur als typisierte Variable; `first: 100` "
        "und `totalCount` bzw. `pr=`, `state=open` und `--paginate`; herkunftsoffen, in der "
        "Befundzahl ungekuerzt, mit unmaskiertem Exit-Code.",
    ),
    Invariante(
        "befund-kein-schreibweg",
        "Beide Befundlesungen sind rein lesend: kein Schreibverb, keine Methode, keine Body- oder "
        "Dateiausgabe, kein `tee` und keine Umleitung.",
    ),
    Invariante(
        "berichtblock-einmal",
        "Beide Berichtsbloecke sind je genau einmal definiert, und der Befundstand ist genau der "
        "geschlossene Dreiklang - kein Wert aus dem CI-Ergebnis.",
    ),
)
INVARIANTEN_IDS = frozenset(invariante.id for invariante in INVARIANTEN)

_ENDLICH = re.compile(r"^timeout\s+\d+\s+\S")
_JSON = re.compile(r"--json\s+(?P<wert>\S+)")
_SLICE = re.compile(r"\[\s*\d+\s*:\s*\d+\s*\]")
_SELECT = re.compile(r"select\((?P<body>[^)]*)\)")
_HERKUNFTSFELD = re.compile(r"\b(?:author|tool|login)\b")
_ZAUN = "```"
_JQ_ANFANG = "--jq '"


def _zeile(text: str, ausschnitt: str) -> int:
    """Zeile des Ausschnitts, sonst 1 - der Befund soll auf die Stelle zeigen, nicht ins Leere."""
    position = text.find(ausschnitt) if ausschnitt else -1
    return 1 if position < 0 else text.count("\n", 0, position) + 1


def _abschnitt(text: str, kennung: str) -> str:
    """Der Abschnitt `## \\`<kennung>\\`` bis zur naechsten Ueberschrift derselben Ebene."""
    beginn = text.find(f"## `{kennung}`")
    if beginn == -1:
        return ""
    rest = text[beginn:]
    ende = rest.find("\n## ", 1)
    return rest if ende == -1 else rest[:ende]


def _befehle(abschnitt: str) -> list[str]:
    return [
        zeile.strip()
        for block in codebloecke(abschnitt)
        for zeile in block.split("\n")
        if "gh pr checks" in zeile
    ]


def _katalogdateien(bestand: Bestand) -> list[str]:
    """Jede Datei des Katalogs - Uebersicht wie Operationsdatei."""
    return sorted(
        pfad for pfad in bestand if pfad == f"{KATALOG}/SKILL.md" or pfad.startswith(f"{KATALOG}/")
    )


def _fangeform(abschnitt: str) -> str | None:
    """Der umzaeunte Befehlsblock einer Befundlesung - erkennbar an der Zuweisung."""
    for block in codebloecke(abschnitt):
        if "if out=$(" in block:
            return block
    return None


def _jq_programm(form: str) -> str | None:
    """Der `--jq`-Ausdruck als Literal; `None`, wenn er fehlt oder nicht schliesst."""
    beginn = form.find(_JQ_ANFANG)
    if beginn == -1:
        return None
    rest = form[beginn + len(_JQ_ANFANG) :]
    ende = rest.find("'")
    return None if ende == -1 else rest[:ende]


def _formzeile(form: str, basis: int, ausschnitt: str) -> int:
    """Die Zeile eines Ausschnitts im Befehlsblock, in Dateikoordinaten."""
    treffer = form.find(ausschnitt)
    return basis if treffer < 0 else basis + form.count("\n", 0, treffer)


def _ergebniswerte(text: str) -> list[tuple[int, str]] | None:
    """Die erste Spalte der Ergebnistabelle des Wartepunkts, mit Zeilennummer."""
    zeilen = text.split("\n")
    beginn = next((i for i, z in enumerate(zeilen) if z.startswith("| Ergebniswert |")), None)
    if beginn is None:
        return None
    werte: list[tuple[int, str]] = []
    for nummer, zeile in enumerate(zeilen[beginn + 2 :], start=beginn + 3):
        if not zeile.startswith("|"):
            break
        zelle = zeile.split("|")[1].strip()
        treffer = re.fullmatch(r"`([^`]+)`", zelle)
        werte.append((nummer, treffer.group(1) if treffer else zelle))
    return werte


def _warten(bestand: Bestand) -> list[Befund]:
    fehlend = [pfad for pfad in (WARTEN_PFAD, LESEN_PFAD) if pfad not in bestand]
    if fehlend:
        return [
            Befund(
                ort="Bestand",
                invariante="pruefstand-blockierend",
                text=f"{', '.join(fehlend)} fehlt - der Wartepunkt waere nicht pruefbar.",
            )
        ]
    warten_text = bestand[WARTEN_PFAD]
    lese_text = bestand[LESEN_PFAD]
    befunde: list[Befund] = []
    block = _abschnitt(warten_text, WARTEN)
    zeilen = [zeile for zeile in _befehle(block) if "--watch" in zeile]
    if len(zeilen) != 1:
        return [
            befund(
                WARTEN_PFAD,
                _zeile(warten_text, block),
                "pruefstand-blockierend",
                f"{len(zeilen)} blockierende Wartebefehle in `{WARTEN}` - erwartet genau einer.",
            )
        ]
    wartezeile = zeilen[0]
    ort = _zeile(warten_text, wartezeile)
    if not _ENDLICH.match(wartezeile):
        befunde.append(
            befund(
                WARTEN_PFAD,
                ort,
                "pruefstand-blockierend",
                f"kein endliches `timeout` vor dem Wartebefehl: {wartezeile!r}.",
            )
        )
    if "--required" in wartezeile:
        befunde.append(
            befund(
                WARTEN_PFAD,
                ort,
                "pruefstand-blockierend",
                "`--required` filtert auf erforderliche Checks, solange keine eingetragen sind.",
            )
        )
    if "|" in wartezeile:
        befunde.append(
            befund(
                WARTEN_PFAD,
                ort,
                "pruefstand-blockierend",
                f"der Wartebefehl laeuft durch eine Pipe: {wartezeile!r}.",
            )
        )

    # Genau ein blockierender Wartebefehl im **Katalog** - geprueft ueber alle Katalogdateien,
    # nicht nur ueber diese eine: Ein zweiter `--watch` waere der zweite Wartepunkt, den diese
    # Spec ausschliesst, und stuende in einer Datei, die dieser Waechter sonst nicht liest.
    wachen = [
        (datei, nummer)
        for datei in _katalogdateien(bestand)
        for nummer, zeile in enumerate(bestand[datei].split("\n"), start=1)
        if "--watch" in zeile
    ]
    for datei, nummer in wachen:
        if (datei, nummer) == (WARTEN_PFAD, ort):
            continue
        befunde.append(
            befund(
                datei,
                nummer,
                "pruefstand-blockierend",
                f"zweiter blockierender Wartebefehl im Katalog - `{WARTEN}` ist der eine "
                "Wartepunkt.",
            )
        )
    if not wachen:
        befunde.append(
            befund(
                WARTEN_PFAD,
                ort,
                "pruefstand-blockierend",
                f"keine Stelle im Katalog traegt `--watch` - `{WARTEN}` wartet nicht mehr.",
            )
        )

    werte = _ergebniswerte(warten_text)
    if werte is None:
        befunde.append(
            befund(
                WARTEN_PFAD,
                _zeile(warten_text, f"## `{WARTEN}`"),
                "pruefstand-blockierend",
                "die Ergebnistabelle des Wartepunkts fehlt.",
            )
        )
    else:
        for nummer, wert in werte:
            if wert in ERGEBNISWERTE:
                continue
            befunde.append(
                befund(
                    WARTEN_PFAD,
                    nummer,
                    "pruefstand-blockierend",
                    f"die Ergebnistabelle fuehrt den Wert {wert!r} - erlaubt sind genau "
                    f"{list(ERGEBNISWERTE)}.",
                )
            )
        fehlende = sorted(set(ERGEBNISWERTE) - {wert for _, wert in werte})
        if fehlende:
            befunde.append(
                befund(
                    WARTEN_PFAD,
                    werte[0][0] if werte else _zeile(warten_text, "| Ergebniswert |"),
                    "pruefstand-blockierend",
                    f"die Ergebnistabelle fuehrt {fehlende} nicht.",
                )
            )

    lesezeilen = _befehle(_abschnitt(lese_text, LESEN))
    if len(lesezeilen) != 1:
        befunde.append(
            befund(
                LESEN_PFAD,
                _zeile(lese_text, f"## `{LESEN}`"),
                "pruefstand-blockierend",
                f"{len(lesezeilen)} lesende Befehle in `{LESEN}` - erwartet genau einer.",
            )
        )
        return befunde
    leseort = _zeile(lese_text, lesezeilen[0])
    treffer = _JSON.search(lesezeilen[0])
    wert = treffer.group("wert") if treffer else ""
    if wert != FELDAUSWAHL:
        befunde.append(
            befund(
                LESEN_PFAD,
                leseort,
                "pruefstand-blockierend",
                f"die Feldauswahl der Lesezeile ist {wert!r} statt {FELDAUSWAHL!r}.",
            )
        )
    if "|" in lesezeilen[0]:
        befunde.append(
            befund(
                LESEN_PFAD,
                leseort,
                "pruefstand-blockierend",
                f"der lesende Befehl laeuft durch eine Pipe: {lesezeilen[0]!r}.",
            )
        )
    return befunde


def _anker(bestand: Bestand) -> list[Befund]:
    if ENTWICKLER not in bestand:
        return [
            Befund(
                ort="Bestand",
                invariante="anker-protokoll",
                text=f"{ENTWICKLER} fehlt - die Anker waeren nicht pruefbar.",
            )
        ]
    text = bestand[ENTWICKLER]
    zeilen = [zeile.strip() for zeile in text.split("\n")]
    befunde: list[Befund] = []
    for anker in ANKER:
        if zeilen.count(anker) == 1:
            continue
        kern = re.split(r" \(| außerhalb", anker)[0]
        befunde.append(
            befund(
                ENTWICKLER,
                _zeile(text, kern),
                "anker-protokoll",
                f"Anker {anker!r} ist {zeilen.count(anker)}-mal als Ueberschrift definiert - "
                "erwartet genau einmal.",
            )
        )
    return befunde


def _befundlesung(bestand: Bestand) -> list[Befund]:
    """Je Auslieferpfad: beide IDs je genau einmal, hinter dem Rundenblock, vor dem Bericht."""
    befunde: list[Befund] = []
    for pfad, (rundenmarke, bericht) in AUSLIEFERPFADE.items():
        if pfad not in bestand:
            befunde.append(
                Befund(
                    ort="Bestand",
                    invariante="befundlesung-einmal-je-pfad",
                    text=f"{pfad} fehlt - der Befundpfad waere nicht pruefbar.",
                )
            )
            continue
        text = bestand[pfad]
        lesemarke = _zeile(text, LESEMARKE)
        if LESEMARKE not in text:
            befunde.append(
                befund(
                    pfad,
                    1,
                    "befundlesung-einmal-je-pfad",
                    f"die Lesemarke {LESEMARKE!r} fehlt - ohne sie ist der Ort der Lesung nicht "
                    "messbar.",
                )
            )
            continue
        if text.count(rundenmarke) != 1:
            befunde.append(
                befund(
                    pfad,
                    lesemarke,
                    "befundlesung-einmal-je-pfad",
                    f"die Marke {rundenmarke!r} steht {text.count(rundenmarke)}-mal - erwartet "
                    "genau einmal; ohne sie ist der Rundenblock nicht abgrenzbar.",
                )
            )
            continue
        rundenblock = text.find(rundenmarke)
        bericht_start = text.find(bericht)
        if bericht_start == -1:
            befunde.append(
                befund(
                    pfad,
                    lesemarke,
                    "befundlesung-einmal-je-pfad",
                    f"die Berichtsueberschrift {bericht!r} fehlt.",
                )
            )
            continue
        for ident in BEFUND_OPERATIONEN:
            stellen = [treffer.start() for treffer in re.finditer(rf"`{ident}`", text)]
            if not stellen:
                befunde.append(
                    befund(
                        pfad,
                        lesemarke,
                        "befundlesung-einmal-je-pfad",
                        f"`{ident}` wird in diesem Pfad nicht aufgerufen.",
                    )
                )
                continue
            for stelle in stellen:
                if len(stellen) == 1 and rundenblock < stelle < bericht_start:
                    continue
                befunde.append(
                    befund(
                        pfad,
                        zeile_an(text, stelle),
                        "befundlesung-einmal-je-pfad",
                        f"`{ident}` steht hier zum {stellen.index(stelle) + 1}. von "
                        f"{len(stellen)} Mal - genau einmal je Lauf, hinter dem Rundenblock und "
                        "vor dem Bericht.",
                    )
                )
        berichtsabschnitt = text[bericht_start:]
        ende = berichtsabschnitt.find("\n## ")
        if ende != -1:
            berichtsabschnitt = berichtsabschnitt[:ende]
        if berichtsabschnitt.count(BEFUNDBLOCK) != 1:
            befunde.append(
                befund(
                    pfad,
                    zeile_an(text, bericht_start),
                    "befundlesung-einmal-je-pfad",
                    f"der Bericht nennt den Block {BEFUNDBLOCK!r} "
                    f"{berichtsabschnitt.count(BEFUNDBLOCK)}-mal - erwartet genau einmal.",
                )
            )
    return befunde


def _fangform_befunde(ident: str, pfad: str, basis: int, form: str) -> list[Befund]:
    """Die Form, die beide Befundbefehle gemeinsam tragen - die Fangform."""
    befunde: list[Befund] = []
    for teil, satz in (
        ("if out=$(", "stdout wird nicht gefangen, bevor es ausgegeben wird."),
        ("2>/dev/null); then", "stderr geht nicht nach `/dev/null` bzw. `then` fehlt."),
        ("printf '%s\\n' \"$out\"", "die Ausgabe geht nicht an eine feste Formatzeichenkette."),
        ("printf 'nicht festgestellt\\n'", "der Fehlerfall lautet nicht `nicht festgestellt`."),
    ):
        if teil not in form:
            befunde.append(befund(pfad, basis, "befundbefehle-verengt", f"{ident}: {satz}"))
    for maske in ("|| true", "|| :"):
        if maske in form:
            befunde.append(
                befund(
                    pfad,
                    _formzeile(form, basis, maske),
                    "befundbefehle-verengt",
                    f"{ident}: der Exit-Code wird maskiert ({maske!r}) - `nicht festgestellt` "
                    "entstuende nie.",
                )
            )
    return befunde


def _jq_befunde(ident: str, pfad: str, basis: int, form: str, programm: str) -> list[Befund]:
    """Die Verengung selbst: Herkunft offen, Menge ungekuerzt, Text gekuerzt und entschaerft."""
    befunde: list[Befund] = []
    anfang = _formzeile(form, basis, "def kurztext")
    if "[0:200]" not in programm:
        befunde.append(
            befund(
                pfad,
                anfang,
                "befundbefehle-verengt",
                f"{ident}: die Verengung kuerzt den Kurztext nicht auf 200 Codepoints.",
            )
        )
    for zeichen in ("\\p{Cc}", "\\p{Cf}"):
        if zeichen not in programm:
            befunde.append(
                befund(
                    pfad,
                    anfang,
                    "befundbefehle-verengt",
                    f"{ident}: die Verengung entfernt die Zeichenklasse {zeichen!r} nicht.",
                )
            )
    for treffer in _SLICE.finditer(programm):
        if treffer.group(0) == "[0:200]":
            continue
        befunde.append(
            befund(
                pfad,
                _formzeile(form, basis, treffer.group(0)),
                "befundbefehle-verengt",
                f"{ident}: die Verengung schneidet die Befundmenge ab ({treffer.group(0)}) - "
                "gefiltert wird ausschliesslich nach dem offenen Zustand.",
            )
        )
    for treffer in _SELECT.finditer(programm):
        if not _HERKUNFTSFELD.search(treffer.group("body")):
            continue
        befunde.append(
            befund(
                pfad,
                _formzeile(form, basis, treffer.group(0)),
                "befundbefehle-verengt",
                f"{ident}: die Auswahl filtert nach der Herkunft ({treffer.group(0)}) - kein "
                "Autor- und kein Werkzeugfilter.",
            )
        )
    return befunde


def _befundbefehle(bestand: Bestand) -> list[Befund]:
    """Je Befundlesung genau ein `gh`-Aufruf in der Fangform, verengt und herkunftsoffen."""
    befunde: list[Befund] = []
    for ident, pfad in BEFUND_PFADE.items():
        if pfad not in bestand:
            befunde.append(
                Befund(
                    ort="Bestand",
                    invariante="befundbefehle-verengt",
                    text=f"{pfad} fehlt - die Befundlesung waere nicht pruefbar.",
                )
            )
            continue
        text = bestand[pfad]
        block = _abschnitt(text, ident)
        form = _fangeform(block)
        if form is None:
            befunde.append(
                befund(
                    pfad,
                    _zeile(text, f"## `{ident}`"),
                    "befundbefehle-verengt",
                    f"{ident}: keine Fangform - der Fehlerfall ginge ungefiltert in den Kontext.",
                )
            )
            continue
        basis = _zeile(text, form)
        befunde.extend(_fangform_befunde(ident, pfad, basis, form))
        aufrufe = [zeile for zeile in form.split("\n") if "gh api" in zeile]
        if len(aufrufe) != 1:
            befunde.append(
                befund(
                    pfad,
                    basis,
                    "befundbefehle-verengt",
                    f"{ident}: {len(aufrufe)} `gh api`-Aufrufe im Befehlsblock - erwartet genau "
                    "einer.",
                )
            )
        programm = _jq_programm(form)
        if programm is None:
            befunde.append(
                befund(
                    pfad,
                    basis,
                    "befundbefehle-verengt",
                    f"{ident}: kein `--jq`-Ausdruck - der Freitext erreichte den Kontext "
                    "ungekuerzt.",
                )
            )
            continue
        befunde.extend(_jq_befunde(ident, pfad, basis, form, programm))
        if ident == "pr-reviewbefunde-lesen":
            if "gh api graphql" not in form:
                befunde.append(
                    befund(
                        pfad,
                        basis,
                        "befundbefehle-verengt",
                        f"{ident}: der Aufruf lautet nicht exakt `gh api graphql`.",
                    )
                )
            if "-f query='" not in form:
                befunde.append(
                    befund(
                        pfad,
                        basis,
                        "befundbefehle-verengt",
                        f"{ident}: die Query steht nicht als Literal in einfachen "
                        "Anfuehrungszeichen.",
                    )
                )
            if form.count("-F ") != 1 or "-F number=<MMM>" not in form:
                befunde.append(
                    befund(
                        pfad,
                        basis,
                        "befundbefehle-verengt",
                        f"{ident}: die Nummer geht nicht ausschliesslich als typisierte Variable "
                        "`-F number=` hinein.",
                    )
                )
            for marke in ("first: 100", "totalCount"):
                if form.count(marke) < 2:
                    befunde.append(
                        befund(
                            pfad,
                            basis,
                            "befundbefehle-verengt",
                            f"{ident}: {marke!r} steht nicht in beiden Verbindungen - die "
                            "Vollstaendigkeit waere nicht entscheidbar.",
                        )
                    )
        else:
            for marke in ("--paginate", "pr=<MMM>", "state=open"):
                if marke not in form:
                    befunde.append(
                        befund(
                            pfad,
                            basis,
                            "befundbefehle-verengt",
                            f"{ident}: {marke!r} fehlt im Aufruf.",
                        )
                    )
    return befunde


def _schreibwege(bestand: Bestand) -> list[Befund]:
    """Rein lesend: keine Methode, kein Body, keine Datei- oder Pipe-Ausgabe."""
    befunde: list[Befund] = []
    for ident, pfad in BEFUND_PFADE.items():
        if pfad not in bestand:
            continue
        text = bestand[pfad]
        form = _fangeform(_abschnitt(text, ident)) or ""
        basis = _zeile(text, form)
        # Platzhalter wie `<MMM>` tragen spitze Klammern und sind keine Umleitung; die beiden
        # gewollten Umleitungen nach `/dev/null` sind Teil der Fangform.
        ohne_platzhalter = re.sub(r"<[^>]*>", "", form)
        for muster in ("-X ", "--method", "--input", "--body", "--field", "tee ", ">>"):
            if muster in ohne_platzhalter:
                befunde.append(
                    befund(
                        pfad,
                        _formzeile(ohne_platzhalter, basis, muster),
                        "befund-kein-schreibweg",
                        f"{ident}: Schreibform {muster!r} im lesenden Aufruf.",
                    )
                )
        reste = ohne_platzhalter.replace("2>/dev/null", "").replace(">/dev/null", "")
        if ">" in reste:
            befunde.append(
                befund(
                    pfad,
                    _formzeile(reste, basis, ">"),
                    "befund-kein-schreibweg",
                    f"{ident}: die Ausgabe wird in eine Datei umgeleitet - der Befund gehoert "
                    "nirgends dauerhaft abgelegt.",
                )
            )
    return befunde


def _definitionen(bestand: Bestand, kopf: str) -> list[tuple[str, int]]:
    """Die Zeilen, an denen `kopf` **in einem umzaeunten Block** steht."""
    stellen: list[tuple[str, int]] = []
    for datei in sorted(bestand):
        if not any(datei == ort or datei.startswith(f"{ort}/") for ort in ANWEISUNGSRAUM):
            continue
        im_zaun = False
        for nummer, zeile in enumerate(bestand[datei].split("\n"), start=1):
            if zeile.startswith(_ZAUN):
                im_zaun = not im_zaun
            elif im_zaun and zeile.strip() == kopf:
                stellen.append((datei, nummer))
    return stellen


def _blockinhalt(text: str, kopfzeile: int) -> str:
    """Der Inhalt des Zaunblocks um die Kopfzeile, ohne die Zaeune."""
    zeilen = text.split("\n")
    oben = kopfzeile - 1
    while oben >= 1 and not zeilen[oben - 1].startswith(_ZAUN):
        oben -= 1
    unten = kopfzeile
    while unten < len(zeilen) and not zeilen[unten].startswith(_ZAUN):
        unten += 1
    return "\n".join(zeilen[oben:unten])


def _berichtbloecke(bestand: Bestand) -> list[Befund]:
    """Beide Berichtsbloecke je genau einmal; der Befundstand ein geschlossener Dreiklang."""
    befunde: list[Befund] = []
    for kopf, was in ((CIBLOCK, "CI-Ergebnis"), (BEFUNDBLOCK, "Befundblock")):
        stellen = _definitionen(bestand, kopf)
        if not stellen:
            befunde.append(
                Befund(
                    ort="Bestand",
                    invariante="berichtblock-einmal",
                    text=f"der {was} {kopf!r} ist nirgends definiert.",
                )
            )
            continue
        for datei, nummer in stellen:
            if len(stellen) == 1:
                continue
            befunde.append(
                befund(
                    datei,
                    nummer,
                    "berichtblock-einmal",
                    f"der {was} {kopf!r} ist {len(stellen)}-mal definiert - erwartet genau einmal.",
                )
            )
    befundbloecke = _definitionen(bestand, BEFUNDBLOCK)
    if len(befundbloecke) != 1:
        return befunde
    datei, nummer = befundbloecke[0]
    inhalt = _blockinhalt(bestand[datei], nummer)
    zeilen = inhalt.split("\n")
    stand = [i for i, zeile in enumerate(zeilen) if zeile.startswith("**Befundstand:**")]
    if len(stand) != 1:
        befunde.append(
            befund(
                datei,
                nummer,
                "berichtblock-einmal",
                f"der Befundblock fuehrt {len(stand)} Befundstand-Zeilen - erwartet genau eine.",
            )
        )
    else:
        klammer = re.search(r"<([^>]*)>", zeilen[stand[0]])
        werte = [teil.strip() for teil in klammer.group(1).split("|")] if klammer else []
        if sorted(werte) != sorted(BEFUNDSTAENDE):
            befunde.append(
                befund(
                    datei,
                    nummer + stand[0],
                    "berichtblock-einmal",
                    f"der Befundstand fuehrt {werte}, erwartet genau {list(BEFUNDSTAENDE)}.",
                )
            )
    for wert in ERGEBNISWERTE:
        for i, zeile in enumerate(zeilen):
            if not re.search(rf"\b{wert}\b", zeile):
                continue
            befunde.append(
                befund(
                    datei,
                    nummer + i,
                    "berichtblock-einmal",
                    f"der Befundblock traegt den Check-Ergebniswert {wert!r}.",
                )
            )
    return befunde


def pruefe(bestand: Bestand) -> list[Befund]:
    """Alle Aussagen des Wartepunkts ueber einem Bestand."""
    return (
        _warten(bestand)
        + _anker(bestand)
        + _befundlesung(bestand)
        + _befundbefehle(bestand)
        + _schreibwege(bestand)
        + _berichtbloecke(bestand)
    )


def test_der_bestand_wartet_blockierend_und_endlich() -> None:
    """Der lebende Bestand haelt alle Invarianten; Verletzungen belegt `mutationen.py`."""
    befunde = pruefe(Bestand.aus_arbeitsbaum())

    assert not befunde, "Wartepunkt-Befunde: " + "; ".join(f.meldung for f in befunde)


# --- Der ausfuehrende Pruefer: das `--jq`-Literale gegen Fixtures ---------------------------


def _programm(ident: str) -> str:
    """Der `--jq`-Ausdruck der Operation - gelesen aus der Datei, nie im Test nachgebaut."""
    pfad = BEFUND_PFADE[ident]
    form = _fangeform(_abschnitt(Bestand.aus_arbeitsbaum()[pfad], ident))
    assert form is not None, f"{pfad}: keine Fangform gefunden."
    programm = _jq_programm(form)
    assert programm is not None, f"{pfad}: kein `--jq`-Ausdruck gefunden."
    return programm


def _ausfuehren(programm: str, dokument: object) -> list[dict[str, object]]:
    """Das Literal gegen ein Dokument; fehlt `jq`, scheitert der Test laut statt zu skippen."""
    ergebnis = subprocess.run(
        ["jq", "-r", programm],
        input=json.dumps(dokument),
        capture_output=True,
        text=True,
        check=True,
    )
    return [json.loads(zeile) for zeile in ergebnis.stdout.split("\n") if zeile.strip()]


def _review(threads: list[dict[str, object]], reviews: list[dict[str, object]]) -> dict:
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {"totalCount": len(threads), "nodes": threads},
                    "latestOpinionatedReviews": {"totalCount": len(reviews), "nodes": reviews},
                }
            }
        }
    }


def _thread(
    *,
    path: str = "backend/src/a.py",
    line: int | None = 12,
    autor: str = "copilot-pull-request-reviewer",
    text: str = "ein Befund",
    aufgeloest: bool = False,
    veraltet: bool = False,
) -> dict[str, object]:
    return {
        "isResolved": aufgeloest,
        "isOutdated": veraltet,
        "comments": {
            "nodes": [
                {
                    "path": path,
                    "line": line,
                    "url": "https://example.invalid/thread",
                    "author": {"login": autor},
                    "bodyText": text,
                }
            ]
        },
    }


def _reviewstand(
    *, autor: str = "copilot-pull-request-reviewer", zustand: str = "CHANGES_REQUESTED"
) -> dict[str, object]:
    return {
        "state": zustand,
        "url": "https://example.invalid/review",
        "author": {"login": autor},
        "bodyText": "bitte ändern",
    }


def _review_ausgabe(dokument: object) -> tuple[list[dict[str, object]], dict[str, object]]:
    ausgabe = _ausfuehren(_programm("pr-reviewbefunde-lesen"), dokument)
    return ausgabe[:-1], ausgabe[-1]


def _scan_ausgabe(dokument: object) -> list[dict[str, object]]:
    return _ausfuehren(_programm("pr-scanbefunde-lesen"), dokument)


def _alert(
    *,
    nummer: int = 7,
    zustand: str = "open",
    werkzeug: str = "CodeQL",
    stufe: str | None = "medium",
    regel: str = "Uncontrolled data used in path expression",
    meldung: str | None = "Path injection",
    pfad: str | None = "backend/src/x.py",
    zeile: int | None = 42,
) -> dict[str, object]:
    """Ein Code-Scanning-Alert in der Form des REST-Endpunkts."""
    instance: dict[str, object] = {"location": {"path": pfad, "start_line": zeile}}
    if meldung is not None:
        instance["message"] = {"text": meldung}
    return {
        "number": nummer,
        "state": zustand,
        "tool": {"name": werkzeug},
        "rule": {"description": regel, "security_severity_level": stufe},
        "most_recent_instance": instance,
        "html_url": f"https://example.invalid/alert/{nummer}",
    }


def test_der_kurztext_entsteht_mechanisch_im_jq() -> None:
    """200 Codepoints, Zeilentrenner als Leerzeichen, `Cf` entfernt, Leerraum gefaltet."""
    grenze = "x" * 199 + "😀" + "y"
    befunde, _ = _review_ausgabe(
        _review(
            [
                _thread(text="Zeile1\nZeile2\u0007\u200e  ok"),
                _thread(text=grenze),
                _thread(text="\u0007\u0000"),
            ],
            [],
        )
    )

    assert [befund["text"] for befund in befunde] == [
        "Zeile1 Zeile2 ok",
        "x" * 199 + "😀",
        "Befund ohne darstellbaren Text",
    ]


def test_nur_offene_befunde_erscheinen() -> None:
    """Aufgeloester Thread und `APPROVED`/`DISMISSED` fehlen; `CHANGES_REQUESTED` erscheint."""
    befunde, summe = _review_ausgabe(
        _review(
            [
                _thread(aufgeloest=True, text="erledigt"),
                _thread(veraltet=True, autor="github-advanced-security[bot]"),
                _thread(autor="TheRealKoller", text="eigener Befund"),
            ],
            [
                _reviewstand(),
                _reviewstand(autor="zweitgutachter"),
                _reviewstand(zustand="APPROVED"),
                _reviewstand(zustand="DISMISSED"),
            ],
        )
    )

    assert sorted({befund["herkunft"] for befund in befunde}) == [
        "TheRealKoller",
        "copilot-pull-request-reviewer",
        "github-advanced-security[bot]",
        "zweitgutachter",
    ]
    veraltet = [befund for befund in befunde if befund["veraltet"]]
    assert [befund["herkunft"] for befund in veraltet] == ["github-advanced-security[bot]"]
    assert summe == {
        "threads": 2,
        "threadsGelesen": 3,
        "threadsGesamt": 3,
        "reviews": 2,
        "reviewsGelesen": 4,
        "reviewsGesamt": 4,
    }


def test_eine_fehlende_zeilennummer_bleibt_ein_befund() -> None:
    befunde, _ = _review_ausgabe(_review([_thread(line=None)], []))

    assert len(befunde) == 1
    assert befunde[0]["zeile"] is None
    assert befunde[0]["pfad"] == "backend/src/a.py"


def test_hundert_knoten_bei_totalcount_101_erscheinen_vollstaendig() -> None:
    """Das `--jq` schneidet die Menge nicht ab; die Vollstaendigkeit entscheidet `totalCount`."""
    threads = [_thread(path=f"datei-{nummer}.py") for nummer in range(100)]
    dokument = _review(threads, [])
    dokument["data"]["repository"]["pullRequest"]["reviewThreads"]["totalCount"] = 101

    befunde, summe = _review_ausgabe(dokument)

    assert len(befunde) == 100
    assert summe == {
        "threads": 100,
        "threadsGelesen": 100,
        "threadsGesamt": 101,
        "reviews": 0,
        "reviewsGelesen": 0,
        "reviewsGesamt": 0,
    }


def test_ein_aufgeloester_thread_haelt_den_totalcount_hoch_und_bleibt_vollstaendig() -> None:
    """Der Ausgangsfall: `totalCount` zaehlt auch, was die Verengung zu Recht verwirft."""
    befunde, summe = _review_ausgabe(
        _review(
            [_thread(text="offen"), _thread(aufgeloest=True, text="erledigt")],
            [_reviewstand(zustand="APPROVED")],
        )
    )

    assert [befund["text"] for befund in befunde] == ["offen"]
    assert summe["threads"] == 1
    assert summe["threadsGelesen"] == summe["threadsGesamt"] == 2
    assert summe["reviews"] == 0
    assert summe["reviewsGelesen"] == summe["reviewsGesamt"] == 1


def test_scanbefunde_offen_stufe_und_fallbackkette() -> None:
    befunde = _scan_ausgabe(
        [
            _alert(),
            _alert(nummer=8, zustand="fixed", meldung="weg"),
            _alert(nummer=9, werkzeug="Semgrep", stufe=None, meldung=None, regel="Nur Regeltext"),
        ]
    )

    assert [befund["number"] for befund in befunde] == [7, 9]
    assert [befund["tool"] for befund in befunde] == ["CodeQL", "Semgrep"]
    assert [befund["stufe"] for befund in befunde] == ["medium", None]
    assert [befund["text"] for befund in befunde] == ["Path injection", "Nur Regeltext"]


def test_scanbefunde_mit_unterdrueckter_meldung_bleiben_sichtbar() -> None:
    """Ein Befund ohne darstellbaren Text erscheint mit dem festen Ersatztext und Fundstelle."""
    alert = _alert(meldung="\u0007\u200b", regel="")
    alert["most_recent_instance"] = {"location": {"path": None, "start_line": None}}

    befunde = _scan_ausgabe([alert])

    assert len(befunde) == 1
    assert befunde[0]["text"] == "Befund ohne darstellbaren Text"
    assert befunde[0]["pfad"] is None


def test_scanbefund_regeltext_erscheint_nur_gekuerzt_als_text() -> None:
    """`rule.description` ist Quelle, kein Ausgabefeld; `pfad`/`tool` tragen keine Steuerzeichen."""
    regel = "R" * 150 + "\u0007\u200e" + "R" * 150
    alert = _alert(meldung=None, regel=regel, werkzeug="Code\u200eQL", pfad="backend/\u200ex.py")

    befunde = _scan_ausgabe([alert])

    assert len(befunde) == 1
    eintrag = befunde[0]
    assert "regel" not in eintrag
    assert eintrag["text"] == "R" * 150 + " " + "R" * 49
    assert len(str(eintrag["text"])) == 200
    assert eintrag["tool"] == "CodeQL"
    assert eintrag["pfad"] == "backend/x.py"


def test_die_verengung_wird_je_seite_angewandt() -> None:
    """`--paginate --jq` wertet je Seite aus: zwei Seiten ergeben beide Mengen, nichts zaehlt neu."""
    erste = _scan_ausgabe([_alert(nummer=1), _alert(nummer=2)])
    zweite = _scan_ausgabe([_alert(nummer=3)])

    assert [befund["number"] for befund in erste] == [1, 2]
    assert [befund["number"] for befunde in (erste, zweite) for befund in befunde] == [1, 2, 3]
