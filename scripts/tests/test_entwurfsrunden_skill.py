"""Haelt die mechanisch pruefbaren Zusagen des Skills `penpot-entwurfsrunden` fest.

Der Rundenablauf legt Entwuerfe auf einer Penpot-Arbeitsseite ab und **entfernt nichts** - die
Arbeitsseite wirft Daniel selbst weg. Diese Datei sichert genau die Teile dieser Zusage, die
statisch pruefbar sind; alles Uebrige (dass tatsaechlich gefragt wird, dass Vorschlaege erkennbar
unterschiedlich sind, die Wirkung in Penpot) bleibt Sichtpruefung und wird hier ausdruecklich
**nicht** durch eine erfundene Kennzahl ersetzt.

Fuenf Zusicherungen:

* **Kein umzaeunter Codeblock des Skills enthaelt eine Loeschanweisung.** Das ist die einzige
  mechanische Zusage, dass die Loeschmechanik nicht durch die Hintertuer zurueckkommt - und die
  Hintertuer ist konkret benennbar: ein im Skilltext vorformulierter Schnipsel, den eine Session
  im Aufraeumschritt absetzt, dessen Text also im Moment des Absendens entsteht und den kein
  Review gesehen hat. Geprueft wird ueber die **Codebloecke**, nicht ueber die ganze Datei: Prosa
  darf ueber das Loeschen reden ("der Ablauf entfernt nichts") - sie soll es sogar. Dieselbe
  Abgrenzung wie bei `test_board_befehle_in_skills.py`/`test_issue_befehle_in_skills.py`.
* **Die sechs Markenschluessel stehen vollstaendig im Skill und sind disjunkt** zu den
  Schluesseln, an denen `design/penpot/verify.js` Ansichten und Bausteine wiedererkennt. Beide
  Mengen werden **aus dem jeweiligen Quelltext gelesen**; zwei im Test literal notierte Listen
  waeren disjunkt per Konstruktion und bewiesen nichts. Ein Vorschlagsbrett, das versehentlich
  `ansicht` truege, zaehlte im Ruecklesen als Ansichtsbrett und verschoebe die Kardinalitaeten in
  `verify.js` - und Arbeitsseiten bleiben unbegrenzt liegen, die Zusage muss also dauerhaft
  halten.
* **Kein Bildexport-Aufruf im Skilltext.** Die Rueckkopplung einer Runde ist Daniels Blick in die
  geoeffnete Datei; ein Export je Runde und Vorschlag waere der teuerste Teil des Ablaufs und der
  einzige, der nichts entscheidet.
* **Die woertlichen Zusagen** (Benennungsschema, Vorgabe "drei", Nie-Ueberschreiben-Regel,
  Wiederaufnahme am hoechsten Rundenstand, Brett als direktes Kind der Seitenwurzel, die
  vollstaendig gebliebene Aufraeum-Auskunft samt der neuen Zeile zum eroeffneten Pull Request,
  und die beiden Folgen, die die Antwort "ja" der Abschlussfrage mitnennt).
* **Die abgeloeste Festlegung ist ersetzt, nicht ergaenzt.** Der Satz, der die Nachtraege "in die
  Story, in deren Rahmen der Lauf stattfand" schob, steht nirgends mehr im Skilltext. Die
  Abwesenheit eines **bekannten Literals** ist mechanisch pruefbar - im Unterschied zur
  Abwesenheit einer Idee, und im Unterschied zu einer Prosa-Suche nach "wird nicht gefragt".
  Wo der neue Uebergabeschritt steht und dass sein Anker genau einmal vorkommt, sichert
  `test_ship_entwurf_skill.py` ueber Zeichenoffsets.

**Zur Empfindlichkeit:** Ein Abwesenheits-Test ist per Konstruktion gruen, wenn er nichts sieht -
auch dann, wenn er nichts sehen *kann*. Deshalb traegt **jeder** Erkenner unten eine synthetische
Probe, die belegt, dass er seinen eigenen Verstoss findet, dazu je eine Gegenprobe, die belegt,
dass er den erlaubten Fall stehen laesst. Ein leerer Codeblock-Bestand im Skill ist ein
legitimer - und der sicherste - Zustand; die Aussagekraft dieser Datei haengt deshalb an den
Proben, nicht am Ist-Bestand.

Kein Netzwerk, kein Penpot - gelesen werden ausschliesslich Dateien dieses Repositories.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

SKILL_PFAD = ".claude/skills/penpot-entwurfsrunden/SKILL.md"
VERIFY_PFAD = "design/penpot/verify.js"

# Selbstschutz: Ein leergelaufener oder falsch gelesener Skilltext liesse jede Abwesenheitszusage
# leer wahr werden. Untergrenze bewusst weit unter dem Ist-Stand.
MINDESTLAENGE_SKILL = 3000

# --- Die Markentabelle des Skills --------------------------------------------------------

# Der Kopf der einen Tabelle, die die Plugin-Daten des Rundenablaufs fuehrt. Gelesen wird
# ausschliesslich ihre **Schluessel-Spalte**: Die Beschreibungsspalte nennt die Vokabularwerte
# (darunter `ansicht`), und die sind Werte, keine Schluessel.
MARKEN_TABELLENKOPF = "| Träger | Schlüssel |"

ERWARTETE_MARKEN = frozenset(
    {
        "entwurfslauf",
        "entwurfsumfang",
        "entwurfsmodus",
        "entwurfsbreite",
        "runde",
        "vorschlag",
    }
)

# Die beiden geschlossenen Vokabulare. Sie stehen im Skill in Backticks - eine Aufzaehlung in
# Prosa waere fuer eine LLM-gelesene Anleitung zu weich, um "genau einer aus" zu tragen.
UMFANG_VOKABULAR = ("ansicht", "ausschnitt", "baustein")
MODUS_VOKABULAR = ("alternativen", "verfeinern")

# --- Erkenner ----------------------------------------------------------------------------

# Bewusst mehr als `.remove(`: Wer die Liste auf eine Form verkuerzt, hat ein Verbot, das seine
# naheliegendste Umgehung nicht kennt. Der letzte Eintrag ist die generische Form und faengt
# auch, was hier noch niemand aufgeschrieben hat (`removeAll(`, `deleteBoard(`, ...).
LOESCH_ERKENNER: dict[str, re.Pattern[str]] = {
    "remove": re.compile(r"\.remove\s*\("),
    "removeChild": re.compile(r"\bremoveChild\s*\("),
    "deleteToken": re.compile(r"\bdeleteToken\s*\("),
    "removeToken": re.compile(r"\bremoveToken\s*\("),
    "deleteSet": re.compile(r"\bdeleteSet\s*\("),
    "splice": re.compile(r"\.splice\s*\("),
    "clear": re.compile(r"\.clear\s*\("),
    "generisch": re.compile(r"\.(?:remove|delete)[A-Z]\w*\s*\("),
}

# Aufrufformen, nicht das Wort: Die Prosa des Skills sagt ausdruecklich, dass waehrend der Runden
# kein Bildexport entsteht - ein Wortscan machte genau diesen Satz zum Befund.
EXPORT_ERKENNER: dict[str, re.Pattern[str]] = {
    "export_shape": re.compile(r"\bexport_shape\b"),
    "exportAsync": re.compile(r"\bexportAsync\s*\("),
    "punkt-export": re.compile(r"\.export\s*\("),
}

# --- Woertliche Zusagen ------------------------------------------------------------------

# Jede einzeln, damit ein Ausfall benennt, WELCHE Zusage verschwunden ist, statt einen Sammelfall
# rot zu faerben.
WOERTLICHE_ZUSAGEN: tuple[tuple[str, str], ...] = (
    ("Benennungsschema der Arbeitsseite", "Entwurf — <Bezeichnung>"),
    ("Benennungsschema der Ergebnisseite", "Ansicht — <Anzeigename>"),
    ("Vorgabe fuer die Zahl der Vorschlaege", "drei als Vorgabe"),
    ("Nie-Ueberschreiben-Regel", "Ein Brett einer früheren Runde wird nie überschrieben"),
    ("Wiederaufnahme am hoechsten Rundenstand", "die höchste `runde` ist der Stand"),
    ("Ablage eines Vorschlags", "direktes Kind der Seitenwurzel"),
    ("Der Ablauf entfernt nichts", "Der Ablauf entfernt nichts"),
    # Die Aufraeum-Auskunft bleibt vollstaendig und nennt zusaetzlich den Pull Request.
    ("Zwischenstand nirgends gesichert", "Der Zwischenstand ist nirgends gesichert"),
    (
        "Pull Request in der Aufraeum-Auskunft",
        "der eröffnete Pull Request, falls es einen gibt",
    ),
    # Die Antwortmoeglichkeit "ja" nennt ihre Folge mit - beide Zweige woertlich.
    ("Folge mit Story", "`Closes #NNN`"),
    ("Folge ohne Story", "keine Verknüpfung und keine Board-Bewegung"),
)

# Die abgeloeste Festlegung aus dem Abschlussschritt. Sie ist **ersetzt, nicht ergaenzt**: Ein
# Lauf liefert seine Nachtraege ab jetzt in einem eigenen Pull Request aus, und eine Story ist
# dafuer keine Voraussetzung mehr. Geprueft wird die Abwesenheit eines **bekannten Literals** -
# das ist mechanisch moeglich, anders als die Abwesenheit einer Idee.
ABGELOESTER_SATZ = (
    "Beides gehört in denselben Pull Request wie der fertige Entwurf — in die Story, in deren "
    "Rahmen der Lauf stattfand."
)

# Die beiden Abschnitte, in denen ein vorformulierter Aufruf am gefaehrlichsten waere. Die Zusage
# ist schaerfer als "keine Loeschanweisung darin" und billiger zu pruefen: **ueberhaupt kein**
# umzaeunter Codeblock.
# Der Uebergabeschritt dazwischen steht bewusst **nicht** in dieser Liste: Er traegt den
# Uebergabeblock, und genau deshalb ist er ein eigener Schritt zwischen den beiden geworden.
ABSCHNITTE_OHNE_CODEBLOCK = (
    "## Schritt 6: Abschluss — das Ergebnis wird ausgearbeitet, nicht verschoben",
    "## Schritt 8: Aufräumen ist eine Auskunft — der Ablauf entfernt nichts",
)

_CODEBLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_JS_KONSTANTE = re.compile(r"^const\s+([A-Z][A-Z0-9_]*)\s*=\s*'([^']*)'", re.MULTILINE)
_JS_PLUGINDATA = re.compile(r"getPluginData\(\s*(?:'([^']*)'|([A-Za-z_]\w*))\s*\)")


# --- Duenne Leser ------------------------------------------------------------------------


def skilltext(wurzel: Path = REPO_WURZEL) -> str:
    return (wurzel / SKILL_PFAD).read_text(encoding="utf-8")


def verifytext(wurzel: Path = REPO_WURZEL) -> str:
    return (wurzel / VERIFY_PFAD).read_text(encoding="utf-8")


# --- Reine Funktionen --------------------------------------------------------------------


def codebloecke(text: str) -> list[str]:
    """Reine Funktion: die Inhalte aller mit ``` umzaeunten Bloecke."""
    return _CODEBLOCK.findall(text)


def loesch_funde(bloecke: list[str]) -> list[str]:
    """Reine Funktion: je Fundstelle `<erkenner>: <zeile>` ueber die uebergebenen Bloecke."""
    befunde: list[str] = []
    for block in bloecke:
        for zeile in block.splitlines():
            for name, muster in LOESCH_ERKENNER.items():
                if muster.search(zeile):
                    befunde.append(f"{name}: {zeile.strip()}")
    return befunde


def export_funde(text: str) -> list[str]:
    """Reine Funktion: je Fundstelle `<erkenner>: <zeile>` ueber den gesamten Text."""
    befunde: list[str] = []
    for zeile in text.splitlines():
        for name, muster in EXPORT_ERKENNER.items():
            if muster.search(zeile):
                befunde.append(f"{name}: {zeile.strip()}")
    return befunde


def marken_schluessel(text: str) -> list[str]:
    """Reine Funktion: die Schluessel-Spalte der Markentabelle, in Reihenfolge der Zeilen."""
    zeilen = text.split("\n")
    start: int | None = None
    for nummer, zeile in enumerate(zeilen):
        if zeile.startswith(MARKEN_TABELLENKOPF):
            start = nummer + 2  # Kopfzeile plus Trennzeile
            break
    if start is None:
        return []

    schluessel: list[str] = []
    for zeile in zeilen[start:]:
        if not zeile.startswith("|"):
            break
        spalten = [teil.strip() for teil in zeile.strip().strip("|").split("|")]
        if len(spalten) < 2:
            break
        schluessel.extend(_INLINE_CODE.findall(spalten[1]))
    return schluessel


def verify_schluessel(js: str) -> tuple[set[str], list[str]]:
    """Reine Funktion: die Plugin-Daten-Schluessel aus `verify.js`, plus Ungeloestes.

    Gelesen wird jedes `getPluginData(...)`: ein Zeichenketten-Literal direkt, ein Bezeichner
    ueber die `const NAME = '...'`-Deklarationen derselben Datei. Was sich nicht aufloesen laesst,
    wird **zurueckgegeben statt verschluckt** - sonst schruempfte die Vergleichsmenge still und
    die Disjunktheit waere leer wahr.
    """
    konstanten = dict(_JS_KONSTANTE.findall(js))
    schluessel: set[str] = set()
    ungeloest: list[str] = []
    for literal, bezeichner in _JS_PLUGINDATA.findall(js):
        if literal:
            schluessel.add(literal)
        elif bezeichner in konstanten:
            schluessel.add(konstanten[bezeichner])
        else:
            ungeloest.append(bezeichner)
    return schluessel, ungeloest


def abschnitt(text: str, ueberschrift: str) -> str:
    """Reine Funktion: der Rumpf eines `##`-Abschnitts bis zur naechsten `##`-Ueberschrift."""
    beginn = text.find(ueberschrift)
    if beginn == -1:
        return ""
    rest = text[beginn + len(ueberschrift) :]
    ende = rest.find("\n## ")
    return rest if ende == -1 else rest[:ende]


