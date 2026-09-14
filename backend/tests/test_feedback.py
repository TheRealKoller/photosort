"""Die reine Auswertung des Ereignis-Logs (`feedback.py`, Spec 0432, ADR 0100).

DAS VERFAHREN HAT DREI WEGE IN SEINEN ENTARTETEN FALL, nicht einen, und jeder bekommt hier
seinen eigenen Fall: keine Paare; Paare mit durchgehendem Gleichstand; und ein entartetes
Kriterium neben einem nicht entarteten in DERSELBEN Ableitung. Ein Schutz der Form
`if not pairs: return baseline` besteht den ersten und wirft im zweiten; ein je Ableitung statt je
Kriterium gezogener Fruehausstieg besteht die ersten beiden und liefert im dritten stillschweigend
ueberall den Startwert.

DER INVARIANTENHELFER `_assert_invariants` steht als Nachsatz JEDES Ableitungsfalls: Die drei
Zusagen (strikt positiv, innerhalb der Bandbreite, Schluesselsatz exakt der Startwertsatz) gelten
fuer jede Eingabe und nicht nur fuer die, fuer die jemand eine eigene Assertion geschrieben hat.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from photosort.feedback import (
    FEEDBACK_WEIGHT_SPAN,
    MOTIF_ABSENT_THRESHOLD,
    PRIOR_STRENGTH,
    CriterionAgreement,
    ExchangeKind,
    ExchangeRecord,
    ExchangeStats,
    FinalDecisionRecord,
    MotifCorrectionRecord,
    MotifErrorCase,
    PreferencePair,
    classify_exchange,
    classify_motif_error,
    count_motif_errors,
    criterion_agreement,
    derive_weights,
    final_decision_pairs,
    preferred_lower_rated,
    summarize_exchanges,
)
from photosort.quality import QUALITY_CRITERION_WEIGHTS
from photosort.selection import MOTIF_PRESENCE_THRESHOLD

# Die Startwerttabelle wird UEBERGEBEN und nicht aus der Modulkonstante gelesen (Teststrategie):
# Sonst waere "ein Kriterium kommt spaeter hinzu" nur per `monkeypatch` erreichbar.
_BASELINE: dict[str, float] = {"sharpness": 1.0, "exposure": 2.0, "aesthetics": 0.5}


def _pair(
    preferred: Mapping[str, float], rejected: Mapping[str, float], weight: float = 1.0
) -> PreferencePair:
    return PreferencePair(preferred=dict(preferred), rejected=dict(rejected), weight=weight)


def _assert_invariants(derived: Mapping[str, float], baseline: Mapping[str, float]) -> None:
    """Die drei Zusagen der Ableitung, als Nachsatz jedes Falls.

    `strikt groesser als 0` ist nicht dasselbe wie `>= 0`: Ein Gewicht null liesse das Kriterium
    aus der Renormierung in `local_correction` ganz herausfallen, und das ist etwas anderes als
    abgewertet."""
    assert set(derived) == set(baseline)
    for key, weight in derived.items():
        assert weight > 0.0, key
        assert abs(weight - baseline[key]) < FEEDBACK_WEIGHT_SPAN * baseline[key], key


class TestTheConstantsStayWhereTheyWere:
    """Je Konstante ein Literal UND eine Ungleichung: Das Literal haelt den Wert fest, die
    Ungleichung die Aussage, die an ihm haengt."""

    def test_the_absent_threshold_is_pinned(self) -> None:
        assert MOTIF_ABSENT_THRESHOLD == 0.2

    def test_the_absent_threshold_lies_strictly_below_the_presence_threshold(self) -> None:
        """Sonst gaebe es kein Band "genannt, aber zu schwach" - die beiden Fehlerfaelle
        `missing` und `too_weak` fielen zu einem zusammen, ohne dass eine Fallunterscheidung
        verschwaende."""
        assert 0.0 < MOTIF_ABSENT_THRESHOLD < MOTIF_PRESENCE_THRESHOLD

    def test_the_weight_span_is_pinned(self) -> None:
        assert FEEDBACK_WEIGHT_SPAN == 0.3

    def test_the_weight_span_stays_strictly_below_one(self) -> None:
        """Bei `>= 1` erreichte ein durchgaengig widersprochenes Kriterium das Gewicht null oder
        ein negatives - das Kriterium waere ausgeschaltet bzw. invertiert statt abgewertet."""
        assert 0.0 < FEEDBACK_WEIGHT_SPAN < 1.0

    def test_the_prior_strength_is_pinned(self) -> None:
        assert PRIOR_STRENGTH == 10.0

    def test_the_prior_strength_is_strictly_positive(self) -> None:
        """Bei `0` entfiele die Schrumpfung, und die erste einzelne Stimme schluege mit der
        vollen Bandbreite durch; bei einem negativen Wert wechselte der Faktor bei
        `n = -PRIOR_STRENGTH` sein Vorzeichen."""
        assert PRIOR_STRENGTH > 0.0


class TestTheMotifErrorClassification:
    """Drei Fehlerfaelle und ihre Nicht-Faelle. Die Praesenzgrenze kommt ueber
    `selection.py::motif_is_present`, nie als Zahl - dass sie hier nirgends steht, haelt der
    baumweite Waechter in `test_selection.py` fest."""

    def test_an_added_motif_the_model_never_named_is_missing(self) -> None:
        assert classify_motif_error("motif_added", None) is MotifErrorCase.MISSING

    def test_an_added_motif_far_below_the_absent_threshold_is_missing(self) -> None:
        assert (
            classify_motif_error("motif_added", MOTIF_ABSENT_THRESHOLD / 2)
            is MotifErrorCase.MISSING
        )

    def test_an_added_motif_between_the_two_thresholds_is_too_weak(self) -> None:
        strength = (MOTIF_ABSENT_THRESHOLD + MOTIF_PRESENCE_THRESHOLD) / 2

        assert classify_motif_error("motif_added", strength) is MotifErrorCase.TOO_WEAK

    def test_the_absent_threshold_itself_counts_as_named(self) -> None:
        """INKLUSIV gegen `too_weak`: Der Wert AN der Grenze ist genannt, nur zu schwach. Ein
        spaeteres `<=` machte daraus stillschweigend `missing`."""
        assert classify_motif_error("motif_added", MOTIF_ABSENT_THRESHOLD) is (
            MotifErrorCase.TOO_WEAK
        )

    def test_an_added_motif_the_model_already_carries_is_no_error(self) -> None:
        assert classify_motif_error("motif_added", MOTIF_PRESENCE_THRESHOLD) is None

    def test_a_dropped_motif_the_model_carried_is_overcalled(self) -> None:
        assert classify_motif_error("motif_dropped", 0.9) is MotifErrorCase.OVERCALLED

    def test_a_dropped_motif_the_model_did_not_carry_is_no_error(self) -> None:
        """Der Nutzer nimmt ein Motiv weg, das das Modell ohnehin nicht behauptet hat - das ist
        die Ruecknahme einer fremden Korrektur, keine Modellaussage."""
        assert classify_motif_error("motif_dropped", MOTIF_ABSENT_THRESHOLD / 2) is None

    def test_a_dropped_motif_without_a_stored_strength_is_no_error(self) -> None:
        assert classify_motif_error("motif_dropped", None) is None

    def test_a_withdrawn_correction_is_never_an_error(self) -> None:
        """Eine Ruecknahme sagt nichts ueber das Modell - sie sagt etwas ueber die vorige
        Korrektur. Geprueft ueber die ganze Staerkeskala, damit kein einzelner Wert durchfaellt."""
        for strength in (None, 0.0, MOTIF_ABSENT_THRESHOLD, MOTIF_PRESENCE_THRESHOLD, 1.0):
            assert classify_motif_error("motif_correction_withdrawn", strength) is None

    @pytest.mark.parametrize(
        "kind",
        ["photo_included", "photo_removed", "decision_withdrawn", "exchanged"],
    )
    def test_no_other_kind_produces_a_motif_error(self, kind: str) -> None:
        assert classify_motif_error(kind, 0.9) is None


class TestTheExchangeClassification:
    def test_two_photos_of_the_same_level_are_within_level(self) -> None:
        assert classify_exchange(3, 3) is ExchangeKind.WITHIN_LEVEL

    def test_two_photos_of_different_levels_are_across_level(self) -> None:
        assert classify_exchange(4, 2) is ExchangeKind.ACROSS_LEVEL

    @pytest.mark.parametrize(("level", "replaced"), [(None, 3), (3, None), (None, None)])
    def test_a_missing_level_makes_the_pair_undetermined(
        self, level: int | None, replaced: int | None
    ) -> None:
        """`undetermined` ist eine eigene ausgewiesene Klasse, KEIN Restposten: Sie wird keiner
        der beiden anderen zugeschlagen (D3)."""
        assert classify_exchange(level, replaced) is ExchangeKind.UNDETERMINED

    def test_the_three_classes_are_disjoint_and_exhaustive(self) -> None:
        """Ueber einer Stichprobe aller Stufen samt `None`: jede Eingabe faellt in genau eine
        Klasse, und jede Klasse kommt vor."""
        levels: list[int | None] = [None, 1, 2, 3, 4, 5]
        seen = {classify_exchange(a, b) for a in levels for b in levels}

        assert seen == set(ExchangeKind)


class TestTheMotifErrorTally:
    def test_every_case_appears_even_without_a_single_correction(self) -> None:
        """Ein Eintrag je Fall, auch bei null - sonst muesste jeder Leser der Zahlen ihre
        Abwesenheit als Null deuten, und der Leerzustand ist etwas anderes als "0 Fehler"."""
        assert count_motif_errors([]) == dict.fromkeys(MotifErrorCase, 0)

    def test_each_correction_lands_in_its_own_case(self) -> None:
        corrections = [
            MotifCorrectionRecord("motif_added", None),
            MotifCorrectionRecord("motif_added", MOTIF_ABSENT_THRESHOLD / 2),
            MotifCorrectionRecord("motif_added", MOTIF_ABSENT_THRESHOLD),
            MotifCorrectionRecord("motif_dropped", 0.9),
        ]

        assert count_motif_errors(corrections) == {
            MotifErrorCase.MISSING: 2,
            MotifErrorCase.TOO_WEAK: 1,
            MotifErrorCase.OVERCALLED: 1,
        }

    def test_corrections_without_a_model_error_are_counted_nowhere(self) -> None:
        """Sie sind kein Restposten und keine vierte Klasse: Sie zaehlen schlicht nicht mit."""
        corrections = [
            MotifCorrectionRecord("motif_added", MOTIF_PRESENCE_THRESHOLD),
            MotifCorrectionRecord("motif_dropped", None),
            MotifCorrectionRecord("motif_correction_withdrawn", 0.9),
        ]

        assert count_motif_errors(corrections) == dict.fromkeys(MotifErrorCase, 0)


class TestTheExchangeTally:
    def _record(
        self,
        *,
        level: int | None = 3,
        replaced_level: int | None = 3,
        quality: float | None = 0.4,
        replaced_quality: float | None = 0.8,
    ) -> ExchangeRecord:
        return ExchangeRecord(
            level=level,
            replaced_level=replaced_level,
            quality=quality,
            replaced_quality=replaced_quality,
        )

    def test_every_kind_appears_even_without_a_single_exchange(self) -> None:
        assert summarize_exchanges([]) == dict.fromkeys(ExchangeKind, ExchangeStats())

    def test_the_three_classes_are_disjoint_and_exhaustive(self) -> None:
        """Ihre Summe IST die Gesamtzahl der Austausch-Ereignisse (D3) - hier als Assertion und
        nicht als ausgewiesene Zahl: Die drei stehen nirgends summiert nebeneinander."""
        records = [
            self._record(level=3, replaced_level=3),
            self._record(level=4, replaced_level=2),
            self._record(level=None, replaced_level=2),
            self._record(level=3, replaced_level=None),
        ]

        result = summarize_exchanges(records)

        assert [result[kind].count for kind in ExchangeKind] == [1, 1, 2]
        assert sum(stats.count for stats in result.values()) == len(records)

    def test_a_pulled_in_photo_with_the_lower_frozen_quality_is_counted(self) -> None:
        result = summarize_exchanges([self._record(quality=0.4, replaced_quality=0.8)])

        assert result[ExchangeKind.WITHIN_LEVEL] == ExchangeStats(
            count=1, preferred_lower_rated_count=1, quality_incomparable_count=0
        )

    def test_a_pulled_in_photo_with_the_higher_frozen_quality_is_not_counted(self) -> None:
        result = summarize_exchanges([self._record(quality=0.8, replaced_quality=0.4)])

        assert result[ExchangeKind.WITHIN_LEVEL] == ExchangeStats(
            count=1, preferred_lower_rated_count=0, quality_incomparable_count=0
        )

    @pytest.mark.parametrize(
        ("quality", "replaced_quality"), [(0.5, 0.5), (None, 0.5), (0.5, None), (None, None)]
    )
    def test_a_tie_or_a_missing_value_forms_its_own_number(
        self, quality: float | None, replaced_quality: float | None
    ) -> None:
        """Weder der einen noch der anderen Seite zugeschlagen (D4)."""
        result = summarize_exchanges(
            [self._record(quality=quality, replaced_quality=replaced_quality)]
        )

        assert result[ExchangeKind.WITHIN_LEVEL] == ExchangeStats(
            count=1, preferred_lower_rated_count=0, quality_incomparable_count=1
        )

    def test_the_quality_comparison_is_kept_per_exchange_kind(self) -> None:
        """JE TAUSCHART GETRENNT GEFUEHRT, nie summiert: Eine Gesamtzahl ueber alle drei mischte
        die Aussage ueber die lokalen Kriterien mit der ueber die Modellstufe."""
        result = summarize_exchanges(
            [
                self._record(level=3, replaced_level=3, quality=0.1, replaced_quality=0.9),
                self._record(level=5, replaced_level=1, quality=0.1, replaced_quality=0.9),
            ]
        )

        assert result[ExchangeKind.WITHIN_LEVEL].preferred_lower_rated_count == 1
        assert result[ExchangeKind.ACROSS_LEVEL].preferred_lower_rated_count == 1


class TestThePreferenceOverTheFrozenQuality:
    def test_a_lower_rated_photo_pulled_in_is_true(self) -> None:
        assert preferred_lower_rated(0.4, 0.8) is True

    def test_a_higher_rated_photo_pulled_in_is_false(self) -> None:
        assert preferred_lower_rated(0.8, 0.4) is False

    def test_an_exact_tie_is_neither(self) -> None:
        """Ein Gleichstand wird KEINER der beiden Seiten zugeschlagen und als eigene Zahl
        ausgewiesen (D4) - `False` hiesse hier "ein besseres Bild vorgezogen"."""
        assert preferred_lower_rated(0.5, 0.5) is None

    @pytest.mark.parametrize(("quality", "replaced"), [(None, 0.5), (0.5, None), (None, None)])
    def test_a_missing_value_is_neither(
        self, quality: float | None, replaced: float | None
    ) -> None:
        assert preferred_lower_rated(quality, replaced) is None


class TestTheCriterionAgreement:
    def test_a_criterion_that_always_agrees_reaches_full_agreement(self) -> None:
        pairs = [_pair({"sharpness": 0.9}, {"sharpness": 0.1}) for _ in range(3)]

        result = criterion_agreement(pairs, _BASELINE)

        assert result["sharpness"] == CriterionAgreement(case_count=3, votes=3.0, agreement=1.0)

    def test_a_criterion_that_always_disagrees_reaches_full_rejection(self) -> None:
        pairs = [_pair({"sharpness": 0.1}, {"sharpness": 0.9}) for _ in range(3)]

        result = criterion_agreement(pairs, _BASELINE)

        assert result["sharpness"] == CriterionAgreement(case_count=3, votes=3.0, agreement=-1.0)

    def test_only_signs_are_compared_never_magnitudes(self) -> None:
        """Ein Kriterium mit gestauchtem Wertebereich darf nicht benachteiligt werden: Der
        winzige Abstand zaehlt genauso viel wie der grosse."""
        tiny = criterion_agreement([_pair({"a": 0.5001}, {"a": 0.5})], {"a": 1.0})
        huge = criterion_agreement([_pair({"a": 1.0}, {"a": 0.0})], {"a": 1.0})

        assert tiny["a"] == huge["a"]

    def test_a_tie_counts_as_an_evaluable_pair_but_casts_no_vote(self) -> None:
        """Der Unterschied traegt den zweiten entarteten Weg: Das Paar IST auswertbar (beide
        Fotos tragen den Messwert, D5), es stimmt nur nicht ab."""
        result = criterion_agreement([_pair({"sharpness": 0.5}, {"sharpness": 0.5})], _BASELINE)

        assert result["sharpness"] == CriterionAgreement(case_count=1, votes=0.0, agreement=0.0)

    def test_the_event_weight_scales_the_votes_not_the_case_count(self) -> None:
        """ANGEZEIGT wird die ungewichtete Fallzahl, GERECHNET wird mit der gewichteten
        Stimmenzahl - eine gewichtete Zahl als Fallzahl behauptete Korrekturen, die niemand
        vorgenommen hat."""
        result = criterion_agreement(
            [_pair({"sharpness": 0.9}, {"sharpness": 0.1}, weight=2.0)], _BASELINE
        )

        assert result["sharpness"] == CriterionAgreement(case_count=1, votes=2.0, agreement=1.0)

    def test_a_heavier_pair_outweighs_a_lighter_opposing_one(self) -> None:
        result = criterion_agreement(
            [
                _pair({"sharpness": 0.9}, {"sharpness": 0.1}, weight=3.0),
                _pair({"sharpness": 0.1}, {"sharpness": 0.9}, weight=1.0),
            ],
            _BASELINE,
        )

        assert result["sharpness"].votes == 4.0
        assert result["sharpness"].agreement == pytest.approx(0.5)

    def test_a_one_sided_value_makes_the_pair_unevaluable_for_every_criterion(self) -> None:
        """Die Assertion gilt ALLEN Kriterien, nicht nur dem fehlenden: Ein Paar mit nur
        einseitigem Wert darf auch bei den vollstaendig belegten keine halbe Stimme hinterlassen."""
        result = criterion_agreement([_pair({"sharpness": 0.9}, {})], _BASELINE)

        assert all(entry == CriterionAgreement(0, 0.0, 0.0) for entry in result.values())

    def test_disjoint_criterion_sets_contribute_nothing(self) -> None:
        result = criterion_agreement([_pair({"sharpness": 0.9}, {"exposure": 0.1})], _BASELINE)

        assert all(entry == CriterionAgreement(0, 0.0, 0.0) for entry in result.values())

    def test_a_photo_without_any_criterion_values_contributes_nothing(self) -> None:
        result = criterion_agreement([_pair({}, {})], _BASELINE)

        assert all(entry == CriterionAgreement(0, 0.0, 0.0) for entry in result.values())

    def test_every_requested_key_appears_even_without_a_single_pair(self) -> None:
        result = criterion_agreement([], _BASELINE)

        assert set(result) == set(_BASELINE)

    def test_a_measured_criterion_outside_the_requested_keys_never_appears(self) -> None:
        """ITERIERT WIRD UEBER DEN UEBERGEBENEN SCHLUESSELSATZ, nie ueber die vorliegenden
        Messwerte: `photo_criterion_scores` traegt Kriterien mit Inhaltsaussage, die `quality.py`
        bewusst nicht gewichtet (G2)."""
        result = criterion_agreement(
            [_pair({"landschaft": 0.9, "sharpness": 0.9}, {"landschaft": 0.1, "sharpness": 0.1})],
            _BASELINE,
        )

        assert "landschaft" not in result


class TestTheWeightDerivation:
    def test_without_any_pair_every_weight_is_exactly_its_baseline(self) -> None:
        """GLEICHHEIT, kein `approx`: Der Nullzustand ist der Startwert und nicht etwas, das ihm
        bis auf Rundung gleicht."""
        derived = derive_weights(criterion_agreement([], _BASELINE), _BASELINE)

        assert derived == _BASELINE
        _assert_invariants(derived, _BASELINE)

    def test_pairs_with_a_running_tie_leave_every_weight_at_its_baseline(self) -> None:
        """Der zweite entartete Weg: Es LIEGEN Paare vor, nur stimmt keines ab. Ein Schutz der
        Form `if not pairs: return baseline` besteht den Fall darueber und teilt hier durch
        null."""
        pairs = [_pair({key: 0.5 for key in _BASELINE}, {key: 0.5 for key in _BASELINE})] * 4

        derived = derive_weights(criterion_agreement(pairs, _BASELINE), _BASELINE)

        assert derived == _BASELINE
        _assert_invariants(derived, _BASELINE)

    def test_a_degenerate_criterion_keeps_its_baseline_next_to_a_moving_one(self) -> None:
        """Der dritte entartete Weg, und der einzige, den ein je ABLEITUNG statt je KRITERIUM
        gezogener Fruehausstieg nicht besteht: Er liefert hier ueberall stillschweigend den
        Startwert."""
        pairs = [_pair({"sharpness": 0.9, "exposure": 0.5}, {"sharpness": 0.1, "exposure": 0.5})]

        derived = derive_weights(criterion_agreement(pairs, _BASELINE), _BASELINE)

        assert derived["exposure"] == _BASELINE["exposure"]
        assert derived["aesthetics"] == _BASELINE["aesthetics"]
        assert derived["sharpness"] > _BASELINE["sharpness"]
        _assert_invariants(derived, _BASELINE)

    def test_full_rejection_devalues_the_criterion_without_inverting_it(self) -> None:
        """ABGEWERTET, NIE INVERTIERT UND NIE AUF NULL: strikt positiv und strikt oberhalb von
        `start * (1 - SPAN)`."""
        pairs = [_pair({"sharpness": 0.1}, {"sharpness": 0.9}) for _ in range(200)]

        derived = derive_weights(criterion_agreement(pairs, _BASELINE), _BASELINE)

        assert derived["sharpness"] < _BASELINE["sharpness"]
        assert derived["sharpness"] > _BASELINE["sharpness"] * (1.0 - FEEDBACK_WEIGHT_SPAN)
        _assert_invariants(derived, _BASELINE)

    def test_full_agreement_upgrades_the_criterion_within_the_span(self) -> None:
        pairs = [_pair({"sharpness": 0.9}, {"sharpness": 0.1}) for _ in range(200)]

        derived = derive_weights(criterion_agreement(pairs, _BASELINE), _BASELINE)

        assert derived["sharpness"] > _BASELINE["sharpness"]
        assert derived["sharpness"] < _BASELINE["sharpness"] * (1.0 + FEEDBACK_WEIGHT_SPAN)
        _assert_invariants(derived, _BASELINE)

    def test_the_shrinkage_follows_the_documented_formula(self) -> None:
        """Der Rechenweg selbst, an einer Stelle festgenagelt - sonst bliebe die Schrumpfung eine
        Behauptung des Docstrings."""
        pairs = [_pair({"sharpness": 0.9}, {"sharpness": 0.1}) for _ in range(5)]

        derived = derive_weights(criterion_agreement(pairs, _BASELINE), _BASELINE)

        expected = _BASELINE["sharpness"] * (
            1.0 + FEEDBACK_WEIGHT_SPAN * 1.0 * 5.0 / (5.0 + PRIOR_STRENGTH)
        )
        assert derived["sharpness"] == pytest.approx(expected)
        _assert_invariants(derived, _BASELINE)

    def test_an_exchange_and_its_reverse_cancel_out_without_erasing_each_other(self) -> None:
        """NUR DIE FALLZAHL trennt das von einer Umsetzung, die die Umkehr als Ruecknahme
        behandelt: Das Gewicht ist in beiden Faellen exakt der Startwert, `n_k` waechst hier aber
        um ZWEI."""
        pairs = [
            _pair({"sharpness": 0.9}, {"sharpness": 0.1}),
            _pair({"sharpness": 0.1}, {"sharpness": 0.9}),
        ]
        agreements = criterion_agreement(pairs, _BASELINE)

        derived = derive_weights(agreements, _BASELINE)

        assert agreements["sharpness"].case_count == 2
        assert agreements["sharpness"].votes == 2.0
        assert derived["sharpness"] == _BASELINE["sharpness"]
        _assert_invariants(derived, _BASELINE)

    def test_a_baseline_key_without_any_agreement_entry_keeps_its_baseline(self) -> None:
        derived = derive_weights({}, _BASELINE)

        assert derived == _BASELINE
        _assert_invariants(derived, _BASELINE)

    def test_an_agreement_key_unknown_to_the_baseline_is_dropped(self) -> None:
        """Die Gegenrichtung, ohne die `{**baseline, **derived}` bestuende - und genau das ist
        der Weg, auf dem ein Inhaltskriterium in den Qualitaetswert geriete (G2)."""
        agreements = {"landschaft": CriterionAgreement(case_count=9, votes=9.0, agreement=1.0)}

        derived = derive_weights(agreements, _BASELINE)

        assert derived == _BASELINE
        _assert_invariants(derived, _BASELINE)

    def test_a_pair_differing_only_in_a_content_criterion_moves_no_weight(self) -> None:
        """Ueber der ECHTEN Startwerttabelle: Eine Ableitung, die ueber die vorliegenden Messwerte
        iteriert, braechte `landschaft` in den Qualitaetswert, ohne dass
        `test_quality.py::TestTheWeightTableCarriesNoContentSignal` rot wuerde."""
        pairs = [_pair({"landschaft": 0.9}, {"landschaft": 0.1}) for _ in range(20)]

        derived = derive_weights(
            criterion_agreement(pairs, QUALITY_CRITERION_WEIGHTS), QUALITY_CRITERION_WEIGHTS
        )

        assert derived == QUALITY_CRITERION_WEIGHTS
        _assert_invariants(derived, QUALITY_CRITERION_WEIGHTS)


class TestThePairsFromTheJointFinalSelection:
    """Je `(Lauf, Ereignis)` tritt jedes aufgenommene gegen jedes herausgenommene Foto DERSELBEN
    Stufe an (G5). Die Gruppierung haelt die Gegenueberstellung lokal - ohne sie verglichen wir
    einen Sonnenuntergang von Tag 1 gegen ein Abendessen von Tag 5."""

    def _record(
        self,
        *,
        included: bool,
        values: Mapping[str, float],
        run_id: int | None = 7,
        event_id: int | None = 3,
        level: int | None = 4,
        weight: float = 2.0,
    ) -> FinalDecisionRecord:
        return FinalDecisionRecord(
            criterion_scoring_run_id=run_id,
            event_id=event_id,
            level=level,
            included=included,
            weight=weight,
            values=dict(values),
        )

    def test_an_included_photo_is_preferred_over_a_removed_one(self) -> None:
        pairs = final_decision_pairs(
            [
                self._record(included=True, values={"sharpness": 0.9}),
                self._record(included=False, values={"sharpness": 0.1}),
            ]
        )

        assert pairs == [
            PreferencePair(preferred={"sharpness": 0.9}, rejected={"sharpness": 0.1}, weight=2.0)
        ]

    def test_every_included_photo_meets_every_removed_one(self) -> None:
        records = [
            self._record(included=True, values={"sharpness": 0.9}),
            self._record(included=True, values={"sharpness": 0.8}),
            self._record(included=False, values={"sharpness": 0.3}),
            self._record(included=False, values={"sharpness": 0.2}),
            self._record(included=False, values={"sharpness": 0.1}),
        ]

        assert len(final_decision_pairs(records)) == 6

    def test_photos_of_different_levels_never_form_a_pair(self) -> None:
        """Stufenuebergreifende Paare bleiben draussen, damit die Aussage ueber die lokalen
        Kriterien nicht mit der ueber das Modell vermischt wird."""
        pairs = final_decision_pairs(
            [
                self._record(included=True, values={"sharpness": 0.9}, level=5),
                self._record(included=False, values={"sharpness": 0.1}, level=2),
            ]
        )

        assert pairs == []

    def test_photos_of_different_events_never_form_a_pair(self) -> None:
        pairs = final_decision_pairs(
            [
                self._record(included=True, values={"sharpness": 0.9}, event_id=1),
                self._record(included=False, values={"sharpness": 0.1}, event_id=2),
            ]
        )

        assert pairs == []

    def test_photos_of_different_runs_never_form_a_pair(self) -> None:
        pairs = final_decision_pairs(
            [
                self._record(included=True, values={"sharpness": 0.9}, run_id=1),
                self._record(included=False, values={"sharpness": 0.1}, run_id=2),
            ]
        )

        assert pairs == []

    @pytest.mark.parametrize("field", ["run_id", "event_id", "level"])
    def test_a_record_without_run_event_or_level_forms_no_pair(self, field: str) -> None:
        """Ein Endauswahl-Ereignis ohne Lauf- oder Event-Bezug bildet KEIN Paar (G5); ohne Stufe
        ebenso wenig - "derselben Stufe" ist fuer `None` nicht erfuellbar, genauso wie ein
        Austausch ohne Stufe `undetermined` ist."""
        records = [
            self._record(included=True, values={"sharpness": 0.9}, **{field: None}),  # type: ignore[arg-type]
            self._record(included=False, values={"sharpness": 0.1}),
        ]

        assert final_decision_pairs(records) == []

    def test_the_pair_carries_the_event_weight(self) -> None:
        pairs = final_decision_pairs(
            [
                self._record(included=True, values={"sharpness": 0.9}, weight=2.0),
                self._record(included=False, values={"sharpness": 0.1}, weight=2.0),
            ]
        )

        assert [pair.weight for pair in pairs] == [2.0]

    def test_a_group_without_a_counterpart_produces_nothing(self) -> None:
        records = [self._record(included=True, values={"sharpness": 0.9}) for _ in range(3)]

        assert final_decision_pairs(records) == []


class TestTheModuleStaysPure:
    """Reinheitswaechter im Muster von `quality.py`/`selection.py`/`album_selection.py`: Die Regel
    lebt DB-frei, damit sie ohne Datenbank vollstaendig pruefbar bleibt. Ein hereingezogenes
    Modell brauchte fuer jeden Randfall eine Sitzung, und die Randfaelle sind hier die Sache."""

    def test_neither_sqlalchemy_nor_the_models_are_imported(self) -> None:
        from photosort import feedback

        source = Path(feedback.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)

        forbidden = sorted(
            name
            for name in imported
            if name.split(".")[0] == "sqlalchemy" or name == "photosort.models"
        )
        assert forbidden == []
