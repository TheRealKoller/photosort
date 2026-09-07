"""Bindet das Figma-Farbregister an den Code und an den gemessenen Nachweis des Board-Laufs.

Diese Story (`specs/features/0336-figma-board-farbvariablen.md`, ADR 0062) bindet jeden der 418
fest eingetragenen Farbwerte des Figma-Boards `photosort-design-system` an eine Variable. Ihre
Wirkung tritt damit in einer **fremden Datei** ein, nicht im Repository - ein Pull Request kann
das nicht zeigen, nur behaupten. Diese Pruefung ist die Gegenmassnahme. Sie liest ausschliesslich
Dateien dieses Repositories: kein Netzwerk, kein MCP-Werkzeug, kein Aufrufkontingent.

**Die fuenf Gegenstaende, in der Reihenfolge ihrer Klassen:**

1. `TestRegisterForm` - der Registerblock in `scripts/figma/board-farbvariablen.js` (AK4/AK5):
   Namen, Zeichenvorrat mit echten Umlauten, Gruppenvokabular, Scopes, Beschreibungen, die zwei
   Korrekturvermerke.
2. `TestRegisterGegenIndexCss` - die geteilte Farbhoheit (AK8): 23 Figma-Werte und 17 code-eigene
   Werte sind disjunkt, und ihre Vereinigung ist **exakt** die Menge der verschiedenen Hexwerte
   aus dem `:root`-Block von `frontend/src/index.css`. Ein neuer Farbwert dort faerbt rot, bis
   jemand ihn einer Seite der Grenze zuordnet - genau das ist der Zweck.
3. `TestPayloadForm` - der Payload als Form: der Registerblock ist strikt JSON-parsbar und im
   ausgefuehrten Payload eingebettet (das Gepruefte **ist** das Ausgefuehrte), der
   `NUR_PRUEFEN`-Schalter liegt vor der ersten Schreiboperation, die byteweise Verbotsliste (M2)
   haelt, und `node --check` uebersetzt die Datei.
4. `TestVorpruefung` - die sechs Grenzfaelle werden **ausgefuehrt**, nicht am Payload-Text
   behauptet. Der Payload trennt dafuer seine reinen Teile (Register + `pruefeVorkommen`) von den
   Figma-API-Teilen; unter `node` ist `figma` nicht definiert, und die reinen Teile landen in
   `globalThis.__PRUEFTEILE`. Ein Test, der nur prueft, ob die Zeichenkette `figma.mixed` im
   Payload vorkommt, prueft eine Schreibweise, keine Entscheidung.
5. `TestNachweis` - alles, was die gemessenen Inventare braucht (AK1-AK3, AK5-AK7).

**`TestNachweis` ist bis zum Figma-Lauf rot, und das ist der gewollte Zustand.** Kein `skipif`,
kein `xfail`: Ein Test, der bei fehlendem Nachweis gruen wird, ist der Nachweis nicht wert - genau
dann waere eine unfertige Umstellung von einer fertigen nicht zu unterscheiden (ADR 0062,
Abschnitt 4). Das erwartete Rot ist beziffert und traegt den Marker `nachweis` (registriert in
`scripts/pyproject.toml`), sodass `pytest -m "not nachweis"` der belegbare Nachweis ist, dass der
Rest gruen laeuft. Die genaue Zahl und die Namen der roten Tests stehen in
`scripts/figma/README.md`.

**Die Zahlen sind Sollwerte, keine Messnotizen (AK0).** Sie stehen unten als Konstanten und werden
nicht zur Laufzeit aus den Daten abgeleitet - sonst pruefte der Test sich selbst. Weicht das
gemessene Inventar ab, ist das ein Halt-und-erklaeren im Pull Request, kein stilles Nachziehen.

**Mutationsproben** (durchgefuehrt am 2026-09-07, jeweils zurueckgenommen):

1. Einen Registerwert (`Rahmen/Trennlinie` `#2A2E3D` -> `#2A2E3E`) auf einen in `index.css` nicht
   vorhandenen Hexwert gesetzt -> `test_die_vereinigung_ist_exakt_die_palette_aus_index_css` rot.
2. Einen Eintrag aus `inventar-nachher.json` entfernt ->
   `test_die_schluesselmenge_ist_in_beiden_inventaren_identisch` rot.
3. Einen der 370 unveraenderten Hexwerte im Nach-Inventar veraendert ->
   `test_genau_achtundvierzig_hexwerte_aendern_sich_in_zwei_uebergaengen` rot.

Zu 2 und 3: Die gemessenen Inventare existieren zum Zeitpunkt der Probe noch nicht - der
Figma-Lauf findet erst in der Hauptsession statt. Die Probe lief deshalb gegen ein
**synthetisches**, aber vollstaendig schemakonformes Inventarpaar an genau den echten Dateipfaden:
erst gruen, dann je Mutation rot, danach wieder entfernt. Sie belegt damit die Pruefmechanik, nicht
den Board-Zustand - der Board-Zustand ist gerade das, was der Lauf erst herstellt. Wer das Muster
aendert, wiederholt die Proben, statt sie zu glauben.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_WURZEL = Path(__file__).parents[2]
FIGMA_VERZEICHNIS = REPO_WURZEL / "scripts" / "figma"
PAYLOAD = FIGMA_VERZEICHNIS / "board-farbvariablen.js"
FIGMA_README = FIGMA_VERZEICHNIS / "README.md"
INVENTAR_VORHER = FIGMA_VERZEICHNIS / "inventar-vorher.json"
INVENTAR_NACHHER = FIGMA_VERZEICHNIS / "inventar-nachher.json"
INDEX_CSS = REPO_WURZEL / "frontend" / "src" / "index.css"

# --- Sollwerte (AK0). Festgeschrieben, nicht aus den Daten abgeleitet. -----------------------

SOLL_VARIABLEN = 23
SOLL_BESTEHENDE = 12
SOLL_NEUE = 11
SOLL_VORKOMMEN = 418
SOLL_FILLS = 318
SOLL_STROKES = 100
SOLL_KNOTEN = 459
SOLL_AN_BESTEHENDE = 336
SOLL_AN_NEUE = 82
SOLL_HEXGLEICH_BESTAND = 289
SOLL_UNVERAENDERT = 370
SOLL_GEAENDERT = 48
SOLL_GEDAEMPFT = 47
SOLL_GEBAEUDE_SCHRIFT = 1
SOLL_TRENNLINIE = 72
SOLL_CODE_EIGENE = 17
SOLL_HEXWERTE_INDEX_CSS = 40
SOLL_FARBTOKENS_INDEX_CSS = 63
SOLL_BOARD_KNOTEN_ID = "2:4"
SOLL_VERSION_VORHER = "V1.2"
SOLL_VERSION_NACHHER = "V1.3"

# Die zwei Uebergaenge aus AK6: alter Board-Wert -> neuer Wert, samt erwarteter Anzahl.
SOLL_UEBERGAENGE = {
    ("#62677A", "#8D92A4"): SOLL_GEDAEMPFT,
    ("#FF007F", "#FF44A1"): SOLL_GEBAEUDE_SCHRIFT,
}

# Die zwei Variablen, die einen Korrekturvermerk tragen - und keine weitere (AK5).
KORREKTUR_VARIABLEN = {
    "Text/Gedämpft": "#62677A",
    "Kategorie/Gebäude & Bauwerk/Schrift": "#FF007F",
}
KORREKTUR_PFLICHTTEILE = ("ADR 0055", "nicht zurückzuschreiben")

# Die zwoelf bestehenden Variablen (Collection "PhotoSort Farben", Modus "Dunkel", seit
# 2026-09-03). Ihre Namen und Werte bleiben byte-gleich; einzige Ausnahme ist der Wert von
# Text/Gedämpft (AK2).
BESTEHENDE_VARIABLEN = {
    "Hintergrund/Basis": "#0B0C10",
    "Hintergrund/Oberfläche": "#14161F",
    "Hintergrund/Erhöht": "#1E2230",
    "Hintergrund/Overlay": "#262B3D",
    "Akzent/Primär": "#FFB000",
    "Akzent/Info": "#00E5FF",
    "Akzent/Aussortiert": "#FF3D00",
    "Akzent/Album-würdig": "#00E676",
    "Text/Primär": "#FFFFFF",
    "Text/Sekundär": "#A0A5B5",
    "Text/Gedämpft": "#8D92A4",
    "Text/Deaktiviert": "#3E4252",
}

# Die elf neuen Variablen (AK3) mit ihrer erwarteten Vorkommenszahl. Summe 82.
NEUE_VARIABLEN = {
    "Rahmen/Trennlinie": ("#2A2E3D", SOLL_TRENNLINIE),
    "Kategorie/Menschen/Fläche": ("#4D3814", 1),
    "Kategorie/Menschen/Schrift": ("#FFC107", 1),
    "Kategorie/Tier/Fläche": ("#163E3C", 1),
    "Kategorie/Tier/Schrift": ("#00F5D4", 1),
    "Kategorie/Landschaft/Fläche": ("#1F2B49", 1),
    "Kategorie/Landschaft/Schrift": ("#00B4D8", 1),
    "Kategorie/Gebäude & Bauwerk/Fläche": ("#3B1F43", 1),
    "Kategorie/Gebäude & Bauwerk/Schrift": ("#FF44A1", 1),
    "Kategorie/Essen & Trinken/Fläche": ("#143C22", 1),
    "Kategorie/Essen & Trinken/Schrift": ("#70E000", 1),
}

# Die fuenf Kategorien des Boards, mit den Anzeigenamen aus ADR 0055 Punkt 6a (nicht den
# Board-Beschriftungen "Tiere"/"Gebäude"). Jeder Name bildet mechanisch auf ein CSS-Token ab -
# genau diese Zuordnung macht den Namen pruefbar statt zu einer blossen Zeichenkette.
KATEGORIE_TOKEN = {
    "Menschen": "menschen",
    "Tier": "tier",
    "Landschaft": "landschaft",
    "Gebäude & Bauwerk": "gebaeude-bauwerk",
    "Essen & Trinken": "essen-trinken",
}
ROLLE_TOKEN = {"Fläche": "bg", "Schrift": "fg"}

GRUPPEN_VOKABULAR = {"Hintergrund", "Akzent", "Text", "Rahmen", "Kategorie"}
NAMENS_ZEICHENVORRAT = re.compile(r"^[A-Za-zÄÖÜäöüß /&-]+$")
ASCII_ERSATZFORMEN = ("Gedaempft", "Gebaeude", "Flaeche")
SCOPE_VOKABULAR = {"FRAME_FILL", "SHAPE_FILL", "TEXT_FILL", "STROKE_COLOR"}

# M2 - byteweise Verbotsliste ueber den Payload. Sie steht hier und im Wortlaut in
# scripts/figma/README.md, ausdruecklich **nicht** im Payload selbst: sonst faerbte der Payload
# seinen eigenen Test rot. Die Pruefung ist byteweise und versteht kein JavaScript - sie ist eine
# Formpruefung, kein Sicherheitsbeweis, und haelt den Payload in dem engen API-Ausschnitt, den ein
# Diff-Leser in Sekunden nachvollzieht.
VERBOTSLISTE = (
    "fetch",
    "XMLHttpRequest",
    "WebSocket",
    "eval(",
    "new Function",
    "import(",
    "require(",
    "process",
    "openExternal",
    "createImageAsync",
    "currentUser",
    "clientStorage",
    "PluginData",
    "teamLibrary",
    "ByKeyAsync",
    ".remove(",
    "deleteAsync",
)

# Figma-Schreiboperationen. Der NUR_PRUEFEN-Schalter muss vor der ersten von ihnen greifen.
SCHREIBOPERATIONEN = (
    "saveVersionHistoryAsync",
    "createVariable",
    "setValueForMode",
    "setBoundVariableForPaint",
)

REGISTER_ANFANG = "/* REGISTER-ANFANG */"
REGISTER_ENDE = "/* REGISTER-ENDE */"

# --- Schema der Inventardateien (M3, geschlossen) -------------------------------------------

KOPF_SCHLUESSEL = {
    "gemessenAm",
    "boardKnotenId",
    "boardVersion",
    "anzahlKnoten",
    "anzahlVorkommen",
    "anzahlFills",
    "anzahlStrokes",
    "anzahlVariablen",
}
VARIABLEN_SCHLUESSEL = {"id", "name", "wert", "scopes", "beschreibung"}
VORKOMMEN_SCHLUESSEL = {
    "knotenId",
    "eigenschaft",
    "index",
    "hex",
    "deckkraft",
    "mischmodus",
    "sichtbar",
}
VORKOMMEN_SCHLUESSEL_NACHHER = VORKOMMEN_SCHLUESSEL | {"variable", "variablenId"}
TOP_LEVEL_SCHLUESSEL = {"kopf", "variablen", "vorkommen"}

MUSTER_KNOTEN_ID = re.compile(r"^\d+:\d+$")
MUSTER_HEX = re.compile(r"^#[0-9A-F]{6}$")
MUSTER_VARIABLEN_ID = re.compile(r"^VariableID:[0-9:]+$")
MUSTER_ZEITSTEMPEL = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MUSTER_VERSION = re.compile(r"^V\d+\.\d+$")
EIGENSCHAFTEN = {"fills", "strokes"}
MISCHMODI = {
    "NORMAL",
    "MULTIPLY",
    "SCREEN",
    "OVERLAY",
    "DARKEN",
    "LIGHTEN",
    "COLOR_DODGE",
    "COLOR_BURN",
    "HARD_LIGHT",
    "SOFT_LIGHT",
    "DIFFERENCE",
    "EXCLUSION",
    "HUE",
    "SATURATION",
    "COLOR",
    "LUMINOSITY",
    "LINEAR_BURN",
    "LINEAR_DODGE",
    "PASS_THROUGH",
}

NACHWEIS_FEHLT = (
    "NACHWEIS FEHLT: scripts/figma/inventar-{vorher,nachher}.json — der use_figma-Lauf steht aus "
    "(scripts/figma/README.md)"
)

# Die geschlossene Liste der Abbruchcodes der Vorpruefung. Sie ist geschlossen, weil ein
# Abbruchgrund sonst Freitext aus einem fremden System in den Kontext der Hauptsession und von
# dort in ein oeffentliches Repository truege (M3).
ABBRUCHCODES = {
    "nicht-solid",
    "gemischte-fuellung",
    "stil-gesetzt",
    "deckkraft-abweichend",
    "fremde-variable",
    "unbekannter-hexwert",
    "scope-deckt-eigenschaft-nicht",
}
GRUND_SCHLUESSEL = {"code", "knotenId", "eigenschaft", "index"}


# --- Duenne Leser und reine Funktionen ------------------------------------------------------


def payload_text() -> str:
    """Duenner Leser: der Payload, so wie er gesendet wird."""
    if not PAYLOAD.exists():
        pytest.fail(
            f"{PAYLOAD.relative_to(REPO_WURZEL)} fehlt - ohne den Payload gibt es nichts zu "
            "pruefen und nichts zu senden."
        )
    return PAYLOAD.read_text(encoding="utf-8")


def registerblock(text: str) -> str:
    """Reine Funktion: der Text zwischen den beiden Registermarken.

    Genau eine Anfangs- und eine Endmarke, Anfang vor Ende. Mehrere Marken waeren mehrere
    Register - und damit wieder zwei Abbilder derselben Aussage, die driften koennen.
    """
    if text.count(REGISTER_ANFANG) != 1 or text.count(REGISTER_ENDE) != 1:
        raise ValueError(
            f"Erwartet genau eine {REGISTER_ANFANG}- und eine {REGISTER_ENDE}-Marke, gefunden "
            f"{text.count(REGISTER_ANFANG)} bzw. {text.count(REGISTER_ENDE)}."
        )
    anfang = text.index(REGISTER_ANFANG) + len(REGISTER_ANFANG)
    ende = text.index(REGISTER_ENDE)
    if ende <= anfang:
        raise ValueError("Die Endmarke steht vor der Anfangsmarke.")
    return text[anfang:ende]


def register() -> dict[str, Any]:
    """Duenner Leser: der Registerblock des Payloads, strikt als JSON gelesen."""
    return json.loads(registerblock(payload_text()))


def hexwerte_aus_root(css: str) -> dict[str, str]:
    """Reine Funktion: die Farbtokens des `:root`-Blocks als Token -> Hexwert (Grossschreibung).

    Nur der `:root`-Block, nicht der `@theme`-Block: dort stehen `var()`-Verweise, keine Werte.
    Jedes Token traegt laut Kopfkommentar von `index.css` einen ausgeschriebenen 6-stelligen
    Hexwert - ein Token mit `var()` oder `color-mix()` taucht hier folglich gar nicht auf.
    """
    anfang = css.index(":root {")
    ende = css.index("\n}", anfang)
    block = css[anfang:ende]
    treffer = re.findall(r"^\s*(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{6});\s*$", block, re.MULTILINE)
    return {token: wert.upper() for token, wert in treffer}


def index_css_tokens() -> dict[str, str]:
    """Duenner Leser: `frontend/src/index.css`, nur gelesen - diese Story aendert dort nichts."""
    return hexwerte_aus_root(INDEX_CSS.read_text(encoding="utf-8"))


def figma_werte(reg: dict[str, Any]) -> set[str]:
    return {eintrag["wert"] for eintrag in reg["variablen"]}


def code_eigene_werte(reg: dict[str, Any]) -> set[str]:
    return {eintrag["wert"] for eintrag in reg["codeEigeneWerte"]}


def variablen_nach_namen(reg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {eintrag["name"]: eintrag for eintrag in reg["variablen"]}


HARNESS = """
require(process.env.PHOTOSORT_PAYLOAD);
const teile = globalThis.__PRUEFTEILE;
if (!teile || typeof teile.pruefeVorkommen !== 'function' || !teile.REGISTER) {
  console.error('globalThis.__PRUEFTEILE fehlt oder ist unvollstaendig');
  process.exit(3);
}
const faelle = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const ergebnisse = faelle.map((fall) => teile.pruefeVorkommen(fall, teile.REGISTER));
process.stdout.write(JSON.stringify({ register: teile.REGISTER, ergebnisse: ergebnisse }));
"""


def node_binary() -> str:
    """Kein `skipif`: fehlt `node`, scheitert die Klasse mit klarer Meldung, statt lautlos zu
    verschwinden. `ubuntu-latest` bringt Node vorinstalliert mit, der CI-Job `demo-scripts`
    braucht dafuer keine Aenderung."""
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "`node` ist nicht im PATH. Die reinen Teile des Payloads werden in ihrer eigenen "
            "Laufzeit ausgefuehrt statt im Quelltext nach Schluesselwoertern durchsucht - ohne "
            "node ist diese Klasse nicht aussagefaehig und darf deshalb nicht gruen werden."
        )
    return node


def vorpruefung_ausfuehren(faelle: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Duenner Leser: laedt den Payload unter `node` und ruft `pruefeVorkommen` je Fall auf.

    Das Laden geschieht **vom Test aus**, nicht aus dem Payload heraus - die Pruefhilfe faellt
    deshalb nicht unter die Verbotsliste M2.
    """
    lauf = subprocess.run(
        [node_binary(), "-e", HARNESS],
        input=json.dumps(faelle),
        text=True,
        capture_output=True,
        env=dict(os.environ, PHOTOSORT_PAYLOAD=str(PAYLOAD)),
    )
    assert lauf.returncode == 0, (
        f"Der node-Lauf ist mit Code {lauf.returncode} gescheitert.\nstderr:\n{lauf.stderr}"
    )
    return json.loads(lauf.stdout)


