"""Haelt die mechanisch pruefbaren Zusagen des Auslieferpfads `ship-entwurf` fest.

Ein Entwurfsrundenlauf hat die Erlaubnisstufe „kein GitHub-Zugriff" und endet deshalb an einem
**Anker**; der Skill `ship-entwurf` faengt dort an und hat „lesend und schreibend". Zwischen
beiden liegt kein Subagenten-Fenster, sondern nur dieser eine Satz - er ist die einzige Stelle,
an der ablesbar bleibt, wo ein Text ohne Zugriffsrecht aufhoert und einer mit Zugriffsrecht
anfaengt. Diese Datei sichert genau die Teile dieser Konstruktion, die statisch pruefbar sind.

Sechs Gruppen:

1. **Anker und Ein-Definitions-Regel.** Die Ankerzeile steht in beiden Dateien woertlich gleich;
   der **Block samt Feldnamen** steht ausschliesslich in der *erzeugenden* Datei
   (`penpot-entwurfsrunden`). Die verbrauchende fuehrt nur die Ankerzeile als Inline-Code in
   ihrer Ausloeseliste - nicht als eigene `##`-Ueberschrift und nicht als zweite umzaeunte Kopie.
   Zwei woertliche Abbilder desselben Formats sind der Drift-Fall, gegen den die Regel
   geschrieben ist; dass beide Texte in derselben Session laufen, macht ihn wahrscheinlicher,
   nicht harmloser.
2. **Platzierung und Kardinalitaet - statt einer Abwesenheitspruefung.** „Beim Abbruch wird nicht
   gefragt" ist ueber Prosa nicht pruefbar: Jede Formulierung, nach der man suchen koennte, ist
   gerade der Satz, der dasteht, und seine Anwesenheit belegt ueber den anderen Zweig nichts.
   Pruefbar ist die Zusage als **Kardinalitaet plus Ort**: Der Anker kommt genau **einmal** vor,
   und der Zeichenoffset dieses Vorkommens liegt zwischen der Ueberschrift des Fertig-Schritts
   und der des Aufraeumschritts.

   **Warum Zeichenoffsets und nicht `abschnitt()`:** Der Abschnittsleser schneidet am naechsten
   `\\n## ` und kennt keine Code-Zaeune - der Uebergabeblock **enthaelt** selbst eine `##`-Zeile.
   Ein auf ihn gestuetzter Platzierungsnachweis schnitte den Schritt genau am Anker ab und
   bestuende leer.
3. **Zulassungsmenge.** Die drei Praefixe, die namentlichen Ausschluesse, `origin/main...HEAD` als
   Vergleichsbasis, Waechter-Halt und Bilddatei-Halt als woertliche Zusagen.
4. **Diff-Hygiene.** Kein pauschales Hinzufuegen und kein Commit ueber den Arbeitsbaum - geprueft
   ueber die **Codebloecke**, nicht ueber die ganze Datei. Diese Abgrenzung ist der Grund, warum
   die Zusage hier ueberhaupt als Verbot formulierbar ist: `test_main_abgleich_verdrahtung.py`
   verzichtet an `developer.md` bewusst darauf, weil ein Textpruefer eine Warnung („nie
   `git add -A`") nicht von einer Anweisung unterscheiden kann. Ein **Codeblock** ist dagegen
   genau das, was eine Session absetzt - dort ist die Unterscheidung eindeutig. Die Anwesenheit
   des richtigen Wegs wird zusaetzlich zugesichert, nicht nur die Abwesenheit des falschen.
5. **Operations-IDs als Whitelist-Gleichheit.** Die Menge der in `ship-entwurf` genannten
   Operations-IDs ist **gleich** `{pr-erstellen, board-status-und-prioritaet-lesen,
   board-status-setzen}`. Das deckt „kein Copilot, keine Perspektivenrunde" ab, ohne eine
   Verbotsliste zu fuehren: Ein auftauchendes `copilot-review-anfordern` wird rot, eine vergessene
   ID ebenfalls. Dazu die woertlichen Zusagen (Titelform, `Closes #NNN`, alle Validierungsmuster,
   Herkunft der Namen).
6. **Die No-Story-Ausnahme an beiden normativen Stellen.** `ship-entwurf` ist der erste Aufrufer
   von `pr-erstellen` **ohne** Story - der Rundenablauf ist jederzeit aufrufbar, auch ohne Issue.
   Der Katalogeintrag war im Kontext von `ship-feature` geschrieben, wo es immer eine Story gibt,
   und formulierte die Closing-Zeile ohne Ausnahme; die Vorlage kennt sie ausdruecklich. Geprueft
   wird, dass beide Texte dieselbe Ausnahme woertlich fuehren - mit einem Selbstschutz fuer den
   Blockschnitt, weil ein leer gelesener oder ueberlaufender Eintrag die Zusage zufaellig
   bestuende.

**Zur Empfindlichkeit:** Jede Abwesenheits- und jede Mengenzusage traegt eine synthetische Probe
(der Erkenner findet seinen eigenen Verstoss) und eine Gegenprobe (der erlaubte Fall bleibt
gruen). Dazu Selbstschutz: Beide Dateien werden auf eine plausible Mindestlaenge geprueft, und
jede Ueberschrift, an der ein Offsetvergleich haengt, muss ueberhaupt existieren - sonst
bestuenden die Vergleiche nach der naechsten Umbenennung leer.

Kein Netzwerk, kein GitHub, kein Penpot - gelesen werden ausschliesslich Dateien dieses
Repositories.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

ERZEUGER_PFAD = ".claude/skills/penpot-entwurfsrunden/SKILL.md"
VERBRAUCHER_PFAD = ".claude/skills/ship-entwurf/SKILL.md"
SHIP_FEATURE_PFAD = ".claude/skills/ship-feature/SKILL.md"

# Selbstschutz: Ein leergelaufener oder falsch gelesener Text liesse jede Abwesenheitszusage
# leer wahr werden. Untergrenzen bewusst weit unter dem Ist-Stand.
MINDESTLAENGE_ERZEUGER = 3000
MINDESTLAENGE_VERBRAUCHER = 3000

# --- 1. Anker und Uebergabeblock ----------------------------------------------------------

ANKER = "## Entwurfslauf abgeschlossen: Pull Request erwünscht"

# Die Feldnamen des Uebergabeblocks. Sie stehen ausschliesslich in der erzeugenden Datei; ihre
# Bold-Doppelpunkt-Form ist die Definitionsform. `ship-entwurf` darf ueber ein Feld reden (die
# Zeile `Geänderte Dateien` wird dort ausdruecklich als *nicht gelesen* benannt), aber es nicht
# noch einmal definieren.
BLOCK_FELDER = (
    "**Arbeitsseite:**",
    "**Runden und Vorschläge:**",
    "**Ergebnis-Ansicht:**",
    "**Story:**",
    "**Geänderte Dateien:**",
)

# --- 2. Platzierung im erzeugenden Skill --------------------------------------------------

UEBERSCHRIFT_ABSCHLUSS = (
    "## Schritt 6: Abschluss — das Ergebnis wird ausgearbeitet, nicht verschoben"
)
UEBERSCHRIFT_UEBERGABE = "## Schritt 7: Pull Request — einmal fragen, dann übergeben"
UEBERSCHRIFT_AUFRAEUMEN = "## Schritt 8: Aufräumen ist eine Auskunft — der Ablauf entfernt nichts"

ERZEUGER_UEBERSCHRIFTEN = (
    UEBERSCHRIFT_ABSCHLUSS,
    UEBERSCHRIFT_UEBERGABE,
    UEBERSCHRIFT_AUFRAEUMEN,
)

# Der Bedingungssatz steht woertlich **im** Uebergabeschritt - sein Ort ist Teil der Zusage.
ABBRUCH_SATZ = "Beim Abbruch wird dieser Schritt übersprungen"

# --- 3./4. Die Ueberschriften des Auslieferpfads -------------------------------------------

UEBERSCHRIFT_AUSLOESER = "## Schritt 0: Auslöser erkennen"
UEBERSCHRIFT_BESTAND = "## Schritt 1: Bestandsaufnahme vor jedem Schreibzugriff"
UEBERSCHRIFT_HALTE = "## Schritt 2: Zwei Halte-Prüfungen auf der gemessenen Menge"
UEBERSCHRIFT_BRANCH = "## Schritt 3: Branch"
UEBERSCHRIFT_COMMIT = "## Schritt 4: Commit — pfadgenau über die gemessenen Pfade"
UEBERSCHRIFT_ABGLEICH = "## Schritt 5: Abgleich mit `main` — nach dem Commit, vor dem Push"
UEBERSCHRIFT_PUSH = "## Schritt 6: Push und Pull Request"
UEBERSCHRIFT_BOARD = "## Schritt 7: Board-Rücklesen — nur mit Story"
UEBERSCHRIFT_NICHT = "## Was dieser Pfad ausdrücklich nicht tut"

VERBRAUCHER_UEBERSCHRIFTEN = (
    UEBERSCHRIFT_AUSLOESER,
    UEBERSCHRIFT_BESTAND,
    UEBERSCHRIFT_HALTE,
    UEBERSCHRIFT_BRANCH,
    UEBERSCHRIFT_COMMIT,
    UEBERSCHRIFT_ABGLEICH,
    UEBERSCHRIFT_PUSH,
    UEBERSCHRIFT_BOARD,
    UEBERSCHRIFT_NICHT,
)

# Die geschlossene Zulassungsmenge und die namentlichen Ausschluesse - beide woertlich, weil ein
# Pfadpraefix, das nicht dasteht, zur Laufzeit auch nicht gilt.
ZUGELASSENE_PRAEFIXE = ("`design/penpot/**`", "`frontend/penpot/**`", "`specs/**`")
NAMENTLICHE_AUSSCHLUESSE = (
    "`backend/**`",
    "`frontend/src/**`",
    "`e2e/**`",
    "`scripts/**`",
    "`.github/**`",
    "`.claude/**`",
)

# Der Statusbefehl traegt `-uall` **nicht** als Geschmacksfrage: Ohne ihn meldet git ein neues,
# noch unversioniertes Verzeichnis als **einen** Eintrag (`?? design/penpot/neu/`) statt als seine
# einzelnen Dateien. Bilddatei-Halt und Zulassungspruefung sähen dann nur den Verzeichnispfad -
# der passt auf kein Bilddatei-Muster -, und der pfadgenaue Commit fuegte genau diesen Pfad
# rekursiv hinzu. Eine `design/penpot/neu/icon.png` faehre damit an der einen Pruefung vorbei, die
# sie abfangen soll, und der CI-Schritt ist ausdruecklich nur ein Detektor **nach** dem Push.
MESSBEFEHLE = ("git status --porcelain -uall", "git diff --name-only origin/main...HEAD")

# Fuer die Verankerung der Zusage: **jedes** Vorkommen des Statusbefehls muss die enumerierende
# Form tragen. Eine blosse Anwesenheitspruefung auf die lange Form ginge daran vorbei, weil die
# kurze Form ihr Praefix ist - eine zweite, zusammenfassende Fundstelle bliebe unbemerkt.
_STATUSBEFEHL = re.compile(r"git status --porcelain(?P<rest>[^\n`]*)")
ENUMERIERENDE_FORMEN = ("-uall", "--untracked-files=all")

# Je Zusage ein eigener Eintrag, damit ein Ausfall benennt, WELCHE verschwunden ist.
VERBRAUCHER_ZUSAGEN: tuple[tuple[str, str], ...] = (
    # Die Messung ist die einzige Grundlage - nicht die Zeile des Uebergabeblocks.
    (
        "Blockzeile steuert den Diff-Umfang nicht",
        "die Zeile `Geänderte Dateien` des Übergabeblocks wird dafür **nicht** gelesen",
    ),
    # Warum der Statusbefehl enumerieren muss - der Grund gehoert neben den Befehl, sonst
    # verschwindet das `-uall` bei der naechsten Vereinfachung.
    (
        "Unversionierte Verzeichnisse werden aufgelöst",
        "zu **einem** Eintrag zusammen",
    ),
    (
        "Enumeration vor allen Prüfungen",
        "**bevor** Zulassungsmenge, Wächter-Halt und Bilddatei-Halt greifen",
    ),
    # Die beiden Namen des Bodys werden unabhaengig geprueft; der Rueckfall gilt nur fuer den
    # einen von ihnen, der einen geprueften Ersatz hat.
    ("Beide Namen unabhängig geprüft", "unabhängig voneinander"),
    (
        "Kein Rückfall auf einen unzulässigen Schlüssel",
        "`schluessel` selbst unzulässig, hält der Ablauf an",
    ),
    ("Halt ausserhalb der Zulassungsmenge", "hält den Ablauf an"),
    ("Leerer Diff ist eine Auskunft", "Ein leerer Diff ist eine Auskunft, kein Fehler"),
    # Waechter-Halt (a) und (b).
    ("Wächter-Halt: neue JS-Nutzlast", "**neue** `*.js`-Datei unter `design/penpot/`"),
    ("Wächter-Halt: Verbotsliste", "`frontend/penpot/payload.test.ts`"),
    ("Wächter-Halt: VERBOTENE_BEZEICHNER", "`VERBOTENE_BEZEICHNER`"),
    ("Wächter-Halt: BEZEICHNER_FREIGABEN", "`BEZEICHNER_FREIGABEN`"),
    ("Wächter-Halt: bezeichner-Schlüssel", "`bezeichner:`"),
    ("Wächter-Halt: muster-Schlüssel", "`muster:`"),
    ("Wächter-Halt: prüfbar an", "git diff -U0"),
    # Bilddatei-Halt, wortgleich mit dem Muster der CI.
    (
        "Bilddatei-Halt: Muster",
        r"\.(png|jpe?g|gif|webp|bmp|tiff?|avif|heic|ico)$",
    ),
    ("Bilddatei-Halt: Schreibungsregel", "ohne Beachtung der Groß-/Kleinschreibung"),
    # Beispieldaten-Regel als dritte Pruefstelle.
    ("Beispieldaten-Regel am Diff", "Beispieldaten-Regel aus `penpot-design`"),
    # Branch und Commit.
    ("Branch-Namensteil validiert", "`^[a-z0-9][a-z0-9-]{2,39}$`"),
    ("Branchform auf main", "`design/<entwurfslauf>`"),
    ("Pfadgenaues Hinzufügen", "`git add <gemessene Pfade>`"),
    ("Verbot der pauschalen Formen", "nie `git add -A`, nie `git commit -a`"),
    # Abgleich mit main.
    ("Abgleichsskript", "scripts/merge-main-into-branch.sh"),
    ("Exit 0", "`0` → weiter, ohne Meldung"),
    ("Exit 10", "`10` → weiter, mit einer Zeile im Bericht"),
    (
        "Exit 20 und jeder andere",
        "`20` (Konflikt) und jeder andere Code → anhalten, nichts pushen",
    ),
    ("Konfliktpfade nicht in den PR-Body", "nie in den Pull-Request-Body"),
    # Pull Request.
    ("Titelform", "`chore(design): <Beschreibung>`"),
    ("Vorlage für den Body", "`.github/pull_request_template.md`"),
    ("Herkunft der Ergebnis-Ansicht", "`design/penpot/views.json`"),
    ("Feld anzeigename", "`anzeigename`"),
    ("Feld schluessel", "`schluessel`"),
    ("Kein Penpot-Rücklesen für den Body", "nicht aus einem Penpot-Rücklesen"),
    ("specs-Pfade getrennt benannt", "einzeln und getrennt"),
    # Story-Bezug.
    ("Closing-Zeile", "Closes #NNN"),
    ("Nummernmuster 1", "`^[0-9]+$`"),
    ("Nummernmuster 2", "`^[1-9][0-9]{0,5}$`"),
    ("Ohne Story keine Board-Bewegung", "wandert dann nicht von selbst auf `Review`"),
    # Haertung am oeffentlichen Artefakt.
    ("Bidi-Overrides", "U+202A–U+202E"),
    ("Bidi-Isolate", "U+2066–U+2069"),
    ("Zero-Width-Zeichen", "U+200B–U+200D"),
    ("Byte-Order-Mark", "U+FEFF"),
)

# --- 5. Operations-IDs ---------------------------------------------------------------------

# Geschlossene Whitelist. **Gleichheit**, nicht Teilmenge: Eine vergessene ID faellt damit ebenso
# auf wie eine hinzugekommene - und „kein Copilot, keine Perspektivenrunde" ist damit belegt,
# ohne dass irgendwo eine Verbotsliste gepflegt wird, die nur verbietet, was sie kennt.
ERWARTETE_OPERATIONEN = frozenset(
    {"pr-erstellen", "board-status-und-prioritaet-lesen", "board-status-setzen"}
)

# Erkennungsraum sind dieselben vier geschlossenen Praefixe wie im Katalogtest.
_ID_VERWENDUNG = re.compile(r"`((?:issue|board|pr|copilot)-[a-z][a-z-]*)`")

_CODEBLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)

# --- Die No-Story-Ausnahme, an zwei normativen Stellen -------------------------------------

# `ship-entwurf` ist der erste Aufrufer von `pr-erstellen` **ohne** Story: Der Rundenablauf ist
# jederzeit aufrufbar, auch ohne Issue. Der Katalogeintrag war im Kontext von `ship-feature`
# geschrieben, wo es immer eine Story gibt, und formulierte die Closing-Zeile deshalb ohne
# Ausnahme - die Vorlage kennt sie ausdruecklich. Zwei normative Texte, die einander
# widersprechen, sind schlimmer als einer, der schweigt: Zur Laufzeit waehlt der Ablauf sonst
# selbst, welchem er folgt.
KATALOG_PFAD = ".claude/skills/github-access/SKILL.md"
PR_VORLAGE_PFAD = ".github/pull_request_template.md"
PR_ERSTELLEN_KOPF = "### `pr-erstellen`"

# Woertlich die Formulierung der Vorlage - abgeschrieben wird sie in den Katalog, nicht
# umgekehrt: Die Vorlage ist der Text, den GitHub tatsaechlich in den Body legt.
NO_STORY_AUSNAHME = "Ausnahme: PR ohne Issue-Bezug (reine Doku-/Chore-PRs) — Zeile löschen."

# Selbstschutz fuer den Blockschnitt: Ein leer gelesener Eintrag bestuende jede Zusicherung
# ueber ihn per Konstruktion nicht - aber ein auf den Resttext der Datei ueberlaufender ebenso
# zufaellig. Untergrenze bewusst weit unter dem Ist-Stand, Obergrenze weit darueber.
KATALOGEINTRAG_MINDESTLAENGE = 400
KATALOGEINTRAG_HOECHSTLAENGE = 6000

# Die pauschalen Formen, in allen Schreibweisen, die am Bestand oder in der Doku vorkommen. Der
# letzte Eintrag faengt das zusammengezogene `-am`, das beide Verstoesse in einem Wort begeht.
PAUSCHAL_ERKENNER: dict[str, re.Pattern[str]] = {
    "add -A": re.compile(r"\bgit\s+add\b[^\n]*(?:\s-A\b|\s--all\b)"),
    "add .": re.compile(r"\bgit\s+add\s+\.(?:\s|$)"),
    "add -u": re.compile(r"\bgit\s+add\b[^\n]*(?:\s-u\b|\s--update\b)"),
    "commit -a": re.compile(r"\bgit\s+commit\b[^\n]*(?:\s-a\b|\s--all\b)"),
    "commit -am": re.compile(r"\bgit\s+commit\b[^\n]*\s-[a-z]*a[a-z]*m\b"),
}


# --- Duenne Leser --------------------------------------------------------------------------


def dateitext(pfad: str, wurzel: Path = REPO_WURZEL) -> str:
    return (wurzel / pfad).read_text(encoding="utf-8")


def erzeugertext() -> str:
    return dateitext(ERZEUGER_PFAD)


def verbrauchertext() -> str:
    return dateitext(VERBRAUCHER_PFAD)


# --- Reine Funktionen ----------------------------------------------------------------------


def codebloecke(text: str) -> list[str]:
    """Reine Funktion: die Inhalte aller mit ``` umzaeunten Bloecke."""
    return _CODEBLOCK.findall(text)


def bloecke_mit_anker(text: str) -> list[str]:
    """Reine Funktion: die umzaeunten Bloecke, die die Ankerzeile enthalten."""
    return [block for block in codebloecke(text) if ANKER in block]


def operations_ids(text: str) -> set[str]:
    """Reine Funktion: die Menge der in Backticks genannten Operations-IDs."""
    return set(_ID_VERWENDUNG.findall(text))


def pauschal_funde(bloecke: list[str]) -> list[str]:
    """Reine Funktion: je Fundstelle `<erkenner>: <zeile>` ueber die uebergebenen Bloecke."""
    befunde: list[str] = []
    for block in bloecke:
        for zeile in block.splitlines():
            for name, muster in PAUSCHAL_ERKENNER.items():
                if muster.search(zeile):
                    befunde.append(f"{name}: {zeile.strip()}")
    return befunde


def offset(text: str, literal: str) -> int:
    """Reine Funktion: der Zeichenoffset eines Literals; -1, wenn es fehlt."""
    return text.find(literal)


def zusammenfassende_statusaufrufe(text: str) -> list[str]:
    """Reine Funktion: je Fundstelle der Statusbefehl **ohne** enumerierende Option.

    Geprueft wird jedes Vorkommen, nicht die blosse Anwesenheit der langen Form: Die kurze Form
    ist ein Praefix der langen, eine zweite, zusammenfassende Fundstelle bliebe sonst unbemerkt.
    """
    befunde: list[str] = []
    for treffer in _STATUSBEFEHL.finditer(text):
        rest = treffer.group("rest")
        if not any(form in rest for form in ENUMERIERENDE_FORMEN):
            befunde.append(treffer.group(0).strip())
    return befunde


def katalogeintrag(text: str, kopf: str) -> str:
    """Reine Funktion: der Rumpf eines `###`-Katalogeintrags bis zur naechsten Ueberschrift."""
    beginn = text.find(kopf)
    if beginn == -1:
        return ""
    rest = text[beginn + len(kopf) :]
    grenzen = [stelle for stelle in (rest.find("\n### "), rest.find("\n## ")) if stelle != -1]
    return rest if not grenzen else rest[: min(grenzen)]


