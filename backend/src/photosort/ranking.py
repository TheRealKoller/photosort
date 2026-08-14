from __future__ import annotations

from dataclasses import dataclass

# specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md, decisions/0021-kriterien-
# datenmodell-kuratierungs-pipeline.md, Punkt 3: reine, DB-freie Rangfolgen-Funktion (analog
# scoring.py::assign_time_clusters/classification.py's ehemaligem select_top_n_with_category_mix).
# Operiert auf EINER Partition (cluster_key x category_key) pro Aufruf - der Worker ruft sie je
# Partition auf und ergaenzt cluster_key/category_key erst beim Persistieren der PhotoRanking-
# Zeilen (siehe worker.py::run_criterion_scoring). Die konkrete Default-Gewichtung ist bewusst
# austauschbar, nicht Teil dieser Spec (siehe "Out of Scope").


@dataclass(frozen=True)
class RankedPhoto:
    photo_id: int
    rank_score: float
    rank_position: int


def rank_photos(
    candidates: dict[int, dict[str, float]], weights: dict[str, float]
) -> list[RankedPhoto]:
    """Bildet fuer jeden Kandidaten (photo_id -> {criterion_key: value}) einen gewichteten
    Rang-Score und sortiert absteigend (Tie-Break: niedrigere photo_id gewinnt, Determinismus-
    Konvention aus Spec 0003/0024 fortgeführt).

    Fehlt einem Kandidaten eines der in `weights` genannten Kriterien (z.B. best-effort
    fehlgeschlagene Berechnung, oder ein Kriterium, das nur fuer eine Teilmenge existiert), wird
    das Gewicht auf die tatsaechlich vorhandene Teilmenge RENORMIERT statt das fehlende Kriterium
    stillschweigend mit 0 zu werten (Akzeptanzkriterium der Spec) - ein Kandidat mit nur einem von
    zwei gewichteten Kriterien wird also nicht automatisch benachteiligt, nur weil ihm ein
    Kriterium fehlt. Ein Kandidat, dem ALLE in `weights` genannten Kriterien fehlen, kann nicht
    sinnvoll gewichtet gemittelt werden (Gesamtgewicht 0) - er bleibt trotzdem im Ergebnis
    enthalten (kein stillschweigendes Herausfallen aus der Rangfolge), bekommt aber den
    niedrigstmoeglichen Score 0.0 (dokumentierte, getestete Entscheidung, siehe Teststrategie-
    Abschnitt der Spec: "Kandidat ganz ohne ein in weights genanntes Kriterium hat ein
    dokumentiertes, getestetes Verhalten"). Ein `criterion_key` in `weights`, den KEIN Kandidat
    besitzt, wirkt sich auf niemanden aus (structurell durch dieselbe Renormierung abgedeckt, kein
    Sonderfall)."""
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
                sum(
                    criterion_values[key] * weight
                    for key, weight in applicable_weights.items()
                )
                / total_weight
            )
        scored.append((photo_id, score))

    ordered = sorted(scored, key=lambda item: (-item[1], item[0]))
    return [
        RankedPhoto(photo_id=photo_id, rank_score=score, rank_position=index + 1)
        for index, (photo_id, score) in enumerate(ordered)
    ]
