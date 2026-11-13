from __future__ import annotations

import io
import random
from datetime import datetime, timedelta
from itertools import permutations

import pytest
from PIL import Image, ImageDraw, ImageFilter

from photosort.scoring import (
    DUPLICATE_CANDIDATE_BANDS,
    DUPLICATE_CANDIDATE_HAMMING,
    DUPLICATE_SIMILAR_FINE_HAMMING,
    DUPLICATE_SIMILAR_HAMMING,
    DUPLICATE_SIMILAR_TIME_WINDOW,
    GPS_CLUSTER_SPLIT_DISTANCE_METERS,
    IDENTICAL_FINE_HAMMING,
    TIME_CLUSTER_GAP,
    ClusterCandidate,
    DuplicateAssignment,
    PhotoFingerprint,
    assign_clusters,
    assign_duplicate_groups,
    candidate_pairs,
    compute_dhash,
    compute_exposure,
    compute_fine_dhash,
    compute_gray_grid,
    compute_sharpness,
    haversine_meters,
    is_practically_identical,
    is_similar,
    taken_at_is_trusted,
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


def _motif(index: int, size: int = 200) -> Image.Image:
    """Ein eigenstaendiges Motiv - fuer Bestaende, in denen nur die gesetzten Paare Duplikate
    sind. Zufaellige Formen je Index statt einer Familie aus einem Bild."""
    rng = random.Random(index)
    image = Image.new("RGB", (size, size), color=(30, 60, 120))
    draw = ImageDraw.Draw(image)
    for _ in range(10):
        x0 = rng.randrange(size)
        y0 = rng.randrange(size)
        draw.ellipse(
            (x0, y0, x0 + rng.randrange(20, 80), y0 + rng.randrange(20, 80)),
            fill=(rng.randrange(256), rng.randrange(256), rng.randrange(256)),
        )
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


def _hamming(left: str, right: str) -> int:
    """Die Bit-Distanz zweier hex-codierter Hashes - im Test, weil `scoring.py` sie nicht mehr
    anbietet."""
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _mask(bits: int) -> int:
    """Eine Bitfolge mit genau `bits` gesetzten niederwertigen Bits."""
    return (1 << bits) - 1


def _resaved(image: Image.Image, quality: int = 90) -> Image.Image:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return Image.open(io.BytesIO(buffer.getvalue()))


def _resized(image: Image.Image, factor: float = 0.5) -> Image.Image:
    size = (int(image.width * factor), int(image.height * factor))
    return image.resize(size, Image.Resampling.LANCZOS)


def _as_png(image: Image.Image) -> Image.Image:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Image.open(io.BytesIO(buffer.getvalue()))


def _shifted_crop(image: Image.Image, fraction: float = 0.02) -> Image.Image:
    """Derselbe Ausschnitt, um rund zwei Prozent verschoben - der Fall, den die alte Schwelle
    nicht von einer Kopie trennte."""
    shift_x = max(1, int(image.width * fraction))
    shift_y = max(1, int(image.height * fraction))
    return image.crop((shift_x, shift_y, image.width - shift_x, image.height - shift_y)).resize(
        image.size, Image.Resampling.LANCZOS
    )


_BASE_TIME = datetime(2023, 1, 1, 10, 0, 0)
_MINUTE = timedelta(minutes=1)


def _fingerprint(
    photo_id: int,
    image: Image.Image,
    *,
    sharpness: float | None = None,
    taken_at: datetime | None = None,
    taken_at_trusted: bool = True,
    phash: int | None = None,
    fine_phash: int | None = None,
    gray_grid: bytes | None = None,
    pixel_count: int | None = -1,
) -> PhotoFingerprint:
    """Ein Fingerabdruck aus einem BILD: die Signaturen kommen aus den Produktionsfunktionen.

    `phash`, `fine_phash` und `gray_grid` ueberschreiben nur dort, wo ein Test eine BIT-Grenze
    exakt treffen muss - auf ein bestimmtes Bit laesst sich kein Bild zielen."""
    return PhotoFingerprint(
        photo_id=photo_id,
        phash=int(compute_dhash(image), 16) if phash is None else phash,
        fine_phash=compute_fine_dhash(image) if fine_phash is None else fine_phash,
        gray_grid=compute_gray_grid(image) if gray_grid is None else gray_grid,
        sharpness=compute_sharpness(image) if sharpness is None else sharpness,
        taken_at=taken_at,
        taken_at_trusted=taken_at_trusted,
        # Ohne Angabe die Groesse des Testbildes: der haeufigste Fall ist eine echte Kopie
        # gleicher Aufloesung. `-1` heisst "nicht angegeben"; `None` bleibt der echte
        # Unbekannt-Zustand.
        pixel_count=(image.width * image.height if pixel_count == -1 else pixel_count),
    )


def _signature(
    photo_id: int,
    *,
    phash: int,
    fine_phash: int,
    sharpness: float,
    taken_at: datetime | None,
    taken_at_trusted: bool = True,
    pixel_count: int | None = None,
    gray_grid: bytes | None = None,
) -> PhotoFingerprint:
    """Ein Fingerabdruck mit GESETZTEN Bits - fuer den Stern und die Stufen, deren Gegenstand die
    Bit-Lage ist.

    Das Gitter unterscheidet sich standardmaessig JE ID (`bytes([photo_id])`), damit die Paare
    "aehnlich" und nicht "praktisch identisch" sind: Der Stern-Gegenstand ist die Bit-Lage, und
    seit Druchgang 1 (Spec 0639) entscheidet bei identischen Paaren die Aufloesung statt der
    Schaerfe. Wer ein identisches Paar braucht, gibt `gray_grid=bytes(1024)` explizit an."""
    return PhotoFingerprint(
        photo_id=photo_id,
        phash=phash,
        fine_phash=fine_phash,
        gray_grid=bytes(((photo_id * 37) % 256,)) * 1024 if gray_grid is None else gray_grid,
        sharpness=sharpness,
        taken_at=taken_at,
        taken_at_trusted=taken_at_trusted,
        pixel_count=pixel_count,
    )


class TestComputeDhash:
    def test_identical_images_have_zero_hamming_distance(self) -> None:
        image = _checkerboard()

        assert _hamming(compute_dhash(image), compute_dhash(image.copy())) == 0

    def test_slightly_modified_image_stays_in_the_candidate_net(self) -> None:
        original = _photo_like()

        distance = _hamming(compute_dhash(original), compute_dhash(_resaved(original)))

        assert distance <= DUPLICATE_CANDIDATE_HAMMING

    def test_different_motif_lies_outside_the_candidate_net(self) -> None:
        checkerboard = compute_dhash(_checkerboard())
        solid = compute_dhash(_solid())

        assert _hamming(checkerboard, solid) > DUPLICATE_CANDIDATE_HAMMING

    def test_dhash_is_64_bit_hex_string(self) -> None:
        digest = compute_dhash(_checkerboard())

        assert len(digest) == 16  # 64 bit == 16 hex chars
        int(digest, 16)  # must be parseable as hex


class TestTheFineSignature:
    def test_the_fine_dhash_uses_256_bits(self) -> None:
        fine = compute_fine_dhash(_checkerboard())

        assert fine.bit_length() <= 256
        assert compute_fine_dhash(_checkerboard()) == fine

    def test_the_gray_grid_is_a_32_by_32_byte_raster(self) -> None:
        assert len(compute_gray_grid(_photo_like())) == 32 * 32


class TestPracticallyIdenticalCopies:
    @pytest.mark.parametrize(
        "copy_form", ["bytegleich", "neu gespeichert", "verkleinert", "anderes Format"]
    )
    def test_a_copy_in_every_form_is_grouped_without_any_time(self, copy_form: str) -> None:
        # AK2: zeitunabhaengig, und ohne Aufnahmezeit erst recht. Die vier Kopieformen sind die
        # vier Wege, auf denen dasselbe Bild zweimal im Bestand landet.
        original = _photo_like()
        copies = {
            "bytegleich": original.copy(),
            "neu gespeichert": _resaved(original),
            "verkleinert": _resized(original),
            "anderes Format": _as_png(original),
        }
        base = _fingerprint(1, original, sharpness=10.0, taken_at=None, taken_at_trusted=False)
        copy = _fingerprint(
            2, copies[copy_form], sharpness=50.0, taken_at=None, taken_at_trusted=False
        )

        assert is_practically_identical(base, copy)
        # Die RICHTUNG ist seit Druchgang 1 eine Frage der Aufloesung/Zeit/Id, nicht der
        # Schaerfe. Der Gegenstand dieses Falls ist allein, DASS die Kopie gruppiert wird - und
        # zwar ohne jede Aufnahmezeit.
        assignment = assign_duplicate_groups([base, copy])
        assert len(assignment.duplicate_of) == 1
        assert {frozenset(pair) for pair in assignment.duplicate_of.items()} == {frozenset((1, 2))}

    def test_a_shifted_crop_is_a_candidate_but_not_identical(self) -> None:
        # AK3: eine Serienaufnahme mit leicht verschobenem Ausschnitt ist Kandidat der Stufe 1,
        # aber keine Kopie - die z-Normierung entfernt keine geometrische Verschiebung.
        original = _photo_like()
        base = _fingerprint(1, original)
        crop = _fingerprint(2, _shifted_crop(original))

        assert (base.phash ^ crop.phash).bit_count() <= DUPLICATE_CANDIDATE_HAMMING
        assert (base.fine_phash ^ crop.fine_phash).bit_count() > IDENTICAL_FINE_HAMMING
        assert not is_practically_identical(base, crop)


class TestSimilarImagesOnlyInsideTheWindow:
    def test_exactly_on_the_window_is_similar_and_one_second_beyond_is_not(self) -> None:
        original = _photo_like()
        shifted = _shifted_crop(original)
        base = _fingerprint(1, original, taken_at=_BASE_TIME)
        on_window = _fingerprint(2, shifted, taken_at=_BASE_TIME + DUPLICATE_SIMILAR_TIME_WINDOW)
        beyond = _fingerprint(
            3, shifted, taken_at=_BASE_TIME + DUPLICATE_SIMILAR_TIME_WINDOW + timedelta(seconds=1)
        )

        assert is_similar(base, on_window)
        assert not is_similar(base, beyond)
        assert len(assign_duplicate_groups([base, on_window]).duplicate_of) == 1
        assert assign_duplicate_groups([base, beyond]).duplicate_of == {}

    def test_the_similar_thresholds_are_the_module_constants(self) -> None:
        # Jede Grenze kommt aus der Konstanten: ein Bit ueber der groben Grenze traegt nicht mehr.
        base = _signature(1, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME)
        on_coarse = _signature(
            2,
            phash=_mask(DUPLICATE_SIMILAR_HAMMING),
            fine_phash=DUPLICATE_SIMILAR_FINE_HAMMING,
            sharpness=10.0,
            taken_at=_BASE_TIME + _MINUTE,
        )
        beyond = _signature(
            3,
            phash=_mask(DUPLICATE_SIMILAR_HAMMING + 1),
            fine_phash=0,
            sharpness=10.0,
            taken_at=_BASE_TIME + _MINUTE,
        )

        assert is_similar(base, on_coarse)
        assert not is_similar(base, beyond)


class TestATimeWithoutProvenance:
    def test_an_untrusted_time_never_connects_similar_images(self) -> None:
        # S10/AK5: ohne verlaessliche Aufnahmezeit ist nur "praktisch identisch" eine Kante.
        base = _fingerprint(1, _photo_like(), taken_at=_BASE_TIME)
        other = _fingerprint(
            2,
            _shifted_crop(_photo_like()),
            taken_at=_BASE_TIME + _MINUTE,
            taken_at_trusted=False,
        )

        assert not is_similar(base, other)
        assert assign_duplicate_groups([base, other]).duplicate_of == {}

    def test_an_identical_copy_is_grouped_without_a_trusted_time(self) -> None:
        original = _photo_like()
        base = _fingerprint(1, original, sharpness=10.0, taken_at=None, taken_at_trusted=False)
        copy = _fingerprint(
            2, _resaved(original), sharpness=50.0, taken_at=None, taken_at_trusted=False
        )

        assignment = assign_duplicate_groups([base, copy])
        assert len(assignment.duplicate_of) == 1
        assert {frozenset(pair) for pair in assignment.duplicate_of.items()} == {frozenset((1, 2))}


class TestTakenAtIsTrusted:
    def test_a_derived_time_is_recognised_by_exact_equality(self) -> None:
        moment = datetime(2023, 1, 1, 10, 0, 0)

        assert not taken_at_is_trusted(moment, moment)
        assert taken_at_is_trusted(moment, moment + timedelta(seconds=1))


class TestTheCandidateStageIsExact:
    @pytest.mark.parametrize("distance", list(range(DUPLICATE_CANDIDATE_HAMMING + 2)))
    def test_every_pair_on_and_below_the_boundary_is_found_and_none_above(
        self, distance: int
    ) -> None:
        base = _signature(1, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME)
        other = _signature(
            2, phash=_mask(distance), fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME
        )

        pairs = candidate_pairs([base, other])

        assert ((1, 2) in pairs) is (distance <= DUPLICATE_CANDIDATE_HAMMING)

    def test_the_pigeonhole_guarantee_holds_across_all_bands(self) -> None:
        # 13 disjunkte Baender ueber 64 Bit: ein gesetztes Bit JE Band (hier alle fuenf
        # Bit-Schritte) laesst bei zwoelf gesetzten Bits genau ein Band frei und muss gefunden
        # werden; bei dreizehn stimmt kein Band mehr exakt ueberein.
        band_bits = list(range(0, 64, 5))
        base = _signature(1, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME)
        twelve = _signature(
            2,
            phash=sum(1 << offset for offset in band_bits[: DUPLICATE_CANDIDATE_BANDS - 1]),
            fine_phash=0,
            sharpness=10.0,
            taken_at=_BASE_TIME,
        )
        thirteen = _signature(
            3,
            phash=sum(1 << offset for offset in band_bits[:DUPLICATE_CANDIDATE_BANDS]),
            fine_phash=0,
            sharpness=10.0,
            taken_at=_BASE_TIME,
        )

        assert (1, 2) in candidate_pairs([base, twelve])
        assert (1, 3) not in candidate_pairs([base, thirteen])

    def test_a_pair_found_in_several_bands_is_reported_once(self) -> None:
        base = _signature(1, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME)
        same = _signature(2, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME)

        assert candidate_pairs([base, same]) == {(1, 2)}


class TestAssignDuplicateGroups:
    def test_an_empty_input_and_a_single_photo_yield_no_group(self) -> None:
        single = _signature(1, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME)

        assert assign_duplicate_groups([]).duplicate_of == {}
        assert assign_duplicate_groups([single]).duplicate_of == {}

    def test_the_sharpest_photo_wins_and_equal_sharpness_falls_to_the_lower_id(self) -> None:
        sharp = _signature(1, phash=0, fine_phash=0, sharpness=50.0, taken_at=_BASE_TIME)
        soft = _signature(2, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME)

        assert assign_duplicate_groups([soft, sharp]).duplicate_of == {2: 1}

        left = _signature(5, phash=0, fine_phash=0, sharpness=30.0, taken_at=_BASE_TIME)
        right = _signature(2, phash=0, fine_phash=0, sharpness=30.0, taken_at=_BASE_TIME)

        assert assign_duplicate_groups([left, right]).duplicate_of == {5: 2}

    def test_the_result_is_independent_of_the_input_order(self) -> None:
        photos = [
            _signature(1, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME),
            _signature(
                2, phash=_mask(8), fine_phash=_mask(20), sharpness=20.0, taken_at=_BASE_TIME
            ),
            _signature(
                3, phash=_mask(16), fine_phash=_mask(40), sharpness=30.0, taken_at=_BASE_TIME
            ),
        ]

        assert all(
            assign_duplicate_groups(list(order)).duplicate_of == {2: 3}
            for order in permutations(photos)
        )

    def test_a_chain_member_without_a_direct_edge_to_the_winner_stays_ungrouped(self) -> None:
        # AK4/S4: A~B und B~C, aber A~C nicht - B haengt am Gewinner C, A nur an B. A bleibt
        # Einzelfoto; die Kette verbindet nichts.
        first = _signature(1, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME)
        middle = _signature(
            2, phash=_mask(8), fine_phash=_mask(20), sharpness=20.0, taken_at=_BASE_TIME + _MINUTE
        )
        last = _signature(
            3,
            phash=_mask(16),
            fine_phash=_mask(40),
            sharpness=30.0,
            taken_at=_BASE_TIME + 2 * _MINUTE,
        )

        assert is_similar(first, middle)
        assert is_similar(middle, last)
        assert not is_similar(first, last)
        assert assign_duplicate_groups([first, middle, last]).duplicate_of == {2: 3}

    def test_every_member_of_a_star_has_a_direct_edge_to_its_winner(self) -> None:
        winner = _signature(10, phash=0, fine_phash=0, sharpness=100.0, taken_at=_BASE_TIME)
        members = [
            _signature(
                11,
                phash=_mask(8),
                fine_phash=_mask(20),
                sharpness=90.0,
                taken_at=_BASE_TIME + _MINUTE,
            ),
            _signature(
                12,
                phash=_mask(4),
                fine_phash=_mask(30),
                sharpness=80.0,
                taken_at=_BASE_TIME + 2 * _MINUTE,
            ),
        ]
        by_id = {photo.photo_id: photo for photo in [winner, *members]}

        result = assign_duplicate_groups([winner, *members])

        assert result.duplicate_of == {11: 10, 12: 10}
        for loser, winner_id in result.duplicate_of.items():
            assert is_similar(by_id[winner_id], by_id[loser])

    def test_two_similar_members_must_lie_within_the_window_of_each_other(self) -> None:
        winner = _signature(10, phash=0, fine_phash=0, sharpness=100.0, taken_at=_BASE_TIME)
        near = _signature(
            11,
            phash=_mask(8),
            fine_phash=_mask(20),
            sharpness=90.0,
            taken_at=_BASE_TIME + 14 * _MINUTE,
        )
        far = _signature(
            12,
            phash=_mask(8),
            fine_phash=_mask(20),
            sharpness=80.0,
            taken_at=_BASE_TIME - 14 * _MINUTE,
        )

        # Beide haben eine direkte Kante zum Gewinner (14 min), liegen aber 28 min auseinander.
        assert is_similar(winner, near)
        assert is_similar(winner, far)
        assert not is_similar(near, far)
        assert assign_duplicate_groups([winner, near, far]).duplicate_of == {11: 10}

    def test_members_inside_the_pairwise_window_all_join(self) -> None:
        winner = _signature(10, phash=0, fine_phash=0, sharpness=100.0, taken_at=_BASE_TIME)
        earlier = _signature(
            11,
            phash=_mask(8),
            fine_phash=_mask(20),
            sharpness=90.0,
            taken_at=_BASE_TIME - 7 * _MINUTE,
        )
        later = _signature(
            12,
            phash=_mask(4),
            fine_phash=_mask(30),
            sharpness=80.0,
            taken_at=_BASE_TIME + 7 * _MINUTE,
        )

        assert assign_duplicate_groups([winner, earlier, later]).duplicate_of == {11: 10, 12: 10}

    def test_a_pair_outside_the_candidate_net_is_never_checked(self) -> None:
        """Harte Stufe-1-Grenze (ADR 0145): gleiche feine Signatur und gleiches Gitter, aber
        grober Hamming ueber `DUPLICATE_CANDIDATE_HAMMING` - das Paar ist kein Kandidat und wird
        nicht gruppiert, obwohl die spaeteren Stufen es als identisch ansaehen."""
        winner = _signature(
            10,
            phash=0,
            fine_phash=0,
            sharpness=100.0,
            taken_at=_BASE_TIME,
            gray_grid=bytes(1024),
        )
        lookalike = _signature(
            11,
            phash=_mask(DUPLICATE_CANDIDATE_HAMMING + 1),
            fine_phash=0,
            sharpness=90.0,
            taken_at=_BASE_TIME,
            gray_grid=bytes(1024),
        )

        assert (winner.phash ^ lookalike.phash).bit_count() > DUPLICATE_CANDIDATE_HAMMING
        assert is_practically_identical(winner, lookalike)
        assert assign_duplicate_groups([winner, lookalike]).duplicate_of == {}


class TestTheIdenticalWinnerRule:
    """Durchgang 1 (Spec 0639, ADR 0146): Fuer praktisch identische Aufnahmen entscheidet die
    Aufloesung, dann die aeltere VERLAESSLICHE Aufnahmezeit, zuletzt die kleinere Id - die
    Schaerfe ist hier kein Kriterium mehr, weil sie auf der verkleinerten `display`-Variante
    irrefuehrt."""

    def test_higher_resolution_wins_against_sharpness(self) -> None:
        original = _photo_like()
        loser = _fingerprint(
            1,
            original,
            sharpness=99.0,
            pixel_count=400,
            taken_at=None,
            taken_at_trusted=False,
        )
        winner = _fingerprint(
            2,
            original.copy(),
            sharpness=1.0,
            pixel_count=1600,
            taken_at=None,
            taken_at_trusted=False,
        )

        assignment = assign_duplicate_groups([loser, winner])

        assert assignment.duplicate_of == {1: 2}
        assert assignment.identical_winners == frozenset({2})

    def test_a_derived_time_loses_against_a_trusted_one_at_equal_resolution(self) -> None:
        original = _photo_like()
        earlier_but_derived = _fingerprint(
            1,
            original,
            sharpness=99.0,
            pixel_count=400,
            taken_at=_BASE_TIME - timedelta(hours=2),
            taken_at_trusted=False,
        )
        trusted = _fingerprint(
            2,
            original.copy(),
            sharpness=1.0,
            pixel_count=400,
            taken_at=_BASE_TIME,
            taken_at_trusted=True,
        )

        assert assign_duplicate_groups([earlier_but_derived, trusted]).duplicate_of == {1: 2}

    def test_equal_resolution_and_time_fall_to_the_lower_id(self) -> None:
        original = _photo_like()
        higher_id = _fingerprint(5, original, sharpness=100.0, pixel_count=400, taken_at=_BASE_TIME)
        lower_id = _fingerprint(
            2, original.copy(), sharpness=1.0, pixel_count=400, taken_at=_BASE_TIME
        )

        assert assign_duplicate_groups([higher_id, lower_id]).duplicate_of == {5: 2}

    def test_an_unknown_resolution_sorts_last(self) -> None:
        original = _photo_like()
        unknown = _fingerprint(1, original, sharpness=100.0, pixel_count=None, taken_at=_BASE_TIME)
        known = _fingerprint(
            2, original.copy(), sharpness=1.0, pixel_count=400, taken_at=_BASE_TIME
        )

        assert assign_duplicate_groups([unknown, known]).duplicate_of == {1: 2}

    def test_a_three_member_star_with_mixed_resolution_has_one_identical_winner(self) -> None:
        original = _photo_like()
        fingerprints = [
            _fingerprint(10, original, sharpness=1.0, pixel_count=1600, taken_at=_BASE_TIME),
            _fingerprint(11, original.copy(), sharpness=99.0, pixel_count=400, taken_at=_BASE_TIME),
            _fingerprint(
                12, original.copy(), sharpness=98.0, pixel_count=None, taken_at=_BASE_TIME
            ),
            _fingerprint(13, original.copy(), sharpness=97.0, pixel_count=800, taken_at=_BASE_TIME),
        ]
        by_id = {fingerprint.photo_id: fingerprint for fingerprint in fingerprints}

        assignment = assign_duplicate_groups(fingerprints)

        assert assignment.duplicate_of == {11: 10, 12: 10, 13: 10}
        assert assignment.identical_winners == frozenset({10})
        for winner_id in assignment.identical_winners:
            assert winner_id not in assignment.duplicate_of
            members = [
                loser for loser, winner in assignment.duplicate_of.items() if winner == winner_id
            ]
            assert members
            for member_id in members:
                assert is_practically_identical(by_id[winner_id], by_id[member_id])

    def test_a_second_pass_does_not_extend_an_identical_group(self) -> None:
        """Ein aehnliches Kettenmitglied bleibt offen: Die Gruppe aus Durchgang 1 ist
        bauartbedingt vollstaendig identisch - eine teilweise automatische Gruppe entsteht
        nicht."""
        original = _photo_like()
        base = _fingerprint(1, original, sharpness=10.0, pixel_count=400, taken_at=_BASE_TIME)
        winner = _fingerprint(
            2, original.copy(), sharpness=20.0, pixel_count=1600, taken_at=_BASE_TIME
        )
        similar = _fingerprint(
            3,
            _shifted_crop(original),
            sharpness=30.0,
            pixel_count=100,
            taken_at=_BASE_TIME + _MINUTE,
        )

        assert is_practically_identical(base, winner)
        assert is_similar(winner, similar)
        assignment = assign_duplicate_groups([base, winner, similar])

        assert assignment.duplicate_of == {1: 2}
        assert assignment.identical_winners == frozenset({2})

    def test_the_assignment_is_a_frozen_value_with_both_answers(self) -> None:
        single = _signature(1, phash=0, fine_phash=0, sharpness=10.0, taken_at=_BASE_TIME)

        assignment = assign_duplicate_groups([single])

        assert isinstance(assignment, DuplicateAssignment)
        assert assignment.duplicate_of == {}
        assert assignment.identical_winners == frozenset()
        with pytest.raises(AttributeError):
            assignment.duplicate_of = {}  # type: ignore[misc]


class TestTheTriggerRegression:
    """Der ausloesende Bestand: 13 Aufnahmen ueber rund 392 Stunden, hoechstens zwei echte Paare
    (AK8). Das alte Verfahren verband einen solchen Bestand transitiv zu EINER Gruppe; hier darf
    keine Gruppe ueber das Zeitfenster hinausreichen, und die beiden echten Paare muessen
    erkannt werden."""

    def test_thirteen_photos_over_392_hours_yield_exactly_the_two_real_pairs(self) -> None:
        span = timedelta(hours=392)
        moments = [_BASE_TIME + span * index / 12 for index in range(13)]
        images = [_motif(index) for index in range(11)]
        # Paar 1: eine Kopie eines anderen Zeitpunkts - zeitunabhaengig identisch.
        images.append(_resaved(_motif(3)))
        # Paar 2: derselbe Ausschnitt, vier Minuten auseinander.
        images.append(_shifted_crop(_motif(6)))
        moments[12] = moments[6] + 4 * _MINUTE
        photos = [
            _fingerprint(index + 1, image, taken_at=moment)
            for index, (image, moment) in enumerate(zip(images, moments, strict=True))
        ]
        by_id = {photo.photo_id: photo for photo in photos}

        assert is_practically_identical(by_id[4], by_id[12])
        assert is_similar(by_id[7], by_id[13])
        assert not is_practically_identical(by_id[7], by_id[13])

        groups = assign_duplicate_groups(photos).duplicate_of

        assert len(groups) == 2
        assert len(set(groups.values())) == 2
        pairs = {frozenset((loser, winner)) for loser, winner in groups.items()}
        assert frozenset((4, 12)) in pairs
        assert frozenset((7, 13)) in pairs
        for loser, winner in groups.items():
            span_seconds = abs((by_id[loser].taken_at - by_id[winner].taken_at).total_seconds())
            assert is_practically_identical(by_id[loser], by_id[winner]) or (
                span_seconds <= DUPLICATE_SIMILAR_TIME_WINDOW.total_seconds()
            )


class TestAssignClustersByTime:
    def test_gap_just_under_threshold_stays_in_same_cluster(self) -> None:
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base),
            ClusterCandidate(photo_id=2, taken_at=base + (TIME_CLUSTER_GAP - _one_second())),
        ]

        result = assign_clusters(candidates)

        assert result[1] == result[2]

    def test_gap_just_over_threshold_starts_new_cluster(self) -> None:
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base),
            ClusterCandidate(photo_id=2, taken_at=base + (TIME_CLUSTER_GAP + _one_second())),
        ]

        result = assign_clusters(candidates)

        assert result[1] != result[2]

    def test_clusters_are_independent_of_input_order(self) -> None:
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=2, taken_at=base + (TIME_CLUSTER_GAP + _one_second())),
            ClusterCandidate(photo_id=1, taken_at=base),
        ]

        result = assign_clusters(candidates)

        assert result[1] != result[2]