def basis_vorkommen(**abweichung: Any) -> dict[str, Any]:
    """Reine Funktion: ein erklaertes Vorkommen, aus dem die Grenzfaelle je eine Abweichung machen.

    Ohne diese gemeinsame Grundlage pruefte jeder Grenzfall eine andere Sache; so ist die genannte
    Abweichung nachweislich die einzige Ursache des Abbruchs.
    """
    eintrag: dict[str, Any] = {
        "knotenId": "40:12",
        "eigenschaft": "fills",
        "index": 0,
        "art": "SOLID",
        "hex": "#2A2E3D",
        "deckkraft": 1,
        "mischmodus": "NORMAL",
        "sichtbar": True,
        "stilId": "",
        "variable": None,
        "variablenId": None,
    }
    eintrag.update(abweichung)
    return eintrag


def inventar(pfad: Path) -> dict[str, Any]:
    """Duenner Leser. Fehlt eine der beiden Dateien, **scheitert** der Test - er ueberspringt sich
    nicht: Genau dann waere eine unfertige Umstellung von einer fertigen nicht zu unterscheiden."""
    if not INVENTAR_VORHER.exists() or not INVENTAR_NACHHER.exists():
        pytest.fail(NACHWEIS_FEHLT)
    return json.loads(pfad.read_text(encoding="utf-8"))


