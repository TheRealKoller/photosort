"""Gemeinsame Bausteine der Foto-API-Tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CategoryMethod,
    CriterionScoringRun,
    Event,
    FinalSelectionDecision,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoRanking,
    Project,
    ProjectCamera,
    Rating,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motif_strengths import upsert_assessment
from photosort.motifs import MOTIF_REGISTRY
from photosort.security import decode_access_token, hash_password
from tests.support import add_photo, make_project


async def _make_project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    return await make_project(session, name, drive_id="d", path="/a")


async def _make_photo(
    session: AsyncSession, project: Project, path: str, taken_at: datetime
) -> Photo:
    return await add_photo(session, project, path, etag="etag-1", taken_at=taken_at)


async def _make_second_user(session: AsyncSession) -> User:
    user = User(username="other-user", password_hash=hash_password("irrelevant"))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _make_criterion_scoring_run(
    session: AsyncSession,
    project: Project,
    *,
    status: ScanStatus = ScanStatus.SUCCESS,
    started_at: datetime | None = None,
    album_level_source: CategoryMethod = CategoryMethod.CLOUD,
) -> CriterionScoringRun:
    """`started_at` bleibt normalerweise beim Server-Default (`now()`). Es ist ausdruecklich zu
    setzen, sobald ein Test ZWEI Laeufe desselben Projekts unterscheiden muss: unter SQLite hat
    `CURRENT_TIMESTAMP` Sekundenaufloesung, und zwei unmittelbar nacheinander angelegte Laeufe
    bekaemen sonst denselben Zeitstempel - "der letzte erfolgreiche Lauf" waere dann nicht
    eindeutig bestimmt.

    `album_level_source` ist das am Lauf eingefrorene Verfahren (ADR 0144); der Vorgabewert ist die
    Ausfallrichtung der Migration und damit der Bestandswert jedes Altlaufs."""
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=status,
        **({} if started_at is None else {"started_at": started_at}),
        album_level_source=album_level_source,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _make_event(
    session: AsyncSession,
    run: CriterionScoringRun,
    *,
    position: int = 1,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    landmark_name: str | None = None,
    place_kind: str | None = None,
    place_lat: float | None = None,
    place_lon: float | None = None,
    place_name: str | None = None,
) -> Event:
    """Ein Event eines Laufs. Die Zeitgrenzen sind zonenlos wie `Photo.taken_at` selbst."""
    default = datetime(2023, 1, 1, 10, 0)
    event_row = Event(
        criterion_scoring_run_id=run.id,
        position=position,
        started_at=default if started_at is None else started_at,
        ended_at=default if ended_at is None else ended_at,
        landmark_name=landmark_name,
        place_kind=place_kind,
        place_lat=place_lat,
        place_lon=place_lon,
        place_name=place_name,
    )
    session.add(event_row)
    await session.commit()
    await session.refresh(event_row)
    return event_row


_DEFAULT_EVENT_POSITION = 1


async def _default_event(
    session: AsyncSession, run: CriterionScoringRun, *, position: int = _DEFAULT_EVENT_POSITION
) -> Event:
    """Das Event, in das jede Rangzeile ohne ausdrueckliche Angabe faellt - angelegt beim ersten
    Bedarf, danach wiederverwendet (`UniqueConstraint(run, position)` wiese eine zweite Anlage
    ab)."""
    existing = (
        await session.execute(
            select(Event).where(
                Event.criterion_scoring_run_id == run.id, Event.position == position
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    return await _make_event(session, run, position=position)


# Sentinel fuer `_add_ranking(selection_position=…)`: "der Vorschlag spiegelt die Rangfolge".
# `None` ist dort ein eigener, bedeutungstragender Wert ("gehoert nicht zum Vorschlag") und taugt
# deshalb nicht als Vorgabewert.
_MIRRORS_RANK = object()


async def _add_ranking(
    session: AsyncSession,
    run: CriterionScoringRun,
    photo: Photo,
    *,
    event: Event | None = None,
    rank_score: float | None,
    rank_position: int | None,
    selection_position: int | None | object = _MIRRORS_RANK,
) -> None:
    """Ein Foto steht je Lauf in GENAU EINER Rangzeile - die Partition ist allein das Event
    (Spec 0427, PR 3).

    Ohne `event` faellt die Zeile in das eine Vorgabe-Event des Laufs.

    `selection_position` spiegelt ohne Angabe die Rangfolge: die meisten Faelle brauchen bloss
    IRGENDEINEN Vorschlag als Vehikel. Jeder Aufbau, in dem Platz und Rang auseinanderfallen oder
    in dem ein Foto ausdruecklich NICHT zum Vorschlag gehoert, sagt es ausgeschrieben."""
    event_row = await _default_event(session, run) if event is None else event
    session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=event_row.id,
            rank_score=rank_score,
            rank_position=rank_position,
            selection_position=(
                rank_position if selection_position is _MIRRORS_RANK else selection_position
            ),
        )
    )
    await session.commit()


def _own_user_id(client: httpx.AsyncClient) -> int:
    """Der angemeldete Nutzer DIESES Clients, aus seinem Token - die Tests wechseln den Token, um
    dieselbe Anfrage als zweiter Nutzer zu stellen."""
    token = client.headers["Authorization"].removeprefix("Bearer ")
    return int(decode_access_token(token)["sub"])


def _own_status(item: dict[str, Any], user_id: int) -> str | None:
    return next((r["status"] for r in item["ratings"] if r["user_id"] == user_id), None)


def assert_album_draft_invariants(body: dict[str, Any], user_id: int) -> None:
    """Die Invarianten der Entwurfsantwort, als Nachsatz JEDES Falls:

    * `events[].position` ist lueckenlos 1..m und aufsteigend;
    * jedes `item.event.id` liegt in `events`;
    * kein eigenes `rejected` ohne Rangzeile - ein gestrichenes Foto steht nur dann in der
      Antwort, wenn der Lauf es fuehrt;
    * im Album genau dann, wenn der eigene Status nicht `rejected` ist - jedes Element ist also
      entweder im Album oder gestrichen, nie etwas Drittes."""
    positions = [event_row["position"] for event_row in body["events"]]
    assert positions == list(range(1, len(positions) + 1))
    event_ids = {event_row["id"] for event_row in body["events"]}
    for item in body["items"]:
        assert item["event"] is not None and item["event"]["id"] in event_ids
        own = _own_status(item, user_id)
        assert own in (None, "album_worthy", "rejected")
        if own == "rejected":
            assert item["ranking"] is not None


async def _album_draft(client: httpx.AsyncClient, project: Project) -> dict[str, Any]:
    response = await client.get(f"/projects/{project.id}/album-draft")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert set(body) == {"events", "items", "eligible_candidate_count"}
    assert_album_draft_invariants(body, _own_user_id(client))
    return body


@contextmanager
def _recorded_select_statements() -> Iterator[list[str]]:
    """Die TATSAECHLICH abgesetzten SELECT-Anweisungen (Muster aus test_project_deletion.py).

    Bewusst ueber das `before_cursor_execute`-Ereignis der Engine und nicht ueber eine daneben
    gepflegte Zahl: eine Konstante und die ausgefuehrten Anweisungen driften, und geprueft gehoert,
    was der Endpunkt tut."""
    statements: list[str] = []

    def _listener(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(Engine, "before_cursor_execute", _listener)
    try:
        yield statements
    finally:
        event.remove(Engine, "before_cursor_execute", _listener)


# ---------------------------------------------------------------------------------------------
# specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 7: die drei neuen
# PhotoOut-Felder und der camera_id-Filter. `taken_at` liefert ab hier die KORRIGIERTE Zeit -
# derselbe Feldname, neue Bedeutung (ADR 0090, Punkt 1).
async def _make_camera(
    session: AsyncSession, project: Project, make: str, model: str, *, offset_minutes: int = 0
) -> ProjectCamera:
    camera = ProjectCamera(
        project_id=project.id, make=make, model=model, offset_minutes=offset_minutes
    )
    session.add(camera)
    await session.commit()
    await session.refresh(camera)
    return camera


async def _make_photo_of_camera(
    session: AsyncSession,
    project: Project,
    path: str,
    taken_at_original: datetime,
    camera: ProjectCamera | None,
) -> Photo:
    offset = 0 if camera is None else camera.offset_minutes
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=taken_at_original + timedelta(minutes=offset),
        taken_at_original=taken_at_original,
        camera_id=None if camera is None else camera.id,
        camera_probed=True,
        last_modified=taken_at_original,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


# specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 5: die beiden ADDITIVEN Felder
# `motif_assessment` und `motifs`. Die Kategoriefelder bleiben in dieser PR unberuehrt daneben
# stehen.
#
# Der tragende Nachweis ist das PAAR in `TestTheFourPhotoStates`: derselbe Aufbau ohne Kopfzeile
# und mit einer Kopfzeile, deren acht Staerken alle 0.0 sind, mit einer Assertion darauf, dass die
# beiden Antworten VERSCHIEDEN sind. Der Fehlerpfad ist ein `?? 0` oder eine leere Standardliste:
# acht Nullzeilen statt eines Satzes.
async def _assess_photo(
    session: AsyncSession,
    photo: Photo,
    *,
    source: MotifAssessmentSource = MotifAssessmentSource.CLOUD,
    provider: str | None = "anthropic",
    excluded_document: bool = False,
    strengths: dict[str, float] | None = None,
    computed_at: datetime | None = None,
) -> None:
    vector = dict.fromkeys(MOTIF_REGISTRY, 0.0)
    if strengths is not None:
        vector.update(strengths)
    await upsert_assessment(
        session,
        photo.id,
        source=source,
        strengths=vector,
        excluded_document=excluded_document,
        provider=provider,
        computed_at=computed_at or datetime(2026, 9, 12, 10, 0, 0),
    )
    await session.commit()


async def _rate_album_suitability(
    session: AsyncSession,
    photo: Photo,
    *,
    level: int = 4,
    reason: str | None = "Alle schauen in die Kamera.",
    computed_at: datetime | None = None,
) -> None:
    session.add(
        PhotoAlbumSuitability(
            photo_id=photo.id,
            level=level,
            reason=reason,
            provider="anthropic",
            computed_at=computed_at or datetime(2026, 9, 13, 10, 0, 0),
        )
    )
    await session.commit()


async def _first_photo_out(client: httpx.AsyncClient, project: Project) -> dict[str, Any]:
    response = await client.get(f"/projects/{project.id}/photos")
    assert response.status_code == 200
    items: list[dict[str, Any]] = response.json()["items"]
    assert len(items) == 1
    return items[0]


# specs/features/0431-endauswahl-gemeinsam.md: die drei additiven `PhotoOut`-Felder der
# Endauswahl und der neue Leseendpunkt.
#
# DIE FIXTURE-FALLE DIESER STORY: `conftest.py::authenticated_api_client` seedet genau EINEN
# Nutzer. Bei einem Nutzer ist jedes vorgeschlagene, unangefasste Foto in der Endauswahl und
# NICHTS ist strittig. Jeder Fall, dessen Aussage "alle einig" oder "strittig" lautet, legt den
# zweiten Nutzer deshalb AUSDRUECKLICH ueber `_make_second_user` an - sonst ist er inhaltsleer und
# trotzdem gruen.
async def _me(session: AsyncSession) -> User:
    """Der EINE Nutzer, den `authenticated_api_client` seedet."""
    return (await session.execute(select(User).where(User.username == "testuser"))).scalar_one()


async def _rate(
    session: AsyncSession,
    photo: Photo,
    user: User,
    status: RatingStatus | None,
    *,
    favorite: bool = False,
) -> None:
    """Die Albumentscheidung EINES Nutzers. `status=None` mit `favorite=True` ist die reine
    Favoritenzeile - eine Zeile OHNE Aussage ueber die Albumzugehoerigkeit (Zusicherung 5)."""
    existing = (
        await session.execute(
            select(Rating).where(Rating.photo_id == photo.id, Rating.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(Rating(photo_id=photo.id, user_id=user.id, status=status, favorite=favorite))
    else:
        existing.status = status
        existing.favorite = favorite
    await session.commit()
    # NUR die Bewertungssammlung dieses Fotos verwerfen, nicht die ganze Sitzung: Test und
    # Anwendung teilen sich hier EINE Sitzung (`conftest.py`), waehrend jede echte Anfrage ihre
    # eigene bekommt. Eine bereits geladene Sammlung bliebe sonst stehen - die Zeile oben wird
    # ueber `photo_id` angelegt und nicht ueber die Beziehung, also feuert kein Backref-Ereignis.
    # Ein pauschales `expire_all()` verboete danach jeden Zugriff auf `photo.id` (synchrones
    # Nachladen, `MissingGreenlet`).
    session.expire(photo, ["ratings"])


async def _decide(session: AsyncSession, photo: Photo, included: bool) -> None:
    """Die gemeinsame Entscheidung des Projekts - ohne jeden Nutzerbezug."""
    existing = await session.get(FinalSelectionDecision, photo.id)
    if existing is None:
        session.add(FinalSelectionDecision(photo_id=photo.id, included=included))
    else:
        existing.included = included
    await session.commit()


def assert_selection_invariants(item: dict[str, Any]) -> None:
    """Zusicherung 3, als NACHSATZ JEDES Falls und nicht nur dort, wo jemand daran gedacht hat.

    Drei Aussagen: nie `contested` und `in_final_selection` zugleich; `contested` impliziert, dass
    keine Entscheidung vorliegt; liegt eine vor, ist sie die Zugehoerigkeit. Der Bruch zeigt sich
    typischerweise in einem ANDEREN Aufbau als dem, der ihn verursacht hat."""
    decision = item["final_selection_decision"]

    assert not (item["contested"] and item["in_final_selection"]), item["id"]
    if item["contested"]:
        assert decision is None, item["id"]
    if decision is not None:
        assert item["in_final_selection"] is decision, item["id"]


def assert_invariants_everywhere(items: list[dict[str, Any]]) -> None:
    for item in items:
        assert_selection_invariants(item)


async def _listing(client: httpx.AsyncClient, project: Project) -> list[dict[str, Any]]:
    response = await client.get(f"/projects/{project.id}/photos")
    assert response.status_code == 200
    items: list[dict[str, Any]] = response.json()["items"]
    assert_invariants_everywhere(items)
    return items


async def _draft(client: httpx.AsyncClient, project: Project) -> list[dict[str, Any]]:
    response = await client.get(f"/projects/{project.id}/album-draft")
    assert response.status_code == 200
    items: list[dict[str, Any]] = response.json()["items"]
    assert_invariants_everywhere(items)
    return items


def _by_id(items: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {item["id"]: item for item in items}


async def _selection(
    client: httpx.AsyncClient, project: Project, *, expect: int = 200
) -> dict[str, Any]:
    response = await client.get(f"/projects/{project.id}/album-selection")
    assert response.status_code == expect
    body: dict[str, Any] = response.json()
    if expect == 200:
        assert_invariants_everywhere(body["items"])
    return body
