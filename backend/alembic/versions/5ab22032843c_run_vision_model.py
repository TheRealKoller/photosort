"""Modell-ID je Cloud-Lauf: eine Spalte an beiden Run-Tabellen

specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, decisions/0059-modellwahl-je-anbieter-
und-modellgebundene-kostenschaetzung.md Punkt 6.

Rein additiv, keine Datenmigration:

- `criterion_scoring_runs`: `landmark_model` - die Modell-ID der Landmark-Phase dieses Laufs.
  Praefix analog den vier Kostenspalten derselben Tabelle (die Tabelle traegt seit ADR 0050 den
  GESAMTEN Klassifizierungslauf).
- `remote_category_classification_runs`: `model` - die Modell-ID dieses Laufs. Kein Praefix,
  dieser Lauf hat genau einen Zweck.

WARUM UEBERHAUPT: mit Spec 0304 wird die Modellwahl je Anbieter zu einer Betriebseinstellung
(`LANDMARK_MODEL`). Der bereits persistierte `provider` je Foto sagt seitdem nicht mehr, WOMIT ein
Lauf gerechnet hat - und das Modell ist die Preisgrundlage des in derselben Zeile eingefrorenen
Betrags. Ohne diese Spalte waere ein historischer Betrag nach einer erkannten Preiskorrektur nicht
mehr nachrechenbar und ein Modellvergleich nicht auswertbar (Akzeptanzkriterium "aus welchem
Modell ein durchgefuehrter Lauf entstanden ist, bleibt nachtraeglich erkennbar").

NULL-SEMANTIK (der Grund fuer "nullable, aber KEIN server_default"), exakt wie bei den
Kostenspalten der Revision f4a5b6c7d8e9:

    NULL = "nicht erfasst" - die Zeile stammt aus der Zeit VOR dieser Revision. Ein Ruecksetzen
                             auf das damalige Voreinstellungs-Modell waere eine Behauptung ueber
                             die Vergangenheit, die diese Migration nicht belegen kann.

Ein `server_default` mit einer Modell-ID wuerde Bestandszeilen genau diese Unterscheidung nehmen -
deshalb bewusst KEINER. Neue Zeilen bekommen ihren Wert ueber den produktiven Schreibpfad
(worker.py, im selben Commit wie der eingefrorene Betrag); der Python-seitige Modell-Default ist
`None`, dasselbe `ScanRun.total_files`-Idiom.

`sa.String()` ohne Laengenbegrenzung, analog `PhotoLandmarkDetection.provider` und den uebrigen
freien Schluesselspalten des Datenmodells (`criterion_key`, `category_key`) - Modell-IDs sind
kurze, vom Anbieter vergebene Kennungen, eine willkuerliche Obergrenze braechte nur ein
Migrationsrisiko beim naechsten laengeren Namen.

`downgrade()` ist verlustbehaftet (die beiden Spaltenwerte gehen verloren), aber schema-
vollstaendig umkehrbar - kein Datenbestand ausserhalb dieser Spalten wird beruehrt.

Revision ID: 5ab22032843c
Revises: f4a5b6c7d8e9
Create Date: 2026-09-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ab22032843c'
down_revision: Union[str, Sequence[str], None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("criterion_scoring_runs") as batch_op:
        batch_op.add_column(sa.Column("landmark_model", sa.String(), nullable=True))

    with op.batch_alter_table("remote_category_classification_runs") as batch_op:
        batch_op.add_column(sa.Column("model", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("remote_category_classification_runs") as batch_op:
        batch_op.drop_column("model")

    with op.batch_alter_table("criterion_scoring_runs") as batch_op:
        batch_op.drop_column("landmark_model")
