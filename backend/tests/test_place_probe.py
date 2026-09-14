"""Tests fuer das rein lesende Messkommando (specs/features/0434-ortsnamen-fuer-events.md,
decisions/0102-ortsauskunft-je-zelle-projektgebunden-eventname-als-laufartefakt.md).

Aufbau nach architecture/0002-testkonzept.md, Sektion "Ein rein lesendes Kommando im
Produktivpaket": die Zaehlbloecke rein und ohne DB, die duenne Leseschicht gegen die
`db_session`-Fixture, `main()` synchron gegen eine dateibasierte SQLite in `tmp_path`.
"""

from __future__ import annotations

import ast
import asyncio
import socket
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.cloud_vision import CloudRequestThrottle
from photosort.db import Base, make_engine, make_session_factory
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
)
from photosort.place_probe import (
    FAILURE_HTTP_STATUS,
    FAILURE_REASONS,
    FAILURE_TOO_LARGE,
    FAILURE_TRANSPORT,
    FAILURE_UNREADABLE,
    PHOTON_MAX_RESPONSE_BYTES,
    PHOTON_MIN_REQUEST_INTERVAL_SECONDS,
    PHOTON_REVERSE_URL,
    Cell,
    PhotonResolver,
    ProbeEvent,
    ProbeInput,
    ProbeTally,
    cell_counts,
    coverage_counts,
    heading_counts,
    level_counts,
    main,
    new_tally,
    photo_counts,
    photon_answer,
)
from photosort.places import PlaceAnswer, PlaceInfo, PlaceResolver, usable_locality
from tests.conftest import NetworkAccessInTestError
from tests.import_closure import import_closure, module_file

REPO_ROOT = Path(__file__).resolve().parents[2]

# Die Schreibformen, gegen die der Waechter antritt. Attributaufrufe (`session.add(...)`) und
# blanke Namen (`insert(...)` aus einem `from sqlalchemy import insert`) getrennt, weil `delete`
# in beiden Formen vorkommt und nur die Kombination beide Wege deckt.
_WRITING_METHODS = frozenset({"add", "add_all", "merge", "delete", "commit", "flush"})
_WRITING_CONSTRUCTORS = frozenset({"insert", "update", "delete"})
_WRITING_NAMES = _WRITING_METHODS | _WRITING_CONSTRUCTORS
_DML_KEYWORDS = ("insert ", "update ", "delete ", "drop ", "alter ", "create ", "truncate ")


def _tally() -> ProbeTally:
    """Ein frischer Nebenbefund-Sammler je Fall - geteilte Zaehler taeuschten Ausfaelle vor."""
    return new_tally()


def write_statements(tree: ast.AST) -> list[str]:
    """Jede SCHREIBFORM in einem Syntaxbaum, als lesbare Liste.

    Bewusst ueber die FORM statt ueber ein Verhalten: ein Laufvergleich allein bestuende gegen
    einen Schreibpfad, den die Testlage nicht betritt (ein Zweig hinter einem nicht gesetzten
    Schalter, ein Fehlerpfad). Umgekehrt bestuende dieser Waechter allein gegen ein Modul, das
    ueber eine Hilfsfunktion schreibt - deshalb tragen beide zusammen, keiner allein."""
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in _WRITING_NAMES:
            # Auch die Attributform der Konstruktoren (`sa.insert(...)`): ein Import unter Alias
            # waere sonst der stille Weg an diesem Waechter vorbei. Der Preis ist, dass
            # `place_probe.py` auf die gleichnamigen Sammlungs-Methoden (`set.add`, `dict.update`)
            # verzichten muss - eine kleine Auflage gegen eine luecklose Zusage.
            found.append(f"{node.func.attr}()")
        elif isinstance(node.func, ast.Name) and node.func.id in _WRITING_CONSTRUCTORS:
            found.append(f"{node.func.id}()")
        elif isinstance(node.func, ast.Name) and node.func.id == "text":
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    lowered = argument.value.lstrip().lower()
                    if lowered.startswith(_DML_KEYWORDS):
                        found.append("text(<DML>)")
    return found


class TestTheNetworkIsLockedForEveryTest:
    """Die Zusage "kein automatisierter Test erreicht je ein Netz" ist ab dieser Auslieferung eine
    SPERRE, keine Konvention mehr (autouse-Fixture in conftest.py). Ein Test, der einen echten
    Auflöser baut, wird dadurch laut rot, statt still online zu gehen."""

    def test_connecting_a_socket_raises(self) -> None:
        with pytest.raises(NetworkAccessInTestError):
            socket.socket().connect(("example.invalid", 80))

    def test_connect_ex_raises_too(self) -> None:
        # `connect_ex` meldet einen Fehler sonst als Rueckgabewert statt als Ausnahme - ohne
        # eigene Sperre ginge ein Verbindungsversuch darueber still hinaus.
        with pytest.raises(NetworkAccessInTestError):
            socket.socket().connect_ex(("example.invalid", 80))

    def test_create_connection_raises_too(self) -> None:
        # Der bequeme Weg der Standardbibliothek; er legt seinen Socket selbst an, und ein Patch
        # allein auf die Methode oben liefe bei einer kuenftigen Implementierung ins Leere.
        with pytest.raises(NetworkAccessInTestError):
            socket.create_connection(("example.invalid", 80))


class TestTheWriteGuardItself:
    """Mikrotests je Schreibform plus Positiv-Gegenproben. Ohne sie sagte ein leeres Ergebnis am
    echten Modul nichts - ein Waechter, der nichts erkennt, ist immer gruen."""

    @pytest.mark.parametrize(
        ("snippet", "expected"),
        [
            ("session.add(row)", "add()"),
            ("session.add_all(rows)", "add_all()"),
            ("session.merge(row)", "merge()"),
            ("await session.delete(row)", "delete()"),
            ("await session.commit()", "commit()"),
            ("await session.flush()", "flush()"),
            ("sa.insert(Photo).values(x=1)", "insert()"),
            ("stmt = insert(Photo)", "insert()"),
            ("stmt = update(Photo).values(x=1)", "update()"),
            ("stmt = delete(Photo)", "delete()"),
            ('await session.execute(text("INSERT INTO photos VALUES (1)"))', "text(<DML>)"),
            ('await session.execute(text("  update photos set x = 1"))', "text(<DML>)"),
            ('await session.execute(text("DELETE FROM photos"))', "text(<DML>)"),
        ],
    )
    def test_each_writing_form_is_recognised(self, snippet: str, expected: str) -> None:
        assert expected in write_statements(ast.parse(snippet))

    @pytest.mark.parametrize(
        "snippet",
        [
            "rows = (await session.execute(select(Photo))).all()",
            "parser.add_argument('--project-id')",
            'await session.execute(text("SELECT 1"))',
            "counts = Counter()",
        ],
    )
    def test_a_reading_form_is_not_flagged(self, snippet: str) -> None:
        """Positiv-Gegenprobe. `parser.add_argument` steht hier, weil ein zu grob geschnittener
        Waechter genau daran haengenbliebe und dann entschaerft wuerde - und mit ihm die Zusage."""
        assert write_statements(ast.parse(snippet)) == []


