"""Ein API-Aufbau fuer Personentests mit Nebenlaeufigkeit: dateibasierte SQLite, je Anfrage eine
eigene Sitzung, `get_session` und `get_session_factory` auf DERSELBEN Engine.

Bewusst kein `test_*`-Modul (Muster `face_fakes.py`). Die geteilte `AsyncSession` aus
`conftest.py` erlaubt keine zwei gleichzeitigen Anfragen, und eine In-Memory-Datenbank teilt sich
eine einzige Verbindung - der Pool-Saldo waere dort nicht messbar.
"""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from photosort.api.deps import get_session, get_session_factory
from photosort.api.persons import get_face_analyzer
from photosort.config import settings
from photosort.db import Base, make_engine, make_session_factory
from photosort.face_analysis import MODEL_KEY
from photosort.main import app
from photosort.models import Person, Photo, PhotoScore, Project, RatingStatus, User
from photosort.persons import create_person
from photosort.security import create_access_token, hash_password
from tests.face_fakes import (
    Color,
    FakeFaceAnalyzer,
    face_box,
    face_embedding,
    write_display_variant,
)

NOW = datetime(2026, 9, 28, 12, 0, 0)


@dataclass
class PoolCounter:
    """Zaehlt ausgeliehene und zurueckgegebene Verbindungen des Pools - aus jedem Thread."""

    checkouts: int = 0
    checkins: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def on_checkout(self, *args: Any) -> None:
        with self._lock:
            self.checkouts += 1

    def on_checkin(self, *args: Any) -> None:
        with self._lock:
            self.checkins += 1

    @property
    def held(self) -> int:
        with self._lock:
            return self.checkouts - self.checkins


@dataclass
class PersonStack:
    engine: AsyncEngine
    factory: async_sessionmaker[AsyncSession]
    client: httpx.AsyncClient
    analyzer: FakeFaceAnalyzer
    cache_dir: Path
    user_id: int
    pool: PoolCounter

    async def project(self, name: str = "Reise") -> int:
        async with self.factory() as session:
            project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
            session.add(project)
            await session.commit()
            return project.id

    async def photo(
        self,
        project_id: int,
        name: str,
        color: Color | None,
        *,
        rejected: bool = False,
        taken_at: datetime = NOW,
    ) -> int:
        async with self.factory() as session:
            photo = Photo(
                project_id=project_id,
                relative_path=f"p{project_id}/{name}.jpg",
                etag=f"etag-{project_id}-{name}",
                content_length=1,
                taken_at=taken_at,
                taken_at_original=taken_at,
                last_modified=taken_at,
            )
            session.add(photo)
            await session.flush()
            if rejected:
                session.add(
                    PhotoScore(
                        photo_id=photo.id,
                        sharpness=1.0,
                        exposure=0.0,
                        cluster_key="c",
                        suggested_status=RatingStatus.REJECTED,
                        computed_at=NOW,
                    )
                )
            await session.commit()
            if color is not None:
                write_display_variant(self.cache_dir, photo.id, photo.etag, color)
            return photo.id

    async def define(self, name: str, axis: int, photo_id: int) -> int:
        async with self.factory() as session:
            person: Person = await create_person(
                session,
                name=name,
                embedding=face_embedding(axis),
                face_box=face_box(axis),
                model_key=MODEL_KEY,
                photo_id=photo_id,
                user_id=self.user_id,
            )
            await session.commit()
            return person.id

    async def count(self, model: Any) -> int:
        async with self.factory() as session:
            return (await session.execute(select(func.count()).select_from(model))).scalar_one()

    async def second_user_token(self, name: str = "partnerin") -> str:
        async with self.factory() as session:
            user = User(username=name, password_hash=hash_password("x"))
            session.add(user)
            await session.commit()
            return create_access_token(user)


async def person_stack(tmp_path: Path, analyzer: FakeFaceAnalyzer) -> AsyncIterator[PersonStack]:
    """Der Aufbau als Generator fuer eine `pytest_asyncio`-Fixture. `settings.photo_cache_dir`
    setzt der Aufrufer (per `monkeypatch`) auf `tmp_path / "cache"`."""
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 'personen.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    pool = PoolCounter()
    event.listen(engine.sync_engine.pool, "checkout", pool.on_checkout)
    event.listen(engine.sync_engine.pool, "checkin", pool.on_checkin)
    factory = make_session_factory(engine)
    cache_dir = Path(settings.photo_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    async def session_per_request() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_per_request
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_face_analyzer] = lambda: analyzer
    async with factory() as session:
        user = User(username="testuser", password_hash=hash_password("irrelevant"))
        session.add(user)
        await session.commit()
        token = create_access_token(user)
        user_id = user.id
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield PersonStack(
            engine=engine,
            factory=factory,
            client=client,
            analyzer=analyzer,
            cache_dir=cache_dir,
            user_id=user_id,
            pool=pool,
        )
    app.dependency_overrides.clear()
    await engine.dispose()
