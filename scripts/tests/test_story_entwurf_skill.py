"""Haelt die mechanisch pruefbaren Zusagen des Skills `story-entwurf` fest.

Besonderheit dieser Datei: **Die einzige Instanz des geprueften Formats liegt ausserhalb des
Repositoriums.** Der Abschnitt `## Design` lebt in einem GitHub-Issue-Body; kein Test bekommt je
ein Exemplar zu sehen. Pruefbar ist allein die **Erzeugungs- und Leseanweisung** - also der Text,
der sagt, wie der Block auszusehen hat und wer ihn schreiben darf.

Fuenf Zusicherungsklassen:

1. **Whitelist-Gleichheit der Operations-IDs.** `story-entwurf` nennt genau drei:
   `board-status-und-prioritaet-lesen`, `issue-lesen`, `issue-body-schreiben`. **Gleichheit**,
   nicht Teilmenge - eine vergessene ID faellt damit ebenso auf wie eine hinzugekommene, und
   "kein `issue-titel-schreiben`, keine `board-*-setzen`, keine `pr-*`-Operation" ist belegt, ohne
   dass irgendwo eine Verbotsliste gepflegt wird, die nur verbietet, was sie kennt.
2. **Ein-Definitions-Regel fuer den `## Design`-Block.** Feldnamen und Vorrat stehen **genau
   einmal** im lebenden Anweisungsraum `.claude/**`. Definitionsform ist ein umzaeunter Block, in
   dem alle drei Feldzeilen am **Zeilenanfang** stehen; die Gegenprobe unten belegt, dass eine
   blosse Erwaehnung der Feldnamen in Prosa nicht als Kopie zaehlt - sonst koennte keine andere
   Datei mehr ueber ein Feld reden, ohne rot zu werden, und die Regel waere unbenutzbar statt
   scharf.
3. **Reihenfolge ueber Zeichenoffsets.** Die Freigabepruefung steht vor der Ausarbeitung, die
   Fortschreibung des Issue-Bodys vor der Uebergabe an den Auslieferpfad, und in **jedem** der
   beiden Schreibschritte stehen eine frische Lesung **und** die verbindliche Selbstpruefung vor
   dessen Schreibzugriff. Ueber Offsets statt ueber eine Anwesenheitspruefung: "existiert
   irgendwo" und "steht davor" sind verschiedene Aussagen, und nur die zweite traegt die Zusage.

   **Warum die frische Lesung eine eigene Zusage ist und nicht in der Selbstpruefung aufgeht:**
   Die Selbstpruefung vergleicht den erzeugten gegen den **gelesenen** Body. Ist der gelesene
   veraltet - zwischen Schritt 0 und einem Schreibzugriff liegen ein vollstaendiger Rundenlauf und
   die Ausarbeitung -, ist sie **gruen, waehrend der Schaden entsteht**: Daniels zwischenzeitliche
   Bearbeitung wird stillschweigend ueberschrieben. Genau dagegen ist die Drift-Pruefung
   gerichtet, und deshalb wird sie hier getrennt geprueft.
4. **Werte aus den Quelltexten, nicht aus Test-Literalen.** Das Schluesselmuster wird aus **drei**
   Dateien gelesen und auf Gleichheit geprueft; das Umfangsvokabular kommt aus
   `penpot-entwurfsrunden`, die storygebundene Teilmenge aus `story-entwurf`. Zwei im Test
   notierte Literale waeren gleich per Konstruktion und bewiesen ueber den Bestand nichts.
5. **Die zwoelf Sicherheitsauflagen.** M-S1 bis M-S12 stehen je einmal als eigene, am Zeilenanfang
   verankerte Marke. Gelesen wird die **Nummernmenge** aus dem Text und gegen den
   luckenlosen Bereich geprueft - eine ausgefallene Auflage faellt damit auf, ohne dass hier zwoelf
   Zitate stuenden, die mit dem Skill driften.

**Zur Empfindlichkeit:** Jeder Erkenner traegt eine synthetische Probe seines eigenen Verstosses
und eine Gegenprobe des erlaubten Falls; dazu Selbstschutz auf eine plausible Textlaenge und auf
die Existenz jeder Ueberschrift, an der ein Offsetvergleich haengt.

Kein Netzwerk, kein GitHub, kein Penpot - gelesen werden ausschliesslich Dateien dieses
Repositories.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

SKILL_PFAD = ".claude/skills/story-entwurf/SKILL.md"
RUNDEN_PFAD = ".claude/skills/penpot-entwurfsrunden/SKILL.md"
SHIP_ENTWURF_PFAD = ".claude/skills/ship-entwurf/SKILL.md"

# Selbstschutz: Ein leergelaufener oder falsch gelesener Text liesse jede Abwesenheits- und jede
# Offsetzusage leer wahr werden. Untergrenze bewusst weit unter dem Ist-Stand.
MINDESTLAENGE_SKILL = 4000

# --- 1. Operations-IDs als Whitelist-Gleichheit -------------------------------------------

ERWARTETE_OPERATIONEN = frozenset(
    {
        "board-status-und-prioritaet-lesen",
        "issue-lesen",
        "issue-body-schreiben",
    }
)

# Derselbe Erkennungsraum wie im Katalogtest: die vier fuer Operations-IDs reservierten Praefixe.
_ID_VERWENDUNG = re.compile(r"`((?:issue|board|pr|copilot)-[a-z][a-z-]*)`")

# --- 2. Der Abschnitt `## Design` ----------------------------------------------------------

# Die drei Feldnamen in ihrer **Definitionsform**: fett, mit Doppelpunkt, am Zeilenanfang. Genau
# diese Form macht aus einer Erwaehnung eine Festlegung; `refinement`, `spec-writer` und
# `ux-ui-designer` duerfen ueber ein Feld reden, aber es nicht zweitdefinieren.
DESIGN_FELDER = ("**Stand:**", "**Penpot-Seite:**", "**Schlüssel:**")

DESIGN_UEBERSCHRIFT = "## Design"

# Der lebende Anweisungsraum. Bewusst **nicht** `specs/`: Dort stehen eingefrorene
# Momentaufnahmen (die Spec und die ADR zeigen den Block als Beispiel), und ein Textscan koennte
# lebende von historischer Nennung dort nicht trennen.
ANWEISUNGSRAUM = (".claude",)

_CODEBLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)

# Der Vorrat von `Stand` steht als eigene, maschinell lesbare Zeile - dieselbe Bauart wie die
# Auswertungsgrenze des Operationskatalogs: Werte vor dem Gedankenstrich, Prosa dahinter.
STAND_MARKER = "**Stand-Vorrat:**"
UMFANG_MARKER = "**Zugelassener Entwurfsumfang:**"
SCHLUESSELMUSTER_MARKER = "**Schlüsselmuster:**"

_BACKTICK_TOKEN = re.compile(r"`([^`\n]+)`")

# --- 3. Ueberschriften und Offsets ----------------------------------------------------------

UEBERSCHRIFT_VORBEDINGUNGEN = "## Schritt 0: Vorbedingungen und Schreibziel"
UEBERSCHRIFT_RUNDEN = "## Schritt 1: Entwurfsrunden, storygebunden"
UEBERSCHRIFT_NACHBESSERN = "## Schritt 2: Den fachlichen Body nachbessern — vorgezogen und eigen"
UEBERSCHRIFT_FREIGABE = "## Schritt 3: Die Auslieferungsfreigabe feststellen"
UEBERSCHRIFT_AUSARBEITEN = "## Schritt 4: Ausarbeiten und in die Nutzlast aufnehmen"
UEBERSCHRIFT_ANHEFTEN = "## Schritt 5: Den Verweis an die Story heften"
UEBERSCHRIFT_UEBERGABE = "## Schritt 6: Übergabe an den Auslieferpfad"
UEBERSCHRIFT_BLOCKFORM = "## Der Abschnitt, den dieser Skill schreibt — Form an genau einer Stelle"
UEBERSCHRIFT_AUFLAGEN = "## Die zwölf Sicherheitsauflagen"
UEBERSCHRIFT_BERICHT = "## Bericht an Daniel"

SKILL_UEBERSCHRIFTEN = (
    UEBERSCHRIFT_VORBEDINGUNGEN,
    UEBERSCHRIFT_RUNDEN,
    UEBERSCHRIFT_NACHBESSERN,
    UEBERSCHRIFT_FREIGABE,
    UEBERSCHRIFT_AUSARBEITEN,
    UEBERSCHRIFT_ANHEFTEN,
    UEBERSCHRIFT_UEBERGABE,
    UEBERSCHRIFT_BLOCKFORM,
    UEBERSCHRIFT_AUFLAGEN,
    UEBERSCHRIFT_BERICHT,
)

# Die beiden Schritte, die schreiben. Ihre Reihenfolge ist die Zusage aus ADR 0094 Abschnitt 7
# (erst der fachliche Body, dann das Anheften) - und in **beiden** stehen frische Lesung,
# Drift-Pruefung und Selbstpruefung vor dem Schreibzugriff.
SCHREIBSCHRITTE = (UEBERSCHRIFT_NACHBESSERN, UEBERSCHRIFT_ANHEFTEN)

SELBSTPRUEFUNG_MARKER = "**Selbstprüfung vor dem Schreibzugriff:**"
SCHREIBOPERATION = "issue-body-schreiben"
LESEOPERATION = "issue-lesen"
FREIGABEOPERATION = "board-status-und-prioritaet-lesen"

# Die Drift-Schranke am Body. Sie steht neben der Selbstpruefung, weil sie etwas **anderes** sichert
# und die Selbstpruefung genau hier blind ist: Diese vergleicht den erzeugten gegen den **gelesenen**
# Body - ist der gelesene veraltet, ist sie gruen, waehrend der Schaden entsteht. Zwischen der
# Lesung in Schritt 0 und einem Schreibzugriff liegen ein vollstaendiger Rundenlauf mit
# Rueckmeldezyklen und die Ausarbeitung; ein Lauf ist kein Moment. Dasselbe Argument wie M-S7 fuer
# die Board-Freigabe, nur mit groesserem Schaden - hier geht Daniels eigener Text in einem
# oeffentlichen, nicht zuruecknehmbaren Artefakt verloren.
DRIFT_MARKER = "**Drift-Prüfung am Body:**"

# --- 4. Werte, die aus den Quelltexten kommen ------------------------------------------------

# Verankert, mit geschlossenem Zeichenvorrat und gedeckelter Laenge. Gelesen statt notiert: Der
# Block ueberquert als Text eine Zustaendigkeitsgrenze, und drei Dateien muessen dasselbe Muster
# meinen, sonst prueft die Verwendungsstelle etwas anderes als die Schreibstelle.
_SCHLUESSELMUSTER = re.compile(r"\^\[a-z0-9\]\[a-z0-9-\]\{\d+,\d+\}\$")

# Die Form, in der `penpot-entwurfsrunden` sein Umfangsvokabular fuehrt. Die Zwei-Wert-Form des
# Modus (`alternativen` / `verfeinern`) trifft dieses Muster nicht.
_UMFANG_VOKABULAR = re.compile(r"genau einer aus `([a-z]+)` / `([a-z]+)` / `([a-z]+)`")

# --- 5. Die zwoelf Sicherheitsauflagen -----------------------------------------------------------

ERWARTETE_AUFLAGEN = tuple(range(1, 13))
_AUFLAGEN_MARKE = re.compile(r"^\*\*M-S(?P<nummer>\d+) — ", re.MULTILINE)

# --- Der Katalog: Erlaubnisstufe und Aufrufer-Zeilen ------------------------------------------

KATALOG_PFAD = ".claude/skills/github-access/SKILL.md"
SKILLNAME = "story-entwurf"
STUFE_SCHREIBEND = "lesend und schreibend"
AUFRUFER_MARKER = "**Aufrufer:**"

# Selbstschutz fuer den Blockschnitt: ein leer gelesener Eintrag bestuende jede Zusicherung ueber
# ihn per Konstruktion nicht, ein auf den Resttext ueberlaufender ebenso zufaellig.
KATALOGEINTRAG_MINDESTLAENGE = 300
KATALOGEINTRAG_HOECHSTLAENGE = 6000

# Die Praezisierung an Haertungsregel 4.3. Sie ist noetig, weil die Regel woertlich sagt, in ein
# dauerhaftes GitHub-Artefakt gelange ausschliesslich **selbst erzeugter** Inhalt - der
# Anheft-Vorgang schreibt aber gerade den unveraenderten, fremd gelesenen Bodyteil zurueck. Ohne
# den Satz stuenden zwei normative Texte gegeneinander, und zur Laufzeit waehlte der Ablauf selbst.
RUECKSCHRIFT_MARKER = "unveränderte Rückschrift desselben Bodys in dasselbe Issue"


# --- Duenne Leser -------------------------------------------------------------------------


def dateitext(pfad: str, wurzel: Path = REPO_WURZEL) -> str:
    return (wurzel / pfad).read_text(encoding="utf-8")


def skilltext() -> str:
    return dateitext(SKILL_PFAD)


def anweisungsraum(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: die Markdown-Dateien unter `.claude/**`, ueber `git ls-files`.

    Ueber die Versionsverwaltung statt `rglob`, damit eine nicht verwaltete Arbeitskopie nicht in
    den Suchraum geraet und die Ein-Definitions-Zusage nicht an einer Datei scheitert, die
    niemand jemals ausliefert.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", *ANWEISUNGSRAUM],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]
    return {
        pfad: (wurzel / pfad).read_text(encoding="utf-8") for pfad in pfade if pfad.endswith(".md")
    }


# --- Reine Funktionen ----------------------------------------------------------------------


def codebloecke(text: str) -> list[str]:
    """Reine Funktion: die Inhalte aller mit ``` umzaeunten Bloecke."""
    return _CODEBLOCK.findall(text)


def operations_ids(text: str) -> set[str]:
    """Reine Funktion: die Menge der in Backticks genannten Operations-IDs."""
    return set(_ID_VERWENDUNG.findall(text))


def design_definitionen(text: str) -> list[str]:
    """Reine Funktion: die umzaeunten Bloecke, die den Abschnitt `## Design` **definieren**.

    Definition heisst: Der Block traegt die Ueberschrift und **alle drei** Feldnamen in ihrer
    Fett-Doppelpunkt-Form, jeweils am Zeilenanfang. Eine Prosa-Erwaehnung derselben Namen ist
    damit ausdruecklich keine Definition - ohne diese Abgrenzung duerfte keine lesende Datei mehr
    ueber ein Feld reden, und die Ein-Definitions-Regel waere unbenutzbar statt scharf.
    """
    treffer: list[str] = []
    for block in codebloecke(text):
        zeilen = block.split("\n")
        if not any(zeile.strip() == DESIGN_UEBERSCHRIFT for zeile in zeilen):
            continue
        if all(any(zeile.startswith(feld) for zeile in zeilen) for feld in DESIGN_FELDER):
            treffer.append(block)
    return treffer


def definitionsstellen(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: je Datei mit mindestens einer Definition ein Eintrag `<pfad>:<anzahl>`."""
    return [
        f"{pfad}:{len(design_definitionen(abbild[pfad]))}"
        for pfad in sorted(abbild)
        if design_definitionen(abbild[pfad])
    ]


