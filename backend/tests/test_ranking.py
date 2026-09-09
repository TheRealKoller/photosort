from __future__ import annotations

import itertools

import pytest

from photosort.ranking import (
    CONFIDENCE_RANK_PENALTY,
    RankedPhoto,
    confidence_ordering_score,
    rank_photos,
)

# Deterministisches Wertegitter fuer die Dominanz-Zusage (Teststrategie der Spec 0300) - bewusst
# Vielfache von 0.25, damit der Float-Vergleich nicht flackert.
_CONFIDENCE_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)


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


class TestConfidenceOrderingScore:
    """specs/features/0300-nebenkategorien.md, Umsetzungsschritt 2 / ADR 0069 Punkt 5: die
    Konfidenz daempft den SORTIERSCHLUESSEL, nie den `rank_score`."""

    def test_without_a_number_the_score_is_returned_unchanged(self) -> None:
        """Akzeptanzkriterium 10: ein Foto ohne Angabe wird nicht gedaempft."""
        assert confidence_ordering_score(0.5, None) == 0.5

    def test_full_confidence_costs_exactly_nothing(self) -> None:
        assert confidence_ordering_score(0.5, 1.0) == 0.5

    def test_zero_confidence_costs_exactly_the_constant(self) -> None:
        assert confidence_ordering_score(0.5, 0.0) == pytest.approx(0.5 - CONFIDENCE_RANK_PENALTY)

    def test_half_confidence_costs_half_the_constant(self) -> None:
        assert confidence_ordering_score(0.5, 0.5) == pytest.approx(
            0.5 - CONFIDENCE_RANK_PENALTY / 2
        )

    @pytest.mark.parametrize(
        "degenerate", ["0.9", True, 2.0, -0.1, float("nan"), float("inf"), [0.9]]
    )
    def test_a_degenerate_persisted_value_does_not_dampen(self, degenerate: object) -> None:
        """Lesepfad-Haertung, Security-Muss-Kriterium 2 der Spec: dieselbe Behandlung wie in
        `secondary_categories` - ein entarteter Wert gilt als "keine Angabe" (`None`, keine
        Daempfung), NIE als `0.0` (volle Daempfung).

        `NaN` ist der Grund, warum das nicht optional ist: als Sortierschluessel wirft es in Python
        keinen Fehler, sondern macht jeden Vergleich `False` und erzeugt eine still falsche, von
        der Eingabereihenfolge abhaengige Ordnung."""
        assert confidence_ordering_score(0.5, degenerate) == 0.5

    def test_the_literal_penalty_value_is_pinned(self) -> None:
        """GENAU EIN Test pinnt den literalen Wert (Teststrategie der Spec) - eine Wertaenderung
        ist damit eine sichtbare Handlung. Produktentscheidung Daniels: spuerbar, aber gedeckelt."""
        assert CONFIDENCE_RANK_PENALTY == 0.15


