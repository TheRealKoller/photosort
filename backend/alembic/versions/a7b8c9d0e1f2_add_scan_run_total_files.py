"""add total_files to scan_runs

Revision ID: a7b8c9d0e1f2
Revises: e5f6a7b8c9d0
Create Date: 2026-08-13 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR 0020: additive Spalte,
    # nullable/kein server_default (anders als last_progress_at oben) - NULL ist hier ein
    # bedeutungstragender Wert ("Enumerationsphase noch nicht abgeschlossen"), kein technischer
    # Platzhalter. Bereits heute laufende ("running") oder abgeschlossene Scan-Zeilen erhalten
    # dadurch bewusst NULL statt eines irrefuehrenden 0 - fuer laengst abgeschlossene Laeufe zeigt
    # das Frontend dann zwar keinen rueckwirkenden Prozent-Fortschritt mehr an, das betrifft aber
    # nur bereits vergangene Laeufe, kein laufender Zustand wird dadurch falsch dargestellt.
    op.add_column('scan_runs', sa.Column('total_files', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('scan_runs', 'total_files')