# --- Selbstschutz ------------------------------------------------------------------------


def test_der_skilltext_hat_eine_plausible_groesse() -> None:
    text = skilltext()

    assert len(text) >= MINDESTLAENGE_SKILL, (
        f"Der Skilltext ist nur {len(text)} Zeichen lang. Entweder ist der Pfad kaputt oder der "
        "Skill leergelaufen - eine Abwesenheitszusage ueber einen leeren Text sagt nichts."
    )


def test_die_geprueften_abschnitte_gibt_es_ueberhaupt() -> None:
    """Ohne diesen Waechter bestuende die Codeblock-Kardinalitaet nach jeder Umbenennung leer."""
    text = skilltext()

    fehlend = [kopf for kopf in ABSCHNITTE_OHNE_CODEBLOCK if kopf not in text]

    assert not fehlend, (
        "Abschnittsueberschrift(en) nicht im Skill gefunden: "
        + "; ".join(fehlend)
        + ". Wandert der Inhalt woanders hin, wandert die Zusicherung mit."
    )


# --- 1. Keine Loeschanweisung in einem Codeblock ------------------------------------------


def test_kein_codeblock_des_skills_enthaelt_eine_loeschanweisung() -> None:
    befunde = loesch_funde(codebloecke(skilltext()))

    assert not befunde, (
        "Loeschanweisung in einem Codeblock von `penpot-entwurfsrunden`. Der Ablauf entfernt "
        "nichts: Die Arbeitsseite wirft Daniel in Penpot selbst weg, und ein vorformulierter "
        "Aufruf im Skilltext ist eine Einladung, ihn abzusetzen. Prosa ueber das Loeschen ist "
        "erlaubt, ein Codeblock nicht: " + "; ".join(befunde)
    )


