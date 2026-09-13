"""Das feste Motivset: acht Motive, je Foto ein Staerkevektor statt einer Hauptkategorie.

Bewusst ein EIGENES Modul und bewusst REIN: keine DB-, Netzwerk- oder
Bildverarbeitungs-Abhaengigkeit und kein Import aus `criteria.py`/`models.py` -
`LOCAL_MOTIF_SIGNALS` referenziert Kriterien-Keys nur als Strings. Die Konsistenz gegen
`criteria.py::CRITERIA_REGISTRY` wird per Invariantentest erzwungen (tests/test_motifs.py), nicht
per Import.

Es gibt hier KEINE Vorrangreihenfolge, keinen Auffangwert und keine Schwelle, ab der ein Motiv
"zaehlt": ein Foto traegt fuer jedes Motiv eine Staerke in [0, 1]. Ein Ordnungsattribut darf an
`MotifDefinition` nicht wieder entstehen - ein Invariantentest haelt fest, dass die Registry keine
Ordnung kennt, die eine Auswahl tragen koennte.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

# "Dokument und Screenshot" ist KEIN Motiv, sondern ein Ausschluss-Signal: ein so erkanntes Foto
# traegt `excluded_document = true` und erscheint in keiner Motivauswahl. Der Schluessel steht
# deshalb AUSSERHALB von `MOTIF_REGISTRY` und ist kein gueltiger Korrektur-Schluessel
# (`is_motif_key(EXCLUSION_KEY)` ist falsch) - `dokument_screenshot` ist nicht von Hand
# korrigierbar, ein faelschlich ausgeschlossenes Foto kommt allein ueber einen erneuten
# Klassifizierungslauf zurueck.
EXCLUSION_KEY = "dokument_screenshot"

# Anzeigebaender der STATISTIK und ausdruecklich KEINE Zugehoerigkeitsschwelle: kein Codepfad, der
# ueber Zugehoerigkeit, Auswahl oder Rangfolge entscheidet, darf sie lesen, und ausserhalb der
# Statistiktabelle erscheint kein Bandwort. Ein Bandwort neben dem Einzelwert eines Fotos lehrte
# den Nutzer genau die Schwelle, die dieses Motivset abschafft.
#
# Beide Grenzen inklusiv verglichen (`>=`). Als Bruch geschrieben und NUR HIER: `0.67` an einer
# Stelle und `2/3` an einer anderen verschiebt die Grenze um einen Betrag, den kein Test trifft.
MOTIF_STRENGTH_BAND_STRONG = 2 / 3
MOTIF_STRENGTH_BAND_MEDIUM = 1 / 3


@dataclass(frozen=True)
class MotifDefinition:
    """Ein Eintrag des festen Motivsets. `definition` und `delimitation` sind fachlich Teil des
    Motivs - sie sind zugleich Prompt-Grundlage (`classification_prompt.py`) und UI-Erklaerung
    (`GET /motifs`); eine zweite Pflegestelle gibt es nicht.

    KEIN Ordnungsattribut - kein Vorrang-, Rang- oder Gewichtsfeld: die Reihenfolge dieses Dict
    ist reine ANZEIGEreihenfolge, keine Auswahlregel. Ein Zahlenfeld daneben waere die feste
    Vorrangreihenfolge zurueck, die dieses Motivset abschafft; ein Invariantentest in
    tests/test_motifs.py prueft die Felder des Eintrags und nicht ihre Namen."""

    key: str
    display_name: str
    definition: str
    delimitation: str


# Die acht Motive in ANZEIGEREIHENFOLGE - `GET /motifs`, die Staerkeliste am Foto und die
# Statistiktabelle uebernehmen genau diese Reihenfolge, damit sie ueberall im Produkt und auf jedem
# Foto dieselbe ist.
MOTIF_REGISTRY: dict[str, MotifDefinition] = {
    "menschen": MotifDefinition(
        key="menschen",
        display_name="Menschen",
        definition=(
            "Eine oder mehrere Personen sind auf dem Foto zu sehen (Porträt, Gruppenbild, "
            "Schnappschuss von Personen)."
        ),
        delimitation=(
            "Die Stärke folgt dem Bildanteil der Personen: Passanten am Bildrand sind schwach, "
            "ein Porträt ist stark. Nicht für Personendarstellungen als Skulptur, Gemälde oder "
            "Puppe."
        ),
    ),
    "landschaft": MotifDefinition(
        key="landschaft",
        display_name="Landschaft",
        definition=(
            "Eine weiträumige Natur- oder Außenszene ist zu sehen (Berge, Küste, See, Wald, Feld, "
            "Wüste, Himmel, Panorama)."
        ),
        delimitation=(
            "Nicht bei Nah- oder Detailaufnahmen einzelner Naturelemente — eine Blütennahaufnahme "
            "ist Detail und Stimmung, eine Blumenwiese als Weitwinkelszene ist Landschaft. Eine "
            "bebaute Szene schwächt Landschaft nicht ab, sondern stärkt Bauwerk und "
            "Sehenswürdigkeit zusätzlich."
        ),
    ),
    "bauwerk_sehenswuerdigkeit": MotifDefinition(
        key="bauwerk_sehenswuerdigkeit",
        display_name="Bauwerk und Sehenswürdigkeit",
        definition=(
            "Ein einzelnes Bauwerk oder eine benannte Sehenswürdigkeit ist zu sehen (Haus, Kirche, "
            "Burg, Brücke, Turm, Denkmal, Tempel, Ruine) — auch von innen."
        ),
        delimitation=(
            "Nicht für eine Bebauung als bloßen Hintergrund einer Straßenszene — dafür Stadt und "
            "Straße. Eine erkannte Sehenswürdigkeit ist kein eigenes Motiv, sie verstärkt dieses."
        ),
    ),
    "stadt_strasse": MotifDefinition(
        key="stadt_strasse",
        display_name="Stadt und Straße",
        definition=(
            "Eine Stadt-, Straßen- oder Verkehrsszene ist zu sehen (Straßenzug, Platz, Markt, "
            "Gasse, Fahrzeuge, Verkehrsmittel, Bahnhof, Hafen)."
        ),
        delimitation=(
            "Ein Fahrzeug ist Teil der Straßenszene und kein eigenes Motiv. Nicht für ein "
            "einzelnes, freistehendes Bauwerk — dafür Bauwerk und Sehenswürdigkeit."
        ),
    ),
    "tiere": MotifDefinition(
        key="tiere",
        display_name="Tiere",
        definition=(
            "Ein oder mehrere Tiere sind zu sehen (Haustier, Wildtier, Vogel, Insekt, Fisch)."
        ),
        delimitation=(
            "Nicht bei Tierdarstellungen als Skulptur, Gemälde oder Plüschtier. Nicht bei "
            "zubereitetem Fleisch oder Fisch als Speise — dafür Essen und Trinken."
        ),
    ),
    "essen_trinken": MotifDefinition(
        key="essen_trinken",
        display_name="Essen und Trinken",
        definition="Speisen, Getränke oder ein gedeckter Tisch sind zu sehen.",
        delimitation=(
            "Die Stärke folgt dem Bildanteil: Lebensmittel als unauffälliges Beiwerk einer Raum- "
            "oder Personenszene sind schwach. Nicht bei lebenden Nutzpflanzen im Feld."
        ),
    ),
    "aktivitaet": MotifDefinition(
        key="aktivitaet",
        display_name="Aktivität",
        definition=(
            "Eine erkennbare Handlung oder Betätigung ist im Bild (Laufen, Radfahren, Schwimmen, "
            "Ski, Ballsport, Wandern, Klettern, Tanzen, Spielen, Handwerken, Kochen)."
        ),
        delimitation=(
            "Nicht bei bloßem Posieren mit Sportgerät ohne erkennbare Handlung. Nicht bei einem "
            "abgestellten Sportgerät ohne handelnde Person."
        ),
    ),
    "detail_stimmung": MotifDefinition(
        key="detail_stimmung",
        display_name="Detail und Stimmung",
        definition=(
            "Eine Nah-, Detail- oder Stimmungsaufnahme ohne eigenständiges Hauptmotiv ist zu sehen "
            "(Blüte, Blatt, Struktur, Gegenstand, Kunstwerk, Handarbeit, Licht, Schatten, "
            "Farbfläche, Abendhimmel)."
        ),
        delimitation=(
            "Nicht als Auffangwert für „nichts erkannt“ — ist kein Motiv erkennbar, bleiben alle "
            "acht Stärken niedrig. Nicht für eine weiträumige Szene, die bereits Landschaft ist."
        ),
    ),
}


@dataclass(frozen=True)
class LocalMotifSignal:
    """Wie ein Motiv OHNE Cloud-Aussage aus den bereits berechneten lokalen Signalen entsteht.

    Zwei Arten, und die Art folgt der Messung statt einer Konvention:

    * `kind="area"` - ein erkanntes Objekt wirkt nach seinem ANTEIL am Bild, nicht nach seiner
      Anwesenheit: `min(1, Summe der Flaechenanteile / saturation_fraction)` ueber die
      Bounding-Boxen der Allow-Liste des jeweiligen Kriteriums. Summiert, nicht das Maximum -
      fuenf kleine Personen sind ein Personenbild. Ueberlappende Boxen zaehlen doppelt; das
      Ergebnis ist geklemmt, der Effekt bewusst hingenommen.
    * `kind="scene"` - die Ganzbild-Konfidenz der Szenen-Klassifikation, die keine Boxen liefert.
      Sie ist bereits eine Aussage ueber das ganze Bild; bei mehreren Kriterien gewinnt das
      MAXIMUM, es wird keine Summe erfunden.

    `saturation_fraction` ist genau bei `kind="area"` gesetzt und dort strikt groesser als 0 (per
    Invariantentest) - eine 0 waere eine Division durch Null im Schreibpfad des Staerkevektors."""

    kind: Literal["area", "scene"]
    criterion_keys: tuple[str, ...]
    saturation_fraction: float | None = None


# Welche lokal berechneten Signale (criteria.py::CRITERIA_REGISTRY) welches Motiv mit welcher Art
# stuetzen. Nur SECHS der acht Motive sind lokal ueberhaupt beurteilbar; `aktivitaet` und
# `detail_stimmung` fehlen hier bewusst und bleiben ohne Cloud-Aussage bei 0 - die akzeptierte
# Grenze der lokalen Grundlage, kein Fehlerfall. `GET /motifs` leitet `locally_assessable` aus
# dieser Abbildung ab, damit die Oberflaeche "0 weil nicht zu sehen" von "0 weil nicht angesehen"
# unterscheiden kann, ohne die Liste zu spiegeln.
#
# Die Saettigungsanteile sind dokumentiert-UNKALIBRIERTE Startwerte derselben Klasse wie
# `SHARPNESS_NORMALIZATION_CEILING`: es gibt keinen Fotokorpus im Repository, gegen den sie
# kalibriert werden koennten. Sie stehen AUSSCHLIESSLICH hier, nie zusaetzlich im Worker.
LOCAL_MOTIF_SIGNALS: dict[str, LocalMotifSignal] = {
    "menschen": LocalMotifSignal(
        kind="area", criterion_keys=("content_people",), saturation_fraction=0.15
    ),
    # Die Szenen-Klassifikation liefert keine Boxen - Ganzbild-Konfidenz.
    "landschaft": LocalMotifSignal(kind="scene", criterion_keys=("landschaft",)),
    # `max(Szenen-Konfidenz, Sehenswuerdigkeits-Konfidenz)`: eine erkannte Sehenswuerdigkeit
    # VERSTAERKT das Motiv, statt ein eigenes zu bilden.
    "bauwerk_sehenswuerdigkeit": LocalMotifSignal(
        kind="scene", criterion_keys=("gebaeude", "landmark")
    ),
    "stadt_strasse": LocalMotifSignal(
        kind="area", criterion_keys=("fahrzeug",), saturation_fraction=0.35
    ),
    "tiere": LocalMotifSignal(kind="area", criterion_keys=("tier",), saturation_fraction=0.25),
    "essen_trinken": LocalMotifSignal(
        kind="area", criterion_keys=("essen_trinken",), saturation_fraction=0.3
    ),
}


def is_motif_key(key: str) -> bool:
    """Reine Mitgliedschaftspruefung im geschlossenen Achter-Schluesselraum - die
    Validierungsfunktion beider Korrektur-Endpunkte.

    BEWUSST ohne jede Normalisierung des Eingabewerts (kein `strip()`/`casefold()`, kein Praefix-,
    `startswith`- oder Regex-Vergleich): der Client schickt den Schluessel exakt so zurueck, wie
    `GET /motifs` ihn geliefert hat. `EXCLUSION_KEY` ist ausdruecklich KEIN gueltiger Wert."""
    return key in MOTIF_REGISTRY


def _usable_fraction(value: object) -> float:
    """Ein Fremdwert aus einer Flaechen-/Konfidenzabbildung als brauchbare Zahl in [0, 1], sonst
    `0.0`.

    `bool` ist ausdruecklich AUSGESCHLOSSEN, obwohl `isinstance(True, int)` in Python wahr ist -
    `True` erschiene sonst als die staerkste Aussage, die das Produkt kennt. `NaN`/`±Infinity`
    fallen ueber `math.isfinite` heraus und werden VERWORFEN, nie geklemmt: `strength` ist eine
    `double precision`-Spalte (PostgreSQL nimmt `NaN` an) und Starlette rendert mit
    `allow_nan=False` - ein einziger entarteter Wert legte die gesamte Fotoliste des Projekts auf
    `500`, nicht nur den einen Eintrag."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    number = float(value)
    if not math.isfinite(number):
        return 0.0
    return max(0.0, min(1.0, number))


