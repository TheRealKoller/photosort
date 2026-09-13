from __future__ import annotations

import inspect
import itertools
import math

from photosort import ranking
from photosort.ranking import RankedPhoto, rank_photos

# Deterministisches Wertegitter fuer die Monotonie-Zusage - bewusst Vielfache von 0.25, damit der
# Float-Vergleich nicht flackert.
_SCORE_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)

# specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 8: `rank_photos` ist ab hier eine
# REINE SORTIERUNG. Gewichtung und Renormierung sind nach `quality.py` umgezogen und dort
# geprueft - diese Datei prueft nur noch Reihenfolge, Tie-Break und Monotonie.


class TestRankPhotos:
    def test_empty_candidates_returns_empty_list(self) -> None:
        assert rank_photos({}) == []

    def test_single_candidate_gets_rank_position_one(self) -> None:
        assert rank_photos({1: 0.5}) == [RankedPhoto(photo_id=1, rank_score=0.5, rank_position=1)]

    def test_orders_by_score_descending(self) -> None:
        result = rank_photos({1: 0.2, 2: 0.9})

        assert [r.photo_id for r in result] == [2, 1]
        assert [r.rank_position for r in result] == [1, 2]

    def test_tie_break_picks_the_lower_photo_id(self) -> None:
        assert [r.photo_id for r in rank_photos({2: 0.5, 1: 0.5})] == [1, 2]

    def test_the_score_is_carried_through_unchanged(self) -> None:
        """Keine Rechnung mehr in dieser Funktion: der Qualitaetswert entsteht in `quality.py` und
        wird hier nur noch sortiert. Ein `0.0` ist dabei ein GUELTIGER Wert - ein
        Falsyness-Filter verloere ihn lautlos."""
        result = rank_photos({1: 0.0, 2: 1.0})

        by_id = {entry.photo_id: entry for entry in result}
        assert by_id[1].rank_score == 0.0
        assert by_id[2].rank_score == 1.0

    def test_positions_are_gapless_from_one(self) -> None:
        """Die Rangfolge laeuft ueber die BEWERTETE Teilmenge - innerhalb ihrer bleibt
        `rank_position` lueckenlos ab 1, unabhaengig davon, wie viele Fotos der Partition gar
        keinen Wert haben."""
        result = rank_photos({7: 0.9, 8: 0.5, 9: 0.1})

        assert [entry.rank_position for entry in result] == [1, 2, 3]


class TestTheMonotonicityIsBack:
    """specs/features/0427-motive-mit-staerke.md, PR 3 Schritt 1: `confidence_ordering_score` und
    `CONFIDENCE_RANK_PENALTY` entfallen mit der Modellkonfidenz je Kategorie.

    Die Faelle hier sind die POSITIVE Haelfte des Abbaus - der strukturelle Waechter in
    tests/test_keine_kategoriebegriffe.py deckt nur ab, dass die Namen nicht mehr vorkommen. Sie
    halten fest, dass `rank_position` monoton in `rank_score` ist: eine still wiedereingefuehrte
    Daempfung (etwa ueber eine Motivstaerke) braeche sie."""

    def test_the_signature_takes_nothing_but_the_scores(self) -> None:
        """Ein zweiter Parameter waere der Einstiegspunkt fuer eine neue Daempfung ODER fuer eine
        wieder hier angesiedelte Gewichtung. Beides gehoert nicht in eine Sortierfunktion: die
        Gewichte haben seit Spec 0428 genau eine Stelle (`quality.py`)."""
        assert list(inspect.signature(rank_photos).parameters) == ["scores"]

    def test_the_module_offers_no_dampening_function_any_more(self) -> None:
        assert not hasattr(ranking, "confidence_ordering_score")
        assert not hasattr(ranking, "CONFIDENCE_RANK_PENALTY")

    def test_the_module_carries_no_weight_table_any_more(self) -> None:
        """Die Gewichte sind DIE eine benannte Stelle in `quality.py` - eine zweite hier waere
        genau die zweite Pflegestelle, die auseinanderlaeuft."""
        assert not hasattr(ranking, "DEFAULT_CRITERION_WEIGHTS")
        assert not hasattr(ranking, "QUALITY_CRITERION_WEIGHTS")

    def test_rank_position_is_monotonic_in_rank_score(self) -> None:
        """Ueber einem Gitter, nicht an einem Beispiel: jedes Foto mit hoeherem `rank_score` steht
        vor jedem mit niedrigerem, ohne Ausnahme."""
        result = rank_photos({index: value for index, value in enumerate(_SCORE_GRID, start=1)})

        by_id = {entry.photo_id: entry for entry in result}
        for left, right in itertools.combinations(by_id, 2):
            if by_id[left].rank_score > by_id[right].rank_score:
                assert by_id[left].rank_position < by_id[right].rank_position
            elif by_id[left].rank_score < by_id[right].rank_score:
                assert by_id[left].rank_position > by_id[right].rank_position

    def test_a_better_rated_photo_is_never_overtaken(self) -> None:
        """Die Gegenprobe zum entfallenen Abzug: es gibt keinen Abstand mehr, den eine zweite Zahl
        ueberbruecken koennte - auch nicht den kleinsten darstellbaren."""
        result = rank_photos({1: math.nextafter(0.5, 1.0), 2: 0.5})

        assert [entry.photo_id for entry in result] == [1, 2]


class TestRankingDocstrings:
    def test_rank_photos_documents_the_restored_monotonicity(self) -> None:
        """Die Monotonie ist eine ZUSAGE und steht im Docstring - wer eine Daempfung ergaenzt, muss
        hier vorbei."""
        assert "monoton" in (rank_photos.__doc__ or "").casefold()
