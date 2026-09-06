from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from photosort.cloud_vision import (
    ANTHROPIC_VISION_MODEL,
    ANTHROPIC_VISION_MODEL_SONNET,
    MISTRAL_VISION_MODEL,
    MISTRAL_VISION_MODEL_8B,
    TokenUsage,
)

# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 2: die Preisquelle der IST-Kostenrechnung - eine Code-Konstante je Modell-ID,
# KEIN Settings-/env-Feld. Eine Preisaenderung ist kein Deployment-Parameter, sondern eine
# belegpflichtige Tatsachenbehauptung: sie gehoert in einen Commit mit Datum, Quelle und Review -
# nicht in eine `.env`, in der sie unbemerkt jeden historischen Betrag umdeuten koennte.
#
# EINE PREISQUELLE, ZWEI ABLEITUNGEN (specs/features/0304-cloud-modell-je-anbieter-waehlbar.md,
# decisions/0059-modellwahl-je-anbieter-und-modellgebundene-kostenschaetzung.md Punkt 3): bis
# Spec 0304 standen hier zwei handgepflegte Preiskonstanten nebeneinander - `MODEL_PRICING` (Ist-
# Rechnung pro TOKEN, nach dem Lauf) und `remote_classification.py::COST_PER_IMAGE_USD` (Vorab-
# Schaetzung pro BILD, je PROVIDER). Die zweite ist ersatzlos entfallen: sie war je Provider
# geschluesselt und wurde damit bei einem Modellwechsel unbemerkt falsch - genau der Defekt, den
# Spec 0304 behebt. Die Schaetzung ist seitdem `estimate_usd_per_image()` unten, abgeleitet aus
# DIESER Tabelle ueber eine offengelegte Verbrauchsannahme. Ein neues Modell braucht damit genau
# EINE gepflegte Tatsache - seine verifizierten Token-Preise -, und die Schaetzung folgt
# zwangslaeufig. Dies loest die gegenteilige Festlegung aus ADR 0051 Punkt 2 ab; alle uebrigen
# Punkte von ADR 0051 bleiben in Kraft.


@dataclass(frozen=True)
class ModelPricing:
    """Listenpreis eines Modells in USD je einer Million Tokens, getrennt nach Ein- und Ausgabe.

    `float` statt `Decimal` analog zur Persistenz der Betraege (ADR 0051 Punkt 3): die Betraege
    liegen im Cent-Bereich, es findet keine Buchhaltung statt, gerundet wird erst bei der
    Ausgabe.

    `source_url`/`verified_on` sind PFLICHTFELDER (ADR 0059 Punkt 5): die Verifikation gegen die
    offizielle Anbieterdokumentation ist damit nicht mehr ein Kommentar, den man vergessen kann,
    sondern ein Feld, ohne das der Eintrag nicht konstruierbar ist. Ein Preis, der nicht gegen die
    offizielle Quelle verifiziert werden konnte, gehoert nicht ins Produkt - und sein Modell nicht
    in `cloud_vision.py::VISION_MODELS_BY_PROVIDER`."""

    input_usd_per_mtok: float
    output_usd_per_mtok: float
    source_url: str
    verified_on: date


_TOKENS_PER_MTOK = 1_000_000

