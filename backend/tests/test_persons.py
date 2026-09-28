"""Die wirksame Zuordnung, das Festlegen und das Entfernen von Personen.

Die Merkmale der Lagen sind Basisvektoren fern jeder Schwelle (Kosinus exakt 1 oder 0) - eine
Kalibrierung der Konstanten in `person_matching.py` roetet hier nichts.
"""

from __future__ import annotations

import ast
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import persons as persons_module
from photosort.face_analysis import FaceBox
from photosort.models import (
    Person,
    PersonReference,
    Photo,
    PhotoPersonCorrection,
    PhotoPersonDetection,
    Project,
    User,
)
from photosort.person_matching import EMBEDDING_DIMENSION, MAX_REFERENCES_PER_PERSON
from photosort.persons import (
    DuplicatePersonName,
    FaceAlreadyAssignedOnPhoto,
    FaceAssignedToOtherPerson,
    InvalidEmbedding,
    InvalidPersonName,
    PersonAssignment,
    PersonLimitReached,
    PersonNotFound,
    ResemblesOtherPerson,
    assign_face,
    assigned_face_boxes,
    clean_person_name,
    create_person,
    current_centroids,
    delete_person,
    list_persons,
    load_effective_persons,
    person_name_key,
    set_correction,
)
from tests.import_closure import SRC_DIR

MODEL = "aktuelles-modell"
OLD_MODEL = "altes-modell"
NOW = datetime(2026, 9, 27, 12, 0, 0)


def _basis(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[index] = 1.0
    return vector


def _box(index: int) -> FaceBox:
    """Je Index eine eigene, dyadische Box - disjunkt zu jeder anderen."""
    return FaceBox(x=0.0625 * index, y=0.25, width=0.0625, height=0.25)


async def _user(session: AsyncSession, name: str = "daniel") -> User:
    user = User(username=name, password_hash="hashed-value")
    session.add(user)
    await session.flush()
    return user


async def _photos(session: AsyncSession, count: int, *, name: str = "Reise") -> list[Photo]:
    project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
    session.add(project)
    await session.flush()
    photos = [
        Photo(
            project_id=project.id,
            relative_path=f"{name}/{index}.jpg",
            etag=f"{name}-{index}",
            content_length=1,
            taken_at=NOW,
            taken_at_original=NOW,
            last_modified=NOW,
        )
        for index in range(count)
    ]
    session.add_all(photos)
    await session.flush()
    return photos


async def _person(
    session: AsyncSession,
    name: str,
    photo: Photo,
    user: User,
    *,
    index: int,
    box: FaceBox | None = None,
) -> Person:
    return await create_person(
        session,
        name=name,
        embedding=_basis(index),
        face_box=_box(index) if box is None else box,
        model_key=MODEL,
        photo_id=photo.id,
        user_id=user.id,
    )


async def _assign(
    session: AsyncSession,
    person: Person,
    photo: Photo,
    user: User,
    *,
    axis: int,
    box: FaceBox | None = None,
    model_key: str = MODEL,
) -> bool:
    return await assign_face(
        session,
        person_id=person.id,
        embedding=_basis(axis),
        face_box=_box(axis) if box is None else box,
        model_key=model_key,
        photo_id=photo.id,
        user_id=user.id,
    )


async def _rows_with_person(session: AsyncSession, person_id: int) -> dict[str, int]:
    return {
        model.__tablename__: (
            await session.execute(
                select(func.count()).select_from(model).where(model.person_id == person_id)
            )
        ).scalar_one()
        for model in (PersonReference, PhotoPersonDetection, PhotoPersonCorrection)
    }


async def _snapshot(session: AsyncSession) -> dict[str, list[tuple[Any, ...]]]:
    """Die drei Personentabellen Zeile fuer Zeile - fuer "nach einer Abweisung ist nichts
    geschrieben"."""
    result: dict[str, list[tuple[Any, ...]]] = {}
    for model in (PersonReference, PhotoPersonDetection, PhotoPersonCorrection):
        rows = (await session.execute(select(model.__table__))).all()
        result[model.__tablename__] = sorted(tuple(row) for row in rows)
    return result


async def _correction(session: AsyncSession, photo: Photo, person: Person) -> Any:
    return (
        await session.execute(
            select(
                PhotoPersonCorrection.applies,
                PhotoPersonCorrection.face_box_x,
                PhotoPersonCorrection.face_box_y,
                PhotoPersonCorrection.face_box_width,
                PhotoPersonCorrection.face_box_height,
                PhotoPersonCorrection.reference_id,
            ).where(
                PhotoPersonCorrection.photo_id == photo.id,
                PhotoPersonCorrection.person_id == person.id,
            )
        )
    ).one_or_none()


async def _reference_count(session: AsyncSession, person: Person) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(PersonReference)
            .where(PersonReference.person_id == person.id)
        )
    ).scalar_one()


