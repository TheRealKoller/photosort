"""Operationskatalog: geschlossene Menge, eine Definitionsstelle, belegte Wege, freie Ablage.

Prüfgegenstand ist ein `Bestand` (Abbild `pfad → text`) aus `.claude/**`, `docs/**` und `CLAUDE.md`.
Die Ablage ist frei: Die Operationen dürfen auf mehrere Dokumente verteilt werden, in beliebiger
Reihenfolge und unter beliebigen Abschnittsnamen. Eine Operation ist **definiert** durch eine
Überschrift, deren Text mit ihrer ID in Backticks beginnt (jede Ebene `##` bis `######`); ihr Block
reicht bis zur nächsten Überschrift gleicher oder höherer Ebene. Das ist die einzige verbleibende
Konvention dieser Prüfung (ADR 0148, Bilanz).

Jede Invariante trägt ihren Satz in `INVARIANTEN`; jeder Befund nennt `datei:zeile` und die
verletzte Invariante. Die Fehlererkennung belegen Mutationen (`mutationen.py`), nicht Negativtests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from waechter import Befund, Bestand, Invariante, befund, ueberschriften

SUCHRAUM = (".claude", "docs", "CLAUDE.md")

# Abwesenheits- und Messbegriffsscans lesen nur den Anweisungsraum; `docs/` ist Setup-Doku und
# nennt `gh`-Befehle legitim.
ANWEISUNGSRAUM = (".claude", "CLAUDE.md")

# Die 21 Operations-IDs als geschlossene Menge - 17 aus ADR 0061, Abschnitt 2, dazu
# `issue-bereich-setzen` und `issue-liste-lesen` aus ADR 0085 sowie zwei Prüfstand-Operationen aus
# ADR 0092. Die Menge selbst *ist* die Zusage ("keine heute vorhandene Operation geht verloren").
ERWARTETE_OPERATIONEN = frozenset(
    {
        "issue-anlegen",
        "issue-lesen",
        "issue-liste-lesen",
        "issue-bereich-setzen",
        "issue-body-schreiben",
        "issue-titel-schreiben",
        "issue-kommentieren",
        "issue-verwerfen",
        "pr-erstellen",
        "pr-body-schreiben",
        "pr-verknuepfung-lesen",
        "pr-pruefstand-abwarten",
        "pr-pruefstand-lesen",
        "copilot-review-anfordern",
        "pr-reviewstand-lesen",
        "pr-reviewkommentare-lesen",
        "pr-reviewkommentar-beantworten",
        "board-aufnahme",
        "board-status-setzen",
        "board-prioritaet-setzen",
        "board-status-und-prioritaet-lesen",
    }
)

# Projects (V2) spricht ausschließlich GraphQL; MCP bietet dafür keine Operation. Diese vier haben
# deshalb genau einen Weg.
BOARD_OPERATIONEN = frozenset(
    {
        "board-aufnahme",
        "board-status-setzen",
        "board-prioritaet-setzen",
        "board-status-und-prioritaet-lesen",
    }
)

# Alle lesenden Operationen. `pr-pruefstand-abwarten` gehört dazu, obwohl seine Auswertungsgrenze
# **leer** ist: aus dem blockierenden Aufruf gelangt nichts in Kontext oder Protokoll.
LESENDE_OPERATIONEN = frozenset(
    {
        "issue-lesen",
        "issue-liste-lesen",
        "pr-verknuepfung-lesen",
        "pr-pruefstand-abwarten",
        "pr-pruefstand-lesen",
        "pr-reviewstand-lesen",
        "pr-reviewkommentare-lesen",
        "board-status-und-prioritaet-lesen",
    }
)

# Die exakte Feldmenge bleibt nur dort, wo sie die Sicherheitszusage selbst ist. `issue-liste-lesen`:
# `title` entfällt, weil es das einzige fremdbeschreibbare Feld ist; `author` muss da sein, weil die
# Markierung fremder Autorschaft vor dem Stapelschreiben daran hängt. `pr-pruefstand-lesen`: `bucket`
# und `state` steuern, `name` und `workflow` sind fremdbeschreibbar und nur Anzeigewerte.
ERWARTETE_AUSWERTUNGSGRENZE: dict[str, tuple[str, ...]] = {
    "issue-liste-lesen": ("number", "labels", "state", "author"),
    "pr-pruefstand-abwarten": (),
    "pr-pruefstand-lesen": ("bucket", "name", "state", "workflow"),
}

# Schwacher Wächter gegen die Rückkehr der Vorabmessung - bewusst enumeriert, kein freier Wortscan.
MESSBEGRIFFE = (
    "gh auth status",  # Probe-Aufruf, dessen einziger Zweck die Vorabmessung ist
    "gh api rate_limit",  # "antwortet GitHub überhaupt?" - dasselbe unter anderem Namen
    "CODESPACES",  # Schluss von einem Umgebungsmerkmal auf eine "Session-Art"
    "GITHUB_ACTIONS",  # dito
    "GH_TOKEN",  # dito, plus: eine Token-Variable gehört nirgends in eine Anweisung
)

# Die Stufe ist ein geschlossener Wert; der Satz daneben ist frei.
STUFE_MARKER = "**GitHub-Erlaubnisstufe:**"
STUFEN = frozenset({"schreibend", "lesend", "keins"})

# Deklarierte Erwartungstabelle. Sie ist eine **Entscheidung** und wird bei Änderung bewusst
# nachgezogen, nicht abgeleitet: Ein neu angelegter Skill wird sonst rot, bis jemand ihn einstuft.
ERWARTETE_STUFEN: dict[str, str] = {
    ".claude/agents/architect.md": "keins",
    ".claude/agents/developer.md": "keins",
    ".claude/agents/requirements-engineer.md": "keins",
    ".claude/agents/research-engineer.md": "keins",
    ".claude/agents/security-engineer.md": "keins",
    ".claude/agents/test-engineer.md": "keins",
    ".claude/agents/ux-ui-designer.md": "keins",
    ".claude/skills/browse-app/SKILL.md": "keins",
    ".claude/skills/capture/SKILL.md": "schreibend",
    ".claude/skills/design-system/SKILL.md": "keins",
    ".claude/skills/github-access/SKILL.md": "schreibend",
    ".claude/skills/laufstand/SKILL.md": "keins",
    ".claude/skills/penpot-design/SKILL.md": "keins",
    ".claude/skills/penpot-entwurfsrunden/SKILL.md": "keins",
    ".claude/skills/produktentscheidung/SKILL.md": "keins",
    ".claude/skills/refinement/SKILL.md": "schreibend",
    ".claude/skills/review-architecture/SKILL.md": "keins",
    ".claude/skills/review-requirements/SKILL.md": "keins",
    ".claude/skills/review-security/SKILL.md": "keins",
    ".claude/skills/review-tests/SKILL.md": "keins",
    ".claude/skills/review-ux/SKILL.md": "keins",
    ".claude/skills/review/SKILL.md": "lesend",
    ".claude/skills/ship-entwurf/SKILL.md": "schreibend",
    ".claude/skills/ship-feature/SKILL.md": "schreibend",
    ".claude/skills/skiller/SKILL.md": "keins",
    ".claude/skills/spec-writer/SKILL.md": "schreibend",
    ".claude/skills/story-entwurf/SKILL.md": "schreibend",
}

WEGE_VOKABULAR = frozenset({"mcp", "gh"})
REMOTE_MARKIERUNG = "remote auf keinem Weg erreichbar"
WEGE_ZEILE = re.compile(r"^\*\*Wege:\*\*(?P<rest>[^\n]*)$", re.MULTILINE)
WEG_TOKEN = re.compile(r"`([a-z]+)`")
AUSWERTUNGSGRENZE = "**Auswertungsgrenze:**"
BACKTICK_TOKEN = re.compile(r"`([^`\n]+)`")
FELDTRENNER = "—"

# Erkennungsraum der Operations-IDs sind die vier geschlossenen Präfixe: `review-tests`,
# `ship-feature` oder `body-file` sind keine Operationen.
ID_VERWENDUNG = re.compile(r"`((?:issue|board|pr|copilot)-[a-z][a-z-]*)`")

GH_ZEILE = re.compile(r"^(?:timeout \d+ )?gh [a-z][a-z-]*\b")
GH_IRGENDWO = re.compile(r"\bgh (?P<unterbefehl>[a-z][a-z-]*)")
MCP_NAME = re.compile(r"mcp__github__[a-z_]*")

# Die MCP-Werkzeugnamen sind für die meisten Operationen bewusst nicht notiert; der Block belegt
# seinen `mcp`-Weg dann über diese eigene Zeile, die die Wegleiter liest.
MCP_ZEILE = "**`mcp`:**"
# Ein Abschnittszitat zählt nur auf einer Zeile, die ein katalogtragendes Dokument **nennt** -
# sonst fänge der Scan jedes beliebige Abschnittszitat einer anderen Datei mit ein.
ABSCHNITTS_ZITAT = re.compile(r"(?:Abschnitt|unter)\s+[„\"](?P<titel>[^„\"“”]+)[“\"]")

DEFINITION = re.compile(r"^(?P<ebene>#{2,6})[ \t]+`(?P<id>[a-z][a-z0-9-]*)`")

# Der Ablauf findet eine Operation über die Übersicht in `SKILL.md`; die Zeile nennt Kennung,
# Zweck und die Datei, die ihre Einzelheiten trägt.
KATALOG_UEBERSICHT = ".claude/skills/github-access/SKILL.md"
UEBERSICHTSZEILE = re.compile(
    r"^\| `(?P<id>[a-z][a-z0-9-]*)` \|[^\n]*\| "
    r"\[`operationen/(?P<datei>[a-z0-9-]+)\.md`\]\(operationen/[a-z0-9-]+\.md\)",
    re.MULTILINE,
)

# Die benannte Ausnahme: die einzige Operation, die Fremdtext aus Kommentaren liest.
KOMMENTAR_AUSNAHME = "pr-reviewkommentare-lesen"
# Der Antwort-Endpunkt fuehrt bauartbedingt durch `/comments` - er schreibt in einen bestehenden
# Thread und holt keinen Fremdtext herein. Er ist die einzige Form, die von der Pfadpruefung
# ausgenommen ist; jede andere `/comments`-Stelle bleibt ein Befund.
KOMMENTAR_ANTWORT = re.compile(r"/comments/<KOMMENTAR-ID>/replies\b")
KOMMENTAR_PFAD = re.compile(r"/comments\b")

INVARIANTEN = (
    Invariante(
        "katalog-geschlossen",
        "Die definierten IDs sind genau die erwarteten 21 - keine fehlt, keine kommt dazu, keine "
        "doppelt.",
    ),
    Invariante(
        "uebersicht-vollstaendig",
        "Die Übersicht in `SKILL.md` nennt jede definierte Operation und verweist auf genau ihre "
        "Datei; keine Zeile zeigt auf eine nicht definierte oder fremde Operation.",
    ),
    Invariante("wege-geschlossen", "Je Operation 1..n Wege aus {mcp, gh}, ohne Dopplung."),
    Invariante(
        "wege-belegt",
        "Jeder deklarierte Weg ist im Block belegt (`mcp__github__…` bzw. eine "
        "`gh <unterbefehl>`-Zeile) und jeder belegte Weg ist deklariert.",
    ),
    Invariante(
        "wege-board",
        "Die vier Board-Operationen nennen genau `gh` und tragen „remote auf keinem Weg "
        "erreichbar“.",
    ),
    Invariante("ziel-literal", "Jeder Block nennt `TheRealKoller` und `photosort` als Literal."),
    Invariante(
        "lesende-grenze",
        "Jede lesende Operation nennt ihre ausgewerteten Felder; die exakte Feldmenge gilt für "
        "die beiden Sicherheitszusagen, für `pr-pruefstand-abwarten` ist sie leer.",
    ),
    Invariante(
        "verweis-abschnitt",
        "Jeder Verweis `Abschnitt „…“` trifft eine existierende Überschrift im Bestand.",
    ),
    Invariante("id-verwendung", "Jede verwendete Operations-ID ist definiert."),
    Invariante(
        "zugriff-nur-im-katalog",
        "Kein `gh`-Befehl und kein `mcp__github__`-Name außerhalb des Katalogs - des Skills "
        "`github-access` samt seinen Operationsdateien.",
    ),
    Invariante("messbegriffe", "Kein enumerierter Messbegriff im Anweisungsraum."),
    Invariante(
        "erlaubnisstufe",
        "Je Skill-/Agenten-Datei genau eine Erlaubnisstufe als geschlossener Wert "
        "(schreibend, lesend, keins).",
    ),
    Invariante(
        "kommentar-pfad",
        "Keine Operation liest Issue-Kommentare außer der benannten PR-Ausnahme; keine "
        "Auswertungsgrenze nennt ein Kommentarfeld und keine Aufrufzeile einen "
        "`/comments`-Pfad außerhalb dieser Ausnahme und des Antwort-Endpunkts "
        "`/comments/<KOMMENTAR-ID>/replies`, der in einen bestehenden Thread schreibt.",
    ),
)

INVARIANTEN_NACH_ID = {invariante.id: invariante for invariante in INVARIANTEN}


@dataclass(frozen=True)
class Eintrag:
    """Eine Definitionsstelle: ID, Datei, Zeile der Überschrift und die Zeilen ihres Blocks."""

    id: str
    datei: str
    zeile: int
    block: tuple[tuple[int, str], ...]

    @property
    def text(self) -> str:
        return "\n".join(zeile for _, zeile in self.block)


def finde_zeile(eintrag: Eintrag, muster: re.Pattern[str]) -> tuple[int, re.Match[str]] | None:
    """Die erste Blockzeile, auf die `muster` passt, mit ihrer Zeilennummer."""
    for nummer, zeile in eintrag.block:
        treffer = muster.search(zeile)
        if treffer:
            return nummer, treffer
    return None


def eintraege(bestand: Bestand) -> list[Eintrag]:
    """Alle Definitionsstellen im Suchraum, in Datei- und Zeilenreihenfolge."""
    gefunden: list[Eintrag] = []
    for datei in sorted(bestand):
        if not _im_suchraum(datei):
            continue
        zeilen = bestand[datei].split("\n")
        koepfe = {nummer: (ebene, titel) for nummer, ebene, titel in ueberschriften(bestand[datei])}
        for nummer in sorted(koepfe):
            ebene, titel = koepfe[nummer]
            treffer = DEFINITION.match("#" * ebene + " " + titel)
            if not treffer:
                continue
            block: list[tuple[int, str]] = []
            for folge in range(nummer, len(zeilen) + 1):
                if folge > nummer and folge in koepfe and koepfe[folge][0] <= ebene:
                    break
                block.append((folge, zeilen[folge - 1]))
            gefunden.append(
                Eintrag(id=treffer.group("id"), datei=datei, zeile=nummer, block=tuple(block))
            )
    return gefunden


def _im_suchraum(datei: str) -> bool:
    return any(datei == ort or datei.startswith(f"{ort}/") for ort in SUCHRAUM)


def _im_anweisungsraum(datei: str) -> bool:
    return any(datei == ort or datei.startswith(f"{ort}/") for ort in ANWEISUNGSRAUM)


def _ist_skill_oder_agent(datei: str) -> bool:
    return datei.endswith("/SKILL.md") or datei.startswith(".claude/agents/")


KATALOG_SKILL = ".claude/skills/github-access"


def katalogdateien(stellen: list[Eintrag]) -> set[str]:
    """Die Dateien, die mindestens eine Operation definieren."""
    return {eintrag.datei for eintrag in stellen}


def _ist_im_katalog(datei: str) -> bool:
    """Jede Datei des Katalogs - Übersicht wie Operationsdatei - darf GitHub-Aufrufe führen."""
    return datei == KATALOG_SKILL or datei.startswith(f"{KATALOG_SKILL}/")


def _katalognamen(dateien: set[str]) -> set[str]:
    """Namen, unter denen ein Text ein katalogtragendes Dokument nennen kann.

    Der ganze Pfad und ein eindeutiger Dateiname zählen immer; der Verzeichnisname nur, solange er
    nicht generisch ist (`docs`). Sonst träfe jeder Satz, der irgendeine Datei unter `docs/` nennt,
    ein Zitat, das gar nicht auf den Katalog zeigt. Der Skillname `github-access` zählt immer,
    auch wenn viele Dateien darunter liegen - andere Dateien nennen den Katalog so.
    """
    namen = set(dateien)
    dateinamen: dict[str, list[str]] = {}
    verzeichnisse: dict[str, list[str]] = {}
    for datei in dateien:
        teile = datei.split("/")
        dateinamen.setdefault(teile[-1], []).append(datei)
        if len(teile) > 1:
            verzeichnisse.setdefault(teile[-2], []).append(datei)
        if len(teile) > 2 and teile[:2] == [".claude", "skills"]:
            namen.add(teile[2])
    namen.update(name for name, pfade in dateinamen.items() if len(pfade) == 1)
    namen.update(
        name
        for name, pfade in verzeichnisse.items()
        if len(pfade) == 1 and name not in {"docs", "specs"}
    )
    return namen


def _gedankenstrich_felder(rest: str) -> tuple[str, ...] | None:
    """Die Felder vor dem Gedankenstrich; `None`, wenn die Grenzzeile ihre Form nicht traegt."""
    if FELDTRENNER not in rest:
        return None
    return tuple(BACKTICK_TOKEN.findall(rest.split(FELDTRENNER, 1)[0]))


def grenzzeile(eintrag: Eintrag) -> tuple[int, tuple[str, ...] | None] | None:
    """Zeilennummer und Feldmenge der Auswertungsgrenze; `None`, wenn die Zeile fehlt.

    Die Grenzzeile darf umbrechen - der Gedankenstrich steht dann auf einer Folgezeile. Gelesen
    wird bis zum Gedankenstrich oder bis zur naechsten Markerzeile.
    """
    for index, (nummer, zeile) in enumerate(eintrag.block):
        if not zeile.startswith(AUSWERTUNGSGRENZE):
            continue
        rest = zeile[len(AUSWERTUNGSGRENZE) :]
        folge = index + 1
        while FELDTRENNER not in rest and folge < len(eintrag.block):
            naechste = eintrag.block[folge][1]
            if not naechste.strip() or naechste.startswith("**"):
                break
            rest += " " + naechste
            folge += 1
        return nummer, _gedankenstrich_felder(rest)
    return None


def pruefe(bestand: Bestand) -> list[Befund]:
    """Alle Invarianten des Katalogs über einem Bestand - die eine Funktion des Wächters."""
    stellen = eintraege(bestand)
    katalog = katalogdateien(stellen)
    if not katalog:
        return [
            Befund(
                ort="Bestand",
                invariante="katalog-geschlossen",
                text="keine Datei definiert eine Operation - der Bestand traegt keinen Katalog.",
            )
        ]
    befunde: list[Befund] = []
    befunde.extend(_katalog_geschlossen(stellen, katalog))
    befunde.extend(_uebersicht(bestand, stellen))
    befunde.extend(_wege(stellen))
    befunde.extend(_ziel_literal(stellen))
    befunde.extend(_lesende_grenze(stellen))
    befunde.extend(_verweis_abschnitt(bestand, katalog))
    befunde.extend(_id_verwendung(bestand, {eintrag.id for eintrag in stellen}))
    befunde.extend(_zugriff_nur_im_katalog(bestand))
    befunde.extend(_messbegriffe(bestand))
    befunde.extend(_erlaubnisstufen(bestand))
    befunde.extend(_kommentar_pfad(stellen))
    return befunde


def _katalog_geschlossen(stellen: list[Eintrag], katalog: set[str]) -> list[Befund]:
    befunde: list[Befund] = []
    datei = sorted(katalog)[0]
    definiert = [eintrag.id for eintrag in stellen]
    for fehlend in sorted(ERWARTETE_OPERATIONEN - set(definiert)):
        befunde.append(
            befund(datei, 1, "katalog-geschlossen", f"Operation `{fehlend}` ist nicht definiert.")
        )
    for zusaetzlich in sorted(set(definiert) - ERWARTETE_OPERATIONEN):
        stelle = next(eintrag for eintrag in stellen if eintrag.id == zusaetzlich)
        befunde.append(
            befund(
                stelle.datei,
                stelle.zeile,
                "katalog-geschlossen",
                f"Operation `{zusaetzlich}` ist nicht im geschlossenen Bestand.",
            )
        )
    for doppelt in sorted({id_ for id_ in definiert if definiert.count(id_) > 1}):
        orte = [f"{e.datei}:{e.zeile}" for e in stellen if e.id == doppelt]
        befunde.append(
            befund(
                orte[0].rsplit(":", 1)[0],
                int(orte[0].rsplit(":", 1)[1]),
                "katalog-geschlossen",
                f"Operation `{doppelt}` ist {len(orte)}-mal definiert ({', '.join(orte)}).",
            )
        )
    return befunde


def _uebersicht(bestand: Bestand, stellen: list[Eintrag]) -> list[Befund]:
    """Jede Operation aus der Übersicht auffindbar - und die Übersicht ohne tote Zeile."""
    if KATALOG_UEBERSICHT not in bestand:
        return [
            befund(
                KATALOG_UEBERSICHT,
                1,
                "uebersicht-vollstaendig",
                "Übersicht fehlt - keine Operation waere auffindbar.",
            )
        ]
    befunde: list[Befund] = []
    zeilen: list[tuple[int, str, str]] = []
    for nummer, zeile in enumerate(bestand[KATALOG_UEBERSICHT].split("\n"), start=1):
        treffer = UEBERSICHTSZEILE.match(zeile)
        if treffer:
            datei = f"{KATALOG_SKILL}/operationen/{treffer.group('datei')}.md"
            zeilen.append((nummer, treffer.group("id"), datei))
    for nummer, ident, datei in zeilen:
        eintrag = next((stelle for stelle in stellen if stelle.id == ident), None)
        if eintrag is None:
            befunde.append(
                befund(
                    KATALOG_UEBERSICHT,
                    nummer,
                    "uebersicht-vollstaendig",
                    f"`{ident}` ist in der Übersicht, aber nirgends definiert.",
                )
            )
        elif eintrag.datei != datei:
            befunde.append(
                befund(
                    KATALOG_UEBERSICHT,
                    nummer,
                    "uebersicht-vollstaendig",
                    f"`{ident}` verweist auf {datei}, definiert ist sie in {eintrag.datei}.",
                )
            )
    genannt = {ident for _, ident, _ in zeilen}
    for eintrag in stellen:
        if eintrag.id not in genannt:
            befunde.append(
                befund(
                    KATALOG_UEBERSICHT,
                    1,
                    "uebersicht-vollstaendig",
                    f"`{eintrag.id}` fehlt in der Übersicht.",
                )
            )
    return befunde


def _wege(stellen: list[Eintrag]) -> list[Befund]:
    befunde: list[Befund] = []
    for eintrag in stellen:
        treffer = finde_zeile(eintrag, WEGE_ZEILE)
        if treffer is None:
            befunde.append(
                befund(
                    eintrag.datei,
                    eintrag.zeile,
                    "wege-geschlossen",
                    f"{eintrag.id}: keine **Wege:**-Zeile.",
                )
            )
            continue
        nummer, passend = treffer
        deklariert = WEG_TOKEN.findall(passend.group("rest"))
        if not deklariert:
            befunde.append(
                befund(
                    eintrag.datei, nummer, "wege-geschlossen", f"{eintrag.id}: kein Weg deklariert."
                )
            )
        if len(set(deklariert)) != len(deklariert):
            befunde.append(
                befund(
                    eintrag.datei,
                    nummer,
                    "wege-geschlossen",
                    f"{eintrag.id}: Weg doppelt deklariert ({deklariert}).",
                )
            )
        fremd = [weg for weg in deklariert if weg not in WEGE_VOKABULAR]
        if fremd:
            befunde.append(
                befund(
                    eintrag.datei,
                    nummer,
                    "wege-geschlossen",
                    f"{eintrag.id}: Weg außerhalb {{mcp, gh}}: {fremd}.",
                )
            )

        belegt: set[str] = set()
        if MCP_NAME.search(eintrag.text) or any(
            zeile.startswith(MCP_ZEILE) for _, zeile in eintrag.block
        ):
            belegt.add("mcp")
        if any(GH_ZEILE.match(zeile) for _, zeile in eintrag.block):
            belegt.add("gh")
        for fehlend in sorted(set(deklariert) - belegt):
            befunde.append(
                befund(
                    eintrag.datei,
                    nummer,
                    "wege-belegt",
                    f"{eintrag.id}: Weg `{fehlend}` ist deklariert, aber im Block nicht belegt.",
                )
            )
        for unerwartet in sorted(belegt - set(deklariert)):
            befunde.append(
                befund(
                    eintrag.datei,
                    nummer,
                    "wege-belegt",
                    f"{eintrag.id}: Weg `{unerwartet}` ist im Block belegt, aber nicht deklariert.",
                )
            )
        if eintrag.id in BOARD_OPERATIONEN:
            if set(deklariert) != {"gh"}:
                befunde.append(
                    befund(
                        eintrag.datei,
                        nummer,
                        "wege-board",
                        f"{eintrag.id}: Board-Operation nennt {deklariert}, erwartet genau `gh`.",
                    )
                )
            if REMOTE_MARKIERUNG not in eintrag.text:
                befunde.append(
                    befund(
                        eintrag.datei,
                        eintrag.zeile,
                        "wege-board",
                        f"{eintrag.id}: „{REMOTE_MARKIERUNG}“ fehlt im Block.",
                    )
                )
    return befunde


def _ziel_literal(stellen: list[Eintrag]) -> list[Befund]:
    befunde: list[Befund] = []
    for eintrag in stellen:
        for literale in ("TheRealKoller", "photosort"):
            if literale not in eintrag.text:
                befunde.append(
                    befund(
                        eintrag.datei,
                        eintrag.zeile,
                        "ziel-literal",
                        f"{eintrag.id}: Literal `{literale}` fehlt im Block.",
                    )
                )
    return befunde


def _lesende_grenze(stellen: list[Eintrag]) -> list[Befund]:
    befunde: list[Befund] = []
    for eintrag in stellen:
        if eintrag.id not in LESENDE_OPERATIONEN:
            continue
        grenze = grenzzeile(eintrag)
        if grenze is None:
            befunde.append(
                befund(
                    eintrag.datei,
                    eintrag.zeile,
                    "lesende-grenze",
                    f"{eintrag.id}: keine {AUSWERTUNGSGRENZE}-Zeile.",
                )
            )
            continue
        nummer, felder = grenze
        if felder is None:
            befunde.append(
                befund(
                    eintrag.datei,
                    nummer,
                    "lesende-grenze",
                    f"{eintrag.id}: die Grenzzeile trennt ihre Felder nicht mit „{FELDTRENNER}“.",
                )
            )
            continue
        erwartet = ERWARTETE_AUSWERTUNGSGRENZE.get(eintrag.id)
        if erwartet is not None and felder != erwartet:
            befunde.append(
                befund(
                    eintrag.datei,
                    nummer,
                    "lesende-grenze",
                    f"{eintrag.id}: Feldmenge {felder}, erwartet exakt {erwartet}.",
                )
            )
        if erwartet is None and not felder:
            befunde.append(
                befund(
                    eintrag.datei,
                    nummer,
                    "lesende-grenze",
                    f"{eintrag.id}: nennt kein ausgewertetes Feld.",
                )
            )
    return befunde


def _ueberschriftstitel(bestand: Bestand) -> set[str]:
    return {titel for datei in bestand for _, _, titel in ueberschriften(bestand[datei])}


def _verweis_abschnitt(bestand: Bestand, katalog: set[str]) -> list[Befund]:
    befunde: list[Befund] = []
    titel = _ueberschriftstitel(bestand)
    namen = _katalognamen(katalog)
    for datei in sorted(bestand):
        if not _im_suchraum(datei):
            continue
        for nummer, zeile in enumerate(bestand[datei].split("\n"), start=1):
            zitate = list(ABSCHNITTS_ZITAT.finditer(zeile))
            if not zitate or not any(name in zeile for name in namen):
                continue
            for zitat in zitate:
                genannt = zitat.group("titel").strip()
                if not any(kopf.startswith(genannt) for kopf in titel):
                    befunde.append(
                        befund(
                            datei,
                            nummer,
                            "verweis-abschnitt",
                            f"zitierter Abschnitt „{genannt}“ existiert nicht.",
                        )
                    )
    return befunde


def _id_verwendung(bestand: Bestand, definiert: set[str]) -> list[Befund]:
    befunde: list[Befund] = []
    for datei in sorted(bestand):
        if not _im_anweisungsraum(datei):
            continue
        for nummer, zeile in enumerate(bestand[datei].split("\n"), start=1):
            for treffer in ID_VERWENDUNG.finditer(zeile):
                if treffer.group(1) not in definiert:
                    befunde.append(
                        befund(
                            datei,
                            nummer,
                            "id-verwendung",
                            f"`{treffer.group(1)}` ist keine definierte Operation.",
                        )
                    )
    return befunde


def _zugriff_nur_im_katalog(bestand: Bestand) -> list[Befund]:
    befunde: list[Befund] = []
    for datei in sorted(bestand):
        if not _im_anweisungsraum(datei) or _ist_im_katalog(datei):
            continue
        for nummer, zeile in enumerate(bestand[datei].split("\n"), start=1):
            if GH_IRGENDWO.search(zeile):
                befunde.append(
                    befund(
                        datei,
                        nummer,
                        "zugriff-nur-im-katalog",
                        f"`gh`-Befehl außerhalb einer katalogtragenden Datei: {zeile.strip()!r}.",
                    )
                )
            if MCP_NAME.search(zeile):
                befunde.append(
                    befund(
                        datei,
                        nummer,
                        "zugriff-nur-im-katalog",
                        f"`mcp__github__`-Name außerhalb einer katalogtragenden Datei: "
                        f"{zeile.strip()!r}.",
                    )
                )
    return befunde


def _messbegriffe(bestand: Bestand) -> list[Befund]:
    befunde: list[Befund] = []
    for datei in sorted(bestand):
        if not _im_anweisungsraum(datei):
            continue
        for nummer, zeile in enumerate(bestand[datei].split("\n"), start=1):
            for begriff in MESSBEGRIFFE:
                if begriff in zeile:
                    befunde.append(
                        befund(
                            datei,
                            nummer,
                            "messbegriffe",
                            f"Messbegriff `{begriff}` - keine Vorabmessung.",
                        )
                    )
    return befunde


def _erlaubnisstufen(bestand: Bestand) -> list[Befund]:
    befunde: list[Befund] = []
    entdeckt = {datei for datei in bestand if _ist_skill_oder_agent(datei)}
    for datei in sorted(set(ERWARTETE_STUFEN) - entdeckt):
        befunde.append(
            befund(
                datei,
                1,
                "erlaubnisstufe",
                "erwartet, aber nicht im entdeckten Bestand - oder keine Skill-/Agenten-Datei.",
            )
        )
    for datei in sorted(entdeckt):
        zeilen = bestand[datei].split("\n")
        stufen: list[tuple[int, str]] = []
        for nummer, zeile in enumerate(zeilen, start=1):
            if not zeile.startswith(STUFE_MARKER):
                continue
            wert = zeile[len(STUFE_MARKER) :].strip()
            stufen.append((nummer, wert.split()[0] if wert else ""))
        if len(stufen) != 1:
            befunde.append(
                befund(
                    datei,
                    1,
                    "erlaubnisstufe",
                    f"trägt {len(stufen)} Erlaubnisstufen ({[wert for _, wert in stufen]}), "
                    f"erwartet genau eine in der Form '{STUFE_MARKER} <Stufe>'.",
                )
            )
            continue
        nummer, wert = stufen[0]
        if wert not in STUFEN:
            befunde.append(
                befund(
                    datei,
                    nummer,
                    "erlaubnisstufe",
                    f"Stufe {wert!r} ist kein geschlossener Wert {sorted(STUFEN)}.",
                )
            )
        if datei in ERWARTETE_STUFEN and wert != ERWARTETE_STUFEN[datei]:
            befunde.append(
                befund(
                    datei,
                    nummer,
                    "erlaubnisstufe",
                    f"trägt {wert!r}, erwartet {ERWARTETE_STUFEN[datei]!r}.",
                )
            )
    return befunde


def _kommentar_pfad(stellen: list[Eintrag]) -> list[Befund]:
    befunde: list[Befund] = []
    for eintrag in stellen:
        if eintrag.id != KOMMENTAR_AUSNAHME and re.search(r"kommentar[a-z-]*lesen", eintrag.id):
            befunde.append(
                befund(
                    eintrag.datei,
                    eintrag.zeile,
                    "kommentar-pfad",
                    f"`{eintrag.id}` liest Kommentare - nur `{KOMMENTAR_AUSNAHME}` darf das.",
                )
            )
        if eintrag.id == KOMMENTAR_AUSNAHME:
            continue
        grenze = grenzzeile(eintrag)
        if grenze is not None:
            nummer, felder = grenze
            kommentar = [feld for feld in felder or () if "comment" in feld.lower()]
            if kommentar:
                befunde.append(
                    befund(
                        eintrag.datei,
                        nummer,
                        "kommentar-pfad",
                        f"{eintrag.id}: Auswertungsgrenze nennt Kommentarfeld {kommentar}.",
                    )
                )
        for nummer, zeile in eintrag.block:
            if KOMMENTAR_PFAD.search(KOMMENTAR_ANTWORT.sub("", zeile)):
                befunde.append(
                    befund(
                        eintrag.datei,
                        nummer,
                        "kommentar-pfad",
                        f"{eintrag.id}: Kommentarpfad in einer deklarierten Aufrufzeile.",
                    )
                )
    return befunde


def test_der_bestand_erfuellt_alle_invarianten() -> None:
    """Der lebende Bestand hält jede Invariante; die Verletzungsfälle belegt `mutationen.py`."""
    befunde = pruefe(Bestand.aus_arbeitsbaum())

    assert not befunde, "Katalog-Befunde: " + "; ".join(f.meldung for f in befunde)
