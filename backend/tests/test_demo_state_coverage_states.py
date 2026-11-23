"""Demo-Zustands-Seeder: Cloud-Bilanz, Kopfzeilen-Zustaende, Bezirksregel, Kamera-, Motiv- und
Albumtauglichkeits-Zustaende, Albumentwurf.
(Aufgeteilt aus test_demo_state.py, Spec 0651.)
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import demo_state
from photosort.album_suitability import (
    ALBUM_SUITABILITY_MAX_LEVEL,
    MAX_ALBUM_SUITABILITY_REASON_LENGTH,
)
from photosort.demo_state import (
    RATED_PROJECT_NAME,
    purge_demo_state,
    rebuild_demo_state,
)
from photosort.events import LANDMARK_MIN_SHARE
from photosort.landmark import sanitize_landmark_name
from photosort.models import (
    CriterionScoringRun,
    Event,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoEyeResult,
    PhotoLandmarkDetection,
    PhotoLocalMotifSnapshot,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    Project,
    ProjectCamera,
    RemoteCategoryClassificationRun,
    User,
)
from photosort.motifs import MOTIF_REGISTRY, is_motif_key
from photosort.places import sanitize_place_name
from photosort.quality import QUALITY_CRITERION_WEIGHTS, compute_quality_score
from tests.import_closure import import_closure, module_file
from tests.support.demo_state_rows import _make_user, _photos_of, _project
from tests.time_offset_invariant import assert_time_offset_invariant


class TestTheDemoStateCarriesACloudBalance:
    """specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-
    vier-teilschritte-und-laufeigene-cloud-bilanz.md: die Lauf-Bilanz zeigt erstmals an der
    AUSLOESE-Stelle einen Geldbetrag. Damit sie im Pruefstack/`browse-app` ueberhaupt sichtbar
    ist, muss der Demo-Zustand einen Lauf MIT Cloud-Anteil tragen - und daneben weiterhin einen
    OHNE, sonst verliert die Bilanz-Variante "ohne Cloud-Anreicherung durchgefuehrt" ihren Fall.

    Alle Demo-Werte sind frei erfunden (Spec 0321: nur synthetische Demo-Daten; das Repository
    ist oeffentlich, PR-Anhaenge liegen oeffentlich auf GitHub)."""

    async def test_the_rated_project_has_a_run_with_a_cloud_balance(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, RATED_PROJECT_NAME)
        runs = (
            (
                await db_session.execute(
                    select(CriterionScoringRun).where(CriterionScoringRun.project_id == project.id)
                )
            )
            .scalars()
            .all()
        )

        # Abgeleitet assertiert, nie ueber einen festen Index: die Reihenfolge der Laeufe ist
        # keine Zusage des Seeders, die Existenz der Eigenschaft schon.
        assert any(
            run.remote_category_classification_run_id is not None
            and run.landmark_photos_total is not None
            and run.estimated_cost_usd is not None
            and run.cloud_requested
            for run in runs
        ), [
            (
                run.remote_category_classification_run_id,
                run.landmark_photos_total,
                run.estimated_cost_usd,
            )
            for run in runs
        ]

    async def test_the_linked_remote_run_belongs_to_the_same_project(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Fremdschluessel darf nicht auf eine Zeile eines anderen Demo-Projekts zeigen -
        sonst zeigte die Bilanz fremde Kosten als eigene, genau der Zuordnungsfehler, den ADR
        0068 Punkt 3 beseitigt."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, RATED_PROJECT_NAME)
        run = (
            (
                await db_session.execute(
                    select(CriterionScoringRun).where(
                        CriterionScoringRun.project_id == project.id,
                        CriterionScoringRun.remote_category_classification_run_id.is_not(None),
                    )
                )
            )
            .scalars()
            .first()
        )
        assert run is not None
        remote_run = await db_session.get(
            RemoteCategoryClassificationRun, run.remote_category_classification_run_id
        )

        assert remote_run is not None
        assert remote_run.project_id == project.id
        assert remote_run.failed_calls is not None

    async def test_at_least_one_project_still_has_a_run_without_any_cloud_phase(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        runs = (await db_session.execute(select(CriterionScoringRun))).scalars().all()

        assert any(
            not run.cloud_requested
            and run.remote_category_classification_run_id is None
            and run.landmark_photos_total is None
            for run in runs
        )


# ---------------------------------------------------------------------------------------------
# Teststrategie der Spec 0425: der Seeder MUSS alle vier
# Anzeigezustaende der Event-Ueberschrift erzeugen - sonst ist die Sichtpruefung ueber
# `browse-app` fuer drei davon blind, und das ist die einzige nicht automatisierte
# Kontrollinstanz dieses Features.
class TestDemoStateCoversAllFourHeadingStates:
    async def _rated_state(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> tuple[dict[int, list[Photo]], dict[int, Event], dict[int, str]]:
        """Die Fotos des "bewertet"-Projekts nach ihrem Event gruppiert, die `events`-Zeilen
        selbst und die Landmark-Namen je Foto-Id."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = {photo.id: photo for photo in await _photos_of(db_session, RATED_PROJECT_NAME)}
        rankings = (
            (
                await db_session.execute(
                    select(PhotoRanking).where(PhotoRanking.photo_id.in_(photos))
                )
            )
            .scalars()
            .all()
        )
        by_event: dict[int, list[Photo]] = {}
        for ranking in rankings:
            members = by_event.setdefault(ranking.event_id, [])
            if photos[ranking.photo_id] not in members:
                members.append(photos[ranking.photo_id])
        events = {
            row.id: row
            for row in (
                (await db_session.execute(select(Event).where(Event.id.in_(by_event))))
                .scalars()
                .all()
            )
        }
        names = {
            row.photo_id: row.name
            for row in (
                (
                    await db_session.execute(
                        select(PhotoLandmarkDetection).where(
                            PhotoLandmarkDetection.photo_id.in_(photos)
                        )
                    )
                )
                .scalars()
                .all()
            )
        }
        return by_event, events, names

    @staticmethod
    def _derived_kind(members: list[Photo], names: dict[int, str]) -> str | None:
        """Bildet die Stufenentscheidung aus `events.py::_place_of` nach - bewusst hier im Test
        und nicht durch einen Aufruf der Produktionsfunktion: geprueft gehoert, dass die DATEN
        alle vier Zustaende hergeben, nicht dass die Funktion sich selbst gleicht.

        MIT dem Rueckhalt aus Spec 0514: Ein einzelnes erkanntes Foto benennt sein Event nur, wenn
        es mindestens `LANDMARK_MIN_SHARE` der Mitglieder ist. Ohne diese Bedingung behauptete die
        Nachbildung fuer eine zu schwach gestuetzte Lage einen `landmark`-Zustand, den der Lauf nie
        schriebe - und der Vergleich darunter bliebe still gruen."""
        share = LANDMARK_MIN_SHARE
        carriers = sum(1 for photo in members if photo.id in names)
        if carriers > 0 and carriers * share.denominator >= len(members) * share.numerator:
            return "landmark"
        cells = {
            (round(photo.gps_lat, 2), round(photo.gps_lon, 2))
            for photo in members
            if photo.gps_lat is not None and photo.gps_lon is not None
        }
        if not cells:
            return None
        return "coordinate" if len(cells) == 1 else "multiple"

    async def test_the_rated_project_produces_every_heading_state_at_least_once(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _by_event, events, _names = await self._rated_state(db_session, tmp_path)

        assert {event.place_kind for event in events.values()} == {
            "landmark",
            "coordinate",
            "multiple",
            None,
        }

    async def test_exactly_one_event_carries_a_name_and_the_others_do_not(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Beide Ueberschriftenformen muessen in der Sichtpruefung vorkommen: der Name und der
        Rueckfall auf "Position N"."""
        _by_event, events, _names = await self._rated_state(db_session, tmp_path)

        named = [event for event in events.values() if event.landmark_name is not None]
        assert len(named) == 1
        assert len(events) > 1

    async def test_the_stored_place_matches_what_its_members_imply(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Seeder darf keinen Zustand erzeugen, den die Anwendung selbst nie schriebe: die
        persistierten Ortsfelder muessen zur Rangfolge ueber die GEMESSENEN Koordinaten der
        Mitglieder passen."""
        by_event, events, names = await self._rated_state(db_session, tmp_path)

        for event_id, members in by_event.items():
            assert events[event_id].place_kind == self._derived_kind(members, names), event_id

    async def test_the_stored_field_combination_holds(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Invariante M7, an den tatsaechlich geschriebenen Zeilen geprueft."""
        _by_event, events, _names = await self._rated_state(db_session, tmp_path)

        for event in events.values():
            if event.place_kind == "landmark":
                assert event.landmark_name is not None
            elif event.place_kind == "coordinate":
                assert event.place_lat is not None and event.place_lon is not None
            elif event.place_kind == "multiple":
                assert (event.place_lat, event.place_lon) == (None, None)
            else:
                assert event.place_kind is None
                assert (event.place_lat, event.place_lon) == (None, None)

    async def test_the_events_of_the_run_are_chronological_and_non_overlapping(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _by_event, events, _names = await self._rated_state(db_session, tmp_path)

        ordered = sorted(events.values(), key=lambda event: event.position)
        assert [event.position for event in ordered] == list(range(1, len(ordered) + 1))
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            assert earlier.ended_at <= later.started_at

    async def test_at_least_one_photo_carries_no_coordinate_at_all(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der haeufigste reale Fall (kein GPS im EXIF) muss in der Demo vorkommen - sonst zeigt
        sie ausgerechnet den Normalzustand nicht."""
        by_event, _events, _names = await self._rated_state(db_session, tmp_path)
        photos = [photo for members in by_event.values() for photo in members]

        assert any(photo.gps_lat is None and photo.gps_lon is None for photo in photos)

    async def test_no_photo_ever_carries_half_a_coordinate(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Paar-Invariante: die Demo darf keinen Zustand erzeugen, den `extract_gps` selbst nie
        schriebe."""
        by_event, _events, _names = await self._rated_state(db_session, tmp_path)
        photos = [photo for members in by_event.values() for photo in members]

        for photo in photos:
            assert (photo.gps_lat is None) == (photo.gps_lon is None), photo.relative_path

    async def test_every_demo_coordinate_lies_inside_the_valid_range(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        by_event, _events, _names = await self._rated_state(db_session, tmp_path)
        photos = [photo for members in by_event.values() for photo in members]

        for photo in photos:
            if photo.gps_lat is None or photo.gps_lon is None:
                continue
            assert -90.0 <= photo.gps_lat <= 90.0, photo.relative_path
            assert -180.0 <= photo.gps_lon <= 180.0, photo.relative_path
            assert (photo.gps_lat, photo.gps_lon) != (0.0, 0.0), photo.relative_path

    async def test_the_landmark_name_survives_the_sanitisation_of_the_read_path(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Ein Demo-Name, den die Sanitisierung verwuerfe (zu lang oder danach leer), liesse das
        Event still auf die Koordinatenstufe zurueckfallen - die Sichtpruefung saehe dann den
        falschen Zustand."""
        _by_event, _events, names = await self._rated_state(db_session, tmp_path)

        assert names
        for name in names.values():
            assert sanitize_landmark_name(name) == name

    async def test_the_coordinates_are_deterministic_across_two_rebuilds(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"
        await rebuild_demo_state(db_session, first_dir, large_collection_photo_count=3)
        first = {
            photo.relative_path: (photo.gps_lat, photo.gps_lon)
            for photo in await _photos_of(db_session, RATED_PROJECT_NAME)
        }
        await rebuild_demo_state(db_session, second_dir, large_collection_photo_count=3)
        second = {
            photo.relative_path: (photo.gps_lat, photo.gps_lon)
            for photo in await _photos_of(db_session, RATED_PROJECT_NAME)
        }

        assert first == second


class TestTheDemoStateShowsTheDistrictRule(TestDemoStateCoversAllFourHeadingStates):
    """specs/features/0434-ortsnamen-fuer-events.md, Teil 2: Ohne den Kardinalitaetsfall - zwei
    Events mit DEMSELBEN Ortsnamen und VERSCHIEDENEN Vierteln - ist die Viertel-Regel im Browser
    unsichtbar, und `browse-app` kann sie nicht zeigen.

    Erbt die Lage-Hilfe der Ueberschriftenzustaende: es ist derselbe Lauf desselben Projekts."""

    async def test_two_events_share_a_locality_and_differ_in_their_district(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        _by_event, events, _names = await self._rated_state(db_session, tmp_path)

        composed = [
            event.place_name
            for event in events.values()
            if event.place_name is not None and ", " in event.place_name
        ]
        # Seit Spec 0514 traegt auch das Landmark-Event einen Ortsnamen - drei Events tragen die
        # zusammengesetzte Form, zwei Viertel stehen darin.
        assert len(composed) == 3
        localities = {name.split(", ")[0] for name in composed}
        districts = {name.split(", ")[1] for name in composed}
        assert len(localities) == 1
        assert len(districts) == 2

    async def test_two_districts_never_come_out_of_a_single_cell(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Demo darf keinen Zustand erzeugen, den die Anwendung selbst nie schriebe: Dieselbe
        Zelle ergibt dieselbe Auskunft - zwei VERSCHIEDENE Viertel aus einer gemeinsamen Zelle
        gaebe es nie.

        Die Umkehrung gilt ausdruecklich NICHT: Zwei Events aus derselben Zelle tragen dasselbe
        Viertel, und genau das ist seit Spec 0514 der Fall von Landmark- und
        "Mehrere Orte"-Event. Geprueft wird deshalb JE VIERTEL gegen die uebrigen."""
        by_event, events, _names = await self._rated_state(db_session, tmp_path)

        named_events: dict[str, list[int]] = {}
        cells_by_event: dict[int, set[tuple[float, float]]] = {}
        for event_id, members in by_event.items():
            name = events[event_id].place_name
            if name is None:
                continue
            assert ", " in name, name
            named_events.setdefault(name.split(", ")[1], []).append(event_id)
            cells_by_event[event_id] = {
                (round(photo.gps_lat, 2), round(photo.gps_lon, 2))
                for photo in members
                if photo.gps_lat is not None and photo.gps_lon is not None
            }

        assert len(named_events) == 2
        # Der Fall, den die Zusage traegt: EIN Viertel wird von ZWEI Events getragen.
        assert max(len(ids) for ids in named_events.values()) >= 2
        [first, second] = named_events.values()
        for left in first:
            for right in second:
                assert not cells_by_event[left] & cells_by_event[right]

    async def test_the_landmark_event_carries_a_place_name_and_the_placeless_one_does_not(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Spec 0514, ADR 0120: Der Ortsname tritt NEBEN die Sehenswuerdigkeit, statt von ihr
        verdraengt zu werden - ohne diesen Fall zeigt `browse-app` die kombinierte Ueberschrift
        nie. Und ohne jede Ortsangabe gibt es weiterhin nichts aufzuloesen. Ein Seeder, der das
        anders schriebe, erzeugte einen Zustand, den die Anwendung selbst nie schreibt."""
        _by_event, events, _names = await self._rated_state(db_session, tmp_path)

        landmark_events = [event for event in events.values() if event.place_kind == "landmark"]
        assert landmark_events
        for event in events.values():
            if event.place_kind is None:
                assert event.place_name is None
            if event.place_kind == "landmark":
                assert event.landmark_name is not None
                assert event.place_name is not None
                # Die KOORDINATENSTUFE bleibt verdraengt: der Name ist kein Ortsbezug.
                assert (event.place_lat, event.place_lon) == (None, None)

    async def test_every_seeded_name_survives_the_sanitisation_unchanged(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Literale muessen durch denselben Rand passen wie ein echter Name - sonst zeigte der
        Browser einen Zustand, den der Lauf nie erzeugt."""
        _by_event, events, _names = await self._rated_state(db_session, tmp_path)

        seeded = [event.place_name for event in events.values() if event.place_name is not None]
        assert seeded
        for name in seeded:
            assert sanitize_place_name(name) == name

    def test_the_seeder_builds_no_resolver_and_fetches_no_dataset(self) -> None:
        """`demo_state` schreibt Ortsnamen als LITERALE und baut nie einen Auflöser (S10).

        Gemessen am eigenen Quelltext und nicht an der Import-Huelle: Der Seeder ruft
        `worker.rebuild_run_selection` und traegt das Auflöser-Modul deshalb ohnehin in seiner
        Huelle - erreichbar heisst hier nicht gerufen. Das Bezugskommando bleibt dagegen auch aus
        der Huelle heraus."""
        assert "photosort.place_dataset" not in import_closure("photosort.demo_state")

        path = module_file("photosort.demo_state")
        assert path is not None
        source = path.read_text(encoding="utf-8")

        assert "build_place_resolver" not in source
        assert "GeoNamesResolver" not in source


class TestDemoStateCoversEveryCameraState:
    """specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 8: Alle Zustaende, die
    Kameraliste und Fotoansicht zeigen muessen, entstehen TATSAECHLICH - sonst ist die
    Sichtpruefung ueber den `browse-app`-Skill fuer die Kennzeichnung "korrigiert" blind."""

    async def _rated_project_id(self, db_session: AsyncSession, tmp_path: Path) -> int:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        project = await _project(db_session, RATED_PROJECT_NAME)
        return project.id

    async def test_it_seeds_one_camera_without_and_one_with_an_offset(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project_id = await self._rated_project_id(db_session, tmp_path)

        cameras = (
            (
                await db_session.execute(
                    select(ProjectCamera)
                    .where(ProjectCamera.project_id == project_id)
                    .order_by(ProjectCamera.make)
                )
            )
            .scalars()
            .all()
        )

        offsets = sorted(camera.offset_minutes for camera in cameras)
        assert len(cameras) == 2
        assert offsets[0] < 0, "die Kamera MIT Versatz fehlt"
        assert offsets[-1] == 0, "die Kamera OHNE Versatz fehlt"

    async def test_the_photos_of_the_offset_camera_carry_a_shifted_effective_time(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project_id = await self._rated_project_id(db_session, tmp_path)

        rows = (
            await db_session.execute(
                select(Photo.taken_at, Photo.taken_at_original, ProjectCamera.offset_minutes)
                .join(ProjectCamera, ProjectCamera.id == Photo.camera_id)
                .where(Photo.project_id == project_id, ProjectCamera.offset_minutes != 0)
            )
        ).all()

        assert rows, "keine Fotos an der Kamera mit Versatz - der Zustand fehlt der Demo"
        for taken_at, taken_at_original, offset in rows:
            assert taken_at != taken_at_original
            assert taken_at == taken_at_original + timedelta(minutes=offset)

    async def test_some_photos_have_no_determinable_camera(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der dritte Zustand: `camera = null`, beide Zeiten gleich, kein Listeneintrag."""
        project_id = await self._rated_project_id(db_session, tmp_path)

        rows = (
            await db_session.execute(
                select(Photo.taken_at, Photo.taken_at_original).where(
                    Photo.project_id == project_id, Photo.camera_id.is_(None)
                )
            )
        ).all()

        assert rows, "kein Foto ohne bestimmbare Kamera - der Zustand fehlt der Demo"
        for taken_at, taken_at_original in rows:
            assert taken_at == taken_at_original

    async def test_the_effective_times_still_grow_strictly_with_the_photo_index(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Bedingung, die den Demo-Versatz klein haelt: Die vier Demo-Events sind
        zusammenhaengende Bloecke ueber die nach `taken_at` aufsteigende Liste. Ein Versatz, der
        Fotos ueber ihre Nachbarn schiebt, erzeugte ueberlappende Events - einen Zustand, den die
        Anwendung selbst nie schreibt."""
        project_id = await self._rated_project_id(db_session, tmp_path)

        times = (
            (
                await db_session.execute(
                    select(Photo.taken_at)
                    .where(Photo.project_id == project_id)
                    .order_by(Photo.relative_path)
                )
            )
            .scalars()
            .all()
        )

        assert times == sorted(times)
        assert len(set(times)) == len(times)

    async def test_the_invariant_holds_over_every_seeded_project(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Nachsatz jedes Falls, der Fotos schreibt - hier ueber ALLE Demo-Projekte."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        project_ids = (await db_session.execute(select(Project.id))).scalars().all()

        assert project_ids
        for project_id in project_ids:
            await assert_time_offset_invariant(db_session, project_id)


class TestTheDemoStateShowsEveryMotifState:
    """specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 6: der Seeder erzeugt Kopfzeilen,
    Staerken und eine Korrektur.

    Geprueft wird, dass ALLE VIER Fotozustaende im Bestand vorkommen - sonst sieht die
    Sichtpruefung im Browser nur den Regelfall, und die drei Sonderdarstellungen (Satz statt
    Liste, lokale Grundlage, Ausschluss) bleiben ungesehen."""

    async def test_every_assessed_photo_carries_a_full_eight_entry_vector(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        for photo in await _photos_of(db_session, RATED_PROJECT_NAME):
            header = await db_session.get(PhotoMotifAssessment, photo.id)
            if header is None:
                continue
            keys = (
                (
                    await db_session.execute(
                        select(PhotoMotifStrength.motif_key).where(
                            PhotoMotifStrength.photo_id == photo.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert set(keys) == set(MOTIF_REGISTRY), photo.relative_path

    async def test_exactly_one_photo_has_no_assessment_at_all(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Zustand „noch nicht klassifiziert" - ohne ihn zeigt die Oberflaeche den Satz statt
        der Liste nie."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        photos = await _photos_of(db_session, RATED_PROJECT_NAME)
        without = [
            photo
            for photo in photos
            if await db_session.get(PhotoMotifAssessment, photo.id) is None
        ]

        assert len(without) == 1

    async def test_cloud_and_exactly_one_eye_basis_occur_and_only_cloud_names_a_provider(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Spec 0609: das frueher lokal grundierte Demo-Foto traegt jetzt die Eye-Kopfzeile -
        die lokale Grundlage wandert als Schnappschuss in die Rueckbaudaten (Produktionspfad).
        Eye ist kein Cloud-Anbieter, also traegt nur `cloud` einen Anbieternamen."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        rated_photos = await _photos_of(db_session, RATED_PROJECT_NAME)
        headers = [
            header
            for photo in rated_photos
            if (header := await db_session.get(PhotoMotifAssessment, photo.id)) is not None
        ]

        assert {header.source for header in headers} == {
            MotifAssessmentSource.CLOUD,
            MotifAssessmentSource.EYE,
        }
        eye_headers = [h for h in headers if h.source == MotifAssessmentSource.EYE]
        assert len(eye_headers) == 1
        for header in headers:
            assert (header.provider is not None) == (header.source == MotifAssessmentSource.CLOUD)

        eye_photo = await db_session.get(Photo, eye_headers[0].photo_id)
        assert eye_photo is not None
        eye_result = await db_session.get(PhotoEyeResult, eye_photo.id)
        assert eye_result is not None
        assert eye_result.album_level == demo_state.DEMO_EYE_ALBUM_LEVEL
        assert eye_result.model_revision == demo_state.DEMO_EYE_MODEL_REVISION
        assert eye_result.mapping_version == demo_state.EYE_MAPPING_VERSION
        # Der verdraengte lokale Vektor liegt als Rueckbaudatensatz daneben - sonst zeigte die
        # Demo einen Eye-Zustand, den die Anwendung selbst nie erzeugt.
        snapshot = await db_session.get(PhotoLocalMotifSnapshot, eye_photo.id)
        assert snapshot is not None

    async def test_exactly_one_photo_is_excluded_as_a_document(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Ausschluss-Zustand - mit vorhandenen Staerken daneben, denn sie werden nicht auf 0
        gesetzt."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        excluded = [
            header
            for photo in await _photos_of(db_session, RATED_PROJECT_NAME)
            if (header := await db_session.get(PhotoMotifAssessment, photo.id)) is not None
            and header.excluded_document
        ]

        assert len(excluded) == 1

    async def test_there_is_exactly_one_correction_and_it_names_a_real_user(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Seeder legt selbst NIE ein Konto an - die Korrektur haengt an einem vorhandenen
        Nutzer, wie die Bewertungen."""
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        corrections = (await db_session.execute(select(PhotoMotifCorrection))).scalars().all()
        user_ids = set((await db_session.execute(select(User.id))).scalars().all())

        assert len(corrections) == 1
        assert corrections[0].user_id in user_ids
        assert is_motif_key(corrections[0].motif_key)

    async def test_without_any_user_no_correction_is_written(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Gegenprobe zur Nutzerbindung: ohne Konto gibt es keine Korrektur, und der Seeder
        scheitert nicht daran."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        assert (await db_session.execute(select(PhotoMotifCorrection))).scalars().all() == []

    async def test_every_strength_lies_within_the_range(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Demo darf keinen Zustand erzeugen, den die Anwendung selbst nie schriebe."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        strengths = (await db_session.execute(select(PhotoMotifStrength.strength))).scalars().all()

        assert strengths
        for strength in strengths:
            assert 0.0 <= strength <= 1.0

    async def test_every_written_motif_key_belongs_to_the_fixed_set(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        keys = (await db_session.execute(select(PhotoMotifStrength.motif_key))).scalars().all()

        assert keys
        for key in keys:
            assert is_motif_key(key), key

    async def test_the_project_deletion_removes_the_motif_rows_too(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der Seeder raeumt ueber `project_deletion` auf - Auflage S16, hier am Demo-Bestand."""
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        await purge_demo_state(db_session, tmp_path)
        await db_session.commit()

        for model in (PhotoMotifAssessment, PhotoMotifStrength, PhotoMotifCorrection):
            assert (await db_session.execute(select(model))).scalars().all() == []
        assert (await db_session.execute(select(User))).scalars().all() != []


class TestTheDemoStateCarriesTheAlbumSuitability:
    """specs/features/0428-albumtauglichkeit-vom-modell.md: der Seeder traegt die Modellbewertung
    und BEIDE Extreme der Begruendung.

    Ohne sie besucht keine Pruefstack-Spezifikation die Kuratierungsroute mit dem Extremfall, und
    die einzige echte Layoutfrage des Features (sprengt eine sehr lange Begruendung die Kachel?)
    bliebe ungestellt - ein eigener E2E-Spec dafuer entfaellt genau deshalb."""

    async def _suitabilities(self, session: AsyncSession) -> list[PhotoAlbumSuitability]:
        photo_ids = [photo.id for photo in await _photos_of(session, RATED_PROJECT_NAME)]
        return list(
            (
                await session.execute(
                    select(PhotoAlbumSuitability).where(
                        PhotoAlbumSuitability.photo_id.in_(photo_ids)
                    )
                )
            )
            .scalars()
            .all()
        )

    async def test_every_rated_photo_carries_a_level_inside_the_scale(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        rows = await self._suitabilities(db_session)

        assert rows
        for row in rows:
            assert 1 <= row.level <= ALBUM_SUITABILITY_MAX_LEVEL, row.photo_id

    async def test_one_reason_sits_exactly_on_the_length_limit_and_one_is_absent(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """BEIDE Extreme in einem Fall: nur zusammen sind sie die Aussage "die Sichtpruefung
        sieht den laengsten und den fehlenden Text"."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        rows = await self._suitabilities(db_session)

        lengths = {len(row.reason) for row in rows if row.reason is not None}
        assert MAX_ALBUM_SUITABILITY_REASON_LENGTH in lengths
        assert sum(1 for row in rows if row.reason is None) == 1

    async def test_no_reason_exceeds_the_limit(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Demo darf keinen Zustand erzeugen, den die Anwendung selbst nie schriebe."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        for row in await self._suitabilities(db_session):
            assert row.reason is None or len(row.reason) <= MAX_ALBUM_SUITABILITY_REASON_LENGTH

    async def test_every_quality_score_matches_the_formula_over_the_seeded_values(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """`rank_score` ist GERECHNET, nicht gewuerfelt - sonst zeigte die Demo eine Stufe neben
        einem Wert, der nicht zu ihr gehoert."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        photos = await _photos_of(db_session, RATED_PROJECT_NAME)

        for photo in photos:
            suitability = await db_session.get(PhotoAlbumSuitability, photo.id)
            ranking = (
                await db_session.execute(
                    select(PhotoRanking).where(PhotoRanking.photo_id == photo.id)
                )
            ).scalar_one_or_none()
            if suitability is None or ranking is None:
                continue
            values = {
                row.criterion_key: row.value
                for row in (
                    await db_session.execute(
                        select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
                    )
                )
                .scalars()
                .all()
            }

            assert ranking.rank_score == pytest.approx(
                compute_quality_score(suitability.level, values, QUALITY_CRITERION_WEIGHTS)
            ), photo.relative_path

    async def test_only_the_rated_project_carries_the_cloud_approval(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Freigabe ist Teil des dargestellten Zustands: ohne sie koennte die Anwendung die
        Cloud-Bilanz und die Albumtauglichkeit dieses Projekts gar nicht erzeugt haben, und die
        Kuratierung zeigte statt der Kacheln den Hinweis auf die fehlende Freigabe. Als PAAR
        geprueft - der Fall "ohne Cloud" muss im Bestand erhalten bleiben."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        projects = (await db_session.execute(select(Project))).scalars().all()
        approved = {project.name for project in projects if project.cloud_vision_detection_enabled}

        assert approved == {RATED_PROJECT_NAME}
        assert len(projects) > 1

    async def test_the_project_deletion_removes_the_suitability_rows_too(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await _make_user(db_session, "daniel")
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)
        await purge_demo_state(db_session, tmp_path)
        await db_session.commit()

        assert (await db_session.execute(select(PhotoAlbumSuitability))).scalars().all() == []


class TestTheDemoStateCarriesAnAlbumDraft:
    """specs/features/0429-auswahl-richtwert-und-mischung.md: der EINZIGE automatisierte Traeger
    der Aussage "die Demo-Instanz zeigt einen Vorschlag".

    Ein neuer E2E-Spec entsteht fuer diese Story nicht - das Aufnahmekriterium ist nicht erfuellt.
    Der Bestandssatz ist aber nicht folgenlos: setzt `demo_state.py` den Vorschlag nicht, zeigt
    `/curate` auf der Demo-Instanz eine leere Liste, und die dortigen Spezifikationen bleiben
    trotzdem gruen - ihre Vorbedingungen haengen an Ueberschrift und Scrollhoehe, nicht an
    Kacheln."""

    @staticmethod
    async def _rankings_of_the_rated_project(session: AsyncSession) -> list[PhotoRanking]:
        photo_ids = [photo.id for photo in await _photos_of(session, RATED_PROJECT_NAME)]
        return list(
            (
                await session.execute(
                    select(PhotoRanking).where(PhotoRanking.photo_id.in_(photo_ids))
                )
            )
            .scalars()
            .all()
        )

    async def test_the_rated_project_carries_a_non_empty_draft(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        rankings = await self._rankings_of_the_rated_project(db_session)

        assert rankings
        assert [row for row in rankings if row.selection_position is not None]

    async def test_every_event_of_the_rated_project_is_represented(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Abdeckung ist die zugesagte Eigenschaft des Verfahrens - und der Demo-Zustand zeigt
        sie nur, wenn sie ueber ALLE Events des Laufs gilt."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        rankings = await self._rankings_of_the_rated_project(db_session)
        events_with_candidates = {row.event_id for row in rankings if row.rank_score is not None}
        events_in_the_draft = {
            row.event_id for row in rankings if row.selection_position is not None
        }

        assert events_with_candidates
        assert events_in_the_draft == events_with_candidates

    async def test_the_places_of_every_event_are_gapless_from_one(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Demo darf keinen Zustand erzeugen, den die Anwendung selbst nie schriebe - der
        Vorschlag kommt deshalb ueber dieselbe Worker-Funktion und nicht aus einer zweiten
        Vergaberegel im Seeder."""
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        places: dict[int, list[int]] = {}
        for row in await self._rankings_of_the_rated_project(db_session):
            if row.selection_position is not None:
                places.setdefault(row.event_id, []).append(row.selection_position)

        assert places
        for event_id, event_places in places.items():
            assert sorted(event_places) == list(range(1, len(event_places) + 1)), event_id

    async def test_no_photo_without_a_quality_score_is_in_the_draft(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        await rebuild_demo_state(db_session, tmp_path, large_collection_photo_count=3)

        for row in await self._rankings_of_the_rated_project(db_session):
            if row.selection_position is not None:
                assert row.rank_score is not None, row.photo_id
