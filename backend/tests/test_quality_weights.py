"""Die Herkunft der Qualitaetsgewichte: geltende Fassung, Vorgaengerfassung, Schreibstelle
(Spec 0432, ADR 0100).

DIE UEBERLAGERUNG WIRD IN BEIDE RICHTUNGEN GEPRUEFT (G2), und das ist die tragende Zusage dieses
Moduls: Ein den Startwerten unbekannter Schluessel der Fassung wird VERWORFEN, ein der Fassung
unbekannter Startwertschluessel behaelt seinen Startwert. Ein `{**startwerte, **fassung}` besaesse
nur die zweite Haelfte - und genau das ist der Weg, auf dem ein entfallenes oder ein
Inhaltskriterium ein Gewicht behielte.

Geprueft wird durchgehend gegen eine UEBERGEBENE Startwerttabelle und nicht gegen die
Modulkonstante: Sonst waere "ein Kriterium kommt spaeter hinzu" nur per `monkeypatch` erreichbar.

S12 - KEIN NICHT-ENDLICHER UND KEIN NICHT-POSITIVER WERT erreicht die Persistenz, und der
Lesepfad nimmt keinen an. Ein gespeichertes `NaN` kommt durch jede Schranke von `quality.py`:
`total_weight <= 0` ist dafuer falsch, `min`/`max` reichen es durch, `compute_quality_score`
liefert `NaN`, und die Rangfolge ALLER Projekte wird beliebig - ohne Fehler, ohne Logzeile.
"""

from __future__ import annotations

import math

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import QualityWeightEntry, QualityWeightSet, QualityWeightSetOrigin, User
from photosort.quality import QUALITY_CRITERION_WEIGHTS
from photosort.quality_weights import (
    effective_weights,
    latest_weight_set,
    overlay_weights,
    previous_weights,
    store_weights,
)

_BASELINE = {"sharpness": 1.0, "exposure": 1.0, "aesthetics": 1.0}


async def _user(session: AsyncSession, username: str = "daniel") -> int:
    user = User(username=username, password_hash="x")
    session.add(user)
    await session.flush()
    return user.id


class TestTheOverlayRunsInBothDirections:
    """G2, als REINE Funktion - sie traegt die Aussage, der Ladepfad reicht sie nur durch."""

    def test_a_key_the_baseline_does_not_know_is_discarded(self) -> None:
        """Die Haelfte, die ein `{**baseline, **stored}` NICHT besitzt. Ohne sie geriete ein
        Kriterium mit Inhaltsaussage in den Qualitaetswert, sobald es je in einer Fassung
        stand - und `test_quality.py::TestTheWeightTableCarriesNoContentSignal` wuerde darueber
        nicht rot, weil es die Modulkonstante prueft und nicht den wirksamen Satz."""
        overlaid = overlay_weights(_BASELINE, {"content_people": 5.0, "sharpness": 1.2})

        assert set(overlaid) == set(_BASELINE)
        assert "content_people" not in overlaid

    def test_a_baseline_key_the_set_does_not_know_keeps_its_starting_value(self) -> None:
        """Die andere Haelfte: Ein spaeter ergaenztes Kriterium steht in keiner gespeicherten
        Fassung und faellt trotzdem nicht aus dem wirksamen Satz."""
        overlaid = overlay_weights(_BASELINE, {"sharpness": 1.2})

        assert overlaid == {"sharpness": 1.2, "exposure": 1.0, "aesthetics": 1.0}

    def test_the_effective_key_set_is_always_exactly_the_baseline_key_set(self) -> None:
        """Beide Haelften PAARWEISE in einem Fall - die erste allein bestuende auch gegen
        `{**baseline, **stored}`."""
        overlaid = overlay_weights(_BASELINE, {"content_people": 5.0, "horizont": 0.7})

        assert set(overlaid) == set(_BASELINE)
        assert overlaid["exposure"] == 1.0

    def test_the_baseline_is_not_mutated(self) -> None:
        """Die Startwerttabelle ist im Betrieb die Modulkonstante `QUALITY_CRITERION_WEIGHTS`.
        Eine Ueberlagerung, die sie veraenderte, machte die erste Anpassung eines Prozesses zur
        letzten - jede spaetere Ableitung rechnete danach gegen bereits verschobene Startwerte."""
        baseline = dict(_BASELINE)

        overlay_weights(baseline, {"sharpness": 1.2})

        assert baseline == _BASELINE


