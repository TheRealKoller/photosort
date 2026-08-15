from __future__ import annotations

from photosort.ranking import RankedPhoto, rank_photos


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
