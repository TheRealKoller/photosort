from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from photosort.horizon import (
    HORIZON_MAX_CANDIDATE_ANGLE,
    HORIZON_MAX_PENALIZED_ANGLE_DEGREES,
    _score_from_angle_deviation,
    _select_dominant_candidate_angle,
    compute_horizon_tilt_score,
)


def _solid(color: int = 100, size: int = 200) -> Image.Image:
    return Image.new("L", (size, size), color=color)


def _line_image(
    xy: tuple[int, int, int, int], color: int = 230, background: int = 30, size: int = 200
) -> Image.Image:
    image = Image.new("L", (size, size), color=background)
    ImageDraw.Draw(image).line(xy, fill=color, width=2)
    return image


class TestComputeHorizonTiltScore:
    def test_no_candidate_line_at_all_yields_the_neutral_fallback(self) -> None:
        # AK der Spec 0048: "Kein erkannter Kandidat -> score == 0.5 (neutral, bewusst nicht
        # niedrig)" - ein komplett flaechiges Bild liefert keine Canny-Kanten, also auch keine
        # Hough-Linie.
        assert compute_horizon_tilt_score(_solid()) == 0.5

    def test_exactly_horizontal_dominant_line_scores_one(self) -> None:
        # AK: "Exakt horizontale, dominante Linie -> score == 1.0".
        image = _line_image((5, 100, 194, 100))
        assert compute_horizon_tilt_score(image) == 1.0

    def test_a_vertical_line_alone_is_not_a_candidate_and_yields_the_neutral_fallback(
        self,
    ) -> None:
        # Nahezu senkrechte Strukturen (Gebaeudekanten, Tuerrahmen) sind KEINE Horizont-
        # Kandidaten (ADR 0026 Punkt 2) - ohne jede weitere Linie bleibt nur der neutrale
        # Fallback, kein Crash/falscher Kandidat.
        image = _line_image((100, 5, 100, 194))
        assert compute_horizon_tilt_score(image) == 0.5

    def test_a_moderately_tilted_line_within_the_penalty_range_scores_between_zero_and_one(
        self,
    ) -> None:
        # 20x20 Pixel Steigung liegt deutlich innerhalb von HORIZON_MAX_CANDIDATE_ANGLE (45 Grad)
        # und ueber einem trivialen Null-Winkel - score muss echt zwischen 0 und 1 liegen, nicht
        # an einem der beiden Fallback-Werte (1.0 oder 0.5) haengen bleiben.
        image = _line_image((20, 80, 180, 100))
        score = compute_horizon_tilt_score(image)
        assert 0.0 < score < 1.0

    def test_the_longest_candidate_line_wins_over_a_shorter_more_tilted_one(self) -> None:
        # ADR 0026 Punkt 2: "laengste Kandidatenlinie gewinnt" - eine lange, fast horizontale
        # Linie MUSS den Score dominieren, obwohl gleichzeitig eine kurze, staerker geneigte
        # Linie im selben Bild existiert.
        image = Image.new("L", (200, 200), color=30)
        draw = ImageDraw.Draw(image)
        draw.line((2, 100, 197, 101), fill=230, width=2)  # lang, fast horizontal
        draw.line((80, 20, 120, 60), fill=230, width=2)  # kurz, stark geneigt (~45 Grad)
        score = compute_horizon_tilt_score(image)
        assert score > 0.9


