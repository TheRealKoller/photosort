"""auswahlvorschlag: richtwert je projekt, platz je rangzeile

Zwei additive, NULLBARE Spalten, kein Backfill und keine Datenmanipulation:

a) `projects.selection_target` - der eingestellte Richtwert des Auswahlvorschlags. `NULL` heisst
   "nicht selbst eingestellt"; wirksam ist dann ein Zehntel der Bilderzahl. Die Vorbelegung wird
   nie in die Spalte geschrieben.
b) `photo_rankings.selection_position` - der 1-basierte Platz eines Fotos innerhalb seines
   Events. `NULL` heisst "gehoert nicht zum Vorschlag".

KEIN `server_default` an beiden Spalten: `NULL` traegt hier in beiden Faellen Bedeutung, und ein
Default `0` oder `10` machte daraus stillschweigend eine Aussage.

Bestandslaeufe tragen danach in allen Zeilen `NULL` und zeigen einen leeren Vorschlag, bis ein
neuer Lauf oder eine Richtwert-Aenderung ihn erzeugt - es gibt bewusst keine Migration, die ihn
rueckwirkend berechnet.

ACHTUNG - `downgrade()` stellt die STRUKTUR wieder her, nie die Daten: ein danach erneutes
`upgrade()` liefert beide Spalten leer zurueck.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-13 13:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("projects", sa.Column("selection_target", sa.Integer(), nullable=True))
    op.add_column("photo_rankings", sa.Column("selection_position", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema.

    Stellt die STRUKTUR wieder her, nie die Daten - siehe Modul-Docstring."""
    op.drop_column("photo_rankings", "selection_position")
    op.drop_column("projects", "selection_target")