def schluessel(eintrag: dict[str, Any]) -> tuple[str, str, int]:
    return (eintrag["knotenId"], eintrag["eigenschaft"], eintrag["index"])


def sortierschluessel(eintrag: dict[str, Any]) -> tuple[int, int, str, int]:
    links, rechts = eintrag["knotenId"].split(":")
    return (int(links), int(rechts), eintrag["eigenschaft"], eintrag["index"])


def _kopf_verstoesse(kopf: Any) -> list[str]:
    if not isinstance(kopf, dict) or set(kopf) != KOPF_SCHLUESSEL:
        return [f"kopf-Schluessel {sorted(kopf) if isinstance(kopf, dict) else kopf!r}."]
    befunde: list[str] = []
    if not MUSTER_ZEITSTEMPEL.match(str(kopf["gemessenAm"])):
        befunde.append(f"kopf.gemessenAm {kopf['gemessenAm']!r} ist kein UTC-Zeitstempel.")
    if kopf["boardKnotenId"] != SOLL_BOARD_KNOTEN_ID:
        befunde.append(f"kopf.boardKnotenId {kopf['boardKnotenId']!r}.")
    if not MUSTER_VERSION.match(str(kopf["boardVersion"])):
        befunde.append(f"kopf.boardVersion {kopf['boardVersion']!r}.")
    for feld in ("anzahlKnoten", "anzahlVorkommen", "anzahlFills", "anzahlStrokes",
                 "anzahlVariablen"):
        wert = kopf[feld]
        if isinstance(wert, bool) or not isinstance(wert, int) or wert < 0:
            befunde.append(f"kopf.{feld} {wert!r} ist keine Anzahl.")
    return befunde


def _variablen_verstoesse(eintraege: Any) -> list[str]:
    if not isinstance(eintraege, list):
        return ["variablen ist keine Liste."]
    befunde: list[str] = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict) or set(eintrag) != VARIABLEN_SCHLUESSEL:
            gefunden = sorted(eintrag) if isinstance(eintrag, dict) else eintrag
            befunde.append(f"variablen-Schluessel {gefunden!r}.")
            continue
        if not MUSTER_VARIABLEN_ID.match(str(eintrag["id"])):
            befunde.append(f"variablen[].id {eintrag['id']!r}.")
        if not NAMENS_ZEICHENVORRAT.match(str(eintrag["name"])):
            befunde.append(f"variablen[].name {eintrag['name']!r}.")
        if not MUSTER_HEX.match(str(eintrag["wert"])):
            befunde.append(f"variablen[].wert {eintrag['wert']!r}.")
        if not isinstance(eintrag["scopes"], list) or not set(eintrag["scopes"]) <= SCOPE_VOKABULAR:
            befunde.append(f"variablen[].scopes {eintrag['scopes']!r}.")
        if not isinstance(eintrag["beschreibung"], str) or not eintrag["beschreibung"].strip():
            befunde.append(f"variablen[].beschreibung zu {eintrag['name']!r} ist leer.")
    return befunde


def _vorkommen_verstoesse(eintraege: Any, erlaubt: set[str]) -> list[str]:
    if not isinstance(eintraege, list):
        return ["vorkommen ist keine Liste."]
    befunde: list[str] = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict) or set(eintrag) != erlaubt:
            gefunden = sorted(eintrag) if isinstance(eintrag, dict) else eintrag
            befunde.append(f"vorkommen-Schluessel {gefunden!r}.")
            continue
        if not MUSTER_KNOTEN_ID.match(str(eintrag["knotenId"])):
            befunde.append(f"vorkommen[].knotenId {eintrag['knotenId']!r}.")
        if eintrag["eigenschaft"] not in EIGENSCHAFTEN:
            befunde.append(f"vorkommen[].eigenschaft {eintrag['eigenschaft']!r}.")
        index = eintrag["index"]
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            befunde.append(f"vorkommen[].index {index!r}.")
        if not MUSTER_HEX.match(str(eintrag["hex"])):
            befunde.append(f"vorkommen[].hex {eintrag['hex']!r}.")
        deckkraft = eintrag["deckkraft"]
        if isinstance(deckkraft, bool) or not isinstance(deckkraft, (int, float)) \
                or not 0 <= deckkraft <= 1:
            befunde.append(f"vorkommen[].deckkraft {deckkraft!r}.")
        if eintrag["mischmodus"] not in MISCHMODI:
            befunde.append(f"vorkommen[].mischmodus {eintrag['mischmodus']!r}.")
        if not isinstance(eintrag["sichtbar"], bool):
            befunde.append(f"vorkommen[].sichtbar {eintrag['sichtbar']!r}.")
        if "variable" not in erlaubt:
            continue
        variable = eintrag["variable"]
        if variable is not None and not NAMENS_ZEICHENVORRAT.match(str(variable)):
            befunde.append(f"vorkommen[].variable {variable!r}.")
        variablen_id = eintrag["variablenId"]
        if variablen_id is not None and not MUSTER_VARIABLEN_ID.match(str(variablen_id)):
            befunde.append(f"vorkommen[].variablenId {variablen_id!r}.")
    return befunde


def schema_verstoesse(daten: Any, erlaubte_vorkommen: set[str]) -> list[str]:
    """Reine Funktion: alle Abweichungen vom geschlossenen Feld- und Werteschema (M3).

    Geschlossen heisst: **jeder** unbekannte Schluessel und **jeder** nicht schemakonforme Wert
    ist ein Verstoss. Eine Ausschlussliste, die nur im Text steht, ist keine - Freitext aus einem
    fremden System ist gleichzeitig Leck- und Injektionskanal (unsichtbare Ebenen, Knotennamen,
    Kommentare), und mit diesem Schema ist die Injektionsflaeche nicht bewacht, sondern
    strukturell nicht vorhanden.
    """
    if not isinstance(daten, dict):
        return ["Die Datei enthaelt kein Objekt."]
    if set(daten) != TOP_LEVEL_SCHLUESSEL:
        return [f"Top-Level-Schluessel {sorted(daten)}, erwartet {sorted(TOP_LEVEL_SCHLUESSEL)}."]
    return (
        _kopf_verstoesse(daten["kopf"])
        + _variablen_verstoesse(daten["variablen"])
        + _vorkommen_verstoesse(daten["vorkommen"], erlaubte_vorkommen)
    )