def feldreihenfolge(block: str) -> tuple[str, ...]:
    """Reine Funktion: die Feldnamen in der Reihenfolge, in der sie im Block stehen."""
    return tuple(
        feld for zeile in block.split("\n") for feld in DESIGN_FELDER if zeile.startswith(feld)
    )


def markierte_werte(text: str, marker: str) -> tuple[str, ...]:
    """Reine Funktion: die Backtick-Werte einer Marker-Zeile, **vor** dem Gedankenstrich.

    Dieselbe Form und derselbe Grund wie bei der Auswertungsgrenze des Operationskatalogs: Hinter
    dem Strich steht Prosa, die ihrerseits Backticks fuehrt. Ohne die Grenze zoege jedes
    erlaeuternde Wort in die Wertemenge.
    """
    zeilen = [z for z in text.split("\n") if z.startswith(marker)]
    if len(zeilen) != 1:
        raise ValueError(
            f"{len(zeilen)} Zeilen mit dem Marker {marker!r} gefunden, erwartet genau eine. "
            "Null heisst: der Wert ist nicht mehr maschinell lesbar und jede Zusage darueber "
            "waere leer wahr. Mehr als eine heisst: zwei Festlegungen, die driften koennen."
        )
    rest = zeilen[0][len(marker) :]
    if "—" not in rest:
        raise ValueError(
            f"Die Zeile {marker!r} fuehrt keinen Gedankenstrich. Die Form ist "
            "'<marker> `<wert>`, `<wert>` — <Erlaeuterung>'; ohne ihn ist die Wertemenge nicht "
            "von der Erlaeuterung zu trennen."
        )
    return tuple(_BACKTICK_TOKEN.findall(rest.split("—")[0]))


