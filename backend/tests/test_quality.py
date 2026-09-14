"""specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 7 - Muster `test_ranking.py`.

Rein, DB-frei, netzfrei. Fünf Zusagen tragen mehr als eine Werteprüfung, und jede bekommt einen
eigenen, benannten Fall, der die Aussage über der TABELLE formuliert statt sie abzuschreiben:

(a) Kein Eintrag der Gewichtstabelle trägt eine `presence_threshold`, und `content_landscape`
    steht nicht darin - gelesen aus `CRITERIA_REGISTRY`, nicht aus einer zweiten Aufzählung hier:
    sonst bestünde der Test ein neu aufgenommenes Inhaltskriterium.
(b) Zwei Fotos, die sich ausschließlich im Inhalt unterscheiden, tragen denselben Qualitätswert.
(c) Die Ordnungszusage über alle vier benachbarten Stufenpaare - plus die STRIKTE Grenze
    `LOCAL_CORRECTION_SPAN < 0,125`, die von der Anzeigezusage kommt.
(d) Die Renormierung: ein fehlendes Kriterium senkt den Wert NICHT.
(e) Dieselbe Renormierung von der anderen Seite: eine gleichmäßige Streckung ALLER Gewichte
    ändert keinen Qualitätswert - es wirken allein die Verhältnisse. Darauf ruht die
    Abwertungsaussage der Gewichtsableitung (`feedback.py::derive_weights`); bricht die
    Eigenschaft hier, wird kein Fall in `test_feedback.py` rot.
"""

from __future__ import annotations

import math

import pytest

from photosort.album_suitability import (
    ALBUM_SUITABILITY_MAX_LEVEL,
    ALBUM_SUITABILITY_MIN_LEVEL,
    normalize_level,
)
from photosort.criteria import CRITERIA_REGISTRY
from photosort.quality import (
    LOCAL_CORRECTION_SPAN,
    QUALITY_CRITERION_WEIGHTS,
    compute_quality_score,
    local_correction,
)

_ALL_LEVELS = tuple(range(ALBUM_SUITABILITY_MIN_LEVEL, ALBUM_SUITABILITY_MAX_LEVEL + 1))


def _values(value: float) -> dict[str, float]:
    """Jedes gewichtete Kriterium auf demselben Wert - aus der Tabelle abgeleitet, nie als zweite
    Liste geschrieben."""
    return dict.fromkeys(QUALITY_CRITERION_WEIGHTS, value)


class TestTheWeightTableCarriesNoContentSignal:
    def test_no_weighted_criterion_makes_a_content_statement(self) -> None:
        """Invariante (a): `presence_threshold is not None` IST die Inhaltsaussage-Frage
        (criteria.py). Gelesen wird die Registry, nicht eine Liste in diesem Test - ein neu
        aufgenommenes Inhaltskriterium soll hier scheitern, nicht unbemerkt durchgehen."""
        for key in QUALITY_CRITERION_WEIGHTS:
            assert CRITERIA_REGISTRY[key].presence_threshold is None, key

    def test_content_landscape_is_not_part_of_the_quality_score(self) -> None:
        """Es misst Texturarmut - "mehr gleichfoermige Flaeche" ist keine Guetaussage. Als
        Kriterium bleibt es bestehen, in den Qualitaetswert geht es nicht ein."""
        assert "content_landscape" in CRITERIA_REGISTRY
        assert "content_landscape" not in QUALITY_CRITERION_WEIGHTS

    def test_the_table_is_not_empty_and_names_exactly_the_seven_expected_keys(self) -> None:
        """Positiv-Gegenprobe zu den beiden Faellen darueber: eine LEERE Tabelle bestuende sie
        beide."""
        assert set(QUALITY_CRITERION_WEIGHTS) == {
            "sharpness",
            "exposure",
            "aesthetics",
            "goldener_schnitt",
            "symmetrie",
            "horizont",
            "freiraum",
        }

    def test_every_weight_is_positive(self) -> None:
        for key, weight in QUALITY_CRITERION_WEIGHTS.items():
            assert weight > 0, key


