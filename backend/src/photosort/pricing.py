from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from photosort.cloud_vision import (
    ANTHROPIC_VISION_MODEL,
    ANTHROPIC_VISION_MODEL_SONNET,
    MISTRAL_VISION_MODEL,
    MISTRAL_VISION_MODEL_SMALL,
    TokenUsage,
)

# Preisquelle der Ist-Kostenrechnung: eine Code-Konstante je Modell-ID, KEIN Settings-/env-Feld.
# Eine Preisänderung ist kein Deployment-Parameter, sondern eine belegpflichtige
# Tatsachenbehauptung - sie gehört in einen Commit mit Datum, Quelle und Review, nicht in eine
# `.env`, in der sie unbemerkt jeden historischen Betrag umdeuten könnte.
#
# Es ist die EINZIGE gepflegte Preistatsache: die Vorab-Schätzung je Bild
# (`estimate_usd_per_image` unten) ist aus dieser Tabelle abgeleitet, keine zweite Konstante
# daneben. Ein neues Modell braucht damit genau eine gepflegte Tatsache - seine verifizierten
# Token-Preise -, und die Schätzung folgt zwangsläufig.


@dataclass(frozen=True)
class ModelPricing:
    """Listenpreis eines Modells in USD je einer Million Tokens, getrennt nach Ein- und Ausgabe.

    `float` statt `Decimal`: die Beträge liegen im Cent-Bereich, es findet keine Buchhaltung
    statt, gerundet wird erst bei der Ausgabe.

    `source_url`/`verified_on` sind PFLICHTFELDER: die Verifikation gegen die offizielle
    Anbieterdokumentation ist damit nicht ein Kommentar, den man vergessen kann, sondern ein
    Feld, ohne das der Eintrag nicht konstruierbar ist. Ein Preis, der nicht gegen die offizielle
    Quelle verifiziert werden konnte, gehört nicht ins Produkt - und sein Modell nicht in
    `cloud_vision.py::VISION_MODELS_BY_PROVIDER`."""

    input_usd_per_mtok: float
    output_usd_per_mtok: float
    source_url: str
    verified_on: date


_TOKENS_PER_MTOK = 1_000_000

