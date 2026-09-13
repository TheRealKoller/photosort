"""endauswahl: die gemeinsame projektentscheidung bekommt ihre eigene tabelle

`final_selection_decisions` traegt die ausdrueckliche Entscheidung des PROJEKTS ueber ein Foto
(ADR 0099). Die Endauswahl selbst ist abgeleitet und wird nirgends materialisiert.

DATENLOS in beide Richtungen: Es gibt vor dieser Story keine Entscheidungszeilen, und kein Schritt
berechnet rueckwirkend etwas. Die Endauswahl eines bestehenden Projekts ist damit genau die
Schnittmenge der beiden Entwuerfe.

`photo_id` ist Primaerschluessel UND Fremdschluessel - "hoechstens eine Entscheidung je Foto" ist
damit strukturell wahr, ohne eigenen Unique-Constraint. Der echte Fremdschluessel ist Pflicht: Die
Loeschzusage in `project_deletion.py` prueft Erreichbarkeit ueber die Kanten in `Base.metadata`,
eine bloss logische Spalte fiele still aus der Pruefung heraus. Sein Name ist ausgeschrieben, weil
`Base.metadata` keine `naming_convention` traegt und ein unbenannter Fremdschluessel unter SQLite
im Rueckwaertsweg nicht droppbar waere.

`included` traegt KEINEN Default, weder Python- noch server-seitig: Die Abwesenheit der Zeile
heisst "unentschieden", und ein Vorgabewert erfaende eine Entscheidung, die niemand getroffen hat.

ACHTUNG - `downgrade()` VERLIERT DATEN, siehe seinen Docstring.

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-09-13 19:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "final_selection_decisions"


def upgrade() -> None:
    """Upgrade schema - legt die Tabelle an, ohne eine einzige Zeile zu schreiben."""
    op.create_table(
        _TABLE,
        sa.Column("photo_id", sa.Integer(), nullable=False),
        # Ohne `server_default`: siehe Modul-Docstring. Der Wert wird ausdruecklich geschrieben
        # oder die Zeile existiert nicht.
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["photo_id"], ["photos.id"], name="fk_final_selection_decisions_photo_id"
        ),
        sa.PrimaryKeyConstraint("photo_id"),
    )


def downgrade() -> None:
    """Downgrade schema.

    STELLT DIE STRUKTUR WIEDER HER, NIE DIE DATEN: Mit der Tabelle sind ALLE gemeinsamen
    Entscheidungen verloren. Die beiden Einzelentwuerfe bleiben unberuehrt - sie haben die
    Endauswahl nie getragen -, aber jede ausdrueckliche Aufnahme und jede ausdrueckliche
    Herausnahme ist danach fort, und die Endauswahl faellt auf die reine Schnittmenge zurueck.
    Ein Rueckweg, der sie erhielte, gibt es nicht: es existiert keine zweite Stelle, an der sie
    stuenden."""
    op.drop_table(_TABLE)