class TestLocalCorrection:
    def test_an_empty_criterion_set_has_no_local_correction_at_all(self) -> None:
        """`None`, nicht `0.0`: "kein lokales Signal" ist nicht dasselbe wie "lokal schlecht" -
        der Unterschied entscheidet ueber `Q = M` statt `Q = M - span`."""
        assert local_correction({}, QUALITY_CRITERION_WEIGHTS) is None

    def test_only_unweighted_criteria_are_no_local_correction_either(self) -> None:
        assert local_correction({"content_people": 1.0}, QUALITY_CRITERION_WEIGHTS) is None

    @pytest.mark.parametrize("value", [0.0, 0.25, 0.5, 1.0])
    def test_all_criteria_at_the_same_value_yield_exactly_that_value(self, value: float) -> None:
        assert local_correction(_values(value), QUALITY_CRITERION_WEIGHTS) == pytest.approx(value)

    def test_a_missing_criterion_does_not_lower_the_value(self) -> None:
        """Invariante (d), die tragende Gegenprobe gegen eine Implementierung, die ein fehlendes
        Kriterium als 0 wertet: das Mittel RENORMIERT auf die vorhandene Teilmenge."""
        full = local_correction(_values(0.8), QUALITY_CRITERION_WEIGHTS)
        without_freiraum = dict(_values(0.8))
        del without_freiraum["freiraum"]

        partial = local_correction(without_freiraum, QUALITY_CRITERION_WEIGHTS)

        assert full == pytest.approx(0.8)
        assert partial == pytest.approx(0.8)

    def test_a_single_present_criterion_is_the_whole_local_value(self) -> None:
        assert local_correction({"sharpness": 0.3}, QUALITY_CRITERION_WEIGHTS) == pytest.approx(0.3)

    def test_the_weights_actually_weight(self) -> None:
        """Sonst waere die Tabelle eine Aufzaehlung und kein Gewicht."""
        weights = {"sharpness": 3.0, "exposure": 1.0}

        assert local_correction({"sharpness": 1.0, "exposure": 0.0}, weights) == pytest.approx(0.75)

    def test_values_outside_the_table_are_ignored(self) -> None:
        mixed = {"sharpness": 1.0, "content_people": 0.0}

        assert local_correction(mixed, QUALITY_CRITERION_WEIGHTS) == pytest.approx(1.0)


class TestComputeQualityScore:
    def test_without_any_local_criterion_the_score_is_exactly_the_model_level(self) -> None:
        for level in _ALL_LEVELS:
            assert compute_quality_score(level, {}, QUALITY_CRITERION_WEIGHTS) == pytest.approx(
                normalize_level(level)
            )

    def test_a_perfect_local_measurement_lifts_the_score_by_the_full_span(self) -> None:
        score = compute_quality_score(3, _values(1.0), QUALITY_CRITERION_WEIGHTS)

        assert score == pytest.approx(normalize_level(3) + LOCAL_CORRECTION_SPAN)

    def test_a_worst_local_measurement_lowers_the_score_by_the_full_span(self) -> None:
        score = compute_quality_score(3, _values(0.0), QUALITY_CRITERION_WEIGHTS)

        assert score == pytest.approx(normalize_level(3) - LOCAL_CORRECTION_SPAN)

    def test_a_neutral_local_measurement_leaves_the_level_untouched(self) -> None:
        score = compute_quality_score(3, _values(0.5), QUALITY_CRITERION_WEIGHTS)

        assert score == pytest.approx(normalize_level(3))

    def test_the_score_is_clamped_at_both_ends(self) -> None:
        """Stufe 1 mit `L = 0` bleibt 0, Stufe 5 mit `L = 1` bleibt 1 - ohne Klemmung entstuenden
        -0,1 und 1,1, und `rank_score` ist eine Groesse auf [0, 1]."""
        assert compute_quality_score(1, _values(0.0), QUALITY_CRITERION_WEIGHTS) == 0.0
        assert compute_quality_score(5, _values(1.0), QUALITY_CRITERION_WEIGHTS) == 1.0

    def test_every_score_stays_inside_the_unit_interval(self) -> None:
        for level in _ALL_LEVELS:
            for value in (0.0, 0.5, 1.0):
                score = compute_quality_score(level, _values(value), QUALITY_CRITERION_WEIGHTS)
                assert 0.0 <= score <= 1.0, (level, value)


