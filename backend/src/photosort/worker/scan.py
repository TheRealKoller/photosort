"""Der Scan-Lauf: Enumeration, Klassifikation der Eintraege, Blockschleife, Nachholrunden."""

from __future__ import annotations

import asyncio
import enum
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker._runs as runs
from photosort.cache_cleanup import cleanup_orphaned_cache
from photosort.cameras import CameraIdentity, shifted
from photosort.config import settings
from photosort.db import async_session_factory
from photosort.models import (
    Photo,
    Project,
    ProjectCamera,
    ScanRun,
    ScanStatus,
)
from photosort.opencloud.client import IMAGE_EXTENSIONS, OpenCloudClient, OpenCloudError
from photosort.opencloud.exif import (
    extract_camera,
    extract_gps,
    extract_pixel_count,
    extract_taken_at,
)
from photosort.opencloud.webdav_xml import DavEntry
from photosort.run_cancel import RunCancelled
from photosort.thumbnails import (
    VariantResult,
    aspect_ratio_of_cached_thumbnail,
    generate_variants,
    thumbnail_path,
)

# HEIC/HEIF lesen ihr EXIF aus demselben 128-KiB-Fenster wie JPEG.
_HEIC_EXTENSIONS = {".heic", ".heif"}


_EXIF_CANDIDATE_EXTENSIONS = {".jpg", ".jpeg"} | _HEIC_EXTENSIONS


_EXIF_RANGE_BYTES = 131_072


# FESTES Grund-Token fuer den einen Fall, in dem der Scan den Versatz eines Fotos nicht anwenden
# kann (das Ergebnis laege ausserhalb des darstellbaren Datumsbereichs) - Muster der
# Grund-Tokens in `opencloud/exif.py`. Kein Rohwert, kein Zeitstempel, kein Fremdtext.
_OFFSET_REASON_OUT_OF_RANGE = "ausserhalb_darstellbarem_bereich"


# Analog SCORE_COMMIT_BATCH_SIZE, aber für ScanRun.files_found. Modul-Konstante statt
# Default-Parameterwert, damit Tests sie per monkeypatch.setattr(worker,
# "SCAN_COMMIT_BATCH_SIZE", ...) verkleinern können. Dieselbe Kadenz gilt ueber den gemeinsamen
# Helfer _maybe_commit_progress_checkpoint (unten), einmal aufgerufen aus Phase 1
# (_enumerate_scan_entries, je gelistetem Eintrag) und einmal aus der Skip-Schleife von Phase 2a
# in run_project_scan (je Skip-Entscheidung).
#
# 1, nicht 25 wie SCORE_COMMIT_BATCH_SIZE: run_project_scan ist netzwerkgebunden (EXIF-Range-Read
# und Thumbnail-Generierung pro Datei ueber OpenCloud-WebDAV), ein zusaetzlicher DB-Commit pro
# Datei faellt gegenueber der Netzwerklatenz nicht messbar ins Gewicht. Ein groesserer Wert friert
# den Live-Zaehler bei jedem Scan mit weniger Dateien als der Batch waehrend der gesamten Laufzeit
# auf 0 ein - und der dominante Realweltfall ist der Re-Scan mit ueberwiegend unveraenderten
# Dateien.
SCAN_COMMIT_BATCH_SIZE = 1


class OpenCloudScanClient(Protocol):
    """The subset of OpenCloudClient that scanning needs — kept narrow so tests can fake it."""

    async def resolve_drive(self, name: str | None) -> Any: ...

    def walk(self, webdav_url: str, root_path: str) -> Any: ...

    async def get_range(self, webdav_url: str, relative_path: str, length: int) -> bytes: ...

    async def download(self, webdav_url: str, relative_path: str) -> bytes: ...


def _extension(relative_path: str) -> str:
    return os.path.splitext(relative_path)[1].lower()


class SkipReason(enum.Enum):
    """Phase 2a: warum ein Eintrag NICHT zu einem Arbeitsposten für Phase 2b wird. Zwei
    getrennte Werte statt eines einzelnen bool-Flags, weil nur UNSUPPORTED_EXTENSION
    zusätzlich ScanRun.files_skipped hochzählt (siehe run_project_scan) - UNCHANGED_ETAG
    zählt nur in
    files_found (Fortschritt), nicht in files_skipped."""

    UNSUPPORTED_EXTENSION = "unsupported_extension"
    UNCHANGED_ETAG = "unchanged_etag"


@dataclass
class ScanWorkItem:
    """Ein Eintrag aus Phase 1, der in Phase 2b tatsaechlich verarbeitet werden muss (neue Datei,
    geaenderter Etag, oder eine der einmaligen Nachhol-Runden fuer Kamera/Aufloesung) -
    `existing_photo` ist `None` fuer neue Dateien, sonst die zu aktualisierende Zeile.

    `probe_only` heisst: die Datei ist UNVERAENDERT, gelesen wird nur ihr EXIF-Fenster, um die
    Kamera-Angabe nachzutragen. Die Thumbnails existieren bereits und waeren identisch - ihre
    Neuerzeugung waere ein Voll-Download je Bestandsfoto.

    `probe_dimensions` heisst: der Range-Read entsteht (auch) aus der offenen Aufloesung. Das ist
    unabhaengig von der Endung - `extract_pixel_count` liest nur den Kopf, waehrend der EXIF-Teil
    weiterhin an `_EXIF_CANDIDATE_EXTENSIONS` gebunden bleibt.

    `dimensions_only` heisst: dieser Posten liest AUSSCHLIESSLICH die Aufloesung. Dann wird
    `extract_pixel_count` auf dem Range-Fenster ausgefuehrt; Zeit, Ort und Kamera bleiben
    unberuehrt (Spec 0639, ADR 0146 Punkt 2). Ein Kamera-Nachhol-Posten an einer EXIF-Endung ist
    ausdruecklich KEIN `dimensions_only`-Posten: er liest die Masse aus demselben Fenster mit.
    Eine Nicht-EXIF-Endung mit offener Kamera UND offener Auflosung ist dagegen
    `dimensions_only` - es gibt fuer sie nichts auszulesen ausser der Masse."""

    relative_path: str
    entry: DavEntry
    existing_photo: Photo | None
    probe_only: bool = False
    dimensions_only: bool = False
    probe_dimensions: bool = False


