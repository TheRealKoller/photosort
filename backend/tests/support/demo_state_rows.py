"""Gemeinsame Bausteine der Demo-Zustands-Tests."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    Photo,
    Project,
    User,
)
from tests.support import make_user


# --- Duenne DB-Schreibschicht -----------------------------------------------------------------
async def _make_user(session: AsyncSession, username: str) -> User:
    return await make_user(session, username, password_hash="argon2-platzhalter", flush=True)


async def _project(session: AsyncSession, name: str) -> Project:
    project = (await session.execute(select(Project).where(Project.name == name))).scalars().first()
    assert project is not None, f"Projekt {name!r} fehlt"
    return project


async def _photos_of(session: AsyncSession, project_name: str) -> list[Photo]:
    project = await _project(session, project_name)
    return list(
        (
            await session.execute(
                select(Photo).where(Photo.project_id == project.id).order_by(Photo.id)
            )
        )
        .scalars()
        .all()
    )