def local_motif_strengths(
    criterion_values: Mapping[str, float],
    area_fractions: Mapping[str, float],
) -> dict[str, float]:
    """Der lokale Staerkevektor eines Fotos - reine Funktion, ALLE acht Motive, in
    Registry-Reihenfolge.

    `criterion_values` sind die im Lauf berechneten Kriterien-Werte (Grundlage der
    `kind="scene"`-Motive), `area_fractions` die Flaechenanteile je Allow-Liste, berechnet aus den
    BEREITS VORHANDENEN Detektionen desselben Laufs (Grundlage der `kind="area"`-Motive) - unter
    demselben Kriterien-Schluessel, damit es keine zweite Schluesselmenge gibt.

    Ein lokal nicht beurteilbares Motiv (`aktivitaet`, `detail_stimmung`) erscheint mit `0.0` und
    fehlt NICHT: der Vektor ist vollstaendig oder er existiert nicht. Ein Foto ohne jede Detektion
    ergibt acht Nullen - auch das ist eine Beurteilung und nicht die Abwesenheit einer.

    Jeder Wert liegt in [0, 1], auch bei ueberlappenden Boxen, einer ueber den Bildrand
    hinausreichenden Box oder einer Objektklasse, die zu zwei Motiven beitraegt."""
    strengths: dict[str, float] = {}
    for motif_key in MOTIF_REGISTRY:
        signal = LOCAL_MOTIF_SIGNALS.get(motif_key)
        if signal is None:
            strengths[motif_key] = 0.0
            continue
        if signal.kind == "scene":
            strengths[motif_key] = max(
                (_usable_fraction(criterion_values.get(key)) for key in signal.criterion_keys),
                default=0.0,
            )
            continue
        saturation = signal.saturation_fraction
        assert saturation is not None and saturation > 0, motif_key
        covered = sum(_usable_fraction(area_fractions.get(key)) for key in signal.criterion_keys)
        strengths[motif_key] = min(1.0, covered / saturation)
    return strengths
