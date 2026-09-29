"""Die acht Endpunkte der Personen.

SICHERHEIT:
* S1 - Der Router traegt `dependencies=[Depends(get_current_user)]`; jeder Endpunkt ist
  authentifiziert, auch die Gesichts-Endpunkte, die Auflistung "Ohne Namen" und der PUT der
  Korrektur.
* S2 - Alle Eingabeschemata haben `extra="forbid"` und genau die genannten Felder. `user_id` kommt
  ausschliesslich aus `current_user` und steht in keiner Antwort. Ein `IntegrityError` wird `409`.
  Eine Box nimmt kein Weg vom Client an: Sie entsteht beim Zuordnen aus demselben Detektionslauf
  wie das Merkmal.
* S3/S5 - Keine Antwort traegt ein Merkmal, einen Schwerpunkt, eine Aehnlichkeit oder eine
  gespeicherte Box. Die Auflistung "Ohne Namen" schreibt nichts und ruft `embed` nie.
* S7 - Die Modellaufrufe laufen auf einem EIGENEN Executor mit genau einem Thread: Wartende belegen
  keinen Platz im gemeinsamen Threadpool, und die `cv2`-Objekte sind serialisiert. Gelesen wird nur
  die lokale Display-Variante; fehlt sie, ruft kein Endpunkt das Modell.
* S8 - Ausschnitte sind neu codierte JPEGs; ihre Antworten tragen `Cache-Control: no-store` und
  `X-Content-Type-Options: nosniff`.
* Schreibsperre - siehe `_person_write_lock`.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import threading
from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi import Path as PathParam
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from photosort.api.deps import get_current_user, get_session, get_session_factory
from photosort.config import settings
from photosort.face_analysis import (
    MODEL_KEY,
    Face,
    FaceAnalyzerLike,
    FaceBox,
    build_face_analyzer,
    face_crop_jpeg,
    load_image,
    order_faces,
    unassigned_faces,
)
from photosort.models import Person, Photo, Project, User
from photosort.person_matching import MAX_FACES_PER_PHOTO
from photosort.persons import (
    ConcurrentPersonChange,
    DuplicatePersonName,
    FaceNotFound,
    PersonAssignment,
    PersonLimitReached,
    PersonNotFound,
    PersonRefusal,
    assign_face,
    assigned_face_boxes,
    clean_person_name,
    create_person,
    delete_person,
    list_persons,
    load_effective_persons,
    person_name_key,
    refuse_if_face_on_photo,
    set_correction,
)
from photosort.thumbnails import variant_path

logger = logging.getLogger(__name__)

# Dieselbe Obergrenze wie `api/photos.py::MAX_QUERY_POSITION` - hier als Wert, weil `api/photos`
# dieses Modul importiert und nicht umgekehrt.
MAX_ID = 1_000_000_000
# Eine Seite "Ohne Namen": hoechstens so viele Fotos, und Schluss nach dem Foto, mit dem so viele
# Gesichter erreicht sind. Mit `MAX_FACES_PER_PHOTO` traegt eine Seite hoechstens 67 Ausschnitte.
UNNAMED_PAGE_MAX_PHOTOS = 24
UNNAMED_PAGE_MAX_FACES = 48
DISCONNECT_WATCHER_NAME = "ohne-namen-trennung"
_NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}

router = APIRouter(tags=["persons"], dependencies=[Depends(get_current_user)])

_PersonId = Annotated[int, PathParam(ge=1, le=MAX_ID)]
_PhotoId = Annotated[int, PathParam(ge=1, le=MAX_ID)]
_ProjectId = Annotated[int, PathParam(ge=1, le=MAX_ID)]
_FaceIndex = Annotated[int, PathParam(ge=0, lt=MAX_FACES_PER_PHOTO)]

# SCHREIBSPERRE: Alle vier schreibenden Personen-Endpunkte (Festlegen, Zeigen, PUT der Korrektur,
# Entfernen der Person) pruefen, schreiben und committen nacheinander unter dieser prozessweiten
# Sperre. Ohne sie gaeben zwei gleichzeitige Zuordnungen dasselbe Gesicht zwei Personen, legten
# eine Referenz ueber `MAX_REFERENCES_PER_PERSON` hinaus an oder verwaisten eine Referenz, die
# danach nicht mehr zuruecknehmbar ist. `detect`/`embed` laufen NIE darunter.
# VORAUSSETZUNG: genau ein API-Prozess (`uvicorn` ohne `--workers`, ohne `WEB_CONCURRENCY`; ein
# Waechter in `tests/test_api_persons.py` liest Dockerfile und Compose-Dateien). Mit mehr als einem
# Prozess muss die Sperre in die Datenbank.
_person_write_lock = asyncio.Lock()


class PersonOut(BaseModel):
    id: int
    name: str
    reference_count: int


class PersonCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # S4: die Laenge an der API-Grenze VOR jeder weiteren Verarbeitung.
    name: str = Field(max_length=200)
    photo_id: int = Field(ge=1, le=MAX_ID)
    face_index: int = Field(ge=0, lt=MAX_FACES_PER_PHOTO)


class ReferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    photo_id: int = Field(ge=1, le=MAX_ID)
    face_index: int = Field(ge=0, lt=MAX_FACES_PER_PHOTO)


class PersonCorrectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applies: bool


class FaceBoxOut(BaseModel):
    x: float
    y: float
    width: float
    height: float


class FaceOut(BaseModel):
    index: int
    box: FaceBoxOut


class PhotoPersonOut(BaseModel):
    """Je wirksam zugeordneter Person nur Id, Herkunft und die Art des gebundenen Gesichts - der
    Name kommt aus `GET /persons`. `face` ist ein Aufzaehlungswert und nie eine Box: `shown`
    (gezeigt und gelernt), `assigned` (gewaehlt, nicht gelernt), `null` (Name fuer das ganze Foto
    oder erkannt)."""

    person_id: int
    origin: Literal["recognized", "corrected"]
    face: Literal["shown", "assigned"] | None


def photo_person_outs(assignments: list[PersonAssignment]) -> list[PhotoPersonOut]:
    return [
        PhotoPersonOut(person_id=entry.person_id, origin=entry.origin, face=entry.face)
        for entry in assignments
    ]


class FaceAssignmentOut(BaseModel):
    """Die Antwort auf Festlegen und Zeigen: die Person, ob PhotoSort aus dem Gesicht gelernt hat
    (`false` an der Obergrenze), und die wirksame Personenliste des Fotos. Kein nutzerabhaengiges
    Feld."""

    person: PersonOut
    learned: bool
    photo_persons: list[PhotoPersonOut]


class UnnamedFaceOut(BaseModel):
    """Ein Gesicht ohne Namen: adressiert ueber (Foto, Index), dazu sein Ausschnitt als base64 eines
    neu codierten JPEG. Keine Box, kein Wert, keine Aehnlichkeit, kein Pfad."""

    photo_id: int
    face_index: int
    crop_jpeg: str


class UnnamedFacesPageOut(BaseModel):
    faces: list[UnnamedFaceOut]
    not_ready_photo_ids: list[int]
    next_after_id: int | None
    photos_done: int
    photos_total: int


# --- Modell und Executor ----------------------------------------------------------------------

_executor: ThreadPoolExecutor | None = None
_analyzer: FaceAnalyzerLike | None = None
_state_lock = threading.Lock()


def get_face_executor() -> Executor:
    """Der EINE Modell-Thread des API-Prozesses, einmal je Prozess angelegt."""
    global _executor
    with _state_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gesichter")
        return _executor


async def get_face_analyzer(
    executor: Executor = Depends(get_face_executor),
) -> FaceAnalyzerLike:
    """Der Adapter, einmal je Prozess traege gebaut - auf dem Modell-Thread selbst. Ueberschreibbar
    ueber `app.dependency_overrides`; die echten Modelle laufen in keinem Test."""
    global _analyzer
    if _analyzer is None:
        built = await asyncio.get_running_loop().run_in_executor(executor, build_face_analyzer)
        with _state_lock:
            if _analyzer is None:
                _analyzer = built
    return _analyzer


def _refusal(refusal: PersonRefusal) -> HTTPException:
    return HTTPException(status_code=refusal.status_code, detail=refusal.detail)


async def _display_path_or_404(session: AsyncSession, photo_id: int) -> Path:
    photo = await session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    path = variant_path(Path(settings.photo_cache_dir), photo.id, photo.etag, "display")
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bild wird noch verarbeitet."
        )
    return path


def _faces(analyzer: FaceAnalyzerLike, path: Path) -> list[Face]:
    image = load_image(path)
    if image is None:
        return []
    return order_faces(analyzer.detect(image))


def _embedding_at(
    analyzer: FaceAnalyzerLike, path: Path, index: int
) -> tuple[list[float], FaceBox]:
    """Auflisten, Merkmal und Box in EINEM Aufruf auf dem Modell-Thread - aus demselben
    Detektionslauf. Der Index zeigt auf das Gesicht, das die Auflistung unter ihm zeigt."""
    image = load_image(path)
    faces = [] if image is None else order_faces(analyzer.detect(image))
    if image is None or index >= len(faces):
        raise FaceNotFound()
    return analyzer.embed(image, faces[index]), faces[index].box


def _crop_at(analyzer: FaceAnalyzerLike, path: Path, index: int) -> bytes | None:
    image = load_image(path)
    faces = [] if image is None else order_faces(analyzer.detect(image))
    if image is None or index >= len(faces):
        return None
    return face_crop_jpeg(image, faces[index])


def _unnamed_on_photo(
    analyzer: FaceAnalyzerLike, path: Path, taken: list[FaceBox]
) -> list[tuple[int, bytes]] | None:
    """Die Gesichter EINES Fotos ohne zugeordnete Person, je mit Index und Ausschnitt - oder
    `None`, wenn das Bild nicht lesbar ist. `embed` laeuft hier nie: Es entsteht kein Merkmal und
    keine Aehnlichkeit, und nichts davon verlaesst den Aufruf ausser der Rueckgabe."""
    image = load_image(path)
    if image is None:
        return None
    faces = order_faces(analyzer.detect(image))
    return [
        (index, face_crop_jpeg(image, faces[index])) for index in unassigned_faces(faces, taken)
    ]


async def _on_model_thread[T](executor: Executor, call: object, *args: object) -> T:
    result: T = await asyncio.get_running_loop().run_in_executor(executor, call, *args)  # type: ignore[arg-type]
    return result


async def _summary(session: AsyncSession, person_id: int) -> PersonOut:
    for entry in await list_persons(session, model_key=MODEL_KEY):
        if entry.id == person_id:
            return PersonOut(id=entry.id, name=entry.name, reference_count=entry.reference_count)
    raise _refusal(PersonNotFound())


async def _assignment(
    session: AsyncSession, *, person_id: int, photo_id: int, learned: bool
) -> FaceAssignmentOut:
    effective = await load_effective_persons(session, [photo_id])
    return FaceAssignmentOut(
        person=await _summary(session, person_id),
        learned=learned,
        photo_persons=photo_person_outs(effective.get(photo_id, [])),
    )


async def _release_connection(session: AsyncSession) -> None:
    """Gibt die Verbindung der Anfrage-Sitzung an den Pool zurueck, bevor die Anfrage auf das
    Modell oder die Schreibsperre wartet - auch die, die `get_current_user` geoeffnet hat. Die
    Sitzung beginnt beim naechsten Zugriff neu. `close` statt `rollback`: Geladene Objekte bleiben
    lesbar statt zu verfallen; ein Nachladen unter `AsyncSession` scheiterte (`MissingGreenlet`)."""
    await session.close()


# --- Endpunkte ---------------------------------------------------------------------------------


@router.get("/persons", response_model=list[PersonOut])
async def get_persons(session: AsyncSession = Depends(get_session)) -> list[PersonOut]:
    """Die festgelegten Personen nach Slot. `reference_count` zaehlt nur gezeigte Gesichter des
    aktuellen Modells; `0` heisst: ohne neues gezeigtes Gesicht wird die Person nicht erkannt."""
    return [
        PersonOut(id=entry.id, name=entry.name, reference_count=entry.reference_count)
        for entry in await list_persons(session, model_key=MODEL_KEY)
    ]


@router.post("/persons", response_model=FaceAssignmentOut, status_code=status.HTTP_201_CREATED)
async def post_person(
    body: PersonCreateIn,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    executor: Executor = Depends(get_face_executor),
    analyzer: FaceAnalyzerLike = Depends(get_face_analyzer),
) -> FaceAssignmentOut:
    """Legt eine Person NUR zusammen mit ihrer ersten Referenz an - dem Gesicht unter
    `face_index` auf der Display-Variante des Fotos - und ordnet ihr dieses Gesicht auf dem Foto per
    Korrektur zu. Hoechstens zwei Personen, kein Name doppelt (nach NFC und `casefold`); ein
    gleichzeitiges Anlegen ergibt `409`, nie `500`. Abgelehnt (`409`) auch, wenn das Gesicht der
    anderen Person gleicht oder ihr auf diesem Foto schon gehoert. Keine Zahl, keine Schwelle in
    Eingabe oder Antwort."""
    try:
        name = clean_person_name(body.name)
    except PersonRefusal as refusal:
        raise _refusal(refusal) from None
    user_id = current_user.id
    path = await _display_path_or_404(session, body.photo_id)
    await _release_connection(session)
    try:
        found: tuple[list[float], FaceBox] = await _on_model_thread(
            executor, _embedding_at, analyzer, path, body.face_index
        )
    except PersonRefusal as refusal:
        raise _refusal(refusal) from None
    embedding, face_box = found
    async with _person_write_lock:
        try:
            person = await create_person(
                session,
                name=name,
                embedding=embedding,
                face_box=face_box,
                model_key=MODEL_KEY,
                photo_id=body.photo_id,
                user_id=user_id,
            )
            person_id = person.id
            await session.commit()
        except PersonRefusal as refusal:
            await session.rollback()
            raise _refusal(refusal) from None
        except IntegrityError:
            await session.rollback()
            raise _refusal(await _conflict_after_integrity_error(session, name)) from None
    return await _assignment(session, person_id=person_id, photo_id=body.photo_id, learned=True)


async def _conflict_after_integrity_error(session: AsyncSession, name: str) -> PersonRefusal:
    """Nennt nach einem Constraint-Treffer die fachliche Ursache, frisch gelesen."""
    persons = await list_persons(session, model_key=MODEL_KEY)
    if len(persons) >= 2:
        return PersonLimitReached()
    if any(person_name_key(entry.name) == person_name_key(name) for entry in persons):
        return DuplicatePersonName()
    return ConcurrentPersonChange()


@router.post(
    "/persons/{person_id}/references",
    response_model=FaceAssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_reference(
    person_id: _PersonId,
    body: ReferenceIn,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    executor: Executor = Depends(get_face_executor),
    analyzer: FaceAnalyzerLike = Depends(get_face_analyzer),
) -> FaceAssignmentOut:
    """Zeigt ein weiteres Gesicht einer Person und ordnet sie diesem Foto zugleich per Korrektur
    zu. Abgelehnt (`409`), wenn diese Person hier schon ein Gesicht hat, das Gesicht der anderen
    Person gleicht oder auf diesem Foto ihr gehoert, oder das Merkmal ungueltig ist. An der
    Obergrenze gezeigter Gesichter wird nur benannt (`learned: false`), PhotoSort lernt dann
    nicht. Schreibt kein Nacharbeits-Ereignis."""
    user_id = current_user.id
    if await session.get(Person, person_id) is None:
        raise _refusal(PersonNotFound())
    path = await _display_path_or_404(session, body.photo_id)
    try:
        # Vor dem Modellaufruf; unter der Sperre wird sie wiederholt.
        await refuse_if_face_on_photo(session, photo_id=body.photo_id, person_id=person_id)
    except PersonRefusal as refusal:
        raise _refusal(refusal) from None
    await _release_connection(session)
    try:
        found: tuple[list[float], FaceBox] = await _on_model_thread(
            executor, _embedding_at, analyzer, path, body.face_index
        )
    except PersonRefusal as refusal:
        raise _refusal(refusal) from None
    embedding, face_box = found
    async with _person_write_lock:
        try:
            learned = await assign_face(
                session,
                person_id=person_id,
                embedding=embedding,
                face_box=face_box,
                model_key=MODEL_KEY,
                photo_id=body.photo_id,
                user_id=user_id,
            )
            await session.commit()
        except PersonRefusal as refusal:
            await session.rollback()
            raise _refusal(refusal) from None
        except IntegrityError:
            await session.rollback()
            raise _refusal(ConcurrentPersonChange()) from None
    return await _assignment(session, person_id=person_id, photo_id=body.photo_id, learned=learned)


@router.delete("/persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_person(
    person_id: _PersonId, session: AsyncSession = Depends(get_session)
) -> Response:
    """Entfernt eine Person in einer Transaktion samt Korrekturen, Erkennungen und gezeigten
    Gesichtern, in allen Projekten. Die Fotos und ihre Bewertungen bleiben unveraendert."""
    await _release_connection(session)
    async with _person_write_lock:
        if not await delete_person(session, person_id):
            raise _refusal(PersonNotFound())
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/photos/{photo_id}/faces", response_model=list[FaceOut])
async def get_faces(
    photo_id: _PhotoId,
    session: AsyncSession = Depends(get_session),
    executor: Executor = Depends(get_face_executor),
    analyzer: FaceAnalyzerLike = Depends(get_face_analyzer),
) -> list[FaceOut]:
    """Die verwertbaren Gesichter der Display-Variante, hoechstens 20, von links nach rechts und
    oben nach unten. Nur `{index, box}` (Box auf das Bild normiert); gespeichert wird nichts.
    `404` "Bild wird noch verarbeitet.", solange die Display-Variante fehlt."""
    path = await _display_path_or_404(session, photo_id)
    faces: list[Face] = await _on_model_thread(executor, _faces, analyzer, path)
    return [
        FaceOut(
            index=index,
            box=FaceBoxOut(
                x=face.box.x, y=face.box.y, width=face.box.width, height=face.box.height
            ),
        )
        for index, face in enumerate(faces)
    ]


@router.get("/photos/{photo_id}/faces/{index}/image")
async def get_face_image(
    photo_id: _PhotoId,
    index: _FaceIndex,
    session: AsyncSession = Depends(get_session),
    executor: Executor = Depends(get_face_executor),
    analyzer: FaceAnalyzerLike = Depends(get_face_analyzer),
) -> Response:
    """Der Ausschnitt eines Gesichts als neu codiertes JPEG, `Cache-Control: no-store`. Nichts
    davon wird gespeichert; `404` bei fehlender Variante oder einem Index ausserhalb der Liste."""
    path = await _display_path_or_404(session, photo_id)
    crop: bytes | None = await _on_model_thread(executor, _crop_at, analyzer, path, index)
    if crop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=FaceNotFound.detail)
    return Response(content=crop, media_type="image/jpeg", headers=_NO_STORE)


@router.put("/photos/{photo_id}/persons/{person_id}", response_model=list[PhotoPersonOut])
async def put_photo_person(
    photo_id: _PhotoId,
    person_id: _PersonId,
    body: PersonCorrectionIn,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[PhotoPersonOut]:
    """Ergaenzt (`applies=true`) oder entfernt (`false`) eine Person auf einem Foto. Die zuletzt
    geschriebene Korrektur gilt fuer beide Nutzer und geht jeder Erkennung vor, ueber beliebig
    viele weitere Laeufe. Traegt das Paar ein gezeigtes Gesicht, nimmt `false` es zurueck: Box und
    Kante werden geleert und die daraus entstandene Referenz geloescht, in derselben
    Transaktion. Antwort ist die wirksame Liste des Fotos; kein Nacharbeits-Ereignis."""
    user_id = current_user.id
    await _release_connection(session)
    async with _person_write_lock:
        if await session.get(Photo, photo_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden."
            )
        if await session.get(Person, person_id) is None:
            raise _refusal(PersonNotFound())
        try:
            await set_correction(
                session,
                photo_id=photo_id,
                person_id=person_id,
                applies=body.applies,
                user_id=user_id,
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise _refusal(ConcurrentPersonChange()) from None
    effective = await load_effective_persons(session, [photo_id])
    return photo_person_outs(effective.get(photo_id, []))


async def _watch_disconnect(request: Request, gone: asyncio.Event) -> None:
    """Liest die Nachrichten der Anfrage, bis der Client sich trennt. Liest nie einen Body - der
    Endpunkt ist ein GET ohne Body. `request.is_disconnected()` meldet die Trennung hinter einem
    `BaseHTTPMiddleware` (hier `SlowAPIMiddleware`) nie; ein wartendes `receive` dagegen schon."""
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            gone.set()
            return


@router.get("/projects/{project_id}/unnamed-faces", response_model=UnnamedFacesPageOut)
async def get_unnamed_faces(
    request: Request,
    response: Response,
    project_id: _ProjectId,
    after_id: Annotated[int, Query(ge=0, le=MAX_ID)] = 0,
    max_photos: Annotated[int, Query(ge=1, le=UNNAMED_PAGE_MAX_PHOTOS)] = UNNAMED_PAGE_MAX_PHOTOS,
    session: AsyncSession = Depends(get_session),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    executor: Executor = Depends(get_face_executor),
    analyzer: FaceAnalyzerLike = Depends(get_face_analyzer),
) -> UnnamedFacesPageOut | Response:
    """Eine Seite "Ohne Namen": je Foto des Projekts ab `after_id` (exklusiv, nach Foto-Id) die
    Gesichter, die keiner Person zugeordnet sind, einzeln mit Ausschnitt, nach (Foto-Id, Index).
    Die Seite endet nach `max_photos` Fotos oder nach dem Foto, mit dem 48 Gesichter erreicht sind.
    `next_after_id` ist `null`, wenn das Projekt kein Foto dahinter hat.

    Nichts wird geschrieben, kein Merkmal gebildet, nichts gruppiert oder vorgeschlagen. Fotos ohne
    Display-Variante, mit unlesbarem Bild oder einem Modellfehler stehen in `not_ready_photo_ids`.
    Je Foto ein eigener Auftrag auf dem Modell-Thread, ohne gehaltene Datenbankverbindung; eine
    Zuordnung wartet so hoechstens ein Foto. Trennt sich der Client, endet die Seite nach dem
    laufenden Foto mit einer leeren `204`."""
    if await session.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    in_project = Photo.project_id == project_id
    photos_total = (
        await session.execute(select(func.count()).select_from(Photo).where(in_project))
    ).scalar_one()
    done_before = (
        await session.execute(
            select(func.count()).select_from(Photo).where(in_project, Photo.id <= after_id)
        )
    ).scalar_one()
    candidates = list(
        (
            await session.execute(
                select(Photo.id)
                .where(in_project, Photo.id > after_id)
                .order_by(Photo.id)
                .limit(max_photos + 1)
            )
        )
        .scalars()
        .all()
    )
    await _release_connection(session)

    gone = asyncio.Event()
    watcher = asyncio.create_task(_watch_disconnect(request, gone), name=DISCONNECT_WATCHER_NAME)
    try:
        faces: list[UnnamedFaceOut] = []
        not_ready: list[int] = []
        processed: list[int] = []
        for photo_id in candidates[:max_photos]:
            if gone.is_set():
                logger.info("Ohne Namen: Anfrage vom Client getrennt, Seite abgebrochen.")
                return Response(status_code=status.HTTP_204_NO_CONTENT, headers=_NO_STORE)
            listed = await _unnamed_photo(photo_id, session_factory, executor, analyzer)
            processed.append(photo_id)
            if listed is None:
                not_ready.append(photo_id)
                continue
            faces.extend(
                UnnamedFaceOut(
                    photo_id=photo_id,
                    face_index=index,
                    crop_jpeg=base64.b64encode(crop).decode("ascii"),
                )
                for index, crop in listed
            )
            if len(faces) >= UNNAMED_PAGE_MAX_FACES:
                break
    finally:
        watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher
    more = len(candidates) > len(processed)
    response.headers.update(_NO_STORE)
    return UnnamedFacesPageOut(
        faces=faces,
        not_ready_photo_ids=not_ready,
        next_after_id=processed[-1] if processed and more else None,
        photos_done=done_before + len(processed),
        photos_total=photos_total,
    )


async def _unnamed_photo(
    photo_id: int,
    session_factory: Callable[[], AsyncSession],
    executor: Executor,
    analyzer: FaceAnalyzerLike,
) -> list[tuple[int, bytes]] | None:
    """EIN Foto: Variantenpfad und zugeordnete Boxen in einer kurzen, eigenen Lesesitzung, die
    VOR dem Modellaufruf endet; dann ein Auftrag auf dem Modell-Thread. `None` heisst "nicht
    bereit". LOG-HYGIENE: Eine Ausnahme erscheint nur als Typname samt `photo_id`."""
    async with session_factory() as photo_session:
        photo = await photo_session.get(Photo, photo_id)
        if photo is None:
            # Inzwischen geloescht: kein Gesicht, aber auch nicht "nicht bereit".
            return []
        path = variant_path(Path(settings.photo_cache_dir), photo.id, photo.etag, "display")
        taken = (await assigned_face_boxes(photo_session, [photo_id])).get(photo_id, [])
    if not path.is_file():
        return None
    try:
        listed: list[tuple[int, bytes]] | None = await _on_model_thread(
            executor, _unnamed_on_photo, analyzer, path, taken
        )
    except Exception as exc:
        logger.warning("Ohne Namen: Foto %s uebersprungen (%s).", photo_id, type(exc).__name__)
        return None
    return listed