class TestTheProbeIsReadOnly:
    """Die Zusage "kein Lauf hinterlaesst eine geaenderte, geloeschte oder neue Zeile", in drei
    Teilen - KEIN Teil traegt allein (siehe `write_statements` oben)."""

    def test_the_command_is_in_no_import_graph_of_the_application(self) -> None:
        assert "photosort.place_probe" not in import_closure("photosort.main")
        assert "photosort.place_probe" not in import_closure("photosort.worker")

    def test_the_import_graph_walker_actually_finds_something(self) -> None:
        # Gegenprobe: ohne sie bestuenden die beiden Zusagen oben auch bei einem Walker, der gar
        # nichts findet - Tippfehler im Modulnamen, geaenderte Verzeichnisstruktur.
        assert {"photosort.models", "photosort.config"} <= import_closure("photosort.main")
        assert "photosort.places" in import_closure("photosort.place_probe")

    def test_no_compose_file_runs_the_command(self) -> None:
        """Der Abfluss tritt nur ein, wenn Daniel ihn TIPPT - nicht, weil ein Container startet."""
        for compose in sorted(REPO_ROOT.glob("docker-compose*.yml")):
            content = compose.read_text(encoding="utf-8")

            assert "place_probe" not in content, compose.name

    def test_the_module_defines_no_endpoint(self) -> None:
        path = module_file("photosort.place_probe")
        assert path is not None
        source = path.read_text(encoding="utf-8")

        assert "APIRouter" not in source
        assert "fastapi" not in source

    def test_the_module_contains_no_writing_statement_at_all(self) -> None:
        path = module_file("photosort.place_probe")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))

        assert write_statements(tree) == []


# --- Die fuenf Messbloecke, je gegen einen von Hand ausgerechneten Projektgraphen -------------
#
# Vier Zellen, bewusst so gewaehlt, dass sie sich in der zweiten Nachkommastelle unterscheiden.
SPLIT = (43.51, 16.44)
BERLIN_KREUZBERG = (52.50, 13.40)
BERLIN_MITTE = (52.52, 13.40)
GARMISCH = (47.49, 11.09)


def _probe_event(
    position: int,
    *,
    cells: tuple[Cell, ...] = (),
    landmark_name: str | None = None,
    place_kind: str | None = None,
) -> ProbeEvent:
    return ProbeEvent(
        position=position, landmark_name=landmark_name, place_kind=place_kind, cells=cells
    )


def _probe_input(
    *,
    photos_total: int = 0,
    photo_cells: tuple[Cell, ...] = (),
    events: tuple[ProbeEvent, ...] = (),
    run_found: bool = True,
) -> ProbeInput:
    """`photo_cells` traegt EINEN Eintrag JE FOTO mit gemessener Koordinate - Dubletten sind der
    Normalfall und tragen Block E."""
    return ProbeInput(
        project_id=7,
        photos_total=photos_total,
        photo_cells=photo_cells,
        events=events,
        run_found=run_found,
    )


def _answer(
    *,
    matched_level: str | None,
    locality: str | None = None,
    neighbourhood: str | None = None,
    region: str | None = None,
    country: str | None = None,
) -> PlaceAnswer:
    return PlaceAnswer(
        neighbourhood=neighbourhood,
        locality=locality,
        region=region,
        country=country,
        matched_level=matched_level,
    )


def _info_of(answer: PlaceAnswer) -> PlaceInfo:
    return PlaceInfo(
        neighbourhood=answer.neighbourhood,
        locality=answer.locality,
        matched_level=answer.matched_level,
    )


class TestBlockACoverage:
    """Die Obergrenze dessen, was ueberhaupt benannt werden kann."""

    def test_the_hand_computed_graph(self) -> None:
        counts = coverage_counts(
            _probe_input(
                photos_total=10,
                photo_cells=(SPLIT, SPLIT, BERLIN_MITTE, GARMISCH),
                events=(
                    _probe_event(1, place_kind="landmark", landmark_name="Diokletianpalast"),
                    _probe_event(2, place_kind="coordinate", cells=(SPLIT,)),
                    _probe_event(3, place_kind="multiple", cells=(BERLIN_MITTE, BERLIN_KREUZBERG)),
                    _probe_event(4, place_kind=None),
                ),
            )
        )

        assert counts.photos_total == 10
        assert counts.photos_with_coordinate == 4
        assert counts.events_total == 4
        assert counts.events_with_landmark == 1
        assert counts.events_coordinate == 1
        assert counts.events_multiple == 1
        assert counts.events_without_place == 1

    def test_the_degenerate_case_no_photo_with_a_coordinate_and_no_run(self) -> None:
        """Ein Projekt ohne jede Koordinate und ohne erfolgreichen Lauf ist ein gueltiges
        Messergebnis, kein Fehler - die Obergrenze ist dann eben null."""
        counts = coverage_counts(_probe_input(photos_total=12, run_found=False))

        assert counts.photos_total == 12
        assert counts.photos_with_coordinate == 0
        assert counts.events_total == 0
        assert counts.events_with_landmark == 0
        assert counts.events_without_place == 0


class TestBlockBCells:
    """Die Zahl der Anfragen, die ein Lauf je Weg tatsaechlich stellte."""

    def test_distinct_cells_count_once_however_many_photos_sit_in_them(self) -> None:
        counts = cell_counts(
            _probe_input(
                photos_total=5,
                photo_cells=(SPLIT, SPLIT, SPLIT, BERLIN_MITTE),
                events=(_probe_event(1, cells=(SPLIT,)),),
            )
        )

        assert counts.distinct_cells == 2

    def test_an_event_across_two_cells(self) -> None:
        """Der entartete Fall dieses Blocks: ein Event darf die Zellgrenze streifen (die
        Ausdehnungsschwelle liegt bei 1000 m, eine Zelle bei rund 1,1 km)."""
        counts = cell_counts(
            _probe_input(
                photos_total=3,
                photo_cells=(BERLIN_MITTE, BERLIN_KREUZBERG, GARMISCH),
                events=(
                    _probe_event(1, cells=(BERLIN_MITTE, BERLIN_KREUZBERG)),
                    _probe_event(2, cells=(GARMISCH,)),
                    _probe_event(3, cells=()),
                ),
            )
        )

        assert counts.distinct_cells == 3
        assert counts.cells_per_event == {0: 1, 1: 1, 2: 1}
        assert counts.max_cells_in_one_event == 2