class TestTheRenormalizationInvariance:
    """Eine gleichmaessige Streckung ALLER Gewichte aendert keinen Qualitaetswert:
    `compute_quality_score(level, values, {k: c*w_k})` ist fuer jedes `c > 0` identisch zu
    `compute_quality_score(level, values, w)`. Es wirken allein die VERHAELTNISSE.

    DAS IST DIE EIGENSCHAFT DES BESTANDSCODES, AUF DER DIE ABWERTUNGSAUSSAGE DER
    GEWICHTSABLEITUNG RUHT (`feedback.py::derive_weights`): "abgewertet, nie invertiert" und "ein
    Kriterium mit Gegenwind verliert an Einfluss" sind nur wahr, weil `local_correction` auf die
    Gewichtssumme renormiert. Ohne diese Renormierung waere eine gleichmaessige Streckung eine
    Verhaltensaenderung, und eine Ableitung, die alle sieben Gewichte anhebt, verschoebe jeden
    Qualitaetswert des Bestands.

    DER FALL STEHT HIER UND NICHT IN `test_feedback.py`: Braeche die Eigenschaft kuenftig in
    `quality.py`, wuerde kein einziger Fall dort rot - die Aussage verschwaende still an einer
    Stelle, die niemand mit dem Feedback in Verbindung bringt.

    Nicht zu verwechseln mit Invariante (d): Die betrifft ein FEHLENDES Kriterium, diese die
    gleichmaessige Streckung der vorhandenen."""

    # UNGLEICHE Gewichte und UNGLEICHE Werte. Bei durchgehend gleichen Werten liefert jedes
    # gewichtete Mittel denselben Wert, und der Fall bestuende auch gegen eine Umsetzung, die die
    # Gewichte gar nicht liest.
    _WEIGHTS = {"sharpness": 1.0, "exposure": 2.0, "aesthetics": 0.5}
    _VALUES = {"sharpness": 0.9, "exposure": 0.2, "aesthetics": 0.6}
    _FACTORS = (0.5, 2.0, 3.0, 100.0)

    @pytest.mark.parametrize("factor", _FACTORS)
    def test_scaling_every_weight_alike_leaves_the_local_correction_untouched(
        self, factor: float
    ) -> None:
        stretched = {key: factor * weight for key, weight in self._WEIGHTS.items()}

        assert local_correction(self._VALUES, stretched) == pytest.approx(
            local_correction(self._VALUES, self._WEIGHTS)
        )

    @pytest.mark.parametrize("factor", _FACTORS)
    def test_scaling_every_weight_alike_leaves_the_quality_score_untouched(
        self, factor: float
    ) -> None:
        stretched = {key: factor * weight for key, weight in self._WEIGHTS.items()}

        assert compute_quality_score(3, self._VALUES, stretched) == pytest.approx(
            compute_quality_score(3, self._VALUES, self._WEIGHTS)
        )

    @pytest.mark.parametrize("factor", _FACTORS)
    def test_the_invariance_holds_for_the_real_weight_table_on_every_level(
        self, factor: float
    ) -> None:
        """Ueber der TATSAECHLICHEN Tabelle und allen Stufen, weil genau sie es ist, die
        `derive_weights` streckt."""
        stretched = {key: factor * weight for key, weight in QUALITY_CRITERION_WEIGHTS.items()}
        # `strict=True` ist hier die Aussage: Waechst die Tabelle um ein achtes Kriterium, soll
        # der Fall LAUT brechen statt still nur noch sieben abzudecken.
        values = dict(
            zip(QUALITY_CRITERION_WEIGHTS, (0.9, 0.2, 0.6, 0.35, 0.8, 0.1, 0.55), strict=True)
        )

        for level in _ALL_LEVELS:
            assert compute_quality_score(level, values, stretched) == pytest.approx(
                compute_quality_score(level, values, QUALITY_CRITERION_WEIGHTS)
            ), level

    def test_the_chosen_case_sits_away_from_both_clamping_edges(self) -> None:
        """Selbstschutz (a): An einer Kappungsgrenze liefern beide Seiten `0.0` bzw. `1.0`, und
        die Faelle darueber bestuenden auch gegen eine kaputte Renormierung."""
        score = compute_quality_score(3, self._VALUES, self._WEIGHTS)

        assert 0.0 < score < 1.0

    def test_the_weights_influence_this_very_case(self) -> None:
        """Selbstschutz (b): Die Invarianz ist nur dann eine Aussage, wenn die Gewichte an dieser
        Stelle ueberhaupt etwas bewirken. Eine NICHT-proportionale Aenderung muss den Wert
        bewegen - sonst waere die Gleichheit oben trivial."""
        reweighted = {"sharpness": 5.0, "exposure": 1.0, "aesthetics": 0.5}

        assert compute_quality_score(3, self._VALUES, reweighted) != pytest.approx(
            compute_quality_score(3, self._VALUES, self._WEIGHTS)
        )


