"""ortsauskunft: neue Tabelle `place_lookups`, neue Spalte `events.place_name`

REIN ADDITIV. Keine Zeile wird geloescht, kein bestehender Wert geaendert, und es wird NICHTS
nachgezogen: `events.place_name` bleibt fuer jeden bestehenden Lauf `NULL`. Das ist eine Zusage
und keine Auslassung - die Namen eines Laufs entstehen im Lauf, aus den Events dieses Laufs; ein
nachtraeglich eingesetzter Name haette keine Gleichnamigkeitspruefung hinter sich.

`place_lookups` traegt die Auskunft ueber eine vergroeberte Ortszelle, projektgebunden und
lauf-unabhaengig. Der Fremdschluessel auf `projects.id` ist ECHT und NOT NULL: an ihm haengt die
Zusage, dass diese Ortsspur mit dem Projekt verschwindet - eine bloss logische Spalte fiele aus
der Erreichbarkeitspruefung der Projektloeschung still heraus.

`UniqueConstraint(project_id, cell_lat, cell_lon)` traegt die Wiederverwendung: eine Zelle wird je
Projekt genau einmal beschafft. `project_id` steht bewusst IM Constraint - dieselbe Zelle in einem
zweiten Projekt ist eine eigene Zeile und wird erneut gefragt.

`downgrade()` nimmt beides zurueck. Es verliert die abgelegten Ortsauskuenfte und die Namen des
letzten Laufs; beide sind wiederherstellbar (erneuter Lauf, lokale Rechenzeit, kein Geld) - anders
als die Ist-Kosten einer Lauf-Zeile.

Revision ID: d7e8f9a0b1c2
Revises: c5d6e7f8a9b0
Create Date: 2026-09-14 16:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Explizite Constraint-Namen: ein per `batch_alter_table` UNBENANNT angelegter Fremdschluessel ist
# im `downgrade()` unter SQLite nicht droppbar, und `Base.metadata` traegt keine
# `naming_convention`, aus der einer entstuende.
_PLACE_LOOKUP_PROJECT_FK = "fk_place_lookups_project_id"
_PLACE_LOOKUP_CELL_UNIQUE = "uq_place_lookup_project_cell"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "place_lookups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        # GLEITKOMMA, nicht Ganzzahl: der Schluessel IST das gerundete Zahlenpaar der Zelle.
        sa.Column("cell_lat", sa.Float(), nullable=False),
        sa.Column("cell_lon", sa.Float(), nullable=False),
        sa.Column("neighbourhood", sa.String(), nullable=True),
        sa.Column("locality", sa.String(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("matched_level", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=_PLACE_LOOKUP_PROJECT_FK),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "cell_lat", "cell_lon", name=_PLACE_LOOKUP_CELL_UNIQUE),
    )

    with op.batch_alter_table("events") as batch:
        batch.add_column(sa.Column("place_name", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("events") as batch:
        batch.drop_column("place_name")

    op.drop_table("place_lookups")
