"""Die drei Schreibwege der Vergleichsansicht - je Aufnahme, je Gruppe und der Gruppenabschluss.

Sie bestimmen mit, welche Bilddaten den Homeserver Richtung Cloud-Anbieter verlassen. Sie tragen
deshalb DREI Sicherungen (S8): die Router-Dependency, den Eintrag in
`test_auth_guard.py::_protected_router_operations()` und je einen eigenen, pfadbenannten 401-Fall
in dieser Datei.

DER GRUPPENWEITE WEG IST DER SCHAERFERE (S5): Ein `None` als Vergleichswert des Gruppenpraedikats
wird in SQLAlchemy zu `duplicate_of IS NULL` und traefe jede nicht aussortierte Aufnahme des
Projekts - ein Klick schriebe `discard` oder `keep` auf den gesamten Bestand. Der Repraesentant
wird deshalb zuerst aufgeloest; gibt es keine Gruppe, ist die Antwort `404`, BEVOR geschrieben
wird.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.duplicate_decisions import DuplicateDecisionIn
from photosort.api.photos import MAX_QUERY_POSITION
from photosort.models import (
    DuplicateDecision,
    FeedbackEvent,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)

_BASE = datetime(2023, 5, 1, 12, 0, 0, tzinfo=UTC)


async def _project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=f"/{name}")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _photo(
    session: AsyncSession,
    project: Project,
    path: str,
    *,
    seconds: int = 0,
    suggested_status: RatingStatus | None = None,
    duplicate_of: int | None = None,
) -> Photo:
    moment = _BASE + timedelta(seconds=seconds)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=1,
        taken_at=moment,
        taken_at_original=moment,
        last_modified=moment,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=100.0,
            exposure=0.0,
            suggested_status=suggested_status,
            duplicate_of=duplicate_of,
            computed_at=moment,
        )
    )
    await session.commit()
    return photo


async def _star(
    session: AsyncSession, project: Project, size: int, *, first_second: int = 0, prefix: str = "g"
) -> tuple[Photo, list[Photo]]:
    winner = await _photo(session, project, f"{prefix}-gewinner.jpg", seconds=first_second)
    losers = [
        await _photo(
            session,
            project,
            f"{prefix}-verlierer-{offset}.jpg",
            seconds=first_second + offset,
            suggested_status=RatingStatus.REJECTED,
            duplicate_of=winner.id,
        )
        for offset in range(1, size)
    ]
    return winner, losers


def _single_url(project_id: int, photo_id: int) -> str:
    return f"/projects/{project_id}/photos/{photo_id}/duplicate-decision"


def _group_url(project_id: int, photo_id: int) -> str:
    return f"/projects/{project_id}/duplicate-groups/{photo_id}/decision"


def _confirm_url(project_id: int, photo_id: int) -> str:
    return f"/projects/{project_id}/duplicate-groups/{photo_id}/confirm"


async def _stored(session: AsyncSession, photo_id: int) -> DuplicateDecision | None:
    return (
        await session.execute(
            select(PhotoDuplicateDecision.decision).where(
                PhotoDuplicateDecision.photo_id == photo_id
            )
        )
    ).scalar_one_or_none()


# ------------------------------------------------------------------------------------------
# Authentifizierung (S8)
# ------------------------------------------------------------------------------------------


async def test_the_single_write_path_requires_a_token(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put(_single_url(1, 1), json={"decision": "keep"})

    assert response.status_code == 401


async def test_the_group_write_path_requires_a_token(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put(_group_url(1, 1), json={"decision": "keep"})

    assert response.status_code == 401


# ------------------------------------------------------------------------------------------
# Einzelentscheidung (AK4)
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("decision", ["keep", "discard"])
async def test_a_single_decision_is_written_and_answered_in_the_group_form(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, decision: str
) -> None:
    project = await _project(db_session)
    _winner, losers = await _star(db_session, project, 3)

    response = await authenticated_api_client.put(
        _single_url(project.id, losers[0].id), json={"decision": decision}
    )

    assert response.status_code == 200
    body = response.json()
    assert {item["photo"]["id"]: item["effective_decision"] for item in body["items"]}[
        losers[0].id
    ] == (decision)
    assert await _stored(db_session, losers[0].id) == DuplicateDecision(decision)


async def test_a_repeated_write_overwrites_instead_of_failing(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der Primaerschluessel ist `photo_id` - ein naives `INSERT` liefe in einen `IntegrityError`
    und damit in eine 500. Der Wechsel behalten -> Ausschuss -> behalten ist ausdruecklich moeglich
    (AK4), und danach steht genau EINE Zeile."""
    project = await _project(db_session)
    _winner, losers = await _star(db_session, project, 2)
    url = _single_url(project.id, losers[0].id)

    for decision in ("keep", "discard", "keep"):
        response = await authenticated_api_client.put(url, json={"decision": decision})
        assert response.status_code == 200

    assert await _stored(db_session, losers[0].id) == DuplicateDecision.KEEP
    zeilen = (
        await db_session.execute(
            select(func.count())
            .select_from(PhotoDuplicateDecision.__table__)
            .where(PhotoDuplicateDecision.photo_id == losers[0].id)
        )
    ).scalar_one()
    assert zeilen == 1


