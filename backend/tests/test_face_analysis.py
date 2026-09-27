"""Der Adapter um YuNet/SFace.

Geprueft gegen Attrappen seiner uebergebenen Detektor- und Erkennerprotokolle: Arbeitsfassung,
Box, Klemmen, Verwertbarkeit, Obergrenze, Reihenfolge, Normierung. Die echten Modelle laufen allein
in `TestTheRealAssets`, nur mit synthetischen Bildern - kein Gesicht einer realen Person.
"""

from __future__ import annotations

import io
import math
import random
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

from photosort import person_matching
from photosort.face_analysis import (
    ANALYSIS_MAX_SIDE,
    Face,
    FaceAnalyzer,
    FaceBox,
    build_face_analyzer,
    face_crop_jpeg,
    load_image,
    order_faces,
)
from tests.conftest import RealFaceModelInTestError

USABLE_SCORE = 0.99
USABLE_SIDE = 150.0


def _row(
    x: float, y: float, width: float, height: float, *, score: float = USABLE_SCORE
) -> list[float]:
    landmarks = [x + width * 0.3, y + height * 0.4, x + width * 0.7, y + height * 0.4]
    landmarks += [x + width * 0.5, y + height * 0.6, x + width * 0.35, y + height * 0.8]
    landmarks += [x + width * 0.65, y + height * 0.8]
    return [x, y, width, height, *landmarks, score]


class RecordingDetector:
    """Liefert vorgegebene Zeilen in Koordinaten der uebergebenen Arbeitsfassung."""

    def __init__(self, rows: list[list[float]] | None = None, *, shuffle: int | None = None):
        self.rows = rows or []
        self.shuffle = shuffle
        self.input_sizes: list[tuple[int, int]] = []
        self.shapes: list[tuple[int, ...]] = []

    def setInputSize(self, input_size: tuple[int, int]) -> None:  # noqa: N802 - cv2-Protokoll
        self.input_sizes.append(input_size)

    def detect(self, image: NDArray[np.uint8]) -> tuple[int, NDArray[np.float64] | None]:
        self.shapes.append(image.shape)
        rows = list(self.rows)
        if self.shuffle is not None:
            random.Random(self.shuffle).shuffle(rows)
        if not rows:
            return 1, None
        # float64, damit "genau auf der Schwelle" darstellbar bleibt; YuNet selbst liefert float32.
        return 1, np.array(rows, dtype=np.float64)


class FractionDetector(RecordingDetector):
    """Ein Gesicht, dessen Groesse ein fester Anteil der uebergebenen Arbeitsfassung ist."""

    def __init__(self, fraction: float) -> None:
        super().__init__()
        self.fraction = fraction

    def detect(self, image: NDArray[np.uint8]) -> tuple[int, NDArray[np.float64] | None]:
        height, width = image.shape[:2]
        self.rows = [_row(10.0, 10.0, width * self.fraction, height * self.fraction)]
        return super().detect(image)


class RecordingRecognizer:
    def __init__(self, feature: list[float] | None = None) -> None:
        self.feature_values = feature or [3.0, 4.0] + [0.0] * 126
        self.aligned_rows: list[list[float]] = []
        self.aligned_shapes: list[tuple[int, ...]] = []

    def alignCrop(  # noqa: N802 - cv2-Protokoll
        self, src_img: NDArray[np.uint8], face_box: NDArray[np.float32]
    ) -> NDArray[np.uint8]:
        self.aligned_shapes.append(src_img.shape)
        self.aligned_rows.append([float(value) for value in np.asarray(face_box).reshape(-1)])
        return np.zeros((112, 112, 3), dtype=np.uint8)

    def feature(self, aligned_img: NDArray[np.uint8]) -> NDArray[np.float32]:
        return np.array([self.feature_values], dtype=np.float32)


def _image(width: int, height: int) -> NDArray[np.uint8]:
    return np.zeros((height, width, 3), dtype=np.uint8)


class TestTheWorkingVersion:
    def test_a_large_image_is_reduced_to_the_maximum_side(self) -> None:
        detector = RecordingDetector()
        FaceAnalyzer(detector, RecordingRecognizer()).detect(_image(2560, 1440))

        assert detector.shapes == [(720, ANALYSIS_MAX_SIDE, 3)]
        assert detector.input_sizes == [(ANALYSIS_MAX_SIDE, 720)]

    def test_a_small_image_is_never_enlarged(self) -> None:
        detector = RecordingDetector()
        FaceAnalyzer(detector, RecordingRecognizer()).detect(_image(640, 480))

        assert detector.shapes == [(480, 640, 3)]
        assert detector.input_sizes == [(640, 480)]

    def test_the_embedding_is_computed_on_the_same_working_version(self) -> None:
        recognizer = RecordingRecognizer()
        analyzer = FaceAnalyzer(RecordingDetector([_row(100, 100, 200, 200)]), recognizer)
        image = _image(2560, 1440)
        [face] = analyzer.detect(image)

        analyzer.embed(image, face)

        assert recognizer.aligned_shapes == [(720, ANALYSIS_MAX_SIDE, 3)]