# --- Selbstschutz --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pfad", "mindestlaenge"),
    [
        (ERZEUGER_PFAD, MINDESTLAENGE_ERZEUGER),
        (VERBRAUCHER_PFAD, MINDESTLAENGE_VERBRAUCHER),
    ],
)
def test_beide_skilltexte_haben_eine_plausible_groesse(pfad: str, mindestlaenge: int) -> None:
    text = dateitext(pfad)

    assert len(text) >= mindestlaenge, (
        f"{pfad} ist nur {len(text)} Zeichen lang. Entweder ist der Pfad kaputt oder der Skill "
        "leergelaufen - eine Abwesenheitszusage ueber einen leeren Text sagt nichts."
    )


@pytest.mark.parametrize("ueberschrift", ERZEUGER_UEBERSCHRIFTEN)
def test_die_geprueften_ueberschriften_des_erzeugers_gibt_es(ueberschrift: str) -> None:
    """Ohne diesen Waechter bestuenden die Offsetvergleiche nach jeder Umbenennung leer."""
    assert ueberschrift in erzeugertext(), (
        f"Ueberschrift {ueberschrift!r} steht nicht in {ERZEUGER_PFAD}. Wandert der Inhalt "
        "woanders hin, wandert die Zusicherung mit."
    )


@pytest.mark.parametrize("ueberschrift", VERBRAUCHER_UEBERSCHRIFTEN)
def test_die_geprueften_ueberschriften_des_verbrauchers_gibt_es(ueberschrift: str) -> None:
    assert ueberschrift in verbrauchertext(), (
        f"Ueberschrift {ueberschrift!r} steht nicht in {VERBRAUCHER_PFAD}."
    )