@dataclass
class ScanEntryDecision:
    """Ergebnis der Klassifikation eines einzelnen Phase-1-Eintrags: entweder ein Skip-Grund ODER
    ein Arbeitsposten, nie beides - siehe _classify_scan_entries."""

    relative_path: str
    skip_reason: SkipReason | None
    work_item: ScanWorkItem | None


@dataclass
class ScanClassification:
    """Ergebnis von _classify_scan_entries fuer die vollstaendige Phase-1-Liste.

    `decisions` behaelt bewusst die Eingabereihenfolge bei (run_project_scan iteriert sie fuer die
    Checkpoint-Kadenz von files_found/files_skipped in Phase 2a) - `work_items` ist
    eine reine Teilmenge davon (nur die Eintraege mit skip_reason is None), fuer Phase 2b."""

    decisions: list[ScanEntryDecision] = field(default_factory=list)
    work_items: list[ScanWorkItem] = field(default_factory=list)
    seen_paths: set[str] = field(default_factory=set)


def _classify_scan_entries(
    entries: list[tuple[str, DavEntry]],
    existing_photos: dict[str, Photo],
) -> ScanClassification:
    """Phase 2a: reine Funktion, keine Session-/DB-Zugriffe - isoliert unit-testbar (siehe
    test_worker_scan_classification.py). Entscheidungslogik: unsupported extension -> Skip +
    files_skipped; unveraenderter Etag UND beide Merker gesetzt (Kamera bzw. HEIC-Ausnahme UND
    Aufloesung) -> Skip ohne files_skipped; unveraenderter Etag mit offenem Kamera-Merkmal ->
    `probe_only=True` (liest Kamera UND Masse); unveraenderter Etag mit offener Aufloesung ->
    zusaetzlich `dimensions_only=True`; sonst -> voller Arbeitsposten. Die Verarbeitung selbst
    gehoert nicht hierher.

    Der `probe_only`-Zweig ist die EINMALIGE Nachhol-Runde fuer Bestandsfotos (ADR 0090,
    Konsequenzen): Ohne sie bliebe die Kameraliste in bereits gescannten Projekten leer, denn ein
    unveraendertes Foto wird nie wieder gelesen. Sie laeuft genau einmal je Foto - danach steht
    der Merker, AUCH wenn die Datei keine Kamera nennt. HEIC/HEIF sind von der KAMERA-Nachholung
    ausgenommen: diese Endungen wurden vor ihrer Unterstuetzung nie gelesen, ein Nachtrag wuerde
    Bestandsprojekte rueckwirkend veraendern. Die AUFLOESUNGS-Nachholung gilt dagegen fuer alle
    Bildendungen (ADR 0146 Punkt 2): eine geschaetzte Zahl verschoebe die Gewinnerregel, und ein
    fehlender Wert ist von einem echten Nullwert nicht zu unterscheiden."""
    classification = ScanClassification()
    for relative_path, entry in entries:
        extension = _extension(relative_path)
        if extension not in IMAGE_EXTENSIONS:
            classification.decisions.append(
                ScanEntryDecision(relative_path, SkipReason.UNSUPPORTED_EXTENSION, None)
            )
            continue

        classification.seen_paths.add(relative_path)
        existing_photo = existing_photos.get(relative_path)
        unchanged = existing_photo is not None and existing_photo.etag == entry.etag
        needs_camera_probe = (
            unchanged
            and existing_photo is not None
            and not existing_photo.camera_probed
            and extension not in _HEIC_EXTENSIONS
        )
        needs_dimensions_probe = (
            unchanged and existing_photo is not None and not existing_photo.pixel_count_probed
        )
        if unchanged and not needs_camera_probe and not needs_dimensions_probe:
            classification.decisions.append(
                ScanEntryDecision(relative_path, SkipReason.UNCHANGED_ETAG, None)
            )
            continue

        work_item = ScanWorkItem(
            relative_path,
            entry,
            existing_photo,
            probe_only=unchanged,
            # Eine offene Kamera-Pruefung deckt Zeit/Ort/Kamera nur fuer EXIF-Endungen ab. Bei
            # PNG/WebP entsteht der Range-Read allein aus der Aufloesung, und der Posten darf
            # deshalb auch nur die Aufloesung schreiben.
            dimensions_only=(
                unchanged
                and needs_dimensions_probe
                and (not needs_camera_probe or extension not in _EXIF_CANDIDATE_EXTENSIONS)
            ),
            probe_dimensions=needs_dimensions_probe,
        )
        classification.decisions.append(ScanEntryDecision(relative_path, None, work_item))
        classification.work_items.append(work_item)

    return classification


def _naive_utc(value: datetime) -> datetime:
    # Stored as naive UTC throughout (matches sqlite/Postgres TIMESTAMP WITHOUT TIME ZONE);
    # WebDAV last-modified values arrive timezone-aware and must be normalized before storing
    # so they stay comparable with EXIF-derived (always naive) timestamps.
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