def schluesselmuster(text: str) -> set[str]:
    """Reine Funktion: die Menge der im Text vorkommenden Schluesselmuster."""
    return set(_SCHLUESSELMUSTER.findall(text))


def umfangsvokabular(text: str) -> list[tuple[str, ...]]:
    """Reine Funktion: je Fundstelle das dreiwertige Umfangsvokabular."""
    return [tuple(treffer) for treffer in _UMFANG_VOKABULAR.findall(text)]


def auflagennummern(text: str) -> list[int]:
    """Reine Funktion: die Nummern der am Zeilenanfang verankerten `M-S`-Marken, in Fundfolge."""
    return [int(treffer.group("nummer")) for treffer in _AUFLAGEN_MARKE.finditer(text)]


def offset(text: str, literal: str) -> int:
    """Reine Funktion: der Zeichenoffset eines Literals; -1, wenn es fehlt."""
    return text.find(literal)


def abschnitt(text: str, ueberschrift: str) -> str:
    """Reine Funktion: der Rumpf eines `##`-Abschnitts bis zur naechsten `##`-Ueberschrift."""
    beginn = text.find(ueberschrift)
    if beginn == -1:
        return ""
    rest = text[beginn + len(ueberschrift) :]
    ende = rest.find("\n## ")
    return rest if ende == -1 else rest[:ende]