class TestBlockCComparison:
    """Je Zelle die getroffene Ebene - AGGREGIERT ausgewiesen, nie eine Zeile je Zelle mit der
    Zelle als Kennung (S5). Die Aufschluesselung nach Ebene ist tragend: ob eine Quelle die
    Viertel-Ebene ueberhaupt fuehrt, entscheidet, ob die Viertel-Regel je greift."""

    def test_one_hit_on_each_of_the_four_levels_and_one_without(self) -> None:
        counts = level_counts(
            {
                BERLIN_KREUZBERG: _answer(
                    matched_level="neighbourhood", locality="Berlin", neighbourhood="Kreuzberg"
                ),
                SPLIT: _answer(matched_level="locality", locality="Split"),
                GARMISCH: _answer(matched_level="region", region="Bayern", locality="Muenchen"),
                BERLIN_MITTE: _answer(matched_level="country", country="Deutschland"),
                (1.0, 1.0): None,
            }
        )

        assert counts.cells_total == 5
        assert counts.cells_without_answer == 1
        assert counts.cells_with_locality == 2
        assert counts.cells_with_neighbourhood == 1
        assert counts.cells_region_or_country_only == 2

    def test_a_failed_request_is_counted_apart_from_a_genuine_miss(self) -> None:
        """DIE UNTERSCHEIDUNG, DIE DIE WEGWAHL TRAEGT. `resolve` liefert `None` sowohl fuer
        "geantwortet, nichts Brauchbares" als auch fuer "gar nicht geantwortet" (HTTP 429,
        Zeitueberschreitung, Transportfehler). Beides als "ohne Treffer" auszuweisen macht aus
        einer Drosselung ein schlechtes Messergebnis - und darauf faellt eine nicht ruecknehmbare
        Entscheidung."""
        counts = level_counts(
            {
                SPLIT: _answer(matched_level="locality", locality="Split"),
                GARMISCH: None,
                BERLIN_MITTE: None,
                BERLIN_KREUZBERG: None,
            },
            {"http-status": 2, "transport": 1},
        )

        assert counts.cells_total == 4
        assert counts.cells_with_a_failed_request == 3
        # "Ohne Treffer" meint ab hier AUSSCHLIESSLICH: der Dienst hat geantwortet und nichts
        # gefunden. Die drei Ausfaelle stehen NICHT zusaetzlich darin - sonst waere dieselbe
        # Zelle doppelt gezaehlt.
        assert counts.cells_without_answer == 0

    def test_without_any_failure_every_none_is_a_genuine_miss(self) -> None:
        counts = level_counts({SPLIT: None, GARMISCH: None})

        assert counts.cells_without_answer == 2
        assert counts.cells_with_a_failed_request == 0

    def test_a_region_hit_naming_a_city_does_not_count_as_a_locality(self) -> None:
        """Die Anbieterangabe gewinnt. Ohne diesen Fall zaehlte eine Umsetzung, die auf die
        gefuellte Spalte statt auf `matched_level` sieht, die Messung systematisch zu guenstig -
        und traege damit eine nicht ruecknehmbare Wegwahl."""
        counts = level_counts(
            {GARMISCH: _answer(matched_level="region", region="Bayern", locality="Muenchen")}
        )

        assert counts.cells_with_locality == 0
        assert counts.cells_region_or_country_only == 1


class TestBlockDHeadings:
    """Verwendung "Ueberschrift" - D ZAEHLT EVENTS."""

    def test_homonymy_one_resolvable_by_district_and_one_not(self) -> None:
        info_by_cell = {
            BERLIN_KREUZBERG: _info_of(
                _answer(matched_level="locality", locality="Berlin", neighbourhood="Kreuzberg")
            ),
            # Zweites Berlin-Event OHNE Viertel: es bleibt beim Ortsnamen und ist nur ueber seine
            # Zeitspanne unterscheidbar.
            BERLIN_MITTE: _info_of(_answer(matched_level="locality", locality="Berlin")),
            SPLIT: _info_of(_answer(matched_level="locality", locality="Split")),
            GARMISCH: _info_of(_answer(matched_level="region", region="Bayern")),
        }
        counts = heading_counts(
            _probe_input(
                photos_total=6,
                events=(
                    _probe_event(1, cells=(BERLIN_KREUZBERG,)),
                    _probe_event(2, cells=(BERLIN_MITTE,)),
                    _probe_event(3, cells=(SPLIT,)),
                    _probe_event(4, cells=(GARMISCH,)),
                    _probe_event(5, place_kind="landmark", landmark_name="Zugspitze"),
                ),
            ),
            info_by_cell,
        )

        assert counts.events_with_landmark == 1
        # Berlin (x2) und Split; das Regions-Event traegt keinen Namen.
        assert counts.events_named == 3
        # NUR Event 4 faellt auf Nummer und Zeitspanne zurueck. Das Landmark-Event zaehlt hier
        # ausdruecklich nicht mit: es heisst bereits nach seiner Sehenswuerdigkeit.
        assert counts.events_keeping_position == 1
        assert counts.events_sharing_a_name == 2
        assert counts.events_distinguishable_by_district == 1

    def test_an_event_over_two_different_names_gets_none(self) -> None:
        info_by_cell = {
            SPLIT: _info_of(_answer(matched_level="locality", locality="Split")),
            GARMISCH: _info_of(_answer(matched_level="locality", locality="Garmisch")),
        }
        counts = heading_counts(
            _probe_input(photos_total=2, events=(_probe_event(1, cells=(SPLIT, GARMISCH)),)),
            info_by_cell,
        )

        assert counts.events_named == 0
        assert counts.events_keeping_position == 1

    def test_a_cell_without_a_name_does_not_stop_the_others(self) -> None:
        """Zellen ohne aufgeloesten Namen zaehlen nicht mit: ein Event aus zwei Zellen, von denen
        nur eine einen Namen liefert, traegt diesen Namen."""
        info_by_cell = {
            SPLIT: _info_of(_answer(matched_level="locality", locality="Split")),
            GARMISCH: _info_of(_answer(matched_level="country", country="Deutschland")),
        }
        counts = heading_counts(
            _probe_input(photos_total=2, events=(_probe_event(1, cells=(SPLIT, GARMISCH)),)),
            info_by_cell,
        )

        assert counts.events_named == 1

    def test_a_landmark_event_never_counts_towards_homonymy(self) -> None:
        """Ein Event mit Sehenswuerdigkeit traegt keinen Ortsnamen und loest deshalb auch bei
        keinem anderen Event die Viertel-Ergaenzung aus. Die Messlage ist so gebaut, dass es einen
        Namen BEKAEME: seine Zelle loest auf."""
        info_by_cell = {
            BERLIN_KREUZBERG: _info_of(
                _answer(matched_level="locality", locality="Berlin", neighbourhood="Kreuzberg")
            )
        }
        counts = heading_counts(
            _probe_input(
                photos_total=2,
                events=(
                    _probe_event(
                        1,
                        cells=(BERLIN_KREUZBERG,),
                        place_kind="landmark",
                        landmark_name="Brandenburger Tor",
                    ),
                    _probe_event(2, cells=(BERLIN_KREUZBERG,)),
                ),
            ),
            info_by_cell,
        )

        assert counts.events_named == 1
        assert counts.events_sharing_a_name == 0
        assert counts.events_distinguishable_by_district == 0


