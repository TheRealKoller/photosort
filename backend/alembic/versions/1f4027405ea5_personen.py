"""personen: vier Tabellen und zwei Zaehlerspalten an `criterion_scoring_runs`

REIN ADDITIV. Keine Zeile wird geloescht, kein bestehender Wert geaendert, nichts nachgezogen:
Bestehende Projekte bekommen ihre Namen mit dem naechsten Klassifizierungslauf, und bestehende
Laeufe behalten `persons_photos_total/_processed = NULL` ("die Phase lief nicht").

* `persons` - global, ohne Projektbezug. `slot IN (1, 2)` mit `UNIQUE(slot)` und
  `UNIQUE(name_key)` machen "hoechstens zwei" und "kein Name doppelt" auch bei gleichzeitigen
  Anlagen strukturell wahr.
* `person_references` - Merkmal eines gezeigten Gesichts; KEIN Fremdschluessel auf Foto oder
  Projekt, damit eine Projektloeschung die Festlegung nicht beruehrt.
* `photo_person_detections` - nur das Paar (Foto, Person), kein Wert, keine Box, kein Merkmal.
* `photo_person_corrections` - `UNIQUE(photo_id, person_id)` OHNE `user_id`; `user_id` ist Audit.

Alle Fremdschluessel sind echt und benannt (`Base.metadata` traegt keine `naming_convention`):
Ein Schreiben der Phase nach einer Personenloeschung scheitert daran, statt eine verwaiste Zeile
zu hinterlassen.

`downgrade()` entfernt Tabellen und Spalten. Es verliert Personen, gezeigte Gesichter,
Erkennungen und Korrekturen; nur die Erkennungen sind durch einen erneuten Lauf wiederherstellbar.

Revision ID: 1f4027405ea5
Revises: 2c5472d41548
Create Date: 2026-09-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f4027405ea5"
down_revision: Union[str, Sequence[str], None] = "2c5472d41548"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        # NFC + casefold des Namens - der Vergleichsschluessel gegen doppelte Namen.
        sa.Column("name_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("slot IN (1, 2)", name="ck_persons_slot"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot", name="uq_persons_slot"),
        sa.UniqueConstraint("name_key", name="uq_persons_name_key"),
    )
    op.create_table(
        "person_references",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("model_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["person_id"], ["persons.id"], name="fk_person_references_person_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "photo_person_detections",
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["photo_id"], ["photos.id"], name="fk_photo_person_detections_photo_id"
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["persons.id"], name="fk_photo_person_detections_person_id"
        ),
        sa.PrimaryKeyConstraint("photo_id", "person_id"),
    )
    op.create_table(
        "photo_person_corrections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("applies", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["photo_id"], ["photos.id"], name="fk_photo_person_corrections_photo_id"
        ),
        sa.ForeignKeyConstraint(
            ["person_id"], ["persons.id"], name="fk_photo_person_corrections_person_id"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_photo_person_corrections_user_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "photo_id", "person_id", name="uq_photo_person_correction_photo_person"
        ),
    )
    with op.batch_alter_table("criterion_scoring_runs") as batch:
        batch.add_column(sa.Column("persons_photos_total", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("persons_photos_processed", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("criterion_scoring_runs") as batch:
        batch.drop_column("persons_photos_processed")
        batch.drop_column("persons_photos_total")
    op.drop_table("photo_person_corrections")
    op.drop_table("photo_person_detections")
    op.drop_table("person_references")
    op.drop_table("persons")
