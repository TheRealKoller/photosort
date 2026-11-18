"""Die Eye-Phase: Schattenzeilen aus dem Sidecar und ihre Kopfzeilen-Promotion."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker._runs as runs
from photosort.cloud_vision import sanitize_label_text
from photosort.duplicates import survives_ausschuss
from photosort.eye_client import (
    EyeClientLike,
    EyeImageUnreadableError,
    EyeServiceUnavailableError,
    build_eye_client,
)
from photosort.eye_mapping import (
    MAPPING_VERSION as EYE_MAPPING_VERSION,
)
from photosort.eye_mapping import (
    MODEL_REVISION as EYE_MODEL_REVISION,
)
from photosort.eye_mapping import (
    EyeAnalysis,
)
from photosort.eye_mapping import (
    analyze as map_eye_analysis,
)
from photosort.models import (
    ClassificationPhase,
    CriterionScoringRun,
    MotifAssessmentSource,
    Photo,
    PhotoEyeFineLabel,
    PhotoEyeMotifStrength,
    PhotoEyeResult,
    PhotoScore,
    Project,
)
from photosort.motif_strengths import upsert_assessment
from photosort.remote_classification import MAX_FINE_LABEL_LENGTH
from photosort.thumbnails import variant_path

# --- Eye-Sidecar (Spec 0609, ADR 0138) ------------------------------------------------------

# Fortschritt wird in Bloecken committet - Muster von `persons_*`. Die ERGEBNISZEILEN bleiben bis
# zum Phasenende ungeschrieben (eine Transaktion), nur der Zaehler wandert frueher.
EYE_PROGRESS_COMMIT_BATCH_SIZE = 20


def _sanitized_eye_labels(analysis: EyeAnalysis) -> list[tuple[str, float]]:
    """Eyes Feinlabels als Text, den die Oberflaeche gefahrlos rendern kann (S12).

    Dieselbe Sanierung und dieselbe Laengengrenze wie der Cloud-Pfad - eine zweite Fassung liefe
    beim naechsten Sonderzeichen auseinander. Leere Texte und Doppelungen fallen weg; die
    Reihenfolge bleibt die von `fine_labels()` (staerkster zuerst)."""
    labels: list[tuple[str, float]] = []
    seen: set[str] = set()
    for raw, confidence in analysis.fine_labels:
        sanitized = sanitize_label_text(raw)
        if not sanitized or len(sanitized) > MAX_FINE_LABEL_LENGTH or sanitized in seen:
            continue
        seen.add(sanitized)
        labels.append((sanitized, confidence))
    return labels


async def _write_eye_shadow_rows(
    session: AsyncSession,
    analyses: Mapping[int, EyeAnalysis],
    *,
    computed_at: datetime,
) -> None:
    """Der Schattensatz: je Foto Kopfzeile, acht Staerken, die Feinlabels.

    Loeschen-dann-Schreiben statt zeilenweisem Mischen: der Vektor eines Fotos ist vollstaendig
    oder er existiert nicht, und ein Motiv, das der neue Lauf nicht mehr nennt, darf nicht mit
    seinem alten Wert stehen bleiben."""
    photo_ids = list(analyses)
    if not photo_ids:
        return
    await session.execute(
        delete(PhotoEyeMotifStrength).where(PhotoEyeMotifStrength.photo_id.in_(photo_ids))
    )
    await session.execute(
        delete(PhotoEyeFineLabel).where(PhotoEyeFineLabel.photo_id.in_(photo_ids))
    )
    await session.execute(delete(PhotoEyeResult).where(PhotoEyeResult.photo_id.in_(photo_ids)))
    await session.flush()

    for photo_id, analysis in analyses.items():
        session.add(
            PhotoEyeResult(
                photo_id=photo_id,
                excluded_document=analysis.excluded_document,
                album_level=analysis.album_level,
                model_revision=EYE_MODEL_REVISION,
                mapping_version=EYE_MAPPING_VERSION,
                computed_at=computed_at,
            )
        )
    # `flush` vor den Kindern: ihr Fremdschluessel zeigt auf die Kopfzeile.
    await session.flush()

    for photo_id, analysis in analyses.items():
        for motif_key, strength in analysis.motif_strengths.items():
            session.add(
                PhotoEyeMotifStrength(photo_id=photo_id, motif_key=motif_key, strength=strength)
            )
        for label, confidence in _sanitized_eye_labels(analysis):
            session.add(PhotoEyeFineLabel(photo_id=photo_id, label=label, confidence=confidence))


async def _run_eye_phase(
    session: AsyncSession,
    run: CriterionScoringRun,
    project: Project,
    cache_dir: Path,
    *,
    build_client: Callable[[], EyeClientLike] = build_eye_client,
) -> None:
    """Der Teilschritt `eye`: Schattenzeilen fuer die ueberlebenden, lesbaren Fotos, die noch keine
    Eye-Zeile haben, und deren Kopfzeilen-Promotion (Spec 0609, Spec 0621).

    Reihenfolge und Grenzen:

    * NACHHOLEN, NICHT NEUBEWERTEN: Kandidat ist nur, wer ueberlebt, lesbar ist UND noch keine
      Zeile in `photo_eye_results` hat. Ein bereits ausgewertetes Foto wird kein zweites Mal an den
      Dienst geschickt; seine Zeile behaelt `computed_at`, `mapping_version` und ihre Werte, und
      seine Kopfzeile wird nicht befördert. `eye_photos_total` ist damit die Nachhol-Menge.
    * SEQUENZIELL, ein Client, 30 s je Aufruf, kein Retry. Ein Modell, eine Anfrage - und ein
      Test haelt fest, dass nie zwei Aufrufe gleichzeitig laufen.
    * Die Gesundheitspruefung laeuft auch bei NULL Kandidaten: Ein Lauf, der den Dienst gar nicht
      erst anspricht, meldete sonst Erfolg, ohne je geprueft zu haben, ob er erreichbar waere.
    * ALLE Analysen zuerst in den Speicher, dann EINE Transaktion fuer Schattensaetze und
      Promotion. Bricht die Phase, ist nichts geschrieben: kein halber Schattensatz, keine
      Promotion, Lauf `FAILED`.
    * Ein einzelnes unlesbares Bild - keine `display`-Variante oder vom Dienst nicht dekodierbar
      (`EyeImageUnreadableError`) - wird uebersprungen und gezaehlt: `eye_photos_processed`
      bleibt dann unter `eye_photos_total`. Jeder andere Fehler bricht die Phase ab.
    * Die Promotion laeuft ueber `upsert_assessment`, das die Rangfolge `local < eye < cloud`
      selbst durchsetzt. Eine Cloud-Kopfzeile bleibt damit unberuehrt und die Schattenzeile steht
      daneben - genau die Zusage aus S8.
    * Geschrieben wird NICHTS in `photo_album_suitability`, `photo_fine_labels` oder
      `fine_labels`: Die Eye-Stufe ist eine Schattenzeile in eigener Tabelle. Sie zaehlt im
      Entwurf genau dann, wenn der Lauf sie als seine Quelle eingefroren hat (ADR 0144);
      `album_stage.load_album_levels` liest sie dann von dort."""
    photos = (
        (
            await session.execute(
                select(Photo)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(
                    Photo.project_id == project.id,
                    survives_ausschuss(),
                    # Die Luecke ist das Praedikat, nicht ein Filter nach dem Laden: Der Dienst
                    # wird je Foto bezahlt, und ohne diese Bedingung schickte jeder Lauf den
                    # gesamten Bestand erneut.
                    ~exists().where(PhotoEyeResult.photo_id == Photo.id),
                )
            )
        )
        .scalars()
        .all()
    )

    runs._set_phase(run, ClassificationPhase.EYE)
    run.eye_photos_total = len(photos)
    run.eye_photos_processed = 0
    await session.commit()

    client = build_client()
    try:
        if not await client.health():
            raise EyeServiceUnavailableError("Die Eye-Auswertung ist nicht gesund.")
        analyses: dict[int, EyeAnalysis] = {}
        for photo in photos:
            path = variant_path(cache_dir, photo.id, photo.etag, "display")
            if not path.exists():
                continue
            try:
                payload = await client.analyze(path.read_bytes())
            except EyeImageUnreadableError:
                continue
            # Eine Antwort ohne Aussage (fehlende Albumstufe) ist ein Defekt des Dienstes, kein
            # unlesbares Bild - `EyeMappingError` bricht die Phase ab.
            analyses[photo.id] = map_eye_analysis(payload, EYE_MAPPING_VERSION)
            run.eye_photos_processed = len(analyses)
            if len(analyses) % EYE_PROGRESS_COMMIT_BATCH_SIZE == 0:
                run.last_progress_at = runs._now_utc()
                await session.commit()

        computed_at = runs._now_utc()
        await _write_eye_shadow_rows(session, analyses, computed_at=computed_at)
        for photo_id, analysis in analyses.items():
            await upsert_assessment(
                session,
                photo_id,
                source=MotifAssessmentSource.EYE,
                strengths=analysis.motif_strengths,
                excluded_document=analysis.excluded_document,
                provider=None,
                computed_at=computed_at,
            )
        run.eye_photos_processed = len(analyses)
        await session.commit()
    finally:
        await client.aclose()
