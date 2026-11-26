"""Der mechanische Träger der Typkette: `types.ts` entsteht aus der Schnittstellenbeschreibung.

Jede Invariante ist eine Aussage über den BESTAND, nicht über das Verhalten einer Seite - sie
bricht ohne eigenen Testfall still:

- `keine-interface-deklaration`: `api/types.ts` enthält kein `interface` mehr; jede Struktur ist
  ein Alias auf ein erzeugtes Schema oder ein gekennzeichneter oberflächen-eigener Typ.
- `marken-einmalig` / `marken-in-reihenfolge`: beide Abschnittsmarker stehen genau einmal und
  „Erzeugt" vor „Oberflächen-eigen"; jede Deklaration liegt unter einem Marker.
- `schemabezug-belegt`: jeder `components["schemas"]["X"]`-Bezug nennt einen Schemanamen, der in
  `backend/openapi.json` existiert.
- `keine-zweite-fassung`: außerhalb von `types.ts`, `client.ts` und `generated/` deklariert kein
  Modul unter `frontend/src/api/` einen eigenen Typ.
- `aufruf-ohne-typargument`: kein Produktivcode nennt einen Antworttyp als Typargument
  (`apiFetch<…>`) oder hebt das Ergebnis mit `as any`/`as unknown` auf.
- `beschreibung-am-typ`: die Verhaltensregeln des Artefakts erscheinen über den erzeugten Typ in
  `schema.d.ts` (Anwesenheit, kein Satzvergleich).
- `nachfuehrung-verdrahtet`: `frontend/package.json` ruft in `typecheck` `api:check` VOR `tsc`.

Der Wächter liest ausschließlich Dateien - kein Backend-Import, kein Netz -, damit er im
`demo-scripts`-Job ohne Backend-Abhängigkeiten läuft. Fehlt eine Eingabe oder läuft eine
Dateimenge leer, ist das ausdrücklich ein Befund und keine leere Wahrheit.
"""

from __future__ import annotations

import json
import re

from waechter import Befund, Bestand, Invariante, befund

TYPES = "frontend/src/api/types.ts"
CLIENT = "frontend/src/api/client.ts"
SCHEMA = "frontend/src/api/generated/schema.d.ts"
ARTEFAKT = "backend/openapi.json"
PACKAGE = "frontend/package.json"
API = "frontend/src/api/"
GENERATED = "frontend/src/api/generated/"
ERLAUBTE_TYPQUELLEN = {TYPES, CLIENT}

INVARIANTEN = (
    Invariante(id="keine-interface-deklaration", satz="api/types.ts enthält kein interface."),
    Invariante(id="marken-einmalig", satz="Beide Abschnittsmarker kommen genau einmal vor."),
    Invariante(
        id="marken-in-reihenfolge",
        satz="Erzeugt steht vor Oberflächen-eigen, und jede Deklaration liegt unter einem Marker.",
    ),
    Invariante(
        id="schemabezug-belegt",
        satz="Jeder components-schemas-Bezug nennt einen Schemanamen aus backend/openapi.json.",
    ),
    Invariante(
        id="keine-zweite-fassung",
        satz="frontend/src/api außer types.ts, client.ts und generated/ deklariert keinen Typ.",
    ),
    Invariante(
        id="aufruf-ohne-typargument",
        satz=(
            "Kein Produktivcode nennt ein Typargument an apiFetch/apiFetchBlob oder hebt "
            "as any/unknown auf."
        ),
    ),
    Invariante(
        id="beschreibung-am-typ",
        satz="Die Beschreibung jeder Regelstelle steht über den erzeugten Typ in schema.d.ts.",
    ),
    Invariante(
        id="nachfuehrung-verdrahtet",
        satz="frontend/package.json ruft in typecheck api:check vor tsc.",
    ),
)

