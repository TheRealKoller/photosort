"""Aufloesung und automatische Entscheidung: drei additive Spalten (ADR 0146 Punkt 2/3)

`photos.pixel_count` (nullable) und `photos.pixel_count_probed` sowie
`photo_scores.auto_decided`. Kein Backfill: Die Aufloesung eines Bestandsfotos ist UNBEKANNT, bis
ein Scan sie liest - eine geschaetzte Zahl verschoebe die Gewinnerregel stillschweigend. Die beiden
Merker sind NOT NULL mit BLEIBENDEM `server_default false`, damit Bestandszeilen ohne Lauf nicht
als automatisch entschieden gelten.

Der Rueckweg entfernt genau diese drei Spalten.

Revision ID: 8c0f0296e1cd
Revises: 6299223059c8
Create Date: 2026-11-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8c0f0296e1cd"
down_revision: Union[str, Sequence[str], None] = "6299223059c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Aufloesung am Foto und Lauf-Merker am Verlierer."""
    with op.batch_alter_table("photos") as batch:
        batch.add_column(sa.Column("pixel_count", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "pixel_count_probed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    with op.batch_alter_table("photo_scores") as batch:
        batch.add_column(
            sa.Column(
                "auto_decided",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    """Downgrade schema - entfernt genau die drei Spalten."""
    with op.batch_alter_table("photo_scores") as batch:
        batch.drop_column("auto_decided")
    with op.batch_alter_table("photos") as batch:
        batch.drop_column("pixel_count_probed")
        batch.drop_column("pixel_count")