async def test_the_representative_can_be_decided_too(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK4: kein Gewinnerzwang, und kein Mitglied ist von der Entscheidung ausgenommen - auch der
    Repraesentant nicht, der selbst keine Vorschlagszeile traegt."""
    project = await _project(db_session)
    winner, _losers = await _star(db_session, project, 3)

    response = await authenticated_api_client.put(
        _single_url(project.id, winner.id), json={"decision": "discard"}
    )

    assert response.status_code == 200
    assert await _stored(db_session, winner.id) == DuplicateDecision.DISCARD


async def test_all_keep_and_all_discard_are_valid_end_states(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK4: Es gibt keinen Gewinnerzwang. "Alle behalten" und "alle verwerfen" sind zulaessige
    Endzustaende, und nichts weist sie zurueck."""
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)

    mitglieder = (winner, *losers)
    for decision in ("keep", "discard"):
        for member in mitglieder:
            response = await authenticated_api_client.put(
                _single_url(project.id, member.id), json={"decision": decision}
            )
            assert response.status_code == 200
        assert {await _stored(db_session, member.id) for member in mitglieder} == {
            DuplicateDecision(decision)
        }


async def test_there_is_no_way_back_to_undecided(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK4/ADR 0104: Eine Ruecknahme nach "noch nicht entschieden" gibt es nicht - es entsteht kein
    `DELETE`, und ein `null` im Koerper wird zurueckgewiesen statt als Ruecknahme gelesen."""
    project = await _project(db_session)
    _winner, losers = await _star(db_session, project, 2)
    url = _single_url(project.id, losers[0].id)

    geloescht = await authenticated_api_client.delete(url)
    leer = await authenticated_api_client.put(url, json={"decision": None})

    assert geloescht.status_code == 405
    assert leer.status_code == 422


async def test_the_single_write_path_writes_no_rating_and_no_feedback_event(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """ADR 0104 Punkt 2: Die Vergleichsansicht schreibt KEINE `Rating`-Zeile und KEIN
    `FeedbackEvent`. Ueber `write_own_rating` geschrieben zoege jedes "behalten" das Foto zugleich
    in den Album-Entwurf des Nutzers und erzeugte ein Nacharbeits-Ereignis - beides sind Aussagen,
    die niemand getroffen hat: Die Nacharbeit misst Korrekturen am Album, nicht am Ausschuss."""
    project = await _project(db_session)
    _winner, losers = await _star(db_session, project, 2)

    await authenticated_api_client.put(
        _single_url(project.id, losers[0].id), json={"decision": "keep"}
    )

    assert (
        await db_session.execute(select(func.count()).select_from(Rating.__table__))
    ).scalar_one() == 0
    assert (
        await db_session.execute(select(func.count()).select_from(FeedbackEvent.__table__))
    ).scalar_one() == 0


# ------------------------------------------------------------------------------------------
# Gruppenweite Abkuerzungen (AK9)
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("decision", ["keep", "discard"])
async def test_the_group_write_path_sets_every_member_in_one_call(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, decision: str
) -> None:
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 5)

    response = await authenticated_api_client.put(
        _group_url(project.id, losers[2].id), json={"decision": decision}
    )

    assert response.status_code == 200
    assert {item["effective_decision"] for item in response.json()["items"]} == {decision}
    assert {await _stored(db_session, member.id) for member in (winner, *losers)} == {
        DuplicateDecision(decision)
    }


async def test_the_group_write_path_overrides_earlier_single_decisions(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK9: Danach traegt JEDES Mitglied denselben Zustand - auch jene, die vorher einzeln anders
    entschieden waren."""
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)
    await authenticated_api_client.put(
        _single_url(project.id, losers[0].id), json={"decision": "discard"}
    )

    await authenticated_api_client.put(_group_url(project.id, winner.id), json={"decision": "keep"})

    assert {await _stored(db_session, member.id) for member in (winner, *losers)} == {
        DuplicateDecision.KEEP
    }


async def test_a_single_write_after_the_group_write_overrides_exactly_one_member(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)
    await authenticated_api_client.put(_group_url(project.id, winner.id), json={"decision": "keep"})

    await authenticated_api_client.put(
        _single_url(project.id, losers[1].id), json={"decision": "discard"}
    )

    assert await _stored(db_session, losers[1].id) == DuplicateDecision.DISCARD
    assert await _stored(db_session, winner.id) == DuplicateDecision.KEEP
    assert await _stored(db_session, losers[0].id) == DuplicateDecision.KEEP


async def test_the_group_write_path_never_touches_another_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S5): Die Gruppengroesse ist die Verstaerkung dieses Schreibwegs. Ein
    danebengreifendes Gruppenpraedikat schriebe auf einen Bestand, den niemand angesehen hat."""
    project = await _project(db_session)
    ziel_winner, ziel_losers = await _star(db_session, project, 3, prefix="a")
    fremd_winner, fremd_losers = await _star(db_session, project, 3, first_second=100, prefix="b")
    allein = await _photo(db_session, project, "allein.jpg", seconds=500)

    await authenticated_api_client.put(
        _group_url(project.id, ziel_winner.id), json={"decision": "discard"}
    )

    assert await _stored(db_session, ziel_losers[0].id) == DuplicateDecision.DISCARD
    for unbeteiligt in (fremd_winner, *fremd_losers, allein):
        assert await _stored(db_session, unbeteiligt.id) is None


async def test_a_photo_without_a_group_is_a_404_before_anything_is_written(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S5), DER Fall: Ein `None` als Repraesentant wird in SQLAlchemy zu
    `duplicate_of IS NULL` und traefe jede nicht aussortierte Aufnahme des Projekts. Der
    Repraesentant wird deshalb zuerst aufgeloest und bei fehlender Gruppe mit `404` geantwortet -
    BEVOR geschrieben wird."""
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)
    allein = await _photo(db_session, project, "allein.jpg", seconds=500)

    response = await authenticated_api_client.put(
        _group_url(project.id, allein.id), json={"decision": "discard"}
    )

    assert response.status_code == 404
    assert (
        await db_session.execute(select(func.count()).select_from(PhotoDuplicateDecision.__table__))
    ).scalar_one() == 0
    for unberuehrt in (winner, *losers, allein):
        assert await _stored(db_session, unberuehrt.id) is None


