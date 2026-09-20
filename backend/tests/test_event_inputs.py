"""Tests fuer den herausgezogenen Aufbau der `EventCandidate`-Menge
(specs/features/0506-cluster-als-anlass.md, decisions/0117-*.md Punkt 5).

Der Aufbau hat ab hier ZWEI Aufrufer - den Lauf und das Messkommando -, und beide gehen ueber
diese eine Stelle. Eine nachbildende zweite Fassung maesse etwas anderes, als der Lauf tut,
waehrend beide fuer sich gruen blieben.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.event_inputs import read_event_inputs
from photosort.models import (
    MotifAssessmentSource,
    Photo,
    PhotoLandmarkDetection,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    Project,
    User,
)

NOW = datetime(2026, 7, 20, 10, 0, 0)


async def _project(session: AsyncSession, name: str = "Reise") -> int:
    project = Project(name=name, opencloud_drive_id="drive", opencloud_path=f"/Fotos/{name}")
    session.add(project)
    await session.flush()
    return project.id


async def _photo(
    session: AsyncSession,
    project_id: int,
    *,
    minutes: int,
    gps: tuple[float, float] | None = None,
) -> int:
    photo = Photo(
        project_id=project_id,
        relative_path=f"img{minutes:03d}.jpg",
        etag=f"etag-{project_id}-{minutes}",
        content_length=1000,
        taken_at=NOW + timedelta(minutes=minutes),
        taken_at_original=NOW + timedelta(minutes=minutes),
        last_modified=NOW,
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )
    session.add(photo)
    await session.flush()
    return photo.id


async def _landmark(session: AsyncSession, photo_id: int, *, name: str, confidence: float) -> None:
    session.add(
        PhotoLandmarkDetection(photo_id=photo_id, name=name, confidence=confidence, computed_at=NOW)
    )
    await session.flush()


async def _motifs(
    session: AsyncSession,
    photo_id: int,
    *,
    strengths: dict[str, float],
    excluded_document: bool = False,
) -> None:
    session.add(
        PhotoMotifAssessment(
            photo_id=photo_id,
            source=MotifAssessmentSource.LOCAL,
            excluded_document=excluded_document,
            computed_at=NOW,
        )
    )
    await session.flush()
    session.add_all(
        [
            PhotoMotifStrength(photo_id=photo_id, motif_key=key, strength=value)
            for key, value in strengths.items()
        ]
    )
    await session.flush()


@pytest.mark.asyncio
class TestTheCandidateSetIsExactlyWhatWasAsked:
    async def test_only_the_named_photos_become_candidates(self, db_session: AsyncSession) -> None:
        """Die Kandidatenmenge IST die uebergebene Id-Menge. Ein aussortiertes Foto des Projekts
        speist die Inferenzbasis, wird aber nie selbst Kandidat - sonst traete es in die
        Gliederung ein, obwohl es das Ausschuss-Gate nicht ueberlebt hat."""
        project_id = await _project(db_session)
        kept = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        await _photo(db_session, project_id, minutes=5, gps=(43.52, 16.45))

        inputs = await read_event_inputs(db_session, project_id, [kept])

        assert [candidate.photo_id for candidate in inputs.candidates] == [kept]

    async def test_an_empty_candidate_set_is_a_valid_result(self, db_session: AsyncSession) -> None:
        project_id = await _project(db_session)
        await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))

        inputs = await read_event_inputs(db_session, project_id, [])

        assert inputs.candidates == ()
        # Die Inferenzbasis bleibt das ganze Projekt - sie haengt nicht an der Kandidatenmenge.
        assert len(inputs.entries) == 1


@pytest.mark.asyncio
class TestTheTwoPlacesSideBySide:
    """`location` ist der WIRKSAME Ort und bestimmt die Grenzen; `gps_lat`/`gps_lon` sind die
    GEMESSENEN Werte und speisen ausschliesslich den Ortsbezug des Events."""

    async def test_a_measured_photo_carries_both_and_is_not_inferred(
        self, db_session: AsyncSession
    ) -> None:
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))

        [candidate] = (await read_event_inputs(db_session, project_id, [photo_id])).candidates

        assert candidate.gps_lat == 43.51
        assert candidate.location is not None
        assert candidate.location.lat == 43.51
        assert candidate.location.inferred is False

    async def test_a_photo_without_a_coordinate_inherits_but_keeps_its_gps_empty(
        self, db_session: AsyncSession
    ) -> None:
        """Der tragende Fall: der uebernommene Ort bestimmt die Grenzen, erscheint aber NIE als
        gemessener Wert."""
        project_id = await _project(db_session)
        await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        without = await _photo(db_session, project_id, minutes=1)

        [candidate] = (await read_event_inputs(db_session, project_id, [without])).candidates

        assert candidate.gps_lat is None
        assert candidate.gps_lon is None
        assert candidate.location is not None
        assert (candidate.location.lat, candidate.location.inferred) == (43.51, True)

    async def test_the_inference_base_stops_at_the_project_border(
        self, db_session: AsyncSession
    ) -> None:
        """Ohne die ausgeschriebene Bindung an `Photo.project_id` erbte ein Foto Koordinaten aus
        einem FREMDEN Projekt, und die Event-Grenzen in Projekt A haengten an Fotos aus B."""
        own = await _project(db_session, "Eigen")
        foreign = await _project(db_session, "Fremd")
        await _photo(db_session, foreign, minutes=0, gps=(43.51, 16.44))
        without = await _photo(db_session, own, minutes=1)

        [candidate] = (await read_event_inputs(db_session, own, [without])).candidates

        assert candidate.location is None


@pytest.mark.asyncio
class TestTheLandmarkNameComesThroughTheReadingGuard:
    async def test_a_name_above_the_threshold_arrives(self, db_session: AsyncSession) -> None:
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, minutes=0)
        await _landmark(db_session, photo_id, name="Diokletianpalast", confidence=0.9)

        [candidate] = (await read_event_inputs(db_session, project_id, [photo_id])).candidates

        assert candidate.landmark_name == "Diokletianpalast"

    async def test_an_unsure_row_yields_no_usable_name(self, db_session: AsyncSession) -> None:
        """Die Grenze wirkt an der LESESTELLE (ADR 0107 Punkt 2): die Zeile bleibt vollstaendig,
        verwendbar ist sie nicht. Ein direkter Zugriff auf `PhotoLandmarkDetection.name` haette
        hier einen Namen."""
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, minutes=0)
        await _landmark(db_session, photo_id, name="Diokletianpalast", confidence=0.1)

        [candidate] = (await read_event_inputs(db_session, project_id, [photo_id])).candidates

        assert candidate.landmark_name is None


@pytest.mark.asyncio
class TestTheMotifPictureKeepsItsThreeStates:
    async def test_no_header_stays_none(self, db_session: AsyncSession) -> None:
        """`None` heisst "noch nicht klassifiziert" und ist ausdruecklich etwas anderes als eine
        leere Abbildung - sonst zerrisse ein unklassifiziertes Foto ein Event, statt uebergangen
        zu werden."""
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, minutes=0)

        [candidate] = (await read_event_inputs(db_session, project_id, [photo_id])).candidates

        assert candidate.motif_strengths is None
        assert candidate.excluded_document is False

    async def test_a_header_whose_motifs_are_all_weak_is_a_mapping_not_none(
        self, db_session: AsyncSession
    ) -> None:
        """Der Unterschied zum Fall darueber: hier IST klassifiziert worden, es traegt nur kein
        Motiv. Diese Abbildung redet beim Motivwechsel voll mit; `None` taete es nicht. Ob aus den
        Zahlen ein getragenes Motiv wird, entscheidet allein `selection.py::carried_motifs`."""
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, minutes=0)
        await _motifs(db_session, photo_id, strengths={"strand": 0.01, "stadt": 0.02})

        [candidate] = (await read_event_inputs(db_session, project_id, [photo_id])).candidates

        assert candidate.motif_strengths == {"strand": 0.01, "stadt": 0.02}

    async def test_the_strengths_arrive_as_plain_numbers(self, db_session: AsyncSession) -> None:
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, minutes=0)
        await _motifs(db_session, photo_id, strengths={"strand": 0.8, "stadt": 0.1})

        [candidate] = (await read_event_inputs(db_session, project_id, [photo_id])).candidates

        assert candidate.motif_strengths == {"strand": 0.8, "stadt": 0.1}

    async def test_an_excluded_document_is_marked(self, db_session: AsyncSession) -> None:
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, minutes=0)
        await _motifs(db_session, photo_id, strengths={"stadt": 0.9}, excluded_document=True)

        [candidate] = (await read_event_inputs(db_session, project_id, [photo_id])).candidates

        assert candidate.excluded_document is True

    async def test_a_hand_correction_reaches_the_candidate(self, db_session: AsyncSession) -> None:
        """WIRKSAME Staerken, nicht die rohe Staerkezeile: Eine Handkorrektur setzt sich hier
        durch, weil der Aufbau ueber `load_effective_strengths` liest. Ein Zugriff auf
        `PhotoMotifStrength` allein liesse die Korrektur unter den Tisch fallen, und das faende
        seit ADR 0119 kein Fall mehr ueber die Gliederung - der Motivwechsel bewegt dort nichts
        mehr, und `selection.py` liest dieselben Staerken."""
        project_id = await _project(db_session)
        photo_id = await _photo(db_session, project_id, minutes=0)
        await _motifs(db_session, photo_id, strengths={"tiere": 0.0})
        user = User(username="daniel", password_hash="hashed-value")
        db_session.add(user)
        await db_session.flush()
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo_id, user_id=user.id, motif_key="tiere", applies=True
            )
        )
        await db_session.flush()

        [candidate] = (await read_event_inputs(db_session, project_id, [photo_id])).candidates

        assert candidate.motif_strengths is not None
        assert candidate.motif_strengths["tiere"] > 0.0