def hex_uebergaenge(vorher: dict[str, Any], nachher: dict[str, Any]) -> dict[tuple[str, str], int]:
    """Reine Funktion: welcher Hexwert an wie vielen Schluesseln durch welchen ersetzt wurde."""
    vorher_nach_schluessel = {schluessel(e): e for e in vorher["vorkommen"]}
    uebergaenge: dict[tuple[str, str], int] = {}
    for eintrag in nachher["vorkommen"]:
        alt = vorher_nach_schluessel.get(schluessel(eintrag))
        if alt is None or alt["hex"] == eintrag["hex"]:
            continue
        paar = (alt["hex"], eintrag["hex"])
        uebergaenge[paar] = uebergaenge.get(paar, 0) + 1
    return uebergaenge


# --- TestRegisterForm (AK4, AK5) ------------------------------------------------------------


class TestRegisterForm:
    """AK4/AK5: Namen, Zeichenvorrat, Gruppen, Scopes, Beschreibungen, Korrekturvermerke."""

    def test_das_register_fuehrt_genau_dreiundzwanzig_variablen(self) -> None:
        reg = register()
        namen = [eintrag["name"] for eintrag in reg["variablen"]]

        assert len(namen) == SOLL_VARIABLEN, (
            f"{len(namen)} Variablen im Register, Sollwert {SOLL_VARIABLEN} "
            f"({SOLL_BESTEHENDE} bestehende + {SOLL_NEUE} neue, AK3)."
        )
        assert len(set(namen)) == len(namen), "Zwei Variablen tragen denselben Namen."
        assert len(figma_werte(reg)) == SOLL_VARIABLEN, (
            "Zwei Variablen tragen denselben Hexwert - dann ist die Zuordnung Hexwert -> Variable "
            "beim Binden nicht mehr eindeutig."
        )

    def test_die_zwoelf_bestehenden_stehen_mit_ihrem_wert_im_register(self) -> None:
        nach_namen = variablen_nach_namen(register())

        for name, wert in BESTEHENDE_VARIABLEN.items():
            assert name in nach_namen, f"Bestehende Variable {name!r} fehlt im Register."
            assert nach_namen[name]["wert"] == wert, (
                f"{name}: Register fuehrt {nach_namen[name]['wert']}, erwartet {wert}."
            )
            assert nach_namen[name]["neu"] is False, f"{name} ist keine neue Variable."

    def test_die_elf_neuen_stehen_mit_wert_und_vorkommenszahl_im_register(self) -> None:
        nach_namen = variablen_nach_namen(register())

        for name, (wert, vorkommen) in NEUE_VARIABLEN.items():
            assert name in nach_namen, f"Neue Variable {name!r} fehlt im Register."
            assert nach_namen[name]["wert"] == wert
            assert nach_namen[name]["neu"] is True
            assert nach_namen[name]["erwarteteVorkommen"] == vorkommen, (
                f"{name}: erwartete Vorkommenszahl {nach_namen[name]['erwarteteVorkommen']}, "
                f"Sollwert {vorkommen}."
            )

        neue = [e for e in nach_namen.values() if e["neu"]]
        assert len(neue) == SOLL_NEUE
        assert sum(e["erwarteteVorkommen"] for e in neue) == SOLL_AN_NEUE, (
            f"Die elf neuen Variablen erklaeren zusammen {SOLL_AN_NEUE} Vorkommen."
        )

    def test_die_namen_tragen_echte_umlaute_und_kein_ascii_ersatz(self) -> None:
        """AK4: `Gedaempft`, `Gebaeude`, `Flaeche` kommen als Teilstring nicht vor."""
        namen = [eintrag["name"] for eintrag in register()["variablen"]]

        for name in namen:
            assert NAMENS_ZEICHENVORRAT.match(name), (
                f"{name!r} enthaelt Zeichen ausserhalb von [A-Za-zÄÖÜäöüß /&-]."
            )
            for ersatz in ASCII_ERSATZFORMEN:
                assert ersatz not in name, (
                    f"{name!r} traegt die ASCII-Ersatzform {ersatz!r} statt des Umlauts."
                )

        assert "Text/Gedämpft" in namen
        assert "Kategorie/Gebäude & Bauwerk/Schrift" in namen

    def test_die_gruppe_vor_dem_ersten_schraegstrich_ist_geschlossen(self) -> None:
        for eintrag in register()["variablen"]:
            gruppe = eintrag["name"].split("/")[0]
            assert gruppe in GRUPPEN_VOKABULAR, (
                f"{eintrag['name']!r} liegt in der Gruppe {gruppe!r}, ausserhalb von "
                f"{sorted(GRUPPEN_VOKABULAR)}."
            )

    def test_jede_variable_traegt_eingegrenzte_scopes(self) -> None:
        """AK4: nicht leer und **nicht** `ALL_SCOPES` - sonst waere der Scope keine Aussage."""
        for eintrag in register()["variablen"]:
            scopes = eintrag["scopes"]
            assert scopes, f"{eintrag['name']}: leere Scope-Liste."
            assert "ALL_SCOPES" not in scopes, f"{eintrag['name']}: ALL_SCOPES ist unzulaessig."
            assert set(scopes) <= SCOPE_VOKABULAR, (
                f"{eintrag['name']}: {sorted(set(scopes) - SCOPE_VOKABULAR)} ausserhalb des "
                f"Scope-Vokabulars."
            )
            assert len(set(scopes)) == len(scopes), f"{eintrag['name']}: doppelter Scope."

    def test_die_kategorie_scopes_trennen_flaeche_und_schrift(self) -> None:
        nach_namen = variablen_nach_namen(register())

        for kategorie in KATEGORIE_TOKEN:
            flaeche = nach_namen[f"Kategorie/{kategorie}/Fläche"]
            schrift = nach_namen[f"Kategorie/{kategorie}/Schrift"]
            assert sorted(flaeche["scopes"]) == ["FRAME_FILL", "SHAPE_FILL"], (
                f"Eine Chip-Flaeche ist nie Schrift: {flaeche['name']} {flaeche['scopes']}."
            )
            assert schrift["scopes"] == ["TEXT_FILL"], (
                f"Eine Chip-Schrift ist nie Flaeche: {schrift['name']} {schrift['scopes']}."
            )

    def test_jede_beschreibung_nennt_den_eigenen_hexwert(self) -> None:
        """AK4: nicht leer und enthaelt den eigenen Hexwert woertlich - wer die Variable in Figma
        anklickt, sieht den Wert auch dann, wenn die Oberflaeche nur den Namen zeigt."""
        for eintrag in register()["variablen"]:
            beschreibung = eintrag["beschreibung"]
            assert beschreibung.strip(), f"{eintrag['name']}: leere Beschreibung."
            assert eintrag["wert"] in beschreibung, (
                f"{eintrag['name']}: Beschreibung nennt {eintrag['wert']} nicht woertlich."
            )

    def test_genau_zwei_variablen_tragen_einen_korrekturvermerk(self) -> None:
        """AK5: der **alte** Board-Wert, der neue Wert, `ADR 0055` und der Rueckschreibe-
        Ausschluss - und genau diese zwei, keine weitere."""
        nach_namen = variablen_nach_namen(register())

        for name, altwert in KORREKTUR_VARIABLEN.items():
            eintrag = nach_namen[name]
            beschreibung = eintrag["beschreibung"]
            assert altwert in beschreibung, (
                f"{name}: der alte Board-Wert {altwert} fehlt in der Beschreibung. Ohne ihn ist "
                "die Warnung fuer die Person, die in Figma den vermeintlich falschen Wert sieht, "
                "nicht auffindbar."
            )
            for teil in KORREKTUR_PFLICHTTEILE:
                assert teil in beschreibung, f"{name}: {teil!r} fehlt in der Beschreibung."
            assert eintrag["altwerte"] == [altwert], (
                f"{name}: altwerte {eintrag['altwerte']!r}, erwartet [{altwert!r}]."
            )

        mit_adr = [e["name"] for e in nach_namen.values() if "ADR 0055" in e["beschreibung"]]
        assert sorted(mit_adr) == sorted(KORREKTUR_VARIABLEN), (
            f"Genau {len(KORREKTUR_VARIABLEN)} Variablen tragen einen Korrekturvermerk, "
            f"gefunden: {sorted(mit_adr)}."
        )
        mit_altwerten = [e["name"] for e in nach_namen.values() if e["altwerte"]]
        assert sorted(mit_altwerten) == sorted(KORREKTUR_VARIABLEN)

    def test_die_erwarteten_vorkommenszahlen_summieren_sich_auf_418(self) -> None:
        """Ohne die erwartete Vorkommenszahl je Variable waere "alle 418 sind gebunden" mit einer
        *falschen* Bindung genauso gruen wie mit der richtigen - die Gesamtzahl stimmt ja."""
        reg = register()
        bekannt = [
            e["erwarteteVorkommen"]
            for e in reg["variablen"]
            if e["erwarteteVorkommen"] is not None
        ]
        rest = reg["restVorkommen"]
        offen = [e["name"] for e in reg["variablen"] if e["erwarteteVorkommen"] is None]

        assert sorted(rest["variablen"]) == sorted(offen), (
            "restVorkommen.variablen muss genau die Variablen ohne einzeln gemessene Zahl "
            f"aufzaehlen. Register: {sorted(offen)}, restVorkommen: {sorted(rest['variablen'])}."
        )
        assert rest["summe"] == SOLL_HEXGLEICH_BESTAND, (
            f"restVorkommen.summe {rest['summe']}, Sollwert {SOLL_HEXGLEICH_BESTAND}."
        )
        assert sum(bekannt) + rest["summe"] == SOLL_VORKOMMEN, (
            f"{sum(bekannt)} einzeln erwartete + {rest['summe']} als Gruppe erwartete Vorkommen "
            f"ergeben nicht den Sollwert {SOLL_VORKOMMEN}."
        )

    def test_der_registerkopf_nennt_board_collection_und_beide_versionen(self) -> None:
        reg = register()

        assert reg["boardKnotenId"] == SOLL_BOARD_KNOTEN_ID
        assert reg["boardName"] == "photosort-design-system"
        assert reg["fileKey"] == "zFiuhI1yjTzAQVQnceBiLC"
        assert reg["collection"] == "PhotoSort Farben"
        assert reg["modus"] == "Dunkel"
        assert reg["versionVorher"] == SOLL_VERSION_VORHER
        assert reg["versionNachher"] == SOLL_VERSION_NACHHER
        assert reg["knotenGesamt"] == SOLL_KNOTEN
        assert reg["vorkommenGesamt"] == SOLL_VORKOMMEN
        assert reg["vorkommenFills"] == SOLL_FILLS
        assert reg["vorkommenStrokes"] == SOLL_STROKES
        assert reg["vorkommenFills"] + reg["vorkommenStrokes"] == reg["vorkommenGesamt"]


