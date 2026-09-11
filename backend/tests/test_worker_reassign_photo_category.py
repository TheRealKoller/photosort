from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import worker
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCategoryClassification,
    PhotoCriterionScore,
    PhotoRanking,
    PhotoScore,
    Project,
    ScanStatus,
    ScoringRun,
)
from photosort.ranking import confidence_ordering_score
from photosort.worker import reassign_photo_category

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 7:
# sofortige Wirkung des Overrides - gezielte Partitions-Neusortierung statt vollem Re-Scoring.


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="p")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(session: AsyncSession, project: Project, path: str) -> Photo:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag="etag",
        content_length=1,
        taken_at=now,
        last_modified=now,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _add_criterion_scoring_run(
    session: AsyncSession, project: Project
) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.commit()
    await session.refresh(scoring_run)
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _add_criterion_score(
    session: AsyncSession, photo: Photo, criterion_key: str, value: float
) -> None:
    session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key=criterion_key,
            value=value,
            source=CriterionSource.LOCAL_HEURISTIC,
            computed_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def _add_ranking(
    session: AsyncSession,
    run: CriterionScoringRun,
    photo: Photo,
    *,
    cluster_key: str,
    category_key: str,
    rank_score: float,
    rank_position: int,
    is_primary: bool = True,
) -> PhotoRanking:
    """specs/features/0300-nebenkategorien.md: `is_primary` ist pflichtig - der Default `True`
    haelt alle bestehenden Aufrufe bei ihrer bisherigen Bedeutung (eine Zugehoerigkeit je Foto,
    und die ist die Hauptzeile)."""
    ranking = PhotoRanking(
        criterion_scoring_run_id=run.id,
        photo_id=photo.id,
        cluster_key=cluster_key,
        category_key=category_key,
        rank_score=rank_score,
        rank_position=rank_position,
        is_primary=is_primary,
    )
    session.add(ranking)
    await session.commit()
    await session.refresh(ranking)
    return ranking


