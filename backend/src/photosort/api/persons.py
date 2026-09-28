"""Die sieben Endpunkte der Personen.

SICHERHEIT:
* S1 - Der Router traegt `dependencies=[Depends(get_current_user)]`; jeder Endpunkt ist
  authentifiziert, auch die beiden Gesichts-Endpunkte und der PUT der Korrektur.
* S2 - Alle Eingabeschemata haben `extra="forbid"` und genau die genannten Felder. `user_id` kommt
  ausschliesslich aus `current_user` und steht in keiner Antwort. Ein `IntegrityError` wird `409`.
* S5 - Keine Antwort traegt ein Merkmal, einen Schwerpunkt oder eine Aehnlichkeit.
* S7 - Die Modellaufrufe laufen auf einem EIGENEN Executor mit genau einem Thread: Wartende belegen
  keinen Platz im gemeinsamen Threadpool, und die `cv2`-Objekte sind serialisiert. Gelesen wird nur
  die lokale Display-Variante; fehlt sie, antwortet der Endpunkt `404`, ohne das Modell zu rufen.
* S8 - Der Ausschnitt ist ein neu codiertes JPEG mit `Cache-Control: no-store` und
  `X-Content-Type-Options: nosniff`.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Executor, ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi import Path as PathParam
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
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
)
from photosort.models import Person, Photo, User
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

# Dieselbe Obergrenze wie `api/photos.py::MAX_QUERY_POSITION` - hier als Wert, weil `api/photos`
# dieses Modul importiert und nicht umgekehrt.
MAX_ID = 1_000_000_000

router = APIRouter(tags=["persons"], dependencies=[Depends(get_current_user)])

_PersonId = Annotated[int, PathParam(ge=1, le=MAX_ID)]
_PhotoId = Annotated[int, PathParam(ge=1, le=MAX_ID)]
_FaceIndex = Annotated[int, PathParam(ge=0, lt=MAX_FACES_PER_PHOTO)]


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
    `face_index` auf der Display-Variante des Fotos - und ordnet sie diesem Foto per Korrektur zu.
    Hoechstens zwei Personen, kein Name doppelt (nach NFC und `casefold`); ein gleichzeitiges
    Anlegen ergibt `409`, nie `500`. Keine Zahl, keine Schwelle in Eingabe oder Antwort."""
    try:
        name = clean_person_name(body.name)
    except PersonRefusal as refusal:
        raise _refusal(refusal) from None
    path = await _display_path_or_404(session, body.photo_id)
    try:
        found: tuple[list[float], FaceBox] = await _on_model_thread(
            executor, _embedding_at, analyzer, path, body.face_index
        )
        embedding, face_box = found
        person = await create_person(
            session,
            name=name,
            embedding=embedding,
            face_box=face_box,
            model_key=MODEL_KEY,
            photo_id=body.photo_id,
            user_id=current_user.id,
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
    Obergrenze gezeigter Gesichter wird nur benannt (`learned: false`). Schreibt kein
    Nacharbeits-Ereignis."""
    if await session.get(Person, person_id) is None:
        raise _refusal(PersonNotFound())
    path = await _display_path_or_404(session, body.photo_id)
    try:
        await refuse_if_face_on_photo(session, photo_id=body.photo_id, person_id=person_id)
    except PersonRefusal as refusal:
        raise _refusal(refusal) from None
    try:
        found: tuple[list[float], FaceBox] = await _on_model_thread(
            executor, _embedding_at, analyzer, path, body.face_index
        )
        embedding, face_box = found
        learned = await assign_face(
            session,
            person_id=person_id,
            embedding=embedding,
            face_box=face_box,
            model_key=MODEL_KEY,
            photo_id=body.photo_id,
            user_id=current_user.id,
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
    return Response(
        content=crop,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


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
    viele weitere Laeufe. Antwort ist die wirksame Liste des Fotos; kein Nacharbeits-Ereignis."""
    if await session.get(Photo, photo_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto nicht gefunden.")
    if await session.get(Person, person_id) is None:
        raise _refusal(PersonNotFound())
    try:
        await set_correction(
            session,
            photo_id=photo_id,
            person_id=person_id,
            applies=body.applies,
            user_id=current_user.id,
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise _refusal(ConcurrentPersonChange()) from None
    effective = await load_effective_persons(session, [photo_id])
    return photo_person_outs(effective.get(photo_id, []))
