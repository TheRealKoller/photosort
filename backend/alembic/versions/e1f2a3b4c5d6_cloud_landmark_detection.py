"""cloud landmark detection: projects.cloud_landmark_detection_enabled/
cloud_landmark_consent_at, photo_landmark_detections table

specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md,
decisions/0025-cloud-landmark-erkennung.md - vollstaendig additiv (zwei neue Project-Spalten,
eine neue Tabelle), keine Aenderung an bestehenden Spalten/Tabellen.

Revision ID: e1f2a3b4c5d6
Revises: c1d2e3f4a5b6
Create Date: 2026-08-21 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'projects',
        sa.Column(
            'cloud_landmark_detection_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'projects', sa.Column('cloud_landmark_consent_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'photo_landmark_detections',
        sa.Column('photo_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.id'], ),
        sa.PrimaryKeyConstraint('photo_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('photo_landmark_detections')
    op.drop_column('projects', 'cloud_landmark_consent_at')
    op.drop_column('projects', 'cloud_landmark_detection_enabled')
