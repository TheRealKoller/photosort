"""Form der sechs Prueftabellen (Spec 0616, ADR 0139 Punkt 3).

Der Test prueft die Zusage am MODELL, nicht an der Migrationsdatei: die Migration wird von
`alembic upgrade head` in `tests/conftest.py` gegen dieselbe Metadaten gebaut, eine Abweichung
zwischen beiden faellt dort auf. Was hier steht, ist die Form, auf die sich Job, API und Export
verlassen - Primaerschluessel, Eindeutigkeit, Nullbarkeit und die geschlossenen Wertevorraete.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.db import Base
from photosort.models import (
    ClassificationReview,
    ClassificationReviewCase,
    ClassificationReviewPurpose,
    ClassificationReviewSideKind,
    ClassificationVerdict,
    Photo,
    Project,
    ReviewPhase,
    ScanStatus,
    User,
)

REVIEW_TABLES = (
    "classification_reviews",
    "classification_review_sides",
    "classification_review_results",
    "classification_review_result_strengths",
    "classification_review_cases",
    "classification_review_verdicts",
)


def _table(name: str):
    return Base.metadata.tables[name]


@pytest.mark.parametrize("table_name", REVIEW_TABLES)
def test_every_review_table_exists(table_name: str) -> None:
    assert table_name in Base.metadata.tables


def test_the_review_header_names_status_phase_sample_size_seed_and_photocounts() -> None:
    columns = _table("classification_reviews").columns
    assert set(columns.keys()) == {
        "id",
        "project_id",
        "created_by_user_id",
        "status",
        "phase",
        "sample_size",
        "seed",
        "photo_count",
        "photos_processed",
        "unclassifiable_photo_count",
        "started_at",
        "finished_at",
        "last_progress_at",
        "error_message",
    }
    # Der Teilschritt ist NULL, sobald der Lauf beendet ist - deshalb nullable.
    assert columns["phase"].nullable is True
    assert columns["finished_at"].nullable is True
    assert columns["error_message"].nullable is True


def test_a_side_is_keyed_by_review_and_side_letter() -> None:
    table = _table("classification_review_sides")
    assert [column.name for column in table.primary_key.columns] == ["review_id", "side"]
    assert set(table.columns.keys()) == {
        "review_id",
        "side",
        "kind",
        "provider",
        "model",
        "eye_model_revision",
        "eye_mapping_version",
        "estimated_cost_usd",
        "api_calls",
        "failed_calls",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    }


def test_a_result_is_keyed_by_review_side_and_photo_and_keeps_nullable_statements() -> None:
    table = _table("classification_review_results")
    assert [column.name for column in table.primary_key.columns] == [
        "review_id",
        "side",
        "photo_id",
    ]
    assert table.columns["excluded_document"].nullable is True
    assert table.columns["album_level"].nullable is True
    strengths = _table("classification_review_result_strengths")
    assert [column.name for column in strengths.primary_key.columns] == [
        "review_id",
        "side",
        "photo_id",
        "motif_key",
    ]


def test_a_case_is_unique_per_review_photo_purpose_and_motif() -> None:
    table = _table("classification_review_cases")
    unique = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns]
        == ["review_id", "photo_id", "purpose", "motif_key"]
    ]
    assert len(unique) == 1
    # Die Fotoposition wird GESPEICHERT, nicht abgeleitet (ADR 0139 Punkt 3).
    assert "photo_position" in table.columns
    assert table.columns["photo_position"].nullable is False
    assert table.columns["motif_key"].nullable is True


def test_a_verdict_is_keyed_by_the_case_and_names_its_writer() -> None:
    table = _table("classification_review_verdicts")
    assert [column.name for column in table.primary_key.columns] == ["case_id"]
    assert set(table.columns.keys()) == {
        "case_id",
        "verdict",
        "updated_by_user_id",
        "updated_at",
    }


def test_the_closed_value_sets_match_the_spec() -> None:
    assert [member.value for member in ClassificationReviewSideKind] == ["cloud", "eye", "local"]
    assert [member.value for member in ClassificationReviewPurpose] == [
        "motifs",
        "motif_feature",
        "excluded_document",
        "album_level",
    ]
    assert [member.value for member in ReviewPhase] == ["side_a", "side_b", "cases"]
    assert [member.value for member in ClassificationVerdict] == [
        "a_better",
        "b_better",
        "both_ok",
        "both_wrong",
    ]


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="drive", opencloud_path="Costa Rica")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _make_user(session: AsyncSession) -> User:
    user = User(username="anleger", password_hash="x")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _add_photo(session: AsyncSession, project: Project) -> Photo:
    moment = datetime(2023, 6, 1, 12, 0)
    photo = Photo(
        project_id=project.id,
        relative_path="keep.jpg",
        etag="etag-keep",
        content_length=1_000,
        taken_at=moment,
        taken_at_original=moment,
        last_modified=moment,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _make_review(session: AsyncSession, project: Project, user: User) -> ClassificationReview:
    review = ClassificationReview(
        project_id=project.id,
        created_by_user_id=user.id,
        status=ScanStatus.SUCCESS,
        sample_size=30,
        seed=4711,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


async def test_a_photo_counting_case_is_unique_even_though_its_motif_key_is_null(
    db_session: AsyncSession,
) -> None:
    """ADR 0139 Punkt 3: ein Fall ist eindeutig je Pruefung, Foto, Zweck und Merkmal. Fuer die drei
    fotozzaehlenden Zwecke ist `motif_key` NULL - und ein einfaches UNIQUE behandelt NULL je Zeile
    als verschieden. Erst der Teilindex `WHERE motif_key IS NULL` macht die Zusage wahr."""
    project = await _make_project(db_session)
    user = await _make_user(db_session)
    photo = await _add_photo(db_session, project)
    review = await _make_review(db_session, project, user)
    # VOR dem `rollback` festhalten: er verfaellt die Instanzen, und ein spaeterer Attributzugriff
    # waere ein Nachladen ausserhalb des async-Kontexts.
    review_id, photo_id = review.id, photo.id
    db_session.add(
        ClassificationReviewCase(
            review_id=review_id,
            photo_id=photo_id,
            photo_position=1,
            purpose=ClassificationReviewPurpose.MOTIFS,
        )
    )
    await db_session.commit()

    db_session.add(
        ClassificationReviewCase(
            review_id=review_id,
            photo_id=photo_id,
            photo_position=1,
            purpose=ClassificationReviewPurpose.MOTIFS,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Ein Merkmal-Fall desselben Fotos ist ein EIGENER Fall - je abweichendem Motiv genau einer.
    db_session.add_all(
        [
            ClassificationReviewCase(
                review_id=review_id,
                photo_id=photo_id,
                photo_position=1,
                purpose=ClassificationReviewPurpose.MOTIF_FEATURE,
                motif_key="menschen",
            ),
            ClassificationReviewCase(
                review_id=review_id,
                photo_id=photo_id,
                photo_position=1,
                purpose=ClassificationReviewPurpose.MOTIF_FEATURE,
                motif_key="tiere",
            ),
        ]
    )
    await db_session.commit()
