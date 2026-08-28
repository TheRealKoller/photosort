"""cloud vision errors: photo_cloud_vision_errors table

specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
fehler-persistierung.md Punkt 2 - neue, schlanke Tabelle photo_cloud_vision_errors: erfasst
ausschliesslich den letzten bekannten Fehlschlag eines Cloud-Vision-Laufs (landmark/
remote_category) je Foto, composite PK (photo_id, phase), kein Verlauf/Historie (ein erneuter
Fehlschlag ueberschreibt die bestehende Zeile, ein erfolgreicher Retry loescht sie). `phase` ist
analog den uebrigen projektweiten Enum-Spalten (z.B. photo_scores.suggested_status) als
String(length=20) statt eines nativen DB-Enums abgelegt (SQLEnum(..., native_enum=False)).

Revision ID: c2d3e4f5a6b7
Revises: b3c4d5e6f7a8
Create Date: 2026-08-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'photo_cloud_vision_errors',
        sa.Column('photo_id', sa.Integer(), nullable=False),
        sa.Column('phase', sa.String(length=20), nullable=False),
        sa.Column('error_type', sa.String(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=False),
        sa.Column('attempted_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.id']),
        sa.PrimaryKeyConstraint('photo_id', 'phase'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('photo_cloud_vision_errors')
