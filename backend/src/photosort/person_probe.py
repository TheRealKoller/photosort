"""REIN LESENDES Messkommando der Personen-Erkennung (S12).

Aufruf::

    docker compose exec -T backend python -m photosort.person_probe --project-id 3

Gezaehlt wird aus der KORREKTURSPUR gegen die ROHE Erkennung, nie gegen die wirksame Zuordnung:
Eine Erkennung mit `applies=false` ist ein Fehlgriff, und die wirksame Zuordnung saehe ihn nie,
weil die Korrektur ihn gerade verdeckt. Je Person (als "Person 1/2" nach Slot):

* erkannt - Erkennungszeilen des Projekts;
* richtig - erkannt und nicht von Hand entfernt;
* falsch - erkannt UND `applies=false`;
* ergaenzt - `applies=true` ohne Erkennung (uebersehen);
* entfernt, nicht mehr erkannt - `applies=false` ohne Erkennung;
* Quote = richtig / (richtig + ergaenzt). Sie ist eine OBERGRENZE der Erkennungsquote: Uebersehene
  Fotos, die niemand ergaenzt hat, fehlen im Nenner. Ohne Nenner steht "nicht bestimmbar".

Kein Modell, kein `cv2`, kein Schreibzugriff, kein Log; Ausgabe nur auf stdout, nur Anzahlen, kein
Name, kein Pfad, keine Zeile je Foto und kein Schalter, der Namen ergaenzt - die Ausgabe geht in
einen oeffentlichen Pull Request. Kein automatischer Pfad erreicht das Kommando (kein Import aus
`main.py`/`worker.py`, kein Endpunkt, kein Compose-`command`); `tests/test_person_probe.py` haelt
das fest. Ein Datenbankfehler nennt nur seinen Typ, nie die `DATABASE_URL`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.config import settings
from photosort.db import make_engine, make_session_factory
from photosort.models import Person, Photo, PhotoPersonCorrection, PhotoPersonDetection, Project

NOT_DETERMINABLE = "nicht bestimmbar"

Pair = tuple[int, int]


class PersonProbeError(Exception):
    """Der Messlauf kann nicht stattfinden - die Meldung nennt nur Bedingung und Id."""


@dataclass(frozen=True)
class PersonCounts:
    label: str
    recognised: int
    correct: int
    wrong: int
    added: int
    removed_not_recognised: int

    @property
    def rate(self) -> float | None:
        denominator = self.correct + self.added
        return None if denominator == 0 else self.correct / denominator


def count_trail(
    person_ids_by_slot: Sequence[int],
    detections: Iterable[Pair],
    corrections: Mapping[Pair, bool],
) -> tuple[PersonCounts, ...]:
    """Rein: je Person die fuenf Zahlen aus roher Erkennung gegen Korrektur."""
    detected = set(detections)
    result: list[PersonCounts] = []
    for position, person_id in enumerate(person_ids_by_slot, start=1):
        mine = {pair for pair in detected if pair[1] == person_id}
        wrong = sum(1 for pair in mine if corrections.get(pair) is False)
        added = sum(
            1
            for pair, applies in corrections.items()
            if pair[1] == person_id and applies and pair not in detected
        )
        removed = sum(
            1
            for pair, applies in corrections.items()
            if pair[1] == person_id and not applies and pair not in detected
        )
        result.append(
            PersonCounts(
                label=f"Person {position}",
                recognised=len(mine),
                correct=len(mine) - wrong,
                wrong=wrong,
                added=added,
                removed_not_recognised=removed,
            )
        )
    return tuple(result)


async def read_counts(session: AsyncSession, project_id: int) -> tuple[PersonCounts, ...]:
    """Der EINZIGE Datenbankzugriff, und er liest ausschliesslich - gebunden an `project_id`."""
    if (
        await session.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none() is None:
        raise PersonProbeError(f"Es gibt kein Projekt mit der Id {project_id}.")
    photos = select(Photo.id).where(Photo.project_id == project_id)
    person_ids = list(
        (await session.execute(select(Person.id).order_by(Person.slot))).scalars().all()
    )
    detections = [
        (photo_id, person_id)
        for photo_id, person_id in (
            await session.execute(
                select(PhotoPersonDetection.photo_id, PhotoPersonDetection.person_id).where(
                    PhotoPersonDetection.photo_id.in_(photos)
                )
            )
        ).all()
    ]
    corrections = {
        (photo_id, person_id): bool(applies)
        for photo_id, person_id, applies in (
            await session.execute(
                select(
                    PhotoPersonCorrection.photo_id,
                    PhotoPersonCorrection.person_id,
                    PhotoPersonCorrection.applies,
                ).where(PhotoPersonCorrection.photo_id.in_(photos))
            )
        ).all()
    }
    return count_trail(person_ids, detections, corrections)


def _rate(counts: PersonCounts) -> str:
    rate = counts.rate
    return NOT_DETERMINABLE if rate is None else f"{100.0 * rate:.1f} %"


def render_report(project_id: int, counts: Sequence[PersonCounts]) -> str:
    """Markdown, AUSSCHLIESSLICH Anzahlen und "Person 1/2" - kein Name, kein Pfad, kein Foto."""
    lines = [f"# Personen-Messung, Projekt {project_id}", ""]
    if not counts:
        lines.append("Keine Person festgelegt.")
    for entry in counts:
        lines += [
            f"## {entry.label}",
            "",
            f"- erkannt: {entry.recognised}",
            f"- richtig erkannt: {entry.correct}",
            f"- falsch erkannt (erkannt und von Hand entfernt): {entry.wrong}",
            f"- von Hand ergaenzt (ohne Erkennung): {entry.added}",
            f"- von Hand entfernt und nicht mehr erkannt: {entry.removed_not_recognised}",
            f"- Quote richtig / (richtig + ergaenzt): {_rate(entry)}",
            "",
        ]
    lines.append(
        "Die Quote ist eine OBERGRENZE: Uebersehene Fotos, die niemand ergaenzt hat, fehlen im "
        "Nenner."
    )
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.person_probe",
        description="Zaehlt die Korrekturspur der Personen-Erkennung. REIN LESEND.",
    )
    parser.add_argument("--project-id", type=int, required=True)
    return parser


async def _probe(database_url: str, project_id: int) -> str:
    engine = make_engine(database_url)
    try:
        async with make_session_factory(engine)() as session:
            counts = await read_counts(session, project_id)
    finally:
        await engine.dispose()
    return render_report(project_id, counts)


def main(argv: Sequence[str] | None = None, *, database_url: str | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = asyncio.run(_probe(database_url or settings.database_url, args.project_id))
    except PersonProbeError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        print(f"Fehler: Datenbankzugriff fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
