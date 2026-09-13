"""Die EINE Schreibstelle des Ereignis-Logs (`feedback_log.py`, Spec 0432, ADR 0100).

DIE FELDMATRIX JE `kind` ist die erste der drei nicht per Constraint erzwungenen Invarianten. Sie
wird hier ueber einen Fall je `kind` geprueft, parametrisiert ueber `tuple(FeedbackEventKind)` und
nicht ueber eine zweite Aufzaehlung: Eine danebenstehende Liste und der Vorrat driften, und ein
ergaenzter Wert liefe ungeprueft durch. Die Assertion gilt dem EXAKTEN Satz belegter Felder - eine
Teilmengenpruefung liesse jedes zusaetzlich befuellte Feld durch, und genau das ist die
Fehlerklasse (ein `user_id` an einer gemeinsamen Entscheidung, ein `replaced_photo_id` an einem
gewoehnlichen Streichen).

`user_id IS NULL` GENAU FUER DIE ENDAUSWAHL ist die zweite Invariante, hier als Allaussage ueber
die Matrix und in beiden Richtungen in EINEM Fall.

Hier steht ausserdem der VIERTE der vier Nachweise dafuer, dass `event_id` wie eine Referenz
aussieht und keine ist: `rebuild_run_grouping` loescht die `Event`-Zeilen eines Laufs und legt sie
neu an - danach sind alle Ereignisse unveraendert da.

EIN ZWISCHENZUSTAND OHNE LESER IST KEIN HANDEINFUEGEN: Die Faelle dieser Datei pruefen die
geschriebene Zeile per `select(FeedbackEvent)`, weil der Lesepfad erst mit PR 2 entsteht. Das
Muster, das handeingefuegte Zeilen bei abgeschaltetem SCHREIBpfad beanstandet, trifft hier nicht
zu - geschrieben wird durchgehend ueber den Produktionsweg.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.feedback_log import (
    FINAL_DECISION_WEIGHT,
    load_frozen_context,
    record_album_decision,
    record_exchange,
    record_final_decision,
    record_motif_correction,
)
from photosort.models import (
    CriterionScoringRun,
    Event,
    FeedbackEvent,
    FeedbackEventKind,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoMotifAssessment,
    PhotoMotifStrength,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.worker import rebuild_run_grouping

# Die Felder, die ueberhaupt belegt sein KOENNEN. `id` und `occurred_at` stehen bewusst nicht
# darin: beide werden von der Datenbank vergeben und tragen keine Aussage ueber den `kind`.
_MATRIX_FIELDS = (
    "project_id",
    "user_id",
    "photo_id",
    "weight",
    "criterion_scoring_run_id",
    "event_id",
    "replaced_photo_id",
    "motif_key",
    "motif_strength",
    "level",
    "replaced_level",
    "quality",
    "replaced_quality",
)

# Die Felder, die JEDES Ereignis traegt, wenn ein erfolgreicher Lauf mit Rangzeile und Modellstufe
# vorliegt.
_BASE = {
    "project_id",
    "photo_id",
    "weight",
    "criterion_scoring_run_id",
    "event_id",
    "level",
    "quality",
}

# Der EXAKTE Satz belegter Felder je `kind`, gemessen in einer Lage, in der JEDES optionale Feld
# belegbar waere: voller Lauf, Rangzeile, Modellstufe, Motivstaerke. Was hier fehlt, fehlt aus
# fachlichem Grund und nicht aus Mangel an Daten.
_EXPECTED_FIELDS: dict[FeedbackEventKind, frozenset[str]] = {
    FeedbackEventKind.PHOTO_INCLUDED: frozenset(_BASE | {"user_id"}),
    FeedbackEventKind.PHOTO_REMOVED: frozenset(_BASE | {"user_id"}),
    FeedbackEventKind.DECISION_WITHDRAWN: frozenset(_BASE | {"user_id"}),
    FeedbackEventKind.EXCHANGED: frozenset(
        _BASE | {"user_id", "replaced_photo_id", "replaced_level", "replaced_quality"}
    ),
    FeedbackEventKind.MOTIF_ADDED: frozenset(_BASE | {"user_id", "motif_key", "motif_strength"}),
    FeedbackEventKind.MOTIF_DROPPED: frozenset(_BASE | {"user_id", "motif_key", "motif_strength"}),
    FeedbackEventKind.MOTIF_CORRECTION_WITHDRAWN: frozenset(
        _BASE | {"user_id", "motif_key", "motif_strength"}
    ),
    FeedbackEventKind.FINAL_DECISION_IN: frozenset(_BASE),
    FeedbackEventKind.FINAL_DECISION_OUT: frozenset(_BASE),
}

_MOTIF_KINDS = (
    FeedbackEventKind.MOTIF_ADDED,
    FeedbackEventKind.MOTIF_DROPPED,
    FeedbackEventKind.MOTIF_CORRECTION_WITHDRAWN,
)
_ALBUM_DECISION_KINDS = (
    FeedbackEventKind.PHOTO_INCLUDED,
    FeedbackEventKind.PHOTO_REMOVED,
    FeedbackEventKind.DECISION_WITHDRAWN,
)
_FINAL_KINDS = (FeedbackEventKind.FINAL_DECISION_IN, FeedbackEventKind.FINAL_DECISION_OUT)


@dataclass(frozen=True)
class _Graph:
    """Die Ids stehen hier als einfache Zahlen und nicht als ORM-Objekte: Die Faelle rufen
    `session.expire_all()`, um den TATSAECHLICH geschriebenen Zeileninhalt zu lesen, und ein
    danach angefasstes Objekt loeste ein Nachladen aus."""

    project_id: int
    user_id: int
    photo: Photo
    other_photo: Photo
    run: CriterionScoringRun
    run_id: int
    event_id: int


async def _build_graph(session: AsyncSession, *, name: str = "Costa Rica") -> _Graph:
    """Ein Projekt mit erfolgreichem Lauf, einem Event und ZWEI eingeordneten Fotos - beide mit
    Modellstufe und Rangwert, damit jedes eingefrorene Feld belegbar waere."""
    project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
    session.add(project)
    user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one_or_none()
    if user is None:
        user = User(username="anne", password_hash="x")
        session.add(user)
    await session.flush()

    now = datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    photos = [
        Photo(
            project_id=project.id,
            relative_path=f"{name}-{index}.jpg",
            etag=f"etag-{name}-{index}",
            content_length=100,
            taken_at=now,
            taken_at_original=now,
            last_modified=now,
        )
        for index in range(2)
    ]
    session.add_all(photos)
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()

    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()

    event = Event(criterion_scoring_run_id=run.id, position=1, started_at=now, ended_at=now)
    session.add(event)
    await session.flush()

    for index, photo in enumerate(photos):
        session.add(
            PhotoAlbumSuitability(
                photo_id=photo.id, level=4 - index, provider="test", computed_at=now
            )
        )
        session.add(
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo.id,
                event_id=event.id,
                rank_score=0.8 - index * 0.1,
                rank_position=index + 1,
            )
        )
    await session.flush()

    return _Graph(
        project_id=project.id,
        user_id=user.id,
        photo=photos[0],
        other_photo=photos[1],
        run=run,
        run_id=run.id,
        event_id=event.id,
    )


async def _write_one(session: AsyncSession, graph: _Graph, kind: FeedbackEventKind) -> None:
    """Schreibt GENAU EIN Ereignis der uebergebenen Art ueber den Produktionsweg.

    Die Verzweigung liegt hier und nicht in den Faellen: Sie bildet ab, welche `record_*`-Funktion
    fuer welchen `kind` zustaendig ist, und ein `kind` ohne Zustaendige faellt beim Aufruf auf."""
    context = await load_frozen_context(
        session, project_id=graph.project_id, photo_id=graph.photo.id
    )
    if kind in _ALBUM_DECISION_KINDS:
        await record_album_decision(
            session,
            project_id=graph.project_id,
            photo_id=graph.photo.id,
            user_id=graph.user_id,
            kind=kind,
            context=context,
        )
    elif kind in _MOTIF_KINDS:
        await record_motif_correction(
            session,
            project_id=graph.project_id,
            photo_id=graph.photo.id,
            user_id=graph.user_id,
            kind=kind,
            motif_key="menschen",
            motif_strength=0.42,
            context=context,
        )
    elif kind in _FINAL_KINDS:
        await record_final_decision(
            session,
            project_id=graph.project_id,
            photo_id=graph.photo.id,
            kind=kind,
            context=context,
        )
    else:
        assert kind is FeedbackEventKind.EXCHANGED
        await record_exchange(
            session,
            project_id=graph.project_id,
            user_id=graph.user_id,
            photo_id=graph.photo.id,
            replaced_photo_id=graph.other_photo.id,
            criterion_scoring_run_id=graph.run_id,
            event_id=graph.event_id,
            level=4,
            replaced_level=3,
            quality=0.8,
            replaced_quality=0.7,
        )
    await session.commit()


async def _only_event(session: AsyncSession) -> FeedbackEvent:
    session.expire_all()
    return (await session.execute(select(FeedbackEvent))).scalar_one()


def _populated_fields(event: FeedbackEvent) -> frozenset[str]:
    return frozenset(name for name in _MATRIX_FIELDS if getattr(event, name) is not None)


# --- Invariante 1: die Feldmatrix je `kind` ----------------------------------------------------


@pytest.mark.parametrize("kind", tuple(FeedbackEventKind), ids=lambda kind: kind.value)
async def test_each_kind_populates_exactly_its_own_set_of_fields(
    db_session: AsyncSession, kind: FeedbackEventKind
) -> None:
    """EIN Fall je `kind`, ueber den Produktionsweg geschrieben, Assertion auf den EXAKTEN Satz.

    Die Lage ist so gebaut, dass jedes optionale Feld belegbar WAERE - was hier fehlt, fehlt aus
    fachlichem Grund. Eine Teilmengenpruefung bestuende auch gegen eine Schreibstelle, die jedes
    Feld pauschal durchreicht."""
    graph = await _build_graph(db_session)

    await _write_one(db_session, graph, kind)

    assert _populated_fields(await _only_event(db_session)) == _EXPECTED_FIELDS[kind]


def test_the_matrix_covers_every_kind_of_the_vocabulary() -> None:
    """SELBSTSCHUTZ der Parametrisierung: Ein ergaenzter `kind` ohne Zeile in der Erwartungstabelle
    brachte den Fall oben sonst mit einem `KeyError` zu Fall, statt die Luecke zu benennen."""
    assert set(_EXPECTED_FIELDS) == set(FeedbackEventKind)


# --- Invariante 2: `user_id IS NULL` genau fuer die Endauswahl ---------------------------------


def test_exactly_the_two_final_decision_kinds_carry_no_user() -> None:
    """BEIDE RICHTUNGEN IN EINEM FALL, als Allaussage ueber die Matrix (S9). Die eine Haelfte
    allein - "die Endauswahl traegt keinen Nutzer" - bestuende auch gegen eine Umsetzung, die
    NIRGENDS einen schreibt, und damit gegen den Verlust jeder Zuschreibung."""
    without_user = {kind for kind, fields in _EXPECTED_FIELDS.items() if "user_id" not in fields}
    with_user = {kind for kind, fields in _EXPECTED_FIELDS.items() if "user_id" in fields}

    assert without_user == set(_FINAL_KINDS)
    assert with_user == set(FeedbackEventKind) - set(_FINAL_KINDS)


@pytest.mark.parametrize("kind", _FINAL_KINDS, ids=lambda kind: kind.value)
async def test_a_joint_decision_is_stored_without_a_user_and_with_the_heavier_weight(
    db_session: AsyncSession, kind: FeedbackEventKind
) -> None:
    graph = await _build_graph(db_session)

    await _write_one(db_session, graph, kind)

    stored = await _only_event(db_session)
    assert stored.user_id is None
    assert stored.weight == FINAL_DECISION_WEIGHT


@pytest.mark.parametrize(
    "kind",
    tuple(kind for kind in FeedbackEventKind if kind not in _FINAL_KINDS),
    ids=lambda kind: kind.value,
)
async def test_every_other_kind_is_stored_with_a_user_and_the_plain_weight(
    db_session: AsyncSession, kind: FeedbackEventKind
) -> None:
    graph = await _build_graph(db_session)

    await _write_one(db_session, graph, kind)

    stored = await _only_event(db_session)
    assert stored.user_id == graph.user_id
    assert stored.weight == 1.0


def test_the_joint_decision_weighs_more_than_a_single_correction() -> None:
    """Die Konstante als UNGLEICHUNG, nicht nur als Literal: Ein Wert <= 1 draehte die Aussage
    "die gemeinsame Entscheidung wiegt schwerer" um, ohne einen Verhaltensfall zu roeten."""
    assert FINAL_DECISION_WEIGHT > 1.0
    assert FINAL_DECISION_WEIGHT == 2.0


# --- Die Feldmatrix wird DURCHGESETZT, nicht nur beschrieben ----------------------------------


async def test_a_joint_decision_with_a_user_is_refused_at_the_write_place(
    db_session: AsyncSession,
) -> None:
    """Die Matrix ist an der Schreibstelle GEHALTEN und nicht bloss dokumentiert: Ein Ereignis der
    Endauswahl mit Nutzerbezug fuehrte das in ADR 0099 verworfene `decided_by` durch die
    Hintertuer ein. Es bricht hier LAUT, statt eine Zeile zu hinterlassen, die niemand mehr von
    einer richtigen unterscheidet."""
    graph = await _build_graph(db_session)
    context = await load_frozen_context(
        db_session, project_id=graph.project_id, photo_id=graph.photo.id
    )

    with pytest.raises(ValueError, match="user_id"):
        await record_final_decision(
            db_session,
            project_id=graph.project_id,
            photo_id=graph.photo.id,
            kind=FeedbackEventKind.FINAL_DECISION_IN,
            context=context,
            user_id=graph.user_id,
        )


async def test_a_motif_event_without_a_motif_key_is_refused_at_the_write_place(
    db_session: AsyncSession,
) -> None:
    """Die Gegenrichtung derselben Durchsetzung: ein PFLICHTIGES Feld, das fehlt. Ohne diesen
    Zweig bestuende die Matrix-Pruefung auch gegen eine Schreibstelle, die gar nichts prueft."""
    graph = await _build_graph(db_session)
    context = await load_frozen_context(
        db_session, project_id=graph.project_id, photo_id=graph.photo.id
    )

    with pytest.raises(ValueError, match="motif_key"):
        await record_motif_correction(
            session=db_session,
            project_id=graph.project_id,
            photo_id=graph.photo.id,
            user_id=graph.user_id,
            kind=FeedbackEventKind.MOTIF_ADDED,
            motif_key=None,  # type: ignore[arg-type]
            motif_strength=0.4,
            context=context,
        )


# --- Die eingefrorene Entscheidungslage --------------------------------------------------------


async def test_the_frozen_context_comes_from_the_latest_successful_run(
    db_session: AsyncSession,
) -> None:
    graph = await _build_graph(db_session)

    context = await load_frozen_context(
        db_session, project_id=graph.project_id, photo_id=graph.photo.id
    )

    assert context.criterion_scoring_run_id == graph.run_id
    assert context.event_id == graph.event_id
    assert context.level == 4
    assert context.quality == pytest.approx(0.8)


async def test_a_photo_without_any_model_assessment_still_yields_an_event(
    db_session: AsyncSession,
) -> None:
    """L4: Die eingefrorenen Felder sind nullbar, und ihre Abwesenheit haelt kein Ereignis auf.
    Ohne diesen Fall braeche die Aufzeichnung ausgerechnet fuer die Fotos, ueber die das Modell am
    wenigsten weiss."""
    project = Project(name="Ohne Lauf", opencloud_drive_id="d", opencloud_path="/b")
    user = User(username="bert", password_hash="x")
    db_session.add_all([project, user])
    await db_session.flush()
    now = datetime(2023, 1, 1)
    photo = Photo(
        project_id=project.id,
        relative_path="a.jpg",
        etag="e",
        content_length=1,
        taken_at=now,
        taken_at_original=now,
        last_modified=now,
    )
    db_session.add(photo)
    await db_session.flush()

    context = await load_frozen_context(db_session, project_id=project.id, photo_id=photo.id)
    await record_album_decision(
        db_session,
        project_id=project.id,
        photo_id=photo.id,
        user_id=user.id,
        kind=FeedbackEventKind.PHOTO_REMOVED,
        context=context,
    )
    await db_session.commit()

    stored = await _only_event(db_session)
    assert _populated_fields(stored) == {"project_id", "photo_id", "weight", "user_id"}


async def test_an_unfinished_run_is_not_the_frozen_context(db_session: AsyncSession) -> None:
    """Das Praedikat ist der JUENGSTE ERFOLGREICHE Lauf. Ein gerade laufender traegt noch keine
    vollstaendige Rangfolge - seine `event_id` einzufrieren hiesse, die Gegenueberstellung an eine
    Gliederung zu binden, die es so nie gab."""
    graph = await _build_graph(db_session)
    running = CriterionScoringRun(
        project_id=graph.project_id,
        scoring_run_id=graph.run.scoring_run_id,
        status=ScanStatus.RUNNING,
        started_at=datetime(2030, 1, 1),
    )
    db_session.add(running)
    await db_session.flush()

    context = await load_frozen_context(
        db_session, project_id=graph.project_id, photo_id=graph.photo.id
    )

    assert context.criterion_scoring_run_id == graph.run_id


# --- L4, zweiter Satz: die eingefrorenen Zahlen ueberleben die Neuklassifikation ---------------


async def test_the_frozen_numbers_stay_untouched_when_the_photo_is_reclassified(
    db_session: AsyncSession,
) -> None:
    """L4, zweiter Satz - und DER NACHWEIS IST DER EINGEFRORENE WERT, nicht das Vorhandensein der
    Zeile.

    Ein spaeterer Lauf ueberschreibt Modellstufe, Qualitaetswert und Motivstaerke an ihren
    Quellzeilen. Traegt das Ereignis die Zahlen nicht selbst, waere danach nicht mehr
    entscheidbar, ob das Modell ein Motiv ZU SCHWACH oder GAR NICHT genannt hatte - die Aussage
    des Ereignisses haengt dann am heutigen Stand, und genau das schliesst ADR 0100 Punkt 2 aus.

    OHNE DIESEN FALL bestuende die Zusage auch gegen eine Umsetzung, die zur AUSWERTUNGSZEIT
    nachschlaegt statt einzufrieren: Solange sich die Quellzeilen nicht bewegen, liefern beide
    Wege dieselben Zahlen. Hier bewegen sie sich - und zwar ALLE DREI in einem Fall, weil sie in
    drei verschiedenen Tabellen stehen und eine davon einzeln vergessen zu werden droht."""
    graph = await _build_graph(db_session)
    photo_id = graph.photo.id
    frozen_strength = 0.2
    db_session.add(
        PhotoMotifAssessment(
            photo_id=photo_id,
            source=MotifAssessmentSource.CLOUD,
            excluded_document=False,
            provider="test",
            computed_at=datetime(2026, 1, 1),
        )
    )
    await db_session.flush()
    db_session.add(
        PhotoMotifStrength(photo_id=photo_id, motif_key="menschen", strength=frozen_strength)
    )
    await db_session.flush()

    context = await load_frozen_context(db_session, project_id=graph.project_id, photo_id=photo_id)
    await record_motif_correction(
        db_session,
        project_id=graph.project_id,
        photo_id=photo_id,
        user_id=graph.user_id,
        kind=FeedbackEventKind.MOTIF_ADDED,
        motif_key="menschen",
        motif_strength=frozen_strength,
        context=context,
    )
    await db_session.commit()
    assert (context.level, context.quality) == (4, pytest.approx(0.8))

    # DIE NEUKLASSIFIKATION: Alle drei Quellzeilen bekommen einen anderen Wert - dasselbe, was ein
    # spaeterer Lauf tut. Alle drei in EINEM Fall, weil sie in drei verschiedenen Tabellen stehen.
    await db_session.execute(
        update(PhotoAlbumSuitability)
        .where(PhotoAlbumSuitability.photo_id == photo_id)
        .values(level=1)
    )
    await db_session.execute(
        update(PhotoRanking)
        .where(
            PhotoRanking.criterion_scoring_run_id == graph.run_id,
            PhotoRanking.photo_id == photo_id,
        )
        .values(rank_score=0.05)
    )
    await db_session.execute(
        update(PhotoMotifStrength)
        .where(
            PhotoMotifStrength.photo_id == photo_id,
            PhotoMotifStrength.motif_key == "menschen",
        )
        .values(strength=0.97)
    )
    await db_session.commit()

    stored = await _only_event(db_session)
    assert stored.motif_strength == pytest.approx(frozen_strength)
    assert stored.level == 4
    assert stored.quality == pytest.approx(0.8)
    # Die Gegenprobe im SELBEN Fall: Die Quellzeilen tragen tatsaechlich die NEUEN Werte - sonst
    # bestuende der Fall auch gegen eine Neuklassifikation, die gar nicht stattgefunden hat.
    assert (
        await db_session.execute(
            select(PhotoAlbumSuitability.level).where(PhotoAlbumSuitability.photo_id == photo_id)
        )
    ).scalar_one() == 1
    assert (
        await db_session.execute(
            select(PhotoRanking.rank_score).where(
                PhotoRanking.criterion_scoring_run_id == graph.run_id,
                PhotoRanking.photo_id == photo_id,
            )
        )
    ).scalar_one() == pytest.approx(0.05)
    assert (
        await db_session.execute(
            select(PhotoMotifStrength.strength).where(
                PhotoMotifStrength.photo_id == photo_id,
                PhotoMotifStrength.motif_key == "menschen",
            )
        )
    ).scalar_one() == pytest.approx(0.97)


# --- Nachweis 4: `event_id` ueberlebt den Neuaufbau der Gliederung -----------------------------


async def test_every_event_survives_a_rebuild_of_the_run_grouping(
    db_session: AsyncSession,
) -> None:
    """VIERTER der vier Nachweise, und der einzige VERHALTENS-Nachweis: `rebuild_run_grouping`
    loescht die `events`-Zeilen des Laufs und legt sie neu an. Mit einem echten Fremdschluessel
    auf `events.id` risse dieser Aufruf entweder die Log-Zeilen mit oder bliebe an der Verletzung
    haengen - beides braeche die Append-only-Zusage, auf der jede Zahl der Diagnose ruht.

    Geprueft wird der VOLLSTAENDIGE Zeileninhalt vorher und nachher, nicht nur die Zeilenzahl: Ein
    auf `NULL` gesetztes `event_id` liesse die Zahl unveraendert und naehme der Ableitung
    trotzdem jede Gruppierung."""
    graph = await _build_graph(db_session)
    await _write_one(db_session, graph, FeedbackEventKind.PHOTO_REMOVED)
    before = [
        {name: getattr(row, name) for name in _MATRIX_FIELDS}
        for row in (await db_session.execute(select(FeedbackEvent).order_by(FeedbackEvent.id)))
        .scalars()
        .all()
    ]
    assert before and before[0]["event_id"] is not None

    await rebuild_run_grouping(db_session, graph.project_id)
    await db_session.commit()

    db_session.expire_all()
    after = [
        {name: getattr(row, name) for name in _MATRIX_FIELDS}
        for row in (await db_session.execute(select(FeedbackEvent).order_by(FeedbackEvent.id)))
        .scalars()
        .all()
    ]
    assert after == before