class TestTheOrderingGuarantee:
    def test_the_lower_level_never_overtakes_the_higher_one(self) -> None:
        """Invariante (c): fuer JEDES der vier benachbarten Stufenpaare gilt
        `Q(n, L=1) <= Q(n+1, L=0)` - die lokalen Messungen ordnen ausschliesslich INNERHALB einer
        Stufe. Ein deutlicher Modellbefund gegen ein Bild kann nicht durch gute lokale Messwerte
        ueberstimmt werden."""
        for level in _ALL_LEVELS[:-1]:
            best_of_the_lower = compute_quality_score(
                level, _values(1.0), QUALITY_CRITERION_WEIGHTS
            )
            worst_of_the_higher = compute_quality_score(
                level + 1, _values(0.0), QUALITY_CRITERION_WEIGHTS
            )

            assert best_of_the_lower <= worst_of_the_higher, level

    def test_the_span_is_strictly_below_an_eighth(self) -> None:
        """Die Ordnungszusage darueber truege noch `<= 0,125`. Diese Grenze ist STRIKT, und sie
        kommt von der ANZEIGEzusage im Frontend: mit den Schwellen auf den Stufenmitten (0,375 /
        0,625) ist die Dreistufigkeit nur dann eine deterministische Vergroeberung der
        Modellstufe, wenn `span < 0,125` gilt. Bei exakt 0,125 faellt Stufe 2 mit `L = 1` genau
        auf 0,375 und erscheint als "mittel", waehrend dieselbe Stufe mit `L = 0` "niedrig" ist -
        dieselbe Modellstufe in zwei Anzeigestufen. Ohne diesen einen Schritt bricht die
        Frontend-Zusage, waehrend die Backend-Suite gruen bleibt."""
        assert LOCAL_CORRECTION_SPAN < 0.125

    def test_the_span_is_positive(self) -> None:
        """Eine Korrekturbreite von 0 machte die lokalen Messungen wirkungslos - dann waere der
        Qualitaetswert die Modellstufe allein."""
        assert LOCAL_CORRECTION_SPAN > 0