class TestTheBox:
    def test_the_box_is_normalised_to_the_image(self) -> None:
        analyzer = FaceAnalyzer(
            RecordingDetector([_row(100, 200, 200, 160)]), RecordingRecognizer()
        )

        [face] = analyzer.detect(_image(1000, 800))

        assert face.box == FaceBox(x=0.1, y=0.25, width=0.2, height=0.2)

    def test_the_box_is_clamped_to_the_image(self) -> None:
        analyzer = FaceAnalyzer(
            RecordingDetector([_row(-50, 700, 200, 200)]), RecordingRecognizer()
        )

        [face] = analyzer.detect(_image(1000, 800))

        assert face.box.x == 0.0
        assert face.box.width == pytest.approx(0.15)
        assert face.box.y == pytest.approx(0.875)
        assert face.box.y + face.box.height == pytest.approx(1.0)


class TestTheEmbedding:
    def test_the_embedding_is_l2_normalised(self) -> None:
        analyzer = FaceAnalyzer(RecordingDetector([_row(0, 0, 200, 200)]), RecordingRecognizer())
        image = _image(640, 480)
        [face] = analyzer.detect(image)

        embedding = analyzer.embed(image, face)

        assert embedding[:2] == pytest.approx([0.6, 0.8])
        assert math.fsum(value * value for value in embedding) == pytest.approx(1.0)

    def test_the_full_detection_row_with_landmarks_goes_to_the_alignment(self) -> None:
        row = _row(20, 30, 200, 220, score=0.95)
        recognizer = RecordingRecognizer()
        analyzer = FaceAnalyzer(RecordingDetector([row]), recognizer)
        image = _image(640, 480)
        [face] = analyzer.detect(image)

        analyzer.embed(image, face)

        assert recognizer.aligned_rows == [pytest.approx(row)]


class TestUsability:
    def test_exactly_the_minimum_score_is_usable_just_below_is_not(self) -> None:
        minimum = person_matching.MIN_DETECTION_SCORE
        below = math.nextafter(minimum, 0.0)
        rows = [_row(0, 0, 200, 200, score=minimum), _row(400, 0, 200, 200, score=below)]

        faces = FaceAnalyzer(RecordingDetector(rows), RecordingRecognizer()).detect(
            _image(1000, 800)
        )

        assert [face.box.x for face in faces] == [0.0]

    def test_exactly_the_minimum_side_is_usable_just_below_is_not(self) -> None:
        side = float(person_matching.MIN_FACE_SIDE_PX)
        rows = [_row(0, 0, side, side + 50), _row(400, 0, side + 50, side - 0.5)]

        faces = FaceAnalyzer(RecordingDetector(rows), RecordingRecognizer()).detect(
            _image(1000, 800)
        )

        assert [face.box.x for face in faces] == [0.0]

    def test_the_shorter_side_in_the_working_version_decides(self) -> None:
        """168 px im Original, 89,6 px in der Arbeitsfassung - unverwertbar."""
        fraction = 0.07
        original = FaceAnalyzer(FractionDetector(fraction), RecordingRecognizer())
        small = FaceAnalyzer(FractionDetector(fraction * 2), RecordingRecognizer())

        assert original.detect(_image(2400, 2400)) == []
        assert len(small.detect(_image(2400, 2400))) == 1


class TestTheCap:
    def test_twenty_five_usable_faces_give_the_twenty_largest(self) -> None:
        rows = [_row(40.0 * index, 0, 100 + index, 100 + index) for index in range(25)]

        faces = FaceAnalyzer(RecordingDetector(rows), RecordingRecognizer()).detect(
            _image(1280, 1000)
        )

        assert len(faces) == person_matching.MAX_FACES_PER_PHOTO
        assert sorted(round(face.box.width * 1280) for face in faces) == list(range(105, 125))

    def test_the_cap_applies_after_the_usability_filter(self) -> None:
        rows = [
            _row(40.0 * index, 0, 100 + index, 100 + index, score=0.5 if index >= 15 else 0.99)
            for index in range(25)
        ]

        faces = FaceAnalyzer(RecordingDetector(rows), RecordingRecognizer()).detect(
            _image(1280, 1000)
        )

        assert len(faces) == 15