# Schlüssel ist die MODELL-ID (nicht der Provider): der Preis hängt am Modell. Die
# Mengengleichheit dieser Tabelle mit `cloud_vision.py::VISION_MODELS_BY_PROVIDER` ist per
# Invariantentest erzwungen (tests/test_pricing.py) - der einzige automatisierte Schutz davor,
# dass ein wählbares Modell ohne Preis in die Auswahl gerät, und zugleich davor, dass ein Eintrag
# ohne Leser als unbeaufsichtigt alternde Tatsachenbehauptung liegenbleibt. Wird ein abgelöstes
# Modell wieder aufgenommen, wird `verified_on` NEU verifiziert, nie aus dem Altbestand geerbt.
#
# Beide Werte je Eintrag sind gegen `source_url` zum Stand `verified_on` verifiziert. Die dort
# ebenfalls gelisteten Cache-Tarife sind bewusst NICHT abgebildet: das Projekt setzt kein
# Prompt-Caching ein, jeder Vision-Aufruf schickt ein eigenes Bild.
#
# `mistral-small-2603` ist das erste asymmetrisch bepreiste Mistral-Modell - der Ausgabepreis ist
# das Vierfache des Eingabepreises, beide Ministral-Einträge sind symmetrisch. Ein vertauschtes
# oder versehentlich symmetrisch übernommenes Paar fällt durch KEINEN der Ordnungstests
# ("stärker => teurer"), weil auch $0,00045 und $0,0017 über der Voreinstellung $0,0003 liegen;
# dagegen steht allein der Literal-Pin auf $0,000504 je Bild in tests/test_pricing.py. Die
# Ausgabeseite ist zusätzlich durch `_MAX_RESPONSE_TOKENS = 256` in BEIDEN Clients hart gedeckelt
# (höchstens $0,00015 Ausgabekosten je Aufruf) - wer den Deckel anhebt, stellt diese Rechnung neu.
#
# Bekannte Grenze, bewusst nicht automatisiert abgesichert: die inhaltliche RICHTIGKEIT dieser
# Werte gegen echte Anbieter-Abrechnungen ist nicht testbar. Ersatzverfahren: Abgleich der ersten
# realen Rechnung mit der Summe auf der Statistikseite; bei Abweichung die Konstante korrigieren
# und die Beträge aus den gespeicherten Tokens neu berechnen.
MODEL_PRICING: dict[str, ModelPricing] = {
    ANTHROPIC_VISION_MODEL: ModelPricing(
        input_usd_per_mtok=1.00,
        output_usd_per_mtok=5.00,
        source_url="https://platform.claude.com/docs/en/about-claude/pricing",
        verified_on=date(2026, 9, 6),
    ),
    ANTHROPIC_VISION_MODEL_SONNET: ModelPricing(
        input_usd_per_mtok=2.00,
        output_usd_per_mtok=10.00,
        source_url="https://platform.claude.com/docs/en/about-claude/pricing",
        verified_on=date(2026, 9, 6),
    ),
    MISTRAL_VISION_MODEL: ModelPricing(
        input_usd_per_mtok=0.10,
        output_usd_per_mtok=0.10,
        source_url="https://docs.mistral.ai/models/ministral-3-3b-25-12",
        verified_on=date(2026, 8, 23),
    ),
    MISTRAL_VISION_MODEL_SMALL: ModelPricing(
        input_usd_per_mtok=0.15,
        output_usd_per_mtok=0.60,
        source_url="https://docs.mistral.ai/models/model-cards/mistral-small-4-0-26-03",
        verified_on=date(2026, 9, 9),
    ),
}


