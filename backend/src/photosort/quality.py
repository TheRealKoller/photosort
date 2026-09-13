from __future__ import annotations

from collections.abc import Mapping

from photosort.album_suitability import normalize_level

# Der Qualitätswert eines Fotos: wie brauchbar es für ein Album ist. Rein, DB-frei, netzfrei.
#
# Die Modellstufe FÜHRT, die lokalen Messungen korrigieren sie innerhalb ihrer Stufe:
#
#     Q = clamp(M + LOCAL_CORRECTION_SPAN * (2*L - 1), 0, 1)
#
# mit `M` der normierten Modellstufe und `L` dem gewichteten Mittel der VORHANDENEN lokalen
# Qualitäts-/Kompositionskriterien. Ohne ein einziges lokales Kriterium gilt `Q = M`.

# DIE eine benannte Stelle für die Gewichte des Qualitätswerts. Gleichgewichtung als
# dokumentiert-unkalibrierter Startwert - es gibt keinen Fotokorpus im Repository, gegen den eine
# andere Verteilung zu belegen wäre.
#
# In den Qualitätswert gehen AUSSCHLIESSLICH Kriterien ohne Inhaltsaussage ein: die sieben mit
# `presence_threshold` (content_people, tier, gebaeude, landschaft, fahrzeug, essen_trinken,
# landmark) fehlen hier, und `content_landscape` ebenfalls - es misst Texturarmut, und "mehr
# gleichförmige Fläche" ist keine Aussage über Bildgüte. Daraus folgt unmittelbar: zwei Fotos, die
# sich ausschließlich im Bildinhalt unterscheiden, tragen denselben Qualitätswert. Ein
# Invariantentest liest die Eigenschaft aus `criteria.py::CRITERIA_REGISTRY` und nicht aus einer
# zweiten Aufzählung (tests/test_quality.py).
#
# Motivabhängige Gewichte (Horizont bei Landschaft, Freiraum bei Porträt) bleiben möglich: beide
# Funktionen unten nehmen die Tabelle als Parameter entgegen. Welche Gewichte je Motiv gelten,
# entscheidet diese Datei nicht.
QUALITY_CRITERION_WEIGHTS: dict[str, float] = {
    "sharpness": 1.0,
    "exposure": 1.0,
    "aesthetics": 1.0,
    "goldener_schnitt": 1.0,
    "symmetrie": 1.0,
    "horizont": 1.0,
    "freiraum": 1.0,
}

# Die halbe Breite des lokalen Korrekturbandes. ZWEI Grenzen hängen daran, und die schärfere gilt:
#
# - ORDNUNG: `2 * span` muss kleiner als der Stufenabstand `0,25` sein, sonst kann ein Foto der
#   niedrigeren Modellstufe eines der höheren überholen und "die Modellstufe führt" ist aufgegeben.
#   Das ließe noch `span <= 0,125` zu.
# - ANZEIGE: die dreistufige Anzeige (`utils/qualityLevel.ts`) hat ihre Schwellen auf den
#   Stufenmitten 0,375 und 0,625. Sie ist nur dann eine deterministische Vergröberung der
#   Modellstufe (1-2 niedrig, 3 mittel, 4-5 hoch), wenn `span < 0,125` STRIKT gilt: bei exakt
#   0,125 fällt Stufe 2 mit `L = 1` genau auf 0,375 und erschiene als "mittel", während dieselbe
#   Stufe mit `L = 0` "niedrig" ist - dieselbe Modellstufe in zwei Anzeigestufen.
#
# Dokumentiert-unkalibrierter Startwert: ob 0,1 die richtige Korrekturbreite ist, ist eine
# Kalibrierungsfrage gegen einen Fotokorpus, den das Repository nach der Bilddaten-Regel nicht hat.
LOCAL_CORRECTION_SPAN = 0.1


def local_correction(values: Mapping[str, float], weights: Mapping[str, float]) -> float | None:
    """Das gewichtete Mittel der VORHANDENEN gewichteten Kriterien eines Fotos, oder `None`.

    `None` heißt "kein einziges gewichtetes Kriterium vorhanden" und ist ausdrücklich NICHT `0.0`:
    "kein lokales Signal" ist etwas anderes als "lokal schlecht", und der Unterschied entscheidet
    über `Q = M` statt `Q = M - span`.

    RENORMIERT auf die tatsächlich vorhandene Teilmenge: ein fehlendes Kriterium senkt den Wert
    nicht. Das ist die Rechenhälfte der Entscheidung "ein nicht messbares Kriterium wird
    weggelassen statt als schlechter Wert gewertet" (ADR 0093, Abschnitt 5) - ohne die
    Renormierung wäre das Weglassen dasselbe wie eine 0.

    Ein Wert außerhalb der Gewichtstabelle wird ignoriert; ein Gewicht ohne zugehörigen Wert wirkt
    sich auf niemanden aus (strukturell durch dieselbe Renormierung abgedeckt)."""
    applicable = {key: weight for key, weight in weights.items() if key in values}
    total_weight = sum(applicable.values())
    if total_weight <= 0:
        return None
    return sum(values[key] * weight for key, weight in applicable.items()) / total_weight


def compute_quality_score(
    level: int, values: Mapping[str, float], weights: Mapping[str, float]
) -> float:
    """Der Qualitätswert eines Fotos aus seiner Modellstufe und seinen lokalen Kriterien.

    `level` ist die bereits validierte Stufe `1..5` (`album_suitability.py`) - ein Foto ohne
    Modellbewertung bekommt hier gar keinen Wert, sondern `NULL` an der Schreibstelle. Es gibt
    keinen Rückfall auf einen rein lokal gebildeten Wert.

    Geklemmt auf `[0, 1]`: an den beiden Rändern der Skala zeigte das Korrekturband sonst über die
    Skala hinaus (Stufe 1 mit `L = 0` ergäbe -0,1)."""
    model_share = normalize_level(level)
    correction = local_correction(values, weights)
    if correction is None:
        return model_share
    score = model_share + LOCAL_CORRECTION_SPAN * (2.0 * correction - 1.0)
    return max(0.0, min(1.0, score))
