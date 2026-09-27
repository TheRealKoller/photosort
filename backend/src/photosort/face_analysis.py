"""YuNet (Detektion) und SFace (Merkmal) ueber OpenCV - die einzige Stelle mit beiden Modellen.

Der Adapter `FaceAnalyzer` bekommt Detektor und Erkenner uebergeben (schmale Protokolle), damit
Arbeitsfassung, Box, Klemmen, Verwertbarkeit, Obergrenze und Reihenfolge ohne Modell pruefbar
sind. `build_face_analyzer()` baut ihn mit den echten Modellen und laeuft in keinem Test ausser der
markierten Klasse gegen die echten Assets.

IMPORTREGEL (ADR 0126 Punkt 1): weder `models` noch `db` noch `config`, damit der vollstaendige
Importgraph keinen Netzwerk-Client enthaelt. Aus dem Manifest kennt dieses Modul nur Dateinamen,
keine Bezugsadresse; es laedt nie selbst.

DATENSCHUTZ: Merkmale, Boxen und Aehnlichkeiten leben nur waehrend der Verarbeitung eines Fotos
im Speicher. Nichts hier schreibt, protokolliert oder gibt sie ueber diese Rueckgabewerte hinaus.
Bild-I/O laeuft ueber Pillow, nie ueber `cv2.imread`/`cv2.imencode`.
"""

from __future__ import annotations

import io
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from photosort.model_assets import ASSETS_DIR, FACE_DETECTOR, FACE_RECOGNIZER
from photosort.person_matching import MAX_FACES_PER_PHOTO, MIN_DETECTION_SCORE, is_usable

# Lange Kante der Arbeitsfassung. YuNet wird bei grossen Gesichtern ungenau, und verrutschte
# Landmarken verfaelschen das Merkmal. Nie vergroessert.
ANALYSIS_MAX_SIDE = 1280
# Kennt das Modell, das die gespeicherten Merkmale gebildet hat. Referenzen eines anderen Werts
# gehen in keinen Vergleich ein.
MODEL_KEY = "sface_2021dec"

_YUNET_NMS_THRESHOLD = 0.3
_YUNET_TOP_K = 5000
_CROP_MARGIN = 0.2
_CROP_MAX_SIDE = 160
_CROP_JPEG_QUALITY = 88

Image8 = NDArray[np.uint8]


