"""Das Vergleichs-CLI: Eye-Ergebnisse gegen die Cloud-Aussagen derselben Fotos (Spec 0609).

Aufruf::

    python -m photosort.eye_comparison --project-id N [--seed S] [--out DATEI]

Die Frage, die dieses Werkzeug beantwortet, ist eine BETRIEBSENTSCHEDUNG ("bleibt Eye oder wird es
wieder ausgebaut?") und keine Produktaussage. Deshalb ist es bewusst:

* **rein lesend** - die einzige Schreibstelle des Moduls ist die `--out`-Datei, und die liegt
  ausserhalb des Repos. Kein Import aus `main.py`/`worker.py`, kein Endpunkt, kein Compose-Dienst.
* **ohne Urteil** - es zaehlt Uebereinstimmungen und Abweichungen je Zweck und nennt hoechstens
  `DEVIATION_SAMPLE_LIMIT` seeded ausgewaehlte Abweichungen. Ob eine Abweichung schlimm ist,
  entscheidet die lesende Person; ein Feld wie "empfohlen" waere genau die Automatisierung, die
  hier nicht stattfinden soll.
* **ohne Namen** - gelesen werden ausschliesslich Eye-, Cloud-, Motiv- und Albumspalten. Weder
  `photos.relative_path` noch Nutzer, Personen, Orte oder Sehenswuerdigkeitsnamen erreichen die
  Ausgabe; ein Dateiname waere schon eine Inhaltsangabe.
* **je Zweck gedeckelt** - hoechstens `DEVIATION_SAMPLE_LIMIT` Zeilen PRO Zweck; eine
  Gesamtgrenze liesse dreissig Motiv-Abweichungen den Platz von Ausschluss und Albumstufe fressen.
* **deterministisch** - dieselbe `--seed` waehlt dieselben Abweichungszeilen aus, damit zwei
  Personen ueber dieselben Beispiele sprechen.
* **ohne Uhrzeit** - die Datei traegt nur `duration_seconds`, nie `finished_at`/`started_at`, und
  keinen Meldungstext aus einem fremden System: `error_message`/`cloud_error_message` werden
  nicht gelesen. Beides waere eine Aussage ueber den Haushalt bzw. ueber fremde Antwortfragmente.

stdout traegt nur die Zaehlungen. Die Abweichungszeilen (Foto-Id und App-Pfad) gehen
ausschliesslich in die `--out`-Datei: eine Konsole ist fluechtig, und die Beispiele sind das, was
eine Entscheidung traegt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from photosort.db import async_session_factory
from photosort.models import (
    ClassificationMode,
    CriterionScoringRun,
    Photo,
    PhotoAlbumSuitability,
    PhotoEyeMotifStrength,
    PhotoEyeResult,
    PhotoMotifAssessment,
    PhotoMotifStrength,
    RemoteCategoryClassificationRun,
    ScanStatus,
)
from photosort.selection import motif_is_present

# So viele Abweichungen nennt die Datei JE ZWECK - mehr sind kein Vergleich mehr, sondern ein
# Datenexport. Je Zweck und nicht insgesamt: sonst fraessen dreissig Motiv-Abweichungen den Platz
# von Ausschluss und Albumstufe, also genau der Zwecke, fuer die das Werkzeug existiert.
DEVIATION_SAMPLE_LIMIT = 30

# Die Zwecke, in denen verglichen wird. Feinlabels sind ausdruecklich NICHT dabei: Eyes
# Tag-Vokabular ist ein anderes als das Cloud-Vokabular, ein Vergleich waere eine Namensdebatte
# und keine Messung.
PURPOSES = ("motifs", "excluded_document", "album_level")


@dataclass(frozen=True)
class PhotoComparison:
    """Die Vergleichszeile EINES Fotos - nur die Aussagen, die verglichen und die Herkunft, die
    genannt wird."""

    photo_id: int
    cloud_motifs: Mapping[str, float]
    eye_motifs: Mapping[str, float]
    cloud_excluded_document: bool
    eye_excluded_document: bool
    cloud_album_level: int | None
    eye_album_level: int
    cloud_provider: str | None
    eye_model_revision: str | None


@dataclass(frozen=True)
class Deviation:
    """Eine einzelne Abweichung - mit BEIDEN Werten ihres Zwecks.

    `motif_key` ist nur beim Motivzweck gesetzt. Die drei Wertepaare tragen bewusst keinen
    Vorgabewert: ein in `summarize` vergessenes Setzen scheitert beim Bau, statt als stilles
    `null` in die Datei zu gehen. `null` steht dort, wo der Zweck das Paar nicht fuehrt ODER die
    Seite den Schluessel nicht beurteilt hat - "nicht beurteilt" ist nicht "als 0.0 beurteilt"."""

    photo_id: int
    purpose: str
    motif_key: str | None
    cloud_strength: float | None
    eye_strength: float | None
    cloud_excluded_document: bool | None
    eye_excluded_document: bool | None
    cloud_album_level: int | None
    eye_album_level: int | None


@dataclass(frozen=True)
class PurposeCounts:
    compared: int
    matching: int
    deviating: int


@dataclass(frozen=True)
class ComparisonReport:
    photos_compared: int
    motifs: PurposeCounts
    excluded_document: PurposeCounts
    album_level: PurposeCounts
    deviations: tuple[Deviation, ...]
    # Herkunft der VERGLICHENEN Fotos - sortiert und ohne Dubletten. Eine leere Liste heisst
    # "kein Wert erfasst", nicht "fand nicht statt".
    cloud_providers: tuple[str, ...]
    eye_model_revisions: tuple[str, ...]


@dataclass(frozen=True)
class CloudRunFacts:
    """Der juengste Cloud-Lauf: Dauer und die Zahlen seines VERKNUEPFTEN Remote-Laufs."""

    duration_seconds: int
    remote_photos_total: int
    remote_api_calls: int | None


@dataclass(frozen=True)
class EyeRunFacts:
    """Der juengste Eye-Lauf. `NULL` bleibt `null` - "Phase nicht betreten" ist keine 0."""

    duration_seconds: int
    eye_photos_total: int | None
    eye_photos_processed: int | None


@dataclass(frozen=True)
class RunFacts:
    """Alles, was aus den Laeufen in die Datei geht - Dauern, Zaehlungen, Kennungen.

    Kein Zeitpunkt und kein Meldungstext: ein Zeitpunkt verriete, wann der Haushalt nicht zu Hause
    war, und `error_message`/`cloud_error_message` tragen `str(exc)` eines fremden Systems."""

    cloud_models: tuple[str, ...] = ()
    cloud_run: CloudRunFacts | None = None
    eye_run: EyeRunFacts | None = None
    remote_api_calls_total: int | None = None


def motif_present(strengths: Mapping[str, float], motif_key: str) -> bool:
    """Gilt das Motiv als vorhanden? Fehlt die Zeile, ist es nicht vorhanden - dieselbe Regel wie
    im Lesepfad, entschieden von `selection.py::motif_is_present` (inklusive Grenze, ein Praedikat
    fuer alle Motive).

    Hier steht NUR die Zuordnung Schluessel -> Staerke; keine eigene Grenze und kein eigener
    Vergleich. Eine zweite Fassung liefe beim naechsten Wechsel der Grenze still auseinander."""
    return motif_is_present(strengths.get(motif_key, 0.0))


def _compared_pairs(
    cloud: Mapping[str, float], eye: Mapping[str, float]
) -> tuple[tuple[int, int], ...]:
    return tuple(
        (int(motif_present(cloud, key)), int(motif_present(eye, key)))
        for key in sorted(set(cloud) | set(eye))
    )


def compare_motifs(cloud: Mapping[str, float], eye: Mapping[str, float]) -> tuple[int, int]:
    """(uebereinstimmende, abweichende) Motiv-Entscheidungen der gemeinsamen Praesenzregel.

    Verglichen wird ueber die VEREINIGUNG der Schluessel: eine auf einer Seite fehlende Zeile ist
    "nicht vorhanden", und genau so liest der Lesepfad sie. Ein Schnitt waere die stillere, aber
    falsche Variante - sie uebersaehe gerade die Faelle, in denen eine Seite ein Motiv gar nicht
    beurteilt hat."""
    matching = 0
    deviating = 0
    for cloud_present, eye_present in _compared_pairs(cloud, eye):
        if cloud_present == eye_present:
            matching += 1
        else:
            deviating += 1
    return matching, deviating


def summarize(
    photos: Iterable[PhotoComparison],
    *,
    seed: int,
    limit: int = DEVIATION_SAMPLE_LIMIT,
) -> ComparisonReport:
    """Reine Vergleichslogik: Zaehlungen je Zweck plus die seeded Abweichungsauswahl.

    Jede Abweichungszeile traegt beide Rohwerte ihres Zwecks. Die Staerke wird durchgereicht, wie
    sie in der Datenbank steht - kein `round`, keine Formatierung: die inklusive Grenze 0.5 muss
    lesbar bleiben."""
    photos_compared = 0
    motif_matching = 0
    motif_deviating = 0
    excluded_matching = 0
    excluded_deviating = 0
    album_matching = 0
    album_deviating = 0
    deviations: list[Deviation] = []
    providers: set[str] = set()
    revisions: set[str] = set()

    for photo in photos:
        photos_compared += 1
        if photo.cloud_provider is not None:
            providers.add(photo.cloud_provider)
        if photo.eye_model_revision is not None:
            revisions.add(photo.eye_model_revision)

        matching, deviating = compare_motifs(photo.cloud_motifs, photo.eye_motifs)
        motif_matching += matching
        motif_deviating += deviating
        if deviating > 0:
            for key in sorted(set(photo.cloud_motifs) | set(photo.eye_motifs)):
                if motif_present(photo.cloud_motifs, key) != motif_present(photo.eye_motifs, key):
                    deviations.append(
                        Deviation(
                            photo_id=photo.photo_id,
                            purpose="motifs",
                            motif_key=key,
                            cloud_strength=photo.cloud_motifs.get(key),
                            eye_strength=photo.eye_motifs.get(key),
                            cloud_excluded_document=None,
                            eye_excluded_document=None,
                            cloud_album_level=None,
                            eye_album_level=None,
                        )
                    )

        if photo.cloud_excluded_document == photo.eye_excluded_document:
            excluded_matching += 1
        else:
            excluded_deviating += 1
            deviations.append(
                Deviation(
                    photo_id=photo.photo_id,
                    purpose="excluded_document",
                    motif_key=None,
                    cloud_strength=None,
                    eye_strength=None,
                    cloud_excluded_document=photo.cloud_excluded_document,
                    eye_excluded_document=photo.eye_excluded_document,
                    cloud_album_level=None,
                    eye_album_level=None,
                )
            )

        # Ohne Albumtauglichkeitszeile gibt es nichts zu vergleichen - sie entsteht nur mit
        # Cloud-Grundlage. Der Fall wird gezaehlt, nicht als Abweichung umgedeutet.
        if photo.cloud_album_level is not None:
            if photo.cloud_album_level == photo.eye_album_level:
                album_matching += 1
            else:
                album_deviating += 1
                deviations.append(
                    Deviation(
                        photo_id=photo.photo_id,
                        purpose="album_level",
                        motif_key=None,
                        cloud_strength=None,
                        eye_strength=None,
                        cloud_excluded_document=None,
                        eye_excluded_document=None,
                        cloud_album_level=photo.cloud_album_level,
                        eye_album_level=photo.eye_album_level,
                    )
                )

    sampled = _sample(deviations, seed=seed, limit=limit)
    return ComparisonReport(
        photos_compared=photos_compared,
        motifs=PurposeCounts(
            compared=motif_matching + motif_deviating,
            matching=motif_matching,
            deviating=motif_deviating,
        ),
        excluded_document=PurposeCounts(
            compared=excluded_matching + excluded_deviating,
            matching=excluded_matching,
            deviating=excluded_deviating,
        ),
        album_level=PurposeCounts(
            compared=album_matching + album_deviating,
            matching=album_matching,
            deviating=album_deviating,
        ),
        deviations=sampled,
        cloud_providers=tuple(sorted(providers)),
        eye_model_revisions=tuple(sorted(revisions)),
    )


def _sample(deviations: Sequence[Deviation], *, seed: int, limit: int) -> tuple[Deviation, ...]:
    """Hoechstens `limit` Zeilen JE ZWECK, seeded ausgewaehlt - und anschliessend SORTIERT, damit
    die Datei unabhaengig von der Zufallsreihenfolge lesbar ist und zwei Laeufe byte-gleich sind.

    Ein gemeinsamer Generator ueber die Zwecke in fester Reihenfolge: der Strom haengt damit nur
    an der Seed und an den Zaehlungen, nicht an der Reihenfolge der Abweichungen in der Datenbank.
    """
    if limit <= 0:
        return ()
    by_purpose: dict[str, list[Deviation]] = {purpose: [] for purpose in PURPOSES}
    for deviation in deviations:
        by_purpose[deviation.purpose].append(deviation)
    rng = random.Random(seed)
    chosen: list[Deviation] = []
    for purpose in PURPOSES:
        rows = by_purpose[purpose]
        if rows:
            chosen.extend(rng.sample(rows, min(limit, len(rows))))
    return tuple(
        sorted(chosen, key=lambda item: (item.photo_id, item.purpose, item.motif_key or ""))
    )


def counts_only(report: ComparisonReport) -> dict[str, object]:
    """Die Fassung fuer stdout: ausschliesslich Zaehlungen, keine Zeilen mit Foto-Ids."""
    return {
        "photos_compared": report.photos_compared,
        "motifs": _counts_dict(report.motifs),
        "excluded_document": _counts_dict(report.excluded_document),
        "album_level": _counts_dict(report.album_level),
    }


def full_report(report: ComparisonReport, runs: RunFacts, *, project_id: int) -> dict[str, object]:
    """Die Fassung fuer `--out`: Zaehlungen, Herkunft, Laufzeit und die Abweichungszeilen mit
    Foto-Id und App-Pfad.

    Die Schluesselmenge ist FEST - es gibt kein Feld, das eine Empfehlung oder ein Gesamturteil
    traegt. Der Pfad ist der kanonische App-Pfad der Fotoansicht, keine Dateisystemangabe. Kein
    Zeitpunkt: nur `duration_seconds`."""
    return {
        "project_id": project_id,
        **counts_only(report),
        "origin": {
            "cloud_providers": list(report.cloud_providers),
            "cloud_models": list(runs.cloud_models),
            "eye_model_revisions": list(report.eye_model_revisions),
        },
        "runtime": {
            "cloud_run": _cloud_run_dict(runs.cloud_run),
            "eye_run": _eye_run_dict(runs.eye_run),
            "remote_api_calls_total": runs.remote_api_calls_total,
        },
        "deviations": [
            {
                "photo_id": deviation.photo_id,
                "purpose": deviation.purpose,
                "motif_key": deviation.motif_key,
                "cloud_strength": deviation.cloud_strength,
                "eye_strength": deviation.eye_strength,
                "cloud_excluded_document": deviation.cloud_excluded_document,
                "eye_excluded_document": deviation.eye_excluded_document,
                "cloud_album_level": deviation.cloud_album_level,
                "eye_album_level": deviation.eye_album_level,
                "path": f"/projects/{project_id}/photos/{deviation.photo_id}",
            }
            for deviation in report.deviations
        ],
    }


def _cloud_run_dict(facts: CloudRunFacts | None) -> dict[str, object] | None:
    if facts is None:
        return None
    return {
        "duration_seconds": facts.duration_seconds,
        "remote_photos_total": facts.remote_photos_total,
        "remote_api_calls": facts.remote_api_calls,
    }


def _eye_run_dict(facts: EyeRunFacts | None) -> dict[str, object] | None:
    if facts is None:
        return None
    return {
        "duration_seconds": facts.duration_seconds,
        "eye_photos_total": facts.eye_photos_total,
        "eye_photos_processed": facts.eye_photos_processed,
    }


def _counts_dict(counts: PurposeCounts) -> dict[str, int]:
    return {
        "compared": counts.compared,
        "matching": counts.matching,
        "deviating": counts.deviating,
    }


def _inside_a_worktree(target: Path) -> bool:
    """Wahr, wenn ein Verzeichnis OBERHALB des Ziels ein `.git` traegt.

    Geprueft wird der ZIELPFAD gegen die Arbeitsbaeume ueber ihm, nicht das installierte Paket
    gegen seinen eigenen: Im Container liegt das Modul unter `site-packages` ohne jeden `.git`
    darueber, und eine Pruefung ab dem Modul lehnte dort JEDEN Pfad ab - auch das in
    `docs/setup.md` dokumentierte `/tmp/...`. Die Auflage bleibt dieselbe: Eye-Ergebnisse gehoeren
    nicht in die Versionsverwaltung. Wird sie verletzt, bricht der Aufruf laut ab, bevor eine Datei
    entsteht; ohne Arbeitsbaum ueber dem Ziel gibt es nichts zu schuetzen."""
    return any((candidate / ".git").exists() for candidate in target.parents)


def _resolve_out(path: Path) -> Path:
    out = path.expanduser().resolve()
    if _inside_a_worktree(out):
        raise ValueError(
            "Die Ausgabedatei muss AUSSERHALB des Repos liegen: "
            "Eye-Ergebnisse gehoeren nicht in die Versionsverwaltung."
        )
    return out


def _strengths(rows: Iterable[PhotoMotifStrength | PhotoEyeMotifStrength]) -> dict[str, float]:
    return {row.motif_key: float(row.strength) for row in rows}


async def load_comparisons(session: AsyncSession, project_id: int) -> list[PhotoComparison]:
    """Alle Fotos des Projekts, fuer die BEIDE Grundlagen vorliegen.

    Gelesen werden nur die Spalten, die verglichen werden. `photo_id` ist die einzige Kennung -
    Pfad, Nutzer, Ort und Personen bleiben unberuehrt (S10)."""
    eye_rows = (
        (
            await session.execute(
                select(PhotoEyeResult)
                .join(Photo, Photo.id == PhotoEyeResult.photo_id)
                .where(Photo.project_id == project_id)
                .options(selectinload(PhotoEyeResult.strengths))
            )
        )
        .scalars()
        .all()
    )
    if not eye_rows:
        return []

    photo_ids = [row.photo_id for row in eye_rows]
    cloud_rows = {
        row.photo_id: row
        for row in (
            (
                await session.execute(
                    select(PhotoMotifAssessment)
                    .where(
                        PhotoMotifAssessment.photo_id.in_(photo_ids),
                        PhotoMotifAssessment.source == "cloud",
                    )
                    .options(selectinload(PhotoMotifAssessment.strengths))
                )
            )
            .scalars()
            .all()
        )
    }
    album_rows = {
        row.photo_id: row
        for row in (
            (
                await session.execute(
                    select(PhotoAlbumSuitability).where(
                        PhotoAlbumSuitability.photo_id.in_(photo_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
    }

    comparisons: list[PhotoComparison] = []
    for eye in eye_rows:
        cloud = cloud_rows.get(eye.photo_id)
        if cloud is None:
            continue
        album = album_rows.get(eye.photo_id)
        comparisons.append(
            PhotoComparison(
                photo_id=eye.photo_id,
                cloud_motifs=_strengths(cloud.strengths),
                eye_motifs=_strengths(eye.strengths),
                cloud_excluded_document=cloud.excluded_document,
                eye_excluded_document=eye.excluded_document,
                cloud_album_level=None if album is None else album.level,
                eye_album_level=eye.album_level,
                cloud_provider=cloud.provider,
                eye_model_revision=eye.model_revision,
            )
        )
    return sorted(comparisons, key=lambda item: item.photo_id)


def _duration_seconds(started_at: datetime, finished_at: datetime) -> int:
    """Ganze Sekunden, ABGESCHNITTEN - nicht gerundet, damit keine Dauer zu hoch steht.

    Eine negative Differenz (Uhrensprung) bleibt sichtbar: `0` waere eine erfundene Messung, ein
    negativer Wert ein Befund."""
    return int((finished_at - started_at).total_seconds())


async def load_run_facts(session: AsyncSession, project_id: int) -> RunFacts:
    """Laufdaten des Projekts: Modellnamen, beide Laeufe, die Aufrufsumme.

    Gelesen werden EINZELNE Spalten, nie ganze Zeilen und nie `error_message`/
    `cloud_error_message` - dort steht `str(exc)` eines fremden Systems, der einzige Fremdtext,
    den dieses Werkzeug uebernehmen koennte. Zeitpunkte werden zum AUSWAEHLEN und fuer die Dauer
    gelesen, nie ausgegeben."""
    cloud_candidate = (
        await session.execute(
            select(
                CriterionScoringRun.started_at,
                CriterionScoringRun.finished_at,
                RemoteCategoryClassificationRun.photos_total,
                RemoteCategoryClassificationRun.api_calls,
            )
            .join(
                RemoteCategoryClassificationRun,
                RemoteCategoryClassificationRun.id
                == CriterionScoringRun.remote_category_classification_run_id,
            )
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
                CriterionScoringRun.finished_at.is_not(None),
                RemoteCategoryClassificationRun.status == ScanStatus.SUCCESS,
            )
            # Gefiltert wird VOR der Ordnung - sonst verdraengte ein neuerer unpassender Lauf den
            # aelteren gueltigen. `mode` bleibt ungefiltert: eine Remote-Phase gibt es nur bei
            # Cloud, also zaehlen auch Altzeilen von vor der Laufwahl.
            .order_by(CriterionScoringRun.finished_at.desc(), CriterionScoringRun.id.desc())
            .limit(1)
        )
    ).first()

    eye_candidate = (
        await session.execute(
            select(
                CriterionScoringRun.started_at,
                CriterionScoringRun.finished_at,
                CriterionScoringRun.eye_photos_total,
                CriterionScoringRun.eye_photos_processed,
            )
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.mode == ClassificationMode.EYE,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
                CriterionScoringRun.finished_at.is_not(None),
            )
            .order_by(CriterionScoringRun.finished_at.desc(), CriterionScoringRun.id.desc())
            .limit(1)
        )
    ).first()

    remote_rows = (
        await session.execute(
            select(
                RemoteCategoryClassificationRun.model,
                RemoteCategoryClassificationRun.api_calls,
            ).where(
                RemoteCategoryClassificationRun.project_id == project_id,
                RemoteCategoryClassificationRun.status == ScanStatus.SUCCESS,
            )
        )
    ).all()

    cloud_run = None
    if cloud_candidate is not None:
        started_at, finished_at, remote_photos_total, remote_api_calls = cloud_candidate
        cloud_run = CloudRunFacts(
            duration_seconds=_duration_seconds(started_at, finished_at),
            remote_photos_total=remote_photos_total,
            remote_api_calls=remote_api_calls,
        )

    eye_run = None
    if eye_candidate is not None:
        started_at, finished_at, eye_photos_total, eye_photos_processed = eye_candidate
        eye_run = EyeRunFacts(
            duration_seconds=_duration_seconds(started_at, finished_at),
            eye_photos_total=eye_photos_total,
            eye_photos_processed=eye_photos_processed,
        )

    # Vollstaendig oder `null`: eine Luecke macht aus der Summe eine Zahl, die zu klein ist, und
    # eine zu kleine Zahl traegt die Ausbauentscheidung nicht.
    if not remote_rows or any(calls is None for _, calls in remote_rows):
        remote_api_calls_total = None
    else:
        remote_api_calls_total = sum(calls for _, calls in remote_rows if calls is not None)

    return RunFacts(
        cloud_models=tuple(sorted({model for model, _ in remote_rows if model is not None})),
        cloud_run=cloud_run,
        eye_run=eye_run,
        remote_api_calls_total=remote_api_calls_total,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m photosort.eye_comparison",
        description=(
            "Stellt Eye-Ergebnisse den Cloud-Ergebnissen derselben Fotos gegenüber. "
            "Nur lesend; die Abweichungszeilen gehen ausschliesslich in die --out-Datei."
        ),
    )
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed der Abweichungsauswahl; gleicher Seed, gleiche Beispiele.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Zieldatei für die Abweichungszeilen (muss ausserhalb des Repos liegen).",
    )
    return parser


async def _run(project_id: int, *, seed: int) -> tuple[ComparisonReport, RunFacts]:
    async with async_session_factory() as session:
        photos = await load_comparisons(session, project_id)
        runs = await load_run_facts(session, project_id)
    return summarize(photos, seed=seed), runs


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    out: Path | None = None
    if args.out is not None:
        # VOR jedem Datenbankzugriff und vor dem Schreiben: eine abgelehnte Ausgabe hinterlaesst
        # keine Datei.
        try:
            out = _resolve_out(args.out)
        except ValueError as exc:
            print(f"Fehler: {exc}", file=sys.stderr)
            return 2

    report, runs = asyncio.run(_run(args.project_id, seed=args.seed))
    print(json.dumps(counts_only(report), indent=2, ensure_ascii=False))

    if out is not None:
        out.write_text(
            json.dumps(
                full_report(report, runs, project_id=args.project_id),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Abweichungen: {len(report.deviations)} Zeilen in {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
