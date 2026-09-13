"""albumtauglichkeit: neue Tabelle photo_album_suitability, Rangspalten nullable

Eine REINE Strukturaenderung:

a) `photo_album_suitability` - die Albumtauglichkeit je Foto (1:1, `photo_id` ist Primary Key UND
   Fremdschluessel auf `photos`). `level` und `provider` sind NOT NULL, `reason` nullable: ohne
   brauchbare Begruendung steht dort `NULL`, nie eine leere Zeichenkette.
b) `photo_rankings.rank_score`/`.rank_position` werden nullable. `NULL` heisst "kein
   Qualitaetswert, weil keine Modellbewertung". `event_id` bleibt NOT NULL - die Gliederung nach
   Events ist keine Cloud-Leistung, und ein Foto ohne Modellurteil bleibt im einsehbaren Vorrat.
c) KEIN Backfill und KEINE Datenmanipulation, auch keine Ruecksetzung der Bestandswerte auf
   `NULL`. Die vorhandenen Werte stammen aus der alten Formel und waeren unter den neuen
   Anzeigeschwellen falsch zu lesen - sie werden trotzdem nicht angefasst, weil der Bestand nach
   der Umsetzung verworfen wird (Spec 0428, "Entscheidungen"). Eine Datenmanipulation waere Arbeit
   an einem Bestand, den es danach nicht mehr gibt.

ACHTUNG - `downgrade()` stellt die STRUKTUR wieder her, nie die Daten.

Die Albumtauglichkeiten sind danach unwiederbringlich fort, und die Rangzeilen OHNE
Qualitaetswert entfallen: sie passen nicht mehr in die strikte Form, und ein erfundener Ersatzwert
waere eine Aussage, die kein Modell getroffen hat. Das ist festgeschriebenes Verhalten, kein
Versehen.

Revision ID: d6e7f8a9b0c1
Revises: c4d5e6f7a8b9
Create Date: 2026-09-13 09:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Expliziter Constraint-Name: `Base.metadata` traegt keine `naming_convention`, aus der einer
# entstuende, und ein unbenannter Constraint ist im `downgrade()` nicht droppbar.
_SUITABILITY_PHOTO_FK = "fk_photo_album_suitability_photo_id"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "photo_album_suitability",
        sa.Column("photo_id", sa.Integer(), nullable=False),
        # `Integer` und nicht `Float`: die Stufe ist ein Anker, kein Messwert. Der normierte Wert
        # entsteht bei jeder Rechnung neu und bekommt bewusst keine zweite Spalte.
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], name=_SUITABILITY_PHOTO_FK),
        sa.PrimaryKeyConstraint("photo_id"),
    )

    # `batch_alter_table`, weil SQLite kein `ALTER COLUMN` kennt: alembic baut die Tabelle dort
    # nach. Unter Postgres laeuft dieselbe Anweisung als gewoehnliches `ALTER COLUMN`.
    with op.batch_alter_table("photo_rankings") as batch_op:
        batch_op.alter_column("rank_score", existing_type=sa.Float(), nullable=True)
        batch_op.alter_column("rank_position", existing_type=sa.Integer(), nullable=True)

    # c) Kein Backfill, keine Ruecksetzung - siehe Modul-Docstring.


def downgrade() -> None:
    """Downgrade schema.

    Stellt die STRUKTUR wieder her, nie die Daten - siehe Modul-Docstring. Die Reihenfolge ist
    Teil der Aussage: erst muessen die Zeilen ohne Qualitaetswert fallen, sonst scheitert das
    Wiederherstellen der NOT-NULL-Bedingung an ihnen."""
    op.execute("DELETE FROM photo_rankings WHERE rank_score IS NULL OR rank_position IS NULL")
    with op.batch_alter_table("photo_rankings") as batch_op:
        batch_op.alter_column("rank_score", existing_type=sa.Float(), nullable=False)
        batch_op.alter_column("rank_position", existing_type=sa.Integer(), nullable=False)

    op.drop_table("photo_album_suitability")
