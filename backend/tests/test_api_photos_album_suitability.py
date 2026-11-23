"""Foto-API: Albumtauglichkeit im Foto-Ausgang, Quelle der Stufe, Auge-Ergebnis.
(Aufgeteilt aus test_api_photos.py, Spec 0651.)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CategoryMethod,
    CriterionScoringRun,
    Event,
    MotifAssessmentSource,
    Photo,
    PhotoEyeFineLabel,
    PhotoEyeResult,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
)
from tests.support.api_photos import (
    _add_ranking,
    _assess_photo,
    _by_id,
    _decide,
    _default_event,
    _draft,
    _first_photo_out,
    _listing,
    _make_criterion_scoring_run,
    _make_event,
    _make_photo,
    _make_project,
    _me,
    _own_status,
    _rate,
    _rate_album_suitability,
    _selection,
)


class TestTheAlbumSuitabilityInThePhotoOut:
    """specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 10: die Modellaussage wird
    ausgeliefert, und die beiden Rangfelder sind nullable geworden."""

    async def test_a_rated_photo_carries_level_and_reason(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _rate_album_suitability(db_session, photo, level=2, reason="Augen geschlossen.")

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["album_suitability"] == {
            "level": 2,
            "reason": "Augen geschlossen.",
            "source": "cloud",
        }

    async def test_a_photo_without_a_row_carries_null(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die ABWESENHEIT ist "noch nicht bewertet" - unterscheidbar von der niedrigsten
        Stufe."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["album_suitability"] is None

    async def test_a_missing_reason_is_null_and_not_an_empty_string(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _rate_album_suitability(db_session, photo, level=5, reason=None)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["album_suitability"] == {"level": 5, "reason": None, "source": "cloud"}

    async def test_the_reason_is_delivered_verbatim_without_any_interpretation(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Fremdtext wird auf dem Lesepfad nicht noch einmal angefasst - saniert und gekappt
        wurde er EINMAL, am Parser. Eine zweite Fassung der Regel hier waere die zweite
        Pflegestelle."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _rate_album_suitability(db_session, photo, reason="<b>fett</b> & 'roh'")

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["album_suitability"]["reason"] == "<b>fett</b> & 'roh'"


_ALBUM_LEVEL_PATHS = (
    "draft",
    "listing",
    "selection",
    "duplicate-group",
    "ausschuss",
    "alternatives",
)


async def _eye_level(session: AsyncSession, photo: Photo, level: int) -> None:
    session.add(
        PhotoEyeResult(
            photo_id=photo.id,
            excluded_document=False,
            album_level=level,
            model_revision="v1.0.0",
            mapping_version="eye-4.2.3/v2",
            computed_at=datetime(2026, 9, 14, 9, 0, 0),
        )
    )
    await session.commit()


@dataclass(frozen=True)
class _SourceLay:
    """Zwei Fotos in EINEM Ereignis, die auf ALLEN sechs Lesepfaden vorkommen: `reference` ist der
    Vorschlag (Entwurf), `subject` steht daneben (Alternativen), ist Duplikat-Verlierer (Gruppe),
    traegt einen offenen Vorschlag (Ausschuss) und eine gemeinsame Entscheidung (Endauswahl).

    BEIDE Fotos tragen Cloud- UND Eye-Stufe, und zwar auseinander (4 gegen 1) - eine Umsetzung, die
    immer dieselbe Tabelle liest, faellt damit auf."""

    project: Project
    run: CriterionScoringRun
    event: Event
    reference: Photo
    subject: Photo


async def _source_lay(
    session: AsyncSession,
    *,
    run_source: CategoryMethod,
    project_method: CategoryMethod,
    name: str = "Zwei Quellen",
) -> _SourceLay:
    project = await _make_project(session, name)
    project.category_method = project_method
    await session.commit()
    run = await _make_criterion_scoring_run(session, project, album_level_source=run_source)
    event = await _make_event(session, run)
    reference = await _make_photo(session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
    subject = await _make_photo(session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
    session.add_all(
        [
            PhotoScore(
                photo_id=reference.id,
                sharpness=100.0,
                exposure=0.0,
                computed_at=datetime(2023, 1, 1, 10, 0),
            ),
            PhotoScore(
                photo_id=subject.id,
                sharpness=100.0,
                exposure=0.0,
                suggested_status=RatingStatus.REJECTED,
                duplicate_of=reference.id,
                computed_at=datetime(2023, 1, 1, 10, 30),
            ),
        ]
    )
    await session.commit()
    await _add_ranking(session, run, reference, event=event, rank_score=0.9, rank_position=1)
    await _add_ranking(
        session,
        run,
        subject,
        event=event,
        rank_score=0.5,
        rank_position=2,
        selection_position=None,
    )
    for photo in (reference, subject):
        await _rate_album_suitability(session, photo, level=4, reason="Augen geschlossen.")
        await _eye_level(session, photo, 1)
    await _decide(session, subject, True)
    return _SourceLay(project=project, run=run, event=event, reference=reference, subject=subject)


async def _photo_on_path(client: httpx.AsyncClient, lay: _SourceLay, path: str) -> dict[str, Any]:
    """Die Antwort des Fotos, das dieser Lesepfad fuehrt: der Entwurf fuehrt `reference` (nur
    vorgeschlagen), die uebrigen Pfade `subject`."""
    if path == "listing":
        return _by_id(await _listing(client, lay.project))[lay.subject.id]
    if path == "draft":
        return _by_id(await _draft(client, lay.project))[lay.reference.id]
    if path == "selection":
        return _by_id((await _selection(client, lay.project))["items"])[lay.subject.id]
    if path == "duplicate-group":
        response = await client.get(f"/projects/{lay.project.id}/duplicate-groups/{lay.subject.id}")
        assert response.status_code == 200
        return _by_id([item["photo"] for item in response.json()["items"]])[lay.subject.id]
    if path == "ausschuss":
        response = await client.get(f"/projects/{lay.project.id}/ausschuss")
        assert response.status_code == 200
        # Der Duplikat-Verlierer steht als STAPEL in der Antwort, sein Titelbild ist der Gewinner.
        # Beide tragen in dieser Lage dieselben Stufen - Gegenstand ist der Pfad, nicht das
        # Mitglied.
        by_id: dict[int, dict[str, Any]] = {}
        for entry in response.json()["items"]:
            if entry["kind"] == "photo":
                by_id[entry["photo"]["id"]] = entry["photo"]
            else:
                by_id[entry["cover"]["id"]] = entry["cover"]
        return by_id.get(lay.subject.id) or by_id[lay.reference.id]
    assert path == "alternatives"
    response = await client.get(
        f"/projects/{lay.project.id}/draft-alternatives",
        params={"event_id": lay.event.id, "photo_id": lay.reference.id},
    )
    assert response.status_code == 200
    return _by_id(response.json()["items"])[lay.subject.id]


@pytest.mark.parametrize("path", _ALBUM_LEVEL_PATHS)
async def test_a_switch_without_a_new_run_keeps_the_level_and_its_source(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    path: str,
) -> None:
    """AK "Wechsel wirkt erst mit dem naechsten Lauf": Der Lauf zaehlte Cloud, das Projekt steht
    jetzt auf Eye - Entwurf, Stufe und Herkunft bleiben die des Laufs (ADR 0144)."""
    lay = await _source_lay(
        db_session, run_source=CategoryMethod.CLOUD, project_method=CategoryMethod.EYE
    )

    item = await _photo_on_path(authenticated_api_client, lay, path)

    assert item["album_suitability"] == {
        "level": 4,
        "reason": "Augen geschlossen.",
        "source": "cloud",
    }


@pytest.mark.parametrize("path", _ALBUM_LEVEL_PATHS)
async def test_an_eye_run_ships_the_eye_level_without_a_reason(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    path: str,
) -> None:
    """S2/S4: Die Herkunft kommt aus dem Lauf, und bei Eye ist `reason` SERVERSEITIG `None` - auch
    wenn daneben eine Cloud-Zeile mit Begruendung liegt."""
    lay = await _source_lay(
        db_session, run_source=CategoryMethod.EYE, project_method=CategoryMethod.EYE
    )

    item = await _photo_on_path(authenticated_api_client, lay, path)

    assert item["album_suitability"] == {"level": 1, "reason": None, "source": "eye"}


async def test_a_supplied_source_parameter_is_ignored(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """S2: Kein Endpunkt nimmt eine Quelle entgegen - ein mitgeschickter Wert bleibt wirkungslos."""
    lay = await _source_lay(
        db_session, run_source=CategoryMethod.CLOUD, project_method=CategoryMethod.CLOUD
    )

    response = await authenticated_api_client.get(
        f"/projects/{lay.project.id}/photos",
        params={"source": "eye", "album_level_source": "eye"},
    )

    assert response.status_code == 200
    item = _by_id(response.json()["items"])[lay.subject.id]
    assert item["album_suitability"]["source"] == "cloud"


async def test_a_photo_without_the_level_of_the_run_reports_null(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Kein Rueckfall: Traegt ein von Hand aufgenommenes Foto nur die Cloud-Stufe, waehrend der Lauf
    Eye zaehlt, bleibt `album_suitability` `null` - im Entwurf wie in der Liste."""
    lay = await _source_lay(
        db_session, run_source=CategoryMethod.EYE, project_method=CategoryMethod.EYE
    )
    manual = await _make_photo(db_session, lay.project, "manuell.jpg", datetime(2023, 1, 1, 11, 0))
    await _rate_album_suitability(db_session, manual, level=3, reason="Nur Cloud.")
    await _rate(db_session, manual, await _me(db_session), status=RatingStatus.ALBUM_WORTHY)

    draft = _by_id(await _draft(authenticated_api_client, lay.project))
    listing = _by_id(await _listing(authenticated_api_client, lay.project))

    assert draft[manual.id]["album_suitability"] is None
    assert listing[manual.id]["album_suitability"] is None


