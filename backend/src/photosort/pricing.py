from __future__ import annotations

from dataclasses import dataclass

from photosort.cloud_vision import ANTHROPIC_VISION_MODEL, MISTRAL_VISION_MODEL, TokenUsage

# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 2: die Preisquelle der IST-Kostenrechnung - eine Code-Konstante je Modell-ID,
# KEIN Settings-/env-Feld. Eine Preisaenderung ist kein Deployment-Parameter, sondern eine
# belegpflichtige Tatsachenbehauptung: sie gehoert in einen Commit mit Datum, Quelle und Review -
# nicht in eine `.env`, in der sie unbemerkt jeden historischen Betrag umdeuten koennte.
#
# ACHTUNG, ZWEI PREISKONSTANTEN (ADR 0051 Punkt 2, bewusst): `remote_classification.py::
# COST_PER_IMAGE_USD` ist die VORAB-Schaetzung (Preis pro BILD, inkl. angenommener Token-Zahlen,
# ADR 0050 Punkt 5); `MODEL_PRICING` hier ist die IST-Rechnung (Preis pro TOKEN, nach dem Lauf).
# Ein Modell-/Preiswechsel betrifft BEIDE - sie werden bewusst nicht auseinander abgeleitet
# (Begruendung: ADR 0051 Punkt 2), muessen aber gemeinsam gepflegt werden.


@dataclass(frozen=True)
class ModelPricing:
    """Listenpreis eines Modells in USD je einer Million Tokens, getrennt nach Ein- und Ausgabe.

    `float` statt `Decimal` analog zur Persistenz der Betraege (ADR 0051 Punkt 3): die Betraege
    liegen im Cent-Bereich, es findet keine Buchhaltung statt, gerundet wird erst bei der
    Ausgabe."""

    input_usd_per_mtok: float
    output_usd_per_mtok: float


_TOKENS_PER_MTOK = 1_000_000

# Schluessel ist die MODELL-ID (nicht der Provider): der Preis haengt am Modell, und die
# Modell-IDs werden bereits in cloud_vision.py zentral gefuehrt. Die Vollstaendigkeit dieser
# Tabelle gegenueber den dortigen `*_VISION_MODEL`-Konstanten ist per Invariantentest erzwungen
# (tests/test_pricing.py) - der einzige automatisierte Schutz gegen einen Modellwechsel ohne
# Preispflege.
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
MODEL_PRICING: dict[str, ModelPricing] = {
    ANTHROPIC_VISION_MODEL: ModelPricing(input_usd_per_mtok=1.00, output_usd_per_mtok=5.00),
    MISTRAL_VISION_MODEL: ModelPricing(input_usd_per_mtok=0.10, output_usd_per_mtok=0.10),
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