def _detection(photo: Photo, person: Person, box: FaceBox | None = None) -> PhotoPersonDetection:
    return PhotoPersonDetection(
        photo_id=photo.id,
        person_id=person.id,
        computed_at=NOW,
        face_box_x=None if box is None else box.x,
        face_box_y=None if box is None else box.y,
        face_box_width=None if box is None else box.width,
        face_box_height=None if box is None else box.height,
    )


class TestTheName:
    @pytest.mark.parametrize(
        "raw",
        [
            "Anna\u202eX",
            "An\u200bna",
            "An\u0000na",
            "Anna\u2028",
            "An\tna",
            "An\u0007na",
            "An\u00adna",
            "Anna\u2029",
            "An\ue000na",
            "An\u0378na",
            "An\u00a0na",
            "",
            "   ",
            "x" * 41,
        ],
        ids=[
            "U+202E",
            "U+200B",
            "U+0000",
            "U+2028",
            "tab",
            "Cc",
            "Cf",
            "Zp",
            "Co",
            "Cn",
            "nbsp",
            "leer",
            "nur-leerraum",
            "41",
        ],
    )
    def test_a_forbidden_name_is_refused_not_cleaned(self, raw: str) -> None:
        with pytest.raises(InvalidPersonName):
            clean_person_name(raw)

    def test_forty_code_points_after_nfc_are_allowed(self) -> None:
        decomposed = "e\u0301" * 40

        assert clean_person_name(decomposed) == "\u00e9" * 40

    def test_the_name_is_trimmed_and_normalised(self) -> None:
        assert clean_person_name("  Rene\u0301 Muster  ") == "René Muster"

    @pytest.mark.parametrize(
        ("first", "second"),
        [("Anna", "ANNA"), ("Straße", "STRASSE"), ("\u00e9", "e\u0301")],
    )
    def test_the_key_folds_case_and_composition(self, first: str, second: str) -> None:
        assert person_name_key(clean_person_name(first)) == person_name_key(
            clean_person_name(second)
        )


def _functions_naming(model: str, prefix: str) -> set[tuple[str, str]]:
    """Je Quelldatei die Funktionen, die ein Klassenattribut `model.<prefix>...` nennen."""
    found: set[tuple[str, str]] = set()
    for path in SRC_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == model
                    and node.attr.startswith(prefix)
                ):
                    found.add((path.name, function.name))
    return found


def _reference_id_writes() -> dict[str, list[tuple[str, str]]]:
    """Jede Stelle, die `reference_id` schreibt - als Schluesselwort (`.values(...)`, Konstruktor)
    oder als Attributzuweisung -, getrennt nach "setzt" und "leert" (Wert `None`)."""
    writes: dict[str, list[tuple[str, str]]] = {"set": [], "clear": []}
    for path in SRC_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(function):
                values: list[ast.expr] = []
                if isinstance(node, ast.Call) and (
                    (isinstance(node.func, ast.Attribute) and node.func.attr == "values")
                    or (isinstance(node.func, ast.Name) and node.func.id == "PhotoPersonCorrection")
                ):
                    values.extend(
                        keyword.value for keyword in node.keywords if keyword.arg == "reference_id"
                    )
                if isinstance(node, ast.Assign):
                    values.extend(
                        node.value
                        for target in node.targets
                        if isinstance(target, ast.Attribute) and target.attr == "reference_id"
                    )
                for value in values:
                    kind = (
                        "clear"
                        if isinstance(value, ast.Constant) and value.value is None
                        else "set"
                    )
                    writes[kind].append((path.name, function.name))
    return writes