async def test_the_group_write_path_commits_in_one_transaction(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S9): Eine halb entschiedene Gruppe waere eine willkuerliche Teilmenge im
    abfliessenden Bestand, ohne dass ein Lesepfad den Zwischenzustand als solchen erkennt. Gemessen
    an der Zahl der `COMMIT`s waehrend des Aufrufs - eine Schleife mit einem Commit je Mitglied
    faellt hier auf, nicht erst an einem abgebrochenen Lauf."""
    project = await _project(db_session)
    winner, _losers = await _star(db_session, project, 5)
    commits: list[int] = []

    # Gezaehlt ueber die Sitzung des Endpunkts: `db_session` teilt die Engine, die eigentliche
    # Transaktionsgrenze setzt der Endpunkt selbst.
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def _on_commit(conn: object) -> None:
        commits.append(1)

    event.listen(Engine, "commit", _on_commit)
    try:
        response = await authenticated_api_client.put(
            _group_url(project.id, winner.id), json={"decision": "keep"}
        )
    finally:
        event.remove(Engine, "commit", _on_commit)

    assert response.status_code == 200
    assert len(commits) == 1


@pytest.mark.parametrize("url_builder", [_single_url, _group_url])
async def test_a_concurrent_write_on_the_same_photo_is_a_409_and_never_a_500(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    url_builder: object,
) -> None:
    """SICHERHEIT (S9), zweite Haelfte: Der Primaerschluessel ist `photo_id`. Das `DELETE` vor dem
    `INSERT` faengt den WIEDERHOLTEN Druck ab - nicht den NEBENLAEUFIGEN: Committet die andere
    Sitzung zwischen beiden Anweisungen, trifft das `INSERT` eine Zeile, die es beim `DELETE` noch
    nicht gab, und der Primaerschluessel wirft.

    Der Fehler wird EINGESETZT statt nachgestellt (Muster `test_api_album_decisions.py`): Das
    Fenster zwischen zwei Anweisungen einer Transaktion ist in einer Testsitzung, die dieselbe
    Verbindung benutzt, nicht herstellbar - und der Testgegenstand ist ohnehin der Zweig, nicht
    das Scheduling. `calls` belegt, dass er betreten wurde; ohne diese Zusicherung bestuende der
    Fall auch gegen eine Umsetzung, die den `flush` gar nicht erst absetzt."""
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)
    projekt_id, ziel_id = project.id, losers[0].id
    mitglied_ids = [winner.id, *(loser.id for loser in losers)]
    calls = {"count": 0}
    original_flush = AsyncSession.flush

    async def _always_failing(self: AsyncSession, *args: object, **kwargs: object) -> None:
        calls["count"] += 1
        raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))

    monkeypatch.setattr(AsyncSession, "flush", _always_failing)
    try:
        response = await authenticated_api_client.put(
            url_builder(projekt_id, ziel_id),  # type: ignore[operator]
            json={"decision": "discard"},
        )
    finally:
        monkeypatch.setattr(AsyncSession, "flush", original_flush)

    assert calls["count"] >= 1, "der IntegrityError-Zweig wurde gar nicht betreten"
    assert response.status_code == 409
    # Die Meldung nennt die Handlung, nie einen Wert oder eine fremde Id.
    assert "erneut" in response.json()["detail"].lower()
    # Der Rueckzug ist vollstaendig: Auf dem Gruppenweg bleibt keine einzige Zeile der Gruppe halb
    # geschrieben zurueck - die Transaktion umfasst sie alle. Die Ids stehen VOR dem Verfallen
    # fest; danach loeste ein Attributzugriff einen Lazy-Load aus.
    for mitglied_id in mitglied_ids:
        assert await _stored(db_session, mitglied_id) is None


# ------------------------------------------------------------------------------------------
# Der Koerper und die Pfad-Ids (S6)
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("url_builder", [_single_url, _group_url])
async def test_the_body_carries_exactly_one_field(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    url_builder: object,
) -> None:
    """SICHERHEIT (S6): Die Feldmenge wird auf GLEICHHEIT geprueft, nicht auf Teilmenge. Eine
    mitgeschickte Id-Liste waere ein Massen-Schreibweg auf beliebige Fotos - sie wird nicht
    ignoriert, sondern zurueckgewiesen."""
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)
    url = url_builder(project.id, winner.id)  # type: ignore[operator]

    mit_id_liste = await authenticated_api_client.put(
        url, json={"decision": "discard", "photo_ids": [losers[0].id]}
    )
    mit_nutzer = await authenticated_api_client.put(url, json={"decision": "discard", "user_id": 1})

    assert mit_id_liste.status_code == 422
    assert mit_nutzer.status_code == 422
    # Die Feldmenge selbst, als Gleichheit: Ein spaeter ergaenztes Feld faellt hier auf, auch wenn
    # kein Aufrufer es je schickt.
    assert set(DuplicateDecisionIn.model_fields) == {"decision"}


@pytest.mark.parametrize("url_builder", [_single_url, _group_url])
async def test_an_unknown_decision_value_is_a_422(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    url_builder: object,
) -> None:
    project = await _project(db_session)
    winner, _losers = await _star(db_session, project, 2)

    response = await authenticated_api_client.put(
        url_builder(project.id, winner.id),  # type: ignore[operator]
        json={"decision": "vielleicht"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "url_builder"),
    [("put", _single_url), ("put", _group_url), ("post", _confirm_url)],
)
@pytest.mark.parametrize("photo_id", [0, -1, MAX_QUERY_POSITION + 1])
async def test_a_photo_id_outside_the_declared_bounds_is_a_422(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    method: str,
    url_builder: object,
    photo_id: int,
) -> None:
    project = await _project(db_session)

    response = await authenticated_api_client.request(
        method,
        url_builder(project.id, photo_id),  # type: ignore[operator]
        json={"decision": "keep"} if method == "put" else None,
    )

    assert response.status_code == 422


@pytest.mark.parametrize("url_builder", [_single_url, _group_url])
async def test_a_photo_of_another_project_is_a_404_and_is_never_written(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    url_builder: object,
) -> None:
    """SICHERHEIT (S7): Die Projektbindung steht ausgeschrieben. Ohne sie entschiede eine Aufnahme
    des einen Projekts ueber den abfliessenden Bestand eines anderen."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    fremd_winner, fremd_losers = await _star(db_session, other, 3, prefix="f")

    response = await authenticated_api_client.put(
        url_builder(home.id, fremd_losers[0].id),  # type: ignore[operator]
        json={"decision": "discard"},
    )

    assert response.status_code == 404
    for unberuehrt in (fremd_winner, *fremd_losers):
        assert await _stored(db_session, unberuehrt.id) is None