async def test_every_project_reads_the_source_of_its_own_run(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """S3: das Laufpraedikat bindet an DIESES Projekt - nie an den global juengsten Lauf."""
    cloud_lay = await _source_lay(
        db_session,
        run_source=CategoryMethod.CLOUD,
        project_method=CategoryMethod.CLOUD,
        name="Nur Cloud",
    )
    eye_lay = await _source_lay(
        db_session,
        run_source=CategoryMethod.EYE,
        project_method=CategoryMethod.EYE,
        name="Nur Eye",
    )

    cloud_item = _by_id(await _listing(authenticated_api_client, cloud_lay.project))[
        cloud_lay.subject.id
    ]
    eye_item = _by_id(await _listing(authenticated_api_client, eye_lay.project))[eye_lay.subject.id]

    assert (cloud_item["album_suitability"]["source"], eye_item["album_suitability"]["source"]) == (
        "cloud",
        "eye",
    )
    assert (cloud_item["album_suitability"]["level"], eye_item["album_suitability"]["level"]) == (
        4,
        1,
    )


async def test_include_and_strike_survive_every_switch(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Cloud-Lauf, Eye-Lauf, Cloud-Lauf: Ein aufgenommenes und ein gestrichenes Foto behalten
    ueber JEDEN Wechsel ihre Bewertungszeile und ihren Anzeigezustand im Entwurf; nur die
    Herkunft der Stufe folgt dem jeweiligen Lauf (ADR 0144)."""
    project = await _make_project(db_session)
    user = await _me(db_session)
    taken = await _make_photo(db_session, project, "aufgenommen.jpg", datetime(2023, 1, 1, 10, 0))
    struck = await _make_photo(db_session, project, "gestrichen.jpg", datetime(2023, 1, 1, 10, 5))
    await _rate(db_session, taken, user, status=RatingStatus.ALBUM_WORTHY)
    await _rate(db_session, struck, user, status=RatingStatus.REJECTED)
    for photo in (taken, struck):
        await _rate_album_suitability(db_session, photo, level=4, reason="Cloud.")
        await _eye_level(db_session, photo, 2)

    seen: list[tuple[str, str | None, str, str | None]] = []
    for index, source in enumerate(
        (CategoryMethod.CLOUD, CategoryMethod.EYE, CategoryMethod.CLOUD)
    ):
        run = await _make_criterion_scoring_run(
            db_session,
            project,
            album_level_source=source,
            started_at=datetime(2023, 2, 1, 12, index),
        )
        await _add_ranking(db_session, run, taken, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, struck, rank_score=0.4, rank_position=2)
        draft = _by_id(await _draft(authenticated_api_client, project))
        seen.append(
            (
                draft[taken.id]["album_suitability"]["source"],
                _own_status(draft[taken.id], user.id),
                draft[struck.id]["album_suitability"]["source"],
                _own_status(draft[struck.id], user.id),
            )
        )

    assert seen == [
        ("cloud", "album_worthy", "cloud", "rejected"),
        ("eye", "album_worthy", "eye", "rejected"),
        ("cloud", "album_worthy", "cloud", "rejected"),
    ]
    statuses = (
        await db_session.execute(select(Rating.photo_id, Rating.status).order_by(Rating.photo_id))
    ).all()
    assert statuses == [
        (taken.id, RatingStatus.ALBUM_WORTHY),
        (struck.id, RatingStatus.REJECTED),
    ]


class TestARankingRowWithoutAModelVerdict:
    async def test_both_rank_fields_are_null_while_the_event_stays(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=None, rank_position=None)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["ranking"]["rank_score"] is None
        assert item["ranking"]["rank_position"] is None
        assert item["ranking"]["event_id"] == (await _default_event(db_session, run)).id

    async def test_a_score_of_zero_survives_as_a_real_value(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`0.0` ist ein GUELTIGER Qualitaetswert (schlechteste Modellstufe, schlechteste lokale
        Messung) - ein Falsyness-Filter auf dem Weg nach draussen verloere ihn lautlos."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.0, rank_position=1)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["ranking"]["rank_score"] == 0.0
        assert item["ranking"]["rank_score"] is not None

    async def test_an_unrated_photo_is_not_part_of_the_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein Foto ohne Qualitaetswert erscheint NICHT im Entwurf - und die Partitionsgroesse
        beschreibt dieselbe Menge, die die Auswahl zeigt. Beides in einem Fall: eine Groesse, die
        die unbewerteten mitzaehlt, machte "Rang 1 von 2" aus einer Partition mit genau einem
        einsehbaren Foto."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        rated = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        unrated = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, rated, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, unrated, rank_score=None, rank_position=None)

        response = await authenticated_api_client.get(f"/projects/{project.id}/album-draft")

        body = response.json()
        assert [item["id"] for item in body["items"]] == [rated.id]
        assert body["items"][0]["ranking"]["partition_size"] == 1


# Spec 0609, "Cloud gilt weiter" und "Lesen": `PhotoOut.eye_result` ist GENAU dann gesetzt, wenn
# die Motiv-Kopfzeile `source="eye"` traegt. Der Schattensatz daneben ist Vergleichsmaterial fuer
# das CLI, keine Anzeige - er darf die Ansicht nicht dazu bringen, Eye-Werte zu zeigen, die gar
# nicht gelten.
async def _add_eye_shadow(
    session: AsyncSession,
    photo: Photo,
    *,
    labels: tuple[tuple[str, float], ...] = (("dog", 0.9), ("mountain", 0.7)),
    mapping_version: str = "eye-4.2.3/v2",
) -> None:
    session.add(
        PhotoEyeResult(
            photo_id=photo.id,
            excluded_document=False,
            album_level=4,
            model_revision="v1.0.0",
            mapping_version=mapping_version,
            computed_at=datetime(2026, 9, 14, 9, 0, 0),
        )
    )
    await session.flush()
    for label, confidence in labels:
        session.add(PhotoEyeFineLabel(photo_id=photo.id, label=label, confidence=confidence))
    await session.commit()


class TestTheEyeResultInThePhotoOut:
    async def test_an_eye_header_carries_album_level_revision_and_labels(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(
            db_session,
            photo,
            source=MotifAssessmentSource.EYE,
            provider=None,
            computed_at=datetime(2026, 9, 14, 9, 0, 0),
        )
        await _add_eye_shadow(db_session, photo)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"]["source"] == "eye"
        assert item["motif_assessment"]["provider"] is None
        assert item["eye_result"] == {
            "album_level": 4,
            "model_revision": "v1.0.0",
            "mapping_version": "eye-4.2.3/v2",
            "computed_at": "2026-09-14T09:00:00",
            "fine_labels": ["dog", "mountain"],
        }

    async def test_the_labels_are_ordered_by_confidence_not_by_insertion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, source=MotifAssessmentSource.EYE, provider=None)
        await _add_eye_shadow(
            db_session, photo, labels=(("schwach", 0.55), ("stark", 0.9), ("mittel", 0.7))
        )

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["eye_result"]["fine_labels"] == ["stark", "mittel", "schwach"]

    async def test_a_v1_row_reports_its_own_mapping_version(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Antwort nennt die Fassung DER ZEILE, nicht die Lauf-Fassung."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, source=MotifAssessmentSource.EYE, provider=None)
        await _add_eye_shadow(db_session, photo, mapping_version="eye-4.2.3/v1")

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["eye_result"]["mapping_version"] == "eye-4.2.3/v1"

    async def test_a_cloud_header_stays_and_the_shadow_is_not_shown(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """AK "Cloud gilt weiter": die Cloud-Kopfzeile bleibt die Grundlage, `eye_result` ist
        `null` - sonst zeigte die Ansicht Eye-Werte als die gueltigen einer Cloud-Kopfzeile."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, strengths={"tiere": 0.8})
        await _add_eye_shadow(db_session, photo)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"]["source"] == "cloud"
        assert item["eye_result"] is None

    async def test_a_shadow_without_a_header_is_not_shown(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _add_eye_shadow(db_session, photo)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"] is None
        assert item["eye_result"] is None

    async def test_a_photo_without_an_eye_run_carries_null(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["eye_result"] is None