# Schluessel ist die MODELL-ID (nicht der Provider): der Preis haengt am Modell, und die
# Modell-IDs werden bereits in cloud_vision.py zentral gefuehrt. Die Vollstaendigkeit dieser
# Tabelle gegenueber `cloud_vision.py::VISION_MODELS_BY_PROVIDER` ist per Invariantentest
# erzwungen (tests/test_pricing.py) - der einzige automatisierte Schutz gegen einen Modellwechsel
# ohne Preispflege, und seit Spec 0304 zugleich der Schutz davor, dass ein WAEHLBARES Modell ohne
# Preis in die Auswahl geraet.
#
# Beide Werte sind gegen die offiziellen Preislisten der Anbieter verifiziert (developer-Agent,
# 2026-09-02):
#
# - claude-haiku-4-5: $1.00/MTok Input, $5.00/MTok Output
#   (https://docs.claude.com/en/docs/about-claude/pricing, abgerufen 2026-09-02; die dort
#   ebenfalls gelisteten Cache-Tarife - $1.25/$2.00 Schreiben, $0.10 Lesen - sind hier bewusst
#   NICHT abgebildet: das Projekt setzt kein Prompt-Caching ein, jeder Vision-Aufruf schickt ein
#   eigenes Bild).
# - ministral-3b-2512: $0.10/MTok Input UND Output
#   (https://docs.mistral.ai/models/ministral-3-3b-25-12, abgerufen 2026-09-02 - symmetrische
#   Preisgestaltung, anders als bei Anthropic; deckt sich mit der frueheren Verifikation vom
#   2026-08-23 in remote_classification.py::COST_PER_IMAGE_USD).
#
# Bekannte Grenze (Teststrategie der Spec, "bewusst nicht automatisiert abgesichert"): die
# inhaltliche RICHTIGKEIT dieser Werte gegen echte Anbieter-Abrechnungen ist nicht testbar.
# Ersatzverfahren: Abgleich der ersten realen Rechnung mit der Summe auf der Statistikseite; bei
# Abweichung die Konstante korrigieren und die Betraege aus den gespeicherten Tokens (die deshalb
# mitpersistiert werden, ADR 0051 Punkt 3) neu berechnen.
#
# - claude-sonnet-5 (Spec 0304, das zweite waehlbare Anthropic-Modell): $2.00/MTok Input,
#   $10.00/MTok Output (https://platform.claude.com/docs/en/about-claude/pricing, abgerufen
#   2026-09-06; Vision-Faehigkeit gegen die Modelluebersicht derselben Doku bestaetigt). Cache-
#   Tarife aus demselben Grund wie oben nicht abgebildet.
# - ministral-8b-2512 (Spec 0304, das zweite waehlbare Mistral-Modell und der Anlass der Story):
#   $0.15/MTok Input UND Output (https://docs.mistral.ai/models/ministral-3-8b-25-12, abgerufen
#   2026-09-06 - symmetrisch wie beim 3B-Geschwistermodell; Vision-Faehigkeit auf derselben Seite
#   bestaetigt). Nachgetragen, nachdem die Verifikation in der umsetzenden Sitzung an einem
#   blockierten Netzzugang zu docs.mistral.ai gescheitert war und ADR 0059 Punkt 5 einen
#   geschaetzten oder aus einer Websuche abgeleiteten Preis ausschliesst.
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
    MISTRAL_VISION_MODEL_8B: ModelPricing(
        input_usd_per_mtok=0.15,
        output_usd_per_mtok=0.15,
        source_url="https://docs.mistral.ai/models/ministral-3-8b-25-12",
        verified_on=date(2026, 9, 6),
    ),
}