async def _rankings_of(
    session: AsyncSession, run: CriterionScoringRun
) -> dict[tuple[int, str], PhotoRanking]:
    """Alle Rangfolgen-Zeilen eines Laufs, geschluesselt ueber `(photo_id, category_key)` - seit
    specs/features/0300-nebenkategorien.md ist `photo_id` allein KEIN eindeutiger Schluessel mehr
    (ein `dict[int, PhotoRanking]` verlaere hier still Zeilen)."""
    rows = (
        (
            await session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    return {(row.photo_id, row.category_key): row for row in rows}


async def _assert_exactly_one_primary_row_per_photo(
    session: AsyncSession, run: CriterionScoringRun
) -> None:
    """Die Invariante, die KEINE Datenbankbedingung traegt (Security-Muss-Kriterium 5 der Spec
    0300): genau eine Zeile mit `is_primary = true` je (Lauf, Foto). Nach JEDER Schreiboperation
    zu pruefen - zwei Hauptzeilen braechen still die Zusage, dass die Summe ueber alle Kategorien
    die Fotoanzahl ergibt."""
    rows = (
        (
            await session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    primaries: dict[int, int] = {}
    for row in rows:
        primaries.setdefault(row.photo_id, 0)
        primaries[row.photo_id] += 1 if row.is_primary else 0
    assert all(count == 1 for count in primaries.values()), primaries


async def _assert_positions_are_gapless(session: AsyncSession, run: CriterionScoringRun) -> None:
    """`rank_position` ist in JEDER beruehrten Partition lueckenlos `1..n` und doppelungsfrei
    (Akzeptanzkriterium 7) - Haupt- und Nebenzeilen werden in EINEM Durchgang sortiert."""
    rows = (
        (
            await session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    positions: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        positions.setdefault((row.cluster_key, row.category_key), []).append(row.rank_position)
    for partition, found in positions.items():
        assert sorted(found) == list(range(1, len(found) + 1)), partition


async def test_an_unchanged_target_set_still_reranks_but_changes_nothing(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VERHALTENSAENDERUNG gegenueber der ersten Fassung (Copilot-Review-Fund zu PR #373):
    frueher stieg die Funktion bei unveraenderter Zielmenge VOR der Neusortierung aus
    (`0 rank_photos-Aufrufe`). Das war falsch - die Daempfung haengt zusaetzlich am
    Override-Zustand, den die Aufrufer vorher setzen bzw. loeschen, und der Mengenvergleich
    uebersah genau diese beiden Wege (Akzeptanzkriterium 22, siehe
    test_api_category_override.py::TestOverrideChangesTheDampeningWithoutChangingTheMembership).

    Der Test haelt deshalb ab hier das Gegenteil fest und bleibt trotzdem eine echte Zusage: die
    Neusortierung LAEUFT (genau einmal, fuer die eine beruehrte Partition), und sie aendert im
    unveraenderten Fall nichts - dieselbe Zeile, dieselbe Kategorie, dieselbe Position, keine
    Loeschung und keine Neuanlage."""
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg")
    await _add_criterion_score(db_session, photo, "sharpness", 0.9)
    before = await _add_ranking(
        db_session,
        run,
        photo,
        cluster_key="c1",
        category_key="people",
        rank_score=0.9,
        rank_position=1,
    )

    calls: list[object] = []
    original_rank_photos = worker.rank_photos

    def spy(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return original_rank_photos(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(worker, "rank_photos", spy)
    await reassign_photo_category(db_session, run.id, photo.id, "c1", "people")

    assert len(calls) == 1
    ranking = (
        await db_session.execute(select(PhotoRanking).where(PhotoRanking.photo_id == photo.id))
    ).scalar_one()
    assert ranking.id == before.id
    assert ranking.category_key == "people"
    assert ranking.rank_position == 1
    assert ranking.is_primary is True


async def test_moving_a_photo_recomputes_rank_in_both_partitions(
    db_session: AsyncSession,
) -> None:
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)

    # Partition A ("people"): zwei Fotos.
    photo_a1 = await _add_photo(db_session, project, "a1.jpg")
    await _add_criterion_score(db_session, photo_a1, "sharpness", 0.9)
    ranking_a1 = await _add_ranking(
        db_session,
        run,
        photo_a1,
        cluster_key="c1",
        category_key="people",
        rank_score=0.9,
        rank_position=1,
    )
    photo_a2 = await _add_photo(db_session, project, "a2.jpg")
    await _add_criterion_score(db_session, photo_a2, "sharpness", 0.5)
    await _add_ranking(
        db_session,
        run,
        photo_a2,
        cluster_key="c1",
        category_key="people",
        rank_score=0.5,
        rank_position=2,
    )

    # Partition B ("landscape"): ein Foto - wird gleich um photo_a2 erweitert.
    photo_b1 = await _add_photo(db_session, project, "b1.jpg")
    await _add_criterion_score(db_session, photo_b1, "sharpness", 0.3)
    await _add_ranking(
        db_session,
        run,
        photo_b1,
        cluster_key="c1",
        category_key="landscape",
        rank_score=0.3,
        rank_position=1,
    )

    await reassign_photo_category(db_session, run.id, photo_a2.id, "c1", "landscape")

    # Neu ABGEFRAGT statt ueber die gehaltenen Instanzen aufgefrischt: seit
    # specs/features/0300-nebenkategorien.md stellt die Funktion die gesamte
    # Zugehoerigkeitsmenge her - eine ueberzaehlige Zeile wird GELOESCHT und eine fehlende NEU
    # angelegt. Ein `refresh()` auf der alten Instanz stiesse deshalb auf eine geloeschte Zeile.
    rows = await _rankings_of(db_session, run)

    # Partition A hat jetzt nur noch photo_a1 - bleibt Rang 1.
    assert rows[(photo_a1.id, "people")].rank_position == 1
    assert (photo_a2.id, "people") not in rows

    # Partition B hat jetzt photo_b1 (0.3) und photo_a2 (0.5) - photo_a2 hat den hoeheren Score,
    # gewinnt also Rang 1, photo_b1 rueckt auf Rang 2.
    assert rows[(photo_a2.id, "landscape")].rank_position == 1
    assert rows[(photo_b1.id, "landscape")].rank_position == 2
    # Die Rangfolgen-Zeile des unbeteiligten Fotos ist dieselbe geblieben.
    assert rows[(photo_a1.id, "people")].id == ranking_a1.id


async def test_no_matching_ranking_row_is_a_safe_no_op(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)
    # Kein PhotoRanking fuer photo_id=999 im Lauf - defensiver No-op statt Exception (die
    # eigentliche 404/409-Validierung lebt am API-Endpunkt, nicht hier).
    await reassign_photo_category(db_session, run.id, 999, "c1", "people")


# ---------------------------------------------------------------------------------------------
# specs/features/0300-nebenkategorien.md, Umsetzungsschritt 5: die Funktion stellt ab hier die
# GESAMTE Zugehoerigkeitsmenge eines Fotos her, nicht mehr nur eine verschobene Zeile.
# ---------------------------------------------------------------------------------------------


async def _add_classification(
    session: AsyncSession, photo: Photo, confidences: dict[str, float] | None
) -> None:
    session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key="menschen",
            detected_categories=list(confidences or {}),
            detected_category_confidences=confidences,
            category_confidence=(confidences or {}).get("menschen"),
            provider="anthropic",
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await session.commit()


async def _add_score(
    session: AsyncSession, photo: Photo, *, category_override: str | None = None
) -> PhotoScore:
    score = PhotoScore(
        photo_id=photo.id,
        sharpness=0.5,
        exposure=0.5,
        cluster_key="c1",
        category_override=category_override,
        computed_at=datetime(2023, 1, 1, tzinfo=UTC),
    )
    session.add(score)
    await session.commit()
    return score


async def _photo_with_two_memberships(
    session: AsyncSession,
    run: CriterionScoringRun,
    project: Project,
    confidences: dict[str, float] | None,
) -> Photo:
    """Ein Foto mit Hauptzeile `menschen` und Nebenzeile `tier` - die Vorbedingung fast aller
    Zusammenfuehrungsfaelle."""
    photo = await _add_photo(session, project, "a.jpg")
    await _add_criterion_score(session, photo, "sharpness", 0.9)
    await _add_classification(session, photo, confidences)
    await _add_ranking(
        session,
        run,
        photo,
        cluster_key="c1",
        category_key="menschen",
        rank_score=0.9,
        rank_position=1,
        is_primary=True,
    )
    if confidences is not None and confidences.get("tier", 0.0) >= 0.7:
        await _add_ranking(
            session,
            run,
            photo,
            cluster_key="c1",
            category_key="tier",
            rank_score=0.9,
            rank_position=1,
            is_primary=False,
        )
    return photo


async def test_an_override_onto_an_existing_secondary_merges_both_rows(
    db_session: AsyncSession,
) -> None:
    """Akzeptanzkriterium 15: der Override auf eine bereits bestehende NEBENkategorie fuehrt beide
    Zeilen zu einer Hauptzeile zusammen - vorher zwei Zeilen, nachher zwei (NICHT drei), und kein
    Konflikt."""
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)
    photo = await _photo_with_two_memberships(
        db_session, run, project, {"menschen": 0.9, "tier": 0.95}
    )
    await _add_score(db_session, photo, category_override="tier")

    await reassign_photo_category(db_session, run.id, photo.id, "c1", "tier")

    rows = await _rankings_of(db_session, run)
    assert {key[1]: row.is_primary for key, row in rows.items()} == {
        "tier": True,
        "menschen": False,
    }
    await _assert_exactly_one_primary_row_per_photo(db_session, run)
    await _assert_positions_are_gapless(db_session, run)


async def test_the_previous_primary_stays_as_a_secondary_when_it_reaches_the_threshold(
    db_session: AsyncSession,
) -> None:
    """Akzeptanzkriterium 15, der Kern der Story: das Foto verschwindet NICHT aus der Kategorie,
    aus der es umgehaengt wurde - sofern das Modell dort sicher genug war."""
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)
    photo = await _photo_with_two_memberships(db_session, run, project, {"menschen": 0.9})
    await _add_score(db_session, photo, category_override="fahrzeug")

    await reassign_photo_category(db_session, run.id, photo.id, "c1", "fahrzeug")

    rows = await _rankings_of(db_session, run)
    assert {key[1]: row.is_primary for key, row in rows.items()} == {
        "fahrzeug": True,
        "menschen": False,
    }
    await _assert_exactly_one_primary_row_per_photo(db_session, run)


async def test_the_previous_primary_disappears_without_a_number(
    db_session: AsyncSession,
) -> None:
    """Die Gegenprobe zum Test darueber: ohne Zahl ist die alte Hauptkategorie keine
    Nebenkategorie (Akzeptanzkriterium 6) - ihre Zeile wird geloescht statt umgewidmet."""
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)
    photo = await _photo_with_two_memberships(db_session, run, project, {})
    await _add_score(db_session, photo, category_override="fahrzeug")

    await reassign_photo_category(db_session, run.id, photo.id, "c1", "fahrzeug")

    rows = await _rankings_of(db_session, run)
    assert {key[1]: row.is_primary for key, row in rows.items()} == {"fahrzeug": True}
    await _assert_exactly_one_primary_row_per_photo(db_session, run)


async def test_an_override_onto_a_never_candidate_category_keeps_both_secondaries(
    db_session: AsyncSession,
) -> None:
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)
    photo = await _photo_with_two_memberships(
        db_session, run, project, {"menschen": 0.9, "tier": 0.95}
    )
    await _add_score(db_session, photo, category_override="dokument_screenshot")

    await reassign_photo_category(db_session, run.id, photo.id, "c1", "dokument_screenshot")

    rows = await _rankings_of(db_session, run)
    assert {key[1]: row.is_primary for key, row in rows.items()} == {
        "dokument_screenshot": True,
        "menschen": False,
        "tier": False,
    }
    await _assert_exactly_one_primary_row_per_photo(db_session, run)


async def test_taking_the_override_back_restores_the_membership_set_of_the_automatic_run(
    db_session: AsyncSession,
) -> None:
    """Akzeptanzkriterium 15, letzter Satz: die Ruecknahme stellt die Mengengleichheit der
    `(category_key, is_primary)`-Paare mit dem automatischen Lauf wieder her."""
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)
    photo = await _photo_with_two_memberships(
        db_session, run, project, {"menschen": 0.9, "tier": 0.95}
    )
    before = {key[1]: row.is_primary for key, row in (await _rankings_of(db_session, run)).items()}

    score = await _add_score(db_session, photo, category_override="tier")
    await reassign_photo_category(db_session, run.id, photo.id, "c1", "tier")

    score.category_override = None
    await db_session.commit()
    await reassign_photo_category(db_session, run.id, photo.id, "c1", "menschen")

    after = {key[1]: row.is_primary for key, row in (await _rankings_of(db_session, run)).items()}
    assert after == before
    await _assert_exactly_one_primary_row_per_photo(db_session, run)


async def test_a_manually_set_primary_row_is_not_dampened(db_session: AsyncSession) -> None:
    """Akzeptanzkriterium 22 / ADR 0069 Punkt 6: eine menschliche Festlegung mit einer Modellzahl
    abzuwerten hiesse, den Nutzer fuer die Unsicherheit des Modells zu bestrafen - sichtbar an
    genau der Stelle, an der er gerade korrigiert hat.

    Aufbau: das uebersteuerte Foto ist mit 0.6 knapp BESSER bewertet als das andere (0.5), der
    Abstand liegt aber unter der Konstante. Das Modell hat zum uebersteuerten Schluessel `0.0`
    gesagt - mit Daempfung fiele die Zeile hinter das andere Foto zurueck, ohne bleibt sie vorn."""
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)

    other = await _add_photo(db_session, project, "other.jpg")
    await _add_criterion_score(db_session, other, "sharpness", 0.5)
    await _add_classification(db_session, other, {"tier": 1.0})
    await _add_ranking(
        db_session,
        run,
        other,
        cluster_key="c1",
        category_key="tier",
        rank_score=0.5,
        rank_position=1,
    )

    overridden = await _add_photo(db_session, project, "overridden.jpg")
    await _add_criterion_score(db_session, overridden, "sharpness", 0.6)
    await _add_classification(db_session, overridden, {"tier": 0.0, "menschen": 0.9})
    await _add_ranking(
        db_session,
        run,
        overridden,
        cluster_key="c1",
        category_key="menschen",
        rank_score=0.6,
        rank_position=1,
    )
    await _add_score(db_session, overridden, category_override="tier")

    await reassign_photo_category(db_session, run.id, overridden.id, "c1", "tier")

    rows = await _rankings_of(db_session, run)
    assert rows[(overridden.id, "tier")].rank_position == 1
    assert rows[(other.id, "tier")].rank_position == 2
    # Die Gegenprobe, ohne die der Aufbau nichts unterscheiden wuerde: MIT Daempfung waere die
    # Reihenfolge umgekehrt - die Zahl 0.0 kostet den vollen Abzug.
    assert confidence_ordering_score(0.6, 0.0) < confidence_ordering_score(0.5, 1.0)
