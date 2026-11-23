"""Demo-Zustands-Seeder: reine Erzeuger ohne Datenbank (Namen, Spezifikationen, Demo-Bilder, Foto-
Kennung).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from photosort import demo_state
from photosort.demo_state import (
    CONFIRM_ENV_VAR,
    CONFIRM_LITERAL,
    DEMO_PROJECT_PREFIX,
    DUPLICATE_PROJECT_NAME,
    EMPTY_PROJECT_NAME,
    ERROR_PROJECT_NAME,
    LARGE_COLLECTION_PHOTO_COUNT,
    LARGE_PROJECT_NAME,
    LONG_AUSSCHUSS_PROJECT_NAME,
    OPERATIONS_PROJECT_NAME,
    RATED_PROJECT_NAME,
    DemoStateError,
    check_confirmation,
    check_opencloud_target,
    demo_etag,
    demo_project_specs,
    demo_relative_path,
    is_demo_project_name,
    render_demo_image,
)
from photosort.motifs import MOTIF_REGISTRY
from photosort.thumbnails import (
    ASPECT_RATIO_MAX,
    ASPECT_RATIO_MIN,
)


class TestIsDemoProjectName:
    """Praefix-Praedikat des Schutzabbruchs. Der interessante Teil ist, was NICHT als Demo-Projekt
    durchgeht - eine lockere `startswith("Demo")`-Pruefung wuerde ein reales Projekt
    "Demolition Sommer 2019" freigeben und loeschen (Edge Case E9 der Spec)."""

    @pytest.mark.parametrize(
        "name",
        [
            EMPTY_PROJECT_NAME,
            LARGE_PROJECT_NAME,
            RATED_PROJECT_NAME,
            ERROR_PROJECT_NAME,
            f"{DEMO_PROJECT_PREFIX}Irgendein Rest aus einem frueheren Lauf",
        ],
    )
    def test_exact_prefix_counts_as_demo_project(self, name: str) -> None:
        assert is_demo_project_name(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "Demo",
            "Demonstration",
            "Demolition Sommer 2019",
            "Demo -- Bewertet",
            "Demo—Bewertet",
            "Demo - Bewertet",
            "demo — bewertet",
            "Ein Demo — Projekt",
            "Familienfotos 2019",
            "",
        ],
    )
    def test_anything_but_the_exact_prefix_counts_as_a_foreign_project(self, name: str) -> None:
        assert is_demo_project_name(name) is False


class TestCheckConfirmation:
    """Teil (a) der dreiteiligen Sperre (M1): ein exakter Satz-Literal, nicht "gesetzt"/truthy."""

    def test_exact_literal_passes(self) -> None:
        check_confirmation(CONFIRM_LITERAL)

    @pytest.mark.parametrize(
        "value",
        [None, "", "0", "false", "1", "true", "yes", "YES-WIPE-AND-SEED-DEMO-DATA"],
    )
    def test_missing_or_merely_truthy_value_aborts(self, value: str | None) -> None:
        with pytest.raises(DemoStateError):
            check_confirmation(value)

    def test_surrounding_whitespace_is_not_accepted(self) -> None:
        with pytest.raises(DemoStateError):
            check_confirmation(f" {CONFIRM_LITERAL} ")

    def test_error_message_names_the_variable_but_not_the_rejected_value(self) -> None:
        with pytest.raises(DemoStateError) as excinfo:
            check_confirmation("geheimer-falscher-wert")
        assert CONFIRM_ENV_VAR in str(excinfo.value)
        assert "geheimer-falscher-wert" not in str(excinfo.value)


class TestCheckOpencloudTarget:
    """Teil (c) der dreiteiligen Sperre (M1) - die einzige Bedingung, die auf einer frisch
    aufgesetzten Produktivinstanz mit leerer Datenbank noch greift. Muster (inkl. Port-Pflicht)
    aus scripts/seed-opencloud-demo.py::validate_demo_base_url."""

    @pytest.mark.parametrize(
        "base_url",
        [
            "",
            "http://opencloud-demo:9200",
            "http://localhost:9200",
            "http://127.0.0.1:9200",
            "http://localhost:8080/",
        ],
    )
    def test_empty_or_known_demo_host_passes(self, base_url: str) -> None:
        check_opencloud_target(base_url)

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://cloud.example.org",
            "http://cloud.example.org:9200",
            "http://localhost",
            "https://localhost:9200",
            "http://192.168.1.10:9200",
            "opencloud-demo:9200",
        ],
    )
    def test_anything_else_aborts(self, base_url: str) -> None:
        with pytest.raises(DemoStateError):
            check_opencloud_target(base_url)

    def test_error_message_does_not_leak_the_configured_url(self) -> None:
        with pytest.raises(DemoStateError) as excinfo:
            check_opencloud_target("https://cloud.familie-koller.example:8443")
        message = str(excinfo.value)
        assert "familie-koller" not in message
        assert "8443" not in message


class TestDemoProjectSpecs:
    """Reine Zustandsbeschreibung - ohne DB, ohne Dateisystem."""

    def test_all_seven_states_are_described_and_carry_the_demo_prefix(self) -> None:
        specs = demo_project_specs()
        assert [spec.name for spec in specs] == [
            EMPTY_PROJECT_NAME,
            LARGE_PROJECT_NAME,
            RATED_PROJECT_NAME,
            ERROR_PROJECT_NAME,
            DUPLICATE_PROJECT_NAME,
            LONG_AUSSCHUSS_PROJECT_NAME,
            OPERATIONS_PROJECT_NAME,
        ]
        assert all(is_demo_project_name(spec.name) for spec in specs)

    def test_the_duplicate_project_holds_the_two_open_sizes_and_the_auto_group(self) -> None:
        """specs/features/0374-duplikate-vergleichen.md und Spec 0639: ZWEI offene Gruppen
        verschiedener Groesse, dazu eine automatisch entschiedene; die Fotoanzahl ist die Summe
        ueber alle drei - kein Foto steht daneben.

        Die zweite Gruppe ist keine Zugabe: AK3 sichert zu, dass eine Gruppe mit sieben
        Mitgliedern UMBRICHT, statt die Bilder zu verkleinern, und diese Zusage ist nur pruefbar,
        wenn eine zweite Gruppe anderer Groesse dieselbe Kachelbreite zeigt. Mit nur einer Gruppe
        bliebe sie unbelegt."""
        duplicates = demo_project_specs()[4]

        assert demo_state.DEMO_DUPLICATE_GROUP_SIZES == (7, 3)
        assert demo_state.DEMO_AUTO_DECIDED_GROUP_SIZE == 2
        assert duplicates.photo_count == (
            sum(demo_state.DEMO_DUPLICATE_GROUP_SIZES) + demo_state.DEMO_AUTO_DECIDED_GROUP_SIZE
        )
        assert len(set(demo_state.DEMO_DUPLICATE_GROUP_SIZES)) == len(
            demo_state.DEMO_DUPLICATE_GROUP_SIZES
        )

    def test_slugs_are_unique(self) -> None:
        slugs = [spec.slug for spec in demo_project_specs()]
        assert len(set(slugs)) == len(slugs)

    def test_empty_project_has_no_photos(self) -> None:
        empty = demo_project_specs()[0]
        assert empty.photo_count == 0
        assert empty.uncached_photo_indices == ()

    def test_large_collection_defaults_to_the_named_constant(self) -> None:
        large = demo_project_specs()[1]
        assert large.photo_count == LARGE_COLLECTION_PHOTO_COUNT

    def test_large_collection_photo_count_stays_inside_the_specified_band(self) -> None:
        # Kardinalitaets-Assertion gegen die KONSTANTE, nicht gegen einen Testparameter: eine
        # spaetere "Optimierung" auf fuenf Fotos wuerde das Grid-/Scroll-Verhalten unbemerkt
        # entwerten und muss rot werden.
        assert 60 <= LARGE_COLLECTION_PHOTO_COUNT <= 80

    def test_large_collection_photo_count_is_injectable_for_fast_tests(self) -> None:
        large = demo_project_specs(large_collection_photo_count=3)[1]
        assert large.photo_count == 3

    def test_rated_project_has_one_photo_per_motif_of_the_fixed_set(self) -> None:
        rated = demo_project_specs()[2]
        assert rated.photo_count == len(MOTIF_REGISTRY)

    def test_every_motif_state_index_lies_inside_the_rated_project(self) -> None:
        """Die vier Motiv-Sonderzustaende haengen an festen Indizes, die Fotoanzahl an der
        Registrygroesse - ohne diesen Waechter fiele bei einer schrumpfenden Registry ein Zustand
        still aus dem Demo-Bestand, und die Sichtpruefung zeigte ihn nie wieder."""
        rated = demo_project_specs()[2]
        indices = (
            demo_state.DEMO_UNASSESSED_INDEX,
            demo_state.DEMO_LOCAL_BASIS_INDEX,
            demo_state.DEMO_EXCLUDED_INDEX,
            demo_state.DEMO_CORRECTED_INDEX,
        )

        assert len(set(indices)) == len(indices)
        for index in indices:
            assert 0 <= index < rated.photo_count, index

    def test_error_state_has_at_least_one_photo_without_cache_files(self) -> None:
        error = demo_project_specs()[3]
        assert error.photo_count > 0
        assert len(error.uncached_photo_indices) >= 1
        assert all(0 <= index < error.photo_count for index in error.uncached_photo_indices)
        assert len(error.uncached_photo_indices) < error.photo_count


class TestRenderDemoImage:
    """Synthetische Bilderzeugung - deterministisch, ohne Netzwerk, ohne echte Fotos."""

    def test_produces_a_decodable_jpeg(self) -> None:
        image = Image.open(io.BytesIO(render_demo_image(slug="bewertet", index=0)))
        image.load()
        assert image.format == "JPEG"
        assert image.width > 0
        assert image.height > 0

    def test_same_arguments_produce_byte_identical_output(self) -> None:
        first = render_demo_image(slug="bewertet", index=7)
        second = render_demo_image(slug="bewertet", index=7)
        assert first == second

    def test_different_index_produces_different_output(self) -> None:
        assert render_demo_image(slug="bewertet", index=1) != render_demo_image(
            slug="bewertet", index=2
        )

    def test_different_slug_produces_different_output(self) -> None:
        assert render_demo_image(slug="bewertet", index=1) != render_demo_image(
            slug="fehlerzustand", index=1
        )


class TestTheDemoImagesCoverSeveralShapes:
    """specs/features/0489-fotouebersicht-ohne-beschnitt.md, ADR 0110 Konsequenzen: An lauter
    gleichen Verhaeltnissen ist ein justiertes Raster von einem Spaltenraster nicht zu
    unterscheiden - der E2E-Pruefstack pruefte die Zusage dann gar nicht."""

    def _ratios(self, slug: str, count: int) -> list[float]:
        ratios = []
        for index in range(count):
            with Image.open(io.BytesIO(render_demo_image(slug=slug, index=index))) as image:
                ratios.append(image.width / image.height)
        return ratios

    def test_the_large_collection_shows_at_least_three_pairwise_different_ratios(self) -> None:
        spec = next(s for s in demo_project_specs() if s.slug == "grosse-sammlung")

        ratios = self._ratios(spec.slug, spec.photo_count)

        assert len({round(ratio, 4) for ratio in ratios}) >= 3

    def test_the_large_collection_shows_both_a_portrait_and_a_wide_format(self) -> None:
        spec = next(s for s in demo_project_specs() if s.slug == "grosse-sammlung")

        ratios = self._ratios(spec.slug, spec.photo_count)

        assert any(ratio < 1 for ratio in ratios), "kein Hochformat im Bestand"
        assert any(ratio > 1.5 for ratio in ratios), "kein Breitformat im Bestand"

    def test_the_shape_is_deterministic_and_the_bytes_stay_identical(self) -> None:
        """Die Formatwahl haengt allein an `slug`/`index` - die Zusage der Byte-Identitaet zweier
        Laeufe bleibt dadurch unberuehrt."""
        for index in (0, 1, 2, 3):
            first = render_demo_image(slug="grosse-sammlung", index=index)
            second = render_demo_image(slug="grosse-sammlung", index=index)
            assert first == second

    def test_every_shape_stays_within_the_valid_band(self) -> None:
        """Ein Demo-Bild ausserhalb von `0.05..20.0` liesse `aspect_ratio` auf `NULL` fallen -
        der Demo-Bestand bildet den Zustand NACH dem Scan ab und darf das nicht erzeugen."""
        spec = next(s for s in demo_project_specs() if s.slug == "grosse-sammlung")

        for ratio in self._ratios(spec.slug, spec.photo_count):
            assert ASPECT_RATIO_MIN <= ratio <= ASPECT_RATIO_MAX


class TestDemoPhotoIdentity:
    """etag und relativer Pfad sind deterministisch und je Foto eindeutig - der etag geht in den
    Cache-Schluessel ein (thumbnails.cache_key), der Pfad ist die Anzeige im Frontend."""

    def test_etag_is_deterministic(self) -> None:
        assert demo_etag("bewertet", 3) == demo_etag("bewertet", 3)

    def test_etag_is_unique_per_photo(self) -> None:
        etags = {
            demo_etag(slug, index) for slug in ("bewertet", "grosse-sammlung") for index in range(5)
        }
        assert len(etags) == 10

    def test_relative_path_is_deterministic_and_unique(self) -> None:
        assert demo_relative_path("bewertet", 3) == demo_relative_path("bewertet", 3)
        paths = {demo_relative_path("bewertet", index) for index in range(5)}
        assert len(paths) == 5

    def test_relative_path_looks_like_an_image_file(self) -> None:
        assert Path(demo_relative_path("bewertet", 3)).suffix == ".jpg"