class TestBlockEPhotos:
    """Verwendung #469 - E ZAEHLT FOTOS, nicht Events. #469 fragt VOR der Event-Bildung; eine
    Messung, die nur Events zaehlt, misst den halben Nutzen."""

    def test_photos_are_counted_not_events(self) -> None:
        """Der tragende Fall: drei Fotos in EINER Zelle gegen ein Foto in einer anderen. Eine
        Umsetzung, die E aus D ableitet, zaehlt hier zwei statt vier und ist genau hier rot."""
        info_by_cell = {
            SPLIT: _info_of(_answer(matched_level="locality", locality="Split")),
            GARMISCH: _info_of(_answer(matched_level="locality", locality="Garmisch")),
        }
        counts = photo_counts(
            _probe_input(
                photos_total=8,
                photo_cells=(SPLIT, SPLIT, SPLIT, GARMISCH),
                events=(_probe_event(1, cells=(SPLIT, GARMISCH)),),
            ),
            info_by_cell,
        )

        assert counts.photos_with_coordinate == 4
        assert counts.photos_with_a_resolved_locality == 4

    def test_photos_whose_event_would_get_no_name_still_count(self) -> None:
        """Der entartete Fall dieses Blocks: beide Zellen loesen auf, das EINE Event daraus
        bekaeme wegen zweier verschiedener Namen trotzdem keinen. Fuer #469 sind die Fotos
        trotzdem versorgt - deshalb zaehlt E sie."""
        info_by_cell = {
            SPLIT: _info_of(_answer(matched_level="locality", locality="Split")),
            GARMISCH: _info_of(_answer(matched_level="locality", locality="Garmisch")),
        }
        probe = _probe_input(
            photos_total=4,
            photo_cells=(SPLIT, GARMISCH),
            events=(_probe_event(1, cells=(SPLIT, GARMISCH)),),
        )

        assert heading_counts(probe, info_by_cell).events_named == 0
        assert photo_counts(probe, info_by_cell).photos_with_a_resolved_locality == 2

    def test_a_photo_in_an_unresolved_cell_does_not_count(self) -> None:
        info_by_cell = {SPLIT: _info_of(_answer(matched_level="country", country="Kroatien"))}
        counts = photo_counts(
            _probe_input(photos_total=3, photo_cells=(SPLIT, SPLIT)), info_by_cell
        )

        assert counts.photos_with_coordinate == 2
        assert counts.photos_with_a_resolved_locality == 0


# --- Der lokale Kandidat (GeoNames), an seinen Raendern -----------------------------------------
#
# Literal geschriebene Zeilen im echten Format: geonameid, name, asciiname, alternatenames,
# lat, lon, featureClass, featureCode, ... Die Ebene kommt aus Klasse und Code, NIE aus der
# Bevoelkerungszahl.
def _geonames_line(name: str, lat: float, lon: float, feature_class: str, feature_code: str) -> str:
    return "\t".join(
        ["1", name, name, "", str(lat), str(lon), feature_class, feature_code, "DE", ""]
    )


BERLIN_LINES = [
    _geonames_line("Berlin", 52.5200, 13.4050, "P", "PPLC"),
    _geonames_line("Kreuzberg", 52.4980, 13.4030, "P", "PPLX"),
    _geonames_line("Land Berlin", 52.5000, 13.4000, "A", "ADM1"),
    _geonames_line("Bundesrepublik Deutschland", 52.5000, 13.4000, "A", "PCLI"),
]


# --- Der externe Kandidat (Photon), an seinen Raendern ------------------------------------------


def _photon_payload(properties: dict[str, object]) -> dict[str, object]:
    return {"features": [{"type": "Feature", "properties": properties}]}


