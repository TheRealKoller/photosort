"""Die beiden benannten Personen: festlegen, gezeigte Gesichter, Korrekturen, entfernen, und die
wirksame Zuordnung.

DIE EINE STELLE fuer die wirksame Zuordnung: `effective_person_assignments()` ist das einzige
SQL-Konstrukt, in dem die Korrekturspalte in die Zuordnung eines Fotos eingeht - Korrektur vor
Erkennung. DIE EINE STELLE fuer "welches Gesicht gilt auf einem Foto als zugeordnet" ist
`assigned_face_boxes`. Filter, Anzeige und "Ohne Namen" beziehen beides von hier; Quelltext-
Waechter in `tests/test_persons.py` halten fest, dass keine zweite Fassung entsteht.

DIE EINE SCHREIBSTELLE fuer `PersonReference`: `_store_reference`, erreicht nur ueber
`create_person` und `assign_face` - und damit nur fuer ein ausdruecklich GEZEIGTES Gesicht.
Erkannte Gesichter werden nie von selbst zu Referenzen. Jede Referenz, die hier entsteht, haengt
ueber `PhotoPersonCorrection.reference_id` an genau einer Korrektur; eine Korrektur `applies=false`
auf diesem Paar nimmt sie in derselben Transaktion zurueck (`set_correction`).

IMPORTREGEL: Dieses Modul importiert direkt keinen Netzwerk-Client.
Schwerpunkte werden je Aufruf frisch aus der Datenbank gebildet und nie darueber hinaus gehalten -
ein Zwischenspeicher erkennte eine entfernte Person weiter, bis der Prozess neu startet.

Kein `commit()` hier: Die Transaktionsgrenze gehoert dem Aufrufer. Eine Person entsteht so nur
zusammen mit ihrer ersten Referenz, und `delete_person` loescht in EINER Transaktion. Gleichzeitige
Schreiber serialisiert der Aufrufer (`api/persons.py::_person_write_lock`); das bedingte Setzen der
Box und `UNIQUE(photo_id, person_id)` sind die zweite Linie dahinter.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from sqlalchemy import String, and_, case, delete, func, literal, null, select, union_all
from sqlalchemy import cast as sql_cast
from sqlalchemy import update as sql_update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Subquery

from photosort.clock import now_utc
from photosort.face_analysis import FaceBox, is_valid_face_box, same_face
from photosort.models import Person, PersonReference, PhotoPersonCorrection, PhotoPersonDetection
from photosort.person_matching import (
    MAX_REFERENCES_PER_PERSON,
    StoredReference,
    centroid,
    conflicts_with_other_person,
    cosine,
    validated_embedding,
)

MAX_PERSONS = 2
PERSON_SLOTS = (1, 2)
MAX_NAME_CODE_POINTS = 40

Origin = Literal["recognized", "corrected"]
# `shown`: Box und Referenz, `assigned`: Box ohne Referenz (Obergrenze, Modellwechsel).
FaceState = Literal["shown", "assigned"]

# Unicode-Kategorien, deren Zeichen einen Namen UNGUELTIG machen: Steuer-, Format-, Ersatz-,
# private und nicht zugewiesene Zeichen sowie Zeilen- und Absatztrenner.
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


class PersonRefusal(Exception):
    """Eine fachliche Ablehnung. `detail` ist der woertlich angezeigte Text - er nennt nie einen
    Namen, ein Merkmal oder eine Aehnlichkeit."""

    status_code = 409
    detail = "Die Anfrage wurde abgelehnt."

    def __init__(self) -> None:
        super().__init__(self.detail)


class InvalidPersonName(PersonRefusal):
    status_code = 422
    detail = (
        "Der Name muss 1 bis 40 Zeichen lang sein und darf keine Steuer- oder unsichtbaren "
        "Zeichen enthalten."
    )


class PersonLimitReached(PersonRefusal):
    detail = "Es sind bereits zwei Personen festgelegt."


class DuplicatePersonName(PersonRefusal):
    detail = "Eine Person mit diesem Namen gibt es schon."


class ConcurrentPersonChange(PersonRefusal):
    detail = "Gleichzeitig wurde eine andere Änderung gespeichert. Bitte erneut versuchen."


class FaceNotFound(PersonRefusal):
    detail = "An dieser Stelle ist auf dem Foto kein Gesicht mehr zu finden."


class InvalidEmbedding(PersonRefusal):
    detail = "Aus diesem Gesicht lässt sich kein verwertbares Merkmal bilden."


class ResemblesOtherPerson(PersonRefusal):
    detail = "Dieses Gesicht gleicht der anderen Person und wird deshalb nicht übernommen."


class FaceAlreadyAssignedOnPhoto(PersonRefusal):
    detail = "Diese Person hat auf diesem Foto schon ein Gesicht."


class FaceAssignedToOtherPerson(PersonRefusal):
    detail = "Dieses Gesicht gehört auf diesem Foto schon der anderen Person."


class PersonNotFound(PersonRefusal):
    status_code = 404
    detail = "Person nicht gefunden."


@dataclass(frozen=True)
class PersonAssignment:
    person_id: int
    origin: Origin
    # Nur im Korrekturzweig gesetzt; eine Erkennung traegt hier immer `None`.
    face: FaceState | None = None


@dataclass(frozen=True)
class PersonSummary:
    id: int
    name: str
    reference_count: int


# --- Name --------------------------------------------------------------------------------------


def clean_person_name(raw: str) -> str:
    """NFC, dann ABWEISEN statt bereinigen, dann an Leerzeichen trimmen und die Laenge pruefen.

    Abgewiesen wird jedes Zeichen der Kategorien in `_FORBIDDEN_CATEGORIES` und jeder Leerraum
    ausser U+0020. Nicht entfernen, weil der Entfernen-Dialog den Namen exakt getippt verlangt:
    Ein unsichtbares Zeichen machte die Person ueber die Oberflaeche unloeschbar, und ein
    Bidi-Override dreht die Anzeige."""
    name = unicodedata.normalize("NFC", raw)
    for character in name:
        if unicodedata.category(character) in _FORBIDDEN_CATEGORIES:
            raise InvalidPersonName()
        if character.isspace() and character != " ":
            raise InvalidPersonName()
    name = name.strip(" ")
    if not 1 <= len(name) <= MAX_NAME_CODE_POINTS:
        raise InvalidPersonName()
    return name


def person_name_key(name: str) -> str:
    """Der Vergleichsschluessel gegen doppelte Namen: NFC und `casefold`, wieder NFC."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", name).casefold())


