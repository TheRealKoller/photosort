"""`GET /projects/{project_id}/duplicate-groups/{photo_id}` - der Lesepfad der Vergleichsansicht.

Die Gruppe ist ABGELEITET (ADR 0104 Punkt 1): Jeder Aufruf bildet den Stern zur Lesezeit neu. Es
gibt keine Gruppen-Id, und dieselbe Gruppe ist deshalb ueber JEDES ihrer Mitglieder erreichbar -
das ist hier eine gepruefte Zusage, kein Nebeneffekt.

`404` DECKT VIER FAELLE UND UNTERSCHEIDET SIE NICHT: unbekannte Id, fremdes Projekt, Foto ohne
Gruppe und Vorschlag aus geringer Bildqualitaet (AK13). Ein Aufruf darf nicht ablesen koennen,
welcher davon vorliegt - sonst waere die Antwort ein Auskunftsmittel ueber fremde Bestaende.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.photos import MAX_QUERY_POSITION
from photosort.models import (
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    RatingStatus,
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
    taken_at: datetime | None = None,
    with_score: bool = True,
    suggested_status: RatingStatus | None = None,
    duplicate_of: int | None = None,
    decision: DuplicateDecision | None = None,
) -> Photo:
    moment = taken_at if taken_at is not None else _BASE + timedelta(seconds=seconds)
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
    if with_score:
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
    if decision is not None:
        session.add(PhotoDuplicateDecision(photo_id=photo.id, decision=decision))
    await session.commit()
    return photo


async def _star(
    session: AsyncSession, project: Project, size: int, *, first_second: int = 0, prefix: str = "g"
) -> tuple[Photo, list[Photo]]:
    """Der Gewinner plus `size - 1` Verlierer, die auf ihn zeigen. Der Gewinner traegt bewusst
    KEINE Vorschlagszeile - er ist der Ausschuss-Ueberlebende der Serie."""
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


def _url(project_id: int, photo_id: int) -> str:
    return f"/projects/{project_id}/duplicate-groups/{photo_id}"


# ------------------------------------------------------------------------------------------
# Erreichbarkeit und Gruppenbegriff (AK1)
# ------------------------------------------------------------------------------------------


async def test_the_endpoint_requires_a_token(api_client: httpx.AsyncClient) -> None:
    """Pfadbenannter 401-Fall: `photos.router` traegt bewusst KEINE router-weite
    `dependencies`-Liste, ein Endpunkt ohne ausgeschriebene Auth-Dependency waere dort still
    oeffentlich."""
    response = await api_client.get(_url(1, 1))

    assert response.status_code == 401


async def test_the_group_holds_the_representative_and_everyone_pointing_at_it(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)

    response = await authenticated_api_client.get(_url(project.id, losers[0].id))

    assert response.status_code == 200
    body = response.json()
    assert [item["photo"]["id"] for item in body["items"]] == [
        winner.id,
        losers[0].id,
        losers[1].id,
    ]


async def test_every_member_reaches_the_same_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Die Gruppe hat keine eigene Id - sie ist ueber jedes Mitglied erreichbar, den Gewinner
    eingeschlossen. Der Gewinner traegt dabei selbst keine Vorschlagszeile (AK1)."""
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, 3)

    antworten = [
        (await authenticated_api_client.get(_url(project.id, member.id))).json()
        for member in (winner, *losers)
    ]

    assert all(antwort == antworten[0] for antwort in antworten)


@pytest.mark.parametrize("size", [2, 3, 5])
async def test_a_star_of_any_size_returns_exactly_its_members(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, size: int
) -> None:
    project = await _project(db_session)
    winner, losers = await _star(db_session, project, size)

    body = (await authenticated_api_client.get(_url(project.id, winner.id))).json()

    assert len(body["items"]) == size
    assert {item["photo"]["id"] for item in body["items"]} == {
        winner.id,
        *(loser.id for loser in losers),
    }