def katalogeintrag(text: str, kopf: str) -> str:
    """Reine Funktion: der Rumpf eines `###`-Katalogeintrags bis zur naechsten Ueberschrift."""
    beginn = text.find(kopf)
    if beginn == -1:
        return ""
    rest = text[beginn + len(kopf) :]
    grenzen = [stelle for stelle in (rest.find("\n### "), rest.find("\n## ")) if stelle != -1]
    return rest if not grenzen else rest[: min(grenzen)]


# --- Selbstschutz ---------------------------------------------------------------------------


def test_der_skilltext_hat_eine_plausible_groesse() -> None:
    text = skilltext()

    assert len(text) >= MINDESTLAENGE_SKILL, (
        f"Der Skilltext ist nur {len(text)} Zeichen lang. Entweder ist der Pfad kaputt oder der "
        "Skill leergelaufen - eine Offset- oder Abwesenheitszusage ueber einen leeren Text sagt "
        "nichts."
    )


@pytest.mark.parametrize("ueberschrift", SKILL_UEBERSCHRIFTEN)
def test_die_geprueften_ueberschriften_gibt_es(ueberschrift: str) -> None:
    """Ohne diesen Waechter bestuenden die Offsetvergleiche nach jeder Umbenennung leer."""
    assert ueberschrift in skilltext(), (
        f"Ueberschrift {ueberschrift!r} steht nicht in {SKILL_PFAD}. Wandert der Inhalt woanders "
        "hin, wandert die Zusicherung mit."
    )


def test_der_anweisungsraum_hat_eine_plausible_groesse() -> None:
    """Ein leer gelesener Suchraum machte die Ein-Definitions-Regel leer wahr."""
    dateien = anweisungsraum()

    assert len(dateien) >= 15, (
        f"Nur {len(dateien)} Markdown-Dateien unter {ANWEISUNGSRAUM} gefunden. Die Aufzaehlung "
        "ist kaputt; 'genau eine Definitionsstelle' waere dann eine Aussage ueber nichts."
    )
    assert SKILL_PFAD in dateien, (
        f"{SKILL_PFAD} liegt nicht im Suchraum - dann sagt die Zaehlung der Definitionsstellen "
        "nichts ueber die Datei, die die Definition tragen soll."
    )


# --- 1. Whitelist-Gleichheit der Operations-IDs ------------------------------------------------


def test_der_skill_nennt_genau_die_drei_erwarteten_operationen() -> None:
    genannt = operations_ids(skilltext())

    assert genannt == set(ERWARTETE_OPERATIONEN), (
        f"Genannt sind {sorted(genannt)}, erwartet genau {sorted(ERWARTETE_OPERATIONEN)}. "
        f"Zu viel: {sorted(genannt - ERWARTETE_OPERATIONEN)}; zu wenig: "
        f"{sorted(ERWARTETE_OPERATIONEN - genannt)}. Die Erlaubnisstufe 'lesend und schreibend' "
        "ist eine Obergrenze, keine Gebrauchserlaubnis - kein `issue-titel-schreiben`, keine "
        "`board-*-setzen`, keine `pr-*`-Operation."
    )


def test_eine_zusaetzliche_operation_im_skilltext_wuerde_die_gleichheit_brechen() -> None:
    """Gegenprobe am **echten** Text, nicht an zwei von Hand gebildeten Mengen.

    Zwei literal notierte Mengen zu vergleichen waere eine Tautologie: Der Test bestuende auch
    dann, wenn die Whitelist-Pruefung vom gelesenen Skilltext entkoppelt worden waere.
    """
    echt = operations_ids(skilltext())
    assert echt == set(ERWARTETE_OPERATIONEN), "Vorbedingung: der Ist-Stand ist gleich."

    zu_viel = operations_ids(skilltext() + "\nSetz danach `board-status-setzen` auf `Done`.\n")

    assert zu_viel - set(ERWARTETE_OPERATIONEN) == {"board-status-setzen"}

    zu_wenig = operations_ids(skilltext().replace(f"`{SCHREIBOPERATION}`", "den Body-Schreiber"))

    assert set(ERWARTETE_OPERATIONEN) - zu_wenig == {SCHREIBOPERATION}


# --- 2. Ein-Definitions-Regel fuer den `## Design`-Block ----------------------------------------


def test_der_design_block_ist_genau_einmal_im_anweisungsraum_definiert() -> None:
    stellen = definitionsstellen(anweisungsraum())

    assert stellen == [f"{SKILL_PFAD}:1"], (
        f"Definitionsstellen des `{DESIGN_UEBERSCHRIFT}`-Blocks: {stellen}, erwartet genau "
        f"['{SKILL_PFAD}:1']. Zwei woertliche Abbilder desselben Formats driften; null heisst, "
        "dass der Ablauf zur Laufzeit selbst entscheidet, welche Felder er schreibt."
    )


