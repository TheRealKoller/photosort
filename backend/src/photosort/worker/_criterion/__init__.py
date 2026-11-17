"""Die gemeinsame Basis der Kriterien-Phasen: der Run-Kontext, den der Orchestrator einmal baut,
und die Schreib-/Loeschhilfe fuer Kriterienzeilen, die mehrere Phasen benutzen.

Warum ein eigenes Modul und keine Funktion in `_criterion/local.py`: `landmark.py` schreibt
ebenfalls `landmark`-Zeilen, und eine Phase darf keine andere Phase importieren (§ "keine Kante
zwischen zwei Phasen"). Die Basis hier haengt nur an `_runs` und an den Modellen.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCriterionScore,
    PhotoScore,
)


@dataclass(frozen=True)
class CriterionRunContext:
    """Der einmal gebaute Run-Kontext eines Kriterien-Laufs.

    Die drei Dictionaries sind die reine In-Memory-Grundlage der spaeteren Phasen und werden
    ABSICHTLICH nur hier gehalten, nie persistiert: `candidate_values` ist die Eingabe von
    `rank_photos` (kein erneutes DB-Read noetig), `area_fractions_by_photo_id` ist die Eingabe der
    lokalen Motiv-Kopfzeile (ein spaeterer Neuaufbau der Gliederung hat sie deshalb nicht und
    schreibt auch keine Kopfzelle), und `existing_criterion_scores` ist der Cache, der eine
    vorhandene Zeile aktualisiert statt eine zweite anzulegen.

    `frozen=True` betrifft nur die Felder: die Dictionaries selbst werden waehrend des Laufs
    gefuellt, das ist ihr Zweck."""

    session: AsyncSession
    run: CriterionScoringRun
    project_id: int
    cache_dir: Path
    now: datetime
    rows: Sequence[Row[tuple[Photo, PhotoScore]]]
    candidate_values: dict[int, dict[str, float]]
    area_fractions_by_photo_id: dict[int, dict[str, float]]
    existing_criterion_scores: dict[tuple[int, str], PhotoCriterionScore]


def upsert_criterion(
    context: CriterionRunContext,
    photo_id: int,
    criterion_key: str,
    value: float,
    source: CriterionSource,
) -> None:
    """Legt die Zeile eines Kriteriums an oder aktualisiert sie - die EINE Schreibstelle beider
    Kriterien-Phasen, mit demselben In-Memory-Cache als Gegenprobe."""
    existing = context.existing_criterion_scores.get((photo_id, criterion_key))
    if existing is None:
        existing = PhotoCriterionScore(photo_id=photo_id, criterion_key=criterion_key)
        context.session.add(existing)
        context.existing_criterion_scores[(photo_id, criterion_key)] = existing
    existing.value = value
    existing.source = source
    existing.computed_at = context.now


async def delete_criterion(context: CriterionRunContext, photo_id: int, criterion_key: str) -> None:
    """Loescht die Zeile eines NICHT MESSBAREN Kriteriums - ausschliesslich fuer
    `ContentCriteria.not_measurable`, nie fuer ein mangels Detektor oder wegen einer Ausnahme
    unberechnetes.

    Ohne dieses Loeschen liefe die Entscheidung "ein nicht messbares Kriterium wird weggelassen"
    fuer den BESTAND ins Leere: `upsert_criterion` loescht nie, und die Altzeile mit ihrem alten
    `0.0` bliebe wirksam.

    Der In-Memory-Cache wird MITgeraeumt: bliebe das ORM-Objekt darin stehen, belebte ein spaeteres
    `upsert_criterion` im selben Lauf eine geloeschte Zeile wieder, und der naechste Lauf faende
    einen Eintrag vor, den es in der Datenbank nicht mehr gibt."""
    existing = context.existing_criterion_scores.pop((photo_id, criterion_key), None)
    if existing is not None:
        await context.session.delete(existing)