class TestRankPhotosWithConfidences:
    """Die Gewichtung der Rangfolge INNERHALB einer Partition (ADR 0069 Punkt 4/5)."""

    def test_the_parameter_is_optional_and_absent_behaves_exactly_as_before(self) -> None:
        candidates = {1: {"a": 0.25}, 2: {"a": 0.75}}
        assert rank_photos(candidates, {"a": 1.0}) == rank_photos(
            candidates, {"a": 1.0}, confidences=None
        )

    def test_an_empty_confidence_mapping_dampens_nothing(self) -> None:
        candidates = {1: {"a": 0.25}, 2: {"a": 0.75}}
        assert rank_photos(candidates, {"a": 1.0}, confidences={}) == rank_photos(
            candidates, {"a": 1.0}
        )

    def test_the_returned_rank_score_stays_undampened(self) -> None:
        """ADR 0069 Punkt 4: `rank_score` traegt im Frontend die grobe Qualitaets-Einordnung -
        gedaempft haette dasselbe Foto in zwei Kategorien zwei verschiedene "Bildqualitaeten"."""
        result = rank_photos({1: {"a": 0.5}}, {"a": 1.0}, confidences={1: 0.0})
        assert result == [RankedPhoto(photo_id=1, rank_score=0.5, rank_position=1)]

    def test_a_low_confidence_moves_a_photo_behind_a_barely_better_rated_one(self) -> None:
        """Akzeptanzkriterium 21: `rank_position` ist innerhalb einer Partition NICHT mehr monoton
        in `rank_score` - genau das ist die halbe Wirkung dieser Story, kein Defekt.

        Exakt darstellbare Werte (Vielfache von 0.125), damit der Vergleich nicht flackert."""
        candidates = {1: {"a": 0.5}, 2: {"a": 0.375}}
        result = rank_photos(candidates, {"a": 1.0}, confidences={1: 0.0, 2: 1.0})
        assert [r.photo_id for r in result] == [2, 1]
        assert [r.rank_score for r in result] == [0.375, 0.5]

    def test_the_tie_break_on_equal_damped_values_still_picks_the_lower_photo_id(self) -> None:
        candidates = {2: {"a": 0.5}, 1: {"a": 0.5}}
        result = rank_photos(candidates, {"a": 1.0}, confidences={1: 0.75, 2: 0.75})
        assert [r.photo_id for r in result] == [1, 2]

    @pytest.mark.parametrize(
        ("confidence_better", "confidence_worse"),
        list(itertools.product(_CONFIDENCE_GRID, repeat=2)),
    )
    def test_a_clearly_better_photo_is_never_overtaken(
        self, confidence_better: float, confidence_worse: float
    ) -> None:
        """Akzeptanzkriterium 8, die bezifferte Zusage: liegt der `rank_score` eines Fotos um MEHR
        als `CONFIDENCE_RANK_PENALTY` ueber dem eines anderen derselben Partition, kehrt keine
        Kombination zulaessiger Konfidenzen die Reihenfolge der beiden um."""
        worse_score = 0.25
        better_score = worse_score + CONFIDENCE_RANK_PENALTY + 0.05
        candidates = {1: {"a": better_score}, 2: {"a": worse_score}}

        result = rank_photos(
            candidates, {"a": 1.0}, confidences={1: confidence_better, 2: confidence_worse}
        )
        assert [r.photo_id for r in result] == [1, 2]

    def test_just_below_the_constant_the_order_does_reverse(self) -> None:
        """Die GEGENPROBE zum Dominanztest darueber (Teststrategie der Spec): ohne sie waere jener
        Test auch bei einer Konstante von 0 gruen - die Zusage waere dann nachweislich leer."""
        worse_score = 0.25
        better_score = worse_score + CONFIDENCE_RANK_PENALTY - 0.05
        candidates = {1: {"a": better_score}, 2: {"a": worse_score}}

        result = rank_photos(candidates, {"a": 1.0}, confidences={1: 0.0, 2: 1.0})
        assert [r.photo_id for r in result] == [2, 1]

    def test_a_photo_without_a_number_is_never_ranked_worse_than_without_any_dampening(
        self,
    ) -> None:
        """Akzeptanzkriterium 10 als PAARWEISER Vergleich zweier Aufrufe derselben Funktion: der
        eigene Sortierwert bleibt unveraendert, jeder andere wird kleiner oder gleich - die
        Position kann deshalb nur gleich bleiben oder besser werden, nie schlechter."""
        candidates = {1: {"a": 0.5}, 2: {"a": 0.625}, 3: {"a": 0.75}}
        undampened = rank_photos(candidates, {"a": 1.0})
        dampened = rank_photos(candidates, {"a": 1.0}, confidences={2: 0.0, 3: 0.25})

        position_before = {r.photo_id: r.rank_position for r in undampened}
        position_after = {r.photo_id: r.rank_position for r in dampened}
        assert position_after[1] <= position_before[1]

    def test_a_photo_id_without_an_entry_in_the_mapping_is_not_dampened(self) -> None:
        candidates = {1: {"a": 0.5}, 2: {"a": 0.5}}
        result = rank_photos(candidates, {"a": 1.0}, confidences={2: 0.0})
        assert [r.photo_id for r in result] == [1, 2]

    def test_an_explicit_none_in_the_mapping_is_not_dampened(self) -> None:
        """`Mapping[int, ...]` mit `None`-Werten ist der Regelfall aus dem Schreibpfad: die
        Hauptzeile eines uebersteuerten Fotos traegt ausdruecklich `None`
        (Akzeptanzkriterium 22)."""
        candidates = {1: {"a": 0.5}, 2: {"a": 0.5}}
        result = rank_photos(candidates, {"a": 1.0}, confidences={1: None, 2: 0.0})
        assert [r.photo_id for r in result] == [1, 2]


class TestRankingDocstrings:
    """Akzeptanzkriterium 21: die fehlende Monotonie ist eine gewollte Eigenschaft und steht in den
    Docstrings - wer sie spaeter als Defekt liest und "repariert", nimmt der Story ihre halbe
    Wirkung."""

    def test_rank_photos_documents_the_lost_monotonicity(self) -> None:
        docstring = rank_photos.__doc__ or ""
        assert "monoton" in docstring.casefold()

    def test_confidence_ordering_score_documents_the_lost_monotonicity(self) -> None:
        docstring = confidence_ordering_score.__doc__ or ""
        assert "monoton" in docstring.casefold()