def _one_second():
    from datetime import timedelta

    return timedelta(seconds=1)


# ---------------------------------------------------------------------------------------------
# specs/features/0051-gps-landmark-cluster-bildung.md, ADR 0029 Punkt 1 + ADR 0072 Entscheidung
# 4/5: Phase A bildet Basis-Cluster aus Zeit UND Ortssprung in EINEM sortierten Durchlauf.
# Verglichen wird gegen das letzte Foto MIT Koordinate im laufenden Cluster, und die
# Bezugskoordinate wird an JEDER Cluster-Grenze zurueckgesetzt.

# Eine Distanzangabe in Metern in einen reinen Breitengrad-Versatz umrechnen. Bewusst aus der
# Implementierung selbst gewonnen (die Haversine-Distanz entlang eines Meridians ist exakt
# proportional zur Breitendifferenz) - so liegt der Schwellwerttest tatsaechlich AUF der Schwelle
# statt knapp daneben, und er bleibt bei einer kuenftigen Kalibrierung des Werts gruen. Dass die
# EINHEIT stimmt, prueft dagegen `TestHaversineMeters::test_one_degree_of_latitude_is_about_111_km`
# gegen eine externe Referenzstrecke - genau die Aussage, die diese Helferfunktion nicht treffen
# kann.
_ONE_DEGREE_LATITUDE_METERS = haversine_meters(0.0, 0.0, 1.0, 0.0)


