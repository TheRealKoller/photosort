"""Die Struktur der beiden Gewichtstabellen am Modell (Spec 0432, ADR 0100).

Die Verhaltensseite (was `effective_weights`/`previous_weights`/`store_weights` tun) steht in
`test_quality_weights.py`; hier stehen die Zusagen, die kein Verhaltensfall roetet.

ES GILT DIE FASSUNG MIT DER HOECHSTEN `id` - es gibt kein `active`-Kennzeichen, das danebentreten
und mit ihr auseinanderlaufen koennte. Diese Abwesenheit ist eine Aussage und wird hier als
Spaltensatz-Gleichheit festgehalten.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    Project,
    QualityWeightEntry,
    QualityWeightSet,
    QualityWeightSetOrigin,
    ScanStatus,
    ScoringRun,
    User,
)


def _column(model: Any, name: str) -> Any:
    return inspect(model).columns[name]


class TestTheSetCarriesNoActiveFlagAndNoScope:
    def test_the_column_set_is_exactly_the_six_known_columns(self) -> None:
        """GLEICHHEIT, nicht Teilmenge: Ein spaeter ergaenztes `active` traete neben die `id` und
        liefe mit ihr auseinander; ein `project_id` oder ein `scope` machte aus dem global
        geltenden Gewichtssatz still einen projektweisen (G1)."""
        assert {column.key for column in inspect(QualityWeightSet).columns} == {
            "id",
            "created_at",
            "created_by_user_id",
            "origin",
            "based_on_event_id",
            "reverts_set_id",
        }

    def test_the_entry_column_set_is_exactly_the_four_known_columns(self) -> None:
        assert {column.key for column in inspect(QualityWeightEntry).columns} == {
            "id",
            "set_id",
            "criterion_key",
            "weight",
        }


class TestTheReferencesThatAreNone:
    """Zwei Spalten SEHEN wie ein Verweis aus und sind keiner. Beide Aussagen stehen jeweils mit
    ihrer Gegenhaelfte im selben Fall - ohne sie bestuenden sie auch fuer eine Tabelle ganz ohne
    Fremdschluessel."""

    def test_the_anchor_carries_no_foreign_key_while_the_author_does(self) -> None:
        """`based_on_event_id` ist das Zustimmungs-Token auf den zuletzt gesehenen
        Ereignisstand (S6): nie zu einer Zeile aufgeloest, und bei leerem Log `0` - ein Wert, auf
        den kein Fremdschluessel zeigen koennte."""
        assert _column(QualityWeightSet, "based_on_event_id").foreign_keys == set()
        assert _column(QualityWeightSet, "created_by_user_id").foreign_keys != set()

    def test_the_criterion_key_carries_no_foreign_key_while_the_set_binding_does(self) -> None:
        """Freier String aus demselben Grund wie bei `photo_criterion_scores.criterion_key`: Ein
        neues Kriterium erzwingt nie eine Migration."""
        assert _column(QualityWeightEntry, "criterion_key").foreign_keys == set()
        assert _column(QualityWeightEntry, "set_id").foreign_keys != set()


class TestTheWeightTablesHangOnNoProject:
    def test_neither_table_carries_a_path_to_projects(self) -> None:
        """S13, GEGENRICHTUNG: Die beiden Tabellen tragen sieben Zahlen und einen Nutzerverweis,
        keinen Foto-Bezug. Eine Kante nach `projects` machte sie zum Gegenstand der
        Projektloeschung - und die global geltenden Gewichte verschwaenden mit dem ersten
        geloeschten Projekt."""
        for model in (QualityWeightSet, QualityWeightEntry):
            referred = {
                key.column.table.name
                for column in inspect(model).columns
                for key in column.foreign_keys
            }
            assert Project.__tablename__ not in referred, model.__name__


class TestTheRunRemembersItsWeightSet:
    async def test_a_run_without_a_set_stays_writable(self, db_session: AsyncSession) -> None:
        """`NULL` heisst "Startwerte oder Altzeile" - jeder bereits gelaufene Lauf hat mit den
        Startwerten gerechnet und hat keine Fassung, auf die er zeigen koennte."""
        project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/c")
        db_session.add(project)
        await db_session.flush()
        scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
        db_session.add(scoring_run)
        await db_session.flush()
        run = CriterionScoringRun(
            project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
        )
        db_session.add(run)
        await db_session.flush()

        assert run.quality_weight_set_id is None


class TestTheEntriesBelongToTheirSet:
    async def test_deleting_a_set_takes_its_entries_with_it(self, db_session: AsyncSession) -> None:
        """`cascade="all, delete-orphan"`: Ein Eintrag ohne Fassung traegt keine Aussage - welches
        Kriterium wann welches Gewicht hatte, steht allein in der Fassung.

        Geloescht wird eine Fassung im laufenden Betrieb NIE (die Kette bleibt lueckenlos, G10);
        die Kaskade steht hier fuer Testaufbauten und den Fall, dass die Kette je bereinigt
        wird."""
        user = User(username="daniel", password_hash="x")
        db_session.add(user)
        await db_session.flush()
        weight_set = QualityWeightSet(
            created_by_user_id=user.id,
            origin=QualityWeightSetOrigin.FEEDBACK,
            based_on_event_id=0,
            entries=[QualityWeightEntry(criterion_key="sharpness", weight=1.2)],
        )
        db_session.add(weight_set)
        await db_session.flush()

        await db_session.delete(weight_set)
        await db_session.flush()

        assert (await db_session.execute(select(QualityWeightEntry))).scalars().all() == []

    async def test_the_same_criterion_cannot_appear_twice_in_one_set(
        self, db_session: AsyncSession
    ) -> None:
        """Zwei Gewichte fuer dasselbe Kriterium in derselben Fassung waeren zwei Wahrheiten;
        welche gilt, entschiede die Zeilenreihenfolge."""
        user = User(username="daniel", password_hash="x")
        db_session.add(user)
        await db_session.flush()
        weight_set = QualityWeightSet(
            created_by_user_id=user.id,
            origin=QualityWeightSetOrigin.FEEDBACK,
            based_on_event_id=0,
            entries=[
                QualityWeightEntry(criterion_key="sharpness", weight=1.2),
                QualityWeightEntry(criterion_key="sharpness", weight=0.8),
            ],
        )
        db_session.add(weight_set)

        with pytest.raises(IntegrityError):
            await db_session.flush()
