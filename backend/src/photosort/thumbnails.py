from __future__ import annotations

import hashlib
import io
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISREG
from typing import Literal

from PIL import Image, ImageOps

# Groessen laut UI/UX-Abschnitt von specs/features/0002-manual-categorization.md: Grid nutzt
# Thumbnail-, Einzelbild-/Vergleichsansicht Display-Auflösung.
THUMBNAIL_MAX_SIZE = 400
DISPLAY_MAX_SIZE = 2048
JPEG_QUALITY_THUMBNAIL = 82
JPEG_QUALITY_DISPLAY = 88

Variant = Literal["thumbnail", "display"]


def cache_key(photo_id: int, etag: str) -> str:
    """Deterministischer, dateisystemsicherer Cache-Schluessel aus photo_id+etag.

    Kein neues DB-Feld noetig (specs/features/0002): aendert sich das Foto auf OpenCloud,
    aendert sich der etag und damit automatisch der Schluessel - alte Cache-Dateien werden
    dadurch implizit ungueltig, ohne dass eine explizite Invalidierung noetig waere.
    """
    digest = hashlib.sha256(f"{photo_id}:{etag}".encode()).hexdigest()
    return digest


def thumbnail_path(cache_dir: Path, photo_id: int, etag: str) -> Path:
    return cache_dir / f"{cache_key(photo_id, etag)}_thumbnail.jpg"


def display_path(cache_dir: Path, photo_id: int, etag: str) -> Path:
    return cache_dir / f"{cache_key(photo_id, etag)}_display.jpg"


def variant_path(cache_dir: Path, photo_id: int, etag: str, variant: Variant) -> Path:
    if variant == "thumbnail":
        return thumbnail_path(cache_dir, photo_id, etag)
    return display_path(cache_dir, photo_id, etag)


def generate_variants(cache_dir: Path, photo_id: int, etag: str, image_bytes: bytes) -> bool:
    """Erzeugt Thumbnail- und Display-Auflösung im lokalen Cache.

    Best-effort wie opencloud/exif.py::extract_taken_at: ein nicht dekodierbares Bild (z.B.
    HEIC ohne installiertes Plugin, beschaedigte Datei) darf einen laufenden Scan nie abbrechen
    - stattdessen liefert der Bild-Endpunkt fuer diese Variante dauerhaft 404 ("wird noch
    verarbeitet"-Platzhalter im Frontend), bis eine neue etag-Version erfolgreich verarbeitet
    werden kann.

    Returns True, wenn beide Varianten geschrieben wurden, sonst False.
    """
    try:
        opened = Image.open(io.BytesIO(image_bytes))
        opened.load()
        image: Image.Image = ImageOps.exif_transpose(opened) or opened
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        cache_dir.mkdir(parents=True, exist_ok=True)

        thumb = image.copy()
        thumb.thumbnail((THUMBNAIL_MAX_SIZE, THUMBNAIL_MAX_SIZE))
        thumb.save(
            thumbnail_path(cache_dir, photo_id, etag),
            format="JPEG",
            quality=JPEG_QUALITY_THUMBNAIL,
        )

        display = image.copy()
        display.thumbnail((DISPLAY_MAX_SIZE, DISPLAY_MAX_SIZE))
        display.save(
            display_path(cache_dir, photo_id, etag), format="JPEG", quality=JPEG_QUALITY_DISPLAY
        )
    except Exception:
        # Bewusst breiter Except-Block statt einer festen Liste von PIL-/OS-Exceptions (Security-
        # Review-Fund, specs/features/0002-manual-categorization.md, erweitert um Code-Review-Fund
        # zu Schreibfehlern): Image.DecompressionBombError erbt NICHT von OSError und wuerde von
        # einer engeren Liste durchgelassen - ein ungewoehnlich hochaufloesendes, aber nicht
        # boeswilliges Foto (Panorama/Drohnenaufnahme) duerfte den gesamten Scan-Job trotzdem nicht
        # crashen lassen. Aus demselben Grund deckt der Block jetzt auch mkdir()/save() ab: ein
        # Schreibfehler (Volume read-only, Platte voll) darf den Scan-Job ebenfalls nicht crashen
        # und den ScanRun dauerhaft auf RUNNING haengen lassen, statt nur dieses eine Thumbnail
        # best-effort zu ueberspringen. Gleiches Best-effort-Muster wie
        # opencloud/exif.py::extract_taken_at.
        return False
    return True


# specs/features/0207-projekt-statistikseite.md, Abschnitt 4 "Speicherbedarf" ab hier.


@dataclass(frozen=True)
class CacheUsage:
    """Ergebnis EINER Messung des lokalen Thumbnail-Caches fuer eine Fotomenge.

    `complete_photo_count` faellt als Nebenprodukt derselben Messung an (Fotos mit BEIDEN
    Varianten) und ist zugleich die Kennzahl "Thumbnails erzeugt" der Statistikseite - kein
    zweiter Durchlauf ueber dieselben Dateien."""

    total_bytes: int
    complete_photo_count: int


def measure_cache_usage(
    cache_dir: Path, photos: Iterable[tuple[int, str]]
) -> CacheUsage:
    """Misst den vom lokalen Cache belegten Platz fuer die uebergebenen (photo_id, etag)-Paare.

    Bewusst gezielt ueber die Pfade DIESER Fotos statt ueber das ganze Verzeichnis: der Cache ist
    flach und projektuebergreifend, eine Verzeichnissumme waere keine Projektkennzahl. Ein
    Nebeneffekt davon ist, dass Dateien unter einem VERALTETEN `etag`-Schluessel weder Bytes noch
    `complete_photo_count` beitragen - sie gehoeren zu einer inzwischen ersetzten Version des
    Fotos (siehe `cache_key`).

    Rein synchron und ohne DB-Bezug (deshalb `(photo_id, etag)`-Tupel statt ORM-Objekten): der
    Aufrufer fuehrt sie ueber `asyncio.to_thread` aus, damit die Event-Loop bei zwei `stat`-
    Aufrufen je Foto nicht blockiert.

    Best-effort je Datei (Security-Muss-Kriterium der Spec): ein `OSError` - fehlende Datei,
    fehlende Rechte, Verzeichnis an Dateistelle - zaehlt als 0 Bytes und wird NIE nach oben
    gereicht. Seine Meldung enthaelt den absoluten Cache-Pfad, also interne Deployment-Struktur,
    und duerfte deshalb weder in einer HTTPException noch in einem Antwortfeld landen."""
    total_bytes = 0
    complete_photo_count = 0
    for photo_id, etag in photos:
        variant_bytes = 0
        present = 0
        for path in (
            thumbnail_path(cache_dir, photo_id, etag),
            display_path(cache_dir, photo_id, etag),
        ):
            try:
                stat_result = path.stat()
            except OSError:
                continue
            if not S_ISREG(stat_result.st_mode):
                continue
            variant_bytes += stat_result.st_size
            present += 1
        total_bytes += variant_bytes
        if present == 2:
            complete_photo_count += 1
    return CacheUsage(total_bytes=total_bytes, complete_photo_count=complete_photo_count)