def _north_by(latitude: float, meters: float) -> float:
    return latitude + meters / _ONE_DEGREE_LATITUDE_METERS


def _legacy_assign_time_clusters(
    candidates: list[ClusterCandidate], gap: timedelta = TIME_CLUSTER_GAP
) -> dict[int, str]:
    """Im Test NACHGEBILDETE Referenzimplementierung des reinen Zeitfensterverhaltens von vor
    Spec 0051 (Teststrategie der Spec): `assign_time_clusters` existiert nach der Umbenennung
    nicht mehr - ohne diese Nachbildung pruefte der Backward-Compatibility-Test die neue Funktion
    gegen sich selbst."""
    ordered = sorted(candidates, key=lambda c: (c.taken_at, c.photo_id))
    result: dict[int, str] = {}
    cluster_index = -1
    previous_taken_at: datetime | None = None
    for candidate in ordered:
        if previous_taken_at is None or candidate.taken_at - previous_taken_at > gap:
            cluster_index += 1
        result[candidate.photo_id] = f"cluster-{cluster_index}"
        previous_taken_at = candidate.taken_at
    return result


class TestHaversineMeters:
    def test_identical_coordinates_have_zero_distance(self) -> None:
        assert haversine_meters(48.8583, 2.2945, 48.8583, 2.2945) == 0.0

    def test_one_degree_of_latitude_is_about_111_km(self) -> None:
        """EINHEITENNACHWEIS (Pflichtfall der Teststrategie, direkte Folge des 500-m-Werts): bei
        einer Schwelle von 500 m ist ein Meter/Kilometer-Dreher kein Randfall mehr, sondern die
        Grenze zwischen "trennt nie" und "trennt immer". Die abstrakten Schwellwerttests weiter
        unten bestehen bei JEDER Einheit und koennen ihn nicht finden - nur der Vergleich gegen
        eine bekannte Referenzstrecke mit ENGER Toleranz (+-0,1 %)."""
        meters = haversine_meters(0.0, 0.0, 1.0, 0.0)

        assert abs(meters - 111_195.0) < 111_195.0 * 0.001

    def test_antipodes_are_about_half_the_earths_circumference_apart(self) -> None:
        meters = haversine_meters(0.0, 0.0, 0.0, 180.0)

        # Grobe Toleranz, bewusst keine Float-Gleichheit - die Erdkugel-Approximation ist hier
        # nicht auf Genauigkeit, sondern auf Groessenordnung zu pruefen.
        assert abs(meters - 20_015_000.0) < 100_000.0

    def test_a_step_across_the_antimeridian_is_a_short_distance(self) -> None:
        """Der naheliegendste Fehler einer naiven Laengendifferenz ohne Wraparound: 179.9 nach
        -179.9 sind 0,2 Grad, nicht 359,8."""
        meters = haversine_meters(0.0, 179.9, 0.0, -179.9)

        assert meters < 25_000.0

    def test_the_same_longitude_difference_is_shorter_near_the_pole(self) -> None:
        """Faellt weg, wenn jemand die `cos(lat)`-Daempfung vergisst."""
        at_equator = haversine_meters(0.0, 0.0, 0.0, 1.0)
        at_seventy_degrees = haversine_meters(70.0, 0.0, 70.0, 1.0)

        assert at_seventy_degrees < at_equator * 0.5


