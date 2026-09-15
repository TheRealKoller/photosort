"""Der Stern ueber `PhotoScore.duplicate_of` - Sternbildung, Mitglieder- und Gruppenreihenfolge.

Die Gruppe ist ABGELEITET und wird zur Lesezeit gebildet (ADR 0104 Punkt 1). Die Logik steht
deshalb als REINE Funktion ueber den geladenen Kanten, und nur das Laden selbst ist eine Abfrage -
sonst waeren Reihenfolge und Entartungsfall nur ueber einen aufgebauten Datenbestand pruefbar.

DER ENTARTETE FALL `n = 1` IST DER TRENNENDE: Ein Foto, auf das niemand zeigt und das selbst kein
`duplicate_of` traegt, ergibt KEINE Gruppe. Er deckt zugleich ein hartkodiertes "mindestens zwei"
und ein Mitzaehlen des Repraesentanten auf.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.duplicates import (
    DuplicateLink,
    GroupStanding,
    all_group_representative_ids,
    group_standing,
    load_duplicate_links,
    member_ids_of,
    representative_of,
)
from photosort.models import Photo, PhotoScore, Project

_BASE = datetime(2023, 5, 1, 12, 0, 0)


def _link(
    photo_id: int,
    duplicate_of: int | None = None,
    *,
    minutes: int = 0,
) -> DuplicateLink:
    return DuplicateLink(
        photo_id=photo_id,
        duplicate_of=duplicate_of,
        taken_at=_BASE + timedelta(minutes=minutes),
    )


def _star(size: int, *, representative_id: int = 10, first_minute: int = 0) -> list[DuplicateLink]:
    """Ein Stern mit `size` Mitgliedern: der Repraesentant plus `size - 1` Verlierer, die auf ihn
    zeigen. Bei `size == 1` bleibt der Repraesentant allein - und ist damit keiner."""
    links = [_link(representative_id, None, minutes=first_minute)]
    links.extend(
        _link(representative_id + offset, representative_id, minutes=first_minute + offset)
        for offset in range(1, size)
    )
    return links


# ------------------------------------------------------------------------------------------
# Sternbildung
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("size", [1, 2, 3, 5])
def test_a_loser_resolves_to_its_representative(size: int) -> None:
    links = _star(size)

    for link in links:
        if link.duplicate_of is None:
            continue
        assert representative_of(link.photo_id, links) == 10


@pytest.mark.parametrize("size", [2, 3, 5])
def test_the_representative_resolves_to_itself_as_soon_as_someone_points_at_it(size: int) -> None:
    links = _star(size)

    assert representative_of(10, links) == 10


def test_a_lone_photo_is_no_group_at_all() -> None:
    """DER trennende Fall (`n = 1`): Der Repraesentant steht in der Kantenliste, aber niemand zeigt
    auf ihn. Eine Umsetzung, die ihn mitzaehlt, oder eine, die "mindestens zwei" hartkodiert,
    faellt genau hier - und nur hier - auf."""
    links = _star(1)

    assert representative_of(10, links) is None


def test_an_unknown_photo_is_no_group_either() -> None:
    assert representative_of(999, _star(3)) is None


def test_a_pointer_leaving_the_loaded_set_is_no_group() -> None:
    """SICHERHEIT (S7): Die Kantenliste ist bereits auf das Projekt begrenzt. Ein `duplicate_of`,
    das aus ihr herauszeigt, wird deshalb NICHT aufgeloest - `photo_scores.duplicate_of` zeigt auf
    `photos.id` ohne Projektbedingung, und ohne diese Zurueckweisung entschiede eine Aufnahme des
    einen Projekts ueber den abfliessenden Bestand eines anderen."""
    links = [_link(7, 4242)]

    assert representative_of(7, links) is None


# ------------------------------------------------------------------------------------------
# Mitgliederreihenfolge (AK2)
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("size", [2, 3, 5])
def test_the_group_holds_the_representative_and_everyone_pointing_at_it(size: int) -> None:
    links = _star(size)

    assert member_ids_of(10, links) == list(range(10, 10 + size))


def test_the_members_are_ordered_by_taken_at_then_id_despite_a_shuffled_insert_order() -> None:
    """AK2 als VOLLSTAENDIGE Id-Folge, nicht als Mengengleichheit: Eine Umsetzung, die die
    Ladereihenfolge durchreicht, bestuende sonst."""
    links = [
        _link(30, 10, minutes=3),
        _link(10, None, minutes=1),
        _link(50, 10, minutes=0),
        _link(20, 10, minutes=2),
    ]

    assert member_ids_of(10, links) == [50, 10, 20, 30]


def test_a_tie_in_taken_at_is_broken_by_the_id_across_the_whole_group() -> None:
    """Serienaufnahmen tragen haeufig denselben Zeitstempel - bei durchgehendem Gleichstand traegt
    allein die Id die Reihenfolge, und ohne sie waere sie nicht reproduzierbar."""
    links = [
        _link(40, 10, minutes=0),
        _link(10, None, minutes=0),
        _link(25, 10, minutes=0),
        _link(31, 10, minutes=0),
    ]

    assert member_ids_of(10, links) == [10, 25, 31, 40]


def test_a_photo_of_another_star_never_joins_this_group() -> None:
    links = _star(3, representative_id=10) + _star(3, representative_id=20, first_minute=10)

    assert member_ids_of(10, links) == [10, 11, 12]
    assert member_ids_of(20, links) == [20, 21, 22]


# ------------------------------------------------------------------------------------------
# Gruppenreihenfolge, Zaehler und Nachbarn (AK5, AK6)
# ------------------------------------------------------------------------------------------


def _drei_gruppen() -> list[DuplicateLink]:
    return [
        _link(10, None, minutes=0),
        _link(11, 10, minutes=1),
        _link(20, None, minutes=5),
        _link(21, 20, minutes=6),
        _link(30, None, minutes=9),
        _link(31, 30, minutes=10),
    ]


def test_the_groups_are_ordered_by_the_earliest_taken_at_of_their_members() -> None:
    """VOLLSTAENDIGE Folge zugesichert. Massgeblich ist der frueheste Zeitpunkt der MITGLIEDER,
    nicht der des Repraesentanten: Der Gewinner einer Serie ist oft nicht die erste Aufnahme."""
    links = [
        _link(10, None, minutes=50),
        _link(11, 10, minutes=20),
        _link(20, None, minutes=30),
        _link(21, 20, minutes=31),
    ]

    assert all_group_representative_ids(links) == [10, 20]


def test_a_tie_between_two_groups_is_broken_by_the_representative_id() -> None:
    links = [
        _link(30, None, minutes=0),
        _link(31, 30, minutes=0),
        _link(10, None, minutes=0),
        _link(11, 10, minutes=0),
    ]

    assert all_group_representative_ids(links) == [10, 30]


def test_the_group_order_cannot_depend_on_any_decision() -> None:
    """AK6 als ERSATZ fuer die abgeloeste Zusage der Spec 0374 (AK10): Eine vollstaendig
    entschiedene Gruppe BLEIBT in der Liste, und die Position einer Gruppe verschiebt sich nicht
    dadurch, dass eine andere entschieden wird.

    Konstruktiv zugesichert statt fallweise geprueft: Die Kantenliste traegt gar keine
    Entscheidungsauskunft mehr, die Reihenfolge KANN also an keiner haengen. Die Feldmenge steht
    hier als Gleichheit - ein wieder eingefuehrtes `decided` faellt auf, bevor eine Verzweigung
    darauf entsteht. Die Wirkung ueber beide Schreibwege prueft
    `test_api_duplicate_groups.py::test_the_counter_stays_constant_while_another_group_is_decided`."""
    assert {feld.name for feld in fields(DuplicateLink)} == {
        "photo_id",
        "duplicate_of",
        "taken_at",
    }
    assert all_group_representative_ids(_drei_gruppen()) == [10, 20, 30]


def test_the_counter_is_one_based_and_names_the_place_among_all_groups() -> None:
    links = _drei_gruppen()

    assert [group_standing(rep, links) for rep in (10, 20, 30)] == [
        GroupStanding(position=1, total=3, previous_id=None, next_id=20),
        GroupStanding(position=2, total=3, previous_id=10, next_id=30),
        GroupStanding(position=3, total=3, previous_id=20, next_id=None),
    ]


def test_a_single_group_has_no_neighbours_at_all() -> None:
    """AK5 am Rand: Bei genau einer Gruppe ist WEDER vor NOCH zurueck bedienbar - und die Stellung
    steht trotzdem auf `(1, 1)` statt auf `(1, 0)`."""
    standing = group_standing(10, _star(3))

    assert standing == GroupStanding(position=1, total=1, previous_id=None, next_id=None)


def test_the_standing_of_an_unknown_representative_is_none() -> None:
    assert group_standing(999, _star(3)) is None


def test_following_next_id_visits_every_group_exactly_once_and_ends() -> None:
    """AK5, der Kettendurchlauf: Ein Durchgang vom Einstieg aus besucht JEDE Gruppe genau einmal
    und endet nach `total` Schritten.

    Die vollstaendig entschiedene Gruppe liegt dabei MITTEN in der Kette - sie wird nicht
    uebersprungen. Ohne den Durchlauf bestuende eine Umsetzung, die `next_id` je Gruppe plausibel,
    aber nicht kettenbildend besetzt (etwa immer den Nachbarn in der Ladereihenfolge)."""
    links = _drei_gruppen()
    geordnet = all_group_representative_ids(links)

    besucht: list[int] = []
    positionen: list[int] = []
    aktuell: int | None = geordnet[0]
    while aktuell is not None:
        standing = group_standing(aktuell, links)
        assert standing is not None
        besucht.append(aktuell)
        positionen.append(standing.position)
        aktuell = standing.next_id

    assert besucht == geordnet
    assert positionen == list(range(1, len(geordnet) + 1))


def test_previous_id_is_the_exact_inverse_of_next_id() -> None:
    links = _drei_gruppen()
    geordnet = all_group_representative_ids(links)

    rueckwaerts: list[int] = []
    aktuell: int | None = geordnet[-1]
    while aktuell is not None:
        standing = group_standing(aktuell, links)
        assert standing is not None
        rueckwaerts.append(aktuell)
        aktuell = standing.previous_id

    assert rueckwaerts == list(reversed(geordnet))


# ------------------------------------------------------------------------------------------
# Das Laden der Kanten (Projektgrenze)
# ------------------------------------------------------------------------------------------


async def _project(session: AsyncSession, name: str) -> Project:
    project = Project(name=name, opencloud_drive_id="d", opencloud_path="/a")
    session.add(project)
    await session.flush()
    return project


async def _photo(
    session: AsyncSession,
    project: Project,
    path: str,
    *,
    minutes: int = 0,
    duplicate_of: int | None = None,
    with_score: bool = True,
) -> Photo:
    taken_at = _BASE + timedelta(minutes=minutes)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag="etag",
        content_length=1,
        taken_at=taken_at,
        taken_at_original=taken_at,
        last_modified=taken_at,
    )
    session.add(photo)
    await session.flush()
    if with_score:
        session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=0.5,
                exposure=0.5,
                duplicate_of=duplicate_of,
                computed_at=taken_at,
            )
        )
        await session.flush()
    return photo


async def test_the_loader_returns_only_photos_that_belong_to_a_star(
    db_session: AsyncSession,
) -> None:
    project = await _project(db_session, "Costa Rica")
    winner = await _photo(db_session, project, "a.jpg")
    loser = await _photo(db_session, project, "b.jpg", minutes=1, duplicate_of=winner.id)
    await _photo(db_session, project, "einzeln.jpg", minutes=2)

    links = await load_duplicate_links(db_session, project.id)

    assert {link.photo_id for link in links} == {winner.id, loser.id}


async def test_the_loader_keeps_a_representative_without_a_score_row(
    db_session: AsyncSession,
) -> None:
    """`photo_scores.duplicate_of` zeigt auf `photos.id`, nicht auf `photo_scores.photo_id` - der
    Gewinner braucht strukturell keine eigene Zeile, um referenziert zu werden. Ein innerer Join
    auf `PhotoScore` liesse ihn aus der Gruppe fallen, und die Ansicht zeigte den Vergleich ohne
    das Bild, gegen das verglichen wird."""
    project = await _project(db_session, "Costa Rica")
    winner = await _photo(db_session, project, "a.jpg", with_score=False)
    loser = await _photo(db_session, project, "b.jpg", minutes=1, duplicate_of=winner.id)

    links = await load_duplicate_links(db_session, project.id)

    assert {link.photo_id for link in links} == {winner.id, loser.id}
    assert member_ids_of(winner.id, links) == [winner.id, loser.id]


async def test_a_photo_of_another_project_pointing_into_this_one_never_joins_the_group(
    db_session: AsyncSession,
) -> None:
    """SICHERHEIT (S7), die SCHARFE Form der Projektgrenze: nicht bloss "fremdes Foto ergibt 404".
    Nur diese Datenlage deckt ein fehlendes `Photo.project_id`-Praedikat auf - der blosse
    404-Fall bestuende auch ohne es."""
    home = await _project(db_session, "Costa Rica")
    other = await _project(db_session, "Island")
    winner = await _photo(db_session, home, "a.jpg")
    own_loser = await _photo(db_session, home, "b.jpg", minutes=1, duplicate_of=winner.id)
    foreign_loser = await _photo(db_session, other, "fremd.jpg", minutes=2, duplicate_of=winner.id)

    links = await load_duplicate_links(db_session, home.id)

    assert member_ids_of(winner.id, links) == [winner.id, own_loser.id]
    assert foreign_loser.id not in {link.photo_id for link in links}
