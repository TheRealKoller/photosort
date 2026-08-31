from __future__ import annotations

import math

import numpy as np
from PIL import Image

# specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md, decisions/0026-
# modellwahl-symmetrie-horizont-freiraum-kriterien.md Punkt 2: neues, eigenstaendiges Modul
# (analog aesthetics.py) - haelt den lokalen cv2-Import (siehe compute_horizon_tilt_score) auf
# genau den Importpfad begrenzt, der ihn tatsaechlich braucht, exakt dasselbe Muster wie der
# lokale tensorflow-Import in aesthetics.py bzw. der lokale mediapipe-Import in
# classification.py::_to_mp_image. `cv2.Canny`+`cv2.HoughLinesP` werden AUSSCHLIESSLICH auf einem
# bereits ueber Pillow dekodierten Graustufen-Array angewendet - nie `cv2.imread`/`cv2.imdecode`,
# Pillow bleibt die alleinige Bild-I/O-Bibliothek im Projekt (Security-Abschnitt der Spec: die
# historisch CVE-traechtigsten OpenCV-Codepfade [Bild-/Video-Decoder] werden dadurch strukturell
# nicht erreicht).

# Canny-Schwellwerte (unkalibriert dokumentiert, gleiche Klasse wie scoring.py::
# SHARPNESS_REJECT_THRESHOLD/classification.py::UNIFORM_TILE_VARIANCE_THRESHOLD - kein Fotokorpus
# im Repo zur Kalibrierung, siehe specs/architecture/0002-testkonzept.md "Bekannte Luecken").
_HORIZON_CANNY_LOW = 50
_HORIZON_CANNY_HIGH = 150

# cv2.HoughLinesP-Parameter (ebenfalls unkalibriert, wie oben).
_HOUGH_RHO = 1.0
_HOUGH_THETA = math.pi / 180
_HOUGH_THRESHOLD = 50
_HOUGH_MIN_LINE_LENGTH = 40
_HOUGH_MAX_LINE_GAP = 10

# Maximale Abweichung von der Horizontalen, ab der eine Hough-Linie ueberhaupt als Horizont-
# Kandidat gilt (ADR 0026 Punkt 2) - schliesst nahezu vertikale Strukturen (Gebaeudekanten,
# Tuerrahmen) aus, die keine Horizont-Kandidaten sind. Grenze selbst zaehlt noch als Kandidat
# (inklusiver Vergleich, `>` statt `>=` beim Ausschluss - konsistent mit der projektweiten
# `>=`-Einschluss-Konvention bei Schwellwertvergleichen, heute in worker.py::derive_photo_category,
# durch Testfall gepinnt).
HORIZON_MAX_CANDIDATE_ANGLE = 45.0

# Maximale Winkelabweichung, ab der der Score auf 0.0 geklemmt wird (ADR 0026 Punkt 2) - eine
# Linie exakt bei dieser Grenze ergibt score == 0.0 (nicht negativ, durch Testfall gepinnt).
HORIZON_MAX_PENALIZED_ANGLE_DEGREES = 15.0

# Kein Kandidat gefunden (z.B. Portrait-Nahaufnahme ohne Linienstruktur) -> neutraler, NICHT
# niedriger Fallback (ADR 0026, bewusste Abweichung von der goldener_schnitt-Praezedenz): die
# Abwesenheit einer geraden Struktur ist kein Hinweis auf eine schiefe Aufnahme - ein niedriger
# Fallback wuerde eine ganze Klasse legitimer Fotos (z.B. Portraits ohne Horizont) systematisch
# abwerten.
_NO_CANDIDATE_FALLBACK_SCORE = 0.5


def _line_angle_degrees(x1: float, y1: float, x2: float, y2: float) -> float:
    """Winkel einer Hough-Linie zur Horizontalen in Grad, normiert auf (-90, 90]. Eine
    HoughLinesP-Linie hat keine Richtung (Endpunkt-Reihenfolge (x1,y1)-(x2,y2) ist gleichwertig zu
    (x2,y2)-(x1,y1)) - der rohe atan2-Winkel wird deshalb auf eine Halbebene reduziert, bevor er
    gegen die Kandidaten-/Penalisierungsgrenzen geprueft wird."""
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    if angle > 90:
        angle -= 180
    elif angle <= -90:
        angle += 180
    return angle


