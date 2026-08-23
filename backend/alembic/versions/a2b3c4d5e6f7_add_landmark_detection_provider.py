"""add landmark detection provider: photo_landmark_detections.provider

specs/features/0054-mistral-provider-option-cloud-landmark.md,
decisions/0031-mistral-provider-option-cloud-landmark.md Punkt 5 - vollstaendig additiv (eine
neue Spalte), keine Aenderung an bestehenden Spalten/Tabellen. server_default="anthropic"
backfillt bestehende Zeilen (Anthropic war bis zu dieser Migration der einzige Provider) - der
ORM-Model-Default (models.py::PhotoLandmarkDetection.provider) deckt dieselbe Situation
Python-seitig fuer neue, ohne explizites provider-Kwarg angelegte Instanzen ab.

Revision ID: a2b3c4d5e6f7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'photo_landmark_detections',
        sa.Column('provider', sa.String(), nullable=False, server_default='anthropic'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('photo_landmark_detections', 'provider')
