"""Read-only CLI: vergleicht die Kategorie-Zuordnung zweier Kriterien-Laeufe eines Projekts.

specs/features/0217-landschaft-erkennung-spezifitaets-vorrang.md (AK7), ADR decisions/0047-
inhaltsbasierte-landschaft-spezifitaets-vorrang-nicht-erkannt.md Punkt 7: `PhotoRanking`-Zeilen
werden pro `criterion_scoring_run_id` geschrieben und nie geloescht - der Stand VOR einer
Umstellung liegt also bereits in der Datenbank und braucht weder Migration noch API-Erweiterung.

Aufruf::

    docker compose exec backend python -m photosort.category_diff --project-id 1

Bewusst ein CLI-Werkzeug und kein Endpunkt/keine UI (ADR 0047 Punkt 7): eine einmalige
Verifikations-/Kalibrierungshilfe fuer zwei bekannte Betreiber, keine dauerhaft zu pflegende
Produktoberflaeche.

AUSGABE-HYGIENE (Security-Abschnitt der Spec 0217, Punkt 3 - verbindlich): die Ausgabe enthaelt
`relative_path`-Werte, also Dateinamen und Ordnerstruktur privater Familienfotos. Sie geht
deshalb AUSSCHLIESSLICH nach stdout - keine Datei-Ausgabe-Option, kein Schreiben ins Repo, keine
Ausgabe ueber den strukturierten Anwendungs-Logger (und damit nicht in persistente
Container-Logs). Die Ausgabe NICHT unveraendert in GitHub-Issues, PR-Beschreibungen, Specs oder
Commit-Messages einfuegen.
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
from photosort.models import CriterionScoringRun, Photo, PhotoRanking, Project, ScanStatus

# Platzhalter fuer ein Foto, das in genau einem der beiden Laeufe eine Zuordnung hat (z.B. erst
# spaeter gescannt oder inzwischen als Ausschuss aussortiert) - eigener Marker statt eines leeren
# Strings, damit die Uebergangsmatrix diesen Fall sichtbar macht statt ihn zu verstecken.
MISSING_CATEGORY = "(keine Zuordnung)"

# Mindestanzahl erfolgreicher Laeufe, die ein Projekt fuer den Default-Vergleich braucht.
_REQUIRED_RUNS_FOR_DEFAULT = 2


class CategoryDiffError(Exception):
    """Erwarteter, benutzerseitig behebbarer Fehler (unbekanntes Projekt, zu wenige Laeufe,
    Run-ID gehoert zu einem anderen Projekt, DB nicht erreichbar) - wird in main() zu einer
    kurzen, eigenen Meldung und einem Exit-Code != 0. Bewusst KEIN durchgereichter
    SQLAlchemy-Traceback (Security-Abschnitt der Spec 0217, Punkt 3): der wuerde die
    DATABASE_URL inklusive Zugangsdaten in die Ausgabe schreiben (Muster analog OpenCloudError).
    """


@dataclass(frozen=True)
class PhotoTransition:
    """Ein Foto und seine Kategorie im Vorher-/Nachher-Lauf."""

    photo_id: int
    before: str
    after: str

    @property
    def changed(self) -> bool:
        return self.before != self.after


@dataclass(frozen=True)
class CategoryDiff:
    """Ergebnis des reinen Vergleichs - Uebergangsmatrix (alt -> neu mit Anzahlen) plus die
    Foto-Einzelliste. Beides deterministisch sortiert (siehe diff_category_assignments)."""

    transitions: tuple[PhotoTransition, ...]

    @property
    def matrix(self) -> dict[tuple[str, str], int]:
        counts: dict[tuple[str, str], int] = {}
        for transition in self.transitions:
            key = (transition.before, transition.after)
            counts[key] = counts.get(key, 0) + 1
        return counts


def diff_category_assignments(
    before: Mapping[int, str], after: Mapping[int, str]
) -> CategoryDiff:
    """Reine, DB-freie Vergleichsfunktion (ADR 0047 Punkt 7: Logik rein, I/O aussen). Fotos, die
    nur in einem der beiden Laeufe eine Zuordnung haben, erscheinen mit MISSING_CATEGORY auf der
    fehlenden Seite - sie fallen nicht stillschweigend aus dem Vergleich. Sortierung nach
    photo_id (deterministisch, unabhaengig von der Dict-Reihenfolge der Aufrufer)."""
    photo_ids = sorted(set(before) | set(after))
    return CategoryDiff(
        transitions=tuple(
            PhotoTransition(
                photo_id=photo_id,
                before=before.get(photo_id, MISSING_CATEGORY),
                after=after.get(photo_id, MISSING_CATEGORY),
            )
            for photo_id in photo_ids
        )
    )


def render_report(
    diff: CategoryDiff,
    photo_paths: Mapping[int, str],
    *,
    before_run_id: int,
    after_run_id: int,
) -> str:
    """Formatiert das Vergleichsergebnis als reinen Text (Uebergangsmatrix + Foto-Einzelliste).
    Deterministisch sortiert: die Matrix nach (alt, neu), die Einzelliste nach relative_path -
    zwei Laeufe ueber dieselben Daten liefern damit byte-identische Ausgabe."""
    lines = [
        f"Kategorie-Vergleich: Lauf {before_run_id} (vorher) -> Lauf {after_run_id} (nachher)",
        f"Fotos gesamt: {len(diff.transitions)}",
        f"Davon veraendert: {sum(1 for t in diff.transitions if t.changed)}",
        "",
        "Uebergangsmatrix (alt -> neu):",
    ]
    matrix = diff.matrix
    if not matrix:
        lines.append("  (keine Daten)")
    for (before_key, after_key), count in sorted(matrix.items()):
        marker = "  " if before_key == after_key else "* "
        lines.append(f"  {marker}{before_key} -> {after_key}: {count}")

    lines.extend(["", "Fotos (relative_path, alt, neu):"])
    if not diff.transitions:
        lines.append("  (keine Daten)")
    for transition in sorted(
        diff.transitions,
        key=lambda t: (photo_paths.get(t.photo_id, ""), t.photo_id),
    ):
        path = photo_paths.get(transition.photo_id, f"<Foto {transition.photo_id}>")
        lines.append(f"  {path}: {transition.before} -> {transition.after}")

    return "\n".join(lines)


async def collect_assignments(session: AsyncSession, run_id: int) -> dict[int, str]:
    """Duenne DB-Leseschicht: photo_id -> category_key aller PhotoRanking-Zeilen EINES Laufs.
    Rein lesend, veraendert nichts."""
    rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.category_key).where(
                PhotoRanking.criterion_scoring_run_id == run_id
            )
        )
    ).all()
    return {photo_id: category_key for photo_id, category_key in rows}


async def collect_photo_paths(
    session: AsyncSession, photo_ids: Iterable[int]
) -> dict[int, str]:
    """Duenne DB-Leseschicht: photo_id -> relative_path fuer die Foto-Einzelliste."""
    ids = list(photo_ids)
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Photo.id, Photo.relative_path).where(Photo.id.in_(ids))
        )
    ).all()
    return {photo_id: relative_path for photo_id, relative_path in rows}


async def resolve_run_ids(
    session: AsyncSession,
    project_id: int,
    before_run_id: int | None,
    after_run_id: int | None,
) -> tuple[int, int]:
    """Ermittelt die zu vergleichenden Laeufe. Default: die beiden juengsten ERFOLGREICHEN Laeufe
    des Projekts. Explizit uebergebene Run-IDs muessen zum angegebenen Projekt gehoeren
    (Konsistenz-Guard, Security-Abschnitt der Spec 0217 Punkt 3) - sonst Abbruch, statt still die
    Daten zweier Projekte zu vermischen."""
    project = await session.get(Project, project_id)
    if project is None:
        raise CategoryDiffError(f"Projekt {project_id} existiert nicht.")

    if before_run_id is not None or after_run_id is not None:
        if before_run_id is None or after_run_id is None:
            raise CategoryDiffError(
                "--before-run-id und --after-run-id muessen gemeinsam angegeben werden."
            )
        if before_run_id == after_run_id:
            # Sonst entsteht ein Report, in dem definitionsgemaess alles unveraendert aussieht -
            # irrefuehrend genau bei dem Werkzeug, das eine Veraenderung nachweisen soll.
            raise CategoryDiffError(
                "--before-run-id und --after-run-id sind identisch - kein Vergleich moeglich."
            )
        for run_id in (before_run_id, after_run_id):
            run = await session.get(CriterionScoringRun, run_id)
            if run is None or run.project_id != project_id:
                raise CategoryDiffError(
                    f"Lauf {run_id} gehoert nicht zu Projekt {project_id}."
                )
        return before_run_id, after_run_id

    run_ids = list(
        (
            await session.execute(
                select(CriterionScoringRun.id)
                .where(
                    CriterionScoringRun.project_id == project_id,
                    CriterionScoringRun.status == ScanStatus.SUCCESS,
                )
                .order_by(CriterionScoringRun.started_at.desc(), CriterionScoringRun.id.desc())
                .limit(_REQUIRED_RUNS_FOR_DEFAULT)
            )
        ).scalars()
    )
    if len(run_ids) < _REQUIRED_RUNS_FOR_DEFAULT:
        raise CategoryDiffError(
            f"Projekt {project_id} hat weniger als {_REQUIRED_RUNS_FOR_DEFAULT} erfolgreiche "
            "Kriterien-Laeufe - kein Vergleich moeglich."
        )
    newest, previous = run_ids
    return previous, newest


async def build_report(
    session: AsyncSession,
    project_id: int,
    before_run_id: int | None,
    after_run_id: int | None,
) -> str:
    """Verdrahtet DB-Leseschicht und reine Funktionen - kein eigener Formatierungs-/Vergleichs-
    Code hier."""
    resolved_before, resolved_after = await resolve_run_ids(
        session, project_id, before_run_id, after_run_id
    )
    before = await collect_assignments(session, resolved_before)
    after = await collect_assignments(session, resolved_after)
    diff = diff_category_assignments(before, after)
    paths = await collect_photo_paths(session, (t.photo_id for t in diff.transitions))
    return render_report(
        diff, paths, before_run_id=resolved_before, after_run_id=resolved_after
    )


async def _build_report_with_own_session(
    database_url: str,
    project_id: int,
    before_run_id: int | None,
    after_run_id: int | None,
) -> str:
    engine = make_engine(database_url)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            return await build_report(session, project_id, before_run_id, after_run_id)
    finally:
        await engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.category_diff",
        description=(
            "Vergleicht die Kategorie-Zuordnung zweier Kriterien-Laeufe eines Projekts "
            "(rein lesend, veraendert nichts)."
        ),
        epilog=(
            "Die Ausgabe enthaelt Dateinamen/Ordnerstruktur privater Fotos und geht "
            "ausschliesslich nach stdout - nicht unveraendert in GitHub-Issues, "
            "PR-Beschreibungen, Specs oder Commit-Messages einfuegen."
        ),
    )
    # type=int statt freier Strings: zusammen mit der reinen SQLAlchemy-Core-/ORM-Nutzung
    # (Parameterbindung, kein text() mit f-String) ist SQL-Injection damit strukturell
    # ausgeschlossen, nicht nur unwahrscheinlich (Security-Abschnitt der Spec 0217, Punkt 3).
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--before-run-id", type=int, default=None)
    parser.add_argument("--after-run-id", type=int, default=None)
    return parser


def main(argv: Sequence[str] | None = None, *, database_url: str | None = None) -> int:
    """Verdrahtung + Exit-Code. `argv` ist injizierbar (kein sys.argv-Zugriff im Testpfad),
    `database_url` ebenso (Default: die konfigurierte Anwendungs-Datenbank)."""
    args = _build_parser().parse_args(argv)
    try:
        report = asyncio.run(
            _build_report_with_own_session(
                database_url or settings.database_url,
                args.project_id,
                args.before_run_id,
                args.after_run_id,
            )
        )
    except CategoryDiffError as exc:
        # Fehlertexte gehen bewusst nach stderr, der REPORT dagegen nach stdout (Review-Fund,
        # bewusst getroffene Entscheidung): die Ausgabe-Hygiene-Vorgabe "ausschliesslich stdout"
        # aus dem Security-Abschnitt der Spec 0217 zielt auf den Report mit den `relative_path`-
        # Werten privater Fotos - Fehlermeldungen enthalten keine Fotopfade, und die uebliche
        # CLI-Trennung haelt ein `... | less`/`> datei` des Reports frei von Fehlertexten.
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        # Nur der Fehlertyp, NIE str(exc)/Traceback - die SQLAlchemy-Meldung kann die
        # DATABASE_URL inklusive Zugangsdaten enthalten.
        print(f"Fehler: Datenbankzugriff fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