@pytest.mark.parametrize(
    ("erkenner", "zeile"),
    [
        ("remove", "  brett.remove()"),
        ("removeChild", "  seite.removeChild(brett)"),
        ("deleteToken", "  penpot.library.local.deleteToken(name)"),
        ("removeToken", "  satz.removeToken(name)"),
        ("deleteSet", "  penpot.library.local.deleteSet('entwurf')"),
        ("splice", "  kinder.splice(0, kinder.length)"),
        ("clear", "  seite.children.clear()"),
        ("generisch", "  penpot.removeAllPages()"),
    ],
)
def test_jeder_loesch_erkenner_findet_seinen_eigenen_verstoss(erkenner: str, zeile: str) -> None:
    """Ein Verbot, das seinen eigenen Verstoss nicht erkennt, ist eine Beruhigung."""
    assert LOESCH_ERKENNER[erkenner].search(zeile), (
        f"Der Erkenner {erkenner!r} findet seine eigene Probe nicht."
    )
    assert loesch_funde([f"const seite = penpot.currentPage\n{zeile}\n"])


@pytest.mark.parametrize(
    "text",
    [
        # Prosa ueber das Loeschen steht ausserhalb jedes Codeblocks - und soll es.
        "**Der Ablauf entfernt nichts**: kein Brett, keine Seite, kein Token.\n",
        "Daniel wirft die Seite in Penpot weg (Rechtsklick auf die Seite).\n",
        # Ein harmloser Codeblock bleibt harmlos.
        "```\nEntwurf — Statistik\n```\n",
        "```\nRunde 2, Vorschlag 1 — Arbeitsseite: Entwurf — Statistik\n```\n",
    ],
)
def test_das_erlaubte_gilt_nicht_als_loeschbefund(text: str) -> None:
    assert loesch_funde(codebloecke(text)) == []


