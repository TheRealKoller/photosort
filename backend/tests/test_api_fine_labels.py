from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import FineLabel, Photo, PhotoFineLabel, Project

# specs/features/0289-feste-kategorien.md, Teststrategie Abschnitt 8 / Security-Abschnitt Punkt 1:
# GET /projects/{id}/fine-labels - haeufigste Feinlabels DIESES Projekts. Die `fine_labels`-
# Registry ist bewusst projektuebergreifend, die ZAEHLUNG darf es nicht sein.


async def _make_project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _make_photo(session: AsyncSession, project: Project, path: str) -> Photo:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=1,
        taken_at=now,
        last_modified=now,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _make_label(session: AsyncSession, canonical_key: str, display_name: str) -> FineLabel:
    label = FineLabel(
        canonical_key=canonical_key, display_name=display_name, embedding=[1.0, 0.0]
    )
    session.add(label)
    await session.commit()
    await session.refresh(label)
    return label


async def _link(session: AsyncSession, photo: Photo, label: FineLabel) -> None:
    session.add(
        PhotoFineLabel(
            photo_id=photo.id,
            fine_label_id=label.id,
            raw_label=label.display_name,
            provider="anthropic",
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await session.commit()


async def test_requires_auth(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    project = await _make_project(db_session)

    response = await api_client.get(f"/projects/{project.id}/fine-labels")

    assert response.status_code == 401


async def test_unknown_project_returns_404(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    # Keine Objekt-ID-Enumeration ueber ein leeres 200 (Security-Abschnitt Punkt 1).
    response = await authenticated_api_client.get("/projects/999/fine-labels")

    assert response.status_code == 404


async def test_empty_project_returns_an_empty_list_with_200(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)

    response = await authenticated_api_client.get(f"/projects/{project.id}/fine-labels")

    assert response.status_code == 200
    assert response.json() == []


async def test_sorts_by_photo_count_descending_with_canonical_key_tie_break(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der Datensatz uebt BEIDE Sortierstufen aus: "strand" hat die hoechste Haeufigkeit,
    "berg"/"hund" liegen mit je einem Foto gleichauf und werden alphabetisch nach
    `canonical_key` sortiert."""
    project = await _make_project(db_session)
    strand = await _make_label(db_session, "strand", "Strand")
    hund = await _make_label(db_session, "hund", "Hund")
    berg = await _make_label(db_session, "berg", "Berg")

    for index in range(3):
        photo = await _make_photo(db_session, project, f"s{index}.jpg")
        await _link(db_session, photo, strand)
    hund_photo = await _make_photo(db_session, project, "h.jpg")
    await _link(db_session, hund_photo, hund)
    berg_photo = await _make_photo(db_session, project, "b.jpg")
    await _link(db_session, berg_photo, berg)

    response = await authenticated_api_client.get(f"/projects/{project.id}/fine-labels")

    assert response.status_code == 200
    assert response.json() == [
        {"canonical_key": "strand", "display_name": "Strand", "photo_count": 3},
        {"canonical_key": "berg", "display_name": "Berg", "photo_count": 1},
        {"canonical_key": "hund", "display_name": "Hund", "photo_count": 1},
    ]


async def test_fine_labels_of_another_project_do_not_appear(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SECURITY-MUSS-KRITERIUM (Spec 0289, Abschnitt 1): `fine_labels` ist eine
    PROJEKTUEBERGREIFENDE Vokabular-Registry - ein globales SELECT wuerde Label-Haeufigkeiten
    ANDERER Projekte ausliefern. Der Join ueber `photos.project_id` verhindert das."""
    project = await _make_project(db_session, "Projekt A")
    other = await _make_project(db_session, "Projekt B")
    hund = await _make_label(db_session, "hund", "Hund")
    geheim = await _make_label(db_session, "geheim", "Geheimprojekt")

    photo_a = await _make_photo(db_session, project, "a.jpg")
    await _link(db_session, photo_a, hund)
    photo_b = await _make_photo(db_session, other, "b.jpg")
    await _link(db_session, photo_b, geheim)
    photo_b2 = await _make_photo(db_session, other, "b2.jpg")
    await _link(db_session, photo_b2, hund)

    response = await authenticated_api_client.get(f"/projects/{project.id}/fine-labels")

    body = response.json()
    assert [entry["canonical_key"] for entry in body] == ["hund"]
    # Die Haeufigkeit zaehlt NUR die Fotos dieses Projekts, obwohl derselbe Registry-Eintrag auch
    # im anderen Projekt verwendet wird.
    assert body[0]["photo_count"] == 1


async def test_a_registry_entry_without_a_photo_in_this_project_is_omitted(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    # Ueber den Join implizit photo_count > 0 - kein Eintrag mit Haeufigkeit 0.
    project = await _make_project(db_session)
    await _make_label(db_session, "verwaist", "Verwaist")

    response = await authenticated_api_client.get(f"/projects/{project.id}/fine-labels")

    assert response.json() == []


async def test_a_label_on_several_photos_of_the_same_project_counts_each_photo_once(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    hund = await _make_label(db_session, "hund", "Hund")
    for index in range(2):
        photo = await _make_photo(db_session, project, f"{index}.jpg")
        await _link(db_session, photo, hund)

    body = (await authenticated_api_client.get(f"/projects/{project.id}/fine-labels")).json()

    assert body == [{"canonical_key": "hund", "display_name": "Hund", "photo_count": 2}]
