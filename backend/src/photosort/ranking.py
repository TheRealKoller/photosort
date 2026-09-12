from __future__ import annotations

from dataclasses import dataclass

# Reine, DB-freie Rangfolgen-Funktion, analog scoring.py::assign_clusters. Operiert auf EINER
# Partition (event_id) pro Aufruf - der Worker ruft sie je Partition auf und ergaenzt event_id
# erst beim Persistieren der PhotoRanking-Zeilen (siehe worker.py::run_criterion_scoring). Die
# konkrete Default-Gewichtung ist austauschbar.
#
# KEINE Daempfung des Sortierschluessels mehr: mit den Kategorien ist die Modellkonfidenz je
# Kategorie entfallen, und die Motivstaerken treten NICHT an ihre Stelle - sie sind eine Aussage
# ueber den Bildinhalt, keine ueber die Bildguete, und keine Schwelle macht aus einer Staerke eine
# Zugehoerigkeit. `rank_position` ist damit innerhalb einer Partition wieder monoton in
# `rank_score`.


@dataclass(frozen=True)
class RankedPhoto:
    photo_id: int
    rank_score: float
    rank_position: int


def rank_photos(
    candidates: dict[int, dict[str, float]],
    weights: dict[str, float],
) -> list[RankedPhoto]:
    """Bildet fuer jeden Kandidaten (photo_id -> {criterion_key: value}) einen gewichteten
    Rang-Score und sortiert absteigend (Tie-Break: niedrigere photo_id gewinnt, projektweite
    Determinismus-Konvention).

    `rank_position` ist innerhalb der Partition damit monoton in `rank_score` - es gibt keinen
    zweiten, gedaempften Sortierschluessel daneben.

    Fehlt einem Kandidaten eines der in `weights` genannten Kriterien (z.B. best-effort
    fehlgeschlagene Berechnung, oder ein Kriterium, das nur fuer eine Teilmenge existiert), wird
    das Gewicht auf die tatsaechlich vorhandene Teilmenge RENORMIERT, statt das fehlende Kriterium
    stillschweigend mit 0 zu werten - ein Kandidat mit nur einem von zwei gewichteten Kriterien
    wird also nicht automatisch benachteiligt, nur weil ihm ein Kriterium fehlt. Ein Kandidat, dem
    ALLE in `weights` genannten Kriterien fehlen, kann nicht sinnvoll gewichtet gemittelt werden
    (Gesamtgewicht 0) - er bleibt trotzdem im Ergebnis enthalten (kein stillschweigendes
    Herausfallen aus der Rangfolge), bekommt aber den niedrigstmoeglichen Score 0.0. Ein
    `criterion_key` in `weights`, den KEIN Kandidat besitzt, wirkt sich auf niemanden aus
    (strukturell durch dieselbe Renormierung abgedeckt, kein Sonderfall)."""
    scored: list[tuple[int, float]] = []
    for photo_id, criterion_values in candidates.items():
        applicable_weights = {
            key: weight for key, weight in weights.items() if key in criterion_values
        }
        total_weight = sum(applicable_weights.values())
        if total_weight <= 0:
            score = 0.0
        else:
            score = (
                sum(criterion_values[key] * weight for key, weight in applicable_weights.items())
                / total_weight
            )
        scored.append((photo_id, score))

    ordered = sorted(scored, key=lambda item: (-item[1], item[0]))
    return [
        RankedPhoto(photo_id=photo_id, rank_score=score, rank_position=index + 1)
        for index, (photo_id, score) in enumerate(ordered)
    ]
