from __future__ import annotations

import hashlib
import io
import logging
import os
import re
from collections.abc import Iterable, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISREG
from typing import Literal

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

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


# specs/features/0044-projekte-loeschen.md, Punkt 2 "Cache-Cleanup" ab hier.


def delete_cached_variants(cache_dir: Path, photos: Iterable[tuple[int, str]]) -> None:
    """Entfernt Thumbnail- und Display-Variante der uebergebenen `(photo_id, etag)`-Paare.

    Gegenstueck zu `measure_cache_usage` und in derselben Form: Mengensignatur, rein synchron,
    ohne DB-Bezug - der Aufrufer fuehrt sie ueber `asyncio.to_thread` aus, damit die Event-Loop
    bei mehreren tausend `unlink`-Aufrufen nicht blockiert.

    Die Pfade werden ausschliesslich aus `photo_id`/`etag` BERECHNET, nie ueber ein
    Verzeichnismuster gesucht (ADR 0062 Punkt 5): der Cache ist flach und projektuebergreifend,
    ein `glob` traefe fremde Dateien. Aus derselben Rechnung folgt die benannte Grenze - Varianten
    unter einem inzwischen veralteten `etag` erreicht diese Funktion strukturell nicht (siehe
    `cache_key`, Restrisiko 2 der Spec, Issue #349).

    Best-effort je Datei: `missing_ok=True` deckt den Race-Fall "Datei bereits weg" ab, ein
    `OSError` wird mit dem Pfad GELOGGT und bricht den Cleanup der uebrigen Dateien nicht ab. Ein
    Dateifehler darf die bereits committete Datenloeschung nicht nachtraeglich zum Fehler machen;
    der absolute Cache-Pfad enthaelt interne Deployment-Struktur und gehoert deshalb ins Log, nie
    in eine HTTP-Antwort (dasselbe Muster wie bei `measure_cache_usage`).
    """
    for photo_id, etag in photos:
        for path in (
            thumbnail_path(cache_dir, photo_id, etag),
            display_path(cache_dir, photo_id, etag),
        ):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Cache-Datei konnte nicht entfernt werden: %s", path)


# specs/features/0349-verwaiste-bildkopien-aufraeumen.md, ADR 0075 ab hier: die einzige Stelle des
# Projekts, die das Cache-Verzeichnis LIEST, statt ihre Pfade aus `(photo_id, etag)` zu berechnen.
# Sie muss es, weil sie einen Rest aufraeumt, dessen Schluessel sich per Definition nicht mehr aus
# der Datenbank berechnen laesst (siehe die benannte Grenze in `delete_cached_variants`). ADR 0062
# Punkt 5 bleibt fuer jeden anderen Loeschpfad unveraendert in Kraft.


CACHE_FILE_PATTERN = re.compile(r"^([0-9a-f]{64})_(?:thumbnail|display)\.jpg\Z")
"""Die exakte Signatur der eigenen Schreiboperation - `cache_key` + `thumbnail_path`/
`display_path` und nichts sonst.

Wird IMMER per `re.fullmatch` angewandt, nie per `.match`/`.search` (Security-Muss-Kriterium 1 der
Spec). Das Endanker ist `\\Z` und NICHT `$`: `$` passt auch unmittelbar VOR einem abschliessenden
Zeilenumbruch, ein `.match` gegen `^...$` traefe deshalb `<64 hex>_display.jpg\\n` - und ein
Dateiname mit `\\n` ist unter Linux anlegbar. `\\Z` ist das absolute Ende der Zeichenkette und hat
diese Schwaeche nicht.

Die Anker sind damit ein zweites, unabhaengiges Netz unter der `fullmatch`-Regel: `fullmatch`
braucht sie nicht, aber sollte hier je jemand versehentlich auf `.match`/`.search` wechseln,
bliebe das Muster trotzdem exakt - ohne sie traefe ein `.match` jeden Namen, der mit der Signatur
nur BEGINNT (`<64 hex>_thumbnail.jpg.bak`), und loeschte ihn. Kein `re.IGNORECASE` -
`hashlib.hexdigest()` liefert ausschliesslich Kleinbuchstaben."""


