"""Modellwahl je Projekt: `projects.category_method`, `category_model`, `landmark_model`

Drei additive Spalten und ein Check-Constraint, keine Datenmigration:

* `category_method` NOT NULL mit BLEIBENDEM `server_default 'cloud'` - Bestandsprojekte laufen
  damit unveraendert ueber die Cloud, ohne dass eine Zeile umgeschrieben wird.
* `category_model`/`landmark_model` sind nullbar; `NULL` heisst "Installationsvorgabe".
* `ck_projects_category_model_requires_cloud` macht die Zeile "Eye mit Cloud-Modell" unmoeglich.

Der Rueckweg entfernt Spalten und Constraint; gespeicherte Wahlen gehen dabei verloren.

Revision ID: 43a3afeb7312
Revises: 5c7633e53257
Create Date: 2026-11-08 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "43a3afeb7312"
down_revision: Union[str, Sequence[str], None] = "5c7633e53257"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Spalten und Check-Constraint an `projects`."""
    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column(
                "category_method",
                sa.String(length=20),
                nullable=False,
                server_default="cloud",
            )
        )
        batch.add_column(sa.Column("category_model", sa.String(), nullable=True))
        batch.add_column(sa.Column("landmark_model", sa.String(), nullable=True))
        batch.create_check_constraint(
            "ck_projects_category_model_requires_cloud",
            "category_method = 'cloud' OR category_model IS NULL",
        )


def downgrade() -> None:
    """Downgrade schema - entfernt Spalten und Constraint."""
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("ck_projects_category_model_requires_cloud", type_="check")
        batch.drop_column("landmark_model")
        batch.drop_column("category_model")
        batch.drop_column("category_method")