class TestTheCorrectedTimeFeedsTheClustering:
    """specs/features/0426-zeitversatz-je-kamera.md: `assign_clusters` bekommt seit ADR 0090 die
    KORRIGIERTE Zeit uebergeben und braucht deshalb KEINE eigene Korrekturlogik.

    Der Nachweis ist ein Datensatz, dessen Gruppierung mit dem Versatz ANDERS ausfaellt als mit
    dem rohen Wert - laufe die Gruppierung weiter auf der aufgezeichneten Zeit, bliebe der Fall
    unbemerkt falsch."""

    def test_the_recorded_time_splits_what_the_corrected_time_keeps_together(self) -> None:
        base = datetime(2023, 1, 1, 10, 0, 0)
        offset = TIME_CLUSTER_GAP + timedelta(minutes=10)
        # Zwei Aufnahmen DESSELBEN Moments, deren Kamerauhr um mehr als die Zeitluecke nachgeht.
        raw = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=None, gps_lon=None),
            ClusterCandidate(photo_id=2, taken_at=base + offset, gps_lat=None, gps_lon=None),
        ]
        corrected = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=None, gps_lon=None),
            # dieselbe Datei, um ihren Versatz zurueckgestellt
            ClusterCandidate(photo_id=2, taken_at=base, gps_lat=None, gps_lon=None),
        ]

        raw_result = assign_clusters(raw)
        corrected_result = assign_clusters(corrected)

        assert raw_result[1] != raw_result[2]
        assert corrected_result[1] == corrected_result[2]


