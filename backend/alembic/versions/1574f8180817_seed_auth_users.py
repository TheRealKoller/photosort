"""seed auth users

Revision ID: 1574f8180817
Revises: c6c17d0ef6d5
Create Date: 2026-07-21 22:00:39.953987

"""
from typing import Sequence, Union

from alembic import op

from photosort.config import settings
from photosort.seed import seed_configured_users

# revision identifiers, used by Alembic.
revision: str = '1574f8180817'
down_revision: Union[str, Sequence[str], None] = 'c6c17d0ef6d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Idempotente Seed-Migration fuer die zwei bekannten PhotoSort-Nutzer.

    Legt fehlende Accounts aus AUTH_SEED_USER1/2_USERNAME/PASSWORD (.env) an; bestehende
    password_hash-Werte werden nie ueberschrieben (siehe specs/features/0006-auth.md).
    """
    bind = op.get_bind()
    seed_configured_users(
        bind,
        [
            (settings.auth_seed_user1_username, settings.auth_seed_user1_password),
            (settings.auth_seed_user2_username, settings.auth_seed_user2_password),
        ],
    )


def downgrade() -> None:
    """Absichtlich kein Downgrade: wuerde echte Nutzerkonten loeschen."""
