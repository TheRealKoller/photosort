"""motivstaerken: die drei neuen Tabellen des Motiv-Staerkevektors

Rein additiv - keine bestehende Tabelle und keine bestehende Spalte wird angefasst. Die
Kategorie-Welt (`photo_category_classifications`, `photo_rankings.category_key`/`.is_primary`,
`photo_scores.category_override`) bleibt vollstaendig stehen und faellt erst in einer spaeteren
Migration.

a) `photo_motif_assessments` - die Kopfzeile je Foto (1:1, `photo_id` ist Primary Key UND
   Fremdschluessel). `excluded_document` ist NOT NULL und traegt BEWUSST KEINEN Default, damit ein
   Schreibpfad, der die Spalte vergisst, laut scheitert statt still ein Foto aus jeder
   Motivauswahl zu nehmen.
b) `photo_motif_strengths` - acht Staerkezeilen je Kopfzeile. Der Fremdschluessel zeigt auf
   `photo_motif_assessments.photo_id` und NICHT auf `photos.id`: eine Staerke kann ohne Kopfzeile
   nicht existieren.
c) `photo_motif_corrections` - Foto x Motiv x zutreffend/nicht zutreffend. Haengt an `photos` und
   `users` und an KEINEM Lauf; der Unique-Constraint lautet `(photo_id, motif_key)` ohne
   `user_id`.
d) KEIN Backfill. Bestandsfotos bleiben ohne Kopfzeile, bis der Nutzer selbst klassifiziert:
   Staerken aus `detected_category_confidences` abzuleiten waere eine Modellaussage, die das
   Modell nie getroffen hat, und ein automatisch ausgeloester Lauf waeren ungefragte Cloud-Kosten.

ACHTUNG - `downgrade()` stellt die STRUKTUR wieder her, nie die Daten.

Es entfernt die drei Tabellen. Ein Bestand an Motivstaerken und an Korrekturen ist danach
unwiederbringlich fort; der Rueckweg legt sie nicht wieder an und rekonstruiert sie aus nichts.
Das ist festgeschriebenes Verhalten, kein Versehen.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-09-12 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Explizite Constraint-Namen: `Base.metadata` traegt keine `naming_convention`, aus der einer
# entstuende, und ein unbenannter Constraint ist im `downgrade()` nicht droppbar. Fuer die
# Unique-Constraints ist der Name zusaetzlich Gegenstand eines Tests - die Modellseite nennt
# dieselben.
_ASSESSMENT_PHOTO_FK = "fk_photo_motif_assessments_photo_id"
_STRENGTH_ASSESSMENT_FK = "fk_photo_motif_strengths_photo_id"
_CORRECTION_PHOTO_FK = "fk_photo_motif_corrections_photo_id"
_CORRECTION_USER_FK = "fk_photo_motif_corrections_user_id"


def upgrade() -> None:
    """Upgrade schema."""
    # a) Die Kopfzeile. `source` als laengenbegrenzter String statt eines PostgreSQL-ENUM-Typs -
    # dasselbe Muster wie ueberall im Projekt (`SQLEnum(..., native_enum=False)`), damit ein
    # weiterer Wert keine Typmigration erzwingt.
    op.create_table(
        "photo_motif_assessments",
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("excluded_document", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], name=_ASSESSMENT_PHOTO_FK),
        sa.PrimaryKeyConstraint("photo_id"),
    )

    # b) Die Staerkezeilen. `Float` statt `Numeric`: SQLite kennt den Unterschied zu INTEGER nicht,
    # unter Postgres muss die Spalte `double precision` sein - ein `Integer` schnitte jede Staerke
    # auf 0 oder 1 ab, und genau das faellt in der SQLite-Suite nicht auf.
    op.create_table(
        "photo_motif_strengths",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("motif_key", sa.String(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["photo_id"],
            ["photo_motif_assessments.photo_id"],
            name=_STRENGTH_ASSESSMENT_FK,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("photo_id", "motif_key", name="uq_motif_strength_photo_key"),
    )

    # c) Die Korrekturen - lauf-unabhaengig, mit `user_id` als AUDITFELD ausserhalb des
    # Unique-Constraints.
    op.create_table(
        "photo_motif_corrections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("motif_key", sa.String(), nullable=False),
        sa.Column("applies", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], name=_CORRECTION_PHOTO_FK),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=_CORRECTION_USER_FK),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("photo_id", "motif_key", name="uq_motif_correction_photo_key"),
    )

    # d) Kein Backfill - siehe Modul-Docstring.


def downgrade() -> None:
    """Downgrade schema.

    Stellt die STRUKTUR wieder her, nie die Daten: die Motivstaerken und die Korrekturen sind
    danach fort und kommen nicht zurueck. Ohne diesen Satz sieht ein `downgrade` wie eine
    Ruecknahme aus.

    Die Reihenfolge ist Teil der Aussage: die Staerkezeilen haengen an der Kopfzeile und muessen
    vor ihr fallen, sonst bricht der Rueckweg an einer echten Datenbank an der
    Fremdschluesselbedingung ab."""
    op.drop_table("photo_motif_corrections")
    op.drop_table("photo_motif_strengths")
    op.drop_table("photo_motif_assessments")