def test_der_abschluss_und_der_aufraeumabschnitt_tragen_keinen_codeblock() -> None:
    text = skilltext()

    befunde = [
        f"{kopf}: {len(codebloecke(abschnitt(text, kopf)))} Codeblock/Bloecke"
        for kopf in ABSCHNITTE_OHNE_CODEBLOCK
        if codebloecke(abschnitt(text, kopf))
    ]

    assert not befunde, (
        "Der Abschluss- bzw. Aufraeumabschnitt traegt einen umzaeunten Codeblock. Genau dort "
        "waere ein vorformulierter Aufruf am gefaehrlichsten - die Auskunft wird in Worten "
        "formuliert, nicht abgesetzt: " + "; ".join(befunde)
    )


# --- 2. Die sechs Markenschluessel, disjunkt zu verify.js ---------------------------------


def test_der_skill_nennt_alle_sechs_markenschluessel() -> None:
    gelesen = marken_schluessel(skilltext())

    assert set(gelesen) == ERWARTETE_MARKEN, (
        f"Die Markentabelle fuehrt {sorted(set(gelesen))}, erwartet {sorted(ERWARTETE_MARKEN)}. "
        "Jede zur Fortsetzung noetige Angabe steht als Plugin-Daten an Seite oder Brett - fehlt "
        "eine, ist ein Lauf nach einem Kontextverlust nicht mehr fortsetzbar."
    )
    assert len(gelesen) == len(ERWARTETE_MARKEN), (
        f"Die Markentabelle fuehrt {len(gelesen)} Zeilen mit Schluesseln, erwartet genau "
        f"{len(ERWARTETE_MARKEN)} - je Schluessel eine."
    )


