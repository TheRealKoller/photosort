"""Der Export-Lauf: Zielordner, Schnappschuss, COPY je Foto."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker._runs as runs
from photosort.config import settings
from photosort.db import async_session_factory
from photosort.final_selection import included_photos
from photosort.models import (
    ExportPhoto,
    ExportRun,
    ExportRunStatus,
    Project,
)
from photosort.opencloud.client import OpenCloudClient, OpenCloudError, join_remote_path
from photosort.run_cancel import cancel_requested


class ExportClient(Protocol):
    """The subset of OpenCloudClient that export needs — narrow, so tests can fake it and record
    which write operation went where (the first time tests assert *what is written where*)."""

    async def resolve_drive(self, name: str | None) -> Any: ...

    async def mkcol(self, webdav_url: str, path: str) -> None: ...

    async def copy(self, webdav_url: str, source_path: str, dest_url: str) -> None: ...


# Der feste Wurzelordner des Exports - eine Modulkonstante, KEIN Env-Parameter. Er begrenzt den
# ersten Schreibpfad der Anwendung auf OpenCloud strukturell: Jede Schreiboperation (MKCOL/COPY)
# liegt unter diesem einen Ordner (Security Muss, ADR 0136).
EXPORT_ROOT_FOLDER = "PhotoSort-Export"


# Obergrenze der Ordnernamen-Laenge nach der Bereinigung - begrenzt einen Freitext (`Project.name`)
# als Pfadbestandteil eines HTTP-Headers, nicht die Benutzung.
EXPORT_FOLDER_NAME_MAX_LENGTH = 200


# Checkpoint-Granularitaet der je-Foto-Ergebnisse: je Block werden `exported_count`/`failed_count`,
# `last_progress_at` und die bereits geschriebenen `export_photos.error`-Zeilen committet. Ein
# Abbruch mitten im Lauf verliert so hoechstens die Ergebnisse des letzten Blocks statt des
# ganzen Laufs (AK8 "nachvollziehbar").
EXPORT_COMMIT_BATCH_SIZE = 50


# Die C0/C1-Steuerzeichen, die aus dem Ordnernamen entfernt werden. U+007F (DEL) ist C0, U+0080-
# U+009F sind C1. Ein Steuerzeichen im `Destination`-Header waere eine Header-Injection; sie
# gehoeren deshalb nicht in den Ordnernamen (Security Muss).
_CONTROL_CHARS = frozenset(
    [chr(c) for c in range(0x20)] + [chr(0x7F)] + [chr(c) for c in range(0x80, 0xA0)]
)


def sanitize_project_name(name: str) -> str:
    """Bereinigt den Projektnamen fuer den Zielordnernamen (ADR 0136 Punkt 2, Security Muss).

    Entfernt werden C0/C1-Steuerzeichen sowie Schraeg- und Rueckwaertsschraegstrich; anschliessend
    wird Leerraum zusammengezogen und die Laenge begrenzt. Reine Punkt-Namen (`.`, `..`) werden
    geleert, damit kein `..`-Segment entsteht - die Rueckfallebene ist `join_remote_path`'s `..`-Ablehnung,
    nicht der alleinige Schutz."""
    cleaned = "".join(ch for ch in name if ch not in _CONTROL_CHARS)
    cleaned = cleaned.replace("/", " ").replace("\\", " ")
    cleaned = " ".join(cleaned.split())
    if cleaned.strip(".") == "":
        cleaned = ""
    return cleaned[:EXPORT_FOLDER_NAME_MAX_LENGTH].rstrip()


def build_export_folder_name(project_name: str, now: datetime) -> str:
    """`<bereinigter Projektname> <YYYY-MM-DD HH-MM-SS.ffffff>` - dateisystem-/WebDAV-sicher, ohne
    `:` im Zeitstempel, mit Mikrosekunden fuer strukturelle Eindeutigkeit (ADR 0136 Punkt 2)."""
    timestamp = now.strftime("%Y-%m-%d %H-%M-%S.%f")
    name = sanitize_project_name(project_name)
    return f"{name} {timestamp}".strip()


def _parent_folders(relative_path: str) -> list[str]:
    """Die Unterordner eines `relative_path` (ohne den Dateinamen), in Einfuegetiefe - die MKCOL-
    Menge, die den Zielordner die Quellstruktur spiegeln laesst (ADR 0136 Punkt 2)."""
    parts = [part for part in relative_path.split("/") if part][:-1]
    folders: list[str] = []
    current = ""
    for part in parts:
        current = f"{current}/{part}" if current else part
        folders.append(current)
    return folders


def _export_overlaps_scan_root(opencloud_path: str) -> bool:
    """Der Export-Wurzelordner `PhotoSort-Export` liegt am Drive-Root. Er liegt damit im Scan-Baum,
    wenn der Scan die Drive-Wurzel selbst ist (`opencloud_path` leer oder `/`) - der naechste Scan
    importierte die exportierten Kopien sonst als neue Fotos (ADR 0136 Punkt 2)."""
    return opencloud_path.strip("/") == ""


async def run_export(
    session: AsyncSession,
    client: ExportClient,
    project: Project,
    *,
    run_id: int | None = None,
) -> ExportRun | None:
    """Der Export-Lauf: Menge ableiten -> Lauf + Schnappschuss -> MKCOL Wurzel/Unterordner -> je
    Foto COPY. Ein leeres Projekt erzeugt KEINEN Lauf (None).

    Mit `run_id` uebernimmt er den von der API angelegten, wartenden Lauf; wurde der in der
    Warteschlange abgebrochen, endet er ohne jede Arbeit (None). Ohne `run_id` (ein vor dem
    Wartezustand eingereihter Job) legt er die Zeile selbst an.

    Einzelfehler je `COPY` schreiben in die Schnappschusszeile (`export_photos.error`) und lassen
    den Lauf weiterlaufen - er endet trotz Teilfehlern `success`. Nur ein fataler Fehler
    (Zielordner nicht anlegbar, OpenCloud nicht erreichbar) endet `failed` (ADR 0136 Punkt 3).
    Ein Abbruchwunsch wird vor jedem COPY gelesen: der Ordner und die bereits kopierten Fotos
    bleiben auf OpenCloud, der Lauf endet `cancelled`."""
    if run_id is not None:
        taken_over = await runs._take_over_queued_run(session, ExportRun, run_id)
        if taken_over is None:
            return None
        run = taken_over
        included = await included_photos(session, project.id)
    else:
        included = await included_photos(session, project.id)
        if not included:
            return None
        run = ExportRun(project_id=project.id, status=ExportRunStatus.RUNNING)
        session.add(run)
        await session.commit()
        await session.refresh(run)

    # Der Zeitstempel wird HIER genommen - im nacheinander arbeitenden Worker -, damit zwei Laeufe
    # nicht in derselben Mikrosekunde beginnen (ADR 0136 Punkt 2: ein erneuter Export erzeugt immer
    # einen weiteren neuen Ordner).
    target_path = f"{EXPORT_ROOT_FOLDER}/{build_export_folder_name(project.name, runs._now_utc())}"
    run.target_path = target_path
    run.photo_count = len(included)
    snapshots: dict[int, ExportPhoto] = {}
    for entry in included:
        row = ExportPhoto(
            export_run_id=run.id, photo_id=entry.photo_id, relative_path=entry.relative_path
        )
        session.add(row)
        snapshots[entry.photo_id] = row
    await session.commit()

    # Vor dem `try`, damit beide Fehlerpfade die Zaehler-Standorte kennen - sie stehen auch bei
    # einem Abbruch VOR der COPY-Schleife auf 0 (Muss-Fix 3).
    exported = 0
    failed = 0

    try:
        drive = await client.resolve_drive(settings.opencloud_drive_name or None)
        # ADR 0136 Punkt 2: Der Export gehoert auf die WebDAV-URL des am PROJEKT persistierten
        # `opencloud_drive_id`, nie auf den globalen Config-Namen. Weicht die Konfiguration
        # zwischen Scan und Export ab, faellt der Lauf hier VOR jedem Schreibzugriff aus - ein
        # stiller COPY aus einem fremden Space waere ein Vertraulichkeits-/Integritaetsbruch.
        if drive.id != project.opencloud_drive_id:
            raise OpenCloudError(
                f"OpenCloud-Space der Konfiguration ({drive.id!r}) weicht vom Projekt "
                f"({project.opencloud_drive_id!r}) ab."
            )
        if _export_overlaps_scan_root(project.opencloud_path):
            raise OpenCloudError(
                "Das Projekt scannt die Drive-Wurzel; ein Export dorthin wuerde die Kopien beim "
                "naechsten Scan als neue Fotos importieren."
            )
        webdav_url = drive.webdav_url

        await client.mkcol(webdav_url, EXPORT_ROOT_FOLDER)
        await client.mkcol(webdav_url, target_path)

        subfolders: list[str] = []
        seen: set[str] = set()
        for entry in included:
            for folder in _parent_folders(entry.relative_path):
                if folder not in seen:
                    seen.add(folder)
                    subfolders.append(folder)
        for folder in subfolders:
            await client.mkcol(webdav_url, f"{target_path}/{folder}")

        for index, entry in enumerate(included):
            if await cancel_requested(session, run):
                break
            try:
                # Das Ziel laeuft AUSSCHLIESSLICH ueber `join_remote_path` - nie manuelle Konkatenation roher
                # Namen (Security Muss gegen Header-Injection und `..`-Ausbruch). Der `join_remote_path`
                # steht INNERHALB des je-Foto-try: ein Foto, dessen Name die Regeln verletzt
                # (`..`-Segment), scheitert als Einzelfehler in `export_photos.error`, nie bricht
                # es den Lauf ab.
                dest_url = join_remote_path(webdav_url, f"{target_path}/{entry.relative_path}")
                await client.copy(webdav_url, entry.relative_path, dest_url)
                exported += 1
            except OpenCloudError as exc:
                failed += 1
                snapshots[entry.photo_id].error = str(exc)
            run.exported_count = exported
            run.failed_count = failed
            run.last_progress_at = runs._now_utc()
            if (index + 1) % EXPORT_COMMIT_BATCH_SIZE == 0:
                await session.commit()

        if await cancel_requested(session, run):
            # Der bis hierher erzielte Stand wird committet, BEVOR _finish_cancelled zurueckrollt -
            # Zielpfad und Kopierzahl bleiben sichtbar, damit der Ordner auffindbar ist.
            await session.commit()
            await runs._finish_cancelled(session, run)
            return run
        run.status = ExportRunStatus.SUCCESS
        run.finished_at = runs._now_utc()
        await session.commit()
    except asyncio.CancelledError:
        # Persistiert den bis hierher erzielten Stand, BEVOR _fail_export_run zurueckrollt - der
        # failed-Bericht bildet so die real erfolgten COPYs ab (Muss-Fix 3).
        run.exported_count = exported
        run.failed_count = failed
        run.last_progress_at = runs._now_utc()
        await session.commit()
        await runs._fail_export_run(
            session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."
        )
        raise
    except Exception as exc:
        run.exported_count = exported
        run.failed_count = failed
        run.last_progress_at = runs._now_utc()
        await session.commit()
        await runs._fail_export_run(session, run, str(exc))
        return run
    return run


async def export_project(
    ctx: dict[str, Any], project_id: int, run_id: int | None = None
) -> int | None:
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        async with OpenCloudClient(
            settings.opencloud_base_url, settings.opencloud_username, settings.opencloud_app_token
        ) as client:
            run = await run_export(session, client, project, run_id=run_id)
        return run.id if run is not None else None
