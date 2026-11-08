"""Spec 0616 / ADR 0139 - die reine A/B-Vergleichslogik der Klassifizierungspruefung.

DB-frei: hier steht nur, wie aus zwei Aussagen je Foto Zaehlungen und Faelle werden. Die
Entscheidung, welche Zwecke ueberhaupt verglichen werden duerfen, ist eine Zeile: nur wenn BEIDE
Seiten eine Aussage haben. Und die Praesenzgrenze kommt aus `selection.motif_is_present` - eine
zweite Schwelle hier liefe beim naechsten Wechsel still auseinander.
"""

from __future__ import annotations

import pytest

from photosort.classification_comparison import (
    PURPOSES,
    Comparison,
    MotifCounts,
    PhotoComparison,
    PurposeCounts,
    compare_motifs,
    compare_review,
    motif_present,
)
from photosort.motifs import MOTIF_REGISTRY
from photosort.selection import MOTIF_PRESENCE_THRESHOLD, motif_is_present

_ZERO = {motif_key: 0.0 for motif_key in MOTIF_REGISTRY}


def _photo(
    photo_id: int,
    *,
    a_motifs: dict[str, float] | None = None,
    b_motifs: dict[str, float] | None = None,
    a_excluded_document: bool | None = None,
    b_excluded_document: bool | None = None,
    a_album_level: int | None = None,
    b_album_level: int | None = None,
) -> PhotoComparison:
    return PhotoComparison(
        photo_id=photo_id,
        a_motifs=dict(_ZERO) if a_motifs is None else a_motifs,
        b_motifs=dict(_ZERO) if b_motifs is None else b_motifs,
        a_excluded_document=a_excluded_document,
        b_excluded_document=b_excluded_document,
        a_album_level=a_album_level,
        b_album_level=b_album_level,
    )


class TestThePresenceRuleIsTheReadPathRule:
    def test_the_threshold_is_shared_with_the_read_path(self) -> None:
        """Keine zweite Zahl: genau an der Grenze kippt `motif_present` wie `motif_is_present`."""
        assert motif_present({}, "landschaft") is False
        below = {key: 0.0 for key in MOTIF_REGISTRY} | {
            "landschaft": MOTIF_PRESENCE_THRESHOLD - 0.01
        }
        at = {key: 0.0 for key in MOTIF_REGISTRY} | {"landschaft": MOTIF_PRESENCE_THRESHOLD}

        assert motif_present(below, "landschaft") is False
        assert motif_present(at, "landschaft") is True
        assert motif_present(at, "landschaft") == motif_is_present(at["landschaft"])

    def test_both_missing_and_present_below_the_threshold_are_not_present(self) -> None:
        assert motif_present({"landschaft": 0.0}, "landschaft") is False

    def test_an_unknown_key_is_not_present(self) -> None:
        assert motif_present({"unbekannt": 1.0}, "landschaft") is False


class TestCompareMotifs:
    def test_two_equal_vectors_match_in_every_motif(self) -> None:
        strengths = dict(_ZERO) | {"landschaft": 0.9, "menschen": 0.6}

        assert compare_motifs(strengths, dict(strengths)) == (len(MOTIF_REGISTRY), 0)

    def test_a_key_only_one_side_carries_counts_as_not_present_there(self) -> None:
        """Die Vereinigung der Schluessel, nicht der Schnitt: eine fehlende Aussage ist
        "nicht vorhanden" - genau so liest der Lesepfad sie."""
        assert compare_motifs({"landschaft": 0.9}, {}) == (0, 1)

    def test_a_below_threshold_value_on_one_side_is_a_deviation(self) -> None:
        a = dict(_ZERO) | {"landschaft": 0.9}
        b = dict(_ZERO) | {"landschaft": 0.49}

        assert compare_motifs(a, b) == (len(MOTIF_REGISTRY) - 1, 1)