def compute_cost_usd(model: str, usage: TokenUsage) -> float | None:
    """Ist-Kosten EINER Phase in USD aus ihrem gemessenen Token-Verbrauch.

    Reine Funktion ohne DB und ohne Netz. Ein hier nicht hinterlegtes Modell liefert `None`, nie
    ein stilles `0.0`: ein Modellwechsel ohne Preispflege soll als "nicht erfasst" auffallen,
    statt sich als kostenloser Lauf zu tarnen. `TokenUsage(0, 0)` liefert dagegen `0.0` -
    "erfasst, es sind keine Kosten angefallen"."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None
    return (
        usage.input_tokens * pricing.input_usd_per_mtok
        + usage.output_tokens * pricing.output_usd_per_mtok
    ) / _TOKENS_PER_MTOK


@dataclass(frozen=True)
class AssumedImageUsage:
    """Angenommener Token-Verbrauch EINES Bildes, je Provider.

    Bewusst je PROVIDER und nicht je Modell: die Annahme hängt an unserer Bildquelle (die
    `display`-Cache-Variante, 2048px lange Kante, thumbnails.py) und unserem Prompt, nicht am
    Modell - nur die Umrechnung Pixel -> Tokens ist providerspezifisch. Ein neues Modell desselben
    Anbieters erbt die Annahme und braucht nur seine verifizierten Token-Preise."""

    input_tokens: int
    output_tokens: int


# Herleitung der beiden Annahmen. Sie sind so kalibriert, dass die abgeleitete Schätzung für das
# jeweilige VOREINSTELLUNGS-Modell $0,0052 anthropic bzw. $0,0003 mistral exakt reproduziert -
# beide Beträge sind in tests/test_pricing.py gepinnt.
#
# anthropic: 4600 Input-Tokens = ~3900 Bild- + ~700 Prompt-Tokens.
#   Bild: offizielle Anthropic-Formel `tokens ~= breite_px * hoehe_px / 750` (verifiziert gegen
#   den bekannten Referenzwert 1092x1092px ~= 1590 Tokens), gerechnet auf die real versendete
#   `display`-Variante (DISPLAY_MAX_SIZE=2048px lange Kante, Seitenverhältnis erhalten): ein
#   typisches 3:2-/4:3-Landschaftsfoto an dieser Obergrenze ergibt ca. 3700-4200 Bild-Tokens.
#   Prompt: der aus CATEGORY_REGISTRY erzeugte Klassifikations-Prompt (categories.py::
#   build_classification_prompt, 13 Kategorie-Blöcke, ~3400 Zeichen bei ~4 Zeichen/Token).
#   Ausgabe: JSON-Array mit 1-3 Objekten. Der Wert 120 deckt die heute vollbesetzte Antwort
#   (überschlägig 80-100 Tokens) ab; bei einer weiteren Erweiterung des Antwortschemas ist die
#   Marge erneut zu prüfen - sie beträgt nur noch etwa das Anderthalbfache, und die Schätzung ist
#   die einzige Absicherung vor der kostenpflichtigen Aktion.
# mistral: 2880 Input-Tokens = ~2030 Bild- + ~850 Prompt-Tokens.
#   Mistral veröffentlicht KEINE offizielle Bild-Token-Formel (anders als Anthropic) - dieser
#   Anteil bleibt ausdrücklich DOKUMENTIERT-UNKALIBRIERT, gestützt auf das vergleichbare
#   Pixtral-Familien-Tiling (Bandbreite 1000-4000 Bild-Tokens je nach Auflösung/Kachelung).
#   Der Eintrag deckt zwei Modellfamilien ab: `mistral-small-2603` erbt die Annahme über eine
#   Familiengrenze hinweg und ist damit ebenfalls unkalibriert, die gefährliche
#   Abweichungsrichtung ist die Unterschätzung. Sie wird trotzdem NICHT angefasst - die Werte
#   sind an die exakte Reproduktion von $0,0003 gebunden, eine Anhebung verschöbe genau die.
#   Größenordnung rund $0,0005 gegenüber ~$0,0003, selbst ein Faktor 2 bliebe im Zehntelcent-
#   Bereich je Bild. Zeigt die erste reale Rechnung deutlich mehr als 120 Ausgabe-Tokens je Bild,
#   ist das der Anlass für eine eigene Story (Verbrauchsannahme je MODELL statt je Anbieter) -
#   nicht für eine stille Korrektur hier.
#
# Bewusst grob und eher über- als unterschätzend: EIN Preis je Bild für BEIDE Cloud-Anteile,
# obwohl der Landmark-Prompt kürzer ist als der Kategorie-Prompt. Die Schätzung soll nicht zu
# niedrig ausfallen. Bekannte Grenze und Ersatzverfahren wie bei MODEL_PRICING oben.
ASSUMED_USAGE_BY_PROVIDER: dict[str, AssumedImageUsage] = {
    "anthropic": AssumedImageUsage(input_tokens=4_600, output_tokens=120),
    "mistral": AssumedImageUsage(input_tokens=2_880, output_tokens=120),
}


def estimate_usd_per_image(model: str, provider: str) -> float | None:
    """Vorab-Schätzung der Kosten EINES Bildes für ein Modell.

    `None` heißt "kein Preis hinterlegt", nie ein stilles `0.0` - dieselbe Semantik wie
    `compute_cost_usd`. Die Oberfläche weist diesen Fall als fehlende Kostenangabe aus, statt
    einen falschen Betrag zu zeigen. Ein unbekannter Provider liefert aus demselben Grund `None`
    statt zu werfen."""
    assumed = ASSUMED_USAGE_BY_PROVIDER.get(provider)
    if assumed is None:
        return None
    return compute_cost_usd(
        model,
        TokenUsage(input_tokens=assumed.input_tokens, output_tokens=assumed.output_tokens),
    )
