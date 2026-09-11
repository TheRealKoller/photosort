"""GPS-Koordinaten am Foto: photos.gps_lat / photos.gps_lon

Zwei nullable Gleitkommaspalten.

Rein additiv: zwei NULLABLE Gleitkommaspalten an `photos`. Keine bestehende Spalte aendert sich,
kein Constraint, kein Index.

KEIN `server_default` - und das ist hier die eigentliche Aussage, nicht eine Auslassung: `0.0`
ist eine GUELTIGE Koordinate (Golf von Guinea, "Null Island"), keine Abwesenheitsmarkierung. Ein
Default machte aus jeder Bestandszeile eine Ortsangabe und risse jedes Zeit-Cluster, in dem eine
solche Zeile liegt, gleich zweimal auf (beim Hinein- und beim Hinauslaufen des 500-m-Vergleichs).
"Kein Ort bekannt" muss `NULL` bleiben.

KEIN BACKFILL (Daniels Entscheidung, siehe "Out of Scope" der Spec): der Scan ueberspringt Dateien
mit unveraendertem `Etag` (`worker.py::_classify_scan_entries`), und die Cache-Varianten tragen
kein EXIF mehr (`thumbnails.py::generate_variants`) - bereits gescannte Fotos bekommen ihre
Koordinaten erst, wenn sich die Datei auf OpenCloud aendert. Ein Nachzug haette eine Markerspalte
und einen zusaetzlichen Arbeitsposten im Scan gebraucht und wurde bewusst verworfen.

`downgrade()` entfernt beide Spalten. Der Verlust ist unvermeidbar und folgenlos: die Werte sind
reine EXIF-Ableitungen und entstehen beim naechsten Scan der Datei erneut.

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-09-09 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # EIN Batch-Block fuer beide Spalten (anders als in Revision c9d0e1f2a3b4, wo ein
    # server_default zwei Bloecke erzwang): unter SQLite baut `batch_alter_table` die Tabelle
    # einmal neu, mit beiden Spalten auf einmal - hier ist kein Zwischenzustand noetig, weil keine
    # NOT-NULL-Bedingung und kein Default zu versorgen ist.
    with op.batch_alter_table("photos") as batch_op:
        batch_op.add_column(sa.Column("gps_lat", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("gps_lon", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("photos") as batch_op:
        batch_op.drop_column("gps_lon")
        batch_op.drop_column("gps_lat")
