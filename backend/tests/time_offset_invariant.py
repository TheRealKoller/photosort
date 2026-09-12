"""Die Invariante des Kamera-Zeitversatzes als Nachsatz jedes Falls, der Fotos schreibt.

Bewusst kein `test_*`-Modul (wird nicht eingesammelt): gebraucht wird sie vom Scan
(`test_worker_scan_project.py`), vom Versatz-Endpunkt (`test_api_cameras.py`) und vom Demo-Seeder
(`test_demo_state.py`) - Muster `assert_event_invariants`/`event_rows.py`.

Zugesichert wird ADR 0088, Punkt 1: `taken_at == taken_at_original + offset_minutes` der Kamera
dieses Fotos IN DIESEM PROJEKT; bei fehlender Kamera oder `offset_minutes = 0` sind beide Werte
gleich. Wird sie verletzt, zeigt die Anwendung eine Aufnahmezeit an, die zu keinem Versatz passt,
gruppiert nach ihr und erbt Orte nach ihr - alles ohne Fehlermeldung.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import Photo, ProjectCamera


async def assert_time_offset_invariant(session: AsyncSession, project_id: int) -> None:
    """Prueft die Invariante fuer JEDES Foto des Projekts.

    Die Kamerazeile wird ueber einen `outerjoin` mitgelesen, nicht je Foto nachgeladen - und die
    Projektbedingung steht AUSGESCHRIEBEN an beiden Seiten: ein Foto, dessen `camera_id` auf eine
    Zeile eines FREMDEN Projekts zeigt, ist selbst eine Verletzung und fiele sonst durch, weil die
    Rechnung mit dem fremden Versatz aufgeht."""
    rows = (
        await session.execute(
            select(
                Photo.id,
                Photo.taken_at,
                Photo.taken_at_original,
                Photo.camera_id,
                ProjectCamera.id,
                ProjectCamera.offset_minutes,
            )
            .outerjoin(ProjectCamera, ProjectCamera.id == Photo.camera_id)
            .where(Photo.project_id == project_id)
        )
    ).all()

    for photo_id, taken_at, taken_at_original, camera_id, joined_camera_id, offset in rows:
        if camera_id is None:
            assert taken_at == taken_at_original, (
                f"Foto {photo_id} hat keine Kamera, aber wirksame und aufgezeichnete Zeit "
                f"weichen ab: {taken_at} != {taken_at_original}"
            )
            continue
        assert joined_camera_id is not None, (
            f"Foto {photo_id} zeigt auf die Kamerazeile {camera_id}, die es nicht gibt."
        )
        expected = taken_at_original + timedelta(minutes=offset)
        assert taken_at == expected, (
            f"Foto {photo_id} verletzt die Invariante: {taken_at} != {taken_at_original} + "
            f"{offset} min ({expected})"
        )

    await _assert_no_camera_crosses_the_project_border(session, project_id)


async def _assert_no_camera_crosses_the_project_border(
    session: AsyncSession, project_id: int
) -> None:
    """Die zweite Haelfte der Zusage (Sicherheitsabschnitt, Punkt 2): `Photo.camera_id` zeigt
    ausschliesslich auf eine Zeile DESSELBEN Projekts. Ohne diese Pruefung ginge die Rechnung oben
    auch mit einer projektfremden Kamerazeile auf."""
    crossing = (
        await session.execute(
            select(Photo.id, ProjectCamera.project_id)
            .join(ProjectCamera, ProjectCamera.id == Photo.camera_id)
            .where(Photo.project_id == project_id, ProjectCamera.project_id != project_id)
        )
    ).all()

    assert not crossing, (
        f"Diese Fotos von Projekt {project_id} zeigen auf eine Kamerazeile eines FREMDEN "
        f"Projekts: {crossing}"
    )
