from __future__ import annotations

import io
from datetime import datetime, timedelta

import pytest
from PIL import Image, ImageDraw, ImageFilter

from photosort.scoring import (
    DUPLICATE_HAMMING_THRESHOLD,
    GPS_CLUSTER_SPLIT_DISTANCE_METERS,
    TIME_CLUSTER_GAP,
    ClusterCandidate,
    DuplicateCandidate,
    _haversine_meters,
    assign_clusters,
    assign_duplicate_clusters,
    compute_dhash,
    compute_exposure,
    compute_sharpness,
    hamming_distance,
    refine_clusters_by_landmark,
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
        hash_b_value = 1 << DUPLICATE_HAMMING_THRESHOLD
        hash_c_value = hash_b_value | (1 << (DUPLICATE_HAMMING_THRESHOLD + 5))
        candidates = [
            DuplicateCandidate(photo_id=1, phash="0000000000000000", sharpness=10.0),
            DuplicateCandidate(photo_id=2, phash=f"{hash_b_value:016x}", sharpness=20.0),
            DuplicateCandidate(photo_id=3, phash=f"{hash_c_value:016x}", sharpness=30.0),
        ]

        result = assign_duplicate_clusters(candidates)

        assert result == {1: 3, 2: 3}


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
_ONE_DEGREE_LATITUDE_METERS = _haversine_meters(0.0, 0.0, 1.0, 0.0)


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
        assert _haversine_meters(48.8583, 2.2945, 48.8583, 2.2945) == 0.0

    def test_one_degree_of_latitude_is_about_111_km(self) -> None:
        """EINHEITENNACHWEIS (Pflichtfall der Teststrategie, direkte Folge des 500-m-Werts): bei
        einer Schwelle von 500 m ist ein Meter/Kilometer-Dreher kein Randfall mehr, sondern die
        Grenze zwischen "trennt nie" und "trennt immer". Die abstrakten Schwellwerttests weiter
        unten bestehen bei JEDER Einheit und koennen ihn nicht finden - nur der Vergleich gegen
        eine bekannte Referenzstrecke mit ENGER Toleranz (+-0,1 %)."""
        meters = _haversine_meters(0.0, 0.0, 1.0, 0.0)

        assert abs(meters - 111_195.0) < 111_195.0 * 0.001

    def test_antipodes_are_about_half_the_earths_circumference_apart(self) -> None:
        meters = _haversine_meters(0.0, 0.0, 0.0, 180.0)

        # Grobe Toleranz, bewusst keine Float-Gleichheit - die Erdkugel-Approximation ist hier
        # nicht auf Genauigkeit, sondern auf Groessenordnung zu pruefen.
        assert abs(meters - 20_015_000.0) < 100_000.0

    def test_a_step_across_the_antimeridian_is_a_short_distance(self) -> None:
        """Der naheliegendste Fehler einer naiven Laengendifferenz ohne Wraparound: 179.9 nach
        -179.9 sind 0,2 Grad, nicht 359,8."""
        meters = _haversine_meters(0.0, 179.9, 0.0, -179.9)

        assert meters < 25_000.0

    def test_the_same_longitude_difference_is_shorter_near_the_pole(self) -> None:
        """Faellt weg, wenn jemand die `cos(lat)`-Daempfung vergisst."""
        at_equator = _haversine_meters(0.0, 0.0, 0.0, 1.0)
        at_seventy_degrees = _haversine_meters(70.0, 0.0, 70.0, 1.0)

        assert at_seventy_degrees < at_equator * 0.5


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
        assert _haversine_meters(0.0, 0.0, far_latitude, 0.0) == pytest.approx(
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
            ClusterCandidate(
                photo_id=2, taken_at=base + _one_second(), gps_lat=None, gps_lon=None
            ),
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
            ClusterCandidate(
                photo_id=2, taken_at=base + _one_second(), gps_lat=None, gps_lon=None
            ),
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
            ClusterCandidate(
                photo_id=2, taken_at=base + _one_second(), gps_lat=None, gps_lon=None
            ),
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
            ClusterCandidate(
                photo_id=2, taken_at=base + _one_second(), gps_lat=80.0, gps_lon=None
            ),
        ]

        result = assign_clusters(candidates)

        assert result[1] == result[2]


# ---------------------------------------------------------------------------------------------
# specs/features/0051-gps-landmark-cluster-bildung.md, ADR 0029 Punkt 1 (Phase 2) + ADR 0072
# Entscheidung 3: reine, DB-FREIE Verfeinerungsfunktion. Die Landmark-Namen kommen als einfaches
# `dict[int, str | None]` herein - die Funktion kennt ihre Datenherkunft nicht, obwohl es sie
# inzwischen gibt. Das haelt die Schluesselvergabe ohne Cloud-Fixture pruefbar.


class TestRefineClustersByLandmark:
    def test_two_names_in_one_cluster_produce_index_based_keys(self) -> None:
        """Die Schluesselform ist TESTGEGENSTAND, nicht Nebenwirkung: `cluster-3-1`/`cluster-3-2`,
        1-basiert, kein Name im Schluessel. Geprueft gegen ein festes Erwartungs-`dict`, nicht
        gegen ein Regex-"sieht passend aus"."""
        base = {1: "cluster-3", 2: "cluster-3"}
        names = {1: "Alexanderplatz", 2: "Zugspitze"}

        assert refine_clusters_by_landmark(base, names) == {
            1: "cluster-3-1",
            2: "cluster-3-2",
        }

    def test_the_index_follows_alphabetical_order_not_the_order_encountered(self) -> None:
        """Ein Test, der nur "unterschiedliche Namen -> unterschiedliche Schluessel" prueft, ist
        gegen die naheliegende Implementierung (Index in Antreffreihenfolge) blind: hier steht
        "Zugspitze" beim fruehesten Foto, bekommt aber die `-2`."""
        base = {1: "cluster-3", 2: "cluster-3"}
        names = {1: "Zugspitze", 2: "Alexanderplatz"}

        assert refine_clusters_by_landmark(base, names) == {
            1: "cluster-3-2",
            2: "cluster-3-1",
        }

    def test_the_result_is_independent_of_the_input_order(self) -> None:
        """Ohne diesen Test haengt die Schluesselvergabe an der Zeilenreihenfolge der Datenbank,
        und dieselbe Partition heisst zwischen zwei Laeufen anders."""
        forward = refine_clusters_by_landmark(
            {1: "cluster-0", 2: "cluster-0", 3: "cluster-0"},
            {1: "Brandenburger Tor", 2: "Alexanderplatz", 3: "Zugspitze"},
        )
        backward = refine_clusters_by_landmark(
            {3: "cluster-0", 2: "cluster-0", 1: "cluster-0"},
            {3: "Zugspitze", 2: "Alexanderplatz", 1: "Brandenburger Tor"},
        )

        assert forward == backward

    def test_sorting_uses_python_codepoint_order_not_a_locale_collation(self) -> None:
        """Sortierkonvention festgeschrieben: Python-Standardsortierung (Codepunkt-Reihenfolge).
        Eine spaeter eingefuehrte `locale`-Sortierung wuerde die Schluessel stillschweigend
        umnummerieren - "Zugspitze" steht vor "Oelberg", weil `Z` (U+005A) vor `Ö` (U+00D6)
        liegt."""
        base = {1: "cluster-0", 2: "cluster-0"}
        names = {1: "Ölberg", 2: "Zugspitze"}

        assert refine_clusters_by_landmark(base, names) == {
            1: "cluster-0-2",
            2: "cluster-0-1",
        }

    def test_unnamed_photos_keep_the_base_key(self) -> None:
        """Ein Cluster mit zwei Namen und zwei namenlosen Fotos ergibt GENAU DREI Schluessel -
        geprueft als exakte Schluesselmenge, nicht als "mindestens zwei"."""
        base = dict.fromkeys((1, 2, 3, 4), "cluster-3")
        names = {1: "Alexanderplatz", 2: "Zugspitze", 3: None, 4: None}

        result = refine_clusters_by_landmark(base, names)

        assert result == {
            1: "cluster-3-1",
            2: "cluster-3-2",
            3: "cluster-3",
            4: "cluster-3",
        }
        assert set(result.values()) == {"cluster-3", "cluster-3-1", "cluster-3-2"}

    def test_exactly_one_name_in_a_cluster_produces_no_refinement(self) -> None:
        """Sonst entstuende fuer jeden benannten Cluster ein Schluesselwechsel ohne jeden Nutzen -
        und `cluster-3` und `cluster-3-1` waeren beide belegt."""
        base = {1: "cluster-3", 2: "cluster-3"}
        names = {1: "Zugspitze", 2: None}

        assert refine_clusters_by_landmark(base, names) == {
            1: "cluster-3",
            2: "cluster-3",
        }

    def test_the_same_name_twice_is_not_two_names(self) -> None:
        base = {1: "cluster-3", 2: "cluster-3"}
        names = {1: "Zugspitze", 2: "Zugspitze"}

        assert refine_clusters_by_landmark(base, names) == {
            1: "cluster-3",
            2: "cluster-3",
        }

    def test_without_any_name_the_result_is_dict_identical_to_the_input(self) -> None:
        """BACKWARD COMPATIBILITY: reiner Passthrough, exakter Gleichheitsvergleich."""
        base = {1: "cluster-0", 2: "cluster-0", 3: "cluster-1"}

        assert refine_clusters_by_landmark(base, dict.fromkeys((1, 2, 3), None)) == base

    def test_an_empty_name_counts_as_no_name(self) -> None:
        """Ein leerer bzw. nur aus Leerraum bestehender Name ist keine Sehenswuerdigkeit - er darf
        weder einen Split ausloesen noch einen eigenen Schluessel bekommen."""
        base = {1: "cluster-0", 2: "cluster-0", 3: "cluster-0"}
        names = {1: "Zugspitze", 2: "", 3: "   "}

        assert refine_clusters_by_landmark(base, names) == {
            1: "cluster-0",
            2: "cluster-0",
            3: "cluster-0",
        }

    def test_the_comparison_is_exact_without_any_fuzzy_matching(self) -> None:
        """Bewusste v1-Vereinfachung (ADR 0029 Punkt 5): zwei Schreibweisen-Varianten desselben
        Orts SPLITTEN. Eigener Testfall, damit eine spaetere Verhaltensaenderung sichtbar wird."""
        base = {1: "cluster-0", 2: "cluster-0"}
        names = {1: "Eiffelturm", 2: "Eiffel-Turm"}

        result = refine_clusters_by_landmark(base, names)

        assert result[1] != result[2]

    def test_each_base_cluster_is_refined_on_its_own(self) -> None:
        """Die Indizes laufen JE BASIS-CLUSTER von 1 an - ein laufweiter Zaehler machte die
        Schluessel von der Reihenfolge fremder Cluster abhaengig."""
        base = {1: "cluster-0", 2: "cluster-0", 3: "cluster-1", 4: "cluster-1"}
        names = {1: "Alexanderplatz", 2: "Zugspitze", 3: "Brandenburger Tor", 4: "Yachthafen"}

        assert refine_clusters_by_landmark(base, names) == {
            1: "cluster-0-1",
            2: "cluster-0-2",
            3: "cluster-1-1",
            4: "cluster-1-2",
        }

    def test_a_name_for_a_photo_outside_the_base_mapping_has_no_effect(self) -> None:
        """Eine Landmark-Zeile zu einem Foto, das im Bezugslauf gar keine Kandidatenzeile hat
        (Ausschuss-Gate), erzeugt keinen Schluessel und keinen Split."""
        base = {1: "cluster-0", 2: "cluster-0"}
        names = {1: "Zugspitze", 2: None, 99: "Alexanderplatz"}

        assert refine_clusters_by_landmark(base, names) == {
            1: "cluster-0",
            2: "cluster-0",
        }
