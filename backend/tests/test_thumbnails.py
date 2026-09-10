from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from PIL import Image

from photosort.thumbnails import (
    CACHE_FILE_PATTERN,
    DISPLAY_MAX_SIZE,
    THUMBNAIL_MAX_SIZE,
    CacheSweepResult,
    CacheUsage,
    cache_key,
    collect_cache_entries,
    delete_cached_variants,
    delete_orphaned_entries,
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


# specs/features/0044-projekte-loeschen.md, Punkt 2 "Cache-Cleanup" ab hier: eine benannte, rein
# synchrone Mengenfunktion in der Form von measure_cache_usage - der Aufrufer fuehrt sie ueber
# asyncio.to_thread aus, damit die Event-Loop bei mehreren tausend unlink-Aufrufen nicht blockiert.


def test_delete_cached_variants_accepts_an_empty_set(tmp_path: Path) -> None:
    delete_cached_variants(tmp_path, [])

    assert list(tmp_path.iterdir()) == []


def test_delete_cached_variants_removes_both_variants_and_tolerates_missing_files(
    tmp_path: Path,
) -> None:
    generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=_jpeg_bytes(60, 40))
    assert thumbnail_path(tmp_path, 1, "etag-a").is_file()

    # Foto 2 hat nie eine Cache-Datei bekommen - der haeufige Normalfall, kein Fehler.
    delete_cached_variants(tmp_path, [(1, "etag-a"), (2, "etag-b")])

    assert not thumbnail_path(tmp_path, 1, "etag-a").exists()
    assert not display_path(tmp_path, 1, "etag-a").exists()


def test_delete_cached_variants_leaves_files_of_other_photos_untouched(tmp_path: Path) -> None:
    generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=_jpeg_bytes(60, 40))
    generate_variants(tmp_path, photo_id=2, etag="etag-b", image_bytes=_jpeg_bytes(60, 40))

    delete_cached_variants(tmp_path, [(1, "etag-a")])

    assert not thumbnail_path(tmp_path, 1, "etag-a").exists()
    assert thumbnail_path(tmp_path, 2, "etag-b").is_file()
    assert display_path(tmp_path, 2, "etag-b").is_file()