@pytest.mark.parametrize("wort", UMFANG_VOKABULAR + MODUS_VOKABULAR)
def test_die_geschlossenen_vokabulare_stehen_im_skilltext(wort: str) -> None:
    assert f"`{wort}`" in skilltext(), (
        f"Der Wert {wort!r} fehlt im Skilltext. Umfang und Modus sind geschlossene Vokabulare; "
        "ein fehlender Wert macht aus der geschlossenen Auswahl eine offene Frage."
    )


def test_verify_js_liefert_die_erwarteten_wiedererkennungsschluessel() -> None:
    """Selbstschutz: Eine leer gelesene Vergleichsmenge machte die Disjunktheit leer wahr."""
    schluessel, ungeloest = verify_schluessel(verifytext())

    assert not ungeloest, (
        "Nicht aufloesbare(r) getPluginData-Bezeichner in verify.js: " + "; ".join(ungeloest)
    )
    assert {"ansicht", "breite", "schluessel"} <= schluessel, (
        f"verify.js liest {sorted(schluessel)} - erwartet werden mindestens die Schluessel, an "
        "denen Ansichten (`ansicht`/`breite`) und Bausteine (`schluessel`) wiedererkannt werden."
    )


def test_die_entwurfsmarken_sind_disjunkt_zu_dem_was_verify_js_liest() -> None:
    marken = set(marken_schluessel(skilltext()))
    gelesen, _ = verify_schluessel(verifytext())

    ueberschneidung = sorted(marken & gelesen)

    assert not ueberschneidung, (
        f"Entwurfsmarke(n) {ueberschneidung} werden von verify.js als Wiedererkennung gelesen. "
        "Ein Vorschlagsbrett zaehlte damit im Ruecklesen als Ansichtsbrett und verschoebe die "
        "Kardinalitaeten - und Arbeitsseiten bleiben liegen, bis Daniel sie wegwirft."
    )


