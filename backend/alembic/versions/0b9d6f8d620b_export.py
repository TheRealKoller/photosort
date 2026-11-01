"""export: die Lauf- und Schnappschuss-Tabellen des Exports nach OpenCloud

`export_runs` traegt je Lauf einen Datensatz (Muster `scan_runs`/`scoring_runs`): `project_id`,
`status` (`running`/`success`/`failed`), `started_at`, `finished_at`, `target_path`,
`photo_count`, `exported_count`, `failed_count`, `error_message`. KEIN `user_id` - das Ergebnis
gehoert dem Projekt, wie bei `final_selection_decisions` (ADR 0136 Punkt 3).

`export_photos` ist der Mengen-Schnappschuss je Lauf (Muster `criterion_scoring_runs.rankings`):
je exportiertem Foto eine Zeile mit `photo_id` (nullable - ein spaeter geloeschtes Foto laesst
den Schnappschuss stehen, ADR 0136 Punkt 3), `relative_path` (eingefroren, zugleich Zielpfad
unter dem Lauf-Ordner) und `error` (nullable - ein fehlgeschlagenes `COPY` schreibt hierher, der
Lauf laeuft weiter und endet trotz Teilfehlern `success`).

Beide Fremdschluessel sind echt und benannt: Der echte Fremdschluessel haelt die Tabellen in der
Erreichbarkeitspruefung der Projektloeschung; ein unbenannter waere unter SQLite im Rueckwaertsweg
nicht droppbar (`Base.metadata` traegt keine `naming_convention`). `export_photos.photo_id` ist
NULLABLE, damit die Loeschung eines Fotos den Schnappschuss nicht zerstoert - die Zeile haengt
am LAUF, nicht am Foto.

Revision ID: 0b9d6f8d620b
Revises: 1d3dbfdde02e
Create Date: 2026-11-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0b9d6f8d620b"
down_revision: Union[str, Sequence[str], None] = "1d3dbfdde02e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_TYPE = sa.String(length=20)


def upgrade() -> None:
    """Upgrade schema - legt beide Tabellen an, ohne eine einzige Zeile zu schreiben."""
    op.create_table(
        "export_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("status", _STATUS_TYPE, nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("target_path", sa.String(), nullable=True),
        sa.Column("photo_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(), nullable=True),
        # Fortschritts-Watchdog, analog ScanRun.last_progress_at: server-seitig defaultet, sonst
        # gaelte ein frisch angelegter Lauf sofort als Stillstand. Periodisch zwischen-committet
        # (worker.py::run_export), gelesen von worker.py::reap_stalled_runs.
        sa.Column("last_progress_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_export_runs_project_id"),
    )
    op.create_table(
        "export_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("export_run_id", sa.Integer(), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=True),
        sa.Column("relative_path", sa.String(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["export_run_id"], ["export_runs.id"], name="fk_export_photos_export_run_id"
        ),
        sa.ForeignKeyConstraint(
            ["photo_id"], ["photos.id"], name="fk_export_photos_photo_id", ondelete="SET NULL"
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Mit beiden Tabellen sind alle Nachweise vergangener Exporte verloren: Laeufe, Zielpfade,
    Mengen-Schnappschuesse und Einzelfehler. Die auf OpenCloud angelegten Zielordner bleiben davon
    unberuehrt - sie liegen ausserhalb der Datenbank."""
    op.drop_table("export_photos")
    op.drop_table("export_runs")
