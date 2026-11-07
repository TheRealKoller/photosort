"""eye mapping version: `photo_eye_results.mapping_version`

Spec 0615 / ADR 0140 Punkt 5. Additiv, eine Spalte, keine Loeschkante.

* Bestehende Zeilen erhalten `eye-4.2.3/v1` - sie sind alle mit v1 entstanden - und werden nicht
  neu berechnet.
* NOT NULL ohne BLEIBENDEN Default: der `server_default` des ersten Batch-Blocks traegt nur das
  Nachtragen und faellt im zweiten weg. Ein Schreibpfad, der die Spalte vergisst, scheitert danach
  laut, statt still "v1" zu behaupten.
* Der Rueckweg entfernt die Spalte; die Fassung der Zeilen geht dabei verloren.

Revision ID: 5c7633e53257
Revises: 44ba5fe0184a
Create Date: 2026-11-07 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c7633e53257"
down_revision: Union[str, Sequence[str], None] = "44ba5fe0184a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Spalte mit Nachtrage-Default anlegen, dann den Default entfernen."""
    with op.batch_alter_table("photo_eye_results") as batch:
        batch.add_column(
            sa.Column(
                "mapping_version",
                sa.String(),
                nullable=False,
                server_default="eye-4.2.3/v1",
            )
        )
    with op.batch_alter_table("photo_eye_results") as batch:
        batch.alter_column("mapping_version", existing_type=sa.String(), server_default=None)


def downgrade() -> None:
    """Downgrade schema - entfernt die Spalte."""
    with op.batch_alter_table("photo_eye_results") as batch:
        batch.drop_column("mapping_version")