@pytest.mark.parametrize("url_builder", [_single_url, _group_url])
async def test_a_photo_without_a_group_and_without_a_suggestion_is_a_404(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    url_builder: object,
) -> None:
    """SICHERHEIT (S10): Die Vorbedingung beider Wege heisst "Gruppe ODER offener Vorschlag".
    Trifft KEINES von beiden zu, bleibt es beim `404` - und es wird nichts geschrieben."""
    project = await _project(db_session)
    ohne_alles = await _photo(db_session, project, "ohne-alles.jpg")

    response = await authenticated_api_client.put(
        url_builder(project.id, ohne_alles.id),  # type: ignore[operator]
        json={"decision": "discard"},
    )

    assert response.status_code == 404
    assert await _stored(db_session, ohne_alles.id) is None


async def test_a_low_quality_suggestion_is_decidable_on_the_single_path(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SPEC 0525, ERWEITERTE VORBEDINGUNG (S10, bewusst benannte Erwartungsaenderung): Der
    Einzelweg nimmt auch die Unschaerfe-Ablehnung an, die in KEINEM Stern liegt - die
    Detailansicht der Ausschuss-Uebersicht entscheidet genau dort.

    Die Antwort ist der leere Gruppenstand (AK6), kein `404`: Der Aufruf hat eine Entscheidung
    getragen, und die Oberflaeche schreibt ihn unmittelbar fort. Die geschriebene Zeile ist der
    Beweis, dass der Weg wirklich gegangen wurde."""
    project = await _project(db_session)
    unscharf = await _photo(
        db_session, project, "unscharf.jpg", suggested_status=RatingStatus.REJECTED
    )

    response = await authenticated_api_client.put(
        _single_url(project.id, unscharf.id), json={"decision": "discard"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "position": 0,
        "total": 0,
        "previous_photo_id": None,
        "next_photo_id": None,
        "span_seconds": 0,
    }
    assert await _stored(db_session, unscharf.id) == DuplicateDecision.DISCARD


async def test_an_ineffective_keep_on_a_low_quality_suggestion_is_accepted(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S10), DIE ZUSAGE: Ein `keep` auf eine Unschaerfe-Ablehnung ohne Gruppe ist
    wirkungslos - der Server weist es trotzdem NICHT ab (Auflage S4 der Spec 0486).

    Die Anzeige versteckt den Knopf; kaeme der Aufruf trotzdem, entstuende sonst eine zweite Regel
    neben ADR 0104 Punkt 3 und ein Widerspruch zum gruppenweiten Weg, der dieselbe Zeile fuer
    dasselbe Mitglied schreibt. Der Schaden bliebe sichtbar, aber begrenzt: Die Aufnahme verlaesst
    den Homeserver nicht."""
    project = await _project(db_session)
    unscharf = await _photo(
        db_session, project, "unscharf.jpg", suggested_status=RatingStatus.REJECTED
    )

    response = await authenticated_api_client.put(
        _single_url(project.id, unscharf.id), json={"decision": "keep"}
    )

    assert response.status_code == 200
    assert await _stored(db_session, unscharf.id) == DuplicateDecision.KEEP


async def test_a_low_quality_suggestion_has_no_group_path(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der GRUPPENWEITE Weg bleibt unveraendert: Die erweiterte Vorbedingung gilt nur fuer den
    Einzelweg (S10). Ein `None` als Gruppenpraedikat traefe jede nicht aussortierte Aufnahme des
    Projekts - hier ist die Aufnahme gar nicht im Stern, also `404` vor jedem Schreiben."""
    project = await _project(db_session)
    unscharf = await _photo(
        db_session, project, "unscharf.jpg", suggested_status=RatingStatus.REJECTED
    )

    response = await authenticated_api_client.put(
        _group_url(project.id, unscharf.id), json={"decision": "keep"}
    )

    assert response.status_code == 404
    assert await _stored(db_session, unscharf.id) is None


async def test_both_write_paths_answer_in_the_same_form_as_the_read_path(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """GEPRUEFT ueber die Gleichheit der Antwortstruktur, nicht ueber vier getrennt
    hingeschriebene Feldlisten: Die Oberflaeche schreibt den Rueckgabewert unmittelbar fort, und
    eine abweichende Form faellt sonst erst in der Ansicht auf."""
    project = await _project(db_session)
    winner, _losers = await _star(db_session, project, 3)

    # Reihenfolge so gewaehlt, dass alle vier Aufrufe DENSELBEN Zustand beschreiben: Der
    # Gruppenweg setzt alles auf `keep`, der Einzelweg danach denselben Wert auf ein Mitglied, der
    # Gruppenabschluss findet keinen offenen Vorschlag mehr, und der Lesepfad liest ihn ab. Ein
    # Formunterschied ist damit der einzige moegliche Unterschied.
    gruppe = await authenticated_api_client.put(
        _group_url(project.id, winner.id), json={"decision": "keep"}
    )
    einzeln = await authenticated_api_client.put(
        _single_url(project.id, winner.id), json={"decision": "keep"}
    )
    abgeschlossen = await authenticated_api_client.post(_confirm_url(project.id, winner.id))
    gelesen = await authenticated_api_client.get(
        f"/projects/{project.id}/duplicate-groups/{winner.id}"
    )

    assert einzeln.json() == gruppe.json() == abgeschlossen.json() == gelesen.json()


# ------------------------------------------------------------------------------------------
# Der erneute Lauf (AK12)
# ------------------------------------------------------------------------------------------


async def test_a_decision_survives_an_unchanged_rescoring(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK12: `run_project_scoring` setzt `duplicate_of`, `cluster_key` und `suggested_status`
    zurueck und fasst `photo_duplicate_decisions` nicht an. Das folgt ohne durchsetzenden Code -
    und wird hier festgeschrieben, damit es nicht unbemerkt verlorengeht."""
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)
    await authenticated_api_client.put(
        _single_url(project.id, losers[0].id), json={"decision": "keep"}
    )

    # Der Neulauf in seiner fuer diese Zusage wesentlichen Wirkung: die drei Felder fallen zurueck
    # und werden gleich wieder gesetzt. Ein vollstaendiger `run_project_scoring` braeuchte
    # Bilddateien und pruefte hier nichts zusaetzlich.
    for score in (await db_session.execute(select(PhotoScore))).scalars():
        score.duplicate_of = None
        score.cluster_key = None
        score.suggested_status = None
    await db_session.commit()
    for loser in losers:
        score = (
            await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == loser.id))
        ).scalar_one()
        score.duplicate_of = winner.id
        score.suggested_status = RatingStatus.REJECTED
    await db_session.commit()

    assert await _stored(db_session, losers[0].id) == DuplicateDecision.KEEP
    body = (
        await authenticated_api_client.get(f"/projects/{project.id}/duplicate-groups/{winner.id}")
    ).json()
    assert {item["photo"]["id"]: item["effective_decision"] for item in body["items"]}[
        losers[0].id
    ] == "keep"


