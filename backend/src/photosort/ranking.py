from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from photosort.categories import usable_confidence

# Reine, DB-freie Rangfolgen-Funktion, analog
# scoring.py::assign_time_clusters/classification.py's ehemaligem select_top_n_with_category_mix.
# Operiert auf EINER Partition (cluster_key x category_key) pro Aufruf - der Worker ruft sie je
# Partition auf und ergaenzt cluster_key/category_key erst beim Persistieren der PhotoRanking-
# Zeilen (siehe worker.py::run_criterion_scoring). Die konkrete Default-Gewichtung ist bewusst
# austauschbar.
#
# `usable_confidence` kommt aus categories.py und wird hier NICHT ein zweites Mal geschrieben
# (Security-Muss-Kriterium): "was gilt als Angabe" muss an beiden Lesestellen dieselbe Antwort geben
# - zwei Kopien koennten auseinanderlaufen, und genau das ist der Fehler, den die Haertung
# verhindern soll. Der Import bleibt DB-, netzwerk- und bildverarbeitungsfrei; categories.py ist
# selbst ein reines Modul und importiert nichts aus diesem hier (kein Zirkel).


# Der maximale Abzug auf den SORTIERSCHLUESSEL einer Partition - erreicht bei einer
# Selbsteinschaetzung von 0, null bei 1. Produktentscheidung Daniels: spuerbar, aber gedeckelt.
# Bewusst additiv statt multiplikativ: `rank_score` ist ein auf [0, 1] normierter gewichteter
# Mittelwert, auf dieser Skala ist ein Abstand eine Aussage, ein Faktor nicht (und ein Faktor
# bestrafte gut bewertete Fotos absolut staerker als schlecht bewertete - genau verkehrt herum).
# Nicht gegen einen echten Fotokorpus kalibriert.
CONFIDENCE_RANK_PENALTY = 0.15


@dataclass(frozen=True)
class RankedPhoto:
    photo_id: int
    rank_score: float
    rank_position: int


def confidence_ordering_score(rank_score: float, confidence: object) -> float:
    """Der gedaempfte SORTIERSCHLUESSEL eines Fotos innerhalb seiner Partition - ausdruecklich
    NICHT sein `rank_score`.

    Ohne brauchbare Zahl ist das Ergebnis der `rank_score` selbst, sonst
    `rank_score - CONFIDENCE_RANK_PENALTY * (1 - confidence)`. Der Abzug liegt damit fuer jede
    zulaessige Konfidenz in `[0, CONFIDENCE_RANK_PENALTY]`.

    Zwei Zusagen folgen daraus unmittelbar aus der Formel, ohne Zusatzpruefung im Code:

    * Liegt der `rank_score` eines Fotos um MEHR als `CONFIDENCE_RANK_PENALTY` ueber dem eines
      anderen derselben Partition, kann keine Konfidenzdifferenz die Reihenfolge der beiden
      umkehren.
    * Ein Foto ohne Angabe steht nie schlechter als ohne jede Daempfung: sein eigener Sortierwert
      bleibt unveraendert, jeder andere wird kleiner oder gleich.

    GEWOLLTE FOLGE, kein Defekt: `rank_position` ist innerhalb einer Partition damit nicht mehr
    monoton in `rank_score` - ein Foto kann mit hoeherem Rang-Score hinter einem anderen stehen.
    Wer das spaeter "repariert", nimmt der Story ihre halbe Wirkung.

    Der Ergebniswert wird NICHT persistiert: er ist ein Zwischenergebnis der Sortierung, deren
    Ergebnis daneben bereits als `rank_position` steht.

    `object` statt `float | None` als Parametertyp: der Wert stammt aus einer JSON-Spalte, deren
    Typzusage ueber die Datenbank statt ueber den Parser laeuft (siehe `usable_confidence`)."""
    number = usable_confidence(confidence)
    if number is None:
        return rank_score
    return rank_score - CONFIDENCE_RANK_PENALTY * (1.0 - number)


def rank_photos(
    candidates: dict[int, dict[str, float]],
    weights: dict[str, float],
    confidences: Mapping[int, object] | None = None,
) -> list[RankedPhoto]:
    """Bildet fuer jeden Kandidaten (photo_id -> {criterion_key: value}) einen gewichteten
    Rang-Score und sortiert absteigend (Tie-Break: niedrigere photo_id gewinnt, projektweite
    Determinismus-Konvention).

    `confidences` ist die Konfidenz je Foto ZUM SCHLUESSEL GENAU DIESER PARTITION - damit wird nie
    zwischen zwei Kategorien
    verglichen, sondern immer nur zwischen zwei Fotos derselben Kategorie. Sortiert wird dann nach
    `confidence_ordering_score`; `RankedPhoto.rank_score` bleibt der UNGEDAEMPFTE Wert und ist
    damit ueber alle Zugehoerigkeitszeilen eines Fotos identisch. `rank_position` ist es nicht: sie
    ist innerhalb einer Partition nicht mehr monoton in `rank_score` (gewollt, siehe
    `confidence_ordering_score`). Ohne den Parameter - und fuer jedes Foto ohne brauchbare Zahl -
    verhaelt sich die Funktion exakt wie bisher.

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
                sum(criterion_values[key] * weight for key, weight in applicable_weights.items())
                / total_weight
            )
        scored.append((photo_id, score))

    # Zwei Werte je Foto: der ungedaempfte `rank_score` (Rueckgabe, Persistenz, Frontend-
    # Qualitaetsstufe) und der gedaempfte Sortierschluessel (nur hier, nie persistiert).
    ordered = sorted(
        scored,
        key=lambda item: (
            -confidence_ordering_score(
                item[1], None if confidences is None else confidences.get(item[0])
            ),
            item[0],
        ),
    )
    return [
        RankedPhoto(photo_id=photo_id, rank_score=score, rank_position=index + 1)
        for index, (photo_id, score) in enumerate(ordered)
    ]