class TestThePhotonParser:
    """Der Parser-Rand: eine FREMDE Struktur, gegen die nichts vorausgesetzt werden darf."""

    def test_the_level_comes_from_type_not_from_layer(self) -> None:
        """`layer` ist ausschliesslich ein Filter-Parameter der ANFRAGE und kommt in der Antwort
        gar nicht vor. Ein Parser, der darauf sieht, liest systematisch nichts."""
        answer = photon_answer(_photon_payload({"type": "city", "city": "Split"}))

        assert answer is not None
        assert answer.matched_level == "locality"

        misleading = photon_answer(
            _photon_payload({"layer": "city", "city": "Split", "type": "state"})
        )
        assert misleading is not None
        assert misleading.matched_level == "region"

    def test_photons_locality_is_not_our_locality(self) -> None:
        """DIE NAMENSKOLLISION. Photon staffelt `locality` ⊂ `district` ⊂ `city`; unser
        `locality` ist der ORT. Wer Photons `locality` uebernimmt, schreibt "Ritterkiez" als
        Event-Ueberschrift statt "Berlin" - und der Fehler ist an keiner Stelle laut."""
        answer = photon_answer(
            _photon_payload(
                {
                    "type": "house",
                    "locality": "Ritterkiez",
                    "district": "Kreuzberg",
                    "city": "Berlin",
                    "state": "Berlin",
                    "country": "Deutschland",
                }
            )
        )

        assert answer is not None
        assert answer.locality == "Berlin"
        assert answer.neighbourhood == "Kreuzberg"
        # "Ritterkiez" darf in KEINER Stufe auftauchen - es ist eine Ebene, die dieses Projekt
        # nicht fuehrt, und wird ersatzlos verworfen.
        assert "Ritterkiez" not in (
            answer.neighbourhood,
            answer.locality,
            answer.region,
            answer.country,
        )

    def test_street_and_housenumber_never_reach_a_field(self) -> None:
        """Datensparsamkeit am Parser-Rand: es gibt keinen offenen Beutel, in dem sie ankaemen."""
        answer = photon_answer(
            _photon_payload(
                {
                    "type": "house",
                    "street": "Oranienstrasse",
                    "housenumber": "12",
                    "postcode": "10999",
                    "name": "Ein Haus",
                    "city": "Berlin",
                }
            )
        )

        assert answer is not None
        assert "Oranienstrasse" not in str(answer)
        assert "12" not in str(answer)
        assert "10999" not in str(answer)

    @pytest.mark.parametrize(
        ("raw_type", "expected"),
        [
            ("house", "neighbourhood"),
            ("street", "neighbourhood"),
            ("locality", "neighbourhood"),
            ("district", "neighbourhood"),
            ("city", "locality"),
            ("county", "region"),
            ("state", "region"),
            ("country", "country"),
            ("other", None),
            ("was-auch-immer", None),
        ],
    )
    def test_the_whole_type_vocabulary(self, raw_type: str, expected: str | None) -> None:
        answer = photon_answer(_photon_payload({"type": raw_type, "city": "Berlin"}))

        assert answer is not None
        assert answer.matched_level == expected

    def test_a_level_finer_than_ours_still_yields_the_place_name(self) -> None:
        """`house`/`street` sind FEINER als jede Ebene dieses Projekts, nicht groeber. Die
        Begruendung des Regions-Ausschlusses traegt hier ausdruecklich nicht: ein Regionstreffer
        nennt oft eine Stadt Dutzende Kilometer entfernt, ein Haustreffer nennt die richtige."""
        answer = photon_answer(_photon_payload({"type": "house", "city": "Split"}))
        assert answer is not None

        assert usable_locality(_info_of(answer)) == "Split"

    def test_the_raw_level_is_counted_for_the_report(self) -> None:
        """Die Zuordnung oben ist eine ANNAHME ueber eine fremde Quelle. Block C weist die roh
        gesehenen Werte zusaetzlich aus, damit sie am Messergebnis nachpruefbar bleibt."""
        seen: dict[str, int] = {}

        photon_answer(_photon_payload({"type": "city", "city": "Split"}), seen)
        photon_answer(_photon_payload({"type": "city", "city": "Berlin"}), seen)
        photon_answer(_photon_payload({"type": "house", "city": "Berlin"}), seen)

        assert seen == {"city": 2, "house": 1}

    @pytest.mark.parametrize(
        "payload",
        [
            None,
            42,
            "keine Antwort",
            {},
            {"features": []},
            {"features": "nichts"},
            {"features": [42]},
            {"features": [{}]},
            {"features": [{"properties": "nichts"}]},
        ],
    )
    def test_a_malformed_answer_is_no_answer_never_an_exception(self, payload: object) -> None:
        assert photon_answer(payload) is None

    def test_a_hostile_name_goes_through_the_same_sanitisation(self) -> None:
        answer = photon_answer(
            _photon_payload({"type": "city", "city": "Ber‮lin\x00", "district": "A" * 200})
        )

        assert answer is not None
        assert answer.locality == "Berlin"
        # VERWORFEN, nie abgeschnitten - ein gekappter Name waere ein anderer Ort.
        assert answer.neighbourhood is None