# --- TestRegisterGegenIndexCss (AK8) --------------------------------------------------------


class TestRegisterGegenIndexCss:
    """AK8: die Teilhoheit ist erzwungen, nicht behauptet."""

    def test_der_suchraum_in_index_css_hat_die_erwartete_groesse(self) -> None:
        """Selbstschutz: Ohne diese Untergrenzen waere ein kaputter `:root`-Leser von einer
        sauberen Palette nicht zu unterscheiden - beide melden dieselbe Vereinigung."""
        tokens = index_css_tokens()

        assert len(tokens) == SOLL_FARBTOKENS_INDEX_CSS, (
            f"{len(tokens)} Farbtokens im :root-Block, Sollwert {SOLL_FARBTOKENS_INDEX_CSS}. "
            "Weicht das ab, ist die Palette gewachsen oder geschrumpft - dann ist die Grenze "
            "zwischen Figma-gefuehrten und code-eigenen Werten neu zu ziehen (AK8)."
        )
        assert len(set(tokens.values())) == SOLL_HEXWERTE_INDEX_CSS, (
            f"{len(set(tokens.values()))} verschiedene Hexwerte, Sollwert "
            f"{SOLL_HEXWERTE_INDEX_CSS}."
        )

    def test_figma_werte_und_code_eigene_werte_sind_disjunkt(self) -> None:
        reg = register()
        ueberschneidung = figma_werte(reg) & code_eigene_werte(reg)

        assert not ueberschneidung, (
            f"{sorted(ueberschneidung)} steht auf beiden Seiten der Grenze. Ein Wert gehoert "
            "entweder Figma oder dem Code, sonst ist die Teilhoheit keine."
        )

    def test_die_vereinigung_ist_exakt_die_palette_aus_index_css(self) -> None:
        """Das ist die gerechnete, nicht die gesetzte Haelfte von AK8: Ein neuer Farbwert in
        `index.css` faerbt hier rot, bis jemand ihn einer Seite der Grenze zuordnet."""
        reg = register()
        palette = set(index_css_tokens().values())
        vereinigung = figma_werte(reg) | code_eigene_werte(reg)

        fehlend = palette - vereinigung
        ueberzaehlig = vereinigung - palette
        assert not fehlend, (
            f"{sorted(fehlend)} steht in index.css, aber auf keiner Seite des Registers. "
            "Entweder wird der Wert kuenftig in Figma gefuehrt, oder er ist als code-eigen mit "
            "eigener Begruendung einzutragen."
        )
        assert not ueberzaehlig, (
            f"{sorted(ueberzaehlig)} steht im Register, aber nicht in index.css. Jeder Wert, den "
            "eine Figma-Variable fuehrt, muss auch als :root-Token ausgeliefert werden (ADR 0062 "
            "Abschnitt 1) - eine Farbe in Figma, die es in der App nicht gibt, ist genau das, was "
            "die Richtungsaussage verbietet."
        )

    def test_es_gibt_genau_siebzehn_code_eigene_werte(self) -> None:
        reg = register()

        assert len(reg["codeEigeneWerte"]) == SOLL_CODE_EIGENE, (
            f"{len(reg['codeEigeneWerte'])} code-eigene Werte, Sollwert {SOLL_CODE_EIGENE}."
        )
        assert len(code_eigene_werte(reg)) == SOLL_CODE_EIGENE, "Doppelter code-eigener Wert."

    def test_jeder_code_eigene_wert_nennt_sein_token_und_seine_begruendung(self) -> None:
        tokens = index_css_tokens()

        for eintrag in register()["codeEigeneWerte"]:
            token = eintrag["token"]
            assert token in tokens, f"{token} gibt es im :root-Block von index.css nicht."
            assert tokens[token] == eintrag["wert"], (
                f"{token}: index.css fuehrt {tokens[token]}, das Register {eintrag['wert']}."
            )
            assert len(eintrag["begruendung"].strip()) >= 20, (
                f"{token}: ohne einzelne Begruendung ist die Zuordnung zur Code-Seite eine "
                "Behauptung."
            )

    def test_die_beiden_verworfenen_board_werte_sind_keine_variablenwerte_mehr(self) -> None:
        """ADR 0055 schlaegt den Board-Wert. `#62677A` und `#FF007F` verschwinden damit
        vollstaendig aus der Figma-Datei, statt dort als tote Alternative weiterzuleben."""
        reg = register()
        palette = set(index_css_tokens().values())
        altwerte = {alt for e in reg["variablen"] for alt in e["altwerte"]}

        assert altwerte == set(KORREKTUR_VARIABLEN.values()), (
            f"altwerte {sorted(altwerte)}, erwartet {sorted(set(KORREKTUR_VARIABLEN.values()))}."
        )
        assert not altwerte & figma_werte(reg), "Ein Altwert ist zugleich Sollwert einer Variable."
        assert not altwerte & palette, (
            "Ein verworfener Board-Wert steht wieder in index.css - dann waere die Korrektur aus "
            "ADR 0055 zurueckgedreht worden."
        )

    def test_jeder_kategoriename_bildet_auf_ein_vorhandenes_css_token_ab(self) -> None:
        """Die Anzeigenamen aus ADR 0055 Punkt 6a, nicht die Board-Beschriftungen: Jeder Name
        bildet mechanisch auf ein vorhandenes CSS-Token ab - Board-Beschriftungen waeren nur eine
        Zeichenkette, die niemand gegen etwas halten kann."""
        tokens = index_css_tokens()
        nach_namen = variablen_nach_namen(register())

        for kategorie, kuerzel in KATEGORIE_TOKEN.items():
            for rolle, endung in ROLLE_TOKEN.items():
                name = f"Kategorie/{kategorie}/{rolle}"
                token = f"--chip-{kuerzel}-{endung}"
                assert token in tokens, f"{name} bildet auf {token} ab, das es nicht gibt."
                assert nach_namen[name]["wert"] == tokens[token], (
                    f"{name} fuehrt {nach_namen[name]['wert']}, {token} fuehrt {tokens[token]}."
                )

    def test_die_vierzehn_abgeleiteten_chip_werte_sind_code_eigen(self) -> None:
        """ADR 0055 Punkt 6a kennt **sieben** abgeleitete Buntpaare. Sie nach Figma zu tragen
        hiesse, eine Ableitung als Entwurfsentscheidung auszugeben."""
        abgeleitet = (
            "pflanze",
            "innenraum",
            "fahrzeug",
            "gegenstand",
            "dokument-screenshot",
            "kunst-kreatives",
            "sport-aktivitaet",
        )
        code_tokens = {e["token"] for e in register()["codeEigeneWerte"]}

        erwartet = {
            f"--chip-{kuerzel}-{endung}" for kuerzel in abgeleitet for endung in ("bg", "fg")
        }
        assert erwartet <= code_tokens, (
            f"{sorted(erwartet - code_tokens)} fehlt unter den code-eigenen Werten."
        )
        assert code_tokens - erwartet == {"--border-control", "--separator", "--danger-text"}, (
            "Neben den 14 abgeleiteten Chip-Werten sind genau --border-control, --separator und "
            f"--danger-text code-eigen; gefunden: {sorted(code_tokens - erwartet)}."
        )