class TestContentDoesNotEnterTheScore:
    def test_two_photos_differing_only_in_content_share_the_same_score(self) -> None:
        """Invariante (b) und zugleich das Akzeptanzkriterium: Inhaltssignale und Motivstaerken
        gehen nicht in den Qualitaetswert ein."""
        quality_part = {"sharpness": 0.8, "exposure": 0.6, "aesthetics": 0.4}
        with_people = {
            **quality_part,
            "content_people": 1.0,
            "tier": 1.0,
            "gebaeude": 1.0,
            "landschaft": 1.0,
            "fahrzeug": 1.0,
            "essen_trinken": 1.0,
            "landmark": 1.0,
            "content_landscape": 1.0,
        }
        without_people = {
            **quality_part,
            "content_people": 0.0,
            "tier": 0.0,
            "gebaeude": 0.0,
            "landschaft": 0.0,
            "fahrzeug": 0.0,
            "essen_trinken": 0.0,
            "landmark": 0.0,
            "content_landscape": 0.0,
        }

        assert compute_quality_score(
            4, with_people, QUALITY_CRITERION_WEIGHTS
        ) == compute_quality_score(4, without_people, QUALITY_CRITERION_WEIGHTS)

    def test_a_photo_without_a_subject_is_not_penalised_for_the_missing_composition(self) -> None:
        """Die Folge von "nicht messbar wird weggelassen": ein Foto ohne Personen und ohne Objekt
        traegt `goldener_schnitt`/`freiraum` gar nicht - und steht damit genauso da wie ein gleich
        gutes Foto MIT Personen, dessen Kompositionswerte dem uebrigen Mittel entsprechen."""
        with_composition = {
            "sharpness": 0.7,
            "exposure": 0.7,
            "aesthetics": 0.7,
            "symmetrie": 0.7,
            "horizont": 0.7,
            "goldener_schnitt": 0.7,
            "freiraum": 0.7,
        }
        without_composition = {
            "sharpness": 0.7,
            "exposure": 0.7,
            "aesthetics": 0.7,
            "symmetrie": 0.7,
            "horizont": 0.7,
        }

        assert compute_quality_score(
            3, with_composition, QUALITY_CRITERION_WEIGHTS
        ) == pytest.approx(compute_quality_score(3, without_composition, QUALITY_CRITERION_WEIGHTS))

    def test_the_old_zero_fallback_would_have_lowered_the_score(self) -> None:
        """Die Gegenprobe zum Fall darueber - sonst pruefte er eine Gleichheit, die auch eine
        kaputte Renormierung liefern koennte."""
        with_zero_fallback = {
            "sharpness": 0.7,
            "exposure": 0.7,
            "aesthetics": 0.7,
            "symmetrie": 0.7,
            "horizont": 0.7,
            "goldener_schnitt": 0.0,
            "freiraum": 0.0,
        }
        without_composition = {
            "sharpness": 0.7,
            "exposure": 0.7,
            "aesthetics": 0.7,
            "symmetrie": 0.7,
            "horizont": 0.7,
        }

        assert compute_quality_score(3, with_zero_fallback, QUALITY_CRITERION_WEIGHTS) < (
            compute_quality_score(3, without_composition, QUALITY_CRITERION_WEIGHTS)
        )


class TestTheDisplayCoarsening:
    """Die Anzeigezusage des Frontends, hier auf der Backend-Seite ihrer Voraussetzung geprueft:
    mit Schwellen auf den Stufenmitten faellt jede Modellstufe fuer JEDEN zulaessigen lokalen
    Korrekturbetrag in genau EINE Anzeigestufe."""

    @pytest.mark.parametrize(
        ("level", "expected"),
        [(1, "niedrig"), (2, "niedrig"), (3, "mittel"), (4, "hoch"), (5, "hoch")],
    )
    def test_every_level_lands_in_exactly_one_display_step(self, level: int, expected: str) -> None:
        def coarse(score: float) -> str:
            if score >= 0.625:
                return "hoch"
            return "mittel" if score >= 0.375 else "niedrig"

        steps = {
            coarse(compute_quality_score(level, _values(value), QUALITY_CRITERION_WEIGHTS))
            for value in (0.0, 0.5, 1.0)
        }

        assert steps == {expected}

    def test_the_boundary_case_of_the_span_would_break_it(self) -> None:
        """Der Nachweis, dass die strikte Grenze oben nicht willkuerlich ist: mit `span = 0,125`
        faellt Stufe 2 mit `L = 1` exakt auf die Schwelle 0,375 und erscheint als "mittel"."""
        breaking_span = 0.125

        assert math.isclose(normalize_level(2) + breaking_span, 0.375)