class TestTheOutgoingEdge:
    """S2/S9 - was das System verlaesst, ist strukturell begrenzt, nicht zugesagt."""

    async def test_an_unrounded_input_leaves_with_exactly_the_cell_precision(self) -> None:
        """DIE ZWEITE, UNABHAENGIGE SCHRANKE. Gemessen wird an der ABGESETZTEN Anfrage, nicht an
        der Aufrufstelle: das Akzeptanzkriterium haengt an dem Rand, an dem die Daten tatsaechlich
        abfliessen. Eine ungerundete Zahl ist in der Zeichenkette nicht darstellbar."""
        requested: list[httpx.URL] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(request.url)
            return httpx.Response(200, json=_photon_payload({"type": "city", "city": "Split"}))

        resolver = PhotonResolver(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            CloudRequestThrottle(min_interval_seconds=0.0),
            _tally(),
        )
        # Volle EXIF-Praezision, wie sie in `photos.gps_lat` steht.
        await resolver.resolve((43.50812345678, 16.44018765432))

        assert len(requested) == 1
        assert requested[0].params["lat"] == "43.51"
        assert requested[0].params["lon"] == "16.44"

    async def test_the_request_goes_to_the_constant_host(self) -> None:
        requested: list[httpx.URL] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(request.url)
            return httpx.Response(200, json=_photon_payload({"type": "city", "city": "Split"}))

        resolver = PhotonResolver(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            CloudRequestThrottle(min_interval_seconds=0.0),
            _tally(),
        )
        await resolver.resolve(SPLIT)

        assert str(requested[0]).startswith(PHOTON_REVERSE_URL)

    def test_the_target_host_is_a_constant_never_a_value_from_outside(self) -> None:
        """Syntaxbaum-Waechter, KEIN SSRF-PFAD: die Ziel-URL jedes abgesetzten Aufrufs ist ein
        Modulname, nie ein Parameter, ein Datenbankwert oder eine zusammengesetzte Zeichenkette."""
        path = module_file("photosort.place_probe")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))

        module_constants = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }

        urls: list[ast.expr] = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr not in ("stream", "get", "post", "request"):
                continue
            # NUR Aufrufe auf einem HTTP-Client. Ohne diese Einschraenkung faengt der Waechter
            # jedes `dict.get("schluessel")` mit und wird dann entschaerft - und mit ihm die
            # Zusage.
            receiver = node.func.value
            receiver_name = (
                receiver.attr
                if isinstance(receiver, ast.Attribute)
                else receiver.id
                if isinstance(receiver, ast.Name)
                else ""
            )
            if "client" not in receiver_name.lower():
                continue
            # Bei `stream`/`request` steht die Methode vorn, die URL dahinter.
            urls.extend(
                argument
                for argument in node.args
                if not (isinstance(argument, ast.Constant) and argument.value in ("GET", "POST"))
            )

        assert urls, "Der Waechter findet gar keinen abgesetzten Aufruf - er prueft dann nichts."
        for url in urls:
            assert isinstance(url, ast.Name), ast.unparse(url)
            assert url.id in module_constants, url.id

    async def test_a_minimum_interval_is_held_between_two_requests(self) -> None:
        """S9: eine Zeitgrenze und ein Mindestabstand sind Muss. Ueber eine INJIZIERTE Uhr - ein
        Test, der echte Sekunden wartet, wird beim ersten Zeitdruck entschaerft."""
        slept: list[float] = []
        now = [0.0]

        async def fake_sleep(seconds: float) -> None:
            slept.append(seconds)
            now[0] += seconds

        throttle = CloudRequestThrottle(
            min_interval_seconds=PHOTON_MIN_REQUEST_INTERVAL_SECONDS,
            clock=lambda: now[0],
            sleep=fake_sleep,
        )
        resolver = PhotonResolver(
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, json=_photon_payload({"type": "city", "city": "Split"})
                    )
                )
            ),
            throttle,
            _tally(),
        )

        await resolver.resolve(SPLIT)
        await resolver.resolve(GARMISCH)

        assert slept == [PHOTON_MIN_REQUEST_INTERVAL_SECONDS]

    async def test_a_timeout_is_no_answer_never_a_crash(self) -> None:
        """KEINE ANTWORT ist ausdruecklich etwas anderes als eine Antwort ohne brauchbare Ebene:
        eine voruebergehende Stoerung darf die Zelle nicht dauerhaft vergiften."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("zu langsam")

        tally = _tally()
        resolver = PhotonResolver(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            CloudRequestThrottle(min_interval_seconds=0.0),
            tally,
        )

        assert await resolver.resolve(SPLIT) is None
        assert tally.failures == {FAILURE_TRANSPORT: 1}

    async def test_an_error_status_is_no_answer(self) -> None:
        tally = _tally()
        resolver = PhotonResolver(
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(429, text="zu viel"))
            ),
            CloudRequestThrottle(min_interval_seconds=0.0),
            tally,
        )

        assert await resolver.resolve(SPLIT) is None
        assert tally.failures == {FAILURE_HTTP_STATUS: 1}

    async def test_an_oversized_answer_is_read_only_up_to_the_limit(self) -> None:
        """S9: Groesse und Struktur werden BEGRENZT gelesen - eine unerwartet grosse Fremdantwort
        soll den Messlauf nicht in den Speicher laufen lassen."""
        huge = b"x" * (PHOTON_MAX_RESPONSE_BYTES + 1024)
        tally = _tally()
        resolver = PhotonResolver(
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=huge))
            ),
            CloudRequestThrottle(min_interval_seconds=0.0),
            tally,
        )

        assert await resolver.resolve(SPLIT) is None
        assert tally.failures == {FAILURE_TOO_LARGE: 1}

    async def test_a_non_json_answer_is_no_answer(self) -> None:
        tally = _tally()
        resolver = PhotonResolver(
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>"))
            ),
            CloudRequestThrottle(min_interval_seconds=0.0),
            tally,
        )

        assert await resolver.resolve(SPLIT) is None
        assert tally.failures == {FAILURE_UNREADABLE: 1}

    async def test_an_answer_without_a_feature_is_a_miss_not_a_failure(self) -> None:
        """DIE GEGENPROBE, und sie traegt den ganzen Fix: der Dienst HAT geantwortet, er hat nur
        nichts gefunden. Das ist ein Messergebnis - kein Ausfall."""
        tally = _tally()
        resolver = PhotonResolver(
            httpx.AsyncClient(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"features": []}))
            ),
            CloudRequestThrottle(min_interval_seconds=0.0),
            tally,
        )

        assert await resolver.resolve(SPLIT) is None
        assert tally.failures == {}

    async def test_every_failure_token_is_free_of_coordinates_and_names(self) -> None:
        """S11: die Gruende sind ein FESTER Vorrat, nie ein Fremdtext - kein Statuswert, keine
        Fehlermeldung des Dienstes und erst recht keine Zelle geraet darueber in die Ausgabe."""
        assert FAILURE_REASONS == (
            FAILURE_HTTP_STATUS,
            FAILURE_TRANSPORT,
            FAILURE_TOO_LARGE,
            FAILURE_UNREADABLE,
        )
        for reason in FAILURE_REASONS:
            assert reason.replace("-", "").isalpha()


# --- main() gegen eine echte, dateibasierte SQLite ----------------------------------------------

# Die gemessene Lage: ein Projekt, vier Fotos mit Koordinate (drei davon in EINER Zelle - das
# traegt Block E), ein Foto ohne, ein erfolgreicher Lauf mit zwei Events.
_MEASURED_PHOTO_CELLS = [
    (43.5081, 16.4402),
    (43.5083, 16.4405),
    (43.5085, 16.4401),
    (47.4920, 11.0950),
]


async def _seed_measured_project(session: AsyncSession) -> int:
    """Baut die Messlage auf. SCHREIBT - aber im TEST, nie im Kommando."""
    now = datetime(2026, 7, 20, 10, 0, 0)
    project = Project(
        name="Kroatien 2026", opencloud_drive_id="drive", opencloud_path="/Fotos/Kroatien"
    )
    session.add(project)
    await session.flush()

    photos = []
    for index, (lat, lon) in enumerate(_MEASURED_PHOTO_CELLS):
        photos.append(
            Photo(
                project_id=project.id,
                relative_path=f"img{index:03d}.jpg",
                etag=f"etag-{index}",
                content_length=1000,
                taken_at=now + timedelta(minutes=index),
                taken_at_original=now + timedelta(minutes=index),
                last_modified=now,
                gps_lat=lat,
                gps_lon=lon,
            )
        )
    photos.append(
        Photo(
            project_id=project.id,
            relative_path="ohne-ort.jpg",
            etag="etag-ohne",
            content_length=1000,
            taken_at=now + timedelta(minutes=9),
            taken_at_original=now + timedelta(minutes=9),
            last_modified=now,
        )
    )
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add_all([*photos, scoring_run])
    await session.flush()

    criterion_run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(criterion_run)
    await session.flush()

    split_event = Event(
        criterion_scoring_run_id=criterion_run.id,
        position=1,
        started_at=now,
        ended_at=now + timedelta(minutes=2),
        place_kind="coordinate",
    )
    garmisch_event = Event(
        criterion_scoring_run_id=criterion_run.id,
        position=2,
        started_at=now + timedelta(minutes=3),
        ended_at=now + timedelta(minutes=4),
        place_kind="coordinate",
    )
    session.add_all([split_event, garmisch_event])
    await session.flush()

    session.add_all(
        [
            PhotoRanking(
                criterion_scoring_run_id=criterion_run.id,
                photo_id=photo.id,
                event_id=split_event.id if index < 3 else garmisch_event.id,
                rank_score=0.5,
                rank_position=1,
            )
            for index, photo in enumerate(photos[:4])
        ]
    )
    await session.flush()
    return project.id


SPLIT_DATASET_LINES = [
    _geonames_line("Split", 43.5081, 16.4402, "P", "PPL"),
    _geonames_line("Varos", 43.5070, 16.4380, "P", "PPLX"),
    _geonames_line("Garmisch-Partenkirchen", 47.4920, 11.0950, "P", "PPL"),
]


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    path = tmp_path / "allCountries.txt"
    path.write_text("\n".join(SPLIT_DATASET_LINES) + "\n", encoding="utf-8")
    return path


async def _table_snapshot(session: AsyncSession) -> dict[str, list[tuple[object, ...]]]:
    """JEDE Tabelle aus `Base.metadata.sorted_tables` - GEMESSEN, nie als handgeschriebene Liste.

    Eine von Hand gepflegte Tabellenliste veraltet still, sobald eine Tabelle hinzukommt; genau
    die neue waere dann die ungepruefte."""
    return {
        table.name: [tuple(row) for row in (await session.execute(select(table))).all()]
        for table in Base.metadata.sorted_tables
    }


class TestARealRunChangesNothing:
    """Teil 3 der Zusage "rein lesend": ein ECHTER `main()`-Lauf gegen eine dateibasierte SQLite,
    mit Schnappschuss jeder Tabelle davor und danach.

    Der Formwaechter allein bestuende gegen ein Modul, das ueber eine Hilfsfunktion schreibt;
    dieser Vergleich allein bestuende gegen einen Schreibpfad, den die Testlage nicht betritt."""

    def test_not_a_single_row_changes(self, tmp_path: Path, dataset: Path) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> tuple[int, dict[str, list[tuple[object, ...]]]]:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _seed_measured_project(session)
                await session.commit()
                before = await _table_snapshot(session)
            await engine.dispose()
            return project_id, before

        async def snapshot() -> dict[str, list[tuple[object, ...]]]:
            engine = make_engine(url)
            factory = make_session_factory(engine)
            async with factory() as session:
                taken = await _table_snapshot(session)
            await engine.dispose()
            return taken

        project_id, before = asyncio.run(prepare())

        exit_code = main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)],
            database_url=url,
            external_lookup_enabled=False,
        )

        assert exit_code == 0
        after = asyncio.run(snapshot())
        assert after == before

    def test_the_snapshot_actually_covers_something(self, tmp_path: Path) -> None:
        """Gegenprobe: ohne sie bestuende der Vergleich oben auch gegen einen leeren
        Schnappschuss - etwa nach einem Umbau von `Base.metadata`."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> dict[str, list[tuple[object, ...]]]:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                await _seed_measured_project(session)
                await session.commit()
                taken = await _table_snapshot(session)
            await engine.dispose()
            return taken

        snapshot = asyncio.run(prepare())

        assert {"projects", "photos", "events", "photo_rankings"} <= set(snapshot)
        assert len(snapshot["photos"]) == 5
        assert len(snapshot["events"]) == 2


