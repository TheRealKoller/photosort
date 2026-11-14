"""Abbruchmerker: sechs nullable Spalten `cancel_requested_at` an den Lauftabellen

Kein Backfill: `NULL` heisst fuer jeden Bestandslauf "kein Abbruch angefordert". Die neuen
Statuswerte `queued`/`cancelled` brauchen kein DDL - die Statusspalten sind `native_enum=False`
ohne CHECK-Constraint.

Der Rueckweg entfernt genau diese sechs Spalten.

Revision ID: 2be43c4b5fb7
Revises: 8c0f0296e1cd
Create Date: 2026-11-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2be43c4b5fb7"
down_revision: Union[str, Sequence[str], None] = "8c0f0296e1cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "scan_runs",
    "scoring_runs",
    "criterion_scoring_runs",
    "remote_category_classification_runs",
    "export_runs",
    "classification_reviews",
)


def upgrade() -> None:
    """Upgrade schema - Abbruchmerker an jeder Lauftabelle."""
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("cancel_requested_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema - entfernt genau die sechs Spalten."""
    for table in reversed(_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("cancel_requested_at")