class TestOnlyCompareWhenBothSidesHaveAStatement:
    def test_a_purpose_without_both_statements_is_not_counted_nor_a_case(self) -> None:
        comparison = compare_review(
            [
                PhotoComparison(
                    photo_id=1,
                    a_motifs=None,
                    b_motifs=None,
                    a_excluded_document=True,
                    b_excluded_document=None,
                    a_album_level=3,
                    b_album_level=None,
                )
            ],
            seed=4711,
            limit=30,
        )

        assert comparison.counts["motifs"] == (0, 0, 0)
        assert comparison.counts["motif_feature"] == (0, 0, 0)
        assert comparison.counts["excluded_document"] == (0, 0, 0)
        assert comparison.counts["album_level"] == (0, 0, 0)
        assert comparison.cases == ()

    def test_both_statements_are_counted_and_a_deviation_becomes_a_case(self) -> None:
        comparison = compare_review(
            [
                _photo(
                    1,
                    a_excluded_document=True,
                    b_excluded_document=False,
                    a_album_level=3,
                    b_album_level=4,
                )
            ],
            seed=4711,
            limit=30,
        )

        assert comparison.counts["excluded_document"] == (1, 0, 1)
        assert comparison.counts["album_level"] == (1, 0, 1)
        assert {case.purpose for case in comparison.cases} == {"excluded_document", "album_level"}


class TestTheCountingUnitPerPurpose:
    def test_motifs_counts_photos_and_motif_feature_counts_photo_motif_pairs(self) -> None:
        """Ein Foto mit drei abweichenden Motiven ist EIN Fall fuer `motifs` und DREI fuer
        `motif_feature` - die Einheit unterscheidet die beiden Zwecke."""
        a = dict(_ZERO) | {"landschaft": 0.9, "menschen": 0.9, "tiere": 0.9}
        comparison = compare_review([_photo(1, a_motifs=a)], seed=4711, limit=30)

        assert comparison.counts["motifs"] == (1, 0, 1)
        assert comparison.counts["motif_feature"] == (len(MOTIF_REGISTRY), 5, 3)
        assert [case.motif_key for case in comparison.cases if case.purpose == "motif_feature"] == [
            key for key in MOTIF_REGISTRY if key in {"landschaft", "menschen", "tiere"}
        ]

    def test_a_matching_photo_produces_no_case(self) -> None:
        comparison = compare_review([_photo(1)], seed=4711, limit=30)

        assert comparison.counts["motifs"] == (1, 1, 0)
        assert comparison.counts["motif_feature"] == (len(MOTIF_REGISTRY), len(MOTIF_REGISTRY), 0)
        assert comparison.cases == ()


class TestTheTwoCapsAreIndependent:
    def test_the_photo_cap_and_the_pair_cap_each_take_their_own_sample_size(self) -> None:
        """Sechszehn Fotos, jedes mit zwei abweichenden Motiven, Deckel 5: `motifs` legt 5 der 16
        Fotos vor, `motif_feature` 5 der 32 Paare. Kein Zweck frisst den Platz eines anderen."""
        photos = [
            _photo(
                photo_id,
                a_motifs=dict(_ZERO) | {"landschaft": 0.9, "menschen": 0.9},
            )
            for photo_id in range(1, 17)
        ]

        comparison = compare_review(photos, seed=4711, limit=5)

        assert comparison.counts["motifs"] == (16, 0, 16)
        assert comparison.counts["motif_feature"] == (16 * len(MOTIF_REGISTRY), 16 * 6, 32)
        assert sum(1 for case in comparison.cases if case.purpose == "motifs") == 5
        assert sum(1 for case in comparison.cases if case.purpose == "motif_feature") == 5

    def test_a_limit_beyond_the_deviations_keeps_all_of_them(self) -> None:
        comparison = compare_review(
            [_photo(1, a_motifs=dict(_ZERO) | {"tiere": 0.9})], seed=1, limit=30
        )

        assert sum(1 for case in comparison.cases if case.purpose == "motifs") == 1
        assert sum(1 for case in comparison.cases if case.purpose == "motif_feature") == 1

    def test_a_limit_of_zero_keeps_counts_but_no_case(self) -> None:
        comparison = compare_review(
            [_photo(1, a_motifs=dict(_ZERO) | {"tiere": 0.9})], seed=1, limit=0
        )

        assert comparison.counts["motifs"] == (1, 0, 1)
        assert comparison.cases == ()


