"""seitenverhaeltnis: neue Spalte `photos.aspect_ratio`

REIN ADDITIV, NULLABLE, OHNE server_default und OHNE Datenwanderung.

`NULL` heisst "nicht bekannt" und ist ein regulaerer Zustand - kein Fehler und keine Auslassung.
Genau er steuert die Nachhol-Runde: Sie laeuft zu Beginn jedes Projekt-Scans ueber die Fotos mit
`aspect_ratio IS NULL` und liest den Wert aus dem lokal zwischengespeicherten Vorschaubild. Ein
`server_default` machte jede Bestandszeile zu einer BEKANNTEN Angabe; die Nachhol-Runde faende
nichts mehr, und jedes Bestandsfoto zeigte dauerhaft ein erfundenes Verhaeltnis, ohne dass
irgendetwas fehlschluege.

Gespeichert wird das Verhaeltnis (Breite geteilt durch Hoehe des GEZEIGTEN Bildes, also nach
EXIF-Orientierung), nicht das Paar aus Breite und Hoehe: Die Nachhol-Runde liest aus der Vorschau
und kennt die Pixelmasse des Originals gar nicht. Ein Feldpaar, dessen Bedeutung davon abhaengt,
welcher Schreibweg es gefuellt hat, waere an jeder Lesestelle eine Falle.

`Float` und nicht `Integer`: Ein Hochformat liegt zwischen 0 und 1 und faende in einer
ganzzahligen Spalte gar nicht statt.

`downgrade()` nimmt die Spalte zurueck. Verloren geht ausschliesslich eine aus den Bilddateien
jederzeit wieder ableitbare Angabe - der naechste Projekt-Scan fuellt sie erneut.

Revision ID: bcc517b1ab22
Revises: a8b9c0d1e2f3
Create Date: 2026-09-14 22:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bcc517b1ab22"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("photos") as batch:
        batch.add_column(sa.Column("aspect_ratio", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("photos") as batch:
        batch.drop_column("aspect_ratio")
