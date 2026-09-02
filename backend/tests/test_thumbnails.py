from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from photosort.thumbnails import (
    DISPLAY_MAX_SIZE,
    THUMBNAIL_MAX_SIZE,
    CacheUsage,
    cache_key,
    display_path,
    generate_variants,
    measure_cache_usage,
    thumbnail_path,
    variant_path,
)


def _jpeg_bytes(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_cache_key_is_deterministic_and_differs_by_etag() -> None:
    assert cache_key(1, "etag-a") == cache_key(1, "etag-a")
    assert cache_key(1, "etag-a") != cache_key(1, "etag-b")
    assert cache_key(1, "etag-a") != cache_key(2, "etag-a")


def test_variant_path_thumbnail_and_display_differ(tmp_path: Path) -> None:
    thumb = thumbnail_path(tmp_path, 1, "etag-a")
    display = display_path(tmp_path, 1, "etag-a")
    assert thumb != display
    assert variant_path(tmp_path, 1, "etag-a", "thumbnail") == thumb
    assert variant_path(tmp_path, 1, "etag-a", "display") == display


def test_generate_variants_writes_both_files_downsized(tmp_path: Path) -> None:
    content = _jpeg_bytes(4000, 3000)

    ok = generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=content)

    assert ok is True
    thumb = thumbnail_path(tmp_path, 1, "etag-a")
    display = display_path(tmp_path, 1, "etag-a")
    assert thumb.is_file()
    assert display.is_file()

    with Image.open(thumb) as image:
        assert max(image.size) <= THUMBNAIL_MAX_SIZE
    with Image.open(display) as image:
        assert max(image.size) <= DISPLAY_MAX_SIZE


def test_generate_variants_converts_non_rgb_images(tmp_path: Path) -> None:
    # Test-Review-Fund: der Konvertierungspfad fuer Nicht-RGB/L-Bilder (z.B. RGBA-PNGs mit
    # Alphakanal, wie sie aus Screenshots/manchen Kamera-Exports vorkommen) war zuvor ungetestet.
    image = Image.new("RGBA", (30, 20), color=(255, 0, 0, 128))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    ok = generate_variants(tmp_path, photo_id=1, etag="etag-rgba", image_bytes=buffer.getvalue())

    assert ok is True
    with Image.open(thumbnail_path(tmp_path, 1, "etag-rgba")) as saved:
        assert saved.mode == "RGB"


def test_generate_variants_does_not_upscale_small_images(tmp_path: Path) -> None:
    content = _jpeg_bytes(50, 40)

    generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=content)

    with Image.open(thumbnail_path(tmp_path, 1, "etag-a")) as image:
        assert image.size == (50, 40)


def test_generate_variants_returns_false_for_undecodable_bytes(tmp_path: Path) -> None:
    ok = generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=b"not an image")

    assert ok is False
    assert not thumbnail_path(tmp_path, 1, "etag-a").exists()
    assert not display_path(tmp_path, 1, "etag-a").exists()


def test_generate_variants_returns_false_instead_of_crashing_on_write_failure(
    tmp_path: Path,
) -> None:
    # Code-Review-Fund: mkdir()/save() lagen zuvor ausserhalb des Except-Blocks - ein
    # Schreibfehler (z.B. read-only Volume, volle Platte) haette den scan_project-Job crashen
    # und den ScanRun dauerhaft auf RUNNING haengen lassen, statt wie bei einem undekodierbaren
    # Bild nur diese eine Thumbnail-Generierung best-effort zu ueberspringen. Ein regulaeres File
    # an der Zielstelle simuliert den Schreibfehler unabhaengig von Dateisystem-Rechten (die als
    # root im Testcontainer wirkungslos waeren).
    content = _jpeg_bytes(100, 100)
    blocked_cache_dir = tmp_path / "blocked"
    blocked_cache_dir.write_text("occupies the path generate_variants tries to mkdir into")

    ok = generate_variants(blocked_cache_dir, photo_id=1, etag="etag-a", image_bytes=content)

    assert ok is False


def test_generate_variants_returns_false_instead_of_crashing_on_decompression_bomb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Security-Review-Fund (specs/features/0002-manual-categorization.md): Pillows
    # DecompressionBombError erbt NICHT von OSError - ohne diesen Test wuerde ein
    # ungewoehnlich hochaufloesendes, aber nicht boeswilliges Foto (Panorama/Drohnenaufnahme,
    # siehe Bedrohungsmodell "OpenCloud potenziell fehlerhaft, nicht boeswillig") den gesamten
    # scan_project-Job crashen lassen statt nur diese eine Thumbnail-Generierung best-effort
    # zu ueberspringen. MAX_IMAGE_PIXELS wird hier auf einen winzigen Wert gesetzt, damit ein
    # gewoehnliches kleines Testbild deterministisch die Bombe simuliert, statt ein echtes
    # Riesenbild erzeugen zu muessen.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    content = _jpeg_bytes(100, 100)

    ok = generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=content)

    assert ok is False
    assert not thumbnail_path(tmp_path, 1, "etag-a").exists()


# specs/features/0207-projekt-statistikseite.md, Abschnitt 4 "Speicherbedarf": reine, DB-freie
# Messfunktion ueber dem lokalen Cache. Gehoert hierher, weil hier die Pfadbildung lebt - und ist
# damit gegen `tmp_path` testbar, ohne eine Datenbank oder den Endpunkt zu bemuehen.


