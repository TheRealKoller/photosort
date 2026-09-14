"""Der Lauf rechnet mit den GESPEICHERTEN Gewichten und haelt fest, mit welcher Fassung
(Spec 0432, PR 3 Schritt 2).

DREI ZUSAGEN, die ohne eigenen Fall still brechen:

1. Eine uebernommene Anpassung WIRKT. Ohne diesen Nachweis besteht "wirkt erst beim naechsten
   Durchlauf" auch gegen eine Umsetzung, die Gewichte speichert, die nie jemand liest - bei einem
   neu eingefuehrten Persistenzweg der wahrscheinlichste Fehler.
2. Die Gewichte werden EINMAL JE LAUF gelesen, vor der Partitionsschleife. Die Konstante stand
   zuvor innerhalb der Schleife, je Foto neu; ein Lesegang je Foto faellt an keinem Ergebnis auf.
3. Die Lauf-Zeile haelt die benutzte Fassung fest. Ohne sie ist ein vergangener Rang-Score nicht
   mehr nachrechenbar, sobald jemand die Gewichte angepasst hat.

Die gewaehlten Gewichte sind ausdruecklich KEINE gleichmaessige Streckung: Die ist nachweislich
wirkungslos (`test_quality.py::TestTheRenormalizationInvariance`), und ein Fall mit ihr bestuende
auch gegen eine Umsetzung, die die Gewichte gar nicht durchreicht.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Event,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.quality import QUALITY_CRITERION_WEIGHTS
from photosort.quality_weights import store_weights
from photosort.worker import rebuild_run_grouping

_NOW = datetime(2026, 8, 12, 9, 0, 0)

# Eine Fassung, die die beiden Kriterien GEGENEINANDER verschiebt statt beide gleich zu strecken.
_TILTED = {"sharpness": 1.9, "exposure": 0.1}


@contextmanager
def _counted_selects(fragment: str) -> Iterator[list[str]]:
    """Die tatsaechlich abgesetzten Anweisungen, die `fragment` enthalten.

    Ueber das `before_cursor_execute`-Ereignis der Engine und nicht ueber einen Zaehler im
    Anwendungscode: Geprueft gehoert, was der Lauf tut, nicht was er zu tun behauptet."""
    seen: list[str] = []

    def _listener(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if fragment in statement:
            seen.append(statement)

    event.listen(Engine, "before_cursor_execute", _listener)
    try:
        yield seen
    finally:
        event.remove(Engine, "before_cursor_execute", _listener)


async def _fixture(session: AsyncSession, *, photo_count: int = 3) -> CriterionScoringRun:
    """Ein Projekt mit `photo_count` Fotos DERSELBEN Modellstufe in EINEM Ereignis.

    Dieselbe Stufe, damit die Rangfolge allein an den lokalen Kriterien haengt - bei
    verschiedenen Stufen fuehrt die Modellstufe, und eine Gewichtsaenderung koennte an der
    Reihenfolge folgenlos bleiben."""
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/c")
    session.add(project)
    await session.flush()
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()
    grouping_event = Event(
        criterion_scoring_run_id=run.id, position=1, started_at=_NOW, ended_at=_NOW
    )
    session.add(grouping_event)
    await session.flush()

    for index in range(photo_count):
        photo = Photo(
            project_id=project.id,
            relative_path=f"img-{index}.jpg",
            etag=f"etag-{index}",
            content_length=1,
            taken_at=_NOW,
            taken_at_original=_NOW,
            last_modified=_NOW,
        )
        session.add(photo)
        await session.flush()
        session.add(
            PhotoAlbumSuitability(
                photo_id=photo.id,
                level=3,
                reason="Modellbegruendung",
                provider="anthropic",
                computed_at=_NOW,
            )
        )
        # Die beiden gewichteten Kriterien laufen GEGENLAEUFIG ueber die Fotos: Eine Verschiebung
        # der Gewichte zueinander veraendert dadurch jeden Qualitaetswert.
        session.add_all(
            [
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key="sharpness",
                    value=0.1 + 0.4 * index,
                    source=CriterionSource.LOCAL_HEURISTIC,
                    computed_at=_NOW,
                ),
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key="exposure",
                    value=0.9 - 0.4 * index,
                    source=CriterionSource.LOCAL_HEURISTIC,
                    computed_at=_NOW,
                ),
            ]
        )
        session.add(
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo.id,
                event_id=grouping_event.id,
                rank_score=0.5,
                rank_position=index + 1,
            )
        )
    await session.flush()
    return run


async def _scores(session: AsyncSession, run_id: int) -> dict[int, float | None]:
    rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.rank_score).where(
                PhotoRanking.criterion_scoring_run_id == run_id
            )
        )
    ).all()
    return {photo_id: rank_score for photo_id, rank_score in rows}


async def _user_id(session: AsyncSession) -> int:
    user = User(username="daniel", password_hash="x")
    session.add(user)
    await session.flush()
    return user.id


class TestARunWithoutAnyStoredSet:
    async def test_it_records_no_weight_set_on_the_run_row(self, db_session: AsyncSession) -> None:
        """`NULL` heisst "Startwerte oder Altzeile" - es gibt keine Fassung, die die Startwerte
        enthielte, und deshalb keinen Wert, auf den dieser Lauf zeigen koennte."""
        run = await _fixture(db_session)

        await rebuild_run_grouping(db_session, run.project_id)
        await db_session.flush()

        assert run.quality_weight_set_id is None


class TestAStoredSetActuallyChangesTheResult:
    async def test_at_least_one_rank_score_moves_after_the_rebuild(
        self, db_session: AsyncSession
    ) -> None:
        """DER NACHWEIS, DASS ES UEBERHAUPT WIRKT. Gepruefte Gegenprobe zur Zusage "wirkt erst
        beim naechsten Durchlauf": Ohne ihn bestuende jene auch gegen eine Umsetzung, die
        Gewichte speichert, die nie jemand liest."""
        run = await _fixture(db_session)
        await rebuild_run_grouping(db_session, run.project_id)
        await db_session.flush()
        before = await _scores(db_session, run.id)

        await store_weights(
            db_session, weights=_TILTED, user_id=await _user_id(db_session), based_on_event_id=0
        )
        await db_session.flush()
        await rebuild_run_grouping(db_session, run.project_id)
        await db_session.flush()

        after = await _scores(db_session, run.id)
        assert set(before) == set(after)
        assert any(before[photo_id] != after[photo_id] for photo_id in before)

    async def test_the_run_row_remembers_the_set_it_used(self, db_session: AsyncSession) -> None:
        run = await _fixture(db_session)
        written = await store_weights(
            db_session, weights=_TILTED, user_id=await _user_id(db_session), based_on_event_id=0
        )
        await db_session.flush()

        await rebuild_run_grouping(db_session, run.project_id)
        await db_session.flush()

        assert run.quality_weight_set_id == written.id

    async def test_a_set_unknown_to_the_baseline_never_reaches_the_score(
        self, db_session: AsyncSession
    ) -> None:
        """G2 am Lauf: Ein Kriterium mit Inhaltsaussage in einer Fassung bewegt keinen einzigen
        Qualitaetswert - der wirksame Schluesselsatz ist exakt der Startwertsatz."""
        run = await _fixture(db_session)
        await rebuild_run_grouping(db_session, run.project_id)
        await db_session.flush()
        before = await _scores(db_session, run.id)

        await store_weights(
            db_session,
            weights={"content_people": 9.0, **QUALITY_CRITERION_WEIGHTS},
            user_id=await _user_id(db_session),
            based_on_event_id=0,
        )
        await db_session.flush()
        await rebuild_run_grouping(db_session, run.project_id)
        await db_session.flush()

        assert await _scores(db_session, run.id) == before


class TestTheWeightsAreReadOncePerRun:
    async def test_the_entry_table_is_queried_at_most_once_for_three_photos(
        self, db_session: AsyncSession
    ) -> None:
        """Heute stand die Konstante INNERHALB der Partitionsschleife, je Foto neu. Ein Lesegang
        je Foto faellt an keinem Ergebnis auf - nur an der Zahl der Anweisungen."""
        run = await _fixture(db_session, photo_count=3)
        await store_weights(
            db_session, weights=_TILTED, user_id=await _user_id(db_session), based_on_event_id=0
        )
        await db_session.flush()

        with _counted_selects("quality_weight_entries") as statements:
            await rebuild_run_grouping(db_session, run.project_id)
            await db_session.flush()

        assert len(statements) == 1, statements