def _select_dominant_candidate_angle(lines: np.ndarray | None) -> float | None:
    """Filtert die von cv2.HoughLinesP gelieferten Kandidatenlinien auf
    +-HORIZON_MAX_CANDIDATE_ANGLE und waehlt die LAENGSTE als Gewinner (ADR 0026 Punkt 2:
    "laengste Kandidatenlinie gewinnt"). `lines` hat je nach cv2-Version die Form (N, 1, 4) oder
    (N, 4) - `reshape(-1, 4)` normiert beide auf dieselbe Iteration, ohne von der genauen Form
    abzuhaengen.

    Tie-Break bei exakt gleicher Laenge (technische Detailentscheidung, von ADR 0026 bewusst offen
    gelassen - siehe specs/architecture/0002-testkonzept.md): die ZUERST in `lines` auftretende
    Linie behaelt Vorrang (striktes `>`, nicht `>=`) - macht das Ergebnis deterministisch, sobald
    `lines` feststeht, unabhaengig von einer zwischen cv2-Versionen nicht garantierten internen
    Rueckgabereihenfolge (siehe test_horizon.py::TestSelectDominantCandidateAngle fuer den
    expliziten Nachweis)."""
    if lines is None:
        return None
    best_length = -1.0
    best_angle: float | None = None
    for row in np.asarray(lines).reshape(-1, 4):
        x1, y1, x2, y2 = (float(value) for value in row)
        length = math.hypot(x2 - x1, y2 - y1)
        if length == 0:
            continue
        angle = _line_angle_degrees(x1, y1, x2, y2)
        if abs(angle) > HORIZON_MAX_CANDIDATE_ANGLE:
            continue
        if length > best_length:
            best_length = length
            best_angle = angle
    return best_angle


def _score_from_angle_deviation(angle_degrees: float) -> float:
    """`score = clip(1.0 - |Winkelabweichung| / HORIZON_MAX_PENALIZED_ANGLE_DEGREES, 0, 1)` (ADR
    0026 Punkt 2) - als eigene, pure Funktion extrahiert (analog aesthetics.py::
    compute_aesthetics_score), damit die Grenzfaelle exakt bei/jenseits
    HORIZON_MAX_PENALIZED_ANGLE_DEGREES unabhaengig von der (rasterungsbedingt nie beliebig exakt
    steuerbaren) echten Hough-Liniengeometrie gepinnt werden koennen."""
    return max(0.0, min(1.0, 1.0 - abs(angle_degrees) / HORIZON_MAX_PENALIZED_ANGLE_DEGREES))


def compute_horizon_tilt_score(image: Image.Image) -> float:
    """`horizont`-Kriterium (ADR 0026 Punkt 2): cv2.Canny + cv2.HoughLinesP auf der Graustufen-
    Variante des bereits via Pillow geladenen Bildes - lokaler cv2-Import (Modul-Kommentar oben).
    Kein Modell-Asset, kein SHA-256-Test noetig - Canny/Hough sind deterministische, klassische
    CV-Algorithmen ohne trainiertes Gewicht (CriterionSource.LOCAL_HEURISTIC, criteria.py)."""
    import cv2

    grayscale = np.asarray(image.convert("L"))
    edges = cv2.Canny(grayscale, _HORIZON_CANNY_LOW, _HORIZON_CANNY_HIGH)
    lines = cv2.HoughLinesP(
        edges,
        _HOUGH_RHO,
        _HOUGH_THETA,
        _HOUGH_THRESHOLD,
        minLineLength=_HOUGH_MIN_LINE_LENGTH,
        maxLineGap=_HOUGH_MAX_LINE_GAP,
    )
    angle = _select_dominant_candidate_angle(lines)
    if angle is None:
        return _NO_CANDIDATE_FALLBACK_SCORE
    return _score_from_angle_deviation(angle)
