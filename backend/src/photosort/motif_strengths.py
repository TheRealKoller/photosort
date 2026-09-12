"""Der DB-nahe Teil des Motivsets: die wirksame Staerke und der Schreibpfad der Kopfzeile.

Bewusst getrennt vom reinen `motifs.py`: dort steht das Vokabular (Registry, Schluesselpruefung,
lokale Signalabbildung, Anzeigebaender), hier alles, was eine Session, ein Modell oder einen
SQL-Ausdruck braucht.

DIE EINE STELLE fuer die wirksame Staerke: `effective_strength_expression()` ist der einzige Ort
im Repository, an dem die Korrekturspalte in einen Wert eingeht. Jeder lesende Pfad - Fotoliste,
Einzelbildansicht, Statistik-Aggregation - bezieht ihn von hier. Eine zweite Fassung desselben
`CASE` liefe beim naechsten Grenzfall auseinander, ohne dass ein Test daran bricht; ein
struktureller Waechter in tests/test_motif_strengths.py haelt deshalb fest, dass keine entsteht.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Float, case, cast, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from photosort.models import (
    MotifAssessmentSource,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
)


@dataclass(frozen=True)
class EffectiveStrength:
    """Die wirksame Staerke eines Motivs an einem Foto samt der Auskunft, WORAUS sie entstanden
    ist.

    `correction` ist `None` ohne Korrekturzeile, sonst die Aussage des Nutzers. Beides zusammen,
    weil die Oberflaeche eine korrigierte Zeile anders darstellt als eine gleich hohe
    Modellaussage: statt der Prozentzahl steht dort das Korrekturwort. Ohne `correction` muesste
    sie aus einer 1.0 bzw. 0.0 raten, und eine Modellaussage von genau 1.0 waere von einer
    Korrektur nicht zu unterscheiden."""

    strength: float
    correction: bool | None


def effective_strength_expression() -> ColumnElement[float]:
    """Der EINE `CASE` ueber Staerke und Korrektur.

    `applies=true` ergibt `1.0`, `applies=false` ergibt `0.0`, keine Korrekturzeile ergibt die
    Staerke der Grundlage. Die Korrektur traegt nie eine Zahl und wird nie in die Staerkezeile
    materialisiert - eine materialisierte Korrektur muesste nach jedem Lauf erneut angewendet
    werden, und genau dieses Nachziehen ist die Stelle, an der sie verloren geht.

    Geschrieben als SQL-Ausdruck und nicht in Python, damit die Statistik-Aggregation ueber der
    WIRKSAMEN Staerke rechnen kann, ohne alle Zeilen zu laden. Die Bedingung prueft `is_(True)`/
    `is_(False)` statt der Wahrheitswertigkeit: `NULL` (kein Verbund-Treffer des LEFT JOIN) faellt
    damit in den `else`-Zweig und nicht in den `false`-Zweig, und ein nicht korrigiertes Motiv
    behaelt seine Modellaussage.

    Vorausgesetzt wird, dass die Abfrage `PhotoMotifStrength` und `PhotoMotifCorrection` ueber
    `(photo_id, motif_key)` als LEFT JOIN verbindet - siehe `_strength_query()`."""
    return case(
        (PhotoMotifCorrection.applies.is_(True), 1.0),
        (PhotoMotifCorrection.applies.is_(False), 0.0),
        # Der Cast haelt den Ergebnistyp des Ausdrucks auf Fliesskomma fest, auch wenn beide
        # Literale oben ganzzahlig aussehen.
        else_=cast(PhotoMotifStrength.strength, Float),
    )


def _strength_query() -> object:
    """Die Staerkezeilen samt ihrer etwaigen Korrektur - ein LEFT JOIN ueber
    `(photo_id, motif_key)`.

    Der Verbund laeuft ueber BEIDE Spalten. Allein ueber `motif_key` liefe die Korrektur eines
    Fotos in die Staerken aller anderen."""
    return (
        select(
            PhotoMotifStrength.photo_id,
            PhotoMotifStrength.motif_key,
            effective_strength_expression().label("effective_strength"),
            PhotoMotifCorrection.applies,
        )
        .outerjoin(
            PhotoMotifCorrection,
            (PhotoMotifCorrection.photo_id == PhotoMotifStrength.photo_id)
            & (PhotoMotifCorrection.motif_key == PhotoMotifStrength.motif_key),
        )
        .order_by(PhotoMotifStrength.photo_id, PhotoMotifStrength.id)
    )


async def load_effective_strengths(
    session: AsyncSession, photo_ids: Iterable[int]
) -> dict[int, dict[str, EffectiveStrength]]:
    """Die wirksamen Staerken der uebergebenen Fotos, je Foto eine Abbildung
    `motif_key -> EffectiveStrength`.

    Ein Foto OHNE Kopfzeile fehlt im Ergebnis vollstaendig - die Abwesenheit der Kopfzeile ist der
    Zustand "noch nicht klassifiziert", und acht Nullen waeren davon nicht zu unterscheiden. Eine
    Korrektur auf einem solchen Foto ist gespeichert und wirkt, sobald der erste
    Klassifizierungslauf Staerkezeilen anlegt; bis dahin liefert diese Funktion fuer das Foto
    nichts.

    Eine leere Id-Liste fragt die Datenbank gar nicht."""
    ids = list(photo_ids)
    if not ids:
        return {}
    rows = (
        await session.execute(
            _strength_query().where(PhotoMotifStrength.photo_id.in_(ids))  # type: ignore[attr-defined]
        )
    ).all()
    result: dict[int, dict[str, EffectiveStrength]] = {}
    for photo_id, motif_key, effective, applies in rows:
        result.setdefault(photo_id, {})[motif_key] = EffectiveStrength(
            strength=float(effective), correction=applies
        )
    return result


async def upsert_assessment(
    session: AsyncSession,
    photo_id: int,
    *,
    source: MotifAssessmentSource,
    strengths: Mapping[str, float],
    excluded_document: bool,
    provider: str | None,
    computed_at: datetime,
) -> bool:
    """Schreibt bzw. ersetzt Kopfzeile und Staerkevektor eines Fotos. Rueckgabe: ob geschrieben
    wurde.

    DIE REGEL, die beide Grundlagen auseinanderhaelt: eine LOKALE Grundlage schreibt nur, wenn
    fuer das Foto keine Zeile existiert ODER die vorhandene `source='local'` traegt. Eine
    Cloud-Grundlage schreibt immer. Liegt eine Cloud-Aussage vor, bleibt sie also unberuehrt -
    Herkunft, Anbieter, Zeitstempel, Ausschluss-Flag und alle acht Werte. Die Reihenfolge im
    verketteten Lauf (Cloud-Teilschritt vor Kriterien-Bewertung, ADR 0068) macht das ohne
    Zusatzzustand richtig.

    Der GESAMTE Vektor wird ersetzt, nicht zeilenweise gemischt: ein halb gefuellter
    Zwischenzustand aus zwei Grundlagen gibt es nicht. Die Korrekturzeilen bleiben dabei
    unangetastet - sie haengen am Foto und nicht an der Kopfzeile.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer (Muster
    `project_deletion`/`_build_grouping_and_rankings`)."""
    existing = await session.get(PhotoMotifAssessment, photo_id)
    if (
        existing is not None
        and source == MotifAssessmentSource.LOCAL
        and existing.source != MotifAssessmentSource.LOCAL
    ):
        return False

    if existing is None:
        existing = PhotoMotifAssessment(
            photo_id=photo_id,
            source=source,
            excluded_document=excluded_document,
            provider=provider,
            computed_at=computed_at,
        )
        session.add(existing)
    else:
        existing.source = source
        existing.excluded_document = excluded_document
        existing.provider = provider
        existing.computed_at = computed_at
        # Die Staerkezeilen der vorherigen Grundlage fallen VOLLSTAENDIG, nicht zeilenweise
        # ueberschrieben: ein Motiv, das die neue Grundlage nicht nennt, darf nicht mit seinem
        # alten Wert stehen bleiben.
        await session.execute(
            delete(PhotoMotifStrength).where(PhotoMotifStrength.photo_id == photo_id)
        )
    # Das `flush` vor den Staerkezeilen: ihr Fremdschluessel zeigt auf die Kopfzeile, und unter
    # echtem Postgres muss die vor ihnen stehen.
    await session.flush()

    session.add_all(
        [
            PhotoMotifStrength(photo_id=photo_id, motif_key=motif_key, strength=strength)
            for motif_key, strength in strengths.items()
        ]
    )
    return True
