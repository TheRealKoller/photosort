"""Ist-Kostenerfassung der Remote-Laeufe: je vier Spalten an beiden Run-Tabellen

specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
laeufe.md Punkt 3.

Rein additiv, keine Datenmigration:

- `criterion_scoring_runs`: `landmark_api_calls`, `landmark_input_tokens`,
  `landmark_output_tokens`, `landmark_cost_usd` - der Landmark-Anteil dieses Klassifizierungs-
  laufs. Praefix, weil die Tabelle seit ADR 0050 den GESAMTEN Lauf traegt und die Kriterien-Phase
  selbst nichts kostet.
- `remote_category_classification_runs`: `api_calls`, `input_tokens`, `output_tokens`,
  `cost_usd` - der Kategorie-Anteil. Kein Praefix, dieser Lauf hat genau einen Zweck.

NULL-vs.-0-SEMANTIK (der Grund fuer "nullable, aber KEIN server_default"):

    NULL = "nicht erfasst"  - die Zeile stammt aus der Zeit VOR dieser Revision. Der Lauf hat
                              moeglicherweise echtes Geld gekostet; wie viel, weiss niemand mehr,
                              weil der Token-Verbrauch nur im Moment der API-Antwort existierte.
    0    = "erfasst, es sind keine Kosten angefallen" - z.B. ein Lauf ohne Cloud-Nutzung.

Beides zu unterscheiden ist der ganze Zweck dieser Spaltenform: die Statistikseite weist eine
unvollstaendige Summe ausdruecklich als solche aus (ADR 0051 Punkt 5, Befund (a)), statt "0,00
USD" wie eine belastbare Antwort aussehen zu lassen. Ein `server_default="0"` wuerde die
Bestandszeilen genau dieser Unterscheidung berauben - deshalb bewusst KEINER. Neue Zeilen
bekommen ihre `0` stattdessen ueber den Python-seitigen Modell-Default
(models.py::CriterionScoringRun/RemoteCategoryClassificationRun), exakt das bereits etablierte
`ScanRun.total_files`-Idiom.

`sa.Float()` fuer die beiden Betragsspalten (rendert `DOUBLE PRECISION` auf Postgres, `FLOAT` auf
SQLite): Cent-Betraege ohne Buchhaltungsanspruch, `float` ist der im gesamten Datenmodell
durchgehend verwendete Fliesskomma-Typ (ADR 0051 Punkt 3). Kein `sa.Numeric`.

`downgrade()` ist verlustbehaftet (die acht Spaltenwerte gehen verloren), aber schema-vollstaendig
umkehrbar - kein Datenbestand ausserhalb dieser Spalten wird beruehrt.

Revision ID: f4a5b6c7d8e9
Revises: e2f3a4b5c6d7
Create Date: 2026-09-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("criterion_scoring_runs") as batch_op:
        batch_op.add_column(sa.Column("landmark_api_calls", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("landmark_input_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("landmark_output_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("landmark_cost_usd", sa.Float(), nullable=True))

    with op.batch_alter_table("remote_category_classification_runs") as batch_op:
        batch_op.add_column(sa.Column("api_calls", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("input_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("output_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("cost_usd", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("remote_category_classification_runs") as batch_op:
        batch_op.drop_column("cost_usd")
        batch_op.drop_column("output_tokens")
        batch_op.drop_column("input_tokens")
        batch_op.drop_column("api_calls")

    with op.batch_alter_table("criterion_scoring_runs") as batch_op:
        batch_op.drop_column("landmark_cost_usd")
        batch_op.drop_column("landmark_output_tokens")
        batch_op.drop_column("landmark_input_tokens")
        batch_op.drop_column("landmark_api_calls")
