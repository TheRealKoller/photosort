"""Kategorietabelle entfaellt: photo_category_classifications

Die zweite und letzte Abloese-Migration. Sie entfernt die Tabelle, die seit PR 2 dieser Story
nicht mehr geschrieben und nach PR 3 nicht mehr gelesen wird. Bewusst eine EIGENE Revision nach
den Spalten: die Spaltenmigration beruehrt die Rangfolge, diese hier eine ganze Tabelle - ein
Rueckweg soll das eine ohne das andere koennen.

Der Datenverlust ist eine getroffene Entscheidung (Spec 0427, Abschnitt "Entscheidungen"): die
bereits bezahlten Kategoriekonfidenzen frueherer Cloud-Laeufe gehen dabei verloren. Motivstaerken
brauchen ohnehin einen neuen Lauf. Kein Export, keine Sicherungstabelle, kein Anhalten.

ACHTUNG - `downgrade()` stellt die STRUKTUR wieder her, nie die Daten.

Die Tabelle existiert danach wieder und ist LEER. Es gibt kein `INSERT`, keine Rekonstruktion aus
den Motivstaerken und keinen Weg zurueck zu den geloeschten Zeilen: eine Motivstaerke ist eine
andere Aussage als eine Kategoriekonfidenz, und ein aus ihr abgeleiteter Wert waere eine
Modellaussage, die das Modell nie getroffen hat. Das ist festgeschriebenes Verhalten, kein
Versehen.

Revision ID: c4d5e6f7a8b9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-12 18:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PHOTO_FK = "fk_photo_category_classifications_photo_id"


def upgrade() -> None:
    op.drop_table("photo_category_classifications")


def downgrade() -> None:
    """Legt die Tabelle in der Form wieder an, die sie zuletzt hatte (Revision
    b3c4d5e6f7a8 plus die beiden Konfidenzspalten aus a3b4c5d6e7f8) - LEER."""
    op.create_table(
        "photo_category_classifications",
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("category_key", sa.String(), nullable=False),
        sa.Column("detected_categories", sa.JSON(), nullable=False),
        sa.Column("detected_category_confidences", sa.JSON(), nullable=True),
        sa.Column("category_confidence", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], name=_PHOTO_FK),
        sa.PrimaryKeyConstraint("photo_id"),
    )
