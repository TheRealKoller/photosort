"""ablauf_uebersicht_gesehen: je Person und Projekt der Merker "Ablaufuebersicht gesehen"

`project_overview_seen` traegt genau `(user_id, project_id)` als Primaerschluessel. Die
Abwesenheit der Zeile heisst "nicht gesehen". Die Migration schreibt KEINE Zeile: Bestehende
Projekte gelten damit fuer beide Personen als ungesehen, und die Uebersicht erscheint beim ersten
Oeffnen nach der Einfuehrung.

Beide Fremdschluessel sind echt und benannt. Der echte Fremdschluessel auf `projects` haelt die
Tabelle in der Erreichbarkeitspruefung der Projektloeschung; ein unbenannter waere unter SQLite
im Rueckwaertsweg nicht droppbar (`Base.metadata` traegt keine `naming_convention`).

Revision ID: 1d3dbfdde02e
Revises: b0814fc600bf
Create Date: 2026-10-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1d3dbfdde02e"
down_revision: Union[str, Sequence[str], None] = "b0814fc600bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "project_overview_seen"


def upgrade() -> None:
    """Upgrade schema - legt die Tabelle an, ohne eine einzige Zeile zu schreiben."""
    op.create_table(
        _TABLE,
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_project_overview_seen_user_id"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_project_overview_seen_project_id"
        ),
        sa.PrimaryKeyConstraint("user_id", "project_id"),
    )


def downgrade() -> None:
    """Downgrade schema.

    Mit der Tabelle sind alle Merker verloren: Danach erscheint die Ablaufuebersicht in jedem
    Projekt fuer beide Personen erneut von selbst, sobald die Tabelle wieder angelegt ist."""
    op.drop_table(_TABLE)
