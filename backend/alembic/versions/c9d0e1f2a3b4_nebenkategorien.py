"""Nebenkategorien: is_primary an photo_rankings, Unique-Constraint auf (Lauf, Foto, Kategorie)

specs/features/0300-nebenkategorien.md, decisions/0069-nebenkategorien-mehrfachzugehoerigkeit-und-
konfidenzgewichtete-rangfolge.md Punkt 1/9.

Ein Foto bekommt pro Klassifizierungslauf EINE ZEILE JE KATEGORIE, zu der es gehoert; genau eine
davon ist die Hauptzeile. Dafuer drei Schritte (siehe `upgrade()` zur Aufteilung auf zwei
`batch_alter_table`-Bloecke):

1. `is_primary` (Boolean, NOT NULL) mit `server_default=sa.true()` - jede bestehende Zeile IST die
   Hauptzeile ihres Fotos. Das ist die bis hierhin geltende Invariante (Unique-Constraint auf
   (Lauf, Foto)), keine Schaetzung.
2. Der Default wird unmittelbar danach wieder ENTFERNT. Er hat genau eine Aufgabe - den Altbestand
   zu versorgen - und darf sie nicht ueberleben: bliebe er stehen, erzeugte ein Schreibpfad, der
   `is_primary` vergisst, still eine ZWEITE Hauptkategorie. Die Invariante "genau eine Hauptzeile
   je (Lauf, Foto)" ist genau das, was die Spalte tragen soll.
3. `uq_photo_ranking_run_photo` -> `uq_photo_ranking_run_photo_category`. Beide Constraints sind in
   `upgrade()` UND in `downgrade()` BENANNT: `Base.metadata` traegt keine `naming_convention`, und
   ein unbenannter Constraint ist unter SQLite nicht droppbar (dieselbe Falle wie in Revision
   b8c9d0e1f2a3).

KEIN BACKFILL, in doppelter Hinsicht und ohne Sonderfallcode: Laeufe von vor dieser Revision
behalten ihre Zeilen unveraendert (`is_primary=true`, keine Nebenzeilen) - Nebenkategorien
entstehen erst im naechsten Kriterien-Lauf. Und Klassifizierungszeilen von vor Revision
a3b4c5d6e7f8 tragen `NULL` in der Konfidenz-Abbildung; sie erzeugen auch in einem neuen Lauf keine
Nebenkategorie, weil ohne Zahl kein Massstab existiert. Ein erneuter Cloud-Aufruf findet dafuer
nicht statt (das Skip-Kriterium aus ADR 0049/0067 bleibt unangetastet).

`downgrade()` loescht VOR dem Zuruecktauschen des Constraints die Nebenzeilen
(`DELETE ... WHERE is_primary = false`) - sonst verletzte der wiederhergestellte alte Constraint
die vorhandenen Daten und der Rueckwaertsweg waere an einer produktiven Datenbank nicht
ausfuehrbar. Der Verlust ist gewollt und unvermeidbar: eine Nebenzeile hat im alten Schema keinen
Platz. Die Hauptzeilen bleiben unveraendert.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ZWEI Batch-Bloecke, nicht einer (verifiziert, nicht vermutet): `batch_alter_table` fasst
    # unter SQLite alle Operationen eines Blocks zu EINEM Tabellen-Neuaufbau zusammen. Stuenden
    # `add_column` und das Entfernen des Defaults im selben Block, haette die neu gebaute Tabelle
    # von vornherein keinen Default - und das `INSERT ... SELECT` des Altbestands scheiterte an
    # der NOT-NULL-Bedingung. Der Default muss beim ersten Aufbau existieren und beim zweiten
    # verschwinden.
    with op.batch_alter_table("photo_rankings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_primary", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )

    with op.batch_alter_table("photo_rankings") as batch_op:
        batch_op.alter_column(
            "is_primary", existing_type=sa.Boolean(), server_default=None
        )
        batch_op.drop_constraint("uq_photo_ranking_run_photo", type_="unique")
        batch_op.create_unique_constraint(
            "uq_photo_ranking_run_photo_category",
            ["criterion_scoring_run_id", "photo_id", "category_key"],
        )


def downgrade() -> None:
    # Zuerst die Nebenzeilen, dann der Constraint-Tausch - in dieser Reihenfolge laeuft der
    # Rueckwaertsweg auch an einer Datenbank MIT Nebenzeilen fehlerfrei.
    op.execute(sa.text("DELETE FROM photo_rankings WHERE is_primary = false"))
    with op.batch_alter_table("photo_rankings") as batch_op:
        batch_op.drop_constraint("uq_photo_ranking_run_photo_category", type_="unique")
        batch_op.create_unique_constraint(
            "uq_photo_ranking_run_photo", ["criterion_scoring_run_id", "photo_id"]
        )
        batch_op.drop_column("is_primary")
