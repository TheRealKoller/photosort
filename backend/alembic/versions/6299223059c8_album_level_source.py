"""Albumstufen-Quelle am Lauf: `criterion_scoring_runs.album_level_source`

Eine additive Spalte, keine Datenmigration: NOT NULL mit BLEIBENDEM `server_default 'cloud'`.
Jeder bestehende Lauf las seine Stufe aus `photo_album_suitability`, Altzeilen tragen damit
wahrheitsgemaess `cloud`.

Der Rueckweg entfernt die Spalte; die eingefrorene Quelle eines Eye-Laufs geht dabei verloren.

Revision ID: 6299223059c8
Revises: 43a3afeb7312
Create Date: 2026-11-08 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6299223059c8"
down_revision: Union[str, Sequence[str], None] = "43a3afeb7312"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Spalte `album_level_source` an `criterion_scoring_runs`."""
    with op.batch_alter_table("criterion_scoring_runs") as batch:
        batch.add_column(
            sa.Column(
                "album_level_source",
                sa.String(length=20),
                nullable=False,
                server_default="cloud",
            )
        )


def downgrade() -> None:
    """Downgrade schema - entfernt die Spalte."""
    with op.batch_alter_table("criterion_scoring_runs") as batch:
        batch.drop_column("album_level_source")