# --- 1. Anker und Ein-Definitions-Regel ------------------------------------------------------


def test_die_ankerzeile_steht_woertlich_in_beiden_dateien() -> None:
    for pfad in (ERZEUGER_PFAD, VERBRAUCHER_PFAD):
        assert ANKER in dateitext(pfad), (
            f"Die Ankerzeile {ANKER!r} steht nicht in {pfad}. Sie ist die einzige Stelle, an der "
            "ablesbar bleibt, wo ein Text ohne GitHub-Zugriff aufhoert und einer mit anfaengt."
        )


def test_der_uebergabeblock_ist_ausschliesslich_im_erzeuger_definiert() -> None:
    """Ein-Definitions-Regel: das Format nur dort, wo es entsteht."""
    bloecke = bloecke_mit_anker(erzeugertext())

    assert len(bloecke) == 1, (
        f"{ERZEUGER_PFAD} fuehrt {len(bloecke)} umzaeunte Bloecke mit der Ankerzeile, erwartet "
        "genau einen. Zwei Fassungen desselben Formats driften."
    )

    fehlend = [feld for feld in BLOCK_FELDER if feld not in bloecke[0]]

    assert not fehlend, (
        "Feld(er) des Uebergabeblocks fehlen in seiner Definition: "
        + "; ".join(fehlend)
        + ". Was nicht dasteht, schreibt der Lauf auch nicht."
    )


