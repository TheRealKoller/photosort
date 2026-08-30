"""Festes, anwendungsweit einheitliches Kategorien-Set (specs/features/0289-feste-kategorien.md,
decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md).

Bewusst ein EIGENES Modul und nicht Teil von `criteria.py` (ADR 0049, Entwurfsentscheidung 1):
Kriterien sind Mess-Signale fuers Ranking, dieses Set ist eine Produkt-Taxonomie. Die Vermischung
beider Anliegen in `criteria.py` war die Ursache der Skalen-/Namensraum-Probleme, die ADR 0032 und
ADR 0047 nacheinander zu reparieren versuchten.

Das Modul ist bewusst REIN: keine DB-, Netzwerk- oder Bildverarbeitungs-Abhaengigkeit und kein
Import aus `criteria.py`/`models.py` - `LOCAL_CATEGORY_SIGNALS` referenziert Kriterien-Keys nur als
Strings. Die Konsistenz beider Registries gegeneinander wird stattdessen per Invariantentest
erzwungen (tests/test_categories.py), nicht per Import.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# Obergrenzen der Modellantwort (ADR 0049): hier statt in `remote_classification.py`, weil
# `build_classification_prompt()` sie in den erzeugten Prompt schreibt - eine Definition dort
# haette einen Zirkelimport erzwungen (remote_classification importiert dieses Modul).
# `remote_classification.py` importiert beide Werte von hier und kuerzt die geparste Antwort
# gegen genau dieselben Konstanten: Prompt und Validierung koennen nicht auseinanderlaufen.
MAX_REMOTE_CATEGORIES_PER_PHOTO = 3
MAX_FINE_LABELS_PER_PHOTO = 2

# Auffangwert fuer "kein Bildmotiv sicher bestimmbar" (ADR 0049). Bewusst KEIN Ersatz fuer
# `gegenstand`: `gegenstand` ist der letzte Eintrag der Vorrangreihenfolge und wird bei einem
# tatsaechlichen Kandidaten vergeben, `nicht_erkannt` steht ausserhalb der Reihenfolge.
CATEGORY_NOT_RECOGNIZED = "nicht_erkannt"


@dataclass(frozen=True)
class CategoryDefinition:
    """Ein Eintrag des festen Sets (ADR 0049, Entwurfsentscheidung 2: Registry-Dataclass statt
    `StrEnum`). `definition` und `delimitation` sind fachlich Teil der Kategorie - sie sind
    zugleich Prompt-Grundlage (`build_classification_prompt`) und UI-Erklaerung (`GET /categories`);
    ein Enum haette sie in eine zweite, driftende Struktur gedraengt.

    `precedence` (kleiner gewinnt) ist die deterministische Vorrangstufe fuer Fotos mit mehreren in
    Frage kommenden Motiven. `None` markiert einen Eintrag AUSSERHALB der Reihenfolge - das gilt
    strukturell ausschliesslich fuer `nicht_erkannt` (per Invariantentest erzwungen), damit dessen
    Sonderrolle nicht nur eine Konvention ist.
    """

    key: str
    display_name: str
    definition: str
    delimitation: str
    precedence: int | None


# Das feste Set in ANZEIGEREIHENFOLGE (nicht in Vorrangreihenfolge) - `GET /categories` und alle
# kategorialen Listen im Frontend uebernehmen genau diese Reihenfolge, damit sie ueberall im
# Produkt identisch ist. Die Vorrangreihenfolge steckt ausschliesslich in `precedence`.
CATEGORY_REGISTRY: dict[str, CategoryDefinition] = {
    "menschen": CategoryDefinition(
        key="menschen",
        display_name="Menschen",
        definition=(
            "Eine oder mehrere Personen sind das bildbestimmende Motiv (Porträt, Gruppenbild, "
            "Schnappschuss von Personen)."
        ),
        delimitation=(
            "Nicht, wenn Personen nur klein/beiläufig im Bild sind, während ein anderes Motiv den "
            "Bildraum bestimmt (Passanten vor einem Bauwerk → Gebäude & Bauwerk). Nicht bei "
            "sportlicher/körperlicher Aktivität (→ Sport & Aktivität). Nicht, wenn am gedeckten "
            "Tisch das Essen bildbestimmend ist (→ Essen & Trinken)."
        ),
        precedence=3,
    ),
    "tier": CategoryDefinition(
        key="tier",
        display_name="Tier",
        definition=(
            "Ein oder mehrere Tiere sind das bildbestimmende Motiv (Haustier, Wildtier, Vogel, "
            "Insekt, Fisch)."
        ),
        delimitation=(
            "Nicht bei Tierdarstellungen als Skulptur, Gemälde oder Plüschtier (→ Kunst & "
            "Kreatives bzw. Gegenstand). Nicht bei zubereitetem Fleisch/Fisch als Speise "
            "(→ Essen & Trinken)."
        ),
        precedence=4,
    ),
    "pflanze": CategoryDefinition(
        key="pflanze",
        display_name="Pflanze",
        definition=(
            "Eine einzelne Pflanze oder eine Pflanzengruppe in Nah-/Mitteldistanz ist "
            "bildbestimmend (Blüte, Blatt, Baum, Strauch, Zimmerpflanze, Blumenstrauß)."
        ),
        delimitation=(
            "Nicht bei einer Weitwinkelszene, in der Vegetation nur Teil der Landschaft ist — "
            "Blumenwiese als Weitwinkelszene → Landschaft, Blütennahaufnahme → Pflanze. Nicht bei "
            "Obst/Gemüse als Nahrungsmittel (→ Essen & Trinken)."
        ),
        precedence=8,
    ),
    "landschaft": CategoryDefinition(
        key="landschaft",
        display_name="Landschaft",
        definition=(
            "Eine weiträumige Natur- oder Außenszene ist bildbestimmend (Berge, Küste, See, Wald, "
            "Feld, Wüste, Himmel, Panorama)."
        ),
        delimitation=(
            "Nicht, wenn ein Bauwerk oder eine Bebauung die Bildfläche bestimmt und die Natur nur "
            "Hintergrund ist (→ Gebäude & Bauwerk). Nicht bei Nah-/Detailaufnahmen einzelner "
            "Naturelemente (→ Pflanze bzw. Gegenstand)."
        ),
        precedence=10,
    ),
    "gebaeude_bauwerk": CategoryDefinition(
        key="gebaeude_bauwerk",
        display_name="Gebäude & Bauwerk",
        definition=(
            "Ein Bauwerk oder eine bebaute Außenansicht ist bildbestimmend (Haus, Kirche, Burg, "
            "Brücke, Turm, Denkmal, Stadtansicht, Sehenswürdigkeit)."
        ),
        delimitation=(
            "Nicht bei Aufnahmen aus dem Inneren eines Gebäudes (→ Innenraum). Nicht, wenn "
            "Bauwerke nur kleiner Teil einer weiten Naturszene sind (→ Landschaft)."
        ),
        precedence=9,
    ),
    "innenraum": CategoryDefinition(
        key="innenraum",
        display_name="Innenraum",
        definition=(
            "Ein Innenraum als Ganzes ist bildbestimmend (Zimmer, Halle, Restaurantraum, "
            "Ladenlokal, Innenarchitektur)."
        ),
        delimitation=(
            "Nicht, wenn im Innenraum ein anderes Motiv bildbestimmend ist (Personen im "
            "Wohnzimmer → Menschen, Teller auf dem Tisch → Essen & Trinken). Nicht bei "
            "Außenansichten von Gebäuden (→ Gebäude & Bauwerk)."
        ),
        precedence=11,
    ),
    "essen_trinken": CategoryDefinition(
        key="essen_trinken",
        display_name="Essen & Trinken",
        definition="Speisen, Getränke oder ein gedeckter Tisch sind bildbestimmend.",
        delimitation=(
            "Nicht bei Lebensmitteln als unauffälligem Beiwerk einer Raum- oder Personenszene. "
            "Nicht bei lebenden Nutzpflanzen im Feld (→ Pflanze bzw. Landschaft)."
        ),
        precedence=5,
    ),
    "fahrzeug": CategoryDefinition(
        key="fahrzeug",
        display_name="Fahrzeug",
        definition=(
            "Ein Fahrzeug ist bildbestimmend (Auto, Fahrrad, Motorrad, Bus, Zug, Boot, Flugzeug)."
        ),
        delimitation=(
            "Nicht bei Straßen-/Stadtszenen, in denen Fahrzeuge nur Teil des Stadtbilds sind "
            "(→ Gebäude & Bauwerk). Nicht, wenn Personen im/am Fahrzeug bildbestimmend sind "
            "(→ Menschen)."
        ),
        precedence=6,
    ),
    "gegenstand": CategoryDefinition(
        key="gegenstand",
        display_name="Gegenstand",
        definition=(
            "Ein konkreter, erkannter Gegenstand ohne passendere spezifischere Kategorie ist "
            "bildbestimmend (Werkzeug, Kleidung, Möbelstück, Gerät, Spielzeug, "
            "Objekt-Detailaufnahme)."
        ),
        delimitation=(
            "NICHT als Ersatz für eine unsichere Erkennung — ist kein Motiv sicher bestimmbar, "
            "gilt „Nicht erkannt“. Nicht, wenn eine spezifischere Kategorie zutrifft."
        ),
        precedence=12,
    ),
    "dokument_screenshot": CategoryDefinition(
        key="dokument_screenshot",
        display_name="Dokument & Screenshot",
        definition=(
            "Eine Text-, Bildschirm- oder Dokumentabbildung ist bildbestimmend (Screenshot, "
            "abfotografiertes Dokument/Formular/Beleg, Ticket, QR-Code, Schild, dessen Text der "
            "Bildzweck ist)."
        ),
        delimitation=(
            "Nicht bei Fotos, auf denen Text nur beiläufig vorkommt (Ladenschild in einer "
            "Straßenszene → Gebäude & Bauwerk). Nicht bei kunstvoll gestalteten Schriftbildern "
            "als Kunstwerk (→ Kunst & Kreatives)."
        ),
        precedence=1,
    ),
    "kunst_kreatives": CategoryDefinition(
        key="kunst_kreatives",
        display_name="Kunst & Kreatives",
        definition=(
            "Ein Kunstwerk oder ein kreatives Erzeugnis ist bildbestimmend (Gemälde, Skulptur, "
            "Wandbild/Graffiti, Museumsexponat, Handarbeit, Bastelarbeit, Zeichnung)."
        ),
        delimitation=(
            "Nicht bei Bauwerken mit kunstvoller Fassade (→ Gebäude & Bauwerk). Nicht bei "
            "kunstvoll angerichteten Speisen (→ Essen & Trinken)."
        ),
        precedence=7,
    ),
    "sport_aktivitaet": CategoryDefinition(
        key="sport_aktivitaet",
        display_name="Sport & Aktivität",
        definition=(
            "Eine sportliche oder körperlich aktive Handlung ist bildbestimmend (Laufen, "
            "Radfahren, Schwimmen, Ski, Ballsport, Wandern, Klettern, Spielplatz-Aktivität)."
        ),
        delimitation=(
            "Nicht bei bloßem Posieren mit Sportgerät ohne erkennbare Handlung (→ Menschen). "
            "Nicht bei einem abgestellten Sportgerät ohne handelnde Person (→ Gegenstand bzw. "
            "Fahrzeug)."
        ),
        # Steht BEWUSST vor `menschen` (ADR 0049): bei sportlichen Aktivitäten sind fast immer
        # Personen bildbestimmend - ohne diesen Vorrang koennte die Kategorie faktisch nie
        # gewinnen. Eigener, literaler Testfall in tests/test_categories.py.
        precedence=2,
    ),
    CATEGORY_NOT_RECOGNIZED: CategoryDefinition(
        key=CATEGORY_NOT_RECOGNIZED,
        display_name="Nicht erkannt",
        definition=(
            "Kein Bildmotiv ist sicher bestimmbar — unscharf, zu dunkel, stark abstrakt, oder die "
            "Erkennung ist zu unsicher."
        ),
        delimitation=(
            "Nicht zu verwenden, wenn ein Motiv erkennbar ist, aber keine spezifischere Kategorie "
            "passt — dann „Gegenstand“."
        ),
        # Ausserhalb der Vorrangreihenfolge (siehe CategoryDefinition-Docstring).
        precedence=None,
    ),
}


# Welche lokal berechneten Kriterien (criteria.py::CRITERIA_REGISTRY) welche Kategorie als
# Kandidaten stuetzen (ADR 0049). Nur SECHS der zwoelf Kategorien sind lokal bestimmbar - die
# uebrigen entstehen ausschliesslich im Remote-Lauf (bewusst akzeptierte Grenze der Spec).
#
# `landmark` speist `gebaeude_bauwerk` mit, bildet aber KEINE eigene Kategorie mehr: der erkannte
# Sehenswuerdigkeits-Name bleibt am Foto sichtbar (PhotoLandmarkDetection), taugt aber nicht als
# Gruppierungsachse eines geschlossenen Sets. Diese bewusste Ausnahme ist im Invariantentest
# benannt, statt die Gegenrichtung der Konsistenzpruefung wegzulassen.
LOCAL_CATEGORY_SIGNALS: dict[str, frozenset[str]] = {
    "menschen": frozenset({"content_people"}),
    "tier": frozenset({"tier"}),
    "essen_trinken": frozenset({"essen_trinken"}),
    "fahrzeug": frozenset({"fahrzeug"}),
    "gebaeude_bauwerk": frozenset({"gebaeude", "landmark"}),
    "landschaft": frozenset({"landschaft"}),
}


def is_known_category(key: str) -> bool:
    """Reine Whitelist-Pruefung gegen das feste Set - Validierungsfunktion von
    `PUT /photos/{id}/category-override` (Security-Abschnitt der Spec 0289, Punkt 2).

    BEWUSST ohne jede Normalisierung des Eingabewerts (kein `strip()`/`casefold()`, kein Praefix-/
    Regex-Vergleich): der Client schickt den Key exakt so zurueck, wie `GET /categories` ihn
    geliefert hat. `nicht_erkannt` ist ein gueltiger Wert (regulaere Option, kein Sonderfall)."""
    return key in CATEGORY_REGISTRY


def resolve_category(candidates: Iterable[str]) -> str:
    """Bestimmt die EINE Kategorie eines Fotos aus seiner Kandidatenmenge (ADR 0049,
    Entwurfsentscheidung 4: "Das Modell nennt Kandidaten, der Code entscheidet").

    Reine Funktion ueber einer geschlossenen Datenstruktur - unabhaengig davon, welche anderen
    Fotos im Projekt liegen (das ist der Kern-Unterschied zur abgeloesten Haeufigkeitsableitung aus
    ADR 0023) und unabhaengig von der HERKUNFT eines Kandidaten: lokale Signale und
    Remote-Kategorien gehen als EINE Menge ein.

    Regeln: unbekannte Werte werden ignoriert (nicht abgelehnt - eine gesteuerte oder entartete
    Modellantwort darf hoechstens eine falsche, aber gueltige Kategorie erzwingen); von den
    verbleibenden echten Kategorien gewinnt die kleinste `precedence`; `CATEGORY_NOT_RECOGNIZED`
    steht ausserhalb der Reihenfolge und ist das Ergebnis genau dann, wenn keine echte Kategorie
    unter den Kandidaten ist (leere Menge oder ausschliesslich der Auffangwert).

    `Iterable[str]` statt `set[str]`, damit Aufrufer keine unnoetige Konvertierung brauchen
    (`set`/`frozenset`/`list`/`tuple` mit Duplikaten liefern dasselbe Ergebnis). Die Eingabe wird
    nicht mutiert."""
    best_key: str | None = None
    best_precedence: int | None = None
    for candidate in candidates:
        definition = CATEGORY_REGISTRY.get(candidate)
        if definition is None or definition.precedence is None:
            continue
        if best_precedence is None or definition.precedence < best_precedence:
            best_key = definition.key
            best_precedence = definition.precedence
    if best_key is None:
        return CATEGORY_NOT_RECOGNIZED
    return best_key


def build_classification_prompt() -> str:
    """Erzeugt den Klassifizierungs-Prompt AUSSCHLIESSLICH aus `CATEGORY_REGISTRY` (ADR 0049,
    Entwurfsentscheidung 3) - Prompt und Set koennen damit nicht auseinanderlaufen, eine zweite
    gepflegte Liste im Prompt-Literal gibt es nicht.

    Security-Muss-Kriterium (Spec 0289, Abschnitt 5): der Prompt entsteht nie aus Datenbankinhalten
    und nie aus vorherigen Modellantworten - es gibt keinen Rueckkopplungspfad, ueber den eine
    Antwort den naechsten Prompt beeinflussen koennte."""
    lines = [
        "Analysiere dieses Foto und ordne es einem festen Kategorien-Set zu.",
        "",
        "Leitfrage fuer die Zuordnung: Was ist das dominante Bildmotiv?",
        "",
        "Verfuegbare Kategorien (verwende ausschliesslich den jeweiligen Schluessel):",
    ]
    for definition in CATEGORY_REGISTRY.values():
        lines.append(
            f'- "{definition.key}" ({definition.display_name}): {definition.definition} '
            f"Abgrenzung: {definition.delimitation}"
        )
    lines.extend(
        [
            "",
            "Anlass- und Ereignisbegriffe (Geburtstag, Urlaub, Weihnachten, Hochzeit) sind KEINE "
            "Kategorie - vergib sie ausschliesslich als Feinlabel.",
            "",
            f"Nenne ALLE in Frage kommenden Kategorien (hoechstens "
            f"{MAX_REMOTE_CATEGORIES_PER_PHOTO}), nicht nur die eine wahrscheinlichste - die "
            "Auswahl der endgueltigen Kategorie trifft die Anwendung selbst. Ist kein Bildmotiv "
            f'sicher bestimmbar, nenne "{CATEGORY_NOT_RECOGNIZED}".',
            "",
            f"Nenne zusaetzlich hoechstens {MAX_FINE_LABELS_PER_PHOTO} kurze, frei formulierte "
            "deutsche Feinlabels, die das Foto naeher beschreiben (Anlass, Ort, konkretes Motiv).",
            "",
            "Antworte AUSSCHLIESSLICH mit einem einzigen validen JSON-Objekt, ohne "
            "Markdown-Codeblock, ohne weiteren Text, exakt in dieser Form: "
            '{"categories": ["<Schluessel>", ...], "fine_labels": ["<Feinlabel>", ...]}',
        ]
    )
    return "\n".join(lines)
