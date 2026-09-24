"""sehenswuerdigkeitsauskunft: neue Tabelle `landmark_place_lookups`

REIN ADDITIV. Keine Zeile wird geloescht, kein bestehender Wert geaendert, und es wird NICHTS
nachgezogen: Bestehende Laeufe behalten ihre Eventnamen bis zur Neuberechnung. Das ist eine Zusage
und keine Auslassung - ein nachtraeglich eingesetzter Name haette die Ortsplausibilitaetspruefung
dieser Spec nie durchlaufen.

`landmark_place_lookups` traegt die Auskunft ueber die Fundorte eines gefalteten
Sehenswuerdigkeitsnamens, projektgebunden und lauf-unabhaengig. Der Fremdschluessel auf
`projects.id` ist ECHT und NOT NULL: an ihm haengt die Zusage, dass diese Namensspur mit dem
Projekt verschwindet - eine bloss logische Spalte fiele aus der Erreichbarkeitspruefung der
Projektloeschung still heraus.

Die Spalte `points` ist NICHT nullbar und darf LEER sein (ADR 0123 Punkt 2). Nur so sind die drei
Zustaende der Auskunft auseinanderzuhalten: keine Zeile heisst "nie nachgeschlagen" (fail-open,
der Name bleibt), eine leere Liste "nachgeschlagen, ohne Fund" (der Name faellt), gefuellte Liste
"nachgeschlagen, mit Fund" (der Name bleibt, wenn ein Fundort im Umkreis liegt). Waere die Spalte
nullbar, fielen die beiden ersten Zustaende zusammen und ein Lauf ohne Auszug verwuerfe jeden
Namen (S4).

`UniqueConstraint(project_id, folded_name)` traegt die Wiederverwendung: ein Name wird je Projekt
genau einmal nachgeschlagen. `project_id` steht bewusst IM Constraint - derselbe Name in einem
zweiten Projekt ist eine eigene Zeile und wird erneut gefragt.

KEINE Spalte fuer eine Entfernung, ein Pruefergebnis oder eine `event_id` (S1): eine persistierte
Entfernung machte aus einer Namensauskunft eine Aufenthaltsaussage mit feinerer Koerung, als
`PLACE_CELL_DIGITS = 2` sie zusichert.

`downgrade()` entfernt die Tabelle. Es verliert die abgelegten Auskuenfte; sie sind
wiederherstellbar (erneuter Durchgang durch den zweiten Auszug, lokale Rechenzeit, kein Geld).

Revision ID: 2c5472d41548
Revises: c5bc9a02c3c2
Create Date: 2026-09-24 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2c5472d41548"
down_revision: Union[str, Sequence[str], None] = "c5bc9a02c3c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Explizite Constraint-Namen, wie in `d7e8f9a0b1c2_ortsauskunft.py`: `Base.metadata` traegt keine
# `naming_convention`, aus der einer entstuende.
_LANDMARK_LOOKUP_PROJECT_FK = "fk_landmark_place_lookups_project_id"
_LANDMARK_LOOKUP_NAME_UNIQUE = "uq_landmark_place_lookup_project_name"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "landmark_place_lookups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        # Der gefaltete Suchschluessel (`geonames.py::fold_landmark_name`) - dieselbe Faltung auf
        # Schreib- und Leseseite.
        sa.Column("folded_name", sa.String(), nullable=False),
        # JSON-Liste von `[lat, lon]` - NICHT nullbar, leer erlaubt (drei Zustaende der Auskunft).
        sa.Column("points", sa.JSON(), nullable=False),
        sa.Column("looked_up_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=_LANDMARK_LOOKUP_PROJECT_FK),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "folded_name", name=_LANDMARK_LOOKUP_NAME_UNIQUE),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("landmark_place_lookups")