def test_der_verbraucher_traegt_keine_zweite_blockkopie() -> None:
    text = verbrauchertext()

    assert bloecke_mit_anker(text) == [], (
        f"{VERBRAUCHER_PFAD} traegt den Uebergabeblock als umzaeunte Kopie. Er fuehrt in seiner "
        "Ausloeseliste ausschliesslich die Ankerzeile - genau so, wie `ship-feature` es mit den "
        "`developer`-Ankern haelt."
    )

    doppelt = [feld for feld in BLOCK_FELDER if feld in text]

    assert not doppelt, (
        "Feldname(n) des Uebergabeblocks stehen ein zweites Mal in "
        f"{VERBRAUCHER_PFAD}: " + "; ".join(doppelt) + ". Zwei Definitionsstellen sind der "
        "Drift-Fall, gegen den die Ein-Definitions-Regel geschrieben ist."
    )


def test_der_verbraucher_fuehrt_den_anker_als_inline_code_nicht_als_ueberschrift() -> None:
    text = verbrauchertext()

    assert f"`{ANKER}`" in text, (
        f"{VERBRAUCHER_PFAD} nennt die Ankerzeile nicht als Inline-Code. In der Ausloeseliste "
        "steht sie als Zeichenkette, nicht als gesetzte Ueberschrift."
    )

    eigene_ueberschriften = [zeile for zeile in text.splitlines() if zeile.startswith(ANKER)]

    assert not eigene_ueberschriften, (
        f"{VERBRAUCHER_PFAD} setzt die Ankerzeile als eigene `##`-Ueberschrift. Damit erzeugte "
        "der verbrauchende Text den Anker, den er nur erkennen soll."
    )