def test_der_definitionsblock_fuehrt_die_drei_felder_in_fester_reihenfolge() -> None:
    block = design_definitionen(skilltext())[0]

    assert feldreihenfolge(block) == DESIGN_FELDER, (
        f"Der Block fuehrt {list(feldreihenfolge(block))}, erwartet {list(DESIGN_FELDER)} in "
        "genau dieser Reihenfolge. Die Reihenfolge ist Teil der Form, nicht Geschmack - ein "
        "lesender Ablauf verankert die Feldzeilen zeilenweise."
    )


def test_eine_prosa_erwaehnung_der_feldnamen_zaehlt_nicht_als_definition() -> None:
    """Die Gegenprobe, ohne die die Ein-Definitions-Regel unbenutzbar waere.

    `refinement`, `spec-writer` und `ux-ui-designer` muessen ueber die Felder reden koennen -
    sonst laesst sich nirgends sagen, was durchgereicht wird. Nur der **umzaeunte Block mit allen
    drei Feldzeilen am Zeilenanfang** ist die Definition.
    """
    prosa = (
        "Der Abschnitt `## Design` traegt die Felder `Stand`, `Penpot-Seite` und `Schlüssel`; "
        "seine Form steht vollstaendig in `story-entwurf`.\n"
        "**Stand:** ist dabei der einzige Wert mit geschlossenem Vorrat.\n"
    )

    assert design_definitionen(prosa) == []


def test_ein_umzaeunter_block_mit_allen_drei_feldzeilen_gilt_als_definition() -> None:
    """Positivprobe: Ohne sie bestuende die Eindeutigkeit auch bei kaputtem Zaun-Muster."""
    block = (
        "```markdown\n"
        f"{DESIGN_UEBERSCHRIFT}\n\n"
        "**Stand:** ausgearbeitet\n"
        "**Penpot-Seite:** Ansicht — Projektübersicht\n"
        "**Schlüssel:** uebersicht\n"
        "```\n"
    )

    assert len(design_definitionen(block)) == 1
    assert feldreihenfolge(design_definitionen(block)[0]) == DESIGN_FELDER


def test_ein_block_ohne_ein_feld_gilt_nicht_als_definition() -> None:
    """Ein unvollstaendiger Block ist keine zweite Definition - aber auch keine gueltige."""
    block = f"```markdown\n{DESIGN_UEBERSCHRIFT}\n\n**Stand:** ausgearbeitet\n```\n"

    assert design_definitionen(block) == []


def test_der_stand_vorrat_ist_geschlossen_und_zweiwertig() -> None:
    vorrat = markierte_werte(skilltext(), STAND_MARKER)

    assert len(vorrat) == 2, (
        f"`Stand` fuehrt {list(vorrat)}, erwartet genau zwei Werte. Ein dritter Wert machte aus "
        "dem geschlossenen Vorrat eine offene Frage, und 'kein Platzhalter, kein leerer "
        "Abschnitt' haengt genau daran."
    )
    assert len(set(vorrat)) == 2, f"Derselbe Wert doppelt im Vorrat: {list(vorrat)}."
    for wert in vorrat:
        assert f"`{wert}`" in skilltext()


@pytest.mark.parametrize(
    ("probe", "erwartet"),
    [
        (f"{STAND_MARKER} `a`, `b` — und kein dritter Wert.\n", ("a", "b")),
        (f"{STAND_MARKER} `a` — und nichts sonst, insbesondere nicht `b`.\n", ("a",)),
    ],
)
def test_der_wertleser_trennt_wertemenge_von_erlaeuterung(
    probe: str, erwartet: tuple[str, ...]
) -> None:
    """Sonst zoege jedes in Backticks gesetzte Wort der Erlaeuterung in die Wertemenge."""
    assert markierte_werte(probe, STAND_MARKER) == erwartet


def test_eine_fehlende_markerzeile_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Zeilen"):
        markierte_werte("Nur Prosa.\n", STAND_MARKER)


def test_eine_markerzeile_ohne_gedankenstrich_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Gedankenstrich"):
        markierte_werte(f"{STAND_MARKER} `a`, `b`\n", STAND_MARKER)


# --- 3. Reihenfolge ueber Zeichenoffsets --------------------------------------------------------


def test_die_schritte_stehen_in_der_zugesagten_reihenfolge() -> None:
    """Anheften **vor** Ausliefern, Ausarbeiten **hinter** der Freigabepruefung."""
    text = skilltext()
    offsets = [offset(text, kopf) for kopf in SKILL_UEBERSCHRIFTEN[:7]]

    assert -1 not in offsets, f"Eine der sieben Schritt-Ueberschriften fehlt (Offsets: {offsets})."
    assert offsets == sorted(offsets), (
        f"Die Schritte stehen in der Reihenfolge {offsets}. Erwartet ist aufsteigend: Die "
        "Freigabepruefung steht vor der Ausarbeitung (ohne Freigabe entsteht kein "
        "`views.json`-Eintrag), und die Fortschreibung des Bodys steht vor der Uebergabe an den "
        "Auslieferpfad - scheitert die Auslieferung, ist der Entwurf trotzdem an der Story."
    )


def test_die_freigabepruefung_steht_vor_der_ausarbeitung() -> None:
    text = skilltext()

    freigabe = offset(text, f"`{FREIGABEOPERATION}`")
    ausarbeiten = offset(text, UEBERSCHRIFT_AUSARBEITEN)

    assert -1 not in (freigabe, ausarbeiten)
    assert freigabe < ausarbeiten, (
        f"Die Freigabeoperation steht bei {freigabe}, die Ausarbeitung bei {ausarbeiten}. "
        "Fail-closed heisst: erst lesen, dann ausarbeiten - nie umgekehrt und nie nachziehen."
    )