@dataclass(frozen=True)
class CacheEntry:
    """EIN vorgefundener, gemusterter Verzeichniseintrag: Pfad, Cache-Schluessel, Aenderungszeit.

    Die Aenderungszeit ist die des Aufnahmezeitpunkts und bewusst nur eine Vorauswahl -
    `delete_orphaned_entries` liest sie unmittelbar vor dem `unlink` erneut."""

    path: Path
    key: str
    mtime: float


@dataclass(frozen=True)
class CacheSweepResult:
    """Ergebnis EINES Bereinigungsdurchgangs - vier reine Zahlen, kein Pfad.

    `kept_recent` ist kein Beiwerk: ohne dieses Feld waere "wegen der Schonfrist bewusst behalten"
    von "gar nicht betrachtet" nicht zu unterscheiden, und genau daran haengt Akzeptanzkriterium 4
    (ein parallel laufender Scan verliert nichts)."""

    deleted_files: int
    freed_bytes: int
    failed_files: int
    kept_recent: int


def collect_cache_entries(cache_dir: Path) -> list[CacheEntry]:
    """Nimmt die gemusterten Dateien in `cache_dir` auf - direkt, nicht rekursiv.

    Aufgenommen wird ausschliesslich, was ALLE drei Bedingungen erfuellt: direkter Eintrag in
    `cache_dir`, REGULAERE Datei (kein Verzeichnis, kein Symlink, kein Geraet), und ein Name, der
    `CACHE_FILE_PATTERN` EXAKT trifft. Alles andere bleibt unberuehrt, ausdruecklich auch
    Unbekanntes.

    Kein `glob`, kein Abstieg in Unterverzeichnisse: das schliesst Symlink-Schleifen und ein
    Ausbrechen aus dem Cache-Verzeichnis strukturell aus statt durch Pruefung. Pfad-Traversal ist
    doppelt versperrt - ein `os.scandir`-`name` enthaelt nie einen Pfadtrenner, und das Muster
    laesst ohnehin nur 64 Hexziffern plus feste Endung durch.

    Rein synchron und ohne DB-Bezug wie `measure_cache_usage`/`delete_cached_variants`: der
    Aufrufer fuehrt sie ueber `asyncio.to_thread` aus.

    Best-effort: ein fehlendes oder unlesbares Verzeichnis liefert eine leere Liste (kein Fehler),
    ein `OSError` auf einem EINZELNEN Eintrag ueberspringt nur diesen. Ein Name, der das Muster
    NICHT bestanden hat, wird nie geloggt (Security-Muss-Kriterium 6: er ist die einzige
    Log-Injection-Flaeche des Features - gezaehlt wird er, benannt nicht)."""
    entries: list[CacheEntry] = []
    try:
        with os.scandir(cache_dir) as scan:
            for entry in scan:
                match = CACHE_FILE_PATTERN.fullmatch(entry.name)
                if match is None:
                    continue
                try:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    stat_result = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                entries.append(
                    CacheEntry(
                        path=cache_dir / entry.name,
                        key=match.group(1),
                        mtime=stat_result.st_mtime,
                    )
                )
    except OSError:
        return entries
    return entries