def test_ship_feature_bekommt_keinen_zweiten_anker() -> None:
    """Der Entwurfspfad ist ein eigener Skill, kein zweiter Einstieg in `ship-feature`."""
    assert ANKER not in dateitext(SHIP_FEATURE_PFAD), (
        f"Die Ankerzeile steht in {SHIP_FEATURE_PFAD}. Ein zweiter Einstieg dort waere ein Anker "
        "mehr plus acht Schritte mit 'gilt im Entwurfspfad nicht'."
    )


@pytest.mark.parametrize(
    ("text", "erwartete_treffer"),
    [
        (f"```\n{ANKER}\n\n**Story:** #392\n```\n", 1),
        (f"Auslöser: `{ANKER}` → Schritt 1.\n", 0),
        (f"```\n{ANKER}\n```\n\n```\n{ANKER}\n```\n", 2),
        ("```\nkein Anker hier\n```\n", 0),
    ],
)
def test_der_blockerkenner_zaehlt_seine_eigenen_proben(text: str, erwartete_treffer: int) -> None:
    """Ohne diese Probe bestuende die Kardinalitaet auch bei kaputtem Zaun-Muster."""
    assert len(bloecke_mit_anker(text)) == erwartete_treffer


# --- 2. Platzierung und Kardinalitaet ---------------------------------------------------------


