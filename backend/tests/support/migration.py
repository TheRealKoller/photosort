"""Migrations-Harness: Modul laden und Upgrade/Downgrade gegen eine echte SQLite-Verbindung.

Der Schema-Nachbau VOR einer Migration (`_create_pre_migration_schema`) bleibt je Testdatei
dateilokal - er ist die inhaltliche Aussage genau dieser Migration. Geladen und angewandt wird
dagegen ueberall ueber diese beiden Funktionen.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection

ALEMBIC_VERSIONS = Path(__file__).resolve().parent.parent.parent / "alembic" / "versions"


def load_migration_module(path: Path) -> types.ModuleType:
    """Laedt eine Revisionsdatei als eigenstaendiges Modul."""
    spec = importlib.util.spec_from_file_location(f"{path.stem}_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_migration(connection: Connection, direction: str, *, path: Path) -> None:
    """Fuehrt `upgrade`/`downgrade` der uebergebenen Revision aus."""
    module = load_migration_module(path)
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()
