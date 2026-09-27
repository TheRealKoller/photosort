"""Fake-Analyzer fuer die Personen-Erkennung (testkonzept 0002, Sektion "Biometrische Merkmale
ohne echtes Modell", Punkt 1a).

Bewusst kein `test_*`-Modul (wird nicht eingesammelt): Worker- und API-Tests brauchen denselben
Fake (Muster `project_graph.py`).

Der Fake erkennt ein Bild an der Vollfarbe der GESCHRIEBENEN Display-Variante - so laeuft der echte
Lesepfad (`thumbnails.variant_path` -> `face_analysis.load_image`) mit. Er liefert nur
verwertbare Gesichter; jedes Merkmal ist ein Basisvektor (Kosinus zueinander exakt 1 bzw. nahe 0,
fern jeder Schwelle) mit einer einpraegsamen SENTINEL-Komponente, nach der danach gesucht wird.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from photosort.face_analysis import Face, FaceBox
from photosort.person_matching import EMBEDDING_DIMENSION
from photosort.thumbnails import display_path

SENTINEL = 0.0123456789
SENTINEL_TEXT = "0.0123456789"
_SENTINEL_INDEX = EMBEDDING_DIMENSION - 1

Color = tuple[int, int, int]


def face_embedding(index: int) -> list[float]:
    """Ein normiertes Merkmal entlang Achse `index`, samt Sentinel-Komponente."""
    assert index != _SENTINEL_INDEX
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[index] = math.sqrt(1.0 - SENTINEL * SENTINEL)
    vector[_SENTINEL_INDEX] = SENTINEL
    return vector


def write_display_variant(cache_dir: Path, photo_id: int, etag: str, color: Color) -> None:
    path = display_path(cache_dir, photo_id, etag)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (320, 240), color=color).save(path, format="JPEG", quality=95)


@dataclass
class FakeFaceAnalyzer:
    """`faces_by_color`: je Vollfarbe die Merkmale der Gesichter darauf, in Reihenfolge links
    nach rechts. `failing`: Farben, bei denen `detect` wirft. `shuffle`: jeder Aufruf liefert
    dieselben Gesichter in anderer Reihenfolge. `on_detect`: Haken je `detect`-Aufruf."""

    faces_by_color: Mapping[Color, Sequence[Sequence[float]]]
    failing: frozenset[Color] = frozenset()
    shuffle: bool = False
    on_detect: Callable[[Color], None] | None = None
    delay_seconds: float = 0.0
    calls: list[tuple[str, str]] = field(default_factory=list)
    spans: list[tuple[float, float]] = field(default_factory=list)
    _detect_count: int = 0

    def _color_of(self, image: NDArray[np.uint8]) -> Color:
        blue, green, red = (int(value) for value in image[0, 0])
        return min(
            self.faces_by_color if self.faces_by_color else {(red, green, blue): ()},
            key=lambda color: sum(
                abs(a - b) for a, b in zip(color, (red, green, blue), strict=True)
            ),
        )

    def _record(self, method: str) -> float:
        self.calls.append((method, threading.current_thread().name))
        return time.monotonic()

    def detect(self, image: NDArray[np.uint8]) -> list[Face]:
        started = self._record("detect")
        color = self._color_of(image)
        if self.on_detect is not None:
            self.on_detect(color)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        self.spans.append((started, time.monotonic()))
        if color in self.failing:
            raise RuntimeError("simulierter Modellfehler")
        embeddings = self.faces_by_color.get(color, ())
        faces = [
            Face(
                box=FaceBox(x=0.05 + 0.2 * index, y=0.2, width=0.15, height=0.3),
                detection=(float(index),),
            )
            for index in range(len(embeddings))
        ]
        self._detect_count += 1
        if self.shuffle and self._detect_count % 2 == 0:
            faces.reverse()
        return faces

    def embed(self, image: NDArray[np.uint8], face: Face) -> list[float]:
        self._record("embed")
        embeddings = self.faces_by_color.get(self._color_of(image), ())
        return list(embeddings[int(face.detection[0])])


class ExplodingAnalyzer:
    """Ein Analyzer, dessen blosser Aufruf den Test scheitern laesst."""

    def detect(self, image: NDArray[np.uint8]) -> list[Face]:
        raise AssertionError("Der Analyzer wurde gerufen, obwohl die Phase nicht laufen darf.")

    def embed(self, image: NDArray[np.uint8], face: Face) -> list[float]:
        raise AssertionError("Der Analyzer wurde gerufen, obwohl die Phase nicht laufen darf.")
