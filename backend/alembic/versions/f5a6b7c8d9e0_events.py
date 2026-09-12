"""events: neue Tabelle `events`, `photo_rankings.cluster_key` -> `event_id`

Drei Teile:

a) Neue Tabelle `events` (je Zeile ein Event eines CriterionScoringRun), mit echtem
   Fremdschluessel auf `criterion_scoring_runs` und `UniqueConstraint(run, position)`.
b) `DELETE FROM photo_rankings` - ALLE Zeilen.
c) `photo_rankings`: `event_id` (echter Fremdschluessel, NOT NULL) ergaenzt, `cluster_key`
   entfernt.

ACHTUNG - DIESE MIGRATION LOESCHT DATEN, UND ZWAR UNUMKEHRBAR.

Fuer Laeufe von vor dieser Migration werden KEINE Events angelegt: es gibt keine Gliederung, aus
der sie entstehen koennten, ohne die gesamte Event-Bildung samt projektweiter Ortsherleitung in
der Migration nachzubauen. Ihre Rangzeilen fallen deshalb weg; die Kuratierung zeigt fuer einen
solchen Lauf nichts, bis er neu berechnet wird. Genau das traegt die NOT-NULL-Zusage von
`event_id` - ohne die Loeschung braeuchte der Lesepfad dauerhaft einen Ausnahmezweig fuer einen
Zustand, den die Anwendung selbst nie erzeugt.

Die LAUF-Zeilen (`criterion_scoring_runs`) bleiben unangetastet: sie tragen die Ist-Kosten der
Cloud-Aufrufe, und die sind nicht wiederherstellbar. Rangzeilen sind es - ein erneuter
Kriterien-Lauf liest die bereits persistierten Erkennungen und kostet lokale Rechenzeit, kein
Geld.

`downgrade()` stellt die SPALTENFORM wieder her, holt die geloeschten Rangzeilen aber NICHT
zurueck. Das ist festgeschriebenes Verhalten, kein Versehen: die Werte existieren nach dem
`DELETE` nirgends mehr.

KEIN Nachziehen bestehender Gruppen und KEINE Namen aus `photo_landmark_detections` in die neue
Spalte - `events.landmark_name` entsteht ausschliesslich im Worker ueber
`sanitize_landmark_name`.

Revision ID: f5a6b7c8d9e0
Revises: d1e2f3a4b5c6
Create Date: 2026-09-12 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Explizite Constraint-Namen: ein per `batch_alter_table` UNBENANNT angelegter Fremdschluessel ist
# im `downgrade()` unter SQLite nicht droppbar, und `Base.metadata` traegt keine
# `naming_convention`, aus der einer entstuende.
_EVENT_RUN_FK = "fk_events_criterion_scoring_run_id"
_RANKING_EVENT_FK = "fk_photo_rankings_event_id"


def upgrade() -> None:
    """Upgrade schema."""
    # a)
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("criterion_scoring_run_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=False),
        sa.Column("landmark_name", sa.String(), nullable=True),
        sa.Column("place_kind", sa.String(), nullable=True),
        sa.Column("place_lat", sa.Float(), nullable=True),
        sa.Column("place_lon", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["criterion_scoring_run_id"], ["criterion_scoring_runs.id"], name=_EVENT_RUN_FK
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("criterion_scoring_run_id", "position", name="uq_event_run_position"),
    )

    # b) VOR dem Spaltentausch: eine NOT-NULL-Spalte laesst sich nur einer LEEREN Tabelle ohne
    # Ersatzwert hinzufuegen, und einen Ersatzwert gaebe es hier nicht (jede Event-Id waere
    # erfunden).
    op.execute(sa.text("DELETE FROM photo_rankings"))

    # c)
    with op.batch_alter_table("photo_rankings") as batch:
        batch.add_column(sa.Column("event_id", sa.Integer(), nullable=False))
        batch.create_foreign_key(_RANKING_EVENT_FK, "events", ["event_id"], ["id"])
        batch.drop_column("cluster_key")


def downgrade() -> None:
    """Downgrade schema.

    Stellt den AUSGANGSZUSTAND wieder her, nicht nur die Spaltenform: `cluster_key` entstand in
    `c1d2e3f4a5b6` als `nullable=False` OHNE `server_default`, und genau so steht sie danach
    wieder da. Ein zurueckbliebener Default machte aus jedem Schreibpfad, der die Spalte vergisst,
    ein stilles `''` statt eines lauten NOT-NULL-Fehlers - dieselbe Ausfallrichtung, die
    `PhotoRanking.is_primary` zwei Spalten weiter ausdruecklich ablehnt.

    Die in `upgrade()` geloeschten Rangzeilen kommen NICHT zurueck - sie sind unwiederbringlich
    fort, und ein erneuter Kriterien-Lauf ist der einzige Weg zu neuen."""
    # ZWEI Batch-Bloecke, nie einer (Muster aus `c9d0e1f2a3b4_nebenkategorien.py`):
    # `batch_alter_table` fasst unter SQLite alle Operationen eines Blocks zu EINEM
    # Tabellen-Neuaufbau zusammen. Stuenden `add_column` und das Entfernen des Defaults im selben
    # Block, haette die neu gebaute Tabelle von vornherein keinen Default - und das
    # `INSERT ... SELECT` des Altbestands scheiterte an der NOT-NULL-Bedingung. Der Default muss
    # beim ersten Aufbau existieren und beim zweiten verschwinden.
    with op.batch_alter_table("photo_rankings") as batch:
        batch.add_column(sa.Column("cluster_key", sa.String(), nullable=False, server_default=""))
        batch.drop_constraint(_RANKING_EVENT_FK, type_="foreignkey")
        batch.drop_column("event_id")

    with op.batch_alter_table("photo_rankings") as batch:
        batch.alter_column("cluster_key", existing_type=sa.String(), server_default=None)

    op.drop_table("events")
