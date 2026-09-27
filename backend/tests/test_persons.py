"""Die wirksame Zuordnung, das Festlegen und das Entfernen von Personen (Spec 0292, ADR 0126
Punkt 6).

Die Merkmale der Lagen sind Basisvektoren fern jeder Schwelle (Kosinus exakt 1 oder 0) - eine
Kalibrierung der Konstanten in `person_matching.py` roetet hier nichts.
"""

from __future__ import annotations

import ast
from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    InvalidEmbedding,
    InvalidPersonName,
    PersonAssignment,
    PersonLimitReached,
    ReferenceLimitReached,
    ResemblesOtherPerson,
    add_reference,
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
    session: AsyncSession, name: str, photo: Photo, user: User, *, index: int
) -> Person:
    return await create_person(
        session,
        name=name,
        embedding=_basis(index),
        model_key=MODEL,
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
            db_session.add(
                PhotoPersonDetection(photo_id=photo.id, person_id=person.id, computed_at=NOW)
            )
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
            assert effective[photo.id] == [PersonAssignment(person_id=person.id, origin=expected)]

    async def test_both_persons_are_listed_by_slot(self, db_session: AsyncSession) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)
        berta = await _person(db_session, "Berta", anchor, user, index=1)
        db_session.add_all(
            [
                PhotoPersonDetection(photo_id=photo.id, person_id=berta.id, computed_at=NOW),
                PhotoPersonDetection(photo_id=photo.id, person_id=anna.id, computed_at=NOW),
            ]
        )
        await db_session.flush()

        effective = await load_effective_persons(db_session, [photo.id])

        assert [entry.person_id for entry in effective[photo.id]] == [anna.id, berta.id]

    def test_exactly_one_place_in_the_read_path_names_the_correction_column(self) -> None:
        """Die wirksame Zuordnung entsteht in GENAU EINEM SQL-Konstrukt. Das Messkommando zaehlt
        bewusst die rohe Spur (Korrektur gegen Erkennung) und ist deshalb ausgenommen."""
        naming = sorted(
            path.name
            for path in SRC_DIR.rglob("*.py")
            if "PhotoPersonCorrection.applies" in path.read_text(encoding="utf-8")
            and path.name != "person_probe.py"
        )
        source = (SRC_DIR / "photosort" / "persons.py").read_text(encoding="utf-8")

        assert naming == ["persons.py"]
        assert source.count("PhotoPersonCorrection.applies") == 1


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
        assert effective[photo.id] == [PersonAssignment(person_id=person.id, origin="corrected")]

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
        "embedding",
        [
            [float("nan")] + [0.0] * (EMBEDDING_DIMENSION - 1),
            [float("inf")] + [0.0] * (EMBEDDING_DIMENSION - 1),
            [0.0] * EMBEDDING_DIMENSION,
        ],
        ids=["nan", "inf", "nullvektor"],
    )
    async def test_a_broken_embedding_writes_nothing(
        self, db_session: AsyncSession, embedding: list[float]
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)

        with pytest.raises(InvalidEmbedding):
            await create_person(
                db_session,
                name="Anna",
                embedding=embedding,
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
            await _person(db_session, "Berta", photo, user, index=0)

        assert len((await db_session.execute(select(Person))).scalars().all()) == 1


class TestReferences:
    async def test_a_reference_assigns_the_person_to_the_photo(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [anchor, photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", anchor, user, index=0)

        await add_reference(
            db_session,
            person_id=anna.id,
            embedding=_basis(0),
            model_key=MODEL,
            photo_id=photo.id,
            user_id=user.id,
        )

        effective = await load_effective_persons(db_session, [photo.id])
        assert effective[photo.id] == [PersonAssignment(person_id=anna.id, origin="corrected")]

    async def test_a_reference_resembling_the_other_person_is_refused(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        await _person(db_session, "Berta", photo, user, index=1)

        with pytest.raises(ResemblesOtherPerson):
            await add_reference(
                db_session,
                person_id=anna.id,
                embedding=_basis(1),
                model_key=MODEL,
                photo_id=photo.id,
                user_id=user.id,
            )

    async def test_the_twentieth_is_accepted_the_twenty_first_refused_whatever_old_references(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        for _ in range(MAX_REFERENCES_PER_PERSON - 1):
            await add_reference(
                db_session,
                person_id=anna.id,
                embedding=_basis(0),
                model_key=MODEL,
                photo_id=photo.id,
                user_id=user.id,
            )

        with pytest.raises(ReferenceLimitReached):
            await add_reference(
                db_session,
                person_id=anna.id,
                embedding=_basis(0),
                model_key=MODEL,
                photo_id=photo.id,
                user_id=user.id,
            )

        [summary] = await list_persons(db_session, model_key=MODEL)
        assert summary.reference_count == MAX_REFERENCES_PER_PERSON

    async def test_a_model_change_replaces_the_old_references_in_the_same_transaction(
        self, db_session: AsyncSession
    ) -> None:
        user = await _user(db_session)
        [photo] = await _photos(db_session, 1)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        await db_session.execute(PersonReference.__table__.update().values(model_key=OLD_MODEL))
        db_session.add_all(
            PersonReference(person_id=anna.id, embedding=_basis(0), model_key=OLD_MODEL)
            for _ in range(MAX_REFERENCES_PER_PERSON - 1)
        )
        await db_session.flush()
        [before] = await list_persons(db_session, model_key=MODEL)
        assert before.reference_count == 0
        assert await current_centroids(db_session, model_key=MODEL) == {}

        await add_reference(
            db_session,
            person_id=anna.id,
            embedding=_basis(0),
            model_key=MODEL,
            photo_id=photo.id,
            user_id=user.id,
        )

        keys = (await db_session.execute(select(PersonReference.model_key))).scalars().all()
        assert keys == [MODEL]
        [after] = await list_persons(db_session, model_key=MODEL)
        assert after.reference_count == 1

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
        user = await _user(db_session)
        [photo, other_photo] = await _photos(db_session, 2)
        anna = await _person(db_session, "Anna", photo, user, index=0)
        berta = await _person(db_session, "Berta", other_photo, user, index=1)
        db_session.add_all(
            [
                PhotoPersonDetection(photo_id=other_photo.id, person_id=anna.id, computed_at=NOW),
                PhotoPersonDetection(photo_id=photo.id, person_id=berta.id, computed_at=NOW),
            ]
        )
        await db_session.flush()
        berta_before = await _rows_with_person(db_session, berta.id)

        assert await delete_person(db_session, anna.id) is True

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