# --- TestPayloadForm ------------------------------------------------------------------------


class TestPayloadForm:
    """Der Payload als Form: eingebettetes Register, Schalter, Verbotsliste, Uebersetzbarkeit."""

    def test_der_registerblock_ist_strikt_als_json_lesbar(self) -> None:
        block = registerblock(payload_text())

        geladen = json.loads(block)
        assert isinstance(geladen, dict), "Der Registerblock ist kein JSON-Objekt."

    def test_der_registerblock_ist_im_ausgefuehrten_payload_eingebettet(self) -> None:
        """Kein zweites Registerdokument, kein Zusammensetzen vor dem Senden: Zwei Dateien, von
        denen eine ausgefuehrt und eine geprueft wird, sind zwei Abbilder derselben Aussage - und
        zwei Abbilder driften."""
        text = payload_text()

        anfang = text.index(REGISTER_ANFANG)
        assert "const REGISTER =" in text[:anfang], (
            "Der Text vor der Anfangsmarke muss den Block an den Bezeichner REGISTER binden, "
            "sonst ist der gepruefte Block nicht der ausgefuehrte."
        )
        assert "REGISTER" in text[text.index(REGISTER_ENDE):], (
            "Nach der Endmarke wird REGISTER nirgends mehr benutzt - dann fuehrt der Payload ein "
            "anderes Register aus als das geprueft wird."
        )
        assert not list(FIGMA_VERZEICHNIS.glob("*register*.json")), (
            "Es darf kein zweites Registerdokument neben dem Payload liegen."
        )

    def test_der_unter_node_geladene_payload_traegt_dasselbe_register(self) -> None:
        """Der starke Teil der Zusicherung: nicht nur der *Text* zwischen den Marken parst - die
        unter `node` tatsaechlich geladene Datei traegt denselben Inhalt."""
        ergebnis = vorpruefung_ausfuehren([[]])

        assert ergebnis["register"] == register(), (
            "Das unter node geladene REGISTER weicht vom JSON-Block zwischen den Marken ab."
        )

    def test_der_nur_pruefen_schalter_liegt_vor_der_ersten_schreiboperation(self) -> None:
        """Ein reiner Schau-Lauf braucht keine zweite Datei: Die Hauptsession stellt dem Payload
        `globalThis.NUR_PRUEFEN = true;` voran."""
        text = payload_text()

        assert "NUR_PRUEFEN" in text, "Der Schau-Lauf-Schalter fehlt."
        schalter = text.index("NUR_PRUEFEN")
        for operation in SCHREIBOPERATIONEN:
            assert operation in text, f"Der Payload benutzt {operation} nirgends."
            assert schalter < text.index(operation), (
                f"{operation} steht vor der Auswertung von NUR_PRUEFEN - ein Schau-Lauf koennte "
                "dann schreiben."
            )

    def test_die_vorpruefung_liegt_vor_jeder_schreiboperation(self) -> None:
        """M1: Trifft die Selbstverortung oder die Vorpruefung nicht zu, kehrt der Lauf mit dem
        Inventar zurueck, ohne einen einzigen Schreibaufruf."""
        text = payload_text()

        vorpruefung = text.index("pruefeVorkommen(")
        for operation in SCHREIBOPERATIONEN:
            assert vorpruefung < text.index(operation), (
                f"{operation} steht vor dem Aufruf der Vorpruefung."
            )

    def test_der_wiederherstellungspunkt_ist_die_erste_schreiboperation(self) -> None:
        """M5: die eine bewusste Ausnahme von "aendert nichts vor bestandener Vorpruefung" - sie
        liegt danach, und ein Checkpoint ist nicht destruktiv."""
        text = payload_text()

        checkpoint = text.index("saveVersionHistoryAsync")
        for operation in SCHREIBOPERATIONEN:
            if operation == "saveVersionHistoryAsync":
                continue
            assert checkpoint < text.index(operation), (
                f"{operation} steht vor dem Wiederherstellungspunkt."
            )

    def test_der_payload_haelt_die_byteweise_verbotsliste(self) -> None:
        """M2. Byteweise, auch in Kommentaren - die Pruefung versteht kein JavaScript."""
        rohbytes = PAYLOAD.read_bytes()

        gefunden = [begriff for begriff in VERBOTSLISTE if begriff.encode("utf-8") in rohbytes]
        assert not gefunden, (
            f"Der Payload enthaelt {gefunden}. Die Liste haelt ihn in dem engen API-Ausschnitt, "
            "den ein Diff-Leser in Sekunden nachvollzieht; sie ist bewusst eine Formpruefung, "
            "kein Sicherheitsbeweis. Der Wortlaut steht in scripts/figma/README.md."
        )

    def test_die_verbotsliste_steht_im_wortlaut_in_der_readme(self) -> None:
        """Die Liste gehoert in die README und in diesen Test, **nicht** in den Payload - sonst
        faerbt der Payload seinen eigenen Test rot."""
        assert FIGMA_README.exists(), f"{FIGMA_README.relative_to(REPO_WURZEL)} fehlt."
        text = FIGMA_README.read_text(encoding="utf-8")

        fehlend = [begriff for begriff in VERBOTSLISTE if begriff not in text]
        assert not fehlend, f"In der README fehlen: {fehlend}."

    def test_der_payload_enthaelt_kein_secret_und_keinen_umgebungszugriff(self) -> None:
        """M7: kein Token, keine Sitzungskennung, kein `.env`-Bezug. `fileKey` und Knoten-ID sind
        kein Geheimnismaterial - sie stehen in jeder Datei-URL und seit Spec 0320 ohnehin
        oeffentlich in specs/architecture/0005."""
        gross = payload_text().upper()

        # Bewusst nicht das blosse "TOKEN": Das Register fuehrt zu jedem code-eigenen Wert sein
        # CSS-Token, und ein Design-Token ist kein Geheimnis. Gesucht sind die Formen, in denen
        # Zugangsmaterial auftritt.
        for begriff in ("_TOKEN", "TOKEN=", "SECRET", "PASSWORT", "PASSWORD", "API_KEY", ".ENV"):
            assert begriff not in gross, f"Der Payload nennt {begriff!r}."

    def test_node_uebersetzt_den_payload(self) -> None:
        lauf = subprocess.run(
            [node_binary(), "--check", str(PAYLOAD)], capture_output=True, text=True
        )

        assert lauf.returncode == 0, f"`node --check` scheitert:\n{lauf.stderr}"

    def test_der_payload_trennt_seine_reinen_teile_von_der_figma_laufzeit(self) -> None:
        text = payload_text()

        assert "typeof figma === 'undefined'" in text, (
            "Ohne diesen Zweig sind die reinen Teile ausserhalb der Plugin-Sandbox nicht "
            "ausfuehrbar - und die Grenzfaelle waeren nur am Payload-Text behauptet."
        )
        assert "__PRUEFTEILE" in text


# --- TestVorpruefung ------------------------------------------------------------------------