class TestTheOrder:
    def test_left_to_right_then_top_to_bottom(self) -> None:
        rows = [_row(500, 0, 150, 150), _row(100, 400, 150, 150), _row(100, 0, 150, 150)]

        faces = FaceAnalyzer(RecordingDetector(rows), RecordingRecognizer()).detect(
            _image(1000, 800)
        )

        assert [(face.box.x, face.box.y) for face in faces] == [(0.1, 0.0), (0.1, 0.5), (0.5, 0.0)]

    def test_the_order_is_total_for_two_faces_at_the_same_position(self) -> None:
        rows = [_row(100, 100, 200, 200), _row(100, 100, 150, 150)]

        forward = FaceAnalyzer(RecordingDetector(rows), RecordingRecognizer()).detect(
            _image(1000, 800)
        )
        backward = FaceAnalyzer(RecordingDetector(rows[::-1]), RecordingRecognizer()).detect(
            _image(1000, 800)
        )

        assert forward == backward
        assert forward[0] != forward[1]

    @pytest.mark.parametrize("seed", range(5))
    def test_a_shuffled_detector_output_gives_the_same_list(self, seed: int) -> None:
        rows = [_row(100.0 * (index % 7), 150.0 * (index // 7), 110, 110) for index in range(12)]
        reference = FaceAnalyzer(RecordingDetector(rows), RecordingRecognizer()).detect(
            _image(1280, 1000)
        )

        shuffled = FaceAnalyzer(RecordingDetector(rows, shuffle=seed), RecordingRecognizer())

        assert shuffled.detect(_image(1280, 1000)) == reference

    def test_order_faces_is_idempotent_and_caps(self) -> None:
        faces = [
            Face(box=FaceBox(x=0.01 * index, y=0.0, width=0.1, height=0.1), detection=(index,))
            for index in range(30)
        ]

        ordered = order_faces(faces[::-1])

        assert len(ordered) == person_matching.MAX_FACES_PER_PHOTO
        assert order_faces(ordered) == ordered


class TestImageIo:
    def test_load_image_gives_a_bgr_array(self, tmp_path: Path) -> None:
        path = tmp_path / "display.jpg"
        Image.new("RGB", (40, 30), color=(250, 0, 0)).save(path, format="PNG")

        image = load_image(path)

        assert image is not None
        assert image.shape == (30, 40, 3)
        assert tuple(int(value) for value in image[0, 0]) == (0, 0, 250)

    def test_load_image_of_a_missing_or_broken_file_is_none(self, tmp_path: Path) -> None:
        broken = tmp_path / "kaputt.jpg"
        broken.write_bytes(b"kein bild")

        assert load_image(tmp_path / "fehlt.jpg") is None
        assert load_image(broken) is None

    def test_the_crop_is_a_freshly_encoded_jpeg_within_the_image(self) -> None:
        image = np.full((400, 600, 3), 200, dtype=np.uint8)
        face = Face(box=FaceBox(x=0.9, y=0.9, width=0.1, height=0.1), detection=())

        encoded = face_crop_jpeg(image, face)

        with Image.open(io.BytesIO(encoded)) as crop:
            assert crop.format == "JPEG"
            assert 0 < crop.width <= 160
            assert 0 < crop.height <= 160


class TestTheBuilderIsLockedInTests:
    def test_building_the_real_analyzer_hits_the_lock(self) -> None:
        with pytest.raises(RealFaceModelInTestError):
            build_face_analyzer()


@pytest.mark.real_face_models
class TestTheRealAssets:
    """Die einzige Klasse mit den echten Modellen - ausschliesslich synthetische Bilder. Sie belegt
    die Verdrahtung gegen die installierte OpenCV-Version, nicht, dass Gesichter erkannt werden."""

    def test_an_empty_image_gives_no_face(self) -> None:
        analyzer = build_face_analyzer()

        assert analyzer.detect(_image(640, 480)) == []

    def test_a_hand_set_detection_row_gives_a_finite_normalised_embedding(self) -> None:
        analyzer = build_face_analyzer()
        image = np.random.default_rng(7).integers(0, 255, (480, 640, 3), dtype=np.uint8)
        row = _row(200, 150, 200, 220)
        face = Face(box=FaceBox(x=0.3, y=0.3, width=0.3, height=0.4), detection=tuple(row))

        embedding = analyzer.embed(image, face)

        assert len(embedding) == person_matching.EMBEDDING_DIMENSION
        assert all(math.isfinite(value) for value in embedding)
        assert math.fsum(value * value for value in embedding) == pytest.approx(1.0)
