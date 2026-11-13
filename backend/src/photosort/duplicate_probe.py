"""REIN LESENDES Messkommando fuer die Duplikaterkennung.

Aufruf::

    docker compose exec -T backend python -m photosort.duplicate_probe --project-id 3

Gemessen wird auf DENSELBEN Signaturen wie der Scoring-Lauf: der grobe dHash aus
``PhotoScore.phash``, die feine Signatur und das Grauwertgitter aus der lokalen ``display``-
Variante, die Schaerfe aus ``PhotoScore``. Drei Laeufe ueber DIESELBE Teilmenge:

* **Vorher** - die alte, transitive Union-Find-Gruppierung ueber dHash-Abstand ``<= 6``.
* **Nachher** - ``scoring.py::assign_duplicate_groups`` (Stand Spec 0637).
* **Gegenlauf** - dasselbe Verfahren, aber ohne die Herkunft der Aufnahmezeit zu pruefen: So
  viele Gruppen entstehen, wenn man eine aus dem Dateidatum abgeleitete Zeit wie eine Messung
  behandelt.

REIN LESEND, geprueft in drei Teilen: kein Pfad aus ``main.py``/``worker.py`` importiert dieses
Modul, ein Syntaxbaum-Waechter verbietet jede Schreibform im Modul, und ein echter ``main()``-Lauf
vergleicht jede Tabelle vorher/nachher.

SICHERHEIT: Die Ausgabe traegt keine Pfade, Dateinamen, Projektnamen, Koordinaten oder
Einzelzeitpunkte. Ausgewiesen werden Projekt-Id, Lauf-Id, Anzahlen, Groessenverteilungen und
Zeitspannen als DAUER. Fehlt fuer ein Foto der Cache oder ist es nicht dekodierbar, zaehlt es als
"uebersprungen" und wird aus ALLEN drei Laeufen entfernt - nie als Null gewertet.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

# Der Modulimport registriert den HEIF-Opener bei Pillow; ohne ihn liefert `Image.open` fuer
# HEIC/HEIF kein Bild, und die Probe uebersaehe einen Teil des Bestands.
import photosort.image_codecs  # noqa: F401
from photosort.config import settings
from photosort.db import make_engine, make_session_factory
from photosort.models import Photo, PhotoScore, Project, ScanStatus, ScoringRun
from photosort.scoring import (
    PhotoFingerprint,
    assign_duplicate_groups,
    candidate_pairs,
    compute_fine_dhash,
    compute_gray_grid,
    is_practically_identical,
    is_similar,
    taken_at_is_trusted,
)
from photosort.thumbnails import display_path

# EINGEFROREN: die Schwelle des abgeloesten Verfahrens. Sie steht absichtlich nicht mehr in
# `scoring.py` - der Vergleich laege sonst gegen einen Wert, den niemand mehr pflegt, und der
# Bericht saehe nach einer Messung des heutigen Codes aus.
OLD_REFERENCE_HAMMING = 6


@dataclass(frozen=True)
class ProbePhoto:
    photo_id: int
    phash: int
    taken_at: datetime
    taken_at_trusted: bool


@dataclass(frozen=True)
class GroupSummary:
    """Die Kennzahlen EINER Gruppierung - ohne Mitglieder, ohne Einzelzeiten."""

    groups: int
    losers: int
    largest: int
    sizes: tuple[int, ...]
    span: timedelta | None


@dataclass(frozen=True)
class DuplicateMeasurement:
    project_id: int
    run_id: int
    photos_total: int
    measured: int
    skipped: int
    untrusted: int
    candidate_pairs: int
    identical_pairs: int
    similar_pairs: int
    old: GroupSummary
    new: GroupSummary
    similar_span: timedelta | None
    counter: GroupSummary


class DuplicateProbeError(RuntimeError):
    """Ein Abbruch mit einer Meldung fuer den Aufrufer - nie ein Traceback."""


def _summarise(groups: Sequence[Sequence[int]], moments: dict[int, datetime]) -> GroupSummary:
    sizes = tuple(sorted((len(members) for members in groups if len(members) > 1), reverse=True))
    spans = [
        max(moments[member] for member in members) - min(moments[member] for member in members)
        for members in groups
        if len(members) > 1 and all(member in moments for member in members)
    ]
    return GroupSummary(
        groups=len(sizes),
        losers=sum(size - 1 for size in sizes),
        largest=sizes[0] if sizes else 0,
        sizes=sizes,
        span=max(spans) if spans else None,
    )


def old_transitive_groups(photos: Sequence[ProbePhoto]) -> list[list[int]]:
    """Die abgeloeste Gruppierung, eingefroren als Referenz: alle Paare ueber dHash ``<= 6``,
    transitiv per Union-Find zusammengefasst. Genau die Bruecke, die Spec 0637 verbietet."""
    parent = {photo.photo_id: photo.photo_id for photo in photos}

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    for position, left in enumerate(photos):
        for right in photos[position + 1 :]:
            if (left.phash ^ right.phash).bit_count() <= OLD_REFERENCE_HAMMING:
                left_root, right_root = find(left.photo_id), find(right.photo_id)
                if left_root != right_root:
                    parent[max(left_root, right_root)] = min(left_root, right_root)

    grouped: dict[int, list[int]] = defaultdict(list)
    for photo in photos:
        grouped[find(photo.photo_id)].append(photo.photo_id)
    return list(grouped.values())


def _groups_of(mapping: dict[int, int]) -> list[list[int]]:
    groups: dict[int, list[int]] = defaultdict(list)
    for loser, winner in mapping.items():
        groups[winner].append(loser)
    return [[winner, *losers] for winner, losers in groups.items()]


def pair_counts(fingerprints: Sequence[PhotoFingerprint]) -> tuple[int, int, int]:
    """Kandidaten-, identische und aehnliche Paare - alles ueber DERSELBEN Kandidatenmenge."""
    by_id = {fingerprint.photo_id: fingerprint for fingerprint in fingerprints}
    pairs = candidate_pairs(fingerprints)
    identical = 0
    similar = 0
    for left, right in pairs:
        if is_practically_identical(by_id[left], by_id[right]):
            identical += 1
        elif is_similar(by_id[left], by_id[right]):
            similar += 1
    return len(pairs), identical, similar


def largest_similar_span(
    mapping: dict[int, int], by_id: dict[int, PhotoFingerprint]
) -> timedelta | None:
    """Die groesste Zeitspanne, die eine Gruppe ueber AEHNLICHE Kanten spannt.

    Ein sternfoermig identisches Mitglied kann Jahre entfernt sein und wuerde die Zahl sonst
    aufblaehen; gezaehlt werden nur Mitglieder, deren Kante zum Gewinner "aehnlich" ist."""
    members: dict[int, list[int]] = defaultdict(list)
    for loser, winner in mapping.items():
        if not is_practically_identical(by_id[winner], by_id[loser]):
            members[winner].append(loser)
    spans: list[timedelta] = []
    for winner, losers in members.items():
        times = [by_id[winner].taken_at, *(by_id[loser].taken_at for loser in losers)]
        known = [moment for moment in times if moment is not None]
        if len(known) == len(times):
            spans.append(max(known) - min(known))
    return max(spans) if spans else None


def _read_signature(path: Path) -> tuple[int, bytes] | None:
    """Feine Signatur und Grauwertgitter aus der lokalen `display`-Variante."""
    try:
        with Image.open(path) as image:
            return compute_fine_dhash(image), compute_gray_grid(image)
    except Exception:
        return None


@dataclass(frozen=True)
class ProbeInput:
    project_id: int
    run_id: int
    photos_total: int
    photos: tuple[ProbePhoto, ...]
    fingerprints: tuple[PhotoFingerprint, ...]
    untrusted: int
    skipped: int


async def read_duplicate_probe_input(session: AsyncSession, project_id: int) -> ProbeInput:
    """Liest Projekt, letzten erfolgreichen Lauf und alle Fotos mit Score. Kein Schreiben."""
    project = await session.get(Project, project_id)
    if project is None:
        raise DuplicateProbeError(f"Projekt {project_id} existiert nicht.")
    run = (
        await session.execute(
            select(ScoringRun)
            .where(ScoringRun.project_id == project_id, ScoringRun.status == ScanStatus.SUCCESS)
            .order_by(ScoringRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run is None:
        raise DuplicateProbeError(
            f"Projekt {project_id} hat keinen erfolgreichen Scoring-Lauf. Ohne Lauf gibt es "
            "nichts zu messen - erst den Lauf durchfuehren."
        )

    rows = list(
        (
            await session.execute(
                select(Photo, PhotoScore)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project_id)
                .order_by(Photo.id)
            )
        ).tuples()
    )
    cache_dir = Path(settings.photo_cache_dir)
    photos_by_id: list[ProbePhoto] = []
    fingerprints: list[PhotoFingerprint] = []
    untrusted = 0

    for photo, score in rows:
        if score.phash is None:
            continue
        signature = _read_signature(display_path(cache_dir, photo.id, photo.etag))
        if signature is None:
            continue
        trusted = taken_at_is_trusted(photo.taken_at_original, photo.last_modified)
        untrusted += int(not trusted)
        coarse = int(score.phash, 16)
        fine, grid = signature
        photos_by_id.append(
            ProbePhoto(
                photo_id=photo.id,
                phash=coarse,
                taken_at=photo.taken_at,
                taken_at_trusted=trusted,
            )
        )
        fingerprints.append(
            PhotoFingerprint(
                photo_id=photo.id,
                phash=coarse,
                fine_phash=fine,
                gray_grid=grid,
                sharpness=score.sharpness,
                taken_at=photo.taken_at,
                taken_at_trusted=trusted,
                pixel_count=photo.pixel_count,
            )
        )

    return ProbeInput(
        project_id=project.id,
        run_id=run.id,
        photos_total=len(rows),
        photos=tuple(photos_by_id),
        fingerprints=tuple(fingerprints),
        untrusted=untrusted,
        skipped=len(rows) - len(photos_by_id),
    )


def measure(probe: ProbeInput) -> DuplicateMeasurement:
    """Die drei Laeufe und ihre Kennzahlen - eine reine Funktion, kein DB-Zugriff."""
    moments = {photo.photo_id: photo.taken_at for photo in probe.photos}
    by_id = {fingerprint.photo_id: fingerprint for fingerprint in probe.fingerprints}
    old = _summarise(old_transitive_groups(probe.photos), moments)
    mapping = assign_duplicate_groups(probe.fingerprints)
    new = _summarise(_groups_of(mapping.duplicate_of), moments)
    counter_fingerprints = tuple(
        PhotoFingerprint(
            photo_id=fingerprint.photo_id,
            phash=fingerprint.phash,
            fine_phash=fingerprint.fine_phash,
            gray_grid=fingerprint.gray_grid,
            sharpness=fingerprint.sharpness,
            taken_at=fingerprint.taken_at,
            taken_at_trusted=fingerprint.taken_at is not None,
            pixel_count=fingerprint.pixel_count,
        )
        for fingerprint in probe.fingerprints
    )
    counter = _summarise(
        _groups_of(assign_duplicate_groups(counter_fingerprints).duplicate_of), moments
    )
    candidates, identical, similar = pair_counts(probe.fingerprints)
    return DuplicateMeasurement(
        project_id=probe.project_id,
        run_id=probe.run_id,
        photos_total=probe.photos_total,
        measured=len(probe.photos),
        skipped=probe.skipped,
        untrusted=probe.untrusted,
        candidate_pairs=candidates,
        identical_pairs=identical,
        similar_pairs=similar,
        old=old,
        new=new,
        similar_span=largest_similar_span(mapping.duplicate_of, by_id),
        counter=counter,
    )


def _distribution(sizes: Sequence[int]) -> str:
    counts = Counter(sizes)
    return ", ".join(f"{size}:{counts[size]}" for size in sorted(counts)) or "keine"


def _span(span: timedelta | None) -> str:
    return "nicht gemessen" if span is None else f"{span.total_seconds() / 60:.0f} min"


def render_report(measurement: DuplicateMeasurement) -> str:
    share = (
        "nicht gemessen (keine Fotos)"
        if measurement.measured == 0
        else f"{measurement.untrusted / measurement.measured * 100:.1f} %"
    )
    lines = [
        f"# Duplikatmessung, Projekt {measurement.project_id}, Lauf {measurement.run_id}",
        "",
        f"- Fotos mit Score: {measurement.photos_total}",
        f"- gemessen: {measurement.measured}",
        f"- uebersprungen (kein Cache / nicht dekodierbar): {measurement.skipped}",
        f"- Aufnahmezeit nicht aus dem Bild: {measurement.untrusted} ({share})",
        f"- Kandidatenpaare Stufe 1: {measurement.candidate_pairs}",
        f"- davon praktisch identisch: {measurement.identical_pairs}",
        f"- davon aehnlich im Zeitfenster: {measurement.similar_pairs}",
        "",
        "## Vorher (transitiver dHash <= 6)",
        f"- Gruppen: {measurement.old.groups}",
        f"- Verlierer: {measurement.old.losers}",
        f"- groesste Gruppe: {measurement.old.largest}",
        f"- groesste Zeitspanne einer Gruppe: {_span(measurement.old.span)}",
        f"- Groessen: {_distribution(measurement.old.sizes)}",
        "",
        "## Nachher (mehrstufig, Zeitfenster, Stern)",
        f"- Gruppen: {measurement.new.groups}",
        f"- Verlierer: {measurement.new.losers}",
        f"- groesste Gruppe: {measurement.new.largest}",
        f"- groesste Zeitspanne aehnlicher Mitglieder: {_span(measurement.similar_span)}",
        f"- Groessen: {_distribution(measurement.new.sizes)}",
        "",
        "## Gegenlauf ohne Zeit-Herkunft",
        f"- Gruppen: {measurement.counter.groups}",
        f"- Verlierer: {measurement.counter.losers}",
        f"- groesste Gruppe: {measurement.counter.largest}",
        f"- Groessen: {_distribution(measurement.counter.sizes)}",
    ]
    if measurement.measured == 0:
        lines.extend(
            [
                "",
                "NICHT GEMESSEN: Fuer kein Foto lag eine lesbare `display`-Variante vor. "
                "Die Zahlen sind nicht null, sondern unbekannt.",
            ]
        )
    return "\n".join(lines)


async def _probe_with_own_session(database_url: str, project_id: int) -> DuplicateMeasurement:
    engine = make_engine(database_url)
    try:
        factory = make_session_factory(engine)
        async with factory() as session:
            probe = await read_duplicate_probe_input(session, project_id)
    finally:
        await engine.dispose()
    return measure(probe)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.duplicate_probe",
        description=(
            "REIN LESEND: misst die Duplikatgruppen eines Projekts vorher/nachher. "
            "Kein Schreibzugriff, keine Bilddaten in der Ausgabe."
        ),
    )
    parser.add_argument("--project-id", type=int, required=True)
    return parser


def main(argv: Sequence[str] | None = None, *, database_url: str | None = None) -> int:
    """Verdrahtung + Exit-Code; `argv` und `database_url` sind injizierbar."""
    args = _build_parser().parse_args(argv)
    try:
        measurement = asyncio.run(
            _probe_with_own_session(database_url or settings.database_url, args.project_id)
        )
    except DuplicateProbeError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        # Nur der Fehlertyp, NIE str(exc) - die Meldung kann die DATABASE_URL enthalten.
        print(f"Fehler: Datenbankzugriff fehlgeschlagen ({type(exc).__name__}).", file=sys.stderr)
        return 1
    print(render_report(measurement))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