async def test_a_stale_keep_becomes_ineffective_while_a_stale_discard_keeps_working(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """DIE VERALTETE ENTSCHEIDUNG, beide Haelften in einem Fall. Nach einem Neulauf, in dem die
    Aufnahmen kein Duplikat mehr sind, wirkt ein altes `discard` weiter und entfernt sie dauerhaft
    aus dem Ueberlebendenbestand, waehrend ein altes `keep` von selbst wirkungslos wird (S3).

    Beides ist Folge der Architektur und wird festgeschrieben, damit es nicht als Bug
    wiederentdeckt wird - und weil die `keep`-Haelfte genau das ist, was eine dauerhafte,
    unsichtbare Ausnahme vom Ausschuss-Gate verhindert."""
    project = await _project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    winner, losers = await _star(db_session, project, 3)
    await authenticated_api_client.put(
        _single_url(project.id, losers[0].id), json={"decision": "keep"}
    )
    await authenticated_api_client.put(
        _single_url(project.id, losers[1].id), json={"decision": "discard"}
    )

    # Der Neulauf erkennt keine Duplikate mehr: `duplicate_of` und `suggested_status` fallen weg.
    for score in (await db_session.execute(select(PhotoScore))).scalars():
        score.duplicate_of = None
        score.suggested_status = None
    await db_session.commit()

    behalten_id, verworfen_id, gewinner_id = losers[0].id, losers[1].id, winner.id
    projekt_id = project.id
    # Die Testsitzung ist DIESELBE, die auch der Endpunkt benutzt, und sie laeuft mit
    # `expire_on_commit=False` (db.py). Ein bereits geladenes `Photo` behielte darin seine alte
    # `duplicate_decision`, und ein eager Loader ueberschreibt einen schon geladenen Zustand nicht.
    # Im Betrieb stellt sich die Frage nicht - jede Anfrage bekommt eine frische Sitzung -, hier
    # ist das Verfallenlassen die getreue Nachbildung davon.
    db_session.expire_all()

    body = (await authenticated_api_client.get(f"/projects/{projekt_id}/photos")).json()
    ueberlebende = {
        item["id"]
        for item in body["items"]
        if any(
            eintrag["phase"] == "remote_category" and eintrag["status"] != "not_candidate"
            for eintrag in item["cloud_vision_status"]
        )
    }

    # Das alte `keep` ist wirkungslos geworden - die Aufnahme steht genau so da wie ohne
    # Entscheidung, nicht schlechter.
    assert behalten_id in ueberlebende
    assert gewinner_id in ueberlebende
    # Das alte `discard` wirkt weiter.
    assert verworfen_id not in ueberlebende
    # Die Gruppe ist zerfallen: Die Vergleichsansicht antwortet `404`, die Zeilen bleiben liegen.
    assert (
        await authenticated_api_client.get(f"/projects/{projekt_id}/duplicate-groups/{gewinner_id}")
    ).status_code == 404
    assert await _stored(db_session, behalten_id) == DuplicateDecision.KEEP
    assert await _stored(db_session, verworfen_id) == DuplicateDecision.DISCARD


# ------------------------------------------------------------------------------------------
# Der Gruppenabschluss (Spec 0533, A9/A14, Auflagen S1-S7)
# ------------------------------------------------------------------------------------------


async def _decide(session: AsyncSession, photo: Photo, decision: DuplicateDecision) -> None:
    session.add(PhotoDuplicateDecision(photo_id=photo.id, decision=decision))
    await session.commit()


async def _all_rows(session: AsyncSession) -> dict[int, DuplicateDecision]:
    rows = await session.execute(
        select(PhotoDuplicateDecision.photo_id, PhotoDuplicateDecision.decision)
    )
    return {photo_id: decision for photo_id, decision in rows.tuples()}


async def _successful_run(session: AsyncSession, project: Project) -> ScoringRun:
    run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS, started_at=_BASE)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


