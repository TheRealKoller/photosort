"""Die Kameras eines Projekts und ihr Zeitversatz - Liste, Setzen, Vorschlag.

Die ZWEITE der zwei Schreibstellen auf `Photo.taken_at` (ADR 0090, Punkt 1; die erste ist
`worker.py::_process_scan_block`), und beide rechnen ueber `cameras.py::shifted` aus
`taken_at_original`.

SICHERHEIT - die PROJEKTGRENZE ist eine Zusage, keine Annahme: Projekte haben keinen Eigentuemer,
jeder angemeldete Nutzer sieht und aendert jedes Projekt, und zwischen den beiden Nutzern gilt
kein Innentaeter-Modell. Geschuetzt wird deshalb die Projektgrenze, nicht eine Nutzergrenze: Eine
`camera_id` oder `photo_id` aus Projekt B, hier an einem Endpunkt von Projekt A abgesetzt, darf
weder Daten aus B zeigen noch in B schreiben. Die Projektbedingung steht dafuer AUSGESCHRIEBEN in
derselben Anweisung, die die Id aufloest - nie als vorgeschaltete Aufloesung. Unbekannt und fremd
sind dieselbe Antwort (`404`), es entsteht also keine Existenzauskunft ueber fremde Zeilen.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.cameras import (
    MAX_TIME_OFFSET_MINUTES,
    CameraIdentity,
    camera_label,
    shifted,
    suggested_offset_minutes,
)
from photosort.models import (
    CriterionScoringRun,
    Photo,
    Project,
    ProjectCamera,
    ScanRun,
    ScanStatus,
)
from photosort.worker import rebuild_run_grouping

# Router-weite Auth wie `api/stats.py` (anders als `api/photos.py`): kein Endpunkt hier braucht
# das tatsaechliche User-Objekt, und dies ist ein NEU angelegtes Modul - ohne die Router-Ebene
# haenge die Absicherung eines kuenftigen vierten Endpunkts allein daran, dass niemand die
# Dependency vergisst.
router = APIRouter(prefix="/projects", tags=["cameras"], dependencies=[Depends(get_current_user)])

# SICHERHEIT - Obergrenze der Foto-Ids des Vorschlags, im Muster von
# `api/photos.py::_MAX_QUERY_POSITION`: ein Pydantic-`int` ist unbeschraenkt und landet direkt im
# SQL-Vergleich; unter SQLite wirft ein Wert jenseits von 2^63 einen `OverflowError` und damit
# eine 500 statt einer 404.
_MAX_PHOTO_ID = 1_000_000_000


class ProjectCameraOut(BaseModel):
    """Eine Kamera des Projekts, wie die Oberflaeche sie zeigt.

    `label` kommt vom SERVER (`cameras.py::camera_label`) - eine Stelle entscheidet, wie eine
    Kamera heisst, und der Wert ist bereits von Zeichen der Unicode-Kategorien Cc/Cf befreit.
    `photo_count` zaehlt ausschliesslich die Fotos DIESES Projekts von dieser Kamera."""

    id: int
    label: str
    photo_count: int
    offset_minutes: int


class TimeOffsetIn(BaseModel):
    offset_minutes: int = Field(ge=-MAX_TIME_OFFSET_MINUTES, le=MAX_TIME_OFFSET_MINUTES)


class CameraTimeOffsetSuggestionOut(BaseModel):
    """Ein errechneter Vorschlag - ein reiner LESEVORGANG ohne Zustand: kein
    "vorgeschlagen"-Feld, keine Zeile. Uebernommen wird er, indem der Nutzer den Wert ueber
    denselben `PUT` setzt wie einen selbst getippten."""

    camera_id: int
    camera_label: str
    offset_minutes: int
    photo_taken_at_original: datetime
    reference_taken_at: datetime


async def _get_project_or_404(project_id: int, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


@router.get("/{project_id}/cameras", response_model=list[ProjectCameraOut])
async def list_cameras(
    project_id: int, session: AsyncSession = Depends(get_session)
) -> list[ProjectCameraOut]:
    """Die Kameras dieses Projekts, sortiert nach Hersteller und Modell - je Eintrag die
    Bezeichnung, die Anzahl der Fotos DIESES Projekts von dieser Kamera und der geltende Versatz.

    Die Liste entsteht aus den Fotos selbst (der Scan legt die Zeilen an), der Nutzer traegt keine
    Kamera ein. Fotos ohne bestimmbare Kamera erscheinen NICHT als Eintrag und erzeugen keinen
    Fehler.

    EINE Abfrage, unabhaengig von der Kameraanzahl: der `outerjoin` traegt BEIDE Bedingungen
    ausgeschrieben - `Photo.camera_id == ProjectCamera.id` UND `Photo.project_id == project_id`.
    Ohne die zweite zaehlte dieselbe Kamera die Fotos eines FREMDEN Projekts mit."""
    await _get_project_or_404(project_id, session)

    rows = (
        await session.execute(
            select(
                ProjectCamera.id,
                ProjectCamera.make,
                ProjectCamera.model,
                ProjectCamera.offset_minutes,
                func.count(Photo.id),
            )
            .outerjoin(
                Photo,
                and_(Photo.camera_id == ProjectCamera.id, Photo.project_id == project_id),
            )
            .where(ProjectCamera.project_id == project_id)
            .group_by(
                ProjectCamera.id,
                ProjectCamera.make,
                ProjectCamera.model,
                ProjectCamera.offset_minutes,
            )
            .order_by(ProjectCamera.make, ProjectCamera.model)
        )
    ).all()

    return [
        ProjectCameraOut(
            id=camera_id,
            label=camera_label(CameraIdentity(make=make, model=model)),
            photo_count=photo_count,
            offset_minutes=offset_minutes,
        )
        for camera_id, make, model, offset_minutes, photo_count in rows
    ]


async def _locked_camera_or_404(
    session: AsyncSession, project_id: int, camera_id: int
) -> ProjectCamera:
    """Die Kamerazeile, mit `id` UND `project_id` in DERSELBEN Anweisung aufgeloest und fuer die
    Dauer der Transaktion gesperrt.

    `with_for_update()` serialisiert zwei gleichzeitige `PUT`s unter PostgreSQL (unter SQLite
    wirkungslos, siehe Sicherheitskonzept) - tragend ist deshalb der `409`-Waechter unten. Eine
    fremde Id ergibt `404` OHNE Rueckspiegelung des Werts."""
    camera = (
        await session.execute(
            select(ProjectCamera)
            .where(ProjectCamera.id == camera_id, ProjectCamera.project_id == project_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if camera is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kamera nicht gefunden.")
    return camera


async def _reject_while_a_run_is_active(session: AsyncSession, project_id: int) -> None:
    """`409`, solange ein Vorgang dieses Projekts laeuft, der in DIESELBEN Zeilen schreibt.

    Erfasst den `CriterionScoringRun` UND DEN SCAN. Der Scan schreibt `taken_at` ebenfalls und
    haelt den Versatz je Lauf zwischengespeichert: ohne diesen Waechter schreibt ein nach dem
    `PUT` weiterlaufender Scan fuer jedes noch verarbeitete Foto die Zeit mit dem ALTEN Versatz
    zurueck und bricht die Invariante still, bis irgendwann erneut gescannt wird.

    Geprueft wird je Typ nur der NEUESTE Lauf (Muster `api/projects.py::delete_project`), damit
    ein haengengebliebener Altlauf nicht dauerhaft blockiert - ein solcher wird ohnehin vom
    Watchdog auf FAILED gesetzt."""
    latest_scan = (
        (
            await session.execute(
                select(ScanRun.status)
                .where(ScanRun.project_id == project_id)
                .order_by(ScanRun.started_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    latest_criterion_run = (
        (
            await session.execute(
                select(CriterionScoringRun.status)
                .where(CriterionScoringRun.project_id == project_id)
                .order_by(CriterionScoringRun.started_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )

    if any(run_status == ScanStatus.RUNNING for run_status in (latest_scan, latest_criterion_run)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fuer dieses Projekt laeuft gerade ein Vorgang. Der Versatz kann danach "
            "gesetzt werden.",
        )


@router.put("/{project_id}/cameras/{camera_id}/time-offset", response_model=ProjectCameraOut)
async def set_camera_time_offset(
    project_id: int,
    camera_id: int,
    payload: TimeOffsetIn,
    session: AsyncSession = Depends(get_session),
) -> ProjectCameraOut:
    """Setzt den Zeitversatz einer Kamera dieses Projekts und macht ihn unmittelbar wirksam -
    in Gliederung, Reihenfolge, Statistik und Ortsuebernahme, OHNE dass die Fotos erneut
    eingelesen werden: kein OpenCloud-Zugriff, kein Cloud-Aufruf.

    ALLES ODER NICHTS - genau EIN `commit` am Ende, in dieser Reihenfolge: Kamerazeile sperren
    (`404` bei fremder Id) -> `409`, solange ein Scan oder Kriterien-Lauf dieses Projekts laeuft
    -> die Zeiten rechnen, ein Ueberlauf ergibt `422` OHNE JEDES SCHREIBEN -> `taken_at`
    gebuendelt schreiben -> `offset_minutes` setzen -> Gliederung neu aufbauen -> committen. Ein
    `409`, ein `422`, ein Verbindungsabbruch und jeder Fehler im Neuaufbau lassen den Vorzustand
    unveraendert; nie eine halb verschobene Fotomenge und nie eine Gliederung ohne Rangzeilen -
    diesen Zustand weist keine Ansicht als fehlerhaft aus.

    WIEDERHOLBAR: gerechnet wird ausschliesslich aus `taken_at_original`, nie durch Addition
    einer Differenz auf den bestehenden Wert (das kumulierte bei jedem weiteren Aufruf und waere
    nicht zurueckrechenbar). Kein frueher Ausstieg bei unveraendertem Wert - ein wiederholter
    Aufruf mit demselben Wert ist folgenlos, ein Aufruf mit verlorener Antwort darf wiederholt
    werden. Der Neuaufbau laeuft trotzdem und vergibt neue Event-Ids.

    KEINE Obergrenze auf der Fotozahl: der Endpunkt ist authentifiziert, beide Nutzer sind die
    Vertrauensbasis, und eine Grenze wuerde grosse Projekte vom Feature ausschliessen. Bewusst
    getragen: ein Aufruf auf einem grossen Projekt laeuft lange und haelt dabei Zeilensperren."""
    await _get_project_or_404(project_id, session)
    camera = await _locked_camera_or_404(session, project_id, camera_id)
    await _reject_while_a_run_is_active(session, project_id)

    rows = (
        await session.execute(
            select(Photo.id, Photo.taken_at_original).where(
                Photo.camera_id == camera.id, Photo.project_id == project_id
            )
        )
    ).all()

    # ERST rechnen, DANN schreiben: ein einziges nicht darstellbares Ergebnis weist den ganzen
    # Versatz zurueck. Ein teilweise angewandter Versatz waere eine gebrochene Invariante, die
    # keine Ansicht als fehlerhaft ausweist.
    updates: list[dict[str, object]] = []
    for photo_id, taken_at_original in rows:
        corrected = shifted(taken_at_original, payload.offset_minutes)
        if corrected is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Mit diesem Versatz liegt die Aufnahmezeit eines Fotos ausserhalb des "
                "darstellbaren Bereichs. Es wurde nichts gespeichert.",
            )
        updates.append({"id": photo_id, "taken_at": corrected})

    # Die Beschriftung entsteht VOR dem `commit`: danach sind die Attribute der Zeile expired,
    # und ein Zugriff darauf liefe in einen Lazy-Load ausserhalb eines aktiven greenlet-Kontexts
    # (`MissingGreenlet`) - dieselbe Falle, die `worker.py::_fail_run` mit seinem `refresh`
    # umgeht. Die Fotoanzahl steht ebenfalls schon fest: `updates` ist genau die Menge der Fotos
    # dieser Kamera in diesem Projekt, eine zweite Zaehlabfrage waere dieselbe Zahl.
    label = camera_label(CameraIdentity(make=camera.make, model=camera.model))
    photo_count = len(updates)

    if updates:
        # EIN Aufruf statt einer Anweisung je Zeile.
        await session.execute(update(Photo), updates)
    camera.offset_minutes = payload.offset_minutes
    await session.flush()

    # Reihenfolge, Anzeige und Ortsherleitung sind mit der Bedeutung von `taken_at` bereits
    # richtig; die EVENTS sind persistierte Lauf-Artefakte und waeren es nicht.
    await rebuild_run_grouping(session, project_id)
    await session.commit()

    return ProjectCameraOut(
        id=camera_id,
        label=label,
        photo_count=photo_count,
        offset_minutes=payload.offset_minutes,
    )


async def _photo_of_project_or_404(session: AsyncSession, project_id: int, photo_id: int) -> Photo:
    photo = (
        await session.execute(
            select(Photo).where(Photo.id == photo_id, Photo.project_id == project_id)
        )
    ).scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    return photo


@router.get(
    "/{project_id}/camera-time-offset-suggestion",
    response_model=CameraTimeOffsetSuggestionOut,
)
async def suggest_camera_time_offset(
    project_id: int,
    photo_id: int = Query(ge=1, le=_MAX_PHOTO_ID),
    reference_photo_id: int = Query(ge=1, le=_MAX_PHOTO_ID),
    session: AsyncSession = Depends(get_session),
) -> CameraTimeOffsetSuggestionOut:
    """Errechnet aus einem Fotopaar desselben Moments einen auf die Minute gerundeten
    Versatzvorschlag - und SPEICHERT NICHTS. Die Uebernahme ist der `PUT` oben.

    `photo_id` ist das Foto der betroffenen Kamera, `reference_photo_id` eines von einer ANDEREN
    Kamera. Gerechnet wird auf der AUFGEZEICHNETEN Zeit des Kamerafotos und der KORRIGIERTEN des
    Referenzfotos (ADR 0090, Punkt 6): rechnete der Vorschlag auf der korrigierten Zeit des
    Kamerafotos, haenge er vom bereits gesetzten Versatz ab und derselbe Aufruf mit demselben
    Fotopaar schluege spaeter etwas anderes vor.

    `422`, wenn das Kamerafoto keine bestimmbare Kamera hat, wenn beide Fotos von derselben
    Kamera stammen (dann ist die Differenz keine Uhrenabweichung) oder wenn das Ergebnis jenseits
    der zulaessigen Grenzen liegt. Ein Foto eines fremden Projekts ergibt `404`."""
    await _get_project_or_404(project_id, session)
    photo = await _photo_of_project_or_404(session, project_id, photo_id)
    reference = await _photo_of_project_or_404(session, project_id, reference_photo_id)

    if photo.camera_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fuer dieses Foto ist keine Kamera bestimmbar - es kann keinen Versatz tragen.",
        )
    if photo.camera_id == reference.camera_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Beide Fotos stammen von derselben Kamera. Waehle als Referenz ein Foto einer "
            "anderen Kamera.",
        )

    offset = suggested_offset_minutes(photo.taken_at_original, reference.taken_at)
    if abs(offset) > MAX_TIME_OFFSET_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Der errechnete Versatz liegt ausserhalb des zulaessigen Bereichs.",
        )

    camera = await session.get(ProjectCamera, photo.camera_id)
    assert camera is not None  # echter Fremdschluessel, die Zeile existiert
    return CameraTimeOffsetSuggestionOut(
        camera_id=camera.id,
        camera_label=camera_label(CameraIdentity(make=camera.make, model=camera.model)),
        offset_minutes=offset,
        photo_taken_at_original=photo.taken_at_original,
        reference_taken_at=reference.taken_at,
    )
