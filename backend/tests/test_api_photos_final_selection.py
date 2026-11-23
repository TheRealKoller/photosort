"""Foto-API: die drei Endauswahl-Felder auf jedem Lesepfad, Albumauswahl, Entscheidungen."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    RatingStatus,
)
from tests.support.api_photos import (
    _add_ranking,
    _album_draft,
    _by_id,
    _decide,
    _default_event,
    _draft,
    _listing,
    _make_criterion_scoring_run,
    _make_event,
    _make_photo,
    _make_project,
    _make_second_user,
    _me,
    _rate,
    _selection,
    assert_invariants_everywhere,
)


def _selection_fields(item: dict[str, Any]) -> tuple[bool | None, bool, bool]:
    return (item["final_selection_decision"], item["in_final_selection"], item["contested"])


class TestTheThreeFinalSelectionFieldsOnTheListing:
    """Die Regel aus ADR 0099, beobachtet am Standard-Listing. Sie lebt in genau einer reinen
    Funktion; hier wird geprueft, dass der Lesepfad sie mit den RICHTIGEN Eingaengen fuettert."""

    async def test_an_untouched_proposed_photo_is_in_the_final_selection_for_both_users(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ "Bilder, die in beiden Entwuerfen stehen, sind OHNE ZUTUN Teil der Endauswahl." Der
        zweite Nutzer ist ausdruecklich angelegt - ohne ihn saesse die Aussage im Leeren."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        await _make_second_user(db_session)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, True, False)

    async def test_a_photo_struck_by_one_of_two_users_is_contested_and_not_in_the_selection(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ "Ein strittiges Bild, ueber das noch nicht gemeinsam entschieden wurde, gehoert NICHT
        zur Endauswahl." Automatische Zugehoerigkeit gibt es allein bei Einigkeit."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.REJECTED)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, False, True)

    async def test_a_proposed_photo_taken_by_one_and_untouched_by_the_other_stays_agreed(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 4 am Lesepfad: Bei einem VORGESCHLAGENEN Foto zaehlen die STREICHUNGEN.
        Eine Umsetzung, die hier `taken` zaehlt, liest "strittig" - und das Foto verschwaende aus
        der Endauswahl, ohne dass jemand es angefasst haette."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.ALBUM_WORTHY)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, True, False)

    async def test_an_unproposed_photo_taken_by_only_one_user_is_contested(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die andere Haelfte von Zusicherung 4: Bei einem NICHT vorgeschlagenen Foto zaehlen die
        AUFNAHMEN. Eine Umsetzung, die hier `user_count - rejected` zaehlt, liest "einig drin"."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(
            db_session, run, photo, rank_score=0.9, rank_position=1, selection_position=None
        )
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.ALBUM_WORTHY)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, False, True)

    async def test_a_pure_favorite_row_of_the_other_user_leaves_a_proposed_photo_agreed(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 5: ZEILENVORHANDENSEIN IST KEINE AUSSAGE. Seit ADR 0098 kann eine Zeile
        allein den Favoriten tragen; wer ueber die Existenz der Zeile zaehlt statt ueber
        `Rating.status`, macht aus einer Auszeichnung eine Streichung."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, None, favorite=True)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, True, False)

    async def test_with_a_single_user_every_proposed_photo_is_in_and_nothing_is_contested(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 6: `n` ist der NUTZERBESTAND, und der Beweis dafuer ist `n = 1`. Ein
        hartkodiertes `== 2` liefert hier flaechendeckend `in_final_selection: false`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, True, False)

    async def test_a_decision_overrides_the_consensus_in_both_directions(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 1: EINIGKEIT IST EINE VORBELEGUNG, KEINE SPERRE. Eine Umsetzung, die den
        Konsenszweig VOR die Entscheidung stellt, besteht jeden anderen Fall."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        await _make_second_user(db_session)

        await _decide(db_session, photo, False)
        removed = await _listing(authenticated_api_client, project)
        await _decide(db_session, photo, True)
        restored = await _listing(authenticated_api_client, project)

        assert _selection_fields(removed[0]) == (False, False, False)
        assert _selection_fields(restored[0]) == (True, True, False)


class TestTheThreeFieldsStandOnEveryReadPath:
    async def test_listing_and_draft_report_the_same_three_values(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 11 (Muster `test_present_is_identical_in_the_listing_and_in_the_draft`):
        Ein je Query-Modus getrennt gesetztes Feld liefe genau hier auseinander - und die eine
        Ansicht naennte ein Foto als Teil des Albums, das die andere weglaesst."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.REJECTED)

        listing = await _listing(authenticated_api_client, project)
        draft = await _draft(authenticated_api_client, project)

        assert _selection_fields(listing[0]) == _selection_fields(draft[0])
        assert _selection_fields(draft[0]) == (None, False, True)

    async def test_the_alternatives_endpoint_reports_them_too(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der dritte Lesepfad. Ein hier vergessener Aufrufer wirft keine Ausnahme und liefert
        keinen Fehlercode - er antwortet `in_final_selection: false` fuer jedes Foto, plausibel
        und still (Auflage S9)."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event = await _default_event(db_session, run)
        reference = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        alternative = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2))
        await _add_ranking(db_session, run, reference, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, alternative, rank_score=0.5, rank_position=2, selection_position=None
        )
        await _decide(db_session, alternative, True)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event.id, "photo_id": reference.id},
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert_invariants_everywhere(items)
        assert _selection_fields(items[0]) == (True, True, False)

    async def test_a_photo_without_any_run_still_carries_the_three_fields(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ohne erfolgreichen Lauf gibt es keinen Vorschlag - die Felder stehen trotzdem, und ein
        von niemandem angefasstes Foto ist dann in keinem Entwurf und damit nicht in der
        Endauswahl."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _make_second_user(db_session)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, False, False)


class TestTheAlbumSelectionCandidateSet:
    """Zusicherung 9: Die Kandidatenmenge ist ein ODER DREIER Praedikate, und jedes braucht einen
    Fall, der NUR ueber es hereinkommt. Dazu die Gegenprobe und der Fall, der Kandidaten- von
    Antwortmenge trennt - ohne ihn ist eine Umsetzung, die den Zustandsfilter ganz weglaesst, in
    allen uebrigen Faellen gruen."""

    async def test_a_photo_enters_solely_through_its_selection_position(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        body = await _selection(authenticated_api_client, project)

        assert [item["id"] for item in body["items"]] == [photo.id]

    async def test_a_photo_enters_solely_through_its_decision_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Weder vorgeschlagen noch bewertet - allein die Entscheidungszeile holt es herein
        (Zusicherung 10). Ohne sie waere die Entscheidung entgegen dem Akzeptanzkriterium nicht
        mehr aenderbar, weil das Bild aus beiden Sichten verschwaende."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        carrier = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, carrier, rank_score=0.9, rank_position=1)
        lonely = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        await _decide(db_session, lonely, False)

        body = await _selection(authenticated_api_client, project)

        by_id = _by_id(body["items"])
        assert lonely.id in by_id
        assert _selection_fields(by_id[lonely.id]) == (False, False, False)

    async def test_a_photo_enters_solely_through_a_rating_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        carrier = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, carrier, rank_score=0.9, rank_position=1)
        taken = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        other = await _make_second_user(db_session)
        await _rate(db_session, taken, other, RatingStatus.ALBUM_WORTHY)

        body = await _selection(authenticated_api_client, project)

        by_id = _by_id(body["items"])
        assert taken.id in by_id
        assert _selection_fields(by_id[taken.id]) == (None, False, True)

    async def test_a_photo_that_meets_none_of_the_three_predicates_does_not_appear(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Gegenprobe. Ohne sie waere eine Umsetzung, die schlicht alle Fotos des Projekts
        liefert, in jedem der drei Faelle oben gruen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        carrier = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, carrier, rank_score=0.9, rank_position=1)
        stranger = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        await _add_ranking(
            db_session, run, stranger, rank_score=0.2, rank_position=2, selection_position=None
        )
        await _make_second_user(db_session)

        body = await _selection(authenticated_api_client, project)

        assert stranger.id not in _by_id(body["items"])

    async def test_a_photo_struck_by_everyone_is_a_candidate_and_still_does_not_appear(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Fall, der KANDIDATEN- von ANTWORTMENGE trennt: Das Foto kommt ueber zwei der drei
        Praedikate herein und faellt am Zustandsfilter wieder heraus. Der Weg zurueck fuehrt ueber
        den Einzelentwurf, in dem es weiterhin steht."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        me = await _me(db_session)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, me, RatingStatus.REJECTED)
        await _rate(db_session, photo, other, RatingStatus.REJECTED)

        body = await _selection(authenticated_api_client, project)

        assert body["items"] == []


class TestTheAlbumSelectionResponseShape:
    async def test_participants_carry_every_user_sorted_by_id_and_only_two_fields(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 13 / Auflage S8: JEDER Nutzer, auch der ohne jede Bewertung - aus
        `ratings[]` abgeleitet fehlte genau der, den die Story ausdruecklich als "kein Sonderfall"
        benennt. Und genau ZWEI Felder: Dies ist der erste Endpunkt, der den vollstaendigen
        Kontenbestand ausliefert; ein `model_validate(User)` schoebe den Passwort-Hash in eine
        Antwort, die im Browser beider Nutzer und in jedem Cache landet."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        me = await _me(db_session)
        other = await _make_second_user(db_session)

        body = await _selection(authenticated_api_client, project)

        assert body["participants"] == [
            {"user_id": me.id, "username": "testuser"},
            {"user_id": other.id, "username": "other-user"},
        ]
        for participant in body["participants"]:
            assert set(participant) == {"user_id", "username"}

    async def test_the_response_carries_no_total(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Menge wird als GANZES geliefert, wie der Entwurfszweig. Ein `total == len(items)`
        lueede dazu ein, etwas zu blaettern, das nicht geblaettert wird."""
        project = await _make_project(db_session)
        await _make_criterion_scoring_run(db_session, project)

        body = await _selection(authenticated_api_client, project)

        assert set(body) == {"participants", "has_proposal", "items"}

    async def test_the_curation_position_is_null_on_this_endpoint(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 16: Eine Zahl waere eine Rangaussage ueber eine Menge, die keinen Rang
        kennt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"p{index}.jpg", datetime(2023, 1, 1, 10, index)
            )
            await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=index + 1)

        body = await _selection(authenticated_api_client, project)

        assert len(body["items"]) == 3
        for item in body["items"]:
            assert item["ranking"]["curation_position"] is None

    async def test_an_unknown_project_is_a_404(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        await _make_project(db_session)

        response = await authenticated_api_client.get("/projects/999999/album-selection")

        assert response.status_code == 404

    async def test_the_endpoint_requires_a_token(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)

        response = await api_client.get(f"/projects/{project.id}/album-selection")

        assert response.status_code == 401


class TestTheTwoEmptyStatesAreSeparate:
    """Zusicherung 12: `has_proposal` trennt die beiden Leerzustaende, die die Story GETRENNT
    verlangt. Ein Fall, der nur die leere Liste prueft, laesst sie zusammenfallen - die Oberflaeche
    schickt den Nutzer dann in die Pipeline, obwohl dort nichts zu tun ist."""

    async def test_without_any_successful_run_the_flag_is_false_but_participants_are_filled(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _make_second_user(db_session)

        body = await _selection(authenticated_api_client, project)

        assert body["has_proposal"] is False
        assert body["items"] == []
        assert len(body["participants"]) == 2

    async def test_a_successful_run_without_a_single_selection_position_is_also_false(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Lauf war erfolgreich und hat trotzdem nichts vorgeschlagen - derselbe Leerzustand
        wie "noch kein Lauf", weil in beiden Faellen ein Lauf fehlt, der etwas vorschlaegt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(
            db_session, run, photo, rank_score=0.9, rank_position=1, selection_position=None
        )

        body = await _selection(authenticated_api_client, project)

        assert body["has_proposal"] is False

    async def test_a_single_selection_position_makes_it_true(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        body = await _selection(authenticated_api_client, project)

        assert body["has_proposal"] is True


class TestTheDecisionSurvivesBothWaysOfChange:
    """Zusicherung 2. BEIDE Richtungen im SELBEN Fall - getrennt geschrieben besteht jede Haelfte
    auch bei einer Umsetzung, die die Entscheidung immer oder nie gewinnen laesst."""

    async def test_a_decision_survives_a_later_draft_change_in_both_directions(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """einig -> uneins UND uneins -> einig lassen `final_selection_decision` und
        `in_final_selection` unveraendert, `contested` bleibt `false`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _decide(db_session, photo, True)

        agreed = _by_id((await _selection(authenticated_api_client, project))["items"])
        await _rate(db_session, photo, other, RatingStatus.REJECTED)
        divided = _by_id((await _selection(authenticated_api_client, project))["items"])
        await _rate(db_session, photo, other, None)
        reunited = _by_id((await _selection(authenticated_api_client, project))["items"])

        assert _selection_fields(agreed[photo.id]) == (True, True, False)
        assert _selection_fields(divided[photo.id]) == (True, True, False)
        assert _selection_fields(reunited[photo.id]) == (True, True, False)

    async def test_a_decision_survives_a_new_run_that_drops_the_photo_from_the_proposal(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die zweite Haelfte: ein NEUER Vorschlagslauf, der das Foto nicht mehr traegt. Die Zeile
        haengt am Foto und an keinem Lauf - genau deshalb ueberlebt sie ihn."""
        project = await _make_project(db_session)
        first = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2026, 1, 1, 10, 0)
        )
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, first, photo, rank_score=0.9, rank_position=1)
        await _make_second_user(db_session)
        await _decide(db_session, photo, True)

        before = _by_id((await _selection(authenticated_api_client, project))["items"])

        second = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2026, 1, 2, 10, 0)
        )
        await _make_event(
            db_session,
            second,
            position=1,
            started_at=datetime(2023, 1, 1, 9, 0),
            ended_at=datetime(2023, 1, 1, 11, 0),
        )
        await _add_ranking(
            db_session, second, photo, rank_score=0.4, rank_position=1, selection_position=None
        )

        after = _by_id((await _selection(authenticated_api_client, project))["items"])

        assert _selection_fields(before[photo.id]) == (True, True, False)
        assert _selection_fields(after[photo.id]) == (True, True, False)