def test_der_anker_kommt_im_erzeuger_genau_einmal_vor() -> None:
    text = erzeugertext()

    assert text.count(ANKER) == 1, (
        f"Die Ankerzeile kommt {text.count(ANKER)}-mal in {ERZEUGER_PFAD} vor, erwartet genau "
        "einmal. Genau einmal ist die pruefbare Fassung von 'im Abbruchfall wird nicht gefragt' - "
        "eine zweite Fundstelle waere ein zweiter Ausloeser, den niemand bemerkt."
    )


def test_der_anker_steht_zwischen_fertig_und_aufraeumschritt() -> None:
    """Ueber Zeichenoffsets statt ueber `abschnitt()`: Der Block traegt selbst eine `##`-Zeile."""
    text = erzeugertext()

    abschluss = offset(text, UEBERSCHRIFT_ABSCHLUSS)
    uebergabe = offset(text, UEBERSCHRIFT_UEBERGABE)
    anker = offset(text, ANKER)
    aufraeumen = offset(text, UEBERSCHRIFT_AUFRAEUMEN)

    assert -1 not in (abschluss, uebergabe, anker, aufraeumen), (
        f"Eine der vier Marken fehlt (Offsets: Abschluss {abschluss}, Uebergabe {uebergabe}, "
        f"Anker {anker}, Aufraeumen {aufraeumen})."
    )
    assert abschluss < uebergabe < anker < aufraeumen, (
        f"Die Reihenfolge stimmt nicht (Abschluss {abschluss}, Uebergabe {uebergabe}, Anker "
        f"{anker}, Aufraeumen {aufraeumen}). Der Uebergabeblock gehoert in einen **eigenen** "
        "Schritt zwischen Abschluss und Aufraeumen - beide duerfen keinen Codeblock tragen."
    )


def test_der_uebergabeschritt_traegt_genau_eine_rueckfrage() -> None:
    text = erzeugertext()
    beginn = offset(text, UEBERSCHRIFT_UEBERGABE)
    ende = offset(text, UEBERSCHRIFT_AUFRAEUMEN)
    schritt = text[beginn:ende]

    assert schritt.count("AskUserQuestion") == 1, (
        f"Der Uebergabeschritt nennt AskUserQuestion {schritt.count('AskUserQuestion')}-mal, "
        "erwartet genau einmal. Gefragt wird genau einmal - eine zweite Stelle waere eine "
        "zweite Frage, die niemand beantworten will."
    )


def test_der_abbruch_satz_steht_woertlich_im_uebergabeschritt() -> None:
    text = erzeugertext()
    beginn = offset(text, UEBERSCHRIFT_UEBERGABE)
    ende = offset(text, UEBERSCHRIFT_AUFRAEUMEN)

    assert ABBRUCH_SATZ in text[beginn:ende], (
        f"Der Satz {ABBRUCH_SATZ!r} steht nicht im Uebergabeschritt. Sein **Ort** ist Teil der "
        "Zusage: Er gilt fuer den Schritt, in dem er steht, nicht fuer den Skill im Ganzen."
    )


@pytest.mark.parametrize(
    ("probe", "erwartet_gueltig"),
    [
        ("A...B...ANKER...C", True),
        ("A...ANKER...B...C", False),
        ("A...B...C...ANKER", False),
    ],
)
def test_der_offsetvergleich_unterscheidet_beide_richtungen(
    probe: str, erwartet_gueltig: bool
) -> None:
    """Gegenprobe an synthetischem Text - sonst waere die Reihenfolgezusage halb."""
    a, b, c = (offset(probe, marke) for marke in ("A", "B", "C"))
    anker = offset(probe, "ANKER")

    assert (a < b < anker < c) is erwartet_gueltig


# --- 3. Zulassungsmenge -----------------------------------------------------------------------


@pytest.mark.parametrize("praefix", ZUGELASSENE_PRAEFIXE)
def test_die_drei_zugelassenen_praefixe_stehen_woertlich(praefix: str) -> None:
    assert praefix in verbrauchertext(), (
        f"Das zugelassene Praefix {praefix!r} steht nicht in {VERBRAUCHER_PFAD}. Die geschlossene "
        "Diff-Klasse ist die Bedingung, unter der der Reviewverzicht vertretbar ist."
    )


@pytest.mark.parametrize("ausschluss", NAMENTLICHE_AUSSCHLUESSE)
def test_die_namentlichen_ausschluesse_stehen_woertlich(ausschluss: str) -> None:
    assert ausschluss in verbrauchertext(), (
        f"Der namentliche Ausschluss {ausschluss!r} steht nicht in {VERBRAUCHER_PFAD}. Ein Lauf, "
        "der dort etwas geaendert hat, ist kein Entwurfslauf mehr."
    )


@pytest.mark.parametrize("befehl", MESSBEFEHLE)
def test_die_gemessene_menge_hat_ihre_beiden_quellen(befehl: str) -> None:
    assert befehl in verbrauchertext(), (
        f"Der Messbefehl {befehl!r} steht nicht in {VERBRAUCHER_PFAD}. Die Zulassungspruefung "
        "laeuft ausschliesslich ueber die selbst gemessene Menge."
    )


