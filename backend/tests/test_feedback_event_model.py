"""Das Modell des Ereignis-Logs (Spec 0432, ADR 0100) und die strukturellen Waechter um es herum.

DREI ZUSAGEN, die weder Schema noch Datenbank erzwingen, stehen hier:

1. `event_id` SIEHT wie eine Referenz aus und ist keine - vier Nachweise, weil kein einzelner
   traegt (Teststrategie). Hier stehen der erste (am Modell) und der dritte (AST-Waechter gegen
   jede Verbindung der beiden Spalten); der zweite steht an der gerenderten Postgres-DDL in
   `test_migration_feedback_events.py`, der vierte als Verhaltensfall ueber
   `rebuild_run_grouping` in `test_feedback_log.py`.
2. APPEND-ONLY (S10): ausserhalb von `project_deletion.py` setzt kein Modul `update(FeedbackEvent)`
   oder `delete(FeedbackEvent)` ab. Ihr Bruch nimmt still weg, worauf sich jede Zahl der Diagnose
   stuetzt.
3. Die Reihenfolge IST die aufsteigende `id`, nie `occurred_at` (L5).
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort
from photosort.models import FeedbackEvent, FeedbackEventKind, Photo, Project, User

# Genau die Module, die eine `FeedbackEvent`-Zeile aendern oder loeschen duerfen. Die
# Projektloeschung ist die einzige Ausnahme der Append-only-Zusage (ADR 0100 Punkt 1, S13).
_ALLOWED_MUTATING_MODULES = ("project_deletion.py",)


async def _make_photo(session: AsyncSession) -> Photo:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    session.add(project)
    await session.flush()
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project.id,
        relative_path="a.jpg",
        etag="etag-1",
        content_length=100,
        taken_at=now,
        taken_at_original=now,
        last_modified=now,
    )
    session.add(photo)
    await session.flush()
    return photo


# --- Der Vorrat und die Reihenfolge ------------------------------------------------------------


def test_the_kind_vocabulary_has_exactly_nine_values() -> None:
    """Die Zahl steht hier als Literal, weil die Feldmatrix ueber `tuple(FeedbackEventKind)`
    parametrisiert ist: Ein ergaenzter Wert brauchte sonst keine eigene Zeile in der Matrix und
    liefe ungeprueft durch."""
    assert len(tuple(FeedbackEventKind)) == 9
    assert {kind.value for kind in FeedbackEventKind} == {
        "photo_included",
        "photo_removed",
        "decision_withdrawn",
        "exchanged",
        "motif_added",
        "motif_dropped",
        "motif_correction_withdrawn",
        "final_decision_in",
        "final_decision_out",
    }


def test_the_withdrawal_of_a_joint_decision_has_no_value_of_its_own() -> None:
    """ADR 0099 kennt kein `DELETE` auf der gemeinsamen Entscheidung - folgerichtig gibt es fuer
    sie keinen Ruecknahme-Wert. Die Aussagerichtung steht als EIGENER Wert und nie als nullable
    Boolean daneben: Eine dritte Bedeutung von `NULL` waere auf keinem Lesepfad als Fehler
    erkennbar."""
    final = {kind.value for kind in FeedbackEventKind if kind.value.startswith("final_decision")}

    assert final == {"final_decision_in", "final_decision_out"}


async def test_two_events_with_the_same_timestamp_stay_ordered_by_their_id(
    db_session: AsyncSession,
) -> None:
    """L5: Der Zeitstempel wird hier GLEICH gesetzt. Mit natuerlich verschiedenen Zeitstempeln
    bestuende der Fall auch gegen ein `ORDER BY occurred_at`, und unter SQLite ist eine
    unvollstaendige Sortierung zufaellig stabil."""
    photo = await _make_photo(db_session)
    same_moment = datetime(2026, 9, 13, 10, 0, 0)

    for kind in (
        FeedbackEventKind.PHOTO_INCLUDED,
        FeedbackEventKind.DECISION_WITHDRAWN,
        FeedbackEventKind.PHOTO_REMOVED,
    ):
        db_session.add(
            FeedbackEvent(
                project_id=photo.project_id,
                photo_id=photo.id,
                kind=kind,
                occurred_at=same_moment,
            )
        )
    await db_session.commit()

    rows = (
        (await db_session.execute(select(FeedbackEvent).order_by(FeedbackEvent.id))).scalars().all()
    )

    assert [row.occurred_at for row in rows] == [same_moment] * 3
    assert [row.id for row in rows] == sorted(row.id for row in rows)
    assert [row.kind for row in rows] == [
        FeedbackEventKind.PHOTO_INCLUDED,
        FeedbackEventKind.DECISION_WITHDRAWN,
        FeedbackEventKind.PHOTO_REMOVED,
    ]


async def test_a_row_without_a_user_and_without_any_frozen_number_is_storable(
    db_session: AsyncSession,
) -> None:
    """L4 und S9 an der Tabelle: Ein Foto ohne Modellbewertung erzeugt trotzdem ein Ereignis, und
    die gemeinsame Entscheidung traegt keinen Nutzer."""
    photo = await _make_photo(db_session)
    db_session.add(
        FeedbackEvent(
            project_id=photo.project_id,
            photo_id=photo.id,
            kind=FeedbackEventKind.FINAL_DECISION_IN,
        )
    )
    await db_session.commit()

    stored = (await db_session.execute(select(FeedbackEvent))).scalar_one()

    assert stored.user_id is None
    assert stored.level is None
    assert stored.quality is None
    assert stored.event_id is None
    assert stored.weight == 1.0
    assert stored.occurred_at is not None


async def test_a_row_with_a_user_keeps_the_reference(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    user = User(username="anne", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        FeedbackEvent(
            project_id=photo.project_id,
            photo_id=photo.id,
            user_id=user.id,
            kind=FeedbackEventKind.PHOTO_REMOVED,
        )
    )
    await db_session.commit()

    stored = (await db_session.execute(select(FeedbackEvent))).scalar_one()

    assert stored.user_id == user.id


# --- `event_id` sieht wie eine Referenz aus und ist keine: Nachweis 1 (Modell) -----------------


def test_the_event_id_carries_no_foreign_key_while_the_photo_id_does() -> None:
    """ERSTER der vier Nachweise. Die zweite Haelfte steht bewusst im SELBEN Fall: Ohne sie
    bestuende die Aussage auch fuer eine Tabelle ganz ohne Fremdschluessel, und genau so ginge
    sie bei einem spaeteren Umbau still verloren."""
    columns = FeedbackEvent.__table__.columns

    assert columns["event_id"].foreign_keys == set()
    assert columns["photo_id"].foreign_keys != set()
    assert columns["replaced_photo_id"].foreign_keys != set()
    assert columns["criterion_scoring_run_id"].foreign_keys != set()


# --- `event_id` sieht wie eine Referenz aus und ist keine: Nachweis 3 (AST-Waechter) ----------


def _joins_feedback_event_id_against_event_id(source: str) -> bool:
    """Findet jede Verbindung von `FeedbackEvent.event_id` gegen `Event.id` im Syntaxbaum.

    Beide Schreibformen, in denen eine solche Verbindung in SQLAlchemy entsteht, sind im Baum
    DERSELBE Knoten: das `where`-Praedikat und das `onclause` eines `join(...)` sind beide ein
    `ast.Compare` der zwei Attributzugriffe. Erkannt wird er in beiden Reihenfolgen.

    BEKANNTE GRENZE: eine ueber rohes SQL (`text(...)`) geschriebene Verbindung ist statisch
    nicht erkennbar. Dagegen steht der Verhaltensfall ueber `rebuild_run_grouping`."""

    def _is_feedback_event_id(node: ast.expr) -> bool:
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "event_id"
            and isinstance(node.value, ast.Name)
            and node.value.id == "FeedbackEvent"
        )

    def _is_event_id(node: ast.expr) -> bool:
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "id"
            and isinstance(node.value, ast.Name)
            and node.value.id == "Event"
        )

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare) and len(node.comparators) == 1:
            left, right = node.left, node.comparators[0]
            if (_is_feedback_event_id(left) and _is_event_id(right)) or (
                _is_event_id(left) and _is_feedback_event_id(right)
            ):
                return True
    return False


def test_no_module_joins_the_log_against_the_event_table() -> None:
    """DRITTER der vier Nachweise, und der einzige, der eine spaeter HINZUGEFUEGTE Abfrage
    faengt: Die Spalte ist ein Gruppierungsschluessel, gueltig allein zusammen mit dem
    `criterion_scoring_run_id` derselben Zeile. Eine Verbindung gegen `events.id` verlaesst sich
    auf eine Zeile, die `rebuild_run_grouping` bei jedem Neuaufbau loescht und neu anlegt - das
    Ergebnis waere eine stillschweigend leere Menge, kein Fehler."""
    source_root = Path(photosort.__file__).resolve().parent
    offenders = sorted(
        str(path.relative_to(source_root))
        for path in source_root.rglob("*.py")
        if _joins_feedback_event_id_against_event_id(path.read_text(encoding="utf-8"))
    )

    assert offenders == [], (
        "Diese Module verbinden `FeedbackEvent.event_id` mit `Event.id`, obwohl die Spalte "
        f"ausdruecklich KEINE Referenz ist: {offenders}"
    )


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param(
            "select(FeedbackEvent).where(FeedbackEvent.event_id == Event.id)", id="vergleich"
        ),
        pytest.param(
            "select(FeedbackEvent).join(Event, Event.id == FeedbackEvent.event_id)",
            id="vergleich-umgekehrt",
        ),
    ],
)
def test_the_guard_finds_every_written_form_of_the_join(snippet: str) -> None:
    """SELBSTSCHUTZ: Ein Waechter, der seine eigene Fundform nicht mehr erkennt, bleibt gruen,
    ohne etwas zu pruefen."""
    assert _joins_feedback_event_id_against_event_id(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param(
            "select(PhotoRanking).where(PhotoRanking.event_id == Event.id)", id="andere-tabelle"
        ),
        pytest.param(
            "select(FeedbackEvent).where(FeedbackEvent.event_id == run_event_id)",
            id="gegen-eine-variable",
        ),
        pytest.param(
            '"FeedbackEvent.event_id traegt keinen Fremdschluessel auf Event.id"',
            id="blosse-nennung-im-text",
        ),
    ],
)
def test_the_guard_stays_silent_on_the_legitimate_forms(snippet: str) -> None:
    """POSITIV-GEGENPROBE: `PhotoRanking.event_id` IST eine echte Referenz und wird taeglich so
    verbunden; der Vergleich gegen eine gewoehnliche Variable ist genau der vorgesehene Weg; und
    die blosse NENNUNG im Fliesstext darf nicht anschlagen - die Modul-Docstrings dieses Projekts
    begruenden die Zusage ausdruecklich."""
    assert not _joins_feedback_event_id_against_event_id(snippet)


# --- Append-only (S10) -------------------------------------------------------------------------


def _mutates_feedback_events(source: str) -> bool:
    """Findet `update(FeedbackEvent)` und `delete(FeedbackEvent)` als Aufruf im Syntaxbaum -
    ueber den Baum und nicht per Textsuche, damit ein Vorkommen im Fliesstext eines Docstrings
    nicht anschlaegt."""
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else None
        )
        if name not in {"update", "delete"}:
            continue
        if any(
            isinstance(argument, ast.Name) and argument.id == "FeedbackEvent"
            for argument in node.args
        ):
            return True
    return False


def test_only_the_project_deletion_may_remove_a_recorded_event() -> None:
    """S10, STRUKTURELLER Waechter: Weder Schema noch Datenbank erzwingen Append-only. Eine
    spaetere Bereinigungsmigration oder ein Feature, das ein Ereignis "korrigiert", roetet keinen
    Verhaltenstest - es nimmt still weg, worauf sich jede Zahl der Diagnose stuetzt.

    Geprueft wird GLEICHHEIT, nicht Teilmenge: Findet der Waechter die erlaubte Stelle nicht
    mehr, prueft er fuer sie nichts."""
    source_root = Path(photosort.__file__).resolve().parent
    mutating = {
        str(path.relative_to(source_root))
        for path in source_root.rglob("*.py")
        if _mutates_feedback_events(path.read_text(encoding="utf-8"))
    }

    assert mutating == set(_ALLOWED_MUTATING_MODULES), (
        "Die Menge der Module, die `FeedbackEvent`-Zeilen aendern oder loeschen, weicht von der "
        f"einen erlaubten ab ({sorted(_ALLOWED_MUTATING_MODULES)}). Zu viel: "
        f"{sorted(mutating - set(_ALLOWED_MUTATING_MODULES))}; nicht mehr gefunden: "
        f"{sorted(set(_ALLOWED_MUTATING_MODULES) - mutating)}"
    )


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param("session.execute(delete(FeedbackEvent))", id="delete"),
        pytest.param(
            "session.execute(update(FeedbackEvent).values(weight=2.0))", id="update-values"
        ),
        pytest.param("sa.delete(FeedbackEvent)", id="qualifizierter-aufruf"),
    ],
)
def test_the_append_only_guard_finds_every_written_form(snippet: str) -> None:
    """SELBSTSCHUTZ, siehe oben."""
    assert _mutates_feedback_events(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param("session.add(FeedbackEvent(photo_id=1))", id="insert-ist-erlaubt"),
        pytest.param("session.execute(delete(Rating))", id="andere-tabelle"),
        pytest.param(
            '"Auf feedback_events laeuft ausschliesslich INSERT - kein delete(FeedbackEvent)."',
            id="blosse-nennung-im-text",
        ),
    ],
)
def test_the_append_only_guard_stays_silent_on_the_legitimate_forms(snippet: str) -> None:
    assert not _mutates_feedback_events(snippet)


# --- Invariante 2, strukturelle Haelfte: die Endauswahl kennt keinen Nutzer -------------------

_ALBUM_DECISIONS_MODULE = Path(photosort.__file__).resolve().parent / "api" / "album_decisions.py"


def _functions_touching_the_user(source: str) -> tuple[list[str], list[str]]:
    """Je Funktionsrumpf: Nimmt sie ein `current_user` entgegen, und liest sie `User`?

    AUF FUNKTIONSRUMPF-GRANULARITAET und nicht ueber eine Textsuche im ganzen Modul - der
    Modulkopf BEGRUENDET die Abwesenheit ausdruecklich und nennt dabei `current_user`. Ein
    Wortverbot ueber die Datei verboete genau diese Begruendung."""
    taking: list[str] = []
    reading: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        arguments = node.args
        names = [
            argument.arg
            for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)
        ]
        if any(name == "current_user" for name in names):
            taking.append(node.name)
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name) and inner.id == "User":
                reading.append(node.name)
                break
    return taking, reading


def test_no_function_of_the_album_decision_endpoint_obtains_a_user() -> None:
    """S9, STRUKTURELLE Haelfte: `user_id IS NULL` der gemeinsamen Entscheidung wird nie
    aufgefuellt - getragen davon, dass dieser Router gar keinen Nutzer kennt.

    Ein Ereignisschreiber, der sich dafuer eines besorgt, fuehrte das in ADR 0099 verworfene
    `decided_by` durch die Hintertuer ein - und das Log waere der Ort, an dem man nachsieht, wer
    wollte, was das PROJEKT entschieden hat. Ein Verhaltensfall roetete das nicht: Die Zeile saehe
    genauso aus wie eine richtige, nur mit einem Wert mehr."""
    source = _ALBUM_DECISIONS_MODULE.read_text(encoding="utf-8")

    taking, reading = _functions_touching_the_user(source)

    assert taking == [], (
        f"Diese Funktionen von api/album_decisions.py nehmen ein `current_user` entgegen: {taking}"
    )
    assert reading == [], f"Diese Funktionen von api/album_decisions.py lesen `User`: {reading}"


def test_the_router_still_carries_its_mandatory_auth_dependency() -> None:
    """GEGENPROBE, und sie traegt hier tatsaechlich: Ohne sie waere der Waechter oben durch
    ENTFERNEN DER AUTHENTIFIZIERUNG zu erfuellen. Die Torwaechter-Dependency am Router ist die
    einzige Auth dieses Endpunkts - an der Funktionssignatur ist sie nicht sichtbar."""
    source = _ALBUM_DECISIONS_MODULE.read_text(encoding="utf-8")

    assert "dependencies=[Depends(get_current_user)]" in source


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param(
            "async def f(current_user: User = Depends(get_current_user)) -> None: ...",
            id="parameter-und-lesezugriff",
        ),
        pytest.param(
            "async def f(session: AsyncSession) -> None:\n    await session.execute(select(User))",
            id="nur-lesezugriff",
        ),
    ],
)
def test_the_user_guard_finds_both_written_forms(snippet: str) -> None:
    """SELBSTSCHUTZ: Beide Haelften der Aussage haben ihre eigene Form im Code - der Parameter und
    der Lesezugriff."""
    taking, reading = _functions_touching_the_user(snippet)

    assert taking or reading


def test_the_user_guard_stays_silent_on_a_mere_mention_in_a_comment() -> None:
    """DIE tragende Gegenprobe: Der Modulkopf von `api/album_decisions.py` begruendet ausdruecklich,
    warum es hier KEIN `current_user` gibt. Ein Waechter, der die blosse Nennung ahndet, verboete
    genau die Begruendung - und wer sie entfernt, macht ihn wieder gruen."""
    snippet = (
        '"""Der Endpunkt nimmt KEIN current_user entgegen - die Entscheidung gehoert dem '
        'Projekt, nicht einem User."""\n'
        "async def f(session: AsyncSession) -> None: ...\n"
    )

    assert _functions_touching_the_user(snippet) == ([], [])
