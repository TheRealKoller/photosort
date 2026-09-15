"""`GET /projects/{project_id}/duplicate-groups` - der Einstieg in den Durchgang.

Der Endpunkt sagt zwei Dinge: WIE VIELE Duplikat-Gruppen das Projekt hat und ueber welche Foto-Id
die ERSTE erreichbar ist. Mehr braucht keiner der beiden Einstiege - eine Liste aller Gruppen waere
eine zweite Quelle derselben Reihenfolge neben `position`/`total` (ADR 0111 Punkt 3).

`total` IST DIESELBE ZAHL wie in `DuplicateGroupOut`. Die Gleichheit steht hier als gepruefte
Zusage: Zwei getrennt gebildete Zahlen liefen auseinander, und der Einstieg fuehrte auf einen
Durchgang, dessen Zaehler eine andere Gesamtzahl nennt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.photos import MAX_QUERY_POSITION
from photosort.models import Photo, PhotoScore, Project, RatingStatus

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
    session: AsyncSession, project: Project, *, first_second: int, prefix: str
) -> Photo:
    winner = await _photo(session, project, f"{prefix}-w.jpg", seconds=first_second)
    await _photo(
        session,
        project,
        f"{prefix}-v.jpg",
        seconds=first_second + 1,
        suggested_status=RatingStatus.REJECTED,
        duplicate_of=winner.id,
    )
    return winner


def _index_url(project_id: int) -> str:
    return f"/projects/{project_id}/duplicate-groups"


def _group_url(project_id: int, photo_id: int) -> str:
    return f"/projects/{project_id}/duplicate-groups/{photo_id}"


# ------------------------------------------------------------------------------------------
# Auth und Eingabegrenzen (Auflage S1)
# ------------------------------------------------------------------------------------------


async def test_the_index_requires_a_token(api_client: httpx.AsyncClient) -> None:
    """EIGENER, PFADBENANNTER 401-FALL. `photos.router` traegt bewusst keine router-weite
    `dependencies`-Liste und keinen Vollstaendigkeitstest (Auflage S8 der Spec 0374) - ein
    vergessener `current_user`-Parameter waere dort still oeffentlich: keine 401, nur Daten."""
    response = await api_client.get(_index_url(1))

    assert response.status_code == 401


async def test_the_401_stands_before_any_statement_about_the_project(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Die 401 steht VOR jeder Aussage ueber das Projekt: Ein unbekanntes Projekt ist ohne Token
    von einem bekannten nicht zu unterscheiden."""
    project = await _project(db_session)

    bekannt = await api_client.get(_index_url(project.id))
    unbekannt = await api_client.get(_index_url(999_999))

    assert bekannt.status_code == unbekannt.status_code == 401
    assert bekannt.json() == unbekannt.json()


@pytest.mark.parametrize("project_id", [0, -1, MAX_QUERY_POSITION + 1])
async def test_a_project_id_outside_the_declared_bounds_is_a_422(
    authenticated_api_client: httpx.AsyncClient, project_id: int
) -> None:
    """SICHERHEIT (S1): Ein unbeschraenkter Pydantic-`int` erreicht die Datenbank und wird jenseits
    von 2^63 zu `500` statt `404`."""
    response = await authenticated_api_client.get(_index_url(project_id))

    assert response.status_code == 422


