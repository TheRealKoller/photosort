"""eye: Schattentabellen der dritten Klassifizierungsgrundlage und der Laufmodus

Spec 0609 / ADR 0138 Punkt 4 und 6. Vier Festlegungen tragen die Form:

* `photo_eye_results` ist die Kopfzeile je Foto (`photo_id` ist Primary Key) und traegt die drei
  Aussagen, die Eye vom Cloud-Pfad unterscheiden: `excluded_document` NOT NULL **ohne** jeden
  Default (ein Schreibpfad, der die Spalte vergisst, scheitert laut, statt still ein Foto aus jeder
  Motivauswahl zu nehmen), `album_level` als 1..5, `model_revision`. `provider` steht bewusst
  NICHT hier - Eye ist kein Cloud-Anbieter, ein Anbieterwert behauptete einen Kontakt, der nicht
  stattfand.
* `photo_eye_motif_strengths` und `photo_eye_fine_labels` haengen an `photo_eye_results`, nicht an
  `photos`: eine Schattenzeile kann ohne Kopfzeile nicht existieren, und ein neuer Eye-Lauf
  ersetzt den ganzen Satz.
* `photo_local_motif_snapshots` (+ `_strengths`) halten den lokalen Vektor, den Eye verdraengt hat.
  Ohne ihn koennte ein Ausbau das lokale Ergebnis nicht wiederherstellen (ADR 0138 Punkt 5).
* `criterion_scoring_runs` bekommt `mode` NULLABLE (Altzeilen bleiben `NULL` und werden nie
  nachtraeglich einem Weg zugeschlagen) sowie die beiden Eye-Zaehler nach dem Muster `persons_*`:
  `NULL` heisst "Phase lief nicht", nie "null Fotos".

Rein additiv - keine bestehende Zeile wird gelesen oder umgeschrieben.

Revision ID: 8cf920dd03b4
Revises: 0b9d6f8d620b
Create Date: 2026-11-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8cf920dd03b4"
down_revision: Union[str, Sequence[str], None] = "0b9d6f8d620b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - legt die fuenf Tabellen an und ergaenzt drei Spalten am Lauf."""
    op.create_table(
        "photo_eye_results",
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("excluded_document", sa.Boolean(), nullable=False),
        sa.Column("album_level", sa.Integer(), nullable=False),
        sa.Column("model_revision", sa.String(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("photo_id"),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], name="fk_photo_eye_results_photo_id"),
        sa.CheckConstraint("album_level BETWEEN 1 AND 5", name="ck_photo_eye_results_album_level"),
    )
    op.create_table(
        "photo_eye_motif_strengths",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("motif_key", sa.String(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["photo_id"],
            ["photo_eye_results.photo_id"],
            name="fk_photo_eye_motif_strengths_photo_id",
        ),
        sa.UniqueConstraint("photo_id", "motif_key", name="uq_eye_motif_strength_photo_key"),
    )
    op.create_table(
        "photo_eye_fine_labels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["photo_id"],
            ["photo_eye_results.photo_id"],
            name="fk_photo_eye_fine_labels_photo_id",
        ),
        sa.UniqueConstraint("photo_id", "label", name="uq_eye_fine_label_photo_label"),
    )
    op.create_table(
        "photo_local_motif_snapshots",
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("excluded_document", sa.Boolean(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("photo_id"),
        sa.ForeignKeyConstraint(
            ["photo_id"], ["photos.id"], name="fk_photo_local_motif_snapshots_photo_id"
        ),
    )
    op.create_table(
        "photo_local_motif_snapshot_strengths",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("motif_key", sa.String(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["photo_id"],
            ["photo_local_motif_snapshots.photo_id"],
            name="fk_photo_local_motif_snapshot_strengths_photo_id",
        ),
        sa.UniqueConstraint("photo_id", "motif_key", name="uq_local_snapshot_strength_photo_key"),
    )
    with op.batch_alter_table("criterion_scoring_runs") as batch:
        batch.add_column(sa.Column("mode", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("eye_photos_total", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("eye_photos_processed", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema.

    Die Struktur wird wiederhergestellt, nie die Daten: Saemtliche Eye-Schattenergebnisse, die
    Modellrevisionen, die Albumstufen der Eye-Auswertung und die zurueckgelegten LOKALEN
    Motivvektoren sind danach fort. Der Rueckbau einer Eye-Kopfzeile (eigene Story) muss deshalb
    VOR dieser Migration gelaufen sein; danach steht kein lokales Ergebnis mehr zur Verfuegung,
    das an ihre Stelle treten koennte. Der Laufmodus und die Eye-Zaehler vergangener Laeufe gehen
    ebenfalls verloren - die Cloud- und lokalen Ergebnisse selbst bleiben unberuehrt."""
    with op.batch_alter_table("criterion_scoring_runs") as batch:
        batch.drop_column("eye_photos_processed")
        batch.drop_column("eye_photos_total")
        batch.drop_column("mode")
    op.drop_table("photo_local_motif_snapshot_strengths")
    op.drop_table("photo_local_motif_snapshots")
    op.drop_table("photo_eye_fine_labels")
    op.drop_table("photo_eye_motif_strengths")
    op.drop_table("photo_eye_results")
