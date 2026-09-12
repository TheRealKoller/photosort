"""Kategoriespalten entfallen: photo_rankings.category_key/.is_primary, photo_scores.category_override

Die erste der beiden Abloese-Migrationen. Sie nimmt die Kategorie-Ebene aus der Rangfolge: die
Partition eines Laufs ist ab hier allein `event_id`, ein Foto steht je Lauf in genau einer Zeile,
und der Unique-Constraint lautet wieder `(criterion_scoring_run_id, photo_id)`. Die dauerhafte
manuelle Uebersteuerung faellt mit ihr.

DREI SCHRITTE, in dieser Reihenfolge - die erste ist eine Auflage, keine Stilfrage:

1. Die ueberzaehligen Rangzeilen werden geloescht. Das muss dem Constraint-Tausch VORAUSGEHEN,
   sonst ist die Migration an einer nicht-leeren Datenbank nicht ausfuehrbar: der
   wiederhergestellte Constraint wuerde die vorhandenen Daten verletzen und mitten im Lauf
   abbrechen.

   Die Anweisung HERSTELLT die Nachbedingung "hoechstens eine Zeile je
   (criterion_scoring_run_id, photo_id)", statt sie vorauszusetzen. Ein blosses
   `DELETE ... WHERE is_primary = false` setzte voraus, dass es je Lauf und Foto nie zwei
   Hauptzeilen gibt - eine Eigenschaft, die im Bestand ausschliesslich der Schreibpfad und eine
   unter SQLite wirkungslose Sperre (`with_for_update()`) schuetzten, nie die Datenbank selbst.
   Es bleibt je Paar EINE Zeile: die Hauptzeile, sofern eine existiert (`is_primary DESC`), bei
   mehreren die mit der niedrigsten `id`.

   `ROW_NUMBER() OVER (PARTITION BY ...)` laeuft auf PostgreSQL und auf SQLite ab 3.25.
2. Constraint-Tausch `uq_photo_ranking_run_photo_category` -> `uq_photo_ranking_run_photo`. Beide
   Constraints sind BENANNT: `Base.metadata` traegt keine `naming_convention`, aus der ein Name
   entstuende, und ein unbenannter Constraint ist unter SQLite nicht droppbar.
3. Die drei Spalten fallen.

ACHTUNG - `downgrade()` stellt die STRUKTUR wieder her, nie die Daten.

Die drei Spalten existieren danach wieder, tragen aber keine Kategorie: `category_key` steht leer,
`is_primary` steht auf `true` (jede verbliebene Zeile IST die einzige ihres Fotos - das ist die ab
`upgrade()` geltende Invariante, keine Schaetzung), `category_override` steht auf NULL. Das
Ergebnis ist eine strukturell gueltige Datenbank, in der jedes Foto kategorielos ist. Beide
voruebergehenden `server_default` verschwinden im selben Rueckweg wieder: sie versorgen die
NOT-NULL-Bedingung des Altbestands und duerfen sie nicht ueberleben. Ein verlorener Override und
eine verlorene Nebenzeile werden aus nichts rekonstruiert. Das ist festgeschriebenes Verhalten,
kein Versehen.

Revision ID: c3d4e5f6a7b8
Revises: b7c8d9e0f1a2
Create Date: 2026-09-12 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Eine Anweisung, nicht zwei: die Auswahl der bleibenden Zeile und die Loeschung aller uebrigen
# sind dieselbe Entscheidung. Zwei Anweisungen liessen dazwischen einen Zustand zu, in dem die
# Nachbedingung schon verletzt und noch nicht hergestellt ist.
_KEEP_ONE_RANKING_ROW_PER_RUN_AND_PHOTO = """
DELETE FROM photo_rankings
WHERE id NOT IN (
    SELECT keeper.id
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY criterion_scoring_run_id, photo_id
                   ORDER BY is_primary DESC, id ASC
               ) AS row_in_partition
        FROM photo_rankings
    ) AS keeper
    WHERE keeper.row_in_partition = 1
)
"""


def upgrade() -> None:
    # Schritt 1 - VOR dem Constraint-Tausch. Siehe Modul-Docstring.
    op.execute(sa.text(_KEEP_ONE_RANKING_ROW_PER_RUN_AND_PHOTO))

    # Schritt 2 und 3 in EINEM Batch-Block: unter SQLite ist beides derselbe Tabellen-Neuaufbau,
    # und es gibt hier - anders als beim Hinzufuegen einer NOT-NULL-Spalte - keinen Default, der
    # zwischen zwei Aufbauten existieren muesste.
    with op.batch_alter_table("photo_rankings") as batch_op:
        batch_op.drop_constraint("uq_photo_ranking_run_photo_category", type_="unique")
        batch_op.create_unique_constraint(
            "uq_photo_ranking_run_photo", ["criterion_scoring_run_id", "photo_id"]
        )
        batch_op.drop_column("category_key")
        batch_op.drop_column("is_primary")

    with op.batch_alter_table("photo_scores") as batch_op:
        batch_op.drop_column("category_override")


def downgrade() -> None:
    # ZWEI Batch-Bloecke fuer photo_rankings, nie einer: `batch_alter_table` fasst unter SQLite
    # alle Operationen eines Blocks zu EINEM Tabellen-Neuaufbau zusammen. Stuenden `add_column`
    # und das Entfernen des Defaults im selben Block, haette die neu gebaute Tabelle von
    # vornherein keinen Default - und das `INSERT ... SELECT` des Altbestands scheiterte an der
    # NOT-NULL-Bedingung.
    with op.batch_alter_table("photo_rankings") as batch_op:
        batch_op.add_column(
            sa.Column("category_key", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    with op.batch_alter_table("photo_rankings") as batch_op:
        batch_op.alter_column("category_key", existing_type=sa.String(), server_default=None)
        batch_op.alter_column("is_primary", existing_type=sa.Boolean(), server_default=None)
        batch_op.drop_constraint("uq_photo_ranking_run_photo", type_="unique")
        batch_op.create_unique_constraint(
            "uq_photo_ranking_run_photo_category",
            ["criterion_scoring_run_id", "photo_id", "category_key"],
        )

    # Nullable und damit ohne Default-Bedarf: "kein Override" IST der Ausgangszustand.
    with op.batch_alter_table("photo_scores") as batch_op:
        batch_op.add_column(sa.Column("category_override", sa.String(), nullable=True))