# --- Die wirksame Zuordnung --------------------------------------------------------------------


def effective_person_assignments() -> Subquery:
    """DAS EINE SQL-Konstrukt: `(photo_id, person_id, origin, face)` je wirksam zugeordnetem Paar.

    Gibt es eine Korrektur, entscheidet sie: `applies=true` ergibt `corrected`, `applies=false`
    nimmt das Paar heraus, auch wenn es erkannt ist. Ohne Korrektur gilt die Erkennung
    (`recognized`). `face` nennt das gebundene Gesicht der Korrektur (`shown`/`assigned`); im
    Erkennungszweig ist es immer `NULL`. Die Zuordnung wird nie materialisiert."""
    face = case(
        (PhotoPersonCorrection.face_box_x.is_(None), sql_cast(null(), String)),
        (PhotoPersonCorrection.reference_id.is_(None), literal("assigned")),
        else_=literal("shown"),
    )
    corrected = select(
        PhotoPersonCorrection.photo_id.label("photo_id"),
        PhotoPersonCorrection.person_id.label("person_id"),
        literal("corrected").label("origin"),
        face.label("face"),
    ).where(PhotoPersonCorrection.applies.is_(True))
    recognized = (
        select(
            PhotoPersonDetection.photo_id.label("photo_id"),
            PhotoPersonDetection.person_id.label("person_id"),
            literal("recognized").label("origin"),
            sql_cast(null(), String).label("face"),
        )
        .outerjoin(
            PhotoPersonCorrection,
            and_(
                PhotoPersonCorrection.photo_id == PhotoPersonDetection.photo_id,
                PhotoPersonCorrection.person_id == PhotoPersonDetection.person_id,
            ),
        )
        .where(PhotoPersonCorrection.id.is_(None))
    )
    return union_all(corrected, recognized).subquery("effective_person_assignments")


