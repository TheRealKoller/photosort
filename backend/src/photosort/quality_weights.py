"""Die Herkunft der Qualitaetsgewichte: geltende Fassung, Vorgaengerfassung, Schreibstelle
(Spec 0432, ADR 0100).

`quality.py::QUALITY_CRITERION_WEIGHTS` bleibt DIE eine benannte Stelle fuer die Startwerte -
dieses Modul wechselt nur die Herkunft des wirksamen Werts, nie den Schluesselsatz.

OHNE EINE EINZIGE GESPEICHERTE FASSUNG GELTEN DIE STARTWERTE (G1). Keine Migration schreibt sie
ein: Ein eingeschriebener Vorgabewert waere von einer uebernommenen Anpassung nicht mehr zu
unterscheiden, und "zurueck auf die Startwerte" hiesse danach "zurueck auf eine Fassung, die
jemand uebernommen hat".

ES GILT DIE FASSUNG MIT DER HOECHSTEN `id`, nie die mit dem juengsten Zeitstempel: Zwei Fassungen
derselben Sekunde sind ueber eine Zeit nicht zu ordnen. Es gibt bewusst kein `active`-Kennzeichen,
das danebentreten und mit der `id` auseinanderlaufen koennte.

DIE UEBERLAGERUNG WIRD IN BEIDE RICHTUNGEN GEPRUEFT (G2): Ein den Startwerten unbekannter
Schluessel der Fassung wird VERWORFEN, ein der Fassung unbekannter Startwertschluessel behaelt
seinen Startwert. Der wirksame Schluesselsatz ist damit immer exakt der Startwertsatz -
insbesondere gelangt kein Kriterium mit Inhaltsaussage in den Qualitaetswert. Ein
`{**startwerte, **fassung}` besaesse nur die zweite Haelfte.

WEDER `commit` NOCH `flush` beim Schreiben: Die Transaktionsgrenze gehoert dem Aufrufer.

S12 - KEIN NICHT-ENDLICHER UND KEIN NICHT-POSITIVER WERT erreicht die Persistenz, und der
Lesepfad nimmt keinen an. Die beiden Schranken sind bewusst verschieden scharf: Der Schreibpfad
bricht LAUT, weil der Wert dort noch abzuwenden ist; der Lesepfad faellt still auf den Startwert
zurueck, weil eine Ausnahme dort jeden Lauf des Systems anhielte. Ein gespeichertes `NaN` kommt
sonst durch jede Schranke von `quality.py`: `total_weight <= 0` ist dafuer falsch, `min`/`max`
reichen es durch, `compute_quality_score` liefert `NaN`, und die Rangfolge ALLER Projekte wird
beliebig - ohne Fehler, ohne Logzeile, bis zum naechsten Lauf unbemerkt.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import QualityWeightEntry, QualityWeightSet, QualityWeightSetOrigin
from photosort.quality import QUALITY_CRITERION_WEIGHTS


def _is_usable(weight: float) -> bool:
    """Ein Gewicht ist brauchbar, wenn es endlich und strikt positiv ist.

    STRIKT POSITIV, nicht "nicht negativ": Ein Gewicht null liesse das Kriterium aus der
    Renormierung in `quality.py::local_correction` ganz herausfallen - ausgeschaltet ist etwas
    anderes als abgewertet. Ein negatives waere die ausgeschlossene Invertierung."""
    return math.isfinite(weight) and weight > 0.0


def overlay_weights(baseline: Mapping[str, float], stored: Mapping[str, float]) -> dict[str, float]:
    """Die wirksamen Gewichte: die gespeicherte Fassung UEBERLAGERT ueber die Startwerte.

    DER ERGEBNIS-SCHLUESSELSATZ IST EXAKT DER DES STARTWERTS, in beide Richtungen (G2). Iteriert
    wird ueber die Startwerte, nie ueber die gespeicherten Eintraege.

    Ein gespeicherter Wert, der die Schranke aus `_is_usable` verfehlt, wird VERWORFEN und der
    Startwert bleibt stehen - je Kriterium und nicht je Fassung: Ein einziger vergifteter Wert
    machte sonst eine ganze uebernommene Anpassung still wirkungslos."""
    overlaid: dict[str, float] = {}
    for key, start in baseline.items():
        candidate = stored.get(key)
        overlaid[key] = candidate if candidate is not None and _is_usable(candidate) else start
    return overlaid


async def latest_weight_set(session: AsyncSession) -> QualityWeightSet | None:
    """Die GELTENDE Fassung, oder `None` - dann gelten die Startwerte.

    Ueber die hoechste `id`, siehe Modulkopf."""
    return (
        await session.execute(
            select(QualityWeightSet).order_by(QualityWeightSet.id.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def _entries_of(session: AsyncSession, set_id: int) -> dict[str, float]:
    rows = (
        await session.execute(
            select(QualityWeightEntry.criterion_key, QualityWeightEntry.weight).where(
                QualityWeightEntry.set_id == set_id
            )
        )
    ).all()
    return {criterion_key: weight for criterion_key, weight in rows}


async def effective_weights(
    session: AsyncSession, *, baseline: Mapping[str, float] | None = None
) -> dict[str, float]:
    """Die Gewichte, mit denen JETZT gerechnet wird.

    `baseline` ist ein Parameter und nicht fest die Modulkonstante, damit "ein Kriterium kommt
    spaeter hinzu" ohne `monkeypatch` pruefbar bleibt."""
    start = QUALITY_CRITERION_WEIGHTS if baseline is None else baseline
    current = await latest_weight_set(session)
    if current is None:
        # GLEICHHEIT mit den Startwerten, nicht ihr Produkt mit 1.0: Der Nullzustand IST der
        # Startwertsatz und nicht etwas, das ihm bis auf Rundung gleicht.
        return dict(start)
    return overlay_weights(start, await _entries_of(session, current.id))


