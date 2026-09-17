"""restdauer: neue Spalte `criterion_scoring_runs.phase_started_at`

REIN ADDITIV, NULLABLE, OHNE server_default und OHNE Datenwanderung.

Die Spalte beschreibt den Beginn genau des Teilschritts, den `phase` daneben nennt - die
Messgrundlage der Restdauer. `NULL` heisst "kein laufender Teilschritt" (beendet, abgebrochen,
oder Altzeile), nie "gerade begonnen".

Kein Backfill, und das ist die eigentliche Aussage: Ein Lauf, der zum Zeitpunkt der Migration
bereits laeuft, traegt `phase` schon, aber keinen Beginn. Er faellt bis zum naechsten Teilschritt
in den regulaeren `null`-Zweig und zeigt dort "wird noch ermittelt". Ein `server_default`
(`now()`) machte daraus einen ERFUNDENEN Beginn: Die Restdauer rechnete dann mit einem
Durchsatz, der die gesamte bisherige Laufzeit unterschlaegt, und waere um genau diesen Anteil zu
klein - ohne Ausnahme und ohne dass irgendetwas fehlschluege.

`downgrade()` nimmt die Spalte zurueck. Verloren geht ausschliesslich die Messgrundlage einer
Anzeige; der naechste Teilschritt jedes Laufs setzt sie erneut.

Revision ID: c5bc9a02c3c2
Revises: bcc517b1ab22
Create Date: 2026-09-17 17:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5bc9a02c3c2"
down_revision: Union[str, Sequence[str], None] = "bcc517b1ab22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("criterion_scoring_runs") as batch:
        batch.add_column(sa.Column("phase_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("criterion_scoring_runs") as batch:
        batch.drop_column("phase_started_at")