# Die Abschnittsmarker in `types.ts`: eine Kommentarzeile, die nur den Marker trägt.
MARKER = re.compile(
    r"^[ \t]*/\*+[ \t]*(?:=+|-+)[ \t]*(Erzeugt|Oberflächen-eigen)[ \t]*(?:=+|-+)[ \t]*\*/[ \t]*$",
    re.MULTILINE,
)
DEKLARATION = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(?:type|interface)[ \t]+(?P<name>[A-Za-z0-9_]+)", re.MULTILINE
)
SCHEMABEZUG = re.compile(
    r"components\[\s*['\"]schemas['\"]\s*\]\[\s*['\"](?P<name>[A-Za-z0-9_]+)['\"]\s*\]"
)
TYPARGUMENT = re.compile(r"(?<!function )\bapiFetch(?:Blob)?[ \t]*<")
AUFHEBUNG = re.compile(r"\bas[ \t]+(?:any|unknown)\b")

# Je Paar (Schema, Feld) muss die Beschreibung des Artefakts im erzeugten Typ stehen. `None`
# meint die Beschreibung des Schemas selbst (Docstring des Modells/Enums).
REGELSTELLEN: tuple[tuple[str, str | None], ...] = (
    ("ScanSummary", "total_files"),
    ("CloudPhaseSummaryOut", "photos_total"),
    ("CloudPhaseSummaryOut", "photos_processed"),
    ("CloudPhaseSummaryOut", "failed_calls"),
    ("CloudPhaseSummaryOut", "responses_used"),
    ("CloudPhaseSummaryOut", "input_tokens"),
    ("CloudPhaseSummaryOut", "output_tokens"),
    ("CloudPhaseSummaryOut", "cost_usd"),
    ("ClassificationEstimatePartOut", "price_per_image_usd"),
    ("ClassificationEstimatePartOut", "candidate_count"),
    ("CriterionScoringRunSummary", "phase_remaining_seconds"),
    ("ScanStatus", None),
    ("ExportRunStatus", None),
    ("ExportRunDetailOut", None),
)


def _normalisiere(text: str) -> str:
    """Whitespace und JSDoc-Sternchen vereinheitlichen - Inhalt, nicht Form."""
    ohne_sterne = [re.sub(r"^[ \t]*\*+[ \t]?", "", zeile) for zeile in text.splitlines()]
    return " ".join(" ".join(ohne_sterne).split())


