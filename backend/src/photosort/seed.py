from __future__ import annotations

from sqlalchemy import Column, MetaData, String, Table, insert, select
from sqlalchemy.engine import Connection

from photosort.security import hash_password

# Bewusst eine eigene, minimale Tabellen-Definition mit eigener MetaData statt des ORM-Modells
# photosort.models.User: Alembic-Datenmigrationen sollen nicht von zukuenftigen Aenderungen am
# App-Modell abhaengen (uebliche Alembic-Konvention) und keine geteilte MetaData mit der
# Deklarativen Basis riskieren. Muss synchron zur "users"-Tabelle aus der Schema-Migration
# bleiben (siehe alembic/versions/c6c17d0ef6d5_add_users_table.py).
_metadata = MetaData()
users_table = Table(
    "users",
    _metadata,
    Column("username", String, unique=True),
    Column("password_hash", String),
)


def seed_user(connection: Connection, username: str, password: str) -> None:
    """Legt den User an, falls er noch nicht existiert - idempotent.

    Ueberschreibt nie einen bestehenden password_hash (siehe specs/features/0006-auth.md).
    """
    existing = connection.execute(
        select(users_table.c.username).where(users_table.c.username == username)
    ).first()
    if existing is not None:
        return

    connection.execute(
        insert(users_table).values(username=username, password_hash=hash_password(password))
    )


def seed_configured_users(connection: Connection, users: list[tuple[str, str]]) -> None:
    for username, password in users:
        seed_user(connection, username, password)
