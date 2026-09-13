from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# Reine, DB-freie Rangfolgen-Funktion, analog scoring.py::assign_clusters. Operiert auf EINER
# Partition (event_id) pro Aufruf - der Worker ruft sie je Partition auf und ergaenzt event_id
# erst beim Persistieren der PhotoRanking-Zeilen (siehe worker.py::run_criterion_scoring).
#
# REINE SORTIERUNG: der Qualitaetswert entsteht in `quality.py` und kommt hier fertig herein.
# Gewichte und Renormierung liegen dort an EINER Stelle; eine zweite hier waere die zweite
# Pflegestelle, die auseinanderlaeuft.
#
# KEINE Daempfung des Sortierschluessels: mit den Kategorien ist die Modellkonfidenz je Kategorie
# entfallen, und die Motivstaerken treten NICHT an ihre Stelle - sie sind eine Aussage ueber den
# Bildinhalt, keine ueber die Bildguete, und keine Schwelle macht aus einer Staerke eine
# Zugehoerigkeit. `rank_position` ist damit innerhalb einer Partition monoton in `rank_score`.


@dataclass(frozen=True)
class RankedPhoto:
    photo_id: int
    rank_score: float
    rank_position: int


def rank_photos(scores: Mapping[int, float]) -> list[RankedPhoto]:
    """Sortiert die uebergebenen Qualitaetswerte (photo_id -> Wert) absteigend und vergibt
    `rank_position` ab 1 (Tie-Break: niedrigere photo_id gewinnt, projektweite
    Determinismus-Konvention).

    `rank_position` ist innerhalb der Partition damit monoton in `rank_score` - es gibt keinen
    zweiten, gedaempften Sortierschluessel daneben.

    Uebergeben wird ausschliesslich die BEWERTETE Teilmenge einer Partition: ein Foto ohne
    Modellbewertung hat keinen Qualitaetswert und bekommt `NULL` in beiden Spalten, statt hier mit
    einem erfundenen Wert mitzulaufen. Innerhalb der uebergebenen Menge bleibt `rank_position`
    lueckenlos ab 1."""
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [
        RankedPhoto(photo_id=photo_id, rank_score=score, rank_position=index + 1)
        for index, (photo_id, score) in enumerate(ordered)
    ]