class TestMainRefusesLoudly:
    """Nicht Traceback und nicht stille Null."""

    def test_an_unknown_project_id(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> None:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await engine.dispose()

        asyncio.run(prepare())

        exit_code = main(["--project-id", "999"], database_url=url, external_lookup_enabled=False)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "999" in captured.err
        assert captured.out == ""

    def test_a_project_without_a_successful_run(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project = Project(name="Ohne Lauf", opencloud_drive_id="d", opencloud_path="/p")
                session.add(project)
                await session.flush()
                project_id = project.id
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        exit_code = main(
            ["--project-id", str(project_id)], database_url=url, external_lookup_enabled=False
        )

        assert exit_code == 1
        assert "Lauf" in capsys.readouterr().err


class TestTheOutputSeparatesNumbersFromPlaces:
    """S5. Die gesuchten Zeichenfolgen stammen aus der MESSLAGE, nie aus einem allgemeinen
    Zahlenmuster: `43.51` ist die Zelle dieses Projekts, `Split` ihr aufgeloester Name."""

    def test_both_halves_in_one_case(
        self, tmp_path: Path, dataset: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _seed_measured_project(session)
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        assert (
            main(
                ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)],
                database_url=url,
                external_lookup_enabled=False,
            )
            == 0
        )
        plain = capsys.readouterr().out

        # OHNE --namen: keine Koordinate der Messlage und kein aufgeloester Name.
        assert "43.51" not in plain
        assert "16.44" not in plain
        assert "47.49" not in plain
        assert "Split" not in plain
        assert "Garmisch-Partenkirchen" not in plain
        # ... aber die Zahlen stehen da.
        assert "Fotos gesamt: 5" in plain
        assert "verschiedene Zellen im Projekt: 2" in plain

        assert (
            main(
                ["--project-id", str(project_id), "--ortsdatensatz", str(dataset), "--namen"],
                database_url=url,
                external_lookup_enabled=False,
            )
            == 0
        )
        with_names = capsys.readouterr().out

        # MIT --namen: genau die Namen, mit ihrem eigenen Warnsatz.
        assert "Split" in with_names
        assert "Garmisch-Partenkirchen" in with_names
        assert "ACHTUNG" in with_names
        # Auch dann keine Koordinate: der Abschnitt traegt Namen, nicht Zellen.
        assert "43.51" not in with_names
        assert "16.44" not in with_names

    def test_block_e_counts_photos_and_block_d_counts_events(
        self, tmp_path: Path, dataset: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Die Messlage traegt DREI Fotos in der Split-Zelle und EIN Event darauf. Eine Ausgabe,
        die E aus D ableitet, zeigt hier zwei statt vier."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _seed_measured_project(session)
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())
        main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)],
            database_url=url,
            external_lookup_enabled=False,
        )
        report = capsys.readouterr().out

        assert "Events, die einen Ortsnamen bekaemen: 2" in report
        assert "davon in einer Zelle mit Ortsnamen: 4" in report


