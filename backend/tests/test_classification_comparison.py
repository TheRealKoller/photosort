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
    PhotoComparison,
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
        comparison = compare_review([_photo(1, a_motifs=dict(_ZERO) | {"tiere": 0.9})], seed=1, limit=30)

        assert sum(1 for case in comparison.cases if case.purpose == "motifs") == 1
        assert sum(1 for case in comparison.cases if case.purpose == "motif_feature") == 1

    def test_a_limit_of_zero_keeps_counts_but_no_case(self) -> None:
        comparison = compare_review([_photo(1, a_motifs=dict(_ZERO) | {"tiere": 0.9})], seed=1, limit=0)

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