class TestTheEffectiveAssignment:
    @pytest.mark.parametrize(
        ("detected", "correction", "expected"),
        [
            (False, None, None),
            (False, True, "corrected"),
            (False, False, None),
            (True, None, "recognized"),
            (True, True, "corrected"),
            (True, False, None),
        ],
    )
    async def test_the_matrix_of_detection_and_correction(
        self,
        db_session: AsyncSession,
        detected: bool,
        correction: bool | None,
        expected: str | None,
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        person = await _person(db_session, "Anna", anchor, user, index=0)
        if detected:
            db_session.add(_detection(photo, person, _box(3)))
        if correction is not None:
            await set_correction(
                db_session,
                photo_id=photo.id,
                person_id=person.id,
                applies=correction,
                user_id=user.id,
            )
        await db_session.flush()

        effective = await load_effective_persons(db_session, [photo.id])

        if expected is None:
            assert effective.get(photo.id, []) == []
        else:
            # Im Erkennungszweig ist `face` immer `None`, auch bei einer Erkennung mit Box.
            assert effective[photo.id] == [
                PersonAssignment(person_id=person.id, origin=expected, face=None)
            ]

    async def test_the_face_of_a_correction_is_shown_assigned_or_none(
        self, db_session: AsyncSession
    ) -> None:
        """`shown`: Box und Referenz. `assigned`: Box ohne Referenz (Obergrenze, Modellwechsel).
        `None`: Name nur fuer das ganze Foto."""
        user = await _user(db_session)
        [shown, assigned, whole] = await _photos(db_session, 3)
        anna = await _person(db_session, "Anna", shown, user, index=0)
        await set_correction(
            db_session, photo_id=whole.id, person_id=anna.id, applies=True, user_id=user.id
        )
        await _assign(db_session, anna, assigned, user, axis=0)
        table = PhotoPersonCorrection.__table__
        await db_session.execute(
            table.update().where(table.c.photo_id == assigned.id).values(reference_id=None)
        )

        effective = await load_effective_persons(db_session, [shown.id, assigned.id, whole.id])

        assert [effective[photo.id][0].face for photo in (shown, assigned, whole)] == [
            "shown",
            "assigned",
            None,
        ]
        assert {effective[photo.id][0].origin for photo in (shown, assigned, whole)} == {
            "corrected"
        }

    async def test_both_persons_are_listed_by_slot(self, db_session: AsyncSession) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        berta = await _person(db_session, "Berta", anchor, user, index=1)
        db_session.add_all([_detection(photo, berta), _detection(photo, anna)])
        await db_session.flush()

        effective = await load_effective_persons(db_session, [photo.id])

        assert [entry.person_id for entry in effective[photo.id]] == [anna.id, berta.id]

    def test_the_correction_column_is_named_by_exactly_two_functions(self) -> None:
        """Die wirksame Zuordnung je Foto entsteht in GENAU EINEM SQL-Konstrukt, die Regel
        "welches Gesicht gilt als zugeordnet" in genau einer Funktion. Das Messkommando zaehlt
        bewusst die rohe Spur (Korrektur gegen Erkennung) und ist deshalb ausgenommen."""
        naming = {
            entry
            for entry in _functions_naming("PhotoPersonCorrection", "applies")
            if entry[0] != "person_probe.py"
        }

        assert naming == {
            ("persons.py", "effective_person_assignments"),
            ("persons.py", "assigned_face_boxes"),
        }

    def test_the_box_columns_are_read_at_exactly_one_place_plus_face(self) -> None:
        """Die Box-Spalten beider Tabellen liest im Lesepfad nur `assigned_face_boxes`;
        `effective_person_assignments` ist die benannte Ausnahme fuer `face`. Dazu kommen die
        beiden Stellen des Schreibwegs: die Vorpruefung "schon ein Gesicht dieser Person" und das
        bedingte Setzen der Box."""
        naming = _functions_naming("PhotoPersonCorrection", "face_box_") | _functions_naming(
            "PhotoPersonDetection", "face_box_"
        )

        assert naming == {
            ("persons.py", "assigned_face_boxes"),
            ("persons.py", "effective_person_assignments"),
            ("persons.py", "_has_correction_face"),
            ("persons.py", "_attach_face"),
        }


_CORRECTION_STATES = ["keine", "applies-false", "applies-true", "applies-true-box"]
_DETECTION_STATES = ["keine", "ohne-box", "mit-box"]


class TestAssignedFaceBoxes:
    """ADR 0127 Punkt 3 als Wahrheitstabelle je Paar (Foto, Person)."""

    @pytest.mark.parametrize("detection", _DETECTION_STATES)
    @pytest.mark.parametrize("correction", _CORRECTION_STATES)
    async def test_the_first_matching_rule_decides(
        self, db_session: AsyncSession, correction: str, detection: str
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        if detection != "keine":
            db_session.add(_detection(photo, anna, _box(3) if detection == "mit-box" else None))
        if correction == "applies-true-box":
            await _assign(db_session, anna, photo, user, axis=0, box=_box(5))
        elif correction != "keine":
            await set_correction(
                db_session,
                photo_id=photo.id,
                person_id=anna.id,
                applies=correction == "applies-true",
                user_id=user.id,
            )
        await db_session.flush()

        boxes = await assigned_face_boxes(db_session, [photo.id])

        if correction == "applies-false":
            expected = []
        elif correction == "applies-true-box":
            expected = [_box(5)]
        elif detection == "mit-box":
            expected = [_box(3)]
        else:
            expected = []
        assert boxes.get(photo.id, []) == expected

    async def test_a_revoked_name_hides_a_recognised_box(self, db_session: AsyncSession) -> None:
        """Pflichtfall 1: Korrektur `applies=false` plus Erkennung mit Box ergibt kein Gesicht."""
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        db_session.add(_detection(photo, anna, _box(3)))
        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
        )

        assert await assigned_face_boxes(db_session, [photo.id]) == {}

    async def test_the_box_of_the_correction_beats_another_recognised_box(
        self, db_session: AsyncSession
    ) -> None:
        """Pflichtfall 2: Korrektur mit Box plus Erkennung mit ANDERER Box."""
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        db_session.add(_detection(photo, anna, _box(3)))
        await _assign(db_session, anna, photo, user, axis=0, box=_box(6))

        assert await assigned_face_boxes(db_session, [photo.id]) == {photo.id: [_box(6)]}

    async def test_two_persons_give_two_boxes_and_other_photos_are_left_out(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo, outside] = await _photos(db_session, 3)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        berta = await _person(db_session, "Berta", anchor, user, index=1)
        db_session.add_all(
            [
                _detection(photo, anna, _box(2)),
                _detection(photo, berta, _box(4)),
                _detection(outside, anna, _box(2)),
            ]
        )
        await db_session.flush()

        boxes = await assigned_face_boxes(db_session, [photo.id])

        assert set(boxes) == {photo.id}
        assert sorted(boxes[photo.id], key=lambda box: box.x) == [_box(2), _box(4)]
        assert await assigned_face_boxes(db_session, [photo.id], excluding_person_id=anna.id) == {
            photo.id: [_box(4)]
        }


class TestCreatingPersons:
    async def test_a_person_arises_only_with_its_first_reference_and_correction(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)

        person = await _person(db_session, "Anna", photo, user, index=0)

        assert person.slot == 1
        assert person.name_key == "anna"
        assert await _rows_with_person(db_session, person.id) == {
            "person_references": 1,
            "photo_person_detections": 0,
            "photo_person_corrections": 1,
        }
        effective = await load_effective_persons(db_session, [photo.id])
        assert effective[photo.id] == [
            PersonAssignment(person_id=person.id, origin="corrected", face="shown")
        ]
        [reference_id] = (await db_session.execute(select(PersonReference.id))).scalars().all()
        assert tuple(await _correction(db_session, photo, person)) == (
            True,
            _box(0).x,
            _box(0).y,
            _box(0).width,
            _box(0).height,
            reference_id,
        )

    async def test_a_third_person_is_refused(self, db_session: AsyncSession) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        await _person(db_session, "Anna", photo, user, index=0)
        await _person(db_session, "Berta", photo, user, index=1)

        with pytest.raises(PersonLimitReached):
            await _person(db_session, "Clara", photo, user, index=2)

    async def test_after_removing_a_person_a_slot_is_free_again(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        await _person(db_session, "Berta", photo, user, index=1)
        await delete_person(db_session, anna.id)

        clara = await _person(db_session, "Clara", photo, user, index=2)

        assert clara.slot == 1

    async def test_a_duplicate_name_is_refused(self, db_session: AsyncSession) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        await _person(db_session, "Straße", photo, user, index=0)

        with pytest.raises(DuplicatePersonName):
            await _person(db_session, "STRASSE", photo, user, index=1)

    @pytest.mark.parametrize(
        ("embedding", "box"),
        [
            ([float("nan")] + [0.0] * (EMBEDDING_DIMENSION - 1), _box(0)),
            ([float("inf")] + [0.0] * (EMBEDDING_DIMENSION - 1), _box(0)),
            ([0.0] * EMBEDDING_DIMENSION, _box(0)),
            (_basis(0), FaceBox(x=float("nan"), y=0.25, width=0.25, height=0.25)),
            (_basis(0), FaceBox(x=0.25, y=0.25, width=float("inf"), height=0.25)),
            (_basis(0), FaceBox(x=0.25, y=0.25, width=0.0, height=0.25)),
            (_basis(0), FaceBox(x=1.0 + 2**-20, y=0.25, width=0.25, height=0.25)),
        ],
        ids=["nan", "inf", "nullvektor", "box-nan", "box-inf", "box-breite-null", "box-x-ueber"],
    )
    async def test_a_broken_embedding_or_box_writes_nothing(
        self, db_session: AsyncSession, embedding: list[float], box: FaceBox
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)

        with pytest.raises(InvalidEmbedding):
            await create_person(
                db_session,
                name="Anna",
                embedding=embedding,
                face_box=box,
                model_key=MODEL,
                photo_id=photo.id,
                user_id=user.id,
            )

        assert (await db_session.execute(select(Person))).scalars().all() == []
        assert (await db_session.execute(select(PersonReference))).scalars().all() == []

    async def test_a_face_resembling_the_other_person_is_refused(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        await _person(db_session, "Anna", photo, user, index=0)

        with pytest.raises(ResemblesOtherPerson):
            await _person(db_session, "Berta", photo, user, index=0, box=_box(1))

        assert len((await db_session.execute(select(Person))).scalars().all()) == 1

    async def test_the_face_of_the_other_person_on_this_photo_is_refused(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        await _person(db_session, "Anna", photo, user, index=0)
        before = await _snapshot(db_session)

        with pytest.raises(FaceAssignedToOtherPerson):
            await _person(db_session, "Berta", photo, user, index=1, box=_box(0))

        assert len((await db_session.execute(select(Person))).scalars().all()) == 1
        assert await _snapshot(db_session) == before


class TestAssigningFaces:
    async def test_a_shown_face_names_the_photo_and_is_learned(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)

        learned = await _assign(db_session, anna, photo, user, axis=0, box=_box(7))

        assert learned is True
        effective = await load_effective_persons(db_session, [photo.id])
        assert effective[photo.id] == [
            PersonAssignment(person_id=anna.id, origin="corrected", face="shown")
        ]
        row = await _correction(db_session, photo, anna)
        assert (row.face_box_x, row.reference_id is not None) == (_box(7).x, True)
        assert await _reference_count(db_session, anna) == 2

    async def test_an_unknown_person_is_refused_first(self, db_session: AsyncSession) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)

        with pytest.raises(PersonNotFound):
            await assign_face(
                db_session,
                person_id=4711,
                embedding=[float("nan")] * EMBEDDING_DIMENSION,
                face_box=_box(0),
                model_key=MODEL,
                photo_id=photo.id,
                user_id=user.id,
            )

    async def test_a_second_correction_face_of_the_person_is_refused_before_the_embedding(
        self, db_session: AsyncSession
    ) -> None:
        """Die Vorpruefung liegt vor der Merkmalspruefung: Scheitern beide, gewinnt sie."""
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        before = await _snapshot(db_session)

        with pytest.raises(FaceAlreadyAssignedOnPhoto):
            await assign_face(
                db_session,
                person_id=anna.id,
                embedding=[float("nan")] * EMBEDDING_DIMENSION,
                face_box=_box(4),
                model_key=MODEL,
                photo_id=photo.id,
                user_id=user.id,
            )

        assert await _snapshot(db_session) == before

    async def test_resembling_the_other_person_wins_over_the_face_of_the_other_person(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        berta = await _person(db_session, "Berta", photo, user, index=1)
        before = await _snapshot(db_session)

        with pytest.raises(ResemblesOtherPerson):
            await _assign(db_session, anna, photo, user, axis=1, box=_box(1))
        with pytest.raises(FaceAssignedToOtherPerson):
            await _assign(db_session, anna, photo, user, axis=0, box=_box(1))

        assert await _snapshot(db_session) == before
        assert berta.id != anna.id

    async def test_at_the_cap_a_look_alike_and_the_face_of_the_other_are_still_refused(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        photos = await _photos(db_session, MAX_REFERENCES_PER_PERSON + 1)
        anna = await _person(db_session, "Anna", photos[0], user, index=0)
        await _person(db_session, "Berta", photos[-1], user, index=1)
        for photo in photos[1:MAX_REFERENCES_PER_PERSON]:
            await _assign(db_session, anna, photo, user, axis=0)
        assert await _reference_count(db_session, anna) == MAX_REFERENCES_PER_PERSON
        before = await _snapshot(db_session)

        with pytest.raises(ResemblesOtherPerson):
            await _assign(db_session, anna, photos[-1], user, axis=1, box=_box(9))
        with pytest.raises(FaceAssignedToOtherPerson):
            await _assign(db_session, anna, photos[-1], user, axis=0, box=_box(1))

        assert await _snapshot(db_session) == before


class TestTheScopeOfTheNewRefusals:
    async def test_a_recognised_box_of_the_same_person_does_not_block(
        self, db_session: AsyncSession
    ) -> None:
        """Ein erkanntes Gesicht ausdruecklich zu zeigen ist Anlernen; ein ANDERES Gesicht zu
        zeigen macht das erkannte wieder frei (Regel 2 vor Regel 3)."""
        user = await _user(db_session)
        [anchor, same, other] = await _photos(db_session, 3)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        db_session.add_all([_detection(same, anna, _box(3)), _detection(other, anna, _box(3))])
        await db_session.flush()

        assert await _assign(db_session, anna, same, user, axis=0, box=_box(3)) is True
        assert await _assign(db_session, anna, other, user, axis=0, box=_box(6)) is True

        boxes = await assigned_face_boxes(db_session, [same.id, other.id])
        assert boxes == {same.id: [_box(3)], other.id: [_box(6)]}

    async def test_the_recognised_box_of_the_other_person_blocks_until_her_name_is_removed(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        berta = await _person(db_session, "Berta", anchor, user, index=1)
        db_session.add(_detection(photo, anna, _box(3)))
        await db_session.flush()

        with pytest.raises(FaceAssignedToOtherPerson):
            await _assign(db_session, berta, photo, user, axis=1, box=_box(3))
        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
        )

        assert await _assign(db_session, berta, photo, user, axis=1, box=_box(3)) is True

    async def test_a_whole_photo_name_of_the_other_person_blocks_nothing(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        berta = await _person(db_session, "Berta", anchor, user, index=1)
        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=True, user_id=user.id
        )

        assert await _assign(db_session, berta, photo, user, axis=1, box=_box(3)) is True


class TestTheConditionalBox:
    """Die zweite Linie hinter der Schreibsperre, mit umgangener Vorpruefung."""

    async def test_an_existing_correction_box_makes_the_update_miss_and_refuses(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        await _assign(db_session, anna, photo, user, axis=0, box=_box(2))
        await db_session.commit()
        before = await _snapshot(db_session)

        async def _never(session: AsyncSession, *, photo_id: int, person_id: int) -> bool:
            return False

        monkeypatch.setattr(persons_module, "_has_correction_face", _never)
        with pytest.raises(FaceAlreadyAssignedOnPhoto):
            await _assign(db_session, anna, photo, user, axis=0, box=_box(5))
        await db_session.rollback()

        assert await _snapshot(db_session) == before

    async def test_a_correction_arising_meanwhile_hits_the_unique_constraint(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=True, user_id=user.id
        )
        await db_session.commit()
        before = await _snapshot(db_session)

        async def _unseen(session: AsyncSession, *, photo_id: int, person_id: int) -> None:
            return None

        monkeypatch.setattr(persons_module, "_correction_row", _unseen)
        with pytest.raises(IntegrityError):
            await _assign(db_session, anna, photo, user, axis=0, box=_box(5))
        await db_session.rollback()

        assert await _snapshot(db_session) == before

    @pytest.mark.parametrize("applies", [True, False], ids=["ganzes-foto", "entfernt"])
    async def test_a_correction_without_box_takes_the_box(
        self, db_session: AsyncSession, applies: bool
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=applies, user_id=user.id
        )

        assert await _assign(db_session, anna, photo, user, axis=0, box=_box(5)) is True

        row = await _correction(db_session, photo, anna)
        assert (row.applies, row.face_box_x, row.reference_id is not None) == (
            True,
            _box(5).x,
            True,
        )


class TestTheCap:
    async def test_the_twentieth_is_learned_the_twenty_first_only_names(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        photos = await _photos(db_session, MAX_REFERENCES_PER_PERSON + 1)
        anna = await _person(db_session, "Anna", photos[0], user, index=0)
        learned = [
            await _assign(db_session, anna, photo, user, axis=0)
            for photo in photos[1:MAX_REFERENCES_PER_PERSON]
        ]
        assert learned == [True] * (MAX_REFERENCES_PER_PERSON - 1)

        assert await _assign(db_session, anna, photos[-1], user, axis=0) is False

        [summary] = await list_persons(db_session, model_key=MODEL)
        assert summary.reference_count == MAX_REFERENCES_PER_PERSON
        row = await _correction(db_session, photos[-1], anna)
        assert (row.applies, row.face_box_x, row.reference_id) == (True, _box(0).x, None)
        effective = await load_effective_persons(db_session, [photos[-1].id])
        assert effective[photos[-1].id][0].face == "assigned"

    async def test_references_of_another_model_do_not_count(self, db_session: AsyncSession) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        db_session.add_all(
            PersonReference(person_id=anna.id, embedding=_basis(0), model_key=OLD_MODEL)
            for _ in range(MAX_REFERENCES_PER_PERSON)
        )
        await db_session.flush()

        assert await _assign(db_session, anna, photo, user, axis=0) is True

    async def test_after_a_revocation_the_next_face_is_learned_again(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        photos = await _photos(db_session, MAX_REFERENCES_PER_PERSON + 1)
        anna = await _person(db_session, "Anna", photos[0], user, index=0)
        for photo in photos[1:MAX_REFERENCES_PER_PERSON]:
            await _assign(db_session, anna, photo, user, axis=0)
        await set_correction(
            db_session, photo_id=photos[1].id, person_id=anna.id, applies=False, user_id=user.id
        )
        assert await _reference_count(db_session, anna) == MAX_REFERENCES_PER_PERSON - 1

        assert await _assign(db_session, anna, photos[-1], user, axis=0) is True


class TestTheRevocation:
    async def test_removing_a_shown_face_deletes_exactly_its_reference(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo, other] = await _photos(db_session, 3)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        berta = await _person(db_session, "Berta", other, user, index=1)
        await _assign(db_session, anna, photo, user, axis=0)
        linked = (await _correction(db_session, photo, anna)).reference_id
        berta_before = await _rows_with_person(db_session, berta.id)

        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
        )

        assert await db_session.get(PersonReference, linked) is None
        assert tuple(await _correction(db_session, photo, anna)) == (
            False,
            None,
            None,
            None,
            None,
            None,
        )
        assert await _reference_count(db_session, anna) == 1
        assert await _rows_with_person(db_session, berta.id) == berta_before
        assert await current_centroids(db_session, model_key=MODEL) == {
            anna.id: tuple(_basis(0)),
            berta.id: tuple(_basis(1)),
        }

    async def test_removing_a_face_without_reference_deletes_none(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        await _assign(db_session, anna, photo, user, axis=0)
        table = PhotoPersonCorrection.__table__
        await db_session.execute(
            table.update().where(table.c.photo_id == photo.id).values(reference_id=None)
        )
        before = await _reference_count(db_session, anna)

        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
        )

        assert (await _correction(db_session, photo, anna)).face_box_x is None
        assert await _reference_count(db_session, anna) == before

    @pytest.mark.parametrize("state", ["nur-erkennung", "korrektur-ohne-box"])
    async def test_removing_a_name_without_a_chosen_face_deletes_no_reference(
        self, db_session: AsyncSession, state: str
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        if state == "nur-erkennung":
            db_session.add(_detection(photo, anna, _box(3)))
            await db_session.flush()
        else:
            await set_correction(
                db_session, photo_id=photo.id, person_id=anna.id, applies=True, user_id=user.id
            )

        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
        )

        assert await _reference_count(db_session, anna) == 1

    async def test_twice_false_changes_nothing_the_second_time(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        await _assign(db_session, anna, photo, user, axis=0)
        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
        )
        before = await _snapshot(db_session)

        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
        )

        after = await _snapshot(db_session)
        assert after["person_references"] == before["person_references"]
        assert tuple(await _correction(db_session, photo, anna)) == (
            False,
            None,
            None,
            None,
            None,
            None,
        )

    async def test_true_on_a_shown_face_keeps_box_and_reference(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        await _assign(db_session, anna, photo, user, axis=0)
        before = tuple(await _correction(db_session, photo, anna))

        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=True, user_id=user.id
        )

        assert tuple(await _correction(db_session, photo, anna)) == before

    async def test_true_after_a_revocation_names_the_whole_photo_without_a_box(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        await _assign(db_session, anna, photo, user, axis=0)
        for applies in (False, True):
            await set_correction(
                db_session, photo_id=photo.id, person_id=anna.id, applies=applies, user_id=user.id
            )

        effective = await load_effective_persons(db_session, [photo.id])
        assert effective[photo.id] == [
            PersonAssignment(person_id=anna.id, origin="corrected", face=None)
        ]
        assert await assigned_face_boxes(db_session, [photo.id]) == {}

    async def test_ten_rounds_of_assigning_and_revoking_leave_no_extra_reference(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)

        for _ in range(10):
            await _assign(db_session, anna, photo, user, axis=0)
            await set_correction(
                db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
            )

        assert await _reference_count(db_session, anna) == 1

    async def test_a_failing_reference_delete_leaves_the_correction_unchanged(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        await _assign(db_session, anna, photo, user, axis=0)
        await db_session.commit()
        before = await _snapshot(db_session)

        async def _boom(session: AsyncSession, reference_id: int) -> None:
            raise RuntimeError("simuliert")

        monkeypatch.setattr(persons_module, "_delete_reference", _boom)
        with pytest.raises(RuntimeError):
            await set_correction(
                db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
            )
        await db_session.rollback()

        assert await _snapshot(db_session) == before

    async def test_a_linked_reference_cannot_be_deleted_behind_the_correction(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        await _person(db_session, "Anna", photo, user, index=0)
        await db_session.commit()

        with pytest.raises(IntegrityError):
            await db_session.execute(PersonReference.__table__.delete())
        await db_session.rollback()

    async def test_a_reference_shown_before_this_story_survives_every_removal(
        self, db_session: AsyncSession
    ) -> None:
        """Eine Referenz ohne verknuepfte Korrektur ist keinem Foto zuzuordnen: Sie uebersteht
        `applies=false` auf jedem Foto der Person und faellt erst mit der Person."""
        user = await _user(db_session)
        photos = await _photos(db_session, 3)
        anna = await _person(db_session, "Anna", photos[0], user, index=0)
        db_session.add(PersonReference(person_id=anna.id, embedding=_basis(0), model_key=MODEL))
        await db_session.flush()

        for photo in photos:
            await set_correction(
                db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=user.id
            )

        assert await _reference_count(db_session, anna) == 1
        await delete_person(db_session, anna.id)
        assert await _reference_count(db_session, anna) == 0


class TestAModelChange:
    async def _lay_old_model(self, session: AsyncSession) -> tuple[User, list[Photo], Person]:
        """Zwei Korrekturen zeigen auf Referenzen des alten Modells, dazu 19 Referenzen ohne
        Korrektur - Fremdschluessel durchgesetzt."""
        user = await _user(session)
        photos = await _photos(session, 3)
        anna = await _person(session, "Anna", photos[0], user, index=0)
        await _assign(session, anna, photos[1], user, axis=0)
        await session.execute(PersonReference.__table__.update().values(model_key=OLD_MODEL))
        session.add_all(
            PersonReference(person_id=anna.id, embedding=_basis(0), model_key=OLD_MODEL)
            for _ in range(MAX_REFERENCES_PER_PERSON - 1)
        )
        await session.flush()
        return user, photos, anna

    async def test_the_old_references_go_and_their_corrections_keep_the_box(
        self, db_session: AsyncSession
    ) -> None:
        user, photos, anna = await self._lay_old_model(db_session)
        [before] = await list_persons(db_session, model_key=MODEL)
        assert before.reference_count == 0
        assert await current_centroids(db_session, model_key=MODEL) == {}

        assert await _assign(db_session, anna, photos[2], user, axis=0) is True

        keys = (await db_session.execute(select(PersonReference.model_key))).scalars().all()
        assert keys == [MODEL]
        effective = await load_effective_persons(db_session, [photo.id for photo in photos])
        assert [effective[photo.id][0].face for photo in photos] == [
            "assigned",
            "assigned",
            "shown",
        ]
        assert (await _correction(db_session, photos[0], anna)).face_box_x == _box(0).x

    async def test_without_unlinking_the_old_references_hit_the_foreign_key(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gegenprobe: Der Fall erreicht den Fremdschluessel wirklich."""
        user, photos, anna = await self._lay_old_model(db_session)

        async def _skip(session: AsyncSession, *, person_id: int, model_key: str) -> None:
            return None

        monkeypatch.setattr(persons_module, "_unlink_references_of_other_models", _skip)

        with pytest.raises(IntegrityError):
            await _assign(db_session, anna, photos[2], user, axis=0)
        await db_session.rollback()


class TestTheWritePlaces:
    def test_a_reference_is_written_at_exactly_one_place(self) -> None:
        """S5: `PersonReference` entsteht nur in `persons.py` - und dort nur einmal."""
        constructing: list[str] = []
        for path in SRC_DIR.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "PersonReference"
                ):
                    constructing.append(path.name)

        assert constructing == ["persons.py"]

    def test_the_reference_edge_is_set_once_and_cleared_twice(self) -> None:
        """Gesetzt beim Zuordnen, geleert bei Ruecknahme und Modellwechsel - sonst nirgends."""
        writes = _reference_id_writes()

        assert writes["set"] == [("persons.py", "_attach_face")]
        assert sorted(writes["clear"]) == [
            ("persons.py", "_unlink_references_of_other_models"),
            ("persons.py", "set_correction"),
        ]


class TestCorrections:
    @pytest.mark.parametrize("order", ["erst-daniel", "erst-partnerin"])
    async def test_two_users_share_one_row_and_the_last_wins(
        self, db_session: AsyncSession, order: str
    ) -> None:
        daniel = await _user(db_session, "daniel")
        partner = await _user(db_session, "partnerin")
        [photo] = await _photos(db_session, 1)
        anna = await _person(db_session, "Anna", photo, daniel, index=0)
        first, second = (daniel, partner) if order == "erst-daniel" else (partner, daniel)

        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=False, user_id=first.id
        )
        await set_correction(
            db_session, photo_id=photo.id, person_id=anna.id, applies=True, user_id=second.id
        )

        rows = (await db_session.execute(select(PhotoPersonCorrection))).scalars().all()
        assert [(row.applies, row.user_id) for row in rows] == [(True, second.id)]


class TestDeletingAPerson:
    async def test_nothing_with_the_person_id_remains_and_the_other_is_untouched(
        self, db_session: AsyncSession
    ) -> None:
        """Auch mit einer Korrektur samt `reference_id`: Sie faellt vor ihrer Referenz."""
        user = await _user(db_session)
        [photo, other_photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        berta = await _person(db_session, "Berta", other_photo, user, index=1)
        await _assign(db_session, anna, other_photo, user, axis=0, box=_box(5))
        db_session.add_all([_detection(other_photo, anna), _detection(photo, berta, _box(8))])
        await db_session.flush()
        berta_before = await _rows_with_person(db_session, berta.id)

        assert await delete_person(db_session, anna.id) is True
        await db_session.flush()

        assert await _rows_with_person(db_session, anna.id) == {
            "person_references": 0,
            "photo_person_detections": 0,
            "photo_person_corrections": 0,
        }
        assert await db_session.get(Person, anna.id) is None
        assert await _rows_with_person(db_session, berta.id) == berta_before
        assert await db_session.get(Person, berta.id) is not None

    async def test_an_unknown_person_is_reported(self, db_session: AsyncSession) -> None:
        assert await delete_person(db_session, 4711) is False

    async def test_after_delete_and_a_new_person_the_old_is_no_longer_recognised(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        await delete_person(db_session, anna.id)

        clara = await _person(db_session, "Clara", photo, user, index=1)

        assert set(await current_centroids(db_session, model_key=MODEL)) == {clara.id}


class TestTheListing:
    async def test_persons_are_listed_by_slot_with_their_current_reference_count(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        berta = await _person(db_session, "Berta", photo, user, index=1)
        await delete_person(db_session, anna.id)
        clara = await _person(db_session, "Clara", photo, user, index=2)
        db_session.add(
            PersonReference(person_id=berta.id, embedding=_basis(1), model_key=OLD_MODEL)
        )
        await db_session.flush()

        listing = await list_persons(db_session, model_key=MODEL)

        assert [(entry.id, entry.name, entry.reference_count) for entry in listing] == [
            (clara.id, "Clara", 1),
            (berta.id, "Berta", 1),
        ]

    async def test_centroids_ignore_references_of_another_model(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        db_session.add(PersonReference(person_id=anna.id, embedding=_basis(5), model_key=OLD_MODEL))
        await db_session.flush()

        centroids = await current_centroids(db_session, model_key=MODEL)

        assert centroids[anna.id] == pytest.approx(tuple(_basis(0)))