def _write_variant(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


class TestMeasureCacheUsage:
    def test_missing_cache_directory_yields_zero(self, tmp_path: Path) -> None:
        usage = measure_cache_usage(tmp_path / "existiert-nicht", [(1, "etag-1")])

        assert usage == CacheUsage(total_bytes=0, complete_photo_count=0)

    def test_empty_cache_directory_yields_zero(self, tmp_path: Path) -> None:
        usage = measure_cache_usage(tmp_path, [(1, "etag-1"), (2, "etag-2")])

        assert usage == CacheUsage(total_bytes=0, complete_photo_count=0)

    def test_no_photos_at_all_yields_zero(self, tmp_path: Path) -> None:
        _write_variant(thumbnail_path(tmp_path, 1, "etag-1"), 100)

        usage = measure_cache_usage(tmp_path, [])

        assert usage == CacheUsage(total_bytes=0, complete_photo_count=0)

    def test_only_the_thumbnail_counts_bytes_but_not_as_complete(self, tmp_path: Path) -> None:
        _write_variant(thumbnail_path(tmp_path, 1, "etag-1"), 120)

        usage = measure_cache_usage(tmp_path, [(1, "etag-1")])

        assert usage.total_bytes == 120
        assert usage.complete_photo_count == 0

    def test_only_the_display_variant_counts_bytes_but_not_as_complete(
        self, tmp_path: Path
    ) -> None:
        _write_variant(display_path(tmp_path, 1, "etag-1"), 300)

        usage = measure_cache_usage(tmp_path, [(1, "etag-1")])

        assert usage.total_bytes == 300
        assert usage.complete_photo_count == 0

    def test_both_variants_count_as_one_complete_photo(self, tmp_path: Path) -> None:
        _write_variant(thumbnail_path(tmp_path, 1, "etag-1"), 120)
        _write_variant(display_path(tmp_path, 1, "etag-1"), 880)

        usage = measure_cache_usage(tmp_path, [(1, "etag-1")])

        assert usage.total_bytes == 1000
        assert usage.complete_photo_count == 1

    def test_sums_over_several_photos(self, tmp_path: Path) -> None:
        _write_variant(thumbnail_path(tmp_path, 1, "etag-1"), 100)
        _write_variant(display_path(tmp_path, 1, "etag-1"), 200)
        _write_variant(thumbnail_path(tmp_path, 2, "etag-2"), 50)

        usage = measure_cache_usage(tmp_path, [(1, "etag-1"), (2, "etag-2")])

        assert usage.total_bytes == 350
        assert usage.complete_photo_count == 1

    def test_a_stale_etag_contributes_neither_bytes_nor_completeness(self, tmp_path: Path) -> None:
        """Der Cache-Schluessel enthaelt den `etag` (siehe cache_key): aendert sich das Foto auf
        OpenCloud, werden die alten Dateien implizit ungueltig. Sie liegen zwar noch auf der
        Platte, gehoeren aber nicht mehr zu diesem Foto - sonst wuerde der Cache-Wert dauerhaft
        wachsen und "Thumbnails erzeugt" ein bereits veraltetes Bild mitzaehlen."""
        _write_variant(thumbnail_path(tmp_path, 1, "etag-alt"), 100)
        _write_variant(display_path(tmp_path, 1, "etag-alt"), 200)

        usage = measure_cache_usage(tmp_path, [(1, "etag-neu")])

        assert usage == CacheUsage(total_bytes=0, complete_photo_count=0)

    def test_a_foreign_file_in_the_cache_directory_is_ignored(self, tmp_path: Path) -> None:
        """Gemessen wird gezielt ueber die Pfade DIESES Projekts, nicht ueber das gesamte
        Verzeichnis - der Cache ist flach und projektuebergreifend."""
        _write_variant(tmp_path / "irgendwas-fremdes.jpg", 9999)
        _write_variant(thumbnail_path(tmp_path, 1, "etag-1"), 100)

        usage = measure_cache_usage(tmp_path, [(1, "etag-1")])

        assert usage.total_bytes == 100

    def test_a_directory_where_a_variant_is_expected_is_ignored(self, tmp_path: Path) -> None:
        """Best-effort statt Absturz: ein `OSError` (oder ein Verzeichnis an Dateistelle) darf die
        Statistikseite nie mit einem 500 beantworten - und seine Meldung enthielte den absoluten
        Cache-Pfad, also interne Deployment-Struktur (Security-Muss-Kriterium der Spec)."""
        thumbnail_path(tmp_path, 1, "etag-1").mkdir(parents=True)
        _write_variant(display_path(tmp_path, 1, "etag-1"), 200)

        usage = measure_cache_usage(tmp_path, [(1, "etag-1")])

        assert usage.total_bytes == 200
        assert usage.complete_photo_count == 0

    def test_an_os_error_while_measuring_is_swallowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_variant(thumbnail_path(tmp_path, 1, "etag-1"), 100)
        _write_variant(display_path(tmp_path, 1, "etag-1"), 200)

        def _explode(self: Path) -> int:
            raise PermissionError(f"Zugriff verweigert: {self}")

        monkeypatch.setattr(Path, "stat", _explode)

        usage = measure_cache_usage(tmp_path, [(1, "etag-1")])

        assert usage == CacheUsage(total_bytes=0, complete_photo_count=0)

    def test_cache_usage_is_frozen(self) -> None:
        usage = CacheUsage(total_bytes=1, complete_photo_count=2)

        with pytest.raises(AttributeError):
            usage.total_bytes = 5  # type: ignore[misc]