async def load_effective_persons(
    session: AsyncSession, photo_ids: Iterable[int]
) -> dict[int, list[PersonAssignment]]:
    """Je Foto die wirksam zugeordneten Personen, nach Slot. Ein Foto ohne Zuordnung fehlt im
    Ergebnis. Eine leere Id-Liste fragt die Datenbank gar nicht."""
    ids = list(photo_ids)
    if not ids:
        return {}
    effective = effective_person_assignments()
    rows = (
        await session.execute(
            select(
                effective.c.photo_id, effective.c.person_id, effective.c.origin, effective.c.face
            )
            .join(Person, Person.id == effective.c.person_id)
            .where(effective.c.photo_id.in_(ids))
            .order_by(effective.c.photo_id, Person.slot)
        )
    ).all()
    result: dict[int, list[PersonAssignment]] = {}
    for photo_id, person_id, origin, face in rows:
        result.setdefault(photo_id, []).append(
            PersonAssignment(person_id=person_id, origin=origin, face=face)
        )
    return result


def _box_of(
    x: float | None, y: float | None, width: float | None, height: float | None
) -> FaceBox | None:
    if x is None or y is None or width is None or height is None:
        return None
    return FaceBox(x=x, y=y, width=width, height=height)


async def assigned_face_boxes(
    session: AsyncSession, photo_ids: Iterable[int], *, excluding_person_id: int | None = None
) -> dict[int, list[FaceBox]]:
    """DIE EINE STELLE der Regel "welches Gesicht gilt als zugeordnet". Je Paar (Foto, Person)
    gilt die erste zutreffende Regel:

    1. Korrektur `applies=false`: kein Gesicht.
    2. Korrektur mit Box: diese Box.
    3. Erkennung mit Box: diese Box.
    4. Sonst kein Gesicht - ein Name nur fuer das ganze Foto oder eine Erkennung aus einem Lauf
       ohne Box laesst die Gesichter des Fotos in "Ohne Namen".

    Je Foto die Boxen, ohne die der Person `excluding_person_id`. Ein Foto ohne Box fehlt."""
    ids = list(photo_ids)
    if not ids:
        return {}
    corrections = (
        await session.execute(
            select(
                PhotoPersonCorrection.photo_id,
                PhotoPersonCorrection.person_id,
                PhotoPersonCorrection.applies,
                PhotoPersonCorrection.face_box_x,
                PhotoPersonCorrection.face_box_y,
                PhotoPersonCorrection.face_box_width,
                PhotoPersonCorrection.face_box_height,
            ).where(PhotoPersonCorrection.photo_id.in_(ids))
        )
    ).all()
    detections = (
        await session.execute(
            select(
                PhotoPersonDetection.photo_id,
                PhotoPersonDetection.person_id,
                PhotoPersonDetection.face_box_x,
                PhotoPersonDetection.face_box_y,
                PhotoPersonDetection.face_box_width,
                PhotoPersonDetection.face_box_height,
            ).where(PhotoPersonDetection.photo_id.in_(ids))
        )
    ).all()
    decided: dict[tuple[int, int], FaceBox | None] = {}
    for photo_id, person_id, applies, *box in corrections:
        if not applies:
            decided[(photo_id, person_id)] = None
        elif (corrected := _box_of(*box)) is not None:
            decided[(photo_id, person_id)] = corrected
    for photo_id, person_id, *box in detections:
        if (photo_id, person_id) not in decided:
            decided[(photo_id, person_id)] = _box_of(*box)
    result: dict[int, list[FaceBox]] = {}
    for (photo_id, person_id), face_box in sorted(decided.items()):
        if face_box is not None and person_id != excluding_person_id:
            result.setdefault(photo_id, []).append(face_box)
    return result


# --- Lesen ---------------------------------------------------------------------------------------


async def list_persons(session: AsyncSession, *, model_key: str) -> list[PersonSummary]:
    """Alle Personen nach Slot, gezaehlt werden nur Referenzen des aktuellen `model_key`."""
    counts = (
        select(PersonReference.person_id, func.count().label("reference_count"))
        .where(PersonReference.model_key == model_key)
        .group_by(PersonReference.person_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Person.id, Person.name, func.coalesce(counts.c.reference_count, 0))
            .outerjoin(counts, counts.c.person_id == Person.id)
            .order_by(Person.slot)
        )
    ).all()
    return [
        PersonSummary(id=person_id, name=name, reference_count=int(count))
        for person_id, name, count in rows
    ]