def test_die_fortschreibung_steht_vor_der_uebergabe_an_den_auslieferpfad() -> None:
    text = skilltext()

    anheften = offset(text, UEBERSCHRIFT_ANHEFTEN)
    uebergabe = offset(text, UEBERSCHRIFT_UEBERGABE)

    assert -1 not in (anheften, uebergabe)
    assert anheften < uebergabe, (
        f"Anheften steht bei {anheften}, Uebergabe bei {uebergabe}. Der Pull Request ist die "
        "einzige nicht zuruecknehmbare Handlung des Laufs; alles davor ist lokal korrigierbar."
    )


@pytest.mark.parametrize("kopf", SCHREIBSCHRITTE)
def test_die_selbstpruefung_steht_in_jedem_schreibschritt_vor_dem_schreibzugriff(
    kopf: str,
) -> None:
    """Die Selbstpruefung ersetzt die Funktion, die es bewusst nicht gibt.

    Geprueft wird **Existenz und Position**: Eine Selbstpruefung, die hinter dem Schreibzugriff
    stuende, belegte den bereits geschriebenen Body - sie waere ein Protokoll, keine Schranke.
    """
    rumpf = abschnitt(skilltext(), kopf)

    pruefung = offset(rumpf, SELBSTPRUEFUNG_MARKER)
    schreiben = offset(rumpf, f"`{SCHREIBOPERATION}`")

    assert pruefung != -1, (
        f"Im Schritt {kopf!r} steht keine Zeile {SELBSTPRUEFUNG_MARKER!r}. Es gibt keine Funktion "
        "unter `scripts/`, die den Body fortschreibt - die Selbstpruefung ist die einzige "
        "Mechanik, die die Byte-Zusage traegt."
    )
    assert schreiben != -1, (
        f"Im Schritt {kopf!r} steht kein `{SCHREIBOPERATION}`. Beide Schreibvorgaenge sind "
        "getrennt und beide benennen ihre Operation."
    )
    assert pruefung < schreiben, (
        f"Im Schritt {kopf!r} steht die Selbstpruefung bei {pruefung}, der Schreibzugriff bei "
        f"{schreiben}. Danach geprueft ist nicht geprueft."
    )


@pytest.mark.parametrize(
    ("probe", "erwartet_gueltig"),
    [
        ("...PRUEFUNG...SCHREIBEN...", True),
        ("...SCHREIBEN...PRUEFUNG...", False),
    ],
)
def test_der_offsetvergleich_unterscheidet_beide_richtungen(
    probe: str, erwartet_gueltig: bool
) -> None:
    """Gegenprobe an synthetischem Text - sonst waere die Reihenfolgezusage halb."""
    assert (offset(probe, "PRUEFUNG") < offset(probe, "SCHREIBEN")) is erwartet_gueltig


@pytest.mark.parametrize("kopf", SCHREIBSCHRITTE)
def test_jeder_schreibschritt_liest_den_body_unmittelbar_davor_neu(kopf: str) -> None:
    """Die Schranke, die die Selbstpruefung strukturell **nicht** stellen kann.

    Sie vergleicht den erzeugten gegen den gelesenen Body. Stammt der gelesene aus Schritt 0, liegt
    dazwischen ein vollstaendiger Rundenlauf mit Rueckmeldezyklen und die Ausarbeitung - Stunden,
    keine Sekunden. Hat Daniel den Body in dieser Zeit bearbeitet, ueberschreibt der Lauf seine
    Fassung, und die Selbstpruefung ist dabei **gruen**: Sie sieht genau den veralteten Stand, gegen
    den sie prueft. Deshalb steht in jedem Schreibschritt eine frische Lesung **und** eine
    Drift-Pruefung, und beide stehen vor dem Schreibzugriff.

    Dasselbe Argument wie M-S7 fuer die Board-Freigabe ("ein Lauf ist kein Moment"), nur mit
    groesserem Schaden: Der Verlust trifft Daniels eigenen Text in einem oeffentlichen, nicht
    zuruecknehmbaren Artefakt.
    """
    rumpf = abschnitt(skilltext(), kopf)

    lesen = offset(rumpf, f"`{LESEOPERATION}`")
    drift = offset(rumpf, DRIFT_MARKER)
    schreiben = offset(rumpf, f"`{SCHREIBOPERATION}`")

    assert lesen != -1, (
        f"Im Schritt {kopf!r} steht kein `{LESEOPERATION}`. Die Fortschreibung baut dann auf der "
        "Lesung aus Schritt 0 auf - und ueberschreibt stillschweigend, was Daniel waehrend des "
        "Rundenlaufs am Body geaendert hat."
    )
    assert drift != -1, (
        f"Im Schritt {kopf!r} steht keine Zeile {DRIFT_MARKER!r}. Ein erneutes Lesen allein "
        "genuegt nicht: Ohne den Vergleich gegen die Fassung aus Schritt 0 laeuft der Ablauf mit "
        "dem aktualisierten Stand einfach weiter, statt anzuhalten."
    )
    assert schreiben != -1, (
        f"Im Schritt {kopf!r} steht kein `{SCHREIBOPERATION}`. Beide Schreibvorgaenge sind "
        "getrennt und beide benennen ihre Operation."
    )
    assert lesen < drift < schreiben, (
        f"Im Schritt {kopf!r} stehen Lesung bei {lesen}, Drift-Pruefung bei {drift}, "
        f"Schreibzugriff bei {schreiben}. Erwartet ist aufsteigend - erst lesen, dann vergleichen, "
        "dann schreiben. Danach geprueft ist nicht geprueft."
    )