class TestVorpruefung:
    """Die sechs Grenzfaelle und die zwei Positivproben - ausgefuehrt, nicht behauptet.

    Ohne die Positivproben bestuende die Abbruchliste auch bei einer Funktion, die immer abbricht.
    """

    GRENZFAELLE: tuple[tuple[str, dict[str, Any]], ...] = (
        ("nicht-solid", {"art": "GRADIENT_LINEAR"}),
        ("gemischte-fuellung", {"art": "MIXED"}),
        ("stil-gesetzt", {"stilId": "S:2b6f1c4a"}),
        ("deckkraft-abweichend", {"deckkraft": 0.4}),
        ("fremde-variable", {"variable": "Fremd/Unbekannt", "variablenId": "VariableID:99:99"}),
        ("unbekannter-hexwert", {"hex": "#123456"}),
    )

    def test_jeder_grenzfall_bricht_mit_seinem_eigenen_code_ab(self) -> None:
        faelle = [[basis_vorkommen(**abweichung)] for _, abweichung in self.GRENZFAELLE]

        ergebnisse = vorpruefung_ausfuehren(faelle)["ergebnisse"]

        paare = zip(self.GRENZFAELLE, ergebnisse, strict=True)
        for (erwarteter_code, abweichung), ergebnis in paare:
            assert ergebnis["ok"] is False, (
                f"{abweichung} haette die Vorpruefung abbrechen lassen muessen."
            )
            codes = [grund["code"] for grund in ergebnis["abbruchgruende"]]
            assert codes == [erwarteter_code], f"{abweichung}: Codes {codes}."

    def test_ein_scope_der_die_eigenschaft_nicht_deckt_ist_ein_abbruchgrund(self) -> None:
        """Scopes verhindern eine programmatische Bindung nicht - die Diskrepanz bliebe sonst
        still. Eine Chip-Flaeche deckt keine Linienfarbe."""
        fall = basis_vorkommen(hex="#4D3814", eigenschaft="strokes")

        ergebnis = vorpruefung_ausfuehren([[fall]])["ergebnisse"][0]

        assert ergebnis["ok"] is False
        assert [g["code"] for g in ergebnis["abbruchgruende"]] == ["scope-deckt-eigenschaft-nicht"]

    def test_ein_bereits_gebundenes_vorkommen_gilt_als_erklaert(self) -> None:
        """Positivprobe 1, zugleich der Beleg fuer die Fortschrittsunabhaengigkeit: Die Formel
        "gebunden **oder** im Register" gilt im unberuehrten Zustand ebenso wie nach einem
        Teillauf und blockiert die Wiederaufnahme nicht."""
        fall = basis_vorkommen(
            variable="Rahmen/Trennlinie", variablenId="VariableID:1:12", hex="#2A2E3D"
        )

        ergebnis = vorpruefung_ausfuehren([[fall]])["ergebnisse"][0]

        assert ergebnis["ok"] is True, f"Abbruchgruende: {ergebnis['abbruchgruende']}"
        assert ergebnis["erklaert"] == 1

    def test_ein_vollstaendig_erklaertes_inventar_liefert_ok(self) -> None:
        """Positivprobe 2: je ein ungebundenes Vorkommen zu jedem Sollwert und zu jedem Altwert
        des Registers. Die 47 Knoten in #62677A und der eine in #FF007F muessen erklaert sein -
        sonst braeche der Lauf ausgerechnet an den Stellen ab, die er korrigieren soll."""
        reg = register()
        faelle = []
        for nummer, eintrag in enumerate(reg["variablen"], start=1):
            eigenschaft = "strokes" if "STROKE_COLOR" in eintrag["scopes"] else "fills"
            for wert in [eintrag["wert"], *eintrag["altwerte"]]:
                faelle.append(
                    basis_vorkommen(knotenId=f"{nummer}:1", hex=wert, eigenschaft=eigenschaft)
                )

        ergebnis = vorpruefung_ausfuehren([faelle])["ergebnisse"][0]

        assert ergebnis["ok"] is True, f"Abbruchgruende: {ergebnis['abbruchgruende']}"
        assert ergebnis["erklaert"] == len(faelle) == SOLL_VARIABLEN + len(KORREKTUR_VARIABLEN)

    def test_ein_abbruchgrund_traegt_keinen_freitext_aus_dem_fremden_system(self) -> None:
        """M3: Der Ruecklauf fliesst in den Kontext der Hauptsession und von dort in ein
        oeffentliches Repository. Ein Grund nennt deshalb einen Code aus einer geschlossenen Liste
        und die Knoten-ID, die den Knoten exakt adressiert - nie einen Namen, nie einen
        Ausnahmetext."""
        faelle = [[basis_vorkommen(**abweichung)] for _, abweichung in self.GRENZFAELLE]

        ergebnisse = vorpruefung_ausfuehren(faelle)["ergebnisse"]

        for ergebnis in ergebnisse:
            for grund in ergebnis["abbruchgruende"]:
                assert set(grund) == GRUND_SCHLUESSEL, f"Grund-Schluessel {sorted(grund)}."
                assert grund["code"] in ABBRUCHCODES, f"Unbekannter Abbruchcode {grund['code']!r}."
                assert "Fremd/Unbekannt" not in json.dumps(grund, ensure_ascii=False), (
                    "Der Name der fremden Variable steht im Abbruchgrund."
                )

    def test_die_vorpruefung_zaehlt_ueber_das_ganze_inventar(self) -> None:
        """Ein Abbruch beendet die Pruefung nicht vorzeitig: Bei Abbruch kehrt der Lauf mit dem
        **vollen** Inventar zurueck; korrigiert wird dann am Register, was nichts kostet."""
        faelle = [
            [
                basis_vorkommen(knotenId="7:1"),
                basis_vorkommen(knotenId="7:2", hex="#123456"),
                basis_vorkommen(knotenId="7:3", hex="#654321"),
            ]
        ]

        ergebnis = vorpruefung_ausfuehren(faelle)["ergebnisse"][0]

        assert ergebnis["gesamt"] == 3
        assert ergebnis["erklaert"] == 1
        assert len(ergebnis["abbruchgruende"]) == 2, (
            "Beide unerklaerten Vorkommen muessen gemeldet werden, nicht nur das erste."
        )


# --- TestNachweis (bis zum Figma-Lauf rot) --------------------------------------------------