def test_jeder_statusaufruf_enumeriert_unversionierte_dateien() -> None:
    """Ohne `-uall` meldet git ein neues Verzeichnis als **einen** Eintrag, nicht als Dateien."""
    befunde = zusammenfassende_statusaufrufe(verbrauchertext())

    assert not befunde, (
        "Statusaufruf ohne enumerierende Option in "
        f"{VERBRAUCHER_PFAD}: " + "; ".join(befunde) + ". Ein neues, noch unversioniertes "
        "Verzeichnis stuende dann als ein einziger Pfad in der gemessenen Menge; der "
        "Bilddatei-Halt saehe nur den Verzeichnisnamen (der auf kein Bildmuster passt), und der "
        "pfadgenaue Commit naehme das Verzeichnis rekursiv mit. Genau die Luecke, die der Halt "
        "schliessen soll - und der CI-Schritt danach ist nur ein Detektor."
    )


@pytest.mark.parametrize(
    ("text", "erwartete_befunde"),
    [
        ("Setz `git status --porcelain` ab.", 1),
        ("Setz `git status --porcelain -uall` ab.", 0),
        ("Setz `git status --porcelain --untracked-files=all` ab.", 0),
        ("git status --porcelain -uall\ngit status --porcelain\n", 1),
        ("Hier steht kein Statusaufruf.", 0),
    ],
)
def test_der_statusbefehl_pruefer_unterscheidet_beide_richtungen(
    text: str, erwartete_befunde: int
) -> None:
    """Gegenprobe an synthetischem Text - die kurze Form ist ein Praefix der langen."""
    assert len(zusammenfassende_statusaufrufe(text)) == erwartete_befunde


# --- 4. Diff-Hygiene --------------------------------------------------------------------------


def test_kein_codeblock_des_auslieferpfads_fuegt_pauschal_hinzu() -> None:
    befunde = pauschal_funde(codebloecke(verbrauchertext()))

    assert not befunde, (
        "Pauschales Hinzufuegen bzw. Commit ueber den Arbeitsbaum in einem Codeblock von "
        f"{VERBRAUCHER_PFAD}. Ein `-A` hinter einer geschlossenen Zulassungsmenge macht sie zur "
        "Zierde, und eine danebenliegende, nicht versionierte Datei faehrt mit in ein "
        "oeffentliches Repositorium: " + "; ".join(befunde)
    )


@pytest.mark.parametrize(
    ("erkenner", "zeile"),
    [
        ("add -A", "git add -A"),
        ("add -A", "git add --all"),
        ("add .", "git add ."),
        ("add -u", "git add -u"),
        ("commit -a", "git commit -a -m 'chore(design): Entwurf'"),
        ("commit -am", "git commit -am 'chore(design): Entwurf'"),
    ],
)
def test_jeder_pauschal_erkenner_findet_seinen_eigenen_verstoss(erkenner: str, zeile: str) -> None:
    assert PAUSCHAL_ERKENNER[erkenner].search(zeile), (
        f"Der Erkenner {erkenner!r} findet seine eigene Probe nicht."
    )
    assert pauschal_funde([f"{zeile}\n"])


@pytest.mark.parametrize(
    "text",
    [
        # Der pfadgenaue Weg bleibt gruen.
        "```bash\ngit add design/penpot/views.json design/penpot/verify.js\n```\n",
        "```bash\ngit commit -m 'chore(design): Fotoansicht aufnehmen'\n```\n",
        "```bash\ngit status --porcelain\n```\n",
        # Prosa ueber das Verbot steht ausserhalb jedes Codeblocks - und soll es.
        "Der Commit ist pfadgenau: nie `git add -A`, nie `git commit -a`.\n",
    ],
)
def test_der_erlaubte_weg_gilt_nicht_als_pauschalbefund(text: str) -> None:
    assert pauschal_funde(codebloecke(text)) == []


def test_der_abgleich_steht_zwischen_commit_und_push() -> None:
    text = verbrauchertext()

    commit = offset(text, UEBERSCHRIFT_COMMIT)
    abgleich = offset(text, UEBERSCHRIFT_ABGLEICH)
    push = offset(text, UEBERSCHRIFT_PUSH)

    assert -1 not in (commit, abgleich, push)
    assert commit < abgleich < push, (
        f"Die Reihenfolge stimmt nicht (Commit {commit}, Abgleich {abgleich}, Push {push}). Der "
        "Abgleich verlangt ein sauberes Arbeitsverzeichnis und muss vor dem Push liegen, damit "
        "der Merge-Commit im selben Push hinausgeht."
    )


# --- 5. Operations-IDs als Whitelist-Gleichheit ------------------------------------------------


def test_der_auslieferpfad_nennt_genau_die_drei_erwarteten_operationen() -> None:
    genannt = operations_ids(verbrauchertext())

    assert genannt == set(ERWARTETE_OPERATIONEN), (
        f"Genannt sind {sorted(genannt)}, erwartet genau {sorted(ERWARTETE_OPERATIONEN)}. "
        f"Zu viel: {sorted(genannt - ERWARTETE_OPERATIONEN)}; zu wenig: "
        f"{sorted(ERWARTETE_OPERATIONEN - genannt)}. Der Pull Request eines Entwurfslaufs "
        "durchlaeuft keine Perspektivenrunde und kein angefordertes Copilot-Review - das ist "
        "hier als Gleichheit einer geschlossenen Whitelist gesichert, nicht als Verbotsliste."
    )