async def current_centroids(
    session: AsyncSession, *, model_key: str
) -> dict[int, tuple[float, ...]]:
    """Je Person mit gueltiger Referenz des aktuellen Modells ihr Schwerpunkt. Liest nur Id und
    Merkmal - NIE den Namen. Frisch je Aufruf, nie zwischengespeichert."""
    rows = (
        await session.execute(
            select(PersonReference.person_id, PersonReference.embedding).where(
                PersonReference.model_key == model_key
            )
        )
    ).all()
    by_person: dict[int, list[StoredReference]] = {}
    for person_id, embedding in rows:
        by_person.setdefault(person_id, []).append(
            StoredReference(model_key=model_key, embedding=embedding)
        )
    centroids: dict[int, tuple[float, ...]] = {}
    for person_id, references in by_person.items():
        center = centroid(references, model_key=model_key)
        if center is not None:
            centroids[person_id] = center
    return centroids


# --- Festlegen und Referenzen ------------------------------------------------------------------


async def _taken_slots(session: AsyncSession) -> set[int]:
    return set((await session.execute(select(Person.slot))).scalars().all())


async def _name_taken(session: AsyncSession, name_key: str) -> bool:
    found = (await session.execute(select(Person.id).where(Person.name_key == name_key))).first()
    return found is not None


async def _refuse_if_like_the_other(
    session: AsyncSession, embedding: Sequence[float], *, person_id: int | None, model_key: str
) -> None:
    for other_id, center in (await current_centroids(session, model_key=model_key)).items():
        if other_id != person_id and conflicts_with_other_person(cosine(embedding, center)):
            raise ResemblesOtherPerson()


def _checked_face(embedding: Sequence[float], face_box: FaceBox) -> tuple[float, ...]:
    """Merkmal und Box aus demselben Detektionslauf. Beide in EINSCHLUSSFORM geprueft - ein NaN
    faellt auf "ungueltig", bevor etwas geschrieben wird; die Pruefeinschraenkungen der Tabelle sind
    die zweite Linie."""
    checked = validated_embedding(embedding)
    if checked is None or not is_valid_face_box(face_box):
        raise InvalidEmbedding()
    return checked


async def _has_correction_face(session: AsyncSession, *, photo_id: int, person_id: int) -> bool:
    found = (
        await session.execute(
            select(PhotoPersonCorrection.id).where(
                PhotoPersonCorrection.photo_id == photo_id,
                PhotoPersonCorrection.person_id == person_id,
                PhotoPersonCorrection.face_box_x.is_not(None),
            )
        )
    ).first()
    return found is not None


async def refuse_if_face_on_photo(session: AsyncSession, *, photo_id: int, person_id: int) -> None:
    """Diese Person hat auf diesem Foto schon ein Gesicht PER KORREKTUR. Eine Erkennung mit Box
    sperrt nicht: Ein erkanntes Gesicht ausdruecklich zu zeigen ist Anlernen, und die Box der
    Korrektur geht vor. Laeuft vor dem Modellaufruf und unter der Schreibsperre erneut."""
    if await _has_correction_face(session, photo_id=photo_id, person_id=person_id):
        raise FaceAlreadyAssignedOnPhoto()


async def _refuse_if_face_of_other(
    session: AsyncSession, face_box: FaceBox, *, photo_id: int, person_id: int | None
) -> None:
    """Das gewaehlte Gesicht ist auf diesem Foto schon einer anderen Person zugeordnet - nach
    `assigned_face_boxes`, also auch ein erkanntes."""
    others = await assigned_face_boxes(session, [photo_id], excluding_person_id=person_id)
    if any(same_face(stored, face_box) for stored in others.get(photo_id, [])):
        raise FaceAssignedToOtherPerson()


async def _unlink_references_of_other_models(
    session: AsyncSession, *, person_id: int, model_key: str
) -> None:
    """Leert die Kante der Korrekturen, die auf Referenzen eines fremden Modells zeigen. MUSS vor
    deren Loeschen laufen: Der Fremdschluessel hat keine DB-Aktion, das Loeschen scheiterte sonst.
    Box und Korrektur bleiben - das Gesicht gilt danach als `assigned`."""
    foreign = select(PersonReference.id).where(
        PersonReference.person_id == person_id, PersonReference.model_key != model_key
    )
    await session.execute(
        sql_update(PhotoPersonCorrection)
        .where(PhotoPersonCorrection.reference_id.in_(foreign))
        .values(reference_id=None)
        .execution_options(synchronize_session="fetch")
    )


