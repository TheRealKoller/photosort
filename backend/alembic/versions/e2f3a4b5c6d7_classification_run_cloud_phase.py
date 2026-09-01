"""criterion_scoring_runs: phase, cloud_requested, cloud_error_message

specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, decisions/0050-verketteter-
klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md Punkt 3.

Rein additiv, keine Datenmigration: `criterion_scoring_runs` traegt ab dieser Revision den
Run-Datensatz des GESAMTEN Klassifizierungslaufs (Remote-Kategorisierung -> Kriterien-Bewertung)
statt nur seiner Kriterien-Phase.

- `phase` (nullable): der gerade laufende Teilschritt (`remote_categories`/`criteria`); NULL
  heisst "laeuft nicht mehr". Altzeilen bekommen NULL - sie stammen aus der Zeit der getrennten
  Ausloesung und liefen per Definition nur die Kriterien-Phase, sind aber laengst beendet.
- `cloud_requested` (NOT NULL, Server-Default false): war die Cloud-Nutzung fuer diesen Lauf
  angefordert? Fuer Altzeilen ist die Frage nachtraeglich nicht beantwortbar - `false` ist die
  Antwort, die nichts Falsches verspricht (die Oberflaeche zeigt daraufhin "ohne Cloud-
  Anreicherung durchgefuehrt", nicht etwa eine Anreicherung, die es ggf. nie gab).
- `cloud_error_message` (nullable): laufweite Zusammenfassung der Cloud-Probleme, NULL = keine.

`server_default="0"` auf `cloud_requested` ist fuer den Bestand noetig (NOT NULL ohne Default
scheitert an vorhandenen Zeilen) und bleibt danach bewusst stehen: SQLite kann eine Spalten-
Default-Definition nicht ohne Tabellen-Neuaufbau entfernen, und der Wert deckt sich mit dem
Modell-Default (models.py::CriterionScoringRun.cloud_requested).

`downgrade()` ist verlustbehaftet (die drei Spaltenwerte gehen verloren), aber schema-vollstaendig
umkehrbar - kein Datenbestand ausserhalb dieser drei Spalten wird beruehrt.

Revision ID: e2f3a4b5c6d7
Revises: d5e6f7a8b9c0
Create Date: 2026-09-01 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("criterion_scoring_runs") as batch_op:
        batch_op.add_column(sa.Column("phase", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column(
                "cloud_requested",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(sa.Column("cloud_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("criterion_scoring_runs") as batch_op:
        batch_op.drop_column("cloud_error_message")
        batch_op.drop_column("cloud_requested")
        batch_op.drop_column("phase")