class TestThePlacementOfTheFinalSelection:
    async def test_a_new_run_moves_the_decided_photo_to_its_new_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 14: Die RANGZEILE hat Vorrang vor der Zeitzuordnung."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 9, 0),
            ended_at=datetime(2023, 1, 1, 11, 0),
        )
        second_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 2, 9, 0),
            ended_at=datetime(2023, 1, 2, 11, 0),
        )
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(
            db_session, run, photo, event=second_event, rank_score=0.9, rank_position=1
        )

        body = await _selection(authenticated_api_client, project)

        assert _by_id(body["items"])[photo.id]["event"]["id"] == second_event.id
        assert first_event.id != second_event.id

    async def test_the_draft_and_the_final_selection_order_the_same_photos_identically(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 15: `_place_in_events` wird von BEIDEN Zweigen aufgerufen, nicht zweimal
        geschrieben. Das Paar gehoert in EINEN Fall - zweimal geschrieben ordneten Entwurf und
        Endauswahl dieselben Fotos verschieden, sichtbar, ohne dass eine Pruefung rot wuerde."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        late_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 2, 9, 0),
            ended_at=datetime(2023, 1, 2, 11, 0),
        )
        early_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 9, 0),
            ended_at=datetime(2023, 1, 1, 11, 0),
        )
        late = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 2, 10, 0))
        early_second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        early_first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        for photo, photo_event in (
            (late, late_event),
            (early_second, early_event),
            (early_first, early_event),
        ):
            await _add_ranking(
                db_session, run, photo, event=photo_event, rank_score=0.5, rank_position=1
            )

        draft = await _draft(authenticated_api_client, project)
        selection = await _selection(authenticated_api_client, project)

        expected = [early_first.id, early_second.id, late.id]
        assert [item["id"] for item in draft] == expected
        assert [item["id"] for item in selection["items"]] == expected
        assert [item["event"]["id"] for item in selection["items"]] == [
            early_event.id,
            early_event.id,
            late_event.id,
        ]