def compute_cost_usd(model: str, usage: TokenUsage) -> float | None:
    """Ist-Kosten EINER Phase in USD aus ihrem gemessenen Token-Verbrauch (ADR 0051 Punkt 1).

    Reine Funktion ohne DB und ohne Netz. Ein hier nicht hinterlegtes Modell liefert `None`, nie
    ein stilles `0.0` (ADR 0051 Punkt 2): ein Modellwechsel ohne Preispflege soll als "nicht
    erfasst" auffallen, statt sich als kostenloser Lauf zu tarnen. `TokenUsage(0, 0)` liefert
    dagegen `0.0` - "erfasst, es sind keine Kosten angefallen"."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None
    return (
        usage.input_tokens * pricing.input_usd_per_mtok
        + usage.output_tokens * pricing.output_usd_per_mtok
    ) / _TOKENS_PER_MTOK


# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 3 ab hier: die VORAB-
# Schaetzung. Sie ist seit Spec 0304 keine eigene Konstante mehr, sondern `compute_cost_usd` ueber
# einer ANGENOMMENEN statt einer gemessenen Tokenzahl - derselbe Rechenweg, dieselbe Preistabelle,
# damit dasselbe Modell.


@dataclass(frozen=True)
class AssumedImageUsage:
    """Angenommener Token-Verbrauch EINES Bildes, je Provider (ADR 0059 Punkt 3).

    Bewusst je PROVIDER und nicht je Modell: die Annahme haengt an unserer Bildquelle (die
    `display`-Cache-Variante, 2048px lange Kante, thumbnails.py) und unserem Prompt, nicht am
    Modell - nur die Umrechnung Pixel -> Tokens ist providerspezifisch. Ein neues Modell desselben
    Anbieters erbt die Annahme und braucht nur seine verifizierten Token-Preise."""

    input_tokens: int
    output_tokens: int


# Herleitung, uebernommen aus der frueheren `remote_classification.py::COST_PER_IMAGE_USD` und
# dort geloescht (ADR 0059 Punkt 3) - die Werte sind so kalibriert, dass die abgeleitete Schaetzung
# fuer das jeweilige VOREINSTELLUNGS-Modell die bisherigen Betraege exakt reproduziert
# ($0.0052 anthropic / $0.0003 mistral, per Test gepinnt). Das macht das Akzeptanzkriterium "ohne
# gesetzte Einstellung exakt wie bisher" zu einer Testaussage statt zu einer Behauptung.
#
# anthropic: 4600 Input-Tokens = ~3900 Bild- + ~700 Prompt-Tokens.
#   Bild: offizielle Anthropic-Formel `tokens ~= breite_px * hoehe_px / 750` (verifiziert gegen den
#   bekannten Referenzwert 1092x1092px ~= 1590 Tokens), gerechnet auf die real versendete
#   `display`-Variante (DISPLAY_MAX_SIZE=2048px lange Kante, Seitenverhaeltnis erhalten): ein
#   typisches 3:2-/4:3-Landschaftsfoto an dieser Obergrenze ergibt ca. 3700-4200 Bild-Tokens
#   (2048x1365 bzw. 2048x1536); viele reale Quellfotos sind kleiner und verbrauchen weniger.
#   Prompt: der aus CATEGORY_REGISTRY erzeugte Klassifikations-Prompt (categories.py::
#   build_classification_prompt, 13 Kategorie-Bloecke, ~3400 Zeichen bei ~4 Zeichen/Token).
#   Ausgabe: JSON-Array mit 1-3 Objekten, 80-160 Tokens, Mittelwert 120.
# mistral: 2880 Input-Tokens = ~2030 Bild- + ~850 Prompt-Tokens.
#   Mistral veroeffentlicht fuer die Ministral-Familie KEINE offizielle Bild-Token-Formel (anders
#   als Anthropic) - dieser Anteil bleibt ausdruecklich DOKUMENTIERT-UNKALIBRIERT, gestuetzt auf
#   das vergleichbare Pixtral-Familien-Tiling (Bandbreite 1000-4000 Bild-Tokens je nach
#   Aufloesung/Kachelung). Ausgabe wie oben.
#
# Bewusst grob und eher ueber- als unterschaetzend (unveraendert gegenueber ADR 0050 Punkt 5): EIN
# Preis je Bild fuer BEIDE Cloud-Anteile, obwohl der Landmark-Prompt kuerzer ist als der
# Kategorie-Prompt. Die Schaetzung ist seit Spec 0296 die einzige verbliebene Absicherung vor der
# kostenpflichtigen Aktion - sie soll nicht zu niedrig ausfallen.
#
# Bekannte Grenze (wie bei MODEL_PRICING): die Richtigkeit der Annahme gegen echte Abrechnungen
# ist nicht testbar. Ersatzverfahren unveraendert: Abgleich der ersten realen Rechnung mit den
# Ist-Kosten auf der Statistikseite.
ASSUMED_USAGE_BY_PROVIDER: dict[str, AssumedImageUsage] = {
    "anthropic": AssumedImageUsage(input_tokens=4_600, output_tokens=120),
    "mistral": AssumedImageUsage(input_tokens=2_880, output_tokens=120),
}


def estimate_usd_per_image(model: str, provider: str) -> float | None:
    """Vorab-Schaetzung der Kosten EINES Bildes fuer ein Modell (ADR 0059 Punkt 3).

    `None` heisst "kein Preis hinterlegt", nie ein stilles `0.0` - dieselbe Semantik wie
    `compute_cost_usd` (ADR 0051 Punkt 2/ADR 0059 Punkt 4). Die Oberflaeche weist diesen Fall als
    fehlende Kostenangabe aus, statt einen falschen Betrag zu zeigen. Ein unbekannter Provider
    liefert aus demselben Grund `None` statt zu werfen."""
    assumed = ASSUMED_USAGE_BY_PROVIDER.get(provider)
    if assumed is None:
        return None
    return compute_cost_usd(
        model,
        TokenUsage(input_tokens=assumed.input_tokens, output_tokens=assumed.output_tokens),
    )
