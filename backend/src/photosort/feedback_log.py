"""DIE EINE Schreibstelle des Ereignis-Logs der Nacharbeit (ADR 0100, Spec 0432).

Jedes `FeedbackEvent` dieses Projekts entsteht hier. Das ist keine Bequemlichkeit, sondern der
Ort, an dem die FELDMATRIX JE `kind` gehalten wird: welches Feld eine Art pflichtig traegt und
welches ihr verboten ist. Neun `CheckConstraint`s statt dessen waeren neun Orte, die auseinander
laufen, und die Matrix trifft ohnehin Aussagen, die eine Datenbank nicht kennt (`user_id` ist
genau fuer die gemeinsame Entscheidung `NULL`, sonst nie).

Eine Verletzung bricht LAUT (`ValueError`), statt eine Zeile zu hinterlassen, die niemand mehr
von einer richtigen unterscheidet: Das Log ist append-only, eine falsch geschriebene Zeile bleibt
also fuer immer, und die Diagnose zaehlt sie mit.

WEDER `commit` NOCH `flush`: Die Transaktionsgrenze gehoert dem Aufrufer. Ein Ereignis gehoert in
dieselbe Transaktion wie der Schreibvorgang, den es beschreibt - insbesondere beim Austausch, der
zwei Bewertungszeilen und ein Ereignis atomar schreibt (S5).

Dieses Modul liest und schreibt, hat also eine Session - die reine, DB-freie Auswertung des Logs
lebt getrennt davon (Muster `quality.py`/`selection.py`/`album_selection.py`).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    FeedbackEvent,
    FeedbackEventKind,
    PhotoAlbumSuitability,
    PhotoRanking,
    ScanStatus,
)

# Das Gewicht eines Ereignisses aus der GEMEINSAMEN Endauswahl (ADR 0100 Punkt 5). Es ist der
# Multiplikator dieses Ereignisses in der Ableitung, nie in der Anzeige: Die ausgewiesene Fallzahl
# bleibt die ungewichtete Anzahl der Korrekturen.
#
# STRIKT GROESSER ALS 1, und das ist die eigentliche Aussage: Eine gemeinsame Entscheidung ist das
# Urteil beider Personen vor einem Geraet, ein Einzelhandgriff das einer. Bei einem Wert <= 1
# waere die Aussage stillschweigend umgedreht oder aufgehoben, ohne dass ein Verhaltensfall
# darueber rot wuerde.
#
# Der Betrag selbst ist ein dokumentiert UNKALIBRIERTER Startwert in der Klasse von
# `LOCAL_CORRECTION_SPAN` - er stammt aus keiner Messung.
FINAL_DECISION_WEIGHT = 2.0

# Die Felder, die die Matrix unterscheidet. `project_id`, `photo_id`, `kind` und `weight` stehen
# nicht darin: Sie traegt jede Art, ausnahmslos. Die eingefrorenen Zahlen `level`/`quality` und
# der Laufbezug ebenfalls nicht - sie sind bei jeder Art erlaubt und bei keiner pflichtig, weil
# ein Foto ohne Modellbewertung trotzdem ein Ereignis erzeugt (L4).
_REQUIRED_FIELDS: dict[FeedbackEventKind, frozenset[str]] = {
    FeedbackEventKind.PHOTO_INCLUDED: frozenset({"user_id"}),
    FeedbackEventKind.PHOTO_REMOVED: frozenset({"user_id"}),
    FeedbackEventKind.DECISION_WITHDRAWN: frozenset({"user_id"}),
    FeedbackEventKind.EXCHANGED: frozenset({"user_id", "replaced_photo_id"}),
    FeedbackEventKind.MOTIF_ADDED: frozenset({"user_id", "motif_key"}),
    FeedbackEventKind.MOTIF_DROPPED: frozenset({"user_id", "motif_key"}),
    FeedbackEventKind.MOTIF_CORRECTION_WITHDRAWN: frozenset({"user_id", "motif_key"}),
    # KEIN `user_id` (S9): Die gemeinsame Entscheidung gehoert dem Projekt. Ihr Schreibendpunkt
    # nimmt aus genau diesem Grund kein `current_user` entgegen.
    FeedbackEventKind.FINAL_DECISION_IN: frozenset(),
    FeedbackEventKind.FINAL_DECISION_OUT: frozenset(),
}

_PAIR_FIELDS = frozenset({"replaced_photo_id", "replaced_level", "replaced_quality"})
_MOTIF_FIELDS = frozenset({"motif_key", "motif_strength"})

_FORBIDDEN_FIELDS: dict[FeedbackEventKind, frozenset[str]] = {
    FeedbackEventKind.PHOTO_INCLUDED: _PAIR_FIELDS | _MOTIF_FIELDS,
    FeedbackEventKind.PHOTO_REMOVED: _PAIR_FIELDS | _MOTIF_FIELDS,
    FeedbackEventKind.DECISION_WITHDRAWN: _PAIR_FIELDS | _MOTIF_FIELDS,
    # Der Austausch ist die einzige Art mit einem PAAR in einer Zeile - "B statt A" ist die
    # Aussage, die beiden Bilder fuer sich tragen sie nicht.
    FeedbackEventKind.EXCHANGED: _MOTIF_FIELDS,
    FeedbackEventKind.MOTIF_ADDED: _PAIR_FIELDS,
    FeedbackEventKind.MOTIF_DROPPED: _PAIR_FIELDS,
    FeedbackEventKind.MOTIF_CORRECTION_WITHDRAWN: _PAIR_FIELDS,
    FeedbackEventKind.FINAL_DECISION_IN: _PAIR_FIELDS | _MOTIF_FIELDS | frozenset({"user_id"}),
    FeedbackEventKind.FINAL_DECISION_OUT: _PAIR_FIELDS | _MOTIF_FIELDS | frozenset({"user_id"}),
}


@dataclass(frozen=True)
class FrozenContext:
    """Die EINGEFRORENE Entscheidungslage eines Fotos zum Zeitpunkt der Korrektur.

    Alle vier Werte sind nullbar und bedeuten dasselbe: "lag damals nicht vor". Ein Foto ohne
    Modellbewertung, ein Projekt ohne erfolgreichen Lauf - beides erzeugt trotzdem ein Ereignis
    (L4), es bildet in der Ableitung nur kein Paar.

    `frozen`, weil die Werte aus EINER Erhebung in die geschriebene Zeile gehen: Eine Zuweisung
    daran waere eine zweite, spaetere Momentaufnahme in derselben Zeile."""

    criterion_scoring_run_id: int | None = None
    event_id: int | None = None
    level: int | None = None
    quality: float | None = None


async def _latest_successful_criterion_scoring_run_id(
    session: AsyncSession, project_id: int
) -> int | None:
    """Bewusst identisch zu `api/photos.py::_latest_successful_criterion_scoring_run_id` (dort
    steht die ausfuehrliche Begruendung des Praedikats). Eine Import-Beziehung von diesem Modul
    in die API-Schicht liefe der Abhaengigkeitsrichtung entgegen."""
    return (
        await session.execute(
            select(CriterionScoringRun.id)
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def load_frozen_context(
    session: AsyncSession, *, project_id: int, photo_id: int
) -> FrozenContext:
    """Erhebt die Entscheidungslage, die das Ereignis mitschreibt.

    EINGEFROREN wird, was ein spaeterer Lauf UEBERSCHREIBT: die Modellstufe
    (`PhotoAlbumSuitability.level`) und der Qualitaetswert (`PhotoRanking.rank_score` des damals
    juengsten erfolgreichen Laufs). Ohne das Einfrieren haenge die Aussage des Ereignisses am
    heutigen Stand - und genau das schliesst die Story aus.

    Die lokalen Kriterienwerte werden hier ausdruecklich NICHT gelesen: Sie sind eine
    deterministische Messung an denselben Pixeln und werden zur Auswertungszeit gejoint.

    IDS STATT EINES `Photo`-OBJEKTS, und das ist kein Geschmack: Die Aufrufer stehen hinter einem
    `flush`, der in einen `rollback` laufen kann (der `409`-Zweig der Bewertungs- und der
    Entscheidungsschreibstelle). Ein danach angefasstes ORM-Objekt ist expired, und der
    Nachladeversuch bricht unter `asyncio` mit `MissingGreenlet` ab - in einem Zweig, der
    ausgerechnet den Wettlauf-Fall behandelt."""
    run_id = await _latest_successful_criterion_scoring_run_id(session, project_id)
    event_id: int | None = None
    quality: float | None = None
    if run_id is not None:
        ranking = (
            await session.execute(
                select(PhotoRanking.event_id, PhotoRanking.rank_score).where(
                    PhotoRanking.criterion_scoring_run_id == run_id,
                    PhotoRanking.photo_id == photo_id,
                )
            )
        ).one_or_none()
        if ranking is not None:
            event_id, quality = ranking
        else:
            # Das Foto stand in keiner Rangzeile dieses Laufs. Dann traegt das Ereignis auch
            # KEINEN Laufbezug: Ein `criterion_scoring_run_id` ohne `event_id` verspraeche eine
            # Gruppierung, die es fuer dieses Foto nicht gibt.
            run_id = None
    level = (
        await session.execute(
            select(PhotoAlbumSuitability.level).where(PhotoAlbumSuitability.photo_id == photo_id)
        )
    ).scalar_one_or_none()
    return FrozenContext(
        criterion_scoring_run_id=run_id, event_id=event_id, level=level, quality=quality
    )


def _append(
    session: AsyncSession,
    *,
    kind: FeedbackEventKind,
    project_id: int,
    photo_id: int,
    user_id: int | None = None,
    weight: float = 1.0,
    criterion_scoring_run_id: int | None = None,
    event_id: int | None = None,
    replaced_photo_id: int | None = None,
    motif_key: str | None = None,
    motif_strength: float | None = None,
    level: int | None = None,
    replaced_level: int | None = None,
    quality: float | None = None,
    replaced_quality: float | None = None,
) -> FeedbackEvent:
    """Legt die Zeile an - der einzige Ort im Anwendungscode, an dem `FeedbackEvent(...)` steht.

    HIER wird die Feldmatrix durchgesetzt, in beide Richtungen: ein pflichtiges Feld, das fehlt,
    und ein verbotenes, das belegt ist, brechen beide mit `ValueError`. Ohne die zweite Richtung
    ginge ausgerechnet die Zusage verloren, die keine Datenbank kennt - dass die gemeinsame
    Entscheidung KEINEN Nutzer traegt."""
    values = {
        "user_id": user_id,
        "replaced_photo_id": replaced_photo_id,
        "replaced_level": replaced_level,
        "replaced_quality": replaced_quality,
        "motif_key": motif_key,
        "motif_strength": motif_strength,
    }
    missing = sorted(name for name in _REQUIRED_FIELDS[kind] if values.get(name, "gesetzt") is None)
    if missing:
        raise ValueError(f"{kind.value}: pflichtige Felder fehlen: {', '.join(missing)}")
    present = sorted(name for name in _FORBIDDEN_FIELDS[kind] if values.get(name) is not None)
    if present:
        raise ValueError(f"{kind.value}: verbotene Felder belegt: {', '.join(present)}")

    event = FeedbackEvent(
        project_id=project_id,
        photo_id=photo_id,
        kind=kind,
        user_id=user_id,
        weight=weight,
        criterion_scoring_run_id=criterion_scoring_run_id,
        event_id=event_id,
        replaced_photo_id=replaced_photo_id,
        motif_key=motif_key,
        motif_strength=motif_strength,
        level=level,
        replaced_level=replaced_level,
        quality=quality,
        replaced_quality=replaced_quality,
    )
    session.add(event)
    return event


async def record_album_decision(
    session: AsyncSession,
    *,
    project_id: int,
    photo_id: int,
    user_id: int,
    kind: FeedbackEventKind,
    context: FrozenContext,
) -> FeedbackEvent:
    """Ein Handgriff am EIGENEN Album-Entwurf: aufgenommen, gestrichen, oder zurueckgenommen.

    Der Aufrufer ruft NUR bei tatsaechlichem Statuswechsel hierher (ADR 0100 Punkt 4); das
    Praedikat dafuer ist `api/ratings.py::album_decision_kind`."""
    return _append(
        session,
        kind=kind,
        project_id=project_id,
        photo_id=photo_id,
        user_id=user_id,
        criterion_scoring_run_id=context.criterion_scoring_run_id,
        event_id=context.event_id,
        level=context.level,
        quality=context.quality,
    )


async def record_motif_correction(
    session: AsyncSession,
    *,
    project_id: int,
    photo_id: int,
    user_id: int,
    kind: FeedbackEventKind,
    motif_key: str,
    motif_strength: float | None,
    context: FrozenContext,
) -> FeedbackEvent:
    """Eine Motivkorrektur. `motif_strength` ist die eingefrorene GESPEICHERTE Modellstaerke, nie
    die wirksame aus `motif_strengths.py::effective_strength_expression` - Letztere traegt bereits
    eine fruehere Korrektur desselben Paares, und die zweite Korrektur eines Motivs zeigte dann
    nie einen Modellfehler an.

    `motif_key` stammt vom Aufrufer IMMER hinter der Pruefung gegen das geschlossene Motivset
    (S11), nie aus dem rohen Pfadparameter davor."""
    return _append(
        session,
        kind=kind,
        project_id=project_id,
        photo_id=photo_id,
        user_id=user_id,
        motif_key=motif_key,
        motif_strength=motif_strength,
        criterion_scoring_run_id=context.criterion_scoring_run_id,
        event_id=context.event_id,
        level=context.level,
        quality=context.quality,
    )


async def record_final_decision(
    session: AsyncSession,
    *,
    project_id: int,
    photo_id: int,
    kind: FeedbackEventKind,
    context: FrozenContext,
    user_id: int | None = None,
) -> FeedbackEvent:
    """Eine Entscheidung der GEMEINSAMEN Endauswahl - ohne Nutzer und mit dem hoeheren Gewicht.

    `user_id` steht hier als Parameter mit Vorgabewert `None` und wird von keiner Aufrufstelle
    belegt: Es ist der Angriffspunkt, an dem sich die Matrix pruefen laesst (ein belegter Wert
    bricht laut), statt dass die Zusage nur behauptet waere."""
    return _append(
        session,
        kind=kind,
        project_id=project_id,
        photo_id=photo_id,
        user_id=user_id,
        weight=FINAL_DECISION_WEIGHT,
        criterion_scoring_run_id=context.criterion_scoring_run_id,
        event_id=context.event_id,
        level=context.level,
        quality=context.quality,
    )


async def record_exchange(
    session: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    photo_id: int,
    replaced_photo_id: int,
    criterion_scoring_run_id: int,
    event_id: int,
    level: int | None,
    replaced_level: int | None,
    quality: float | None,
    replaced_quality: float | None,
) -> FeedbackEvent:
    """ "B statt A" als EIN Ereignis mit beiden Foto-Verweisen.

    Anders als die uebrigen `record_*` nimmt diese Funktion keinen `FrozenContext` entgegen,
    sondern die Werte einzeln: Der Austausch-Endpunkt hat die beiden Rangzeilen bereits gelesen -
    sie sind seine Projekt- und Event-Bindung (S2/S3) -, und ein zweiter Lesegang daneben koennte
    eine andere Lage sehen als die, gegen die gerade geprueft wurde.

    `criterion_scoring_run_id` und `event_id` sind hier PFLICHTIG und nicht nullbar: Ohne Lauf und
    ohne gemeinsames Event gibt es keinen Austausch, der Endpunkt weist ihn vorher ab."""
    return _append(
        session,
        kind=FeedbackEventKind.EXCHANGED,
        project_id=project_id,
        photo_id=photo_id,
        user_id=user_id,
        replaced_photo_id=replaced_photo_id,
        criterion_scoring_run_id=criterion_scoring_run_id,
        event_id=event_id,
        level=level,
        replaced_level=replaced_level,
        quality=quality,
        replaced_quality=replaced_quality,
    )