async def _generate_thumbnails(
    client: OpenCloudScanClient,
    webdav_url: str,
    relative_path: str,
    photo_id: int,
    etag: str,
    cache_dir: Path,
) -> VariantResult | None:
    """Best-effort: weder ein Download- noch ein
    Dekodierfehler duerfen den Scan des Projekts abbrechen (anders als die uebrigen
    OpenCloudError-Faelle unten, die den ganzen Scan als FAILED markieren) - ein fehlendes
    Thumbnail aeussert sich nur als 404-Platzhalter im Bild-Endpunkt, siehe thumbnails.py.

    Gibt das Ergebnis der einen Dekodierung zurueck: gezeigtes Seitenverhaeltnis UND Aufloesung -
    oder `None`, wenn keine Vorschau geschrieben werden konnte (Downloadfehler, nicht dekodierbar,
    Schreibfehler).

    Nimmt bewusst `photo_id`/`etag` statt eines `Photo`-Objekts entgegen: wird als Teil
    von _fetch_and_thumbnail parallel zu Geschwister-Aufrufen desselben Blocks ausgefuehrt und darf
    deshalb keinerlei Session-Zugriff ausloesen - ein ORM-Objekt hier entgegenzunehmen wuerde dazu
    verleiten, versehentlich weitere (nicht nebenlaeufigkeitssichere) Attribute zu lesen/zu
    setzen."""
    try:
        content = await client.download(webdav_url, relative_path)
    except OpenCloudError:
        return None
    return generate_variants(cache_dir, photo_id, etag, content)


@dataclass(frozen=True)
class ScanExifResult:
    """Das EXIF-Ergebnis EINES Arbeitspostens: Zeitpunkt UND Koordinate aus demselben
    Range-Read-Fenster.

    Eingefroren und zusammengesetzt statt zweier nackter Rueckgabewerte, damit die Typzusicherung
    nach `asyncio.gather` in `_process_scan_block` weiterhin die FORM festnageln kann - eine
    durchgereichte `BaseException` (mit `return_exceptions=True` faengt `gather` ein
    `CancelledError` einer Kind-Coroutine NICHT ab) darf nicht in die Felder entpackt werden.

    `gps` ist ein Paar oder `None` - nie eine halbe Koordinate (Paar-Invariante von
    `extract_gps`).

    `taken_at` ist hier die AUFGEZEICHNETE Zeit (EXIF `DateTimeOriginal`, sonst der Rueckfall auf
    `last_modified`) - die Korrektur um den Kamera-Versatz passiert erst im sequentiellen Teil von
    `_process_scan_block`, wo die Kamerazeile und damit der Versatz bekannt sind.

    `aspect_ratio` ist das Seitenverhaeltnis des GEZEIGTEN Bildes, das die Thumbnail-Erzeugung
    ohnehin kennt - `None` fuer einen `probe_only`-Posten (es wurde gar nichts dekodiert) und fuer
    jeden Fehlerfall. Es faellt bei derselben Dekodierung an wie die Vorschau; es entsteht kein
    zusaetzlicher Abruf und kein zweites Dekodieren.

    `pixel_count` ist die Aufloesung des GEZEIGTEN Bildes. Sie kommt beim vollen Posten aus
    derselben Dekodierung, beim Nachhol-Posten aus demselben Range-Fenster wie die uebrigen
    EXIF-Werte (`extract_pixel_count`); `None` heisst "nicht lesbar" und setzt den Merker
    trotzdem."""

    taken_at: datetime
    gps: tuple[float, float] | None
    camera: CameraIdentity | None
    aspect_ratio: float | None = None
    pixel_count: int | None = None
    # Nur ein Posten an einer EXIF-Endung und ohne `dimensions_only` hat das Fenster geparst.
    # Fuer einen `probe_only`-Posten an PNG/WebP heisst `False`: Zeit und Ort NICHT schreiben.
    exif_read: bool = False


async def _fetch_and_thumbnail(
    client: OpenCloudScanClient,
    webdav_url: str,
    relative_path: str,
    extension: str,
    fallback_taken_at: datetime,
    photo_id: int,
    etag: str,
    cache_dir: Path,
    *,
    probe_only: bool = False,
    dimensions_only: bool = False,
    probe_dimensions: bool = False,
) -> ScanExifResult:
    """Der reine I/O-/CPU-Teil eines einzelnen Arbeitspostens aus Phase 2b: ein Range-Fenster fuer
    `taken_at`, die GPS-Koordinate UND die Kamera-Angabe (nur EXIF-Kandidaten), zusaetzlich die
    Aufloesung fuer jeden Dimensions-Nachhol-Posten; danach best-effort Download +
    Thumbnail-Erzeugung -
    bewusst OHNE jeglichen Session-Zugriff, damit mehrere Aufrufe sicher parallel per
    asyncio.gather laufen koennen (_process_scan_block unten). Ein EXIF-Lesefehler wird NICHT
    abgefangen: ein einzelner OpenCloud-Fehler hier laesst den gesamten Scan fehlschlagen.

    Alle DREI EXIF-Werte stammen aus DEMSELBEN bereits geladenen Byte-Fenster - kein zusaetzlicher
    Netzwerkzugriff fuer Koordinate oder Kamera. Fuer Nicht-JPEG-Posten wird gar kein EXIF
    gelesen: der Zeitpunkt faellt auf `fallback_taken_at` zurueck, Koordinate und Kamera bleiben
    `None`.

    `probe_only` ueberspringt AUSSCHLIESSLICH die Thumbnail-Erzeugung (die Nachhol-Runde der
    Kamera-Angabe an einer unveraenderten Datei - die Thumbnails existieren und waeren identisch).
    Das EXIF-Fenster wird weiterhin gelesen; genau darum geht es.

    `probe_dimensions` loest den Range-Read unabhaengig von der Endung aus: `extract_pixel_count`
    liest nur den Kopf, das ist kein zweiter Lesevorgang fuer den vollen Posten.

    `dimensions_only` liest dasselbe Fenster, aber ausschliesslich fuer die Aufloesung. Zeit, Ort
    und Kamera bleiben dann unberuehrt: Es ist die Nachhol-Runde fuer `pixel_count`, und ein
    Schreibzugriff auf die anderen Werte uebernaehme einen Stand, den dieser Posten gar nicht
    geprueft hat. `exif_read` sagt dem Schreibteil, ob ueberhaupt ein EXIF-Fenster geparst wurde -
    ein Kamera-Nachhol-Posten an einer Nicht-EXIF-Endung setzt nur den Kamera-Merker."""
    taken_at = fallback_taken_at
    gps: tuple[float, float] | None = None
    camera: CameraIdentity | None = None
    pixel_count: int | None = None
    exif_read = False
    if extension in _EXIF_CANDIDATE_EXTENSIONS or probe_dimensions:
        content = await client.get_range(webdav_url, relative_path, _EXIF_RANGE_BYTES)
        if not dimensions_only:
            exif_taken_at = extract_taken_at(content)
            if exif_taken_at is not None:
                taken_at = exif_taken_at
            gps = extract_gps(content, photo_id=photo_id)
            camera = extract_camera(content, photo_id=photo_id)
            exif_read = extension in _EXIF_CANDIDATE_EXTENSIONS
        pixel_count = extract_pixel_count(content)

    aspect_ratio: float | None = None
    if not probe_only:
        variants = await _generate_thumbnails(
            client, webdav_url, relative_path, photo_id, etag, cache_dir
        )
        if variants is not None:
            aspect_ratio = variants.aspect_ratio
            # Die Dekodierung der Vorschau ist die genauere Quelle (sie kennt die gedrehte
            # Ansicht); der Kopfwert traegt nur, wenn das Bild nicht dekodierbar war.
            pixel_count = variants.pixel_count
    return ScanExifResult(
        taken_at=taken_at,
        gps=gps,
        camera=camera,
        aspect_ratio=aspect_ratio,
        pixel_count=pixel_count,
        exif_read=exif_read,
    )


