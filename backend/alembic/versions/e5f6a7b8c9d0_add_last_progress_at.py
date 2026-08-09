"""add last_progress_at to scan_runs/scoring_runs/top_selection_runs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-09 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md, ADR 0019):
    # additive Spalte auf allen drei Run-Tabellen, server_default=now() analog started_at. Bereits
    # heute hängende running-Zeilen erhalten dadurch den Migrationszeitpunkt als Startwert -
    # gewollter Nebeneffekt (siehe Spec, Abschnitt "Datenmodell-Bezug"), kein separater Backfill
    # nötig.
    op.add_column(
        'scan_runs',
        sa.Column('last_progress_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.add_column(
        'scoring_runs',
        sa.Column('last_progress_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.add_column(
        'top_selection_runs',
        sa.Column('last_progress_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('top_selection_runs', 'last_progress_at')
    op.drop_column('scoring_runs', 'last_progress_at')
    op.drop_column('scan_runs', 'last_progress_at')
