"""Tests fuer das rein lesende Messkommando der Event-Bildung
(specs/features/0506-cluster-als-anlass.md, decisions/0117-*.md).

Aufbau nach architecture/0002-testkonzept.md, Sektion "Ein rein lesendes Kommando im
Produktivpaket": die Zaehlbloecke rein und ohne DB gegen einen von Hand ausgerechneten
Projektgraphen, `main()` synchron gegen eine dateibasierte SQLite in `tmp_path`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.event_probe import EventProbeError, read_event_probe_input, size_counts
from photosort.events import EventCandidate, explain_events
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
)

NOW = datetime(2026, 7, 20, 10, 0, 0)


def _candidate(minutes: float, *, gps: tuple[float, float] | None = None) -> EventCandidate:
    """Ein Kandidat OHNE Ort, sofern keiner genannt ist: die Zeitluecke allein gliedert dann."""
    return EventCandidate(
        photo_id=int(minutes * 60),
        taken_at=NOW + timedelta(minutes=minutes),
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )


async def _project(session: AsyncSession, name: str = "Reise") -> int:
    project = Project(name=name, opencloud_drive_id="drive", opencloud_path=f"/Fotos/{name}")
    session.add(project)
    await session.flush()
    return project.id


async def _photo(
    session: AsyncSession,
    project_id: int,
    *,
    minutes: float,
    gps: tuple[float, float] | None = None,
) -> int:
    photo = Photo(
        project_id=project_id,
        relative_path=f"img{int(minutes * 60):06d}.jpg",
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


async def _successful_run(
    session: AsyncSession, project_id: int, photo_ids: list[int]
) -> CriterionScoringRun:
    """Ein erfolgreicher Kriterien-Lauf samt seiner Rangzeilen - die Kandidatenmenge des Laufs.

    Ein Event je Rangzeile: Block A rechnet die Gliederung ohnehin neu, die Event-Zeile traegt
    hier nur den Fremdschluessel."""
    scoring_run = ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project_id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()
    event = Event(
        criterion_scoring_run_id=run.id, position=1, started_at=NOW, ended_at=NOW, place_kind=None
    )
    session.add(event)
    await session.flush()
    session.add_all(
        [
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo_id,
                event_id=event.id,
                rank_score=0.5,
                rank_position=position,
            )
            for position, photo_id in enumerate(photo_ids, start=1)
        ]
    )
    await session.flush()
    return run


@pytest.mark.asyncio
class TestTheReadPath:
    """Der einzige Datenbankzugriff des Kommandos - und er liest ausschliesslich."""

    async def test_an_unknown_project_refuses_loudly(self, db_session: AsyncSession) -> None:
        with pytest.raises(EventProbeError):
            await read_event_probe_input(db_session, 4711)

    async def test_a_project_without_a_successful_run_is_marked_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """ "Kein erfolgreicher Lauf" ist etwas anderes als "ein Lauf ohne Kandidaten" - eine
        gemeinsame leere Menge verwischte beides."""
        project_id = await _project(db_session)
        await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))

        probe = await read_event_probe_input(db_session, project_id)

        assert probe.run_found is False
        assert probe.candidates == ()

    async def test_the_candidates_are_the_ranked_photos_of_the_run(
        self, db_session: AsyncSession
    ) -> None:
        """Die Kandidatenmenge des Laufs sind genau die Fotos seiner Rangzeilen - nicht die
        aktuellen Fotos des Projekts. Ein nach dem Lauf aussortiertes oder hinzugekommenes Foto
        speist die Inferenzbasis, wird aber nie Kandidat."""
        project_id = await _project(db_session)
        ranked = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        unranked = await _photo(db_session, project_id, minutes=5, gps=(43.52, 16.45))
        await _successful_run(db_session, project_id, [ranked])

        probe = await read_event_probe_input(db_session, project_id)

        assert probe.run_found is True
        assert [candidate.photo_id for candidate in probe.candidates] == [ranked]
        # Die Inferenzbasis bleibt das ganze Projekt: ein aussortiertes Foto traegt eine ebenso
        # gueltige Koordinate.
        assert {entry.photo_id for entry in probe.entries} == {ranked, unranked}

    async def test_only_the_latest_successful_run_is_measured(
        self, db_session: AsyncSession
    ) -> None:
        project_id = await _project(db_session)
        older = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        newer = await _photo(db_session, project_id, minutes=5, gps=(43.52, 16.45))
        await _successful_run(db_session, project_id, [older])
        await _successful_run(db_session, project_id, [newer])

        probe = await read_event_probe_input(db_session, project_id)

        assert [candidate.photo_id for candidate in probe.candidates] == [newer]


class TestBlockASizes:
    """Wie sich die Bilder heute ueber die Cluster verteilen - der Ausgangswert, gegen den die
    Abnahme laeuft."""

    def test_the_hand_computed_graph(self) -> None:
        """Vier Events zu 3, 1, 2 und 1 Fotos. Die Zeitluecke steht bei einer Stunde; die
        Abstaende sind so gewaehlt, dass sie klar darueber bzw. darunter liegen - kein Fall
        haengt an einem Zahlwert der Schwelle."""
        formation = explain_events(
            [
                # Event 1: drei Fotos ueber acht Minuten.
                _candidate(0),
                _candidate(4),
                _candidate(8),
                # Event 2: ein einzelnes Foto.
                _candidate(200),
                # Event 3: zwei Fotos ueber zwei Minuten.
                _candidate(400),
                _candidate(402),
                # Event 4: ein einzelnes Foto.
                _candidate(600),
            ]
        )

        counts = size_counts(formation)

        assert counts.events_total == 4
        assert counts.photos_total == 7
        assert counts.events_by_photo_count == {1: 2, 2: 1, 3: 1}
        assert counts.single_photo_events == 2
        # Die vier Groessen sortiert: 1, 1, 2, 3 - der Median liegt zwischen 1 und 2.
        assert counts.median_photos == 1.5
        assert counts.largest_event_photos == 3
        # DAUERN, nie Anfang oder Ende (S2): laengste acht Minuten, kuerzeste null (Einzelfoto).
        assert counts.longest_seconds == 8 * 60
        assert counts.shortest_seconds == 0

    def test_a_run_without_a_single_event_is_a_valid_result(self) -> None:
        """Ein Lauf ohne Kandidaten ist ein gueltiges Messergebnis, kein Fehler - es gibt dann
        keine laengste und keine kuerzeste Dauer, und `None` ist etwas anderes als null."""
        counts = size_counts(explain_events([]))

        assert counts.events_total == 0
        assert counts.photos_total == 0
        assert counts.events_by_photo_count == {}
        assert counts.single_photo_events == 0
        assert counts.median_photos is None
        assert counts.largest_event_photos == 0
        assert counts.longest_seconds is None
        assert counts.shortest_seconds is None