async def _store_reference(
    session: AsyncSession, *, person_id: int, embedding: tuple[float, ...], model_key: str
) -> PersonReference:
    """DIE EINZIGE Schreibstelle fuer `PersonReference`. Die erste Referenz des aktuellen Modells
    loescht Referenzen anderer `model_key` derselben Person in derselben Transaktion, nachdem die
    Kante ihrer Korrekturen geleert ist."""
    await _unlink_references_of_other_models(session, person_id=person_id, model_key=model_key)
    await session.execute(
        delete(PersonReference).where(
            PersonReference.person_id == person_id, PersonReference.model_key != model_key
        )
    )
    reference = PersonReference(person_id=person_id, embedding=list(embedding), model_key=model_key)
    session.add(reference)
    await session.flush()
    return reference


async def _attach_face(
    session: AsyncSession,
    *,
    photo_id: int,
    person_id: int,
    user_id: int,
    face_box: FaceBox,
    reference_id: int | None,
) -> None:
    """Benennt das Foto per Korrektur und setzt Box und Kante BEDINGT: nur, wenn die Korrektur
    noch keine Box traegt. Trifft das bedingte Setzen keine Zeile, hat inzwischen ein anderer
    Schreiber ein Gesicht dieser Person hier gesetzt - `FaceAlreadyAssignedOnPhoto`, und der
    Rollback des Aufrufers nimmt die neue Referenz mit. Beim Neuanlegen traegt
    `UNIQUE(photo_id, person_id)` denselben Fall als `IntegrityError`."""
    await set_correction(
        session, photo_id=photo_id, person_id=person_id, applies=True, user_id=user_id
    )
    result = await session.execute(
        sql_update(PhotoPersonCorrection)
        .where(
            PhotoPersonCorrection.photo_id == photo_id,
            PhotoPersonCorrection.person_id == person_id,
            PhotoPersonCorrection.face_box_x.is_(None),
        )
        .values(
            face_box_x=face_box.x,
            face_box_y=face_box.y,
            face_box_width=face_box.width,
            face_box_height=face_box.height,
            reference_id=reference_id,
        )
        .execution_options(synchronize_session="fetch")
    )
    if cast(CursorResult[Any], result).rowcount != 1:
        raise FaceAlreadyAssignedOnPhoto()


async def create_person(
    session: AsyncSession,
    *,
    name: str,
    embedding: Sequence[float],
    face_box: FaceBox,
    model_key: str,
    photo_id: int,
    user_id: int,
) -> Person:
    """Legt eine Person NUR zusammen mit ihrer ersten Referenz an und ordnet ihr das gezeigte
    Gesicht (Box) auf dem Foto per Korrektur zu. `name` ist bereits durch `clean_person_name`
    gegangen.

    Die Vorabpruefungen liefern die fachliche Meldung; die Constraints auf `slot` und `name_key`
    tragen den gleichzeitigen Fall und enden beim Flush in einem `IntegrityError`."""
    taken = await _taken_slots(session)
    if len(taken) >= MAX_PERSONS:
        raise PersonLimitReached()
    name_key = person_name_key(name)
    if await _name_taken(session, name_key):
        raise DuplicatePersonName()
    checked = _checked_face(embedding, face_box)
    await _refuse_if_like_the_other(session, checked, person_id=None, model_key=model_key)
    await _refuse_if_face_of_other(session, face_box, photo_id=photo_id, person_id=None)

    slot = min(slot for slot in PERSON_SLOTS if slot not in taken)
    person = Person(slot=slot, name=name, name_key=name_key)
    session.add(person)
    await session.flush()
    reference = await _store_reference(
        session, person_id=person.id, embedding=checked, model_key=model_key
    )
    await _attach_face(
        session,
        photo_id=photo_id,
        person_id=person.id,
        user_id=user_id,
        face_box=face_box,
        reference_id=reference.id,
    )
    return person


