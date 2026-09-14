"""Die Verdrahtung der Ortsauflösung im Worker (Spec 0434 Teil 2, ADR 0102 Punkt 5, ADR 0105).

Der Auflöser ist hier durchgaengig ein ZAEHLENDES Test-Double: kein automatisierter Test erreicht
je ein Netz oder liest den echten Datensatz, und die Zahl der gestellten Anfragen ist genau das,
worum es in den meisten Faellen geht.

Zwei Stellen, an denen ein stiller Fehler sitzt, und beide sind hier ausgeschrieben: der Treffer
eines abgelegten Eintrags haengt an einem GLEITKOMMA-Schluessel und wird deshalb nach einem echten
Rundgang ueber `flush`/`expunge_all` gemessen - nie aus derselben Abbildung, in die gerade
geschrieben wurde; und die drei Fehler-Ausgaenge sehen ohne einen ZWEITEN Lauf paarweise gleich
aus.
"""

from __future__ import annotations

import ast
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.landmark import LANDMARK_CONFIDENCE_THRESHOLD
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PlaceLookup,
    Project,
    ScanStatus,
    ScoringRun,
)
from photosort.places import PlaceAnswer, PlaceResolver
from photosort.worker import _build_grouping_and_rankings, _place_infos
from tests.import_closure import module_file

_BASE = datetime(2026, 8, 12, 9, 0, 0)

# Zwei Zellen in Berlin und eine in Split - sie unterscheiden sich in der zweiten
# Nachkommastelle, also genau in der Koernung, mit der gefragt und abgelegt wird.
KREUZBERG = (52.5, 13.4)
MITTE = (52.52, 13.4)
SPLIT = (43.51, 16.44)

# Zwei Aufnahmeorte rund 20 m auseinander, die trotzdem in VERSCHIEDENE Zellen fallen: ein Event
# darf die Zellgrenze streifen (die Ausdehnungsschwelle liegt bei 1000 m, eine Zelle bei rund
# 1,1 km).
DIESSEITS_DER_ZELLGRENZE = (52.5249, 13.4)
JENSEITS_DER_ZELLGRENZE = (52.5251, 13.4)


class CountingResolver:
    """Ein Auflöser, der zaehlt, was er gefragt wurde - und nichts sonst tut.

    `answers` bildet Zelle auf Antwort ab; eine nicht enthaltene Zelle beantwortet er mit `None`
    ("keine Antwort")."""

    def __init__(self, answers: dict[tuple[float, float], PlaceAnswer | None]) -> None:
        self.answers = answers
        self.asked: list[tuple[float, float]] = []

    async def resolve(self, cell: tuple[float, float]) -> PlaceAnswer | None:
        self.asked.append(cell)
        return self.answers.get(cell)


def _answer(
    locality: str | None,
    neighbourhood: str | None = None,
    matched_level: str | None = "locality",
) -> PlaceAnswer:
    return PlaceAnswer(
        neighbourhood=neighbourhood,
        locality=locality,
        region="Berlin",
        country="Deutschland",
        matched_level="neighbourhood" if neighbourhood is not None else matched_level,
    )


def _factory(resolver: PlaceResolver | None) -> object:
    """Die Fabrik, wie der Worker sie bekommt: sie merkt sich, ob und womit sie gerufen wurde.

    Der Auflöser wird ERST GEBAUT, wenn es tatsaechlich etwas zu fragen gibt - ein Durchgang durch
    den Ortsdatensatz ohne offene Zelle waere reine Arbeit."""

    class _Factory:
        def __init__(self) -> None:
            self.calls: list[frozenset[tuple[float, float]]] = []
            self.resolver = resolver

        def __call__(self, cells: object) -> PlaceResolver | None:
            self.calls.append(frozenset(cells))  # type: ignore[arg-type]
            return self.resolver

    return _Factory()


async def _project(session: AsyncSession, name: str) -> Project:
    project = Project(name=name, opencloud_drive_id="drive", opencloud_path=f"/{name}")
    session.add(project)
    await session.flush()
    return project


