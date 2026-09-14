"""feedback events: die nacharbeit am album-entwurf bekommt ihr eigenes append-only log

`feedback_events` haelt, DASS korrigiert wurde (ADR 0100). Das Zustandsmodell (`ratings`,
`photo_motif_corrections`, `final_selection_decisions`) bleibt unveraendert und haelt weiter nur
den heutigen Stand.

DATENLOS in beide Richtungen: Es gibt vor dieser Story keine Ereigniszeilen, und kein Schritt
leitet welche aus dem Bestand ab - er koennte es auch nicht. Eine zurueckgenommene Korrektur
hinterlaesst im Bestand keine Spur, zwei Korrekturen am selben Foto sind dort nicht
unterscheidbar.

`event_id` TRAEGT KEINEN FREMDSCHLUESSEL, obwohl die Spalte wie eine Referenz aussieht:
`worker.py::rebuild_run_grouping` loescht die `events`-Zeilen eines Laufs und legt sie neu an. Ein
echter Fremdschluessel hielte entweder den Neuaufbau an oder risse Zeilen dieses Logs mit - beides
braeche die Append-only-Zusage, auf der jede Zahl der Diagnose ruht. Gueltig ist die Spalte allein
zusammen mit dem `criterion_scoring_run_id` derselben Zeile.

`user_id` ist NULLBAR, und `NULL` heisst "keine Zuschreibung": Die gemeinsame Entscheidung der
Endauswahl gehoert nach ADR 0099 dem Projekt und nicht einem Nutzer.

`project_id` ist eine EIGENE Spalte und wird nie ueber den Foto-Join hergeleitet - die
Projektloeschung prueft Erreichbarkeit ueber die Kanten in `Base.metadata`, und der Index traegt
sie, weil das Log mit jeder Korrektur waechst.

ACHTUNG - `downgrade()` VERLIERT DATEN, siehe seinen Docstring.

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-13 21:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "feedback_events"
_PROJECT_INDEX = "ix_feedback_events_project_id"


def upgrade() -> None:
    """Upgrade schema - legt die Tabelle an, ohne eine einzige Zeile zu schreiben."""
    op.create_table(
        _TABLE,
        # `id` IST die Reihenfolge (ADR 0100 Punkt 1) - `occurred_at` ist Anzeige und nie
        # Sortierschluessel.
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        # Nullbar: `NULL` heisst "keine Zuschreibung", siehe Modul-Docstring.
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        # `native_enum=False`: ein neuer Wert erzwingt sonst unter Postgres eine Typmigration,
        # waehrend SQLite sie nie verlangt - der Unterschied faellt erst produktiv auf.
        sa.Column(
            "kind",
            sa.Enum(
                "photo_included",
                "photo_removed",
                "decision_withdrawn",
                "exchanged",
                "motif_added",
                "motif_dropped",
                "motif_correction_withdrawn",
                "final_decision_in",
                "final_decision_out",
                native_enum=False,
                length=32,
                name="feedbackeventkind",
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # `server_default` hier UND am Modell, damit beide dieselbe DDL lesen: Eine ueber rohes
        # SQL eingefuegte Zeile traegt sonst kein Gewicht, und die Ableitung multiplizierte mit
        # `NULL`.
        sa.Column("weight", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("criterion_scoring_run_id", sa.Integer(), nullable=True),
        # OHNE `ForeignKeyConstraint`, siehe Modul-Docstring. Die Abwesenheit ist die Zusage.
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("replaced_photo_id", sa.Integer(), nullable=True),
        sa.Column("motif_key", sa.String(), nullable=True),
        sa.Column("motif_strength", sa.Float(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("replaced_level", sa.Integer(), nullable=True),
        sa.Column("quality", sa.Float(), nullable=True),
        sa.Column("replaced_quality", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"]),
        sa.ForeignKeyConstraint(["replaced_photo_id"], ["photos.id"]),
        sa.ForeignKeyConstraint(["criterion_scoring_run_id"], ["criterion_scoring_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(_PROJECT_INDEX, _TABLE, ["project_id"])


def downgrade() -> None:
    """Downgrade schema.

    STELLT DIE STRUKTUR WIEDER HER, NIE DIE DATEN: Mit der Tabelle ist JEDE aufgezeichnete
    Korrektur verloren, und es gibt keine zweite Stelle, an der sie stuende. Der Bestand haelt den
    heutigen Stand - dass ein Bild ausgetauscht, eine Entscheidung zurueckgenommen oder ein Motiv
    zweimal korrigiert wurde, ist daraus nicht mehr ableitbar. Die Diagnose faellt danach auf
    ihren Nullzustand zurueck, ohne dass irgendetwas das als Verlust ausweist."""
    op.drop_index(_PROJECT_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
