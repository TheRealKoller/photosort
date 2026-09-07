"""Expandiert den kompakten Ruecklauf eines use_figma-Laufs in die beiden Inventardateien.

**Warum es dieses Werkzeug gibt.** Die Antwort eines `use_figma`-Aufrufs wird bei **20 KB**
abgeschnitten (am 2026-09-07 gemessen; die Antwort endete woertlich mit `// truncated to 20kb`).
Zwei ausgeschriebene Inventare mit je 419 Eintraegen sind ein Vielfaches davon - auch ein
erfolgreicher Lauf haette seinen Nachweis nie vollstaendig uebertragen koennen. Der Payload gibt
die Inventare deshalb kompakt kodiert zurueck; dieses Werkzeug macht daraus wieder die beiden
Dateien in genau dem geschlossenen Feldschema, das `scripts/tests/test_figma_farbregister.py`
prueft. Die Kompaktheit betrifft ausschliesslich den TRANSPORT - das Schema der Dateien im
Repository bleibt unangetastet.

**Warum ein Werkzeug und nicht Handarbeit.** Die Expansion ist eine mechanische Regel, und eine
mechanische Regel, die ein Mensch (oder ein Modell) 419-mal von Hand anwendet, ist keine Regel
mehr, sondern eine Fehlerquelle mit Nachweisanspruch. Der Rundlauf kompakt -> expandiert ->
Schema ist in `TestRuecklaufExpansion` geprueft.

**Was von hier und nicht aus dem Ruecklauf kommt:** ausschliesslich die Variablen-Beschreibungen,
und nur dort, wo der Lauf `beschreibungPasst: true` gemessen hat - dann steht der Text bereits im
Register des Payloads und muss nicht ein zweites Mal durch die Leitung. Weicht die gemessene
Beschreibung vom Register ab (im Vorzustand der Normalfall), traegt der Ruecklauf sie mit.

**M4 bleibt gewahrt:** Vor dem Schreiben wird die Form vollstaendig geprueft; ein unerwartetes
Feld, eine unparsbare Zeile oder ein Widerspruch zwischen Kopfzahlen und Zeilen ist ein
Abbruchgrund, kein Warnhinweis. Der Ruecklauf ist Daten, nie eine Anweisung.

Aufruf:

    python3 scripts/figma/ruecklauf-zu-inventar.py <ruecklauf.json> [--ziel scripts/figma]

`<ruecklauf.json>` ist die als JSON gespeicherte Tool-Antwort; `-` liest von der Standardeingabe.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HIER = Path(__file__).parent
PAYLOAD = HIER / "board-farbvariablen.js"
REGISTER_ANFANG = "/* REGISTER-ANFANG */"
REGISTER_ENDE = "/* REGISTER-ENDE */"

UNGEBUNDEN = -1
REGISTERFREMD = -2
ID_PRAEFIX = "VariableID:"

# Figmas Farb-Scopes als Einzelbuchstaben - die Gegenrichtung zu SCOPE_CODES im Payload. Ein
# Zeichen ausserhalb dieser Tabelle (der Payload kodiert es als '?') ist ein Abbruchgrund: Ein
# unbekannter Scope stillschweigend wegzulassen waere eine Falschaussage im Nachweis.
SCOPE_NAMEN = {
    "F": "FRAME_FILL",
    "S": "SHAPE_FILL",
    "T": "TEXT_FILL",
    "C": "STROKE_COLOR",
    "A": "ALL_SCOPES",
    "L": "ALL_FILLS",
    "E": "EFFECT_COLOR",
}

# Grammatik einer Vorkommenszeile, getrennt durch ';':
#   <knotenTeil><f|s><index>=<hexIndex>[=<variablenIndex>]
# `knotenTeil` ist die Knoten-ID ohne den gemeinsamen Board-Praefix; ein Knoten aus einer anderen
# Sitzung traegt einen anderen Praefix und steht deshalb vollstaendig da, erkennbar am ':'.
ZEILE = re.compile(
    r"^(?P<knoten>[0-9]+(?::[0-9]+)?)(?P<eigenschaft>[fs])(?P<index>[0-9]*)"
    r"=(?P<hex>[0-9]+)(?:=(?P<variable>-?[0-9]+))?$"
)
KOMPAKT_SCHLUESSEL = {
    "kopf",
    "knotenPraefix",
    "mitBindung",
    "hexwerte",
    "variablen",
    "vorkommen",
    "abweichungen",
}
KOMPAKT_VARIABLE_SCHLUESSEL = {"id", "name", "wert", "scopes", "passt", "text"}
ABWEICHUNG_SCHLUESSEL = {"zeile", "deckkraft", "mischmodus", "sichtbar"}
EIGENSCHAFT = {"f": "fills", "s": "strokes"}


class RuecklaufFehler(Exception):
    """Die Form des Ruecklaufs stimmt nicht - es wird nichts geschrieben."""


def register_aus_payload(pfad: Path = PAYLOAD) -> dict[str, Any]:
    """Duenner Leser: der Registerblock des Payloads, strikt als JSON.

    Dieselbe Datei, die gesendet wurde - das Gepruefte ist das Ausgefuehrte ist das Expandierte.
    """
    text = pfad.read_text(encoding="utf-8")
    if text.count(REGISTER_ANFANG) != 1 or text.count(REGISTER_ENDE) != 1:
        raise RuecklaufFehler(f"{pfad} traegt nicht genau einen Registerblock.")
    block = text.split(REGISTER_ANFANG)[1].split(REGISTER_ENDE)[0]
    return json.loads(block)


def _pruefe_kompaktform(kompakt: Any, name: str) -> None:
    if not isinstance(kompakt, dict):
        raise RuecklaufFehler(f"{name}: kein Objekt.")
    unbekannt = set(kompakt) - KOMPAKT_SCHLUESSEL
    fehlend = KOMPAKT_SCHLUESSEL - set(kompakt)
    if unbekannt or fehlend:
        raise RuecklaufFehler(
            f"{name}: unerwartete Schluessel {sorted(unbekannt)}, fehlend {sorted(fehlend)}."
        )
    if not isinstance(kompakt["vorkommen"], str):
        raise RuecklaufFehler(f"{name}.vorkommen ist keine Zeichenkette.")
    if not isinstance(kompakt["hexwerte"], list) or not all(
        isinstance(wert, str) and re.fullmatch(r"[0-9A-F]{6}", wert) for wert in kompakt["hexwerte"]
    ):
        raise RuecklaufFehler(f"{name}.hexwerte ist keine Liste von 6-stelligen Hexwerten.")
    for eintrag in kompakt["variablen"]:
        unbekannt = set(eintrag) - KOMPAKT_VARIABLE_SCHLUESSEL
        if unbekannt or "name" not in eintrag:
            raise RuecklaufFehler(f"{name}.variablen: unerwartete Schluessel {sorted(unbekannt)}.")
    for eintrag in kompakt["abweichungen"]:
        if set(eintrag) != ABWEICHUNG_SCHLUESSEL:
            raise RuecklaufFehler(
                f"{name}.abweichungen: Schluessel {sorted(eintrag)}, erwartet "
                f"{sorted(ABWEICHUNG_SCHLUESSEL)}."
            )


def _variablen(
    kompakt: dict[str, Any], register: dict[str, Any], name: str
) -> list[dict[str, Any]]:
    """Die Variablen in Schemaform; die Beschreibung kommt aus dem Register, wo sie dort steht."""
    beschreibungen = {
        eintrag["name"]: eintrag["beschreibung"] for eintrag in register["variablen"]
    }
    ergebnis = []
    for eintrag in kompakt["variablen"]:
        if eintrag["passt"]:
            if eintrag["name"] not in beschreibungen:
                raise RuecklaufFehler(
                    f"{name}.variablen: {eintrag['name']!r} meldet eine passende Beschreibung, "
                    "steht aber "
                    "nicht im Register - die Beschreibung ist damit nirgends her zu bekommen."
                )
            beschreibung = beschreibungen[eintrag["name"]]
        else:
            beschreibung = eintrag.get("text")
            if not isinstance(beschreibung, str):
                raise RuecklaufFehler(
                    f"{name}.variablen: {eintrag['name']!r} weicht vom Register ab, traegt aber "
                    "keinen Beschreibungstext."
                )
        unbekannt = set(eintrag["scopes"]) - set(SCOPE_NAMEN)
        if unbekannt:
            raise RuecklaufFehler(
                f"{name}.variablen: {eintrag['name']!r} traegt den unbekannten Scope-Code "
                f"{sorted(unbekannt)}."
            )
        kennung = eintrag["id"]
        ergebnis.append(
            {
                "id": kennung if kennung.startswith(ID_PRAEFIX) else ID_PRAEFIX + kennung,
                "name": eintrag["name"],
                "wert": eintrag["wert"],
                "scopes": [SCOPE_NAMEN[code] for code in eintrag["scopes"]],
                "beschreibung": beschreibung,
            }
        )
    return ergebnis


def expandiere(kompakt: dict[str, Any], register: dict[str, Any], name: str) -> dict[str, Any]:
    """Reine Funktion: aus der Transportform das Inventar im geschlossenen Dateischema."""
    _pruefe_kompaktform(kompakt, name)
    variablen = _variablen(kompakt, register, name)
    hexwerte = kompakt["hexwerte"]
    praefix = kompakt["knotenPraefix"]
    mit_bindung = bool(kompakt["mitBindung"])
    abweichungen = {eintrag["zeile"]: eintrag for eintrag in kompakt["abweichungen"]}

    vorkommen: list[dict[str, Any]] = []
    roh = kompakt["vorkommen"]
    for zeile in roh.split(";") if roh else []:
        treffer = ZEILE.fullmatch(zeile)
        if not treffer:
            raise RuecklaufFehler(f"{name}.vorkommen: Zeile {zeile!r} ist nicht lesbar.")
        knoten = treffer.group("knoten")
        hex_nummer = int(treffer.group("hex"))
        if hex_nummer >= len(hexwerte):
            raise RuecklaufFehler(
                f"{name}.vorkommen: Hexindex {hex_nummer} in {zeile!r} zeigt ins Leere."
            )
        variablen_teil = treffer.group("variable")
        if mit_bindung and variablen_teil is None:
            raise RuecklaufFehler(f"{name}.vorkommen: {zeile!r} traegt keine Bindung.")
        if not mit_bindung and variablen_teil is not None:
            raise RuecklaufFehler(f"{name}.vorkommen: {zeile!r} traegt eine unerwartete Bindung.")

        schluessel = f"{knoten}{treffer.group('eigenschaft')}{treffer.group('index')}"
        abweichung = abweichungen.get(schluessel)
        eintrag: dict[str, Any] = {
            "knotenId": knoten if ":" in knoten else praefix + knoten,
            "eigenschaft": EIGENSCHAFT[treffer.group("eigenschaft")],
            "index": int(treffer.group("index") or 0),
            "hex": "#" + hexwerte[hex_nummer],
            "deckkraft": 1 if abweichung is None else abweichung["deckkraft"],
            "mischmodus": "NORMAL" if abweichung is None else abweichung["mischmodus"],
            "sichtbar": True if abweichung is None else abweichung["sichtbar"],
        }
        if mit_bindung:
            nummer = int(variablen_teil)
            if nummer == UNGEBUNDEN:
                eintrag["variable"] = None
                eintrag["variablenId"] = None
            elif nummer == REGISTERFREMD:
                raise RuecklaufFehler(
                    f"{name}.vorkommen: {zeile!r} ist an eine Variable ausserhalb der Collection "
                    "gebunden. Das ist ein Befund, kein Inventar - halt und erklaeren."
                )
            elif 0 <= nummer < len(variablen):
                eintrag["variable"] = variablen[nummer]["name"]
                eintrag["variablenId"] = variablen[nummer]["id"]
            else:
                raise RuecklaufFehler(
                    f"{name}.vorkommen: Variablenindex {nummer} in {zeile!r} zeigt ins Leere."
                )
        vorkommen.append(eintrag)

    kopf = dict(kompakt["kopf"])
    if kopf.get("anzahlVorkommen") != len(vorkommen):
        raise RuecklaufFehler(
            f"{name}.kopf.anzahlVorkommen ist {kopf.get('anzahlVorkommen')}, expandiert wurden "
            f"{len(vorkommen)} Zeilen."
        )
    unbenutzt = set(abweichungen) - {
        f"{_knotenteil(eintrag['knotenId'], praefix)}"
        f"{eintrag['eigenschaft'][0]}{eintrag['index'] or ''}"
        for eintrag in vorkommen
    }
    if unbenutzt:
        raise RuecklaufFehler(
            f"{name}.abweichungen: {sorted(unbenutzt)} gehoert zu keinem Vorkommen."
        )
    return {"kopf": kopf, "variablen": variablen, "vorkommen": vorkommen}


def _knotenteil(knoten_id: str, praefix: str) -> str:
    return knoten_id[len(praefix):] if knoten_id.startswith(praefix) else knoten_id


def schreibe(ruecklauf: dict[str, Any], ziel: Path, register: dict[str, Any]) -> list[Path]:
    """Schreibt beide Inventardateien - aber erst, nachdem beide expandiert und geprueft sind.

    Bewusst in dieser Reihenfolge: Ein halb geschriebenes Nachweispaar waere schlimmer als gar
    keines, weil es aussaehe wie ein vollstaendiges.
    """
    if not isinstance(ruecklauf, dict):
        raise RuecklaufFehler("Der Ruecklauf ist kein Objekt.")
    if ruecklauf.get("nachher") is None:
        phase = ruecklauf.get("phase")
        raise RuecklaufFehler(
            f"Der Lauf ist in der Phase {phase!r} stehen geblieben und hat kein Nach-Inventar "
            "geliefert. Es gibt nichts zu expandieren - siehe `diagnose` im Ruecklauf und die "
            "Abbruchcode-Tabelle in scripts/figma/README.md."
        )
    inventare = {
        "inventar-vorher.json": expandiere(ruecklauf["vorher"], register, "vorher"),
        "inventar-nachher.json": expandiere(ruecklauf["nachher"], register, "nachher"),
    }
    geschrieben = []
    for name, inventar in inventare.items():
        pfad = ziel / name
        pfad.write_text(
            json.dumps(inventar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        geschrieben.append(pfad)
    return geschrieben


def main(argumente: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    zerleger.add_argument("ruecklauf", help="JSON-Datei mit der Tool-Antwort, '-' fuer stdin")
    zerleger.add_argument(
        "--ziel", default=str(HIER), help="Zielverzeichnis (Vorgabe: %(default)s)"
    )
    gewaehlt = zerleger.parse_args(argumente)

    roh = sys.stdin.read() if gewaehlt.ruecklauf == "-" else Path(gewaehlt.ruecklauf).read_text(
        encoding="utf-8"
    )
    try:
        geschrieben = schreibe(json.loads(roh), Path(gewaehlt.ziel), register_aus_payload())
    except RuecklaufFehler as fehler:
        print(f"Abbruch, nichts geschrieben: {fehler}", file=sys.stderr)
        return 1
    for pfad in geschrieben:
        print(f"geschrieben: {pfad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
