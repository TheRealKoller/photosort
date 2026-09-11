"""Bereinigung verwaister Bildkopien nach jedem erfolgreichen Scan (Spec 0349, ADR 0076).

Eigenes Modul wie `project_deletion.py` und bewusst NICHT in `worker.py`: die async-Klammer um den
Verzeichnisdurchgang ist eine abgeschlossene Aufgabe mit einer einzigen Datenbankabfrage, und
`worker.py` ist bereits gross genug. Die reine, DB-freie Mechanik darunter
(`collect_cache_entries`/`delete_orphaned_entries`) lebt in `thumbnails.py`, wo auch die
Pfadbildung liegt, die das Muster wiedererkennt.

Der Defekt, den das behebt: `cache_key` ist `sha256(f"{photo_id}:{etag}")`. Dieselbe Rechnung, die
eine alte Fassung unerreichbar macht, laesst sie auch aus jeder Loeschmenge herausfallen -
`api/photos.py`, `measure_cache_usage` und `delete_cached_variants` rechnen alle drei aus
VORHANDENEN Zeilen. Was zu keiner Zeile mehr gehoert, ist deshalb weder sichtbar noch loeschbar.
Wer diese Dateien finden will, muss das Verzeichnis lesen - genau einmal, an genau dieser Stelle.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import Photo
from photosort.thumbnails import (
    CacheSweepResult,
    cache_key,
    collect_cache_entries,
    delete_orphaned_entries,
)

logger = logging.getLogger(__name__)

CACHE_CLEANUP_GRACE_SECONDS = 3600
"""Schonfrist: juenger als eine Stunde wird nichts entfernt.

Sie traegt das Nebenlaeufigkeitskriterium der Spec. Ein paralleler Scan schreibt die Cache-Datei
VOR dem Commit der Foto-Zeile (`_process_scan_block`: Zeile anlegen/`flush()` -> Download +
Thumbnail -> Commit erst nach dem ganzen Block). In diesem Fenster ist die Datei da und die Zeile
fuer uns unsichtbar - eine rein datenbankbasierte Bereinigung loeschte genau das, was der andere
Scan gerade erzeugt. Eine Datei, deren Zeile noch nicht committet ist, wurde zwangslaeufig eben
erst geschrieben: Jugend schuetzt. Ein Scan committet spaetestens je Block
(`settings.scan_download_concurrency`, Vorgabe 4); eine Stunde liegt um Groessenordnungen darueber.

Bewusst eine KONSTANTE und keine Umgebungsvariable: ein Korrektheitsabstand, kein
Betriebsparameter. Als Einstellung luede der Wert dazu ein, ihn auf 0 zu setzen und damit das
Nebenlaeufigkeitskriterium still aufzugeben."""


async def cleanup_orphaned_cache(session: AsyncSession, cache_dir: Path) -> CacheSweepResult:
    """Entfernt aus `cache_dir` die gemusterten Dateien, die zu keinem vorhandenen Foto in seiner
    aktuellen Fassung gehoeren und aelter als die Schonfrist sind.

    Die REIHENFOLGE ist Teil der Loesung und keine Geschmackssache: erst das Verzeichnis aufnehmen,
    DANN den Datenbank-Schnappschuss ziehen. Nur so ist jede Zeile, die zwischen beiden Zeitpunkten
    committet wird, im Schnappschuss enthalten und schuetzt ihre Datei; umgekehrt waere jede in
    diesem Fenster sichtbar gewordene Datei ungeschuetzt. Der Aufrufer committet unmittelbar davor,
    der Schnappschuss wird also nach einem Commit-Rand gezogen und sieht den aktuellen Stand
    fremder Transaktionen.

    Die Gueltigkeitsmenge umfasst die Fotos ALLER Projekte - `select(Photo.id, Photo.etag)` ohne
    `where` (Security-Muss-Kriterium 4). Der Cache ist flach und projektuebergreifend; eine
    projektbezogene Menge waere fuer ihn die falsche Frage und loeschte fremde, gueltige Kopien.
    Jeder kuenftige Filter an dieser Abfrage (Soft-Delete-Flag, "nur aktive Projekte", eine
    Nutzergrenze) machte aus einer Bereinigung eine Loeschung fremder, gueltiger Bilddaten.
    Spalten-Tupel statt `select(Photo)`: keine ORM-Objekte, kein Identity-Map-Effekt nach dem
    Commit.

    Beide Dateiteile laufen ueber `asyncio.to_thread`, damit die Event-Loop bei mehreren tausend
    `stat`-/`unlink`-Aufrufen nicht blockiert - dasselbe Muster wie bei `measure_cache_usage`.

    Abschluss ist GENAU EINE INFO-Zeile aus reinen Zahlen. Pfade stehen ausschliesslich in der
    WARNING-Zeile eines Einzelfehlers und nie in einer HTTP-Antwort.
    """
    entries = await asyncio.to_thread(collect_cache_entries, cache_dir)

    rows = (await session.execute(select(Photo.id, Photo.etag))).all()
    valid_keys = {cache_key(photo_id, etag) for photo_id, etag in rows}

    # Beide Uhren stammen aus derselben Quelle (Host-Kernel: `st_mtime` und `time.time()`);
    # verglichen wird NIE gegen einen Datenbank-Zeitstempel.
    cutoff = time.time() - CACHE_CLEANUP_GRACE_SECONDS

    result = await asyncio.to_thread(delete_orphaned_entries, entries, valid_keys, cutoff)

    logger.info(
        "Bild-Cache bereinigt: %d Datei(en) entfernt, %d Byte freigegeben, "
        "%d Fehlschlag/Fehlschlaege, %d wegen Schonfrist behalten.",
        result.deleted_files,
        result.freed_bytes,
        result.failed_files,
        result.kept_recent,
    )
    return result
