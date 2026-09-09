"""Laufeigene Cloud-Bilanz und Live-Zaehler: fuenf Spalten + FK, eine Spalte

specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
teilschritte-und-laufeigene-cloud-bilanz.md Punkt 2, 3 und 5.

Rein additiv, keine Datenmigration, kein Backfill:

- `criterion_scoring_runs.landmark_photos_total` - Kandidatenzahl der Landmark-Phase; zugleich
  der MARKER, ob es diesen Teilschritt in diesem Lauf ueberhaupt gab.
- `criterion_scoring_runs.landmark_photos_processed` - abgesetzte Aufrufe (Erfolge UND
  Fehlschlaege), je asyncio.gather-Block fortgeschrieben.
- `criterion_scoring_runs.landmark_failed_calls` - fehlgeschlagene Einzelaufrufe, ebenso live.
- `criterion_scoring_runs.estimated_cost_usd` - die Schaetzung, mit der dieser Lauf gestartet
  wurde (ADR 0068 Punkt 5); ohne sie ist "Ist gegen Schaetzung einordenbar" nach dem Lauf
  unerfuellbar, weil derselbe Endpunkt danach nahe null schaetzt.
- `criterion_scoring_runs.remote_category_classification_run_id` - FK auf den Remote-Lauf DIESES
  Durchlaufs (ADR 0068 Punkt 3), Ersatz fuer die Heuristik "juengste Remote-Zeile des Projekts".
- `remote_category_classification_runs.failed_calls` - dasselbe wie oben fuer die Remote-Phase.

NULL-SEMANTIK (der Grund fuer "nullable, aber KEIN server_default"), exakt wie bei den
Kostenspalten der Revisionen f4a5b6c7d8e9/5ab22032843c:

    NULL = "nicht erfasst" - die Phase wurde nicht betreten, oder die Zeile stammt aus der Zeit
                             VOR dieser Revision.
    0    = "erfasst, es ist nichts passiert".

Ein `server_default='0'` an `landmark_photos_total` naehme Bestandszeilen genau diese
Unterscheidung und liesse jeden Altlauf wie einen Lauf mit leerer Landmark-Phase aussehen; an
`estimated_cost_usd` behauptete er eine Kostenaussage, die niemand getroffen hat. Deshalb bewusst
KEINER - neue Zeilen bekommen ihre Werte ueber den produktiven Schreibpfad (worker.py).

DER FREMDSCHLUESSEL IST EXPLIZIT BENANNT (`fk_criterion_scoring_runs_remote_category_
classification_run_id`) - und das ist kein Stilfrage: Es ist der erste nachtraeglich an eine
bestehende Tabelle gehaengte Fremdschluessel dieses Projekts, `Base.metadata` traegt keine
`naming_convention`, und ein per `batch_alter_table` UNBENANNT angelegter Constraint ist im
`downgrade()` unter SQLite nicht droppbar (`drop_constraint` braucht einen Namen). Der
Rueckwaertsweg dieser Migration waere ohne den Namen schlicht nicht ausfuehrbar.

`batch_alter_table` fuer beide Tabellen (Muster 5ab22032843c/e2f3a4b5c6d7): unter SQLite entsteht
ein nachtraeglicher Fremdschluessel ausschliesslich ueber den Tabellen-Neuaufbau, den `batch`
durchfuehrt. Die Zieltabelle wird dabei ueber ihren NAMEN aufgeloest und muss zum Zeitpunkt des
Neuaufbaus in der Datenbank stehen - `remote_category_classification_runs` existiert seit
Revision b3c4d5e6f7a8, also lange vorher. Ein `copy_from`/`sa.Table` im Batch-Kontext ist dafuer
nicht noetig und steht deshalb auch nicht da; der Round-Trip-Test faehrt `upgrade` und
`downgrade` unter SQLite und wuerde es merken.

Unter Postgres sind das sechs `ADD COLUMN` ohne Table-Rewrite; die Validierung des neuen FK laeuft
gegen ausschliesslich NULL-Werte und ist trivial erfuellt - keine Sperrzeit von Belang.

`downgrade()` ist verlustbehaftet (die sechs Spaltenwerte gehen verloren), aber schema-
vollstaendig umkehrbar - kein Datenbestand ausserhalb dieser Spalten wird beruehrt.

Revision ID: b8c9d0e1f2a3
Revises: a3b4c5d6e7f8
Create Date: 2026-09-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FK_NAME = "fk_criterion_scoring_runs_remote_category_classification_run_id"


def upgrade() -> None:
    with op.batch_alter_table("remote_category_classification_runs") as batch_op:
        batch_op.add_column(sa.Column("failed_calls", sa.Integer(), nullable=True))

    with op.batch_alter_table("criterion_scoring_runs") as batch_op:
        batch_op.add_column(sa.Column("landmark_photos_total", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("landmark_photos_processed", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("landmark_failed_calls", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("estimated_cost_usd", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("remote_category_classification_run_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            FK_NAME,
            "remote_category_classification_runs",
            ["remote_category_classification_run_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("criterion_scoring_runs") as batch_op:
        batch_op.drop_constraint(FK_NAME, type_="foreignkey")
        batch_op.drop_column("remote_category_classification_run_id")
        batch_op.drop_column("estimated_cost_usd")
        batch_op.drop_column("landmark_failed_calls")
        batch_op.drop_column("landmark_photos_processed")
        batch_op.drop_column("landmark_photos_total")

    with op.batch_alter_table("remote_category_classification_runs") as batch_op:
        batch_op.drop_column("failed_calls")