def delete_orphaned_entries(
    entries: Sequence[CacheEntry], valid_keys: AbstractSet[str], mtime_cutoff: float
) -> CacheSweepResult:
    """Entfernt die Eintraege, deren Schluessel nicht in `valid_keys` liegt und die aelter als
    `mtime_cutoff` sind.

    Die Zeitgrenze kommt als PARAMETER herein und nie aus `settings` oder einer Uhr im Innern -
    dadurch ist die Funktion ohne Warten und ohne Uhr-Attrappe pruefbar (`tmp_path` + `os.utime`).
    Verglichen wird ausschliesslich gegen `st_mtime`, nie gegen einen Datenbank-Zeitstempel: beide
    Zeiten stammen so aus derselben Quelle (Host-Kernel).

    FAIL-CLOSED (Security-Muss-Kriterium 5 der Spec): Sind Eintraege vorhanden, die Menge der
    gueltigen Schluessel aber leer, wird NICHTS geloescht und eine WARNING geschrieben. Eine leere
    Menge ist der einzige Zustand, in dem dieser Durchgang den kompletten Bild-Cache raeumte, und
    zugleich das Symptom praktisch jedes denkbaren Fehlers an der Schnappschuss-Abfrage (falsche
    Datenbank, versehentlicher Filter, unbrauchbare Session). Der Preis ist der Randfall
    "Installation ohne ein einziges Foto behaelt ihre Reste".

    Unmittelbar vor dem `unlink` wird `lstat()` gelesen - NICHT `stat()` (Security-Muss-Kriterium
    2): `stat()` folgte einem zwischenzeitlich untergeschobenen Symlink und autorisierte dessen
    Entfernung ueber die Aenderungszeit einer FREMDEN Datei, dazu verfaelschte es `freed_bytes` um
    deren Groesse. Derselbe Aufruf liefert `st_size` und erlaubt die erneute `S_ISREG`-Pruefung.
    Auch die Aenderungszeit wird dabei erneut gegen `mtime_cutoff` geprueft: ein zwischenzeitliches
    Neuschreiben derselben Datei macht sie sofort wieder unantastbar.

    Best-effort je Datei: ein `OSError` wird MIT PFAD geloggt, zaehlt in `failed_files` und bricht
    den Durchgang nicht ab - ein einzelner Dateifehler darf einen erfolgreichen Scan nicht
    entwerten. Ausnahme ist `FileNotFoundError` beim `lstat`: die Datei ist inzwischen anderweitig
    verschwunden, das ist der erwartete Ausgang der harmlosen Wettlaufsituation und KEIN Fehlschlag
    - er wird still uebersprungen, weder gezaehlt noch geloggt. Absolute Cache-Pfade gehoeren ins
    Log, nie in eine HTTP-Antwort (dasselbe Muster wie `delete_cached_variants`)."""
    if entries and not valid_keys:
        logger.warning(
            "Bereinigung des Bild-Caches uebersprungen: %d gemusterte Datei(en) vorhanden, aber "
            "kein einziger gueltiger Cache-Schluessel - es wird nichts geloescht.",
            len(entries),
        )
        return CacheSweepResult(
            deleted_files=0, freed_bytes=0, failed_files=0, kept_recent=0
        )

    deleted_files = 0
    freed_bytes = 0
    failed_files = 0
    kept_recent = 0
    for entry in entries:
        if entry.key in valid_keys:
            continue
        if entry.mtime >= mtime_cutoff:
            kept_recent += 1
            continue
        try:
            stat_result = entry.path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            failed_files += 1
            logger.warning("Cache-Datei konnte nicht geprueft werden: %s", entry.path)
            continue
        if not S_ISREG(stat_result.st_mode):
            # Zwischen Aufnahme und Loeschung ist an dieser Stelle etwas anderes aufgetaucht
            # (Symlink, Verzeichnis). Kein Fehlschlag - eine bewusste Verweigerung.
            logger.warning("Cache-Eintrag ist keine regulaere Datei mehr: %s", entry.path)
            continue
        if stat_result.st_mtime >= mtime_cutoff:
            kept_recent += 1
            continue
        try:
            entry.path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            failed_files += 1
            logger.warning("Cache-Datei konnte nicht entfernt werden: %s", entry.path)
            continue
        deleted_files += 1
        freed_bytes += stat_result.st_size
    return CacheSweepResult(
        deleted_files=deleted_files,
        freed_bytes=freed_bytes,
        failed_files=failed_files,
        kept_recent=kept_recent,
    )
