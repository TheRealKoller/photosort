"""Haelt den Durchgriff fest: vom Entwurfswunsch im Gespraech bis in den Umsetzungslauf.

Der Abschnitt `## Design` entsteht in `story-entwurf` (dort steht seine Form, genau einmal) und
muss von dort aus zwei Wege ueberleben: den **Einstieg** (`refinement` Schritt 3b, und der
eigenstaendige Aufruf) und den **Ausgang** (`spec-writer` reicht den Block an `ux-ui-designer`
durch, der ihn als Kopf des `## UI/UX`-Abschnitts uebernimmt und den `Schlüssel` aufloest). Erst
damit erreicht der Verweis den Umsetzungslauf, der ausschliesslich die Spec-Datei liest und nie
das Issue.

Wie in `test_story_entwurf_skill.py` gilt: **Die einzige Instanz des Formats liegt ausserhalb des
Repositoriums.** Pruefbar ist allein die Erzeugungs- und Leseanweisung. Diese Datei prueft die
drei **lesenden** Orte und die Landkarte, nicht die Schreibstelle.

Vier Zusicherungsklassen:

1. **Ort ueber Zeichenoffsets.** Schritt 3b liegt zwischen der Ueberschrift von Schritt 3 und der
   von Schritt 5 - das Lohnenswert-Gate urteilt damit ueber die Idee, die die Entwuerfe gezeigt
   haben. Bewusst **nicht** enger gefasst ("vor Schritt 4"): zugesagt ist das Fenster, nicht die
   Nachbarschaft. Die Uebergabe an den gemeinsamen Nachlauf steht am Ende von Schritt 6, **hinter**
   dem Statuswechsel-Versuch: Ein Entwurfslauf darf den Uebergang auf `Ready` nicht aufhalten.
2. **Abschnittsgebundenheit.** Der Satz, der den Skip in `spec-writer` Schritt 2 ausschliesst, steht
   **innerhalb** des Skip-Absatzes. Dateiweit gesucht waere die Zusage wertlos: Genau dort, wo ueber
   den Skip entschieden wird, geht der Durchgriff sonst still verloren - der Absatz ist der einzige
   Text, den ein Ablauf an dieser Stelle liest.
3. **Werte aus den Quelltexten, nicht aus Test-Literalen.** Die drei Feldnamen kommen aus dem
   Definitionsblock in `story-entwurf`, der Modus der ersten Runde aus dem Vokabular von
   `penpot-entwurfsrunden`, das Schluesselmuster aus beiden Dateien im Vergleich. Ein im Test
   notiertes Literal waere gleich per Konstruktion und bewiese ueber den Bestand nichts.
4. **M-S5 an der Verwendungsstelle.** `ux-ui-designer` prueft das Muster selbst und loest ueber
   **Mengenzugehoerigkeit** auf - nie ueber eine zusammengesetzte Pfadangabe, nie ueber einen
   Rohindex. Kein Treffer ist ein Befund, kein Abbruch. Dazu die Gegenrichtung seiner
   Erlaubnisstufe: Er nennt **keine** Operations-ID, liest den Block also als durchgereichten Text
   und nie das Issue.

Jeder Erkenner traegt eine synthetische Probe seines eigenen Verstosses und eine Gegenprobe des
erlaubten Falls; dazu Selbstschutz auf die Existenz jeder Ueberschrift, an der ein Offsetvergleich
haengt.

Kein Netzwerk, kein GitHub, kein Penpot - gelesen werden ausschliesslich Dateien dieses
Repositories.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

REFINEMENT_PFAD = ".claude/skills/refinement/SKILL.md"
SPEC_WRITER_PFAD = ".claude/skills/spec-writer/SKILL.md"
DESIGNER_PFAD = ".claude/agents/ux-ui-designer.md"
STORY_ENTWURF_PFAD = ".claude/skills/story-entwurf/SKILL.md"
RUNDEN_PFAD = ".claude/skills/penpot-entwurfsrunden/SKILL.md"
WORKFLOW_PFAD = "docs/ai-workflow.md"

# Selbstschutz: Ein leergelaufener oder falsch gelesener Text liesse jede Abwesenheits- und jede
# Offsetzusage leer wahr werden. Untergrenzen bewusst weit unter dem Ist-Stand.
MINDESTLAENGEN = {
    REFINEMENT_PFAD: 8000,
    SPEC_WRITER_PFAD: 8000,
    DESIGNER_PFAD: 5000,
    WORKFLOW_PFAD: 8000,
}

# --- 1. Ort ueber Zeichenoffsets ----------------------------------------------------------------

REFINEMENT_SCHRITT_3 = "## Schritt 3: Code und bestehende Specs untersuchen"
REFINEMENT_SCHRITT_3B = "## Schritt 3b: Entwurfsrunden auf ausdrücklichen Wunsch"
REFINEMENT_SCHRITT_4 = "## Schritt 4: Nachfragen bei Unklarheiten"
REFINEMENT_SCHRITT_5 = "## Schritt 5: Lohnenswert-Gate (Devil's Advocate)"
REFINEMENT_SCHRITT_6 = "## Schritt 6: Ergebnis in den Issue-Body schreiben"

REFINEMENT_UEBERSCHRIFTEN = (
    REFINEMENT_SCHRITT_3,
    REFINEMENT_SCHRITT_3B,
    REFINEMENT_SCHRITT_4,
    REFINEMENT_SCHRITT_5,
    REFINEMENT_SCHRITT_6,
)

# Die Marke, an der der Wunsch-Vorbehalt haengt. Ohne sie waere Schritt 3b ein Regelschritt, und
# jede Schaerfung zoege einen Entwurfslauf nach sich.
WUNSCH_MARKER = "**Nur auf ausdrücklichen Wunsch.**"

# Die Marke der Uebergabe am Ende von Schritt 6. Sie steht hinter dem Statuswechsel-Versuch.
UEBERGABE_MARKER = "**Übergabe an den gemeinsamen Nachlauf:**"
STATUS_OPERATION = "board-status-setzen"
SCHREIBOPERATION = "issue-body-schreiben"

NACHLAUF_SKILL = "story-entwurf"
RUNDEN_SKILL = "penpot-entwurfsrunden"

# Die Marke, an der der Vergleichsstand der Drift-Pruefung haengt. Auf diesem Weg entfaellt
# Schritt 0 des Nachlaufs und damit die Lesung, die den Vergleichsstand sonst liefert - ohne die
# Benennung stuende die Drift-Pruefung des Nachlaufs ohne Bezugspunkt da, und eine Auflage, die
# sich nicht ausfuehren laesst, ist keine.
VERGLEICHSSTAND_MARKER = "**Vergleichsstand der Drift-Prüfung:**"

# Die Auflage im Nachlauf, die den Vergleichsstand definiert. Ihr erster Absatz muss **beide**
# Einstiegspunkte nennen, sonst setzt sie stillschweigend voraus, dass Schritt 0 gelaufen ist.
STORY_ENTWURF_AUFLAGEN = "## Die zwölf Sicherheitsauflagen"
DRIFT_AUFLAGE = "**M-S12 — "
EINSTIEGE_IN_DER_AUFLAGE = ("Schritt 0", "`refinement`")

# --- 2. Abschnittsgebundenheit in `spec-writer` --------------------------------------------------

SPEC_WRITER_SCHRITT_2 = "## Schritt 2: UI/UX-Ansatz festlegen"
SKIP_ABSATZ_MARKER = "**Skip-Prüfung**"
SKIP_AUSSCHLUSS_MARKER = "schließt den Skip aus"
DURCHREICH_MARKER = "unverändert an `ux-ui-designer` durchgereicht"

# --- 3. Werte aus den Quelltexten ----------------------------------------------------------------

DESIGN_UEBERSCHRIFT = "## Design"

_CODEBLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
_FELDZEILE = re.compile(r"^\*\*(?P<name>[^*:]+):\*\*")

# Die Zwei-Wert-Form des Modus. Die Drei-Wert-Form des Umfangs faellt durch die Vorausschau heraus,
# sonst zaehlten deren erste beide Werte als Modusvokabular.
_MODUS_VOKABULAR = re.compile(r"genau einer aus `([a-z]+)` / `([a-z]+)`(?! / `)")

# Der Modus, der **mehrere** Vorschlaege je Runde erzeugt - gelesen statt notiert. Die erste Runde
# eines Weg-A-Laufs laeuft in ihm, weil die Zusage "erkennbar verschiedene Ansaetze zur Auswahl"
# genau daran haengt; der andere Modus schaerft eine bereits gewaehlte Fassung.
_AUSWAHLMODUS = re.compile(r"`([a-z]+)`: je Runde mehrere Vorschläge")

# Verankert, geschlossener Zeichenvorrat, gedeckelte Laenge - dieselbe Form wie an der
# Schreibstelle. Gelesen aus beiden Dateien und verglichen: Der Block ueberquert als Text eine
# Zustaendigkeitsgrenze, und eine Verwendungsstelle, die ein anderes Muster prueft, prueft nichts.
_SCHLUESSELMUSTER = re.compile(r"\^\[a-z0-9\]\[a-z0-9-\]\{\d+,\d+\}\$")

# --- 4. M-S5 an der Verwendungsstelle -------------------------------------------------------------

DESIGNER_AUFGABE_2 = "## Aufgabe 2: UI/UX-Ansatz beim Verfeinern von Features"

VIEWS_DATEI = "design/penpot/views.json"

# Die drei Halbsaetze, die aus "aufloesen" eine Mengenzugehoerigkeit machen. Ohne sie bliebe offen,
# **wie** aufgeloest wird - und genau die verworfenen Wege (zusammengesetzte Pfadangabe, Rohindex
# auf das geparste Objekt) sind die, die aus einem Wert einen Zugriff machen.
AUFLOESUNGS_MARKER = ("Mengenzugehörigkeit", "zusammengesetzte Pfadangabe", "Rohindex")

# Kein Treffer haelt den Ablauf nicht an: Der Entwurfs-Pull-Request kann noch offen sein, waehrend
# die Spec entsteht. Ein Abbruch machte den Regelfall zum Fehlerfall.
FEHLTREFFER_MARKER = ("offener Punkt", "kein Abbruch")

# Derselbe Erkennungsraum wie im Katalogtest: die vier fuer Operations-IDs reservierten Praefixe.
_ID_VERWENDUNG = re.compile(r"`((?:issue|board|pr|copilot)-[a-z][a-z-]*)`")

# --- Die Landkarte ---------------------------------------------------------------------------

WORKFLOW_TABELLE_UEBERSCHRIFT = "## Der Workflow als eine Tabelle"
ROLLEN_UEBERSCHRIFT = "## Rollen-Landkarte: warum Agent oder Skill, wo ausgeführt"

# Die zwei Einstiegspunkte, in der Zeile der Rollen-Landkarte benannt: aus dem Schaerfungsgespraech
# heraus (Weg A) und eigenstaendig zu einer bereits geschaerften Story (Weg B). Eine Zeile, die nur
# den Skill nennt, sagt nicht, wie man dorthin kommt.
EINSTIEGE = ("`refinement`", "`Ready`")


# --- Duenne Leser -------------------------------------------------------------------------


def dateitext(pfad: str, wurzel: Path = REPO_WURZEL) -> str:
    return (wurzel / pfad).read_text(encoding="utf-8")


# --- Reine Funktionen ----------------------------------------------------------------------


def offset(text: str, literal: str) -> int:
    """Reine Funktion: der Zeichenoffset eines Literals; -1, wenn es fehlt."""
    return text.find(literal)


def abschnitt(text: str, ueberschrift: str) -> str:
    """Reine Funktion: der Rumpf eines `##`-Abschnitts bis zur naechsten `##`-Ueberschrift.

    **Umzaeunte Bloecke begrenzen nicht.** `refinement` Schritt 6 zeigt die Vorlage des
    Issue-Bodys als umzaeunten Block, und die traegt ihrerseits `## Ziel` am Zeilenanfang. Eine
    Suche nach der naechsten `##`-Zeile schnitte den Abschnitt genau dort ab - der Rumpf endete
    vor der Haelfte, und jede Zusage ueber seinen hinteren Teil waere still leer wahr.
    """
    beginn = text.find(ueberschrift)
    if beginn == -1:
        return ""
    rest = text[beginn + len(ueberschrift) :]
    im_zaun = False
    gelesen = 0
    for zeile in rest.split("\n"):
        if zeile.startswith("```"):
            im_zaun = not im_zaun
        elif not im_zaun and zeile.startswith("## "):
            return rest[:gelesen]
        gelesen += len(zeile) + 1
    return rest


def absatz(text: str, marker: str) -> str:
    """Reine Funktion: der Absatz ab `marker` bis zur naechsten Leerzeile.

    Der Absatz, nicht der Abschnitt: Ein Satz, der die Skip-Entscheidung bedingt, muss dort stehen,
    wo sie getroffen wird. Zwei Absaetze weiter unten ist er Prosa ueber den Ablauf.
    """
    beginn = text.find(marker)
    if beginn == -1:
        return ""
    rest = text[beginn:]
    ende = rest.find("\n\n")
    return rest if ende == -1 else rest[:ende]


def codebloecke(text: str) -> list[str]:
    """Reine Funktion: die Inhalte aller mit ``` umzaeunten Bloecke."""
    return _CODEBLOCK.findall(text)


def design_feldnamen(text: str) -> tuple[str, ...]:
    """Reine Funktion: die Feldnamen aus dem Definitionsblock des Abschnitts `## Design`.

    Gelesen aus der einen Definitionsstelle statt im Test notiert: Die lesenden Dateien muessen
    ueber **dieselben** Felder reden wie die schreibende, sonst reicht `spec-writer` einen Block
    durch, den `ux-ui-designer` an anderen Namen sucht.
    """
    for block in codebloecke(text):
        zeilen = block.split("\n")
        if not any(zeile.strip() == DESIGN_UEBERSCHRIFT for zeile in zeilen):
            continue
        namen = tuple(
            treffer.group("name") for zeile in zeilen if (treffer := _FELDZEILE.match(zeile))
        )
        if namen:
            return namen
    return ()


def modusvokabular(text: str) -> set[tuple[str, ...]]:
    """Reine Funktion: die Fundstellen des zweiwertigen Modusvokabulars."""
    return {tuple(treffer) for treffer in _MODUS_VOKABULAR.findall(text)}


def auswahlmodus(text: str) -> set[str]:
    """Reine Funktion: der Modus, der je Runde mehrere Vorschlaege erzeugt."""
    return set(_AUSWAHLMODUS.findall(text))


def schluesselmuster(text: str) -> set[str]:
    """Reine Funktion: die Menge der im Text vorkommenden Schluesselmuster."""
    return set(_SCHLUESSELMUSTER.findall(text))


def operations_ids(text: str) -> set[str]:
    """Reine Funktion: die Menge der in Backticks genannten Operations-IDs."""
    return set(_ID_VERWENDUNG.findall(text))


def tabellenzeilen(text: str, inhalt: str) -> list[str]:
    """Reine Funktion: die Tabellenzeilen eines Abschnitts, die `inhalt` fuehren."""
    return [zeile for zeile in text.split("\n") if zeile.startswith("|") and inhalt in zeile]


# --- Selbstschutz ---------------------------------------------------------------------------


@pytest.mark.parametrize(("pfad", "mindestens"), sorted(MINDESTLAENGEN.items()))
def test_die_gelesenen_dateien_haben_eine_plausible_groesse(pfad: str, mindestens: int) -> None:
    laenge = len(dateitext(pfad))

    assert laenge >= mindestens, (
        f"{pfad} ist nur {laenge} Zeichen lang. Entweder ist der Pfad kaputt oder die Datei "
        "leergelaufen - eine Offset- oder Abwesenheitszusage ueber einen leeren Text sagt nichts."
    )


@pytest.mark.parametrize("ueberschrift", REFINEMENT_UEBERSCHRIFTEN)
def test_die_geprueften_refinement_ueberschriften_gibt_es(ueberschrift: str) -> None:
    """Ohne diesen Waechter bestuenden die Offsetvergleiche nach jeder Umbenennung leer."""
    assert ueberschrift in dateitext(REFINEMENT_PFAD), (
        f"Ueberschrift {ueberschrift!r} steht nicht in {REFINEMENT_PFAD}. Wandert der Inhalt "
        "woanders hin, wandert die Zusicherung mit."
    )


@pytest.mark.parametrize(
    ("pfad", "ueberschrift"),
    [
        (SPEC_WRITER_PFAD, SPEC_WRITER_SCHRITT_2),
        (DESIGNER_PFAD, DESIGNER_AUFGABE_2),
        (WORKFLOW_PFAD, WORKFLOW_TABELLE_UEBERSCHRIFT),
        (WORKFLOW_PFAD, ROLLEN_UEBERSCHRIFT),
    ],
)
def test_die_uebrigen_geprueften_ueberschriften_gibt_es(pfad: str, ueberschrift: str) -> None:
    assert ueberschrift in dateitext(pfad), (
        f"Ueberschrift {ueberschrift!r} steht nicht in {pfad}. Jede abschnittsgebundene Zusage "
        "haengt daran; ohne die Ueberschrift ist sie leer wahr."
    )


# --- 1. Schritt 3b: Ort, Vorbehalt, Modus ---------------------------------------------------------


def test_schritt_3b_liegt_zwischen_der_recherche_und_dem_lohnenswert_gate() -> None:
    """Das Fenster ist die Zusage, nicht die Nachbarschaft.

    Vor dem Gate, weil es ueber die Idee urteilen soll, die die Entwuerfe **gezeigt** haben;
    hinter der Recherche, weil ein Entwurf, der einem bestehenden Bildschirm widerspricht, ohne
    sie nicht als Widerspruch auffaellt. Ob Schritt 4 davor oder dahinter liegt, ist nirgends
    zugesagt und wird hier deshalb auch nicht verlangt.
    """
    text = dateitext(REFINEMENT_PFAD)

    recherche = offset(text, REFINEMENT_SCHRITT_3)
    runden = offset(text, REFINEMENT_SCHRITT_3B)
    gate = offset(text, REFINEMENT_SCHRITT_5)

    assert -1 not in (recherche, runden, gate)
    assert recherche < runden < gate, (
        f"Recherche bei {recherche}, Schritt 3b bei {runden}, Lohnenswert-Gate bei {gate}. "
        "Erwartet ist aufsteigend: Hinter dem Gate waeren die Entwuerfe fuer das Urteil zu spaet, "
        "vor der Recherche entstuenden sie ohne Kenntnis dessen, was es schon gibt."
    )


@pytest.mark.parametrize(
    ("probe", "erwartet_gueltig"),
    [
        ("...DREI...DREIB...FUENF...", True),
        ("...DREI...FUENF...DREIB...", False),
        ("...DREIB...DREI...FUENF...", False),
    ],
)
def test_der_fenstervergleich_unterscheidet_alle_lagen(probe: str, erwartet_gueltig: bool) -> None:
    """Gegenprobe an synthetischem Text - sonst bestuende die Ortszusage bei jeder Lage."""
    lagen = (offset(probe, "DREI"), offset(probe, "DREIB"), offset(probe, "FUENF"))

    assert (lagen[0] < lagen[1] < lagen[2]) is erwartet_gueltig


def test_schritt_3b_laeuft_nur_auf_ausdruecklichen_wunsch() -> None:
    """Ohne den Vorbehalt zoege jede Schaerfung einen Entwurfslauf nach sich.

    Geprueft wird die Marke, nicht das Verhalten: Ob der Ablauf den Schritt zur Laufzeit wirklich
    nur auf Ansage geht, ist eine Eigenschaft eines LLM-interpretierten Textes und bewusst
    ungeprueft (siehe Teststrategie der Spec 0452).
    """
    rumpf = abschnitt(dateitext(REFINEMENT_PFAD), REFINEMENT_SCHRITT_3B)

    assert WUNSCH_MARKER in rumpf, (
        f"In Schritt 3b steht keine Zeile {WUNSCH_MARKER!r}. Ein Schritt ohne Vorbehalt ist ein "
        "Regelschritt - und ein Entwurfslauf je Idee ist genau das, was niemand wollte."
    )


def test_schritt_3b_nennt_die_beiden_ablaeufe_die_er_benutzt() -> None:
    """Der Rundenablauf baut, der Nachlauf heftet an. Fehlt einer, endet der Weg auf halber Strecke."""
    rumpf = abschnitt(dateitext(REFINEMENT_PFAD), REFINEMENT_SCHRITT_3B)

    fehlend = [name for name in (RUNDEN_SKILL, NACHLAUF_SKILL) if f"`{name}`" not in rumpf]

    assert not fehlend, (
        f"Schritt 3b nennt nicht: {fehlend}. Ohne den Rundenablauf entstehen keine Entwuerfe, "
        "ohne den Nachlauf erreicht das Ergebnis die Story nie."
    )


def test_die_erste_runde_laeuft_im_auswahlmodus() -> None:
    """Beide Werte kommen aus Quelltexten - zwei Test-Literale waeren gleich per Konstruktion."""
    runden = dateitext(RUNDEN_PFAD)
    vokabular = modusvokabular(runden)

    assert len(vokabular) == 1, (
        f"{RUNDEN_PFAD} fuehrt {sorted(vokabular)} als Modusvokabular, erwartet genau eine "
        "Fassung. Null heisst: nicht mehr maschinell lesbar, und die Zusage waere leer wahr."
    )
    modi = set(next(iter(vokabular)))

    gewaehlt = auswahlmodus(runden)
    assert len(gewaehlt) == 1, (
        f"Der Modus mit mehreren Vorschlaegen je Runde ist in {RUNDEN_PFAD} nicht mehr eindeutig "
        f"bestimmbar: {sorted(gewaehlt)}."
    )
    assert gewaehlt < modi, (
        f"Der Auswahlmodus {sorted(gewaehlt)} steht nicht im Vokabular {sorted(modi)}."
    )

    rumpf = abschnitt(dateitext(REFINEMENT_PFAD), REFINEMENT_SCHRITT_3B)
    genannt = {modus for modus in modi if f"`{modus}`" in rumpf}

    assert genannt == gewaehlt, (
        f"Schritt 3b nennt {sorted(genannt)} als Modus der ersten Runde, erwartet "
        f"{sorted(gewaehlt)}. Zugesagt sind mehrere erkennbar verschiedene Ansaetze **zur "
        "Auswahl**; der andere Modus schaerft eine Fassung, die noch niemand gewaehlt hat."
    )


# --- 1b. Die Uebergabe am Ende von Schritt 6 -------------------------------------------------------


def test_die_uebergabe_steht_hinter_dem_statuswechsel_versuch() -> None:
    """Erst `Ready`, dann der Entwurf.

    Der Statuswechsel ist der Abschluss der Schaerfung und die Vorbedingung der Freigabe, die der
    Nachlauf gleich darauf am Board liest. Stuende die Uebergabe davor, liefe der Nachlauf gegen
    einen Wert, den derselbe Ablauf erst noch schreiben wollte - fail-closed hiesse dann: nie
    ausliefern.
    """
    rumpf = abschnitt(dateitext(REFINEMENT_PFAD), REFINEMENT_SCHRITT_6)

    status = offset(rumpf, f"`{STATUS_OPERATION}`")
    uebergabe = offset(rumpf, UEBERGABE_MARKER)

    assert status != -1, (
        f"In {REFINEMENT_SCHRITT_6!r} steht kein `{STATUS_OPERATION}` mehr - dann ist die "
        "Reihenfolgezusage leer wahr."
    )
    assert uebergabe != -1, (
        f"In {REFINEMENT_SCHRITT_6!r} steht keine Zeile {UEBERGABE_MARKER!r}. Ohne sie endet Weg A "
        "mit dem Rundenstand im Gespraech, und der Entwurf erreicht die Story nie."
    )
    assert status < uebergabe, (
        f"Statuswechsel bei {status}, Uebergabe bei {uebergabe}. Erwartet ist aufsteigend."
    )


def test_die_uebergabe_benennt_den_vergleichsstand_der_drift_pruefung() -> None:
    """Die Luecke, die `Schritte 0 bis 2 entfallen` aufreisst.

    Der Nachlauf liest den Body unmittelbar vor jedem Schreibzugriff neu und vergleicht ihn gegen
    den Stand vom Laufbeginn - auf dem eigenstaendigen Weg ist das die Lesung aus seinem Schritt 0.
    Aus der Schaerfung heraus laeuft Schritt 0 nicht, und damit gaebe es keinen Bezugspunkt: Die
    Drift-Pruefung stuende ohne Vergleichsstand da, waehrend zwischen dem Schreibzugriff hier und
    dem Anheften der vollstaendige Ausarbeitungslauf liegt - genau das Zeitfenster, fuer das die
    Auflage geschrieben ist.
    """
    rumpf = abschnitt(dateitext(REFINEMENT_PFAD), REFINEMENT_SCHRITT_6)

    uebergabe = offset(rumpf, UEBERGABE_MARKER)
    vergleichsstand = offset(rumpf, VERGLEICHSSTAND_MARKER)

    assert vergleichsstand != -1, (
        f"In {REFINEMENT_SCHRITT_6!r} steht keine Zeile {VERGLEICHSSTAND_MARKER!r}. Ohne sie "
        "uebergibt dieser Ablauf einen Auftrag, dessen Drift-Schranke keinen Bezugspunkt hat."
    )
    assert uebergabe < vergleichsstand, (
        f"Uebergabe bei {uebergabe}, Vergleichsstand bei {vergleichsstand}. Der Vergleichsstand "
        "gehoert zur Uebergabe; davor stehend haengt er an keinem Auftrag."
    )
    assert f"`{SCHREIBOPERATION}`" in absatz(rumpf, VERGLEICHSSTAND_MARKER), (
        f"Der Absatz nennt `{SCHREIBOPERATION}` nicht. Der Vergleichsstand ist kein beliebiger "
        "Stand, sondern genau der Body, den dieser Schritt selbst geschrieben hat - ohne die "
        "Quelle bliebe offen, wogegen der Nachlauf vergleicht."
    )


def test_die_drift_auflage_des_nachlaufs_kennt_beide_einstiegspunkte() -> None:
    """Die Gegenseite derselben Zusage, im Nachlauf.

    Eine Auflage, die ihren Vergleichsstand nur fuer einen von zwei Einstiegspunkten definiert,
    laesst sich auf dem anderen nicht ausfuehren - und eine Auflage, die sich nicht ausfuehren
    laesst, ist keine. Geprueft wird der **erste Absatz** der Auflage: Dort steht, was gilt.
    """
    auflagen = abschnitt(dateitext(STORY_ENTWURF_PFAD), STORY_ENTWURF_AUFLAGEN)
    erster_absatz = absatz(auflagen, DRIFT_AUFLAGE)

    assert erster_absatz, (
        f"In {STORY_ENTWURF_AUFLAGEN!r} steht keine Auflage {DRIFT_AUFLAGE!r} mehr - dann ist "
        "diese Zusage eine Aussage ueber nichts."
    )

    fehlend = [marke for marke in EINSTIEGE_IN_DER_AUFLAGE if marke not in erster_absatz]

    assert not fehlend, (
        f"Der erste Absatz der Drift-Auflage nennt {fehlend} nicht: {erster_absatz!r}. Er muss "
        "beide Einstiegspunkte benennen - die eigene Lesung aus Schritt 0 und den vom aufrufenden "
        "Ablauf zuletzt geschriebenen Body -, statt Schritt 0 stillschweigend vorauszusetzen."
    )


def test_der_auflagenabsatz_zaehlt_nur_den_ersten_absatz_der_auflage() -> None:
    """Probe und Gegenprobe: Was zwei Absaetze spaeter steht, ist Erlaeuterung, nicht die Regel."""
    probe = (
        f"{DRIFT_AUFLAGE}Der Vergleichsstand ist definiert.**\n\n"
        "Zweiter Absatz, in dem `refinement` nur beilaeufig vorkommt.\n"
    )

    assert "`refinement`" not in absatz(probe, DRIFT_AUFLAGE)
    assert "`refinement`" in absatz(probe.replace("\n\n", " "), DRIFT_AUFLAGE)


def test_die_uebergabe_nennt_den_gemeinsamen_nachlauf() -> None:
    rumpf = abschnitt(dateitext(REFINEMENT_PFAD), REFINEMENT_SCHRITT_6)

    assert f"`{NACHLAUF_SKILL}`" in absatz(rumpf, UEBERGABE_MARKER), (
        f"Der Uebergabe-Absatz nennt `{NACHLAUF_SKILL}` nicht. Der Nachlauf existiert genau "
        "einmal; ein zweiter, hier ausformulierter Anheft-Ablauf waere der Drift-Fall."
    )


# --- 2. Der Skip-Ausschluss in `spec-writer` -------------------------------------------------------


def test_der_skip_ausschluss_steht_im_skip_absatz_selbst() -> None:
    """Abschnittsgebunden, nicht dateiweit.

    Die Skip-Frage wird in genau diesem Absatz entschieden. Ein Satz zwei Absaetze weiter unten
    ist Prosa ueber den Ablauf und aendert die Entscheidung nicht - dateiweit gesucht waere der
    Test gruen, waehrend der Durchgriff an der einen Stelle verloren geht, an der er zaehlt.
    """
    schritt = abschnitt(dateitext(SPEC_WRITER_PFAD), SPEC_WRITER_SCHRITT_2)
    skip = absatz(schritt, SKIP_ABSATZ_MARKER)

    assert skip, (
        f"In {SPEC_WRITER_SCHRITT_2!r} steht kein Absatz {SKIP_ABSATZ_MARKER!r} mehr. Ohne ihn "
        "gibt es keine Stelle, an der der Ausschluss wirken koennte."
    )
    assert SKIP_AUSSCHLUSS_MARKER in skip, (
        f"Der Skip-Absatz sagt nicht {SKIP_AUSSCHLUSS_MARKER!r}. Ein vorhandener "
        f"{DESIGN_UEBERSCHRIFT}-Abschnitt ist per Bauart ein konkret benennbarer Anhaltspunkt fuer "
        "eine sichtbare Oberflaeche; wird trotzdem uebersprungen, endet der Verweis hier."
    )
    assert DESIGN_UEBERSCHRIFT in skip, (
        "Der Skip-Absatz benennt den ausschliessenden Abschnitt nicht. Ein Ausschluss ohne "
        "Gegenstand ist zur Laufzeit keiner."
    )


def test_der_abschnittsschnitt_endet_an_der_naechsten_ueberschrift() -> None:
    """Gegenprobe: ohne sie liefe der Rumpf bis zum Dateiende und bestuende jede Zusage."""
    probe = "## A\nInhalt A\n\n## B\nInhalt B\n"

    assert abschnitt(probe, "## A").strip() == "Inhalt A"
    assert abschnitt(probe, "## C") == ""


def test_der_abschnittsschnitt_uebergeht_ueberschriften_in_umzaeunten_bloecken() -> None:
    """Die Falle, an der die naive Fassung still danebengriff.

    Die Vorlage des Issue-Bodys steht als umzaeunter Block mitten im Abschnitt und fuehrt `## Ziel`
    am Zeilenanfang. Wer dort abschneidet, prueft den halben Abschnitt und haelt das Ergebnis fuer
    eine Abwesenheit.
    """
    probe = "## A\nVor dem Block\n\n```markdown\n## Ziel\n\n<Text>\n```\n\nNach dem Block\n\n## B\nInhalt B\n"

    rumpf = abschnitt(probe, "## A")

    assert "Nach dem Block" in rumpf
    assert "Inhalt B" not in rumpf


def test_der_absatzschnitt_endet_an_der_leerzeile() -> None:
    """Gegenprobe: ohne sie liefe der Absatz bis zum Abschnittsende und bestuende jede Zusage."""
    probe = (
        f"{SKIP_ABSATZ_MARKER}: kurzer Absatz.\n\nZwei Absaetze weiter: {SKIP_AUSSCHLUSS_MARKER}."
    )

    assert SKIP_AUSSCHLUSS_MARKER not in absatz(probe, SKIP_ABSATZ_MARKER)
    assert SKIP_AUSSCHLUSS_MARKER in absatz(probe.replace("\n\n", " "), SKIP_ABSATZ_MARKER)


def test_der_absatzschnitt_meldet_einen_fehlenden_marker_als_leer() -> None:
    assert absatz("Nur Prosa, kein Marker.\n", SKIP_ABSATZ_MARKER) == ""


def test_spec_writer_reicht_den_block_unveraendert_durch() -> None:
    """Durchgereicht, nicht zusammengefasst: Was hier neu formuliert wuerde, ist neuer Inhalt."""
    schritt = abschnitt(dateitext(SPEC_WRITER_PFAD), SPEC_WRITER_SCHRITT_2)

    assert DURCHREICH_MARKER in schritt, (
        f"In {SPEC_WRITER_SCHRITT_2!r} steht nicht {DURCHREICH_MARKER!r}. Der Block ist der Kanal; "
        "eine Zusammenfassung davon waere ein zweiter, unkontrollierter."
    )
    assert f"`{NACHLAUF_SKILL}`" in schritt, (
        f"{SPEC_WRITER_SCHRITT_2!r} nennt `{NACHLAUF_SKILL}` nicht - die Form des Blocks steht dort "
        "und wird hier verwiesen, nicht kopiert."
    )


# --- 3./4. Die Verwendungsstelle in `ux-ui-designer` -----------------------------------------------


def test_die_drei_feldnamen_stehen_in_aufgabe_2() -> None:
    """Die Namen kommen aus der einen Definitionsstelle, nicht aus einem Test-Literal."""
    felder = design_feldnamen(dateitext(STORY_ENTWURF_PFAD))

    assert len(felder) == 3, (
        f"Im Definitionsblock von {STORY_ENTWURF_PFAD} stehen {list(felder)}, erwartet genau drei "
        "Felder. Ohne sie ist die Durchgriff-Zusage eine Aussage ueber nichts."
    )

    rumpf = abschnitt(dateitext(DESIGNER_PFAD), DESIGNER_AUFGABE_2)
    fehlend = [feld for feld in felder if f"`{feld}`" not in rumpf]

    assert not fehlend, (
        f"{DESIGNER_AUFGABE_2!r} nennt die Felder {fehlend} nicht. Der Block wird dort zum Kopf "
        f"des `## UI/UX`-Abschnitts; ein Feld, das der lesende Ablauf nicht kennt, faellt beim "
        "Uebernehmen still weg."
    )


def test_der_feldnamen_leser_liest_nur_die_definitionsform() -> None:
    """Gegenprobe: eine Prosa-Erwaehnung ist keine Definition, ein Block ohne Ueberschrift auch nicht."""
    block = (
        "```markdown\n"
        f"{DESIGN_UEBERSCHRIFT}\n\n"
        "**Stand:** ausgearbeitet\n"
        "**Penpot-Seite:** Ansicht — Projektübersicht\n"
        "**Schlüssel:** uebersicht\n"
        "```\n"
    )

    assert design_feldnamen(block) == ("Stand", "Penpot-Seite", "Schlüssel")
    assert design_feldnamen("Die Felder `Stand`, `Penpot-Seite` und `Schlüssel`.\n") == ()
    assert design_feldnamen("```markdown\n**Stand:** ausgearbeitet\n```\n") == ()


def test_die_verwendungsstelle_prueft_dasselbe_schluesselmuster_wie_die_schreibstelle() -> None:
    """Gelesen, nicht notiert: Der Block ueberquert als Text eine Zustaendigkeitsgrenze."""
    muster = {
        pfad: schluesselmuster(dateitext(pfad)) for pfad in (STORY_ENTWURF_PFAD, DESIGNER_PFAD)
    }

    leer = sorted(pfad for pfad, werte in muster.items() if not werte)
    assert not leer, (
        f"Kein Schluesselmuster gefunden in: {leer}. An der Verwendungsstelle ungeprueft heisst: "
        "Der Wert wandert aus einem oeffentlichen Issue-Body ungeprueft in eine Nachschlagung."
    )

    mehrdeutig = sorted(pfad for pfad, werte in muster.items() if len(werte) != 1)
    assert not mehrdeutig, f"Mehr als ein Schluesselmuster in: {mehrdeutig}."

    assert len({next(iter(werte)) for werte in muster.values()}) == 1, (
        f"Schreibstelle und Verwendungsstelle fuehren verschiedene Muster: "
        f"{ {pfad: sorted(werte) for pfad, werte in muster.items()} }."
    )


def test_die_aufloesung_laeuft_ueber_mengenzugehoerigkeit() -> None:
    """Wie aufgeloest wird, ist die Zusage - nicht dass aufgeloest wird."""
    rumpf = abschnitt(dateitext(DESIGNER_PFAD), DESIGNER_AUFGABE_2)

    fehlend = [marke for marke in (*AUFLOESUNGS_MARKER, VIEWS_DATEI) if marke not in rumpf]

    assert not fehlend, (
        f"{DESIGNER_AUFGABE_2!r} nennt nicht: {fehlend}. Eine zusammengesetzte Pfadangabe und ein "
        "Rohindex auf das geparste Objekt sind genau die beiden Wege, auf denen aus einem "
        "geprueften Wert doch noch ein Zugriff ausserhalb der Menge wird."
    )


def test_ein_fehltreffer_ist_ein_benannter_offener_punkt_und_kein_abbruch() -> None:
    rumpf = abschnitt(dateitext(DESIGNER_PFAD), DESIGNER_AUFGABE_2)

    fehlend = [marke for marke in FEHLTREFFER_MARKER if marke not in rumpf]

    assert not fehlend, (
        f"{DESIGNER_AUFGABE_2!r} nennt nicht: {fehlend}. Solange der Entwurfs-Pull-Request offen "
        "ist, laesst sich der Schluessel im Repository nicht aufloesen - das ist der Regelfall "
        "und darf weder abbrechen noch stillschweigend wegfallen."
    )


def test_der_designer_nennt_keine_einzige_operations_id() -> None:
    """Die Gegenrichtung seiner Erlaubnisstufe.

    Er liest den Block als durchgereichten Text, nie das Issue. Die Stufe selbst steht in der
    eingefrorenen Tabelle des Katalogtests; hier steht, dass sie auch gelebt wird - eine genannte
    Operation waere der erste Schritt zum eigenen Zugriff.
    """
    genannt = operations_ids(dateitext(DESIGNER_PFAD))

    assert genannt == set(), (
        f"{DESIGNER_PFAD} nennt Operations-IDs: {sorted(genannt)}. Der Agent traegt 'kein "
        "GitHub-Zugriff'; der `## Design`-Block erreicht ihn ausschliesslich als durchgereichter "
        "Text aus `spec-writer`."
    )


def test_der_id_erkenner_findet_eine_eingeschmuggelte_operation() -> None:
    """Mutationsprobe zur Abwesenheitszusage oben.

    Der Bestand ist sauber, jene Zusage startet also gruen - ein Rot-Lauf belegt dort nichts. Ohne
    diese Probe waere ein kaputtes Muster von einem echten Nullbefund nicht zu unterscheiden.
    """
    assert operations_ids("Lies vorher `issue-lesen` und setz `board-status-setzen`.\n") == {
        "issue-lesen",
        "board-status-setzen",
    }
    assert operations_ids("Der Abschnitt `## Design` wird durchgereicht.\n") == set()


# --- Die Landkarte ---------------------------------------------------------------------------


def test_die_workflow_tabelle_fuehrt_den_neuen_skill() -> None:
    rumpf = abschnitt(dateitext(WORKFLOW_PFAD), WORKFLOW_TABELLE_UEBERSCHRIFT)
    zeilen = tabellenzeilen(rumpf, f"`{NACHLAUF_SKILL}`")

    assert len(zeilen) == 1, (
        f"{len(zeilen)} Zeilen mit `{NACHLAUF_SKILL}` in der Schritt-Tabelle, erwartet genau eine. "
        "Die Tabelle ist die einzige Stelle fuer den Gesamtueberblick; ein Schritt, der dort "
        "fehlt, existiert fuer jeden Leser von aussen nicht."
    )


def test_die_rollen_landkarte_nennt_beide_einstiegspunkte() -> None:
    rumpf = abschnitt(dateitext(WORKFLOW_PFAD), ROLLEN_UEBERSCHRIFT)
    zeilen = tabellenzeilen(rumpf, f"`{NACHLAUF_SKILL}`")

    assert len(zeilen) == 1, (
        f"{len(zeilen)} Zeilen mit `{NACHLAUF_SKILL}` in der Rollen-Landkarte, erwartet genau eine."
    )

    fehlend = [einstieg for einstieg in EINSTIEGE if einstieg not in zeilen[0]]

    assert not fehlend, (
        f"Die Zeile nennt {fehlend} nicht: {zeilen[0]!r}. Der Skill hat zwei Einstiegspunkte - aus "
        "der Schaerfung heraus und eigenstaendig zu einer bereits geschaerften Story. Eine Zeile, "
        "die nur den Skill nennt, sagt nicht, wie man dorthin kommt."
    )


def test_der_tabellenzeilen_leser_trennt_zeile_von_fliesstext() -> None:
    """Gegenprobe: eine Erwaehnung im Fliesstext ist keine Tabellenzeile."""
    probe = f"| a | `{NACHLAUF_SKILL}` |\nDer Skill `{NACHLAUF_SKILL}` steht daneben.\n"

    assert tabellenzeilen(probe, f"`{NACHLAUF_SKILL}`") == [f"| a | `{NACHLAUF_SKILL}` |"]