@pytest.mark.parametrize(
    ("probe", "erwartet"),
    [
        (
            "Ruf `pr-erstellen` auf, lies mit `board-status-und-prioritaet-lesen` zurueck und "
            "nimm `board-status-setzen` in den Bericht.",
            ERWARTETE_OPERATIONEN,
        ),
        (
            "Ruf `pr-erstellen` und danach `copilot-review-anfordern` auf.",
            frozenset({"pr-erstellen", "copilot-review-anfordern"}),
        ),
        ("Hier steht keine Operation.", frozenset()),
    ],
)
def test_der_id_erkenner_liest_seine_eigenen_proben(probe: str, erwartet: frozenset[str]) -> None:
    assert operations_ids(probe) == set(erwartet)


def test_eine_zusaetzliche_operation_im_skilltext_wuerde_die_gleichheit_brechen() -> None:
    """Gegenprobe am **echten** Text, nicht an zwei von Hand gebildeten Mengen.

    Der Vorgaenger dieses Tests verglich zwei literal notierte Mengen und war damit eine
    Tautologie: Er haette auch dann bestanden, wenn die Whitelist-Pruefung vom gelesenen
    Skilltext entkoppelt worden waere. Mutiert wird deshalb `verbrauchertext()` selbst, und
    geprueft wird das **geparste** Ergebnis - in beide Richtungen.
    """
    echt = operations_ids(verbrauchertext())
    assert echt == set(ERWARTETE_OPERATIONEN), "Vorbedingung: der Ist-Stand ist gleich."

    zu_viel = operations_ids(verbrauchertext() + "\nRuf `copilot-review-anfordern` auf.\n")

    assert zu_viel != set(ERWARTETE_OPERATIONEN), (
        "Eine im Skilltext ergaenzte Operations-ID veraendert die geparste Menge nicht - der "
        "Erkenner liest den Text nicht mehr, und die Whitelist-Gleichheit bestuende leer."
    )
    assert zu_viel - set(ERWARTETE_OPERATIONEN) == {"copilot-review-anfordern"}

    zu_wenig = operations_ids(verbrauchertext().replace("`board-status-setzen`", "den Board-Wert"))

    assert zu_wenig != set(ERWARTETE_OPERATIONEN), (
        "Eine aus dem Skilltext entfernte Operations-ID veraendert die geparste Menge nicht - "
        "eine vergessene ID fiele damit nicht auf."
    )
    assert set(ERWARTETE_OPERATIONEN) - zu_wenig == {"board-status-setzen"}


# --- 6. Die No-Story-Ausnahme an beiden normativen Stellen -------------------------------------


def test_der_katalogeintrag_pr_erstellen_wird_als_block_gelesen() -> None:
    """Selbstschutz: ein leerer oder ueberlaufender Block bestuende die Zusage unten zufaellig."""
    block = katalogeintrag(dateitext(KATALOG_PFAD), PR_ERSTELLEN_KOPF)

    assert KATALOGEINTRAG_MINDESTLAENGE <= len(block) <= KATALOGEINTRAG_HOECHSTLAENGE, (
        f"Der Eintrag {PR_ERSTELLEN_KOPF} wurde mit {len(block)} Zeichen gelesen. Entweder ist "
        "die Ueberschrift gewandert (leer) oder der Blockschnitt greift nicht mehr und zieht den "
        "Resttext der Datei mit (zu lang)."
    )


def test_die_no_story_ausnahme_steht_woertlich_in_katalog_und_vorlage() -> None:
    """`ship-entwurf` ist der erste Aufrufer von `pr-erstellen` ohne Story."""
    vorlage = dateitext(PR_VORLAGE_PFAD)
    block = katalogeintrag(dateitext(KATALOG_PFAD), PR_ERSTELLEN_KOPF)

    assert NO_STORY_AUSNAHME in vorlage, (
        f"Die Ausnahme steht nicht mehr woertlich in {PR_VORLAGE_PFAD} (erwartet: "
        f"{NO_STORY_AUSNAHME!r}). Sie ist der Text, den GitHub tatsaechlich in den Body legt - "
        "wandert sie, wandert die Zusicherung mit."
    )
    assert NO_STORY_AUSNAHME in block, (
        f"Der Katalogeintrag {PR_ERSTELLEN_KOPF} nennt die Ausnahme nicht. Er formuliert die "
        "Closing-Zeile sonst ohne Ausnahme (enthaelt die **ausgefuellte** Zeile) und "
        "widerspricht damit der Vorlage. Zwei normative Texte, die einander widersprechen, sind "
        "schlimmer als einer, der schweigt: Zur Laufzeit waehlt der Ablauf selbst, welchem er "
        "folgt - und das Akzeptanzkriterium 'ohne Story entsteht der PR trotzdem' haengt daran."
    )


def test_der_blockschnitt_endet_an_der_naechsten_ueberschrift() -> None:
    """Gegenprobe: ohne sie liefe der Block bis zum Dateiende und bestuende jede Zusage."""
    probe = "### `a`\nInhalt A\n\n### `b`\nInhalt B\n"

    assert katalogeintrag(probe, "### `a`").strip() == "Inhalt A"
    assert katalogeintrag(probe, "### `c`") == ""


@pytest.mark.parametrize(("bezeichnung", "literal"), VERBRAUCHER_ZUSAGEN)
def test_der_auslieferpfad_traegt_die_woertliche_zusage(bezeichnung: str, literal: str) -> None:
    assert literal in verbrauchertext(), (
        f"Die Zusage {bezeichnung!r} steht nicht woertlich in {VERBRAUCHER_PFAD} (erwartet: "
        f"{literal!r}). Der Skill ist LLM-interpretierter Text - was nicht dasteht, gilt nicht."
    )
