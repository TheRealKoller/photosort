from __future__ import annotations

import io
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter

from photosort.scoring import (
    DUPLICATE_HAMMING_THRESHOLD,
    TIME_CLUSTER_GAP,
    DuplicateCandidate,
    TimeClusterCandidate,
    assign_duplicate_clusters,
    assign_time_clusters,
    compute_dhash,
    compute_exposure,
    compute_sharpness,
    hamming_distance,
    local_quality_score,
)


def _checkerboard(size: int = 64) -> Image.Image:
    # High-frequency content (alternating black/white squares) - a sharp reference image whose
    # Laplace-Kernel-Varianz is unambiguously higher than the same image blurred.
    image = Image.new("L", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = 255 if (x // 4 + y // 4) % 2 == 0 else 0
    return image.convert("RGB")


def _solid(color: int = 128, size: int = 64) -> Image.Image:
    return Image.new("RGB", (size, size), color=(color, color, color))


def _photo_like(size: int = 200) -> Image.Image:
    # Ein realistischeres Motiv (Verlauf + Formen statt einer harten Schwarz-Weiss-Kante alle 4
    # Pixel): ein 4px-Schachbrettmuster wird beim Downsampling auf das 9x8-dHash-Raster leicht
    # instabil (jede minimale JPEG-Verschiebung kippt viele Bits) - fuer den
    # Kompressions-Robustheitstest bewusst ein Bild ohne diese pathologische Hochfrequenz.
    image = Image.new("RGB", (size, size), color=(30, 60, 120))
    draw = ImageDraw.Draw(image)
    draw.ellipse((size * 0.2, size * 0.2, size * 0.7, size * 0.8), fill=(220, 180, 90))
    draw.rectangle((size * 0.5, size * 0.1, size * 0.9, size * 0.4), fill=(90, 200, 90))
    return image


class TestComputeSharpness:
    def test_sharp_image_has_higher_variance_than_blurred_version(self) -> None:
        sharp = _checkerboard()
        blurred = sharp.filter(ImageFilter.GaussianBlur(radius=6))

        assert compute_sharpness(sharp) > compute_sharpness(blurred)

    def test_flat_image_has_much_lower_sharpness_than_high_contrast_edges(self) -> None:
        # Nicht exakt 0.0: Pillows Kernel-Filter behaelt am Bildrand den unveraenderten
        # Originalwert (kein Zero-Padding) statt ihn zu falten - bei echten, deutlich groesseren
        # Fotos (bis 2048px Display-Cache) ist dieser 1px-Randeffekt vernachlaessigbar, bei
        # kleinen Testbildern macht er sich staerker bemerkbar. Die eigentlich relevante
        # Eigenschaft ist die relative Ordnung: eine flaeche Flaeche ist um Groessenordnungen
        # "unschaerfer" als ein hochkontrastiges Schachbrettmuster.
        assert compute_sharpness(_solid()) < compute_sharpness(_checkerboard()) * 0.1

    def test_uniform_flat_color_at_zero_has_exactly_zero_sharpness(self) -> None:
        # Randpixel behalten den Originalwert (siehe Kommentar oben) - ist dieser Wert selbst 0,
        # verschwindet der Randeffekt vollstaendig und die Varianz ist exakt 0.
        assert compute_sharpness(_solid(0)) == 0.0


class TestComputeExposure:
    def test_neutral_gray_image_has_low_exposure_fraction(self) -> None:
        assert compute_exposure(_solid(128)) == 0.0

    def test_pure_black_image_is_fully_clipped(self) -> None:
        assert compute_exposure(_solid(0)) == 1.0

    def test_pure_white_image_is_fully_clipped(self) -> None:
        assert compute_exposure(_solid(255)) == 1.0


class TestComputeDhash:
    def test_identical_images_have_zero_hamming_distance(self) -> None:
        image = _checkerboard()
        hash_a = compute_dhash(image)
        hash_b = compute_dhash(image.copy())

        assert hamming_distance(hash_a, hash_b) == 0

    def test_slightly_modified_image_has_small_hamming_distance(self) -> None:
        original = _photo_like()
        buffer = io.BytesIO()
        original.save(buffer, format="JPEG", quality=90)
        recompressed = Image.open(io.BytesIO(buffer.getvalue()))

        distance = hamming_distance(compute_dhash(original), compute_dhash(recompressed))

        assert distance <= DUPLICATE_HAMMING_THRESHOLD

    def test_different_motif_has_large_hamming_distance(self) -> None:
        checkerboard = compute_dhash(_checkerboard())
        solid = compute_dhash(_solid())

        assert hamming_distance(checkerboard, solid) > DUPLICATE_HAMMING_THRESHOLD

    def test_dhash_is_64_bit_hex_string(self) -> None:
        digest = compute_dhash(_checkerboard())

        assert len(digest) == 16  # 64 bit == 16 hex chars
        int(digest, 16)  # must be parseable as hex


class TestLocalQualityScore:
    def test_sharper_and_better_exposed_photo_scores_higher(self) -> None:
        assert local_quality_score(sharpness=100.0, exposure=0.0) > local_quality_score(
            sharpness=100.0, exposure=0.5
        )
        assert local_quality_score(sharpness=200.0, exposure=0.0) > local_quality_score(
            sharpness=100.0, exposure=0.0
        )


class TestAssignDuplicateClusters:
    def test_no_duplicates_when_hashes_are_far_apart(self) -> None:
        candidates = [
            DuplicateCandidate(photo_id=1, phash="0" * 16, sharpness=10.0),
            DuplicateCandidate(photo_id=2, phash="f" * 16, sharpness=20.0),
        ]

        assert assign_duplicate_clusters(candidates) == {}

    def test_sharper_photo_wins_within_a_cluster(self) -> None:
        candidates = [
            DuplicateCandidate(photo_id=1, phash="0000000000000000", sharpness=10.0),
            DuplicateCandidate(photo_id=2, phash="0000000000000000", sharpness=50.0),
        ]

        result = assign_duplicate_clusters(candidates)

        assert result == {1: 2}

    def test_tie_break_by_lower_photo_id(self) -> None:
        candidates = [
            DuplicateCandidate(photo_id=5, phash="0000000000000000", sharpness=30.0),
            DuplicateCandidate(photo_id=2, phash="0000000000000000", sharpness=30.0),
        ]

        result = assign_duplicate_clusters(candidates)

        assert result == {5: 2}

    def test_transitively_close_hashes_form_a_single_cluster(self) -> None:
        # a<->b within threshold, b<->c within threshold, a<->c NOT within threshold directly -
        # still one cluster via transitivity (burst sequence drifting slowly).
        candidates = [
            DuplicateCandidate(photo_id=1, phash="0000000000000000", sharpness=10.0),
            DuplicateCandidate(
                photo_id=2, phash=f"{(1 << DUPLICATE_HAMMING_THRESHOLD):016x}", sharpness=20.0
            ),
            DuplicateCandidate(
                photo_id=3,
                phash=f"{((1 << DUPLICATE_HAMMING_THRESHOLD) | (1 << (DUPLICATE_HAMMING_THRESHOLD + 5))):016x}",
                sharpness=30.0,
            ),
        ]

        result = assign_duplicate_clusters(candidates)

        assert result == {1: 3, 2: 3}


class TestAssignTimeClusters:
    def test_gap_just_under_threshold_stays_in_same_cluster(self) -> None:
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            TimeClusterCandidate(photo_id=1, taken_at=base),
            TimeClusterCandidate(photo_id=2, taken_at=base + (TIME_CLUSTER_GAP - _one_second())),
        ]

        result = assign_time_clusters(candidates)

        assert result[1] == result[2]

    def test_gap_just_over_threshold_starts_new_cluster(self) -> None:
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            TimeClusterCandidate(photo_id=1, taken_at=base),
            TimeClusterCandidate(photo_id=2, taken_at=base + (TIME_CLUSTER_GAP + _one_second())),
        ]

        result = assign_time_clusters(candidates)

        assert result[1] != result[2]

    def test_clusters_are_independent_of_input_order(self) -> None:
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            TimeClusterCandidate(photo_id=2, taken_at=base + (TIME_CLUSTER_GAP + _one_second())),
            TimeClusterCandidate(photo_id=1, taken_at=base),
        ]

        result = assign_time_clusters(candidates)

        assert result[1] != result[2]


def _one_second():
    from datetime import timedelta

    return timedelta(seconds=1)