@pytest.mark.parametrize(
    ("probe", "erwartet_gueltig"),
    [
        # Der zugesagte Fall.
        (f"`{LESEOPERATION}` … {DRIFT_MARKER} … `{SCHREIBOPERATION}`", True),
        # Der Defekt, gegen den diese Zusage geschrieben ist: gelesen wird nur vorher, irgendwo.
        (f"{DRIFT_MARKER} … `{SCHREIBOPERATION}` … `{LESEOPERATION}`", False),
        # Gelesen, aber ohne Schranke dazwischen - der Ablauf zoege mit dem neuen Stand nach.
        (f"`{LESEOPERATION}` … `{SCHREIBOPERATION}` … {DRIFT_MARKER}", False),
    ],
)
def test_der_drift_offsetvergleich_unterscheidet_alle_richtungen(
    probe: str, erwartet_gueltig: bool
) -> None:
    """Gegenprobe an synthetischem Text - sonst bestuende die Reihenfolgezusage bei jeder Lage."""
    lesen = offset(probe, f"`{LESEOPERATION}`")
    drift = offset(probe, DRIFT_MARKER)
    schreiben = offset(probe, f"`{SCHREIBOPERATION}`")

    assert (lesen < drift < schreiben) is erwartet_gueltig


# --- 4. Werte aus den Quelltexten ---------------------------------------------------------------


def test_das_schluesselmuster_ist_in_allen_drei_dateien_dasselbe() -> None:
    """Gelesen, nicht notiert: Schreibstelle und Verwendungsstelle muessen dasselbe meinen."""
    muster = {
        pfad: schluesselmuster(dateitext(pfad))
        for pfad in (SKILL_PFAD, RUNDEN_PFAD, SHIP_ENTWURF_PFAD)
    }

    leer = sorted(pfad for pfad, werte in muster.items() if not werte)
    assert not leer, (
        f"Kein Schluesselmuster gefunden in: {leer}. Ohne ein einziges Vorkommen ist der "
        "Gleichheitsvergleich leer wahr, und ein vertipptes Muster bliebe dauerhaft gruen."
    )

    mehrdeutig = sorted(pfad for pfad, werte in muster.items() if len(werte) != 1)
    assert not mehrdeutig, (
        f"Mehr als ein Schluesselmuster in: {mehrdeutig}. Zwei Fassungen in derselben Datei sind "
        "der Drift-Fall im Kleinen."
    )

    verschieden = {pfad: sorted(werte) for pfad, werte in muster.items()}
    assert len({next(iter(werte)) for werte in muster.values()}) == 1, (
        f"Die drei Dateien fuehren verschiedene Schluesselmuster: {verschieden}. Geprueft wird "
        "der Wert **an der Verwendungsstelle**, nicht nur dort, wo er geschrieben wurde - der "
        "Block ueberquert als Text eine Zustaendigkeitsgrenze."
    )


def test_die_markierte_musterzeile_traegt_dasselbe_muster_wie_der_rest_der_datei() -> None:
    """Die maschinell lesbare Zeile ist die Definitionsstelle, nicht eine zweite Meinung."""
    markiert = markierte_werte(skilltext(), SCHLUESSELMUSTER_MARKER)

    assert len(markiert) == 1, (
        f"Die Musterzeile fuehrt {list(markiert)}, erwartet genau einen Wert."
    )
    assert set(markiert) == schluesselmuster(skilltext())


def test_der_storygebundene_umfang_ist_eine_echte_teilmenge_des_vokabulars() -> None:
    """Beide Mengen kommen aus Quelltexten - zwei Test-Literale waeren gleich per Konstruktion."""
    vokabular = umfangsvokabular(dateitext(RUNDEN_PFAD))

    assert vokabular, (
        f"In {RUNDEN_PFAD} steht kein dreiwertiges Umfangsvokabular mehr. Dann ist die "
        "Teilmengen-Zusage eine Aussage ueber nichts."
    )
    assert len(set(vokabular)) == 1, (
        f"{RUNDEN_PFAD} fuehrt verschiedene Umfangsvokabulare: {vokabular}. Schritt 1 und die "
        "Wiederaufnahme-Tabelle muessen dasselbe meinen."
    )

    alle = set(vokabular[0])
    zugelassen = set(markierte_werte(skilltext(), UMFANG_MARKER))

    assert zugelassen < alle, (
        f"Storygebunden zugelassen: {sorted(zugelassen)}, Vokabular des Rundenablaufs: "
        f"{sorted(alle)}. Erwartet ist eine **echte** Teilmenge - ein zugelassener Wert ausserhalb "
        "des Vokabulars waere ein Verweis ins Leere, die volle Menge hoebe die Grenze auf."
    )
    assert len(zugelassen) == 1, (
        f"Storygebunden zugelassen sind {sorted(zugelassen)}, erwartet genau einer. Fuer die "
        "uebrigen Umfaenge existiert keine ausgearbeitete, ausgelieferte Ablageform; ihr Verweis "
        "waere nach dem Merge nicht aufloesbar."
    )

    ausgeschlossen = alle - zugelassen
    fehlend = sorted(wert for wert in ausgeschlossen if f"`{wert}`" not in skilltext())
    assert not fehlend, (
        f"Der Skill nennt die ausgeschlossenen Umfaenge nicht: {fehlend}. Eine Grenze, die den "
        "ausgeschlossenen Fall nicht benennt, ist zur Laufzeit keine."
    )


# --- 5. Die zwoelf Sicherheitsauflagen --------------------------------------------------------------