def test_delete_cached_variants_keeps_going_after_an_oserror_and_logs_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Die eigentliche Zusage ist die zweite Haelfte: ein Fehler auf EINEM Element darf den
    Cleanup der uebrigen nicht abbrechen. Der Pfad gehoert ins Log, nie in eine Antwort."""
    generate_variants(tmp_path, photo_id=1, etag="etag-a", image_bytes=_jpeg_bytes(60, 40))
    generate_variants(tmp_path, photo_id=2, etag="etag-b", image_bytes=_jpeg_bytes(60, 40))
    doomed = thumbnail_path(tmp_path, 1, "etag-a")
    original_unlink = Path.unlink

    def _failing_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == doomed:
            raise OSError("Nur-Lese-Dateisystem")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", _failing_unlink)

    with caplog.at_level("WARNING"):
        delete_cached_variants(tmp_path, [(1, "etag-a"), (2, "etag-b")])

    assert doomed.is_file()
    assert not thumbnail_path(tmp_path, 2, "etag-b").exists()
    assert not display_path(tmp_path, 2, "etag-b").exists()
    assert str(doomed) in caplog.text


# specs/features/0349-verwaiste-bildkopien-aufraeumen.md, ADR 0075 ab hier: der EINE gemusterte
# Verzeichnisdurchgang des Projekts. Das Muster gehoert neben die Pfadbildung, die es
# wiedererkennt - wer `thumbnail_path`/`display_path` aendert, muss es in derselben Datei
# anfassen. Beide Funktionen sind rein/DB-frei und damit gegen `tmp_path` pruefbar, ohne
# Datenbank, ohne Fake-Client und ohne Uhr: das Alter kommt ausschliesslich ueber `os.utime`,
# die Grenze als Parameter.


def _write_aged(path: Path, size: int, mtime: float) -> None:
    _write_variant(path, size)
    os.utime(path, (mtime, mtime))


class TestCacheFilePattern:
    """Die Anker `^...\\Z` sind ein zweites Netz UNTER der `fullmatch`-Regel und keine Zierde.

    Geprueft wird deshalb hier ausdruecklich `.match` - der Aufruf, den der Produktivcode nie
    macht: verrutschte er dorthin, muss das Muster trotzdem exakt bleiben."""

    @pytest.mark.parametrize(
        "name",
        ["0" * 64 + "_display.jpg\n", "0" * 64 + "_thumbnail.jpg.bak"],
        ids=["zeilenumbruch", "angehaengtes-suffix"],
    )
    def test_even_an_accidental_match_would_reject_a_merely_prefixed_name(
        self, name: str
    ) -> None:
        """`$` statt `\\Z` liesse den Zeilenumbruch-Namen durch, ein ANKERLOSES Muster zusaetzlich
        jeden Namen, der mit der Signatur nur beginnt - beide wuerden dann geloescht."""
        assert CACHE_FILE_PATTERN.match(name) is None

    def test_the_pattern_accepts_exactly_what_the_write_operation_produces(
        self, tmp_path: Path
    ) -> None:
        """Der Treffer entsteht ueber `thumbnail_path`/`display_path`, nie als handgetippter
        Hex-String - sonst driften Muster und Namensschema auseinander."""
        for path in (
            thumbnail_path(tmp_path, 1, "etag-1"),
            display_path(tmp_path, 1, "etag-1"),
        ):
            match = CACHE_FILE_PATTERN.fullmatch(path.name)

            assert match is not None
            assert match.group(1) == cache_key(1, "etag-1")


class TestCollectCacheEntries:
    def test_missing_cache_directory_yields_no_entries(self, tmp_path: Path) -> None:
        assert collect_cache_entries(tmp_path / "existiert-nicht") == []

    def test_empty_cache_directory_yields_no_entries(self, tmp_path: Path) -> None:
        assert collect_cache_entries(tmp_path) == []

    def test_both_variants_of_one_photo_become_two_entries_with_the_same_key(
        self, tmp_path: Path
    ) -> None:
        _write_variant(thumbnail_path(tmp_path, 1, "etag-1"), 100)
        _write_variant(display_path(tmp_path, 1, "etag-1"), 200)

        entries = collect_cache_entries(tmp_path)

        assert len(entries) == 2
        assert {entry.key for entry in entries} == {cache_key(1, "etag-1")}
        assert {entry.path for entry in entries} == {
            thumbnail_path(tmp_path, 1, "etag-1"),
            display_path(tmp_path, 1, "etag-1"),
        }

    @pytest.mark.parametrize(
        "name",
        [
            "0" * 63 + "_thumbnail.jpg",
            "0" * 65 + "_thumbnail.jpg",
            "A" * 64 + "_thumbnail.jpg",
            "0" * 64 + "_thumbnail.jpeg",
            "0" * 64 + "_preview.jpg",
            "_thumbnail.jpg",
            "vorher-" + "0" * 64 + "_thumbnail.jpg",
            "0" * 64 + "_thumbnail.jpg.bak",
        ],
        ids=[
            "63-hexstellen",
            "65-hexstellen",
            "grossbuchstaben",
            "jpeg-statt-jpg",
            "unbekannte-variante",
            "ohne-schluessel",
            "praefix",
            "suffix",
        ],
    )
    def test_schema_similar_names_are_not_collected(self, tmp_path: Path, name: str) -> None:
        """Schemaaehnliche Nicht-Treffer, nicht "irgendwas-fremdes.jpg": nur sie pruefen das
        Muster tatsaechlich."""
        _write_variant(tmp_path / name, 50)

        assert collect_cache_entries(tmp_path) == []

    def test_a_trailing_newline_in_the_name_is_not_collected(self, tmp_path: Path) -> None:
        """Security-Muss-Kriterium 1 der Spec: `re.match` traefe diesen Namen, weil `$` auch
        unmittelbar vor einem abschliessenden Zeilenumbruch passt - und ein Dateiname mit `\\n`
        ist unter Linux anlegbar. Nur `re.fullmatch` weist ihn ab; er ist zugleich die einzige
        Log-Injection-Flaeche des Features."""
        _write_variant(tmp_path / ("0" * 64 + "_display.jpg\n"), 50)

        assert collect_cache_entries(tmp_path) == []

    def test_a_subdirectory_with_a_valid_name_is_not_collected_and_not_descended(
        self, tmp_path: Path
    ) -> None:
        directory = tmp_path / ("0" * 64 + "_thumbnail.jpg")
        directory.mkdir()
        _write_variant(directory / ("1" * 64 + "_display.jpg"), 50)

        assert collect_cache_entries(tmp_path) == []

    def test_a_symlink_with_a_valid_name_is_not_collected_and_not_followed(
        self, tmp_path: Path
    ) -> None:
        """Der Fall, der die Schutzwirkung des abgeloesten Verbots aus ADR 0062 Punkt 5 ersetzt -
        ohne eigenen Test nur eine Absichtserklaerung."""
        outside = tmp_path.parent / "fremde-datei.bin"
        outside.write_bytes(b"x" * 999)
        (tmp_path / ("0" * 64 + "_display.jpg")).symlink_to(outside)

        assert collect_cache_entries(tmp_path) == []
        assert outside.is_file()

    def test_the_entry_carries_the_modification_time_set_via_utime(self, tmp_path: Path) -> None:
        path = thumbnail_path(tmp_path, 1, "etag-1")
        _write_aged(path, 100, mtime=1_600_000_000.0)

        entries = collect_cache_entries(tmp_path)

        assert len(entries) == 1
        assert entries[0].mtime == pytest.approx(1_600_000_000.0)

    def test_an_oserror_on_a_single_entry_does_not_abort_the_collection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        good = thumbnail_path(tmp_path, 2, "etag-2")
        _write_variant(good, 100)
        doomed_name = "0" * 64 + "_display.jpg"
        real_scandir = os.scandir

        class _ExplodingEntry:
            name = doomed_name
            path = str(tmp_path / doomed_name)

            def is_file(self, *, follow_symlinks: bool = True) -> bool:
                return True

            def stat(self, *, follow_symlinks: bool = True) -> object:
                raise PermissionError("Zugriff verweigert")

        class _FakeScandir:
            def __enter__(self) -> object:
                return iter([_ExplodingEntry(), *real_scandir(tmp_path)])

            def __exit__(self, *args: object) -> bool:
                return False

        monkeypatch.setattr(os, "scandir", lambda _path: _FakeScandir())

        entries = collect_cache_entries(tmp_path)

        assert [entry.path for entry in entries] == [good]


# Die Grenze `CUTOFF` ist ein reiner Parameter - keine Uhr, keine Wartezeit. `ALT` liegt weit
# davor, `JUNG` weit dahinter; die Sekundengenauigkeit ist nirgends Gegenstand ausser im
# ausdruecklichen Grenzwertfall.
CUTOFF = 1_600_000_000.0
ALT = CUTOFF - 10_000.0
JUNG = CUTOFF + 10_000.0


class TestDeleteOrphanedEntries:
    """Jeder Loeschfall traegt eine Ueberlebens-Assertion auf einer Nachbardatei: ein Test, der
    nur "die verwaiste Datei ist weg" behauptet, bliebe gruen, wenn die Implementierung das
    Verzeichnis leerraeumt."""

    def test_an_empty_input_yields_four_zeros(self, tmp_path: Path) -> None:
        result = delete_orphaned_entries([], {cache_key(1, "etag-1")}, CUTOFF)

        assert result == CacheSweepResult(
            deleted_files=0, freed_bytes=0, failed_files=0, kept_recent=0
        )

    def test_entries_with_only_valid_keys_yield_four_zeros_and_survive(
        self, tmp_path: Path
    ) -> None:
        _write_aged(thumbnail_path(tmp_path, 1, "etag-1"), 100, ALT)
        _write_aged(display_path(tmp_path, 1, "etag-1"), 200, ALT)

        result = delete_orphaned_entries(
            collect_cache_entries(tmp_path), {cache_key(1, "etag-1")}, CUTOFF
        )

        assert result == CacheSweepResult(
            deleted_files=0, freed_bytes=0, failed_files=0, kept_recent=0
        )
        assert thumbnail_path(tmp_path, 1, "etag-1").is_file()
        assert display_path(tmp_path, 1, "etag-1").is_file()

    def test_an_orphaned_and_aged_file_is_removed_while_a_valid_neighbour_survives(
        self, tmp_path: Path
    ) -> None:
        orphan = thumbnail_path(tmp_path, 9, "etag-weg")
        valid = thumbnail_path(tmp_path, 1, "etag-1")
        _write_aged(orphan, 300, ALT)
        _write_aged(valid, 100, ALT)

        result = delete_orphaned_entries(
            collect_cache_entries(tmp_path), {cache_key(1, "etag-1")}, CUTOFF
        )

        assert not orphan.exists()
        assert valid.is_file()
        assert result == CacheSweepResult(
            deleted_files=1, freed_bytes=300, failed_files=0, kept_recent=0
        )

    def test_an_orphaned_but_young_file_stays_and_counts_as_kept_recent(
        self, tmp_path: Path
    ) -> None:
        """Ohne das eigene Zaehlfeld waere "bewusst behalten" von "gar nicht betrachtet" nicht zu
        unterscheiden - und der Fall, der Akzeptanzkriterium 4 traegt, bestuende leer."""
        young_orphan = thumbnail_path(tmp_path, 9, "etag-weg")
        valid = thumbnail_path(tmp_path, 1, "etag-1")
        _write_aged(young_orphan, 300, JUNG)
        _write_aged(valid, 100, ALT)

        result = delete_orphaned_entries(
            collect_cache_entries(tmp_path), {cache_key(1, "etag-1")}, CUTOFF
        )

        assert young_orphan.is_file()
        assert valid.is_file()
        assert result == CacheSweepResult(
            deleted_files=0, freed_bytes=0, failed_files=0, kept_recent=1
        )

    def test_the_cutoff_itself_is_the_keeping_side(self, tmp_path: Path) -> None:
        """Eine Seite festlegen und pruefen: `mtime < cutoff` loescht, `mtime == cutoff` bleibt."""
        on_the_line = thumbnail_path(tmp_path, 8, "etag-genau")
        just_before = thumbnail_path(tmp_path, 9, "etag-knapp-davor")
        _write_aged(on_the_line, 100, CUTOFF)
        _write_aged(just_before, 100, CUTOFF - 1.0)

        result = delete_orphaned_entries(collect_cache_entries(tmp_path), {"unbenutzt"}, CUTOFF)

        assert on_the_line.is_file()
        assert not just_before.exists()
        assert result == CacheSweepResult(
            deleted_files=1, freed_bytes=100, failed_files=0, kept_recent=1
        )

    def test_a_file_rewritten_between_collection_and_unlink_survives(
        self, tmp_path: Path
    ) -> None:
        """Der Kern von Akzeptanzkriterium 4: die Aenderungszeit wird unmittelbar vor dem `unlink`
        ERNEUT gelesen. Ohne diesen Fall bliebe eine Implementierung gruen, die die Zeit aus dem
        Schnappschuss nimmt."""
        orphan = thumbnail_path(tmp_path, 9, "etag-weg")
        neighbour = thumbnail_path(tmp_path, 8, "etag-auch-weg")
        _write_aged(orphan, 300, ALT)
        _write_aged(neighbour, 100, ALT)
        entries = collect_cache_entries(tmp_path)

        os.utime(orphan, (JUNG, JUNG))

        result = delete_orphaned_entries(entries, {"unbenutzt"}, CUTOFF)

        assert orphan.is_file()
        assert not neighbour.exists()
        assert result == CacheSweepResult(
            deleted_files=1, freed_bytes=100, failed_files=0, kept_recent=1
        )

    def test_a_symlink_swapped_in_before_the_unlink_is_not_removed(
        self, tmp_path: Path
    ) -> None:
        """Security-Muss-Kriterium 2: `Path.stat()` folgte dem Symlink und autorisierte seine
        Entfernung ueber die Aenderungszeit einer FREMDEN Datei. `lstat()` plus erneutes
        `S_ISREG` faellt ihn heraus - auch dann, wenn die eigene Aenderungszeit des Links
        (per `follow_symlinks=False` gealtert) die Schonfrist gar nicht mehr schuetzt."""
        orphan = thumbnail_path(tmp_path, 9, "etag-weg")
        _write_aged(orphan, 300, ALT)
        entries = collect_cache_entries(tmp_path)

        outside = tmp_path.parent / "fremde-datei.bin"
        _write_aged(outside, 999, ALT)
        orphan.unlink()
        orphan.symlink_to(outside)
        os.utime(orphan, (ALT, ALT), follow_symlinks=False)

        result = delete_orphaned_entries(entries, {"unbenutzt"}, CUTOFF)

        assert orphan.is_symlink()
        assert outside.is_file()
        assert result.deleted_files == 0
        assert result.freed_bytes == 0

    def test_freed_bytes_sums_only_the_actually_deleted_files(self, tmp_path: Path) -> None:
        _write_aged(thumbnail_path(tmp_path, 9, "etag-weg"), 300, ALT)
        _write_aged(display_path(tmp_path, 9, "etag-weg"), 4_000, ALT)
        _write_aged(thumbnail_path(tmp_path, 1, "etag-1"), 111, ALT)

        result = delete_orphaned_entries(
            collect_cache_entries(tmp_path), {cache_key(1, "etag-1")}, CUTOFF
        )

        assert result.deleted_files == 2
        assert result.freed_bytes == 4_300
        assert thumbnail_path(tmp_path, 1, "etag-1").is_file()

    def test_an_oserror_on_unlink_is_counted_logged_and_does_not_stop_the_rest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Die eigentliche Zusage ist die zweite Haelfte (Akzeptanzkriterium 7): die ZWEITE
        verwaiste Datei ist trotzdem weg."""
        doomed = thumbnail_path(tmp_path, 9, "etag-weg")
        other = thumbnail_path(tmp_path, 8, "etag-auch-weg")
        _write_aged(doomed, 300, ALT)
        _write_aged(other, 100, ALT)
        entries = collect_cache_entries(tmp_path)
        original_unlink = Path.unlink

        def _failing_unlink(self: Path, missing_ok: bool = False) -> None:
            if self == doomed:
                raise OSError("Nur-Lese-Dateisystem")
            original_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _failing_unlink)

        with caplog.at_level("WARNING"):
            result = delete_orphaned_entries(entries, {"unbenutzt"}, CUTOFF)

        assert doomed.is_file()
        assert not other.exists()
        assert result == CacheSweepResult(
            deleted_files=1, freed_bytes=100, failed_files=1, kept_recent=0
        )
        assert str(doomed) in caplog.text

    def test_an_oserror_on_lstat_is_counted_and_the_file_stays(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        doomed = thumbnail_path(tmp_path, 9, "etag-weg")
        _write_aged(doomed, 300, ALT)
        entries = collect_cache_entries(tmp_path)

        def _explode(self: Path) -> object:
            raise PermissionError(f"Zugriff verweigert: {self}")

        monkeypatch.setattr(Path, "lstat", _explode)

        with caplog.at_level("WARNING"):
            result = delete_orphaned_entries(entries, {"unbenutzt"}, CUTOFF)

        assert doomed.is_file()
        assert result == CacheSweepResult(
            deleted_files=0, freed_bytes=0, failed_files=0 + 1, kept_recent=0
        )
        assert str(doomed) in caplog.text

    def test_a_file_that_vanished_before_the_lstat_is_skipped_silently(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Auflage 2 der Teststrategie: die harmlose Wettlaufsituation trifft ab jetzt den
        `lstat`, nicht mehr das `missing_ok=True` des `unlink`. Sie ist KEIN Fehlschlag - sonst
        meldet der Normalfall Fehler, die keine sind, und ein echtes Rechteproblem geht im
        Rauschen unter."""
        vanishing = thumbnail_path(tmp_path, 9, "etag-weg")
        _write_aged(vanishing, 300, ALT)
        entries = collect_cache_entries(tmp_path)
        vanishing.unlink()

        with caplog.at_level("DEBUG"):
            result = delete_orphaned_entries(entries, {"unbenutzt"}, CUTOFF)

        assert result == CacheSweepResult(
            deleted_files=0, freed_bytes=0, failed_files=0, kept_recent=0
        )
        assert caplog.records == []

    def test_a_file_that_vanishes_between_lstat_and_unlink_counts_as_neither(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Das Mikrosekundenfenster zwischen letzter Zeitpruefung und `unlink` ist in der
        Wirklichkeit nicht herstellbar (ADR 0075, "Konsequenzen") - die AUFFANGLOGIK dafuer ist es
        sehr wohl: der Ausgang zaehlt weder als Fehlschlag noch als geloeschte Datei, und er
        traegt keine Bytes zu `freed_bytes` bei."""
        vanishing = thumbnail_path(tmp_path, 9, "etag-weg")
        other = thumbnail_path(tmp_path, 8, "etag-auch-weg")
        _write_aged(vanishing, 300, ALT)
        _write_aged(other, 100, ALT)
        entries = collect_cache_entries(tmp_path)
        original_unlink = Path.unlink

        def _vanishing_unlink(self: Path, missing_ok: bool = False) -> None:
            if self == vanishing:
                raise FileNotFoundError(f"Datei bereits entfernt: {self}")
            original_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _vanishing_unlink)

        with caplog.at_level("DEBUG"):
            result = delete_orphaned_entries(entries, {"unbenutzt"}, CUTOFF)

        assert not other.exists()
        assert result == CacheSweepResult(
            deleted_files=1, freed_bytes=100, failed_files=0, kept_recent=0
        )
        assert caplog.records == []

    def test_an_empty_valid_key_set_deletes_nothing_and_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Security-Muss-Kriterium 5, fail-closed: eine leere Gueltigkeitsmenge ist der einzige
        Zustand, in dem der Durchgang den kompletten Bild-Cache raeumte - und zugleich das Symptom
        praktisch jedes denkbaren Fehlers an der Schnappschuss-Abfrage."""
        orphan = thumbnail_path(tmp_path, 9, "etag-weg")
        _write_aged(orphan, 300, ALT)

        with caplog.at_level("WARNING"):
            result = delete_orphaned_entries(collect_cache_entries(tmp_path), set(), CUTOFF)

        assert orphan.is_file()
        assert result == CacheSweepResult(
            deleted_files=0, freed_bytes=0, failed_files=0, kept_recent=0
        )
        assert [record.levelname for record in caplog.records] == ["WARNING"]

    def test_cache_sweep_result_is_frozen(self) -> None:
        result = CacheSweepResult(
            deleted_files=1, freed_bytes=2, failed_files=3, kept_recent=4
        )

        with pytest.raises(AttributeError):
            result.deleted_files = 5  # type: ignore[misc]