async def previous_weights(
    session: AsyncSession, *, baseline: Mapping[str, float] | None = None
) -> dict[str, float]:
    """Die Werte der VORGAENGERFASSUNG der geltenden - Rueckfall auf die Startwerte.

    Der Rueckfall ist nicht Bequemlichkeit: Die erste Fassung hat als Vorgaengerin keine Fassung,
    sondern den Zustand davor, und der ist der Startwertsatz. Ohne ihn waere ausgerechnet die
    erste Anpassung nicht zuruecknehmbar.

    Ueberlagert wird auch hier in beide Richtungen - sonst brachte ausgerechnet das Zuruecksetzen
    ein entfallenes Kriterium zurueck."""
    start = QUALITY_CRITERION_WEIGHTS if baseline is None else baseline
    predecessor = (
        await session.execute(
            select(QualityWeightSet).order_by(QualityWeightSet.id.desc()).offset(1).limit(1)
        )
    ).scalar_one_or_none()
    if predecessor is None:
        return dict(start)
    return overlay_weights(start, await _entries_of(session, predecessor.id))


async def store_weights(
    session: AsyncSession,
    *,
    weights: Mapping[str, float],
    user_id: int,
    based_on_event_id: int | None = None,
    origin: QualityWeightSetOrigin = QualityWeightSetOrigin.FEEDBACK,
    reverts_set_id: int | None = None,
) -> QualityWeightSet:
    """Legt eine NEUE Fassung an - die einzige Stelle, an der `QualityWeightSet(...)` steht.

    ZURUECKSETZEN IST EINE NEUE FASSUNG mit den Werten der Vorgaengerin, nie ein Loeschen: Die
    Kette bleibt lueckenlos, und der zweite Druck fuehrt auf die Werte zurueck, von denen der
    erste zurueckgesetzt hat (G10).

    S12 am Schreibpfad: Ein nicht endlicher oder nicht positiver Wert bricht mit `ValueError`, und
    es entsteht KEINE Zeile - die Pruefung steht vor dem ersten `session.add`. Eine halb
    geschriebene Fassung waere von einer richtigen nicht mehr zu unterscheiden.

    Weder `commit` noch `flush` - die Transaktionsgrenze gehoert dem Aufrufer."""
    unusable = sorted(key for key, weight in weights.items() if not _is_usable(weight))
    if unusable:
        raise ValueError(
            f"Gewichte muessen endlich und strikt positiv sein; verletzt: {', '.join(unusable)}"
        )

    weight_set = QualityWeightSet(
        created_by_user_id=user_id,
        origin=origin,
        based_on_event_id=based_on_event_id,
        reverts_set_id=reverts_set_id,
        entries=[
            QualityWeightEntry(criterion_key=key, weight=weight) for key, weight in weights.items()
        ],
    )
    session.add(weight_set)
    return weight_set