def _zeile(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _produktivquellen(bestand: Bestand) -> dict[str, str]:
    """Alle `.ts`/`.tsx` unter `frontend/src` ohne Tests, Testbausteine und generated/."""
    quellen: dict[str, str] = {}
    for pfad, text in bestand.items():
        if not pfad.startswith("frontend/src/") or not pfad.endswith((".ts", ".tsx")):
            continue
        if pfad.endswith(".test.ts") or pfad.endswith(".test.tsx"):
            continue
        if pfad.startswith("frontend/src/test/") or pfad.startswith(GENERATED):
            continue
        quellen[pfad] = text
    return quellen


def _pruefe_marker(types: str) -> list[Befund]:
    befunde: list[Befund] = []
    treffer = list(MARKER.finditer(types))
    je_marke: dict[str, list[int]] = {"Erzeugt": [], "Oberflächen-eigen": []}
    for eintrag in treffer:
        je_marke[eintrag.group(1)].append(eintrag.start())

    for marke, positionen in je_marke.items():
        if not positionen:
            befunde.append(
                befund(TYPES, 1, "marken-einmalig", f"Abschnittsmarker „{marke}“ fehlt.")
            )
        for position in positionen[1:]:
            befunde.append(
                befund(
                    TYPES,
                    _zeile(types, position),
                    "marken-einmalig",
                    f"Abschnittsmarker „{marke}“ steht mehrfach.",
                )
            )

    erzeugt = je_marke["Erzeugt"][0] if je_marke["Erzeugt"] else None
    eigen = je_marke["Oberflächen-eigen"][0] if je_marke["Oberflächen-eigen"] else None
    if erzeugt is None or eigen is None:
        vorhanden = erzeugt if erzeugt is not None else eigen
        befunde.append(
            befund(
                TYPES,
                _zeile(types, vorhanden) if vorhanden is not None else 1,
                "marken-in-reihenfolge",
                "Eine Reihenfolge ohne beide Marker gibt es nicht.",
            )
        )
    elif erzeugt > eigen:
        befunde.append(
            befund(
                TYPES,
                _zeile(types, eigen),
                "marken-in-reihenfolge",
                "„Erzeugt“ steht nicht vor „Oberflächen-eigen“.",
            )
        )

    positionen = [position for liste in je_marke.values() for position in liste]
    if positionen:
        erste_marke = min(positionen)
        for deklaration in DEKLARATION.finditer(types[:erste_marke]):
            befunde.append(
                befund(
                    TYPES,
                    _zeile(types, deklaration.start()),
                    "marken-in-reihenfolge",
                    f"Deklaration „{deklaration.group('name')}“ steht vor jedem Marker.",
                )
            )
    return befunde


def _schema_block(schema_text: str, schema_name: str) -> tuple[int, int] | None:
    """(Start, Ende) des Schema-Blocks in `schema.d.ts`, oder None."""
    treffer = re.search(rf"^[ \t]+{re.escape(schema_name)}: \{{", schema_text, re.MULTILINE)
    if treffer is None:
        return None
    ende = schema_text.find("\n    };", treffer.end())
    return treffer.start(), ende if ende >= 0 else len(schema_text)


def _fundstelle(schema_text: str, schema_name: str, feld: str | None) -> int:
    """Die Zeile, an der die Beschreibung von (Schema, Feld) im erzeugten Typ steht."""
    block = _schema_block(schema_text, schema_name)
    if block is None:
        return 1
    block_start, block_ende = block
    if feld is not None:
        deklaration = re.search(
            rf"^[ \t]+{re.escape(feld)}\??: ", schema_text[block_start:block_ende], re.MULTILINE
        )
        if deklaration is not None:
            position = block_start + deklaration.start()
            jsdoc = schema_text.rfind("/**", block_start, position)
            return _zeile(schema_text, jsdoc if jsdoc >= 0 else position)
        return _zeile(schema_text, block_start)
    jsdoc = schema_text.rfind("/**", 0, block_start)
    return _zeile(schema_text, jsdoc if jsdoc >= 0 else block_start)


def pruefe(bestand: Bestand) -> list[Befund]:
    """Reine Funktion: Bestand -> Befunde. Fehlende Eingaben sind Befunde, nie leere Wahrheiten."""
    befunde: list[Befund] = []
    types = bestand.get(TYPES)
    schema = bestand.get(SCHEMA)
    artefakt_text = bestand.get(ARTEFAKT)
    package = bestand.get(PACKAGE)

    if types is None:
        befunde.append(befund(TYPES, 1, "marken-einmalig", "api/types.ts fehlt."))
        types = ""
    if artefakt_text is None:
        befunde.append(befund(ARTEFAKT, 1, "schemabezug-belegt", "backend/openapi.json fehlt."))
        artefakt_text = "{}"
    if schema is None:
        befunde.append(befund(SCHEMA, 1, "beschreibung-am-typ", "api/generated/schema.d.ts fehlt."))
        schema = ""

    # 1. Kein interface in types.ts.
    for treffer in re.finditer(r"\binterface[ \t]+(?P<name>[A-Za-z0-9_]+)", types):
        befunde.append(
            befund(
                TYPES,
                _zeile(types, treffer.start()),
                "keine-interface-deklaration",
                f"types.ts deklariert das interface „{treffer.group('name')}“.",
            )
        )

    # 2./3. Marker und Reihenfolge.
    befunde.extend(_pruefe_marker(types))

    # 4. Jeder Schemabezug nennt ein vorhandenes Schema.
    artefakt = json.loads(artefakt_text)
    schemata = set(artefakt.get("components", {}).get("schemas", {}))
    if not schemata:
        befunde.append(
            befund(
                ARTEFAKT,
                1,
                "schemabezug-belegt",
                "Das Artefakt führt keine Schemata - die Prüfung liefe leer.",
            )
        )
    for treffer in SCHEMABEZUG.finditer(types):
        if treffer.group("name") not in schemata:
            befunde.append(
                befund(
                    TYPES,
                    _zeile(types, treffer.start()),
                    "schemabezug-belegt",
                    f"Schema „{treffer.group('name')}“ steht nicht in backend/openapi.json.",
                )
            )

    # 5. Keine zweite Fassung in den API-Modulen.
    module = {
        pfad: text
        for pfad, text in bestand.items()
        if pfad.startswith(API)
        and pfad.endswith((".ts", ".tsx"))
        and not pfad.endswith(".test.ts")
        and not pfad.endswith(".test.tsx")
        and not pfad.startswith(GENERATED)
        and pfad not in ERLAUBTE_TYPQUELLEN
    }
    if not module:
        befunde.append(
            befund(
                API, 1, "keine-zweite-fassung", "Kein API-Modul gelesen - die Prüfung liefe leer."
            )
        )
    for pfad, text in sorted(module.items()):
        for treffer in DEKLARATION.finditer(text):
            befunde.append(
                befund(
                    pfad,
                    _zeile(text, treffer.start()),
                    "keine-zweite-fassung",
                    f"Modul deklariert den Typ „{treffer.group('name')}“ - Typen gehören in types.ts.",
                )
            )

    # 6. Kein Typargument, keine Aufhebung im Produktivcode.
    for pfad, text in sorted(_produktivquellen(bestand).items()):
        if pfad in {CLIENT, TYPES}:
            continue
        for treffer in TYPARGUMENT.finditer(text):
            befunde.append(
                befund(
                    pfad,
                    _zeile(text, treffer.start()),
                    "aufruf-ohne-typargument",
                    "Der Antworttyp ist ein Typargument - er gehört aus dem Endpunkt abgeleitet.",
                )
            )
        for treffer in AUFHEBUNG.finditer(text):
            befunde.append(
                befund(
                    pfad,
                    _zeile(text, treffer.start()),
                    "aufruf-ohne-typargument",
                    "`as any`/`as unknown` hebt die Typaussage der Aufrufgrenze auf.",
                )
            )

    # 7. Die Beschreibung jeder Regelstelle steht in schema.d.ts.
    erzeugt = _normalisiere(schema)
    for schema_name, feld in REGELSTELLEN:
        modell = artefakt.get("components", {}).get("schemas", {}).get(schema_name)
        if modell is None:
            befunde.append(
                befund(
                    ARTEFAKT,
                    1,
                    "beschreibung-am-typ",
                    f"Regelstelle {schema_name} fehlt im Artefakt.",
                )
            )
            continue
        if feld is None:
            beschreibung = modell.get("description", "")
        else:
            beschreibung = modell.get("properties", {}).get(feld, {}).get("description", "")
        if not beschreibung.strip():
            befunde.append(
                befund(
                    ARTEFAKT,
                    1,
                    "beschreibung-am-typ",
                    f"{schema_name}.{feld or '<Schema>'} trägt keine Beschreibung.",
                )
            )
            continue
        if _normalisiere(beschreibung) not in erzeugt:
            befunde.append(
                befund(
                    SCHEMA,
                    _fundstelle(schema, schema_name, feld),
                    "beschreibung-am-typ",
                    f"Beschreibung von {schema_name}.{feld or '<Schema>'} fehlt im erzeugten Typ.",
                )
            )

    # 8. api:check läuft vor tsc.
    if package is None:
        befunde.append(befund(PACKAGE, 1, "nachfuehrung-verdrahtet", "package.json fehlt."))
    else:
        skripte = json.loads(package).get("scripts", {})
        typecheck = skripte.get("typecheck", "")
        position_check = typecheck.find("api:check")
        position_tsc = typecheck.find("tsc")
        if position_check < 0 or position_tsc < 0 or position_check > position_tsc:
            stelle = package.find('"typecheck"')
            befunde.append(
                befund(
                    PACKAGE,
                    _zeile(package, stelle) if stelle >= 0 else 1,
                    "nachfuehrung-verdrahtet",
                    f"typecheck ruft api:check nicht vor tsc auf: {typecheck!r}.",
                )
            )
    return befunde