def test_eine_zur_ansichtsmarke_umbenannte_entwurfsmarke_faellt_auf() -> None:
    """Gegenprobe: ohne sie bestuende die Disjunktheit auch bei kaputtem Tabellenparser."""
    probe = (
        "| Träger | Schlüssel | Wozu |\n"
        "|---|---|---|\n"
        "| Vorschlagsbrett | `ansicht` | faelschlich die Ansichtsmarke |\n"
    )
    gelesen, _ = verify_schluessel(verifytext())

    assert set(marken_schluessel(probe)) & gelesen == {"ansicht"}


# --- 3. Kein Bildexport waehrend der Runden ------------------------------------------------


def test_der_skilltext_enthaelt_keinen_bildexport_aufruf() -> None:
    befunde = export_funde(skilltext())

    assert not befunde, (
        "Bildexport-Aufruf im Skilltext. Die Rueckkopplung einer Runde ist Daniels Blick in die "
        "geoeffnete Datei; ein Export je Runde und Vorschlag waere der teuerste Teil des Ablaufs "
        "und der einzige, der nichts entscheidet: " + "; ".join(befunde)
    )


@pytest.mark.parametrize(
    ("erkenner", "zeile"),
    [
        ("export_shape", "Dann `export_shape` auf das Brett der Runde."),
        ("exportAsync", "  const bild = await brett.exportAsync({ type: 'png' })"),
        ("punkt-export", "  const bild = brett.export({ type: 'png' })"),
    ],
)
def test_jeder_export_erkenner_findet_seinen_eigenen_verstoss(erkenner: str, zeile: str) -> None:
    assert EXPORT_ERKENNER[erkenner].search(zeile)
    assert export_funde(zeile)


@pytest.mark.parametrize(
    "zeile",
    [
        "**Während der Runden entstehen keine Bildexporte.**",
        "Ob am Ende Bilder an einem Pull Request hängen, entscheidet die jeweilige Story.",
    ],
)
def test_prosa_ueber_den_verzicht_gilt_nicht_als_exportbefund(zeile: str) -> None:
    assert export_funde(zeile) == []


# --- 4. Die woertlichen Zusagen ------------------------------------------------------------


@pytest.mark.parametrize(("bezeichnung", "literal"), WOERTLICHE_ZUSAGEN)
def test_der_skill_traegt_die_woertliche_zusage(bezeichnung: str, literal: str) -> None:
    assert literal in skilltext(), (
        f"Die Zusage {bezeichnung!r} steht nicht woertlich im Skill (erwartet: {literal!r}). "
        "Der Skill ist LLM-interpretierter Text - was nicht dasteht, gilt nicht."
    )


def test_die_abgeloeste_festlegung_steht_nicht_mehr_im_skill() -> None:
    """Ersetzt, nicht ergaenzt - sonst stuenden zwei Auslieferwege nebeneinander im Text."""
    assert ABGELOESTER_SATZ not in skilltext(), (
        "Der abgeloeste Satz steht noch im Skill: " + ABGELOESTER_SATZ + " Ein Lauf liefert "
        "seine Nachtraege ab jetzt in einem eigenen Pull Request aus; eine Story ist dafuer "
        "keine Voraussetzung mehr. Zwei Auslieferwege nebeneinander sind schlimmer als der "
        "alte allein - der Ablauf waehlte dann zur Laufzeit selbst."
    )


def test_der_erkenner_fuer_die_abgeloeste_festlegung_findet_sie() -> None:
    """Gegenprobe: Ohne sie bestuende die Abwesenheit auch bei vertipptem Literal."""
    assert ABGELOESTER_SATZ in f"Vorher stand hier: {ABGELOESTER_SATZ} Jetzt nicht mehr."
