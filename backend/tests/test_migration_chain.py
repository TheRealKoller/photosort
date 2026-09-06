from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

# Kein Gegenstand einer einzelnen Spec, sondern die Luecke zwischen allen test_migration_*.py:
# jeder von ihnen laedt SEINE Revision isoliert ueber importlib und prueft ihr Auf-/Abwaerts-
# Verhalten an einem nachgebauten Schema-Stand. Das ist Absicht (kein Test haengt an der vollen
# Historie), hat aber einen blinden Fleck - die Kette selbst pruefte niemand. Eine Revision mit
# einer bereits vergebenen ID faellt dort nicht auf: die Datei laedt fuer sich genommen sauber,
# alle Einzeltests bleiben gruen, und erst `alembic upgrade head` beim Prozessstart bricht ab.
# Nachgewiesen am 2026-09-06 (PR #341, Spec 0304): die neue Migration bekam die schon vergebene
# ID `a7b8c9d0e1f2`, `pytest` war vollstaendig gruen, und der Backend-Container wurde in
# `docker-compose-check` nie healthy - "Cycle is detected in revisions".
#
# Diese Datei schliesst genau das: sie laesst Alembic die Kette selbst aufloesen, mit derselben
# Mechanik, die auch der Prozessstart benutzt.


@pytest.fixture(scope="module")
def script_directory() -> ScriptDirectory:
    backend_root = Path(__file__).resolve().parent.parent
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    return ScriptDirectory.from_config(config)


def test_the_migration_chain_resolves_at_all(script_directory: ScriptDirectory) -> None:
    """Der Kern: Alembic muss die Historie ueberhaupt aufloesen koennen.

    `walk_revisions()` wirft bei einer doppelt vergebenen Revisions-ID, einem Zyklus oder einem
    `down_revision`, das auf nichts zeigt - dieselben Fehler, an denen sonst erst der
    Container-Start scheitert."""
    revisions = list(script_directory.walk_revisions())

    assert revisions, "keine Migrationen gefunden - stimmt der script_location-Pfad?"


def test_every_revision_id_is_unique(script_directory: ScriptDirectory) -> None:
    """Die eigentliche Falle, gegen die diese Datei geschrieben ist. Eine von Hand vergebene ID
    (das Projekt nutzt lesbare Hex-Folgen statt reiner Alembic-Generate) kollidiert leicht mit
    einer bestehenden - und die Kollision sieht in der Einzeldatei nach nichts aus.

    Bewusst ueber die DATEIEN gezaehlt, nicht ueber das von Alembic aufgeloeste Mapping: dort
    ueberschriebe die zweite Datei die erste stillschweigend, und der Test bewiese nur, dass ein
    dict eindeutige Schluessel hat."""
    versions_dir = Path(script_directory.dir) / "versions"
    ids: dict[str, list[str]] = {}

    for path in sorted(versions_dir.glob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("revision: str = ") or line.startswith("revision = "):
                revision_id = line.split("=", 1)[1].strip().strip("\"'")
                ids.setdefault(revision_id, []).append(path.name)
                break

    duplicates = {rev: files for rev, files in ids.items() if len(files) > 1}

    assert not duplicates, f"Revisions-ID mehrfach vergeben: {duplicates}"


def test_there_is_exactly_one_head(script_directory: ScriptDirectory) -> None:
    """`alembic upgrade head` ist der Startbefehl des Backend-Containers (docker-compose.yml).
    Bei zwei Heads ist "head" mehrdeutig und der Befehl bricht ab - der typische Zustand, wenn
    zwei parallele Branches je eine Migration auf denselben Vorgaenger setzen und beide gemergt
    werden."""
    heads = script_directory.get_heads()

    assert len(heads) == 1, f"erwartet genau ein head, gefunden: {heads}"


def test_every_revision_is_reachable_from_the_head(script_directory: ScriptDirectory) -> None:
    """Gegenprobe zum Head-Test: eine Revision, die in keiner Kette haengt, wird beim Start nie
    ausgefuehrt - ihre Spalten fehlen dann in der Datenbank, waehrend das ORM sie erwartet."""
    versions_dir = Path(script_directory.dir) / "versions"
    files_on_disk = len(list(versions_dir.glob("*.py")))
    reachable = len(list(script_directory.walk_revisions("base", "heads")))

    assert reachable == files_on_disk, (
        f"{files_on_disk} Migrationsdateien, aber nur {reachable} von base bis head erreichbar"
    )