class TestSelectDominantCandidateAngle:
    def test_no_lines_returns_none(self) -> None:
        assert _select_dominant_candidate_angle(None) is None

    def test_a_candidate_exactly_at_the_max_candidate_angle_boundary_is_still_included(
        self,
    ) -> None:
        # Inklusiv-/Exklusiv-Grenze bei HORIZON_MAX_CANDIDATE_ANGLE (AK der Spec 0048) - analog
        # zur bereits etablierten >=-Einschluss-Konvention in criteria.py::
        # derive_active_categories. Eine Linie GENAU an der Grenze zaehlt noch als Kandidat.
        assert HORIZON_MAX_CANDIDATE_ANGLE == 45.0
        lines = np.array([[0, 0, 10, 10]])  # exakt 45 Grad (dx == dy)
        assert _select_dominant_candidate_angle(lines) == 45.0

    def test_a_candidate_just_beyond_the_max_candidate_angle_is_excluded(self) -> None:
        lines = np.array([[0, 0, 10, 11]])  # > 45 Grad
        assert _select_dominant_candidate_angle(lines) is None

    def test_the_strictly_longer_candidate_wins(self) -> None:
        lines = np.array(
            [
                [0, 0, 10, 1],  # kurz, kleiner Winkel
                [0, 0, 100, 20],  # laenger, groesserer Winkel
            ]
        )
        winner = _select_dominant_candidate_angle(lines)
        assert winner == _select_dominant_candidate_angle(np.array([[0, 0, 100, 20]]))

    def test_tie_break_between_equally_long_candidates_is_deterministic(self) -> None:
        # Tie-Break bei exakt gleicher Laenge (technische Detailentscheidung, ADR 0026 offen
        # gelassen, siehe Modul-Kommentar in horizon.py): die ZUERST auftretende Linie gewinnt -
        # deterministisch bei wiederholten Aufrufen mit identischer Eingabe, unabhaengig von einer
        # nicht garantierten cv2-internen Rueckgabereihenfolge.
        lines = np.array(
            [
                [0, 0, 10, 2],  # Laenge sqrt(104), kleiner Winkel
                [0, 0, 10, -2],  # exakt dieselbe Laenge, gegensaetzlicher Winkel
            ]
        )
        first_call = _select_dominant_candidate_angle(lines)
        second_call = _select_dominant_candidate_angle(lines)
        assert first_call == second_call
        assert first_call == _select_dominant_candidate_angle(np.array([[0, 0, 10, 2]]))

    def test_a_line_with_a_raw_atan2_angle_above_ninety_degrees_is_normalized(self) -> None:
        # (x1,y1)-(x2,y2) mit x2 < x1 und y2 > y1 (Endpunkte "rueckwaerts") liefert einen rohen
        # atan2-Winkel > 90 Grad - _line_angle_degrees muss ihn auf die aequivalente Halbebene
        # (-90, 90] normieren (hier: -180 Grad addiert), nicht faelschlich als jenseits von
        # HORIZON_MAX_CANDIDATE_ANGLE ausschliessen.
        lines = np.array([[10, 0, 0, 1]])  # roher Winkel ~174.3 Grad -> normiert ~-5.7 Grad
        angle = _select_dominant_candidate_angle(lines)
        assert angle is not None
        assert -6.0 < angle < -5.0

    def test_zero_length_entries_are_ignored_without_crashing(self) -> None:
        lines = np.array([[5, 5, 5, 5], [0, 0, 10, 10]])
        assert _select_dominant_candidate_angle(lines) == 45.0


class TestScoreFromAngleDeviation:
    def test_zero_deviation_scores_one(self) -> None:
        assert _score_from_angle_deviation(0.0) == 1.0

    def test_deviation_exactly_at_the_penalty_ceiling_scores_zero(self) -> None:
        # AK der Spec 0048: "Linie exakt bei HORIZON_MAX_PENALIZED_ANGLE_DEGREES -> score == 0.0
        # (nicht negativ)".
        assert HORIZON_MAX_PENALIZED_ANGLE_DEGREES == 15.0
        assert _score_from_angle_deviation(15.0) == 0.0
        assert _score_from_angle_deviation(-15.0) == 0.0

    def test_deviation_beyond_the_penalty_ceiling_is_clamped_to_zero_not_negative(self) -> None:
        # AK: "Linie jenseits HORIZON_MAX_PENALIZED_ANGLE_DEGREES, aber innerhalb
        # HORIZON_MAX_CANDIDATE_ANGLE -> score auf 0.0 geklemmt".
        assert _score_from_angle_deviation(30.0) == 0.0

    def test_deviation_within_range_scales_linearly(self) -> None:
        assert _score_from_angle_deviation(7.5) == 0.5