async def test_the_members_are_ordered_by_taken_at_then_id(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK2 als vollstaendige Id-Folge bei durchgehend gleichem `taken_at` - Serienaufnahmen tragen
    haeufig denselben Zeitstempel, und ohne den Zweitschluessel waere die Reihenfolge nicht
    reproduzierbar."""
    project = await _project(db_session)
    gleichzeitig = _BASE
    winner = await _photo(db_session, project, "w.jpg", taken_at=gleichzeitig)
    zweiter = await _photo(
        db_session,
        project,
        "b.jpg",
        taken_at=gleichzeitig,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )
    dritter = await _photo(
        db_session,
        project,
        "c.jpg",
        taken_at=gleichzeitig,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )

    body = (await authenticated_api_client.get(_url(project.id, winner.id))).json()

    assert [item["photo"]["id"] for item in body["items"]] == [winner.id, zweiter.id, dritter.id]


# ------------------------------------------------------------------------------------------
# Die vier 404-Faelle
# ------------------------------------------------------------------------------------------


async def test_an_unknown_photo_is_a_404(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)

    response = await authenticated_api_client.get(_url(project.id, 999_999))

    assert response.status_code == 404


async def test_a_photo_without_a_group_is_a_404(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der entartete Fall `n = 1`: kein `duplicate_of`, niemand zeigt darauf. Zugleich die
    Durchsetzung von "nur fuer als Duplikat erkannte Aufnahmen"."""
    project = await _project(db_session)
    einzeln = await _photo(db_session, project, "einzeln.jpg")

    response = await authenticated_api_client.get(_url(project.id, einzeln.id))

    assert response.status_code == 404


async def test_a_low_quality_suggestion_is_a_404(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK13: Fuer Vorschlaege wegen geringer Bildqualitaet aendert sich nichts. Eine solche
    Aufnahme traegt `suggested_status = REJECTED` OHNE `duplicate_of` - sie hat keine Gruppe, und
    der Vergleich hat ihr nichts zu zeigen."""
    project = await _project(db_session)
    unscharf = await _photo(
        db_session, project, "unscharf.jpg", suggested_status=RatingStatus.REJECTED
    )

    response = await authenticated_api_client.get(_url(project.id, unscharf.id))

    assert response.status_code == 404


async def test_a_photo_of_another_project_is_a_404_that_reveals_nothing(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S7): Die Antwort spiegelt den Wert nicht und ist von der eines unbekannten
    Fotos nicht zu unterscheiden."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    _fremder_gewinner, fremde_verlierer = await _star(db_session, other, 3, prefix="f")

    fremd = await authenticated_api_client.get(_url(home.id, fremde_verlierer[0].id))
    unbekannt = await authenticated_api_client.get(_url(home.id, 999_999))

    assert fremd.status_code == 404
    assert fremd.json() == unbekannt.json()


async def test_a_foreign_photo_pointing_into_this_project_never_joins_the_group(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S7) in der SCHARFEN Form: Nur diese Datenlage deckt ein fehlendes
    `Photo.project_id`-Praedikat auf - der blosse 404-Fall bestuende auch ohne es.
    `photo_scores.duplicate_of` zeigt auf `photos.id` ohne Projektbedingung."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    winner, losers = await _star(db_session, home, 2)
    fremder_verlierer = await _photo(
        db_session,
        other,
        "fremd.jpg",
        seconds=5,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )

    body = (await authenticated_api_client.get(_url(home.id, winner.id))).json()

    assert [item["photo"]["id"] for item in body["items"]] == [winner.id, losers[0].id]
    assert fremder_verlierer.id not in {item["photo"]["id"] for item in body["items"]}


async def test_an_unknown_project_is_a_404(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get(_url(999_999, 1))

    assert response.status_code == 404


@pytest.mark.parametrize("photo_id", [0, -1, MAX_QUERY_POSITION + 1])
async def test_a_photo_id_outside_the_declared_bounds_is_a_422(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, photo_id: int
) -> None:
    """SICHERHEIT (S6): Ein unbeschraenkter Pydantic-`int` erreicht die Datenbank und wird
    jenseits von 2^63 zu `500` statt `404`."""
    project = await _project(db_session)

    response = await authenticated_api_client.get(_url(project.id, photo_id))

    assert response.status_code == 422


# ------------------------------------------------------------------------------------------
# Entscheidung und Gruppenzaehler
# ------------------------------------------------------------------------------------------


async def test_each_item_carries_its_own_decision_or_null(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    winner = await _photo(db_session, project, "w.jpg", decision=DuplicateDecision.KEEP)
    verworfen = await _photo(
        db_session,
        project,
        "b.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
        decision=DuplicateDecision.DISCARD,
    )
    offen = await _photo(
        db_session,
        project,
        "c.jpg",
        seconds=2,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )

    body = (await authenticated_api_client.get(_url(project.id, winner.id))).json()

    assert {item["photo"]["id"]: item["decision"] for item in body["items"]} == {
        winner.id: "keep",
        verworfen.id: "discard",
        offen.id: None,
    }


async def test_the_counter_is_one_based_over_the_open_groups(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    erste, _ = await _star(db_session, project, 2, first_second=0, prefix="a")
    zweite, _ = await _star(db_session, project, 2, first_second=100, prefix="b")
    dritte, _ = await _star(db_session, project, 2, first_second=200, prefix="c")

    zaehler = {}
    for stern in (erste, zweite, dritte):
        body = (await authenticated_api_client.get(_url(project.id, stern.id))).json()
        zaehler[stern.id] = (body["position"], body["total"])

    assert zaehler == {erste.id: (1, 3), zweite.id: (2, 3), dritte.id: (3, 3)}


async def test_a_finished_group_drops_out_of_the_reference_set_of_the_others(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK10: Der Zaehler beschreibt die VERBLEIBENDE Arbeit und laeuft auf null zu. Dass sich
    `position` verschiebt, sobald eine Gruppe abgeschlossen wird, ist die bewusst getragene
    Folge."""
    project = await _project(db_session)
    fertig_winner = await _photo(db_session, project, "a-w.jpg", decision=DuplicateDecision.KEEP)
    await _photo(
        db_session,
        project,
        "a-v.jpg",
        seconds=1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=fertig_winner.id,
        decision=DuplicateDecision.DISCARD,
    )
    offen_winner, _ = await _star(db_session, project, 2, first_second=100, prefix="b")

    offen_body = (await authenticated_api_client.get(_url(project.id, offen_winner.id))).json()
    fertig_body = (await authenticated_api_client.get(_url(project.id, fertig_winner.id))).json()

    assert (offen_body["position"], offen_body["total"]) == (1, 1)
    # Die gerade angesehene Gruppe behaelt ihren Platz, auch wenn sie fertig ist - sonst liefe
    # die Zusage `1 <= position <= total` aus AK10 leer.
    assert (fertig_body["position"], fertig_body["total"]) == (1, 2)


# ------------------------------------------------------------------------------------------
# Die Form der Antwort
# ------------------------------------------------------------------------------------------


async def test_the_item_carries_an_unextended_photo_out(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`PhotoOut` wird WIEDERVERWENDET und nicht erweitert (ADR 0104): Die Entscheidung hat
    ausserhalb dieser Ansicht keine Rolle und stuende sonst als Feld auf jedem Lesepfad. Geprueft
    als Gleichheit der Feldmenge gegen die Fotoliste - ein zusaetzliches Feld faellt hier auf."""
    project = await _project(db_session)
    winner, _ = await _star(db_session, project, 2)

    gruppe = (await authenticated_api_client.get(_url(project.id, winner.id))).json()
    liste = (await authenticated_api_client.get(f"/projects/{project.id}/photos")).json()

    vom_vergleich = next(
        item["photo"] for item in gruppe["items"] if item["photo"]["id"] == winner.id
    )
    aus_der_liste = next(item for item in liste["items"] if item["id"] == winner.id)
    assert set(vom_vergleich) == set(aus_der_liste)
    assert set(gruppe["items"][0]) == {"photo", "decision"}
    assert set(gruppe) == {"items", "position", "total"}