class TestAssignClustersByLocation:
    def test_a_location_jump_starts_a_new_cluster_without_any_time_gap(self) -> None:
        """DER Kern dieser Spec, nicht die Ergaenzung: zwei Sehenswuerdigkeiten kurz
        hintereinander landeten bisher in einem Cluster."""
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=0.0, gps_lon=0.0),
            ClusterCandidate(
                photo_id=2,
                taken_at=base + _one_second(),
                gps_lat=_north_by(0.0, GPS_CLUSTER_SPLIT_DISTANCE_METERS + 100.0),
                gps_lon=0.0,
            ),
        ]

        result = assign_clusters(candidates)

        assert result[1] != result[2]

    def test_a_distance_exactly_at_the_threshold_does_not_split(self) -> None:
        """`>` und nicht `>=` - explizit festgelegt und geprueft, nicht implizit von der
        Zeitbedingung geerbt."""
        base = datetime(2023, 1, 1, 10, 0, 0)
        far_latitude = _north_by(0.0, GPS_CLUSTER_SPLIT_DISTANCE_METERS)
        # Fixture-Garantie: das Paar liegt tatsaechlich AUF der Schwelle, nicht knapp darunter -
        # sonst pruefte der Test die Grenze gar nicht.
        assert haversine_meters(0.0, 0.0, far_latitude, 0.0) == pytest.approx(
            GPS_CLUSTER_SPLIT_DISTANCE_METERS, abs=1e-6
        )
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=0.0, gps_lon=0.0),
            ClusterCandidate(
                photo_id=2,
                taken_at=base + _one_second(),
                gps_lat=far_latitude,
                gps_lon=0.0,
            ),
        ]

        result = assign_clusters(candidates)

        assert result[1] == result[2]

    def test_a_distance_just_over_the_threshold_splits(self) -> None:
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=0.0, gps_lon=0.0),
            ClusterCandidate(
                photo_id=2,
                taken_at=base + _one_second(),
                gps_lat=_north_by(0.0, GPS_CLUSTER_SPLIT_DISTANCE_METERS + 1.0),
                gps_lon=0.0,
            ),
        ]

        result = assign_clusters(candidates)

        assert result[1] != result[2]

    def test_a_photo_without_a_coordinate_never_splits_by_itself(self) -> None:
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=0.0, gps_lon=0.0),
            ClusterCandidate(photo_id=2, taken_at=base + _one_second(), gps_lat=None, gps_lon=None),
            ClusterCandidate(
                photo_id=3, taken_at=base + 2 * _one_second(), gps_lat=0.0, gps_lon=0.0
            ),
        ]

        result = assign_clusters(candidates)

        assert result[1] == result[2] == result[3]

    def test_a_photo_without_a_coordinate_does_not_suppress_a_split_between_its_neighbours(
        self,
    ) -> None:
        """Fall (a) der Teststrategie: verglichen wird gegen das letzte Foto MIT Koordinate im
        laufenden Cluster, nicht gegen den unmittelbaren zeitlichen Vorgaenger. Unter der
        strengeren Lesart unterdrueckte ein einziges koordinatenloses Foto zwischen zwei weit
        auseinanderliegenden Aufnahmen die Trennung vollstaendig."""
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=0.0, gps_lon=0.0),
            ClusterCandidate(photo_id=2, taken_at=base + _one_second(), gps_lat=None, gps_lon=None),
            ClusterCandidate(
                photo_id=3,
                taken_at=base + 2 * _one_second(),
                gps_lat=_north_by(0.0, GPS_CLUSTER_SPLIT_DISTANCE_METERS + 100.0),
                gps_lon=0.0,
            ),
        ]

        result = assign_clusters(candidates)

        assert result[1] == result[2]
        assert result[3] != result[2]

    def test_the_reference_coordinate_is_reset_at_a_time_boundary(self) -> None:
        """Fall (b) der Teststrategie: ohne Ruecksetzung wuerde das erste koordinatentragende
        Foto des NEUEN Clusters gegen eines aus dem VORHERIGEN verglichen und ein zweites Mal
        getrennt. Der Fehler ist unsichtbar, solange nur eine Grenze im Spiel ist."""
        base = datetime(2023, 1, 1, 10, 0, 0)
        after_gap = base + TIME_CLUSTER_GAP + _one_second()
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=0.0, gps_lon=0.0),
            ClusterCandidate(photo_id=2, taken_at=after_gap, gps_lat=None, gps_lon=None),
            ClusterCandidate(
                photo_id=3,
                taken_at=after_gap + _one_second(),
                gps_lat=_north_by(0.0, GPS_CLUSTER_SPLIT_DISTANCE_METERS + 100.0),
                gps_lon=0.0,
            ),
        ]

        result = assign_clusters(candidates)

        assert result[1] != result[2]
        assert result[2] == result[3]

    def test_the_reference_coordinate_is_reset_after_a_location_split(self) -> None:
        """Fall (c) der Teststrategie: die neue Bezugskoordinate ist B, nicht A. C liegt 750 m von
        A entfernt, aber nur 150 m von B - und gehoert deshalb zu B."""
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=0.0, gps_lon=0.0),
            ClusterCandidate(
                photo_id=2,
                taken_at=base + _one_second(),
                gps_lat=_north_by(0.0, 600.0),
                gps_lon=0.0,
            ),
            ClusterCandidate(
                photo_id=3,
                taken_at=base + 2 * _one_second(),
                gps_lat=_north_by(0.0, 750.0),
                gps_lon=0.0,
            ),
        ]

        result = assign_clusters(candidates)

        assert result[1] != result[2]
        assert result[2] == result[3]

    def test_cumulative_drift_below_the_threshold_stays_one_cluster(self) -> None:
        """Dokumentiertes, GEWOLLTES Verhalten (eigener Testfall, damit eine spaetere Umstellung
        auf einen Schwerpunktvergleich bewusst statt versehentlich passiert): verglichen wird
        paarweise, nicht gegen Cluster-Anfang oder Schwerpunkt. Eine Kette aus je 300-m-Schritten
        ueber insgesamt 3 km bleibt EIN Cluster."""
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(
                photo_id=index + 1,
                taken_at=base + index * _one_second(),
                gps_lat=_north_by(0.0, 300.0 * index),
                gps_lon=0.0,
            )
            for index in range(11)
        ]

        result = assign_clusters(candidates)

        assert len(set(result.values())) == 1

    def test_without_any_coordinate_the_result_is_identical_to_the_old_time_clustering(
        self,
    ) -> None:
        """BACKWARD COMPATIBILITY auf Funktionsebene, nicht als ADR-Prosa: exakte `dict`-Gleichheit
        gegen die im Test nachgebildete Referenzimplementierung des alten Zeitverhaltens."""
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=None, gps_lon=None),
            ClusterCandidate(photo_id=2, taken_at=base + _one_second(), gps_lat=None, gps_lon=None),
            ClusterCandidate(
                photo_id=3,
                taken_at=base + TIME_CLUSTER_GAP + _one_second(),
                gps_lat=None,
                gps_lon=None,
            ),
            ClusterCandidate(
                photo_id=4,
                taken_at=base + 2 * TIME_CLUSTER_GAP + 2 * _one_second(),
                gps_lat=None,
                gps_lon=None,
            ),
        ]

        assert assign_clusters(candidates) == _legacy_assign_time_clusters(candidates)

    def test_a_half_coordinate_is_treated_as_no_coordinate(self) -> None:
        """Verteidigung in der Tiefe: `extract_gps` liefert nie eine halbe Koordinate, aber ein
        Altbestand oder ein kuenftiger Schreibpfad koennte eine erzeugen. Ein einzelner gesetzter
        Wert darf keine Trennung ausloesen und nicht als Bezug dienen."""
        base = datetime(2023, 1, 1, 10, 0, 0)
        candidates = [
            ClusterCandidate(photo_id=1, taken_at=base, gps_lat=0.0, gps_lon=0.0),
            ClusterCandidate(photo_id=2, taken_at=base + _one_second(), gps_lat=80.0, gps_lon=None),
        ]

        result = assign_clusters(candidates)

        assert result[1] == result[2]
