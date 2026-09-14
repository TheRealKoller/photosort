"""Der Stern ueber `PhotoScore.duplicate_of` - Sternbildung, Mitglieder- und Gruppenreihenfolge.

Die Gruppe ist ABGELEITET und wird zur Lesezeit gebildet (ADR 0104 Punkt 1). Die Logik steht
deshalb als REINE Funktion ueber den geladenen Kanten, und nur das Laden selbst ist eine Abfrage -
sonst waeren Reihenfolge und Entartungsfall nur ueber einen aufgebauten Datenbestand pruefbar.

DER ENTARTETE FALL `n = 1` IST DER TRENNENDE: Ein Foto, auf das niemand zeigt und das selbst kein
`duplicate_of` traegt, ergibt KEINE Gruppe. Er deckt zugleich ein hartkodiertes "mindestens zwei"
und ein Mitzaehlen des Repraesentanten auf.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.duplicates import (
    DuplicateLink,
    group_position,
    load_duplicate_links,
    member_ids_of,
    open_group_representative_ids,
    representative_of,
)
from photosort.models import Photo, PhotoScore, Project

_BASE = datetime(2023, 5, 1, 12, 0, 0)


def _link(
    photo_id: int,
    duplicate_of: int | None = None,
    *,
    minutes: int = 0,
    decided: bool = False,
) -> DuplicateLink:
    return DuplicateLink(
        photo_id=photo_id,
        duplicate_of=duplicate_of,
        taken_at=_BASE + timedelta(minutes=minutes),
        decided=decided,
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
# Gruppenreihenfolge und Zaehler (AK10)
# ------------------------------------------------------------------------------------------


def test_the_groups_are_ordered_by_the_earliest_taken_at_of_their_members() -> None:
    """VOLLSTAENDIGE Folge zugesichert. Massgeblich ist der frueheste Zeitpunkt der MITGLIEDER,
    nicht der des Repraesentanten: Der Gewinner einer Serie ist oft nicht die erste Aufnahme."""
    links = [
        _link(10, None, minutes=50),
        _link(11, 10, minutes=20),
        _link(20, None, minutes=30),
        _link(21, 20, minutes=31),
    ]

    assert open_group_representative_ids(links) == [10, 20]


def test_a_tie_between_two_groups_is_broken_by_the_representative_id() -> None:
    links = [
        _link(30, None, minutes=0),
        _link(31, 30, minutes=0),
        _link(10, None, minutes=0),
        _link(11, 10, minutes=0),
    ]

    assert open_group_representative_ids(links) == [10, 30]


def test_a_group_whose_every_member_is_decided_drops_out_of_the_reference_set() -> None:
    """AK10: Der Zaehler beschreibt die VERBLEIBENDE Arbeit und laeuft auf null zu."""
    links = [
        _link(10, None, minutes=0, decided=True),
        _link(11, 10, minutes=1, decided=True),
        _link(20, None, minutes=5),
        _link(21, 20, minutes=6),
    ]

    assert open_group_representative_ids(links) == [20]


def test_a_single_undecided_member_keeps_its_whole_group_open() -> None:
    links = [
        _link(10, None, minutes=0, decided=True),
        _link(11, 10, minutes=1, decided=True),
        _link(12, 10, minutes=2),
    ]

    assert open_group_representative_ids(links) == [10]


def test_the_counter_is_one_based_and_names_the_place_among_the_open_groups() -> None:
    links = [
        _link(10, None, minutes=0),
        _link(11, 10, minutes=1),
        _link(20, None, minutes=5),
        _link(21, 20, minutes=6),
        _link(30, None, minutes=9),
        _link(31, 30, minutes=10),
    ]

    assert group_position(10, links) == (1, 3)
    assert group_position(20, links) == (2, 3)
    assert group_position(30, links) == (3, 3)


def test_the_viewed_group_keeps_its_place_even_after_it_has_been_finished() -> None:
    """Die eine Stelle, an der die Bezugsmenge nicht bloss die offenen Gruppen ist: Die GERADE
    ANGESEHENE Gruppe zaehlt mit, auch wenn jedes ihrer Mitglieder entschieden ist.

    Ohne sie liefe die Zusage `1 <= position <= total` aus AK10 leer - wer die letzte offene Gruppe
    fertig entscheidet, laedt sie danach neu und bekaeme `position = 1` bei `total = 0`. Fremde
    abgeschlossene Gruppen fallen unveraendert heraus."""
    links = [
        _link(10, None, minutes=0, decided=True),
        _link(11, 10, minutes=1, decided=True),
        _link(20, None, minutes=5),
        _link(21, 20, minutes=6),
    ]

    assert group_position(10, links) == (1, 2)
    assert group_position(20, links) == (1, 1)


def test_the_position_of_an_unknown_representative_is_none() -> None:
    assert group_position(999, _star(3)) is None


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