@dataclass(frozen=True)
class FaceBox:
    """Auf das Bild normiert (0..1) und an seine Grenzen geklemmt."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class Face:
    box: FaceBox
    # Die volle Detektorzeile in Koordinaten der Arbeitsfassung: Box, fuenf Landmarken, Wert.
    detection: tuple[float, ...]


class FaceDetectorModel(Protocol):
    def setInputSize(self, input_size: tuple[int, int]) -> None: ...  # noqa: N802

    def detect(self, image: Image8) -> tuple[int, NDArray[Any] | None]: ...


class FaceRecognizerModel(Protocol):
    def alignCrop(self, src_img: Image8, face_box: NDArray[Any]) -> Image8: ...  # noqa: N802

    def feature(self, aligned_img: Image8) -> NDArray[Any]: ...


class FaceAnalyzerLike(Protocol):
    def detect(self, image: Image8) -> list[Face]: ...

    def embed(self, image: Image8, face: Face) -> list[float]: ...


def working_image(image: Image8) -> Image8:
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= ANALYSIS_MAX_SIDE:
        return image
    import cv2

    scale = ANALYSIS_MAX_SIDE / longest
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    resized = np.asarray(cv2.resize(image, size, interpolation=cv2.INTER_AREA), dtype=np.uint8)
    return resized


def _position_key(face: Face) -> tuple[Any, ...]:
    box = face.box
    return (box.x, box.y, box.width, box.height, face.detection)


def order_faces(faces: Sequence[Face]) -> list[Face]:
    """Hoechstens `MAX_FACES_PER_PHOTO`, die groessten (bei Gleichstand nach Position), dann von
    links nach rechts und oben nach unten. Die Sortierung ist total - der Index eines Gesichts
    zeigt bei gleicher Datei immer auf dasselbe Gesicht, auch wenn der Detektor seine Ausgabe
    anders ordnet. Wer ueber einen Index adressiert, ordnet mit dieser Funktion."""
    largest = sorted(
        faces, key=lambda face: (-(face.box.width * face.box.height), _position_key(face))
    )
    return sorted(largest[:MAX_FACES_PER_PHOTO], key=_position_key)


def _clamped_box(
    x: float, y: float, width: float, height: float, image_width: int, image_height: int
) -> FaceBox:
    left = min(max(x, 0.0), float(image_width))
    top = min(max(y, 0.0), float(image_height))
    right = min(max(x + width, left), float(image_width))
    bottom = min(max(y + height, top), float(image_height))
    return FaceBox(
        x=left / image_width,
        y=top / image_height,
        width=(right - left) / image_width,
        height=(bottom - top) / image_height,
    )


class FaceAnalyzer:
    """`cv2`-Objekte sind nicht threadsicher: Ein Adapter wird je Prozess von genau einem Thread
    benutzt (API: eigener Ein-Thread-Executor; Worker: der Job selbst)."""

    def __init__(self, detector: FaceDetectorModel, recognizer: FaceRecognizerModel) -> None:
        self._detector = detector
        self._recognizer = recognizer

    def detect(self, image: Image8) -> list[Face]:
        work = working_image(image)
        height, width = work.shape[:2]
        self._detector.setInputSize((width, height))
        _, rows = self._detector.detect(work)
        faces: list[Face] = []
        for raw in [] if rows is None else np.asarray(rows).reshape(-1, 15):
            row = tuple(float(value) for value in raw)
            x, y, face_width, face_height, score = row[0], row[1], row[2], row[3], row[14]
            if not is_usable(score=score, width=face_width, height=face_height):
                continue
            box = _clamped_box(x, y, face_width, face_height, width, height)
            faces.append(Face(box=box, detection=row))
        return order_faces(faces)

    def embed(self, image: Image8, face: Face) -> list[float]:
        """Das L2-normierte Merkmal. Ausgerichtet wird immer ueber `alignCrop` mit der vollen
        Detektorzeile samt fuenf Landmarken, auf derselben Arbeitsfassung wie die Detektion. Ein
        entartetes Merkmal (Norm 0, nicht endlich) kommt unnormiert zurueck und scheitert an
        `person_matching.validated_embedding`."""
        work = working_image(image)
        aligned = self._recognizer.alignCrop(work, np.asarray(face.detection, dtype=np.float32))
        vector = [float(value) for value in np.asarray(self._recognizer.feature(aligned)).ravel()]
        norm = math.sqrt(math.fsum(value * value for value in vector))
        if not (norm > 0.0 and math.isfinite(norm)):
            return vector
        return [value / norm for value in vector]


def load_image(path: Path) -> Image8 | None:
    """Die Display-Variante als BGR-Feld (Farbfolge von OpenCV), oder `None`, wenn die Datei
    fehlt oder nicht lesbar ist."""
    try:
        with Image.open(path) as opened:
            rgb = opened.convert("RGB")
    except (OSError, ValueError):
        return None
    array: Image8 = np.ascontiguousarray(np.asarray(rgb, dtype=np.uint8)[:, :, ::-1])
    return array


def face_crop_jpeg(image: Image8, face: Face) -> bytes:
    """Der Ausschnitt eines Gesichts als neu codiertes JPEG, hoechstens 160 px. Die Box wird mit
    etwas Rand an die Bildgrenzen geklemmt, bevor zugeschnitten wird."""
    height, width = image.shape[:2]
    box = face.box
    margin_x = box.width * _CROP_MARGIN
    margin_y = box.height * _CROP_MARGIN
    left = max(0, math.floor((box.x - margin_x) * width))
    top = max(0, math.floor((box.y - margin_y) * height))
    right = min(width, math.ceil((box.x + box.width + margin_x) * width))
    bottom = min(height, math.ceil((box.y + box.height + margin_y) * height))
    right = max(right, min(width, left + 1))
    bottom = max(bottom, min(height, top + 1))
    crop = Image.fromarray(np.ascontiguousarray(image[top:bottom, left:right, ::-1]))
    crop.thumbnail((_CROP_MAX_SIDE, _CROP_MAX_SIDE))
    buffer = io.BytesIO()
    crop.save(buffer, format="JPEG", quality=_CROP_JPEG_QUALITY)
    return buffer.getvalue()


def build_face_analyzer() -> FaceAnalyzerLike:
    """Baut den Adapter mit den echten Modellen aus `assets/`. Laeuft in keinem Test ausser der
    markierten Klasse gegen die echten Assets; ein Fehlschlag laesst beim Aufrufer nur die
    Personen-Erkennung entfallen."""
    import cv2

    detector = cv2.FaceDetectorYN.create(
        str(ASSETS_DIR / FACE_DETECTOR.filename),
        "",
        (320, 320),
        MIN_DETECTION_SCORE,
        _YUNET_NMS_THRESHOLD,
        _YUNET_TOP_K,
    )
    recognizer = cv2.FaceRecognizerSF.create(str(ASSETS_DIR / FACE_RECOGNIZER.filename), "")
    # Die cv2-Stubs typisieren Bildargumente breiter als die schmalen Protokolle hier.
    analyzer: FaceAnalyzerLike = FaceAnalyzer(detector, cast(FaceRecognizerModel, recognizer))
    return analyzer