class TestTheSwitchIsOffByDefault:
    """S1/S4: steht der Schalter auf `false`, wird der externe Auflöser GAR NICHT ERST GEBAUT."""

    def test_the_external_factory_is_never_called_and_the_run_goes_through(
        self, tmp_path: Path, dataset: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _seed_measured_project(session)
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        def exploding_factory(seen_levels: dict[str, int]) -> PlaceResolver:
            raise AssertionError(
                "Der externe Aufloeser wurde trotz ausgeschaltetem Schalter gebaut."
            )

        exit_code = main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)],
            database_url=url,
            external_lookup_enabled=False,
            build_external_resolver=exploding_factory,
        )

        assert exit_code == 0
        report = capsys.readouterr().out
        # Das AUSBLEIBEN wird gemeldet, statt eine leere Spalte zu zeigen, die als schlechtes
        # Messergebnis gelesen wuerde.
        assert "NICHT GEMESSEN" in report
        assert "EXTERNAL_PLACE_LOOKUP_ENABLED" in report
        assert "sie sind nicht null" in report

    def test_an_absent_local_dataset_is_reported_too_not_shown_as_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _seed_measured_project(session)
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        assert (
            main(
                ["--project-id", str(project_id)],
                database_url=url,
                external_lookup_enabled=False,
            )
            == 0
        )
        report = capsys.readouterr().out

        assert report.count("NICHT GEMESSEN") == 2
        assert "--ortsdatensatz" in report

    def test_with_the_switch_on_the_external_candidate_is_measured(
        self, tmp_path: Path, dataset: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Die Gegenprobe zum Fall darueber: ohne sie bestuende "der Schalter wirkt" auch dann,
        wenn der externe Weg ueberhaupt nicht mehr gebaut werden KANN."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _seed_measured_project(session)
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        class FakeResolver:
            """Ein Double, kein Client - die Netzsperre machte einen echten laut."""

            def __init__(self, tally: ProbeTally) -> None:
                self._tally = tally

            async def resolve(self, cell: Cell) -> PlaceAnswer | None:
                return photon_answer(
                    _photon_payload({"type": "city", "city": "Split"}), self._tally.seen_levels
                )

        exit_code = main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)],
            database_url=url,
            external_lookup_enabled=True,
            build_external_resolver=FakeResolver,
        )

        assert exit_code == 0
        report = capsys.readouterr().out
        # Nur der lokale Kandidat fehlt nicht mehr - der externe traegt jetzt Zahlen.
        assert report.count("NICHT GEMESSEN") == 0
        # Die roh gesehene Ebenenangabe steht in Block C, damit die Zuordnung auf `PLACE_LEVELS`
        # am Messergebnis nachpruefbar bleibt statt geglaubt werden zu muessen.
        assert "rohe Ebenenangaben der Quelle: city: 2" in report
        # ... und weiterhin keine Koordinate und kein Name ohne --namen.
        assert "43.51" not in report
        assert "Split" not in report

    def test_a_partial_outage_is_reported_apart_from_the_misses(
        self, tmp_path: Path, dataset: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """DAS SZENARIO, GEGEN DAS DER AUSFALLZAEHLER ANTRITT: Die Dienst-Instanz drosselt nach
        der ersten Zelle. Ohne die Trennung meldete der Bericht "ohne Treffer: 1" und liesse eine
        Drosselung wie einen schlechten Anbieter aussehen - und darauf faellt eine nicht
        ruecknehmbare Wegwahl, die ein zweiter Messlauf nur um den Preis eines zweiten Abflusses
        korrigieren koennte."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _seed_measured_project(session)
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        def throttling_factory(tally: ProbeTally) -> PlaceResolver:
            # Die erste Zelle wird beantwortet, ab der zweiten kommt HTTP 429.
            answered = [0]

            def handler(request: httpx.Request) -> httpx.Response:
                answered[0] += 1
                if answered[0] == 1:
                    return httpx.Response(
                        200, json=_photon_payload({"type": "city", "city": "Split"})
                    )
                return httpx.Response(429, text="slow down")

            return PhotonResolver(
                httpx.AsyncClient(transport=httpx.MockTransport(handler)),
                CloudRequestThrottle(min_interval_seconds=0.0),
                tally,
            )

        exit_code = main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)],
            database_url=url,
            external_lookup_enabled=True,
            build_external_resolver=throttling_factory,
        )

        assert exit_code == 0
        report = capsys.readouterr().out

        # Die zwei Zellen des Projekts: eine beantwortet, eine gedrosselt.
        assert "AUSFALL (gar keine verwertbare Antwort): 1" in report
        assert f"{FAILURE_HTTP_STATUS}: 1" in report
        # Der Ausfall steht NICHT zusaetzlich als Nichttreffer da.
        assert "ohne Treffer (Quelle antwortete, fand nichts): 0" in report
        # Und er ist als unbrauchbar gekennzeichnet, nicht als Messwert.
        assert "NICHT gemessen" in report

    def test_without_an_outage_the_failure_line_stays_at_zero(
        self, tmp_path: Path, dataset: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Gegenprobe: die Ausfallzeile steht immer da - eine Zeile, die nur bei Ausfall
        erschiene, liesse ihr Fehlen als "kein Ausfallbegriff" lesen."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'probe.db'}"

        async def prepare() -> int:
            engine = make_engine(url)
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = make_session_factory(engine)
            async with factory() as session:
                project_id = await _seed_measured_project(session)
                await session.commit()
            await engine.dispose()
            return project_id

        project_id = asyncio.run(prepare())

        def healthy_factory(tally: ProbeTally) -> PlaceResolver:
            return PhotonResolver(
                httpx.AsyncClient(
                    transport=httpx.MockTransport(
                        lambda _: httpx.Response(200, json={"features": []})
                    )
                ),
                CloudRequestThrottle(min_interval_seconds=0.0),
                tally,
            )

        main(
            ["--project-id", str(project_id), "--ortsdatensatz", str(dataset)],
            database_url=url,
            external_lookup_enabled=True,
            build_external_resolver=healthy_factory,
        )
        report = capsys.readouterr().out

        assert "AUSFALL (gar keine verwertbare Antwort): 0" in report
        # Der Dienst HAT geantwortet und nichts gefunden - das ist ein Messergebnis.
        assert "ohne Treffer (Quelle antwortete, fand nichts): 2" in report
        assert "NICHT gemessen" not in report

    def test_an_unreachable_database_leaks_no_credentials(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Die SQLAlchemy-Meldung kann die DATABASE_URL samt Zugangsdaten enthalten - ausgegeben
        wird deshalb nur der Fehlertyp, nie `str(exc)` und nie ein Traceback."""
        unreachable = "sqlite+aiosqlite:////nicht/vorhandenes/verzeichnis/geheim.db"

        exit_code = main(
            ["--project-id", "1"], database_url=unreachable, external_lookup_enabled=False
        )

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "geheim" not in captured.err
        assert "Datenbankzugriff fehlgeschlagen" in captured.err
