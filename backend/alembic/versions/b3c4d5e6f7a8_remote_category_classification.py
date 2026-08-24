"""remote category classification: naming migration + category_override + category_labels +
photo_category_detections + remote_category_classification_runs

specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 2 - fuenf Teile:

a) Umbenennung `projects.cloud_landmark_detection_enabled`/`cloud_landmark_consent_at` ->
   `cloud_vision_detection_enabled`/`cloud_vision_consent_at` (wertsicheres RENAME COLUMN, keine
   Wertaenderung - ein Projekt mit bereits aktivierter landmark-Cloud-Erkennung bleibt danach
   technisch identisch aktiv).
b) Additiv `photo_scores.category_override: str | None`.
c1) Neue, projektuebergreifende Tabelle `category_labels` (kanonische Label-Registry).
c2) Neue Tabelle `photo_category_detections`, 1:N zu `photos` (bis zu drei Zeilen pro Foto).
d) Neue Tabelle `remote_category_classification_runs` (Run-Tracking analog `criterion_scoring_
   runs`, kein `scoring_run_id`-FK).

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # a) Naming-Migration (wertsicher, keine Neubefuellung).
    op.alter_column(
        'projects', 'cloud_landmark_detection_enabled', new_column_name='cloud_vision_detection_enabled'
    )
    op.alter_column(
        'projects', 'cloud_landmark_consent_at', new_column_name='cloud_vision_consent_at'
    )

    # b) Additiv, PhotoScore.category_override.
    op.add_column('photo_scores', sa.Column('category_override', sa.String(), nullable=True))

    # c1) Kanonische Label-Registry, projektuebergreifend (kein project_id-Bezug, ADR 0032 Punkt 2).
    op.create_table(
        'category_labels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('canonical_key', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('canonical_key', name='uq_category_label_canonical_key'),
    )

    # c2) 1:N zu photos (bis zu drei Zeilen pro Foto, ADR 0032 Punkt 2).
    op.create_table(
        'photo_category_detections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('photo_id', sa.Integer(), nullable=False),
        sa.Column('category_label_id', sa.Integer(), nullable=False),
        sa.Column('raw_label', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.id']),
        sa.ForeignKeyConstraint(['category_label_id'], ['category_labels.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'photo_id', 'category_label_id', name='uq_category_detection_photo_label'
        ),
    )

    # d) Run-Tracking, analog criterion_scoring_runs, aber ohne scoring_run_id-FK (ADR 0032 Punkt
    # 2: dieser Job schreibt ausschliesslich in photo_category_detections/category_labels, beruehrt
    # weder cluster_key noch PhotoRanking direkt).
    op.create_table(
        'remote_category_classification_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('photos_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('photos_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column(
            'last_progress_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('remote_category_classification_runs')
    op.drop_table('photo_category_detections')
    op.drop_table('category_labels')
    op.drop_column('photo_scores', 'category_override')
    op.alter_column(
        'projects', 'cloud_vision_consent_at', new_column_name='cloud_landmark_consent_at'
    )
    op.alter_column(
        'projects', 'cloud_vision_detection_enabled', new_column_name='cloud_landmark_detection_enabled'
    )
