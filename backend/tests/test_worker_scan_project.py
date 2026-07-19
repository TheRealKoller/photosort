from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import Photo, Project, ScanStatus
from photosort.opencloud.client import Drive, OpenCloudError
from photosort.opencloud.webdav_xml import DavEntry
from photosort.worker import run_project_scan

DRIVE = Drive(id="drive-1", name="Family", drive_type="project", webdav_url="https://cloud.example.com/dav/spaces/drive-1")


def _entry(name: str, etag: str, last_modified: datetime, content_length: int = 100) -> DavEntry:
    return DavEntry(
        href=f"/dav/spaces/drive-1/CostaRica/{name}",
        name=name,
        is_collection=False,
        etag=etag,
        last_modified=last_modified,
        content_length=content_length,
    )


class FakeOpenCloudClient:
    def __init__(
        self,
        entries: list[tuple[str, DavEntry]],
        file_contents: dict[str, bytes] | None = None,
        fail_with: OpenCloudError | None = None,
    ) -> None:
        self._entries = entries
        self._file_contents = file_contents or {}
        self._fail_with = fail_with
        self.range_requests: list[str] = []

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail_with:
            raise self._fail_with
        return DRIVE

    async def walk(self, webdav_url: str, root_path: str) -> AsyncIterator[tuple[str, DavEntry]]:
        for item in self._entries:
            yield item

    async def get_range(self, webdav_url: str, relative_path: str, length: int) -> bytes:
        self.range_requests.append(relative_path)
        return self._file_contents.get(relative_path, b"")


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="CostaRica")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def test_scan_adds_new_photos(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[
            ("CostaRica/img001.png", _entry("img001.png", "etag-1", modified)),
        ]
    )

    scan_run = await run_project_scan(db_session, client, project, drive_name=None)

    assert scan_run.status == ScanStatus.SUCCESS
    assert scan_run.photos_added == 1
    assert scan_run.files_found == 1
    assert scan_run.files_skipped == 0

    result = await db_session.execute(select(Photo).where(Photo.project_id == project.id))
    photos = result.scalars().all()
    assert len(photos) == 1
    assert photos[0].relative_path == "CostaRica/img001.png"
    # PNG: EXIF not attempted, falls back to last_modified (stored as naive UTC)
    assert photos[0].taken_at == modified.replace(tzinfo=None)


async def test_scan_updates_photo_on_etag_change(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="CostaRica/img001.png",
            etag="old-etag",
            content_length=10,
            taken_at=modified,
            last_modified=modified,
        )
    )
    await db_session.commit()

    new_modified = datetime(2023, 8, 16, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[("CostaRica/img001.png", _entry("img001.png", "new-etag", new_modified))]
    )

    scan_run = await run_project_scan(db_session, client, project, drive_name=None)

    assert scan_run.photos_added == 0
    assert scan_run.photos_updated == 1
    photo = (await db_session.execute(select(Photo))).scalar_one()
    assert photo.etag == "new-etag"


async def test_scan_skips_photo_with_unchanged_etag(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="CostaRica/img001.jpg",
            etag="same-etag",
            content_length=10,
            taken_at=modified,
            last_modified=modified,
        )
    )
    await db_session.commit()

    client = FakeOpenCloudClient(
        entries=[("CostaRica/img001.jpg", _entry("img001.jpg", "same-etag", modified))]
    )

    scan_run = await run_project_scan(db_session, client, project, drive_name=None)

    assert scan_run.photos_updated == 0
    assert scan_run.photos_added == 0
    assert client.range_requests == []  # unchanged files must not trigger an EXIF re-fetch


async def test_scan_removes_photos_no_longer_present(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="CostaRica/gone.jpg",
            etag="etag",
            content_length=10,
            taken_at=modified,
            last_modified=modified,
        )
    )
    await db_session.commit()

    client = FakeOpenCloudClient(entries=[])

    scan_run = await run_project_scan(db_session, client, project, drive_name=None)

    assert scan_run.photos_removed == 1
    result = await db_session.execute(select(Photo).where(Photo.project_id == project.id))
    assert result.scalars().all() == []


async def test_scan_skips_non_image_files(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[("CostaRica/notes.txt", _entry("notes.txt", "etag", modified))]
    )

    scan_run = await run_project_scan(db_session, client, project, drive_name=None)

    assert scan_run.files_skipped == 1
    assert scan_run.photos_added == 0
    photos = (await db_session.execute(select(Photo))).scalars().all()
    assert photos == []


async def test_scan_extracts_exif_for_jpeg(db_session: AsyncSession) -> None:
    import io

    from PIL import Image
    from PIL.ExifTags import IFD

    image = Image.new("RGB", (4, 4), color="red")
    exif = image.getexif()
    exif.get_ifd(IFD.Exif)[36867] = "2022:01:02 03:04:05"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)

    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[("CostaRica/img.jpg", _entry("img.jpg", "etag-jpg", modified))],
        file_contents={"CostaRica/img.jpg": buffer.getvalue()},
    )

    await run_project_scan(db_session, client, project, drive_name=None)

    photo = (await db_session.execute(select(Photo))).scalar_one()
    assert photo.taken_at == datetime(2022, 1, 2, 3, 4, 5)
    assert client.range_requests == ["CostaRica/img.jpg"]


async def test_scan_run_marked_failed_on_opencloud_error(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    client = FakeOpenCloudClient(entries=[], fail_with=OpenCloudError("Ordner nicht erreichbar"))

    scan_run = await run_project_scan(db_session, client, project, drive_name=None)

    assert scan_run.status == ScanStatus.FAILED
    assert scan_run.error_message == "Ordner nicht erreichbar"
    photos = (await db_session.execute(select(Photo))).scalars().all()
    assert photos == []
