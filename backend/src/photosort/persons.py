"""Die beiden benannten Personen: festlegen, gezeigte Gesichter, Korrekturen, entfernen, und die
wirksame Zuordnung.

DIE EINE STELLE fuer die wirksame Zuordnung: `effective_person_assignments()` ist das einzige
SQL-Konstrukt, in dem die Korrekturspalte in die Zuordnung eingeht - Korrektur vor Erkennung.
Filter und Anzeige beziehen sie von hier; ein Quelltext-Waechter in `tests/test_persons.py` haelt
fest, dass keine zweite Fassung entsteht.

DIE EINE SCHREIBSTELLE fuer `PersonReference`: `_store_reference`, erreicht nur ueber
`create_person` und `add_reference` - und damit nur fuer ein ausdruecklich GEZEIGTES Gesicht.
Erkannte Gesichter werden nie von selbst zu Referenzen.

IMPORTREGEL: Dieses Modul importiert direkt keinen Netzwerk-Client.
Schwerpunkte werden je Aufruf frisch aus der Datenbank gebildet und nie darueber hinaus gehalten -
ein Zwischenspeicher erkennte eine entfernte Person weiter, bis der Prozess neu startet.

Kein `commit()` hier: Die Transaktionsgrenze gehoert dem Aufrufer. Eine Person entsteht so nur
zusammen mit ihrer ersten Referenz, und `delete_person` loescht in EINER Transaktion.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import and_, delete, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Subquery

from photosort.clock import now_utc
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


class ReferenceLimitReached(PersonRefusal):
    detail = "Für diese Person sind bereits genug Gesichter gezeigt."


class PersonNotFound(PersonRefusal):
    status_code = 404
    detail = "Person nicht gefunden."


@dataclass(frozen=True)
class PersonAssignment:
    person_id: int
    origin: Origin


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
    """DAS EINE SQL-Konstrukt: `(photo_id, person_id, origin)` je wirksam zugeordnetem Paar.

    Gibt es eine Korrektur, entscheidet sie: `applies=true` ergibt `corrected`, `applies=false`
    nimmt das Paar heraus, auch wenn es erkannt ist. Ohne Korrektur gilt die Erkennung
    (`recognized`). Die Zuordnung wird nie materialisiert."""
    corrected = select(
        PhotoPersonCorrection.photo_id.label("photo_id"),
        PhotoPersonCorrection.person_id.label("person_id"),
        literal("corrected").label("origin"),
    ).where(PhotoPersonCorrection.applies.is_(True))
    recognized = (
        select(
            PhotoPersonDetection.photo_id.label("photo_id"),
            PhotoPersonDetection.person_id.label("person_id"),
            literal("recognized").label("origin"),
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
            select(effective.c.photo_id, effective.c.person_id, effective.c.origin)
            .join(Person, Person.id == effective.c.person_id)
            .where(effective.c.photo_id.in_(ids))
            .order_by(effective.c.photo_id, Person.slot)
        )
    ).all()
    result: dict[int, list[PersonAssignment]] = {}
    for photo_id, person_id, origin in rows:
        result.setdefault(photo_id, []).append(PersonAssignment(person_id=person_id, origin=origin))
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


def _checked_embedding(embedding: Sequence[float]) -> tuple[float, ...]:
    checked = validated_embedding(embedding)
    if checked is None:
        raise InvalidEmbedding()
    return checked


async def _store_reference(
    session: AsyncSession, *, person_id: int, embedding: tuple[float, ...], model_key: str
) -> None:
    """DIE EINZIGE Schreibstelle fuer `PersonReference`. Die erste Referenz des aktuellen Modells
    loescht Referenzen anderer `model_key` derselben Person in derselben Transaktion."""
    await session.execute(
        delete(PersonReference).where(
            PersonReference.person_id == person_id, PersonReference.model_key != model_key
        )
    )
    session.add(
        PersonReference(person_id=person_id, embedding=list(embedding), model_key=model_key)
    )


async def create_person(
    session: AsyncSession,
    *,
    name: str,
    embedding: Sequence[float],
    model_key: str,
    photo_id: int,
    user_id: int,
) -> Person:
    """Legt eine Person NUR zusammen mit ihrer ersten Referenz an und ordnet sie dem Foto per
    Korrektur zu. `name` ist bereits durch `clean_person_name` gegangen.

    Die Vorabpruefungen liefern die fachliche Meldung; die Constraints auf `slot` und `name_key`
    tragen den gleichzeitigen Fall und enden beim Flush in einem `IntegrityError`."""
    taken = await _taken_slots(session)
    if len(taken) >= MAX_PERSONS:
        raise PersonLimitReached()
    name_key = person_name_key(name)
    if await _name_taken(session, name_key):
        raise DuplicatePersonName()
    checked = _checked_embedding(embedding)
    await _refuse_if_like_the_other(session, checked, person_id=None, model_key=model_key)

    slot = min(slot for slot in PERSON_SLOTS if slot not in taken)
    person = Person(slot=slot, name=name, name_key=name_key)
    session.add(person)
    await session.flush()
    await _store_reference(session, person_id=person.id, embedding=checked, model_key=model_key)
    await set_correction(
        session, photo_id=photo_id, person_id=person.id, applies=True, user_id=user_id
    )
    return person


async def add_reference(
    session: AsyncSession,
    *,
    person_id: int,
    embedding: Sequence[float],
    model_key: str,
    photo_id: int,
    user_id: int,
) -> None:
    """Ein weiteres gezeigtes Gesicht einer Person - und zugleich ihre Zuordnung zu diesem Foto.
    Hoechstens `MAX_REFERENCES_PER_PERSON` Referenzen des aktuellen Modells, gleich wie viele
    eines fremden Modells noch stehen."""
    if await session.get(Person, person_id) is None:
        raise PersonNotFound()
    checked = _checked_embedding(embedding)
    await _refuse_if_like_the_other(session, checked, person_id=person_id, model_key=model_key)
    current = (
        await session.execute(
            select(func.count())
            .select_from(PersonReference)
            .where(PersonReference.person_id == person_id, PersonReference.model_key == model_key)
        )
    ).scalar_one()
    if current >= MAX_REFERENCES_PER_PERSON:
        raise ReferenceLimitReached()
    await _store_reference(session, person_id=person_id, embedding=checked, model_key=model_key)
    await set_correction(
        session, photo_id=photo_id, person_id=person_id, applies=True, user_id=user_id
    )


async def set_correction(
    session: AsyncSession, *, photo_id: int, person_id: int, applies: bool, user_id: int
) -> None:
    """Upsert ueber `(photo_id, person_id)`: die zuletzt geschriebene Korrektur gilt fuer beide
    Nutzer, `user_id` haelt fest, wer zuletzt geschrieben hat. Ein gleichzeitiges erstes
    Schreiben endet beim Flush in einem `IntegrityError`."""
    existing = (
        await session.execute(
            select(PhotoPersonCorrection).where(
                PhotoPersonCorrection.photo_id == photo_id,
                PhotoPersonCorrection.person_id == person_id,
            )
        )
    ).scalar_one_or_none()
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
    else:
        existing.applies = applies
        existing.user_id = user_id
        existing.updated_at = now
    await session.flush()


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
