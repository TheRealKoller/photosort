from __future__ import annotations

import hashlib
import io
from pathlib import Path
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
    except Exception:
        # Bewusst breiter Except-Block statt einer festen Liste von PIL-Exceptions (Security-
        # Review-Fund, specs/features/0002-manual-categorization.md): Image.DecompressionBombError
        # erbt NICHT von OSError und wuerde von einer engeren Liste durchgelassen - ein
        # ungewoehnlich hochaufloesendes, aber nicht boeswilliges Foto (Panorama/Drohnenaufnahme)
        # duerfte den gesamten Scan-Job trotzdem nicht crashen lassen. Gleiches Best-effort-Muster
        # wie opencloud/exif.py::extract_taken_at.
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)

    thumb = image.copy()
    thumb.thumbnail((THUMBNAIL_MAX_SIZE, THUMBNAIL_MAX_SIZE))
    thumb.save(
        thumbnail_path(cache_dir, photo_id, etag), format="JPEG", quality=JPEG_QUALITY_THUMBNAIL
    )

    display = image.copy()
    display.thumbnail((DISPLAY_MAX_SIZE, DISPLAY_MAX_SIZE))
    display.save(
        display_path(cache_dir, photo_id, etag), format="JPEG", quality=JPEG_QUALITY_DISPLAY
    )
    return True