async def _resolve_project_camera(
    session: AsyncSession,
    project_id: int,
    identity: CameraIdentity,
    cache: dict[tuple[str, str], ProjectCamera],
) -> ProjectCamera:
    """Die Kamerazeile DIESES Projekts zur uebergebenen Identitaet - angelegt, falls es sie noch
    nicht gibt, mit `offset_minutes = 0`.

    Der `cache` wird von `run_project_scan` ueber alle Bloecke eines Laufs durchgereicht: ohne ihn
    entstuende eine Abfrage JE FOTO statt je Kamera, und ein Projekt hat typischerweise zwei
    Kameras und tausende Fotos.

    SICHERHEIT (Projektgrenze): `project_id` steht in derselben Anweisung, die die Zeile
    aufloest - `Photo.camera_id` zeigt damit ausschliesslich auf eine Zeile desselben Projekts."""
    key = (identity.make, identity.model)
    cached = cache.get(key)
    if cached is not None:
        return cached

    existing = (
        await session.execute(
            select(ProjectCamera).where(
                ProjectCamera.project_id == project_id,
                ProjectCamera.make == identity.make,
                ProjectCamera.model == identity.model,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = ProjectCamera(
            project_id=project_id, make=identity.make, model=identity.model, offset_minutes=0
        )
        session.add(existing)
        await session.flush()
    cache[key] = existing
    return existing


async def _process_scan_block(
    session: AsyncSession,
    client: OpenCloudScanClient,
    webdav_url: str,
    cache_dir: Path,
    project_id: int,
    block: list[ScanWorkItem],
    camera_cache: dict[tuple[str, str], ProjectCamera] | None = None,
) -> tuple[int, int]:
    """Verarbeitet einen einzelnen Block von Arbeitsposten, Blockgröße
    settings.scan_download_concurrency: zunächst sequentiell Photo-Zeilen
    anlegen/aktualisieren + flush() - KEIN commit() hier, ein
    Absturz in diesem Fenster ist dadurch folgenlos, die Transaktion wird beim Neuverbinden
    verworfen), danach die reinen I/O-Coroutinen des Blocks parallel per asyncio.gather. Der
    Aufrufer (run_project_scan) committet erst NACH erfolgreicher Rueckkehr dieser Funktion - ein
    Commit pro vollstaendig abgearbeitetem Block. Gibt (photos_added, photos_updated) fuer diesen
    Block zurueck."""
    photos: list[Photo] = []
    added = 0
    updated = 0
    for item in block:
        last_modified = (
            _naive_utc(item.entry.last_modified) if item.entry.last_modified else runs._now_utc()
        )
        if item.existing_photo is not None:
            photo = item.existing_photo
            photo.etag = item.entry.etag or ""
            photo.content_length = item.entry.content_length or 0
            photo.last_modified = last_modified
            updated += 1
        else:
            photo = Photo(
                project_id=project_id,
                relative_path=item.relative_path,
                etag=item.entry.etag or "",
                content_length=item.entry.content_length or 0,
                # Beide vorlaeufig, beide werden unten nach dem gather() ersetzt - erst dort
                # steht der EXIF-Wert fest. `taken_at_original` ist NOT NULL ohne Default und
                # muss deshalb schon hier einen Wert tragen.
                taken_at=last_modified,
                taken_at_original=last_modified,
                last_modified=last_modified,
            )
            session.add(photo)
            added += 1
        photos.append(photo)

    if added:
        # Nur neu angelegte Zeilen brauchen flush() fuer eine DB-vergebene ID (fuer den
        # Thumbnail-Dateinamen unten) - bereits bestehende Zeilen haben schon eine ID.
        await session.flush()

    results = await asyncio.gather(
        *[
            _fetch_and_thumbnail(
                client,
                webdav_url,
                item.relative_path,
                _extension(item.relative_path),
                photos[index].last_modified,
                photos[index].id,
                photos[index].etag,
                cache_dir,
                probe_only=item.probe_only,
                dimensions_only=item.dimensions_only,
                probe_dimensions=item.probe_dimensions,
            )
            for index, item in enumerate(block)
        ],
        return_exceptions=True,
    )

    # Python-Async-Fallstrick: mit return_exceptions=True faengt asyncio.gather() ein
    # CancelledError, das eine EINZELNE Kind-Coroutine wirft, NICHT als Exception ab, sondern
    # reicht es als gewoehnliches Element der Ergebnisliste durch - `await gather(...)` selbst
    # wirft in diesem Fall NICHTS. Ohne diese explizite Pruefung erreichte ein Abbruch mitten in
    # einer parallelen I/O-Coroutine den `except asyncio.CancelledError`-Zweig in run_project_scan
    # nicht. Eine ECHTE aeussere Task-Cancellation (arq job_timeout) propagiert dagegen ohne
    # Sonderbehandlung roh durch `await gather(...)` hindurch - dieser Fall betrifft ausschliesslich
    # eine Kind-Coroutine, die CancelledError selbst wirft/traegt.
    # Bricht in tests/test_worker_scan_project.py.
    for result in results:
        if isinstance(result, asyncio.CancelledError):
            raise result
    for result in results:
        if isinstance(result, BaseException):
            raise result

    cache = {} if camera_cache is None else camera_cache
    for photo, exif_result, item in zip(photos, results, block, strict=True):
        # Die Typzusicherung nagelt die FORM fest: ohne sie entpackte eine durchgereichte
        # BaseException ihre Attribute in die Foto-Felder, statt oben als Fehler erkannt zu werden.
        assert isinstance(exif_result, ScanExifResult)  # bereits oben auf Exceptions geprueft

        # Ein `dimensions_only`-Posten liest NUR die Masse: Zeit, Ort und Kamera bleiben
        # unberuehrt, weil er ueber sie nichts geprueft hat. Ein Schreiben uebernaehme hier einen
        # Stand, den der Posten gar nicht gelesen hat.
        if not item.dimensions_only:
            # UNBEDINGT schreiben, auch zurueck auf None - dieselbe Begruendung wie bei `gps_lat`
            # unten: verliert eine Datei ihre Kamera-Angabe, verliert das Foto sie auch. Der
            # Merker wird AUCH OHNE FUND gesetzt, sonst liest jeder weitere Scan den Bestand
            # erneut.
            camera = (
                None
                if exif_result.camera is None
                else await _resolve_project_camera(session, project_id, exif_result.camera, cache)
            )
            photo.camera_id = None if camera is None else camera.id
            photo.camera_probed = True

            # Eine Nicht-EXIF-Endung hat fuer Zeit und Ort nichts gelesen. Ein Voll-Posten
            # schreibt den Rueckfall weiterhin, ein Nachhol-Posten uebernaehme sonst den
            # WebDAV-Zeitstempel und loeschte die vorhandene Koordinate.
            if exif_result.exif_read or not item.probe_only:
                # DIE ERSTE der zwei Schreibstellen der Invariante (ADR 0090, Punkt 1; die zweite
                # ist `api/cameras.py`), und beide rechnen ueber `cameras.py::shifted` aus
                # `taken_at_original` - NIE aus dem bestehenden `taken_at`. Eine Differenz auf den
                # bestehenden Wert zu addieren kumulierte bei jedem weiteren Lauf.
                photo.taken_at_original = exif_result.taken_at
                offset_minutes = 0 if camera is None else camera.offset_minutes
                corrected = shifted(exif_result.taken_at, offset_minutes)
                if corrected is None:
                    # Ausfallrichtung fuer dieses EINE Foto: die unkorrigierte Zeit plus eine
                    # Warnzeile mit festem Token - kein Laufabbruch und kein Datum ausserhalb des
                    # darstellbaren Bereichs. Die Invariante ist fuer dieses Foto damit bewusst
                    # verletzt; ein Versatz, der das ausloest, ist am Endpunkt gar nicht setzbar
                    # (dort 422).
                    runs.logger.warning(
                        "_process_scan_block: Versatz nicht anwendbar photo_id=%s grund=%s",
                        photo.id,
                        _OFFSET_REASON_OUT_OF_RANGE,
                    )
                photo.taken_at = exif_result.taken_at if corrected is None else corrected
                # SICHERHEIT: UNBEDINGT beide Felder schreiben, auch zurueck auf None. Das ist
                # eine DATENSCHUTZBEDINGUNG, keine Aufraeum-Kosmetik - dies ist der einzige Pfad,
                # ueber den das ENTFERNEN von GPS aus einer Quelldatei in PhotoSort ankommt, also
                # genau die Handlung, die eine datenschutzbewusste Person vornimmt. Ein bedingtes
                # Schreiben (`if gps is not None`) hielte die alte Koordinate unbegrenzt fest, und
                # die Anwendung zeigte weiter einen Ort an, den die Datei nachweislich nicht mehr
                # enthaelt. Abgedeckt durch test_worker_scan_project.py.
                photo.gps_lat, photo.gps_lon = exif_result.gps or (None, None)

        # ERSTER der zwei Schreibwege der Spalte (ADR 0110 Punkt 3). Fuer einen Posten, der die
        # Datei tatsaechlich gelesen hat, wird UNBEDINGT geschrieben - auch zurueck auf `None`:
        # Aendert eine Datei ihre Form, aendert das Foto sie mit, und ein nicht mehr dekodierbares
        # Bild verliert seine Angabe, statt eine falsche zu behalten. Zurueck auf `None` heisst
        # dabei nichts Endgueltiges: `aspect_ratio IS NULL` ist zugleich die Arbeitsmenge der
        # Nachhol-Runde, die es beim naechsten Lauf erneut versucht.
        #
        # Ein `probe_only`-Posten wird dabei UEBERSPRUNGEN statt auf `None` gesetzt: Er hat die
        # Datei gar nicht geladen (das ist sein ganzer Zweck) und weiss deshalb nichts ueber ihre
        # Form. Ein unbedingtes Schreiben loeschte hier bei jedem Scan einen bereits bekannten,
        # unveraendert gueltigen Wert.
        if not item.probe_only:
            photo.aspect_ratio = exif_result.aspect_ratio

        # ZWEITER Schreibweg der Aufloesung (neben `generate_variants`): Jeder Posten, der die
        # Aufloesung prueft, schreibt Wert und Merker - der volle Posten aus der einen Dekodierung,
        # der Nachhol-Posten aus dem Range-Fenster. Ein Kamera-Nachhol-Posten an einer
        # Nicht-EXIF-Endung hat kein Fenster gelesen und laesst den bekannten Wert stehen. Der
        # Merker faellt AUCH OHNE FUND, sonst laese jeder Scan denselben Bestand erneut ueber das
        # Netz; ein `None` ist dann ehrlich "nicht lesbar" und keine Schaetzung.
        if not item.probe_only or item.probe_dimensions:
            photo.pixel_count = exif_result.pixel_count
            photo.pixel_count_probed = True
    return added, updated


async def _maybe_commit_progress_checkpoint(
    session: AsyncSession, run: ScanRun, count: int
) -> None:
    """Gemeinsamer Zwischen-Commit-Checkpoint für Phase 1 (Enumeration) UND Phase 2a
    (Skip-Fälle) - ein einziger Aufrufpunkt statt zweier `continue`-Zweige:
    strukturell ausgeschlossen, dass ein Skip-Zweig den Checkpoint verpasst, da jede Iteration in
    Phase 2a denselben Aufruf durchlaeuft."""
    if count % SCAN_COMMIT_BATCH_SIZE == 0:
        run.files_found = count
        run.last_progress_at = runs._now_utc()
        await session.commit()


async def _enumerate_scan_entries(
    session: AsyncSession,
    client: OpenCloudScanClient,
    webdav_url: str,
    root_path: str,
    scan_run: ScanRun,
) -> list[tuple[str, DavEntry]]:
    """Phase 1 (Enumeration): materialisiert `client.walk(...)` zu einer In-Memory-Liste - KEIN
    Photo-DB-Schreibzugriff, nur periodische files_found/last_progress_at-Checkpoints (bestehende
    Checkpoint-Kadenz, Zweitverwendung von _maybe_commit_progress_checkpoint). Erst nach
    vollstaendigem Abschluss ist die Gesamtzahl bekannt (run_project_scan setzt danach
    ScanRun.total_files)."""
    entries: list[tuple[str, DavEntry]] = []
    files_found = 0
    entry: DavEntry
    async for relative_path, entry in client.walk(webdav_url, root_path):
        entries.append((relative_path, entry))
        files_found += 1
        await _maybe_commit_progress_checkpoint(session, scan_run, files_found)
    return entries


# Blockgroesse der Nachhol-Runde: je Block ein Commit und ein Fortschrittsstempel (Auflage S1).
# Modul-Konstante statt Default-Parameterwert, damit Tests sie per
# monkeypatch.setattr(worker, "ASPECT_RATIO_CATCH_UP_BATCH_SIZE", ...) verkleinern koennen -
# dasselbe Muster wie SCAN_COMMIT_BATCH_SIZE.
ASPECT_RATIO_CATCH_UP_BATCH_SIZE = 200


# Das aus der VORSCHAU gelesene Verhaeltnis ist wegen der Ganzzahl-Skalierung beim Erzeugen der
# Vorschau nicht exakt das des Originals. Diese relative Abweichung ist die zugesicherte Grenze;
# sie wird nie auf Gleichheit mit dem Scan-Weg geprueft. Bei THUMBNAIL_MAX_SIZE = 400 kann die
# kurze Kante um hoechstens eine halbe Pixelzeile danebenliegen - eine relative Abweichung von
# unter einem Prozent, und damit weit unterhalb dessen, was im Raster sichtbar waere.
ASPECT_RATIO_PREVIEW_TOLERANCE = 0.01


def _read_cached_aspect_ratios(
    cache_dir: Path, photos: Sequence[tuple[int, str]]
) -> list[tuple[int, float]]:
    """Liest das Seitenverhaeltnis der uebergebenen `(photo_id, etag)`-Paare aus ihrer lokalen
    Vorschau-Variante. Ein Paar ohne lesbare Datei kommt schlicht nicht zurueck.

    Rein synchron und ohne DB-Bezug (deshalb Tupel statt ORM-Objekten), genau wie
    `thumbnails.measure_cache_usage`: Der Aufrufer fuehrt sie ueber `asyncio.to_thread` aus, damit
    die Event-Loop bei einem Dateisystemzugriff je Foto nicht blockiert.

    SICHERHEIT (Auflage S4): Der Pfad entsteht AUSSCHLIESSLICH ueber `thumbnails.thumbnail_path`.
    Der `etag` kommt vom WebDAV-Server, ist damit Fremdtext und geht dort nur als SHA-256-Eingabe
    in `cache_key` ein, nie in einen Dateinamen. Jede zweite Pfadbildung, die `etag` oder
    `relative_path` als Namensbestandteil verwendet, bleibt untersagt: ein `etag` mit `../` laese
    sonst aus einem beliebigen Pfad ausserhalb des Cache-Verzeichnisses.

    SICHERHEIT (Auflage S2): Je Foto isoliert - die Fehlerbehandlung liegt vollstaendig in
    `aspect_ratio_of_cached_thumbnail` (bewusst breites `except Exception`). Hier steht deshalb
    kein zweiter, engerer Block."""
    ratios: list[tuple[int, float]] = []
    for photo_id, etag in photos:
        ratio = aspect_ratio_of_cached_thumbnail(thumbnail_path(cache_dir, photo_id, etag))
        if ratio is not None:
            ratios.append((photo_id, ratio))
    return ratios


async def _catch_up_aspect_ratios(
    session: AsyncSession, project_id: int, cache_dir: Path, run: ScanRun
) -> int:
    """Fuellt `Photo.aspect_ratio` fuer die Bestandsfotos des Projekts aus deren lokal
    zwischengespeichertem Vorschaubild - ohne Netz, ohne OpenCloud-Abruf, ohne das Original
    (ADR 0110 Punkt 3). Gibt die Zahl der gefuellten Zeilen zurueck.

    Die Arbeitsmenge ist `aspect_ratio IS NULL` und damit zugleich die Abbruchbedingung: Es gibt
    KEINE Merker-Spalte nach dem Muster von `camera_probed`. Der Merker dort verhindert einen
    wiederholten NETZZUGRIFF je Bestandsfoto; hier kostet ein erneuter Versuch einen lokalen
    Dateizugriff. Fehlt die Cache-Datei, bleibt der Wert `NULL` und der naechste Scan versucht es
    erneut.

    SICHERHEIT (Auflage S1): Je Block wird committet UND `ScanRun.last_progress_at` gesetzt.
    Diese Runde laeuft VOR Phase 1 und damit vor dem ersten Stempel, den `run_project_scan` sonst
    setzt. Ohne eigene Commit-Punkte setzte `reap_stalled_runs` einen Lauf, dessen Runde laenger
    als `STALL_THRESHOLD` (15 Minuten) ohne Stempel arbeitet, auf FAILED - und braeche die
    Coroutine dabei bewusst NICHT ab. Der Scan liefe weiter, waehrend die Oberflaeche
    "fehlgeschlagen" sagt.

    SICHERHEIT (Auflage S1, zweiter Teil): Geladen werden je Foto nur `id` und `etag`, nie ganze
    `Photo`-Objekte ueber den gesamten Bestand - ein `select(Photo)` zoege bei zehntausenden
    Bestandsfotos ebenso viele ORM-Objekte in die Sitzung."""
    rows = (
        (
            await session.execute(
                select(Photo.id, Photo.etag).where(
                    Photo.project_id == project_id,
                    Photo.aspect_ratio.is_(None),
                )
            )
        )
        .tuples()
        .all()
    )
    filled = 0
    for start in range(0, len(rows), ASPECT_RATIO_CATCH_UP_BATCH_SIZE):
        await runs._raise_if_cancel_requested(session, run)
        block = list(rows[start : start + ASPECT_RATIO_CATCH_UP_BATCH_SIZE])
        ratios = await asyncio.to_thread(_read_cached_aspect_ratios, cache_dir, block)
        for photo_id, ratio in ratios:
            await session.execute(
                update(Photo).where(Photo.id == photo_id).values(aspect_ratio=ratio)
            )
        filled += len(ratios)
        run.last_progress_at = runs._now_utc()
        await session.commit()
    return filled


async def run_project_scan(
    session: AsyncSession,
    client: OpenCloudScanClient,
    project: Project,
    drive_name: str | None,
    cache_dir: Path,
    *,
    run_id: int | None = None,
) -> ScanRun | None:
    """Der Scan-Lauf. Mit `run_id` uebernimmt er den von der API angelegten, wartenden Lauf und
    endet ohne jede Arbeit (None), wenn der in der Warteschlange abgebrochen wurde; ohne `run_id`
    legt er die Zeile selbst an.

    Ein Abbruchwunsch wird vor jedem Block gelesen. Was bis dahin committet ist - Fotos,
    Vorschaubilder, Zaehler -, bleibt; verschwundene Fotos werden dann NICHT entfernt und der
    Bild-Cache nicht aufgeraeumt, weil der Lauf den Ordnerbaum nicht vollstaendig gesehen hat."""
    if run_id is not None:
        scan_run = await runs._take_over_queued_run(session, ScanRun, run_id)
        if scan_run is None:
            return None
    else:
        scan_run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING)
        session.add(scan_run)
        await session.commit()
        await session.refresh(scan_run)

    try:
        # Nachhol-Runde fuer den Bestand, VOR Phase 1 und vor jedem Netzzugriff dieses Laufs
        # (ADR 0110 Punkt 3). Sie steht bewusst vor dem Laden von `existing_photos`: So schreibt
        # sie ausschliesslich per UPDATE-Anweisung und kann keine ORM-Objekte hinter dem Ruecken
        # der Sitzung veraltern lassen.
        await _catch_up_aspect_ratios(session, project.id, cache_dir, scan_run)

        drive = await client.resolve_drive(drive_name)

        existing_photos = {
            photo.relative_path: photo
            for photo in (
                await session.execute(select(Photo).where(Photo.project_id == project.id))
            ).scalars()
        }

        # Phase 1 (Enumeration) - siehe _enumerate_scan_entries.
        entries = await _enumerate_scan_entries(
            session, client, drive.webdav_url, project.opencloud_path, scan_run
        )

        # Phasenuebergang: total_files wird HIER einmalig gesetzt, files_found auf 0
        # zurueckgesetzt - das Feld wechselt die Bedeutung von "in Phase 1 gelistet" auf "in
        # Phase 2 verarbeitet". Sofort committet, damit ein zwischen Phase 1 und Phase 2
        # beobachtender Client (Polling) diesen konsistenten Zwischenzustand sehen kann
        # (total_files gesetzt, files_found == 0).
        scan_run.total_files = len(entries)
        scan_run.files_found = 0
        scan_run.last_progress_at = runs._now_utc()
        await session.commit()

        # Phase 2a (Klassifikation, reine Funktion) - siehe _classify_scan_entries.
        await runs._raise_if_cancel_requested(session, scan_run)
        classification = _classify_scan_entries(entries, existing_photos)

        files_found = 0
        files_skipped = 0
        for decision in classification.decisions:
            if decision.skip_reason is not None:
                files_found += 1
                if decision.skip_reason is SkipReason.UNSUPPORTED_EXTENSION:
                    files_skipped += 1
                await _maybe_commit_progress_checkpoint(session, scan_run, files_found)

        # Phase 2b (begrenzt parallele Verarbeitung in festen Bloecken) - siehe
        # _process_scan_block. Blockgroesse = settings.scan_download_concurrency
        # (env-ueberschreibbar); ein Commit PRO BLOCK (nicht an die SCAN_COMMIT_BATCH_SIZE-Kadenz
        # von Phase 1/2a gekoppelt), das ist zugleich die Crash-Sicherheits-Grenze.
        photos_added = 0
        photos_updated = 0
        # settings.scan_download_concurrency ist per Field(ge=1) in config.py bereits gegen
        # 0/negative Werte validiert und fällt beim Prozessstart auf - kein zusätzlicher
        # Laufzeit-Clamp hier nötig.
        concurrency = settings.scan_download_concurrency
        work_items = classification.work_items
        # EIN Cache ueber alle Bloecke des Laufs: sonst eine Kamera-Abfrage je Foto statt je
        # Kamera. Er haelt ORM-Objekte derselben Sitzung, die der Lauf ohnehin durchgaengig
        # benutzt.
        camera_cache: dict[tuple[str, str], ProjectCamera] = {}
        for start in range(0, len(work_items), concurrency):
            await runs._raise_if_cancel_requested(session, scan_run)
            block = work_items[start : start + concurrency]
            added, updated = await _process_scan_block(
                session, client, drive.webdav_url, cache_dir, project.id, block, camera_cache
            )
            photos_added += added
            photos_updated += updated
            files_found += len(block)
            scan_run.files_found = files_found
            scan_run.last_progress_at = runs._now_utc()
            await session.commit()

        # Letzter Pruefpunkt VOR dem Entfernen: ein Abbruch nach dem letzten Block endet
        # ebenfalls `cancelled`, und ein abgebrochener Lauf entfernt nichts.
        await runs._raise_if_cancel_requested(session, scan_run)
        removed_paths = set(existing_photos) - classification.seen_paths
        for path in removed_paths:
            await session.delete(existing_photos[path])

        scan_run.status = ScanStatus.SUCCESS
        scan_run.finished_at = runs._now_utc()
        scan_run.files_found = files_found
        scan_run.photos_added = photos_added
        scan_run.photos_updated = photos_updated
        scan_run.photos_removed = len(removed_paths)
        scan_run.files_skipped = files_skipped
        await session.commit()
    except RunCancelled:
        await runs._finish_cancelled(session, scan_run)
        return scan_run
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs: ein arq job_timeout-Ablauf, ein geplanter
        # Worker-Shutdown und ein künftiger Job.abort() lösen alle denselben
        # asyncio.CancelledError-Pfad aus. Er wird bewusst NICHT unbehandelt durchgelassen: der
        # Lauf wird sofort auf FAILED gesetzt, danach re-raised - kein Verschlucken einer
        # BaseException, arqs eigene Task-/Retry-Buchhaltung funktioniert dadurch unverändert
        # weiter.
        await runs._fail_run(
            session, scan_run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."
        )
        raise
    except Exception as exc:
        # BREIT abfangen, nicht nur OpenCloudError: jede andere Exception (z.B. aus dem
        # WebDAV-XML-Parsing, siehe opencloud/client.py::list_folder) liefe sonst ungefangen durch
        # und liesse den ScanRun dauerhaft auf status="running" haengen, ohne Watchdog/Recovery.
        # OpenCloudError ist eine Teilmenge von Exception, ein einzelner breiter Handler reicht
        # deshalb aus - dasselbe Muster wie in run_project_scoring unten.
        await runs._fail_run(session, scan_run, str(exc))
        return scan_run

    # Ab hier ist der Lauf SUCCESS: der Erfolgspfad faellt aus dem `try` HERAUS, beide
    # Fehlerzweige kehren oben zurueck bzw. re-raisen. Damit erreicht die Bereinigung den Abbruch-
    # und den Fehlerpfad strukturell nicht (bei Abbruch/Fehlschlag wird nicht aufgeraeumt, der
    # naechste erfolgreiche Scan holt es nach).
    #
    # AUSSERHALB des Fehler-Handlers und mit eigenem `except`: ein Fehler beim Aufraeumen darf
    # einen bereits erfolgreichen Lauf nicht nachtraeglich auf FAILED setzen. Der unmittelbar
    # vorangehende `commit()` ist zugleich der Commit-Rand, nach dem der Schnappschuss der
    # Bereinigung gezogen wird.
    try:
        await cleanup_orphaned_cache(session, cache_dir)
    except Exception:
        # Das `rollback()` ist keine Kosmetik: schlaegt die Schnappschuss-Abfrage fehl, bliebe die
        # Transaktion sonst blockiert. Es expired aber alle ORM-Objekte der Session - ohne das
        # anschliessende `refresh()` liefe der Attributzugriff auf `scan_run.id` in `scan_project`
        # in einen impliziten Lazy-Load ausserhalb eines aktiven greenlet-Kontexts
        # (sqlalchemy.exc.MissingGreenlet), und der Job stuerzte NACH einem erfolgreichen Scan ab.
        await session.rollback()
        await session.refresh(scan_run)
        runs.logger.warning("Bereinigung des Bild-Caches fehlgeschlagen", exc_info=True)
    return scan_run


async def scan_project(
    ctx: dict[str, Any], project_id: int, run_id: int | None = None
) -> int | None:
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        async with OpenCloudClient(
            settings.opencloud_base_url, settings.opencloud_username, settings.opencloud_app_token
        ) as client:
            scan_run = await run_project_scan(
                session,
                client,
                project,
                settings.opencloud_drive_name or None,
                cache_dir=Path(settings.photo_cache_dir),
                run_id=run_id,
            )
        return scan_run.id if scan_run is not None else None
