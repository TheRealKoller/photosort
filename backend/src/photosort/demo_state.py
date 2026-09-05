"""Schreibendes CLI: legt einen deterministischen Demo-Datenbestand fuer die browsergestuetzte
Oberflaechenpruefung an (specs/features/0174-browser-zugang-fuer-claude.md, ADR decisions/0057-
browsergestuetzte-oberflaechenpruefung.md).

Aufruf::

    docker compose -f docker-compose.yml -f docker-compose.e2e.yml \\
        exec -T backend python -m photosort.demo_state

Vier Projekte mit dem festen Namenspraefix ``Demo — `` decken die vier prueflohnenden Zustaende ab
(leer, grosse Sammlung, bewertet, Fehlerzustand). Die Bilddateien entstehen synthetisch mit Pillow
und werden ueber die ECHTE ``thumbnails.py``-Logik in den lokalen Cache geschrieben - kein zweites
Abbild von Datenmodell oder Cache-Schluessel, das bei einer Modelaenderung still abdriften koennte
(ADR 0057 Punkt 4).

WARUM DIESES MODUL IM PRODUKTIV-PAKET LIEGT UND TROTZDEM UNGEFAEHRLICH IST: Es braucht die echten
SQLAlchemy-Modelle und die echte Cache-Schluessel-Bildung, liegt damit im Produktiv-Image - und ist
bewusst destruktiv (es loescht seine eigenen Demo-Projekte, bevor es sie neu anlegt). Drei
Eigenschaften halten das zusammen:

* **Dreiteilige, fail-closed Sperre (M1)**, vollstaendig ausgewertet VOR dem ersten Schreibzugriff:
  eine Umgebungsvariable mit exaktem Literalwert, kein Projekt ohne Demo-Praefix in der Datenbank,
  und eine OpenCloud-Basis-URL, die leer ist oder auf einen bekannten Demo-Host zeigt. Die dritte
  Bedingung ist die einzige, die auf einer frisch aufgesetzten Produktivinstanz mit LEERER
  Datenbank noch greift - dort ist die zweite leer erfuellt.
* **Geloescht wird nur, was dieses Modul selbst angelegt hat (M2):** zeilenweise entlang der
  eigenen Demo-Projekte, im Thumbnail-Cache ausschliesslich ueber die aus den eigenen
  ``(photo_id, etag)``-Paaren BERECHNETEN Pfade. Kein ``glob``, kein ``rmtree`` - die
  Cache-Dateinamen sind flache Hash-Schluessel ohne Projektzuordnung, bei einem geteilten Volume
  traefe ein Glob echte Familien-Thumbnails.
* **Kein Aufrufpfad aus der laufenden Anwendung (M3):** kein Import aus ``main.py``/``worker.py``,
  kein Endpunkt, kein Compose-``command``. Ein Test haelt das ueber den Import-Graphen fest.

Fehlermeldungen nennen nur Bedingung und Status, nie Konfigurationswerte (M2).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import random
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.categories import CATEGORY_REGISTRY
from photosort.config import settings
from photosort.criteria import CRITERIA_REGISTRY
from photosort.db import make_engine, make_session_factory
from photosort.models import (
    ClassificationPhase,
    CloudVisionPhase,
    CriterionScoringRun,
    Photo,
    PhotoCategoryClassification,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoLandmarkDetection,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.thumbnails import display_path, generate_variants, thumbnail_path

# --- Namen, Konstanten, Sperr-Literale -------------------------------------------------------

# Der Praefix ist der Anker der gesamten Sperre: exakt so, mit Geviertstrich und beidseitigem
# Leerzeichen. Eine lockere Pruefung ("startswith('Demo')") wuerde ein reales Projekt
# "Demolition Sommer 2019" freigeben und loeschen (Edge Case E9 der Spec).
DEMO_PROJECT_PREFIX = "Demo — "

EMPTY_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Leeres Projekt"
LARGE_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Große Sammlung"
RATED_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Bewertet"
ERROR_PROJECT_NAME = f"{DEMO_PROJECT_PREFIX}Fehlerzustand"

# Umgebungsvariable + exakter Satz-Literal (M1a). Bewusst KEIN "gesetzt"/truthy-Test: `1`/`true`
# setzt man versehentlich, einen Satz wie diesen nicht.
CONFIRM_ENV_VAR = "PHOTOSORT_DEMO_STATE_CONFIRM"
CONFIRM_LITERAL = "yes-wipe-and-seed-demo-data"

# Fotoanzahl der grossen Sammlung. Vorgabe der Spec: Band 60-80 - genug fuer Scrollen und
# Listendichte, bewusst keine Performance-Groessenordnung. Die Tests fahren diese Groesse genau
# EINMAL; alle uebrigen Testfaelle uebergeben eine kleine Anzahl (Edge Case E6).
LARGE_COLLECTION_PHOTO_COUNT = 72

# Fotoanzahl des Fehlerzustands-Projekts - klein, aber gross genug, dass ein Foto ohne
# Cache-Datei ("wird noch verarbeitet"-Platzhalter) neben normal dargestellten Fotos auffaellt.
ERROR_STATE_PHOTO_COUNT = 6

# Hostnamen, die als "eindeutig lokal/Demo" gelten (M1c). Muster inklusive Port-Pflicht aus
# scripts/seed-opencloud-demo.py::validate_demo_base_url - dort als Copilot-Review-Fund ergaenzt,
# weil "http://localhost" (impliziter Port 80) sonst einen ganz anderen lokalen Dienst treffen
# koennte. Bewusst nachgebaut statt importiert: scripts/ ist ein eigenstaendiges Python-Paket und
# im Backend-Image nicht installiert.
_DEMO_HOSTS = frozenset({"opencloud-demo", "localhost", "127.0.0.1", "::1"})

# Bilderzeugung: fester Zufallskeim, feste Groesse, feste JPEG-Qualitaet - zwei Laeufe liefern
# byte-identische Dateien (per Test belegt, nicht behauptet).
_IMAGE_SEED = "photosort-demo-state-v1"
_IMAGE_SIZE = (960, 720)
_IMAGE_JPEG_QUALITY = 90

# Feste Zeit-Anker: alle Zeitstempel sind deterministisch daraus abgeleitet, damit Sortierung,
# Zeit-Cluster und angezeigte Daten zwischen zwei Laeufen identisch bleiben. Naiv/UTC wie im
# uebrigen Backend (worker.py: `datetime.now(UTC).replace(tzinfo=None)`).
_BASE_TAKEN_AT = datetime(2024, 5, 1, 9, 0, 0)
_BASE_SCAN_AT = datetime(2024, 6, 1, 10, 0, 0)
_BASE_SCORING_AT = datetime(2024, 6, 1, 11, 0, 0)

# Das Foto des bewerteten Projekts, das einen OFFENEN Ausschuss-Vorschlag traegt: bewusst hinter
# den drei bewerteten Fotos, damit es garantiert keine Bewertung hat (ein bewerteter Vorschlag
# waere bereits entschieden und zeigte den Zustand nicht mehr).
_OPEN_SUGGESTION_INDEX = 3

# Reihenfolge, in der die drei Bewertungsstatus auf die ersten Fotos des bewerteten Projekts
# verteilt werden - ueber das Enum gebildet, damit ein vierter Status nicht stillschweigend
# unbewertet bliebe.
_RATED_STATUS_ORDER = tuple(RatingStatus)

# Das Foto des Fehlerzustands-Projekts, das eine Cloud-Vision-Fehlerzeile traegt (nicht dasselbe
# wie das Foto ohne Cache-Datei - die Oberflaeche soll beide Fehlerbilder nebeneinander zeigen).
_CLOUD_VISION_ERROR_INDEX = 1


class DemoStateError(Exception):
    """Erwarteter, benutzerseitig behebbarer Abbruch (Sperre nicht erfuellt, DB nicht erreichbar).

    Wird in main() zu einer kurzen Meldung auf stderr und einem Exit-Code != 0. Der Text nennt nur
    Bedingung und Status, nie einen Konfigurationswert (M2) - ein durchgereichter Wert waere genau
    der Pfad, ueber den eine echte OPENCLOUD_BASE_URL oder ein Token in ein CI-Log geriete.
    """


# --- Reine Praedikate der dreiteiligen Sperre (M1) --------------------------------------------


def is_demo_project_name(name: str) -> bool:
    """Traegt der Projektname exakt den Demo-Praefix? Bewusst `startswith` auf dem VOLLSTAENDIGEN
    Praefix inklusive Geviertstrich und Leerzeichen, case-sensitiv."""
    return name.startswith(DEMO_PROJECT_PREFIX)


def check_confirmation(value: str | None) -> None:
    """Teil (a) der Sperre: die Umgebungsvariable traegt den exakten Literalwert.

    Kein `strip()`, kein Case-Insensitive-Vergleich, kein Truthy-Test - jede Aufweichung machte
    aus einer bewussten Freigabe wieder ein Versehen."""
    if value != CONFIRM_LITERAL:
        raise DemoStateError(
            f"Freigabe fehlt: {CONFIRM_ENV_VAR} muss exakt auf den vorgesehenen Freigabe-Satz "
            "gesetzt sein (siehe docs/setup.md). Abbruch, ohne etwas zu veraendern."
        )


def check_opencloud_target(base_url: str) -> None:
    """Teil (c) der Sperre: die konfigurierte OpenCloud-Basis-URL ist leer oder zeigt auf einen
    bekannten lokalen Demo-Host (mit explizit angegebenem Port).

    Diese Bedingung ist die einzige, die auf einer frisch aufgesetzten Produktivinstanz noch
    greift: dort ist die Datenbank leer, Teil (b) also leer erfuellt."""
    if base_url == "":
        return
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in _DEMO_HOSTS or parsed.port is None:
        raise DemoStateError(
            "Die konfigurierte OpenCloud-Basis-URL zeigt nicht auf eine lokale Demo-Instanz "
            "(erwartet: leer oder http://<lokaler Demo-Host>:<port>). Abbruch, ohne etwas zu "
            "veraendern - der Demo-Seeder darf nie neben einer echten OpenCloud-Anbindung laufen."
        )


# --- Reine Zustandsbeschreibung ---------------------------------------------------------------


@dataclass(frozen=True)
class DemoProjectSpec:
    """Beschreibung EINES Demo-Projekts, unabhaengig von Datenbank und Dateisystem.

    `uncached_photo_indices` sind die Fotos, fuer die bewusst KEINE Cache-Datei erzeugt wird - sie
    loesen im Frontend den "wird noch verarbeitet"-Platzhalter aus und sind Teil des
    Fehlerzustands, kein Versehen."""

    name: str
    slug: str
    photo_count: int
    uncached_photo_indices: tuple[int, ...] = ()


def demo_project_specs(
    *, large_collection_photo_count: int = LARGE_COLLECTION_PHOTO_COUNT
) -> tuple[DemoProjectSpec, ...]:
    """Die vier Zustaende in fester Reihenfolge.

    Die Fotoanzahl der grossen Sammlung ist ein Parameter mit der Produktionskonstante als Default
    (Edge Case E6): die Masse der Tests laeuft klein, genau ein Test faehrt die echte Groesse.
    Die Anzahl des bewerteten Projekts leitet sich dagegen aus dem festen Kategorien-Set ab - jedes
    Foto traegt genau einen Kategorie-Schluessel, damit ALLE Schluessel belegt sind, ohne dass
    irgendwo eine abgeschriebene Liste gepflegt werden muesste."""
    return (
        DemoProjectSpec(name=EMPTY_PROJECT_NAME, slug="leeres-projekt", photo_count=0),
        DemoProjectSpec(
            name=LARGE_PROJECT_NAME,
            slug="grosse-sammlung",
            photo_count=large_collection_photo_count,
        ),
        DemoProjectSpec(
            name=RATED_PROJECT_NAME, slug="bewertet", photo_count=len(CATEGORY_REGISTRY)
        ),
        DemoProjectSpec(
            name=ERROR_PROJECT_NAME,
            slug="fehlerzustand",
            photo_count=ERROR_STATE_PHOTO_COUNT,
            uncached_photo_indices=(0,),
        ),
    )


# --- Reine Erzeuger je Foto -------------------------------------------------------------------


def demo_etag(slug: str, index: int) -> str:
    """Deterministischer etag. Geht ueber `thumbnails.cache_key` in den Cache-Dateinamen ein."""
    return f"demo-{slug}-{index:04d}"


def demo_relative_path(slug: str, index: int) -> str:
    """Deterministischer, im Frontend sichtbarer Dateipfad innerhalb des Demo-Projekts."""
    return f"Demo/{slug}/foto-{index:04d}.jpg"


def demo_taken_at(index: int) -> datetime:
    """Aufnahmezeitpunkt, streng monoton mit dem Index. Naiv/UTC wie im uebrigen Backend
    (worker.py: `datetime.now(UTC).replace(tzinfo=None)`)."""
    return _BASE_TAKEN_AT + timedelta(minutes=17 * index)


def render_demo_image(*, slug: str, index: int) -> bytes:
    """Erzeugt ein synthetisches, erkennbar durchnummeriertes JPEG.

    Deterministisch: der Zufallskeim haengt ausschliesslich an `slug`/`index`, JPEG-Qualitaet und
    Bildgroesse sind Konstanten. Zwei Laeufe liefern byte-identische Dateien - ohne diese Zusage
    waere jeder darauf aufbauende E2E-Spec sprunghaft."""
    rng = random.Random(f"{_IMAGE_SEED}:{slug}:{index}")
    width, height = _IMAGE_SIZE
    background = (rng.randrange(24, 96), rng.randrange(24, 96), rng.randrange(40, 120))
    image = Image.new("RGB", _IMAGE_SIZE, background)
    draw = ImageDraw.Draw(image)

    # Ein paar grobe Formen, damit die Bilder im Grid unterscheidbar sind und die
    # Thumbnail-Skalierung etwas zu tun hat.
    for _ in range(6):
        x0 = rng.randrange(0, width)
        y0 = rng.randrange(0, height)
        x1 = min(width, x0 + rng.randrange(80, 360))
        y1 = min(height, y0 + rng.randrange(80, 360))
        fill = (rng.randrange(60, 240), rng.randrange(60, 240), rng.randrange(60, 240))
        draw.rectangle((x0, y0, x1, y1), fill=fill)

    label = f"{slug} #{index:04d}"
    font = ImageFont.load_default(size=64)
    draw.text((40, height - 120), label, fill=(255, 255, 255), font=font)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=_IMAGE_JPEG_QUALITY)
    return buffer.getvalue()


# --- Duenne DB-Schreibschicht -----------------------------------------------------------------


@dataclass(frozen=True)
class DemoStateSummary:
    """Ergebnis EINES Laufs - Grundlage der CLI-Ausgabe. Enthaelt nur Zaehlwerte und die eigenen
    Projektnamen, keine Konfigurationswerte."""

    project_names: tuple[str, ...]
    photo_count: int
    cache_file_count: int
    rated_user_count: int


async def load_demo_projects(session: AsyncSession) -> list[Project]:
    """Die eigenen Projekte, ausschliesslich ueber den exakten Praefix bestimmt."""
    projects = (await session.execute(select(Project).order_by(Project.id))).scalars().all()
    return [project for project in projects if is_demo_project_name(project.name)]


async def check_only_demo_projects(session: AsyncSession) -> None:
    """Teil (b) der Sperre: kein einziges Projekt ohne Demo-Praefix in der Datenbank.

    Eine LEERE Datenbank erfuellt die Bedingung (Edge Case E8) - der Erstlauf darf nicht daran
    scheitern, dass noch keine Demo-Projekte existieren. Gemeldet wird nur die Anzahl, nie ein
    Projektname: Projektnamen sind Familiendaten."""
    projects = (await session.execute(select(Project.name))).scalars().all()
    foreign = [name for name in projects if not is_demo_project_name(name)]
    if foreign:
        raise DemoStateError(
            f"Die Datenbank enthaelt {len(foreign)} Projekt(e) ohne den Demo-Praefix. Abbruch, "
            "ohne etwas zu veraendern - der Demo-Seeder laeuft nur gegen eine Datenbank, die "
            "ausschliesslich seine eigenen Demo-Projekte enthaelt."
        )


async def assert_safe_to_seed(
    session: AsyncSession, *, confirmation: str | None, opencloud_base_url: str
) -> None:
    """Die dreiteilige, fail-closed Sperre (M1), vollstaendig ausgewertet VOR dem ersten
    Schreibzugriff. Reihenfolge: die beiden reinen Bedingungen zuerst, danach die Datenbankfrage -
    ein fehlgeleiteter Aufruf soll gar nicht erst lesend auf eine fremde Datenbank gehen."""
    check_confirmation(confirmation)
    check_opencloud_target(opencloud_base_url)
    await check_only_demo_projects(session)


async def purge_demo_state(session: AsyncSession, cache_dir: Path) -> int:
    """Entfernt die eigenen Demo-Projekte samt aller abhaengigen Zeilen und Cache-Dateien.

    M2: zeilenweise entlang der eigenen Projekt-IDs, im Cache ausschliesslich ueber die aus den
    eigenen `(photo_id, etag)`-Paaren BERECHNETEN Pfade. Kein `glob`, kein `rmtree` - die
    Cache-Dateinamen sind flache Hash-Schluessel ohne Projektzuordnung, bei einem geteilten Volume
    traefe ein Glob echte Familien-Thumbnails.

    Rueckgabe: Anzahl entfernter Projekte."""
    projects = await load_demo_projects(session)
    project_ids = [project.id for project in projects]
    if not project_ids:
        return 0

    photo_rows = (
        await session.execute(
            select(Photo.id, Photo.etag).where(Photo.project_id.in_(project_ids))
        )
    ).all()
    for photo_id, etag in photo_rows:
        thumbnail_path(cache_dir, photo_id, etag).unlink(missing_ok=True)
        display_path(cache_dir, photo_id, etag).unlink(missing_ok=True)

    photo_ids = [photo_id for photo_id, _ in photo_rows]
    if photo_ids:
        # Bewusst einzeln ausgeschrieben statt in einer Modell-Schleife: eine Schleife ueber
        # heterogene Modellklassen verliert unter mypy --strict die Spaltentypen, und die
        # Reihenfolge ist hier fachlich relevant (Fremdschluessel unter echtem Postgres).
        await session.execute(
            delete(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id.in_(photo_ids))
        )
        await session.execute(
            delete(PhotoCategoryClassification).where(
                PhotoCategoryClassification.photo_id.in_(photo_ids)
            )
        )
        await session.execute(
            delete(PhotoFineLabel).where(PhotoFineLabel.photo_id.in_(photo_ids))
        )
        await session.execute(
            delete(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id.in_(photo_ids))
        )
        await session.execute(
            delete(PhotoRanking).where(PhotoRanking.photo_id.in_(photo_ids))
        )
        await session.execute(
            delete(PhotoCriterionScore).where(PhotoCriterionScore.photo_id.in_(photo_ids))
        )
        await session.execute(delete(PhotoScore).where(PhotoScore.photo_id.in_(photo_ids)))
        await session.execute(delete(Rating).where(Rating.photo_id.in_(photo_ids)))
        await session.execute(delete(Photo).where(Photo.id.in_(photo_ids)))

    await session.execute(
        delete(CriterionScoringRun).where(CriterionScoringRun.project_id.in_(project_ids))
    )
    await session.execute(delete(ScoringRun).where(ScoringRun.project_id.in_(project_ids)))
    await session.execute(delete(ScanRun).where(ScanRun.project_id.in_(project_ids)))
    await session.execute(
        delete(RemoteCategoryClassificationRun).where(
            RemoteCategoryClassificationRun.project_id.in_(project_ids)
        )
    )
    await session.execute(delete(Project).where(Project.id.in_(project_ids)))
    await session.flush()
    return len(project_ids)


async def _create_project(session: AsyncSession, spec: DemoProjectSpec) -> Project:
    project = Project(
        name=spec.name,
        opencloud_drive_id="demo-drive",
        opencloud_path=f"/Demo/{spec.slug}",
    )
    session.add(project)
    await session.flush()
    return project


async def _create_photos(
    session: AsyncSession, project: Project, spec: DemoProjectSpec, cache_dir: Path
) -> list[Photo]:
    """Legt die Fotos eines Demo-Projekts an und schreibt ihre Bildvarianten ueber die ECHTE
    thumbnails.py-Logik in den Cache - kein nachgebauter Cache-Schluessel."""
    photos: list[Photo] = []
    for index in range(spec.photo_count):
        image_bytes = render_demo_image(slug=spec.slug, index=index)
        photo = Photo(
            project_id=project.id,
            relative_path=demo_relative_path(spec.slug, index),
            etag=demo_etag(spec.slug, index),
            content_length=len(image_bytes),
            taken_at=demo_taken_at(index),
            last_modified=demo_taken_at(index),
        )
        session.add(photo)
        await session.flush()
        if index not in spec.uncached_photo_indices:
            if not generate_variants(cache_dir, photo.id, photo.etag, image_bytes):
                raise DemoStateError(
                    "Die Thumbnail-Erzeugung im Cache-Verzeichnis ist fehlgeschlagen (Pfad "
                    "nicht beschreibbar?). Abbruch."
                )
        photos.append(photo)
    return photos


def _scan_run(
    project: Project,
    *,
    status: ScanStatus,
    photo_count: int,
    started_at: datetime,
    error_message: str | None = None,
) -> ScanRun:
    return ScanRun(
        project_id=project.id,
        status=status,
        started_at=started_at,
        finished_at=started_at + timedelta(minutes=2),
        last_progress_at=started_at + timedelta(minutes=2),
        files_found=photo_count,
        photos_added=photo_count if status == ScanStatus.SUCCESS else 0,
        photos_updated=0,
        photos_removed=0,
        files_skipped=0,
        total_files=photo_count,
        error_message=error_message,
    )


def _deterministic_unit_value(slug: str, index: int, salt: str) -> float:
    """Reproduzierbarer Wert in [0, 1] fuer Score-/Kriterienwerte - gerundet, damit zwei Laeufe
    exakt gleiche Zahlen liefern."""
    rng = random.Random(f"{_IMAGE_SEED}:{slug}:{index}:{salt}")
    return round(rng.uniform(0.05, 0.98), 3)


async def _seed_empty_project(
    session: AsyncSession, spec: DemoProjectSpec, cache_dir: Path
) -> list[Photo]:
    """Zustand 1: ein Projekt, das es wirklich gibt, aber ohne ein einziges Foto - der leere
    Zustand der Oberflaeche."""
    project = await _create_project(session, spec)
    session.add(
        _scan_run(
            project,
            status=ScanStatus.SUCCESS,
            photo_count=0,
            started_at=_BASE_SCAN_AT,
        )
    )
    await session.flush()
    return await _create_photos(session, project, spec, cache_dir)


async def _seed_large_collection(
    session: AsyncSession, spec: DemoProjectSpec, cache_dir: Path
) -> list[Photo]:
    """Zustand 2: genug Fotos fuer Grid-Dichte und Scrollen (Band 60-80), bewusst keine
    Performance-Groessenordnung."""
    project = await _create_project(session, spec)
    photos = await _create_photos(session, project, spec, cache_dir)
    session.add(
        _scan_run(
            project,
            status=ScanStatus.SUCCESS,
            photo_count=len(photos),
            started_at=_BASE_SCAN_AT,
        )
    )
    await session.flush()
    return photos


async def _seed_rated_project(
    session: AsyncSession, spec: DemoProjectSpec, cache_dir: Path
) -> tuple[list[Photo], int]:
    """Zustand 3: alle drei Bewertungsstatus, ein offener Ausschuss-Vorschlag, ein
    Kriterien-Lauf samt Kriterien-Bewertungen und alle Kategorie-Schluessel des festen Sets.

    Rueckgabe: die Fotos und die Anzahl der Nutzer, fuer die Bewertungen geschrieben wurden."""
    project = await _create_project(session, spec)
    photos = await _create_photos(session, project, spec, cache_dir)
    session.add(
        _scan_run(
            project,
            status=ScanStatus.SUCCESS,
            photo_count=len(photos),
            started_at=_BASE_SCAN_AT,
        )
    )

    scoring_run = ScoringRun(
        project_id=project.id,
        status=ScanStatus.SUCCESS,
        started_at=_BASE_SCORING_AT,
        finished_at=_BASE_SCORING_AT + timedelta(minutes=5),
        last_progress_at=_BASE_SCORING_AT + timedelta(minutes=5),
        photos_total=len(photos),
        photos_processed=len(photos),
        suggestions_found=1,
        gate_confirmed_at=_BASE_SCORING_AT + timedelta(minutes=6),
    )
    session.add(scoring_run)
    await session.flush()

    criterion_run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=ScanStatus.SUCCESS,
        started_at=_BASE_SCORING_AT + timedelta(minutes=10),
        finished_at=_BASE_SCORING_AT + timedelta(minutes=15),
        last_progress_at=_BASE_SCORING_AT + timedelta(minutes=15),
        photos_total=len(photos),
        photos_processed=len(photos),
        phase=ClassificationPhase.CRITERIA,
        cloud_requested=False,
    )
    session.add(criterion_run)
    await session.flush()

    # Ein Foto je Kategorie-Schluessel des FESTEN Sets - ueber die Registry iteriert, damit eine
    # vierzehnte Kategorie automatisch mit abgedeckt ist statt durchzurutschen.
    for index, (photo, category_key) in enumerate(zip(photos, CATEGORY_REGISTRY, strict=True)):
        session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=_deterministic_unit_value(spec.slug, index, "sharpness"),
                exposure=_deterministic_unit_value(spec.slug, index, "exposure"),
                cluster_key=f"{spec.slug}-cluster-{index % 3}",
                # Genau ein offener Ausschuss-Vorschlag: ein Foto mit Vorschlag "Ausschuss", das
                # bewusst KEINE Bewertung traegt - sonst waere der Vorschlag bereits entschieden.
                suggested_status=(
                    RatingStatus.REJECTED if index == _OPEN_SUGGESTION_INDEX else None
                ),
                computed_at=_BASE_SCORING_AT,
            )
        )
        session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key=category_key,
                detected_categories=[category_key],
                provider="demo-state",
                computed_at=_BASE_SCORING_AT,
            )
        )
        session.add(
            PhotoRanking(
                criterion_scoring_run_id=criterion_run.id,
                photo_id=photo.id,
                cluster_key=f"{spec.slug}-cluster-{index % 3}",
                category_key=category_key,
                rank_score=_deterministic_unit_value(spec.slug, index, "rank"),
                rank_position=index + 1,
            )
        )
        for criterion_key, definition in CRITERIA_REGISTRY.items():
            session.add(
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key=criterion_key,
                    value=_deterministic_unit_value(spec.slug, index, criterion_key),
                    source=definition.source,
                    computed_at=_BASE_SCORING_AT,
                )
            )

    # Bewertungen haengen an VORHANDENEN Nutzern; der Seeder legt selbst nie ein Konto an (ein
    # Konto mit bekannten Zugangsdaten waere genau das Sicherheitsproblem, gegen das die Sperre
    # antritt). Alle vorhandenen Nutzer bekommen dieselben Bewertungen, damit der Zustand
    # unabhaengig davon sichtbar ist, wer sich anmeldet.
    users = (await session.execute(select(User).order_by(User.id))).scalars().all()
    for user in users:
        for offset, status in enumerate(_RATED_STATUS_ORDER):
            session.add(
                Rating(
                    photo_id=photos[offset].id,
                    user_id=user.id,
                    status=status,
                    updated_at=_BASE_SCORING_AT,
                )
            )
    await session.flush()
    return photos, len(users)


async def _seed_error_project(
    session: AsyncSession, spec: DemoProjectSpec, cache_dir: Path
) -> list[Photo]:
    """Zustand 4: fehlgeschlagener Lauf mit nicht-leerem Fehlertext, mindestens ein Foto ohne
    Cache-Datei ("wird noch verarbeitet"-Platzhalter) und mindestens eine Cloud-Vision-Fehlerzeile
    - die drei Fehlerdarstellungen des Frontends haengen daran."""
    project = await _create_project(session, spec)
    photos = await _create_photos(session, project, spec, cache_dir)
    session.add(
        _scan_run(
            project,
            status=ScanStatus.SUCCESS,
            photo_count=len(photos),
            started_at=_BASE_SCAN_AT,
        )
    )
    session.add(
        _scan_run(
            project,
            status=ScanStatus.FAILED,
            photo_count=len(photos),
            started_at=_BASE_SCAN_AT + timedelta(days=1),
            error_message=(
                "OpenCloud nicht erreichbar: Verbindung zum Space abgelehnt "
                "(Demo-Fehlerzustand, kein echter Vorfall)."
            ),
        )
    )
    session.add(
        PhotoCloudVisionError(
            photo_id=photos[_CLOUD_VISION_ERROR_INDEX].id,
            phase=CloudVisionPhase.LANDMARK,
            error_type="upstream_error",
            error_message=(
                "Cloud-Vision-Anbieter antwortete mit 503 (Demo-Fehlerzustand, kein echter "
                "Vorfall)."
            ),
            attempted_at=_BASE_SCORING_AT,
        )
    )
    await session.flush()
    return photos


async def rebuild_demo_state(
    session: AsyncSession,
    cache_dir: Path,
    *,
    large_collection_photo_count: int = LARGE_COLLECTION_PHOTO_COUNT,
) -> DemoStateSummary:
    """Zielzustands-idempotent: entfernt zuerst ALLE eigenen Demo-Projekte (auch Reste eines
    frueheren Laufs mit anderen Namen) und legt die vier Zustaende danach neu an. Das Ergebnis
    haengt nicht vom Vorzustand ab.

    Enthaelt selbst KEINE Sperre - der Aufrufer (main()) wertet `assert_safe_to_seed` vor dem
    ersten Schreibzugriff vollstaendig aus."""
    await purge_demo_state(session, cache_dir)
    empty_spec, large_spec, rated_spec, error_spec = demo_project_specs(
        large_collection_photo_count=large_collection_photo_count
    )
    photos = list(await _seed_empty_project(session, empty_spec, cache_dir))
    photos += await _seed_large_collection(session, large_spec, cache_dir)
    rated_photos, rated_user_count = await _seed_rated_project(session, rated_spec, cache_dir)
    photos += rated_photos
    photos += await _seed_error_project(session, error_spec, cache_dir)
    await session.flush()

    cache_file_count = (
        sum(1 for path in cache_dir.iterdir() if path.is_file()) if cache_dir.exists() else 0
    )
    return DemoStateSummary(
        project_names=(
            empty_spec.name,
            large_spec.name,
            rated_spec.name,
            error_spec.name,
        ),
        photo_count=len(photos),
        cache_file_count=cache_file_count,
        rated_user_count=rated_user_count,
    )


# --- CLI-Verdrahtung ---------------------------------------------------------------------------


async def _rebuild_with_own_session(
    database_url: str,
    cache_dir: Path,
    *,
    confirmation: str | None,
    opencloud_base_url: str,
) -> DemoStateSummary:
    engine = make_engine(database_url)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            # Die vollstaendige Sperre laeuft VOR dem ersten Schreibzugriff (M1).
            await assert_safe_to_seed(
                session, confirmation=confirmation, opencloud_base_url=opencloud_base_url
            )
            summary = await rebuild_demo_state(session, cache_dir)
            await session.commit()
            return summary
    finally:
        await engine.dispose()


def render_summary(summary: DemoStateSummary) -> str:
    """Reine Formatierung der Ausgabe - Zaehlwerte und die eigenen Projektnamen, sonst nichts.
    Kein Konfigurationswert, kein Pfad, kein Nutzername (M2)."""
    lines = [
        "Demo-Datenbestand neu aufgebaut.",
        f"Projekte: {len(summary.project_names)}",
    ]
    lines.extend(f"  - {name}" for name in summary.project_names)
    lines.append(f"Fotos: {summary.photo_count}")
    lines.append(f"Cache-Dateien: {summary.cache_file_count}")
    lines.append(f"Bewertungen geschrieben fuer {summary.rated_user_count} vorhandene(n) Nutzer.")
    if summary.rated_user_count == 0:
        lines.append(
            "  Hinweis: kein Benutzerkonto in der Datenbank - das bewertete Projekt bleibt "
            "deshalb ohne Bewertungen. Der Seeder legt bewusst nie selbst ein Konto an."
        )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.demo_state",
        description=(
            "Baut den deterministischen Demo-Datenbestand fuer die browsergestuetzte "
            "Oberflaechenpruefung auf. Loescht dabei die EIGENEN Demo-Projekte und legt sie neu "
            "an - laeuft nur mit ausdruecklicher Freigabe ueber eine Umgebungsvariable, nur gegen "
            "eine Datenbank ohne Fremdprojekte und nur ohne echte OpenCloud-Anbindung."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default=settings.photo_cache_dir,
        help="Ziel-Verzeichnis des Thumbnail-Caches (Default: die konfigurierte Anwendung).",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, database_url: str | None = None) -> int:
    """Verdrahtung + Exit-Code. `argv` und `database_url` sind injizierbar (kein sys.argv-Zugriff
    im Testpfad, kein unbeabsichtigter Zugriff auf die konfigurierte Anwendungs-Datenbank).
    `asyncio.run` laeuft INNERHALB von main(): eine Async-Engine ueberlebt keinen Loop-Wechsel."""
    args = _build_parser().parse_args(argv)
    try:
        summary = asyncio.run(
            _rebuild_with_own_session(
                database_url or settings.database_url,
                Path(args.cache_dir),
                confirmation=os.environ.get(CONFIRM_ENV_VAR),
                opencloud_base_url=settings.opencloud_base_url,
            )
        )
    except DemoStateError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        # Nur der Fehlertyp, NIE str(exc)/Traceback - die SQLAlchemy-Meldung kann die
        # DATABASE_URL inklusive Zugangsdaten enthalten (Muster aus category_diff.py).
        print(f"Fehler: Datenbankzugriff fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(render_summary(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
