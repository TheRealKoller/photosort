"""Der EINE Lesepunkt der zaehlenden Albumstufe (ADR 0144).

Welche Stufe fuer ein Foto zaehlt, folgt dem am Lauf eingefrorenen Verfahren
(`CriterionScoringRun.album_level_source`): `cloud` liest `photo_album_suitability.level`, `eye`
liest `photo_eye_results.album_level`. Rangbildung, Tausch-Diagnose und Feedback-Ereignisse lesen
die Stufe ausschliesslich hier; eine zweite Lesestelle wuerde beim naechsten Verfahrenswechsel
still die andere Quelle zaehlen (Strukturwaechter in `tests/test_album_stage.py`).

Kein Rueckfall: Fehlt einem Foto die Stufe der Quelle, fehlt es im Ergebnis - auch wenn es eine
Stufe des anderen Verfahrens traegt. Ein lokal gebildeter Ersatzwert existiert nicht.

Reiner Datenbank-Lesepfad (Security S1, S5): Dieses Modul importiert keinen Netzwerk-, Vision-
oder Eye-Client. Ein Request-Pfad, der hier liest, loest damit nie Modellarbeit aus.

Keine Aufloesung (Security S3): Die Foto-Ids muessen bereits projektgebunden sein (etwa aus den
Rangzeilen des Laufs). Das Ergebnis-Dict ist eine Abbildung, keine Mitgliedschaftsaussage.
"""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import CategoryMethod, PhotoAlbumSuitability, PhotoEyeResult


async def load_album_levels(
    session: AsyncSession, source: CategoryMethod, photo_ids: Collection[int]
) -> dict[int, int]:
    """Die zaehlende Stufe (1-5) je Foto-Id aus der Tabelle des Verfahrens `source`.

    Leere Eingabe ergibt `{}` OHNE Abfrage."""
    if not photo_ids:
        return {}
    if source is CategoryMethod.EYE:
        statement = select(PhotoEyeResult.photo_id, PhotoEyeResult.album_level).where(
            PhotoEyeResult.photo_id.in_(photo_ids)
        )
    else:
        statement = select(PhotoAlbumSuitability.photo_id, PhotoAlbumSuitability.level).where(
            PhotoAlbumSuitability.photo_id.in_(photo_ids)
        )
    return {photo_id: level for photo_id, level in (await session.execute(statement)).all()}
