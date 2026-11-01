"""Die geteilte Ableitung der Endauswahl (`final_selection.included_photos`).

Die Regel selbst ist in `test_album_selection.py` vollstaendig prueft; hier wird die DB-gestuetzte
ANWENDUNG geprueft: dass `included_photos` exakt die `included`-Menge liefert - dieselbe Menge, die
der Export nimmt und die der Lesepfad als `in_final_selection` zeigt (Auflage S9 der Spec 0431).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.final_selection import included_photos
from photosort.models import (
    CriterionScoringRun,
    FinalSelectionDecision,
    Photo,
    PhotoRanking,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from tests.event_rows import event_id_of_run


async def _user(session: AsyncSession, username: str) -> User:
    user = User(username=username, password_hash="irrelevant")
    session.add(user)
    await session.flush()
    return user


async def _project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="/a")
    session.add(project)
    await session.flush()
    return project


async def _successful_run(session: AsyncSession, project: Project) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()
    return run


async def _photo(session: AsyncSession, project: Project, path: str) -> Photo:
    now = datetime.now(UTC).replace(tzinfo=None)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=now,
        taken_at_original=now,
        last_modified=now,
    )
    session.add(photo)
    await session.flush()
    return photo


async def _propose(session: AsyncSession, run: CriterionScoringRun, photo: Photo) -> None:
    """Eine Rangzeile MIT `selection_position` - das Foto ist vorgeschlagen."""
    session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=await event_id_of_run(session, run),
            rank_score=0.9,
            rank_position=1,
            selection_position=1,
        )
    )
    await session.flush()


async def test_included_photos_returns_exactly_the_included_set(db_session: AsyncSession) -> None:
    first = await _user(db_session, "first")
    second = await _user(db_session, "second")
    project = await _project(db_session)
    run = await _successful_run(db_session, project)

    # A: vorgeschlagen, niemand streicht -> einig drin.
    a = await _photo(db_session, project, "a.jpg")
    await _propose(db_session, run, a)
    # B: vorgeschlagen, einer streicht -> strittig, NICHT drin.
    b = await _photo(db_session, project, "b.jpg")
    await _propose(db_session, run, b)
    db_session.add(Rating(photo_id=b.id, user_id=first.id, status=RatingStatus.REJECTED))
    # C: nicht vorgeschlagen, beide nehmen -> einig drin.
    c = await _photo(db_session, project, "c.jpg")
    db_session.add(Rating(photo_id=c.id, user_id=first.id, status=RatingStatus.ALBUM_WORTHY))
    db_session.add(Rating(photo_id=c.id, user_id=second.id, status=RatingStatus.ALBUM_WORTHY))
    # D: ausdruecklich herausgenommen -> NICHT drin, obwohl vorgeschlagen.
    d = await _photo(db_session, project, "d.jpg")
    await _propose(db_session, run, d)
    db_session.add(FinalSelectionDecision(photo_id=d.id, included=False))
    # E: ausdruecklich hineingenommen (ohne jeden Entwurf) -> drin.
    e = await _photo(db_session, project, "e.jpg")
    db_session.add(FinalSelectionDecision(photo_id=e.id, included=True))
    await db_session.commit()

    included = await included_photos(db_session, project.id)

    assert {(entry.photo_id, entry.relative_path) for entry in included} == {
        (a.id, "a.jpg"),
        (c.id, "c.jpg"),
        (e.id, "e.jpg"),
    }


async def test_included_photos_is_sorted_by_photo_id(db_session: AsyncSession) -> None:
    await _user(db_session, "first")
    await _user(db_session, "second")
    project = await _project(db_session)
    run = await _successful_run(db_session, project)

    z = await _photo(db_session, project, "z.jpg")
    a = await _photo(db_session, project, "a.jpg")
    await _propose(db_session, run, z)
    await _propose(db_session, run, a)
    await db_session.commit()

    included = await included_photos(db_session, project.id)

    # `z` wurde zuerst angelegt und traegt die kleinere Id - die Menge ist nach `photo_id` geordnet.
    assert [entry.photo_id for entry in included] == [z.id, a.id]


async def test_included_photos_is_empty_without_a_successful_run(db_session: AsyncSession) -> None:
    await _user(db_session, "first")
    await _user(db_session, "second")
    project = await _project(db_session)
    await _photo(db_session, project, "a.jpg")
    await db_session.commit()

    assert await included_photos(db_session, project.id) == []


async def test_included_photos_is_empty_with_zero_users(db_session: AsyncSession) -> None:
    """`user_count == 0` ist kein Konsens - ohne Konten gehoert nichts zur Endauswahl."""
    project = await _project(db_session)
    run = await _successful_run(db_session, project)
    a = await _photo(db_session, project, "a.jpg")
    await _propose(db_session, run, a)
    await db_session.commit()

    assert await included_photos(db_session, project.id) == []


async def test_selection_state_of_is_the_shared_rule(db_session: AsyncSession) -> None:
    """Die geteilte Regel - derselbe Einstiegspunkt, den der Lesepfad importiert (Auflage S9)."""
    from photosort.api.photos import _selection_state_of
    from photosort.final_selection import selection_state_of

    assert _selection_state_of is selection_state_of
