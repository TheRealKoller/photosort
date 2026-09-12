"""kamera_zeitversatz: neue Tabelle `project_cameras`, drei neue Spalten an `photos`

Vier Teile:

a) Neue Tabelle `project_cameras` (je Zeile eine Kamera EINES Projekts samt ihrem Versatz), mit
   echtem Fremdschluessel auf `projects` und `UniqueConstraint(project_id, make, model)`.
b) `photos.taken_at_original` - zuerst nullable ergaenzt, dann je Zeile aus ihrem EIGENEN
   `taken_at` gefuellt, dann auf NOT NULL gesetzt.
c) `photos.camera_id` (echter, nullabler Fremdschluessel) und `photos.camera_probed`
   (NOT NULL, `false` fuer Bestandszeilen).
d) KEIN Backfill der Kamera: das erledigt der naechste Scan ueber `camera_probed`.

Die Kopie in b) entsteht zu einem Zeitpunkt, an dem es noch keinen Versatz gibt - `taken_at` ist
hier also beweisbar noch die AUFGEZEICHNETE Zeit, und die Kopie ist damit der richtige Wert. Ab
dieser Migration dreht sich die Bedeutung von `photos.taken_at`: es traegt danach die KORRIGIERTE
Zeit (ADR 0088, Punkt 1).

ACHTUNG - `downgrade()` VERLIERT DIE VERSAETZE UNUMKEHRBAR.

Es schreibt `taken_at = taken_at_original` ZURUECK, BEVOR es die Spalten und die Tabelle
entfernt. Ohne diesen Schritt behielte die Datenbank die korrigierten Zeiten, und die
aufgezeichneten waeren unwiederbringlich fort - `taken_at_original` ist ihre einzige Kopie. Die
gesetzten Versaetze selbst kommen nach dem Rueckweg NICHT zurueck; die rohen Zeiten stehen.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-09-12 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Explizite Constraint-Namen: ein per `batch_alter_table` UNBENANNT angelegter Fremdschluessel ist
# im `downgrade()` unter SQLite nicht droppbar, und `Base.metadata` traegt keine
# `naming_convention`, aus der einer entstuende. `fk_photos_camera_id` ist zudem nur im
# Postgres-Render ueberhaupt sichtbar - ohne den expliziten Namen ist der Rueckweg nicht
# ausfuehrbar.
_CAMERA_PROJECT_FK = "fk_project_cameras_project_id"
_PHOTO_CAMERA_FK = "fk_photos_camera_id"


def upgrade() -> None:
    """Upgrade schema."""
    # a)
    op.create_table(
        "project_cameras",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("make", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("offset_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=_CAMERA_PROJECT_FK),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "make", "model", name="uq_project_camera_make_model"),
    )

    # b) In DREI Schritten, nicht in einem: eine NOT-NULL-Spalte ohne Ersatzwert laesst sich nur
    # einer LEEREN Tabelle hinzufuegen, und einen tabellenweiten Ersatzwert gaebe es hier nicht -
    # jede Zeile braucht IHREN EIGENEN `taken_at`-Wert.
    op.add_column("photos", sa.Column("taken_at_original", sa.DateTime(), nullable=True))
    op.execute(sa.text("UPDATE photos SET taken_at_original = taken_at"))
    # `batch_alter_table`, sonst scheitert SQLite: es kennt kein `ALTER COLUMN ... SET NOT NULL`
    # und braucht den Tabellen-Neuaufbau.
    with op.batch_alter_table("photos") as batch:
        batch.alter_column("taken_at_original", existing_type=sa.DateTime(), nullable=False)

    # c) `server_default` fuer `camera_probed` als BOOLEAN-Literal, nicht als `0`: SQLite
    # akzeptiert `DEFAULT 0` auf einer Boolean-Spalte klaglos, Postgres bricht mit
    # `DatatypeMismatch` ab. Der Default fuellt zugleich die Bestandszeilen mit `false` - sie sind
    # genau die, die der naechste Scan nachholt.
    with op.batch_alter_table("photos") as batch:
        batch.add_column(sa.Column("camera_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "camera_probed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.create_foreign_key(_PHOTO_CAMERA_FK, "project_cameras", ["camera_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema.

    Die Reihenfolge ist die eigentliche Aussage: das Zurueckschreiben der aufgezeichneten Zeiten
    steht VOR dem Entfernen der Spalte, aus der sie kommen. Umgekehrt behielte die Datenbank die
    korrigierten Zeiten als seien sie die aufgezeichneten, und die echten waeren fort.

    Die gesetzten Versaetze kommen NICHT zurueck - sie existieren nach dem `drop_table` nirgends
    mehr. Das ist festgeschriebenes Verhalten, kein Versehen: der Rueckweg stellt die rohen Zeiten
    und die Spaltenform wieder her, nicht die Einstellungen."""
    op.execute(sa.text("UPDATE photos SET taken_at = taken_at_original"))

    with op.batch_alter_table("photos") as batch:
        batch.drop_constraint(_PHOTO_CAMERA_FK, type_="foreignkey")
        batch.drop_column("camera_probed")
        batch.drop_column("camera_id")
        batch.drop_column("taken_at_original")

    op.drop_table("project_cameras")