class TestTheOverlayRefusesAPoisonedValue:
    """S12 am LESEPFAD. Der Schreibpfad weist denselben Wert ab; beide Schranken stehen, weil
    eine Zeile auch ueber rohes SQL oder eine spaetere Migration in die Tabelle geraten kann."""

    @pytest.mark.parametrize(
        "poisoned", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0], ids=str
    )
    def test_it_keeps_the_starting_value_instead_of_letting_the_value_through(
        self, poisoned: float
    ) -> None:
        """KEIN Abbruch, sondern der Startwert: Ein `NaN` in der Persistenz darf nicht dazu
        fuehren, dass jeder Lauf des Systems mit einer Ausnahme endet - er darf nur nicht
        wirken."""
        overlaid = overlay_weights(_BASELINE, {"sharpness": poisoned})

        assert overlaid["sharpness"] == 1.0

    def test_a_healthy_value_beside_a_poisoned_one_still_applies(self) -> None:
        """Die Gegenprobe: Die Schranke gilt JE KRITERIUM und nicht je Fassung - sonst machte ein
        einziger vergifteter Wert eine ganze uebernommene Anpassung still wirkungslos."""
        overlaid = overlay_weights(_BASELINE, {"sharpness": float("nan"), "exposure": 1.2})

        assert overlaid == {"sharpness": 1.0, "exposure": 1.2, "aesthetics": 1.0}


class TestTheEffectiveWeightsWithoutAnyStoredSet:
    async def test_the_starting_values_apply_unchanged(self, db_session: AsyncSession) -> None:
        """G1: Ohne eine einzige gespeicherte Fassung gelten die Startwerte - GLEICHHEIT, nicht
        `approx`. Keine Migration schreibt sie ein; ein eingeschriebener Vorgabewert waere von
        einer uebernommenen Anpassung nicht mehr zu unterscheiden."""
        assert await effective_weights(db_session, baseline=_BASELINE) == _BASELINE

    async def test_there_is_no_latest_set(self, db_session: AsyncSession) -> None:
        assert await latest_weight_set(db_session) is None

    async def test_the_previous_weights_fall_back_to_the_starting_values(
        self, db_session: AsyncSession
    ) -> None:
        assert await previous_weights(db_session, baseline=_BASELINE) == _BASELINE


class TestTheLatestSetWins:
    async def test_the_highest_id_applies_and_not_the_newest_timestamp(
        self, db_session: AsyncSession
    ) -> None:
        """ES GILT DIE FASSUNG MIT DER HOECHSTEN `id`. Zwei Fassungen derselben Sekunde sind
        ueber eine Zeit nicht zu ordnen, und es gibt bewusst kein `active`-Kennzeichen, das
        danebentreten koennte."""
        user_id = await _user(db_session)
        await store_weights(
            db_session, weights={"sharpness": 1.2}, user_id=user_id, based_on_event_id=0
        )
        newest = await store_weights(
            db_session, weights={"sharpness": 0.8}, user_id=user_id, based_on_event_id=0
        )
        await db_session.flush()

        assert (await effective_weights(db_session, baseline=_BASELINE))["sharpness"] == 0.8
        assert (await latest_weight_set(db_session)).id == newest.id  # type: ignore[union-attr]


class TestTheStoredSetRefusesAPoisonedValue:
    """S12 am SCHREIBPFAD - bricht LAUT, statt eine Zeile zu hinterlassen, die niemand mehr von
    einer richtigen unterscheidet. Anders als der Lesepfad, der still auf den Startwert
    zurueckfaellt: Hier ist der Wert noch abzuwenden, dort nur noch zu entschaerfen."""

    @pytest.mark.parametrize(
        "poisoned", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0], ids=str
    )
    async def test_it_raises_and_writes_nothing(
        self, db_session: AsyncSession, poisoned: float
    ) -> None:
        user_id = await _user(db_session)

        with pytest.raises(ValueError, match="sharpness"):
            await store_weights(
                db_session,
                weights={"sharpness": poisoned, "exposure": 1.0},
                user_id=user_id,
                based_on_event_id=0,
            )

        assert (await db_session.execute(select(QualityWeightSet))).scalars().all() == []
        assert (await db_session.execute(select(QualityWeightEntry))).scalars().all() == []


class TestTheStoredSetKeepsItsValuesExactly:
    async def test_every_written_weight_is_the_value_that_was_handed_in(
        self, db_session: AsyncSession
    ) -> None:
        """G6: Wird die Anpassung ohne zwischenzeitliche Aenderung uebernommen, sind die
        gespeicherten Werte EXAKT die zuvor angezeigten - Gleichheit, kein `approx`."""
        user_id = await _user(db_session)
        weights = {"sharpness": 1.23, "exposure": 0.77, "aesthetics": 1.0}

        await store_weights(db_session, weights=weights, user_id=user_id, based_on_event_id=41)
        await db_session.flush()

        assert await effective_weights(db_session, baseline=_BASELINE) == weights

    async def test_the_origin_and_the_anchor_are_written(self, db_session: AsyncSession) -> None:
        user_id = await _user(db_session)

        written = await store_weights(
            db_session, weights={"sharpness": 1.1}, user_id=user_id, based_on_event_id=7
        )
        await db_session.flush()

        assert written.origin is QualityWeightSetOrigin.FEEDBACK
        assert written.based_on_event_id == 7
        assert written.reverts_set_id is None
        assert written.created_by_user_id == user_id