async def test_an_unknown_project_is_a_404_that_does_not_mirror_the_value(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get(_index_url(999_999))

    assert response.status_code == 404
    assert "999999" not in response.text


# ------------------------------------------------------------------------------------------
# Die Auskunft selbst (AK7, AK8)
# ------------------------------------------------------------------------------------------


async def test_a_project_without_any_group_answers_zero_and_no_first_photo(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK8: Es darf keinen Einstieg ins Leere geben - die Oberflaeche rendert ihn bei `total === 0`
    gar nicht. `first_photo_id` ist hier `null`, nicht die Id irgendeines Fotos: Ein Foto ohne
    Duplikat hat keine Gruppe, und der Vergleich antwortete darauf `404`."""
    project = await _project(db_session)
    await _photo(db_session, project, "einzeln.jpg")

    body = (await authenticated_api_client.get(_index_url(project.id))).json()

    assert body == {"total": 0, "first_photo_id": None}


async def test_the_first_photo_id_reaches_the_first_group_of_the_run(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`first_photo_id` wird NICHT gegen eine abgeschriebene Id geprueft, sondern ueber den Abruf:
    Die Gruppe dazu steht auf `position == 1` und hat keinen Vorgaenger. Eine Umsetzung, die
    irgendein Sternmitglied nennt, faellt genau daran auf."""
    project = await _project(db_session)
    await _star(db_session, project, first_second=200, prefix="c")
    await _star(db_session, project, first_second=0, prefix="a")
    await _star(db_session, project, first_second=100, prefix="b")

    index = (await authenticated_api_client.get(_index_url(project.id))).json()
    gruppe = (
        await authenticated_api_client.get(_group_url(project.id, index["first_photo_id"]))
    ).json()

    assert gruppe["position"] == 1
    assert gruppe["previous_photo_id"] is None


async def test_the_total_is_the_same_number_as_in_the_group_answer(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Als GLEICHHEIT zweier Beobachtungen ueber demselben Bestand, mit Gegenprobe gegen die
    selbsterfuellende Variante: Zwei Nullen waeren ebenfalls gleich."""
    project = await _project(db_session)
    await _star(db_session, project, first_second=0, prefix="a")
    await _star(db_session, project, first_second=100, prefix="b")
    await _star(db_session, project, first_second=200, prefix="c")

    index = (await authenticated_api_client.get(_index_url(project.id))).json()
    gruppe = (
        await authenticated_api_client.get(_group_url(project.id, index["first_photo_id"]))
    ).json()

    assert index["total"] == gruppe["total"]
    assert index["total"] == 3


async def test_a_fully_decided_project_still_names_its_groups(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """AK6 auch hier: Der Einstieg fuehrt weiterhin zur ersten Gruppe, auch wenn alles entschieden
    ist. Ein Index, der nur die offenen zaehlte, liesse den Durchgang nach der letzten Entscheidung
    verschwinden - und mit ihm den Weg zurueck."""
    project = await _project(db_session)
    erste = await _star(db_session, project, first_second=0, prefix="a")
    await _star(db_session, project, first_second=100, prefix="b")

    for anker in (erste,):
        entschieden = await authenticated_api_client.put(
            f"/projects/{project.id}/duplicate-groups/{anker.id}/decision",
            json={"decision": "discard"},
        )
        assert entschieden.status_code == 200

    body = (await authenticated_api_client.get(_index_url(project.id))).json()

    assert body == {"total": 2, "first_photo_id": erste.id}


async def test_a_group_of_another_project_is_never_counted(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SICHERHEIT (S6): `first_photo_id` stammt aus derselben projektbegrenzten Kantenliste wie die
    Gruppe selbst, nie aus einer eigenen Abfrage auf `photo_scores` - dessen `duplicate_of` zeigt
    auf `photos.id` OHNE Projektbedingung. Ohne die Bindung nennte die Antwort Foto-Ids fremder
    Projekte, und der Durchgang endete an einer Gruppe, die es hier nicht gibt."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    eigene = await _star(db_session, home, first_second=0, prefix="a")
    fremde = await _star(db_session, other, first_second=0, prefix="f")

    body = (await authenticated_api_client.get(_index_url(home.id))).json()

    assert body == {"total": 1, "first_photo_id": eigene.id}
    assert body["first_photo_id"] != fremde.id


async def test_the_answer_carries_exactly_two_fields(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Als Gleichheit der Feldmenge: Die Antwort traegt KEIN `PhotoOut` und ist damit keine
    Funktion des anfragenden Nutzers - die Cache-Schluessel-Auflage S10 der Spec 0374 gilt fuer sie
    nicht. Ein spaeter angehaengtes `PhotoOut` faellt hier auf, bevor die Auflage stillschweigend
    wieder greifen muesste."""
    project = await _project(db_session)
    await _star(db_session, project, first_second=0, prefix="a")

    body = (await authenticated_api_client.get(_index_url(project.id))).json()

    assert set(body) == {"total", "first_photo_id"}
