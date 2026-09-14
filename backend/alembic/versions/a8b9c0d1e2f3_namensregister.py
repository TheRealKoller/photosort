"""namensregister: neue Tabelle `landmark_names`, neue Spalte
`photo_landmark_detections.canonical_name`

REIN ADDITIV. Keine Zeile wird geloescht, kein bestehender Wert geaendert, und es wird NICHTS
nachgezogen: `canonical_name` bleibt fuer jede bestehende Erkennungszeile `NULL`. Das ist eine
Zusage und keine Auslassung - ein Nachziehen frueherer Laeufe braeuchte fuer jede Zeile einen
Einbettungsvektor, und ohne die Spalte verhaelt sich eine Altzeile exakt wie zuvor (sie faellt auf
ihren Rohnamen zurueck).

Insbesondere wird KEINE unsichere Erkennungszeile geloescht: Die Antwort ist bezahlt und bleibt
vollstaendig erhalten; ob aus ihr ein verwendbarer Name wird, entscheidet die Lesestelle.

Ebenso unberuehrt bleibt `projects.cloud_vision_detection_enabled`: Bereits erteilte
Cloud-Einwilligungen bleiben gueltig und werden nicht zurueckgesetzt (Daniel, 2026-09-14).

`landmark_names` traegt das projektgebundene Namensregister. Der Fremdschluessel auf `projects.id`
ist ECHT und NOT NULL: An ihm haengt die Zusage, dass das Register mit dem Projekt verschwindet -
eine bloss logische Spalte fiele aus der Erreichbarkeitspruefung der Projektloeschung still heraus,
und beide Vollstaendigkeitstests prueften die Tabelle dann nicht mehr.

`UniqueConstraint(project_id, normalized_name)` haelt je Projekt genau einen Eintrag je Name.
`project_id` steht bewusst IM Constraint - dieselbe Sehenswuerdigkeit in einem zweiten Projekt ist
eine eigene Zeile und wird nie mit der ersten zusammengefuehrt.

`downgrade()` nimmt beides zurueck. Es verliert das Register und die kanonischen Namen des letzten
Laufs; beide sind wiederherstellbar (erneuter Neuaufbau der Gruppierung bzw. ein weiterer
Erkennungslauf) - anders als die Ist-Kosten einer Lauf-Zeile.

Revision ID: a8b9c0d1e2f3
Revises: e3f4a5b6c7d8
Create Date: 2026-09-14 17:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Explizite Constraint-Namen: ein per `batch_alter_table` UNBENANNT angelegter Fremdschluessel ist
# im `downgrade()` unter SQLite nicht droppbar, und `Base.metadata` traegt keine
# `naming_convention`, aus der einer entstuende.
_LANDMARK_NAME_PROJECT_FK = "fk_landmark_names_project_id"
_LANDMARK_NAME_UNIQUE = "uq_landmark_name_project_normalized"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "landmark_names",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        # Der Einbettungsvektor als JSON-Liste von float, wie `fine_labels.embedding`.
        sa.Column("embedding", sa.JSON(), nullable=False),
        # Der aufgeloeste Ortsname wirkt als SPERRE und nie als Schluessel - er darf fehlen.
        sa.Column("locality", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=_LANDMARK_NAME_PROJECT_FK),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "normalized_name", name=_LANDMARK_NAME_UNIQUE),
    )

    with op.batch_alter_table("photo_landmark_detections") as batch:
        batch.add_column(sa.Column("canonical_name", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("photo_landmark_detections") as batch:
        batch.drop_column("canonical_name")

    op.drop_table("landmark_names")