@contextmanager
def _recorded_statements() -> Iterator[list[str]]:
    """Die TATSAECHLICH abgesetzten Anweisungen (Muster `test_api_cameras.py`)."""
    statements: list[str] = []

    def _listener(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        statements.append(statement)

    event.listen(Engine, "before_cursor_execute", _listener)
    try:
        yield statements
    finally:
        event.remove(Engine, "before_cursor_execute", _listener)


async def test_the_group_confirm_requires_a_token(api_client: httpx.AsyncClient) -> None:
    """SICHERHEIT (S6): eigener, pfadbenannter 401-Fall neben Router-Dependency und
    Router-Iteration in `test_auth_guard.py`."""
    response = await api_client.post(_confirm_url(1, 1))

    assert response.status_code == 401


async def test_an_unknown_project_is_a_404_for_the_group_confirm(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.post(_confirm_url(999_999, 1))

    assert response.status_code == 404
    assert "999999" not in response.text


async def test_the_group_confirm_resolves_the_group_before_writing(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S1): Ohne Gruppe ist die Antwort `404`, BEVOR geschrieben wird - auch fuer ein
    Foto mit offenem Vorschlag. `member_ids_of(None, links)` liefert jedes Foto ohne
    `duplicate_of`; zusammen mit dem offenen Vorschlag schriebe ein Aufruf auf ein einzelnes
    unscharfes Foto sonst `discard` auf jede Unschaerfe-Ablehnung des Projekts."""
    project = await _project(db_session)
    erstes = await _photo(
        db_session, project, "unscharf-1.jpg", suggested_status=RatingStatus.REJECTED
    )
    await _photo(
        db_session, project, "unscharf-2.jpg", seconds=1, suggested_status=RatingStatus.REJECTED
    )

    response = await authenticated_api_client.post(_confirm_url(project.id, erstes.id))

    assert response.status_code == 404
    assert await _all_rows(db_session) == {}


async def test_a_single_low_quality_photo_beside_a_group_is_a_404_for_the_group_confirm(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S1), der `None`-Repraesentant neben einer echten Gruppe: Auch dann entsteht
    projektweit keine einzige Zeile."""
    project = await _project(db_session)
    await _star(db_session, project, 3)
    unscharf = await _photo(
        db_session, project, "unscharf.jpg", seconds=50, suggested_status=RatingStatus.REJECTED
    )

    response = await authenticated_api_client.post(_confirm_url(project.id, unscharf.id))

    assert response.status_code == 404
    assert await _all_rows(db_session) == {}


async def test_the_group_confirm_writes_discard_only_for_the_open_suggestions_of_this_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S2/S3): Mitgliedschaft, Projektbindung und offener Vorschlag in EINER Anweisung
    mit innerem Join auf `PhotoScore`. Danach traegt allein der offene Verlierer `discard`: Der
    Gewinner ohne Vorschlag bekommt keine Zeile (das unterscheidet den Abschluss vom untersagten
    Festschreiben aus dem Client), `keep` bleibt `keep`, und die zweite Gruppe sowie das zweite
    Projekt bleiben leer. Ohne den Join wuerde die Bedingung fuer jedes Mitglied wahr, sobald
    irgendein Foto der Instanz einen offenen Vorschlag traegt."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    winner, [offen, behalten] = await _star(db_session, home, 3)
    await _decide(db_session, behalten, DuplicateDecision.KEEP)
    _zweite_gruppe, zweite_verlierer = await _star(
        db_session, home, 2, first_second=100, prefix="b"
    )
    _fremd_winner, fremd_verlierer = await _star(db_session, other, 2, prefix="f")
    ids = {
        "winner": winner.id,
        "offen": offen.id,
        "behalten": behalten.id,
        "zweite": zweite_verlierer[0].id,
        "fremd": fremd_verlierer[0].id,
    }

    response = await authenticated_api_client.post(_confirm_url(home.id, winner.id))

    assert response.status_code == 200
    assert await _all_rows(db_session) == {
        ids["offen"]: DuplicateDecision.DISCARD,
        ids["behalten"]: DuplicateDecision.KEEP,
    }


async def test_a_photo_of_another_project_is_a_404_for_the_group_confirm(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S2): Eine Foto-Id eines fremden Projekts loest sich in der projektbegrenzten
    Kantenliste nicht auf - `404`, ohne den Wert zu spiegeln, und in keinem Projekt eine Zeile."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    await _star(db_session, home, 2)
    _fremd_winner, fremd_verlierer = await _star(db_session, other, 3, prefix="f")
    fremde_id = fremd_verlierer[0].id

    response = await authenticated_api_client.post(_confirm_url(home.id, fremde_id))

    assert response.status_code == 404
    assert str(fremde_id) not in response.text
    assert await _all_rows(db_session) == {}


async def test_a_foreign_photo_pointing_into_the_group_is_never_confirmed(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S2), die scharfe Form: Eine fremde Aufnahme mit offenem Vorschlag und
    `duplicate_of` auf den eigenen Gewinner bekommt keine Zeile."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    winner, [eigener] = await _star(db_session, home, 2)
    fremd = await _photo(
        db_session,
        other,
        "fremd.jpg",
        seconds=5,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )
    eigener_id, fremd_id = eigener.id, fremd.id

    response = await authenticated_api_client.post(_confirm_url(home.id, winner.id))

    assert response.status_code == 200
    assert await _all_rows(db_session) == {eigener_id: DuplicateDecision.DISCARD}
    assert fremd_id not in await _all_rows(db_session)


async def test_the_group_confirm_reads_no_body(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S4): Weder Menge noch Wert kommen vom Aufrufer. Ein Koerper mit Id-Liste und
    `keep` wird nie gelesen: Das genannte Foto ausserhalb der Gruppe bleibt ohne Zeile, und
    nirgends entsteht ein `keep`."""
    project = await _project(db_session)
    winner, [verlierer] = await _star(db_session, project, 2)
    ausserhalb = await _photo(
        db_session, project, "unscharf.jpg", seconds=50, suggested_status=RatingStatus.REJECTED
    )
    verlierer_id, ausserhalb_id = verlierer.id, ausserhalb.id

    response = await authenticated_api_client.post(
        _confirm_url(project.id, winner.id),
        json={"photo_ids": [ausserhalb_id], "decision": "keep"},
    )

    assert response.status_code == 200
    assert await _all_rows(db_session) == {verlierer_id: DuplicateDecision.DISCARD}


async def test_the_group_confirm_never_issues_a_delete(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S3): nur einfuegen. Ein vorangestelltes `DELETE` raeumte eine im Wettlauf
    committete `keep`-Zeile des anderen Nutzers weg und ersetzte seine Handlung durch
    `discard`."""
    project = await _project(db_session)
    winner, [_offen, behalten] = await _star(db_session, project, 3)
    await _decide(db_session, behalten, DuplicateDecision.KEEP)

    with _recorded_statements() as statements:
        response = await authenticated_api_client.post(_confirm_url(project.id, winner.id))

    assert response.status_code == 200
    assert any(statement.lstrip().upper().startswith("INSERT") for statement in statements)
    assert not [s for s in statements if s.lstrip().upper().startswith("DELETE")]


async def test_a_concurrent_write_during_the_group_confirm_is_a_409_and_writes_nothing(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SICHERHEIT (S3): Zwischen Auswahl und Schreiben kann der andere Nutzer eine Zeile
    committen; der Primaerschluessel wirft. Das wird `409` mit vollstaendigem Rueckzug - keine
    Teilmenge der Gruppe bleibt geschrieben. Eingesetzt statt nachgestellt, mit Zaehler auf den
    betretenen Zweig (Muster des 409-Falls oben)."""
    project = await _project(db_session)
    winner, _losers = await _star(db_session, project, 4)
    projekt_id, winner_id = project.id, winner.id
    calls = {"count": 0}
    original_flush = AsyncSession.flush

    async def _always_failing(self: AsyncSession, *args: object, **kwargs: object) -> None:
        calls["count"] += 1
        raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))

    monkeypatch.setattr(AsyncSession, "flush", _always_failing)
    try:
        response = await authenticated_api_client.post(_confirm_url(projekt_id, winner_id))
    finally:
        monkeypatch.setattr(AsyncSession, "flush", original_flush)

    assert calls["count"] >= 1, "der IntegrityError-Zweig wurde gar nicht betreten"
    assert response.status_code == 409
    assert "erneut" in response.json()["detail"].lower()
    assert await _all_rows(db_session) == {}


async def test_the_group_confirm_is_idempotent(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Ein zweiter Aufruf findet keine offene Aufnahme mehr: `200` mit derselben Gruppe, gleiche
    Zeilenzahl, kein `409`."""
    project = await _project(db_session)
    winner, _losers = await _star(db_session, project, 3)

    erster = await authenticated_api_client.post(_confirm_url(project.id, winner.id))
    zeilen = await _all_rows(db_session)
    zweiter = await authenticated_api_client.post(_confirm_url(project.id, winner.id))

    assert erster.status_code == zweiter.status_code == 200
    assert zweiter.json() == erster.json()
    assert await _all_rows(db_session) == zeilen
    assert len(zeilen) == 2


async def test_the_group_confirm_never_sets_the_gate(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S5): Die einzige Gruppe ist abgeschlossen, danach gibt es keinen offenen
    Vorschlag mehr - und `gate_confirmed_at` bleibt trotzdem `NULL`. Setzte der Abschluss der
    letzten Gruppe das Gate, liefe der Cloud-Teilschritt ohne die projektweite Bestaetigung an."""
    project = await _project(db_session)
    run = await _successful_run(db_session, project)
    run_id, projekt_id = run.id, project.id
    winner, _losers = await _star(db_session, project, 3)

    response = await authenticated_api_client.post(_confirm_url(projekt_id, winner.id))
    uebersicht = (await authenticated_api_client.get(f"/projects/{projekt_id}/ausschuss")).json()

    assert response.status_code == 200
    assert uebersicht["open_count"] == 0
    db_session.expire_all()
    gate = (
        await db_session.execute(
            select(ScoringRun.gate_confirmed_at).where(ScoringRun.id == run_id)
        )
    ).scalar_one()
    assert gate is None


async def test_the_group_confirm_via_a_loser_writes_the_same_set_as_via_the_winner(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Die Gruppe ist ueber JEDES Mitglied erreichbar - der Abschluss auch. Zwei gleich gebaute
    Projekte, einmal ueber den Gewinner, einmal ueber einen Verlierer abgeschlossen."""
    ueber_gewinner = await _project(db_session, "Costa Rica")
    ueber_verlierer = await _project(db_session, "Island")
    winner_a, _ = await _star(db_session, ueber_gewinner, 3)
    _winner_b, losers_b = await _star(db_session, ueber_verlierer, 3)

    await authenticated_api_client.post(_confirm_url(ueber_gewinner.id, winner_a.id))
    await authenticated_api_client.post(_confirm_url(ueber_verlierer.id, losers_b[1].id))

    assert await _decided_paths(db_session, ueber_gewinner.id) == await _decided_paths(
        db_session, ueber_verlierer.id
    )
    assert len(await _decided_paths(db_session, ueber_gewinner.id)) == 2


async def _decided_paths(session: AsyncSession, project_id: int) -> set[tuple[str, str]]:
    rows = await session.execute(
        select(Photo.relative_path, PhotoDuplicateDecision.decision)
        .join(PhotoDuplicateDecision, PhotoDuplicateDecision.photo_id == Photo.id)
        .where(Photo.project_id == project_id)
    )
    return {(path, str(decision)) for path, decision in rows.tuples()}


async def test_the_group_confirm_changes_no_displayed_state_and_no_standing(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A9/A1/A12: Ein offener Vorschlag zeigt schon `discard` - der Abschluss schreibt den
    angezeigten Zustand fest, statt ihn zu aendern. Zustand je Mitglied, Position, Gesamtzahl und
    Nachbarn sind vor und nach dem Abschluss gleich, ueber den Schreibweg des Produkts; die
    abgeschlossene Gruppe bleibt erreichbar, und die Nachbargruppe behaelt ihren Platz. Dabei ist
    der Gewinner mit Schaerfe-Ablehnung, der `discard` bekommt und "Ausschuss" bleibt."""
    project = await _project(db_session)
    unscharfer_gewinner = await _photo(
        db_session, project, "u-w.jpg", suggested_status=RatingStatus.REJECTED
    )
    await _photo(
        db_session,
        project,
        "u-v.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=unscharfer_gewinner.id,
    )
    nachbar, _ = await _star(db_session, project, 2, first_second=100, prefix="b")
    gruppe_url = f"/projects/{project.id}/duplicate-groups/{unscharfer_gewinner.id}"
    nachbar_url = f"/projects/{project.id}/duplicate-groups/{nachbar.id}"
    confirm_url = _confirm_url(project.id, unscharfer_gewinner.id)
    gewinner_id = unscharfer_gewinner.id

    vorher = (await authenticated_api_client.get(gruppe_url)).json()
    nachbar_vorher = (await authenticated_api_client.get(nachbar_url)).json()
    antwort = (await authenticated_api_client.post(confirm_url)).json()
    db_session.expire_all()
    nachher = await authenticated_api_client.get(gruppe_url)
    nachbar_nachher = (await authenticated_api_client.get(nachbar_url)).json()

    def zustand(body: dict[str, Any]) -> list[tuple[int, str]]:
        return [(item["photo"]["id"], item["effective_decision"]) for item in body["items"]]

    def stellung(body: dict[str, Any]) -> tuple[Any, ...]:
        return (body["position"], body["total"], body["previous_photo_id"], body["next_photo_id"])

    assert nachher.status_code == 200
    assert zustand(vorher) == zustand(antwort) == zustand(nachher.json())
    assert stellung(vorher) == stellung(antwort) == stellung(nachher.json())
    assert stellung(nachbar_vorher) == stellung(nachbar_nachher)
    assert await _stored(db_session, gewinner_id) == DuplicateDecision.DISCARD
    assert dict(zustand(nachher.json()))[gewinner_id] == "discard"


async def test_the_open_count_drops_by_exactly_the_open_suggestions_of_the_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    winner, _ = await _star(db_session, project, 4)
    await _star(db_session, project, 3, first_second=100, prefix="b")
    uebersicht_url = f"/projects/{project.id}/ausschuss"
    confirm_url = _confirm_url(project.id, winner.id)

    vorher = (await authenticated_api_client.get(uebersicht_url)).json()["open_count"]
    await authenticated_api_client.post(confirm_url)
    db_session.expire_all()
    nachher = (await authenticated_api_client.get(uebersicht_url)).json()["open_count"]

    assert (vorher, nachher) == (5, 2)


async def test_the_group_confirm_has_the_effect_the_gate_confirm_would_have_had(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A14 als ZWILLINGSPROJEKT-DIFFERENZ: P1 schliesst eine Gruppe ab und danach den
    Ausschuss-Schritt, P2 nur den Ausschuss-Schritt. Die geschriebenen Mengen (`relative_path`,
    `decision`) sind gleich, und kein `409` tritt auf. Einzelne Erwartungswerte bestuenden auch
    dann, wenn beide Wege auseinanderliefen und beide Erwartungen mitgezogen wuerden."""
    zwillinge = [await _project(db_session, "Costa Rica"), await _project(db_session, "Island")]
    winner_ids: list[int] = []
    for zwilling in zwillinge:
        await _successful_run(db_session, zwilling)
        winner, [_offen, behalten] = await _star(db_session, zwilling, 3)
        await _decide(db_session, behalten, DuplicateDecision.KEEP)
        await _star(db_session, zwilling, 2, first_second=100, prefix="b")
        await _photo(
            db_session,
            zwilling,
            "unscharf.jpg",
            seconds=500,
            suggested_status=RatingStatus.REJECTED,
        )
        winner_ids.append(winner.id)
    p1, p2 = (zwilling.id for zwilling in zwillinge)

    abschluss = await authenticated_api_client.post(_confirm_url(p1, winner_ids[0]))
    gate_p1 = await authenticated_api_client.post(f"/projects/{p1}/confirm-ausschuss-gate")
    gate_p2 = await authenticated_api_client.post(f"/projects/{p2}/confirm-ausschuss-gate")

    assert [abschluss.status_code, gate_p1.status_code, gate_p2.status_code] == [200, 200, 200]
    assert await _decided_paths(db_session, p1) == await _decided_paths(db_session, p2)
    assert len(await _decided_paths(db_session, p1)) == 4
