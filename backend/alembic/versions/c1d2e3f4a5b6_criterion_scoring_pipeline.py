"""criterion scoring pipeline: photo_criterion_scores, criterion_scoring_runs, photo_rankings,
gate_confirmed_at; drop photo_scores.category/local_quality_score and top_selection_runs

specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md,
decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md - erste nicht-additive Migration im
Projekt (Akzeptanzkriterium der Spec): ein zum Deploy-Zeitpunkt noch RUNNING befindlicher alter
TopSelectionRun wird durch den Tabellen-Drop ersatzlos nicht mehr referenzierbar (dokumentiertes,
akzeptiertes Verhalten, kein Rating-Datenverlust).

Revision ID: c1d2e3f4a5b6
Revises: a7b8c9d0e1f2
Create Date: 2026-08-14 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'photo_criterion_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('photo_id', sa.Integer(), nullable=False),
        sa.Column('criterion_key', sa.String(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column(
            'source',
            sa.Enum(
                'LOCAL_HEURISTIC', 'LOCAL_ML', 'CLOUD',
                name='criterionsource', native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'photo_id', 'criterion_key', name='uq_criterion_score_photo_key'
        ),
    )

    op.add_column(
        'scoring_runs', sa.Column('gate_confirmed_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'criterion_scoring_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('scoring_run_id', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('RUNNING', 'SUCCESS', 'FAILED', name='scanstatus', native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('photos_total', sa.Integer(), nullable=False),
        sa.Column('photos_processed', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('last_progress_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['scoring_run_id'], ['scoring_runs.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'photo_rankings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('criterion_scoring_run_id', sa.Integer(), nullable=False),
        sa.Column('photo_id', sa.Integer(), nullable=False),
        sa.Column('cluster_key', sa.String(), nullable=False),
        sa.Column('category_key', sa.String(), nullable=False),
        sa.Column('rank_score', sa.Float(), nullable=False),
        sa.Column('rank_position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['criterion_scoring_run_id'], ['criterion_scoring_runs.id'], ),
        sa.ForeignKeyConstraint(['photo_id'], ['photos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'criterion_scoring_run_id', 'photo_id', name='uq_photo_ranking_run_photo'
        ),
    )

    # Copilot-Review-Finding auf PR #80 (specs/features/0037): der alte, hiermit entfernte
    # select_top-Job setzte suggested_status=ALBUM_WORTHY. Seit Spec 0037 kennt SuggestionOut nur
    # noch duplicate/low_quality - ein bestehender ALBUM_WORTHY-Altwert wuerde ohne Bereinigung
    # nach dem Deploy faelschlich als low_quality-Ausschuss-Vorschlag angezeigt. REJECTED-Werte
    # bleiben unangetastet, da sie weiterhin gueltige Ausschuss-Vorschlaege sind.
    op.execute(
        sa.text(
            "UPDATE photo_scores SET suggested_status = NULL "
            "WHERE suggested_status = 'album_worthy'"
        )
    )

    op.drop_table('top_selection_runs')
    op.drop_column('photo_scores', 'category')
    op.drop_column('photo_scores', 'local_quality_score')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'photo_scores',
        sa.Column('local_quality_score', sa.Float(), nullable=True),
    )
    op.add_column(
        'photo_scores',
        sa.Column(
            'category',
            sa.Enum('LANDSCAPE', 'DETAIL', 'PEOPLE', name='photocategory', native_enum=False, length=20),
            nullable=True,
        ),
    )

    op.create_table(
        'top_selection_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('RUNNING', 'SUCCESS', 'FAILED', name='scanstatus', native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('top_n_per_cluster', sa.Integer(), nullable=False),
        sa.Column('candidates_total', sa.Integer(), nullable=False),
        sa.Column('candidates_processed', sa.Integer(), nullable=False),
        sa.Column('suggestions_found', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.drop_table('photo_rankings')
    op.drop_table('criterion_scoring_runs')
    op.drop_column('scoring_runs', 'gate_confirmed_at')
    op.drop_table('photo_criterion_scores')
