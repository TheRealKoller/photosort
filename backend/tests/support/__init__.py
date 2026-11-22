"""Gemeinsame Testbausteine des Backends - die EINE Fundstelle.

`specs/architecture/0002-testkonzept.md` nennt dieses Paket als Fundstelle fuer Testdaten,
Doppelgaenger und den Migrations-Harness. Jede Abweichung zwischen frueheren Kopien ist hier ein
Schluesselwort-Parameter; dateilokal bleibt nur, was inhaltliche Zusicherung eines einzelnen
Tests ist.
"""

from tests.support.fakes import FakeEnqueuer, FakeOpenCloudClient
from tests.support.fixtures import (
    add_photo,
    add_scoring_run,
    add_successful_run,
    create_project_via_api,
    make_project,
    make_project_id,
    make_user,
    opencloud_entry,
    write_display_variant,
)
from tests.support.migration import apply_migration, load_migration_module

__all__ = [
    "FakeEnqueuer",
    "FakeOpenCloudClient",
    "add_photo",
    "add_scoring_run",
    "add_successful_run",
    "create_project_via_api",
    "apply_migration",
    "load_migration_module",
    "make_project",
    "make_project_id",
    "make_user",
    "opencloud_entry",
    "write_display_variant",
]