class TestTheSampleIsSeededAndSorted:
    def _photos(self) -> list[PhotoComparison]:
        return [
            _photo(photo_id, a_motifs=dict(_ZERO) | {"landschaft": 0.9})
            for photo_id in range(1, 21)
        ]

    def test_the_same_seed_chooses_the_same_cases(self) -> None:
        first = compare_review(self._photos(), seed=4711, limit=4)
        second = compare_review(self._photos(), seed=4711, limit=4)

        assert first.cases == second.cases

    def test_a_different_seed_chooses_different_cases(self) -> None:
        first = compare_review(self._photos(), seed=4711, limit=4)
        second = compare_review(self._photos(), seed=4712, limit=4)

        assert first.cases != second.cases

    def test_the_selection_does_not_depend_on_the_input_order(self) -> None:
        """Gleicher Seed und gleiche Abweichungsliste ergeben dieselbe Auswahl, unabhaengig von
        der Reihenfolge der Zeilen: `rng.sample` zieht POSITIONEN, deshalb muss die
        Kandidatenliste je Zweck vor dem Ziehen in fester Ordnung stehen."""
        photos = self._photos()

        forward = compare_review(photos, seed=4711, limit=4)
        backward = compare_review(list(reversed(photos)), seed=4711, limit=4)

        assert forward.cases == backward.cases
        assert forward.counts == backward.counts

    def test_the_cases_are_sorted_by_photo_then_purpose_then_motif(self) -> None:
        photos = [
            _photo(
                2,
                a_motifs=dict(_ZERO) | {"tiere": 0.9, "landschaft": 0.9},
                a_excluded_document=True,
                b_excluded_document=False,
            ),
            _photo(1, a_motifs=dict(_ZERO) | {"landschaft": 0.9}),
        ]

        comparison = compare_review(photos, seed=4711, limit=30)

        order = [
            (case.photo_id, PURPOSES.index(case.purpose), case.motif_key or "")
            for case in comparison.cases
        ]
        assert order == sorted(
            order,
            key=lambda entry: (
                entry[0],
                entry[1],
                list(MOTIF_REGISTRY).index(entry[2]) if entry[2] else -1,
            ),
        )
        assert [case.photo_id for case in comparison.cases] == sorted(
            case.photo_id for case in comparison.cases
        )
        assert [case.purpose for case in comparison.cases if case.photo_id == 2][0] == "motifs"
        assert [
            case.motif_key for case in comparison.cases if case.purpose == "motif_feature"
        ] == sorted(
            [case.motif_key for case in comparison.cases if case.purpose == "motif_feature"],
            key=lambda key: list(MOTIF_REGISTRY).index(key or ""),
        )


class TestTheComparisonCarriesBothRawValues:
    def test_each_case_carries_the_raw_values_of_its_purpose(self) -> None:
        photo = _photo(
            1,
            a_motifs=dict(_ZERO) | {"landschaft": 0.9},
            a_excluded_document=True,
            b_excluded_document=False,
            a_album_level=3,
            b_album_level=4,
        )

        comparison = compare_review([photo], seed=1, limit=30)
        by_purpose = {case.purpose: case for case in comparison.cases}

        assert by_purpose["motifs"].a_strength is None
        assert by_purpose["motif_feature"].a_strength == pytest.approx(0.9)
        assert by_purpose["motif_feature"].b_strength == pytest.approx(0.0)
        assert by_purpose["excluded_document"].a_excluded_document is True
        assert by_purpose["excluded_document"].b_excluded_document is False
        assert by_purpose["album_level"].a_album_level == 3
        assert by_purpose["album_level"].b_album_level == 4

    def test_the_result_is_a_comparison(self) -> None:
        comparison = compare_review([_photo(1)], seed=1, limit=30)

        assert isinstance(comparison, Comparison)
        assert comparison.photos_compared == 1


class TestThePurposeList:
    def test_the_purposes_are_the_four_documented_ones_in_that_order(self) -> None:
        assert PURPOSES == ("motifs", "motif_feature", "excluded_document", "album_level")


