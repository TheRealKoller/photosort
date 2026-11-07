"""Klassifizierungspruefung: sechs eigene Tabellen fuer den A/B-Prueflauf

Spec 0616 / ADR 0139 Punkt 3. Fuenf Festlegungen tragen die Form:

* `classification_reviews` ist der Lauf (Projekt, anlegender Nutzer, `ScanStatus`, Teilschritt,
  Pruefgroesse JE ZWECK, Seed, Fotozahlen, Fortschritts-Watchdog, Zeitpunkte, Fehlermeldung). Der
  Teilschritt ist `NULL`, sobald der Lauf beendet ist - deshalb nullable.
* `classification_review_sides` haengt mit zusammengesetztem Primaerschluessel an der Pruefung
  (`a`/`b`) und traegt die beim Anlegen GESPEICHERTE Herkunft, die eingefrorene Schaetzung und die
  Ist-Kosten im Idiom der Remote-Laeufe (`NULL` = nicht erfasst).
* `classification_review_results` haengt an Pruefung, Seite und Foto; `excluded_document` und
  `album_level` sind NULLBAR, weil `NULL` hier "das Verfahren sagt dazu nichts" heisst. Die
  Staerkezeilen tragen alle acht Motive und haengen an DERSELBEN zusammengesetzten Kennung, nicht
  an `photos`.
* `classification_review_cases` speichert die **Fotoposition** einmal, dazu Zweck und `motif_key`
  (nur bei `motif_feature`); eindeutig je Pruefung, Foto, Zweck und Merkmal - fuer die drei
  fotozzaehlenden Zwecke ueber einen Teilindex `WHERE motif_key IS NULL`.
* `classification_review_verdicts` hat den Fall als Primaerschluessel - genau EIN Urteil je Fall,
  nicht eines je Nutzer - und fuehrt den Schreiber als Auditfeld.

Rein additiv: keine bestehende Tabelle wird gelesen, umgeschrieben oder ergaenzt.

Revision ID: 44ba5fe0184a
Revises: 8cf920dd03b4
Create Date: 2026-11-07 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "44ba5fe0184a"
down_revision: Union[str, Sequence[str], None] = "8cf920dd03b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - legt die sechs Tabellen in Fremdschluessel-Reihenfolge an."""
    op.create_table(
        "classification_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING", "SUCCESS", "FAILED", name="scanstatus", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column(
            "phase",
            sa.Enum(
                "SIDE_A",
                "SIDE_B",
                "CASES",
                name="reviewphase",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("photo_count", sa.Integer(), nullable=False),
        sa.Column("photos_processed", sa.Integer(), nullable=False),
        sa.Column("unclassifiable_photo_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "last_progress_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_classification_reviews_project_id"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_classification_reviews_created_by_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "classification_review_sides",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=1), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "CLOUD",
                "EYE",
                "LOCAL",
                name="classificationreviewsidekind",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("eye_model_revision", sa.String(), nullable=True),
        sa.Column("eye_mapping_version", sa.String(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("api_calls", sa.Integer(), nullable=True),
        sa.Column("failed_calls", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["classification_reviews.id"],
            name="fk_classification_review_sides_review_id",
        ),
        sa.PrimaryKeyConstraint("review_id", "side"),
    )
    op.create_table(
        "classification_review_results",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=1), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("excluded_document", sa.Boolean(), nullable=True),
        sa.Column("album_level", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["classification_reviews.id"],
            name="fk_classification_review_results_review_id",
        ),
        sa.ForeignKeyConstraint(
            ["photo_id"], ["photos.id"], name="fk_classification_review_results_photo_id"
        ),
        sa.PrimaryKeyConstraint("review_id", "side", "photo_id"),
    )
    op.create_table(
        "classification_review_result_strengths",
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=1), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("motif_key", sa.String(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id", "side", "photo_id"],
            [
                "classification_review_results.review_id",
                "classification_review_results.side",
                "classification_review_results.photo_id",
            ],
            name="fk_classification_review_result_strengths_result",
        ),
        sa.PrimaryKeyConstraint("review_id", "side", "photo_id", "motif_key"),
    )
    op.create_table(
        "classification_review_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("photo_id", sa.Integer(), nullable=False),
        sa.Column("photo_position", sa.Integer(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum(
                "MOTIFS",
                "MOTIF_FEATURE",
                "EXCLUDED_DOCUMENT",
                "ALBUM_LEVEL",
                name="classificationreviewpurpose",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("motif_key", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["classification_reviews.id"],
            name="fk_classification_review_cases_review_id",
        ),
        sa.ForeignKeyConstraint(
            ["photo_id"], ["photos.id"], name="fk_classification_review_cases_photo_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_id",
            "photo_id",
            "purpose",
            "motif_key",
            name="uq_classification_review_case_review_photo_purpose_motif",
        ),
    )
    # Die drei fotozzaehlenden Zwecke tragen `motif_key = NULL`; ein einfaches UNIQUE behandelt
    # NULL je Zeile als verschieden, deshalb sichert der Teilindex die Eindeutigkeit fuer sie.
    op.create_index(
        "uq_classification_review_case_review_photo_purpose_counted",
        "classification_review_cases",
        ["review_id", "photo_id", "purpose"],
        unique=True,
        sqlite_where=sa.text("motif_key IS NULL"),
        postgresql_where=sa.text("motif_key IS NULL"),
    )
    op.create_table(
        "classification_review_verdicts",
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column(
            "verdict",
            sa.Enum(
                "A_BETTER",
                "B_BETTER",
                "BOTH_OK",
                "BOTH_WRONG",
                name="classificationverdict",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["classification_review_cases.id"],
            name="fk_classification_review_verdicts_case_id",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name="fk_classification_review_verdicts_updated_by_user_id",
        ),
        sa.PrimaryKeyConstraint("case_id"),
    )


def downgrade() -> None:
    """Downgrade schema.

    Die Struktur wird wiederhergestellt, nie die Daten: Saemtliche Pruefungen, ihre Seiten,
    Ergebnisse, Faelle und Urteile sind danach fort. Die geltenden Ergebnisse der Fotos sind davon
    nicht beruehrt - die Pruefung hat nie in ihre Tabellen geschrieben."""
    op.drop_table("classification_review_verdicts")
    op.drop_table("classification_review_cases")
    op.drop_table("classification_review_result_strengths")
    op.drop_table("classification_review_results")
    op.drop_table("classification_review_sides")
    op.drop_table("classification_reviews")
