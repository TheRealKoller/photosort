from __future__ import annotations

import inspect
import itertools
import math

from photosort import ranking
from photosort.ranking import RankedPhoto, rank_photos

# Deterministisches Wertegitter fuer die Monotonie-Zusage - bewusst Vielfache von 0.25, damit der
# Float-Vergleich nicht flackert.
_SCORE_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)


class TestRankPhotos:
    def test_empty_candidates_returns_empty_list(self) -> None:
        assert rank_photos({}, {"sharpness": 1.0}) == []

    def test_single_candidate_gets_rank_position_one(self) -> None:
        result = rank_photos({1: {"sharpness": 0.5}}, {"sharpness": 1.0})
        assert result == [RankedPhoto(photo_id=1, rank_score=0.5, rank_position=1)]

    def test_orders_by_weighted_score_descending(self) -> None:
        candidates = {1: {"sharpness": 0.2}, 2: {"sharpness": 0.9}}
        result = rank_photos(candidates, {"sharpness": 1.0})
        assert [r.photo_id for r in result] == [2, 1]
        assert [r.rank_position for r in result] == [1, 2]

    def test_equal_weights_average_two_criteria(self) -> None:
        candidates = {1: {"a": 1.0, "b": 0.0}}
        result = rank_photos(candidates, {"a": 1.0, "b": 1.0})
        assert result[0].rank_score == 0.5

    def test_tie_break_picks_the_lower_photo_id(self) -> None:
        candidates = {2: {"sharpness": 0.5}, 1: {"sharpness": 0.5}}
        result = rank_photos(candidates, {"sharpness": 1.0})
        assert [r.photo_id for r in result] == [1, 2]

    def test_missing_criterion_is_renormalized_not_scored_as_zero(self) -> None:
        # Kernfall der Spec: Kandidat 1 hat nur "a" (Wert 1.0), Kandidat 2 hat beide (a=1.0,
        # b=0.0) bei Gleichgewichtung. Ohne Renormierung wuerde Kandidat 1s fehlendes "b"
        # stillschweigend als 0 gewertet (Score 0.5) - MIT Renormierung zaehlt fuer Kandidat 1
        # nur das vorhandene Kriterium "a" (Score 1.0), er landet also VOR Kandidat 2.
        candidates = {1: {"a": 1.0}, 2: {"a": 1.0, "b": 0.0}}
        result = rank_photos(candidates, {"a": 1.0, "b": 1.0})
        by_id = {r.photo_id: r for r in result}
        assert by_id[1].rank_score == 1.0
        assert by_id[2].rank_score == 0.5
        assert [r.photo_id for r in result] == [1, 2]

    def test_candidate_missing_every_weighted_criterion_gets_lowest_score_but_stays_included(
        self,
    ) -> None:
        # Dokumentiertes, getestetes Verhalten (Teststrategie-Abschnitt der Spec): ein Kandidat
        # ganz ohne ein in weights genanntes Kriterium bleibt Teil der Rangfolge (kein
        # stillschweigendes Herausfallen), bekommt aber den niedrigstmoeglichen Score.
        candidates = {1: {"other_key": 1.0}, 2: {"sharpness": 0.5}}
        result = rank_photos(candidates, {"sharpness": 1.0})
        assert len(result) == 2
        by_id = {r.photo_id: r for r in result}
        assert by_id[1].rank_score == 0.0
        assert by_id[2].rank_score == 0.5
        assert [r.photo_id for r in result] == [2, 1]

    def test_unknown_criterion_key_in_weights_is_ignored(self) -> None:
        # Ein in weights genannter criterion_key, den KEIN Kandidat besitzt, wirkt sich auf
        # niemanden aus - kein Sonderfall, deckt sich strukturell mit der Renormierung.
        candidates = {1: {"sharpness": 0.5}}
        result = rank_photos(candidates, {"sharpness": 1.0, "nonexistent": 5.0})
        assert result[0].rank_score == 0.5


class TestTheMonotonicityIsBack:
    """specs/features/0427-motive-mit-staerke.md, PR 3 Schritt 1: `confidence_ordering_score` und
    `CONFIDENCE_RANK_PENALTY` entfallen mit der Modellkonfidenz je Kategorie.

    Die beiden Faelle hier sind die POSITIVE Haelfte des Abbaus - der strukturelle Waechter in
    tests/test_keine_kategoriebegriffe.py deckt nur ab, dass die Namen nicht mehr vorkommen. Sie
    halten fest, dass `rank_position` wieder monoton in `rank_score` ist: eine still
    wiedereingefuehrte Daempfung (etwa ueber eine Motivstaerke) braeche sie."""

    def test_the_signature_takes_no_third_parameter(self) -> None:
        """Ein dritter Parameter waere der Einstiegspunkt fuer eine neue Daempfung. Die
        Motivstaerken treten ausdruecklich NICHT an die Stelle der Konfidenz: sie sind eine
        Aussage ueber den Bildinhalt, keine ueber die Bildguete."""
        parameters = inspect.signature(rank_photos).parameters

        assert list(parameters) == ["candidates", "weights"]

    def test_the_module_offers_no_dampening_function_any_more(self) -> None:
        assert not hasattr(ranking, "confidence_ordering_score")
        assert not hasattr(ranking, "CONFIDENCE_RANK_PENALTY")

    def test_rank_position_is_monotonic_in_rank_score(self) -> None:
        """Ueber einem Gitter, nicht an einem Beispiel: jedes Foto mit hoeherem `rank_score` steht
        vor jedem mit niedrigerem, ohne Ausnahme."""
        candidates = {index: {"a": value} for index, value in enumerate(_SCORE_GRID, start=1)}

        result = rank_photos(candidates, {"a": 1.0})

        by_id = {entry.photo_id: entry for entry in result}
        for left, right in itertools.combinations(by_id, 2):
            if by_id[left].rank_score > by_id[right].rank_score:
                assert by_id[left].rank_position < by_id[right].rank_position
            elif by_id[left].rank_score < by_id[right].rank_score:
                assert by_id[left].rank_position > by_id[right].rank_position

    def test_a_better_rated_photo_is_never_overtaken(self) -> None:
        """Die Gegenprobe zum entfallenen Abzug: es gibt keinen Abstand mehr, den eine zweite Zahl
        ueberbruecken koennte - auch nicht den kleinsten darstellbaren."""
        candidates = {1: {"a": math.nextafter(0.5, 1.0)}, 2: {"a": 0.5}}

        result = rank_photos(candidates, {"a": 1.0})

        assert [entry.photo_id for entry in result] == [1, 2]


class TestRankingDocstrings:
    def test_rank_photos_documents_the_restored_monotonicity(self) -> None:
        """Die Monotonie ist eine ZUSAGE und steht im Docstring - wer eine Daempfung ergaenzt, muss
        hier vorbei."""
        assert "monoton" in (rank_photos.__doc__ or "").casefold()
