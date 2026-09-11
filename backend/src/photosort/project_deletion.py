"""Die EINE Aufzaehlung dessen, was an einem Projekt haengt.

Metadatengeordnete Mengenloeschung statt ORM-Kaskade: `session.delete(project)` laedt bei
mehreren tausend Fotos rund 10^5 abhaengige Zeilen als Objekte und setzt ein DELETE je Zeile ab.
Stattdessen eine feste, kleine Anweisungsfolge `delete(Model).where(<spalte>.in_(...))` in
Fremdschluessel-Reihenfolge - unabhaengig von der Datenmenge.

Genutzt von `api/projects.py::delete_project` UND `demo_state.py::purge_demo_state`; es gibt
danach genau eine Stelle, die weiss, welche Tabellen am Projekt haengen. Zwei Tests in
`tests/test_project_deletion.py` sichern Reihenfolge und Vollstaendigkeit gegen `Base.metadata`
ab - noetig, weil die Testsuite gegen SQLite ohne `PRAGMA foreign_keys=ON` laeuft und eine
falsche Reihenfolge dort strukturell nicht auffiele.

Nicht geloescht werden `users` und `fine_labels`: beide sind Fremdschluessel-ELTERN (die
Feinlabel-Registry ist projektuebergreifendes Vokabular) und fallen aus der
Erreichbarkeitspruefung automatisch heraus, ohne eigene Ausnahmeliste.

SICHERHEITS-MUSS-KRITERIUM (Demo-Seeder-Sperre M3): Dieses Modul importiert `demo_state` NICHT
(die Import-Richtung ist umgekehrt), nimmt die zu loeschenden Projekt-IDs ausschliesslich vom
Aufrufer entgegen und enthaelt KEINE Projekt-AUSWAHL-Logik (kein Namenspraefix, kein "alle
Projekte"). Sonst waere ausgerechnet der Teil, den die dreiteilige Demo-Sperre bewacht, ueber
einen HTTP-Endpunkt erreichbar. Bricht in
tests/test_demo_state.py::TestNoCallPathFromTheRunningApplication (drei Faelle).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import CursorResult, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Delete

from photosort.models import (
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
    RemoteCategoryClassificationRun,
    ScanRun,
    ScoringRun,
)


async def collect_photo_cache_keys(
    session: AsyncSession, project_ids: Sequence[int]
) -> list[tuple[int, str]]:
    """Die `(photo_id, etag)`-Paare aller Fotos der uebergebenen Projekte.

    VOR der Zeilenloeschung aufzurufen - nach ihr gibt es die Zeilen nicht mehr, aus denen sich
    die Cache-Pfade berechnen liessen. Die Paare sind genau die Eingabe von
    `thumbnails.delete_cached_variants`."""
    if not project_ids:
        return []
    rows = (
        await session.execute(select(Photo.id, Photo.etag).where(Photo.project_id.in_(project_ids)))
    ).all()
    return [(photo_id, etag) for photo_id, etag in rows]


async def delete_projects(session: AsyncSession, project_ids: Sequence[int]) -> dict[str, int]:
    """Loescht die uebergebenen Projekte samt aller an ihnen haengenden Zeilen.

    Weder `commit()` noch `flush()` - die Transaktionsgrenze gehoert dem Aufrufer (der Endpunkt
    committet genau einmal, `purge_demo_state` flusht im Rahmen seiner eigenen Sitzung).

    Rueckgabe: Zeilenzahl je Tabellenname, Grundlage der INFO-Logzeile des Endpunkts.

    Die Anweisungen sind bewusst einzeln ausgeschrieben statt in einer Schleife ueber
    Modellklassen: eine Schleife ueber heterogene Modelle verliert unter `mypy --strict` die
    Spaltentypen, und die Reihenfolge ist fachlich relevant (Fremdschluessel unter echtem
    Postgres). Ihre Reihenfolge ist `reversed(Base.metadata.sorted_tables)`, per Test erzwungen.

    Die Kindzeilen werden ueber eine Unterabfrage auf `photos` adressiert statt ueber eine nach
    Python geladene ID-Liste: bei mehreren tausend Fotos waere die IN-Liste sonst ebenso gross,
    und die Datenbank kann die Auswahl selbst treffen.
    """
    photo_ids = select(Photo.id).where(Photo.project_id.in_(project_ids))
    criterion_run_ids = select(CriterionScoringRun.id).where(
        CriterionScoringRun.project_id.in_(project_ids)
    )
    deleted: dict[str, int] = {}

    async def _run(table_name: str, statement: Delete) -> None:
        result = await session.execute(statement)
        deleted[table_name] = cast("CursorResult[Any]", result).rowcount

    # photo_rankings haengt an ZWEI Eltern (Foto und Kuratierungslauf) - beide Kanten werden
    # abgedeckt, damit keine Zeile stehen bleibt, deren einer Elternteil gerade verschwindet.
    await _run(
        "photo_rankings",
        delete(PhotoRanking).where(
            or_(
                PhotoRanking.photo_id.in_(photo_ids),
                PhotoRanking.criterion_scoring_run_id.in_(criterion_run_ids),
            )
        ),
    )
    await _run("ratings", delete(Rating).where(Rating.photo_id.in_(photo_ids)))
    await _run("photo_scores", delete(PhotoScore).where(PhotoScore.photo_id.in_(photo_ids)))
    await _run(
        "photo_landmark_detections",
        delete(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id.in_(photo_ids)),
    )
    await _run(
        "photo_fine_labels",
        delete(PhotoFineLabel).where(PhotoFineLabel.photo_id.in_(photo_ids)),
    )
    await _run(
        "photo_criterion_scores",
        delete(PhotoCriterionScore).where(PhotoCriterionScore.photo_id.in_(photo_ids)),
    )
    await _run(
        "photo_cloud_vision_errors",
        delete(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id.in_(photo_ids)),
    )
    await _run(
        "photo_category_classifications",
        delete(PhotoCategoryClassification).where(
            PhotoCategoryClassification.photo_id.in_(photo_ids)
        ),
    )
    await _run(
        "criterion_scoring_runs",
        delete(CriterionScoringRun).where(CriterionScoringRun.project_id.in_(project_ids)),
    )
    await _run("scoring_runs", delete(ScoringRun).where(ScoringRun.project_id.in_(project_ids)))
    await _run("scan_runs", delete(ScanRun).where(ScanRun.project_id.in_(project_ids)))
    await _run(
        "remote_category_classification_runs",
        delete(RemoteCategoryClassificationRun).where(
            RemoteCategoryClassificationRun.project_id.in_(project_ids)
        ),
    )
    await _run("photos", delete(Photo).where(Photo.project_id.in_(project_ids)))
    await _run("projects", delete(Project).where(Project.id.in_(project_ids)))
    return deleted