class TestThePreviousWeights:
    async def test_with_exactly_one_stored_set_they_are_the_starting_values(
        self, db_session: AsyncSession
    ) -> None:
        """Die erste Fassung hat als Vorgaengerin keine Fassung, sondern den Zustand davor - und
        der ist der Startwertsatz. Ohne diesen Rueckfall waere die erste Anpassung nicht
        zuruecknehmbar."""
        user_id = await _user(db_session)
        await store_weights(
            db_session, weights={"sharpness": 1.2}, user_id=user_id, based_on_event_id=0
        )
        await db_session.flush()

        assert await previous_weights(db_session, baseline=_BASELINE) == _BASELINE

    async def test_with_two_stored_sets_they_are_the_values_of_the_older_one(
        self, db_session: AsyncSession
    ) -> None:
        user_id = await _user(db_session)
        await store_weights(
            db_session, weights={"sharpness": 1.2}, user_id=user_id, based_on_event_id=0
        )
        await store_weights(
            db_session, weights={"sharpness": 0.8}, user_id=user_id, based_on_event_id=0
        )
        await db_session.flush()

        assert (await previous_weights(db_session, baseline=_BASELINE))["sharpness"] == 1.2

    async def test_they_are_overlaid_over_the_baseline_too(self, db_session: AsyncSession) -> None:
        """Dieselbe Ueberlagerung in beide Richtungen wie beim geltenden Satz (G2): Sonst
        brachte ausgerechnet das Zuruecksetzen ein entfallenes Kriterium zurueck."""
        user_id = await _user(db_session)
        weight_set = QualityWeightSet(
            created_by_user_id=user_id,
            origin=QualityWeightSetOrigin.FEEDBACK,
            based_on_event_id=0,
            entries=[QualityWeightEntry(criterion_key="content_people", weight=5.0)],
        )
        db_session.add(weight_set)
        await store_weights(
            db_session, weights={"sharpness": 0.8}, user_id=user_id, based_on_event_id=0
        )
        await db_session.flush()

        assert await previous_weights(db_session, baseline=_BASELINE) == _BASELINE


class TestTheRevertIsANewSet:
    async def test_it_writes_a_new_set_and_deletes_none(self, db_session: AsyncSession) -> None:
        """G10: Es wird NIE eine Fassung geloescht - die Kette bleibt lueckenlos, und die Anzeige
        kann jederzeit sagen, welche Fassung wann galt."""
        user_id = await _user(db_session)
        first = await store_weights(
            db_session, weights={"sharpness": 1.2}, user_id=user_id, based_on_event_id=0
        )
        await db_session.flush()

        await store_weights(
            db_session,
            weights=await previous_weights(db_session, baseline=_BASELINE),
            user_id=user_id,
            origin=QualityWeightSetOrigin.REVERT,
            reverts_set_id=first.id,
        )
        await db_session.flush()

        stored = (
            (await db_session.execute(select(QualityWeightSet).order_by(QualityWeightSet.id)))
            .scalars()
            .all()
        )
        assert [entry.origin for entry in stored] == [
            QualityWeightSetOrigin.FEEDBACK,
            QualityWeightSetOrigin.REVERT,
        ]
        assert stored[1].reverts_set_id == first.id
        assert stored[1].based_on_event_id is None
        assert await effective_weights(db_session, baseline=_BASELINE) == _BASELINE

    async def test_reverting_twice_returns_to_the_values_the_first_revert_started_from(
        self, db_session: AsyncSession
    ) -> None:
        """DER UMSCHALTER (G10), vollstaendige Wertefolge: Der zweite Druck fuehrt auf die Werte
        zurueck, von denen der erste zurueckgesetzt hat - er geht NICHT eine weitere Fassung
        rueckwaerts."""
        user_id = await _user(db_session)
        await store_weights(
            db_session, weights={"sharpness": 1.2}, user_id=user_id, based_on_event_id=0
        )
        adjusted = await store_weights(
            db_session, weights={"sharpness": 0.8}, user_id=user_id, based_on_event_id=0
        )
        await db_session.flush()

        first_revert = await store_weights(
            db_session,
            weights=await previous_weights(db_session, baseline=_BASELINE),
            user_id=user_id,
            origin=QualityWeightSetOrigin.REVERT,
            reverts_set_id=adjusted.id,
        )
        await db_session.flush()
        assert (await effective_weights(db_session, baseline=_BASELINE))["sharpness"] == 1.2

        await store_weights(
            db_session,
            weights=await previous_weights(db_session, baseline=_BASELINE),
            user_id=user_id,
            origin=QualityWeightSetOrigin.REVERT,
            reverts_set_id=first_revert.id,
        )
        await db_session.flush()

        assert (await effective_weights(db_session, baseline=_BASELINE))["sharpness"] == 0.8


class TestTheModuleDefaultsToTheProjectBaseline:
    async def test_without_a_baseline_argument_the_quality_module_table_applies(
        self, db_session: AsyncSession
    ) -> None:
        """DIE eine benannte Stelle fuer die Startwerte bleibt `quality.py`; dieses Modul
        wechselt nur die Herkunft des Werts, nie den Schluesselsatz."""
        effective = await effective_weights(db_session)

        assert effective == QUALITY_CRITERION_WEIGHTS
        assert all(math.isfinite(weight) and weight > 0 for weight in effective.values())
