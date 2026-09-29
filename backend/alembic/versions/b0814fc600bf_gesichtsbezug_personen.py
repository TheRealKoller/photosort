"""gesichtsbezug_personen: Box an Erkennung und Korrektur, Kante Korrektur -> Referenz

REIN ADDITIV. Keine Tabelle entsteht, keine Zeile wird geloescht, nichts wird nachgezogen:
Bestehende Erkennungen und Korrekturen behalten `NULL`. Erkennungen bekommen ihre Box mit dem
naechsten Klassifizierungslauf; frueher gezeigte Gesichter bleiben ohne Fotobezug.

* `photo_person_detections.face_box_*` - die Box des einen Kandidatengesichts.
* `photo_person_corrections.face_box_*` - die Box des gewaehlten Gesichts, nur mit `applies`.
* `photo_person_corrections.reference_id` -> `person_references`, `UNIQUE`, nur mit Box. Der
  Fremdschluessel hat KEINE `ON DELETE`-Aktion: Eine Referenz laesst sich nur loeschen, nachdem
  die Kante geleert ist. `person_references` bleibt ohne Foto- und Projektspalte.

Alle Einschraenkungen sind benannt (`Base.metadata` traegt keine `naming_convention`). SQLite
braucht fuer Pruefeinschraenkungen und Fremdschluessel den Batch-Modus.

`downgrade()` entfernt Boxen und Kante. Die Zeilen bleiben stehen, die Referenzen ebenso - danach
ohne Fotobezug, wie nach einer Projektloeschung.

Revision ID: b0814fc600bf
Revises: 1f4027405ea5
Create Date: 2026-09-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b0814fc600bf"
down_revision: Union[str, Sequence[str], None] = "1f4027405ea5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BOX_COLUMNS = ("face_box_x", "face_box_y", "face_box_width", "face_box_height")


def _box_condition() -> str:
    """Wortgleich mit `models.py::_face_box_check`: jede Spalte ausdruecklich `IS NOT NULL`, sonst
    ginge eine unvollstaendige Box ueber "unbekannt" durch."""
    return (
        "(face_box_x IS NULL AND face_box_y IS NULL AND face_box_width IS NULL"
        " AND face_box_height IS NULL)"
        " OR (face_box_x IS NOT NULL AND face_box_y IS NOT NULL AND face_box_width IS NOT NULL"
        " AND face_box_height IS NOT NULL"
        " AND face_box_x >= 0 AND face_box_x <= 1 AND face_box_y >= 0 AND face_box_y <= 1"
        " AND face_box_width > 0 AND face_box_width <= 1"
        " AND face_box_height > 0 AND face_box_height <= 1)"
    )


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("photo_person_detections") as batch:
        for column in _BOX_COLUMNS:
            batch.add_column(sa.Column(column, sa.Float(), nullable=True))
        batch.create_check_constraint("ck_photo_person_detections_face_box", _box_condition())
    with op.batch_alter_table("photo_person_corrections") as batch:
        for column in _BOX_COLUMNS:
            batch.add_column(sa.Column(column, sa.Float(), nullable=True))
        batch.add_column(sa.Column("reference_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_photo_person_corrections_reference_id",
            "person_references",
            ["reference_id"],
            ["id"],
        )
        batch.create_unique_constraint("uq_photo_person_corrections_reference_id", ["reference_id"])
        batch.create_check_constraint("ck_photo_person_corrections_face_box", _box_condition())
        batch.create_check_constraint(
            "ck_photo_person_corrections_face_requires_applies", "face_box_x IS NULL OR applies"
        )
        batch.create_check_constraint(
            "ck_photo_person_corrections_reference_requires_face",
            "reference_id IS NULL OR face_box_x IS NOT NULL",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("photo_person_corrections") as batch:
        batch.drop_constraint("ck_photo_person_corrections_reference_requires_face", type_="check")
        batch.drop_constraint("ck_photo_person_corrections_face_requires_applies", type_="check")
        batch.drop_constraint("ck_photo_person_corrections_face_box", type_="check")
        batch.drop_constraint("uq_photo_person_corrections_reference_id", type_="unique")
        batch.drop_constraint("fk_photo_person_corrections_reference_id", type_="foreignkey")
        batch.drop_column("reference_id")
        for column in reversed(_BOX_COLUMNS):
            batch.drop_column(column)
    with op.batch_alter_table("photo_person_detections") as batch:
        batch.drop_constraint("ck_photo_person_detections_face_box", type_="check")
        for column in reversed(_BOX_COLUMNS):
            batch.drop_column(column)