class TestTheDirectionOfAMotifDeviation:
    """`a_only`/`b_only` machen die Richtung einer Merkmalsabweichung lesbar - `deviating` allein
    ist richtungslos (ADR 0141 Punkt 6). Die Richtung entsteht im selben Durchlauf wie
    `motif_units`, aus derselben Praesenzregel."""

    def test_the_direction_names_the_side_that_alone_sees_the_motif(self) -> None:
        a = dict(_ZERO) | {"landschaft": 0.9, "menschen": 0.9}
        b = dict(_ZERO) | {"menschen": 0.9, "tiere": 0.9}

        comparison = compare_review([_photo(1, a_motifs=a, b_motifs=b)], seed=4711, limit=30)

        assert comparison.motif_counts["landschaft"].a_only == 1
        assert comparison.motif_counts["landschaft"].b_only == 0
        assert comparison.motif_counts["tiere"].a_only == 0
        assert comparison.motif_counts["tiere"].b_only == 1
        assert comparison.motif_counts["menschen"].a_only == 0
        assert comparison.motif_counts["menschen"].b_only == 0

    def test_the_two_directions_add_up_to_the_deviations(self) -> None:
        photos = [
            _photo(1, a_motifs=dict(_ZERO) | {"landschaft": 0.9}),
            _photo(2, b_motifs=dict(_ZERO) | {"landschaft": 0.9}),
            _photo(3, a_motifs=dict(_ZERO) | {"landschaft": 0.9, "tiere": 0.9}),
        ]

        comparison = compare_review(photos, seed=4711, limit=30)

        for motif_key in MOTIF_REGISTRY:
            counts = comparison.motif_counts[motif_key]
            assert counts.a_only + counts.b_only == counts.deviating, motif_key
            assert counts.matching + counts.deviating == counts.compared, motif_key

    def test_a_matching_pair_has_no_direction(self) -> None:
        comparison = compare_review([_photo(1)], seed=4711, limit=30)

        for motif_key in MOTIF_REGISTRY:
            counts = comparison.motif_counts[motif_key]
            assert (counts.a_only, counts.b_only) == (0, 0), motif_key
            assert counts.matching == counts.compared, motif_key

    def test_two_below_threshold_values_on_both_sides_leave_no_direction(self) -> None:
        """Unter der Schwelle heisst "nicht vorhanden" - auch wenn beide Seiten verschiedene
        kleine Werte tragen, gibt es keine Abweichung."""
        a = dict(_ZERO) | {"landschaft": MOTIF_PRESENCE_THRESHOLD - 0.1}
        b = dict(_ZERO) | {"landschaft": MOTIF_PRESENCE_THRESHOLD - 0.2}

        comparison = compare_review([_photo(1, a_motifs=a, b_motifs=b)], seed=4711, limit=30)
        counts = comparison.motif_counts["landschaft"]

        assert counts.compared == 1
        assert counts.matching == 1
        assert (counts.deviating, counts.a_only, counts.b_only) == (0, 0, 0)

    def test_the_threshold_edge_decides_the_direction(self) -> None:
        at = dict(_ZERO) | {"landschaft": MOTIF_PRESENCE_THRESHOLD}
        below = dict(_ZERO) | {"landschaft": MOTIF_PRESENCE_THRESHOLD - 0.0001}

        a_side = compare_review([_photo(1, a_motifs=at, b_motifs=below)], seed=4711, limit=30)
        b_side = compare_review([_photo(1, a_motifs=below, b_motifs=at)], seed=4711, limit=30)
        a_counts = a_side.motif_counts["landschaft"]
        b_counts = b_side.motif_counts["landschaft"]

        assert (a_counts.a_only, a_counts.b_only) == (1, 0)
        assert (b_counts.a_only, b_counts.b_only) == (0, 1)

    def test_a_motif_key_on_one_side_only_counts_as_that_side(self) -> None:
        without_tiere = dict(_ZERO)
        del without_tiere["tiere"]
        present = dict(_ZERO) | {"tiere": 0.9}

        b_side = compare_review(
            [_photo(1, a_motifs=without_tiere, b_motifs=present)], seed=4711, limit=30
        )
        a_side = compare_review(
            [_photo(1, a_motifs=present, b_motifs=without_tiere)], seed=4711, limit=30
        )
        b_counts = b_side.motif_counts["tiere"]
        a_counts = a_side.motif_counts["tiere"]

        assert (b_counts.a_only, b_counts.b_only) == (0, 1)
        assert (a_counts.a_only, a_counts.b_only) == (1, 0)

    def test_the_purpose_counts_keep_their_three_fields(self) -> None:
        """`PurposeCounts` ist die Form von `counts_by_purpose` und bleibt unangetastet."""
        assert PurposeCounts._fields == ("compared", "matching", "deviating")
        assert MotifCounts._fields == ("compared", "matching", "deviating", "a_only", "b_only")