class TestTheFinalSelectionIsBoundToItsProject:
    async def test_a_decided_photo_of_another_project_never_enters_the_answer(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S2: Zwei der drei Quellen sind PROJEKTBLIND - `final_selection_decisions` hat
        nur `photo_id`, `Rating` nur `(photo_id, user_id)`. Ein in die ODER-Verknuepfung
        gerutschtes Projektpraedikat ist syntaktisch unauffaellig und liesse jedes jemals bewertete
        oder entschiedene Foto ALLER Projekte herein - kohaerent aussehende Fremddaten statt einer
        erkennbar falschen Menge. Und das ist die Menge, die der Export nimmt."""
        mine = await _make_project(db_session, "Meins")
        theirs = await _make_project(db_session, "Fremd")
        my_run = await _make_criterion_scoring_run(db_session, mine)
        my_photo = await _make_photo(db_session, mine, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, my_run, my_photo, rank_score=0.9, rank_position=1)

        other = await _make_second_user(db_session)
        foreign_decided = await _make_photo(
            db_session, theirs, "x.jpg", datetime(2023, 1, 1, 10, 0)
        )
        foreign_rated = await _make_photo(db_session, theirs, "y.jpg", datetime(2023, 1, 1, 10, 5))
        await _decide(db_session, foreign_decided, True)
        await _rate(db_session, foreign_rated, other, RatingStatus.ALBUM_WORTHY)

        body = await _selection(authenticated_api_client, mine)

        assert [item["id"] for item in body["items"]] == [my_photo.id]

    async def test_a_ranking_of_another_projects_run_never_enters_the_answer(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Rangzweig haengt zusaetzlich am `criterion_scoring_run_id` des letzten
        erfolgreichen Laufs DIESES Projekts - `PhotoRanking` traegt keine `project_id`."""
        mine = await _make_project(db_session, "Meins")
        theirs = await _make_project(db_session, "Fremd")
        my_run = await _make_criterion_scoring_run(db_session, mine)
        their_run = await _make_criterion_scoring_run(db_session, theirs)
        my_photo = await _make_photo(db_session, mine, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, my_run, my_photo, rank_score=0.9, rank_position=1)
        foreign = await _make_photo(db_session, theirs, "x.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, their_run, foreign, rank_score=0.9, rank_position=1)

        body = await _selection(authenticated_api_client, mine)

        assert [item["id"] for item in body["items"]] == [my_photo.id]


class TestTheDenominatorComesFromTheSameRead:
    async def test_the_participant_count_is_the_denominator_of_the_rule(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S8: `user_count` stammt aus DERSELBEN Leseoperation wie `participants`. Gingen
        beide auseinander, behauptete die Ansicht Einigkeit ueber zwei Teilnehmer, waehrend die
        Regel ueber drei rechnet - die Endauswahl waere kleiner als die Anzeige sie zeigt, ohne
        dass ein Feld der Antwort widerspruechlich aussieht.

        Der Nachweis laeuft ueber den entarteten Fall: Mit genau EINEM Teilnehmer ist jedes
        vorgeschlagene, unangefasste Foto drin; mit ZWEI und einer Streichung ist es strittig."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        alone = await _selection(authenticated_api_client, project)

        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.REJECTED)
        together = await _selection(authenticated_api_client, project)

        assert len(alone["participants"]) == 1
        assert _selection_fields(_by_id(alone["items"])[photo.id]) == (None, True, False)
        assert len(together["participants"]) == 2
        assert _selection_fields(_by_id(together["items"])[photo.id]) == (None, False, True)


class TestTheThreeFieldsAreIdenticalOnAllFourReadPaths:
    async def test_the_same_photo_reports_the_same_three_values_everywhere(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 11, vollstaendig: Listing, Entwurfszweig, Alternativen-Endpunkt und der
        neue Endpunkt fuer DASSELBE Foto."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event = await _default_event(db_session, run)
        reference = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        subject = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        await _add_ranking(db_session, run, reference, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, subject, rank_score=0.5, rank_position=2, selection_position=None
        )
        await _make_second_user(db_session)
        await _decide(db_session, subject, True)

        listing = _by_id(await _listing(authenticated_api_client, project))
        draft = _by_id(await _draft(authenticated_api_client, project))
        alternatives = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event.id, "photo_id": reference.id},
        )
        selection = _by_id((await _selection(authenticated_api_client, project))["items"])

        assert alternatives.status_code == 200
        alternative_items = _by_id(alternatives.json()["items"])
        values = {
            "listing": _selection_fields(listing[subject.id]),
            "alternatives": _selection_fields(alternative_items[subject.id]),
            "selection": _selection_fields(selection[subject.id]),
        }
        assert set(values.values()) == {(True, True, False)}, values
        # Der Entwurfszweig fuehrt dieses Foto bewusst NICHT (niemand hat es aufgenommen) - die
        # Feldgleichheit gilt fuer das Bezugsbild, das in allen vier Antworten steht.
        assert _selection_fields(draft[reference.id]) == _selection_fields(listing[reference.id])


class TestTheSingleDraftStaysUntouchedByAJointDecision:
    """Die "Spannung, die aufzuloesen ist": Story 6 sagt zu, dass neben der Bewertung KEINE zweite,
    daneben liegende Auswahlebene entsteht. Die Endauswahl ist eine Ebene UEBER beiden Entwuerfen -
    hier sind die Verhaltensnachweise dafuer, in beide Richtungen."""

    async def test_a_joint_decision_changes_neither_the_draft_nor_any_ratings(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nachweisstelle 4: Verglichen wird die vollstaendige ID-FOLGE und die Eventliste, nicht
        die Menge - eine Umordnung waere sonst unsichtbar. Dazu die `ratings[]` BEIDER Nutzer."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = []
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"p{index}.jpg", datetime(2023, 1, 1, 10, index)
            )
            await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=index + 1)
            photos.append(photo)
        other = await _make_second_user(db_session)
        await _rate(db_session, photos[1], other, RatingStatus.REJECTED)

        before = await _draft(authenticated_api_client, project)
        before_events = (await _album_draft(authenticated_api_client, project))["events"]

        await _decide(db_session, photos[1], False)
        await _decide(db_session, photos[0], False)

        after = await _draft(authenticated_api_client, project)
        after_events = (await _album_draft(authenticated_api_client, project))["events"]

        assert [item["id"] for item in after] == [item["id"] for item in before]
        assert after_events == before_events
        assert [item["ratings"] for item in after] == [item["ratings"] for item in before]

    async def test_a_draft_change_leaves_an_existing_joint_decision_untouched(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nachweisstelle 5, die GEGENRICHTUNG, die Nachweisstelle 4 nicht abdeckt: Nach einer
        Aenderung der Albumentscheidung eines Nutzers sind die drei Felder unveraendert."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        me = await _me(db_session)
        await _make_second_user(db_session)
        await _decide(db_session, photo, False)

        before = _by_id(await _listing(authenticated_api_client, project))
        await _rate(db_session, photo, me, RatingStatus.ALBUM_WORTHY)
        after = _by_id(await _listing(authenticated_api_client, project))

        assert _selection_fields(before[photo.id]) == (False, False, False)
        assert _selection_fields(after[photo.id]) == (False, False, False)

    async def test_the_alternatives_response_is_identical_before_and_after_a_joint_decision(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nachweisstelle 6: Antwortmenge UND Reihenfolge des Alternativen-Endpunkts sind vor und
        nach einer gemeinsamen Entscheidung identisch."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event = await _default_event(db_session, run)
        reference = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, reference, rank_score=0.9, rank_position=1)
        alternatives = []
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"alt{index}.jpg", datetime(2023, 1, 1, 11, index)
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                rank_score=0.5 - index * 0.1,
                rank_position=index + 2,
                selection_position=None,
            )
            alternatives.append(photo)
        await _make_second_user(db_session)

        async def _alternative_ids() -> list[int]:
            response = await authenticated_api_client.get(
                f"/projects/{project.id}/draft-alternatives",
                params={"event_id": event.id, "photo_id": reference.id},
            )
            assert response.status_code == 200
            return [item["id"] for item in response.json()["items"]]

        before = await _alternative_ids()
        await _decide(db_session, alternatives[1], True)
        await _decide(db_session, alternatives[2], False)
        after = await _alternative_ids()

        assert before
        assert after == before