def test_die_zwoelf_sicherheitsauflagen_stehen_vollstaendig_und_je_einmal() -> None:
    nummern = auflagennummern(skilltext())

    assert tuple(nummern) == ERWARTETE_AUFLAGEN, (
        f"Gefundene Auflagen: {nummern}, erwartet {list(ERWARTETE_AUFLAGEN)} in dieser "
        f"Reihenfolge. Fehlend: {sorted(set(ERWARTETE_AUFLAGEN) - set(nummern))}; doppelt: "
        f"{sorted({n for n in nummern if nummern.count(n) > 1})}. Die Auflagen sind "
        "Zusicherungen, keine Erlaeuterung - eine ausgefallene faellt sonst niemandem auf."
    )


def test_der_auflagen_erkenner_verlangt_die_verankerte_marke() -> None:
    """Eine Erwaehnung im Fliesstext ist keine Auflage - sonst zaehlte jeder Rueckverweis mit."""
    assert auflagennummern("Wie in **M-S3 — Schreibziel** beschrieben, gilt das auch hier.\n") == []
    assert auflagennummern("**M-S3 — Das Schreibziel stammt nie aus gelesenem Text.**\n") == [3]


def test_die_auflagen_stehen_im_dafuer_vorgesehenen_abschnitt() -> None:
    """Ort statt blosser Anwesenheit: verstreute Auflagen sind nicht als Menge lesbar."""
    text = skilltext()
    rumpf = abschnitt(text, UEBERSCHRIFT_AUFLAGEN)

    assert auflagennummern(rumpf) == list(ERWARTETE_AUFLAGEN), (
        f"Im Abschnitt {UEBERSCHRIFT_AUFLAGEN!r} stehen die Auflagen "
        f"{auflagennummern(rumpf)}. Erwartet sind dort alle elf - der Abschnitt ist die Stelle, "
        "an der sie als geschlossene Menge lesbar sind."
    )


# --- Der Katalog: Erlaubnisstufe und Aufrufer-Zeilen ---------------------------------------------


def test_die_erlaubnisstufen_tabelle_des_katalogs_nennt_den_skill() -> None:
    """Der Katalog ist die normative Stelle; die Skill-Datei spricht ihre Stufe nur aus."""
    zeilen = [
        zeile
        for zeile in dateitext(KATALOG_PFAD).split("\n")
        if zeile.startswith("|") and STUFE_SCHREIBEND in zeile
    ]

    assert len(zeilen) == 1, (
        f"{len(zeilen)} Tabellenzeilen mit {STUFE_SCHREIBEND!r} im Katalog, erwartet genau eine."
    )
    assert f"`{SKILLNAME}`" in zeilen[0], (
        f"Die Stufenzeile {STUFE_SCHREIBEND!r} nennt `{SKILLNAME}` nicht. Die Stufe in der "
        "Skill-Datei und die Aufzaehlung im Katalog sind zwei Haelften derselben Zusage; "
        "eine halbe ist keine."
    )


@pytest.mark.parametrize("operation", sorted(ERWARTETE_OPERATIONEN))
def test_jeder_der_drei_katalogeintraege_nennt_den_skill_in_seiner_aufrufer_zeile(
    operation: str,
) -> None:
    """Die Gegenrichtung der Whitelist: Der Katalog weiss, wer ihn benutzt.

    Ohne diese Zeilen bliebe 'genau drei Operationen' eine Aussage, die nur der Skill selbst
    macht - und eine Erlaubnisstufe ohne benannte Aufrufer ist eine Gebrauchserlaubnis.
    """
    block = katalogeintrag(dateitext(KATALOG_PFAD), f"### `{operation}`")

    assert KATALOGEINTRAG_MINDESTLAENGE <= len(block) <= KATALOGEINTRAG_HOECHSTLAENGE, (
        f"Der Eintrag `{operation}` wurde mit {len(block)} Zeichen gelesen. Entweder ist die "
        "Ueberschrift gewandert (leer) oder der Blockschnitt greift nicht mehr (zu lang)."
    )

    aufrufer = [zeile for zeile in block.split("\n") if zeile.startswith(AUFRUFER_MARKER)]

    assert len(aufrufer) == 1, (
        f"Der Eintrag `{operation}` fuehrt {len(aufrufer)} Zeilen {AUFRUFER_MARKER!r}, erwartet "
        "genau eine."
    )
    assert f"`{SKILLNAME}`" in aufrufer[0], (
        f"Die Aufrufer-Zeile von `{operation}` nennt `{SKILLNAME}` nicht: {aufrufer[0]!r}."
    )


def test_der_blockschnitt_endet_an_der_naechsten_ueberschrift() -> None:
    """Gegenprobe: ohne sie liefe der Block bis zum Dateiende und bestuende jede Zusage."""
    probe = "### `a`\nInhalt A\n\n### `b`\nInhalt B\n"

    assert katalogeintrag(probe, "### `a`").strip() == "Inhalt A"
    assert katalogeintrag(probe, "### `c`") == ""


def test_haertungsregel_4_3_nennt_die_unveraenderte_rueckschrift() -> None:
    """Sonst stuenden zwei normative Texte gegeneinander.

    Haertungsregel 4.3 sagt woertlich, in ein dauerhaftes GitHub-Artefakt gelange ausschliesslich
    **selbst erzeugter** Inhalt. Der Anheft-Vorgang schreibt aber genau den unveraendert
    gelesenen Bodyteil zurueck - ohne die Praezisierung waere die tragende Byte-Zusage dieses
    Ablaufs ein Regelverstoss, und zur Laufzeit waehlte der Ablauf selbst, welchem Text er folgt.
    """
    assert RUECKSCHRIFT_MARKER in dateitext(KATALOG_PFAD), (
        f"Der Katalog nennt {RUECKSCHRIFT_MARKER!r} nicht. Die Abgrenzung gehoert an die Regel "
        "selbst, nicht in den Skill, der sie braucht - sonst ist sie eine Selbstbefreiung."
    )