async def _lookup_rows(session: AsyncSession, project_id: int) -> list[PlaceLookup]:
    return list(
        (
            await session.execute(
                select(PlaceLookup)
                .where(PlaceLookup.project_id == project_id)
                .order_by(PlaceLookup.cell_lat, PlaceLookup.cell_lon)
            )
        )
        .scalars()
        .all()
    )


class TestPlaceInfosAsksOnlyWhatIsMissing:
    async def test_an_empty_cell_set_asks_nobody_and_builds_no_resolver(
        self, db_session: AsyncSession
    ) -> None:
        project = await _project(db_session, "leer")
        factory = _factory(CountingResolver({}))

        infos = await _place_infos(db_session, project.id, set(), factory)  # type: ignore[arg-type]

        assert infos == {}
        assert factory.calls == []  # type: ignore[attr-defined]
        assert await _lookup_rows(db_session, project.id) == []

    async def test_only_the_missing_cells_are_asked(self, db_session: AsyncSession) -> None:
        project = await _project(db_session, "teilweise")
        db_session.add(
            PlaceLookup(
                project_id=project.id,
                cell_lat=KREUZBERG[0],
                cell_lon=KREUZBERG[1],
                neighbourhood="Kreuzberg",
                locality="Berlin",
                matched_level="neighbourhood",
                source="geonames",
                resolved_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await db_session.flush()
        resolver = CountingResolver({SPLIT: _answer("Split")})
        factory = _factory(resolver)

        infos = await _place_infos(db_session, project.id, {KREUZBERG, SPLIT}, factory)  # type: ignore[arg-type]

        assert resolver.asked == [SPLIT]
        assert factory.calls == [frozenset({SPLIT})]  # type: ignore[attr-defined]
        assert infos[KREUZBERG].locality == "Berlin"
        assert infos[SPLIT].locality == "Split"

    async def test_a_row_of_another_project_is_never_read(self, db_session: AsyncSession) -> None:
        """Der Lesepfad faellt NIE auf die Zeile eines anderen Projekts zurueck - ein solcher
        Rueckfall waere der stille Weg, auf dem die Lebensdauer-Bindung aufhoert zu gelten (S6)."""
        other = await _project(db_session, "fremd")
        mine = await _project(db_session, "eigen")
        db_session.add(
            PlaceLookup(
                project_id=other.id,
                cell_lat=SPLIT[0],
                cell_lon=SPLIT[1],
                locality="Split",
                matched_level="locality",
                source="geonames",
                resolved_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await db_session.flush()
        resolver = CountingResolver({SPLIT: _answer("Split")})

        await _place_infos(db_session, mine.id, {SPLIT}, _factory(resolver))  # type: ignore[arg-type]

        assert resolver.asked == [SPLIT]
        assert len(await _lookup_rows(db_session, mine.id)) == 1
        assert len(await _lookup_rows(db_session, other.id)) == 1

    async def test_it_does_not_commit(self, db_session: AsyncSession) -> None:
        """Die Transaktionsgrenze gehoert dem Aufrufer (Muster `project_deletion`)."""
        project = await _project(db_session, "ohne-commit")
        committed: list[int] = []
        original = db_session.commit

        async def _spy() -> None:
            committed.append(1)
            await original()

        db_session.commit = _spy  # type: ignore[method-assign]
        try:
            await _place_infos(
                db_session,
                project.id,
                {SPLIT},
                _factory(CountingResolver({SPLIT: _answer("Split")})),  # type: ignore[arg-type]
            )
        finally:
            db_session.commit = original  # type: ignore[method-assign]

        assert committed == []

    async def test_a_second_pass_after_a_real_round_trip_asks_nothing(
        self, db_session: AsyncSession
    ) -> None:
        """DER TREFFERNACHWEIS. Der Schluessel ist ein GLEITKOMMA-Paar - genau die Stelle, an der
        ein nie treffender Speicher still entsteht. Ein Test, der aus derselben In-Memory-Abbildung
        wiederliest, in die er geschrieben hat, beweist das nicht."""
        project = await _project(db_session, "rundgang")
        first = CountingResolver({SPLIT: _answer("Split"), MITTE: _answer("Berlin", "Mitte")})
        await _place_infos(db_session, project.id, {SPLIT, MITTE}, _factory(first))  # type: ignore[arg-type]
        await db_session.flush()
        db_session.expunge_all()

        second = CountingResolver({SPLIT: _answer("Split"), MITTE: _answer("Berlin", "Mitte")})
        infos = await _place_infos(db_session, project.id, {SPLIT, MITTE}, _factory(second))  # type: ignore[arg-type]

        assert first.asked
        assert second.asked == []
        assert infos[SPLIT].locality == "Split"
        assert infos[MITTE].neighbourhood == "Mitte"

    async def test_a_level_outside_the_vocabulary_is_stored_as_null(
        self, db_session: AsyncSession
    ) -> None:
        """SCHREIBRAND (S7): `matched_level` wird gegen `PLACE_LEVELS` geprueft - ein Wert
        ausserhalb heisst `NULL`, nie "duerftiger, aber brauchbarer Name"."""
        project = await _project(db_session, "fremde-ebene")
        resolver = CountingResolver({SPLIT: _answer("Split", matched_level="stadtbezirk")})

        infos = await _place_infos(db_session, project.id, {SPLIT}, _factory(resolver))  # type: ignore[arg-type]

        [row] = await _lookup_rows(db_session, project.id)
        assert row.matched_level is None
        assert infos[SPLIT].matched_level is None

    async def test_an_unusable_name_level_is_dropped_on_its_own(
        self, db_session: AsyncSession
    ) -> None:
        """Je Stufe EINZELN geprueft: eine unbrauchbare Stufe wird `NULL`, nie die ganze Antwort
        verworfen - und verworfen wird ganz, nie abgeschnitten."""
        project = await _project(db_session, "lange-stufe")
        resolver = CountingResolver(
            {
                SPLIT: PlaceAnswer(
                    neighbourhood="V" * 200,
                    locality="Split",
                    region=None,
                    country=None,
                    matched_level="locality",
                )
            }
        )

        await _place_infos(db_session, project.id, {SPLIT}, _factory(resolver))  # type: ignore[arg-type]

        [row] = await _lookup_rows(db_session, project.id)
        assert row.neighbourhood is None
        assert row.locality == "Split"


# --- Die Verdrahtung ueber einen ganzen Lauf ----------------------------------------------------


async def _run_with_photos(
    session: AsyncSession, name: str, cells: list[tuple[float, float] | None]
) -> tuple[Project, CriterionScoringRun, dict[int, dict[str, float]]]:
    """Ein Lauf mit einem Foto JE ZELLE, weit genug auseinander fuer je ein eigenes Event.

    `None` steht fuer ein Foto ohne Koordinate."""
    project = await _project(session, name)
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()

    values: dict[int, dict[str, float]] = {}
    for index, cell in enumerate(cells):
        photo = Photo(
            project_id=project.id,
            relative_path=f"{name}-{index}.jpg",
            etag=f"etag-{name}-{index}",
            content_length=100,
            # Ein Tag Abstand je Foto: jedes bekommt sein eigenes Event, unabhaengig von der
            # Ortslage - so misst dieser Aufbau die NAMENSVERGABE und nicht die Event-Bildung.
            taken_at=_BASE + timedelta(days=index),
            taken_at_original=_BASE + timedelta(days=index),
            last_modified=_BASE,
            gps_lat=None if cell is None else cell[0],
            gps_lon=None if cell is None else cell[1],
        )
        session.add(photo)
        await session.flush()
        values[photo.id] = {}
    return project, run, values


async def _events_of(session: AsyncSession, run: CriterionScoringRun) -> list[Event]:
    return list(
        (
            await session.execute(
                select(Event)
                .where(Event.criterion_scoring_run_id == run.id)
                .order_by(Event.position)
            )
        )
        .scalars()
        .all()
    )


class TestTheRunWritesTheNames:
    async def test_the_event_carries_the_resolved_name(self, db_session: AsyncSession) -> None:
        project, run, values = await _run_with_photos(db_session, "benannt", [SPLIT])
        resolver = CountingResolver({SPLIT: _answer("Split")})

        await _build_grouping_and_rankings(db_session, run, project.id, values, _factory(resolver))  # type: ignore[arg-type]

        [event] = await _events_of(db_session, run)
        assert event.place_name == "Split"

    async def test_a_cell_in_two_events_is_asked_exactly_once(
        self, db_session: AsyncSession
    ) -> None:
        project, run, values = await _run_with_photos(db_session, "zweimal", [SPLIT, SPLIT])
        resolver = CountingResolver({SPLIT: _answer("Split")})

        await _build_grouping_and_rankings(db_session, run, project.id, values, _factory(resolver))  # type: ignore[arg-type]

        assert resolver.asked == [SPLIT]
        assert [event.place_name for event in await _events_of(db_session, run)] == [
            "Split",
            "Split",
        ]

    async def test_only_events_without_a_landmark_are_asked_for(
        self, db_session: AsyncSession
    ) -> None:
        """Gefragt wird nur fuer Events OHNE Sehenswuerdigkeit - das spart Anfragen und setzt das
        Akzeptanzkriterium strukturell um. Die Zelle des Landmark-Events kommt nirgends sonst vor;
        ohne diese Bedingung waere der Fall leer."""
        project, run, values = await _run_with_photos(db_session, "landmark", [MITTE, SPLIT])
        landmark_photo = min(values)
        await _add_landmark(db_session, landmark_photo, "Brandenburger Tor")
        resolver = CountingResolver({MITTE: _answer("Berlin", "Mitte"), SPLIT: _answer("Split")})

        await _build_grouping_and_rankings(db_session, run, project.id, values, _factory(resolver))  # type: ignore[arg-type]

        assert resolver.asked == [SPLIT]
        names = [
            (event.landmark_name, event.place_name) for event in await _events_of(db_session, run)
        ]
        assert names == [("Brandenburger Tor", None), (None, "Split")]

    async def test_a_resolver_that_yields_nothing_leaves_the_run_successful(
        self, db_session: AsyncSession
    ) -> None:
        """AUSGANG 1 - keine Antwort: KEINE Zeile, kein Name, und der zweite Lauf fragt ERNEUT.
        Sonst vergiftete eine voruebergehende Stoerung die Zelle dauerhaft."""
        project, run, values = await _run_with_photos(db_session, "stoerung", [SPLIT])
        first = CountingResolver({})

        await _build_grouping_and_rankings(db_session, run, project.id, values, _factory(first))  # type: ignore[arg-type]

        [event] = await _events_of(db_session, run)
        assert event.place_name is None
        assert await _lookup_rows(db_session, project.id) == []

        await db_session.flush()
        db_session.expunge_all()
        second = CountingResolver({SPLIT: _answer("Split")})
        infos = await _place_infos(db_session, project.id, {SPLIT}, _factory(second))  # type: ignore[arg-type]

        assert second.asked == [SPLIT]
        assert infos[SPLIT].locality == "Split"

    async def test_an_answer_without_a_usable_level_is_stored_and_not_asked_again(
        self, db_session: AsyncSession
    ) -> None:
        """AUSGANG 2 - eine Auskunft, keine Stoerung: GENAU EINE Zeile mit leeren Namensstufen,
        kein Name, und der zweite Lauf fragt NICHT erneut."""
        project, run, values = await _run_with_photos(db_session, "ohne-ebene", [SPLIT])
        first = CountingResolver(
            {
                SPLIT: PlaceAnswer(
                    neighbourhood=None,
                    locality=None,
                    region="Dalmatien",
                    country="Kroatien",
                    matched_level="region",
                )
            }
        )

        await _build_grouping_and_rankings(db_session, run, project.id, values, _factory(first))  # type: ignore[arg-type]

        [event] = await _events_of(db_session, run)
        assert event.place_name is None
        [row] = await _lookup_rows(db_session, project.id)
        assert (row.locality, row.neighbourhood, row.matched_level) == (None, None, "region")

        await db_session.flush()
        db_session.expunge_all()
        second = CountingResolver({SPLIT: _answer("Split")})
        await _place_infos(db_session, project.id, {SPLIT}, _factory(second))  # type: ignore[arg-type]

        assert second.asked == []

    async def test_two_names_in_one_event_leave_it_nameless_but_store_both_cells(
        self, db_session: AsyncSession
    ) -> None:
        """AUSGANG 3 - fuer eine Menge von Orten gibt es keinen einen Namen. Die Auskuenfte
        bleiben trotzdem abgelegt: sie sind richtig, nur nicht als Ueberschrift brauchbar.

        Die beiden Aufnahmen liegen rund 20 m auseinander und trotzdem in VERSCHIEDENEN Zellen -
        der Fall, fuer den die Aufloesung ueber alle Zellen eines Events laeuft."""
        project, run, values = await _run_with_photos(
            db_session, "zwei-namen", [DIESSEITS_DER_ZELLGRENZE, JENSEITS_DER_ZELLGRENZE]
        )
        photos = (
            (await db_session.execute(select(Photo).where(Photo.project_id == project.id)))
            .scalars()
            .all()
        )
        for photo in photos:
            photo.taken_at = _BASE
        await db_session.flush()
        resolver = CountingResolver(
            {(52.52, 13.4): _answer("Berlin"), (52.53, 13.4): _answer("Hamburg")}
        )

        await _build_grouping_and_rankings(db_session, run, project.id, values, _factory(resolver))  # type: ignore[arg-type]

        events = await _events_of(db_session, run)
        assert [event.place_kind for event in events] == ["multiple"]
        assert [event.place_name for event in events] == [None]
        assert len(await _lookup_rows(db_session, project.id)) == 2

    async def test_without_a_factory_nothing_is_asked_and_stored_rows_still_count(
        self, db_session: AsyncSession
    ) -> None:
        """Der Request-Pfad bekommt `None` (S10): er liest den Bestand und fragt niemanden."""
        project, run, values = await _run_with_photos(db_session, "nur-lesen", [SPLIT])
        db_session.add(
            PlaceLookup(
                project_id=project.id,
                cell_lat=SPLIT[0],
                cell_lon=SPLIT[1],
                locality="Split",
                matched_level="locality",
                source="geonames",
                resolved_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await db_session.flush()

        await _build_grouping_and_rankings(db_session, run, project.id, values, None)

        [event] = await _events_of(db_session, run)
        assert event.place_name == "Split"
        assert len(await _lookup_rows(db_session, project.id)) == 1

    async def test_a_cell_without_a_stored_lookup_stays_nameless_in_the_reading_path(
        self, db_session: AsyncSession
    ) -> None:
        """Die harmlose Kehrseite von S10: eine noch nie gefragte Zelle bleibt dort ohne Namen,
        bis der naechste Kriterien-Lauf sie beschafft. Die erste Haelfte oben allein bestuende
        auch dann, wenn dieser Pfad das Merkmal gar nicht mehr kennte."""
        project, run, values = await _run_with_photos(db_session, "unbekannt", [SPLIT])

        await _build_grouping_and_rankings(db_session, run, project.id, values, None)

        [event] = await _events_of(db_session, run)
        assert event.place_name is None
        assert await _lookup_rows(db_session, project.id) == []


async def _add_landmark(
    session: AsyncSession, photo_id: int, name: str, *, confidence: float = 0.9
) -> None:
    from photosort.models import PhotoLandmarkDetection

    session.add(
        PhotoLandmarkDetection(
            photo_id=photo_id,
            name=name,
            confidence=confidence,
            computed_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    await session.flush()


def _event_shape(event: Event) -> dict[str, object]:
    """Alles, was an einer Event-Zeile ueberhaupt steht - ohne `id` und Laufbezug.

    Bewusst ueber die Metadaten und nicht ueber eine ausgeschriebene Feldliste: Genau der Fall, der
    hier zaehlt, ist ein KUENFTIGES Feld, das die beiden Datenlagen doch unterscheidet. Eine
    Handliste erfasste es nicht."""
    return {
        column.name: getattr(event, column.name)
        for column in Event.__table__.columns
        if column.name not in ("id", "criterion_scoring_run_id")
    }


class TestADiscardedHitIsIndistinguishableFromNoHitAtAll:
    """specs/features/0469, ADR 0107 Punkt 2: Ein wegen Unsicherheit verworfener Treffer ist von
    "nie erkannt" nicht zu unterscheiden.

    Es entsteht kein zusaetzlicher Anzeigezustand und kein Hinweis auf die verworfene Vermutung.
    Geprueft als GLEICHHEIT ZWEIER BEOBACHTUNGEN in EINEM Fall - zwei getrennte Faelle, die je
    einen erwarteten Wert festnageln, bestuenden auch dann, wenn die beiden Lagen auseinanderlaufen
    und beide Erwartungen mitgezogen wuerden."""

    async def test_both_data_situations_produce_exactly_the_same_events(
        self, db_session: AsyncSession
    ) -> None:
        mit_verworfener_zeile, run_a, values_a = await _run_with_photos(
            db_session, "verworfen", [KREUZBERG]
        )
        await _add_landmark(
            db_session, next(iter(values_a)), "Vermutetes Wahrzeichen", confidence=0.49
        )
        ohne_zeile, run_b, values_b = await _run_with_photos(db_session, "gar-nichts", [KREUZBERG])

        resolver_a = CountingResolver({KREUZBERG: _answer("Berlin")})
        resolver_b = CountingResolver({KREUZBERG: _answer("Berlin")})
        await _build_grouping_and_rankings(
            db_session,
            run_a,
            mit_verworfener_zeile.id,
            values_a,
            _factory(resolver_a),  # type: ignore[arg-type]
        )
        await _build_grouping_and_rankings(
            db_session,
            run_b,
            ohne_zeile.id,
            values_b,
            _factory(resolver_b),  # type: ignore[arg-type]
        )

        events_a = [_event_shape(event) for event in await _events_of(db_session, run_a)]
        events_b = [_event_shape(event) for event in await _events_of(db_session, run_b)]

        assert events_a == events_b
        # Gegenprobe zur Selbsterfuellung: ein Lauf ganz ohne Events bestuende die Gleichheit oben.
        assert len(events_a) == 1

    async def test_an_event_whose_hits_were_all_discarded_falls_back_to_the_place_name(
        self, db_session: AsyncSession
    ) -> None:
        """Der fachliche Folgefall: Das Foto verliert nicht seinen Ortsbezug, es verliert nur die
        unsichere Vermutung."""
        project, run, values = await _run_with_photos(db_session, "rueckfall", [KREUZBERG])
        await _add_landmark(
            db_session, next(iter(values)), "Vermutetes Wahrzeichen", confidence=0.1
        )
        resolver = CountingResolver({KREUZBERG: _answer("Berlin")})

        await _build_grouping_and_rankings(
            db_session,
            run,
            project.id,
            values,
            _factory(resolver),  # type: ignore[arg-type]
        )

        [event] = await _events_of(db_session, run)
        assert event.landmark_name is None
        assert event.place_name == "Berlin"

    async def test_a_hit_exactly_on_the_threshold_still_names_its_event(
        self, db_session: AsyncSession
    ) -> None:
        """Die Gegenprobe zu beiden Faellen darueber: Die Grenze verwirft, sie verstummt nicht."""
        project, run, values = await _run_with_photos(db_session, "genau-drauf", [KREUZBERG])
        await _add_landmark(
            db_session,
            next(iter(values)),
            "Brandenburger Tor",
            confidence=LANDMARK_CONFIDENCE_THRESHOLD,
        )

        await _build_grouping_and_rankings(db_session, run, project.id, values, None)

        [event] = await _events_of(db_session, run)
        assert event.landmark_name == "Brandenburger Tor"


class TestNothingLeaksIntoALogOrIntoTheRunRow:
    async def test_no_log_record_carries_a_coordinate_or_a_resolved_name(
        self, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Geprueft ueber `record.getMessage()` UND `record.args` - sonst rutscht ein
        `%s`-Argument durch (S11)."""
        project, run, values = await _run_with_photos(db_session, "leise", [SPLIT])
        resolver = CountingResolver({SPLIT: _answer("Split")})

        with caplog.at_level(logging.DEBUG):
            await _build_grouping_and_rankings(
                db_session,
                run,
                project.id,
                values,
                _factory(resolver),  # type: ignore[arg-type]
            )

        for record in caplog.records:
            if record.name.split(".")[0] != "photosort":
                continue
            rendered = record.getMessage() + repr(record.args)
            assert "43.5" not in rendered
            assert "16.4" not in rendered
            assert "Split" not in rendered

    def test_the_run_row_gets_no_new_counting_column(self) -> None:
        """Die Zaehler an der Lauf-Zeile tragen IST-KOSTEN, und diese Aufloesung ist keine."""
        columns = {column.name for column in inspect(CriterionScoringRun).columns}

        assert not [name for name in columns if "place" in name]


class TestTheRequestPathAsksNobody:
    """S10: `rebuild_run_grouping` laeuft in einem Request. Ohne diese Grenze loeste eine
    authentifizierte Anfrage - auch eine mit gestohlenem JWT - Arbeit an einem Dritten aus."""

    def _call_arguments(self, function_name: str) -> list[ast.expr]:
        path = module_file("photosort.worker")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
            and node.name == function_name
        )
        call = next(
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_build_grouping_and_rankings"
        )
        return [*call.args, *(keyword.value for keyword in call.keywords)]

    def test_the_rebuild_passes_a_literal_none_as_resolver(self) -> None:
        arguments = self._call_arguments("rebuild_run_grouping")

        assert any(
            isinstance(argument, ast.Constant) and argument.value is None for argument in arguments
        )

    def test_the_criterion_run_does_not_pass_none(self) -> None:
        """Gegenprobe: der Waechter darf die BESCHAFFENDE Aufrufstelle nicht mitfangen - sonst
        waere er gruen, auch wenn beide Pfade dasselbe taeten."""
        arguments = self._call_arguments("run_criterion_scoring")

        assert not any(
            isinstance(argument, ast.Constant) and argument.value is None for argument in arguments
        )


class TestTheRunUsesTheConfiguredFactory:
    """`run_criterion_scoring` reicht den konfigurierten Auflöser durch. Fehlt der Ortsdatensatz
    oder weicht er von seinem Hash ab, wird KEINER gebaut - und der Lauf geht trotzdem durch."""

    def test_the_default_factory_is_the_local_dataset(self) -> None:
        from photosort.geonames import build_place_resolver
        from photosort.worker import run_criterion_scoring

        defaults = inspect_signature_default(run_criterion_scoring, "build_place_resolver")

        assert defaults is build_place_resolver

    async def test_a_missing_dataset_leaves_the_events_unnamed_without_a_replacement_path(
        self, db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        from photosort.geonames import DATASET_REASON_MISSING, build_place_resolver

        project, run, values = await _run_with_photos(db_session, "kein-datensatz", [SPLIT])

        with caplog.at_level(logging.ERROR, logger="photosort.geonames"):
            await _build_grouping_and_rankings(
                db_session,
                run,
                project.id,
                values,
                lambda cells: build_place_resolver(cells, path=tmp_path / "fehlt.txt.gz"),
            )

        [event] = await _events_of(db_session, run)
        assert event.place_name is None
        assert await _lookup_rows(db_session, project.id) == []
        assert any(DATASET_REASON_MISSING in record.getMessage() for record in caplog.records)

    async def test_the_run_itself_stays_successful(self, db_session: AsyncSession) -> None:
        """Kein aufgeloester Name gefaehrdet je einen Lauf (ADR 0102 Punkt 5)."""
        project, run, values = await _run_with_photos(db_session, "erfolgreich", [SPLIT])

        await _build_grouping_and_rankings(
            db_session,
            run,
            project.id,
            values,
            _factory(None),  # type: ignore[arg-type]
        )

        assert run.status == ScanStatus.SUCCESS
        assert (
            await db_session.execute(
                select(func.count())
                .select_from(Event)
                .where(Event.criterion_scoring_run_id == run.id)
            )
        ).scalar_one() == 1


def inspect_signature_default(function: object, parameter: str) -> object:
    import inspect as python_inspect

    return python_inspect.signature(function).parameters[parameter].default  # type: ignore[arg-type]
