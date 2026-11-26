"""Kandidatenmengen der kostenpflichtigen Läufe, als eigene Zählung geschätzt.

Dieses Modul liegt außerhalb der HTTP-Schicht, weil `criterion_probe.py` dieselben Zahlen braucht
und ein Endpunkt-Modul kein Ort für einen von mehreren Seiten benutzten Baustein ist. Es enthält
nur Datenbank-Zählungen: kein `fastapi`, kein Worker-Import.

SICHERHEIT: Jede Zählung ist eine bewusste DUPLIKATION derselben Bedingung wie im Lauf,
und deshalb ändern sich beide Stellen in derselben Änderung. Eine Schätzung, die eine andere Menge
zählt als der Lauf sendet, ist eine falsche Grundlage für die Freigabe einer kostenpflichtigen
Aktion; die Tests prüfen deshalb Mengengleichheit gegen den Lauf über demselben Datenbestand.
"""

from __future__ import annotations

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.criteria import LANDMARK_CANDIDATE_CRITERION_KEYS, is_landmark_candidate
from photosort.duplicates import survives_ausschuss
from photosort.models import (
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoEyeResult,
    PhotoMotifAssessment,
    PhotoScore,
)


async def count_remote_category_candidates(session: AsyncSession, project_id: int) -> int:
    """Ermittelt über dieselbe Kandidaten-Selektion wie der tatsächliche Lauf
    (worker/remote_categories.py::select_remote_category_candidates), als eigenstaendige kleine
    Query dupliziert: dieses Modul importiert das Worker-Paket nicht.

    Ein einzelnes `COUNT` mit `NOT EXISTS`, komplett serverseitig ausgewertet - keine Zeile
    verlaesst die Datenbank, auch nicht bei einem grossen Projekt.

    SICHERHEIT: eine bewusste DUPLIKATION derselben Bedingung, und deshalb aendern sich beide
    Stellen in derselben Aenderung. Das Kriterium ist ZUSAMMENGESETZT - eine Kopfzeile mit
    `source='cloud'` UND eine Albumtauglichkeitszeile; nicht das bloße Vorhandensein einer
    Kopfzeile (der Kriterien-Lauf schreibt lokale). Eine Schaetzung, die eine andere Menge zaehlt
    als der Lauf sendet, ist eine falsche Grundlage fuer die Freigabe einer kostenpflichtigen
    Aktion.

    Die Negation der KONJUNKTION wird per De Morgan zur DISJUNKTION: Kandidat ist, wem eines von
    beiden fehlt. Eine falsch geklammerte Negation (`~(a & b)` als `~a & ~b` gelesen) zaehlt still
    eine andere Menge - der Test prueft deshalb MENGENGLEICHHEIT gegen den Worker-Pfad ueber
    demselben Datenbestand, nicht zwei getrennt hingeschriebene Erwartungswerte."""
    cloud_assessed = exists().where(
        PhotoMotifAssessment.photo_id == Photo.id,
        PhotoMotifAssessment.source == MotifAssessmentSource.CLOUD,
    )
    album_rated = exists().where(PhotoAlbumSuitability.photo_id == Photo.id)
    result = await session.execute(
        select(func.count())
        .select_from(Photo)
        .join(PhotoScore, PhotoScore.photo_id == Photo.id)
        .where(
            Photo.project_id == project_id,
            # SICHERHEIT: DASSELBE Praedikat wie im Lauf. Es folgt der Auswahl nicht von selbst -
            # dies ist eine eigene Anweisung, und sie muss dieselbe Menge zaehlen, die der Lauf
            # sendet.
            survives_ausschuss(),
            or_(~cloud_assessed, ~album_rated),
        )
    )
    return result.scalar_one()


async def count_landmark_candidates(session: AsyncSession, project_id: int) -> int:
    """Der Landmark-Anteil der Kostenschätzung.

    Zaehlt Ausschuss-Ueberlebende, deren BEREITS GESPEICHERTE Kriterien-Werte
    `criteria.py::is_landmark_candidate` erfuellen und die noch keine `landmark`-Zeile haben -
    dieselbe reine Schwellenwert-Funktion, die auch der Live-Lauf ueber
    worker/_criterion/landmark.py::select_landmark_candidates nutzt (kein zweiter, auseinanderlaufender

    STRUKTURELL EINE SCHAETZUNG, keine Vorausberechnung: die Landmark-Kandidaten des kommenden
    Laufs ergeben sich aus Kriterien-Werten, die genau dieser Lauf erst neu berechnet. Vor dem
    allerersten Lauf eines Projekts liegen gar keine Vorwerte vor und die Zahl ist 0; die
    Oberflaeche weist sie als Schaetzung aus.

    Die Schwellenwert-Pruefung laeuft in Python, nie als SQL-Ausdruck: `is_landmark_candidate`
    ist die geteilte Quelle der Wahrheit, eine SQL-Nachbildung der Schwellenwerte waere die
    zweite, auseinanderlaufende Stelle. Geladen werden nur die beiden relevanten
    Kriterien-Zeilen je Foto, nicht die vollen Fotos."""
    already_scored = (
        select(PhotoCriterionScore.photo_id)
        .join(Photo, Photo.id == PhotoCriterionScore.photo_id)
        .where(Photo.project_id == project_id, PhotoCriterionScore.criterion_key == "landmark")
    )
    rows = (
        await session.execute(
            select(
                PhotoCriterionScore.photo_id,
                PhotoCriterionScore.criterion_key,
                PhotoCriterionScore.value,
            )
            .join(Photo, Photo.id == PhotoCriterionScore.photo_id)
            .join(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(
                Photo.project_id == project_id,
                # SICHERHEIT: dieselbe Begruendung wie eine Funktion weiter oben. Der
                # Sehenswuerdigkeits-Teilschritt wird vom Kriterien-Lauf gespeist, und dessen
                # Fotoauswahl traegt dasselbe Praedikat.
                survives_ausschuss(),
                PhotoCriterionScore.criterion_key.in_(LANDMARK_CANDIDATE_CRITERION_KEYS),
                PhotoCriterionScore.photo_id.not_in(already_scored),
            )
        )
    ).all()

    values_by_photo: dict[int, dict[str, float]] = {}
    for photo_id, criterion_key, value in rows:
        values_by_photo.setdefault(photo_id, {})[criterion_key] = value
    return sum(1 for values in values_by_photo.values() if is_landmark_candidate(values))


async def count_eye_candidates(session: AsyncSession, project_id: int) -> int:
    """Die Kandidatenmenge der Eye-Phase: Ausschuss-Überlebende mit Bewertungszeile, die noch
    KEINE Eye-Zeile haben - die Nachhol-Menge, nicht der Bestand.

    Dieselbe Bedingung wie `worker/_criterion/eye.py::run_eye_phase`, als eigenstaendige kleine
    Query dupliziert - dieselbe Begruendung wie bei `count_remote_category_candidates`: dieses
    Modul importiert das Worker-Paket nicht. Eine Schaetzung, die eine andere Menge zaehlt als
    der Lauf, waere eine falsche Grundlage: Sie verspraeche Kosten fuer Fotos, die der Lauf gar
    nicht mehr an den Dienst schickt."""
    result = await session.execute(
        select(func.count())
        .select_from(Photo)
        .join(PhotoScore, PhotoScore.photo_id == Photo.id)
        .where(
            Photo.project_id == project_id,
            survives_ausschuss(),
            ~exists().where(PhotoEyeResult.photo_id == Photo.id),
        )
    )
    return result.scalar_one()