async def assign_face(
    session: AsyncSession,
    *,
    person_id: int,
    embedding: Sequence[float],
    face_box: FaceBox,
    model_key: str,
    photo_id: int,
    user_id: int,
) -> bool:
    """Ordnet ein gezeigtes Gesicht einer Person zu und benennt damit das Foto. `True`, wenn
    PhotoSort daraus lernt (neue Referenz); `False` an der Obergrenze von
    `MAX_REFERENCES_PER_PERSON` Referenzen des aktuellen Modells - dann traegt die Korrektur die
    Box ohne Referenz.

    Reihenfolge der Pruefungen: Person vorhanden, schon eine Korrektur-Box dieser Person auf dem
    Foto, Merkmal und Box gueltig, gleicht der anderen Person, Gesicht der anderen Person auf
    diesem Foto, Obergrenze (nur noch benennen). Jede Abweisung schreibt nichts."""
    if await session.get(Person, person_id) is None:
        raise PersonNotFound()
    await refuse_if_face_on_photo(session, photo_id=photo_id, person_id=person_id)
    checked = _checked_face(embedding, face_box)
    await _refuse_if_like_the_other(session, checked, person_id=person_id, model_key=model_key)
    await _refuse_if_face_of_other(session, face_box, photo_id=photo_id, person_id=person_id)
    current = (
        await session.execute(
            select(func.count())
            .select_from(PersonReference)
            .where(PersonReference.person_id == person_id, PersonReference.model_key == model_key)
        )
    ).scalar_one()
    learned = current < MAX_REFERENCES_PER_PERSON
    reference_id: int | None = None
    if learned:
        reference = await _store_reference(
            session, person_id=person_id, embedding=checked, model_key=model_key
        )
        reference_id = reference.id
    await _attach_face(
        session,
        photo_id=photo_id,
        person_id=person_id,
        user_id=user_id,
        face_box=face_box,
        reference_id=reference_id,
    )
    return learned


async def _correction_row(
    session: AsyncSession, *, photo_id: int, person_id: int
) -> PhotoPersonCorrection | None:
    return (
        await session.execute(
            select(PhotoPersonCorrection).where(
                PhotoPersonCorrection.photo_id == photo_id,
                PhotoPersonCorrection.person_id == person_id,
            )
        )
    ).scalar_one_or_none()


async def _delete_reference(session: AsyncSession, reference_id: int) -> None:
    await session.execute(delete(PersonReference).where(PersonReference.id == reference_id))


async def set_correction(
    session: AsyncSession, *, photo_id: int, person_id: int, applies: bool, user_id: int
) -> None:
    """Upsert ueber `(photo_id, person_id)`: die zuletzt geschriebene Korrektur gilt fuer beide
    Nutzer, `user_id` haelt fest, wer zuletzt geschrieben hat. Ein gleichzeitiges erstes
    Schreiben endet beim Flush in einem `IntegrityError`.

    RUECKNAHME: `applies=false` auf einem Paar mit Box leert Box und `reference_id` und loescht
    die verknuepfte Referenz - in DERSELBEN Transaktion, erst die Kante, dann die Referenz. Ein
    gezeigtes Gesicht auf einem Foto, das den Namen nicht mehr traegt, gibt es damit nicht.
    `applies=true` laesst Box und Referenz stehen."""
    existing = await _correction_row(session, photo_id=photo_id, person_id=person_id)
    now = now_utc()
    if existing is None:
        session.add(
            PhotoPersonCorrection(
                photo_id=photo_id,
                person_id=person_id,
                user_id=user_id,
                applies=applies,
                updated_at=now,
            )
        )
        await session.flush()
        return
    revoked: int | None = None
    if not applies and existing.face_box_x is not None:
        revoked = existing.reference_id
        existing.face_box_x = None
        existing.face_box_y = None
        existing.face_box_width = None
        existing.face_box_height = None
        existing.reference_id = None
    existing.applies = applies
    existing.user_id = user_id
    existing.updated_at = now
    await session.flush()
    if revoked is not None:
        await _delete_reference(session, revoked)


# --- Entfernen ---------------------------------------------------------------------------------


async def delete_person(session: AsyncSession, person_id: int) -> bool:
    """Loescht eine Person samt Korrekturen, Erkennungen und Referenzen - Mengenanweisungen in
    Fremdschluessel-Reihenfolge, EINE Transaktion (der Aufrufer committet einmal). `False`, wenn
    es die Person nicht gibt. Danach traegt keine Zeile mehr diese `person_id`."""
    if await session.get(Person, person_id) is None:
        return False
    await session.execute(
        delete(PhotoPersonCorrection).where(PhotoPersonCorrection.person_id == person_id)
    )
    await session.execute(
        delete(PhotoPersonDetection).where(PhotoPersonDetection.person_id == person_id)
    )
    await session.execute(delete(PersonReference).where(PersonReference.person_id == person_id))
    await session.execute(delete(Person).where(Person.id == person_id))
    return True