@pytest.mark.nachweis
class TestNachweis:
    """AK1-AK3, AK5-AK7 - alles, was die gemessenen Inventare braucht.

    Diese Klasse ist bis zum `use_figma`-Lauf der Hauptsession rot. Kein `skipif`, kein `xfail`:
    Ein Test, der bei fehlendem Nachweis gruen wird, ist der Nachweis nicht wert.
    """

    def test_beide_inventardateien_liegen_vor(self) -> None:
        assert INVENTAR_VORHER.exists() and INVENTAR_NACHHER.exists(), NACHWEIS_FEHLT

    def test_beide_inventare_halten_das_geschlossene_schema(self) -> None:
        """M3: jeder unbekannte Schluessel und jeder nicht schemakonforme Wert faerbt rot."""
        vorher = inventar(INVENTAR_VORHER)
        nachher = inventar(INVENTAR_NACHHER)

        assert schema_verstoesse(vorher, VORKOMMEN_SCHLUESSEL) == []
        assert schema_verstoesse(nachher, VORKOMMEN_SCHLUESSEL_NACHHER) == []

    def test_beide_inventare_sind_deterministisch_sortiert(self) -> None:
        """Gleiches Format und gleiche Sortierung - dadurch ist der Textdiff der beiden Dateien
        selbst schon der Nachweis."""
        for pfad in (INVENTAR_VORHER, INVENTAR_NACHHER):
            vorkommen = inventar(pfad)["vorkommen"]
            assert vorkommen == sorted(vorkommen, key=sortierschluessel), (
                f"{pfad.name} ist nicht deterministisch sortiert."
            )

    def test_die_schluesselmenge_ist_in_beiden_inventaren_identisch(self) -> None:
        """AK1: kein Vorkommen verloren, keines hinzugekommen."""
        vorher = inventar(INVENTAR_VORHER)
        nachher = inventar(INVENTAR_NACHHER)
        vorher_schluessel = {schluessel(e) for e in vorher["vorkommen"]}
        nachher_schluessel = {schluessel(e) for e in nachher["vorkommen"]}

        assert len(vorher["vorkommen"]) == SOLL_VORKOMMEN
        assert len(nachher["vorkommen"]) == SOLL_VORKOMMEN
        assert len(vorher_schluessel) == SOLL_VORKOMMEN, "Doppelter Schluessel im Vor-Inventar."
        assert vorher_schluessel == nachher_schluessel, (
            f"Verloren: {sorted(vorher_schluessel - nachher_schluessel)[:5]}, "
            f"hinzugekommen: {sorted(nachher_schluessel - vorher_schluessel)[:5]}."
        )

        for daten, name in ((vorher, "vorher"), (nachher, "nachher")):
            fills = [e for e in daten["vorkommen"] if e["eigenschaft"] == "fills"]
            strokes = [e for e in daten["vorkommen"] if e["eigenschaft"] == "strokes"]
            assert len(fills) == SOLL_FILLS, f"{name}: {len(fills)} Fills."
            assert len(strokes) == SOLL_STROKES, f"{name}: {len(strokes)} Strokes."

    def test_nach_dem_lauf_traegt_kein_vorkommen_mehr_eine_feste_farbe(self) -> None:
        """AK1: jeder der 418 Eintraege traegt eine Bindung an eine Variable der Collection."""
        nachher = inventar(INVENTAR_NACHHER)
        namen = set(BESTEHENDE_VARIABLEN) | set(NEUE_VARIABLEN)

        ungebunden = [schluessel(e) for e in nachher["vorkommen"] if e["variable"] is None]
        assert not ungebunden, f"{len(ungebunden)} ungebundene Vorkommen, z.B. {ungebunden[:5]}."
        fremd = {e["variable"] for e in nachher["vorkommen"]} - namen
        assert not fremd, f"Bindung an registerfremde Variablen: {sorted(fremd)}."
        ohne_id = [
            schluessel(e)
            for e in nachher["vorkommen"]
            if not MUSTER_VARIABLEN_ID.match(str(e["variablenId"]))
        ]
        assert not ohne_id, f"Bindung ohne Variablen-ID: {ohne_id[:5]}."

    def test_die_bindungen_verteilen_sich_wie_im_register_erwartet(self) -> None:
        """AK1/AK2/AK3: Ohne die erwartete Vorkommenszahl je Variable waere eine *falsche*
        Bindung genauso gruen wie die richtige - die Gesamtzahl stimmt ja."""
        nachher = inventar(INVENTAR_NACHHER)
        reg = register()
        gezaehlt: dict[str, int] = {}
        for eintrag in nachher["vorkommen"]:
            gezaehlt[eintrag["variable"]] = gezaehlt.get(eintrag["variable"], 0) + 1

        an_bestehende = sum(gezaehlt.get(name, 0) for name in BESTEHENDE_VARIABLEN)
        an_neue = sum(gezaehlt.get(name, 0) for name in NEUE_VARIABLEN)
        assert an_bestehende == SOLL_AN_BESTEHENDE, (
            f"{an_bestehende} Vorkommen an den zwoelf bestehenden Variablen, Sollwert "
            f"{SOLL_AN_BESTEHENDE}."
        )
        assert an_neue == SOLL_AN_NEUE, (
            f"{an_neue} Vorkommen an den elf neuen Variablen, Sollwert {SOLL_AN_NEUE}."
        )
        for eintrag in reg["variablen"]:
            if eintrag["erwarteteVorkommen"] is None:
                continue
            assert gezaehlt.get(eintrag["name"], 0) == eintrag["erwarteteVorkommen"], (
                f"{eintrag['name']}: {gezaehlt.get(eintrag['name'], 0)} Bindungen, Register "
                f"erwartet {eintrag['erwarteteVorkommen']}."
            )
        rest = sum(gezaehlt.get(name, 0) for name in reg["restVorkommen"]["variablen"])
        assert rest == reg["restVorkommen"]["summe"]

    def test_die_scopes_decken_jede_gebundene_eigenschaft(self) -> None:
        """Scopes verhindern eine programmatische Bindung nicht - eine Bindung auf einer nicht
        gedeckten Eigenschaft bliebe sonst still."""
        nachher = inventar(INVENTAR_NACHHER)
        scopes = {e["name"]: set(e["scopes"]) for e in register()["variablen"]}

        for eintrag in nachher["vorkommen"]:
            gedeckt = scopes.get(eintrag["variable"], set())
            if eintrag["eigenschaft"] == "strokes":
                assert "STROKE_COLOR" in gedeckt, (
                    f"{schluessel(eintrag)}: {eintrag['variable']} deckt keine Linienfarbe."
                )
            else:
                assert gedeckt & {"FRAME_FILL", "SHAPE_FILL", "TEXT_FILL"}, (
                    f"{schluessel(eintrag)}: {eintrag['variable']} deckt keine Fuellung."
                )

    def test_die_zwoelf_bestehenden_variablen_bleiben_und_elf_kommen_hinzu(self) -> None:
        """AK2/AK3: Name und Wert byte-gleich, einzige Ausnahme ist der Wert von Text/Gedämpft."""
        vorher = {e["name"]: e for e in inventar(INVENTAR_VORHER)["variablen"]}
        nachher = {e["name"]: e for e in inventar(INVENTAR_NACHHER)["variablen"]}

        assert set(vorher) == set(BESTEHENDE_VARIABLEN), (
            f"Vor dem Lauf fuehrt die Collection {sorted(vorher)}."
        )
        assert len(nachher) == SOLL_VARIABLEN
        assert set(nachher) == set(BESTEHENDE_VARIABLEN) | set(NEUE_VARIABLEN)
        assert set(nachher) - set(vorher) == set(NEUE_VARIABLEN), (
            "Jede der elf neuen Variablen muss im Variablen-Vorzustand fehlen."
        )
        for name, eintrag in vorher.items():
            if name == "Text/Gedämpft":
                assert eintrag["wert"] == KORREKTUR_VARIABLEN[name]
                assert nachher[name]["wert"] == BESTEHENDE_VARIABLEN[name]
                continue
            assert nachher[name]["wert"] == eintrag["wert"], (
                f"{name}: Wert von {eintrag['wert']} auf {nachher[name]['wert']} geaendert - die "
                "zwoelf bestehenden bleiben byte-gleich."
            )

    def test_beide_korrekturvermerke_stehen_nach_dem_lauf_in_figma(self) -> None:
        """AK5: Die Person, die in Figma den vermeintlich falschen Wert sieht, hat das Repository
        in dem Moment nicht offen."""
        nachher = {e["name"]: e for e in inventar(INVENTAR_NACHHER)["variablen"]}

        for name, altwert in KORREKTUR_VARIABLEN.items():
            beschreibung = nachher[name]["beschreibung"]
            assert altwert in beschreibung
            assert nachher[name]["wert"] in beschreibung
            for teil in KORREKTUR_PFLICHTTEILE:
                assert teil in beschreibung, f"{name}: {teil!r} fehlt in der Figma-Beschreibung."

    def test_genau_achtundvierzig_hexwerte_aendern_sich_in_zwei_uebergaengen(self) -> None:
        """AK6: genau 48 Aenderungen, sonst nichts."""
        vorher = inventar(INVENTAR_VORHER)
        nachher = inventar(INVENTAR_NACHHER)

        uebergaenge = hex_uebergaenge(vorher, nachher)
        assert uebergaenge == SOLL_UEBERGAENGE, (
            f"Gemessene Uebergaenge {uebergaenge}, Sollwert {SOLL_UEBERGAENGE}."
        )
        assert sum(uebergaenge.values()) == SOLL_GEAENDERT

        vorher_nach_schluessel = {schluessel(e): e for e in vorher["vorkommen"]}
        unveraendert = [
            e for e in nachher["vorkommen"]
            if vorher_nach_schluessel[schluessel(e)]["hex"] == e["hex"]
        ]
        assert len(unveraendert) == SOLL_UNVERAENDERT
        for alt, _ in SOLL_UEBERGAENGE:
            uebrig = [e for e in unveraendert if e["hex"] == alt]
            assert not uebrig, (
                f"{len(uebrig)} Vorkommen tragen weiterhin {alt} - geaendert werden genau die "
                "Schluessel, die im Vor-Inventar den alten Wert trugen."
            )

    def test_deckkraft_mischmodus_und_sichtbarkeit_bleiben_an_allen_418_gleich(self) -> None:
        """AK6: `paint.opacity`, `blendMode` und `visible` bleiben unangetastet - deshalb ist die
        Zusage fuer die 370 unveraenderten Vorkommen eine gepruefte Aussage."""
        vorher_nach_schluessel = {
            schluessel(e): e for e in inventar(INVENTAR_VORHER)["vorkommen"]
        }
        abweichungen = []

        for eintrag in inventar(INVENTAR_NACHHER)["vorkommen"]:
            alt = vorher_nach_schluessel[schluessel(eintrag)]
            for feld in ("deckkraft", "mischmodus", "sichtbar"):
                if alt[feld] != eintrag[feld]:
                    abweichungen.append((schluessel(eintrag), feld, alt[feld], eintrag[feld]))

        assert not abweichungen, f"{len(abweichungen)} Abweichungen, z.B. {abweichungen[:5]}."

    def test_die_board_version_geht_von_v12_auf_v13(self) -> None:
        """AK7: Der Lauf gibt beide Werte zurueck; die Pruefung bindet sie literal."""
        vorher = inventar(INVENTAR_VORHER)["kopf"]
        nachher = inventar(INVENTAR_NACHHER)["kopf"]

        assert vorher["boardVersion"] == SOLL_VERSION_VORHER
        assert nachher["boardVersion"] == SOLL_VERSION_NACHHER
        assert vorher["boardKnotenId"] == nachher["boardKnotenId"] == SOLL_BOARD_KNOTEN_ID

    def test_die_kopfzahlen_entsprechen_den_sollwerten(self) -> None:
        """AK0: Weicht das gemessene Inventar ab, ist das ein Halt-und-erklaeren im Pull Request,
        kein stilles Nachziehen der Testzahlen."""
        vorher = inventar(INVENTAR_VORHER)["kopf"]
        nachher = inventar(INVENTAR_NACHHER)["kopf"]

        for kopf, name, variablen in ((vorher, "vorher", SOLL_BESTEHENDE),
                                      (nachher, "nachher", SOLL_VARIABLEN)):
            assert kopf["anzahlKnoten"] == SOLL_KNOTEN, f"{name}: {kopf['anzahlKnoten']} Knoten."
            assert kopf["anzahlVorkommen"] == SOLL_VORKOMMEN
            assert kopf["anzahlFills"] == SOLL_FILLS
            assert kopf["anzahlStrokes"] == SOLL_STROKES
            assert kopf["anzahlVariablen"] == variablen, (
                f"{name}: {kopf['anzahlVariablen']} Variablen, Sollwert {variablen}."
            )

    def test_der_kopfvermerk_der_board_referenz_nennt_die_neue_version(self) -> None:
        """AK7: sonst behauptet das Repository eine Version, die es nicht gibt."""
        referenz = REPO_WURZEL / "specs" / "architecture" / "0005-board-dark-utility-register.md"
        gemessen = inventar(INVENTAR_NACHHER)["kopf"]["boardVersion"]

        assert gemessen in referenz.read_text(encoding="utf-8"), (
            f"Der Kopfvermerk in {referenz.name} nennt {gemessen} nicht."
        )
